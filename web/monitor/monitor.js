// API URL - 动态获取当前host，端口从URL参数或使用默认值
const urlParams = new URLSearchParams(window.location.search);
const API_PORT = urlParams.get('apiPort') || 5000;
const API_BASE_URL = `http://${window.location.hostname}:${API_PORT}/api`;

// 刷新间隔（毫秒），可通过URL参数配置
const REFRESH_INTERVAL = parseInt(urlParams.get('refreshInterval')) || 5000;

// Toast通知
function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// 格式化时间
function formatTime(timestamp) {
    if (!timestamp) return '--';
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString('zh-CN');
}

// 获取进度条class
function getBarClass(percent) {
    if (percent >= 90) return 'danger';
    if (percent >= 70) return 'warning';
    return '';
}

// 获取从机数据
async function fetchSlaveData() {
    try {
        const response = await fetch(`${API_BASE_URL}/slaves`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status} from ${API_BASE_URL}/slaves`);
        }
        return await response.json();
    } catch (error) {
        showToast(`获取数据失败: ${error.message}`, 'error');
        throw error;
    }
}

// 渲染系统信息
function renderSystemInfo(system) {
    if (!system) return '<div class="system-info"><span>系统信息不可用</span></div>';
    
    const memPercent = system.memory?.percent || 0;
    const swapPercent = system.swap?.percent || 0;
    
    return `
        <div class="system-info">
            <div class="system-item">
                <span class="system-label">主机名</span>
                <span class="system-value">${system.hostname || 'Unknown'}</span>
            </div>
            <div class="system-item">
                <span class="system-label">操作系统</span>
                <span class="system-value small">${system.os || 'Unknown'}</span>
            </div>
            <div class="system-item">
                <span class="system-label">CPU</span>
                <span class="system-value small">${system.cpu_model || 'Unknown'}</span>
                <span class="system-value small">${system.cpu_cores || 0} 核心 | ${system.cpu_usage || 0}% 使用率</span>
            </div>
            <div class="system-item">
                <span class="system-label">内存</span>
                <span class="system-value">${system.memory?.used || 0} / ${system.memory?.total || 0} GB</span>
                <div class="usage-bar-container">
                    <div class="usage-bar">
                        <div class="usage-bar-fill ${getBarClass(memPercent)}" style="width: ${memPercent}%"></div>
                    </div>
                </div>
            </div>
            <div class="system-item">
                <span class="system-label">Swap</span>
                <span class="system-value">${system.swap?.used || 0} / ${system.swap?.total || 0} GB</span>
                <div class="usage-bar-container">
                    <div class="usage-bar">
                        <div class="usage-bar-fill ${getBarClass(swapPercent)}" style="width: ${swapPercent}%"></div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// 渲染GPU进程列表
function renderProcessList(processes) {
    if (!processes || processes.length === 0) {
        return '<div class="no-process">无运行中的进程</div>';
    }
    
    return processes.map(proc => `
        <div class="process-item">
            <div class="process-info">
                <span class="process-name">${escapeHtml(proc.name)}</span>
                <div class="process-details">
                    <span>PID: ${proc.pid}</span>
                    <span>用户: ${escapeHtml(proc.username)}</span>
                    <span>显存: ${proc.memory_mb} MB</span>
                </div>
            </div>
            ${proc.cmdline ? `<div class="process-cmd">${escapeHtml(proc.cmdline)}</div>` : ''}
        </div>
    `).join('');
}

// 渲染单个GPU卡片
function renderGpuCard(gpu) {
    const memTotal = gpu.memory?.total || 1;
    const memUsed = gpu.memory?.used || 0;
    const memPercent = (memUsed / memTotal * 100).toFixed(1);
    const utilization = gpu.utilization || 0;
    const temp = gpu.temperature || 0;
    const powerCurrent = gpu.power?.current || 0;
    const powerMax = gpu.power?.max || 1;
    
    const tempClass = temp >= 80 ? 'high' : '';
    
    return `
        <div class="gpu-card">
            <div class="gpu-header">
                <span class="gpu-name">${escapeHtml(gpu.name)}</span>
                <span class="gpu-id">GPU ${gpu.id}</span>
            </div>
            
            <div class="gpu-metrics">
                <div class="metric-item">
                    <span class="metric-label">温度</span>
                    <span class="metric-value temp ${tempClass}">${temp}°C</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">功耗</span>
                    <span class="metric-value power">${powerCurrent}W / ${powerMax}W</span>
                </div>
            </div>
            
            <div class="gpu-bars">
                <div class="bar-item">
                    <div class="bar-header">
                        <span class="bar-label">显存使用</span>
                        <span class="bar-value">${memUsed} / ${memTotal} MB</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill ${getBarClass(memPercent)}" style="width: ${memPercent}%"></div>
                    </div>
                </div>
                <div class="bar-item">
                    <div class="bar-header">
                        <span class="bar-label">GPU使用率</span>
                        <span class="bar-value">${utilization}%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill ${getBarClass(utilization)}" style="width: ${utilization}%"></div>
                    </div>
                </div>
            </div>
            
            <div class="process-list">
                <div class="process-header">
                    <span>运行中的进程</span>
                    <span>${gpu.processes?.length || 0} 个</span>
                </div>
                ${renderProcessList(gpu.processes)}
            </div>
        </div>
    `;
}

// 渲染GPU列表
function renderGpuList(gpus) {
    if (!gpus || gpus.length === 0) {
        return '<div class="gpu-list"><div class="no-process">未检测到GPU</div></div>';
    }
    
    return `
        <div class="gpu-list">
            ${gpus.map(gpu => renderGpuCard(gpu)).join('')}
        </div>
    `;
}

// 渲染离线从机
function renderOfflineSlave(slave) {
    return `
        <div class="slave-card offline">
            <div class="slave-header">
                <div class="slave-title">
                    <span class="slave-name">${escapeHtml(slave.name)}</span>
                    <span class="slave-ip">${slave.ip}:${slave.port}</span>
                </div>
                <span class="slave-status offline">离线</span>
            </div>
            <div class="offline-message">
                <div class="icon">⚠️</div>
                <div>无法连接到从机</div>
                ${slave.error ? `<div class="error">${escapeHtml(slave.error)}</div>` : ''}
            </div>
        </div>
    `;
}

// 渲染在线从机
function renderOnlineSlave(slave) {
    const data = slave.data || {};
    const system = data.system || {};
    const gpus = data.gpus || [];
    
    return `
        <div class="slave-card">
            <div class="slave-header">
                <div class="slave-title">
                    <span class="slave-name">${escapeHtml(slave.name)}</span>
                    <span class="slave-ip">${slave.ip}:${slave.port}</span>
                </div>
                <span class="slave-status online">在线</span>
            </div>
            ${renderSystemInfo(system)}
            ${renderGpuList(gpus)}
        </div>
    `;
}

// 渲染所有从机
function renderSlaves(slavesData) {
    const container = document.getElementById('slavesContainer');
    
    if (!slavesData || Object.keys(slavesData).length === 0) {
        container.innerHTML = '<div class="loading">未配置从机</div>';
        return;
    }
    
    // 按名称排序
    const slaves = Object.values(slavesData).sort((a, b) => 
        (a.name || a.ip).localeCompare(b.name || b.ip)
    );
    
    // 更新在线计数
    const onlineCount = slaves.filter(s => s.online).length;
    document.getElementById('onlineCount').textContent = `在线从机: ${onlineCount}/${slaves.length}`;
    
    // 渲染从机卡片
    container.innerHTML = slaves.map(slave => 
        slave.online ? renderOnlineSlave(slave) : renderOfflineSlave(slave)
    ).join('');
}

// 更新最后刷新时间
function updateLastRefreshTime() {
    document.getElementById('lastUpdate').textContent = 
        `上次更新: ${new Date().toLocaleTimeString('zh-CN')}`;
}

// 刷新数据
async function refreshData() {
    try {
        const data = await fetchSlaveData();
        renderSlaves(data);
        updateLastRefreshTime();
    } catch (error) {
        console.error('Failed to refresh data:', error);
    }
}

// HTML转义
function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    // 绑定刷新按钮
    document.getElementById('refreshBtn').addEventListener('click', () => {
        showToast('正在刷新...', 'info', 1000);
        refreshData();
    });
    
    // 初始加载
    refreshData();
    
    // 定时刷新
    setInterval(refreshData, REFRESH_INTERVAL);
});
