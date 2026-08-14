import { useEffect } from "react";
import type { BackendApi, NoteDto, ViewState } from "./bridge";

function isEditingTarget(target: EventTarget | null) {
  const element = target as HTMLElement | null;
  if (!element) return false;
  return element instanceof HTMLInputElement || element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement || element.isContentEditable;
}

type Args = {
  api: BackendApi | null; notes: NoteDto[]; selected: number[]; playbackTime: number; view: ViewState; nudgeSeconds: number;
  openAudio(): void; saveProject(): void; loadProject(): void; importMidi(): void; setStatus(text: string): void;
  undo(): void; redo(): void; select(indices: number[]): void; applyMutation(result: any, selection?: number[]): void;
  move(indices: number[], dx: number, dy: number): void; stop(): void; play(): void; deleteSelected(): void;
  mode(value: ViewState["mode"]): void; seek(delta: number): void; updateView(changes: Partial<ViewState>): void;
};

export default function useEditorShortcuts(a: Args) {
  useEffect(() => {
    const api = a.api;
    if (!api) return;
    const handler = (event: KeyboardEvent) => {
      if (isEditingTarget(event.target) && event.key !== "Escape") return;
      const key = event.key.toLowerCase();
      const ctrl = event.ctrlKey || event.metaKey;
      if (ctrl && key === "o") { event.preventDefault(); a.openAudio(); return; }
      if (ctrl && key === "s") { event.preventDefault(); a.saveProject(); return; }
      if (ctrl && key === "l") { event.preventDefault(); a.loadProject(); return; }
      if (ctrl && key === "i") { event.preventDefault(); a.importMidi(); return; }
      if (ctrl && key === "m") { event.preventDefault(); void api.export_midi_dialog().then((x) => a.setStatus(x.status)); return; }
      if (ctrl && key === "e") { event.preventDefault(); void api.export_adofai_dialog().then((x) => a.setStatus(x.status)); return; }
      if (ctrl && key === "z" && !event.shiftKey) { event.preventDefault(); a.undo(); return; }
      if ((ctrl && key === "y") || (ctrl && event.shiftKey && key === "z")) { event.preventDefault(); a.redo(); return; }
      if (ctrl && key === "a") { event.preventDefault(); a.select(a.notes.map((_, i) => i)); return; }
      if (ctrl && key === "c") { event.preventDefault(); void api.copy_notes(a.selected).then((x) => a.setStatus(x.status)); return; }
      if (ctrl && key === "x") { event.preventDefault(); void api.cut_notes(a.selected).then((x) => a.applyMutation(x, [])); return; }
      if (ctrl && key === "v") { event.preventDefault(); void api.paste_notes(a.playbackTime).then((x) => a.applyMutation(x, x.indices ?? [])); return; }
      if (ctrl && event.altKey && key === "a") { event.preventDefault(); void api.apply_target_angle(a.selected).then((x) => a.applyMutation(x, a.selected)); return; }
      if (ctrl && event.shiftKey && key === "arrowleft") { event.preventDefault(); a.move(a.selected, -a.nudgeSeconds, 0); return; }
      if (ctrl && event.shiftKey && key === "arrowright") { event.preventDefault(); a.move(a.selected, a.nudgeSeconds, 0); return; }
      if (ctrl && event.shiftKey && key === "arrowup") { event.preventDefault(); a.move(a.selected, 0, 1); return; }
      if (ctrl && event.shiftKey && key === "arrowdown") { event.preventDefault(); a.move(a.selected, 0, -1); return; }
      if (ctrl && key === " ") { event.preventDefault(); a.stop(); return; }
      if (key === " ") { event.preventDefault(); a.play(); return; }
      if (key === "delete") { event.preventDefault(); a.deleteSelected(); return; }
      if (key === "escape") { event.preventDefault(); a.select([]); return; }
      if (key === "tab") { event.preventDefault(); const order: ViewState["mode"][] = ["spec", "notes", "both"]; a.mode(order[(order.indexOf(a.view.mode) + 1) % order.length]); return; }
      if (key === "1") { a.mode("spec"); return; }
      if (key === "2") { a.mode("notes"); return; }
      if (key === "3") { a.mode("both"); return; }
      if (key === "arrowleft") { event.preventDefault(); a.seek(event.shiftKey ? -5 : -1); return; }
      if (key === "arrowright") { event.preventDefault(); a.seek(event.shiftKey ? 5 : 1); return; }
      if (key === "w" || (ctrl && key === "arrowup")) { event.preventDefault(); a.updateView({ pitchBottom: a.view.pitchBottom + 12 }); return; }
      if (key === "s" || (ctrl && key === "arrowdown")) { event.preventDefault(); a.updateView({ pitchBottom: a.view.pitchBottom - 12 }); return; }
      if (key === "arrowup") { event.preventDefault(); a.updateView({ pitchBottom: a.view.pitchBottom + 1 }); return; }
      if (key === "arrowdown") { event.preventDefault(); a.updateView({ pitchBottom: a.view.pitchBottom - 1 }); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [a]);
}
