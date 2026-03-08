const { app, BrowserWindow, Menu, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const { CustomModulesStore } = require('./custom-modules-store');

let mainWindow = null;
let pythonProcess = null;
let shellProcess = null;
let blockFactoryWindow = null;
let moduleManagerWindow = null;
let customModulesStore = null;

function sendToRenderer(channel, data) {
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send(channel, data);
    }
}

// Python 执行：用 -u（无缓冲）-c（代码字符串）
ipcMain.handle('python:run', async (event, code) => {
    if (pythonProcess) { pythonProcess.kill(); pythonProcess = null; }

    return new Promise((resolve) => {
        pythonProcess = spawn('python', ['-u', '-c', code], {
            env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' },
        });

        sendToRenderer('process:start', { source: 'python' });
        pythonProcess.stdout.on('data', (d) => sendToRenderer('terminal:output', d.toString()));
        pythonProcess.stderr.on('data', (d) =>
            sendToRenderer('terminal:output', `\x1b[31m${d.toString()}\x1b[0m`));
        pythonProcess.on('close', (exitCode) => {
            pythonProcess = null;
            sendToRenderer('process:exit', { exitCode, source: 'python' });
            resolve({ exitCode });
        });
        pythonProcess.on('error', (err) => {
            sendToRenderer('terminal:output',
                `\x1b[31mPython 启动失败: ${err.message}\r\n\x1b[0m`);
            pythonProcess = null;
            resolve({ exitCode: -1 });
        });
    });
});

ipcMain.handle('python:kill', async () => {
    if (pythonProcess) {
        if (process.platform === 'win32') {
            spawn('taskkill', ['/pid', String(pythonProcess.pid), '/f', '/t']);
        } else {
            pythonProcess.kill('SIGTERM');
        }
        pythonProcess = null;
    }
    return { success: true };
});

// 持久 Shell（PowerShell / bash）
ipcMain.handle('shell:start', async () => {
    if (shellProcess) return { success: true };
    const cmd = process.platform === 'win32' ? 'powershell.exe' : 'bash';
    const args = process.platform === 'win32' ? ['-NoLogo'] : [];

    shellProcess = spawn(cmd, args, { env: { ...process.env } });
    sendToRenderer('process:start', { source: 'shell' });

    shellProcess.stdout.on('data', (d) => sendToRenderer('terminal:output', d.toString()));
    shellProcess.stderr.on('data', (d) =>
        sendToRenderer('terminal:output', `\x1b[31m${d.toString()}\x1b[0m`));
    shellProcess.on('close', (exitCode) => {
        shellProcess = null;
        sendToRenderer('process:exit', { exitCode, source: 'shell' });
    });
    return { success: true };
});

ipcMain.on('shell:write', (_, data) => {
    if (shellProcess && shellProcess.stdin.writable) shellProcess.stdin.write(data);
});

ipcMain.on('terminal:resize', (_, { cols, rows }) => {
    // 预留接口，node-pty 升级时启用：ptyProcess.resize(cols, rows)
});

// ── 文件系统 IPC ──
ipcMain.handle('file:open', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        filters: [
            { name: 'Python 文件', extensions: ['py'] },
            { name: '所有文件', extensions: ['*'] },
        ],
        properties: ['openFile'],
    });
    if (result.canceled || result.filePaths.length === 0) return { canceled: true };
    const filePath = result.filePaths[0];
    const content = fs.readFileSync(filePath, 'utf-8');
    return { canceled: false, filePath, content };
});

ipcMain.handle('file:save', async (_, { filePath, content }) => {
    fs.writeFileSync(filePath, content, 'utf-8');
    return { success: true };
});

ipcMain.handle('file:saveAs', async (_, { content }) => {
    const result = await dialog.showSaveDialog(mainWindow, {
        filters: [
            { name: 'Python 文件', extensions: ['py'] },
            { name: '所有文件', extensions: ['*'] },
        ],
    });
    if (result.canceled) return { canceled: true };
    fs.writeFileSync(result.filePath, content, 'utf-8');
    return { canceled: false, filePath: result.filePath };
});

ipcMain.handle('file:exportPng', async (_, { dataUrl }) => {
    const result = await dialog.showSaveDialog(mainWindow, {
        filters: [{ name: 'PNG 图片', extensions: ['png'] }],
    });
    if (result.canceled) return { canceled: true };
    const base64Data = dataUrl.replace(/^data:image\/png;base64,/, '');
    fs.writeFileSync(result.filePath, Buffer.from(base64Data, 'base64'));
    return { canceled: false, filePath: result.filePath };
});

ipcMain.handle('file:confirmSave', async () => {
    const result = await dialog.showMessageBox(mainWindow, {
        type: 'warning',
        title: '未保存的更改',
        message: '当前文件有未保存的更改，是否保存？',
        buttons: ['保存', '不保存', '取消'],
        defaultId: 0,
        cancelId: 2,
    });
    // response: 0=保存, 1=不保存, 2=取消
    return { response: result.response };
});

ipcMain.on('window:setTitle', (_, title) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.setTitle(title);
    }
});

ipcMain.on('window:forceClose', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.removeAllListeners('close');
        mainWindow.close();
    }
});

// 自定义积木块窗口
ipcMain.on('blockfactory:open', () => {
    if (blockFactoryWindow && !blockFactoryWindow.isDestroyed()) {
        blockFactoryWindow.focus();
        return;
    }
    blockFactoryWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        title: '自定义积木块 - BlockMirror',
        autoHideMenuBar: true,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
        },
    });
    blockFactoryWindow.setMenu(null);
    blockFactoryWindow.loadFile(path.join(__dirname, '..', 'blockfactory', 'index.html'));
    // blockfactory 页面注册了 beforeunload 拦截，忽略它以允许直接关闭
    blockFactoryWindow.webContents.on('will-prevent-unload', (event) => {
        event.preventDefault();
    });
    blockFactoryWindow.on('closed', () => {
        blockFactoryWindow = null;
    });
});

// ── 自定义模块管理 IPC ──
ipcMain.on('custom-modules:openManager', () => {
    if (moduleManagerWindow && !moduleManagerWindow.isDestroyed()) {
        moduleManagerWindow.focus();
        return;
    }
    moduleManagerWindow = new BrowserWindow({
        width: 960,
        height: 640,
        title: '自定义模块管理 - BlockMirror',
        autoHideMenuBar: true,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, '..', 'custom-modules', 'manager-preload.js'),
        },
    });
    moduleManagerWindow.setMenu(null);
    moduleManagerWindow.loadFile(path.join(__dirname, '..', 'custom-modules', 'manager.html'));
    moduleManagerWindow.on('closed', () => {
        moduleManagerWindow = null;
    });
});

ipcMain.handle('custom-modules:getAll', async () => {
    return customModulesStore.getAll();
});

ipcMain.handle('custom-modules:createModule', async (_, data) => {
    return customModulesStore.createModule(data);
});

ipcMain.handle('custom-modules:updateModule', async (_, { id, data }) => {
    return customModulesStore.updateModule(id, data);
});

ipcMain.handle('custom-modules:deleteModule', async (_, id) => {
    return customModulesStore.deleteModule(id);
});

ipcMain.handle('custom-modules:createFunction', async (_, { moduleId, fnData }) => {
    return customModulesStore.createFunction(moduleId, fnData);
});

ipcMain.handle('custom-modules:updateFunction', async (_, { moduleId, fnId, fnData }) => {
    return customModulesStore.updateFunction(moduleId, fnId, fnData);
});

ipcMain.handle('custom-modules:deleteFunction', async (_, { moduleId, fnId }) => {
    return customModulesStore.deleteFunction(moduleId, fnId);
});

ipcMain.handle('custom-modules:export', async (_, moduleId) => {
    const result = await dialog.showSaveDialog(moduleManagerWindow || mainWindow, {
        filters: [{ name: 'JSON 文件', extensions: ['json'] }],
        defaultPath: 'custom-modules.json',
    });
    if (result.canceled) return { canceled: true };
    customModulesStore.exportToFile(result.filePath, moduleId || null);
    return { canceled: false, filePath: result.filePath };
});

ipcMain.handle('custom-modules:import', async () => {
    const result = await dialog.showOpenDialog(moduleManagerWindow || mainWindow, {
        filters: [{ name: 'JSON 文件', extensions: ['json'] }],
        properties: ['openFile'],
    });
    if (result.canceled || result.filePaths.length === 0) return { canceled: true };
    try {
        const imported = customModulesStore.importFromFile(result.filePaths[0]);
        return { canceled: false, modules: imported };
    } catch (err) {
        return { canceled: false, error: err.message };
    }
});

ipcMain.on('custom-modules:changed', () => {
    // 重新读取最新数据并推送到主窗口
    customModulesStore.load();
    const modules = customModulesStore.getAll();
    sendToRenderer('custom-modules:reload', modules);
});

// 窗口创建：注册 preload
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1280,
        height: 800,
        title: 'BlockMirror',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js'),
        },
    });

    mainWindow.loadFile(path.join(__dirname, '..', 'test', 'simple_v2.html'));

    // 页面加载完成后推送自定义模块数据
    mainWindow.webContents.on('did-finish-load', () => {
        if (customModulesStore) {
            const modules = customModulesStore.getAll();
            sendToRenderer('custom-modules:reload', modules);
        }
    });

    // 开发时可取消注释以打开 DevTools
    // mainWindow.webContents.openDevTools();

    // 窗口关闭拦截：检查未保存的更改
    mainWindow.on('close', (e) => {
        e.preventDefault();
        sendToRenderer('menu:command', 'file:beforeClose');
    });

    mainWindow.on('closed', () => {
        if (pythonProcess) pythonProcess.kill();
        if (shellProcess) shellProcess.kill();
        mainWindow = null;
    });
}

// ── 构建原生应用菜单 ──
function buildAppMenu() {
    const template = [
        {
            label: '文件(&F)',
            submenu: [
                { label: '新建', accelerator: 'CmdOrCtrl+N', click: () => sendToRenderer('menu:command', 'file:new') },
                { label: '打开...', accelerator: 'CmdOrCtrl+O', click: () => sendToRenderer('menu:command', 'file:open') },
                { type: 'separator' },
                { label: '保存', accelerator: 'CmdOrCtrl+S', click: () => sendToRenderer('menu:command', 'file:save') },
                { label: '另存为...', accelerator: 'CmdOrCtrl+Shift+S', click: () => sendToRenderer('menu:command', 'file:saveAs') },
                { type: 'separator' },
                { label: '导出 PNG...', click: () => sendToRenderer('menu:command', 'file:exportPng') },
                { type: 'separator' },
                { label: '退出', accelerator: 'Alt+F4', click: () => { if (mainWindow) mainWindow.close(); } },
            ],
        },
        {
            label: '编辑(&E)',
            submenu: [
                { role: 'undo', label: '撤销' },
                { role: 'redo', label: '重做' },
                { type: 'separator' },
                { role: 'cut', label: '剪切' },
                { role: 'copy', label: '复制' },
                { role: 'paste', label: '粘贴' },
                { type: 'separator' },
                { role: 'selectAll', label: '全选' },
            ],
        },
        {
            label: '视图(&V)',
            submenu: [
                { label: '块视图', click: () => sendToRenderer('menu:command', 'view:block') },
                { label: '分屏视图', click: () => sendToRenderer('menu:command', 'view:split') },
                { label: '文本视图', click: () => sendToRenderer('menu:command', 'view:text') },
                { type: 'separator' },
                { label: '切换终端', click: () => sendToRenderer('menu:command', 'view:toggleTerminal') },
                { type: 'separator' },
                { label: '开发者工具', accelerator: 'F12', click: () => { if (mainWindow) mainWindow.webContents.toggleDevTools(); } },
            ],
        },
        {
            label: '工具(&T)',
            submenu: [
                { label: '自定义积木块...', click: () => sendToRenderer('menu:command', 'tools:blockFactory') },
                { label: '自定义模块管理...', click: () => sendToRenderer('menu:command', 'tools:moduleManager') },
            ],
        },
        {
            label: '帮助(&H)',
            submenu: [
                {
                    label: '关于 BlockMirror',
                    click: () => {
                        dialog.showMessageBox(mainWindow, {
                            type: 'info',
                            title: '关于 BlockMirror',
                            message: 'BlockMirror',
                            detail: '双模式 Python 编辑器\n基于 Blockly + CodeMirror',
                        });
                    },
                },
            ],
        },
    ];
    Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

app.whenReady().then(() => {
    customModulesStore = new CustomModulesStore(app.getPath('userData'));
    buildAppMenu();
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});
