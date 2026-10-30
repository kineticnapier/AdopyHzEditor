import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import AdoFAIExportDialog from "./dialogs/AdoFAIExportDialogJa";
import AppMenus from "./components/AppMenus";
import EditorCanvas, {
  type TrackHoverInfo,
  type TrackSelectionState,
} from "./editor/EditorCanvas";
import HelpDialog from "./dialogs/HelpDialog";
import SettingsPanel from "./settings/SettingsPanel";
import {
  BlankWorkspaceDialog,
  HarmonicDiagramDialog,
  QuickHzDialog,
  UpdateDialog,
} from "./dialogs/ToolDialogs";
import { useDialogAccessibility } from "./dialogs/useDialogAccessibility";
import Timeline from "./editor/Timeline";
import { clampPitchViewChange } from "./editor/pitchViewport";
import TopToolbar from "./components/TopToolbar";
import useEditorShortcuts from "./editor/useEditorShortcuts";
import {
  DirectSpectrumRegionCache,
  followViewportStart,
  nextPrefetchStart,
  spectrumLayersForMode,
  spectrumRegion,
  spectrumRegionKey,
} from "./editor/directSpectrum";
import type { TrackSelectionRange } from "./editor/trackSelection";
import { resolveTrackLookup } from "./editor/trackLookup";
import { midiLabel, midiToHz } from "./editor/musicMath";
import { formatCursorPeakLabel } from "./editor/cursorStatus";
import { shouldShowCanvasEmptyHint } from "./editor/emptyState";
import { runMidiExport } from "./editor/midiExport";
import "./dialogs.css";
import {
  getBackendApi,
  type AppState,
  type BackendApi,
  type DirectSpectrumPayload,
  type EditorSettings,
  type FrequencyTrackPayload,
  type NoteDto,
  type NoteMutationResult,
  type PlaybackState,
  type SpectrogramPayload,
  type ViewState,
} from "./api/bridge";
import {
  AsyncActionGuard,
  enqueueAppliedTask,
  enqueueRecoverableViewTask,
  enqueueStateTaskAfterSettings,
  LatestRequestGate,
  SerialTaskQueue,
  runWithErrorFeedback,
} from "./api/requestCoordinator";
import type { ToolBackendApi } from "./api/toolsBridge";

const defaultSettings: EditorSettings = {
  volume: 85,
  speed: 1,
  notePreview: true,
  previewVolume: 20,
  previewOctave: 0,
  previewSound: "sine",
  exportOctave: 0,
  exportSemitone: 0,
  gridEnabled: false,
  metronomeEnabled: false,
  bpm: 175,
  offsetMs: 0,
  metronomeVolume: 35,
  snapEnabled: false,
  snapDiv: 1,
  contrast: 115,
  gamma: 75,
  enhance: true,
  displayMode: "wavetone",
  harmonics: "off",
  colormap: "wavetone",
  analysisProfile: "Normal",
  cqtResolution: "profile default",
  analysisSource: "cqt",
  spectrumThreshold: 2,
  spectrumOpacity: 70,
  spectrumLayerMode: "both",
  curveShape: "ease",
  curveInterpolation: "bezier_pitch",
  targetAngle: 165,
};
const defaultView: ViewState = {
  mode: "spec",
  start: 0,
  windowSeconds: 12,
  pitchBottom: 12,
  visibleNotes: 60,
};
const defaultPlayback: PlaybackState = {
  time: 0,
  duration: 60,
  playing: false,
  available: false,
  error: null,
};
type ToolDialog = "blank" | "quickHz" | "harmonic" | "update" | null;
type PendingDestructiveAction = {
  label: string;
  run(): void | Promise<void>;
  cancel?(): void | Promise<void>;
};

function UnsavedChangesDialog({
  label,
  saving,
  onSave,
  onDiscard,
  onCancel,
}: {
  label: string;
  saving: boolean;
  onSave(): void;
  onDiscard(): void;
  onCancel(): void;
}) {
  const { dialogRef, titleId } = useDialogAccessibility(onCancel);
  return (
    <div className="modal-backdrop">
      <section
        ref={dialogRef}
        tabIndex={-1}
        className="modal-window"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <header className="modal-title">
          <strong id={titleId}>未保存の変更</strong>
        </header>
        <div className="dialog-body export-dialog-body">
          <div className="info-card">「{label}」の前に変更を保存しますか？</div>
        </div>
        <div className="dialog-footer">
          <button className="primary" disabled={saving} onClick={onSave}>
            {saving ? "保存中…" : "保存"}
          </button>
          <button disabled={saving} onClick={onDiscard}>
            保存せず続行
          </button>
          <button disabled={saving} onClick={onCancel}>
            キャンセル
          </button>
        </div>
      </section>
    </div>
  );
}

export default function App() {
  const [api, setApi] = useState<BackendApi | null>(null),
    [connected, setConnected] = useState(false),
    [settings, setSettings] = useState(defaultSettings),
    [view, setView] = useState(defaultView),
    [playback, setPlayback] = useState(defaultPlayback),
    [notes, setNotes] = useState<NoteDto[]>([]),
    [selected, setSelected] = useState<number[]>([]),
    [spectrum, setSpectrum] = useState<SpectrogramPayload | null>(null),
    [directSpectrum, setDirectSpectrum] =
      useState<DirectSpectrumPayload | null>(null),
    [frequencyTracks, setFrequencyTracks] =
      useState<FrequencyTrackPayload | null>(null),
    [analysisAvailable, setAnalysisAvailable] = useState(false),
    [analysisSource, setAnalysisSource] = useState("cqt"),
    [analysisRevision, setAnalysisRevision] = useState(0),
    [viewportSize, setViewportSize] = useState({ width: 800, height: 500 }),
    [audioName, setAudioName] = useState<string | null>(null),
    [projectPath, setProjectPath] = useState<string | null>(null),
    [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [status, setStatus] = useState("準備完了");
  const [adoExportOpen, setAdoExportOpen] = useState(false),
    [adoExportSelectedOnly,setAdoExportSelectedOnly]=useState(false),
    [helpSection, setHelpSection] = useState<string | null>(null),
    [toolDialog, setToolDialog] = useState<ToolDialog>(null),
    [followPlayback, setFollowPlayback] = useState(true);
  const [panelOpen, setPanelOpen] = useState(true),
    [trackSelection, setTrackSelection] = useState<TrackSelectionState>({
      ids: [],
      range: null,
      useRange: false,
    }),
    [hoveredTrack, setHoveredTrack] = useState<TrackHoverInfo | null>(null);
  const [cursorReadout, setCursorReadout] = useState<{
    time: number;
    midi: number;
    peak?: string;
  } | null>(null);
  const [pendingDestructive, setPendingDestructive] =
    useState<PendingDestructiveAction | null>(null);
  const peakRequest = useRef(new LatestRequestGate());
  const spectrumRequests = useRef(new LatestRequestGate());
  const settingsRequests = useRef(new LatestRequestGate());
  const pendingSettings = useRef<Partial<EditorSettings>>({});
  const settingsFlush = useRef<Promise<void> | null>(null);
  const stateTransitionPending = useRef(0);
  const mutationQueue = useRef(new SerialTaskQueue());
  const viewQueue = useRef(new SerialTaskQueue());
  const viewRequests = useRef(new LatestRequestGate());
  const playbackRequests = useRef(new LatestRequestGate());
  const trackSelectionRequests = useRef(new LatestRequestGate());
  const deletingSelection = useRef("");
  const documentGeneration = useRef(0);
  const analysisIdentity = useRef("");
  const pendingSaveGuard = useRef(new AsyncActionGuard());
  const [savingPending, setSavingPending] = useState(false);
  const spectrumRequest = useRef(0);
  const desiredSpectrumKey = useRef("");
  const trackRequest = useRef(0);
  const desiredTrackKey = useRef("");
  const spectrumLoader = useMemo(
    () =>
      api
        ? new DirectSpectrumRegionCache((region) =>
            api.get_spectrum_region(
              region.startTime,
              region.endTime,
              region.minMidi,
              region.maxMidi,
              region.pixelWidth,
              region.pixelHeight,
              region.threshold,
            ),
          )
        : null,
    [api],
  );
  const trackLoader = useMemo(
    () =>
      api
        ? new DirectSpectrumRegionCache<FrequencyTrackPayload>((region) =>
            api.get_frequency_track_region(
              region.startTime,
              region.endTime,
              region.minMidi,
              region.maxMidi,
              region.pixelWidth,
              region.pixelHeight,
            ),
          )
        : null,
    [api],
  );
  const spectrumLayers = spectrumLayersForMode(settings.spectrumLayerMode);
  const visibleSpectrum =
    analysisAvailable && analysisSource !== "vorbis_direct" ? spectrum : null;
  const visibleDirectSpectrum =
    analysisAvailable &&
    analysisSource === "vorbis_direct" &&
    spectrumLayers.raw
      ? directSpectrum
      : null;
  const visibleFrequencyTracks =
    analysisAvailable &&
    analysisSource === "vorbis_direct" &&
    spectrumLayers.tracks
      ? frequencyTracks
      : null;
  const toolsApi = api as ToolBackendApi | null;

  function applyState(state: AppState) {
    documentGeneration.current += 1;
    peakRequest.current.invalidate();
    setCursorReadout(null);
    // Ignore playback replies issued for the previous document.
    playbackRequests.current.invalidate();
    trackSelectionRequests.current.invalidate();
    const identity = `${state.audio.path ?? ""}\0${state.analysis.source ?? "cqt"}\0${state.analysis.available}`;
    if (identity !== analysisIdentity.current) {
      analysisIdentity.current = identity;
      setAnalysisRevision((v) => v + 1);
    }
    setSettings(state.settings);
    setView(state.view);
    setPlayback(state.playback);
    setNotes(state.notes);
    setSelected((old) => old.filter((i) => i >= 0 && i < state.notes.length));
    setTrackSelection({ ids: [], range: null, useRange: false });
    setHoveredTrack(null);
    setAnalysisAvailable(state.analysis.available);
    setAnalysisSource(state.analysis.source ?? "cqt");
    setAudioName(state.audio.name);
    setProjectPath(state.projectPath);
    setDirty(state.dirty);
    setBusy(state.busy);
    setStatus(state.status || "準備完了");
  }
  async function refreshSpectrum(
    backend = api,
    range: Pick<
      ViewState,
      "start" | "windowSeconds" | "pitchBottom" | "visibleNotes"
    > = view,
  ) {
    if (!backend) return;
    const request = spectrumRequests.current.issue();
    setSpectrum(null);
    const columns = Math.max(
      256,
      Math.min(
        4096,
        Math.ceil(window.innerWidth * (window.devicePixelRatio || 1)),
      ),
    );
    try {
      const payload = await backend.get_spectrogram(
        columns,
        range.start,
        range.start + range.windowSeconds,
        range.pitchBottom - 0.5,
        range.pitchBottom + range.visibleNotes - 0.5,
      );
      if (spectrumRequests.current.isCurrent(request))
        setSpectrum(payload.available ? payload : null);
    } catch (e) {
      if (spectrumRequests.current.isCurrent(request)) {
        setSpectrum(null);
        setStatus(`スペクトラム取得失敗: ${String(e)}`);
      }
    }
  }

  useEffect(() => {
    let active = true;
    void (async () => {
      while (active) {
        const backend = await getBackendApi();
        if (!active) return;
        if (!backend) {
          await new Promise((resolve) => window.setTimeout(resolve, 500));
          continue;
        }
        try {
          const ping = await backend.ping();
          if (!active) return;
          setApi(backend);
          setConnected(ping.ok);
          const state = await backend.get_state();
          if (!active) return;
          applyState(state);
          if (
            state.analysis.available &&
            state.analysis.source !== "vorbis_direct"
          )
            await refreshSpectrum(backend, state.view);
          return;
        } catch (e) {
          if (!active) return;
          setConnected(false);
          setStatus(`バックエンド接続を再試行中: ${String(e)}`);
          await new Promise((resolve) => window.setTimeout(resolve, 500));
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    if (!api) return;
    let active = true;
    const id = window.setInterval(
      () => {
        const generation = documentGeneration.current;
        const request = playbackRequests.current.issue();
        void api
          .get_playback_state()
          .then((x) => {
            if (active && generation === documentGeneration.current &&
                playbackRequests.current.isCurrent(request))
              setPlayback(x);
          })
          .catch(() => {});
      },
      playback.playing ? 50 : 500,
    );
    return () => {
      active = false;
      window.clearInterval(id);
    };
  }, [api, playback.playing]);
  useEffect(() => {
    if (
      !api ||
      !analysisAvailable ||
      analysisSource === "vorbis_direct" ||
      view.mode === "notes"
    ) {
      setSpectrum(null);
      return;
    }
    const id = window.setTimeout(() => void refreshSpectrum(api, view), 140);
    return () => window.clearTimeout(id);
  }, [
    api,
    analysisAvailable,
    analysisSource,
    settings.contrast,
    settings.gamma,
    settings.enhance,
    settings.displayMode,
    settings.harmonics,
    view.mode,
    view.start,
    view.windowSeconds,
    view.pitchBottom,
    view.visibleNotes,
  ]);
  useLayoutEffect(() => {
    spectrumLoader?.invalidate();
    spectrumRequest.current += 1;
  }, [
    spectrumLoader,
    analysisAvailable,
    analysisSource,
    analysisRevision,
    settings.spectrumThreshold,
    view.windowSeconds,
    view.pitchBottom,
    view.visibleNotes,
    viewportSize.width,
    viewportSize.height,
  ]);
  useLayoutEffect(() => {
    const request = ++spectrumRequest.current;
    if (
      !spectrumLoader ||
      !analysisAvailable ||
      analysisSource !== "vorbis_direct" ||
      view.mode === "notes" ||
      !spectrumLayers.raw
    ) {
      desiredSpectrumKey.current = "";
      setDirectSpectrum(null);
      return;
    }
    const region = spectrumRegion(
        view,
        viewportSize,
        settings.spectrumThreshold,
      ),
      key = spectrumRegionKey(region);
    desiredSpectrumKey.current = key;
    const prefetch = () => {
      if (!followPlayback || !playback.playing) return;
      const next = nextPrefetchStart(
        view.start,
        view.windowSeconds,
        playback.duration,
      );
      if (next !== null)
        spectrumLoader.prefetch(
          spectrumRegion(view, viewportSize, settings.spectrumThreshold, next),
        );
    };
    const cached = spectrumLoader.peek(region);
    if (cached) {
      setDirectSpectrum(cached.available ? cached : null);
      prefetch();
      return;
    }
    setDirectSpectrum(null);
    void spectrumLoader
      .load(region)
      .then((payload) => {
        if (
          request !== spectrumRequest.current ||
          key !== desiredSpectrumKey.current ||
          !payload
        )
          return;
        setDirectSpectrum(payload.available ? payload : null);
        prefetch();
      })
      .catch((e) => {
        if (request === spectrumRequest.current) setStatus(String(e));
      });
  }, [
    spectrumLoader,
    analysisAvailable,
    analysisSource,
    analysisRevision,
    spectrumLayers.raw,
    settings.spectrumThreshold,
    view.mode,
    view.start,
    view.windowSeconds,
    view.pitchBottom,
    view.visibleNotes,
    viewportSize.width,
    viewportSize.height,
    followPlayback,
    playback.playing,
    playback.duration,
  ]);
  useLayoutEffect(() => {
    trackLoader?.invalidate();
    trackRequest.current += 1;
  }, [
    trackLoader,
    analysisAvailable,
    analysisSource,
    analysisRevision,
    view.windowSeconds,
    view.pitchBottom,
    view.visibleNotes,
    viewportSize.width,
    viewportSize.height,
  ]);
  useLayoutEffect(() => {
    const request = ++trackRequest.current;
    if (
      !trackLoader ||
      !analysisAvailable ||
      analysisSource !== "vorbis_direct" ||
      view.mode === "notes" ||
      !spectrumLayers.tracks
    ) {
      desiredTrackKey.current = "";
      setFrequencyTracks(null);
      return;
    }
    const region = spectrumRegion(view, viewportSize, 0),
      key = spectrumRegionKey(region);
    desiredTrackKey.current = key;
    const prefetch = () => {
      if (!followPlayback || !playback.playing) return;
      const next = nextPrefetchStart(
        view.start,
        view.windowSeconds,
        playback.duration,
      );
      if (next !== null)
        trackLoader.prefetch(spectrumRegion(view, viewportSize, 0, next));
    };
    const cached = trackLoader.peek(region);
    if (cached) {
      setFrequencyTracks(cached.available ? cached : null);
      prefetch();
      return;
    }
    setFrequencyTracks(null);
    void trackLoader
      .load(region)
      .then((payload) => {
        if (
          request !== trackRequest.current ||
          key !== desiredTrackKey.current ||
          !payload
        )
          return;
        setFrequencyTracks(payload.available ? payload : null);
        prefetch();
      })
      .catch((e) => {
        if (request === trackRequest.current) setStatus(String(e));
      });
  }, [
    trackLoader,
    analysisAvailable,
    analysisSource,
    analysisRevision,
    spectrumLayers.tracks,
    view.mode,
    view.start,
    view.windowSeconds,
    view.pitchBottom,
    view.visibleNotes,
    viewportSize.width,
    viewportSize.height,
    followPlayback,
    playback.playing,
    playback.duration,
  ]);
  useEffect(() => {
    if (stateTransitionPending.current > 0 || !followPlayback || !playback.playing || view.windowSeconds <= 0) return;
    const next = followViewportStart(
      view.start,
      view.windowSeconds,
      playback.time,
      playback.duration,
    );
    if (next !== null) {
      setView((v) => ({ ...v, start: next }));
      // Follow updates must share the manual viewport queue and failure recovery.
      // Otherwise an in-flight follow write can overtake a user's pan/zoom.
      if (api && stateTransitionPending.current === 0)
        void applyViewAction(() => api.set_view({ start: next }), "再生追従");
    }
  }, [
    api,
    followPlayback,
    playback.duration,
    playback.playing,
    playback.time,
    view.start,
    view.windowSeconds,
  ]);

  async function patch(changes: Partial<EditorSettings>) {
    if (stateTransitionPending.current > 0) {
      setStatus("プロジェクト処理中は設定を変更できません");
      return;
    }
    const sourceChanged =
      changes.analysisSource !== undefined &&
      changes.analysisSource !== settings.analysisSource;
    if (sourceChanged) {
      peakRequest.current.invalidate();
      setCursorReadout(null);
      trackSelectionRequests.current.invalidate();
      setAnalysisAvailable(false);
      setSpectrum(null);
      setDirectSpectrum(null);
      setFrequencyTracks(null);
      setTrackSelection({ ids: [], range: null, useRange: false });
      setHoveredTrack(null);
    }
    setSettings((v) => ({ ...v, ...changes }));
    setDirty(true);
    pendingSettings.current = { ...pendingSettings.current, ...changes };
    await flushPendingSettings();
  }
  async function flushPendingSettings() {
    if (!api) return;
    if (settingsFlush.current) return settingsFlush.current;
    settingsFlush.current = (async () => {
      while (Object.keys(pendingSettings.current).length) {
        const batch = pendingSettings.current;
        pendingSettings.current = {};
        const request = settingsRequests.current.issue();
        try {
          const normalized = await api.update_settings(batch);
          if (
            settingsRequests.current.isCurrent(request) &&
            Object.keys(pendingSettings.current).length === 0
          )
            setSettings(normalized);
        } catch (e) {
          setStatus(`設定の更新に失敗しました: ${String(e)}`);
          if (
            settingsRequests.current.isCurrent(request) &&
            Object.keys(pendingSettings.current).length === 0
          ) {
            try {
              setSettings((await api.get_state()).settings);
            } catch {
              /* Keep the visible value and the dirty warning. */
            }
          }
        }
      }
    })().finally(() => {
      settingsFlush.current = null;
    });
    return settingsFlush.current;
  }
  async function applyViewAction(
    action: () => Promise<ViewState>,
    label: string,
  ) {
    if (!api || stateTransitionPending.current > 0) return;
    const request = viewRequests.current.issue();
    const generation = documentGeneration.current;
    const isCurrent = () =>
      viewRequests.current.isCurrent(request) &&
      generation === documentGeneration.current;
    await enqueueRecoverableViewTask(
      viewQueue.current,
      action,
      isCurrent,
      setView,
      async (error) => {
        setStatus(`${label}に失敗しました: ${String(error)}`);
        try {
          // Read the backend's actual view, not the optimistic local value.
          const state = await viewQueue.current.enqueue(() => api.get_state());
          if (isCurrent()) setView(state.view);
        } catch (recoveryError) {
          if (isCurrent())
            setStatus(`表示範囲の再取得に失敗しました: ${String(recoveryError)}`);
        }
      },
    );
  }
  async function updateView(changes: Partial<ViewState>) {
    if (stateTransitionPending.current > 0) {
      setStatus("プロジェクト処理中は表示範囲を変更できません");
      return;
    }
    // Keep optimistic canvas coordinates within the same MIDI bounds as Bridge.set_view.
    const normalized = clampPitchViewChange(view, changes);
    if (Object.keys(normalized).some((key) => key !== "mode"))
      setFollowPlayback(false);
    if (normalized.mode === "notes") {
      trackSelectionRequests.current.invalidate();
      setTrackSelection({ ids: [], range: null, useRange: false });
      setHoveredTrack(null);
    }
    setView((v) => ({ ...v, ...normalized }));
    if (api) await applyViewAction(() => api.set_view(normalized), "表示範囲の変更");
  }
  async function fitView() {
    if (stateTransitionPending.current > 0) {
      setStatus("プロジェクト処理中は表示範囲を変更できません");
      return;
    }
    setFollowPlayback(false);
    if (api) await applyViewAction(() => api.fit_view(), "全体表示");
  }
  async function performStateAction(
    action: () => Promise<AppState>,
    clearSelection = false,
  ): Promise<AppState> {
    if (!api) throw new Error("バックエンドに接続されていません");
    stateTransitionPending.current += 1;
    // A pending CQT peak belongs to the previous document or analysis state.
    peakRequest.current.invalidate();
    setCursorReadout(null);
    // Invalidate pending viewport writes before reserving the document queue.
    viewRequests.current.invalidate();
    setBusy(true);
    spectrumRequests.current.invalidate();
    spectrumRequest.current += 1;
    trackRequest.current += 1;
    try {
      // Keep the backend action and applyState inside the edit queue.
      // Edits queued after a document switch are rejected by generation.
      // A prior viewport write must finish before a new document is loaded.
      const guardedAction = async () => {
        await viewQueue.current.enqueue(async () => undefined);
        return action();
      };
      const state = await enqueueStateTaskAfterSettings(
        mutationQueue.current,
        flushPendingSettings,
        guardedAction,
        (next) => {
          applyState(next);
          if (clearSelection) setSelected([]);
        },
      );
      if (state.analysis.available && state.analysis.source !== "vorbis_direct")
        await refreshSpectrum(api, state.view);
      else setSpectrum(null);
      if (!state.analysis.available) {
        setDirectSpectrum(null);
        setFrequencyTracks(null);
      }
      return state;
    } finally {
      stateTransitionPending.current -= 1;
      setBusy(stateTransitionPending.current > 0);
    }
  }
  async function runStateAction(
    action: () => Promise<AppState>,
    clearSelection = false,
  ): Promise<void> {
    try {
      await performStateAction(action, clearSelection);
    } catch (e) {
      setStatus(String(e));
    }
  }
  function requestDestructive(
    label: string,
    run: () => void | Promise<void>,
    cancel?: () => void | Promise<void>,
  ) {
    if (dirty) setPendingDestructive({ label, run, cancel });
    else void run();
  }
  async function cancelPendingDestructive(status?: string) {
    const pending = pendingDestructive;
    setPendingDestructive(null);
    try {
      await pending?.cancel?.();
    } catch (e) {
      setStatus(String(e));
      return;
    }
    if (status) setStatus(status);
  }
  async function saveThenContinue() {
    await pendingSaveGuard.current.run(async () => {
      const pending = pendingDestructive;
      if (!api || !pending) return;
      stateTransitionPending.current += 1;
      viewRequests.current.invalidate();
      setSavingPending(true);
      setBusy(true);
      let state: AppState | undefined;
      try {
        // Reserve the edit queue before waiting for settings and viewport writes.
        state = await enqueueStateTaskAfterSettings(
          mutationQueue.current,
          flushPendingSettings,
          async () => {
            await viewQueue.current.enqueue(async () => undefined);
            return api.save_project_dialog();
          },
          applyState,
        );
      } catch (e) {
        setStatus(String(e));
      } finally {
        stateTransitionPending.current -= 1;
        setBusy(stateTransitionPending.current > 0);
        setSavingPending(false);
      }
      if (!state) return;
      if (state.dirty) {
        await cancelPendingDestructive(
          "保存がキャンセルされたため、操作を中止しました",
        );
        return;
      }
      setPendingDestructive(null);
      try {
        await pending.run();
      } catch (e) {
        setStatus(String(e));
      }
    });
  }
  async function discardThenContinue() {
    if (pendingSaveGuard.current.isRunning) return;
    const pending = pendingDestructive;
    if (!pending) return;
    setPendingDestructive(null);
    stateTransitionPending.current += 1;
    try {
      await flushPendingSettings();
      await pending.run();
    } catch (e) {
      setStatus(String(e));
    } finally {
      stateTransitionPending.current -= 1;
    }
  }
  function applyMutation(
    result: NoteMutationResult,
    selection?: number[],
    markDirty = true,
  ) {
    setNotes(result.notes);
    setStatus(result.status);
    if (result.dirty !== undefined) setDirty(result.dirty);
    else if (markDirty && result.changed !== false) setDirty(true);
    if (selection)
      setSelected(selection.filter((i) => i >= 0 && i < result.notes.length));
    else
      setSelected((old) =>
        old.filter((i) => i >= 0 && i < result.notes.length),
      );
  }
  async function queuedMutation(
    call: () => Promise<NoteMutationResult>,
    selection: (result: NoteMutationResult) => number[] | undefined,
    markDirty: (result: NoteMutationResult) => boolean = () => true,
  ) {
    const generation = documentGeneration.current;
    return runWithErrorFeedback(
      () => enqueueAppliedTask(
        mutationQueue.current,
        call,
        (result) => applyMutation(result, selection(result), markDirty(result)),
        () => generation === documentGeneration.current,
      ),
      () => undefined,
      (message) => setStatus(`ノート編集に失敗しました: ${message}`),
    );
  }
  function queueExternalMutation(
    call: () => Promise<NoteMutationResult>,
    selection: (result: NoteMutationResult) => number[] | undefined = () => undefined,
  ) {
    return queuedMutation(call, selection);
  }
  async function addNote(
    start: number,
    end: number,
    midi: number,
    kind: "note" | "curve",
    endMidi: number,
  ) {
    if (api)
      await queuedMutation(
        () => api.add_note(start, end, midi, kind, endMidi),
        (r) => (r.index === undefined ? [] : [r.index]),
      );
  }
  async function moveNotes(indices: number[], dx: number, dy: number) {
    if (api && indices.length)
      await queuedMutation(
        () => api.move_notes(indices, dx, dy),
        () => indices,
      );
  }
  async function duplicateMove(indices: number[], dx: number, dy: number) {
    if (api && indices.length)
      await queuedMutation(
        () => api.duplicate_notes_shifted(indices, dx, dy),
        (r) => r.indices ?? [],
      );
  }
  async function resizeNotes(
    indices: number[],
    edge: "start" | "end",
    delta: number,
  ) {
    if (api && indices.length)
      await queuedMutation(
        () => api.resize_notes(indices, edge, delta),
        () => indices,
      );
  }
  async function deleteNotes(indices = selected) {
    if (!api || !indices.length) return;
    const key = [...indices].sort((a, b) => a - b).join(",");
    if (deletingSelection.current === key) return;
    deletingSelection.current = key;
    try {
      await queuedMutation(
        () => api.delete_notes(indices),
        () => [],
      );
    } finally {
      if (deletingSelection.current === key) deletingSelection.current = "";
    }
  }
  async function cutRange(indices: number[], start: number, end: number) {
    if (api && indices.length)
      await queuedMutation(
        () => api.cut_notes_range(indices, start, end),
        (r) => r.indices ?? [],
        (r) => r.changed !== false,
      );
  }
  async function duplicate() {
    if (api && selected.length)
      await queuedMutation(
        () => api.duplicate_notes(selected),
        (r) => r.indices ?? [],
      );
  }
  async function quantize() {
    if (api && selected.length)
      await queuedMutation(
        () => api.quantize_notes(selected),
        () => selected,
      );
  }
  async function splitSelected() {
    if (api && selected.length)
      await queuedMutation(
        () => api.split_notes(selected, playback.time),
        (r) => (r.indices?.length ? r.indices : selected),
      );
  }
  async function copySelected() {
    if (api) {
      const generation = documentGeneration.current;
      await runWithErrorFeedback(
        () => enqueueAppliedTask(
          mutationQueue.current,
          () => api.copy_notes(selected),
          (result) => setStatus(result.status),
          () => generation === documentGeneration.current,
        ),
        () => undefined,
        (message) => setStatus(`コピーに失敗しました: ${message}`),
      );
    }
  }
  async function cutSelected() {
    if (api)
      await queuedMutation(
        () => api.cut_notes(selected),
        () => [],
        (r) => r.changed !== false,
      );
  }
  async function pasteAtPlayback() {
    if (api)
      await queuedMutation(
        () => api.paste_notes(playback.time),
        (r) => r.indices ?? [],
        (r) => r.changed !== false,
      );
  }
  async function applyTargetAngle() {
    if (api)
      await queuedMutation(
        () => api.apply_target_angle(selected, settings.targetAngle),
        () => selected,
        (r) => r.changed !== false,
      );
  }
  // Playback commands mutate backend state and must not overtake document loads.
  async function queuedPlaybackAction(call: () => Promise<PlaybackState>) {
    const generation = documentGeneration.current;
    await runWithErrorFeedback(
      () => enqueueAppliedTask(
        mutationQueue.current,
        async () => {
          const request = playbackRequests.current.issue();
          return { request, next: await call() };
        },
        ({ request, next }) => {
          if (playbackRequests.current.isCurrent(request)) setPlayback(next);
        },
        () => generation === documentGeneration.current,
      ),
      () => undefined,
      (message) => setStatus(`再生操作に失敗しました: ${message}`),
    );
  }
  async function seekTo(t: number) {
    if (api) await queuedPlaybackAction(() => api.seek_to(t));
    else setPlayback((p) => ({ ...p, time: t }));
  }
  async function togglePlayback() {
    if (api) await queuedPlaybackAction(() => api.toggle_playback());
  }
  async function stopPlayback() {
    if (api) await queuedPlaybackAction(() => api.stop_playback());
  }
  async function seekRelative(s: number) {
    if (api) await queuedPlaybackAction(() => api.seek_relative(s));
  }
  async function mode(v: ViewState["mode"]) {
    await updateView({ mode: v });
  }
  async function undo() {
    if (api)
      await queuedMutation(
        () => api.undo(),
        () => [],
        (r) => r.changed !== false,
      );
  }
  async function redo() {
    if (api)
      await queuedMutation(
        () => api.redo(),
        () => [],
        (r) => r.changed !== false,
      );
  }
  async function cursorMoved(time: number, midi: number) {
    // Issue before the early return: moving into a non-CQT view also
    // invalidates any pending response from the previous cursor position.
    const request = peakRequest.current.issue();
    const generation = documentGeneration.current;
    setCursorReadout({ time, midi });
    if (!api || !analysisAvailable || analysisSource === "vorbis_direct" ||
        stateTransitionPending.current > 0)
      return;
    try {
      const peak = await api.get_cursor_peak(time, midi, 5);
      if (!peakRequest.current.isCurrent(request) ||
          generation !== documentGeneration.current ||
          stateTransitionPending.current > 0) return;
      const label = formatCursorPeakLabel(peak);
      if (label !== null)
        setCursorReadout({ time: peak.time ?? time, midi, peak: label });
    } catch {
      /* Cursor diagnostics must not interrupt editing. */
    }
  }
  function changeTrackSelection(selection: TrackSelectionState) {
    // Inspector edits must supersede an in-flight canvas range lookup too.
    trackSelectionRequests.current.invalidate();
    setTrackSelection(selection);
    if (selection.ids.length) setPanelOpen(true);
  }
  async function findTracks(range: TrackSelectionRange): Promise<number[] | null> {
    if (!api || stateTransitionPending.current > 0) return null;
    const generation = documentGeneration.current;
    const request = trackSelectionRequests.current.issue();
    const isCurrent = () =>
      generation === documentGeneration.current &&
      stateTransitionPending.current === 0 &&
      trackSelectionRequests.current.isCurrent(request);
    return resolveTrackLookup(
      () => api.find_frequency_tracks(
        range.startTime,
        range.endTime,
        range.minMidi,
        range.maxMidi,
      ),
      isCurrent,
      setStatus,
    );
  }
  async function convertTracks(
    trackIds: number[],
    conversionMode: "fixed" | "curve",
    range: TrackSelectionRange | null,
  ) {
    if (!api || !trackIds.length) return;
    setBusy(true);
    try {
      await queuedMutation(
        () => api.create_notes_from_tracks(
          trackIds,
          conversionMode,
          range?.startTime ?? null,
          range?.endTime ?? null,
        ),
        (result) => result.indices ?? [],
        (result) => result.changed !== false,
      );
    } catch (e) {
      setStatus(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function convertSelectedTracks(conversionMode: "fixed" | "curve") {
    await convertTracks(
      trackSelection.ids,
      conversionMode,
      trackSelection.useRange ? trackSelection.range : null,
    );
  }
  function exportMidi(selectedOnly = false) {
    if (!api) return;
    const generation = documentGeneration.current;
    // Capture the selection at invocation time, not when earlier edits finish.
    const selectedAtRequest = [...selected];
    const action =
      selectedOnly && toolsApi
        ? () => toolsApi.export_selected_midi_dialog(selectedAtRequest)
        : () => api.export_midi_dialog();
    // Exports read the current backend document. Keep them in the same order
    // as edits and document replacements, and drop stale queued exports.
    void enqueueAppliedTask(
      mutationQueue.current,
      () => runMidiExport(action, (message) => {
        if (generation === documentGeneration.current) setStatus(message);
      }),
      () => undefined,
      () => generation === documentGeneration.current,
    );
  }

  const stateAction = (fn: () => Promise<AppState>) => void runStateAction(fn),
    nudgeSeconds = settings.snapEnabled
      ? 60 / Math.max(1, settings.bpm) / Math.max(1, settings.snapDiv)
      : 0.01;
  const openAudioSafely = () =>
    api &&
    requestDestructive("音声を開く", () =>
      runStateAction(() => api.open_audio()),
    );
  const loadProjectSafely = () =>
    api &&
    requestDestructive("プロジェクトを読み込む", () =>
      runStateAction(() => api.load_project_dialog(), true),
    );
  useEffect(() => {
    if (!api) return;
    const requested = () =>
      setPendingDestructive({
        label: "ウィンドウを閉じる",
        run: async () => {
          await api.close_window();
        },
        cancel: async () => {
          await api.cancel_window_close();
        },
      });
    window.addEventListener("adopyhz-close-requested", requested);
    return () =>
      window.removeEventListener("adopyhz-close-requested", requested);
  }, [api]);
  useEditorShortcuts({
    disabled: Boolean(
      adoExportOpen || helpSection || toolDialog || pendingDestructive,
    ),
    api,
    notes,
    selected,
    playbackTime: playback.time,
    view,
    nudgeSeconds,
    openAudio: openAudioSafely,
    saveProject: () => api && stateAction(() => api.save_project_dialog()),
    saveProjectAs: () => api && stateAction(() => api.save_project_as_dialog()),
    loadProject: loadProjectSafely,
    importMidi: () =>
      api && void runStateAction(() => api.import_midi_dialog(), true),
    exportMidi: () => exportMidi(),
    openAdoExport: () => {setAdoExportSelectedOnly(false);setAdoExportOpen(true)},
    openHelp: () => setHelpSection("quick_start"),
    setStatus,
    undo: () => void undo(),
    redo: () => void redo(),
    duplicate: () => void duplicate(),
    quantize: () => void quantize(),
    select: setSelected,
    clearTracks: () => changeTrackSelection({ ids: [], range: null, useRange: false }),
    copy: () => void copySelected(),
    cut: () => void cutSelected(),
    paste: () => void pasteAtPlayback(),
    applyTargetAngle: () => void applyTargetAngle(),
    move: (i, dx, dy) => void moveNotes(i, dx, dy),
    stop: () => void stopPlayback(),
    play: () => void togglePlayback(),
    deleteSelected: () => void deleteNotes(),
    mode: (v) => void mode(v),
    seek: (d) => void seekRelative(d),
    seekTo: (t) => void seekTo(t),
    updateView: (c) => void updateView(c),
  });

  const menus = toolsApi ? (
    <AppMenus
      hasSelection={selected.length > 0}
      hasProject={Boolean(projectPath)}
      onOpenAudio={openAudioSafely}
      onLoadProject={loadProjectSafely}
      onSaveProject={() => api && stateAction(() => api.save_project_dialog())}
      onSaveProjectAs={() =>
        api && stateAction(() => api.save_project_as_dialog())
      }
      onImportMidi={() =>
        api && void runStateAction(() => api.import_midi_dialog(), true)
      }
      onExportMidi={() => exportMidi()}
      onExportAdo={() => {setAdoExportSelectedOnly(false);setAdoExportOpen(true)}}
      onBlankWorkspace={() =>
        requestDestructive("空のワークスペースへ切り替える", () =>
          setToolDialog("blank"),
        )
      }
      onLoadNotesOnly={() =>
        requestDestructive("ノートだけ読み込む", () =>
          runStateAction(() => toolsApi.load_project_notes_only_dialog(), true),
        )
      }
      onMergeProject={() =>
        void runStateAction(() => toolsApi.merge_project_notes_dialog(), true)
      }
      onRelinkProjectAudio={() =>
        api && stateAction(() => api.relink_project_audio_dialog())
      }
      onExportSelectedMidi={() => exportMidi(true)}
      onExportSelectedAdo={() => {
        setAdoExportSelectedOnly(true);setAdoExportOpen(true);
        setStatus("ADOFAI出力で「選択ノートのみ」を使用できます");
      }}
      onUndo={() => void undo()}
      onRedo={() => void redo()}
      onDuplicate={() => void duplicate()}
      onQuantize={() => void quantize()}
      onSplit={() => void splitSelected()}
      onHarmonicDiagram={() => setToolDialog("harmonic")}
      onReanalyze={() => stateAction(() => toolsApi.reanalyze_audio())}
      onQuickHz={() => setToolDialog("quickHz")}
      onUpdates={() => setToolDialog("update")}
      onHelp={() => setHelpSection("quick_start")}
    />
  ) : null;

  return (
    <div className="app">
      <TopToolbar
        connected={connected}
        audioName={audioName}
        dirty={dirty}
        playback={playback}
        view={view}
        menus={menus}
        panelOpen={panelOpen}
        onTogglePanel={() => setPanelOpen((value) => !value)}
        onSeek={(t) => void seekTo(t)}
        onStop={() => void stopPlayback()}
        onPlay={() => void togglePlayback()}
        onMode={(v) => void mode(v)}
      />
      <main className={panelOpen ? "workspace" : "workspace panel-collapsed"}>
        <section className="editor">
          <div className="editor-stage">
            <EditorCanvas
              notes={notes}
              selected={selected}
              settings={settings}
              view={view}
              playback={playback}
              spectrum={visibleSpectrum}
              directSpectrum={visibleDirectSpectrum}
              frequencyTracks={visibleFrequencyTracks}
              trackSelection={trackSelection}
              onViewportSize={setViewportSize}
              onSelect={setSelected}
              onAdd={addNote}
              onMove={moveNotes}
              onDuplicateMove={duplicateMove}
              onResize={resizeNotes}
              onDelete={deleteNotes}
              onCutRange={cutRange}
              onSeek={seekTo}
              onView={updateView}
              onCursorMove={(time, midi) => void cursorMoved(time, midi)}
              onTrackHover={setHoveredTrack}
              onTrackSelectionChange={changeTrackSelection}
              onFindTracks={findTracks}
            />
            {shouldShowCanvasEmptyHint(audioName, notes.length) && (
              <div className="canvas-empty" aria-hidden="true">
                <strong>ノートを追加するか、音源を開く</strong>
                <span>
                  ドラッグでノート作成 / ファイル → 音声を開く…{" "}
                  <kbd>Ctrl+O</kbd>
                </span>
                <small>音源がない空のワークスペースでも採譜できます。</small>
              </div>
            )}
          </div>
          <div className="canvas-readout" aria-live="off">
            <span>
              {cursorReadout ? `${cursorReadout.time.toFixed(3)} s` : "—.—— s"}
            </span>
            <span>
              {cursorReadout
                ? `MIDI ${cursorReadout.midi.toFixed(2)}`
                : "MIDI —"}
            </span>
            <span>
              {cursorReadout
                ? `${midiLabel(cursorReadout.midi)} · ${midiToHz(cursorReadout.midi).toFixed(2)} Hz`
                : "Pitch —"}
            </span>
            {hoveredTrack && (
              <strong>
                Track #{hoveredTrack.id} · {hoveredTrack.noteName} ·{" "}
                {hoveredTrack.duration.toFixed(3)} s · $
                {(hoveredTrack.magnitude * 100).toFixed(1)}%
              </strong>
            )}
            {!hoveredTrack && cursorReadout?.peak && (
              <strong>{cursorReadout.peak}</strong>
            )}
          </div>
          <Timeline
            view={view}
            playback={playback}
            followPlayback={followPlayback}
            onFollowPlayback={setFollowPlayback}
            onView={(c) => void updateView(c)}
            onFit={() => void fitView()}
          />
        </section>
        {panelOpen && (
          <SettingsPanel
            api={api}
            settings={settings}
            notes={notes}
            selected={selected}
            audioName={audioName}
            busy={busy}
            analysisAvailable={analysisAvailable}
            actualAnalysisSource={analysisSource}
            trackSelection={trackSelection}
            hoveredTrack={hoveredTrack}
            onPatch={patch}
            onStateAction={runStateAction}
            onQueuedMutation={queueExternalMutation}
            onStatus={setStatus}
            onTrackSelectionChange={changeTrackSelection}
            onConvertTracks={convertSelectedTracks}
          />
        )}
      </main>
      <footer className="statusbar" role="status" aria-live="polite">
        <span>{busy ? "処理中…" : status}</span>
        <span>
          {projectPath ? projectPath.split(/[\\/]/).pop() : "プロジェクトなし"}{" "}
          · Note {notes.length}個
        </span>
      </footer>
      {adoExportOpen && api && (
        <AdoFAIExportDialog
          api={api}
          selected={selected}
          defaultSelectedOnly={adoExportSelectedOnly}
          onClose={() => setAdoExportOpen(false)}
          onStatus={setStatus}
          onHelp={(s) => {
            setAdoExportOpen(false);
            setHelpSection(s ?? "adofai_export");
          }}
        />
      )}{" "}
      {helpSection && api && (
        <HelpDialog
          api={api}
          initialSection={helpSection}
          onClose={() => setHelpSection(null)}
        />
      )}{" "}
      {toolDialog === "blank" && toolsApi && (
        <BlankWorkspaceDialog
          api={toolsApi}
          onClose={() => setToolDialog(null)}
          onStatus={setStatus}
          onApply={async (options) => {
            await performStateAction(() => toolsApi.apply_blank_workspace(options));
          }}
        />
      )}{" "}
      {toolDialog === "quickHz" && toolsApi && (
        <QuickHzDialog
          api={toolsApi}
          onClose={() => setToolDialog(null)}
          onStatus={setStatus}
        />
      )}{" "}
      {toolDialog === "harmonic" && toolsApi && (
        <HarmonicDiagramDialog
          api={toolsApi}
          selected={selected}
          onClose={() => setToolDialog(null)}
          onStatus={setStatus}
          onQueuedMutation={queueExternalMutation}
        />
      )}{" "}
      {toolDialog === "update" && toolsApi && (
        <UpdateDialog
          api={toolsApi}
          onClose={() => setToolDialog(null)}
          onStatus={setStatus}
        />
      )}
      {pendingDestructive && (
        <UnsavedChangesDialog
          label={pendingDestructive.label}
          saving={savingPending}
          onSave={() => void saveThenContinue()}
          onDiscard={() => void discardThenContinue()}
          onCancel={() => {
            if (!pendingSaveGuard.current.isRunning)
              void cancelPendingDestructive();
          }}
        />
      )}
    </div>
  );
}
