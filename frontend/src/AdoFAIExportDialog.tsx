import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { AdoFAIDebugPreview, AdoFAIExportOptions, AdoFAITilePreview, BackendApi } from "./bridge";

type Tab = "basic" | "harmony" | "advanced" | "final" | "song" | "preview";

type Props = {
  api: BackendApi;
  selected: number[];
  onClose(): void;
  onStatus(text: string): void;
  onHelp(section?: string): void;
};

const tabs: Array<[Tab, string]> = [
  ["basic", "基本"],
  ["harmony", "Harmony"],
  ["advanced", "詳細"],
  ["final", "端数タイル"],
  ["song", "音声"],
  ["preview", "Preview"],
];

export default function AdoFAIExportDialog({ api, selected, onClose, onStatus, onHelp }: Props) {
  const [options, setOptions] = useState<AdoFAIExportOptions | null>(null);
  const [tab, setTab] = useState<Tab>("basic");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [tilePreview, setTilePreview] = useState<AdoFAITilePreview | null>(null);
  const [debugPreview, setDebugPreview] = useState<AdoFAIDebugPreview | null>(null);

  useEffect(() => {
    let alive = true;
    void api.get_adofai_export_defaults(selected).then((value) => {
      if (alive) setOptions(value);
    }).catch((e) => alive && setError(String(e)));
    return () => { alive = false; };
  }, [api, selected]);

  function patch<K extends keyof AdoFAIExportOptions>(key: K, value: AdoFAIExportOptions[K]) {
    setOptions((old) => old ? { ...old, [key]: value } : old);
  }

  async function run<T>(action: () => Promise<T>): Promise<T | null> {
    setWorking(true);
    setError("");
    try {
      return await action();
    } catch (e) {
      setError(String(e));
      return null;
    } finally {
      setWorking(false);
    }
  }

  async function exportLevel() {
    if (!options) return;
    const result = await run(() => api.export_adofai_advanced(options, selected));
    if (!result) return;
    onStatus(result.status);
    if (result.ok) onClose();
  }

  async function loadTilePreview() {
    if (!options) return;
    const result = await run(() => api.preview_adofai_tiles(options, selected));
    if (result) {
      setTilePreview(result);
      setDebugPreview(null);
      setTab("preview");
    }
  }

  async function loadDebugPreview() {
    if (!options) return;
    const result = await run(() => api.preview_adofai_debug(options, selected));
    if (result) {
      setDebugPreview(result);
      setTilePreview(null);
      setTab("preview");
    }
  }

  if (!options) {
    return <Modal title="ADOFAI Export" onClose={onClose}><div className="dialog-loading">Loading export settings…</div></Modal>;
  }

  return <Modal title="ADOFAI Export" onClose={onClose} wide>
    <div className="dialog-tabs">
      {tabs.map(([id, label]) => <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}</button>)}
    </div>
    <div className="dialog-body export-dialog-body">
      {tab === "basic" && <>
        <Field label="Method"><Select value={options.method} onChange={(v) => patch("method", v as AdoFAIExportOptions["method"])} options={[["rabbit_zip", "Angle Compression"], ["angle_only", "Angle-only"], ["harmony", "Harmony / Polyrhythm"]]} /></Field>
        <Field label="Base BPM"><NumberInput value={options.baseBpm} min={1} max={999999} step={0.001} onChange={(v) => patch("baseBpm", v)} /></Field>
        <Field label="Angle-only BPM"><NumberInput value={options.angleOnlyBpm} min={1} max={999999} step={1} onChange={(v) => patch("angleOnlyBpm", v)} /></Field>
        <Field label="Track visual"><Select value={options.trackVisual} onChange={(v) => patch("trackVisual", v as AdoFAIExportOptions["trackVisual"])} options={[["normal", "Normal"], ["faint", "Faint"], ["very faint", "Very faint"], ["hidden", "Hidden"]]} /></Field>
        <Field label="Visual path"><Select value={options.visualPathMode} onChange={(v) => patch("visualPathMode", v as AdoFAIExportOptions["visualPathMode"])} options={[["raw", "Raw"], ["upward", "Upward"], ["upward avoid", "Upward avoid"], ["twirl upward", "Twirl upward"]]} /></Field>
        <Field label="Path angle"><NumberInput value={options.visualPathAngle} min={0} max={359.999} step={1} onChange={(v) => patch("visualPathAngle", v)} suffix="°" /></Field>
        <Field label="Position"><Select value={options.visualPositionMode} onChange={(v) => patch("visualPositionMode", v as AdoFAIExportOptions["visualPositionMode"])} options={[["off", "Off"], ["note step", "Note step"]]} /></Field>
        <Field label="Position X"><NumberInput value={options.visualPositionX} min={-100000} max={100000} step={1} onChange={(v) => patch("visualPositionX", v)} /></Field>
        <Field label="Position Y"><NumberInput value={options.visualPositionY} min={-100000} max={100000} step={1} onChange={(v) => patch("visualPositionY", v)} /></Field>
      </>}

      {tab === "harmony" && <>
        <Field label="Harmony"><Select value={options.harmonyMode} onChange={(v) => patch("harmonyMode", v)} options={[
          ["off", "Off"], ["octave +12", "Octave +12"], ["fifth +7", "Fifth +7"], ["major third +4", "Major third +4"], ["minor third +3", "Minor third +3"], ["lower octave -12", "Lower octave -12"], ["major triad", "Major triad"], ["minor triad", "Minor triad"], ["sus4", "sus4"], ["dominant 7", "Dominant 7"], ["custom", "Custom"],
        ]} /></Field>
        <Field label="Custom semitone"><NumberInput value={options.harmonyCustomSemitone} min={-48} max={48} step={0.1} onChange={(v) => patch("harmonyCustomSemitone", v)} /></Field>
        <Field label="Epsilon"><NumberInput value={options.harmonyEpsilonMs} min={0.000001} max={10} step={0.001} onChange={(v) => patch("harmonyEpsilonMs", v)} suffix=" ms" /></Field>
        <Field label="Tuning"><Select value={options.harmonyTuning} onChange={(v) => patch("harmonyTuning", v as AdoFAIExportOptions["harmonyTuning"])} options={[["equal temperament", "Equal temperament"], ["just intonation", "Just intonation"]]} /></Field>
        <Field label="Root mode"><Select value={options.harmonyRootMode} onChange={(v) => patch("harmonyRootMode", v)} options={[["fixed root", "Fixed root"], ["least squares Hz", "Least squares Hz"], ["least squares cents", "Least squares cents"], ["minimax cents", "Minimax cents"]]} /></Field>
        <Field label="Timing"><Select value={options.harmonyTimingMode} onChange={(v) => patch("harmonyTimingMode", v as AdoFAIExportOptions["harmonyTimingMode"])} options={[["setspeed", "SetSpeed"], ["angle-only", "Angle-only"], ["ratio-polyrhythm", "Ratio-polyrhythm"]]} /></Field>
        <Field label="Visual mode"><Select value={options.harmonyVisualMode} onChange={(v) => patch("harmonyVisualMode", v)} options={[["raw", "Raw"], ["round 45°", "Round 45°"], ["round 90°", "Round 90°"], ["custom step", "Custom step"]]} /></Field>
        <Field label="Visual step"><NumberInput value={options.harmonyVisualStep} min={1} max={180} step={1} onChange={(v) => patch("harmonyVisualStep", v)} suffix="°" /></Field>
        <Field label="Poly cycle"><NumberInput value={options.harmonyPolyCycleAngle} min={1} max={100000} step={1} onChange={(v) => patch("harmonyPolyCycleAngle", v)} suffix="°" /></Field>
        <Field label="Max denominator"><NumberInput value={options.harmonyPolyMaxDenominator} min={1} max={256} step={1} integer onChange={(v) => patch("harmonyPolyMaxDenominator", v)} /></Field>
        <Field label="Octave ratio"><Select value={options.harmonyPolyRatioOctaveMode} onChange={(v) => patch("harmonyPolyRatioOctaveMode", v as AdoFAIExportOptions["harmonyPolyRatioOctaveMode"])} options={[["octave-folded", "Octave-folded"], ["absolute", "Absolute"]]} /></Field>
      </>}

      {tab === "advanced" && <>
        <Field label="Change x"><Select value={options.xMode} onChange={(v) => patch("xMode", v as AdoFAIExportOptions["xMode"])} options={[["floor", "Floor"], ["lowest_floor", "Lowest floor"], ["round", "Round"], ["ceil", "Ceil"], ["fixed", "Fixed"], ["target_bpm", "Target BPM"]]} /></Field>
        <Field label="Fixed x"><NumberInput value={options.fixedX} min={0.000001} max={100000} step={0.1} onChange={(v) => patch("fixedX", v)} /></Field>
        <Field label="Target BPM"><NumberInput value={options.targetBpm} min={1} max={999999} step={1} onChange={(v) => patch("targetBpm", v)} /></Field>
        <Field label="Max tiles"><NumberInput value={options.maxTiles} min={0} max={10000000} step={10000} integer onChange={(v) => patch("maxTiles", v)} /><small>0 = unlimited</small></Field>
        <Field label="Per note"><NumberInput value={options.maxTilesPerNote} min={0} max={1000000} step={500} integer onChange={(v) => patch("maxTilesPerNote", v)} /><small>0 = unlimited</small></Field>
        <Field label="Selection"><label className="inline-check"><input type="checkbox" checked={options.selectedOnly} disabled={selected.length === 0} onChange={(e) => patch("selectedOnly", e.target.checked)} /> Selected notes only ({selected.length})</label></Field>
      </>}

      {tab === "final" && <>
        <Field label="Final mode"><Select value={options.finalAngleMode} onChange={(v) => patch("finalAngleMode", v as AdoFAIExportOptions["finalAngleMode"])} options={[["scaled", "Scaled"], ["cardinal", "Cardinal"], ["horizontal", "Horizontal"], ["custom", "Custom"]]} /></Field>
        <Field label="Custom angle"><NumberInput value={options.finalCustomAngle} min={0.001} max={359.999} step={1} onChange={(v) => patch("finalCustomAngle", v)} suffix="°" /></Field>
        <Field label="Cardinal step"><NumberInput value={options.finalCardinalStep} min={1} max={180} step={1} onChange={(v) => patch("finalCardinalStep", v)} suffix="°" /></Field>
        <div className="info-card">Phase-continuous glide is enabled by default, matching the current PySide6 exporter.</div>
      </>}

      {tab === "song" && <>
        <Field label="Project audio"><label className="inline-check"><input type="checkbox" checked={options.useProjectSong} onChange={(e) => patch("useProjectSong", e.target.checked)} /> Use current audio</label></Field>
        <Field label="Copy audio"><label className="inline-check"><input type="checkbox" checked={options.copyProjectSong} disabled={!options.useProjectSong} onChange={(e) => patch("copyProjectSong", e.target.checked)} /> Copy next to level</label></Field>
        <Field label="Offset"><label className="inline-check"><input type="checkbox" checked={options.songOffsetAuto} disabled={!options.useProjectSong} onChange={(e) => patch("songOffsetAuto", e.target.checked)} /> Use first note start</label></Field>
        <Field label="songOffset"><NumberInput value={options.songOffsetMs} min={-3600000} max={3600000} step={1} disabled={!options.useProjectSong || options.songOffsetAuto} onChange={(v) => patch("songOffsetMs", v)} suffix=" ms" /></Field>
      </>}

      {tab === "preview" && <div className="preview-tab">
        <div className="preview-actions">
          <button onClick={() => void loadTilePreview()} disabled={working}>Tile Preview</button>
          <button onClick={() => void loadDebugPreview()} disabled={working}>Debug Preview</button>
          <button onClick={() => onHelp("adofai_export")}>Export Help</button>
        </div>
        {tilePreview && <TilePreview preview={tilePreview} />}
        {debugPreview && <DebugPreview preview={debugPreview} />}
        {!tilePreview && !debugPreview && <div className="info-card">Preview uses the same Python exporter as the final file, so tile counts and geometry are generated from the current settings.</div>}
      </div>}
    </div>
    {error && <div className="dialog-error">{error}</div>}
    <div className="dialog-footer">
      <button onClick={onClose}>Cancel</button>
      <button onClick={() => void loadTilePreview()} disabled={working}>Preview</button>
      <button className="primary" onClick={() => void exportLevel()} disabled={working}>{working ? "Working…" : "Export"}</button>
    </div>
  </Modal>;
}

function Modal({ title, onClose, wide, children }: { title: string; onClose(): void; wide?: boolean; children: ReactNode }) {
  return <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
    <section className={wide ? "modal-window wide" : "modal-window"} role="dialog" aria-modal="true">
      <header className="modal-title"><strong>{title}</strong><button aria-label="Close" onClick={onClose}>×</button></header>
      {children}
    </section>
  </div>;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="dialog-field"><span>{label}</span><div>{children}</div></label>;
}

function Select({ value, options, onChange }: { value: string; options: Array<[string, string]>; onChange(value: string): void }) {
  return <select value={value} onChange={(e) => onChange(e.target.value)}>{options.map(([v, label]) => <option key={v} value={v}>{label}</option>)}</select>;
}

function NumberInput({ value, min, max, step, integer, disabled, suffix, onChange }: { value: number; min: number; max: number; step: number; integer?: boolean; disabled?: boolean; suffix?: string; onChange(value: number): void }) {
  return <div className="number-with-suffix"><input type="number" value={Number.isFinite(value) ? value : 0} min={min} max={max} step={step} disabled={disabled} onChange={(e) => { const v = integer ? Math.round(Number(e.target.value)) : Number(e.target.value); if (Number.isFinite(v)) onChange(v); }} />{suffix && <span>{suffix}</span>}</div>;
}

function TilePreview({ preview }: { preview: AdoFAITilePreview }) {
  const geometry = useMemo(() => {
    const points = preview.points;
    if (!points.length) return null;
    let minX = points[0].x, maxX = points[0].x, minY = points[0].y, maxY = points[0].y;
    for (const p of points) { minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x); minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y); }
    const pad = Math.max(2, Math.max(maxX - minX, maxY - minY) * 0.04);
    const d = points.map((p, i) => `${i ? "L" : "M"} ${p.x} ${-p.y}`).join(" ");
    return { d, viewBox: `${minX - pad} ${-maxY - pad} ${Math.max(1, maxX - minX + pad * 2)} ${Math.max(1, maxY - minY + pad * 2)}` };
  }, [preview]);
  if (!geometry) return <div className="info-card">No tiles.</div>;
  return <div className="tile-preview-wrap">
    <div className="preview-summary">{preview.shownTiles} / {preview.totalTiles} tiles{preview.limited ? " (preview limited)" : ""}</div>
    <svg className="tile-preview-svg" viewBox={geometry.viewBox} preserveAspectRatio="xMidYMid meet">
      <path d={geometry.d} className="tile-track-outline" />
      <path d={geometry.d} className="tile-track" />
      {preview.points.length > 0 && <><circle cx={preview.points[0].x} cy={-preview.points[0].y} r="0.35" className="tile-start" /><circle cx={preview.points[preview.points.length - 1].x} cy={-preview.points[preview.points.length - 1].y} r="0.35" className="tile-end" /></>}
    </svg>
    <Stats stats={preview.stats} />
  </div>;
}

function DebugPreview({ preview }: { preview: AdoFAIDebugPreview }) {
  const columns = preview.rows.length ? Object.keys(preview.rows[0]) : [];
  const rows = preview.rows.slice(0, 1000);
  async function copy(fmt: "tsv" | "csv") {
    const sep = fmt === "csv" ? "," : "\t";
    const quote = (v: unknown) => { const s = String(v ?? ""); return fmt === "csv" && /[",\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s; };
    const text = [columns.map(quote).join(sep), ...preview.rows.map((r) => columns.map((c) => quote(r[c])).join(sep))].join("\n");
    await navigator.clipboard.writeText(text);
  }
  return <div className="debug-preview">
    <div className="preview-summary">Rows {preview.summary.rows} · Estimated tiles {preview.summary.estimatedTiles} · warnings {preview.summary.warnings}{preview.limited ? " · first 5000 rows loaded" : ""}</div>
    <div className="preview-actions"><button onClick={() => void copy("tsv")}>Copy TSV</button><button onClick={() => void copy("csv")}>Copy CSV</button></div>
    <div className="debug-table-wrap"><table><thead><tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr></thead><tbody>{rows.map((row, i) => <tr key={i}>{columns.map((c) => <td key={c}>{String(row[c] ?? "")}</td>)}</tr>)}</tbody></table></div>
  </div>;
}

function Stats({ stats }: { stats: Record<string, unknown> }) {
  const keys = ["method", "tiles_total", "floors_total", "actions_total", "first_note_offset_seconds", "harmony_mode", "harmony_tuning", "harmony_timing_mode", "rabbit_target_bpm", "target_angle_override_events", "songFilename", "song_offset_ms"];
  return <div className="stats-grid">{keys.filter((k) => k in stats).map((k) => <div key={k}><span>{k}</span><b>{String(stats[k])}</b></div>)}</div>;
}