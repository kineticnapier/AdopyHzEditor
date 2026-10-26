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
  return <div className="timeline">
    <b>タイムライン</b>
    <input aria-label="表示開始位置" type="range" min={0} max={Math.max(.001,max)} step={Math.max(.001,max/1000)} value={Math.min(view.start,max)} onChange={e=>onView({start:+e.target.value})}/>
    <label htmlFor="timeline-window-seconds">表示秒数</label><input id="timeline-window-seconds" type="number" min={.2} max={Math.max(.2,playback.duration)} step={.1} value={view.windowSeconds} onChange={e=>onView({windowSeconds:+e.target.value})}/>
    <label htmlFor="timeline-pitch-bottom">下端音高</label><input id="timeline-pitch-bottom" type="number" min={0} max={127} value={view.pitchBottom} onChange={e=>onView({pitchBottom:+e.target.value})}/>
    <button aria-label="下端音高を12下げる" onClick={()=>onView({pitchBottom:view.pitchBottom-12})}>−12</button><button aria-label="下端音高を12上げる" onClick={()=>onView({pitchBottom:view.pitchBottom+12})}>+12</button>
    <label htmlFor="timeline-visible-notes">音域</label><input id="timeline-visible-notes" type="number" min={6} max={128} value={view.visibleNotes} onChange={e=>onView({visibleNotes:+e.target.value})}/>
    <button onClick={onFit}>全体表示</button>
    <label className="timeline-follow"><input type="checkbox" checked={followPlayback} onChange={e=>onFollowPlayback(e.target.checked)}/>再生追従</label>
  </div>;
}
