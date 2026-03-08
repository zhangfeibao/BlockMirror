const { app, BrowserWindow, Menu } = require('electron');
const path = require('path');

function createWindow() {
    const win = new BrowserWindow({
        width: 1280,
        height: 800,
        title: 'BlockMirror',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
        },
    });

    win.loadFile(path.join(__dirname, '..', 'test', 'simple_v2.html'));

    // 开发时可取消注释以打开 DevTools
    // win.webContents.openDevTools();
}

// 移除默认菜单栏（可选）
Menu.setApplicationMenu(null);

app.whenReady().then(() => {
    createWindow();

    app.on('activate', () => {
        // macOS：点击 Dock 图标时重新创建窗口
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    // macOS 以外的平台关闭所有窗口时退出应用
    if (process.platform !== 'darwin') {
        app.quit();
    }
});
