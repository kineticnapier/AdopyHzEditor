import { useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent, type PointerEvent as ReactPointerEvent, type WheelEvent as ReactWheelEvent } from "react";
import type { EditorSettings, NoteDto, PlaybackState, SpectrogramPayload, ViewState } from "./bridge";

type Props = {
  notes: NoteDto[];
  selected: number[];
  settings: EditorSettings;
  view: ViewState;
  playback: PlaybackState;
  spectrum: SpectrogramPayload | null;
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
};

type DragMode = "create" | "curve" | "region" | "cut-range" | "move" | "duplicate-move" | "resize-start" | "resize-end";
type DragState = { mode: DragMode; startTime: number; startMidi: number; nowTime: number; nowMidi: number; indices: number[] };

function midiToHz(midi: number) { return 440 * 2 ** ((midi - 69) / 12); }
function hzToMidi(hz: number) { return 69 + 12 * Math.log2(Math.max(1e-9, hz) / 440); }
function cubic(p0: number, p1: number, p2: number, p3: number, u: number) { const v = 1 - u; return v ** 3 * p0 + 3 * v ** 2 * u * p1 + 3 * v * u ** 2 * p2 + u ** 3 * p3; }
function noteMidiAt(note: NoteDto, u: number) {
  if ((note.kind ?? "note") !== "curve") return note.midi;
  const p0 = note.midi, p3 = note.midi_end ?? p0, p1 = note.ctrl1_midi ?? p0, p2 = note.ctrl2_midi ?? p3, t = Math.max(0, Math.min(1, u));
  const mode = note.interpolation ?? "bezier_pitch";
  if (mode === "linear_pitch") return p0 + (p3 - p0) * t;
  if (mode === "linear_hz") return hzToMidi(midiToHz(p0) + (midiToHz(p3) - midiToHz(p0)) * t);
  if (mode === "bezier_hz") return hzToMidi(cubic(midiToHz(p0), midiToHz(p1), midiToHz(p2), midiToHz(p3), t));
  return cubic(p0, p1, p2, p3, t);
}
function hitNote(notes: NoteDto[], time: number, midi: number, pitchStep = 1) {
  const hits: Array<[number, number]> = [];
  notes.forEach((note, index) => {
    if (time < note.start - 1e-9 || time > note.end + 1e-9) return;
    if ((note.kind ?? "note") === "curve") {
      const u = note.end <= note.start ? 0 : (time - note.start) / (note.end - note.start);
      if (Math.abs(midi - noteMidiAt(note, u)) <= .6) hits.push([note.end - note.start, index]);
    } else if (Math.abs(midi - note.midi) <= Math.max(.6, pitchStep * .55)) hits.push([note.end - note.start, index]);
  });
  hits.sort((a, b) => a[0] - b[0]);
  return hits[0]?.[1] ?? null;
}
function noteIntersects(note: NoteDto, x1: number, x2: number, y1: number, y2: number) {
  const xmin = Math.min(x1, x2), xmax = Math.max(x1, x2), ymin = Math.min(y1, y2), ymax = Math.max(y1, y2);
  if (note.end < xmin || note.start > xmax) return false;
  if ((note.kind ?? "note") !== "curve") return note.midi + .55 >= ymin && note.midi - .55 <= ymax;
  for (let i = 0; i <= 32; i += 1) {
    const u = i / 32, t = note.start + (note.end - note.start) * u;
    if (t >= xmin && t <= xmax) {
      const y = noteMidiAt(note, u);
      if (y + .55 >= ymin && y - .55 <= ymax) return true;
    }
  }
  return false;
}
function colorFor(v: number, map: string): [number, number, number] {
  const x = Math.max(0, Math.min(1, v));
  if (map === "gray") { const q = Math.round(x * 255); return [q, q, q]; }
  const maps: Record<string, Array<[number, [number, number, number]]>> = {
    wavetone: [[0,[0,0,0]],[.12,[0,0,120]],[.35,[0,80,255]],[.55,[0,255,180]],[.75,[255,240,0]],[1,[255,0,0]]],
    viridis: [[0,[68,1,84]],[.33,[49,104,142]],[.66,[53,183,121]],[1,[253,231,37]]],
    magma: [[0,[0,0,4]],[.33,[113,31,129]],[.66,[237,104,37]],[1,[252,253,191]]],
    inferno: [[0,[0,0,4]],[.33,[120,28,109]],[.66,[237,105,37]],[1,[252,255,164]]],
    plasma: [[0,[13,8,135]],[.33,[126,3,168]],[.66,[224,100,98]],[1,[240,249,33]]],
  };
  const stops = maps[map] ?? maps.wavetone;
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
  const raw = atob(payload.data), bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return { ...payload, rows: payload.rows, cols: payload.cols, bytes };
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
  const canvasRef = useRef<HTMLCanvasElement>(null), containerRef = useRef<HTMLDivElement>(null), lastCursorReport = useRef(0);
  const [size, setSize] = useState({ width: 800, height: 500 });
  const [drag, setDrag] = useState<DragState | null>(null);
  const decoded = useMemo(() => decodeSpectrum(props.spectrum), [props.spectrum]);
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

  useEffect(() => {
    const el = containerRef.current; if (!el) return;
    const observer = new ResizeObserver(([entry]) => setSize({ width: Math.max(1,entry.contentRect.width), height: Math.max(1,entry.contentRect.height) }));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const coords = useMemo(() => {
    const { width, height } = size, start = props.view.start, win = Math.max(.001, props.view.windowSeconds), bottom = props.view.pitchBottom - .5, visible = Math.max(1, props.view.visibleNotes);
    return {
      x: (time:number) => (time-start)/win*width,
      y: (midi:number) => height-(midi-bottom)/visible*height,
      time: (px:number) => start+px/width*win,
      midi: (py:number) => bottom+(height-py)/height*visible,
    };
  }, [props.view, size]);

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
      const sx=Math.max(0,props.view.start/decoded.duration*decoded.cols), sw=Math.max(1,Math.min(decoded.cols-sx,props.view.windowSeconds/decoded.duration*decoded.cols));
      const full=Math.max(1e-6,decoded.midiMax-decoded.midiMin+1), top=props.view.pitchBottom+props.view.visibleNotes-.5,bottom=props.view.pitchBottom-.5;
      const sy=Math.max(0,(decoded.midiMax+.5-top)/full*decoded.rows), sh=Math.max(1,Math.min(decoded.rows-sy,(top-bottom)/full*decoded.rows));
      ctx.save(); ctx.globalAlpha=props.view.mode==="spec"?1:.7; ctx.imageSmoothingEnabled=props.settings.displayMode==="smooth";
      ctx.drawImage(spectrumCanvas,sx,sy,sw,sh,0,0,w,h); ctx.restore();
    }

    for(let midi=Math.floor(props.view.pitchBottom);midi<=Math.ceil(props.view.pitchBottom+props.view.visibleNotes);midi+=1){
      const y=coords.y(midi-.5);ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.strokeStyle=midi%12===0?"rgba(255,255,255,.22)":"rgba(255,255,255,.075)";ctx.stroke();
      if(midi%12===0){ctx.fillStyle="rgba(235,240,245,.68)";ctx.font="11px Segoe UI,sans-serif";ctx.fillText(`C${Math.floor(midi/12)-1}`,5,Math.max(12,y-3));}
    }
    const secStep=props.view.windowSeconds<=5?.25:props.view.windowSeconds<=20?1:props.view.windowSeconds<=60?5:10;
    for(let t=Math.floor(props.view.start/secStep)*secStep;t<=props.view.start+props.view.windowSeconds+secStep;t+=secStep){const x=coords.x(t);ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.strokeStyle="rgba(255,255,255,.075)";ctx.stroke();}
    if(props.settings.gridEnabled){
      const beat=60/Math.max(1e-6,props.settings.bpm),offset=props.settings.offsetMs/1000,k0=Math.floor((props.view.start-offset)/beat),k1=Math.ceil((props.view.start+props.view.windowSeconds-offset)/beat);
      for(let k=k0;k<=k1;k+=1){const x=coords.x(offset+k*beat);ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.strokeStyle=k%4===0?"rgba(255,230,120,.38)":"rgba(255,255,255,.17)";ctx.stroke();}
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

    props.notes.forEach((note,index)=>drawNote(note,props.selected.includes(index)));

    if(drag && ["move","duplicate-move","resize-start","resize-end"].includes(drag.mode)) {
      const rawDx=drag.nowTime-drag.startTime;
      const dy=Math.round(drag.nowMidi-drag.startMidi);
      let dx=rawDx;
      const first=props.notes[drag.indices[0]];
      if(first&&props.settings.snapEnabled&&(drag.mode==="move"||drag.mode==="duplicate-move")) dx=snapTime(props.settings,props.playback.duration,first.start+rawDx)-first.start;
      for(const index of drag.indices){
        const note=props.notes[index];if(!note)continue;
        const ghost=drag.mode==="resize-start"?resizeNote(note,"start",rawDx,props.settings,props.playback.duration):drag.mode==="resize-end"?resizeNote(note,"end",rawDx,props.settings,props.playback.duration):shiftNote(note,dx,dy);
        drawNote(ghost,false,drag.mode==="duplicate-move"?"duplicate":"move");
      }
    }

    if(drag){
      const x1=coords.x(drag.startTime),x2=coords.x(drag.nowTime),y1=coords.y(drag.startMidi),y2=coords.y(drag.nowMidi);
      ctx.save();ctx.setLineDash([6,4]);
      if(drag.mode==="cut-range"){
        ctx.strokeStyle="rgba(255,120,120,.98)";ctx.fillStyle="rgba(255,80,80,.2)";
        ctx.fillRect(Math.min(x1,x2),0,Math.abs(x2-x1),h);ctx.strokeRect(Math.min(x1,x2),0,Math.abs(x2-x1),h);
      }else{
        ctx.strokeStyle="rgba(255,255,255,.9)";ctx.fillStyle="rgba(70,175,255,.16)";
        if(drag.mode==="region"){ctx.fillRect(Math.min(x1,x2),Math.min(y1,y2),Math.abs(x2-x1),Math.abs(y2-y1));ctx.strokeRect(Math.min(x1,x2),Math.min(y1,y2),Math.abs(x2-x1),Math.abs(y2-y1));}
        else if(drag.mode==="create"){const ym=coords.y((drag.startMidi+drag.nowMidi)/2),rh=Math.abs(coords.y(0)-coords.y(.9));ctx.fillRect(Math.min(x1,x2),ym-rh/2,Math.abs(x2-x1),rh);ctx.strokeRect(Math.min(x1,x2),ym-rh/2,Math.abs(x2-x1),rh);}
        else if(drag.mode==="curve"){ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();}
      }
      ctx.restore();
    }

    const playX=coords.x(props.playback.time);if(playX>=0&&playX<=w){ctx.beginPath();ctx.moveTo(playX,0);ctx.lineTo(playX,h);ctx.strokeStyle="rgba(255,255,255,.92)";ctx.lineWidth=2;ctx.stroke();}
  },[coords,decoded,drag,props.notes,props.playback.duration,props.playback.time,props.selected,props.settings,props.view,size,spectrumCanvas]);

  function eventPosition(event: ReactPointerEvent<HTMLCanvasElement>|ReactMouseEvent<HTMLCanvasElement>){
    const r=event.currentTarget.getBoundingClientRect(),x=event.clientX-r.left,y=event.clientY-r.top;
    return{time:coords.time(x),midi:coords.midi(y),x,y};
  }
  function edgeFor(index:number,px:number){
    const n=props.notes[index];if(!n)return null;
    const a=Math.abs(px-coords.x(n.start)),b=Math.abs(px-coords.x(n.end));if(Math.min(a,b)>8)return null;
    return a<=b?"start":"end" as const;
  }
  function onPointerDown(event:ReactPointerEvent<HTMLCanvasElement>){
    if(event.button!==0)return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const p=eventPosition(event);
    if(event.ctrlKey&&event.altKey&&props.selected.length){
      setDrag({mode:"cut-range",startTime:p.time,startMidi:p.midi,nowTime:p.time,nowMidi:p.midi,indices:props.selected});
      return;
    }
    const hit=hitNote(props.notes,p.time,p.midi,props.spectrum?.pitchStep??1);
    if(hit!==null){
      let next=props.selected;
      if(event.ctrlKey){next=props.selected.includes(hit)?props.selected.filter(x=>x!==hit):[...props.selected,hit];props.onSelect(next);return;}
      if(event.shiftKey){next=Array.from(new Set([...props.selected,hit])).sort((a,b)=>a-b);props.onSelect(next);return;}
      if(!props.selected.includes(hit)){next=[hit];props.onSelect(next);}
      const edge=edgeFor(hit,p.x);
      const mode:DragMode=edge==="start"?"resize-start":edge==="end"?"resize-end":event.altKey?"duplicate-move":"move";
      setDrag({mode,startTime:p.time,startMidi:p.midi,nowTime:p.time,nowMidi:p.midi,indices:next});
      return;
    }
    setDrag({mode:event.ctrlKey?"region":event.altKey?"curve":"create",startTime:p.time,startMidi:p.midi,nowTime:p.time,nowMidi:p.midi,indices:[]});
  }
  function onPointerMove(event:ReactPointerEvent<HTMLCanvasElement>){
    const p=eventPosition(event);
    if(drag){setDrag({...drag,nowTime:p.time,nowMidi:p.midi});return;}
    const now=performance.now();
    if(props.onCursorMove&&now-lastCursorReport.current>=50){lastCursorReport.current=now;props.onCursorMove(p.time,p.midi);}
    if(event.ctrlKey&&event.altKey&&props.selected.length){event.currentTarget.style.cursor="crosshair";return;}
    const hit=hitNote(props.notes,p.time,p.midi,props.spectrum?.pitchStep??1);
    event.currentTarget.style.cursor=hit!==null&&edgeFor(hit,p.x)?"ew-resize":hit!==null?"move":"crosshair";
  }
  async function onPointerUp(event:ReactPointerEvent<HTMLCanvasElement>){
    if(!drag)return;
    const p=eventPosition(event),cur={...drag,nowTime:p.time,nowMidi:p.midi};setDrag(null);
    if(cur.mode==="cut-range"){
      if(Math.abs(cur.nowTime-cur.startTime)>=.001)await props.onCutRange(cur.indices,Math.min(cur.startTime,cur.nowTime),Math.max(cur.startTime,cur.nowTime));
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
    if(Math.abs(cur.nowTime-cur.startTime)<.035){props.onSelect([]);await props.onSeek(cur.startTime);return;}
    const a=Math.min(cur.startTime,cur.nowTime),b=Math.max(cur.startTime,cur.nowTime);
    if(cur.mode==="curve"){
      const p0=cur.startTime<=cur.nowTime?cur.startMidi:cur.nowMidi,p3=cur.startTime<=cur.nowTime?cur.nowMidi:cur.startMidi;
      await props.onAdd(a,b,p0,"curve",p3);
    }else await props.onAdd(a,b,(cur.startMidi+cur.nowMidi)/2,"note",cur.nowMidi);
  }
  async function onContextMenu(event:ReactMouseEvent<HTMLCanvasElement>){
    event.preventDefault();const p=eventPosition(event),hit=hitNote(props.notes,p.time,p.midi,props.spectrum?.pitchStep??1);if(hit===null)return;
    await props.onDelete(props.selected.includes(hit)&&props.selected.length>1?props.selected:[hit]);
  }
  function onWheel(event:ReactWheelEvent<HTMLCanvasElement>){
    event.preventDefault();const sign=event.deltaY<0?1:-1;
    if(event.shiftKey)void props.onView({pitchBottom:props.view.pitchBottom+sign*3});
    else if(event.altKey)void props.onView({visibleNotes:props.view.visibleNotes-sign*4});
    else if(event.ctrlKey)void props.onView({windowSeconds:props.view.windowSeconds*(sign>0?.85:1.18)});
    else void props.onView({start:props.view.start-sign*props.view.windowSeconds*.08});
  }
  return <div className="canvas-wrap" ref={containerRef}><canvas ref={canvasRef} title="Ctrl+Alt+ドラッグ: 選択ノートの時間範囲を切り取り" onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={e=>void onPointerUp(e)} onContextMenu={e=>void onContextMenu(e)} onWheel={onWheel}/></div>;
}
