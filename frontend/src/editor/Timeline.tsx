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
    <input className="timeline-slider" aria-label="タイムライン" type="range" min={0} max={Math.max(.001,max)} step={Math.max(.001,max/1000)} value={Math.min(view.start,max)} onChange={e=>onView({start:+e.target.value})}/>
    <label className="timeline-field"><span>Window</span><input type="number" min={.2} max={Math.max(.2,playback.duration)} step={.1} value={view.windowSeconds} onChange={e=>onView({windowSeconds:+e.target.value})}/><small>s</small></label>
    <label className="timeline-field pitch-field"><span>Pitch</span><input type="number" min={0} max={127} step={1} value={view.pitchBottom} onChange={e=>onView({pitchBottom:+e.target.value})}/><small>–</small><input type="number" min={Math.min(128,view.pitchBottom+6)} max={128} step={1} value={pitchTop} onChange={e=>onView({visibleNotes:Math.max(6,Math.min(128,+e.target.value-view.pitchBottom))})}/></label>
    <button onClick={onFit} title="全体表示">Fit</button>
    <label className="timeline-follow"><input type="checkbox" checked={followPlayback} onChange={e=>onFollowPlayback(e.target.checked)}/>Follow</label>
  </div>;
}
