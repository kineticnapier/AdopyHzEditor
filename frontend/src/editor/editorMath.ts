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
  const sh = Math.max(0, Math.min(rows - sy, (viewTop - viewBottom) / (top - bottom) * rows));
  return { sy, sh };
}


/** Map only the visible pitch overlap to matching source and canvas rectangles.
 * Using the full viewport for source cropping stretches the spectrogram when
 * the pitch view extends above or below the available spectrum bins. */
export function spectrogramPitchVisibleCrop(
  rows: number, midiMin: number, pitchStep: number,
  viewBottom: number, viewTop: number, destinationHeight: number,
) {
  if (![rows, midiMin, pitchStep, viewBottom, viewTop, destinationHeight].every(Number.isFinite) ||
      !Number.isSafeInteger(rows) || rows <= 0 || pitchStep <= 0 ||
      viewTop <= viewBottom || destinationHeight <= 0) return null;
  const sourceBottom = midiMin - pitchStep / 2;
  const sourceTop = midiMin + (rows - .5) * pitchStep;
  const sourceSpan = sourceTop - sourceBottom;
  const viewSpan = viewTop - viewBottom;
  if (![sourceBottom, sourceTop, sourceSpan, viewSpan].every(Number.isFinite) ||
      sourceSpan <= 0 || viewSpan <= 0) return null;
  const visibleBottom = Math.max(viewBottom, sourceBottom);
  const visibleTop = Math.min(viewTop, sourceTop);
  if (visibleTop <= visibleBottom) return null;
  const { sy, sh } = spectrogramPitchCrop(rows, midiMin, pitchStep, visibleBottom, visibleTop);
  const crop = {
    sy, sh,
    dy: (viewTop - visibleTop) / viewSpan * destinationHeight,
    dh: (visibleTop - visibleBottom) / viewSpan * destinationHeight,
  };
  return Object.values(crop).every(Number.isFinite) && crop.sh > 0 && crop.dh > 0 ? crop : null;
}

export function spectrogramTimeCrop(
  sourceStart: number,
  sourceEnd: number,
  viewStart: number,
  viewWindowSeconds: number,
  sourceCols: number,
  destinationWidth: number,
) {
  // Invalid metadata must not reach CanvasRenderingContext2D.drawImage.
  if (![sourceStart, sourceEnd, viewStart, viewWindowSeconds, sourceCols, destinationWidth].every(Number.isFinite) ||
      !Number.isSafeInteger(sourceCols)) return null;
  const sourceSpan = sourceEnd - sourceStart;
  const viewSpan = viewWindowSeconds;
  if (!Number.isFinite(sourceSpan) || sourceSpan <= 1e-12 || viewSpan <= 1e-12 ||
      sourceCols <= 0 || destinationWidth <= 0) return null;

  const viewEnd = viewStart + viewSpan;
  if (!Number.isFinite(viewEnd)) return null;
  const overlapStart = Math.max(sourceStart, viewStart);
  const overlapEnd = Math.min(sourceEnd, viewEnd);
  if (overlapEnd <= overlapStart) return null;

  const overlap = overlapEnd - overlapStart;
  const crop = {
    sx: (overlapStart - sourceStart) / sourceSpan * sourceCols,
    sw: overlap / sourceSpan * sourceCols,
    dx: (overlapStart - viewStart) / viewSpan * destinationWidth,
    dw: overlap / viewSpan * destinationWidth,
  };
  return Object.values(crop).every(Number.isFinite) && crop.sw > 0 && crop.dw > 0 ? crop : null;
}



/** Clip packed Direct Spectrum cells to both the time and pitch viewport.
 * Untrusted metadata and overflow must not reach canvas drawImage. */
export function directSpectrumVisibleCrop(
  sourceStart: number, sourceEnd: number, sourceBottom: number, sourceTop: number,
  viewStart: number, viewWindowSeconds: number, viewBottom: number, viewHeight: number,
  sourceWidth: number, sourceHeight: number, destinationWidth: number, destinationHeight: number,
) {
  const values = [sourceStart, sourceEnd, sourceBottom, sourceTop, viewStart, viewWindowSeconds,
    viewBottom, viewHeight, sourceWidth, sourceHeight, destinationWidth, destinationHeight];
  if (!values.every(Number.isFinite) || !Number.isSafeInteger(sourceWidth) ||
      !Number.isSafeInteger(sourceHeight) || sourceWidth <= 0 || sourceHeight <= 0 ||
      destinationWidth <= 0 || destinationHeight <= 0 || viewWindowSeconds <= 0 || viewHeight <= 0) return null;
  const sourceTimeSpan = sourceEnd - sourceStart, sourcePitchSpan = sourceTop - sourceBottom;
  const viewEnd = viewStart + viewWindowSeconds, viewTop = viewBottom + viewHeight;
  if (![sourceTimeSpan, sourcePitchSpan, viewEnd, viewTop].every(Number.isFinite) ||
      sourceTimeSpan <= 0 || sourcePitchSpan <= 0) return null;
  const timeStart = Math.max(viewStart, sourceStart), timeEnd = Math.min(viewEnd, sourceEnd);
  const pitchBottom = Math.max(viewBottom, sourceBottom), pitchTop = Math.min(viewTop, sourceTop);
  if (timeEnd <= timeStart || pitchTop <= pitchBottom) return null;
  const crop = {
    sx: (timeStart - sourceStart) / sourceTimeSpan * sourceWidth,
    sy: (sourceTop - pitchTop) / sourcePitchSpan * sourceHeight,
    sw: (timeEnd - timeStart) / sourceTimeSpan * sourceWidth,
    sh: (pitchTop - pitchBottom) / sourcePitchSpan * sourceHeight,
    dx: (timeStart - viewStart) / viewWindowSeconds * destinationWidth,
    dy: (viewTop - pitchTop) / viewHeight * destinationHeight,
    dw: (timeEnd - timeStart) / viewWindowSeconds * destinationWidth,
    dh: (pitchTop - pitchBottom) / viewHeight * destinationHeight,
  };
  return Object.values(crop).every(Number.isFinite) &&
    crop.sw > 0 && crop.sh > 0 && crop.dw > 0 && crop.dh > 0 ? crop : null;
}

/** Reject invalid packed Frequency Track samples before hover indexing or Canvas drawing. */
export function isValidTrackSample(time: number, midi: number, magnitude: number, duration: number): boolean {
  return [time, midi, magnitude, duration].every(Number.isFinite) &&
    magnitude >= 0 && magnitude <= 1 && duration >= 0;
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

export function notesInTimeRange(index:NoteTimeIndex,start:number,end:number){
  const right=upperBound(index.starts,end),left=lowerBound(index.maxEnds,start);
  return index.order.slice(left,right);
}

export type ScreenSegment = { ax: number; ay: number; bx: number; by: number };
export type SegmentSpatialIndex = {
  cellSize: number;
  buckets: Map<string, number[]>;
};

export function buildSegmentSpatialIndex(
  segments: ScreenSegment[],
  cellSize = 24,
  padding = 8,
  viewport?: { width: number; height: number },
): SegmentSpatialIndex {
  const size = Math.max(1, cellSize), buckets = new Map<string, number[]>();
  // Index only cells reachable by the pointer. A segment can extend far beyond
  // the visible canvas after zooming, so indexing its full bounds can hang.
  if (viewport && (!Number.isFinite(viewport.width) || !Number.isFinite(viewport.height) ||
      viewport.width <= 0 || viewport.height <= 0)) return { cellSize: size, buckets };
  const minX = viewport ? Math.floor(-padding / size) : -Infinity;
  const maxX = viewport ? Math.floor((viewport.width + padding) / size) : Infinity;
  const minY = viewport ? Math.floor(-padding / size) : -Infinity;
  const maxY = viewport ? Math.floor((viewport.height + padding) / size) : Infinity;
  // A diagonal crossing the viewport must not occupy its entire bounding box.
  // Walk the clipped line instead; neighboring cells retain the 8px hit margin.
  if (viewport) {
    const radius = Math.ceil((Math.max(0, padding) + size / 4) / size);
    segments.forEach((segment, index) => {
      if (![segment.ax, segment.ay, segment.bx, segment.by].every(Number.isFinite)) return;
      const dx = segment.bx - segment.ax, dy = segment.by - segment.ay;
      if (!Number.isFinite(dx) || !Number.isFinite(dy)) return;
      // Liang-Barsky clipping to the visible rectangle, including hit padding.
      let from = 0, to = 1;
      for (const [p, q] of [
        [-dx, segment.ax + padding], [dx, viewport.width + padding - segment.ax],
        [-dy, segment.ay + padding], [dy, viewport.height + padding - segment.ay],
      ]) {
        if (p === 0) { if (q < 0) return; continue; }
        const t = q / p;
        if (p < 0) from = Math.max(from, t); else to = Math.min(to, t);
        if (from > to) return;
      }
      const startX = segment.ax + dx * from, startY = segment.ay + dy * from;
      const endX = segment.ax + dx * to, endY = segment.ay + dy * to;
      const steps = Math.max(1, Math.ceil(Math.max(Math.abs(endX - startX), Math.abs(endY - startY)) / (size / 2)));
      const visited = new Set<string>();
      for (let step = 0; step <= steps; step += 1) {
        const t = step / steps;
        const cx = Math.floor((startX + (endX - startX) * t) / size);
        const cy = Math.floor((startY + (endY - startY) * t) / size);
        for (let x = Math.max(minX, cx - radius); x <= Math.min(maxX, cx + radius); x += 1) {
          for (let y = Math.max(minY, cy - radius); y <= Math.min(maxY, cy + radius); y += 1) {
            const key = `${x}:${y}`;
            if (visited.has(key)) continue;
            visited.add(key);
            const bucket = buckets.get(key);
            if (bucket) bucket.push(index); else buckets.set(key, [index]);
          }
        }
      }
    });
    return { cellSize: size, buckets };
  }
  segments.forEach((segment, index) => {
    if (![segment.ax, segment.ay, segment.bx, segment.by].every(Number.isFinite)) return;
    const left = Math.max(minX, Math.floor((Math.min(segment.ax, segment.bx) - padding) / size));
    const right = Math.min(maxX, Math.floor((Math.max(segment.ax, segment.bx) + padding) / size));
    const top = Math.max(minY, Math.floor((Math.min(segment.ay, segment.by) - padding) / size));
    const bottom = Math.min(maxY, Math.floor((Math.max(segment.ay, segment.by) + padding) / size));
    if (left > right || top > bottom) return;
    for (let x = left; x <= right; x += 1) for (let y = top; y <= bottom; y += 1) {
      const key = `${x}:${y}`, bucket = buckets.get(key);
      if (bucket) bucket.push(index); else buckets.set(key, [index]);
    }
  });
  return { cellSize: size, buckets };
}

export function nearbySegmentIndices(index: SegmentSpatialIndex, x: number, y: number) {
  return index.buckets.get(`${Math.floor(x / index.cellSize)}:${Math.floor(y / index.cellSize)}`) ?? [];
}

export function adjacentNoteIndex(order: number[], current: number | null, direction: -1 | 1) {
  if (!order.length) return null;
  if (current === null) return direction > 0 ? order[0] : order[order.length - 1];
  const position = order.indexOf(current);
  if (position < 0) return direction > 0 ? order[0] : order[order.length - 1];
  return order[Math.max(0, Math.min(order.length - 1, position + direction))];
}

/** Cap timeline second ticks so long recordings cannot stall Canvas redraws.
 * Use an index-based loop: adding a tiny step to a huge timestamp can stop advancing. */
export function boundedTimelineTickRange(
  start: number, windowSeconds: number, step: number, maxLines = 600,
) {
  const empty = { first: 0, stride: 1, count: 0 };
  const cap = Math.floor(maxLines);
  if (![start, windowSeconds, step, maxLines].every(Number.isFinite) ||
      windowSeconds <= 0 || step <= 0 || cap <= 0) return empty;
  const end = start + windowSeconds;
  if (!Number.isFinite(end)) return empty;
  const from = Math.floor(start / step), to = Math.ceil(end / step);
  if (!Number.isSafeInteger(from) || !Number.isSafeInteger(to) || to < from) return empty;
  const total = to - from + 1;
  if (!Number.isSafeInteger(total) || total <= 0) return empty;
  // Keep tick spacing stable while panning: rounded viewport endpoints can
  // change the apparent tick count by one even when zoom is unchanged.
  const stride = Math.max(1, Math.ceil((Math.ceil(windowSeconds / step) + 2) / cap));
  if (!Number.isSafeInteger(stride)) return empty;
  // Keep the grid aligned to the same absolute ticks while panning.
  const first = Math.floor(from / stride) * stride;
  if (!Number.isSafeInteger(first)) return empty;
  const count = Math.min(cap, Math.floor((to - first) / stride) + 1);
  return { first, stride, count };
}

/** Bound beat-grid work even for invalid or unrepresentable view/BPM values.
 * The caller must iterate by count, not by repeatedly adding stride to a large tick. */
export function boundedGridRange(start: number, windowSeconds: number, beat: number, offset: number, maxLines = 2000) {
  const empty = { first: 0, last: -1, stride: 1, count: 0 };
  const cap = Math.floor(maxLines);
  if (![start, windowSeconds, beat, offset, maxLines].every(Number.isFinite) ||
      windowSeconds <= 0 || beat <= 0 || cap <= 0) return empty;
  const end = start + windowSeconds;
  const from = (start - offset) / beat, to = (end - offset) / beat;
  if (![end, from, to].every(Number.isFinite)) return empty;
  const first = Math.floor(from), last = Math.ceil(to);
  if (!Number.isSafeInteger(first) || !Number.isSafeInteger(last) || last < first) return empty;
  const total = last - first + 1;
  if (!Number.isSafeInteger(total) || total <= 0) return empty;
  // Derive the stride from zoom, not rounded viewport endpoints. Otherwise
  // scrolling near a decimation boundary changes every displayed beat line.
  const stride = Math.max(1, Math.ceil((Math.ceil(windowSeconds / beat) + 2) / cap));
  if (!Number.isSafeInteger(stride)) return empty;
  // Align decimated beats to the global grid, not the current viewport edge.
  // Otherwise panning by one beat flips every other visible line at stride=2.
  const alignedFirst = Math.ceil(first / stride) * stride;
  if (!Number.isSafeInteger(alignedFirst) || alignedFirst > last) return empty;
  const count = Math.min(cap, Math.floor((last - alignedFirst) / stride) + 1);
  return { first: alignedFirst, last, stride, count };
}

/** Right-click acts on the note under the pointer; Delete acts on the selection. */
export function contextMenuDeleteIndices(hit: number | null): number[] {
  return hit === null ? [] : [hit];
}


/** Coarse viewport rejection for drag ghosts. Bezier curves stay within the
 * convex hull of their pitch controls (also for Hz interpolation), so using
 * their control pitches is conservative and avoids sampling every curve.
 * Callers provide a pixel-derived margin to retain strokes at the edges.
 */
export function noteGhostIntersectsViewport(
  note: NoteDto,
  timeStart: number, timeEnd: number, midiBottom: number, midiTop: number,
): boolean {
  if (note.end < timeStart || note.start > timeEnd) return false;
  if ((note.kind ?? "note") !== "curve")
    return note.midi + .43 >= midiBottom && note.midi - .43 <= midiTop;
  const end = note.midi_end ?? note.midi;
  const low = Math.min(note.midi, end, note.ctrl1_midi ?? note.midi, note.ctrl2_midi ?? end);
  const high = Math.max(note.midi, end, note.ctrl1_midi ?? note.midi, note.ctrl2_midi ?? end);
  return high >= midiBottom && low <= midiTop;
}

/** Conservatively reject Frequency Track points and segments that cannot
 * reach the visible canvas. Bounding-box overlap retains lines crossing the
 * viewport even when both endpoints are outside it. */
export function trackPrimitiveIntersectsViewport(
  ax: number, ay: number, bx: number, by: number,
  width: number, height: number, margin = 8,
): boolean {
  if (!Number.isFinite(ax) || !Number.isFinite(ay) ||
      !Number.isFinite(bx) || !Number.isFinite(by) ||
      !Number.isFinite(width) || !Number.isFinite(height) ||
      !Number.isFinite(margin) || width <= 0 || height <= 0 || margin < 0) return false;
  return Math.max(ax, bx) >= -margin && Math.min(ax, bx) <= width + margin &&
    Math.max(ay, by) >= -margin && Math.min(ay, by) <= height + margin;
}

/** Bound the ghost preview for a multi-note drag without spreading the full
 * selection into Math.min/Math.max. Large imported charts may have >100k notes,
 * exceeding the JavaScript engine's argument limit.
 */
export function clampDraggedNoteOffset(
  notes: readonly NoteDto[],
  indices: readonly number[],
  dx: number,
  dy: number,
  duration: number,
): { dx: number; dy: number } {
  let minStart = Infinity;
  let maxEnd = -Infinity;
  let minPitch = Infinity;
  let maxPitch = -Infinity;
  for (const index of indices) {
    const note = notes[index];
    if (!note) continue;
    minStart = Math.min(minStart, note.start);
    maxEnd = Math.max(maxEnd, note.end);
    minPitch = Math.min(minPitch, note.midi, note.midi_end ?? note.midi,
      note.ctrl1_midi ?? note.midi, note.ctrl2_midi ?? note.midi);
    maxPitch = Math.max(maxPitch, note.midi, note.midi_end ?? note.midi,
      note.ctrl1_midi ?? note.midi, note.ctrl2_midi ?? note.midi);
  }
  if (minStart === Infinity) return { dx, dy };
  return {
    dx: Math.max(-minStart, Math.min(Math.max(0, duration - maxEnd), dx)),
    dy: Math.max(-minPitch, Math.min(127 - maxPitch, dy)),
  };
}
