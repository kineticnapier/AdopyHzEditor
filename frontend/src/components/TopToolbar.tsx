import type { ReactNode } from "react";
import { formatPlaybackTime } from "./formatPlaybackTime";
import { playbackStatusMessage, playbackToggleEnabled } from "./playbackStatusMessage";
import { workspaceTitle } from "../editor/emptyState";
import type { PlaybackState, ViewState } from "./bridge";
import { t, useLanguage } from "../i18n/index.ts";

type Props = {
  connected:boolean;
  audioName:string|null;
  hasPlayableContent:boolean;
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


export default function TopToolbar(p:Props){
  useLanguage();
  const playbackStatus = p.connected ? playbackStatusMessage(p.playback, p.hasPlayableContent) : null;
  return <>
    <header className="titlebar">
      <div className="title-left">
        <strong>AdopyHzEditor</strong>
        <span className="document-name">{workspaceTitle(p.audioName,p.hasPlayableContent)}{p.dirty&&<span className="dirty-mark" aria-label={t("toolbar.unsaved")}>●</span>}</span>
        {p.menus}
      </div>
      <span className={p.connected?"status-pill on":"status-pill"}>{p.connected?t("toolbar.connected"):t("toolbar.browser_preview")}</span>
    </header>
    <div className="toolbar">
      <div className="transport-group" role="group" aria-label={t("toolbar.transport")}>
        <button className="icon-button" aria-label={t("toolbar.to_start")} title={t("toolbar.to_start_tip")} onClick={()=>p.onSeek(0)}><TransportIcon name="start"/></button>
        <button className="icon-button" aria-label={t("toolbar.stop")} title={t("toolbar.stop_tip")} disabled={!p.connected} onClick={p.onStop}><TransportIcon name="stop"/></button>
        <button className={p.playback.playing?"play active":"play"} aria-label={p.playback.playing?t("toolbar.pause"):t("toolbar.play")} aria-pressed={p.playback.playing} title={t("toolbar.play_tip")} disabled={!playbackToggleEnabled(p.connected, p.playback)} onClick={p.onPlay}><TransportIcon name={p.playback.playing?"pause":"play"}/></button>
      </div>
      <output aria-live="off" aria-label={t("toolbar.time")}>{formatPlaybackTime(p.playback.time)} / {formatPlaybackTime(p.playback.duration)}</output>
      {playbackStatus && <span className="playback-error" role="status" title={playbackStatus}>{playbackStatus}</span>}
      <span className="toolbar-spacer"/>
      <div className="view-toggle" role="group" aria-label={t("toolbar.view_mode")}>
        <button className={p.view.mode==="spec"?"selected":""} aria-pressed={p.view.mode==="spec"} onClick={()=>p.onMode("spec")}>{t("toolbar.mode_spec")}</button>
        <button className={p.view.mode==="notes"?"selected":""} aria-pressed={p.view.mode==="notes"} onClick={()=>p.onMode("notes")}>{t("toolbar.mode_notes")}</button>
        <button className={p.view.mode==="both"?"selected":""} aria-pressed={p.view.mode==="both"} onClick={()=>p.onMode("both")}>{t("toolbar.mode_both")}</button>
      </div>
      <button className="panel-toggle" aria-label={p.panelOpen?t("toolbar.panel_close"):t("toolbar.panel_open")} aria-pressed={p.panelOpen} title={t("toolbar.panel_tip")} onClick={p.onTogglePanel}>{t("toolbar.panel")}</button>
    </div>
  </>;
}
