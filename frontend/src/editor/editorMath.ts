import type { NoteDto } from "./bridge";

function midiToHz(midi: number) { return 440 * 2 ** ((midi - 69) / 12); }
function hzToMidi(hz: number) { return 69 + 12 * Math.log2(Math.max(1e-9, hz) / 440); }
function cubic(p0: number, p1: number, p2: number, p3: number, u: number) { const v = 1 - u; return v ** 3 * p0 + 3 * v ** 2 * u * p1 + 3 * v * u ** 2 * p2 + u ** 3 * p3; }
function interpolationMode(note: NoteDto) { return (note.interpolation ?? "bezier_pitch").toLowerCase().replace(/[ -]/g, "_"); }

export function noteEdgeAt(startPx: number, endPx: number, pointerPx: number, thresholdPx = 8): "start" | "end" | null {
  const threshold = Math.max(0, thresholdPx);
  if (Math.abs(endPx - startPx) <= threshold * 2) return null;
  const startDistance = Math.abs(pointerPx - startPx), endDistance = Math.abs(pointerPx - endPx);
  if (Math.min(startDistance, endDistance) > threshold) return null;
  return startDistance <= endDistance ? "start" : "end";
}

export function noteMidiAt(note: NoteDto, u: number) {
  if ((note.kind ?? "note") !== "curve") return note.midi;
  const p0 = note.midi, p3 = note.midi_end ?? p0, p1 = note.ctrl1_midi ?? p0, p2 = note.ctrl2_midi ?? p3, t = Math.max(0, Math.min(1, u));
  const mode = interpolationMode(note);
  if (mode === "linear_pitch" || mode === "linear_midi" || mode === "pitch_linear") return p0 + (p3 - p0) * t;
  if (mode === "linear_hz" || mode === "hz_linear") return hzToMidi(midiToHz(p0) + (midiToHz(p3) - midiToHz(p0)) * t);
  if (mode === "bezier_hz" || mode === "hz_bezier") return hzToMidi(cubic(midiToHz(p0), midiToHz(p1), midiToHz(p2), midiToHz(p3), t));
  return cubic(p0, p1, p2, p3, t);
}

function cubicExtrema(p0: number, p1: number, p2: number, p3: number, low: number, high: number) {
  const values = [cubic(p0, p1, p2, p3, low), cubic(p0, p1, p2, p3, high)];
  const a = -p0 + 3 * p1 - 3 * p2 + p3, b = 3 * p0 - 6 * p1 + 3 * p2, c = -3 * p0 + 3 * p1;
  const candidates: number[] = [];
  if (Math.abs(a) < 1e-12) {
    if (Math.abs(b) >= 1e-12) candidates.push(-c / (2 * b));
  } else {
    const discriminant = 4 * b * b - 12 * a * c;
    if (discriminant >= 0) {
      const root = Math.sqrt(discriminant);
      candidates.push((-2 * b + root) / (6 * a), (-2 * b - root) / (6 * a));
    }
  }
  for (const u of candidates) if (u > low && u < high) values.push(cubic(p0, p1, p2, p3, u));
  return [Math.min(...values), Math.max(...values)] as const;
}

export function noteIntersects(note: NoteDto, x1: number, x2: number, y1: number, y2: number) {
  const xmin = Math.min(x1, x2), xmax = Math.max(x1, x2), ymin = Math.min(y1, y2), ymax = Math.max(y1, y2);
  if (note.end < xmin || note.start > xmax) return false;
  if ((note.kind ?? "note") !== "curve") return note.midi + .55 >= ymin && note.midi - .55 <= ymax;
  const duration = note.end - note.start;
  if (duration <= 0) return note.midi + .55 >= ymin && note.midi - .55 <= ymax;
  const u0 = Math.max(0, Math.min(1, (xmin - note.start) / duration)), u1 = Math.max(0, Math.min(1, (xmax - note.start) / duration));
  const mode = interpolationMode(note);
  let range: readonly [number, number];
  if (["linear_pitch", "linear_midi", "pitch_linear", "linear_hz", "hz_linear"].includes(mode)) {
    const values = [noteMidiAt(note, u0), noteMidiAt(note, u1)]; range = [Math.min(...values), Math.max(...values)];
  } else {
    const p0 = note.midi, p3 = note.midi_end ?? p0, p1 = note.ctrl1_midi ?? p0, p2 = note.ctrl2_midi ?? p3;
    if (mode === "bezier_hz" || mode === "hz_bezier") {
      const hz = cubicExtrema(midiToHz(p0), midiToHz(p1), midiToHz(p2), midiToHz(p3), u0, u1); range = [hzToMidi(hz[0]), hzToMidi(hz[1])];
    } else range = cubicExtrema(p0, p1, p2, p3, u0, u1);
  }
  return range[1] + .55 >= ymin && range[0] - .55 <= ymax;
}

export function spectrogramPitchCrop(rows: number, midiMin: number, pitchStep: number, viewBottom: number, viewTop: number) {
  const step = Math.max(1e-9, pitchStep), bottom = midiMin - step / 2, top = midiMin + (rows - .5) * step;
  const sy = Math.max(0, (top - viewTop) / (top - bottom) * rows);
  const sh = Math.max(1, Math.min(rows - sy, (viewTop - viewBottom) / (top - bottom) * rows));
  return { sy, sh };
}

export type NoteTimeIndex = { order: number[]; starts: number[]; maxEnds: number[] };

export function buildNoteTimeIndex(notes: NoteDto[]): NoteTimeIndex {
  const order = notes.map((_, index) => index).sort((a, b) => notes[a].start - notes[b].start || a - b);
  const starts = order.map(index => notes[index].start), maxEnds: number[] = [];
  let maxEnd = -Infinity;
  for (const index of order) { maxEnd = Math.max(maxEnd, notes[index].end); maxEnds.push(maxEnd); }
  return { order, starts, maxEnds };
}

function upperBound(values: number[], value: number) {
  let low = 0, high = values.length;
  while (low < high) { const mid = (low + high) >>> 1; if (values[mid] <= value) low = mid + 1; else high = mid; }
  return low;
}

function lowerBound(values: number[], value: number) {
  let low = 0, high = values.length;
  while (low < high) { const mid = (low + high) >>> 1; if (values[mid] < value) low = mid + 1; else high = mid; }
  return low;
}

export function noteCandidatesAt(index: NoteTimeIndex, time: number) {
  const right = upperBound(index.starts, time), left = lowerBound(index.maxEnds, time);
  return index.order.slice(left, right);
}

export function boundedGridRange(start: number, windowSeconds: number, beat: number, offset: number, maxLines = 2000) {
  const first = Math.floor((start - offset) / beat), last = Math.ceil((start + windowSeconds - offset) / beat);
  const total = Math.max(0, last - first + 1), stride = Math.max(1, Math.ceil(total / Math.max(1, maxLines)));
  return { first, last, stride, count: total ? Math.floor((last - first) / stride) + 1 : 0 };
}
