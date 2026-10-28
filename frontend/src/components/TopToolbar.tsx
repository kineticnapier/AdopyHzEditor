import type { ReactNode } from "react";
import type { PlaybackState, ViewState } from "./bridge";

type Props = {
  connected:boolean;
  audioName:string|null;
  dirty:boolean;
  playback:PlaybackState;
  view:ViewState;
  menus?:ReactNode;
  panelOpen:boolean;
  onTogglePanel():void;
  onSeek(time:number):void;
  onStop():void;
  onPlay():void;
  onMode(mode:ViewState["mode"]):void;
};

function TransportIcon({name}:{name:"start"|"stop"|"play"|"pause"}){
  if(name==="start")return <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 3v10M12.5 3.5 6 8l6.5 4.5z"/></svg>;
  if(name==="stop")return <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4h8v8H4z"/></svg>;
  if(name==="pause")return <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 3h3v10H4zm5 0h3v10H9z"/></svg>;
  return <svg viewBox="0 0 16 16" aria-hidden="true"><path d="m5 3 8 5-8 5z"/></svg>;
}

function formatTime(seconds:number){
  const totalMs=Math.max(0,Math.round((seconds||0)*1000));
  const minutes=Math.floor(totalMs/60000);
  const sec=Math.floor((totalMs%60000)/1000);
  const ms=totalMs%1000;
  return `${minutes}:${String(sec).padStart(2,"0")}.${String(ms).padStart(3,"0")}`;
}

export default function TopToolbar(p:Props){
  return <>
    <header className="titlebar">
      <div className="title-left">
        <strong>AdopyHzEditor</strong>
        <span className="document-name">{p.audioName??"空のワークスペース"}{p.dirty&&<span className="dirty-mark" aria-label="未保存">●</span>}</span>
        {p.menus}
      </div>
      <span className={p.connected?"status-pill on":"status-pill"}>{p.connected?"Python 接続済み":"ブラウザプレビュー"}</span>
    </header>
    <div className="toolbar">
      <div className="transport-group" role="group" aria-label="再生">
        <button className="icon-button" aria-label="先頭へ移動" title="先頭へ (Home)" onClick={()=>p.onSeek(0)}><TransportIcon name="start"/></button>
        <button className="icon-button" aria-label="停止" title="停止 (Ctrl+Space)" onClick={p.onStop}><TransportIcon name="stop"/></button>
        <button className={p.playback.playing?"play active":"play"} aria-label={p.playback.playing?"一時停止":"再生"} aria-pressed={p.playback.playing} title="再生 / 一時停止 (Space)" onClick={p.onPlay}><TransportIcon name={p.playback.playing?"pause":"play"}/></button>
      </div>
      <span className="toolbar-spacer"/>
      <div className="view-toggle" role="group" aria-label="表示モード">
        <button className={p.view.mode==="spec"?"selected":""} aria-pressed={p.view.mode==="spec"} onClick={()=>p.onMode("spec")}>Spectrum</button>
        <button className={p.view.mode==="notes"?"selected":""} aria-pressed={p.view.mode==="notes"} onClick={()=>p.onMode("notes")}>Notes</button>
        <button className={p.view.mode==="both"?"selected":""} aria-pressed={p.view.mode==="both"} onClick={()=>p.onMode("both")}>Both</button>
      </div>
      <output>{formatTime(p.playback.time)} / {formatTime(p.playback.duration)}</output>
      <button className="panel-toggle" aria-label={p.panelOpen?"右パネルを閉じる":"右パネルを開く"} aria-pressed={p.panelOpen} onClick={p.onTogglePanel}>Inspector</button>
    </div>
  </>;
}
