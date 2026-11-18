import { useEffect, useRef, useState, type ReactNode } from "react";
import type { NoteMutationResult } from "./bridge";
import type {
  BlankWorkspaceOptions,
  HarmonicDiagramOptions,
  HarmonicPreview,
  ToolBackendApi,
} from "./toolsBridge";
import { useDialogAccessibility } from "./useDialogAccessibility";
import { isDialogCompositionKey, isPlainDialogEscape } from "./dialogFocus";
import { commitNumericEdit } from "../settings/numericInputModel";
import { runReleasePageAction } from "./releasePageAction";
import { createExclusiveAsyncAction } from "./exclusiveAsyncAction";
import { blankWorkspaceDefaultsContextIsCurrent, blankWorkspaceMidiRangeIsValid, documentActionIsCurrent, harmonicDefaultsContextIsCurrent, harmonicErrorIsCurrent, previewIsCurrent, selectionScopedPreviewIsCurrent } from "./previewFreshness";
import { dismissUnlessBusy } from "./dialogClosePolicy";
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
  step?: number | "any";
  disabled?: boolean;
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
    if (disabled) {
      // Disabling a focused input can fire blur after an action has started.
      cancelledRef.current = false;
      editedRef.current = false;
      setEditing(false);
      setText(String(fallback));
      return;
    }
    const next = commitNumericEdit(text, fallback, min, max, cancelledRef.current, step === 1, editedRef.current);
    cancelledRef.current = false;
    editedRef.current = false;
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
  );
}
function LoadFailure({ error, onRetry, disabled = false }: { error: string; onRetry(): void; disabled?: boolean }) {
  return (
    <>
      <div className="dialog-error" role="alert">読込に失敗しました: {error}</div>
      <div className="dialog-footer">
        <span />
        <button className="primary" onClick={onRetry} disabled={disabled}>
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
    [loadedContext, setLoadedContext] = useState<{ api: ToolBackendApi; attempt: number } | null>(null),
    [loadError, setLoadError] = useState<{ message: string; api: ToolBackendApi; attempt: number } | null>(null),
    [attempt, setAttempt] = useState(0),
    [applying, setApplying] = useState(false);
  // An API replacement or retry must hide the previous defaults during render,
  // before React runs the cleanup/reset effect.
  const requestContext = { api, attempt };
  // Async completion must check the latest API, not the render that started it.
  const latestRequestContext = useRef(requestContext);
  latestRequestContext.current = requestContext;
  const defaultsCurrent = blankWorkspaceDefaultsContextIsCurrent(loadedContext, requestContext);
  const midiRangeValid = blankWorkspaceMidiRangeIsValid(value);
  const currentLoadError = blankWorkspaceDefaultsContextIsCurrent(loadError, requestContext)
    ? loadError!.message : "";
  useEffect(() => {
    let alive = true;
    setValue(null);
    setLoadedContext(null);
    setLoadError(null);
    void api
      .get_blank_workspace_defaults()
      .then((x) => {
        if (!alive) return;
        setValue(x);
        setLoadedContext({ api, attempt });
      })
      .catch((e) => {
        if (!alive) return;
        setValue(null);
        setLoadedContext(null);
        setLoadError({ message: String(e), api, attempt });
      });
    return () => {
      alive = false;
    };
  }, [api, attempt]);
  function patchValue(changes: Partial<BlankWorkspaceOptions>) {
    if (!defaultsCurrent || applying) return;
    setValue((current) => current ? { ...current, ...changes } : current);
  }
  async function apply() {
    if (!value || !defaultsCurrent || applying || !midiRangeValid) return;
    const snapshot = { ...value };
    await applyOnce.current(async () => {
      setApplying(true);
      try {
        await onApply(snapshot);
        if (!blankWorkspaceDefaultsContextIsCurrent(loadedContext, latestRequestContext.current)) return;
        onStatus("空のワークスペースに切り替えました");
        onClose();
      } catch (e) {
        if (blankWorkspaceDefaultsContextIsCurrent(loadedContext, latestRequestContext.current)) onStatus(String(e));
      } finally {
        setApplying(false);
      }
    });
  }
  return (
    <Modal title="空のワークスペース" onClose={onClose} locked={applying}>
      {currentLoadError ? (
        <LoadFailure
          error={currentLoadError}
          onRetry={() => setAttempt((v) => v + 1)}
          disabled={applying}
        />
      ) : (
        <>
          <div className="dialog-body export-dialog-body">
            {value && defaultsCurrent ? (
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
                    step="any"
                    onChange={(v) => patchValue({ duration: v })}
                  />
                  <span>秒</span>
                </Field>
                <Field label="最低MIDI">
                  <Num
                    value={value.midiMin}
                    disabled={applying}
                    min={0}
                    max={127}
                    onChange={(v) => patchValue({ midiMin: Math.round(v) })}
                  />
                </Field>
                <Field label="最高MIDI">
                  <Num
                    value={value.midiMax}
                    disabled={applying}
                    min={0}
                    max={127}
                    onChange={(v) => patchValue({ midiMax: Math.round(v) })}
                  />
                </Field>
                {!midiRangeValid && (
                  <div className="dialog-error inline" role="alert">
                    最低MIDIは最高MIDIより小さくしてください。
                  </div>
                )}
              </>
            ) : (
              <div className="dialog-loading" role="status">読み込み中…</div>
            )}
          </div>
          <div className="dialog-footer">
            <span />
            <button disabled={applying} onClick={onClose}>キャンセル</button>
            <button
              className="primary"
              onClick={() => void apply()}
              disabled={!value || !defaultsCurrent || applying || !midiRangeValid}
            >
              適用
            </button>
          </div>
        </>
      )}
    </Modal>
  );
}

export function HarmonicDiagramDialog({
  api,
  selected,
  documentGeneration,
  onClose,
  onStatus,
  onQueuedMutation,
}: Common & {
  selected: number[];
  documentGeneration: number;
  onQueuedMutation(
    call: () => Promise<NoteMutationResult>,
    selection?: (result: NoteMutationResult) => number[] | undefined,
  ): Promise<NoteMutationResult | undefined>;
}) {
  const insertOnce = useRef(createExclusiveAsyncAction());
  // A completed insertion may legitimately change selection; only API/document changes invalidate its completion.
  const latestDocumentContext = useRef({ api, documentGeneration });
  latestDocumentContext.current = { api, documentGeneration };
  const insertingRef = useRef(false);
  const [inserting, setInserting] = useState(false);
  const [opts, setOpts] = useState<HarmonicDiagramOptions | null>(null),
    [preview, setPreview] = useState<HarmonicPreview | null>(null),
    [previewKey,setPreviewKey]=useState(""),
    [defaultsSelectionKey, setDefaultsSelectionKey] = useState<string | null>(null),
    [defaultsContext, setDefaultsContext] = useState<{ api: ToolBackendApi; selected: number[]; attempt: number; documentGeneration: number } | null>(null),
    [error, setError] = useState<{ message: string; api: ToolBackendApi; selected: number[]; attempt: number; documentGeneration: number; optionsKey?: string } | null>(null),
    [attempt, setAttempt] = useState(0);
  const currentError = harmonicDefaultsContextIsCurrent(error, { api, selected, attempt, documentGeneration }) &&
    harmonicErrorIsCurrent(error, opts ? JSON.stringify(opts) : null)
    ? error!.message : "";
  const selectionKey = JSON.stringify(selected);
  const selectionCurrent = defaultsSelectionKey === selectionKey &&
    harmonicDefaultsContextIsCurrent(defaultsContext, { api, selected, attempt, documentGeneration });
  const previewCurrent = selectionCurrent && selectionScopedPreviewIsCurrent(preview, previewKey, JSON.stringify(opts), defaultsSelectionKey, selectionKey);
  function updateOpts(next: HarmonicDiagramOptions) {
    // A numeric field can commit on blur while disabling the form.
    if (!insertingRef.current && selectionCurrent) {
      setError(null);
      setOpts(next);
    }
  }
  useEffect(() => {
    let alive = true;
    // Selection-dependent defaults are invalid as soon as the selection changes.
    // Do not allow inserting the previous selection's diagram while loading.
    setOpts(null);
    setDefaultsSelectionKey(null);
    setDefaultsContext(null);
    setPreview(null);
    setPreviewKey("");
    setError(null);
    void api.get_harmonic_diagram_defaults(selected).then(value => {
      if (alive) {
        setOpts(value);
        setDefaultsSelectionKey(selectionKey);
        setDefaultsContext({ api, selected, attempt, documentGeneration });
      }
    }).catch(reason => alive && setError({ message: String(reason), api, selected, attempt, documentGeneration }));
    return () => { alive = false; };
  }, [api, selected, attempt, documentGeneration]);
  useEffect(() => {
    if (!opts || !selectionCurrent) return;
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
              setError(null);
            }
          })
          .catch((e) => {
            if (alive) {
              setPreview(null);
              setPreviewKey("");
              setError({ message: String(e), api, selected, attempt, documentGeneration, optionsKey: requestedKey });
            }
          }),
      100,
    );
    return () => {
      alive = false;
      window.clearTimeout(id);
    };
  }, [api, opts, selected, attempt, documentGeneration, selectionCurrent]);
  async function insert() {
    if (!opts || !selectionCurrent) return;
    if(!previewCurrent){setError({ message: "最新設定のプレビューを待っています", api, selected, attempt, documentGeneration, optionsKey: JSON.stringify(opts) });return}
    const startedDocument = { api, documentGeneration };
    await insertOnce.current(async () => {
      insertingRef.current = true;
      setInserting(true);
      try {
        const r = await onQueuedMutation(
          () => api.insert_harmonic_diagram(opts),
          result => result.indices ?? [],
        );
        if (!r) return;
        if (!documentActionIsCurrent(startedDocument, latestDocumentContext.current)) return;
        onStatus(r.status);
        onClose();
      } catch (e) {
        if (documentActionIsCurrent(startedDocument, latestDocumentContext.current)) {
          setError({ message: String(e), api, selected, attempt, documentGeneration, optionsKey: JSON.stringify(opts) });
        }
      } finally {
        insertingRef.current = false;
        setInserting(false);
      }
    });
  }
  if (!opts && currentError)
    return <Modal title="倍音ダイアグラム" onClose={onClose} locked={inserting}><LoadFailure error={currentError} onRetry={() => setAttempt(value => value + 1)} disabled={inserting} /></Modal>;
  if (!opts || !selectionCurrent)
    return (
      <Modal title="倍音ダイアグラム" onClose={onClose} locked={inserting}>
        <div className="dialog-loading" role="status">{inserting ? "挿入処理中…" : "読み込み中…"}</div>
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
              step="any"
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
              step="any"
              disabled={opts.timeUnit !== "beats"}
              onChange={(v) => updateOpts({ ...opts, bpm: v })}
            />
          </Field>
          <Field label="開始">
            <Num
              value={opts.start}
              min={0}
              max={36000}
              step="any"
              onChange={(v) => updateOpts({ ...opts, start: v })}
            />
          </Field>
          <Field label="長さ">
            <Num
              value={opts.duration}
              min={0.001}
              max={36000}
              step="any"
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
          {currentError && <div className="dialog-error inline" role="alert">{currentError}</div>}
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
              {currentError ? "プレビューを表示できません" : "プレビューを計算中…"}
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
  type UpdateInfo = { version: string; text: string; info: string };
  type RequestContext = { api: ToolBackendApi; attempt: number };
  const [info, setInfo] = useState<(RequestContext & { value: UpdateInfo }) | null>(null);
  const [error, setError] = useState<(RequestContext & { message: string }) | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [openError, setOpenError] = useState<(RequestContext & { message: string }) | null>(null);
  const [opening, setOpening] = useState(false);
  const openOnce = useRef(createExclusiveAsyncAction());
  const context: RequestContext = { api, attempt };
  const latestContext = useRef(context);
  latestContext.current = context;
  // Hide results from a previous API or retry during render, before effect cleanup.
  const currentInfo = blankWorkspaceDefaultsContextIsCurrent(info, context) ? info!.value : null;
  const currentError = blankWorkspaceDefaultsContextIsCurrent(error, context) ? error!.message : "";
  const currentOpenError = blankWorkspaceDefaultsContextIsCurrent(openError, context) ? openError!.message : "";

  useEffect(() => {
    let alive = true;
    setInfo(null);
    setError(null);
    setOpenError(null);
    void api.get_update_info()
      .then(value => {
        if (alive) setInfo({ api, attempt, value });
      })
      .catch(reason => {
        if (alive) setError({ api, attempt, message: String(reason) });
      });
    return () => { alive = false; };
  }, [api, attempt]);

  async function open() {
    await openOnce.current(async () => {
      setOpening(true);
      setOpenError(null);
      try {
        await runReleasePageAction(
          () => api.open_releases_page(),
          () => {
            if (!blankWorkspaceDefaultsContextIsCurrent(context, latestContext.current)) return;
            onStatus("リリースページを開きました");
            onClose();
          },
          message => {
            if (blankWorkspaceDefaultsContextIsCurrent(context, latestContext.current))
              setOpenError({ ...context, message });
          },
        );
      } finally {
        setOpening(false);
      }
    });
  }
  return (
    <Modal title="更新を確認" onClose={onClose} locked={opening}>
      <div className="dialog-body export-dialog-body">
        {currentError ? (
          <LoadFailure error={currentError} onRetry={() => setAttempt(value => value + 1)} disabled={opening} />
        ) : currentInfo ? (
          <>
            <div className="info-card">現在のバージョン: {currentInfo.version}</div>
            <div className="info-card">{currentInfo.text}</div>
            <div className="info-card">{currentInfo.info}</div>
          </>
        ) : (
          <div className="dialog-loading" role="status">確認中…</div>
        )}
        {currentOpenError && <div className="dialog-error" role="alert">{currentOpenError}</div>}
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
