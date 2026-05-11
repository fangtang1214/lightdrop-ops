const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("lightdrop", {
  getServiceStatus: () => ipcRenderer.invoke("services:status"),
  openWebFrontend: () => ipcRenderer.invoke("services:open-web"),
  openWebFrontendInBrowser: () => ipcRenderer.invoke("services:open-web-browser"),
  openLanWebFrontendInBrowser: () => ipcRenderer.invoke("services:open-lan-web-browser"),
  onServicesChanged: (callback) => {
    const listener = () => callback();
    ipcRenderer.on("services:changed", listener);
    return () => ipcRenderer.removeListener("services:changed", listener);
  },
});
