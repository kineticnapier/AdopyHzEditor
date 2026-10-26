import { useEffect } from "react";
import type { BackendApi, NoteDto, ViewState } from "./bridge";

function isInteractiveTarget(target: EventTarget | null) {
  const element = target as HTMLElement | null;
  return Boolean(element?.closest("input,select,textarea,button,a,[contenteditable='true'],[role='dialog']"));
}

type Args = {
  disabled: boolean;
  api: BackendApi | null;
  notes: NoteDto[];
  selected: number[];
  playbackTime: number;
  view: ViewState;
  nudgeSeconds: number;
  openAudio(): void; saveProject(): void; saveProjectAs(): void; loadProject(): void; importMidi(): void;
  openAdoExport(): void; openHelp(): void; setStatus(text: string): void; undo(): void; redo(): void;
  duplicate(): void; quantize(): void; select(indices: number[]): void;
  copy(): void; cut(): void; paste(): void; applyTargetAngle(): void;
  move(indices: number[], dx: number, dy: number): void;
  stop(): void; play(): void; deleteSelected(): void; mode(value: ViewState["mode"]): void;
  seek(delta: number): void; updateView(changes: Partial<ViewState>): void;
};

export default function useEditorShortcuts(a: Args) {
  useEffect(() => {
    const api = a.api;
    if (!api) return;
    const handler = (event: KeyboardEvent) => {
      if (a.disabled || isInteractiveTarget(event.target)) return;
      const key = event.key.toLowerCase();
      const ctrl = event.ctrlKey || event.metaKey;
      const handled = (action: () => void) => { event.preventDefault(); action(); };

      if (event.key === "F1") return handled(a.openHelp);
      if (ctrl && key === "o") return handled(a.openAudio);
      if (ctrl && event.shiftKey && key === "s") return handled(a.saveProjectAs);
      if (ctrl && key === "s") return handled(a.saveProject);
      if (ctrl && key === "l") return handled(a.loadProject);
      if (ctrl && key === "i") return handled(a.importMidi);
      if (ctrl && key === "m") return handled(() => void api.export_midi_dialog().then(x => a.setStatus(x.status)));
      if (ctrl && key === "e") return handled(a.openAdoExport);
      if (ctrl && key === "z" && !event.shiftKey) return handled(a.undo);
      if ((ctrl && key === "y") || (ctrl && event.shiftKey && key === "z")) return handled(a.redo);
      if (ctrl && event.altKey && key === "a") return handled(a.applyTargetAngle);
      if (ctrl && !event.altKey && key === "a") return handled(() => a.select(a.notes.map((_, i) => i)));
      if (ctrl && key === "c") return handled(a.copy);
      if (ctrl && key === "x") return handled(a.cut);
      if (ctrl && key === "v") return handled(a.paste);
      if (ctrl && key === "d") return handled(a.duplicate);
      if (key === "q" && !ctrl && !event.altKey) return handled(a.quantize);
      if (ctrl && event.shiftKey && key === "arrowleft") return handled(() => a.move(a.selected, -a.nudgeSeconds, 0));
      if (ctrl && event.shiftKey && key === "arrowright") return handled(() => a.move(a.selected, a.nudgeSeconds, 0));
      if (ctrl && event.shiftKey && key === "arrowup") return handled(() => a.move(a.selected, 0, 1));
      if (ctrl && event.shiftKey && key === "arrowdown") return handled(() => a.move(a.selected, 0, -1));
      if (ctrl && key === " ") return handled(a.stop);
      if (key === " ") return handled(a.play);
      if (key === "delete" || key === "backspace") return handled(a.deleteSelected);
      if (key === "escape") return handled(() => a.select([]));
      // Tab and Shift+Tab intentionally retain native focus navigation.
      if (key === "1") return a.mode("spec");
      if (key === "2") return a.mode("notes");
      if (key === "3") return a.mode("both");
      if (key === "arrowleft") return handled(() => a.seek(event.shiftKey ? -5 : -1));
      if (key === "arrowright") return handled(() => a.seek(event.shiftKey ? 5 : 1));
      if (key === "w" || (ctrl && key === "arrowup")) return handled(() => a.updateView({ pitchBottom: a.view.pitchBottom + 12 }));
      if (key === "s" || (ctrl && key === "arrowdown")) return handled(() => a.updateView({ pitchBottom: a.view.pitchBottom - 12 }));
      if (key === "arrowup") return handled(() => a.updateView({ pitchBottom: a.view.pitchBottom + 1 }));
      if (key === "arrowdown") return handled(() => a.updateView({ pitchBottom: a.view.pitchBottom - 1 }));
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [a]);
}
