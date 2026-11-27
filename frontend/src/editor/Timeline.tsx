import { useEffect, useRef, useState } from "react";
import { t } from "../i18n/index.ts";
import { commitNumericEdit } from "../settings/numericInputModel";
import { isDialogCompositionKey, isPlainDialogEscape } from "../dialogs/dialogFocus";
import { timelineSliderBounds, timelineSliderStart, timelineWindowInputMax } from "./timelineNavigation";
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
  const { max, value: sliderValue } = timelineSliderBounds(playback.duration, view.windowSeconds, view.start);
  const pitchTop=Math.min(128,view.pitchBottom+view.visibleNotes);
  return <div className="timeline">
    <input className="timeline-slider" aria-label={t("timeline.start")} type="range" min={0}
      max={max > 0 ? max : .001} step="any"
      value={sliderValue} disabled={max <= 0}
      onChange={e => {
        const start = timelineSliderStart(Number(e.target.value), view.start, max);
        if (start !== null) onView({ start });
      }}/>
    <label className="timeline-field" htmlFor="timeline-window-seconds"><span>{t("timeline.window")}</span><CommitNumber id="timeline-window-seconds" label={t("timeline.window_label")} value={view.windowSeconds} min={.2} max={timelineWindowInputMax(playback.duration, view.windowSeconds)} step="any" onCommit={value=>onView({windowSeconds:value})}/><small>s</small></label>
    <div className="timeline-field pitch-field" role="group" aria-label={t("timeline.pitch_range")}><span>{t("timeline.pitch")}</span><CommitNumber label={t("timeline.pitch_bottom")} value={view.pitchBottom} min={0} max={Math.max(0,128-view.visibleNotes)} step={1} onCommit={value=>onView({pitchBottom:value})}/><small>–</small><CommitNumber label={t("timeline.pitch_top")} value={pitchTop} min={Math.min(128,view.pitchBottom+6)} max={128} step={1} onCommit={value=>onView({visibleNotes:Math.max(6,Math.min(128,value-view.pitchBottom))})}/></div>
    <button onClick={onFit} title={t("timeline.fit_tip")}>{t("timeline.fit")}</button>
    <label className="timeline-follow" title={t("timeline.follow_tip")}><input type="checkbox" checked={followPlayback} onChange={e=>onFollowPlayback(e.target.checked)}/>{t("timeline.follow")}</label>
  </div>;
}

function CommitNumber({id,label,value,min,max,step,onCommit}:{id?:string;label:string;value:number;min:number;max:number;step:number | "any";onCommit(value:number):void}){
  const [text, setText] = useState(String(value));
  const cancelledRef = useRef(false);
  const editingRef = useRef(false);
  const editedRef = useRef(false);
  // A wheel/slider update must not overwrite text while the user is typing.
  useEffect(() => { if (!editingRef.current) setText(String(value)); }, [value]);

  function commit() {
    // Escape calls blur synchronously; state updates have not reached text yet.
    const next = commitNumericEdit(text, value, min, max, cancelledRef.current, step === 1, editedRef.current);
    editingRef.current = false;
    editedRef.current = false;
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
      onFocus={() => { cancelledRef.current = false; editingRef.current = true; editedRef.current = false; }}
      onChange={(event) => { editedRef.current = true; setText(event.target.value); }}
      onBlur={commit}
      onKeyDown={(event) => {
        // Do not commit or cancel a number while the IME is composing.
        if (isDialogCompositionKey(event.nativeEvent)) return;
        if (event.key === "Enter") {
          event.preventDefault();
          event.stopPropagation();
          event.currentTarget.blur();
        } else if (isPlainDialogEscape(event)) {
          event.preventDefault();
          event.stopPropagation();
          cancelledRef.current = true;
          setText(String(value));
          event.currentTarget.blur();
        }
      }}
    />
  );
}
