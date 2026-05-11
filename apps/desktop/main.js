const { app, BrowserWindow, ipcMain, shell, Menu } = require("electron");
const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const os = require("node:os");
const { spawn, spawnSync } = require("node:child_process");

const projectRoot = path.resolve(__dirname, "../..");
const cacheDir = path.join(projectRoot, "data", "cache");
const backendUrl = process.env.LIGHTDROP_BACKEND_URL || "http://127.0.0.1:8000";
const webUrl = process.env.LIGHTDROP_WEB_URL || "http://127.0.0.1:5173";
const backendBindHost = process.env.LIGHTDROP_BACKEND_HOST || "0.0.0.0";
const webBindHost = process.env.LIGHTDROP_WEB_HOST || "0.0.0.0";
const logMaxBytes = 2 * 1024 * 1024;
const logBackups = 3;

let webWindow = null;
let backendProcess = null;
let webProcess = null;
let startedBackend = false;
let startedWeb = false;
let servicesStarting = false;
let servicesPromise = null;
let isQuitting = false;
let isCleaningUp = false;

function ensureCacheDir() {
  fs.mkdirSync(cacheDir, { recursive: true });
}

function getLanAddress() {
  const interfaces = os.networkInterfaces();
  for (const addresses of Object.values(interfaces)) {
    for (const address of addresses ?? []) {
      if (address.family === "IPv4" && !address.internal) {
        return address.address;
      }
    }
  }
  return null;
}

function buildLanUrl(port) {
  const host = process.env.LIGHTDROP_LAN_HOST || getLanAddress();
  return host ? `http://${host}:${port}` : null;
}

function rotateLogIfNeeded(name) {
  ensureCacheDir();
  const logPath = path.join(cacheDir, name);
  if (!fs.existsSync(logPath)) {
    return;
  }

  try {
    if (fs.statSync(logPath).size < logMaxBytes) {
      return;
    }

    for (let index = logBackups - 1; index >= 1; index -= 1) {
      const source = `${logPath}.${index}`;
      const target = `${logPath}.${index + 1}`;
      if (fs.existsSync(source)) {
        fs.renameSync(source, target);
      }
    }
    fs.renameSync(logPath, `${logPath}.1`);
  } catch {
    // Log rotation should never block service startup.
  }
}

function openLogStream(name) {
  ensureCacheDir();
  rotateLogIfNeeded(name);
  return fs.openSync(path.join(cacheDir, name), "a");
}

function notifyStatusChanged() {
  if (webWindow && !webWindow.isDestroyed()) {
    webWindow.webContents.send("services:changed");
  }
}

function appendLog(logName, message) {
  ensureCacheDir();
  rotateLogIfNeeded(logName);
  fs.appendFileSync(path.join(cacheDir, logName), message, "utf8");
}

function spawnManagedProcess(label, executable, args, logName, options = {}) {
  appendLog(logName, `\n[${new Date().toISOString()}] Starting ${label}: ${executable} ${args.join(" ")}\n`);
  const logStream = openLogStream(logName);
  const child = spawn(executable, args, {
    cwd: projectRoot,
    windowsHide: true,
    stdio: ["ignore", logStream, logStream],
    ...options,
  });

  child.on("exit", (code, signal) => {
    appendLog(logName, `[${new Date().toISOString()}] ${label} exited: code=${code} signal=${signal}\n`);
    if (label === "backend") {
      backendProcess = null;
    }
    if (label === "web") {
      webProcess = null;
    }
    notifyStatusChanged();
  });

  child.on("error", (error) => {
    appendLog(logName, `[${new Date().toISOString()}] ${label} failed: ${error.message}\n`);
    notifyStatusChanged();
  });

  return child;
}

function startBackend() {
  if (backendProcess && !backendProcess.killed) {
    return;
  }

  backendProcess = spawnManagedProcess(
    "backend",
    "python",
    ["-m", "uvicorn", "backend.main:app", "--host", backendBindHost, "--port", "8000"],
    "backend.log",
  );
  startedBackend = true;
}

function startWeb() {
  if (app.isPackaged) {
    return;
  }

  if (webProcess && !webProcess.killed) {
    return;
  }

  const viteScript = path.join(projectRoot, "node_modules", "vite", "bin", "vite.js");
  webProcess = spawnManagedProcess(
    "web",
    process.execPath,
    [viteScript, "--host", webBindHost, "--port", "5173", "apps/web"],
    "web.log",
    {
      env: {
        ...process.env,
        ELECTRON_RUN_AS_NODE: "1",
      },
    },
  );
  startedWeb = true;
}

function killProcessTree(pid) {
  if (!pid) {
    return;
  }

  if (process.platform === "win32") {
    spawnSync("taskkill", ["/pid", String(pid), "/T", "/F"], {
      windowsHide: true,
      stdio: "ignore",
    });
    return;
  }

  try {
    process.kill(pid, "SIGTERM");
  } catch {
    // The process may have exited already.
  }
}

function cleanupManagedServices() {
  if (isCleaningUp) {
    return;
  }
  isCleaningUp = true;

  killProcessTree(webProcess?.pid);
  killProcessTree(backendProcess?.pid);

  webProcess = null;
  backendProcess = null;
  isCleaningUp = false;
}

function isUrlReady(url, timeout = 800) {
  return new Promise((resolve) => {
    const request = http.get(url, (response) => {
      response.resume();
      resolve(response.statusCode >= 200 && response.statusCode < 500);
    });

    request.on("error", () => resolve(false));
    request.setTimeout(timeout, () => {
      request.destroy();
      resolve(false);
    });
  });
}

async function ensureServices() {
  if (servicesPromise) {
    return servicesPromise;
  }

  servicesPromise = (async () => {
    servicesStarting = true;
    notifyStatusChanged();

    try {
      if (!(await isUrlReady(`${backendUrl}/health`))) {
        startBackend();
      }

      if (!app.isPackaged && !(await isUrlReady(webUrl))) {
        startWeb();
      }

      const [backendReady, webReady] = await Promise.all([
        waitUntilReady(`${backendUrl}/health`, 60000),
        app.isPackaged ? Promise.resolve(true) : waitUntilReady(webUrl, 60000),
      ]);
      if (!backendReady) {
        appendLog("backend.log", `[${new Date().toISOString()}] backend did not become ready within 60s\n`);
      }
      if (!webReady) {
        appendLog("web.log", `[${new Date().toISOString()}] web did not become ready within 60s\n`);
      }
    } finally {
      servicesStarting = false;
      servicesPromise = null;
      notifyStatusChanged();
    }
  })();

  return servicesPromise;
}

async function getServiceStatus() {
  const lanBackendUrl = buildLanUrl(8000);
  const lanWebUrl = app.isPackaged ? null : buildLanUrl(5173);
  const [backendReady, devWebReady] = await Promise.all([
    isUrlReady(`${backendUrl}/health`),
    app.isPackaged ? Promise.resolve(true) : isUrlReady(webUrl),
  ]);

  return {
    backendReady,
    webReady: devWebReady,
    backendUrl,
    webUrl,
    lanBackendUrl,
    lanWebUrl,
    servicesStarting,
    startedBackend,
    startedWeb,
  };
}

async function waitUntilReady(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await isUrlReady(url, 1200)) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return false;
}

function quitFromWindow() {
  if (isQuitting) {
    return;
  }

  isQuitting = true;
  cleanupManagedServices();
  app.quit();
}

function buildChineseMenu() {
  const template = [
    {
      label: "文件",
      submenu: [
        { label: "新建窗口", accelerator: "CmdOrCtrl+N", click: () => { createWebWindow(); ensureServices().then(loadWebApp); } },
        { type: "separator" },
        { label: "退出", accelerator: "CmdOrCtrl+Q", role: "quit" },
      ],
    },
    {
      label: "编辑",
      submenu: [
        { label: "撤销", accelerator: "CmdOrCtrl+Z", role: "undo" },
        { label: "重做", accelerator: "CmdOrCtrl+Shift+Z", role: "redo" },
        { type: "separator" },
        { label: "剪切", accelerator: "CmdOrCtrl+X", role: "cut" },
        { label: "复制", accelerator: "CmdOrCtrl+C", role: "copy" },
        { label: "粘贴", accelerator: "CmdOrCtrl+V", role: "paste" },
        { label: "全选", accelerator: "CmdOrCtrl+A", role: "selectAll" },
      ],
    },
    {
      label: "视图",
      submenu: [
        { label: "重新加载", accelerator: "CmdOrCtrl+R", role: "reload" },
        { label: "强制重新加载", accelerator: "CmdOrCtrl+Shift+R", role: "forceReload" },
        { label: "开发者工具", accelerator: "F12", role: "toggleDevTools" },
        { type: "separator" },
        { label: "实际大小", accelerator: "CmdOrCtrl+0", role: "resetZoom" },
        { label: "放大", accelerator: "CmdOrCtrl+Plus", role: "zoomIn" },
        { label: "缩小", accelerator: "CmdOrCtrl+-", role: "zoomOut" },
        { type: "separator" },
        { label: "全屏", accelerator: "F11", role: "togglefullscreen" },
      ],
    },
    {
      label: "窗口",
      submenu: [
        { label: "最小化", accelerator: "CmdOrCtrl+M", role: "minimize" },
        { label: "关闭", accelerator: "CmdOrCtrl+W", role: "close" },
      ],
    },
    {
      label: "帮助",
      submenu: [
        { label: "关于轻放助手", click: () => {
          const { dialog } = require("electron");
          dialog.showMessageBox(webWindow, {
            type: "info",
            title: "关于",
            message: "轻放直播电商运营助手",
            detail: "版本 0.1.0\n直播电商数据分析与运营工具",
          });
        }},
      ],
    },
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

function createWebWindow() {
  if (webWindow && !webWindow.isDestroyed()) {
    webWindow.focus();
    return;
  }

  webWindow = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 1100,
    minHeight: 720,
    title: "轻放直播电商运营助手",
    backgroundColor: "#f0f4f8",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  webWindow.loadURL(
    "data:text/html;charset=utf-8," +
      encodeURIComponent(`
        <!doctype html>
        <html lang="zh-CN">
          <head>
            <meta charset="UTF-8" />
            <title>轻放直播电商运营助手</title>
            <style>
              body {
                display: grid;
                place-items: center;
                min-height: 100vh;
                margin: 0;
                color: #1a2332;
                background: #f0f4f8;
                font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
              }
              main {
                display: grid;
                gap: 10px;
                text-align: center;
              }
              strong {
                font-size: 22px;
              }
              span {
                color: #68736f;
              }
            </style>
          </head>
          <body>
            <main>
              <strong>轻放直播电商运营助手</strong>
              <span>正在启动后端服务和 Web 前端...</span>
            </main>
          </body>
        </html>
      `),
  );

  webWindow.on("close", () => {
    quitFromWindow();
  });

  webWindow.on("closed", () => {
    webWindow = null;
  });
}

function loadWebApp() {
  if (!webWindow || webWindow.isDestroyed()) {
    return;
  }

  if (app.isPackaged) {
    webWindow.loadFile(path.join(projectRoot, "apps/web/dist/index.html"));
  } else {
    webWindow.loadURL(webUrl);
  }
}

ipcMain.handle("services:status", getServiceStatus);

ipcMain.handle("services:open-web", async () => {
  await ensureServices();
  const status = await getServiceStatus();
  if (!status.backendReady || !status.webReady) {
    return status;
  }
  createWebWindow();
  loadWebApp();
  return status;
});

ipcMain.handle("services:open-web-browser", async () => {
  await ensureServices();
  const status = await getServiceStatus();
  if (!status.backendReady || !status.webReady) {
    return status;
  }
  await shell.openExternal(webUrl);
  return status;
});

ipcMain.handle("services:open-lan-web-browser", async () => {
  await ensureServices();
  const status = await getServiceStatus();
  if (!status.backendReady || !status.webReady || !status.lanWebUrl) {
    return status;
  }
  await shell.openExternal(status.lanWebUrl);
  return status;
});

app.whenReady().then(() => {
  buildChineseMenu();
  cleanupManagedServices();
  createWebWindow();
  ensureServices().then(loadWebApp);

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWebWindow();
      ensureServices().then(loadWebApp);
    }
  });
});

app.on("window-all-closed", () => {
  app.quit();
});

app.on("before-quit", () => {
  isQuitting = true;
  cleanupManagedServices();
});
