export type EditorSettings = {
  volume: number;
  speed: number;
  notePreview: boolean;
  previewVolume: number;
  bpm: number;
  snapEnabled: boolean;
};

export type BackendApi = {
  ping(): Promise<{ ok: boolean; app: string; ui: string }>;
  get_settings(): Promise<EditorSettings>;
  update_settings(changes: Partial<EditorSettings>): Promise<EditorSettings>;
};

declare global {
  interface Window {
    pywebview?: { api?: BackendApi };
  }
}

export async function getBackendApi(timeoutMs = 3000): Promise<BackendApi | null> {
  if (window.pywebview?.api) return window.pywebview.api;

  return await new Promise((resolve) => {
    const onReady = () => {
      window.clearTimeout(timer);
      resolve(window.pywebview?.api ?? null);
    };
    const timer = window.setTimeout(() => {
      window.removeEventListener("pywebviewready", onReady);
      resolve(null);
    }, timeoutMs);
    window.addEventListener("pywebviewready", onReady, { once: true });
  });
}
