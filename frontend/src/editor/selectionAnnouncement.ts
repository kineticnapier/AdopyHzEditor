import type { NoteDto } from "./bridge.ts";
import { midiLabel } from "./musicMath.ts";

/** Keep long selections readable without hiding the active end of a range. */
function selectionLabels(ids: readonly number[], label: (id: number) => string): string {
  const shown = ids.length <= 4 ? ids : [...ids.slice(0, 3), ids[ids.length - 1]];
  const labels = shown.map(label);
  if (ids.length > 4) labels.splice(3, 0, "…");
  return labels.join("、");
}

/** Announce mouse, Inspector and keyboard selection changes to screen readers. */
export function selectionStatusText(
  notes: readonly NoteDto[],
  selected: readonly number[],
  trackIds: readonly number[],
  keyboardNote: number | null,
): string {
  const validSelected = selected.filter(
    index => Number.isSafeInteger(index) && index >= 0 && index < notes.length,
  );
  const describeNote = (index: number): string => {
    const note = notes[index];
    return `${index + 1}番目の${(note.kind ?? "note") === "curve" ? "カーブノート" : "ノート"}、開始${note.start.toFixed(3)}秒、${midiLabel(note.midi)}`;
  };
  if (keyboardNote !== null && validSelected.includes(keyboardNote))
    return `${describeNote(keyboardNote)}、選択${validSelected.length}件`;
  // Count-only text stays identical when a different note/track is selected.
  // A live region needs a changed description to announce that transition.
  if (validSelected.length === 1) return `${describeNote(validSelected[0])}、選択1件`;
  if (validSelected.length)
    return `ノートを${validSelected.length}件選択中（${selectionLabels(validSelected, index => `${index + 1}番目`)}）`;
  if (trackIds.length)
    return `Trackを${trackIds.length}件選択中（${selectionLabels(trackIds, id => `ID ${id}`)}）`;
  return "選択なし";
}
