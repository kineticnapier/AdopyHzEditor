import type { ReactNode } from "react";
import type { PlaybackState, ViewState } from "./bridge";

type Props = {
  connected:boolean;
  audioName:string|null;
  dirty:boolean;
  playback:PlaybackState;
  view:ViewState;
  menus?:ReactNode;
  onSeek(time:number):void;
  onStop():void;
  onPlay():void;
  onMode(mode:ViewState["mode"]):void;
};

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
        <span className="document-name">{p.audioName??"空のワークスペース"}{p.dirty?" •":""}</span>
        {p.menus}
      </div>
      <span className={p.connected?"status-pill on":"status-pill"}>{p.connected?"Python 接続済み":"ブラウザプレビュー"}</span>
    </header>
    <div className="toolbar">
      <div className="transport-group" aria-label="再生">
        <button className="icon-button" title="先頭へ (Home)" onClick={()=>p.onSeek(0)}>⏮</button>
        <button className="icon-button" title="停止 (Ctrl+Space)" onClick={p.onStop}>■</button>
        <button className={p.playback.playing?"play active":"play"} title="再生 / 一時停止 (Space)" onClick={p.onPlay}>{p.playback.playing?"❚❚":"▶"}</button>
      </div>
      <span className="toolbar-spacer"/>
      <div className="view-toggle" aria-label="表示モード">
        <button className={p.view.mode==="spec"?"selected":""} onClick={()=>p.onMode("spec")}>スペクトル</button>
        <button className={p.view.mode==="notes"?"selected":""} onClick={()=>p.onMode("notes")}>ノート</button>
        <button className={p.view.mode==="both"?"selected":""} onClick={()=>p.onMode("both")}>両方</button>
      </div>
      <output>{formatTime(p.playback.time)} / {formatTime(p.playback.duration)}</output>
    </div>
  </>;
}
