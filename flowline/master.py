"""
Master module for FlowPipeLine Multi-Machine GPU Monitoring System

This module runs on the master machine and:
1. Collects GPU/system information from slave machines
2. Provides web API for the frontend
3. Manages slave connection status
"""

import json
import time
import threading
import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
import datetime

from flowline.utils import Log

logger = Log(__name__)


class SlaveInfo:
    """Store information about a slave machine"""
    
    def __init__(self, name, ip, port=5001):
        self.name = name
        self.ip = ip
        self.port = port
        self.online = False
        self.last_seen = None
        self.data = None
        self.error = None
    
    def to_dict(self):
        return {
            "name": self.name,
            "ip": self.ip,
            "port": self.port,
            "online": self.online,
            "last_seen": self.last_seen,
            "data": self.data,
            "error": self.error
        }


class MasterServer:
    """Master server that collects info from slaves and serves the frontend"""
    
    def __init__(self, config_path=None):
        self.config = self._load_config(config_path)
        self.slaves = {}
        self._init_slaves()
        
        self.app = Flask(__name__)
        CORS(self.app)
        self._setup_routes()
        
        self.start_time = datetime.datetime.now()
        self._monitor_thread = None
        self._running = False
    
    def _load_config(self, config_path):
        """Load configuration from file"""
        default_config = {
            "master_host": "0.0.0.0",
            "master_port": 5000,
            "slaves": [
                {"name": "Slave-1", "ip": "192.168.217.180"},
                {"name": "Slave-2", "ip": "192.168.217.190"},
                {"name": "Slave-3", "ip": "192.168.217.200"}
            ],
            "slave_port": 5001,
            "refresh_interval": 5
        }
        
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        
        return default_config
    
    def _init_slaves(self):
        """Initialize slave list from config"""
        slave_port = self.config.get('slave_port', 5001)
        for slave_config in self.config.get('slaves', []):
            name = slave_config.get('name', slave_config.get('ip'))
            ip = slave_config.get('ip')
            port = slave_config.get('port', slave_port)
            self.slaves[ip] = SlaveInfo(name, ip, port)
    
    def _fetch_slave_info(self, slave):
        """Fetch information from a single slave"""
        timeout = self.config.get('request_timeout', 3)
        try:
            url = f"http://{slave.ip}:{slave.port}/api/info"
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                slave.data = response.json()
                slave.online = True
                slave.last_seen = time.time()
                slave.error = None
            else:
                slave.online = False
                slave.error = f"HTTP {response.status_code} from {slave.name} ({slave.ip})"
        except requests.exceptions.Timeout:
            slave.online = False
            slave.error = f"Connection timeout to {slave.name} ({slave.ip}:{slave.port})"
        except requests.exceptions.ConnectionError:
            slave.online = False
            slave.error = f"Connection refused by {slave.name} ({slave.ip}:{slave.port})"
        except Exception as e:
            slave.online = False
            slave.error = f"Error from {slave.name}: {str(e)}"
    
    def _monitor_slaves(self):
        """Continuously monitor slave status"""
        while self._running:
            for slave in self.slaves.values():
                self._fetch_slave_info(slave)
            time.sleep(self.config.get('refresh_interval', 5))
    
    def start_monitoring(self):
        """Start the slave monitoring thread"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_slaves)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        logger.info("Slave monitoring started")
    
    def stop_monitoring(self):
        """Stop the slave monitoring thread"""
        self._running = False
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/api/slaves', methods=['GET'])
        def get_slaves():
            """Get all slave information"""
            result = {}
            for ip, slave in self.slaves.items():
                result[ip] = slave.to_dict()
            return jsonify(result)
        
        @self.app.route('/api/slaves/<slave_ip>', methods=['GET'])
        def get_slave(slave_ip):
            """Get single slave information"""
            if slave_ip in self.slaves:
                return jsonify(self.slaves[slave_ip].to_dict())
            return jsonify({"error": "Slave not found"}), 404
        
        @self.app.route('/api/slaves/<slave_ip>/refresh', methods=['POST'])
        def refresh_slave(slave_ip):
            """Force refresh slave information"""
            if slave_ip in self.slaves:
                self._fetch_slave_info(self.slaves[slave_ip])
                return jsonify(self.slaves[slave_ip].to_dict())
            return jsonify({"error": "Slave not found"}), 404
        
        @self.app.route('/api/refresh', methods=['POST'])
        def refresh_all():
            """Force refresh all slaves"""
            for slave in self.slaves.values():
                self._fetch_slave_info(slave)
            return jsonify({"success": True})
        
        @self.app.route('/api/system/uptime', methods=['GET'])
        def get_uptime():
            """Get server uptime"""
            uptime = datetime.datetime.now() - self.start_time
            return jsonify({
                'days': uptime.days,
                'hours': uptime.seconds // 3600,
                'minutes': (uptime.seconds % 3600) // 60,
                'seconds': uptime.seconds % 60
            })
        
        @self.app.route('/api/health', methods=['GET'])
        def health_check():
            """Health check endpoint"""
            online_count = sum(1 for s in self.slaves.values() if s.online)
            return jsonify({
                "status": "ok",
                "timestamp": time.time(),
                "slaves_total": len(self.slaves),
                "slaves_online": online_count
            })
    
    def run(self, host=None, port=None):
        """Run the master server"""
        host = host or self.config.get('master_host', '0.0.0.0')
        port = port or self.config.get('master_port', 5000)
        
        self.start_monitoring()
        
        logger.info(f"Starting master server on {host}:{port}")
        self.app.run(host=host, port=port, debug=False, threaded=True)


def main():
    """Main entry point for master server"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FlowPipeLine Master Server')
    parser.add_argument('--config', '-c', type=str, default='config/master.json',
                        help='Path to configuration file')
    parser.add_argument('--host', type=str, default=None,
                        help='Host to bind to')
    parser.add_argument('--port', '-p', type=int, default=None,
                        help='Port to bind to')
    
    args = parser.parse_args()
    
    server = MasterServer(args.config)
    server.run(host=args.host, port=args.port)


if __name__ == '__main__':
    main()
