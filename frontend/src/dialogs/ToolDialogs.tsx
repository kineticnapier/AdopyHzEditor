import { useEffect, useRef, useState, type ReactNode } from "react";
import type { EditorSettings, MidiTrackSummary, NoteMutationResult } from "./bridge";
import { midiLabel } from "../editor/musicMath";
import type {
  BlankWorkspaceOptions,
  Preferences,
  ToolBackendApi,
  UpdateCheck,
} from "./toolsBridge";
import { useDialogAccessibility } from "./useDialogAccessibility";
import { isDialogCompositionKey, isPlainDialogEscape } from "./dialogFocus";
import { commitNumericEdit } from "../settings/numericInputModel";
import { runReleasePageAction } from "./releasePageAction";
import { createExclusiveAsyncAction } from "./exclusiveAsyncAction";
import { blankWorkspaceDefaultsContextIsCurrent, blankWorkspaceMidiRangeIsValid } from "./previewFreshness";
import { dismissUnlessBusy } from "./dialogClosePolicy";
import { setLanguage } from "../i18n/index.ts";
import { changedNewProject, effectiveNewProject, updateCheckMessage, type NewProjectValues } from "./preferencesModel";
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

export function MidiTrackDialog({
  fileName,
  tracks,
  onImport,
  onClose,
}: {
  fileName: string;
  tracks: MidiTrackSummary[];
  onImport(trackIndices: number[]): void;
  onClose(): void;
}) {
  // Drum-like tracks start unchecked: their note numbers are drum sounds,
  // not pitches, so they would add bogus notes and chords.
  const [checked, setChecked] = useState<Set<number>>(
    () => new Set(tracks.filter((t) => !t.drums).map((t) => t.index)),
  );
  const toggle = (index: number, on: boolean) =>
    setChecked((prev) => {
      const next = new Set(prev);
      if (on) next.add(index);
      else next.delete(index);
      return next;
    });
  const chosen = tracks.filter((t) => checked.has(t.index));
  const noteTotal = chosen.reduce((sum, t) => sum + t.noteCount, 0);
  const range = (t: MidiTrackSummary) =>
    t.lowest === null || t.highest === null
      ? ""
      : t.lowest === t.highest
        ? midiLabel(t.lowest)
        : `${midiLabel(t.lowest)}〜${midiLabel(t.highest)}`;
  return (
    <Modal title="MIDIトラックを選択" onClose={onClose}>
      <div className="dialog-body export-dialog-body">
        <div className="info-card">
          {fileName} から読み込むトラックを選んでください。ドラムらしいトラックは最初から外してあります。
        </div>
        <div className="midi-track-list" role="group" aria-label="読み込むトラック">
          {tracks.map((t) => (
            <label key={t.index} className="inline-check midi-track-row">
              <input
                type="checkbox"
                checked={checked.has(t.index)}
                onChange={(e) => toggle(t.index, e.target.checked)}
              />
              <span className="midi-track-name">{t.name}</span>
              <span className="midi-track-meta">
                {t.noteCount}ノート
                {range(t) && ` / ${range(t)}`}
                {t.channels.length > 0 && ` / ch ${t.channels.join(",")}`}
                {t.drums && " / ドラム"}
              </span>
            </label>
          ))}
        </div>
        <div className="info-card">
          各トラックはレイヤーとして読み込まれます。読み込んだあとも、インスペクタのレイヤー一覧で使うレイヤーを切り替えられます。
        </div>
        <div className="midi-track-actions">
          <button type="button" onClick={() => setChecked(new Set(tracks.map((t) => t.index)))}>
            すべて選択
          </button>
          <button type="button" onClick={() => setChecked(new Set())}>
            すべて解除
          </button>
        </div>
      </div>
      <div className="dialog-footer">
        <span>
          {chosen.length}トラック / {noteTotal}ノート
        </span>
        <button onClick={onClose}>キャンセル</button>
        <button
          className="primary"
          disabled={chosen.length === 0}
          onClick={() => onImport(chosen.map((t) => t.index))}
        >
          読み込む
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
  type UpdateInfo = UpdateCheck;
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
    void api.check_for_update()
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
            <div className="info-card">現在のバージョン: {currentInfo.current}</div>
            <div className="info-card">{updateCheckMessage(currentInfo)}</div>
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

const LANGUAGE_LABELS: Record<string, string> = { ja: "日本語", en: "English" };
const PREVIEW_SOUND_OPTIONS: Array<[string, string]> = [
  ["sine", "サイン波"],
  ["piano", "ピアノ"],
  ["organ", "オルガン"],
  ["square", "矩形波"],
  ["triangle", "三角波"],
  ["adofai_kick", "ADOFAI Kick"],
];
const COLORMAP_OPTIONS: Array<[string, string]> = [
  ["wavetone", "WaveTone"],
  ["viridis", "Viridis"],
  ["magma", "Magma"],
  ["inferno", "Inferno"],
  ["plasma", "Plasma"],
  ["gray", "グレー"],
];
export function PreferencesDialog({
  api,
  settings,
  onClose,
  onStatus,
}: Common & { settings: EditorSettings }) {
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [language, setLanguage] = useState("ja");
  const [values, setValues] = useState<NewProjectValues | null>(null);
  const [kpsLimit, setKpsLimit] = useState(200);
  const [checkUpdates, setCheckUpdates] = useState(false);
  const [reopenLastProject, setReopenLastProject] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let alive = true;
    setError("");
    void api.get_preferences()
      .then(value => {
        if (!alive) return;
        setPrefs(value);
        setLanguage(value.language);
        setValues(effectiveNewProject(value));
        setKpsLimit(value.kpsLimit);
        setCheckUpdates(value.checkUpdates);
        setReopenLastProject(value.reopenLastProject);
      })
      .catch(reason => {
        if (alive) setError(String(reason));
      });
    return () => { alive = false; };
  }, [api, attempt]);

  if (!prefs || !values) {
    return (
      <Modal title="環境設定" onClose={onClose}>
        {error ? (
          <LoadFailure error={error} onRetry={() => setAttempt(v => v + 1)} />
        ) : (
          <div className="dialog-loading" role="status">読み込んでいます…</div>
        )}
      </Modal>
    );
  }
  const loaded = prefs;
  const set = <K extends keyof NewProjectValues>(key: K, value: NewProjectValues[K]) =>
    setValues(current => (current ? { ...current, [key]: value } : current));

  function takeCurrentSettings() {
    const next = { ...values! };
    for (const key of Object.keys(loaded.newProjectBuiltin) as Array<keyof NewProjectValues>) {
      (next as Record<string, unknown>)[key] = (settings as unknown as Record<string, unknown>)[key];
    }
    setValues(next);
  }
  async function clearExportDefaults() {
    setSaving(true);
    try {
      setPrefs(await api.clear_adofai_export_defaults());
      onStatus("ADOFAI書き出しの既定値を元に戻しました");
    } catch (reason) {
      setError(String(reason));
    } finally {
      setSaving(false);
    }
  }
  async function save() {
    setSaving(true);
    setError("");
    try {
      await api.set_preferences({
        language,
        newProject: changedNewProject(values!, loaded.newProjectBuiltin),
        kpsLimit,
        checkUpdates,
        reopenLastProject,
      });
      setLanguage(language);
      onStatus("環境設定を保存しました");
      onClose();
    } catch (reason) {
      setError(String(reason));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title="環境設定" onClose={onClose} locked={saving}>
      <div className="dialog-body export-dialog-body preferences-body">
        <section className="preferences-section">
          <h3>言語</h3>
          <Field label="言語">
            <select value={language} disabled={saving} onChange={e => setLanguage(e.target.value)}>
              {loaded.languages.map(code => (
                <option key={code} value={code}>{LANGUAGE_LABELS[code] ?? code}</option>
              ))}
            </select>
          </Field>
          <p className="dialog-note">メニュー、ツールバー、右パネル、ヘルプが切り替わります。ダイアログとメッセージは日本語のままです（順に対応します）。</p>
        </section>

        <section className="preferences-section">
          <h3>新しいプロジェクトの初期値</h3>
          <p className="dialog-note">アプリを起動したときの最初の状態に使います。保存済みのプロジェクトを開いたときは、そのプロジェクトの設定が優先されます。</p>
          <Field label="BPM">
            <Num label="BPM" value={Number(values.bpm)} min={1} max={10000} step="any" disabled={saving} onChange={v => set("bpm", v)} />
          </Field>
          <Field label="グリッド">
            <input type="checkbox" checked={Boolean(values.gridEnabled)} disabled={saving} onChange={e => set("gridEnabled", e.target.checked)} />
          </Field>
          <Field label="スナップ">
            <input type="checkbox" checked={Boolean(values.snapEnabled)} disabled={saving} onChange={e => set("snapEnabled", e.target.checked)} />
          </Field>
          <Field label="分割数">
            <Num label="分割数" value={Number(values.snapDiv)} min={1} max={64} disabled={saving} onChange={v => set("snapDiv", v)} />
          </Field>
          <Field label="出力オクターブ">
            <Num label="出力オクターブ" value={Number(values.exportOctave)} min={-4} max={4} disabled={saving} onChange={v => set("exportOctave", v)} />
          </Field>
          <Field label="試聴音色">
            <select value={String(values.previewSound)} disabled={saving} onChange={e => set("previewSound", e.target.value)}>
              {PREVIEW_SOUND_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </Field>
          <Field label="試聴音量">
            <Num label="試聴音量" value={Number(values.previewVolume)} min={0} max={100} disabled={saving} onChange={v => set("previewVolume", v)} />
          </Field>
          <Field label="配色">
            <select value={String(values.colormap)} disabled={saving} onChange={e => set("colormap", e.target.value)}>
              {COLORMAP_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </Field>
          <div className="preferences-actions">
            <button className="quiet" disabled={saving} onClick={takeCurrentSettings}>今のプロジェクトの値を入れる</button>
            <button className="quiet" disabled={saving} onClick={() => setValues({ ...loaded.newProjectBuiltin })}>初期値に戻す</button>
          </div>
        </section>

        <section className="preferences-section">
          <h3>ADOFAI書き出し</h3>
          <Field label="KPS警告のしきい値">
            <Num label="KPS警告のしきい値" value={kpsLimit} min={1} max={100000} step="any" disabled={saving} onChange={setKpsLimit} />
          </Field>
          <Field label="書き出し設定の既定値" group>
            <span>{loaded.hasExportDefaults ? "保存した値を使っています" : "最初からの値を使っています"}</span>
            <button className="quiet" disabled={saving || !loaded.hasExportDefaults} onClick={() => void clearExportDefaults()}>元に戻す</button>
          </Field>
          <p className="dialog-note">書き出しダイアログの「既定にする」で、その時の設定を次から最初に入る値にできます。</p>
        </section>

        <section className="preferences-section">
          <h3>起動時</h3>
          <label className="preferences-check">
            <input type="checkbox" checked={checkUpdates} disabled={saving} onChange={e => setCheckUpdates(e.target.checked)} />
            新しいバージョンを確認する（GitHub に問い合わせます）
          </label>
          <label className="preferences-check">
            <input type="checkbox" checked={reopenLastProject} disabled={saving} onChange={e => setReopenLastProject(e.target.checked)} />
            前回のプロジェクトを開く
          </label>
          {loaded.lastProject && <p className="dialog-note">前回: {loaded.lastProject}</p>}
        </section>
        {error && <div className="dialog-error" role="alert">{error}</div>}
      </div>
      <div className="dialog-footer">
        <span />
        <button onClick={onClose} disabled={saving}>キャンセル</button>
        <button className="primary" onClick={() => void save()} disabled={saving}>保存</button>
      </div>
    </Modal>
  );
}
