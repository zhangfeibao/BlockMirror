const { contextBridge, ipcRenderer, clipboard } = require('electron');

contextBridge.exposeInMainWorld('terminalAPI', {
    spawn: () => ipcRenderer.invoke('pty:spawn'),
    write: (data) => ipcRenderer.send('pty:write', data),
    resize: (cols, rows) => ipcRenderer.send('pty:resize', { cols, rows }),
    onData: (cb) => {
        ipcRenderer.on('pty:data', (_, d) => cb(d));
    },
    onExit: (cb) => {
        ipcRenderer.on('pty:exit', (_, info) => cb(info));
    },
    clipboardRead: () => clipboard.readText(),
    clipboardWrite: (text) => ipcRenderer.send('clipboard:write', text),
});
