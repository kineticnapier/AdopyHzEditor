import type { NewProjectDefaults, Preferences, UpdateCheck } from "./toolsBridge";

export type NewProjectValues = Required<NewProjectDefaults>;

/** Values a new project starts from: saved ones over the built-in defaults. */
export function effectiveNewProject(prefs: Pick<Preferences, "newProject" | "newProjectBuiltin">): NewProjectValues {
  return { ...prefs.newProjectBuiltin, ...prefs.newProject } as NewProjectValues;
}

/** Only values that differ from the built-in defaults are saved. */
export function changedNewProject(values: NewProjectValues, builtin: NewProjectValues): NewProjectDefaults {
  const out: NewProjectDefaults = {};
  for (const key of Object.keys(builtin) as Array<keyof NewProjectValues>) {
    if (values[key] !== builtin[key]) out[key] = values[key];
  }
  return out;
}

/** One line for the result of asking GitHub for the latest release. */
export function updateCheckMessage(check: UpdateCheck): string {
  if (!check.ok) return `最新版を確認できませんでした（${check.error ?? "不明なエラー"}）。リリースページで確認できます。`;
  if (check.newer) return `新しいバージョン ${check.latest} があります。`;
  return `最新のバージョンです（${check.latest}）。`;
}
