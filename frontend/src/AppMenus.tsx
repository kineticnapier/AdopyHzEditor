import { useEffect, useRef, useState, type ReactNode } from "react";

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

type MenuId = "file" | "edit" | "analyze" | "tools" | "options" | "help";

type MenuProps = {
  id: MenuId;
  label: string;
  active: MenuId | null;
  setActive(value: MenuId | null): void;
  children: ReactNode;
};

function Menu({ id, label, active, setActive, children }: MenuProps) {
  const open = active === id;
  return <div
    className={open ? "app-menu open" : "app-menu"}
    onMouseEnter={() => { if (active !== null && !open) setActive(id); }}
  >
    <button
      className="app-menu-trigger"
      type="button"
      aria-haspopup="menu"
      aria-expanded={open}
      onClick={() => setActive(open ? null : id)}
    >{label}</button>
    {open && <div className="app-menu-popup" role="menu">{children}</div>}
  </div>;
}

function MenuAction({ children, disabled, onClick, close }: { children: string; disabled?: boolean; onClick(): void; close(): void }) {
  return <button
    type="button"
    role="menuitem"
    disabled={disabled}
    onClick={() => {
      close();
      onClick();
    }}
  >{children}</button>;
}

export default function AppMenus(p: Props) {
  const [active, setActive] = useState<MenuId | null>(null);
  const rootRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      const root = rootRef.current;
      if (root && !root.contains(event.target as Node)) setActive(null);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setActive(null);
    };
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  const close = () => setActive(null);
  return <nav className="app-menus" ref={rootRef}>
    <Menu id="file" label="File" active={active} setActive={setActive}>
      <MenuAction close={close} onClick={p.onBlankWorkspace}>Blank workspace…</MenuAction>
      <MenuAction close={close} onClick={p.onLoadNotesOnly}>Load project notes only…</MenuAction>
      <MenuAction close={close} onClick={p.onMergeProject}>Merge project notes…</MenuAction>
      <hr />
      <MenuAction close={close} disabled={!p.hasSelection} onClick={p.onExportSelectedMidi}>Export selected MIDI…</MenuAction>
      <MenuAction close={close} disabled={!p.hasSelection} onClick={p.onExportSelectedAdo}>Export selected ADOFAI…</MenuAction>
    </Menu>
    <Menu id="edit" label="Edit" active={active} setActive={setActive}>
      <MenuAction close={close} onClick={p.onHarmonicDiagram}>Insert Harmonic Diagram…</MenuAction>
    </Menu>
    <Menu id="analyze" label="Analyze" active={active} setActive={setActive}>
      <MenuAction close={close} onClick={p.onReanalyze}>Reanalyze audio</MenuAction>
    </Menu>
    <Menu id="tools" label="Tools" active={active} setActive={setActive}>
      <MenuAction close={close} onClick={p.onQuickHz}>Quick Hz Tools…</MenuAction>
    </Menu>
    <Menu id="options" label="Options" active={active} setActive={setActive}>
      <MenuAction close={close} onClick={p.onLanguage}>Language…</MenuAction>
      <MenuAction close={close} onClick={p.onUpdates}>Check for updates…</MenuAction>
    </Menu>
    <Menu id="help" label="Help" active={active} setActive={setActive}>
      <MenuAction close={close} onClick={p.onHelp}>Quick Start</MenuAction>
    </Menu>
  </nav>;
}
