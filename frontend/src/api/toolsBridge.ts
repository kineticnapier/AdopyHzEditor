import type { AppState, BackendApi, NoteMutationResult } from "./bridge";

export type BlankWorkspaceOptions = { duration: number; midiMin: number; midiMax: number };
export type LanguageState = { current: string; available: string[] };

export type ToolBackendApi = BackendApi & {
  get_blank_workspace_defaults(): Promise<BlankWorkspaceOptions>;
  apply_blank_workspace(options: BlankWorkspaceOptions): Promise<AppState>;
  load_project_notes_only_dialog(): Promise<AppState>;
  merge_project_notes_dialog(): Promise<AppState>;
  export_selected_midi_dialog(indices: number[]): Promise<{ ok: boolean; path?: string; status: string }>;
  get_language_state(): Promise<LanguageState>;
  set_app_language(language: string): Promise<{ current: string; restartRequired: boolean; status: string }>;
  get_update_info(): Promise<{ version: string; text: string; info: string }>;
};
