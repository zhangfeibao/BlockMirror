const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    // Python 执行
    runPython: (filePath) => ipcRenderer.invoke('python:run', filePath),
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
    openBlockFactory: () => ipcRenderer.send('blockfactory:open'),

    // 自定义模块管理
    openModuleManager: () => ipcRenderer.send('custom-modules:openManager'),
    getCustomModules: () => ipcRenderer.invoke('custom-modules:getAll'),
    onCustomModulesReload: (callback) => {
        const fn = (_, modules) => callback(modules);
        ipcRenderer.on('custom-modules:reload', fn);
        return () => ipcRenderer.removeListener('custom-modules:reload', fn);
    },

    // AI 助手
    aiSendMessage: (conversationId, userMessage, editorCode, apiDocContent) => ipcRenderer.invoke('ai:sendMessage', { conversationId, userMessage, editorCode, apiDocContent }),
    aiGetSettings: () => ipcRenderer.invoke('ai:getSettings'),
    aiSaveSettings: (data) => ipcRenderer.invoke('ai:saveSettings', data),
    aiGetConversations: () => ipcRenderer.invoke('ai:getConversations'),
    aiGetConversation: (id) => ipcRenderer.invoke('ai:getConversation', id),
    aiCreateConversation: (title) => ipcRenderer.invoke('ai:createConversation', title),
    aiDeleteConversation: (id) => ipcRenderer.invoke('ai:deleteConversation', id),
    aiClearConversation: (id) => ipcRenderer.invoke('ai:clearConversation', id),
    aiSelectApiDoc: () => ipcRenderer.invoke('ai:selectApiDoc'),

    // RAMViewer (ramgs) 工具
    ramgsPorts: () => ipcRenderer.invoke('ramgs:ports'),
    ramgsStatus: () => ipcRenderer.invoke('ramgs:status'),
    ramgsCreate: (elfPath, outputDir) => ipcRenderer.invoke('ramgs:create', { elfPath, outputDir }),
    ramgsLoad: (symbolsPath) => ipcRenderer.invoke('ramgs:load', symbolsPath),
    ramgsOpen: (port, baud, endian) => ipcRenderer.invoke('ramgs:open', { port, baud, endian }),
    ramgsClose: () => ipcRenderer.invoke('ramgs:close'),
    ramgsSelectElf: () => ipcRenderer.invoke('ramgs:selectElf'),
    ramgsSelectSymbols: () => ipcRenderer.invoke('ramgs:selectSymbols'),
    ramgsSelectOutputDir: () => ipcRenderer.invoke('ramgs:selectOutputDir'),
    ramgsOpenMcuLib: () => ipcRenderer.invoke('ramgs:openMcuLib'),
    ramgsShowIntegrationGuide: () => ipcRenderer.invoke('ramgs:showIntegrationGuide'),

    // VS Code
    openVscode: () => ipcRenderer.invoke('vscode:open'),

    // Advanced Terminal
    openAdvancedTerminal: () => ipcRenderer.send('advanced-terminal:open'),

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
