import type { KickPitchCandidate, KickPitchPayload } from "../api/bridge";
import type { TrackSelectionRange } from "../editor/trackSelection";

export type KickPitchRegion = {
  start: number;
  end: number;
  minHz: number;
  maxHz: number;
};

export const KICK_PITCH_MAX_SECONDS = 10;

function midiToHz(midi: number) {
  return 440 * 2 ** ((midi - 69) / 12);
}

/** Region defaults: the Track selection rectangle if present, else the view start. */
export function defaultKickPitchRegion(
  range: TrackSelectionRange | null,
  viewStart: number,
): KickPitchRegion {
  if (range && range.endTime > range.startTime) {
    return {
      start: range.startTime,
      end: Math.min(range.endTime, range.startTime + KICK_PITCH_MAX_SECONDS),
      minHz: Math.max(10, Math.round(midiToHz(range.minMidi) * 10) / 10),
      maxHz: Math.min(2000, Math.round(midiToHz(range.maxMidi) * 10) / 10),
    };
  }
  const start = Math.max(0, viewStart);
  return { start, end: start + 0.5, minHz: 25, maxHz: 500 };
}

export function validKickPitchRegion(region: KickPitchRegion): string | null {
  const values = [region.start, region.end, region.minHz, region.maxHz];
  if (!values.every(Number.isFinite)) return "数値を入力してください";
  if (region.end - region.start < 0.01) return "解析範囲は10ms以上にしてください";
  if (region.end - region.start > KICK_PITCH_MAX_SECONDS)
    return `解析範囲は${KICK_PITCH_MAX_SECONDS}秒以内にしてください`;
  if (region.minHz <= 0 || region.maxHz <= region.minHz * 1.5)
    return "最高Hzは最低Hzの1.5倍より大きくしてください";
  return null;
}

export function candidateRoleLabel(candidate: KickPitchCandidate) {
  if (candidate.role === "primary") return "主（基本周波数）";
  if (candidate.role === "harmonic")
    return `倍音 ×${candidate.harmonicNumber ?? "?"}`;
  return "独立成分";
}

function firstLast(values: Array<number | null>): [number, number] | null {
  const finite = values.filter((v): v is number => v !== null && Number.isFinite(v));
  return finite.length ? [finite[0], finite[finite.length - 1]] : null;
}

export function candidateSummary(candidate: KickPitchCandidate) {
  const ends = firstLast(candidate.hz);
  const sweep = ends ? `${ends[0].toFixed(1)}→${ends[1].toFixed(1)} Hz` : "—";
  return `${sweep} · ${candidate.duration.toFixed(3)} s · 信頼度 ${Math.round(candidate.meanConfidence * 100)}%`;
}

/** Candidate ids worth pre-selecting: the primary track only. */
export function defaultKickPitchSelection(payload: KickPitchPayload | null): number[] {
  if (!payload?.available || payload.primaryIndex === null || payload.primaryIndex === undefined)
    return [];
  const primary = payload.candidates?.[payload.primaryIndex];
  return primary ? [primary.id] : [];
}

export type KickPitchPolyline = {
  id: number;
  role: KickPitchCandidate["role"];
  points: Array<{ time: number; midi: number; confidence: number }>;
};

/**
 * Split candidates into drawable polylines.  Points below ``minConfidence``
 * break the line instead of being joined, mirroring the backend rule that
 * unreliable estimates are never bridged.
 */
export function kickPitchPolylines(
  payload: KickPitchPayload | null,
  minConfidence = 0.5,
): KickPitchPolyline[] {
  if (!payload?.available) return [];
  const out: KickPitchPolyline[] = [];
  for (const candidate of payload.candidates ?? []) {
    let current: KickPitchPolyline | null = null;
    for (let i = 0; i < candidate.times.length; i += 1) {
      const time = candidate.times[i],
        midi = candidate.midi[i],
        confidence = candidate.confidence[i] ?? 0;
      if (time === null || midi === null || confidence < minConfidence) {
        current = null;
        continue;
      }
      if (!current) {
        current = { id: candidate.id, role: candidate.role, points: [] };
        out.push(current);
      }
      current.points.push({ time, midi, confidence });
    }
  }
  return out;
}
