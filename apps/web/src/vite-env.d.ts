/// <reference types="vite/client" />

interface LightDropServiceStatus {
  backendReady: boolean;
  webReady: boolean;
  backendUrl: string;
  webUrl: string;
  lanBackendUrl: string | null;
  lanWebUrl: string | null;
  servicesStarting: boolean;
  startedBackend: boolean;
  startedWeb: boolean;
}

interface LightDropBridge {
  getServiceStatus: () => Promise<LightDropServiceStatus>;
  openWebFrontend: () => Promise<LightDropServiceStatus>;
  openWebFrontendInBrowser: () => Promise<LightDropServiceStatus>;
  openLanWebFrontendInBrowser: () => Promise<LightDropServiceStatus>;
  onServicesChanged: (callback: () => void) => () => void;
}

interface Window {
  lightdrop?: LightDropBridge;
}
