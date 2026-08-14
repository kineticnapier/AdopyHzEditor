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
  onDelete(indices: number[]): Promise<void>;
  onSeek(time: number): Promise<void>;
  onView(changes: Partial<ViewState>): Promise<void>;
};

type DragState = {
  mode: "create" | "curve" | "region" | "move";
  startTime: number;
  startMidi: number;
  nowTime: number;
  nowMidi: number;
  indices: number[];
};

function midiToHz(midi: number) {
  return 440 * 2 ** ((midi - 69) / 12);
}

function hzToMidi(hz: number) {
  return 69 + 12 * Math.log2(Math.max(1e-9, hz) / 440);
}

function cubic(p0: number, p1: number, p2: number, p3: number, u: number) {
  const v = 1 - u;
  return v ** 3 * p0 + 3 * v ** 2 * u * p1 + 3 * v * u ** 2 * p2 + u ** 3 * p3;
}

function noteMidiAt(note: NoteDto, u: number) {
  if ((note.kind ?? "note") !== "curve") return note.midi;
  const p0 = note.midi;
  const p3 = note.midi_end ?? p0;
  const p1 = note.ctrl1_midi ?? p0;
  const p2 = note.ctrl2_midi ?? p3;
  const t = Math.max(0, Math.min(1, u));
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
      if (Math.abs(midi - noteMidiAt(note, u)) <= 0.55) hits.push([note.end - note.start, index]);
    } else if (Math.abs(midi - note.midi) <= Math.max(0.55, pitchStep * 0.55)) {
      hits.push([note.end - note.start, index]);
    }
  });
  hits.sort((a, b) => a[0] - b[0]);
  return hits[0]?.[1] ?? null;
}

function noteIntersects(note: NoteDto, x1: number, x2: number, y1: number, y2: number) {
  const xmin = Math.min(x1, x2);
  const xmax = Math.max(x1, x2);
  const ymin = Math.min(y1, y2);
  const ymax = Math.max(y1, y2);
  if (note.end < xmin || note.start > xmax) return false;
  if ((note.kind ?? "note") !== "curve") return note.midi + 0.55 >= ymin && note.midi - 0.55 <= ymax;
  const steps = 32;
  for (let i = 0; i <= steps; i += 1) {
    const u = i / steps;
    const t = note.start + (note.end - note.start) * u;
    if (t < xmin || t > xmax) continue;
    const y = noteMidiAt(note, u);
    if (y + 0.55 >= ymin && y - 0.55 <= ymax) return true;
  }
  return false;
}

function interpolateColor(stops: Array<[number, [number, number, number]]>, v: number) {
  const value = Math.max(0, Math.min(1, v));
  for (let i = 0; i < stops.length - 1; i += 1) {
    const [a, ca] = stops[i];
    const [b, cb] = stops[i + 1];
    if (value <= b) {
      const t = b <= a ? 0 : (value - a) / (b - a);
      return ca.map((c, j) => Math.round(c + (cb[j] - c) * t)) as [number, number, number];
    }
  }
  return stops[stops.length - 1][1];
}

function colorFor(v: number, map: string): [number, number, number] {
  const x = Math.max(0, Math.min(1, v));
  if (map === "gray") {
    const q = Math.round(x * 255);
    return [q, q, q];
  }
  const palettes: Record<string, Array<[number, [number, number, number]]>> = {
    wavetone: [[0, [0, 0, 0]], [0.12, [0, 0, 120]], [0.35, [0, 80, 255]], [0.55, [0, 255, 180]], [0.75, [255, 240, 0]], [1, [255, 0, 0]]],
    viridis: [[0, [68, 1, 84]], [0.33, [49, 104, 142]], [0.66, [53, 183, 121]], [1, [253, 231, 37]]],
    magma: [[0, [0, 0, 4]], [0.33, [113, 31, 129]], [0.66, [237, 104, 37]], [1, [252, 253, 191]]],
    inferno: [[0, [0, 0, 4]], [0.33, [120, 28, 109]], [0.66, [237, 105, 37]], [1, [252, 255, 164]]],
    plasma: [[0, [13, 8, 135]], [0.33, [126, 3, 168]], [0.66, [224, 100, 98]], [1, [240, 249, 33]]],
  };
  return interpolateColor(palettes[map] ?? palettes.wavetone, x);
}

function decodeSpectrum(payload: SpectrogramPayload | null) {
  if (!payload?.available || !payload.data || !payload.rows || !payload.cols) return null;
  const raw = atob(payload.data);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return { ...payload, rows: payload.rows, cols: payload.cols, bytes };
}

export default function EditorCanvas(props: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 800, height: 500 });
  const [drag, setDrag] = useState<DragState | null>(null);
  const decoded = useMemo(() => decodeSpectrum(props.spectrum), [props.spectrum]);
  const spectrumCanvas = useMemo(() => {
    if (!decoded) return null;
    const canvas = document.createElement("canvas");
    canvas.width = decoded.cols;
    canvas.height = decoded.rows;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    const image = ctx.createImageData(decoded.cols, decoded.rows);
    for (let row = 0; row < decoded.rows; row += 1) {
      for (let col = 0; col < decoded.cols; col += 1) {
        const value = decoded.bytes[row * decoded.cols + col] / 255;
        const [r, g, b] = colorFor(value, props.settings.colormap);
        const y = decoded.rows - 1 - row;
        const p = (y * decoded.cols + col) * 4;
        image.data[p] = r;
        image.data[p + 1] = g;
        image.data[p + 2] = b;
        image.data[p + 3] = 255;
      }
    }
    ctx.putImageData(image, 0, 0);
    return canvas;
  }, [decoded, props.settings.colormap]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      const rect = entry.contentRect;
      setSize({ width: Math.max(1, rect.width), height: Math.max(1, rect.height) });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const coords = useMemo(() => {
    const width = size.width;
    const height = size.height;
    const start = props.view.start;
    const windowSeconds = Math.max(0.001, props.view.windowSeconds);
    const bottom = props.view.pitchBottom - 0.5;
    const visible = Math.max(1, props.view.visibleNotes);
    return {
      x(time: number) { return (time - start) / windowSeconds * width; },
      y(midi: number) { return height - (midi - bottom) / visible * height; },
      time(px: number) { return start + px / width * windowSeconds; },
      midi(py: number) { return bottom + (height - py) / height * visible; },
    };
  }, [props.view, size]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.round(size.width * dpr));
    canvas.height = Math.max(1, Math.round(size.height * dpr));
    canvas.style.width = `${size.width}px`;
    canvas.style.height = `${size.height}px`;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const w = size.width;
    const h = size.height;

    ctx.fillStyle = "#080b0e";
    ctx.fillRect(0, 0, w, h);

    if (spectrumCanvas && props.view.mode !== "notes" && decoded?.duration && decoded.midiMin !== undefined && decoded.midiMax !== undefined) {
      const sx = Math.max(0, props.view.start / decoded.duration * decoded.cols);
      const sw = Math.max(1, Math.min(decoded.cols - sx, props.view.windowSeconds / decoded.duration * decoded.cols));
      const fullPitch = Math.max(1e-6, (decoded.midiMax - decoded.midiMin + 1));
      const topMidi = props.view.pitchBottom + props.view.visibleNotes - 0.5;
      const bottomMidi = props.view.pitchBottom - 0.5;
      const sy = Math.max(0, (decoded.midiMax + 0.5 - topMidi) / fullPitch * decoded.rows);
      const sh = Math.max(1, Math.min(decoded.rows - sy, (topMidi - bottomMidi) / fullPitch * decoded.rows));
      ctx.save();
      ctx.globalAlpha = props.view.mode === "spec" ? 1 : 0.7;
      ctx.imageSmoothingEnabled = props.settings.displayMode === "smooth";
      ctx.drawImage(spectrumCanvas, sx, sy, sw, sh, 0, 0, w, h);
      ctx.restore();
    }

    const pitchFirst = Math.floor(props.view.pitchBottom);
    const pitchLast = Math.ceil(props.view.pitchBottom + props.view.visibleNotes);
    for (let midi = pitchFirst; midi <= pitchLast; midi += 1) {
      const y = coords.y(midi - 0.5);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.strokeStyle = midi % 12 === 0 ? "rgba(255,255,255,.22)" : "rgba(255,255,255,.075)";
      ctx.lineWidth = 1;
      ctx.stroke();
      if (midi % 12 === 0) {
        ctx.fillStyle = "rgba(235,240,245,.68)";
        ctx.font = "11px Segoe UI, sans-serif";
        ctx.fillText(`C${Math.floor(midi / 12) - 1}`, 5, Math.max(12, y - 3));
      }
    }

    const secondsStep = props.view.windowSeconds <= 5 ? 0.25 : props.view.windowSeconds <= 20 ? 1 : props.view.windowSeconds <= 60 ? 5 : 10;
    const firstTime = Math.floor(props.view.start / secondsStep) * secondsStep;
    for (let t = firstTime; t <= props.view.start + props.view.windowSeconds + secondsStep; t += secondsStep) {
      const x = coords.x(t);
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.strokeStyle = "rgba(255,255,255,.075)";
      ctx.stroke();
    }
    if (props.settings.gridEnabled) {
      const beat = 60 / Math.max(1e-6, props.settings.bpm);
      const offset = props.settings.offsetMs / 1000;
      const k0 = Math.floor((props.view.start - offset) / beat);
      const k1 = Math.ceil((props.view.start + props.view.windowSeconds - offset) / beat);
      for (let k = k0; k <= k1; k += 1) {
        const x = coords.x(offset + k * beat);
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.strokeStyle = k % 4 === 0 ? "rgba(255,230,120,.38)" : "rgba(255,255,255,.17)";
        ctx.stroke();
      }
    }

    const noteAlpha = props.view.mode === "spec" ? 0.42 : props.view.mode === "notes" ? 0.92 : 0.68;
    props.notes.forEach((note, index) => {
      const selected = props.selected.includes(index);
      const x1 = coords.x(note.start);
      const x2 = coords.x(note.end);
      if (x2 < 0 || x1 > w) return;
      if ((note.kind ?? "note") === "curve") {
        const steps = Math.max(8, Math.min(96, Math.round((note.end - note.start) / 0.02)));
        ctx.beginPath();
        for (let i = 0; i <= steps; i += 1) {
          const u = i / steps;
          const x = coords.x(note.start + (note.end - note.start) * u);
          const y = coords.y(noteMidiAt(note, u));
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.globalAlpha = 1;
        ctx.strokeStyle = selected ? "#ffe65a" : `rgba(90,190,255,${noteAlpha})`;
        ctx.lineWidth = selected ? 4 : 3;
        ctx.stroke();
      } else {
        const yTop = coords.y(note.midi + 0.43);
        const yBottom = coords.y(note.midi - 0.43);
        ctx.globalAlpha = 1;
        ctx.fillStyle = selected ? "rgba(255,230,90,.86)" : `rgba(70,175,255,${noteAlpha})`;
        ctx.fillRect(x1, yTop, Math.max(2, x2 - x1), Math.max(2, yBottom - yTop));
        ctx.strokeStyle = selected ? "#fff1a2" : "rgba(170,225,255,.82)";
        ctx.strokeRect(x1, yTop, Math.max(2, x2 - x1), Math.max(2, yBottom - yTop));
      }
    });

    if (drag) {
      const x1 = coords.x(drag.startTime);
      const x2 = coords.x(drag.nowTime);
      const y1 = coords.y(drag.startMidi);
      const y2 = coords.y(drag.nowMidi);
      ctx.save();
      ctx.setLineDash([6, 4]);
      ctx.strokeStyle = "rgba(255,255,255,.85)";
      ctx.fillStyle = "rgba(70,175,255,.16)";
      if (drag.mode === "region") {
        ctx.fillRect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1));
        ctx.strokeRect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1));
      } else if (drag.mode === "create") {
        const ym = coords.y((drag.startMidi + drag.nowMidi) / 2);
        const rh = Math.abs(coords.y(0) - coords.y(0.9));
        ctx.fillRect(Math.min(x1, x2), ym - rh / 2, Math.abs(x2 - x1), rh);
        ctx.strokeRect(Math.min(x1, x2), ym - rh / 2, Math.abs(x2 - x1), rh);
      } else if (drag.mode === "curve") {
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }
      ctx.restore();
    }

    const playX = coords.x(props.playback.time);
    if (playX >= 0 && playX <= w) {
      ctx.beginPath();
      ctx.moveTo(playX, 0);
      ctx.lineTo(playX, h);
      ctx.strokeStyle = "rgba(255,255,255,.92)";
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  }, [coords, decoded, drag, props.notes, props.playback.time, props.selected, props.settings, props.view, size, spectrumCanvas]);

  function eventPosition(event: ReactPointerEvent<HTMLCanvasElement> | ReactMouseEvent<HTMLCanvasElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    return { time: coords.time(x), midi: coords.midi(y) };
  }

  function onPointerDown(event: ReactPointerEvent<HTMLCanvasElement>) {
    if (event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const p = eventPosition(event);
    const hit = hitNote(props.notes, p.time, p.midi, props.spectrum?.pitchStep ?? 1);
    if (hit !== null) {
      let next = props.selected;
      if (event.ctrlKey) {
        next = props.selected.includes(hit) ? props.selected.filter((x) => x !== hit) : [...props.selected, hit];
        props.onSelect(next);
        return;
      }
      if (event.shiftKey) {
        next = Array.from(new Set([...props.selected, hit])).sort((a, b) => a - b);
        props.onSelect(next);
        return;
      }
      if (!props.selected.includes(hit)) {
        next = [hit];
        props.onSelect(next);
      }
      setDrag({ mode: "move", startTime: p.time, startMidi: p.midi, nowTime: p.time, nowMidi: p.midi, indices: next });
      return;
    }
    setDrag({
      mode: event.ctrlKey ? "region" : event.altKey ? "curve" : "create",
      startTime: p.time,
      startMidi: p.midi,
      nowTime: p.time,
      nowMidi: p.midi,
      indices: [],
    });
  }

  function onPointerMove(event: ReactPointerEvent<HTMLCanvasElement>) {
    if (!drag) return;
    const p = eventPosition(event);
    setDrag({ ...drag, nowTime: p.time, nowMidi: p.midi });
  }

  async function onPointerUp(event: ReactPointerEvent<HTMLCanvasElement>) {
    if (!drag) return;
    const p = eventPosition(event);
    const current = { ...drag, nowTime: p.time, nowMidi: p.midi };
    setDrag(null);
    if (current.mode === "move") {
      const dx = current.nowTime - current.startTime;
      const dy = Math.round(current.nowMidi - current.startMidi);
      if (Math.abs(dx) > 1e-4 || dy !== 0) await props.onMove(current.indices, dx, dy);
      return;
    }
    if (current.mode === "region") {
      const found = props.notes.flatMap((note, i) => noteIntersects(note, current.startTime, current.nowTime, current.startMidi, current.nowMidi) ? [i] : []);
      props.onSelect(found);
      return;
    }
    if (Math.abs(current.nowTime - current.startTime) < 0.035) {
      props.onSelect([]);
      await props.onSeek(current.startTime);
      return;
    }
    const a = Math.min(current.startTime, current.nowTime);
    const b = Math.max(current.startTime, current.nowTime);
    if (current.mode === "curve") {
      const p0 = current.startTime <= current.nowTime ? current.startMidi : current.nowMidi;
      const p3 = current.startTime <= current.nowTime ? current.nowMidi : current.startMidi;
      await props.onAdd(a, b, p0, "curve", p3);
    } else {
      await props.onAdd(a, b, (current.startMidi + current.nowMidi) / 2, "note", current.nowMidi);
    }
  }

  async function onContextMenu(event: ReactMouseEvent<HTMLCanvasElement>) {
    event.preventDefault();
    const p = eventPosition(event);
    const hit = hitNote(props.notes, p.time, p.midi, props.spectrum?.pitchStep ?? 1);
    if (hit === null) return;
    const indices = props.selected.includes(hit) && props.selected.length > 1 ? props.selected : [hit];
    await props.onDelete(indices);
  }

  function onWheel(event: ReactWheelEvent<HTMLCanvasElement>) {
    event.preventDefault();
    const sign = event.deltaY < 0 ? 1 : -1;
    if (event.shiftKey) {
      void props.onView({ pitchBottom: props.view.pitchBottom + sign * 3 });
    } else if (event.altKey) {
      void props.onView({ visibleNotes: props.view.visibleNotes - sign * 4 });
    } else if (event.ctrlKey) {
      void props.onView({ windowSeconds: props.view.windowSeconds * (sign > 0 ? 0.85 : 1.18) });
    } else {
      void props.onView({ start: props.view.start - sign * props.view.windowSeconds * 0.08 });
    }
  }

  return (
    <div className="canvas-wrap" ref={containerRef}>
      <canvas
        ref={canvasRef}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={(e) => void onPointerUp(e)}
        onContextMenu={(e) => void onContextMenu(e)}
        onWheel={onWheel}
      />
    </div>
  );
}
