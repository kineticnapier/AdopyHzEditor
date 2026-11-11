import type { NoteDto } from "./bridge.ts";
import { midiLabel } from "./musicMath.ts";

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
  if (keyboardNote !== null && validSelected.includes(keyboardNote)) {
    const note = notes[keyboardNote];
    return `${keyboardNote + 1}番目の${(note.kind ?? "note") === "curve" ? "カーブノート" : "ノート"}、開始${note.start.toFixed(3)}秒、${midiLabel(note.midi)}、選択${validSelected.length}件`;
  }
  if (validSelected.length) return `ノートを${validSelected.length}件選択中`;
  if (trackIds.length) return `Trackを${trackIds.length}件選択中`;
  return "選択なし";
}
