import type { NoteDto, ViewState } from "./bridge";

export type ShortcutActions = {
  notes: NoteDto[];
  selected: number[];
  playbackTime: number;
  view: ViewState;
  nudgeSeconds: number;
  openAudio(): void; saveProject(): void; saveProjectAs(): void; loadProject(): void; importMidi(): void;
  exportMidi(): void;
  openAdoExport(): void; openHelp(): void; setStatus(text: string): void; undo(): void; redo(): void;
  duplicate(): void; quantize(): void; select(indices: number[]): void; clearTracks(): void;
  copy(): void; cut(): void; paste(): void; applyTargetAngle(): void;
  move(indices: number[], dx: number, dy: number): void;
  stop(): void; play(): void; deleteSelected(): void; mode(value: ViewState["mode"]): void;
  seek(delta: number): void; seekTo(time: number): void; updateView(changes: Partial<ViewState>): void;
};

export type ShortcutEvent = Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "altKey" | "shiftKey" | "preventDefault"> & {
  target?: EventTarget | null;
  repeat?: boolean;
  getModifierState?: (key: string) => boolean;
};

/** Commit a focused editor field before saving, just as a toolbar click does. */
function commitFocusedEditBeforeSave(event: ShortcutEvent): void {
  const target = event.target as HTMLElement | null | undefined;
  const field = target?.closest?.("input,textarea,[contenteditable='true']") as HTMLElement | null | undefined;
  field?.blur();
}

/** Only explicitly assigned combinations may run while Ctrl/Meta/Alt is pressed. */
export function dispatchEditorShortcut(event: ShortcutEvent, a: ShortcutActions): void {
  const key = event.key.toLowerCase();
  const ctrl = event.ctrlKey || event.metaKey;
  const plain = !ctrl && !event.altKey;
  const handled = (action: () => void) => { event.preventDefault(); action(); };

  // AltGr can be reported as Ctrl+Alt, but is text input rather than a shortcut.
  if (event.getModifierState?.("AltGraph")) return;
  // Only explicitly assigned modified chords may reach the action table.
  // In particular, Ctrl+Shift+I/C/V/M must not import, copy, paste or export.
  if (ctrl && event.altKey && (key !== "a" || event.shiftKey)) return;
  if (ctrl && event.shiftKey && key !== "s" && key !== "z" &&
      key !== "arrowleft" && key !== "arrowright" &&
      key !== "arrowup" && key !== "arrowdown") return;

  // Held file shortcuts must not queue duplicate saves or native dialogs.
  // Consume repeats to avoid falling through to the browser shortcut.
  if (event.repeat && (
    key === "f1" ||
    (ctrl && !event.altKey &&
      (key === "s" || (!event.shiftKey && ["o", "l", "i", "m", "e"].includes(key))))
  )) {
    event.preventDefault();
    return;
  }

  if (key === "f1") return handled(a.openHelp);
  if (ctrl && key === "o") return handled(a.openAudio);
  if (ctrl && event.shiftKey && key === "s")
    return handled(() => { commitFocusedEditBeforeSave(event); a.saveProjectAs(); });
  if (ctrl && key === "s")
    return handled(() => { commitFocusedEditBeforeSave(event); a.saveProject(); });
  if (ctrl && key === "l") return handled(a.loadProject);
  if (ctrl && key === "i") return handled(a.importMidi);
  if (ctrl && key === "m") return handled(a.exportMidi);
  if (ctrl && key === "e") return handled(a.openAdoExport);
  if (ctrl && key === "z" && !event.shiftKey) return handled(a.undo);
  if ((ctrl && key === "y") || (ctrl && event.shiftKey && key === "z")) return handled(a.redo);
  if (ctrl && event.altKey && key === "a") return handled(a.applyTargetAngle);
  if (ctrl && !event.altKey && key === "a") return handled(() => a.select(a.notes.map((_, i) => i)));
  if (ctrl && key === "c") return handled(a.copy);
  if (ctrl && key === "x") return handled(a.cut);
  if (ctrl && key === "v") return handled(a.paste);
  if (ctrl && key === "d") return handled(a.duplicate);
  if (plain && key === "q") return handled(a.quantize);
  if (ctrl && event.shiftKey && !event.altKey && key === "arrowleft") return handled(() => a.move(a.selected, -a.nudgeSeconds, 0));
  if (ctrl && event.shiftKey && !event.altKey && key === "arrowright") return handled(() => a.move(a.selected, a.nudgeSeconds, 0));
  if (ctrl && event.shiftKey && !event.altKey && key === "arrowup") return handled(() => a.move(a.selected, 0, 1));
  if (ctrl && event.shiftKey && !event.altKey && key === "arrowdown") return handled(() => a.move(a.selected, 0, -1));
  if (ctrl && !event.altKey && key === " ") return handled(a.stop);
  if (plain && key === " ") return handled(a.play);
  if (plain && (key === "delete" || key === "backspace")) return handled(a.deleteSelected);
  if (plain && key === "escape") return handled(() => { a.clearTracks(); a.select([]); });
  // Tab and Shift+Tab intentionally retain native focus navigation.
  if (plain && key === "home") return handled(() => a.seekTo(0));
  if (plain && key === "1") return handled(() => a.mode("spec"));
  if (plain && key === "2") return handled(() => a.mode("notes"));
  if (plain && key === "3") return handled(() => a.mode("both"));
  if (plain && key === "arrowleft") return handled(() => a.seek(event.shiftKey ? -5 : -1));
  if (plain && key === "arrowright") return handled(() => a.seek(event.shiftKey ? 5 : 1));
  // The shortcut must not request a viewport outside MIDI 0..127.
  const scrollPitch = (delta: number) => {
    const pitchBottom = Math.max(0, Math.min(128 - a.view.visibleNotes, a.view.pitchBottom + delta));
    // Do not disable playback follow or enqueue set_view when already at the MIDI boundary.
    if (pitchBottom !== a.view.pitchBottom) a.updateView({ pitchBottom });
  };
  if ((plain && key === "w") || (ctrl && !event.altKey && key === "arrowup")) return handled(() => scrollPitch(12));
  if ((plain && key === "s") || (ctrl && !event.altKey && key === "arrowdown")) return handled(() => scrollPitch(-12));
  if (plain && key === "arrowup") return handled(() => scrollPitch(1));
  if (plain && key === "arrowdown") return handled(() => scrollPitch(-1));
}
