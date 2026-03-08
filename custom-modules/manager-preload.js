const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('moduleManagerAPI', {
    // 模块 CRUD
    getModules: () => ipcRenderer.invoke('custom-modules:getAll'),
    createModule: (data) => ipcRenderer.invoke('custom-modules:createModule', data),
    updateModule: (id, data) => ipcRenderer.invoke('custom-modules:updateModule', { id, data }),
    deleteModule: (id) => ipcRenderer.invoke('custom-modules:deleteModule', id),

    // 函数 CRUD
    createFunction: (moduleId, fnData) => ipcRenderer.invoke('custom-modules:createFunction', { moduleId, fnData }),
    updateFunction: (moduleId, fnId, fnData) => ipcRenderer.invoke('custom-modules:updateFunction', { moduleId, fnId, fnData }),
    deleteFunction: (moduleId, fnId) => ipcRenderer.invoke('custom-modules:deleteFunction', { moduleId, fnId }),

    // 导入导出
    exportModule: (moduleId) => ipcRenderer.invoke('custom-modules:export', moduleId),
    importModule: () => ipcRenderer.invoke('custom-modules:import'),

    // 通知主窗口数据已变更
    notifyChanged: () => ipcRenderer.send('custom-modules:changed'),
});
