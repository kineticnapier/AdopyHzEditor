import type { NoteDto } from "./bridge.ts";
import { midiLabel } from "./musicMath.ts";

/** Describe selected members compactly, preserving full detail for up to 16 ranges. */
function selectionLabels(ids: readonly number[], label: (id: number) => string): string {
  const sorted = [...ids].sort((a, b) => a - b);
  if (sorted.length <= 4) return sorted.map(label).join("、");

  // Keep ordinary selections identifiable while compressing contiguous IDs.
  // Omitting the middle caused different selections to have identical aria-live text.
  const ranges: string[] = [];
  let first = sorted[0], last = first;
  for (const id of sorted.slice(1)) {
    if (id === last + 1) {
      last = id;
      continue;
    }
    ranges.push(first === last ? label(first) : `${label(first)}〜${label(last)}`);
    first = last = id;
  }
  ranges.push(first === last ? label(first) : `${label(first)}〜${label(last)}`);
  // Avoid reading thousands of sparse IDs aloud. A very fragmented selection
  // still uses a short preview; those rare middle-only changes need a
  // change-aware live announcement in a future UI pass.
  if (ranges.length > 16)
    return `${ranges.slice(0, 3).join("、")}、…、${ranges[ranges.length - 1]}`;
  return ranges.join("、");
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
  // Inspector can select Tracks without clearing selected Notes. Announce both
  // layers so changing Tracks does not leave the aria-live text unchanged.
  const trackSummary = trackIds.length
    ? `、Trackを${trackIds.length}件選択中（${selectionLabels(trackIds, id => `ID ${id}`)}）`
    : "";
  const describeNote = (index: number): string => {
    const note = notes[index];
    return `${index + 1}番目の${(note.kind ?? "note") === "curve" ? "カーブノート" : "ノート"}、開始${note.start.toFixed(3)}秒、${midiLabel(note.midi)}`;
  };
  if (keyboardNote !== null && validSelected.includes(keyboardNote)) {
    // The active keyboard note can remain unchanged while other selected notes change.
    // Include the members so an aria-live region receives different text.
    const members = validSelected.length > 1
      ? `（${selectionLabels(validSelected, index => `${index + 1}番目`)}）`
      : "";
    return `${describeNote(keyboardNote)}、選択${validSelected.length}件${members}${trackSummary}`;
  }
  // Count-only text stays identical when a different note/track is selected.
  // A live region needs a changed description to announce that transition.
  if (validSelected.length === 1) return `${describeNote(validSelected[0])}、選択1件${trackSummary}`;
  if (validSelected.length)
    return `ノートを${validSelected.length}件選択中（${selectionLabels(validSelected, index => `${index + 1}番目`)}）${trackSummary}`;
  if (trackIds.length)
    return `Trackを${trackIds.length}件選択中（${selectionLabels(trackIds, id => `ID ${id}`)}）`;
  return "選択なし";
}
