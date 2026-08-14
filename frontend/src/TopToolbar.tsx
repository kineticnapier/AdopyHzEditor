import type { PlaybackState, ViewState } from "./bridge";

type Props = {
  connected: boolean; busy: boolean; audioName: string | null; dirty: boolean; playback: PlaybackState; view: ViewState;
  onOpen(): void; onLoadProject(): void; onSaveProject(): void; onSeek(time: number): void; onStop(): void; onPlay(): void; onSeekRelative(delta: number): void;
  onImportMidi(): void; onExportMidi(): void; onExportAdo(): void; onHelp(): void; onMode(mode: ViewState["mode"]): void;
};
function formatTime(seconds: number) { const totalMs = Math.max(0, Math.round((seconds || 0) * 1000)); const minutes = Math.floor(totalMs / 60000); const sec = Math.floor((totalMs % 60000) / 1000); const ms = totalMs % 1000; return `${minutes}:${String(sec).padStart(2, "0")}.${String(ms).padStart(3, "0")}`; }
export default function TopToolbar(p: Props) {
  return <>
    <header className="titlebar"><div className="title-left"><strong>AdopyHzEditor</strong><span className="document-name">{p.audioName ?? "Blank workspace"}{p.dirty ? " •" : ""}</span></div><span className={p.connected ? "status-pill on" : "status-pill"}>{p.connected ? "Python connected" : "Browser preview"}</span></header>
    <div className="toolbar">
      <button title="Open audio (Ctrl+O)" onClick={p.onOpen} disabled={!p.connected || p.busy}>Audio</button><button title="Load project (Ctrl+L)" onClick={p.onLoadProject} disabled={!p.connected || p.busy}>Project ↓</button><button title="Save project (Ctrl+S)" onClick={p.onSaveProject} disabled={!p.connected || p.busy}>Project ↑</button><i />
      <button title="First" onClick={() => p.onSeek(0)}>↶</button><button title="Stop (Ctrl+Space)" onClick={p.onStop}>■</button><button className={p.playback.playing ? "play active" : "play"} title="Play / pause (Space)" onClick={p.onPlay}>▶</button><button onClick={() => p.onSeekRelative(-1)}>−1s</button><button onClick={() => p.onSeekRelative(1)}>+1s</button><i />
      <button title="Import MIDI (Ctrl+I)" onClick={p.onImportMidi} disabled={!p.connected || p.busy}>MIDI ↓</button><button title="Export MIDI (Ctrl+M)" onClick={p.onExportMidi}>MIDI ↑</button><button title="Export ADOFAI (Ctrl+E)" onClick={p.onExportAdo}>ADOFAI ↑</button><span className="toolbar-spacer" />
      <button className={p.view.mode === "spec" ? "selected" : ""} onClick={() => p.onMode("spec")}>Spec</button><button className={p.view.mode === "notes" ? "selected" : ""} onClick={() => p.onMode("notes")}>Notes</button><button className={p.view.mode === "both" ? "selected" : ""} onClick={() => p.onMode("both")}>Both</button><button title="Help (F1)" onClick={p.onHelp}>?</button><output>{formatTime(p.playback.time)} / {formatTime(p.playback.duration)}</output>
    </div>
  </>;
}