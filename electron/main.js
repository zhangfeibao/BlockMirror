const { app, BrowserWindow, Menu, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const { CustomModulesStore } = require('./custom-modules-store');
const { AiClient } = require('./ai-client');
const { AiSettingsStore } = require('./ai-settings-store');
const { AiConversationsStore } = require('./ai-conversations-store');

let mainWindow = null;
let pythonProcess = null;
let shellProcess = null;
let blockFactoryWindow = null;
let moduleManagerWindow = null;
let customModulesStore = null;
let aiClient = null;
let aiSettingsStore = null;
let aiConversationsStore = null;

function getRamgsDir() {
    return path.join(__dirname, '..', 'ramgs');
}

function ensureRamgsInPath() {
    const ramgsDir = getRamgsDir();
    const envPath = process.env.PATH || process.env.Path || '';
    const sep = process.platform === 'win32' ? ';' : ':';
    const dirs = envPath.split(sep);
    const normalizedRamgs = path.normalize(ramgsDir).toLowerCase();
    const found = dirs.some(function(d) {
        return path.normalize(d).toLowerCase() === normalizedRamgs;
    });
    if (!found) {
        process.env.PATH = ramgsDir + sep + envPath;
    }
}

function sendToRenderer(channel, data) {
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send(channel, data);
    }
}

// Python 执行：在文件所在目录运行 Python 脚本
ipcMain.handle('python:run', async (event, filePath) => {
    if (pythonProcess) { pythonProcess.kill(); pythonProcess = null; }

    const cwd = path.dirname(filePath);

    return new Promise((resolve) => {
        pythonProcess = spawn('python', ['-u', filePath], {
            cwd: cwd,
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

// ── AI 助手 IPC ──
ipcMain.handle('ai:getSettings', async () => {
    return aiSettingsStore.getAll();
});

ipcMain.handle('ai:saveSettings', async (_, data) => {
    return aiSettingsStore.update(data);
});

ipcMain.handle('ai:getConversations', async () => {
    return aiConversationsStore.getAll();
});

ipcMain.handle('ai:getConversation', async (_, id) => {
    return aiConversationsStore.get(id);
});

ipcMain.handle('ai:createConversation', async (_, title) => {
    return aiConversationsStore.create(title);
});

ipcMain.handle('ai:deleteConversation', async (_, id) => {
    return aiConversationsStore.delete(id);
});

ipcMain.handle('ai:clearConversation', async (_, id) => {
    return aiConversationsStore.clearMessages(id);
});

ipcMain.handle('ai:selectApiDoc', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        filters: [
            { name: 'Text/Markdown', extensions: ['txt', 'md', 'json', 'yaml', 'yml', 'rst'] },
            { name: 'All Files', extensions: ['*'] },
        ],
        properties: ['openFile'],
    });
    if (result.canceled || result.filePaths.length === 0) return { canceled: true };
    const filePath = result.filePaths[0];
    const content = fs.readFileSync(filePath, 'utf-8');
    const fileName = path.basename(filePath);
    return { canceled: false, filePath, fileName, content };
});

ipcMain.handle('ai:sendMessage', async (_, { conversationId, userMessage, editorCode, apiDocContent }) => {
    const settings = aiSettingsStore.getAll();

    // Save user message to conversation
    aiConversationsStore.addMessage(conversationId, { role: 'user', content: userMessage });

    // Get full conversation for context
    const conv = aiConversationsStore.get(conversationId);
    if (!conv) return { content: null, error: 'Conversation not found' };

    // Build messages (exclude system prompt - it's sent separately)
    const messages = conv.messages.map(m => ({ role: m.role, content: m.content }));

    // Build dynamic system prompt: base prompt + API doc + current editor code
    let systemPrompt = settings.systemPrompt || '';
    if (apiDocContent && apiDocContent.trim()) {
        systemPrompt += '\n\n--- Hardware API Reference Documentation ---\n' + apiDocContent + '\n--- End of API Documentation ---\nYou MUST use only the API functions described above when generating code that interacts with hardware devices. Do not invent or assume any API functions not listed in this documentation.';
    }
    if (editorCode && editorCode.trim()) {
        systemPrompt += '\n\n--- Current code in the editor ---\n```python\n' + editorCode + '\n```\nWhen the user asks to modify or improve code, base your changes on the code above.';
    }

    const result = await aiClient.sendMessage(messages, {
        model: settings.model,
        authToken: settings.authToken,
        aigcUser: settings.aigcUser,
        effort: settings.effort,
        systemPrompt: systemPrompt,
    });

    // Save assistant response to conversation
    if (result.content) {
        aiConversationsStore.addMessage(conversationId, { role: 'assistant', content: result.content });

        // Auto-title: if this is the first exchange, use first 30 chars of user message
        if (conv.messages.length <= 1) {
            const title = userMessage.substring(0, 40) + (userMessage.length > 40 ? '...' : '');
            aiConversationsStore.updateTitle(conversationId, title);
        }
    }

    return result;
});

// ── RAMViewer (ramgs) IPC ──
function spawnRamgs(args, label) {
    const ramgsDir = getRamgsDir();
    return new Promise((resolve) => {
        const child = spawn('ramgs.exe', args, { cwd: ramgsDir });

        sendToRenderer('process:start', { source: 'ramgs' });
        child.stdout.on('data', (d) => sendToRenderer('terminal:output', d.toString()));
        child.stderr.on('data', (d) =>
            sendToRenderer('terminal:output', `\x1b[31m${d.toString()}\x1b[0m`));
        child.on('close', (exitCode) => {
            sendToRenderer('process:exit', { exitCode, source: 'ramgs' });
            resolve({ exitCode });
        });
        child.on('error', (err) => {
            sendToRenderer('terminal:output',
                `\x1b[31m${label} failed: ${err.message}\r\n\x1b[0m`);
            resolve({ exitCode: -1 });
        });
    });
}

ipcMain.handle('ramgs:ports', async () => {
    const ramgsDir = getRamgsDir();
    return new Promise((resolve) => {
        const child = spawn('ramgs.exe', ['ports'], { cwd: ramgsDir });
        let stdout = '';
        let stderr = '';
        child.stdout.on('data', (d) => { stdout += d.toString(); });
        child.stderr.on('data', (d) => { stderr += d.toString(); });
        child.on('close', (exitCode) => {
            if (exitCode !== 0) {
                resolve({ success: false, ports: [], error: stderr || stdout });
                return;
            }
            // Parse "ramgs ports" output: each line like "COM3 - USB Serial Device"
            const ports = [];
            stdout.split('\n').forEach((line) => {
                line = line.trim();
                if (!line) return;
                const dashIdx = line.indexOf(' - ');
                if (dashIdx > 0) {
                    ports.push({ name: line.substring(0, dashIdx).trim(), description: line.substring(dashIdx + 3).trim() });
                } else {
                    ports.push({ name: line, description: '' });
                }
            });
            resolve({ success: true, ports });
        });
        child.on('error', (err) => {
            resolve({ success: false, ports: [], error: err.message });
        });
    });
});

ipcMain.handle('ramgs:status', async () => {
    const ramgsDir = getRamgsDir();
    return new Promise((resolve) => {
        const child = spawn('ramgs.exe', ['status'], { cwd: ramgsDir });
        let stdout = '';
        let stderr = '';
        child.stdout.on('data', (d) => { stdout += d.toString(); });
        child.stderr.on('data', (d) => { stderr += d.toString(); });
        child.on('close', (exitCode) => {
            const status = { connected: false, port: '', baud: '', endian: '', symbols: '' };
            if (exitCode !== 0) {
                status.error = stderr || ('ramgs status exited with code ' + exitCode);
                resolve(status);
                return;
            }
            // Parse status output into structured object
            stdout.split('\n').forEach((line) => {
                line = line.trim();
                if (/^connected\s*[:=]\s*true/i.test(line)) status.connected = true;
                if (/^connected\s*[:=]\s*false/i.test(line)) status.connected = false;
                const portMatch = line.match(/^port\s*[:=]\s*(.+)/i);
                if (portMatch) status.port = portMatch[1].trim();
                const baudMatch = line.match(/^baud\s*[:=]\s*(.+)/i);
                if (baudMatch) status.baud = baudMatch[1].trim();
                const endianMatch = line.match(/^endian\s*[:=]\s*(.+)/i);
                if (endianMatch) status.endian = endianMatch[1].trim();
                const symbolsMatch = line.match(/^symbols\s*[:=]\s*(.+)/i);
                if (symbolsMatch) status.symbols = symbolsMatch[1].trim();
            });
            resolve(status);
        });
        child.on('error', (err) => {
            resolve({ connected: false, port: '', baud: '', endian: '', symbols: '', error: err.message });
        });
    });
});

ipcMain.handle('ramgs:create', async (_, { elfPath, outputDir }) => {
    const outputPath = path.join(outputDir, 'symbols.json');
    return spawnRamgs(['create', elfPath, '-o', outputPath], 'ramgs create');
});

ipcMain.handle('ramgs:load', async (_, symbolsPath) => {
    return spawnRamgs(['load', symbolsPath], 'ramgs load');
});

ipcMain.handle('ramgs:open', async (_, { port, baud, endian }) => {
    // Validate port: must match COM port or /dev/ device name
    if (!/^(COM\d+|\/dev\/[a-zA-Z0-9._/-]+)$/i.test(port)) {
        return { exitCode: -1, error: 'Invalid port name' };
    }
    // Validate baud: must be a number
    if (!/^\d+$/.test(String(baud))) {
        return { exitCode: -1, error: 'Invalid baud rate' };
    }
    // Validate endian: whitelist
    if (endian && endian !== 'little' && endian !== 'big') {
        return { exitCode: -1, error: 'Invalid endian value' };
    }

    const args = ['open', '--name', port, '--baud', String(baud)];
    if (endian) args.push('--endian', endian);
    return spawnRamgs(args, 'ramgs open');
});

ipcMain.handle('ramgs:close', async () => {
    return spawnRamgs(['close'], 'ramgs close');
});

ipcMain.handle('ramgs:selectElf', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        filters: [
            { name: 'ELF/ABS/AXF/OUT', extensions: ['elf', 'abs', 'axf', 'out'] },
            { name: 'All Files', extensions: ['*'] },
        ],
        properties: ['openFile'],
    });
    if (result.canceled || result.filePaths.length === 0) return { canceled: true };
    return { canceled: false, filePath: result.filePaths[0] };
});

ipcMain.handle('ramgs:selectSymbols', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        filters: [
            { name: 'JSON', extensions: ['json'] },
            { name: 'All Files', extensions: ['*'] },
        ],
        properties: ['openFile'],
    });
    if (result.canceled || result.filePaths.length === 0) return { canceled: true };
    return { canceled: false, filePath: result.filePaths[0] };
});

ipcMain.handle('ramgs:selectOutputDir', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openDirectory'],
    });
    if (result.canceled || result.filePaths.length === 0) return { canceled: true };
    return { canceled: false, dirPath: result.filePaths[0] };
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
                { type: 'separator' },
                { label: 'AI 助手', accelerator: 'CmdOrCtrl+Shift+A', click: () => sendToRenderer('menu:command', 'tools:aiAssistant') },
                { type: 'separator' },
                { label: '生成符号表...', click: () => sendToRenderer('menu:command', 'ramgs:create') },
                { label: '加载符号表...', click: () => sendToRenderer('menu:command', 'ramgs:load') },
                { label: '连接设备...', click: () => sendToRenderer('menu:command', 'ramgs:connect') },
                { label: '断开设备', click: () => sendToRenderer('menu:command', 'ramgs:disconnect') },
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
    const userData = app.getPath('userData');
    customModulesStore = new CustomModulesStore(userData);
    aiClient = new AiClient();
    aiSettingsStore = new AiSettingsStore(userData);
    aiConversationsStore = new AiConversationsStore(userData);
    ensureRamgsInPath();
    buildAppMenu();
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});
