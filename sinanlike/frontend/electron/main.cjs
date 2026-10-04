const { app, BrowserWindow, Menu, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const http = require('http');

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;
let backendProc = null;

function readLocalEnv(file) {
  const out = {};
  try {
    const text = fs.readFileSync(file, 'utf-8');
    for (const raw of text.split(/\r?\n/)) {
      const line = raw.trim();
      if (!line || line.startsWith('#') || !line.includes('=')) continue;
      const i = line.indexOf('=');
      out[line.slice(0, i).trim()] = line.slice(i + 1).trim();
    }
  } catch (e) { /* ignore */ }
  return out;
}

function httpGetJson(url, timeout = 2500) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      let body = '';
      res.on('data', (c) => { body += c; });
      res.on('end', () => {
        try { resolve({ ok: res.statusCode === 200, data: JSON.parse(body) }); }
        catch { resolve({ ok: false, data: null }); }
      });
    });
    req.on('error', () => resolve({ ok: false, data: null }));
    req.setTimeout(timeout, () => { req.destroy(); resolve({ ok: false, data: null }); });
  });
}

async function backendReady() {
  const r = await httpGetJson('http://127.0.0.1:18000/');
  return !!(r.ok && r.data && r.data.status === 'ok');
}

// 打包版：拉起内置 Python 运行时 + 后端脚本（resources/runtime/python + resources/app_backend）
async function ensureBackend() {
  if (await backendReady()) return true;
  if (isDev) return false;
  const resources = process.resourcesPath;
  const python = path.join(resources, 'runtime', 'python', 'python.exe');
  const script = path.join(resources, 'app_backend', 'backend_main.py');
  if (!fs.existsSync(python) || !fs.existsSync(script)) {
    dialog.showErrorBox('旅鸢', '未找到内置运行环境：\n' + python + '\n' + script);
    return false;
  }
  const userData = app.getPath('userData');
  fs.mkdirSync(userData, { recursive: true });
  const envFromFile = readLocalEnv(path.join(resources, 'local.env'));
  const backendEnv = {
    ...envFromFile,
    ...process.env,
    BOC_DB_PATH: path.join(userData, 'brain_of_cloud.sqlite'),
    BOC_DATA_DIR: path.join(resources, 'data'),
    BOC_PORT: '18000',
  };
  backendProc = spawn(python, [script], {
    cwd: userData,
    env: backendEnv,
    windowsHide: true,
    stdio: 'ignore',
  });
  backendProc.on('exit', (code) => { backendProc = null; });
  const deadline = Date.now() + 90000; // 首次加载知识库较慢
  while (Date.now() < deadline) {
    if (await backendReady()) return true;
    await new Promise((r) => setTimeout(r, 800));
  }
  dialog.showErrorBox('旅鸢', '后端 90 秒内未就绪，请查看是否被安全软件拦截后重试。');
  return false;
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1360,
    height: 860,
    minWidth: 1024,
    minHeight: 680,
    title: '旅鸢',
    icon: path.join(__dirname, '../build/icon.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
    },
    frame: true,
    autoHideMenuBar: true,
    show: false,
  });
  win.once('ready-to-show', () => win.show());
  if (isDev) {
    win.loadURL('http://localhost:5173');
  } else {
    win.loadFile(path.join(__dirname, '../dist/index.html'));
  }
  win.on('page-title-updated', (e) => e.preventDefault());
}

app.whenReady().then(async () => {
  Menu.setApplicationMenu(null);
  if (!isDev) {
    await ensureBackend();
  }
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('will-quit', () => {
  if (backendProc) { try { backendProc.kill(); } catch (e) {} }
});
