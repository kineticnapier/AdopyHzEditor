import type { ReactNode } from "react";
import type { PlaybackState, ViewState } from "./bridge";

type Props = {
  connected:boolean; busy:boolean; audioName:string|null; dirty:boolean; playback:PlaybackState; view:ViewState; menus?:ReactNode;
  onOpen():void; onLoadProject():void; onSaveProject():void; onSeek(time:number):void; onStop():void; onPlay():void; onSeekRelative(delta:number):void;
  onImportMidi():void; onExportMidi():void; onExportAdo():void; onHelp():void; onMode(mode:ViewState["mode"]):void;
};
function formatTime(seconds:number){const totalMs=Math.max(0,Math.round((seconds||0)*1000)),minutes=Math.floor(totalMs/60000),sec=Math.floor((totalMs%60000)/1000),ms=totalMs%1000;return `${minutes}:${String(sec).padStart(2,"0")}.${String(ms).padStart(3,"0")}`}
export default function TopToolbar(p:Props){return <>
  <header className="titlebar"><div className="title-left"><strong>AdopyHzEditor</strong><span className="document-name">{p.audioName??"空のワークスペース"}{p.dirty?" •":""}</span>{p.menus}</div><span className={p.connected?"status-pill on":"status-pill"}>{p.connected?"Python 接続済み":"ブラウザプレビュー"}</span></header>
  <div className="toolbar">
    <button title="音声を開く (Ctrl+O)" onClick={p.onOpen} disabled={!p.connected||p.busy}>音声</button><button title="プロジェクトを開く (Ctrl+L)" onClick={p.onLoadProject} disabled={!p.connected||p.busy}>読込</button><button title="プロジェクトを保存 (Ctrl+S)" onClick={p.onSaveProject} disabled={!p.connected||p.busy}>保存</button><i/>
    <button title="先頭へ" onClick={()=>p.onSeek(0)}>↶</button><button title="停止 (Ctrl+Space)" onClick={p.onStop}>■</button><button className={p.playback.playing?"play active":"play"} title="再生 / 一時停止 (Space)" onClick={p.onPlay}>▶</button><button title="1秒戻る" onClick={()=>p.onSeekRelative(-1)}>−1秒</button><button title="1秒進む" onClick={()=>p.onSeekRelative(1)}>+1秒</button><i/>
    <button title="MIDIを読み込む (Ctrl+I)" onClick={p.onImportMidi} disabled={!p.connected||p.busy}>MIDI 読込</button><button title="MIDIを書き出す (Ctrl+M)" onClick={p.onExportMidi}>MIDI 出力</button><button title="ADOFAIを書き出す (Ctrl+E)" onClick={p.onExportAdo}>ADOFAI 出力</button><span className="toolbar-spacer"/>
    <button className={p.view.mode==="spec"?"selected":""} onClick={()=>p.onMode("spec")}>スペクトル</button><button className={p.view.mode==="notes"?"selected":""} onClick={()=>p.onMode("notes")}>ノート</button><button className={p.view.mode==="both"?"selected":""} onClick={()=>p.onMode("both")}>両方</button><button title="ヘルプ (F1)" onClick={p.onHelp}>?</button><output>{formatTime(p.playback.time)} / {formatTime(p.playback.duration)}</output>
  </div>
</>}
