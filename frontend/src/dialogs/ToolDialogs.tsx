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
import { setLanguage, t } from "../i18n/index.ts";
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
          <button aria-label={t("dialog.close")} disabled={locked} onClick={close}>
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
      <div className="dialog-error" role="alert">{t("dialog.load_failed", { error })}</div>
      <div className="dialog-footer">
        <span />
        <button className="primary" onClick={onRetry} disabled={disabled}>
          {t("dialog.retry")}
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
        onStatus(t("blank.switched"));
        onClose();
      } catch (e) {
        if (blankWorkspaceDefaultsContextIsCurrent(loadedContext, latestRequestContext.current)) onStatus(String(e));
      } finally {
        setApplying(false);
      }
    });
  }
  return (
    <Modal title={t("blank.title")} onClose={onClose} locked={applying}>
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
                  {t("blank.info")}
                </div>
                <Field label={t("blank.length")}>
                  <Num
                    value={value.duration}
                    disabled={applying}
                    min={1}
                    max={36000}
                    step="any"
                    onChange={(v) => patchValue({ duration: v })}
                  />
                  <span>{t("dialog.seconds")}</span>
                </Field>
                <Field label={t("blank.midi_min")}>
                  <Num
                    value={value.midiMin}
                    disabled={applying}
                    min={0}
                    max={127}
                    onChange={(v) => patchValue({ midiMin: Math.round(v) })}
                  />
                </Field>
                <Field label={t("blank.midi_max")}>
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
                    {t("blank.midi_order")}
                  </div>
                )}
              </>
            ) : (
              <div className="dialog-loading" role="status">{t("dialog.loading")}</div>
            )}
          </div>
          <div className="dialog-footer">
            <span />
            <button disabled={applying} onClick={onClose}>{t("dialog.cancel")}</button>
            <button
              className="primary"
              onClick={() => void apply()}
              disabled={!value || !defaultsCurrent || applying || !midiRangeValid}
            >
              {t("dialog.apply")}
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
  const chosen = tracks.filter((track) => checked.has(track.index));
  const noteTotal = chosen.reduce((sum, track) => sum + track.noteCount, 0);
  const range = (track: MidiTrackSummary) =>
    track.lowest === null || track.highest === null
      ? ""
      : track.lowest === track.highest
        ? midiLabel(track.lowest)
        : `${midiLabel(track.lowest)}〜${midiLabel(track.highest)}`;
  return (
    <Modal title={t("midi.title")} onClose={onClose}>
      <div className="dialog-body export-dialog-body">
        <div className="info-card">
          {t("midi.info", { file: fileName })}
        </div>
        <div className="midi-track-list" role="group" aria-label={t("midi.tracks")}>
          {tracks.map((track) => (
            <label key={track.index} className="inline-check midi-track-row">
              <input
                type="checkbox"
                checked={checked.has(track.index)}
                onChange={(e) => toggle(track.index, e.target.checked)}
              />
              <span className="midi-track-name">{track.name}</span>
              <span className="midi-track-meta">
                {t("midi.notes", { count: track.noteCount })}
                {range(track) && ` / ${range(track)}`}
                {track.channels.length > 0 && ` / ch ${track.channels.join(",")}`}
                {track.drums && t("midi.drums")}
              </span>
            </label>
          ))}
        </div>
        <div className="info-card">
          {t("midi.layers_info")}
        </div>
        <div className="midi-track-actions">
          <button type="button" onClick={() => setChecked(new Set(tracks.map((t) => t.index)))}>
            {t("midi.select_all")}
          </button>
          <button type="button" onClick={() => setChecked(new Set())}>
            {t("midi.select_none")}
          </button>
        </div>
      </div>
      <div className="dialog-footer">
        <span>
          {t("midi.summary", { tracks: chosen.length, notes: noteTotal })}
        </span>
        <button onClick={onClose}>{t("dialog.cancel")}</button>
        <button
          className="primary"
          disabled={chosen.length === 0}
          onClick={() => onImport(chosen.map((t) => t.index))}
        >
          {t("midi.import")}
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
            onStatus(t("update.opened"));
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
    <Modal title={t("update.title")} onClose={onClose} locked={opening}>
      <div className="dialog-body export-dialog-body">
        {currentError ? (
          <LoadFailure error={currentError} onRetry={() => setAttempt(value => value + 1)} disabled={opening} />
        ) : currentInfo ? (
          <>
            <div className="info-card">{t("update.current", { version: currentInfo.current })}</div>
            <div className="info-card">{updateCheckMessage(currentInfo)}</div>
          </>
        ) : (
          <div className="dialog-loading" role="status">{t("update.checking")}</div>
        )}
        {currentOpenError && <div className="dialog-error" role="alert">{currentOpenError}</div>}
      </div>
      <div className="dialog-footer">
        <span />
        <button onClick={onClose} disabled={opening}>{t("update.later")}</button>
        <button className="primary" disabled={opening} onClick={() => void open()}>
          {t("update.open_page")}
        </button>
      </div>
    </Modal>
  );
}

const LANGUAGE_LABELS: Record<string, string> = { ja: "日本語", en: "English" };
const previewSoundOptions = (): Array<[string, string]> => [
  ["sine", t("panel.sound_sine")],
  ["piano", t("panel.sound_piano")],
  ["organ", t("panel.sound_organ")],
  ["square", t("panel.sound_square")],
  ["triangle", t("panel.sound_triangle")],
  ["adofai_kick", "ADOFAI Kick"],
];
const colormapOptions = (): Array<[string, string]> => [
  ["wavetone", "WaveTone"],
  ["viridis", "Viridis"],
  ["magma", "Magma"],
  ["inferno", "Inferno"],
  ["plasma", "Plasma"],
  ["gray", t("prefs.gray")],
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
      <Modal title={t("prefs.title")} onClose={onClose}>
        {error ? (
          <LoadFailure error={error} onRetry={() => setAttempt(v => v + 1)} />
        ) : (
          <div className="dialog-loading" role="status">{t("prefs.loading")}</div>
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
      onStatus(t("prefs.export_cleared"));
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
      onStatus(t("prefs.saved"));
      onClose();
    } catch (reason) {
      setError(String(reason));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title={t("prefs.title")} onClose={onClose} locked={saving}>
      <div className="dialog-body export-dialog-body preferences-body">
        <section className="preferences-section">
          <h3>{t("prefs.language")}</h3>
          <Field label={t("prefs.language")}>
            <select value={language} disabled={saving} onChange={e => setLanguage(e.target.value)}>
              {loaded.languages.map(code => (
                <option key={code} value={code}>{LANGUAGE_LABELS[code] ?? code}</option>
              ))}
            </select>
          </Field>
          <p className="dialog-note">{t("prefs.language_note")}</p>
        </section>

        <section className="preferences-section">
          <h3>{t("prefs.new_project")}</h3>
          <p className="dialog-note">{t("prefs.new_project_note")}</p>
          <Field label="BPM">
            <Num label="BPM" value={Number(values.bpm)} min={1} max={10000} step="any" disabled={saving} onChange={v => set("bpm", v)} />
          </Field>
          <Field label={t("prefs.grid")}>
            <input type="checkbox" checked={Boolean(values.gridEnabled)} disabled={saving} onChange={e => set("gridEnabled", e.target.checked)} />
          </Field>
          <Field label={t("prefs.snap")}>
            <input type="checkbox" checked={Boolean(values.snapEnabled)} disabled={saving} onChange={e => set("snapEnabled", e.target.checked)} />
          </Field>
          <Field label={t("prefs.divisions")}>
            <Num label={t("prefs.divisions")} value={Number(values.snapDiv)} min={1} max={64} disabled={saving} onChange={v => set("snapDiv", v)} />
          </Field>
          <Field label={t("prefs.export_octave")}>
            <Num label={t("prefs.export_octave")} value={Number(values.exportOctave)} min={-4} max={4} disabled={saving} onChange={v => set("exportOctave", v)} />
          </Field>
          <Field label={t("prefs.preview_sound")}>
            <select value={String(values.previewSound)} disabled={saving} onChange={e => set("previewSound", e.target.value)}>
              {previewSoundOptions().map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </Field>
          <Field label={t("prefs.preview_volume")}>
            <Num label={t("prefs.preview_volume")} value={Number(values.previewVolume)} min={0} max={100} disabled={saving} onChange={v => set("previewVolume", v)} />
          </Field>
          <Field label={t("prefs.colormap")}>
            <select value={String(values.colormap)} disabled={saving} onChange={e => set("colormap", e.target.value)}>
              {colormapOptions().map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </Field>
          <div className="preferences-actions">
            <button className="quiet" disabled={saving} onClick={takeCurrentSettings}>{t("prefs.take_current")}</button>
            <button className="quiet" disabled={saving} onClick={() => setValues({ ...loaded.newProjectBuiltin })}>{t("prefs.reset")}</button>
          </div>
        </section>

        <section className="preferences-section">
          <h3>{t("prefs.adofai")}</h3>
          <Field label={t("prefs.kps_limit")}>
            <Num label={t("prefs.kps_limit")} value={kpsLimit} min={1} max={100000} step="any" disabled={saving} onChange={setKpsLimit} />
          </Field>
          <Field label={t("prefs.export_defaults")} group>
            <span>{loaded.hasExportDefaults ? t("prefs.export_saved") : t("prefs.export_builtin")}</span>
            <button className="quiet" disabled={saving || !loaded.hasExportDefaults} onClick={() => void clearExportDefaults()}>{t("prefs.export_reset")}</button>
          </Field>
          <p className="dialog-note">{t("prefs.export_note")}</p>
        </section>

        <section className="preferences-section">
          <h3>{t("prefs.startup")}</h3>
          <label className="preferences-check">
            <input type="checkbox" checked={checkUpdates} disabled={saving} onChange={e => setCheckUpdates(e.target.checked)} />
            {t("prefs.check_updates")}
          </label>
          <label className="preferences-check">
            <input type="checkbox" checked={reopenLastProject} disabled={saving} onChange={e => setReopenLastProject(e.target.checked)} />
            {t("prefs.reopen")}
          </label>
          {loaded.lastProject && <p className="dialog-note">{t("prefs.last_project", { path: loaded.lastProject })}</p>}
        </section>
        {error && <div className="dialog-error" role="alert">{error}</div>}
      </div>
      <div className="dialog-footer">
        <span />
        <button onClick={onClose} disabled={saving}>{t("dialog.cancel")}</button>
        <button className="primary" onClick={() => void save()} disabled={saving}>{t("dialog.save")}</button>
      </div>
    </Modal>
  );
}
