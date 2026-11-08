/** A backend may report a failed export as a resolved result, not an exception. */
export function exportFailureMessage(result: { ok: boolean; status: string }): string | null {
  if (result.ok) return null;
  const status = result.status.trim();
  // Closing the native Save dialog is not an export error.
  if (status.toLowerCase() === "cancelled" || status === "キャンセルしました") return null;
  return status || "ADOFAIの書き出しに失敗しました";
}

/** A cancelled Save dialog must not overwrite the editor's current status. */
export function exportStatusMessage(result: { ok: boolean; status: string }): string | null {
  return result.ok ? result.status : exportFailureMessage(result);
}
