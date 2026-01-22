"""
Slave module for FlowPipeLine Multi-Machine GPU Monitoring System

This module runs on slave machines and:
1. Collects GPU information (usage, memory, temperature, power, processes)
2. Collects system information (CPU model, memory usage, swap usage)
3. Reports to the master server periodically
"""

import json
import time
import threading
import socket
import platform
import os
import psutil
from flask import Flask, jsonify
from flask_cors import CORS

try:
    import pynvml
    HAS_PYNVML = True
except ImportError:
    HAS_PYNVML = False

from flowline.utils import Log

logger = Log(__name__)

# Configurable constants
CPU_MEASURE_INTERVAL = 0.1  # seconds for CPU usage measurement
CMDLINE_MAX_ARGS = 5  # max number of cmdline arguments to display
def get_cpu_model():
    """Get CPU model name"""
    try:
        if platform.system() == "Linux":
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":")[1].strip()
        elif platform.system() == "Windows":
            import subprocess
            result = subprocess.run(["wmic", "cpu", "get", "name"], capture_output=True, text=True)
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                return lines[1].strip()
        return platform.processor() or "Unknown CPU"
    except Exception as e:
        logger.error(f"Error getting CPU model: {e}")
        return "Unknown CPU"


def get_system_info():
    """Collect system information"""
    try:
        # Memory info
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        system_info = {
            "hostname": socket.gethostname(),
            "cpu_model": get_cpu_model(),
            "cpu_cores": os.cpu_count(),
            "cpu_usage": psutil.cpu_percent(interval=CPU_MEASURE_INTERVAL),
            "memory": {
                "total": round(mem.total / (1024 ** 3), 2),  # GB
                "used": round(mem.used / (1024 ** 3), 2),    # GB
                "available": round(mem.available / (1024 ** 3), 2),  # GB
                "percent": mem.percent
            },
            "swap": {
                "total": round(swap.total / (1024 ** 3), 2),  # GB
                "used": round(swap.used / (1024 ** 3), 2),    # GB
                "free": round(swap.free / (1024 ** 3), 2),    # GB
                "percent": swap.percent
            },
            "os": f"{platform.system()} {platform.release()}"
        }
        return system_info
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return {}


def get_gpu_processes(handle):
    """Get processes running on a GPU"""
    processes = []
    try:
        proc_infos = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
        for proc in proc_infos:
            try:
                p = psutil.Process(proc.pid)
                processes.append({
                    "pid": proc.pid,
                    "name": p.name(),
                    "username": p.username(),
                    "memory_mb": round(proc.usedGpuMemory / (1024 ** 2), 1) if proc.usedGpuMemory else 0,
                    "cmdline": " ".join(p.cmdline()[:CMDLINE_MAX_ARGS]) if p.cmdline() else ""
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                processes.append({
                    "pid": proc.pid,
                    "name": "Unknown",
                    "username": "Unknown",
                    "memory_mb": round(proc.usedGpuMemory / (1024 ** 2), 1) if proc.usedGpuMemory else 0,
                    "cmdline": ""
                })
    except Exception as e:
        logger.error(f"Error getting GPU processes: {e}")
    return processes


def get_gpu_info():
    """Collect GPU information"""
    gpus = []
    
    if not HAS_PYNVML:
        logger.warning("pynvml not available, returning empty GPU list")
        return gpus
    
    try:
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            
            # Get memory info
            memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            
            # Get utilization
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            
            # Get temperature
            temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            
            # Get power
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000  # mW to W
            except pynvml.NVMLError:
                power = 0
            
            try:
                max_power = pynvml.nvmlDeviceGetPowerManagementLimit(handle) / 1000  # mW to W
            except pynvml.NVMLError:
                max_power = 0
            
            # Get name
            gpu_name = pynvml.nvmlDeviceGetName(handle)
            name = gpu_name.decode('utf-8') if isinstance(gpu_name, bytes) else gpu_name
            
            # Get processes
            processes = get_gpu_processes(handle)
            
            gpus.append({
                "id": i,
                "name": name,
                "memory": {
                    "total": round(memory_info.total / (1024 ** 2), 1),  # MB
                    "used": round(memory_info.used / (1024 ** 2), 1),   # MB
                    "free": round(memory_info.free / (1024 ** 2), 1)    # MB
                },
                "utilization": utilization.gpu,
                "temperature": temperature,
                "power": {
                    "current": round(power, 1),
                    "max": round(max_power, 1)
                },
                "processes": processes
            })
        
        pynvml.nvmlShutdown()
    except Exception as e:
        logger.error(f"Error getting GPU info: {e}")
    
    return gpus


def collect_all_info():
    """Collect all system and GPU information"""
    return {
        "timestamp": time.time(),
        "system": get_system_info(),
        "gpus": get_gpu_info()
    }


class SlaveServer:
    """Slave server that provides GPU/system info via REST API"""
    
    def __init__(self, config_path=None):
        self.config = self._load_config(config_path)
        self.app = Flask(__name__)
        CORS(self.app)
        self._setup_routes()
    
    def _load_config(self, config_path):
        """Load configuration from file"""
        default_config = {
            "slave_host": "0.0.0.0",
            "slave_port": 5001,
            "master_ip": "192.168.217.190",
            "master_port": 5000,
            "report_interval": 3
        }
        
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        
        return default_config
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/api/info', methods=['GET'])
        def get_info():
            """Return all GPU and system information"""
            return jsonify(collect_all_info())
        
        @self.app.route('/api/health', methods=['GET'])
        def health_check():
            """Health check endpoint"""
            return jsonify({"status": "ok", "timestamp": time.time()})
    
    def run(self, host=None, port=None):
        """Run the slave server"""
        host = host or self.config.get('slave_host', '0.0.0.0')
        port = port or self.config.get('slave_port', 5001)
        
        logger.info(f"Starting slave server on {host}:{port}")
        self.app.run(host=host, port=port, debug=False, threaded=True)


def main():
    """Main entry point for slave server"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FlowPipeLine Slave Server')
    parser.add_argument('--config', '-c', type=str, default='config/slave.json',
                        help='Path to configuration file')
    parser.add_argument('--host', type=str, default=None,
                        help='Host to bind to')
    parser.add_argument('--port', '-p', type=int, default=None,
                        help='Port to bind to')
    
    args = parser.parse_args()
    
    server = SlaveServer(args.config)
    server.run(host=args.host, port=args.port)


if __name__ == '__main__':
    main()
