import type { AppState, BackendApi, NoteMutationResult } from "./bridge";

export type BlankWorkspaceOptions = { duration: number; midiMin: number; midiMax: number };
export type HarmonicDiagramOptions = { rootHz: number; rootShift: string; base1dOffset: number; harmonics: string; timeUnit: "seconds" | "beats"; bpm: number; start: number; duration: number; edo: number; offset: number };
export type HarmonicPreview = { rows: Array<{ local: string; dimension: string; ratio: string; hz: number; midi: number; pitchNumber: number }>; startSeconds: number; endSeconds: number; durationSeconds: number };
export type LanguageState = { current: string; available: string[] };

export type ToolBackendApi = BackendApi & {
  get_blank_workspace_defaults(): Promise<BlankWorkspaceOptions>;
  apply_blank_workspace(options: BlankWorkspaceOptions): Promise<AppState>;
  load_project_notes_only_dialog(): Promise<AppState>;
  merge_project_notes_dialog(): Promise<AppState>;
  export_selected_midi_dialog(indices: number[]): Promise<{ ok: boolean; path?: string; status: string }>;
  get_harmonic_diagram_defaults(selectedIndices?: number[]): Promise<HarmonicDiagramOptions>;
  preview_harmonic_diagram(options: HarmonicDiagramOptions): Promise<HarmonicPreview>;
  insert_harmonic_diagram(options: HarmonicDiagramOptions): Promise<NoteMutationResult>;
  get_language_state(): Promise<LanguageState>;
  set_app_language(language: string): Promise<{ current: string; restartRequired: boolean; status: string }>;
  get_update_info(): Promise<{ version: string; text: string; info: string }>;
};
