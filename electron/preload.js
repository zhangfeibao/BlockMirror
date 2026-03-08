const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    // Python 执行
    runPython: (code) => ipcRenderer.invoke('python:run', code),
    killPython: () => ipcRenderer.invoke('python:kill'),

    // Shell 交互
    startShell: () => ipcRenderer.invoke('shell:start'),
    writeToShell: (data) => ipcRenderer.send('shell:write', data),
    resizeTerminal: (cols, rows) => ipcRenderer.send('terminal:resize', { cols, rows }),

    // 主进程 → 渲染进程 事件监听（返回取消函数）
    onOutput: (callback) => {
        const fn = (_, data) => callback(data);
        ipcRenderer.on('terminal:output', fn);
        return () => ipcRenderer.removeListener('terminal:output', fn);
    },
    onProcessExit: (callback) => {
        const fn = (_, info) => callback(info);
        ipcRenderer.on('process:exit', fn);
        return () => ipcRenderer.removeListener('process:exit', fn);
    },
    onProcessStart: (callback) => {
        const fn = (_, info) => callback(info);
        ipcRenderer.on('process:start', fn);
        return () => ipcRenderer.removeListener('process:start', fn);
    },
});
