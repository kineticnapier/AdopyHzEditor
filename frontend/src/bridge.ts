export type EditorSettings = {
  volume: number;
  speed: number;
  notePreview: boolean;
  previewVolume: number;
  previewOctave: number;
  previewSound: string;
  exportOctave: number;
  exportSemitone: number;
  gridEnabled: boolean;
  metronomeEnabled: boolean;
  bpm: number;
  offsetMs: number;
  metronomeVolume: number;
  snapEnabled: boolean;
  snapDiv: number;
  contrast: number;
  gamma: number;
  enhance: boolean;
  displayMode: string;
  harmonics: string;
  colormap: string;
  analysisProfile: string;
  cqtResolution: string;
  curveShape: string;
  curveInterpolation: string;
  targetAngle: number;
};

export type ViewState = {
  mode: "spec" | "notes" | "both";
  start: number;
  windowSeconds: number;
  pitchBottom: number;
  visibleNotes: number;
};

export type PlaybackState = {
  time: number;
  duration: number;
  playing: boolean;
  available: boolean;
  error: string | null;
};

export type NoteDto = {
  start: number;
  end: number;
  midi: number;
  velocity?: number;
  kind?: "note" | "curve";
  midi_end?: number;
  ctrl1_midi?: number;
  ctrl2_midi?: number;
  interpolation?: string;
  target_angle?: number;
};

export type AnalysisState = {
  available: boolean;
  duration: number;
  midiMin: number;
  midiMax: number;
  pitchStep: number;
};

export type AppState = {
  settings: EditorSettings;
  view: ViewState;
  playback: PlaybackState;
  audio: { path: string | null; name: string | null; loaded: boolean };
  projectPath: string | null;
  notes: NoteDto[];
  analysis: AnalysisState;
  busy: boolean;
  status: string;
  dirty: boolean;
};

export type SpectrogramPayload = {
  available: boolean;
  rows?: number;
  cols?: number;
  data?: string;
  duration?: number;
  midiMin?: number;
  midiMax?: number;
  pitchStep?: number;
};

export type NoteMutationResult = {
  notes: NoteDto[];
  status: string;
  index?: number;
  indices?: number[];
};

export type BackendApi = {
  ping(): Promise<{ ok: boolean; app: string; ui: string; capabilities: string[] }>;
  get_state(): Promise<AppState>;
  get_settings(): Promise<EditorSettings>;
  update_settings(changes: Partial<EditorSettings>): Promise<EditorSettings>;
  set_view(changes: Partial<ViewState>): Promise<ViewState>;
  fit_view(): Promise<ViewState>;

  open_audio(): Promise<AppState>;
  reanalyze_audio(): Promise<AppState>;
  get_spectrogram(maxColumns?: number): Promise<SpectrogramPayload>;
  get_playback_state(): Promise<PlaybackState>;
  toggle_playback(): Promise<PlaybackState>;
  stop_playback(): Promise<PlaybackState>;
  seek_to(seconds: number): Promise<PlaybackState>;
  seek_relative(seconds: number): Promise<PlaybackState>;

  add_note(start: number, end: number, midi: number, kind?: string, endMidi?: number | null): Promise<NoteMutationResult>;
  delete_notes(indices: number[]): Promise<NoteMutationResult>;
  move_notes(indices: number[], dx: number, dy: number): Promise<NoteMutationResult>;
  apply_interpolation(indices: number[]): Promise<NoteMutationResult>;
  apply_target_angle(indices: number[]): Promise<NoteMutationResult>;
  clear_target_angle(indices: number[]): Promise<NoteMutationResult>;
  undo(): Promise<NoteMutationResult>;
  redo(): Promise<NoteMutationResult>;
  copy_notes(indices: number[]): Promise<{ status: string }>;
  cut_notes(indices: number[]): Promise<NoteMutationResult>;
  paste_notes(atTime: number): Promise<NoteMutationResult>;

  save_project_dialog(): Promise<AppState>;
  load_project_dialog(): Promise<AppState>;
  import_midi_dialog(): Promise<AppState>;
  export_midi_dialog(): Promise<{ ok: boolean; path?: string; status: string }>;
  export_adofai_dialog(): Promise<{ ok: boolean; path?: string; stats?: Record<string, unknown>; status: string }>;
};

declare global {
  interface Window {
    pywebview?: { api?: BackendApi };
  }
}

export async function getBackendApi(timeoutMs = 3000): Promise<BackendApi | null> {
  if (window.pywebview?.api) return window.pywebview.api;

  return await new Promise((resolve) => {
    const onReady = () => {
      window.clearTimeout(timer);
      resolve(window.pywebview?.api ?? null);
    };
    const timer = window.setTimeout(() => {
      window.removeEventListener("pywebviewready", onReady);
      resolve(null);
    }, timeoutMs);
    window.addEventListener("pywebviewready", onReady, { once: true });
  });
}
