const { app, BrowserWindow, Menu, Tray, ipcMain, nativeImage } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

const rootDir = path.resolve(__dirname, "../..");
const desktopDir = path.resolve(__dirname, "..");
const backendDir = path.join(rootDir, "backend");
const sidecarDir = path.join(rootDir, "rpa-sidecar");
const preloadPath = path.join(__dirname, "preload.cjs");

const BACKEND_URL = "http://127.0.0.1:8710";
const SIDECAR_URL = "http://127.0.0.1:8720";
const RENDERER_URL = process.env.VITE_DEV_SERVER_URL || "http://127.0.0.1:5173";

let mainWindow = null;
let floatingWindow = null;
let tray = null;
const childProcesses = [];

function httpRequest(method, url, body) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const payload = body === undefined ? "" : JSON.stringify(body);
    const request = http.request(
      {
        method,
        hostname: parsed.hostname,
        port: parsed.port,
        path: `${parsed.pathname}${parsed.search}`,
        headers: payload ? { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(payload) } : undefined,
        timeout: 8000
      },
      (response) => {
        let data = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => {
          data += chunk;
        });
        response.on("end", () => {
          if (response.statusCode < 200 || response.statusCode >= 300) {
            reject(new Error(`${response.statusCode} ${response.statusMessage}`));
            return;
          }
          try {
            resolve(data ? JSON.parse(data) : {});
          } catch {
            resolve({});
          }
        });
      }
    );
    request.on("error", reject);
    request.on("timeout", () => {
      request.destroy(new Error("request_timeout"));
    });
    if (payload) request.write(payload);
    request.end();
  });
}

async function waitForUrl(url, seconds = 25) {
  const deadline = Date.now() + seconds * 1000;
  while (Date.now() < deadline) {
    try {
      await httpRequest("GET", url);
      return true;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 600));
    }
  }
  return false;
}

function spawnService(name, command, args, cwd, outLog, errLog) {
  const fs = require("fs");
  const out = fs.openSync(outLog, "a");
  const err = fs.openSync(errLog, "a");
  const child = spawn(command, args, {
    cwd,
    windowsHide: true,
    stdio: ["ignore", out, err],
    shell: false
  });
  childProcesses.push({ name, child });
  child.on("exit", () => {
    fs.closeSync(out);
    fs.closeSync(err);
  });
}

async function ensureServices() {
  if (!(await waitForUrl(`${BACKEND_URL}/health`, 1))) {
    spawnService("backend", "python", ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8710"], backendDir, path.join(backendDir, "backend.log"), path.join(backendDir, "backend.err.log"));
  }
  if (!(await waitForUrl(`${SIDECAR_URL}/health`, 1))) {
    spawnService("rpa-sidecar", "python", ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8720"], sidecarDir, path.join(sidecarDir, "sidecar.log"), path.join(sidecarDir, "sidecar.err.log"));
  }
  if (process.env.NODE_ENV !== "production" && !(await waitForUrl(RENDERER_URL, 1))) {
    const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
    spawnService("renderer", npmCommand, ["run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"], desktopDir, path.join(desktopDir, "vite.log"), path.join(desktopDir, "vite.err.log"));
  }
  await Promise.all([
    waitForUrl(`${BACKEND_URL}/health`, 25),
    waitForUrl(`${SIDECAR_URL}/health`, 25),
    process.env.NODE_ENV === "production" ? Promise.resolve(true) : waitForUrl(RENDERER_URL, 25)
  ]);
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1080,
    minHeight: 720,
    title: "AI 客户触达助手",
    backgroundColor: "#f7f8fb",
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  if (process.env.NODE_ENV === "production") {
    mainWindow.loadFile(path.join(desktopDir, "dist/index.html"));
  } else {
    mainWindow.loadURL(RENDERER_URL);
  }
  mainWindow.on("close", (event) => {
    if (app.isQuitting) return;
    event.preventDefault();
    mainWindow.hide();
  });
}

function createFloatingWindow() {
  floatingWindow = new BrowserWindow({
    width: 320,
    height: 178,
    x: 1320,
    y: 72,
    frame: false,
    resizable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    show: false,
    title: "运行状态",
    backgroundColor: "#172033",
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false
    }
  });
  floatingWindow.setMenu(null);
  floatingWindow.loadFile(path.join(__dirname, "floating.html"));
}

function createTray() {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" rx="7" fill="#1667d9"/><path d="M9 22V10h5.5c4.8 0 8.5 2.7 8.5 6s-3.7 6-8.5 6H9zm4-3h1.5c2.6 0 4.5-1.2 4.5-3s-1.9-3-4.5-3H13v6z" fill="#fff"/></svg>`;
  const icon = nativeImage.createFromDataURL(`data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`);
  tray = new Tray(icon);
  tray.setToolTip("AI 客户触达助手");
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "打开主界面", click: () => showMainWindow() },
      { label: "暂停任务", click: () => taskControl("pause") },
      { label: "继续任务", click: () => taskControl("resume") },
      { label: "停止任务", click: () => taskControl("stop") },
      { type: "separator" },
      { label: "退出", click: () => app.quit() }
    ])
  );
  tray.on("click", () => showMainWindow());
}

function showMainWindow() {
  if (!mainWindow) return;
  mainWindow.show();
  mainWindow.focus();
}

async function enterRunMode() {
  if (mainWindow) mainWindow.hide();
  if (floatingWindow) {
    floatingWindow.showInactive();
    floatingWindow.setAlwaysOnTop(true, "screen-saver");
  }
  const prepare = await httpRequest("POST", `${BACKEND_URL}/wechat/window/prepare-dedicated-desktop`, {});
  if (floatingWindow) floatingWindow.webContents.send("task:refresh");
  return prepare;
}

async function exitRunMode() {
  if (floatingWindow) floatingWindow.hide();
  showMainWindow();
  return { ok: true };
}

async function taskControl(action) {
  const result = await httpRequest("POST", `${BACKEND_URL}/tasks/control`, { action });
  if (floatingWindow) floatingWindow.webContents.send("task:refresh");
  return result;
}

ipcMain.handle("app:start-services", async () => {
  await ensureServices();
  return { ok: true };
});
ipcMain.handle("app:enter-run-mode", () => enterRunMode());
ipcMain.handle("app:exit-run-mode", () => exitRunMode());
ipcMain.handle("task:pause", () => taskControl("pause"));
ipcMain.handle("task:resume", () => taskControl("resume"));
ipcMain.handle("task:stop", () => taskControl("stop"));
ipcMain.handle("task:status", () => httpRequest("GET", `${BACKEND_URL}/tasks/current`));

app.whenReady().then(async () => {
  await ensureServices();
  createMainWindow();
  createFloatingWindow();
  createTray();
});

app.on("window-all-closed", () => {});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createMainWindow();
    createFloatingWindow();
  } else {
    showMainWindow();
  }
});

app.on("before-quit", () => {
  app.isQuitting = true;
  for (const item of childProcesses) {
    try {
      item.child.kill();
    } catch {
      // Ignore process cleanup races on Windows shutdown.
    }
  }
});
