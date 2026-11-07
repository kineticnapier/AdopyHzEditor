import { useEffect, useLayoutEffect, useMemo, useRef, useState, type FocusEvent as ReactFocusEvent, type KeyboardEvent as ReactKeyboardEvent, type MouseEvent as ReactMouseEvent, type PointerEvent as ReactPointerEvent } from "react";
import type { DirectSpectrumPayload, EditorSettings, FrequencyTrackPayload, NoteDto, PlaybackState, SpectrogramPayload, ViewState } from "./bridge";
import { adjacentNoteIndex, boundedGridRange, boundedTimelineTickRange, buildNoteTimeIndex, buildSegmentSpatialIndex, nearbySegmentIndices, noteCandidatesAt, notesInTimeRange, noteEdgeAt, noteIntersects, noteMidiAt, spectrogramPitchVisibleCrop, spectrogramTimeCrop, directSpectrumVisibleCrop, clampDraggedNoteOffset, contextMenuDeleteIndices, isValidTrackSample, type NoteTimeIndex } from "./editorMath";
import { mergeTrackSelection, normalizeTrackRange, updateTrackSelection, type TrackSelectionRange } from "./trackSelection";
import { midiLabel, midiToHz } from "./musicMath";
import type { WheelPitchAccumulator } from "./wheelNavigation";
import { createCanvasWheelHandler, observeWheelPitchCarryRelease, syncCanvasWheelView } from "./canvasWheelHandler";
import { decodePackedDirectSpectrumBytes, decodePackedFrequencyTrackBytes, decodeSizedBase64Bytes, isValidDirectSpectrumSize, isValidSpectrogramSize } from "./base64Payload";
import { pitchBottomToRevealNote } from "./pitchViewport";
import { isNoteNavigationKey, keyboardRangeSelection, reconcileKeyboardNote } from "./noteKeyboardNavigation";
import { canStartCanvasGesture, canvasEscapeAction, shouldHandleCanvasEscape, shouldIgnoreRepeatedCanvasEscape, clearIdleCanvasSelection, isCanvasGesturePointer, releaseCanvasPointerCapture, shouldSuppressCanvasArrowDuringPointerGesture, shouldSuppressCanvasNonArrowKeyDuringPointerGesture, shouldCancelCanvasGestureForResize, shouldCancelCanvasGestureForViewChange, shouldCancelCanvasGestureForNotesChange, observeCanvasPageExit, createTrailingReporter } from "./canvasInteraction";

export type TrackHoverInfo = {id:number;frequency:number;noteName:string;duration:number;magnitude:number};
export type TrackSelectionState = {ids:number[];range:TrackSelectionRange|null;useRange:boolean};

type Props = {
  notes: NoteDto[];
  selected: number[];
  settings: EditorSettings;
  view: ViewState;
  playback: PlaybackState;
  spectrum: SpectrogramPayload | null;
  directSpectrum: DirectSpectrumPayload | null;
  frequencyTracks: FrequencyTrackPayload | null;
  trackSelection: TrackSelectionState;
  onViewportSize?(size: {width:number;height:number}): void;
  onSelect(indices: number[]): void;
  onAdd(start: number, end: number, midi: number, kind: "note" | "curve", endMidi: number): Promise<void>;
  onMove(indices: number[], dx: number, dy: number): Promise<void>;
  onDuplicateMove(indices: number[], dx: number, dy: number): Promise<void>;
  onResize(indices: number[], edge: "start" | "end", delta: number): Promise<void>;
  onDelete(indices: number[]): Promise<void>;
  onCutRange(indices: number[], start: number, end: number): Promise<void>;
  onSeek(time: number): Promise<void>;
  onView(changes: Partial<ViewState>): Promise<void>;
  onCursorMove?(time: number, midi: number): void;
  onTrackHover?(track: TrackHoverInfo|null): void;
  onTrackSelectionChange(selection:TrackSelectionState):void;
  onFindTracks(range: TrackSelectionRange): Promise<number[] | null>;
};

type DragMode = "create" | "curve" | "region" | "track-region" | "cut-range" | "move" | "duplicate-move" | "resize-start" | "resize-end";
type DragState = { mode: DragMode; startTime: number; startMidi: number; nowTime: number; nowMidi: number; indices: number[]; trackAdditive?: boolean };

function hitNote(notes: NoteDto[], index: NoteTimeIndex, time: number, midi: number, midiPerPixel:number) {
  const hits: Array<[number, number]> = [],curveTolerance=Math.max(.03,midiPerPixel*6),fixedTolerance=.43+midiPerPixel*4;
  noteCandidatesAt(index,time).forEach(noteIndex => {
    const note=notes[noteIndex];
    if (time < note.start - 1e-9 || time > note.end + 1e-9) return;
    if ((note.kind ?? "note") === "curve") {
      const u = note.end <= note.start ? 0 : (time - note.start) / (note.end - note.start);
      const distance=Math.abs(midi-noteMidiAt(note,u));if(distance<=curveTolerance)hits.push([distance,noteIndex]);
    } else {const distance=Math.abs(midi-note.midi);if(distance<=fixedTolerance)hits.push([distance,noteIndex]);}
  });
  hits.sort((a, b) => a[0] - b[0]);
  return hits[0]?.[1] ?? null;
}
const COLOR_MAPS: Record<string, Array<[number, [number, number, number]]>> = {
  wavetone: [[0,[0,0,0]],[.12,[0,0,120]],[.35,[0,80,255]],[.55,[0,255,180]],[.75,[255,240,0]],[1,[255,0,0]]],
  viridis: [[0,[68,1,84]],[.33,[49,104,142]],[.66,[53,183,121]],[1,[253,231,37]]],
  magma: [[0,[0,0,4]],[.33,[113,31,129]],[.66,[237,104,37]],[1,[252,253,191]]],
  inferno: [[0,[0,0,4]],[.33,[120,28,109]],[.66,[237,105,37]],[1,[252,255,164]]],
  plasma: [[0,[13,8,135]],[.33,[126,3,168]],[.66,[224,100,98]],[1,[240,249,33]]],
};
function colorFor(v: number, map: string): [number, number, number] {
  const x = Math.max(0, Math.min(1, v));
  if (map === "gray") { const q = Math.round(x * 255); return [q, q, q]; }
  const stops = COLOR_MAPS[map] ?? COLOR_MAPS.wavetone;
  for (let i = 0; i < stops.length - 1; i += 1) {
    const [a, ca] = stops[i], [b, cb] = stops[i + 1];
    if (x <= b) {
      const t = b <= a ? 0 : (x - a) / (b - a);
      return ca.map((c, j) => Math.round(c + (cb[j] - c) * t)) as [number, number, number];
    }
  }
  return stops[stops.length - 1][1];
}
function decodeSpectrum(payload: SpectrogramPayload | null) {
  if (!payload?.available || !payload.data || !payload.rows || !payload.cols) return null;
  if (!isValidSpectrogramSize(payload.rows, payload.cols)) return null;
  const bytes = decodeSizedBase64Bytes(payload.data, payload.rows * payload.cols);
  if (!bytes) return null;
  return { ...payload, rows: payload.rows, cols: payload.cols, bytes };
}
function decodeFrequencyTracks(payload: FrequencyTrackPayload | null) {
  if (!payload?.available || !payload.data || typeof payload.pointCount !== "number" || !Number.isSafeInteger(payload.pointCount) || payload.pointCount <= 0) return null;
  const bytes=decodePackedFrequencyTrackBytes(payload.data, payload.pointCount);
  if(!bytes)return null;
  const stride=18,count=payload.pointCount,view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
  const ids=new Uint32Array(count),times=new Float32Array(count),midis=new Float32Array(count),magnitudes=new Float32Array(count),durations=new Float32Array(count),flags=new Uint8Array(count);
  for(let i=0;i<count;i+=1){const offset=i*stride;ids[i]=view.getUint32(offset,true);times[i]=view.getFloat32(offset+4,true);midis[i]=view.getFloat32(offset+8,true);magnitudes[i]=view.getUint8(offset+12)/255;durations[i]=view.getFloat32(offset+13,true);flags[i]=view.getUint8(offset+17);}
  return{ids,times,midis,magnitudes,durations,flags,count};
}
function snapTime(settings: EditorSettings, duration: number, time: number) {
  const t = Math.max(0, Math.min(duration, time));
  if (!settings.snapEnabled) return t;
  const step = 60 / Math.max(1e-6, settings.bpm) / Math.max(1, settings.snapDiv);
  const offset = settings.offsetMs / 1000;
  return Math.max(0, Math.min(duration, offset + Math.round((t - offset) / step) * step));
}
function shiftNote(note: NoteDto, dx: number, dy: number): NoteDto {
  return {
    ...note,
    start: note.start + dx,
    end: note.end + dx,
    midi: note.midi + dy,
    midi_end: note.midi_end === undefined ? undefined : note.midi_end + dy,
    ctrl1_midi: note.ctrl1_midi === undefined ? undefined : note.ctrl1_midi + dy,
    ctrl2_midi: note.ctrl2_midi === undefined ? undefined : note.ctrl2_midi + dy,
  };
}
function resizeNote(note: NoteDto, edge: "start" | "end", delta: number, settings: EditorSettings, duration: number): NoteDto {
  if (edge === "start") {
    const start = Math.min(note.end - .001, snapTime(settings, duration, note.start + delta));
    return { ...note, start: Math.max(0, start) };
  }
  const end = Math.max(note.start + .001, snapTime(settings, duration, note.end + delta));
  return { ...note, end: Math.min(duration, end) };
}

export default function EditorCanvas(props: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null), playheadRef = useRef<HTMLCanvasElement>(null), containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 800, height: 500 });
  const observedCanvasSizeRef = useRef(size);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [keyboardNote, setKeyboardNote] = useState<number | null>(null);
  const keyboardSelectionRef = useRef<number[] | null>(null);
  const keyboardAnchorRef = useRef<number | null>(null);
  const activePointerIdRef = useRef<number | null>(null);
  const cursorReporterRef = useRef(createTrailingReporter<{ time: number; midi: number; track: TrackHoverInfo | null }>(50));
  const trackHoverRef = useRef(props.onTrackHover);
  useLayoutEffect(() => { trackHoverRef.current = props.onTrackHover; }, [props.onTrackHover]);
  const observedCanvasViewRef = useRef(props.view);
  useLayoutEffect(() => {
    const previous = observedCanvasViewRef.current;
    observedCanvasViewRef.current = props.view;
    // Playback follow or an external viewport change must not mix old drag
    // start coordinates with the new mapping on pointer release.
    if (!shouldCancelCanvasGestureForViewChange(activePointerIdRef.current, previous, props.view)) return;
    const pointerId = activePointerIdRef.current;
    cursorReporterRef.current.cancel();
    activePointerIdRef.current = null;
    if (canvasRef.current) releaseCanvasPointerCapture(canvasRef.current, pointerId);
    setDrag(null);
  }, [props.view]);
  const observedNotesRef = useRef(props.notes);
  useLayoutEffect(() => {
    const previous = observedNotesRef.current;
    observedNotesRef.current = props.notes;
    // An async edit or document replacement can invalidate the indices
    // captured at pointer down. Cancel before a pointer-up can commit them.
    if (!shouldCancelCanvasGestureForNotesChange(activePointerIdRef.current, previous, props.notes)) return;
    const pointerId = activePointerIdRef.current;
    cursorReporterRef.current.cancel();
    activePointerIdRef.current = null;
    if (canvasRef.current) releaseCanvasPointerCapture(canvasRef.current, pointerId);
    setDrag(null);
  }, [props.notes]);
  useEffect(() => () => cursorReporterRef.current.cancel(), []);
  useEffect(() => observeCanvasPageExit(window, document, () => {
    // Window blur (Alt+Tab, browser chrome) need not blur the focused canvas.
    // Do not allow a captured drag to resume after returning to this page.
    const pointerId = activePointerIdRef.current;
    if (pointerId === null) return;
    cursorReporterRef.current.cancel();
    trackHoverRef.current?.(null);
    activePointerIdRef.current = null;
    if (canvasRef.current) releaseCanvasPointerCapture(canvasRef.current, pointerId);
    setDrag(null);
  }), []);

  // View/data changes invalidate hover coordinates captured by a delayed report.
  // This also covers document replacement without unmounting the canvas.
  useEffect(() => {
    cursorReporterRef.current.cancel();
    // A previously displayed Track is no longer tied to the current coordinates.
    // Do not leave it visible until the pointer moves again.
    props.onTrackHover?.(null);
  }, [props.notes, props.frequencyTracks, props.view, size]);
  const wheelPitchAccumulatorRef = useRef<WheelPitchAccumulator>({ modifier: null, remainder: 0 });
  const wheelViewRef = useRef(props.view);
  const wheelOnViewRef = useRef(props.onView);
  const wheelDurationRef = useRef(props.playback.duration);
  useEffect(() => observeWheelPitchCarryRelease(window, wheelPitchAccumulatorRef, document), []);
  useLayoutEffect(() => {
    wheelOnViewRef.current = props.onView;
    wheelDurationRef.current = props.playback.duration;
  }, [props.onView, props.playback.duration]);
  const lastSelectionRef = useRef(props.selected);
  const lastNotesRef = useRef(props.notes);
  useEffect(() => {
    const expected = keyboardSelectionRef.current;
    keyboardSelectionRef.current = null;
    const previous = lastSelectionRef.current;
    const notesChanged = lastNotesRef.current !== props.notes;
    const sameSelection = (a: readonly number[] | null, b: readonly number[]) =>
      a !== null && a.length === b.length && a.every((index, i) => index === b[i]);
    // A mouse/inspector selection or document edit starts a new keyboard range.
    if (notesChanged || !(sameSelection(expected, props.selected) || sameSelection(previous, props.selected)))
      keyboardAnchorRef.current = null;
    lastSelectionRef.current = props.selected;
    lastNotesRef.current = props.notes;
    setKeyboardNote(focused =>
      reconcileKeyboardNote(focused, previous, expected, props.selected, props.notes.length, notesChanged));
  }, [props.selected, props.notes]);
  const selectedSet=useMemo(()=>new Set(props.selected),[props.selected]);
  const noteTimeIndex=useMemo(()=>buildNoteTimeIndex(props.notes),[props.notes]);
  const keyboardOrder=noteTimeIndex.order;
  const decoded = useMemo(() => decodeSpectrum(props.spectrum), [props.spectrum]);
  const decodedTracks = useMemo(() => decodeFrequencyTracks(props.frequencyTracks), [props.frequencyTracks]);
  const selectedTrackSet = useMemo(() => new Set(props.trackSelection.ids), [props.trackSelection.ids]);

  const spectrumCanvas = useMemo(() => {
    if (!decoded) return null;
    const canvas = document.createElement("canvas");
    canvas.width = decoded.cols; canvas.height = decoded.rows;
    const maybeCtx = canvas.getContext("2d"); if (!maybeCtx) return null;
    const ctx: CanvasRenderingContext2D = maybeCtx;
    const image = ctx.createImageData(decoded.cols, decoded.rows);
    for (let row = 0; row < decoded.rows; row += 1) for (let col = 0; col < decoded.cols; col += 1) {
      const [r,g,b] = colorFor(decoded.bytes[row * decoded.cols + col] / 255, props.settings.colormap);
      const y = decoded.rows - 1 - row, p = (y * decoded.cols + col) * 4;
      image.data[p]=r; image.data[p+1]=g; image.data[p+2]=b; image.data[p+3]=255;
    }
    ctx.putImageData(image, 0, 0);
    return canvas;
  }, [decoded, props.settings.colormap]);
  const directSpectrumCanvas = useMemo(() => {
    const payload=props.directSpectrum;
    if (!payload?.data || typeof payload.timeBuckets !== "number" || typeof payload.pitchBuckets !== "number" || typeof payload.recordCount !== "number" || !isValidDirectSpectrumSize(payload.timeBuckets, payload.pitchBuckets)) return null;
    const bytes=decodePackedDirectSpectrumBytes(payload.data, payload.recordCount, payload.timeBuckets, payload.pitchBuckets);
    if(!bytes)return null;
    const canvas=document.createElement("canvas");canvas.width=payload.timeBuckets;canvas.height=payload.pitchBuckets;
    const maybeCtx=canvas.getContext("2d");if(!maybeCtx)return null;
    const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength),image=maybeCtx.createImageData(canvas.width,canvas.height);
    for(let offset=0;offset+5<=bytes.byteLength;offset+=5){
      const x=view.getUint16(offset,true),pitch=view.getUint16(offset+2,true),magnitude=view.getUint8(offset+4);
      if(x>=canvas.width||pitch>=canvas.height)continue;
      const [r,g,b]=colorFor(Math.sqrt(magnitude/255),props.settings.colormap),y=canvas.height-1-pitch,p=(y*canvas.width+x)*4;
      image.data[p]=r;image.data[p+1]=g;image.data[p+2]=b;image.data[p+3]=255;
    }
    maybeCtx.putImageData(image,0,0);return canvas;
  },[props.directSpectrum,props.settings.colormap]);

  useEffect(() => {
    const el = containerRef.current; if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      const next = { width: Math.max(1, entry.contentRect.width), height: Math.max(1, entry.contentRect.height) };
      const previous = observedCanvasSizeRef.current;
      observedCanvasSizeRef.current = next;
      // A resize changes the coordinate mapping while a drag retains its start position.
      // Cancel before publishing the new size so the drag cannot commit with mixed coordinates.
      if (shouldCancelCanvasGestureForResize(activePointerIdRef.current, previous, next)) {
        const pointerId = activePointerIdRef.current;
        cursorReporterRef.current.cancel();
        activePointerIdRef.current = null;
        if (canvasRef.current) releaseCanvasPointerCapture(canvasRef.current, pointerId);
        setDrag(null);
      }
      setSize(next);
      props.onViewportSize?.(next);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [props.onViewportSize]);

  const coords = useMemo(() => {
    const { width, height } = size, start = props.view.start, win = Math.max(.001, props.view.windowSeconds), bottom = props.view.pitchBottom - .5, visible = Math.max(1, props.view.visibleNotes);
    return {
      x: (time:number) => (time-start)/win*width,
      y: (midi:number) => height-(midi-bottom)/visible*height,
      time: (px:number) => start+px/width*win,
      midi: (py:number) => bottom+(height-py)/height*visible,
    };
  }, [props.view, size]);
  // Packed float32 Track samples may contain NaN/Infinity. Never pass those
  // samples to Canvas or let them contribute to pointer hit testing.
  const validTrackPoint = (i: number) =>
    decodedTracks !== null && i >= 0 && i < decodedTracks.count &&
    isValidTrackSample(decodedTracks.times[i], decodedTracks.midis[i], decodedTracks.magnitudes[i], decodedTracks.durations[i]) &&
    Number.isFinite(coords.x(decodedTracks.times[i])) && Number.isFinite(coords.y(decodedTracks.midis[i]));
  const trackHitIndex = useMemo(() => {
    if (!decodedTracks) return null;
    const segments = Array.from({ length: decodedTracks.count }, (_, i) => {
      const valid = validTrackPoint(i);
      const connected = valid && i > 0 && validTrackPoint(i - 1) &&
        (decodedTracks.flags[i] & 1) === 0 && decodedTracks.ids[i] === decodedTracks.ids[i - 1];
      const a = connected ? i - 1 : i;
      return valid
        ? { ax: coords.x(decodedTracks.times[a]), ay: coords.y(decodedTracks.midis[a]), bx: coords.x(decodedTracks.times[i]), by: coords.y(decodedTracks.midis[i]) }
        : { ax: NaN, ay: NaN, bx: NaN, by: NaN };
    });
    return { segments, index: buildSegmentSpatialIndex(segments, 24, 8, size) };
  }, [coords, decodedTracks, size]);

  useEffect(() => {
    const canvas = canvasRef.current; if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width=Math.max(1,Math.round(size.width*dpr)); canvas.height=Math.max(1,Math.round(size.height*dpr));
    canvas.style.width=`${size.width}px`; canvas.style.height=`${size.height}px`;
    const maybeCtx = canvas.getContext("2d"); if (!maybeCtx) return;
    const ctx: CanvasRenderingContext2D = maybeCtx;
    ctx.setTransform(dpr,0,0,dpr,0,0);
    const w=size.width,h=size.height;
    ctx.fillStyle="#080b0e"; ctx.fillRect(0,0,w,h);

    if (spectrumCanvas && props.view.mode !== "notes" && decoded?.duration && decoded.midiMin !== undefined && decoded.midiMax !== undefined) {
      const dataStart=decoded.start??0,dataEnd=decoded.end??decoded.duration;
      const timeCrop=spectrogramTimeCrop(dataStart,dataEnd,props.view.start,props.view.windowSeconds,decoded.cols,w);
      const top=props.view.pitchBottom+props.view.visibleNotes-.5,bottom=props.view.pitchBottom-.5;
      const pitchCrop=spectrogramPitchVisibleCrop(decoded.rows,decoded.midiMin,decoded.pitchStep??1,bottom,top,h);
      if(timeCrop&&pitchCrop){
        ctx.save(); ctx.globalAlpha=props.view.mode==="spec"?1:.7; ctx.imageSmoothingEnabled=props.settings.displayMode==="smooth";
        ctx.drawImage(spectrumCanvas,timeCrop.sx,pitchCrop.sy,timeCrop.sw,pitchCrop.sh,timeCrop.dx,pitchCrop.dy,timeCrop.dw,pitchCrop.dh); ctx.restore();
      }
    }
    if(directSpectrumCanvas&&props.directSpectrum&&props.view.mode!=="notes"){
      const payload=props.directSpectrum;
      const viewBottom = props.view.pitchBottom - .5;
      const crop = directSpectrumVisibleCrop(
        payload.startTime ?? props.view.start,
        payload.endTime ?? props.view.start + props.view.windowSeconds,
        payload.minMidi ?? viewBottom,
        payload.maxMidi ?? viewBottom + props.view.visibleNotes,
        props.view.start, props.view.windowSeconds, viewBottom, props.view.visibleNotes,
        directSpectrumCanvas.width, directSpectrumCanvas.height, w, h,
      );
      if (crop) {
        ctx.save();ctx.globalAlpha=(props.settings.spectrumOpacity/100)*(props.view.mode==="spec"?1:.82);ctx.imageSmoothingEnabled=false;
        ctx.drawImage(directSpectrumCanvas,crop.sx,crop.sy,crop.sw,crop.sh,crop.dx,crop.dy,crop.dw,crop.dh);ctx.restore();
      }
    }
    if(decodedTracks&&props.view.mode!=="notes"){
      ctx.save();ctx.lineCap="round";ctx.lineJoin="round";
      for(let i=0;i<decodedTracks.count;i+=1){
        if (!validTrackPoint(i)) continue;
        const trackId=decodedTracks.ids[i],selectedTrack=selectedTrackSet.has(trackId),x=coords.x(decodedTracks.times[i]),y=coords.y(decodedTracks.midis[i]),m=decodedTracks.magnitudes[i],duration=decodedTracks.durations[i],strength=Math.sqrt(m),durationWeight=Math.max(.25,Math.min(1,duration/.2));
        const connected = i > 0 && validTrackPoint(i - 1) &&
          (decodedTracks.flags[i] & 1) === 0 && trackId === decodedTracks.ids[i - 1];
        if(!connected){ctx.beginPath();ctx.arc(x,y,selectedTrack?Math.max(1.7,2.2*strength):Math.max(.65,1.3*strength),0,Math.PI*2);ctx.fillStyle=selectedTrack?"rgba(255,235,95,.98)":`rgba(155,245,255,${(.12+.58*strength)*durationWeight})`;ctx.fill();continue;}
        const averageStrength=Math.sqrt((m+decodedTracks.magnitudes[i-1])/2);
        ctx.beginPath();ctx.moveTo(coords.x(decodedTracks.times[i-1]),coords.y(decodedTracks.midis[i-1]));ctx.lineTo(x,y);
        ctx.strokeStyle=selectedTrack?"rgba(255,235,95,.98)":`rgba(135,240,255,${(.16+.76*averageStrength)*durationWeight})`;ctx.lineWidth=selectedTrack?2.8+.8*averageStrength:.65+1.75*averageStrength+Math.min(1.1,duration*.55);ctx.stroke();
      }
      ctx.restore();
    }

    for(let midi=Math.floor(props.view.pitchBottom);midi<=Math.ceil(props.view.pitchBottom+props.view.visibleNotes);midi+=1){
      const y=coords.y(midi-.5);ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.strokeStyle=midi%12===0?"rgba(255,255,255,.22)":"rgba(255,255,255,.075)";ctx.stroke();
      if(midi%12===0){ctx.fillStyle="rgba(235,240,245,.68)";ctx.font="11px Segoe UI,sans-serif";ctx.fillText(`C${Math.floor(midi/12)-1}`,5,Math.max(12,y-3));}
    }
    const secStep=props.view.windowSeconds<=5?.25:props.view.windowSeconds<=20?1:props.view.windowSeconds<=60?5:10;
    const timelineTicks=boundedTimelineTickRange(props.view.start,props.view.windowSeconds,secStep);
    for(let i=0;i<timelineTicks.count;i+=1){const t=(timelineTicks.first+i*timelineTicks.stride)*secStep,x=coords.x(t);if(!Number.isFinite(x))continue;ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.strokeStyle="rgba(255,255,255,.075)";ctx.stroke();}
    if(props.settings.gridEnabled){
      const beat=60/Math.max(1e-6,props.settings.bpm),offset=props.settings.offsetMs/1000;
      const beatGrid=boundedGridRange(props.view.start,props.view.windowSeconds,beat,offset);
      for(let i=0;i<beatGrid.count;i+=1){
        const k=beatGrid.first+i*beatGrid.stride,x=coords.x(offset+k*beat);
        if(!Number.isFinite(x))continue;
        ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.strokeStyle=k%4===0?"rgba(255,230,120,.38)":"rgba(255,255,255,.17)";ctx.stroke();
      }
    }

    const alpha=props.view.mode==="spec"?.42:props.view.mode==="notes"?.92:.68;
    function drawNote(note: NoteDto, selected: boolean, ghost: "none" | "move" | "duplicate" = "none") {
      const x1=coords.x(note.start),x2=coords.x(note.end);if(x2<0||x1>w)return;
      const isGhost=ghost!=="none";
      ctx.save();
      if(isGhost){ctx.globalAlpha=.72;ctx.setLineDash([5,3]);}
      if((note.kind??"note")==="curve"){
        const steps=Math.max(8,Math.min(96,Math.round((note.end-note.start)/.02)));ctx.beginPath();
        for(let i=0;i<=steps;i+=1){const u=i/steps,x=coords.x(note.start+(note.end-note.start)*u),y=coords.y(noteMidiAt(note,u));if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);}
        ctx.strokeStyle=isGhost?(ghost==="duplicate"?"#67e8a7":"#8dd7ff"):(selected?"#ffe65a":`rgba(90,190,255,${alpha})`);ctx.lineWidth=isGhost?3:selected?4:3;ctx.stroke();
        if(selected&&!isGhost){for(const [x,y] of [[x1,coords.y(note.midi)],[x2,coords.y(note.midi_end??note.midi)]] as Array<[number,number]>){ctx.fillStyle="#fff3a6";ctx.fillRect(x-4,y-5,8,10);}}
      }else{
        const yt=coords.y(note.midi+.43),yb=coords.y(note.midi-.43);
        ctx.fillStyle=isGhost?(ghost==="duplicate"?"rgba(72,220,145,.45)":"rgba(90,190,255,.38)"):(selected?"rgba(255,230,90,.86)":`rgba(70,175,255,${alpha})`);
        ctx.fillRect(x1,yt,Math.max(2,x2-x1),Math.max(2,yb-yt));
        ctx.strokeStyle=isGhost?(ghost==="duplicate"?"#7af0b2":"#9ddcff"):(selected?"#fff1a2":"rgba(170,225,255,.82)");
        ctx.strokeRect(x1,yt,Math.max(2,x2-x1),Math.max(2,yb-yt));
        if(selected&&!isGhost){ctx.fillStyle="#fff3a6";ctx.fillRect(x1-3,yt,6,yb-yt);ctx.fillRect(x2-3,yt,6,yb-yt);}
      }
      ctx.restore();
    }

    for(const index of notesInTimeRange(noteTimeIndex,props.view.start,props.view.start+props.view.windowSeconds)){const note=props.notes[index];if(note)drawNote(note,selectedSet.has(index))}
    if(keyboardNote!==null){const note=props.notes[keyboardNote];if(note){const x=coords.x(note.start),y=coords.y(note.midi);ctx.save();ctx.strokeStyle="#ffffff";ctx.lineWidth=2;ctx.setLineDash([2,2]);ctx.strokeRect(x-6,y-7,12,14);ctx.restore();}}

  },[coords,decoded,decodedTracks,directSpectrumCanvas,keyboardNote,noteTimeIndex,props.directSpectrum,props.notes,props.settings.bpm,props.settings.displayMode,props.settings.gridEnabled,props.settings.offsetMs,props.settings.spectrumOpacity,props.view,selectedSet,selectedTrackSet,size,spectrumCanvas]);

  useEffect(()=>{
    const canvas=playheadRef.current;if(!canvas)return;const dpr=window.devicePixelRatio||1;
    canvas.width=Math.max(1,Math.round(size.width*dpr));canvas.height=Math.max(1,Math.round(size.height*dpr));canvas.style.width=`${size.width}px`;canvas.style.height=`${size.height}px`;
    const ctx=canvas.getContext("2d");if(!ctx)return;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,size.width,size.height);
    if(drag&&["move","duplicate-move","resize-start","resize-end"].includes(drag.mode)){
      const rawDx=drag.nowTime-drag.startTime;let dy=Math.round(drag.nowMidi-drag.startMidi);const first=props.notes[drag.indices[0]];
      let dx=rawDx;if(first&&props.settings.snapEnabled&&Math.abs(rawDx)>1e-12&&(drag.mode==="move"||drag.mode==="duplicate-move"))dx=snapTime(props.settings,props.playback.duration,first.start+rawDx)-first.start;
      const bounded = clampDraggedNoteOffset(props.notes, drag.indices, dx, dy, props.playback.duration);
      dx = bounded.dx; dy = bounded.dy;
      for(const index of drag.indices){const note=props.notes[index];if(!note)continue;const ghost=drag.mode==="resize-start"?resizeNote(note,"start",rawDx,props.settings,props.playback.duration):drag.mode==="resize-end"?resizeNote(note,"end",rawDx,props.settings,props.playback.duration):shiftNote(note,dx,dy);const x1=coords.x(ghost.start),x2=coords.x(ghost.end);ctx.save();ctx.globalAlpha=.72;ctx.setLineDash([5,3]);
        if((ghost.kind??"note")==="curve"){const steps=Math.max(8,Math.min(96,Math.round((ghost.end-ghost.start)/.02)));ctx.beginPath();for(let i=0;i<=steps;i++){const u=i/steps;i?ctx.lineTo(coords.x(ghost.start+(ghost.end-ghost.start)*u),coords.y(noteMidiAt(ghost,u))):ctx.moveTo(coords.x(ghost.start),coords.y(noteMidiAt(ghost,0)))}ctx.strokeStyle=drag.mode==="duplicate-move"?"#67e8a7":"#8dd7ff";ctx.lineWidth=3;ctx.stroke()}else{const yt=coords.y(ghost.midi+.43),yb=coords.y(ghost.midi-.43);ctx.fillStyle=drag.mode==="duplicate-move"?"rgba(72,220,145,.45)":"rgba(90,190,255,.38)";ctx.fillRect(x1,yt,Math.max(2,x2-x1),Math.max(2,yb-yt));ctx.strokeStyle=drag.mode==="duplicate-move"?"#7af0b2":"#9ddcff";ctx.strokeRect(x1,yt,Math.max(2,x2-x1),Math.max(2,yb-yt))}ctx.restore()}
    }
    if(drag){
      const shownStart=drag.mode==="cut-range"?snapTime(props.settings,props.playback.duration,drag.startTime):drag.startTime;
      const shownNow=drag.mode==="cut-range"?snapTime(props.settings,props.playback.duration,drag.nowTime):drag.nowTime;
      const x1=coords.x(shownStart),x2=coords.x(shownNow),y1=coords.y(drag.startMidi),y2=coords.y(drag.nowMidi);
      ctx.save();ctx.setLineDash([6,4]);
      if(drag.mode==="cut-range"){
        ctx.strokeStyle="rgba(255,120,120,.98)";ctx.fillStyle="rgba(255,80,80,.2)";
        ctx.fillRect(Math.min(x1,x2),0,Math.abs(x2-x1),size.height);ctx.strokeRect(Math.min(x1,x2),0,Math.abs(x2-x1),size.height);
      }else{
        ctx.strokeStyle=drag.mode==="track-region"?"rgba(255,235,95,.98)":"rgba(255,255,255,.9)";ctx.fillStyle=drag.mode==="track-region"?"rgba(255,220,70,.14)":"rgba(70,175,255,.16)";
        if(drag.mode==="region"||drag.mode==="track-region"){ctx.fillRect(Math.min(x1,x2),Math.min(y1,y2),Math.abs(x2-x1),Math.abs(y2-y1));ctx.strokeRect(Math.min(x1,x2),Math.min(y1,y2),Math.abs(x2-x1),Math.abs(y2-y1));}
        else if(drag.mode==="create"){const ym=coords.y((drag.startMidi+drag.nowMidi)/2),rh=Math.abs(coords.y(0)-coords.y(.9));ctx.fillRect(Math.min(x1,x2),ym-rh/2,Math.abs(x2-x1),rh);ctx.strokeRect(Math.min(x1,x2),ym-rh/2,Math.abs(x2-x1),rh);}
        else if(drag.mode==="curve"){ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();}
      }
      ctx.restore();
    }
    const x=coords.x(props.playback.time);if(x>=0&&x<=size.width){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,size.height);ctx.strokeStyle="rgba(255,255,255,.92)";ctx.lineWidth=2;ctx.stroke()}
  },[coords,drag,props.notes,props.playback.duration,props.playback.time,props.settings,size]);

  function hoveredTrack(px:number,py:number){
    if(!decodedTracks||props.view.mode==="notes")return null;
    let bestDistance=64,best:null|{id:number;frequency:number;noteName:string;duration:number;magnitude:number}=null;
    const candidates = trackHitIndex ? nearbySegmentIndices(trackHitIndex.index, px, py) : [];
    for(const i of candidates){
      const bx=coords.x(decodedTracks.times[i]),by=coords.y(decodedTracks.midis[i]);let distance=(px-bx)**2+(py-by)**2,midi=decodedTracks.midis[i],magnitude=decodedTracks.magnitudes[i];
      if((decodedTracks.flags[i]&1)===0&&i>0&&validTrackPoint(i-1)&&decodedTracks.ids[i]===decodedTracks.ids[i-1]){
        const segment=trackHitIndex!.segments[i],ax=segment.ax,ay=segment.ay,dx=bx-ax,dy=by-ay,length=Math.max(1e-9,dx*dx+dy*dy),fraction=Math.max(0,Math.min(1,((px-ax)*dx+(py-ay)*dy)/length)),qx=ax+dx*fraction,qy=ay+dy*fraction;
        distance=(px-qx)**2+(py-qy)**2;midi=decodedTracks.midis[i-1]+(decodedTracks.midis[i]-decodedTracks.midis[i-1])*fraction;magnitude=decodedTracks.magnitudes[i-1]+(decodedTracks.magnitudes[i]-decodedTracks.magnitudes[i-1])*fraction;
      }
      if(distance<bestDistance){bestDistance=distance;best={id:decodedTracks.ids[i],frequency:midiToHz(midi),noteName:midiLabel(midi),duration:decodedTracks.durations[i],magnitude};}
    }
    return best;
  }

  function eventPosition(event: ReactPointerEvent<HTMLCanvasElement>|ReactMouseEvent<HTMLCanvasElement>){
    const r=event.currentTarget.getBoundingClientRect(),x=event.clientX-r.left,y=event.clientY-r.top;
    return{time:coords.time(x),midi:coords.midi(y),x,y};
  }
  function edgeFor(index:number,px:number){
    const n=props.notes[index];if(!n)return null;
    return noteEdgeAt(coords.x(n.start),coords.x(n.end),px);
  }
  function clearTrackSelection(){props.onTrackSelectionChange({ids:[],range:null,useRange:false});}
  function onPointerDown(event:ReactPointerEvent<HTMLCanvasElement>){
    if(event.button!==0 || !canStartCanvasGesture(activePointerIdRef.current))return;
    cursorReporterRef.current.cancel();
    // Dragging does not update hover, so invalidate the last displayed Track now.
    props.onTrackHover?.(null);
    event.currentTarget.focus({ preventScroll: true });
    keyboardSelectionRef.current = null;
    keyboardAnchorRef.current = null;
    setKeyboardNote(null);
    event.currentTarget.setPointerCapture(event.pointerId);
    activePointerIdRef.current = event.pointerId;
    const p=eventPosition(event);
    if(event.ctrlKey&&event.altKey&&props.selected.length){
      clearTrackSelection();
      setDrag({mode:"cut-range",startTime:p.time,startMidi:p.midi,nowTime:p.time,nowMidi:p.midi,indices:props.selected});
      return;
    }
    const hit=hitNote(props.notes,noteTimeIndex,p.time,p.midi,props.view.visibleNotes/Math.max(1,size.height));
    if(hit!==null){
      setKeyboardNote(hit);
      clearTrackSelection();
      let next=props.selected;
      if(event.ctrlKey){next=props.selected.includes(hit)?props.selected.filter(x=>x!==hit):[...props.selected,hit];props.onSelect(next);return;}
      if(event.shiftKey){next=Array.from(new Set([...props.selected,hit])).sort((a,b)=>a-b);props.onSelect(next);return;}
      if(!props.selected.includes(hit)){next=[hit];props.onSelect(next);}
      const edge=event.altKey?null:edgeFor(hit,p.x);
      const mode:DragMode=event.altKey?"duplicate-move":edge==="start"?"resize-start":edge==="end"?"resize-end":"move";
      setDrag({mode,startTime:p.time,startMidi:p.midi,nowTime:p.time,nowMidi:p.midi,indices:next});
      return;
    }
    if(event.shiftKey&&decodedTracks&&props.view.mode!=="notes"){
      setDrag({mode:"track-region",startTime:p.time,startMidi:p.midi,nowTime:p.time,nowMidi:p.midi,indices:[],trackAdditive:event.ctrlKey});
      return;
    }
    const trackHit=hoveredTrack(p.x,p.y);
    if(trackHit){
      props.onTrackSelectionChange({ids:updateTrackSelection(props.trackSelection.ids,trackHit.id,event.ctrlKey),range:null,useRange:false});
      props.onSelect([]);
      return;
    }
    clearTrackSelection();
    setDrag({mode:event.ctrlKey?"region":event.altKey?"curve":"create",startTime:p.time,startMidi:p.midi,nowTime:p.time,nowMidi:p.midi,indices:[]});
  }
  function onPointerMove(event:ReactPointerEvent<HTMLCanvasElement>){
    if(activePointerIdRef.current!==null && !isCanvasGesturePointer(activePointerIdRef.current,event.pointerId))return;
    const p=eventPosition(event);
    if(drag){
      // A cancel clears pointer ownership synchronously, but React may still
      // expose the previous drag state until its next render. Never revive it.
      if (!isCanvasGesturePointer(activePointerIdRef.current,event.pointerId)) return;
      setDrag({...drag,nowTime:p.time,nowMidi:p.midi});
      return;
    }
    const track=hoveredTrack(p.x,p.y);
    cursorReporterRef.current.report({time:p.time,midi:p.midi,track}, value => {
      props.onCursorMove?.(value.time,value.midi);
      props.onTrackHover?.(value.track);
    });
    if(event.ctrlKey&&event.altKey&&props.selected.length){event.currentTarget.style.cursor="crosshair";return;}
    const hit=hitNote(props.notes,noteTimeIndex,p.time,p.midi,props.view.visibleNotes/Math.max(1,size.height));
    event.currentTarget.style.cursor=hit!==null&&!event.altKey&&edgeFor(hit,p.x)?"ew-resize":hit!==null?"move":track?"pointer":"crosshair";
  }
  async function onPointerUp(event:ReactPointerEvent<HTMLCanvasElement>){
    if(!isCanvasGesturePointer(activePointerIdRef.current,event.pointerId))return;
    activePointerIdRef.current = null;
    if(!drag)return;
    const p=eventPosition(event),cur={...drag,nowTime:p.time,nowMidi:p.midi};setDrag(null);
    if(cur.mode==="track-region"){
      const range=normalizeTrackRange(cur.startTime,cur.nowTime,cur.startMidi,cur.nowMidi);
      if(range.endTime-range.startTime>=.001){
        const ids=await props.onFindTracks(range);
        if(ids===null)return; // Ignore a stale document or superseded selection.
        props.onTrackSelectionChange({ids:mergeTrackSelection(props.trackSelection.ids,ids,Boolean(cur.trackAdditive)),range,useRange:ids.length>0});
        props.onSelect([]);
      }
      return;
    }
    if(cur.mode==="cut-range"){
      const a=snapTime(props.settings,props.playback.duration,cur.startTime),b=snapTime(props.settings,props.playback.duration,cur.nowTime);
      if(Math.abs(b-a)>=.001)await props.onCutRange(cur.indices,Math.min(a,b),Math.max(a,b));
      return;
    }
    if(cur.mode==="move"||cur.mode==="duplicate-move"){
      const dx=cur.nowTime-cur.startTime,dy=Math.round(cur.nowMidi-cur.startMidi);
      if(Math.abs(dx)>1e-4||dy!==0){if(cur.mode==="duplicate-move")await props.onDuplicateMove(cur.indices,dx,dy);else await props.onMove(cur.indices,dx,dy);}
      return;
    }
    if(cur.mode==="resize-start"||cur.mode==="resize-end"){
      const d=cur.nowTime-cur.startTime;if(Math.abs(d)>1e-4)await props.onResize(cur.indices,cur.mode==="resize-start"?"start":"end",d);return;
    }
    if(cur.mode==="region"){props.onSelect(props.notes.flatMap((n,i)=>noteIntersects(n,cur.startTime,cur.nowTime,cur.startMidi,cur.nowMidi)?[i]:[]));return;}
    if(Math.abs(cur.nowTime-cur.startTime)*size.width/Math.max(.001,props.view.windowSeconds)<4){props.onSelect([]);await props.onSeek(cur.startTime);return;}
    const a=Math.min(cur.startTime,cur.nowTime),b=Math.max(cur.startTime,cur.nowTime);
    if(cur.mode==="curve"){
      const p0=cur.startTime<=cur.nowTime?cur.startMidi:cur.nowMidi,p3=cur.startTime<=cur.nowTime?cur.nowMidi:cur.startMidi;
      await props.onAdd(a,b,p0,"curve",p3);
    }else await props.onAdd(a,b,(cur.startMidi+cur.nowMidi)/2,"note",cur.nowMidi);
  }
  function cancelDrag(event:ReactPointerEvent<HTMLCanvasElement>){
    if(!isCanvasGesturePointer(activePointerIdRef.current,event.pointerId))return;
    cursorReporterRef.current.cancel();
    props.onTrackHover?.(null);
    activePointerIdRef.current = null;
    releaseCanvasPointerCapture(event.currentTarget, event.pointerId);
    setDrag(null);
  }
  function onCanvasBlur(event: ReactFocusEvent<HTMLCanvasElement>) {
    // Tab or an external focus change ends the gesture before window shortcuts
    // can act on the note indices captured at pointer down.
    const pointerId = activePointerIdRef.current;
    if (pointerId === null) return;
    cursorReporterRef.current.cancel();
    props.onTrackHover?.(null);
    activePointerIdRef.current = null;
    releaseCanvasPointerCapture(event.currentTarget, pointerId);
    setDrag(null);
  }
  async function onContextMenu(event:ReactMouseEvent<HTMLCanvasElement>){
    event.preventDefault();
    // A second-button menu must not delete a note while a pointer owns a drag.
    // The pending drag still holds note indices captured before any deletion.
    if (!canStartCanvasGesture(activePointerIdRef.current)) return;
    const p=eventPosition(event),hit=hitNote(props.notes,noteTimeIndex,p.time,p.midi,props.view.visibleNotes/Math.max(1,size.height));
    const indices=contextMenuDeleteIndices(hit);
    if(indices.length)await props.onDelete(indices);
  }
  function onCanvasKeyDown(event: ReactKeyboardEvent<HTMLCanvasElement>) {
    // The first Escape cancels pointer capture. Auto-repeat after that must
    // not run the idle Escape path and erase the preserved selection.
    if (shouldIgnoreRepeatedCanvasEscape(event)) {
      event.preventDefault();
      return;
    }
    if (shouldHandleCanvasEscape(event, activePointerIdRef.current)) {
      event.preventDefault();
      // Ctrl-click can own pointer capture without creating a drag state.
      if (canvasEscapeAction(activePointerIdRef.current !== null) === "cancel-drag") {
        // Ctrl-click has capture without drag state and may still have a
        // delayed hover report from pointermove. Do not publish it after Escape.
        cursorReporterRef.current.cancel();
        props.onTrackHover?.(null);
        setDrag(null);
        releaseCanvasPointerCapture(event.currentTarget, activePointerIdRef.current);
        activePointerIdRef.current = null;
        return;
      }
      keyboardSelectionRef.current = [];
      keyboardAnchorRef.current = null;
      setKeyboardNote(null);
      clearIdleCanvasSelection(clearTrackSelection, () => props.onSelect([]));
      return;
    }
    // Keep the pointer gesture's captured note indices stable. Also consume
    // global Ctrl+Shift+arrow moves and pitch/seek arrows while the pointer is held.
    if (shouldSuppressCanvasArrowDuringPointerGesture(event.key, activePointerIdRef.current)) {
      event.preventDefault();
      return;
    }
    // The canvas receives keyboard focus on pointer down. Prevent global
    // cut/delete/undo/file shortcuts from changing notes during a live drag.
    if (shouldSuppressCanvasNonArrowKeyDuringPointerGesture(event.key, activePointerIdRef.current)) {
      event.preventDefault();
      return;
    }
    if (!isNoteNavigationKey(event)) return;
    if (!keyboardOrder.length) return;
    event.preventDefault();
    const delta = event.key === "ArrowRight" ? 1 : -1;
    const current = keyboardNote ?? props.selected.at(-1) ?? null;
    const next = adjacentNoteIndex(keyboardOrder, current, delta);
    if (next === null) return;
    // Shift extends/shrinks one anchored range, rather than permanently unioning
    // every note ever visited by the keyboard focus.
    const anchor = event.shiftKey ? (keyboardAnchorRef.current ?? current ?? next) : null;
    const nextSelection = anchor === null ? [next] : keyboardRangeSelection(keyboardOrder, anchor, next);
    keyboardAnchorRef.current = anchor;
    keyboardSelectionRef.current = nextSelection;
    setKeyboardNote(next);
    props.onSelect(nextSelection);
    const note = props.notes[next], changes: Partial<ViewState> = {};
    if (note.start < props.view.start || note.end > props.view.start + props.view.windowSeconds)
      changes.start = Math.max(0, note.start - props.view.windowSeconds * .15);
    const nextPitchBottom = pitchBottomToRevealNote(props.view, note.midi);
    if (nextPitchBottom !== null) changes.pitchBottom = nextPitchBottom;
    if (Object.keys(changes).length) void props.onView(changes);
  }
  // Keep the wheel baseline aligned with committed views, but do not carry
  // sub-MIDI steps across an external pitch or display-mode change.
  useLayoutEffect(() => {
    syncCanvasWheelView(wheelViewRef, wheelPitchAccumulatorRef, props.view);
  }, [props.view]);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const handler = createCanvasWheelHandler({
      canvas,
      view: wheelViewRef,
      pitchAccumulator: wheelPitchAccumulatorRef,
      activePointerId: activePointerIdRef,
      duration: wheelDurationRef,
      onView: wheelOnViewRef,
    });
    canvas.addEventListener("wheel", handler, { passive: false });
    return () => canvas.removeEventListener("wheel", handler);
  }, []);
  return <div className="canvas-wrap" ref={containerRef}>
    <canvas ref={canvasRef} tabIndex={0} role="region" aria-label="採譜エディタ。時間を横軸、音高を縦軸にスペクトル、Track、Noteを編集します。" aria-describedby="editor-keyboard-help editor-selection-status" title="Track: クリックで選択 / Ctrl+クリックで複数選択 / Shift+ドラッグでTrack範囲選択 / Ctrl+Alt+ドラッグで選択ノートを切り取り" onKeyDown={onCanvasKeyDown} onBlur={onCanvasBlur} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerLeave={()=>{cursorReporterRef.current.cancel();props.onTrackHover?.(null)}} onPointerUp={e=>void onPointerUp(e)} onPointerCancel={cancelDrag} onLostPointerCapture={cancelDrag} onContextMenu={e=>void onContextMenu(e)}/>
    <canvas ref={playheadRef} className="playhead-canvas" aria-hidden="true"/>
    <span id="editor-keyboard-help" className="sr-only">左右矢印で時間順にノートを選択します。Shiftと矢印で複数選択、Escapeで選択解除します。F1で操作方法を確認できます。</span>
    <span id="editor-selection-status" className="sr-only" aria-live="polite">{keyboardNote === null ? "" : (()=>{const note=props.notes[keyboardNote];return note ? `${keyboardNote + 1}番目の${(note.kind??"note")==="curve"?"カーブノート":"ノート"}、開始${note.start.toFixed(3)}秒、${midiLabel(note.midi)}、選択${props.selected.length}件` : ""})()}</span>
  </div>;
}
