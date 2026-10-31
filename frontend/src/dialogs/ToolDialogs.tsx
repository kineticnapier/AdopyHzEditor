import { useEffect, useRef, useState, type ReactNode } from "react";
import type { NoteMutationResult } from "./bridge";
import type {
  BlankWorkspaceOptions,
  HarmonicDiagramOptions,
  HarmonicPreview,
  QuickHzOptions,
  QuickHzResult,
  ToolBackendApi,
} from "./toolsBridge";
import { useDialogAccessibility } from "./useDialogAccessibility";
import { commitNumericEdit } from "../settings/numericInputModel";
import { runQuickHzOutputAction } from "./quickHzOutputActions";
import { runReleasePageAction } from "./releasePageAction";
import { createExclusiveAsyncAction } from "./exclusiveAsyncAction";
import { previewIsCurrent } from "./previewFreshness";
import { dismissUnlessBusy } from "./dialogClosePolicy";
import { quickHzActionPolicy } from "./quickHzActionPolicy";
type Common = {
  api: ToolBackendApi;
  onClose(): void;
  onStatus(text: string): void;
};
function Modal({
  title,
  children,
  onClose,
  wide,
  locked = false,
}: {
  title: string;
  children: ReactNode;
  onClose(): void;
  wide?: boolean;
  locked?: boolean;
}) {
  const close = () => { dismissUnlessBusy(locked, onClose); };
  const { dialogRef, titleId } = useDialogAccessibility(close);
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
function Field({ label, children, group = false }: { label: string; children: ReactNode; group?: boolean }) {
  if (group) {
    // A label must not contain multiple controls or another label.
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
function Num({
  label,
  value,
  min,
  max,
  step = 1,
  disabled,
  onChange,
}: {
  label?: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  disabled?: boolean;
  onChange(v: number): void;
}) {
  const fallback = Number.isFinite(value) ? value : 0;
  const [text, setText] = useState(String(fallback));
  const [editing, setEditing] = useState(false);
  const cancelledRef = useRef(false);
  useEffect(() => {
    if (!editing) setText(String(fallback));
  }, [editing, fallback]);
  function commit() {
    if (disabled) {
      // Disabling a focused input can fire blur after an action has started.
      cancelledRef.current = false;
      setEditing(false);
      setText(String(fallback));
      return;
    }
    const next = commitNumericEdit(text, fallback, min, max, cancelledRef.current);
    cancelledRef.current = false;
    setEditing(false);
    setText(String(next));
    if (next !== fallback) onChange(next);
  }
  return (
      <input
        type="number"
        aria-label={label}
        value={text}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        onFocus={() => { cancelledRef.current = false; setEditing(true); }}
        onChange={(event) => setText(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur();
          else if (event.key === "Escape") {
            event.preventDefault();
            // Cancel this edit without closing the surrounding modal.
            event.stopPropagation();
            cancelledRef.current = true;
            setText(String(fallback));
            event.currentTarget.blur();
          }
        }}
      />
  );
}
function LoadFailure({ error, onRetry }: { error: string; onRetry(): void }) {
  return (
    <>
      <div className="dialog-error">読込に失敗しました: {error}</div>
      <div className="dialog-footer">
        <span />
        <button className="primary" onClick={onRetry}>
          再試行
        </button>
      </div>
    </>
  );
}

export function BlankWorkspaceDialog({
  api,
  onClose,
  onStatus,
  onApply,
}: Common & { onApply(options: BlankWorkspaceOptions): Promise<void> }) {
  const applyOnce = useRef(createExclusiveAsyncAction());
  const [value, setValue] = useState<BlankWorkspaceOptions | null>(null),
    [loadError, setLoadError] = useState(""),
    [attempt, setAttempt] = useState(0),
    [applying, setApplying] = useState(false);
  useEffect(() => {
    let alive = true;
    setLoadError("");
    void api
      .get_blank_workspace_defaults()
      .then((x) => alive && setValue(x))
      .catch((e) => alive && setLoadError(String(e)));
    return () => {
      alive = false;
    };
  }, [api, attempt]);
  async function apply() {
    if (!value) return;
    await applyOnce.current(async () => {
      setApplying(true);
      try {
        await onApply(value);
        onStatus("空のワークスペースに切り替えました");
        onClose();
      } catch (e) {
        onStatus(String(e));
      } finally {
        setApplying(false);
      }
    });
  }
  return (
    <Modal title="空のワークスペース" onClose={onClose} locked={applying}>
      {loadError ? (
        <LoadFailure
          error={loadError}
          onRetry={() => setAttempt((v) => v + 1)}
        />
      ) : (
        <>
          <div className="dialog-body export-dialog-body">
            {value ? (
              <>
                <div className="info-card">
                  音声を外して黒い編集領域に切り替えます。既存ノートは保持されます。
                </div>
                <Field label="長さ">
                  <Num
                    value={value.duration}
                    disabled={applying}
                    min={1}
                    max={36000}
                    step={1}
                    onChange={(v) => setValue({ ...value, duration: v })}
                  />
                  <span>秒</span>
                </Field>
                <Field label="最低MIDI">
                  <Num
                    value={value.midiMin}
                    disabled={applying}
                    min={0}
                    max={127}
                    onChange={(v) =>
                      setValue({ ...value, midiMin: Math.round(v) })
                    }
                  />
                </Field>
                <Field label="最高MIDI">
                  <Num
                    value={value.midiMax}
                    disabled={applying}
                    min={0}
                    max={127}
                    onChange={(v) =>
                      setValue({ ...value, midiMax: Math.round(v) })
                    }
                  />
                </Field>
              </>
            ) : (
              <div className="dialog-loading">読み込み中…</div>
            )}
          </div>
          <div className="dialog-footer">
            <span />
            <button disabled={applying} onClick={onClose}>キャンセル</button>
            <button
              className="primary"
              onClick={() => void apply()}
              disabled={!value || applying}
            >
              適用
            </button>
          </div>
        </>
      )}
    </Modal>
  );
}

export function QuickHzDialog({ api, onClose, onStatus }: Common) {
  const appendOnce = useRef(createExclusiveAsyncAction());
  const [appending, setAppending] = useState(false);
  const [choosing, setChoosing] = useState(false);
  const [outputting, setOutputting] = useState<"copy" | "save" | null>(null);
  const [opts, setOpts] = useState<QuickHzOptions>({
    bpm: 175,
    hz: 16,
    startFloor: 0,
    useEndFloor: false,
    count: 16,
    endFloor: 16,
    addSetSpeed: true,
    overwrite: false,
  });
  const [result, setResult] = useState<QuickHzResult | null>(null),
    [resultKey, setResultKey] = useState(""),
    [error, setError] = useState(""),
    [chart, setChart] = useState("");
  const optsKey = JSON.stringify(opts), resultCurrent = previewIsCurrent(result, resultKey, optsKey);
  const busy = appending || choosing || outputting !== null;
  const actions = quickHzActionPolicy(busy, Boolean(chart), resultCurrent);
  useEffect(() => {
    let alive = true;
    const requestedKey = optsKey;
    const id = window.setTimeout(
      () =>
        void api
          .calculate_quick_hz(opts)
          .then((x) => {
            if (alive) {
              setResult(x);
              setResultKey(requestedKey);
              setError("");
            }
          })
          .catch((e) => {
            if (alive) {
              setResult(null);
              setResultKey("");
              setError(String(e));
            }
          }),
      80,
    );
    return () => {
      alive = false;
      window.clearTimeout(id);
    };
  }, [api, opts, optsKey]);
  async function chooseChart() {
    // File selection and chart append must not overlap: a late picker result
    // could otherwise change the destination while a write is in progress.
    await appendOnce.current(async () => {
      setChoosing(true);
      try {
        const x = await api.choose_quick_hz_chart();
        onStatus(x.status);
        if (x.ok && x.path) {
          setChart(x.path);
          setOpts((o) => ({
            ...o,
            startFloor: x.tailFloor ?? o.startFloor,
            endFloor: Math.max(
              o.endFloor,
              (x.tailFloor ?? 0) + Math.max(1, o.count),
            ),
          }));
        }
      } catch (e) {
        setError(String(e));
      } finally {
        setChoosing(false);
      }
    });
  }
  async function append() {
    if (!chart) {
      setError("譜面が選択されていません");
      return;
    }
    if (!resultCurrent) { setError("最新設定のプレビューを待っています"); return; }
    await appendOnce.current(async () => {
      setAppending(true);
      try {
        const x = await api.append_quick_hz_chart(chart, opts);
        if (x.ok) {
          setError("");
          onStatus(x.status);
        } else {
          setError(x.status);
        }
      } catch (e) {
        setError(String(e));
      } finally {
        setAppending(false);
      }
    });
  }
  async function copy() {
    if (!result?.output || !resultCurrent) return;
    // Share the chart action lock so a slow clipboard request cannot outlive
    // this dialog or race with a chart chooser/append.
    await appendOnce.current(async () => {
      setOutputting("copy");
      try {
        await runQuickHzOutputAction(
          "コピー",
          () => navigator.clipboard.writeText(result.output),
          () => { setError(""); onStatus("Quick Hz出力をコピーしました"); },
          setError,
        );
      } finally {
        setOutputting(null);
      }
    });
  }
  async function saveText() {
    if (!result?.output || !resultCurrent) return;
    await appendOnce.current(async () => {
      setOutputting("save");
      try {
        await runQuickHzOutputAction(
          "テキスト保存",
          () => api.save_quick_hz_text(result.output),
          x => { setError(""); onStatus(x.status); },
          setError,
        );
      } finally {
        setOutputting(null);
      }
    });
  }
  return (
    <Modal title="Quick Hz ツール" onClose={onClose} wide locked={busy}>
      <div className="dialog-body quick-hz-layout">
        <section className="tool-form">
          <Field label="BPM">
            <Num
              disabled={!actions.canEdit}
              value={opts.bpm}
              min={0.001}
              max={999999}
              onChange={(v) => setOpts({ ...opts, bpm: v })}
            />
          </Field>
          <Field label="周波数">
            <Num
              disabled={!actions.canEdit}
              value={opts.hz}
              min={0.001}
              max={100000}
              onChange={(v) => setOpts({ ...opts, hz: v })}
            />
            <span>Hz</span>
          </Field>
          <Field label="開始床">
            <Num
              disabled={!actions.canEdit}
              value={opts.startFloor}
              min={0}
              max={10000000}
              onChange={(v) => setOpts({ ...opts, startFloor: Math.round(v) })}
            />
          </Field>
          <Field label="生成範囲" group>
            <div className="compact-row">
              <label>
                <input
                  type="checkbox"
                  disabled={!actions.canEdit}
                  checked={opts.useEndFloor}
                  onChange={(e) =>
                    setOpts({ ...opts, useEndFloor: e.target.checked })
                  }
                />
                終了床で指定
              </label>
              {opts.useEndFloor ? (
                <Num
                  label="終了床"
                  disabled={!actions.canEdit}
                  value={opts.endFloor}
                  min={0}
                  max={10000000}
                  onChange={(v) =>
                    setOpts({ ...opts, endFloor: Math.round(v) })
                  }
                />
              ) : (
                <Num
                  label="生成数"
                  disabled={!actions.canEdit}
                  value={opts.count}
                  min={1}
                  max={10000000}
                  onChange={(v) => setOpts({ ...opts, count: Math.round(v) })}
                />
              )}
            </div>
          </Field>
          <Field label="SetSpeed追加">
            <input
              type="checkbox"
              disabled={!actions.canEdit}
              checked={opts.addSetSpeed}
              onChange={(e) =>
                setOpts({ ...opts, addSetSpeed: e.target.checked })
              }
            />
          </Field>
          {resultCurrent && result && (
            <div className="tool-results">
              <div>
                間隔<b>{result.info.intervalMs.toFixed(6)} ms</b>
              </div>
              <div>
                1拍<b>{result.info.beatMs.toFixed(6)} ms</b>
              </div>
              <div>
                1打あたりの拍
                <b>
                  {result.info.beatsPerHit.toFixed(9)} (
                  {result.info.beatFractionText})
                </b>
              </div>
              <div>
                相対角度<b>{result.info.relativeAngle.toFixed(9)}°</b>
              </div>
            </div>
          )}
          {error && <div className="dialog-error inline">{error}</div>}
          <div className="chart-tools">
            <button onClick={() => void chooseChart()} disabled={!actions.canChooseChart}>譜面を選択…</button>
            <span title={chart}>
              {chart ? chart.split(/[\\/]/).pop() : "未選択"}
            </span>
            <label>
              <input
                type="checkbox"
                disabled={!actions.canEdit}
                checked={opts.overwrite}
                onChange={(e) =>
                  setOpts({ ...opts, overwrite: e.target.checked })
                }
              />
              上書き
            </label>
            <button onClick={() => void append()} disabled={!actions.canAppend}>
              {appending ? "追加中…" : "末尾へ追加"}
            </button>
          </div>
        </section>
        <section className="quick-hz-output">
          <textarea value={resultCurrent ? result?.output ?? "" : ""} readOnly spellCheck={false} />
          <div className="preview-actions">
            <button onClick={() => void copy()} disabled={!actions.canOutput}>
              {outputting === "copy" ? "コピー中…" : "コピー"}
            </button>
            <button onClick={() => void saveText()} disabled={!actions.canOutput}>
              {outputting === "save" ? "保存中…" : "テキスト保存…"}
            </button>
          </div>
        </section>
      </div>
      <div className="dialog-footer">
        <span />
        <button className="primary" onClick={onClose} disabled={!actions.canClose}>
          閉じる
        </button>
      </div>
    </Modal>
  );
}

export function HarmonicDiagramDialog({
  api,
  selected,
  onClose,
  onStatus,
  onQueuedMutation,
}: Common & {
  selected: number[];
  onQueuedMutation(
    call: () => Promise<NoteMutationResult>,
    selection?: (result: NoteMutationResult) => number[] | undefined,
  ): Promise<NoteMutationResult | undefined>;
}) {
  const insertOnce = useRef(createExclusiveAsyncAction());
  const insertingRef = useRef(false);
  const [inserting, setInserting] = useState(false);
  const [opts, setOpts] = useState<HarmonicDiagramOptions | null>(null),
    [preview, setPreview] = useState<HarmonicPreview | null>(null),
    [previewKey,setPreviewKey]=useState(""),
    [error, setError] = useState(""),
    [attempt, setAttempt] = useState(0);
  const previewCurrent = previewIsCurrent(preview, previewKey, JSON.stringify(opts));
  function updateOpts(next: HarmonicDiagramOptions) {
    // A numeric field can commit on blur while disabling the form.
    if (!insertingRef.current) setOpts(next);
  }
  useEffect(() => {
    let alive = true;
    setError("");
    void api.get_harmonic_diagram_defaults(selected).then(value => alive && setOpts(value)).catch(reason => alive && setError(String(reason)));
    return () => { alive = false; };
  }, [api, selected, attempt]);
  useEffect(() => {
    if (!opts) return;
    let alive = true;
    const requestedKey=JSON.stringify(opts);
    const id = window.setTimeout(
      () =>
        void api
          .preview_harmonic_diagram(opts)
          .then((x) => {
            if (alive) {
              setPreview(x);
              setPreviewKey(requestedKey);
              setError("");
            }
          })
          .catch((e) => {
            if (alive) {
              setPreview(null);
              setPreviewKey("");
              setError(String(e));
            }
          }),
      100,
    );
    return () => {
      alive = false;
      window.clearTimeout(id);
    };
  }, [api, opts]);
  async function insert() {
    if (!opts) return;
    if(!previewCurrent){setError("最新設定のプレビューを待っています");return}
    await insertOnce.current(async () => {
      insertingRef.current = true;
      setInserting(true);
      try {
        const r = await onQueuedMutation(
          () => api.insert_harmonic_diagram(opts),
          result => result.indices ?? [],
        );
        if (!r) return;
        onStatus(r.status);
        onClose();
      } catch (e) {
        setError(String(e));
      } finally {
        insertingRef.current = false;
        setInserting(false);
      }
    });
  }
  if (!opts && error)
    return <Modal title="倍音ダイアグラム" onClose={onClose}><LoadFailure error={error} onRetry={() => setAttempt(value => value + 1)} /></Modal>;
  if (!opts)
    return (
      <Modal title="倍音ダイアグラム" onClose={onClose}>
        <div className="dialog-loading">読み込み中…</div>
      </Modal>
    );
  return (
    <Modal title="倍音ダイアグラム" onClose={onClose} wide locked={inserting}>
      <div className="dialog-body harmonic-layout">
        <fieldset className="tool-form harmonic-form" disabled={inserting}>
          <Field label="基準周波数">
            <Num
              value={opts.rootHz}
              min={0.001}
              max={100000}
              onChange={(v) => updateOpts({ ...opts, rootHz: v })}
            />
            <span>Hz</span>
          </Field>
          <Field label="基準倍率">
            <input
              value={opts.rootShift}
              onChange={(e) => updateOpts({ ...opts, rootShift: e.target.value })}
            />
          </Field>
          <Field label="1次元オフセット">
            <Num
              value={opts.base1dOffset}
              min={-64}
              max={64}
              onChange={(v) =>
                updateOpts({ ...opts, base1dOffset: Math.round(v) })
              }
            />
          </Field>
          <Field label="倍音列">
            <input
              value={opts.harmonics}
              onChange={(e) => updateOpts({ ...opts, harmonics: e.target.value })}
            />
          </Field>
          <Field label="時間単位">
            <select
              value={opts.timeUnit}
              onChange={(e) =>
                updateOpts({
                  ...opts,
                  timeUnit: e.target.value as "seconds" | "beats",
                })
              }
            >
              <option value="seconds">秒</option>
              <option value="beats">拍</option>
            </select>
          </Field>
          <Field label="BPM">
            <Num
              value={opts.bpm}
              min={1}
              max={2000}
              disabled={opts.timeUnit !== "beats"}
              onChange={(v) => updateOpts({ ...opts, bpm: v })}
            />
          </Field>
          <Field label="開始">
            <Num
              value={opts.start}
              min={0}
              max={36000}
              step={0.25}
              onChange={(v) => updateOpts({ ...opts, start: v })}
            />
          </Field>
          <Field label="長さ">
            <Num
              value={opts.duration}
              min={0.001}
              max={36000}
              step={0.25}
              onChange={(v) => updateOpts({ ...opts, duration: v })}
            />
          </Field>
          <Field label="EDO">
            <Num
              value={opts.edo}
              min={1}
              max={999}
              onChange={(v) => updateOpts({ ...opts, edo: Math.round(v) })}
            />
          </Field>
          <Field label="番号オフセット">
            <Num
              value={opts.offset}
              min={-999}
              max={999}
              onChange={(v) => updateOpts({ ...opts, offset: Math.round(v) })}
            />
          </Field>
          {error && <div className="dialog-error inline">{error}</div>}
        </fieldset>
        <section className="harmonic-preview">
          {previewCurrent && preview ? (
            <>
              <div className="preview-summary">
                {preview.startSeconds.toFixed(6)}秒 –{" "}
                {preview.endSeconds.toFixed(6)}秒
              </div>
              {preview.rows.map((r, i) => (
                <div className="harmonic-row" key={i}>
                  <b>#{r.pitchNumber}</b>
                  <span>{r.local}</span>
                  <span>{r.ratio}</span>
                  <span>{r.hz.toFixed(6)} Hz</span>
                  <span>MIDI {r.midi.toFixed(6)}</span>
                </div>
              ))}
            </>
          ) : (
            <div className="dialog-loading" role="status">
              {error ? "プレビューを表示できません" : "プレビューを計算中…"}
            </div>
          )}
        </section>
      </div>
      <div className="dialog-footer">
        <span />
        <button onClick={onClose} disabled={inserting}>キャンセル</button>
        <button
          className="primary"
          onClick={() => void insert()}
          disabled={inserting || !previewCurrent}
        >
          {inserting ? "挿入中…" : "挿入"}
        </button>
      </div>
    </Modal>
  );
}

export function LanguageDialog({ onClose }: Common) {
  return (
    <Modal title="言語" onClose={onClose}>
      <div className="dialog-body export-dialog-body">
        <div className="info-card">Web UIは日本語表示に統一されています。</div>
      </div>
      <div className="dialog-footer">
        <span />
        <button className="primary" onClick={onClose}>
          閉じる
        </button>
      </div>
    </Modal>
  );
}
export function UpdateDialog({ api, onClose, onStatus }: Common) {
  const [info, setInfo] = useState<{
    version: string;
    text: string;
    info: string;
  } | null>(null), [error, setError] = useState(""), [attempt, setAttempt] = useState(0);
  const [openError, setOpenError] = useState(""), [opening, setOpening] = useState(false);
  const openOnce = useRef(createExclusiveAsyncAction());
  useEffect(() => {
    let alive=true;setError("");
    void api.get_update_info().then(value=>alive&&setInfo(value)).catch(reason=>alive&&setError(String(reason)));
    return()=>{alive=false};
  }, [api,attempt]);
  async function open() {
    await openOnce.current(async () => {
      setOpening(true);
      setOpenError("");
      try {
        await runReleasePageAction(
          () => api.open_releases_page(),
          () => { onStatus("リリースページを開きました"); onClose(); },
          setOpenError,
        );
      } finally {
        setOpening(false);
      }
    });
  }
  return (
    <Modal title="更新を確認" onClose={onClose} locked={opening}>
      <div className="dialog-body export-dialog-body">
        {error ? <LoadFailure error={error} onRetry={()=>setAttempt(value=>value+1)}/> : info ? (
          <>
            <div className="info-card">現在のバージョン: {info.version}</div>
            <div className="info-card">{info.text}</div>
            <div className="info-card">{info.info}</div>
          </>
        ) : (
          <div className="dialog-loading">確認中…</div>
        )}
        {openError && <div className="dialog-error" role="alert">{openError}</div>}
      </div>
      <div className="dialog-footer">
        <span />
        <button onClick={onClose} disabled={opening}>あとで</button>
        <button className="primary" disabled={opening} onClick={() => void open()}>
          リリースページを開く
        </button>
      </div>
    </Modal>
  );
}
