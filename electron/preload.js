const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    // Python 执行
    runPython: (code) => ipcRenderer.invoke('python:run', code),
    killPython: () => ipcRenderer.invoke('python:kill'),

    // Shell 交互
    startShell: () => ipcRenderer.invoke('shell:start'),
    writeToShell: (data) => ipcRenderer.send('shell:write', data),
    resizeTerminal: (cols, rows) => ipcRenderer.send('terminal:resize', { cols, rows }),

    // 文件操作
    fileOpen: () => ipcRenderer.invoke('file:open'),
    fileSave: (data) => ipcRenderer.invoke('file:save', data),
    fileSaveAs: (data) => ipcRenderer.invoke('file:saveAs', data),
    fileExportPng: (data) => ipcRenderer.invoke('file:exportPng', data),
    fileConfirmSave: () => ipcRenderer.invoke('file:confirmSave'),

    // 窗口控制
    setWindowTitle: (title) => ipcRenderer.send('window:setTitle', title),
    forceClose: () => ipcRenderer.send('window:forceClose'),

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
    onMenuCommand: (callback) => {
        const fn = (_, command) => callback(command);
        ipcRenderer.on('menu:command', fn);
        return () => ipcRenderer.removeListener('menu:command', fn);
    },
});
