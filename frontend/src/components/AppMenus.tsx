import { useEffect, useRef, useState, type ReactNode } from "react";

type Props = {
  hasSelection:boolean; hasProject:boolean;
  onBlankWorkspace():void; onLoadNotesOnly():void; onMergeProject():void; onRelinkProjectAudio():void; onExportSelectedMidi():void; onExportSelectedAdo():void;
  onDuplicate():void; onQuantize():void; onSplit():void; onHarmonicDiagram():void; onReanalyze():void; onQuickHz():void; onUpdates():void; onHelp():void;
};
type MenuId="file"|"edit"|"analyze"|"tools"|"options"|"help";
type MenuProps={id:MenuId;label:string;active:MenuId|null;setActive(v:MenuId|null):void;children:ReactNode};
function Menu({id,label,active,setActive,children}:MenuProps){const open=active===id;return <div className={open?"app-menu open":"app-menu"} onMouseEnter={()=>{if(active!==null&&!open)setActive(id)}}><button className="app-menu-trigger" type="button" aria-haspopup="menu" aria-expanded={open} onClick={()=>setActive(open?null:id)}>{label}</button>{open&&<div className="app-menu-popup" role="menu">{children}</div>}</div>}
function Action({children,disabled,onClick,close}:{children:string;disabled?:boolean;onClick():void;close():void}){return <button type="button" role="menuitem" disabled={disabled} onClick={()=>{close();onClick()}}>{children}</button>}
export default function AppMenus(p:Props){const[active,setActive]=useState<MenuId|null>(null);const rootRef=useRef<HTMLElement>(null);useEffect(()=>{const down=(e:PointerEvent)=>{const r=rootRef.current;if(r&&!r.contains(e.target as Node))setActive(null)};const key=(e:KeyboardEvent)=>{if(e.key==="Escape")setActive(null)};window.addEventListener("pointerdown",down);window.addEventListener("keydown",key);return()=>{window.removeEventListener("pointerdown",down);window.removeEventListener("keydown",key)}},[]);const close=()=>setActive(null);return <nav className="app-menus" ref={rootRef}>
  <Menu id="file" label="ファイル" active={active} setActive={setActive}><Action close={close} onClick={p.onBlankWorkspace}>空のワークスペース…</Action><Action close={close} onClick={p.onLoadNotesOnly}>ノートだけ読み込む…</Action><Action close={close} onClick={p.onMergeProject}>プロジェクトのノートを結合…</Action><Action close={close} disabled={!p.hasProject} onClick={p.onRelinkProjectAudio}>プロジェクト音源を再指定…</Action><hr/><Action close={close} disabled={!p.hasSelection} onClick={p.onExportSelectedMidi}>選択ノートをMIDI出力…</Action><Action close={close} disabled={!p.hasSelection} onClick={p.onExportSelectedAdo}>選択ノートをADOFAI出力…</Action></Menu>
  <Menu id="edit" label="編集" active={active} setActive={setActive}><Action close={close} disabled={!p.hasSelection} onClick={p.onDuplicate}>選択ノートを複製</Action><Action close={close} disabled={!p.hasSelection} onClick={p.onQuantize}>選択ノートをクオンタイズ</Action><Action close={close} disabled={!p.hasSelection} onClick={p.onSplit}>再生位置で分割</Action><hr/><Action close={close} onClick={p.onHarmonicDiagram}>倍音ダイアグラムを挿入…</Action></Menu>
  <Menu id="analyze" label="解析" active={active} setActive={setActive}><Action close={close} onClick={p.onReanalyze}>音声を再解析</Action></Menu>
  <Menu id="tools" label="ツール" active={active} setActive={setActive}><Action close={close} onClick={p.onQuickHz}>Quick Hz ツール…</Action></Menu>
  <Menu id="options" label="オプション" active={active} setActive={setActive}><Action close={close} onClick={p.onUpdates}>更新を確認…</Action></Menu>
  <Menu id="help" label="ヘルプ" active={active} setActive={setActive}><Action close={close} onClick={p.onHelp}>クイックスタート</Action></Menu>
</nav>}
