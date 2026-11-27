import type { NoteDto } from "./bridge.ts";
import { midiLabel } from "./musicMath.ts";
import { t } from "../i18n/index.ts";

/** Describe selected members compactly, preserving full detail for up to 16 ranges. */
function selectionLabels(ids: readonly number[], label: (id: number) => string): string {
  const sorted = [...ids].sort((a, b) => a - b);
  if (sorted.length <= 4) return sorted.map(label).join(t("a11y.sep"));

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
  if (ranges.length > 16) {
    const sep = t("a11y.sep");
    return `${ranges.slice(0, 3).join(sep)}${sep}…${sep}${ranges[ranges.length - 1]}`;
  }
  return ranges.join(t("a11y.sep"));
}

/** Announce mouse, Inspector and keyboard selection changes to screen readers. */
export function selectionStatusText(
  notes: readonly NoteDto[],
  selected: readonly number[],
  trackIds: readonly number[],
  keyboardNote: number | null,
): string {
  // A selection is a set of valid IDs. Keep the spoken count consistent
  // with the actual unique selection and with selectionChangeText().
  const validSelected = [...new Set(selected.filter(
    index => Number.isSafeInteger(index) && index >= 0 && index < notes.length,
  ))];
  const validTracks = [...new Set(trackIds.filter(
    id => Number.isSafeInteger(id) && id >= 0,
  ))];
  // Inspector can select Tracks without clearing selected Notes. Announce both
  // layers so changing Tracks does not leave the aria-live text unchanged.
  const trackSummary = validTracks.length
    ? `${t("a11y.sep")}${t("a11y.tracks_selected", { count: validTracks.length, list: selectionLabels(validTracks, id => `ID ${id}`) })}`
    : "";
  const describeNote = (index: number): string => {
    const note = notes[index];
    return t((note.kind ?? "note") === "curve" ? "a11y.curve_note" : "a11y.note", { n: index + 1, start: note.start.toFixed(3), pitch: midiLabel(note.midi) });
  };
  if (keyboardNote !== null && validSelected.includes(keyboardNote)) {
    // The active keyboard note can remain unchanged while other selected notes change.
    // Include the members so an aria-live region receives different text.
    const members = validSelected.length > 1
      ? t("a11y.members", { list: selectionLabels(validSelected, index => t("a11y.nth", { n: index + 1 })) })
      : "";
    return `${describeNote(keyboardNote)}${t("a11y.sep")}${t("a11y.selected_count", { count: validSelected.length })}${members}${trackSummary}`;
  }
  // Count-only text stays identical when a different note/track is selected.
  // A live region needs a changed description to announce that transition.
  if (validSelected.length === 1) return `${describeNote(validSelected[0])}${t("a11y.sep")}${t("a11y.selected_count", { count: 1 })}${trackSummary}`;
  if (validSelected.length)
    return `${t("a11y.notes_selected", { count: validSelected.length, list: selectionLabels(validSelected, index => t("a11y.nth", { n: index + 1 })) })}${trackSummary}`;
  if (validTracks.length)
    return t("a11y.tracks_selected", { count: validTracks.length, list: selectionLabels(validTracks, id => `ID ${id}`) });
  return t("a11y.nothing");
}

/**
 * Explain a selection change when the bounded status preview cannot show it.
 * Report the actual added/removed members instead of a meaningless checksum.
 */
export function selectionChangeText(
  previousNotes: readonly number[],
  currentNotes: readonly number[],
  previousTracks: readonly number[],
  currentTracks: readonly number[],
  noteCount: number,
): string {
  const validNotes = (ids: readonly number[]) => new Set(
    ids.filter(id => Number.isSafeInteger(id) && id >= 0 && id < noteCount),
  );
  const validTracks = (ids: readonly number[]) => new Set(
    ids.filter(id => Number.isSafeInteger(id) && id >= 0),
  );
  const parts: string[] = [];
  const describeChanges = (
    previous: Set<number>,
    current: Set<number>,
    name: string,
    label: (id: number) => string,
  ) => {
    const added = [...current].filter(id => !previous.has(id));
    const removed = [...previous].filter(id => !current.has(id));
    if (added.length) parts.push(t("a11y.added", { name, list: selectionLabels(added, label) }));
    if (removed.length) parts.push(t("a11y.removed", { name, list: selectionLabels(removed, label) }));
  };
  describeChanges(validNotes(previousNotes), validNotes(currentNotes), t("a11y.notes"), id => t("a11y.nth", { n: id + 1 }));
  describeChanges(validTracks(previousTracks), validTracks(currentTracks), t("a11y.tracks"), id => `ID ${id}`);
  return parts.length ? t("a11y.changed", { list: parts.join(t("a11y.sep")) }) : "";
}
