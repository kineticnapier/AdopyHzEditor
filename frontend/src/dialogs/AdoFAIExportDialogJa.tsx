import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { beatSyncedOutputBpm } from "./beatSync";
import type {
  AdoFAIDebugPreview,
  AdoFAIExportOptions,
  AdoFAIKpsReport,
  AdoFAITilePreview,
  BackendApi,
} from "./bridge";
import { LatestRequestGate } from "../api/requestCoordinator";
import { useDialogAccessibility } from "./useDialogAccessibility";
import { isDialogCompositionKey, isPlainDialogEscape } from "./dialogFocus";
import { commitNumericEdit } from "../settings/numericInputModel";
import { createExclusiveAsyncAction } from "./exclusiveAsyncAction";
import { exportDefaultsContextIsCurrent } from "./previewFreshness";
import { exportFailureMessage, exportStatusMessage, kpsRangeLines } from "./exportResult";
import { exportScopeOffset } from "./exportScopeOffset";
import { t } from "../i18n/index.ts";
import { isXModeAvailable, xModeForCompression } from "./angleCompressionXMode";

type ExportContext = { api: BackendApi; selected: number[]; defaultSelectedOnly: boolean; loadAttempt: number; documentGeneration: number };

const xModeOptions = (): Array<[AdoFAIExportOptions["xMode"], string]> => [
  ["floor", t("export.x_floor")],
  ["lowest_floor", t("export.x_lowest_floor")],
  ["round", t("export.x_round")],
  ["ceil", t("export.x_ceil")],
  ["fixed", t("export.fixed")],
  ["target_bpm", t("export.target_bpm")],
];

type Props = {
  api: BackendApi;
  selected: number[];
  documentGeneration: number;
  defaultSelectedOnly?: boolean;
  onClose(): void;
  onStatus(text: string): void;
  onHelp(section?: string): void;
};
function formatBpm(bpm: number): string {
  return Number.isFinite(bpm) ? `${Math.round(bpm * 1000) / 1000}` : "-";
}
function formatCycleSeconds(cycleAngle: number, bpm: number): string {
  if (!(cycleAngle > 0) || !(bpm > 0)) return "-";
  const seconds = (cycleAngle * 60) / (180 * bpm);
  return t("export.seconds", { value: seconds.toFixed(4) });
}
export default function AdoFAIExportDialogJa({
  api,
  selected,
  documentGeneration,
  defaultSelectedOnly = false,
  onClose,
  onStatus,
  onHelp,
}: Props) {
  const [options, setOptions] = useState<AdoFAIExportOptions | null>(null),
    [loadedContext, setLoadedContext] = useState<{ api: BackendApi; selected: number[]; defaultSelectedOnly: boolean; loadAttempt: number; documentGeneration: number } | null>(null),
    [working, setWorking] = useState(false),
    [error, setError] = useState<{ message: string; context: ExportContext } | null>(null),
    [tile, setTile] = useState<AdoFAITilePreview | null>(null),
    [debug, setDebug] = useState<AdoFAIDebugPreview | null>(null),
    [previewMode, setPreviewMode] = useState<"none" | "tile" | "debug">("none"),
    // Set after an export that has stretches too fast to hit by hand.
    [kpsNotice, setKpsNotice] = useState<{ status: string; report: AdoFAIKpsReport } | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const previewRequests = useRef(new LatestRequestGate());
  const actionOnce = useRef(createExclusiveAsyncAction());
  const workingRef = useRef(false);
  // Async actions must check the latest document/selection, not their old render.
  const requestContext = { api, selected, defaultSelectedOnly, loadAttempt, documentGeneration };
  const latestRequestContext = useRef(requestContext);
  latestRequestContext.current = requestContext;
  // Compare during render: effects run after a new selection has already rendered.
  const defaultsCurrent = exportDefaultsContextIsCurrent(loadedContext, requestContext);
  // A failure from a previous selection/document must not appear in the new form.
  const currentError = exportDefaultsContextIsCurrent(error?.context ?? null, requestContext)
    ? error!.message : "";
  function isCurrentAction(context: typeof loadedContext) {
    return exportDefaultsContextIsCurrent(context, latestRequestContext.current);
  }
  useEffect(() => {
    previewRequests.current.invalidate();
    setTile(null);
    setDebug(null);
    setPreviewMode("none");
    setError(null);
    // A changed selection invalidates the previous export options. Do not let
    // the user export with stale defaults while the new request is pending.
    setOptions(null);
    setLoadedContext(null);
    let alive = true;
    void api
      .get_adofai_export_defaults(selected, defaultSelectedOnly)
      .then((v) => {
        if (alive) {
          setLoadedContext({ api, selected, defaultSelectedOnly, loadAttempt, documentGeneration });
          setOptions({ ...v, trackVisual: "normal", selectedOnly:defaultSelectedOnly&&selected.length>0, harmonyTuning: "equal temperament" });
        }
      })
      .catch((e) => {
        if (alive) setError({ message: String(e), context: { api, selected, defaultSelectedOnly, loadAttempt, documentGeneration } });
      });
    return () => {
      alive = false;
    };
  }, [api, selected, defaultSelectedOnly, loadAttempt, documentGeneration]);
  function invalidatePreview() {
    previewRequests.current.invalidate();
    setTile(null);
    setDebug(null);
    setPreviewMode("none");
  }
  function patch<K extends keyof AdoFAIExportOptions>(
    k: K,
    v: AdoFAIExportOptions[K],
  ) {
    // A focused numeric input may blur as the form becomes disabled.
    if (workingRef.current || !defaultsCurrent) return;
    invalidatePreview();
    // An error from the previous options must not remain after editing.
    setError(null);
    setOptions((o) =>
      o ? { ...o, [k]: v, harmonyTuning: "equal temperament" } : o,
    );
  }
  function changeAngleCompressionMode(angleCompressionMode: AdoFAIExportOptions["angleCompressionMode"]) {
    if (workingRef.current || !defaultsCurrent) return;
    invalidatePreview();
    setError(null);
    // Python uses "floor" when fixed angles and target BPM are combined.
    // Keep the displayed X mode consistent with the actual export.
    setOptions((o) => o ? {
      ...o,
      angleCompressionMode,
      xMode: xModeForCompression(angleCompressionMode, o.xMode),
    } : o);
  }
  function changeSelectedOnly(selectedOnly: boolean) {
    if (workingRef.current || !defaultsCurrent) return;
    invalidatePreview();
    setError(null);
    setOptions((o) => o ? {
      ...o, selectedOnly,
      songOffsetMs: o.songOffsetAuto
        ? exportScopeOffset(o.fullSongOffsetMs, o.selectedSongOffsetMs, selectedOnly)
        : o.songOffsetMs,
    } : o);
  }
  function changeSongOffsetAuto(songOffsetAuto: boolean) {
    if (workingRef.current || !defaultsCurrent) return;
    invalidatePreview();
    setError(null);
    setOptions((o) => o ? {
      ...o, songOffsetAuto,
      songOffsetMs: songOffsetAuto
        ? exportScopeOffset(o.fullSongOffsetMs, o.selectedSongOffsetMs, o.selectedOnly)
        : o.songOffsetMs,
    } : o);
  }
  async function run<T>(fn: () => Promise<T>) {
    const context = loadedContext;
    return actionOnce.current(async () => {
      workingRef.current = true;
      setWorking(true);
      setError(null);
      try {
        return await fn();
      } catch (e) {
        if (context && isCurrentAction(context)) setError({ message: String(e), context });
        return null;
      } finally {
        workingRef.current = false;
        setWorking(false);
      }
    });
  }
  const fixed = options && defaultsCurrent
    ? { ...options, harmonyTuning: "equal temperament" as const }
    : null;
  async function exportLevel() {
    const context = loadedContext;
    if (!fixed || !context) return;
    const r = await run(() => api.export_adofai_advanced(fixed, selected));
    if (!r || !isCurrentAction(context)) return;
    const status = exportStatusMessage(r);
    if (status !== null) onStatus(status);
    const failure = exportFailureMessage(r);
    if (failure) setError({ message: failure, context });
    if (r.ok && r.kps && r.kps.ranges.length) {
      // The chart is written; stay open so the warning is not missed.
      setKpsNotice({ status: r.status, report: r.kps });
      return;
    }
    if (r.ok) onClose();
  }
  async function tilePreview() {
    const context = loadedContext;
    if (!fixed || !context) return;
    const snapshot = { ...fixed }, selection = [...selected];
    const r = await run(async () => {
      const request = previewRequests.current.issue();
      const result = await api.preview_adofai_tiles(snapshot, selection);
      return { request, result };
    });
    if (r && isCurrentAction(context) && previewRequests.current.isCurrent(r.request)) {
      setTile(r.result);
      setDebug(null);
      setPreviewMode("tile");
    }
  }
  async function debugPreview() {
    const context = loadedContext;
    if (!fixed || !context) return;
    const snapshot = { ...fixed }, selection = [...selected];
    const r = await run(async () => {
      const request = previewRequests.current.issue();
      const result = await api.preview_adofai_debug(snapshot, selection);
      return { request, result };
    });
    if (r && isCurrentAction(context) && previewRequests.current.isCurrent(r.request)) {
      setDebug(r.result);
      setTile(null);
      setPreviewMode("debug");
    }
  }
  async function saveAsDefaults() {
    if (!fixed) return;
    const snapshot = { ...fixed };
    const r = await run(() => api.save_adofai_export_defaults(snapshot));
    if (r?.ok) onStatus(t("export.saved_defaults"));
  }
  async function chooseSongSource() {
    const context = loadedContext;
    if (!fixed || !context) return;
    const r = await run(() => api.choose_adofai_song_source());
    if (r?.ok && r.path && isCurrentAction(context)) {
      invalidatePreview();
      setOptions((o) =>
        isCurrentAction(context) && o
          ? {
              ...o,
              useProjectSong: true,
              songSourcePath: r.path!,
              harmonyTuning: "equal temperament",
            }
          : o,
      );
      onStatus(r.status);
    }
  }
  if (!options || !defaultsCurrent)
    return (
      <Modal title={t("export.title")} onClose={onClose} locked={working}>
        {currentError ? (
          <>
            <div className="dialog-error" role="alert">
              {t("export.defaults_failed", { error: currentError })}
            </div>
            <div className="dialog-footer">
              <button onClick={onClose} disabled={working}>{t("dialog.close")}</button>
              <button
                className="primary"
                disabled={working}
                onClick={() => setLoadAttempt((v) => v + 1)}
              >
                {t("dialog.retry")}
              </button>
            </div>
          </>
        ) : (
          <div className="dialog-loading" role="status">{working ? t("export.exporting") : t("export.loading")}</div>
        )}
      </Modal>
    );
  if (kpsNotice)
    return (
      <Modal title={t("export.title")} onClose={onClose} locked={working}>
        <div className="export-dialog-body">
          <p>{t("export.done")}</p>
          <div className="dialog-warning" role="alert">
            <b>
              {t("export.kps_heading", { limit: kpsNotice.report.limit, count: kpsNotice.report.ranges.length, max: Math.round(kpsNotice.report.maxKps) })}
            </b>
            <p>{t("export.kps_hint")}</p>
            <ul>
              {kpsRangeLines(kpsNotice.report).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        </div>
        <div className="dialog-footer">
          <span />
          <button className="primary" onClick={onClose}>
            {t("dialog.close")}
          </button>
        </div>
      </Modal>
    );
  const isHarmony = options.method === "harmony",
    isAngle = options.method === "angle_only",
    isZip = options.method === "rabbit_zip",
    isRatioPoly = options.harmonyTimingMode === "ratio-polyrhythm",
    cycleTiming = options.harmonyPolyCycleTiming ?? "pitch",
    beatSync = cycleTiming === "beat",
    syncedBpm = beatSyncedOutputBpm(
      options.projectBpm,
      options.harmonyPolyCycleAngle,
      options.harmonyPolyBeatsPerCycle ?? 1,
    );
  return (
    <Modal
      title={t("export.title")}
      onClose={onClose}
      locked={working}
      wide={previewMode !== "none"}
    >
      <div className={previewMode !== "none" ? "dialog-body export-dialog-body compact-export with-preview" : "dialog-body export-dialog-body compact-export"}>
        <fieldset
          disabled={working}
          aria-label={t("export.settings_label")}
          style={{ display: "grid", gap: 8, border: 0, margin: 0, padding: 0, minWidth: 0 }}
        >
        <Field label={t("export.destination")}>
          <Select
            value={options.appendToChart ? "append" : "new"}
            options={[
              ["new", t("export.dest_new")],
              ["append", t("export.dest_append")],
            ]}
            onChange={(v) => patch("appendToChart", v === "append")}
          />
        </Field>
        {options.appendToChart && (
          <div className="info-card compact">
            {t("export.append_info")}
          </div>
        )}
        <Field label={t("export.method")}>
          <Select
            value={options.method}
            options={[
              ["rabbit_zip", "Angle Compression"],
              ["angle_only", "Angle-only"],
              ["harmony", "Harmony / Polyrhythm"],
            ]}
            onChange={(v) =>
              patch("method", v as AdoFAIExportOptions["method"])
            }
          />
        </Field>
        {isHarmony && isRatioPoly && (
          <Field label={t("export.cycle_length")}>
            <Select
              value={cycleTiming}
              options={[
                ["pitch", t("export.cycle_pitch")],
                ["beat", t("export.cycle_beat", { bpm: formatBpm(options.projectBpm) })],
                ["manual", t("export.cycle_manual")],
              ]}
              onChange={(v) =>
                patch(
                  "harmonyPolyCycleTiming",
                  v as AdoFAIExportOptions["harmonyPolyCycleTiming"],
                )
              }
            />
          </Field>
        )}
        {isHarmony && isRatioPoly && beatSync && (
          <Field label={t("export.beats_per_cycle")}>
            <Num
              value={options.harmonyPolyBeatsPerCycle ?? 1}
              min={1 / 64}
              max={64}
              step="any"
              suffix={t("export.beats_unit")}
              onChange={(v) => patch("harmonyPolyBeatsPerCycle", v)}
            />
          </Field>
        )}
        {(isAngle || isHarmony) && !(isHarmony && isRatioPoly && cycleTiming !== "manual") && (
          <Field label={t("export.output_bpm")}>
            <Num
              value={options.angleOnlyBpm}
              min={1}
              max={999999}
              step="any"
              onChange={(v) => patch("angleOnlyBpm", v)}
            />
          </Field>
        )}
        {isHarmony && isRatioPoly && (
          <div className="info-card">
            {cycleTiming === "pitch"
              ? t("export.cycle_info_pitch")
              : beatSync
                ? t("export.cycle_info_beat", { bpm: formatBpm(syncedBpm), cycle: formatCycleSeconds(options.harmonyPolyCycleAngle, syncedBpm) })
                : t("export.cycle_info_manual", { cycle: formatCycleSeconds(options.harmonyPolyCycleAngle, options.angleOnlyBpm) })}
          </div>
        )}
        {isHarmony && (
          <>
            <Field label={t("export.chord")}>
              <Select
                value={options.harmonyMode}
                options={[
                  ["off", t("export.none")],
                  ["octave +12", t("export.chord_octave_up")],
                  ["fifth +7", t("export.chord_fifth")],
                  ["major third +4", t("export.chord_major_third")],
                  ["minor third +3", t("export.chord_minor_third")],
                  ["lower octave -12", t("export.chord_octave_down")],
                  ["major triad", t("export.chord_major_triad")],
                  ["minor triad", t("export.chord_minor_triad")],
                  ["sus4", "sus4"],
                  ["dominant 7", t("export.chord_dominant7")],
                  ["custom", t("export.custom")],
                ]}
                onChange={(v) => patch("harmonyMode", v)}
              />
            </Field>
            {options.harmonyMode === "custom" && (
              <Field label={t("export.semitones")}>
                <Num
                  value={options.harmonyCustomSemitone}
                  min={-48}
                  max={48}
                  step="any"
                  onChange={(v) => patch("harmonyCustomSemitone", v)}
                />
              </Field>
            )}
            <Field label={t("export.timing")}>
              <Select
                value={options.harmonyTimingMode}
                options={[
                  ["setspeed", "SetSpeed"],
                  ["angle-only", "Angle-only"],
                  ["ratio-polyrhythm", t("export.ratio_polyrhythm")],
                ]}
                onChange={(v) =>
                  patch(
                    "harmonyTimingMode",
                    v as AdoFAIExportOptions["harmonyTimingMode"],
                  )
                }
              />
            </Field>
            {options.harmonyTimingMode === "ratio-polyrhythm" && (
              <Field label={t("export.chord_source")}>
                <Select
                  value={options.harmonyPolyChordSource ?? "overlap"}
                  options={[
                    ["overlap", t("export.chord_overlap")],
                    ["preset", t("export.chord_preset")],
                  ]}
                  onChange={(v) =>
                    patch(
                      "harmonyPolyChordSource",
                      v as AdoFAIExportOptions["harmonyPolyChordSource"],
                    )
                  }
                />
              </Field>
            )}
            {options.harmonyTimingMode === "ratio-polyrhythm" &&
              (options.harmonyPolyChordSource ?? "overlap") === "overlap" && (
                <details className="advanced-fold">
                  <summary>{t("export.chord_details")}</summary>
                  <div className="advanced-grid">
                  <Field label={t("export.ignore_short")}>
                    <Num
                      value={options.harmonyPolyLegatoMs ?? 50}
                      min={0}
                      max={1000}
                      step="any"
                      suffix=" ms"
                      onChange={(v) => patch("harmonyPolyLegatoMs", v)}
                    />
                  </Field>
                  <Field label={t("export.max_voices")}>
                    <Num
                      value={options.harmonyPolyMaxVoices ?? 3}
                      min={0}
                      max={16}
                      step={1}
                      suffix={t("export.max_voices_unit")}
                      onChange={(v) => patch("harmonyPolyMaxVoices", Math.round(v))}
                    />
                  </Field>
                  <Field label={t("export.max_root_cycles")}>
                    <Num
                      value={options.harmonyPolyMaxRootCycles ?? 12}
                      min={0}
                      max={1024}
                      step={1}
                      suffix={t("export.no_limit_unit")}
                      onChange={(v) => patch("harmonyPolyMaxRootCycles", Math.round(v))}
                    />
                  </Field>
                  <div className="info-card">
                    {t("export.voices_info")}
                  </div>
                  <Field label={t("export.octave_dup")} group>
                    <label className="inline-check">
                      <input
                        type="checkbox"
                        checked={options.harmonyPolyMergeOctaves ?? true}
                        onChange={(e) => patch("harmonyPolyMergeOctaves", e.target.checked)}
                      />
                      {t("export.merge_octaves")}
                    </label>
                  </Field>
                  </div>
                </details>
              )}
            <div className="info-card">
              {options.harmonyTimingMode === "ratio-polyrhythm"
                ? (options.harmonyPolyChordSource ?? "overlap") === "overlap"
                  ? t("export.ratio_info_overlap")
                  : t("export.ratio_info_preset")
                : t("export.equal_temperament")}
            </div>
          </>
        )}
        {!options.appendToChart && (<>
        <Field label={t("export.audio")} group>
          <label className="inline-check">
            <input
              type="checkbox"
              checked={options.useProjectSong}
              onChange={(e) => patch("useProjectSong", e.target.checked)}
            />
            {t("export.use_audio")}
          </label>
        </Field>
        {options.useProjectSong && (
          <Field label={t("export.song_source")} group>
            <div className="number-with-suffix">
              <input
                type="text"
                value={options.songSourcePath || t("export.not_selected")}
                aria-label={t("export.song_source")}
                readOnly
                title={options.songSourcePath || t("export.song_not_selected")}
              />
              <button
                type="button"
                onClick={() => void chooseSongSource()}
                disabled={working}
              >
                {t("export.change")}
              </button>
            </div>
          </Field>
        )}
        </>)}
        {selected.length > 0 && (
          <Field label={t("export.scope")} group>
            <label className="inline-check">
              <input
                type="checkbox"
                checked={options.selectedOnly}
                onChange={(e) => changeSelectedOnly(e.target.checked)}
              />
              {t("export.selected_only", { count: selected.length })}
            </label>
          </Field>
        )}
        <details className="advanced-fold">
          <summary>{t("export.advanced")}</summary>
          <div className="advanced-grid">
            <Field label={t("export.duplicates")} group>
              <label className="inline-check">
                <input
                  type="checkbox"
                  checked={options.mergeDuplicateNotes ?? true}
                  onChange={(e) => patch("mergeDuplicateNotes", e.target.checked)}
                />
                {t("export.merge_duplicates")}
              </label>
            </Field>
            {!isHarmony && (
              <Field label={t("export.chain")} group>
                <label className="inline-check">
                  <input
                    type="checkbox"
                    checked={options.chainContiguous ?? true}
                    onChange={(e) => patch("chainContiguous", e.target.checked)}
                  />
                  {t("export.chain_contiguous")}
                </label>
              </Field>
            )}
            {isZip && (
              <>
                <Field label={t("export.compression_angle")}>
                  <Select
                    value={options.angleCompressionMode}
                    options={[
                      ["auto", t("export.auto")],
                      ["fixed", t("export.fixed_angle")],
                    ]}
                    onChange={(v) =>
                      changeAngleCompressionMode(v as AdoFAIExportOptions["angleCompressionMode"])
                    }
                  />
                </Field>
                {options.angleCompressionMode === "fixed" && (
                  <Field label={t("export.fixed_angle")}>
                    <Num
                      value={options.angleCompressionFixedAngle}
                      min={0.001}
                      max={359.999}
                      step="any"
                      suffix="°"
                      onChange={(v) => patch("angleCompressionFixedAngle", v)}
                    />
                  </Field>
                )}
                {options.angleCompressionMode === "fixed" && (
                  <div className="info-card">{t("export.fixed_angle_no_target")}</div>
                )}
                <Field label={t("export.x_mode")}>
                  <Select
                    value={options.xMode}
                    options={xModeOptions().filter(([mode]) =>
                      isXModeAvailable(options.angleCompressionMode, mode)
                    )}
                    onChange={(v) =>
                      patch("xMode", v as AdoFAIExportOptions["xMode"])
                    }
                  />
                </Field>
                {options.xMode === "fixed" && (
                  <Field label={t("export.fixed_x")}>
                    <Num
                      value={options.fixedX}
                      min={0.000001}
                      max={100000}
                      step="any"
                      onChange={(v) => patch("fixedX", v)}
                    />
                  </Field>
                )}
                {options.xMode === "target_bpm" && (
                  <Field label={t("export.target_bpm")}>
                    <Num
                      value={options.targetBpm}
                      min={1}
                      max={999999}
                      step="any"
                      onChange={(v) => patch("targetBpm", v)}
                    />
                  </Field>
                )}
              </>
            )}
            <Field label={t("export.path")}>
              <Select
                value={options.visualPathMode}
                options={[
                  ["raw", t("export.path_raw")],
                  ["upward", t("export.path_upward")],
                  ["upward avoid", t("export.path_upward_avoid")],
                  ["auto route twirl", t("export.path_auto_twirl")],
                ]}
                onChange={(v) =>
                  patch(
                    "visualPathMode",
                    v as AdoFAIExportOptions["visualPathMode"],
                  )
                }
              />
            </Field>
            {options.visualPathMode !== "raw" && (
              <Field label={t("export.path_angle")}>
                <Num
                  value={options.visualPathAngle}
                  min={0}
                  max={359.999}
                  step="any"
                  suffix="°"
                  onChange={(v) => patch("visualPathAngle", v)}
                />
              </Field>
            )}
            <Field label={t("export.position_events")}>
              <Select
                value={options.visualPositionMode}
                options={[
                  ["off", t("export.off")],
                  ["note step", t("export.per_note")],
                ]}
                onChange={(v) =>
                  patch(
                    "visualPositionMode",
                    v as AdoFAIExportOptions["visualPositionMode"],
                  )
                }
              />
            </Field>
            {options.visualPositionMode !== "off" && (
              <>
                <Field label={t("export.position_x")}>
                  <Num
                    value={options.visualPositionX}
                    min={-100000}
                    max={100000}
                    step="any"
                    onChange={(v) => patch("visualPositionX", v)}
                  />
                </Field>
                <Field label={t("export.position_y")}>
                  <Num
                    value={options.visualPositionY}
                    min={-100000}
                    max={100000}
                    step="any"
                    onChange={(v) => patch("visualPositionY", v)}
                  />
                </Field>
              </>
            )}
            <Field label={t("export.final_tile")}>
              <Select
                value={options.finalAngleMode}
                options={[
                  ["scaled", t("export.final_scaled")],
                  ["cardinal", t("export.final_cardinal")],
                  ["horizontal", t("export.final_horizontal")],
                  ["custom", t("export.final_custom")],
                ]}
                onChange={(v) =>
                  patch(
                    "finalAngleMode",
                    v as AdoFAIExportOptions["finalAngleMode"],
                  )
                }
              />
            </Field>
            {options.finalAngleMode === "custom" && (
              <Field label={t("export.final_custom")}>
                <Num
                  value={options.finalCustomAngle}
                  min={0.001}
                  max={359.999}
                  step="any"
                  suffix="°"
                  onChange={(v) => patch("finalCustomAngle", v)}
                />
              </Field>
            )}
            {options.finalAngleMode === "cardinal" && (
              <Field label={t("export.step")}>
                <Num
                  value={options.finalCardinalStep}
                  min={1}
                  max={180}
                  step="any"
                  suffix="°"
                  onChange={(v) => patch("finalCardinalStep", v)}
                />
              </Field>
            )}
            {isHarmony && (
              <>
                <Field label={t("export.root_estimate")}>
                  <Select
                    value={options.harmonyRootMode}
                    options={[
                      ["fixed root", t("export.fixed")],
                      ["least squares Hz", t("export.root_ls_hz")],
                      ["least squares cents", t("export.root_ls_cents")],
                      ["minimax cents", t("export.root_minimax")],
                    ]}
                    onChange={(v) => patch("harmonyRootMode", v)}
                  />
                </Field>
                <Field label={t("export.visual_round")}>
                  <Select
                    value={options.harmonyVisualMode}
                    options={[
                      ["raw", t("export.none")],
                      ["round 45°", "45°"],
                      ["round 90°", "90°"],
                      ["custom step", t("export.custom_step")],
                    ]}
                    onChange={(v) => patch("harmonyVisualMode", v)}
                  />
                </Field>
                {options.harmonyVisualMode === "custom step" && (
                  <Field label={t("export.step")}>
                    <Num
                      value={options.harmonyVisualStep}
                      min={1}
                      max={180}
                      step="any"
                      suffix="°"
                      onChange={(v) => patch("harmonyVisualStep", v)}
                    />
                  </Field>
                )}
                {options.harmonyTimingMode === "ratio-polyrhythm" && (
                  <>
                    <Field label={t("export.cycle_angle")}>
                      <Select
                        value={options.harmonyPolyCycleMode}
                        options={[
                          ["auto", t("export.cycle_angle_auto")],
                          ["fixed", t("export.fixed")],
                        ]}
                        onChange={(v) =>
                          patch(
                            "harmonyPolyCycleMode",
                            v as AdoFAIExportOptions["harmonyPolyCycleMode"],
                          )
                        }
                      />
                    </Field>
                    <Field
                      label={
                        options.harmonyPolyCycleMode === "auto"
                          ? t("export.cycle_length")
                          : t("export.cycle_angle_value")
                      }
                    >
                      <Num
                        value={options.harmonyPolyCycleAngle}
                        min={1}
                        max={100000}
                        step="any"
                        suffix="°"
                        onChange={(v) => patch("harmonyPolyCycleAngle", v)}
                      />
                    </Field>
                    {options.harmonyPolyCycleMode === "auto" && (
                      <div className="info-card">
                        {t("export.cycle_auto_info")}
                      </div>
                    )}
                    <Field label={t("export.max_denominator")}>
                      <Num
                        value={options.harmonyPolyMaxDenominator}
                        min={1}
                        max={256}
                        step={1}
                        onChange={(v) =>
                          patch("harmonyPolyMaxDenominator", Math.round(v))
                        }
                      />
                    </Field>
                    <Field label={t("export.octave_ratio")}>
                      <Select
                        value={options.harmonyPolyRatioOctaveMode}
                        options={[
                          ["octave-folded", t("export.octave_folded")],
                          ["absolute", t("export.absolute")],
                        ]}
                        onChange={(v) =>
                          patch(
                            "harmonyPolyRatioOctaveMode",
                            v as AdoFAIExportOptions["harmonyPolyRatioOctaveMode"],
                          )
                        }
                      />
                    </Field>
                  </>
                )}
              </>
            )}
            {options.useProjectSong && !options.appendToChart && (
              <>
                <Field label={t("export.copy_audio")} group>
                  <label className="inline-check">
                    <input
                      type="checkbox"
                      checked={options.copyProjectSong}
                      onChange={(e) =>
                        patch("copyProjectSong", e.target.checked)
                      }
                    />
                    {t("export.copy_beside")}
                  </label>
                </Field>
                {options.copyProjectSong && (
                  <Field label={t("export.same_name")}>
                    <Select
                      value={options.songConflictAction}
                      options={[
                        ["cancel", t("export.conflict_cancel")],
                        ["rename", t("export.conflict_rename")],
                        ["overwrite", t("export.conflict_overwrite")],
                      ]}
                      onChange={(v) =>
                        patch(
                          "songConflictAction",
                          v as AdoFAIExportOptions["songConflictAction"],
                        )
                      }
                    />
                  </Field>
                )}
                <Field label="songOffset" group>
                  <label className="inline-check">
                    <input
                      type="checkbox"
                      checked={options.songOffsetAuto}
                      onChange={(e) => changeSongOffsetAuto(e.target.checked)}
                    />
                    {t("export.offset_auto")}
                  </label>
                </Field>
                {!options.songOffsetAuto && (
                  <Field label="songOffset">
                    <Num
                      value={options.songOffsetMs}
                      min={-3600000}
                      max={3600000}
                      step="any"
                      suffix=" ms"
                      onChange={(v) => patch("songOffsetMs", v)}
                    />
                  </Field>
                )}
              </>
            )}
          </div>
        </details>
        </fieldset>
        {currentError && <div className="dialog-error" role="alert">{currentError}</div>}
        {previewMode === "tile" && tile && <TilePreview preview={tile} />}{" "}
        {previewMode === "debug" && debug && <DebugPreview preview={debug} />}
      </div>
      <div className="dialog-footer">
        {/* Side tools on the left; the decision (cancel / export) together on the right. */}
        <button className="quiet" onClick={() => onHelp("adofai_export")} disabled={working}>
          {t("export.help")}
        </button>
        <button className="quiet" onClick={() => void tilePreview()} disabled={working}>
          {t("export.tile_preview")}
        </button>
        <button className="quiet" onClick={() => void debugPreview()} disabled={working}>
          {t("export.debug")}
        </button>
        <button className="quiet" onClick={() => void saveAsDefaults()} disabled={working} title={t("export.set_default_tip")}>
          {t("export.set_default")}
        </button>
        <span />
        <button onClick={onClose} disabled={working}>
          {t("dialog.cancel")}
        </button>
        <button
          className="primary"
          onClick={() => void exportLevel()}
          disabled={working}
        >
          {working ? t("dialog.processing") : options?.appendToChart ? t("export.append_button") : t("export.export_button")}
        </button>
      </div>
    </Modal>
  );
}
function Modal({
  title,
  onClose,
  wide,
  locked = false,
  children,
}: {
  title: string;
  onClose(): void;
  wide?: boolean;
  locked?: boolean;
  children: ReactNode;
}) {
  const close = () => {
      if (!locked) onClose();
    },
    { dialogRef, titleId } = useDialogAccessibility(close);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <section
        ref={dialogRef}
        tabIndex={-1}
        className={wide ? "modal-window wide" : "modal-window"}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-busy={locked}
      >
        <header className="modal-title">
          <strong id={titleId}>{title}</strong>
          <button aria-label={t("dialog.close")} disabled={locked} onClick={close}>
            ×
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}
function Field({
  label,
  children,
  group = false,
}: {
  label: string;
  children: ReactNode;
  group?: boolean;
}) {
  if (group) {
    // Group controls without nesting labels or associating multiple controls with one label.
    return (
      <div className="dialog-field" role="group" aria-label={label}>
        <span>{label}</span>
        <div>{children}</div>
      </div>
    );
  }
  return (
    <label className="dialog-field">
      <span>{label}</span>
      <div>{children}</div>
    </label>
  );
}
function Select({
  value,
  options,
  onChange,
}: {
  value: string;
  options: Array<[string, string]>;
  onChange(v: string): void;
}) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      {options.map(([v, l]) => (
        <option key={v} value={v}>
          {l}
        </option>
      ))}
    </select>
  );
}
function Num({
  value,
  min,
  max,
  step,
  suffix,
  onChange,
}: {
  value: number;
  min: number;
  max: number;
  step: number | "any";
  suffix?: string;
  onChange(v: number): void;
}) {
  const fallback = Number.isFinite(value) ? value : 0;
  const [text, setText] = useState(String(fallback));
  const [editing, setEditing] = useState(false);
  const cancelledRef = useRef(false);
  const editedRef = useRef(false);
  useEffect(() => {
    if (!editing) setText(String(fallback));
  }, [editing, fallback]);
  function commit() {
    const next = commitNumericEdit(text, fallback, min, max, cancelledRef.current, step === 1, editedRef.current);
    cancelledRef.current = false;
    editedRef.current = false;
    setEditing(false);
    setText(String(next));
    if (next !== fallback) onChange(next);
  }
  return (
    <div className="number-with-suffix">
      <input
        type="number"
        value={text}
        min={min}
        max={max}
        step={step}
        onFocus={() => { cancelledRef.current = false; editedRef.current = false; setEditing(true); }}
        onChange={(event) => { editedRef.current = true; setText(event.target.value); }}
        onBlur={commit}
        onKeyDown={(event) => {
          // IME owns Enter/Escape while a composition is active.
          if (isDialogCompositionKey(event.nativeEvent)) return;
          if (event.key === "Enter") event.currentTarget.blur();
          else if (isPlainDialogEscape(event)) {
            event.preventDefault();
            // Cancel this edit without closing the surrounding modal.
            event.stopPropagation();
            cancelledRef.current = true;
            setText(String(fallback));
            event.currentTarget.blur();
          }
        }}
      />
      {suffix && <span>{suffix}</span>}
    </div>
  );
}
function TilePreview({ preview }: { preview: AdoFAITilePreview }) {
  const geo = useMemo(() => {
    if (!preview.points.length) return null;
    let minX = preview.points[0].x,
      maxX = minX,
      minY = preview.points[0].y,
      maxY = minY;
    for (const p of preview.points) {
      minX = Math.min(minX, p.x);
      maxX = Math.max(maxX, p.x);
      minY = Math.min(minY, p.y);
      maxY = Math.max(maxY, p.y);
    }
    const pad = Math.max(2, Math.max(maxX - minX, maxY - minY) * 0.04),
      d = preview.points
        .map((p, i) => `${i ? "L" : "M"} ${p.x} ${-p.y}`)
        .join(" ");
    return {
      d,
      viewBox: `${minX - pad} ${-maxY - pad} ${Math.max(1, maxX - minX + pad * 2)} ${Math.max(1, maxY - minY + pad * 2)}`,
    };
  }, [preview]);
  if (!geo) return <div className="info-card">{t("export.no_tiles")}</div>;
  return (
    <div className="tile-preview-wrap">
      <div className="preview-summary">
        {t("export.tiles_shown", { shown: preview.shownTiles, total: preview.totalTiles })}
        {preview.limited ? t("export.partial") : ""}
      </div>
      <svg
        className="tile-preview-svg"
        viewBox={geo.viewBox}
        role="img"
        aria-label={t("export.path_preview", { count: preview.shownTiles })}
      >
        <path d={geo.d} className="tile-track-outline" />
        <path d={geo.d} className="tile-track" />
      </svg>
    </div>
  );
}
function DebugPreview({ preview }: { preview: AdoFAIDebugPreview }) {
  const cols = preview.rows.length ? Object.keys(preview.rows[0]) : [],
    rows = preview.rows.slice(0, 300);
  return (
    <div className="debug-preview">
      <div className="preview-summary">
        {t("export.rows_shown", { shown: rows.length, total: preview.summary.rows })}
        {preview.summary.rows > rows.length || preview.limited ? t("export.partial") : ""}{" / "}
        {t("export.estimated", { tiles: preview.summary.estimatedTiles, warnings: preview.summary.warnings })}
      </div>
      <div className="debug-table-wrap">
        <table>
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {cols.map((c) => (
                  <td key={c}>{String(r[c] ?? "")}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
