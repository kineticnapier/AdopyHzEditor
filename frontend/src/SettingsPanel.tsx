import { useState, type ReactNode } from "react";
import type { AppState, BackendApi, EditorSettings, NoteMutationResult } from "./bridge";

type Page = "playback" | "export" | "grid" | "view" | "analysis" | "curve";
const pages: Array<[Page, string]> = [
  ["playback", "再生"], ["export", "出力"], ["grid", "グリッド"],
  ["view", "表示"], ["analysis", "解析"], ["curve", "カーブ"],
];

type Props = {
  api: BackendApi | null;
  settings: EditorSettings;
  selected: number[];
  audioName: string | null;
  busy: boolean;
  onPatch(changes: Partial<EditorSettings>): Promise<void>;
  onStateAction(action: () => Promise<AppState>): Promise<void>;
  onMutation(result: NoteMutationResult, nextSelection?: number[]): void;
};

export default function SettingsPanel({ api, settings, selected, audioName, busy, onPatch, onStateAction, onMutation }: Props) {
  const [page, setPage] = useState<Page>("playback");
  return (
    <aside className="settings">
      <h2>設定</h2>
      <nav>{pages.map(([id, label]) => <button key={id} className={page === id ? "active" : ""} onClick={() => setPage(id)}>{label}</button>)}</nav>
      <div className="settings-body">
        {page === "playback" && <>
          <Row label="Song Vol"><Range value={settings.volume} onChange={(value) => void onPatch({ volume: value })} /></Row>
          <Row label="Speed"><NumberInput value={settings.speed} min={0.1} max={4} step={0.05} onChange={(value) => void onPatch({ speed: value })} /></Row>
          <Row label="Note Preview"><input type="checkbox" checked={settings.notePreview} onChange={(e) => void onPatch({ notePreview: e.target.checked })} /></Row>
          <Row label="Note Vol"><Range value={settings.previewVolume} disabled={!settings.notePreview} onChange={(value) => void onPatch({ previewVolume: value })} /></Row>
          <Row label="Preview Oct"><NumberInput value={settings.previewOctave} min={-4} max={4} step={1} disabled={!settings.notePreview} onChange={(value) => void onPatch({ previewOctave: value })} /></Row>
          <Row label="Preview Sound"><Select value={settings.previewSound} disabled={!settings.notePreview} values={["sine", "piano", "organ", "square", "triangle"]} onChange={(value) => void onPatch({ previewSound: value })} /></Row>
        </>}
        {page === "export" && <>
          <Row label="Export Oct"><NumberInput value={settings.exportOctave} min={-4} max={4} step={1} onChange={(value) => void onPatch({ exportOctave: value })} /></Row>
          <Row label="Export Semi"><NumberInput value={settings.exportSemitone} min={-12} max={12} step={1} onChange={(value) => void onPatch({ exportSemitone: value })} /></Row>
          <div className="hint">Export pitch = note pitch + Export Oct × 12 + Export Semi</div>
        </>}
        {page === "grid" && <>
          <Row label="Grid"><input type="checkbox" checked={settings.gridEnabled} onChange={(e) => void onPatch({ gridEnabled: e.target.checked })} /></Row>
          <Row label="Metronome"><input type="checkbox" checked={settings.metronomeEnabled} onChange={(e) => void onPatch({ metronomeEnabled: e.target.checked })} /></Row>
          <Row label="BPM"><NumberInput value={settings.bpm} min={1} max={10000} step={0.1} onChange={(value) => void onPatch({ bpm: value })} /></Row>
          <Row label="Offset"><NumberInput value={settings.offsetMs} min={-600000} max={600000} step={1} suffix=" ms" onChange={(value) => void onPatch({ offsetMs: value })} /></Row>
          <Row label="Metro Vol"><Range value={settings.metronomeVolume} disabled={!settings.metronomeEnabled} onChange={(value) => void onPatch({ metronomeVolume: value })} /></Row>
          <Row label="Snap"><input type="checkbox" checked={settings.snapEnabled} onChange={(e) => void onPatch({ snapEnabled: e.target.checked })} /></Row>
          <Row label="Snap div"><NumberInput value={settings.snapDiv} min={1} max={64} step={1} disabled={!settings.snapEnabled} onChange={(value) => void onPatch({ snapDiv: value })} /></Row>
        </>}
        {page === "view" && <>
          <Row label="Contrast"><Range value={settings.contrast} min={0} max={300} onChange={(value) => void onPatch({ contrast: value })} /></Row>
          <Row label="Gamma"><Range value={settings.gamma} min={5} max={500} onChange={(value) => void onPatch({ gamma: value })} /></Row>
          <Row label="Enhance"><input type="checkbox" checked={settings.enhance} onChange={(e) => void onPatch({ enhance: e.target.checked })} /></Row>
          <Row label="Display"><Select value={settings.displayMode} values={["wavetone", "ridge", "smooth"]} onChange={(value) => void onPatch({ displayMode: value })} /></Row>
          <Row label="Harmonics"><Select value={settings.harmonics} values={["off", "soft", "strong"]} onChange={(value) => void onPatch({ harmonics: value })} /></Row>
          <Row label="Colormap"><Select value={settings.colormap} values={["wavetone", "viridis", "magma", "inferno", "plasma", "gray"]} onChange={(value) => void onPatch({ colormap: value })} /></Row>
        </>}
        {page === "analysis" && <>
          <Row label="Analysis"><Select value={settings.analysisProfile} values={["Fast", "Normal", "Precise", "Full C0-C10"]} onChange={(value) => void onPatch({ analysisProfile: value })} /></Row>
          <Row label="CQT Resolution"><Select value={settings.cqtResolution} values={["profile default", "100 cents", "50 cents", "25 cents", "12.5 cents", "41 EDO", "53 EDO"]} onChange={(value) => void onPatch({ cqtResolution: value })} /></Row>
          <button className="wide" disabled={!api || !audioName || busy} onClick={() => void onStateAction(() => api!.reanalyze_audio())}>音声を再解析</button>
          <div className="hint">解析設定の変更は再解析後に反映されます。</div>
        </>}
        {page === "curve" && <>
          <Row label="Curve"><Select value={settings.curveShape} values={["ease", "s_curve", "linear", "ease_in", "ease_out"]} onChange={(value) => void onPatch({ curveShape: value })} /></Row>
          <Row label="Interp"><Select value={settings.curveInterpolation} values={["bezier_pitch", "linear_pitch", "linear_hz", "bezier_hz"]} onChange={(value) => void onPatch({ curveInterpolation: value })} /></Row>
          <button className="wide" disabled={!api || selected.length === 0} onClick={() => void api!.apply_interpolation(selected).then((x) => onMutation(x, selected))}>補間を適用</button>
          <Row label="Target Angle"><NumberInput value={settings.targetAngle} min={0.001} max={359.999} step={0.001} suffix="°" onChange={(value) => void onPatch({ targetAngle: value })} /></Row>
          <div className="button-row">
            <button disabled={!api || selected.length === 0} onClick={() => void api!.apply_target_angle(selected).then((x) => onMutation(x, selected))}>角度を適用</button>
            <button disabled={!api || selected.length === 0} onClick={() => void api!.clear_target_angle(selected).then((x) => onMutation(x, selected))}>角度を解除</button>
          </div>
          <div className="hint">Alt+ドラッグでCurve。選択中: {selected.length} note(s)</div>
        </>}
      </div>
    </aside>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) { return <label className="row"><span>{label}</span><div>{children}</div></label>; }
function Range({ value, min = 0, max = 100, disabled = false, onChange }: { value: number; min?: number; max?: number; disabled?: boolean; onChange(value: number): void }) { return <div className="range-wrap"><input type="range" min={min} max={max} value={value} disabled={disabled} onChange={(e) => onChange(+e.target.value)} /><output>{value}</output></div>; }
function NumberInput({ value, min, max, step, suffix, disabled = false, onChange }: { value: number; min: number; max: number; step: number; suffix?: string; disabled?: boolean; onChange(value: number): void }) { return <div className="number-wrap"><input type="number" value={value} min={min} max={max} step={step} disabled={disabled} onChange={(e) => onChange(+e.target.value)} />{suffix && <span>{suffix}</span>}</div>; }
function Select({ value, values, disabled = false, onChange }: { value: string; values: string[]; disabled?: boolean; onChange(value: string): void }) { return <select value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>{values.map((item) => <option key={item} value={item}>{item}</option>)}</select>; }
