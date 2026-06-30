const { app, BrowserWindow } = require("electron");
const path = require("path");

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1080,
    minHeight: 720,
    title: "Agent MVP",
    backgroundColor: "#f7f8fb"
  });

  const devUrl = process.env.VITE_DEV_SERVER_URL || "http://127.0.0.1:5173";
  if (process.env.NODE_ENV === "production") {
    win.loadFile(path.join(__dirname, "../dist/index.html"));
  } else {
    win.loadURL(devUrl);
  }
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
