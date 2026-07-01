const { app, BrowserWindow, Menu, Tray, ipcMain, nativeImage } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const http = require("http");
const path = require("path");

const rootDir = path.resolve(__dirname, "../..");
const desktopDir = path.resolve(__dirname, "..");
const backendDir = path.join(rootDir, "backend");
const sidecarDir = path.join(rootDir, "rpa-sidecar");
const preloadPath = path.join(__dirname, "preload.cjs");
const startAgentScript = path.join(rootDir, "Start-Agent.ps1");
const adminContactSyncHelperScript = path.join(rootDir, "tools", "run_admin_contact_sync_helper.py");
const adminContactSyncResultPath = path.join(rootDir, ".runtime", "contact_sync_admin_result.json");

const BACKEND_URL = "http://127.0.0.1:8710";
const SIDECAR_URL = "http://127.0.0.1:8720";
const RENDERER_URL = process.env.VITE_DEV_SERVER_URL || "http://127.0.0.1:5173";
const electronLogPath = path.join(desktopDir, "electron-main.log");

let mainWindow = null;
let floatingWindow = null;
let tray = null;
const childProcesses = [];

function appendMainLog(level, message, detail = "") {
  const line = `[${new Date().toISOString()}] ${level} ${message}${detail ? ` ${detail}` : ""}\n`;
  try {
    fs.appendFileSync(electronLogPath, line, "utf8");
  } catch {
    // Logging must never take down the desktop shell.
  }
}

function isBrokenPipe(error) {
  return error && (error.code === "EPIPE" || String(error.message || "").includes("EPIPE"));
}

for (const stream of [process.stdout, process.stderr]) {
  try {
    stream.on("error", (error) => {
      if (!isBrokenPipe(error)) appendMainLog("stream-error", error.message || String(error));
    });
  } catch {
    // Some Electron launches do not expose normal node streams.
  }
}

process.on("uncaughtException", (error) => {
  if (isBrokenPipe(error)) {
    appendMainLog("ignored", "EPIPE from detached console stream");
    return;
  }
  appendMainLog("uncaughtException", error.stack || String(error));
});

process.on("unhandledRejection", (reason) => {
  appendMainLog("unhandledRejection", reason && reason.stack ? reason.stack : String(reason));
});

function errorResponse(error, fallbackMessage = "本地桌面服务暂时不可用") {
  const message = error && error.message ? error.message : String(error || fallbackMessage);
  appendMainLog("ipc-error", message);
  return {
    ok: false,
    success: false,
    message: fallbackMessage,
    error: message
  };
}

function safeHandle(channel, handler, fallbackMessage) {
  ipcMain.handle(channel, async (...args) => {
    try {
      return await handler(...args);
    } catch (error) {
      return errorResponse(error, fallbackMessage);
    }
  });
}

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

async function checkUrl(url) {
  try {
    await httpRequest("GET", url);
    return true;
  } catch {
    return false;
  }
}

async function getServiceStatus() {
  const [backend, sidecar, renderer] = await Promise.all([
    checkUrl(`${BACKEND_URL}/health`),
    checkUrl(`${SIDECAR_URL}/health`),
    process.env.NODE_ENV === "production" ? Promise.resolve(true) : checkUrl(RENDERER_URL)
  ]);
  const ready = backend && sidecar && renderer;
  return {
    ok: ready,
    ready,
    backend,
    sidecar,
    renderer,
    message: ready ? "软件服务已就绪" : "软件服务未完全启动"
  };
}

function psSingleQuoted(value) {
  return `'${String(value).replace(/'/g, "''")}'`;
}

function resolvePythonExecutable() {
  const candidates = [
    process.env.PYTHON,
    path.join(process.env.LOCALAPPDATA || "", "Programs", "Python", "Python314", "python.exe"),
    "python.exe"
  ].filter(Boolean);
  for (const candidate of candidates) {
    try {
      if (path.isAbsolute(candidate) && fs.existsSync(candidate)) return candidate;
    } catch {
      // Try next candidate.
    }
  }
  return "python.exe";
}

function psJsonWriteCommand(filePath, payload) {
  const json = JSON.stringify(payload).replace(/'/g, "''");
  return `[System.IO.File]::WriteAllText(${psSingleQuoted(filePath)}, '${json}', [System.Text.Encoding]::UTF8)`;
}

async function restartServicesAsAdmin() {
  if (!fs.existsSync(startAgentScript)) {
    return {
      ok: false,
      success: false,
      message: "没有找到本地启动脚本，请检查软件目录是否完整"
    };
  }
  const elevatedArgs = [
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-WindowStyle",
    "Hidden",
    "-File",
    startAgentScript,
    "-ServicesOnly"
  ];
  const argumentList = `@(${elevatedArgs.map(psSingleQuoted).join(",")})`;
  const command = `Start-Process -FilePath ${psSingleQuoted("powershell.exe")} -Verb RunAs -WindowStyle Hidden -ArgumentList ${argumentList}`;
  const child = spawn(
    "powershell.exe",
    ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
    {
      cwd: rootDir,
      windowsHide: true,
      detached: true,
      stdio: "ignore",
      shell: false
    }
  );
  child.unref();
  appendMainLog("admin-restart", "requested services-only restart");
  return {
    ok: true,
    success: true,
    message: "已弹出权限确认，请点击“是”，软件会自动恢复服务"
  };
}

function writeAdminSyncPendingResult() {
  fs.mkdirSync(path.dirname(adminContactSyncResultPath), { recursive: true });
  fs.writeFileSync(
    adminContactSyncResultPath,
    JSON.stringify(
      {
        success: false,
        status: "waiting_admin_confirmation",
        reason: "waiting_admin_confirmation",
        message: "等待 Windows 管理员确认",
        started_at: new Date().toISOString()
      },
      null,
      2
    ),
    "utf8"
  );
}

async function startContactSyncAdminHelper() {
  if (!fs.existsSync(adminContactSyncHelperScript)) {
    return {
      ok: false,
      success: false,
      message: "没有找到管理员同步助手，请检查软件目录是否完整。"
    };
  }
  writeAdminSyncPendingResult();
  const helperArgs = [
    adminContactSyncHelperScript,
    "--result",
    adminContactSyncResultPath
  ];
  const pythonPath = resolvePythonExecutable();
  const argumentList = `@(${helperArgs.map(psSingleQuoted).join(",")})`;
  const cancelPayload = {
    success: false,
    status: "admin_confirmation_cancelled",
    reason: "admin_confirmation_cancelled",
    message: "没有完成 Windows 管理员确认，请重新点击静默同步通讯录并在弹窗里点击“是”。",
    completed_at: new Date().toISOString()
  };
  const command = [
    `$ErrorActionPreference = 'Stop'`,
    `try {`,
    `  Start-Process -FilePath ${psSingleQuoted(pythonPath)} -Verb RunAs -WindowStyle Hidden -Wait -ArgumentList ${argumentList}`,
    `} catch {`,
    `  ${psJsonWriteCommand(adminContactSyncResultPath, cancelPayload)}`,
    `}`
  ].join("; ");
  const child = spawn(
    "powershell.exe",
    ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
    {
      cwd: rootDir,
      windowsHide: true,
      detached: true,
      stdio: "ignore",
      shell: false
    }
  );
  child.unref();
  appendMainLog("admin-contact-sync", "requested one-shot elevated helper");
  return {
    ok: true,
    success: true,
    message: "已弹出管理员确认，请点击“是”。确认后软件会自动继续同步。"
  };
}

function getContactSyncAdminResult() {
  if (!fs.existsSync(adminContactSyncResultPath)) {
    return {
      ok: true,
      success: false,
      status: "not_started",
      reason: "not_started",
      message: "管理员同步助手还没有启动。"
    };
  }
  try {
    const parsed = JSON.parse(fs.readFileSync(adminContactSyncResultPath, "utf8"));
    return {
      ok: true,
      ...parsed
    };
  } catch (error) {
    return {
      ok: false,
      success: false,
      status: "result_unreadable",
      reason: "result_unreadable",
      message: error && error.message ? error.message : "管理员同步结果暂时不可读取。"
    };
  }
}

function spawnService(name, command, args, cwd, outLog, errLog) {
  const out = fs.openSync(outLog, "a");
  const err = fs.openSync(errLog, "a");
  const child = spawn(command, args, {
    cwd,
    windowsHide: true,
    stdio: ["ignore", out, err],
    shell: false
  });
  childProcesses.push({ name, child });
  appendMainLog("spawn", `${name} ${command} ${args.join(" ")}`);
  child.on("exit", () => {
    try {
      fs.closeSync(out);
      fs.closeSync(err);
    } catch {
      // Ignore log descriptor cleanup races.
    }
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

safeHandle("app:start-services", async () => {
  await ensureServices();
  return { ok: true };
}, "本地服务启动失败");
safeHandle("app:get-service-status", () => getServiceStatus(), "软件服务状态检查失败");
safeHandle("app:restart-services-admin", () => restartServicesAsAdmin(), "请求管理员权限重启失败");
safeHandle("app:start-contact-sync-admin-helper", () => startContactSyncAdminHelper(), "管理员同步助手启动失败");
safeHandle("app:get-contact-sync-admin-result", () => getContactSyncAdminResult(), "管理员同步结果读取失败");
safeHandle("app:enter-run-mode", () => enterRunMode(), "微信专用运行模式启动失败");
safeHandle("app:exit-run-mode", () => exitRunMode(), "退出运行模式失败");
safeHandle("task:pause", () => taskControl("pause"), "暂停任务失败");
safeHandle("task:resume", () => taskControl("resume"), "继续任务失败");
safeHandle("task:stop", () => taskControl("stop"), "停止任务失败");
safeHandle("task:status", async () => {
  const status = await httpRequest("GET", `${BACKEND_URL}/tasks/current`);
  if (status && status.error === "not_found") {
    throw new Error("backend_endpoint_missing:/tasks/current");
  }
  return status;
}, "悬浮窗状态接口暂不可用，请重启本地服务");

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
