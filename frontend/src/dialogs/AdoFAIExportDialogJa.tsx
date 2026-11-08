import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type {
  AdoFAIDebugPreview,
  AdoFAIExportOptions,
  AdoFAITilePreview,
  BackendApi,
} from "./bridge";
import { LatestRequestGate } from "../api/requestCoordinator";
import { useDialogAccessibility } from "./useDialogAccessibility";
import { isDialogCompositionKey, isPlainDialogEscape } from "./dialogFocus";
import { commitNumericEdit } from "../settings/numericInputModel";
import { createExclusiveAsyncAction } from "./exclusiveAsyncAction";
import { exportDefaultsContextIsCurrent } from "./previewFreshness";
import { exportFailureMessage } from "./exportResult";
import { exportScopeOffset } from "./exportScopeOffset";
import { isXModeAvailable, xModeForCompression } from "./angleCompressionXMode";

type ExportContext = { api: BackendApi; selected: number[]; defaultSelectedOnly: boolean; loadAttempt: number; documentGeneration: number };

const xModeOptions: Array<[AdoFAIExportOptions["xMode"], string]> = [
  ["floor", "切り捨て"],
  ["lowest_floor", "最小切り捨て"],
  ["round", "四捨五入"],
  ["ceil", "切り上げ"],
  ["fixed", "固定"],
  ["target_bpm", "目標BPM"],
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
    [previewMode, setPreviewMode] = useState<"none" | "tile" | "debug">("none");
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
    onStatus(r.status);
    const failure = exportFailureMessage(r);
    if (failure) setError({ message: failure, context });
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
      <Modal title="ADOFAI出力" onClose={onClose} locked={working}>
        {currentError ? (
          <>
            <div className="dialog-error" role="alert">
              設定の読込に失敗しました: {currentError}
            </div>
            <div className="dialog-footer">
              <button onClick={onClose} disabled={working}>閉じる</button>
              <button
                className="primary"
                disabled={working}
                onClick={() => setLoadAttempt((v) => v + 1)}
              >
                再試行
              </button>
            </div>
          </>
        ) : (
          <div className="dialog-loading" role="status">{working ? "出力処理中…" : "設定を読み込んでいます…"}</div>
        )}
      </Modal>
    );
  const isHarmony = options.method === "harmony",
    isAngle = options.method === "angle_only",
    isZip = options.method === "rabbit_zip";
  return (
    <Modal
      title="ADOFAI出力"
      onClose={onClose}
      locked={working}
      wide={previewMode !== "none"}
    >
      <div className="dialog-body export-dialog-body compact-export">
        <fieldset
          disabled={working}
          aria-label="ADOFAI出力設定"
          style={{ display: "grid", gap: 8, border: 0, margin: 0, padding: 0, minWidth: 0 }}
        >
        <Field label="方式">
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
        {!isAngle && (
          <Field label="基準BPM">
            <Num
              value={options.baseBpm}
              min={1}
              max={999999}
              step="any"
              onChange={(v) => patch("baseBpm", v)}
            />
          </Field>
        )}
        {isAngle && (
          <Field label="出力BPM">
            <Num
              value={options.angleOnlyBpm}
              min={1}
              max={999999}
              step="any"
              onChange={(v) => patch("angleOnlyBpm", v)}
            />
          </Field>
        )}
        {isHarmony && (
          <>
            <Field label="和音">
              <Select
                value={options.harmonyMode}
                options={[
                  ["off", "なし"],
                  ["octave +12", "1オクターブ上"],
                  ["fifth +7", "完全5度"],
                  ["major third +4", "長3度"],
                  ["minor third +3", "短3度"],
                  ["lower octave -12", "1オクターブ下"],
                  ["major triad", "長三和音"],
                  ["minor triad", "短三和音"],
                  ["sus4", "sus4"],
                  ["dominant 7", "属7"],
                  ["custom", "カスタム"],
                ]}
                onChange={(v) => patch("harmonyMode", v)}
              />
            </Field>
            {options.harmonyMode === "custom" && (
              <Field label="半音差">
                <Num
                  value={options.harmonyCustomSemitone}
                  min={-48}
                  max={48}
                  step="any"
                  onChange={(v) => patch("harmonyCustomSemitone", v)}
                />
              </Field>
            )}
            <Field label="タイミング">
              <Select
                value={options.harmonyTimingMode}
                options={[
                  ["setspeed", "SetSpeed"],
                  ["angle-only", "Angle-only"],
                  ["ratio-polyrhythm", "比率ポリリズム"],
                ]}
                onChange={(v) =>
                  patch(
                    "harmonyTimingMode",
                    v as AdoFAIExportOptions["harmonyTimingMode"],
                  )
                }
              />
            </Field>
            <div className="info-card">音律は平均律に固定されています。</div>
          </>
        )}
        <Field label="音声" group>
          <label className="inline-check">
            <input
              type="checkbox"
              checked={options.useProjectSong}
              onChange={(e) => patch("useProjectSong", e.target.checked)}
            />
            音声を使用
          </label>
        </Field>
        {options.useProjectSong && (
          <Field label="音源先" group>
            <div className="number-with-suffix">
              <input
                type="text"
                value={options.songSourcePath || "未選択"}
                aria-label="音源先"
                readOnly
                title={options.songSourcePath || "音源先が未選択です"}
              />
              <button
                type="button"
                onClick={() => void chooseSongSource()}
                disabled={working}
              >
                変更
              </button>
            </div>
          </Field>
        )}
        {selected.length > 0 && (
          <Field label="出力範囲" group>
            <label className="inline-check">
              <input
                type="checkbox"
                checked={options.selectedOnly}
                onChange={(e) => changeSelectedOnly(e.target.checked)}
              />
              選択ノートのみ（{selected.length}個）
            </label>
          </Field>
        )}
        <details className="advanced-fold">
          <summary>詳細設定</summary>
          <div className="advanced-grid">
            {isZip && (
              <>
                <Field label="圧縮角度">
                  <Select
                    value={options.angleCompressionMode}
                    options={[
                      ["auto", "自動"],
                      ["fixed", "固定角度"],
                    ]}
                    onChange={(v) =>
                      changeAngleCompressionMode(v as AdoFAIExportOptions["angleCompressionMode"])
                    }
                  />
                </Field>
                {options.angleCompressionMode === "fixed" && (
                  <Field label="固定角度">
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
                  <div className="info-card">固定圧縮角度では「目標BPM」のX計算は使えません。</div>
                )}
                <Field label="Xの決め方">
                  <Select
                    value={options.xMode}
                    options={xModeOptions.filter(([mode]) =>
                      isXModeAvailable(options.angleCompressionMode, mode)
                    )}
                    onChange={(v) =>
                      patch("xMode", v as AdoFAIExportOptions["xMode"])
                    }
                  />
                </Field>
                {options.xMode === "fixed" && (
                  <Field label="固定X">
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
                  <Field label="目標BPM">
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
            <Field label="経路">
              <Select
                value={options.visualPathMode}
                options={[
                  ["raw", "そのまま"],
                  ["upward", "上向き"],
                  ["upward avoid", "上向き＋重なり回避"],
                  ["auto route twirl", "自動経路（Twirl）"],
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
              <Field label="経路角度">
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
            <Field label="位置イベント">
              <Select
                value={options.visualPositionMode}
                options={[
                  ["off", "オフ"],
                  ["note step", "ノートごと"],
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
                <Field label="位置X">
                  <Num
                    value={options.visualPositionX}
                    min={-100000}
                    max={100000}
                    step="any"
                    onChange={(v) => patch("visualPositionX", v)}
                  />
                </Field>
                <Field label="位置Y">
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
            <Field label="端数タイル">
              <Select
                value={options.finalAngleMode}
                options={[
                  ["scaled", "比率維持"],
                  ["cardinal", "基準角へ丸める"],
                  ["horizontal", "水平"],
                  ["custom", "指定角度"],
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
              <Field label="指定角度">
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
              <Field label="丸め幅">
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
                <Field label="基準音推定">
                  <Select
                    value={options.harmonyRootMode}
                    options={[
                      ["fixed root", "固定"],
                      ["least squares Hz", "最小二乗（Hz）"],
                      ["least squares cents", "最小二乗（セント）"],
                      ["minimax cents", "最大誤差最小（セント）"],
                    ]}
                    onChange={(v) => patch("harmonyRootMode", v)}
                  />
                </Field>
                <Field label="見た目丸め">
                  <Select
                    value={options.harmonyVisualMode}
                    options={[
                      ["raw", "なし"],
                      ["round 45°", "45°"],
                      ["round 90°", "90°"],
                      ["custom step", "指定幅"],
                    ]}
                    onChange={(v) => patch("harmonyVisualMode", v)}
                  />
                </Field>
                {options.harmonyVisualMode === "custom step" && (
                  <Field label="丸め幅">
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
                    <Field label="周期角度">
                      <Num
                        value={options.harmonyPolyCycleAngle}
                        min={1}
                        max={100000}
                        step="any"
                        suffix="°"
                        onChange={(v) => patch("harmonyPolyCycleAngle", v)}
                      />
                    </Field>
                    <Field label="最大分母">
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
                    <Field label="オクターブ比">
                      <Select
                        value={options.harmonyPolyRatioOctaveMode}
                        options={[
                          ["octave-folded", "オクターブ内へ折り返す"],
                          ["absolute", "絶対比率"],
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
            {options.useProjectSong && (
              <>
                <Field label="音声コピー" group>
                  <label className="inline-check">
                    <input
                      type="checkbox"
                      checked={options.copyProjectSong}
                      onChange={(e) =>
                        patch("copyProjectSong", e.target.checked)
                      }
                    />
                    譜面の横へコピー
                  </label>
                </Field>
                {options.copyProjectSong && (
                  <Field label="同名音源">
                    <Select
                      value={options.songConflictAction}
                      options={[
                        ["cancel", "中止して保護"],
                        ["rename", "別名でコピー"],
                        ["overwrite", "上書き"],
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
                    最初のノートから自動計算
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
            <Field label="最大床数">
              <Num
                value={options.maxTiles}
                min={0}
                max={10000000}
                step={1}
                onChange={(v) => patch("maxTiles", Math.round(v))}
              />
            </Field>
            <Field label="1ノート上限">
              <Num
                value={options.maxTilesPerNote}
                min={0}
                max={1000000}
                step={1}
                onChange={(v) => patch("maxTilesPerNote", Math.round(v))}
              />
            </Field>
          </div>
        </details>
        </fieldset>
        {currentError && <div className="dialog-error" role="alert">{currentError}</div>}
        {previewMode === "tile" && tile && <TilePreview preview={tile} />}{" "}
        {previewMode === "debug" && debug && <DebugPreview preview={debug} />}
      </div>
      <div className="dialog-footer">
        <button onClick={onClose} disabled={working}>
          キャンセル
        </button>
        <button onClick={() => void tilePreview()} disabled={working}>
          タイルプレビュー
        </button>
        <button onClick={() => void debugPreview()} disabled={working}>
          デバッグ
        </button>
        <button onClick={() => onHelp("adofai_export")} disabled={working}>
          ヘルプ
        </button>
        <span />
        <button
          className="primary"
          onClick={() => void exportLevel()}
          disabled={working}
        >
          {working ? "処理中…" : "出力"}
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
          <button aria-label="閉じる" disabled={locked} onClick={close}>
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
  if (!geo) return <div className="info-card">タイルがありません。</div>;
  return (
    <div className="tile-preview-wrap">
      <div className="preview-summary">
        表示 {preview.shownTiles} / 全 {preview.totalTiles} タイル
        {preview.limited ? "（一部のみ）" : ""}
      </div>
      <svg
        className="tile-preview-svg"
        viewBox={geo.viewBox}
        role="img"
        aria-label={`ADOFAI経路プレビュー。${preview.shownTiles}タイルを表示`}
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
        表示 {rows.length} / 全 {preview.summary.rows} 行{" "}
        {preview.summary.rows > rows.length || preview.limited ? "（一部のみ）" : ""} / 推定タイル{" "}
        {preview.summary.estimatedTiles} / 警告 {preview.summary.warnings}
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
