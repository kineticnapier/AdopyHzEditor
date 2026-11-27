import { useEffect, useRef, useState } from "react";
import { t } from "../i18n/index.ts";
import type { BackendApi, KickPitchFitMode, KickPitchMethod, KickPitchPayload, NoteMutationResult } from "./bridge";
import type { TrackSelectionRange } from "../editor/trackSelection";
import {
  candidateRoleLabel,
  candidateSummary,
  defaultKickPitchRegion,
  defaultKickPitchSelection,
  kickPitchRegionFromPick,
  KICK_PITCH_SHOWN_CANDIDATES,
  orderedKickPitchCandidates,
  validKickPitchRegion,
  type KickPitchPick,
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
  /** True while the next drag on the canvas sets the region. */
  picking: boolean;
  /** The last box dragged on the canvas. */
  pick: KickPitchPick | null;
  onPickingChange(picking: boolean): void;
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
  picking,
  pick,
  onPickingChange,
  onKickPitch,
  onSelectIds,
  onQueuedMutation,
  onStatus,
}: Props) {
  const [region, setRegion] = useState<KickPitchRegion>(() =>
    defaultKickPitchRegion(trackRange, viewStart),
  );
  const [fitMode, setFitMode] = useState<KickPitchFitMode>("line");
  const [maxErrorCents, setMaxErrorCents] = useState(30);
  const [maxNotes, setMaxNotes] = useState(0);
  const [minConfidence, setMinConfidence] = useState(0.5);
  const [method, setMethod] = useState<KickPitchMethod>("harmonic");
  const [running, setRunning] = useState(false);
  const invalid = validKickPitchRegion(region);
  const [showAllCandidates, setShowAllCandidates] = useState(false);
  const candidates = orderedKickPitchCandidates(kickPitch);
  // Fragments past the first few stay folded unless one of them is selected.
  const shownCandidates = showAllCandidates
    ? candidates
    : candidates.filter(
        (candidate, index) => index < KICK_PITCH_SHOWN_CANDIDATES || selectedIds.includes(candidate.id),
      );
  const hiddenCandidates = candidates.length - shownCandidates.length;
  // A new result starts folded again.
  useEffect(() => setShowAllCandidates(false), [kickPitch]);

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

  // A box dragged on the canvas sets the region and analyses it at once.
  const handledPick = useRef(pick?.seq ?? 0);
  useEffect(() => {
    if (!pick || pick.seq === handledPick.current) return;
    handledPick.current = pick.seq;
    const next = kickPitchRegionFromPick(pick.range);
    setRegion(next);
    void analyze(next);
    // analyze reads the latest method and api from this render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pick]);

  // A Track rectangle (Shift+drag) also becomes the region, without analysing.
  useEffect(() => {
    if (trackRange && trackRange.endTime > trackRange.startTime)
      setRegion(defaultKickPitchRegion(trackRange, viewStart));
    // viewStart only matters without a rectangle.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trackRange]);

  // Esc leaves pick mode.
  useEffect(() => {
    if (!picking) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onPickingChange(false);
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [picking, onPickingChange]);

  async function analyze(target: KickPitchRegion = region) {
    if (!api || validKickPitchRegion(target)) {
      const reason = validKickPitchRegion(target);
      if (reason) onStatus(reason);
      return;
    }
    setRunning(true);
    try {
      const payload = await api.analyze_kick_pitch(
        target.start,
        target.end,
        target.minHz,
        target.maxHz,
        1,
        method,
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
      () => api.create_notes_from_kick_pitch(selectedIds, minConfidence, maxErrorCents, fitMode, maxNotes),
      (r) => r.indices,
    );
    if (result?.status) onStatus(result.status);
  }

  return (
    <details className="kick-pitch-section">
      <summary>{t("kick.title")}</summary>
      <p className="inspector-help">
        {t("kick.info")}
      </p>
      <div className="kick-pitch-pick">
        <button
          className={picking ? "primary-soft active" : "primary-soft"}
          aria-pressed={picking}
          disabled={!api || !audioLoaded || busy || running}
          onClick={() => onPickingChange(!picking)}
        >
          {picking ? t("kick.picking") : t("kick.pick")}
        </button>
      </div>
      {picking && (
        <p className="inspector-help">
          {t("kick.pick_info")}
        </p>
      )}
      <div className="kick-pitch-grid">
        {field("start", t("kick.start_s"), 0.001)}
        {field("end", t("kick.end_s"), 0.001)}
        {field("minHz", t("kick.min_hz"), 1)}
        {field("maxHz", t("kick.max_hz"), 1)}
      </div>
      <label className="kick-pitch-field kick-pitch-method">
        <span>{t("kick.method")}</span>
        <select value={method} onChange={(event) => setMethod(event.target.value as KickPitchMethod)}>
          <option value="harmonic">{t("kick.method_harmonic")}</option>
          <option value="cycle">{t("kick.method_cycle")}</option>
          <option value="multiwindow">{t("kick.method_multiwindow")}</option>
        </select>
      </label>
      {method === "multiwindow" && (
        <p className="inspector-help">
          {t("kick.multiwindow_info")}
        </p>
      )}
      {method === "cycle" && (
        <p className="inspector-help">
          {t("kick.cycle_info")}
        </p>
      )}
      <div className="track-actions">
        <button
          className="quiet-button"
          disabled={busy || running}
          onClick={() => setRegion(defaultKickPitchRegion(trackRange, viewStart))}
        >
          {trackRange ? t("kick.from_track") : t("kick.from_view")}
        </button>
        <button
          disabled={!api || !audioLoaded || busy || running || Boolean(invalid)}
          title={invalid ?? undefined}
          onClick={() => void analyze()}
        >
          {running ? t("kick.running") : t("kick.run")}
        </button>
      </div>
      {invalid && <p className="inspector-help">{invalid}</p>}
      {kickPitch?.available && (
        <>
          <ul className="kick-pitch-candidates" aria-label={t("kick.candidates")}>
            {shownCandidates.map((candidate) => (
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
            {!candidates.length && <li>{t("kick.no_candidates")}</li>}
          </ul>
          {(hiddenCandidates > 0 || showAllCandidates) && (
            <button className="quiet-button" onClick={() => setShowAllCandidates(!showAllCandidates)}>
              {showAllCandidates ? t("kick.hide_short") : t("kick.show_short", { count: hiddenCandidates })}
            </button>
          )}
          <label className="kick-pitch-field kick-pitch-method">
            <span>{t("kick.build")}</span>
            <select
              value={fitMode}
              onChange={(event) => {
                const next = event.target.value as KickPitchFitMode;
                setFitMode(next);
                setMaxErrorCents(next === "line" ? 30 : 5);
              }}
            >
              <option value="line">{t("kick.build_line")}</option>
              <option value="exact">{t("kick.build_exact")}</option>
            </select>
          </label>
          <p className="inspector-help">
            {fitMode === "line"
              ? t("kick.build_line_info")
              : t("kick.build_exact_info")}
          </p>
          <div className="kick-pitch-grid">
            <label className="kick-pitch-field">
              <span>{t("kick.tolerance")}</span>
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
              <span>{t("kick.min_confidence")}</span>
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={minConfidence}
                onChange={(event) => setMinConfidence(Number(event.target.value))}
              />
            </label>
            {fitMode === "line" && (
              <label className="kick-pitch-field">
                <span>{t("kick.max_notes")}</span>
                <input
                  type="number"
                  min={0}
                  max={256}
                  step={1}
                  value={maxNotes}
                  onChange={(event) => setMaxNotes(Math.max(0, Math.round(Number(event.target.value) || 0)))}
                />
              </label>
            )}
          </div>
          <div className="track-actions">
            <button
              disabled={busy || !selectedIds.length}
              onClick={() => void convert()}
            >
              {t("kick.make_curve")}
            </button>
            <button
              className="quiet-button"
              disabled={busy}
              onClick={() => {
                onKickPitch(null, []);
                void api?.clear_kick_pitch();
              }}
            >
              {t("kick.clear")}
            </button>
          </div>
        </>
      )}
    </details>
  );
}
