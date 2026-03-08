const { app, BrowserWindow, Menu, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow = null;
let pythonProcess = null;
let shellProcess = null;

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

    // 开发时可取消注释以打开 DevTools
    // mainWindow.webContents.openDevTools();

    mainWindow.on('closed', () => {
        if (pythonProcess) pythonProcess.kill();
        if (shellProcess) shellProcess.kill();
        mainWindow = null;
    });
}

Menu.setApplicationMenu(null);

app.whenReady().then(() => {
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});
