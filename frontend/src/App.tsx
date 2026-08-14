import { useEffect, useState, type ReactNode } from "react";
import { getBackendApi, type BackendApi, type EditorSettings } from "./bridge";

const defaults: EditorSettings = {
  volume: 85,
  speed: 1,
  notePreview: true,
  previewVolume: 20,
  bpm: 120,
  snapEnabled: false,
};

type Page = "playback" | "export" | "grid" | "view" | "analysis" | "curve";
const pages: Array<[Page, string]> = [
  ["playback", "再生"], ["export", "出力"], ["grid", "グリッド"],
  ["view", "表示"], ["analysis", "解析"], ["curve", "カーブ"],
];

export default function App() {
  const [api, setApi] = useState<BackendApi | null>(null);
  const [connected, setConnected] = useState(false);
  const [page, setPage] = useState<Page>("playback");
  const [settings, setSettings] = useState(defaults);

  useEffect(() => {
    void getBackendApi().then(async (backend) => {
      if (!backend) return;
      setApi(backend);
      setConnected((await backend.ping()).ok);
      setSettings(await backend.get_settings());
    });
  }, []);

  async function patch(changes: Partial<EditorSettings>) {
    setSettings((value) => ({ ...value, ...changes }));
    if (api) setSettings(await api.update_settings(changes));
  }

  return (
    <div className="app">
      <header className="titlebar">
        <strong>AdopyHzEditor</strong>
        <span className={connected ? "status on" : "status"}>
          {connected ? "Python connected" : "Browser preview"}
        </span>
      </header>

      <div className="toolbar">
        <button>↶</button><button>■</button><button className="play">▶</button>
        <button>−1s</button><button>+1s</button><i />
        <button>MIDI ↓</button><button>MIDI ↑</button><button>ADOFAI ↑</button>
        <span /><button className="selected">Spec</button><button>Notes</button><button>Both</button>
        <output>0:00.000 / 0:00.000</output>
      </div>

      <main className="workspace">
        <section className="editor">
          <div className="canvas"><div>Editor surface<br /><small>描画部分は次の移植段階</small></div></div>
          <div className="timeline"><b>Timeline</b><input type="range" /><span>Window</span><input type="number" defaultValue={12} /><span>Pitch</span><input type="number" defaultValue={12} /><button>−12</button><button>+12</button><button>Fit</button></div>
        </section>

        <aside className="settings">
          <h2>設定</h2>
          <nav>{pages.map(([id, label]) => <button key={id} className={page === id ? "active" : ""} onClick={() => setPage(id)}>{label}</button>)}</nav>
          <div className="settings-body">
            {page === "playback" && <>
              <Row label="Song Vol"><input type="range" min="0" max="100" value={settings.volume} onChange={(e) => void patch({ volume: +e.target.value })} /></Row>
              <Row label="Speed"><input type="number" min="0.1" max="4" step="0.05" value={settings.speed} onChange={(e) => void patch({ speed: +e.target.value })} /></Row>
              <Row label="Note Preview"><input type="checkbox" checked={settings.notePreview} onChange={(e) => void patch({ notePreview: e.target.checked })} /></Row>
              <Row label="Note Vol"><input type="range" min="0" max="100" value={settings.previewVolume} disabled={!settings.notePreview} onChange={(e) => void patch({ previewVolume: +e.target.value })} /></Row>
            </>}
            {page === "grid" && <>
              <Row label="BPM"><input type="number" min="1" max="10000" value={settings.bpm} onChange={(e) => void patch({ bpm: +e.target.value })} /></Row>
              <Row label="Snap"><input type="checkbox" checked={settings.snapEnabled} onChange={(e) => void patch({ snapEnabled: e.target.checked })} /></Row>
            </>}
            {page !== "playback" && page !== "grid" && <div className="placeholder">{pages.find(([id]) => id === page)?.[1]}設定をここへ移植</div>}
          </div>
        </aside>
      </main>
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return <label className="row"><span>{label}</span><div>{children}</div></label>;
}
