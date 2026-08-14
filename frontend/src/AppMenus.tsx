import type { MouseEvent } from "react";

type Props = {
  hasSelection: boolean;
  onBlankWorkspace(): void;
  onLoadNotesOnly(): void;
  onMergeProject(): void;
  onExportSelectedMidi(): void;
  onExportSelectedAdo(): void;
  onHarmonicDiagram(): void;
  onReanalyze(): void;
  onQuickHz(): void;
  onLanguage(): void;
  onUpdates(): void;
  onHelp(): void;
};

function closeMenu(event: MouseEvent<HTMLElement>) {
  event.currentTarget.closest("details")?.removeAttribute("open");
}

function MenuAction({ children, disabled, onClick }: { children: string; disabled?: boolean; onClick(): void }) {
  return <button disabled={disabled} onClick={(e) => { closeMenu(e); onClick(); }}>{children}</button>;
}

export default function AppMenus(p: Props) {
  return <nav className="app-menus">
    <details><summary>File</summary><div className="app-menu-popup">
      <MenuAction onClick={p.onBlankWorkspace}>Blank workspace…</MenuAction>
      <MenuAction onClick={p.onLoadNotesOnly}>Load project notes only…</MenuAction>
      <MenuAction onClick={p.onMergeProject}>Merge project notes…</MenuAction>
      <hr />
      <MenuAction disabled={!p.hasSelection} onClick={p.onExportSelectedMidi}>Export selected MIDI…</MenuAction>
      <MenuAction disabled={!p.hasSelection} onClick={p.onExportSelectedAdo}>Export selected ADOFAI…</MenuAction>
    </div></details>
    <details><summary>Edit</summary><div className="app-menu-popup"><MenuAction onClick={p.onHarmonicDiagram}>Insert Harmonic Diagram…</MenuAction></div></details>
    <details><summary>Analyze</summary><div className="app-menu-popup"><MenuAction onClick={p.onReanalyze}>Reanalyze audio</MenuAction></div></details>
    <details><summary>Tools</summary><div className="app-menu-popup"><MenuAction onClick={p.onQuickHz}>Quick Hz Tools…</MenuAction></div></details>
    <details><summary>Options</summary><div className="app-menu-popup"><MenuAction onClick={p.onLanguage}>Language…</MenuAction><MenuAction onClick={p.onUpdates}>Check for updates…</MenuAction></div></details>
    <details><summary>Help</summary><div className="app-menu-popup"><MenuAction onClick={p.onHelp}>Quick Start</MenuAction></div></details>
  </nav>;
}
