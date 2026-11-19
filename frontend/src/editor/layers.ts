import type { NoteDto } from "../api/bridge";

// Notes carry the layer they came from (e.g. a MIDI track name).  "" stands
// for notes without a layer, matching the backend's mutedLayers setting.
export type LayerSummary = { name: string; label: string; count: number };

export function noteLayer(note: NoteDto): string {
  return note.layer ?? "";
}

/** Layers in order of first appearance, with their note counts. */
export function summarizeLayers(notes: readonly NoteDto[]): LayerSummary[] {
  const counts = new Map<string, number>();
  for (const note of notes) {
    const name = noteLayer(note);
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  return [...counts].map(([name, count]) => ({ name, label: name || "レイヤーなし", count }));
}

export function isLayerMuted(note: NoteDto, muted: readonly string[] | undefined): boolean {
  return Boolean(muted && muted.length && muted.includes(noteLayer(note)));
}

/** New muted list with one layer switched on (on = true) or off. */
export function setLayerActive(muted: readonly string[] | undefined, name: string, on: boolean): string[] {
  const rest = (muted ?? []).filter((m) => m !== name);
  return on ? rest : [...rest, name];
}
