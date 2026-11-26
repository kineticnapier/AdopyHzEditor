import type { AppState, BackendApi, NoteMutationResult } from "./bridge";

export type BlankWorkspaceOptions = { duration: number; midiMin: number; midiMax: number };
export type LanguageState = { current: string; available: string[] };
export type NewProjectDefaults = Partial<Record<"bpm" | "gridEnabled" | "snapEnabled" | "snapDiv" | "exportOctave" | "previewSound" | "previewVolume" | "colormap", number | boolean | string>>;
export type Preferences = {
  language: string;
  languages: string[];
  newProject: NewProjectDefaults;
  newProjectBuiltin: Required<NewProjectDefaults>;
  kpsLimit: number;
  hasExportDefaults: boolean;
  checkUpdates: boolean;
  reopenLastProject: boolean;
  lastProject: string | null;
};
export type PreferenceChanges = Partial<Pick<Preferences, "language" | "newProject" | "kpsLimit" | "checkUpdates" | "reopenLastProject">>;
export type UpdateCheck = { ok: boolean; current: string; latest?: string; newer?: boolean; url: string; error?: string };

export type ToolBackendApi = BackendApi & {
  get_blank_workspace_defaults(): Promise<BlankWorkspaceOptions>;
  apply_blank_workspace(options: BlankWorkspaceOptions): Promise<AppState>;
  load_project_notes_only_dialog(): Promise<AppState>;
  merge_project_notes_dialog(): Promise<AppState>;
  export_selected_midi_dialog(indices: number[]): Promise<{ ok: boolean; path?: string; status: string }>;
  get_language_state(): Promise<LanguageState>;
  set_app_language(language: string): Promise<{ current: string; restartRequired: boolean; status: string }>;
  get_update_info(): Promise<{ version: string; text: string; info: string }>;
  check_for_update(): Promise<UpdateCheck>;
  get_preferences(): Promise<Preferences>;
  set_preferences(changes: PreferenceChanges): Promise<Preferences>;
  clear_adofai_export_defaults(): Promise<Preferences>;
  apply_startup_preferences(): Promise<{ state: AppState; checkUpdates: boolean; reopened: string | null }>;
};
