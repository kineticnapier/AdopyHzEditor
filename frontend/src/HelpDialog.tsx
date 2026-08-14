import { useEffect, useState } from "react";
import type { BackendApi, HelpPayload } from "./bridge";

type Props = { api: BackendApi; initialSection?: string; onClose(): void };

export default function HelpDialog({ api, initialSection = "quick_start", onClose }: Props) {
  const [payload, setPayload] = useState<HelpPayload | null>(null);
  const [section, setSection] = useState(initialSection);
  useEffect(() => { let alive = true; void api.get_help_sections().then((x) => alive && setPayload(x)); return () => { alive = false; }; }, [api]);
  const current = payload?.sections.find((x) => x.id === section) ?? payload?.sections[0];
  return <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
    <section className="modal-window help-window" role="dialog" aria-modal="true">
      <header className="modal-title"><strong>Help</strong><button onClick={onClose}>×</button></header>
      {!payload ? <div className="dialog-loading">Loading help…</div> : <>
        <div className="help-header">{payload.header}</div>
        <div className="help-layout">
          <nav>{payload.sections.map((x) => <button key={x.id} className={current?.id === x.id ? "active" : ""} onClick={() => setSection(x.id)}>{x.title}</button>)}</nav>
          <article><h2>{current?.title}</h2><pre>{current?.body}</pre></article>
        </div>
        <div className="dialog-footer"><button onClick={() => void api.open_releases_page()}>Releases</button><span /><button className="primary" onClick={onClose}>Close</button></div>
      </>}
    </section>
  </div>;
}