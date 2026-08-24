export type EditorSettings = {
  volume: number; speed: number; notePreview: boolean; previewVolume: number; previewOctave: number; previewSound: string;
  exportOctave: number; exportSemitone: number; gridEnabled: boolean; metronomeEnabled: boolean; bpm: number; offsetMs: number;
  metronomeVolume: number; snapEnabled: boolean; snapDiv: number; contrast: number; gamma: number; enhance: boolean;
  displayMode: string; harmonics: string; colormap: string; analysisProfile: string; cqtResolution: string;
  curveShape: string; curveInterpolation: string; targetAngle: number;
};
export type ViewState = { mode: "spec" | "notes" | "both"; start: number; windowSeconds: number; pitchBottom: number; visibleNotes: number };
export type PlaybackState = { time: number; duration: number; playing: boolean; available: boolean; error: string | null };
export type NoteDto = { start: number; end: number; midi: number; velocity?: number; kind?: "note" | "curve"; midi_end?: number; ctrl1_midi?: number; ctrl2_midi?: number; interpolation?: string; target_angle?: number };
export type AnalysisState = { available: boolean; duration: number; midiMin: number; midiMax: number; pitchStep: number };
export type AppState = { settings: EditorSettings; view: ViewState; playback: PlaybackState; audio: { path: string | null; name: string | null; loaded: boolean }; projectPath: string | null; notes: NoteDto[]; analysis: AnalysisState; busy: boolean; status: string; dirty: boolean };
export type SpectrogramPayload = { available: boolean; rows?: number; cols?: number; data?: string; duration?: number; midiMin?: number; midiMax?: number; pitchStep?: number };
export type CursorPeakPayload = { available: boolean; time?: number; cursorMidi?: number; cursorHz?: number; cursorName?: string; cursorCents?: number; peakMidi?: number; peakHz?: number; peakName?: string; peakCents?: number; peakDb?: number };
export type NoteMutationResult = { notes: NoteDto[]; status: string; index?: number; indices?: number[]; changed?: boolean };
export type NotePreset = { name: string; note: NoteDto; duration: number; kind: "note" | "curve" };
export type NotePresetResult = { presets: NotePreset[]; status: string };

export type AdoFAIExportOptions = {
  method: "rabbit_zip" | "angle_only" | "harmony"; baseBpm: number; angleOnlyBpm: number; harmonyMode: string; harmonyCustomSemitone: number;
  harmonyEpsilonMs: number; harmonyTuning: "equal temperament"; harmonyRootMode: string; harmonyTimingMode: "setspeed" | "angle-only" | "ratio-polyrhythm";
  harmonyVisualMode: string; harmonyVisualStep: number; harmonyPolyCycleAngle: number; harmonyPolyMaxDenominator: number; harmonyPolyRatioOctaveMode: "octave-folded" | "absolute";
  xMode: "floor" | "lowest_floor" | "round" | "ceil" | "fixed" | "target_bpm"; fixedX: number; targetBpm: number; angleCompressionMode: "auto" | "fixed"; angleCompressionFixedAngle: number; maxTiles: number; maxTilesPerNote: number;
  trackVisual: "normal" | "faint" | "very faint" | "hidden"; visualPathMode: "raw" | "upward" | "upward avoid" | "twirl upward"; visualPathAngle: number;
  visualPositionMode: "off" | "note step"; visualPositionX: number; visualPositionY: number; finalAngleMode: "scaled" | "cardinal" | "horizontal" | "custom";
  finalCustomAngle: number; finalCardinalStep: number; useProjectSong: boolean; copyProjectSong: boolean; songSourcePath: string; songOffsetAuto: boolean; songOffsetMs: number; selectedOnly: boolean;
};
export type AdoFAITilePreview = { points: Array<{ x: number; y: number; angle: number }>; stats: Record<string, unknown>; shownTiles: number; totalTiles: number; limited: boolean };
export type AdoFAIDebugPreview = { rows: Array<Record<string, unknown>>; summary: { rows: number; estimatedTiles: number; targetAngleUsed: number; targetAngleIgnored: number; finalVisualCorrections: number; warnings: number }; limited: boolean };
export type HelpPayload = { header: string; sections: Array<{ id: string; title: string; body: string }>; releasesUrl: string };

export type BackendApi = {
  ping(): Promise<{ ok: boolean; app: string; ui: string; capabilities: string[] }>;
  get_state(): Promise<AppState>; get_settings(): Promise<EditorSettings>; update_settings(changes: Partial<EditorSettings>): Promise<EditorSettings>;
  set_view(changes: Partial<ViewState>): Promise<ViewState>; fit_view(): Promise<ViewState>;
  open_audio(): Promise<AppState>; reanalyze_audio(): Promise<AppState>; get_spectrogram(maxColumns?: number): Promise<SpectrogramPayload>; get_cursor_peak(seconds: number, midi: number, searchRange?: number): Promise<CursorPeakPayload>;
  get_playback_state(): Promise<PlaybackState>; toggle_playback(): Promise<PlaybackState>; stop_playback(): Promise<PlaybackState>; seek_to(seconds: number): Promise<PlaybackState>; seek_relative(seconds: number): Promise<PlaybackState>;
  add_note(start: number, end: number, midi: number, kind?: string, endMidi?: number | null): Promise<NoteMutationResult>;
  delete_notes(indices: number[]): Promise<NoteMutationResult>; move_notes(indices: number[], dx: number, dy: number): Promise<NoteMutationResult>;
  resize_notes(indices: number[], edge: "start" | "end", deltaSeconds: number): Promise<NoteMutationResult>;
  set_note_properties(index: number, changes: Partial<{ start: number; end: number; duration: number; midi: number; velocity: number }>): Promise<NoteMutationResult>;
  duplicate_notes(indices: number[]): Promise<NoteMutationResult>; duplicate_notes_shifted(indices: number[], dx: number, dy: number): Promise<NoteMutationResult>;
  quantize_notes(indices: number[]): Promise<NoteMutationResult>; split_notes(indices: number[], atTime: number): Promise<NoteMutationResult>; cut_notes_range(indices: number[], startTime: number, endTime: number): Promise<NoteMutationResult>;
  bulk_edit_notes(indices: number[], changes: Partial<{ timeDelta: number; pitchDelta: number; duration: number; align: "start" | "end" | "" }>): Promise<NoteMutationResult>;
  get_note_presets(): Promise<NotePreset[]>; save_note_preset(name: string, index: number): Promise<NotePresetResult>; delete_note_preset(name: string): Promise<NotePresetResult>; insert_note_preset(name: string, atTime: number): Promise<NoteMutationResult>;
  apply_curve_shape(indices: number[]): Promise<NoteMutationResult>; apply_interpolation(indices: number[]): Promise<NoteMutationResult>; apply_target_angle(indices: number[]): Promise<NoteMutationResult>; clear_target_angle(indices: number[]): Promise<NoteMutationResult>;
  undo(): Promise<NoteMutationResult>; redo(): Promise<NoteMutationResult>; copy_notes(indices: number[]): Promise<{ status: string }>;
  cut_notes(indices: number[]): Promise<NoteMutationResult>; paste_notes(atTime: number): Promise<NoteMutationResult>;
  save_project_dialog(): Promise<AppState>; load_project_dialog(): Promise<AppState>; relink_project_audio_dialog(): Promise<AppState>; import_midi_dialog(): Promise<AppState>;
  close_window(): Promise<{ ok: boolean }>;
  export_midi_dialog(): Promise<{ ok: boolean; path?: string; status: string }>; export_adofai_dialog(): Promise<{ ok: boolean; path?: string; stats?: Record<string, unknown>; status: string }>;
  get_adofai_export_defaults(selectedIndices?: number[]): Promise<AdoFAIExportOptions>;
  choose_adofai_song_source(): Promise<{ ok: boolean; path?: string; name?: string; status: string }>;
  preview_adofai_tiles(options: AdoFAIExportOptions, selectedIndices?: number[]): Promise<AdoFAITilePreview>;
  preview_adofai_debug(options: AdoFAIExportOptions, selectedIndices?: number[]): Promise<AdoFAIDebugPreview>;
  export_adofai_advanced(options: AdoFAIExportOptions, selectedIndices?: number[]): Promise<{ ok: boolean; path?: string; copiedSong?: string | null; stats?: Record<string, unknown>; status: string }>;
  get_help_sections(): Promise<HelpPayload>; open_releases_page(): Promise<{ ok: boolean; url: string }>;
};

declare global { interface Window { pywebview?: { api?: BackendApi } } }
export async function getBackendApi(timeoutMs = 3000): Promise<BackendApi | null> {
  if (window.pywebview?.api) return window.pywebview.api;
  return await new Promise((resolve) => {
    const onReady = () => { window.clearTimeout(timer); resolve(window.pywebview?.api ?? null); };
    const timer = window.setTimeout(() => { window.removeEventListener("pywebviewready", onReady); resolve(null); }, timeoutMs);
    window.addEventListener("pywebviewready", onReady, { once: true });
  });
}
