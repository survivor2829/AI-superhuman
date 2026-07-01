const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("agentDesktop", {
  startServices: () => ipcRenderer.invoke("app:start-services"),
  getServiceStatus: () => ipcRenderer.invoke("app:get-service-status"),
  restartServicesAsAdmin: () => ipcRenderer.invoke("app:restart-services-admin"),
  enterRunMode: () => ipcRenderer.invoke("app:enter-run-mode"),
  exitRunMode: () => ipcRenderer.invoke("app:exit-run-mode"),
  pauseTask: () => ipcRenderer.invoke("task:pause"),
  resumeTask: () => ipcRenderer.invoke("task:resume"),
  stopTask: () => ipcRenderer.invoke("task:stop"),
  getTaskStatus: () => ipcRenderer.invoke("task:status"),
  onTaskRefresh: (callback) => {
    const listener = () => callback();
    ipcRenderer.on("task:refresh", listener);
    return () => ipcRenderer.removeListener("task:refresh", listener);
  }
});
