import { useState } from "react";
import type { BackendApi, KickPitchPayload, NoteMutationResult } from "./bridge";
import type { TrackSelectionRange } from "../editor/trackSelection";
import {
  candidateRoleLabel,
  candidateSummary,
  defaultKickPitchRegion,
  defaultKickPitchSelection,
  validKickPitchRegion,
  type KickPitchRegion,
} from "./kickPitchModel";

type Props = {
  api: BackendApi | null;
  busy: boolean;
  audioLoaded: boolean;
  trackRange: TrackSelectionRange | null;
  viewStart: number;
  kickPitch: KickPitchPayload | null;
  selectedIds: number[];
  onKickPitch(payload: KickPitchPayload | null, selectedIds: number[]): void;
  onSelectIds(ids: number[]): void;
  onQueuedMutation(
    call: () => Promise<NoteMutationResult>,
    selection?: (result: NoteMutationResult) => number[] | undefined,
  ): Promise<NoteMutationResult | undefined>;
  onStatus(text: string): void;
};

/** Prototype: track a kick's pitch in a short region and turn it into Curve Notes. */
export default function KickPitchSection({
  api,
  busy,
  audioLoaded,
  trackRange,
  viewStart,
  kickPitch,
  selectedIds,
  onKickPitch,
  onSelectIds,
  onQueuedMutation,
  onStatus,
}: Props) {
  const [region, setRegion] = useState<KickPitchRegion>(() =>
    defaultKickPitchRegion(trackRange, viewStart),
  );
  const [maxErrorCents, setMaxErrorCents] = useState(5);
  const [minConfidence, setMinConfidence] = useState(0.5);
  const [running, setRunning] = useState(false);
  const invalid = validKickPitchRegion(region);
  const candidates = kickPitch?.available ? (kickPitch.candidates ?? []) : [];

  const field = (key: keyof KickPitchRegion, label: string, step: number) => (
    <label className="kick-pitch-field">
      <span>{label}</span>
      <input
        type="number"
        step={step}
        value={region[key]}
        onChange={(event) =>
          setRegion({ ...region, [key]: Number(event.target.value) })
        }
      />
    </label>
  );

  async function analyze() {
    if (!api || invalid) return;
    setRunning(true);
    try {
      const payload = await api.analyze_kick_pitch(
        region.start,
        region.end,
        region.minHz,
        region.maxHz,
      );
      onKickPitch(payload.available ? payload : null, defaultKickPitchSelection(payload));
      if (payload.status) onStatus(payload.status);
    } catch (error) {
      onStatus(String(error));
    } finally {
      setRunning(false);
    }
  }

  async function convert() {
    if (!api || !selectedIds.length) return;
    const result = await onQueuedMutation(
      () => api.create_notes_from_kick_pitch(selectedIds, minConfidence, maxErrorCents),
      (r) => r.indices,
    );
    if (result?.status) onStatus(result.status);
  }

  return (
    <details className="kick-pitch-section">
      <summary>キック音高解析（試作）</summary>
      <p className="inspector-help">
        短い区間の基本周波数を追跡します。倍音（Piepの高い成分）は基本周波数へまとめ、
        独立した成分は別候補として表示します。
      </p>
      <div className="kick-pitch-grid">
        {field("start", "開始 s", 0.001)}
        {field("end", "終了 s", 0.001)}
        {field("minHz", "最低 Hz", 1)}
        {field("maxHz", "最高 Hz", 1)}
      </div>
      <div className="track-actions">
        <button
          className="quiet-button"
          disabled={busy || running}
          onClick={() => setRegion(defaultKickPitchRegion(trackRange, viewStart))}
        >
          {trackRange ? "Track矩形から" : "表示位置から"}
        </button>
        <button
          className="primary-soft"
          disabled={!api || !audioLoaded || busy || running || Boolean(invalid)}
          title={invalid ?? undefined}
          onClick={() => void analyze()}
        >
          {running ? "解析中…" : "解析"}
        </button>
      </div>
      {invalid && <p className="inspector-help">{invalid}</p>}
      {kickPitch?.available && (
        <>
          <ul className="kick-pitch-candidates" aria-label="キック音高の候補">
            {candidates.map((candidate) => (
              <li key={candidate.id}>
                <label className="inline-check">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(candidate.id)}
                    onChange={(event) =>
                      onSelectIds(
                        event.target.checked
                          ? [...selectedIds, candidate.id]
                          : selectedIds.filter((id) => id !== candidate.id),
                      )
                    }
                  />
                  <span>
                    <b>
                      #{candidate.id} {candidateRoleLabel(candidate)}
                    </b>
                    <small>{candidateSummary(candidate)}</small>
                  </span>
                </label>
              </li>
            ))}
            {!candidates.length && <li>信頼できる音高が見つかりませんでした</li>}
          </ul>
          <div className="kick-pitch-grid">
            <label className="kick-pitch-field">
              <span>許容誤差 cent</span>
              <input
                type="number"
                min={0.5}
                max={100}
                step={0.5}
                value={maxErrorCents}
                onChange={(event) => setMaxErrorCents(Number(event.target.value))}
              />
            </label>
            <label className="kick-pitch-field">
              <span>最低信頼度</span>
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={minConfidence}
                onChange={(event) => setMinConfidence(Number(event.target.value))}
              />
            </label>
          </div>
          <div className="track-actions">
            <button
              disabled={busy || !selectedIds.length}
              onClick={() => void convert()}
            >
              Curve Noteを作成
            </button>
            <button
              className="quiet-button"
              disabled={busy}
              onClick={() => {
                onKickPitch(null, []);
                void api?.clear_kick_pitch();
              }}
            >
              結果を消去
            </button>
          </div>
        </>
      )}
    </details>
  );
}
