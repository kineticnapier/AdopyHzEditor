import { useEffect, useRef, useState } from "react";
import { commitNumericEdit } from "../settings/numericInputModel";
import { timelineSliderStart } from "./timelineNavigation";
import type { PlaybackState, ViewState } from "./bridge";

type Props={
  view:ViewState;
  playback:PlaybackState;
  followPlayback:boolean;
  onFollowPlayback(value:boolean):void;
  onView(changes:Partial<ViewState>):void;
  onFit():void;
};

export default function Timeline({view,playback,followPlayback,onFollowPlayback,onView,onFit}:Props){
  const max=Math.max(0,playback.duration-view.windowSeconds);
  const pitchTop=Math.min(128,view.pitchBottom+view.visibleNotes);
  return <div className="timeline">
    <input className="timeline-slider" aria-label="表示開始位置" type="range" min={0}
      max={max > 0 ? max : .001} step={max > 0 ? max / 1000 : .001}
      value={Math.max(0, Math.min(view.start, max))} disabled={max <= 0}
      onChange={e => {
        const start = timelineSliderStart(Number(e.target.value), view.start, max);
        if (start !== null) onView({ start });
      }}/>
    <label className="timeline-field" htmlFor="timeline-window-seconds"><span>表示幅</span><CommitNumber id="timeline-window-seconds" label="時間の表示幅" value={view.windowSeconds} min={.2} max={Math.max(.2,playback.duration)} step={.1} onCommit={value=>onView({windowSeconds:value})}/><small>s</small></label>
    <label className="timeline-field pitch-field"><span>音高</span><CommitNumber label="下端音高" value={view.pitchBottom} min={0} max={Math.max(0,128-view.visibleNotes)} step={1} onCommit={value=>onView({pitchBottom:value})}/><small>–</small><CommitNumber label="上端音高" value={pitchTop} min={Math.min(128,view.pitchBottom+6)} max={128} step={1} onCommit={value=>onView({visibleNotes:Math.max(6,Math.min(128,value-view.pitchBottom))})}/></label>
    <button onClick={onFit} title="音源全体を表示">全体</button>
    <label className="timeline-follow" title="再生位置を表示範囲内に追従"><input type="checkbox" checked={followPlayback} onChange={e=>onFollowPlayback(e.target.checked)}/>再生追従</label>
  </div>;
}

function CommitNumber({id,label,value,min,max,step,onCommit}:{id?:string;label:string;value:number;min:number;max:number;step:number;onCommit(value:number):void}){
  const [text, setText] = useState(String(value));
  const cancelledRef = useRef(false);
  useEffect(() => setText(String(value)), [value]);

  function commit() {
    // Escape calls blur synchronously; state updates have not reached text yet.
    const next = commitNumericEdit(text, value, min, max, cancelledRef.current);
    cancelledRef.current = false;
    setText(String(next));
    if (next !== value) onCommit(next);
  }

  return (
    <input
      id={id}
      aria-label={label}
      type="number"
      min={min}
      max={max}
      step={step}
      value={text}
      onFocus={() => { cancelledRef.current = false; }}
      onChange={(event) => setText(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.currentTarget.blur();
        } else if (event.key === "Escape") {
          event.preventDefault();
          cancelledRef.current = true;
          setText(String(value));
          event.currentTarget.blur();
        }
      }}
    />
  );
}
