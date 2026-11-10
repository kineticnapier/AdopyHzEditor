import { useEffect, useId, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from "react";
import { consumeMenuEscape } from "./menuEscape";
import { canTransferDeferredMenuFocus, focusAdjacentMenu, isPlainMenuNavigationEvent, menuHoverFocusOrigin, nextMenuId, restoreMenuTriggerFocus } from "./menuNavigation";

type Props = {
  hasSelection:boolean;
  hasProject:boolean;
  onOpenAudio():void;
  onLoadProject():void;
  onSaveProject():void;
  onSaveProjectAs():void;
  onImportMidi():void;
  onExportMidi():void;
  onExportAdo():void;
  onBlankWorkspace():void;
  onLoadNotesOnly():void;
  onMergeProject():void;
  onRelinkProjectAudio():void;
  onExportSelectedMidi():void;
  onExportSelectedAdo():void;
  onUndo():void;
  onRedo():void;
  onDuplicate():void;
  onQuantize():void;
  onSplit():void;
  onHarmonicDiagram():void;
  onReanalyze():void;
  onUpdates():void;
  onHelp():void;
};

type MenuId="file"|"edit"|"analyze"|"tools"|"options"|"help";
type MenuProps={id:MenuId;label:string;active:MenuId|null;setActive(v:MenuId|null):void;children:ReactNode};

function Menu({id,label,active,setActive,children}:MenuProps){
  const open=active===id;
  const popupId=useId(),triggerId=useId(),popupRef=useRef<HTMLDivElement>(null);
  const focusItem=(edge:"first"|"last")=>window.requestAnimationFrame(()=>{const items=popupRef.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)');items?.[edge==="first"?0:Math.max(0,items.length-1)]?.focus()});
  function navigate(event:ReactKeyboardEvent<HTMLDivElement>){
    if(!isPlainMenuNavigationEvent(event.nativeEvent))return;
    const items=Array.from(popupRef.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')??[]),index=items.indexOf(document.activeElement as HTMLButtonElement);
    if(event.key==="ArrowDown"){event.preventDefault();items[(index+1+items.length)%items.length]?.focus()}
    else if(event.key==="ArrowUp"){event.preventDefault();items[(index-1+items.length)%items.length]?.focus()}
    else if(event.key==="Home"){event.preventDefault();items[0]?.focus()}
    else if(event.key==="End"){event.preventDefault();items.at(-1)?.focus()}
  }
  return <div className={open?"app-menu open":"app-menu"} onMouseEnter={event=>{
    if(active===null||open)return;
    const focusedBeforeSwitch=document.activeElement;
    const origin=menuHoverFocusOrigin(active,focusedBeforeSwitch);
    const root=event.currentTarget.closest<HTMLElement>(".app-menus");
    setActive(id);
    // Do not override a new focus destination chosen before the next frame.
    if(origin)window.requestAnimationFrame(()=>{
      if(canTransferDeferredMenuFocus(focusedBeforeSwitch,document.activeElement,document.body,document.documentElement))
        focusAdjacentMenu(root,id,origin==="popup",true);
    });
  }}>
    <button id={triggerId} className="app-menu-trigger" data-menu-id={id} type="button" aria-haspopup="menu" aria-expanded={open} aria-controls={open?popupId:undefined} onKeyDown={event=>{if(!isPlainMenuNavigationEvent(event.nativeEvent))return;if(event.key==="ArrowDown"||event.key==="Enter"||event.key===" "){event.preventDefault();setActive(id);focusItem("first")}else if(event.key==="ArrowUp"){event.preventDefault();setActive(id);focusItem("last")}}} onClick={()=>setActive(open?null:id)}>{label}</button>
    {open&&<div ref={popupRef} id={popupId} data-menu-popup={id} className="app-menu-popup" role="menu" aria-labelledby={triggerId} onKeyDown={navigate}>{children}</div>}
  </div>;
}

function Action({children,shortcut,disabled,onClick,close}:{children:string;shortcut?:string;disabled?:boolean;onClick():void;close():void}){
  return <button type="button" role="menuitem" disabled={disabled} onClick={()=>{close();onClick()}}><span>{children}</span>{shortcut&&<kbd>{shortcut}</kbd>}</button>;
}

export default function AppMenus(p:Props){
  const[active,setActive]=useState<MenuId|null>(null);
  const rootRef=useRef<HTMLElement>(null);
  const focusTrigger=(id:MenuId)=>window.requestAnimationFrame(()=>restoreMenuTriggerFocus(rootRef.current,id,document.activeElement,document.body,document.documentElement));
  useEffect(()=>{
    const down=(e:PointerEvent)=>{const r=rootRef.current;if(r&&!r.contains(e.target as Node))setActive(null)};
    const key=(e:KeyboardEvent)=>{consumeMenuEscape(e,active,id=>{setActive(null);focusTrigger(id)})};
    window.addEventListener("pointerdown",down);
    window.addEventListener("keydown",key,true);
    return()=>{window.removeEventListener("pointerdown",down);window.removeEventListener("keydown",key,true)};
  },[active]);
  const close=()=>{const id=active;setActive(null);if(id)focusTrigger(id)};
  const menuIds:MenuId[]=["file","edit","analyze","tools","options","help"];
  function traverseMenus(event:ReactKeyboardEvent<HTMLElement>){
    if(!isPlainMenuNavigationEvent(event.nativeEvent))return;
    if(event.key!=="ArrowLeft"&&event.key!=="ArrowRight")return;
    const target=(event.target as HTMLElement).closest<HTMLButtonElement>("[data-menu-id]");
    const next=nextMenuId(menuIds,active,(target?.dataset.menuId as MenuId|undefined)??null,event.key);
    if(!next)return;
    event.preventDefault();
    const fromPopup=Boolean((event.target as HTMLElement).closest('[role="menu"]'));
    const focusedBeforeMove=document.activeElement;
    if(active)setActive(next);
    window.requestAnimationFrame(()=>{
      if(canTransferDeferredMenuFocus(focusedBeforeMove,document.activeElement,document.body,document.documentElement))
        focusAdjacentMenu(rootRef.current,next,Boolean(active && fromPopup),Boolean(active));
    });
  }
  return <nav className="app-menus" aria-label="アプリケーションメニュー" ref={rootRef} onKeyDown={traverseMenus} onBlur={event=>{if(active&&!event.currentTarget.contains(event.relatedTarget as Node|null))setActive(null)}}>
    <Menu id="file" label="ファイル" active={active} setActive={setActive}>
      <Action close={close} shortcut="Ctrl+O" onClick={p.onOpenAudio}>音声を開く…</Action>
      <Action close={close} shortcut="Ctrl+L" onClick={p.onLoadProject}>プロジェクトを開く…</Action>
      <Action close={close} shortcut="Ctrl+S" onClick={p.onSaveProject}>保存</Action>
      <Action close={close} shortcut="Ctrl+Shift+S" onClick={p.onSaveProjectAs}>名前を付けて保存…</Action>
      <hr/>
      <Action close={close} shortcut="Ctrl+I" onClick={p.onImportMidi}>MIDIを読み込む…</Action>
      <Action close={close} shortcut="Ctrl+M" onClick={p.onExportMidi}>MIDIを書き出す…</Action>
      <Action close={close} shortcut="Ctrl+E" onClick={p.onExportAdo}>ADOFAIを書き出す…</Action>
      <hr/>
      <Action close={close} onClick={p.onBlankWorkspace}>空のワークスペース…</Action>
      <Action close={close} onClick={p.onLoadNotesOnly}>ノートだけ読み込む…</Action>
      <Action close={close} onClick={p.onMergeProject}>プロジェクトのノートを結合…</Action>
      <Action close={close} disabled={!p.hasProject} onClick={p.onRelinkProjectAudio}>プロジェクト音源を再指定…</Action>
      <hr/>
      <Action close={close} disabled={!p.hasSelection} onClick={p.onExportSelectedMidi}>選択ノートをMIDI出力…</Action>
      <Action close={close} disabled={!p.hasSelection} onClick={p.onExportSelectedAdo}>選択ノートをADOFAI出力…</Action>
    </Menu>
    <Menu id="edit" label="編集" active={active} setActive={setActive}>
      <Action close={close} shortcut="Ctrl+Z" onClick={p.onUndo}>元に戻す</Action>
      <Action close={close} shortcut="Ctrl+Y" onClick={p.onRedo}>やり直す</Action>
      <hr/>
      <Action close={close} shortcut="Ctrl+D" disabled={!p.hasSelection} onClick={p.onDuplicate}>選択ノートを複製</Action>
      <Action close={close} shortcut="Q" disabled={!p.hasSelection} onClick={p.onQuantize}>選択ノートをクオンタイズ</Action>
      <Action close={close} disabled={!p.hasSelection} onClick={p.onSplit}>再生位置で分割</Action>
    </Menu>
    <Menu id="analyze" label="解析" active={active} setActive={setActive}>
      <Action close={close} onClick={p.onReanalyze}>音声を再解析</Action>
    </Menu>
    <Menu id="tools" label="ツール" active={active} setActive={setActive}>
      <Action close={close} onClick={p.onHarmonicDiagram}>倍音ダイアグラムを挿入…</Action>
    </Menu>
    <Menu id="options" label="オプション" active={active} setActive={setActive}>
      <Action close={close} onClick={p.onUpdates}>更新を確認…</Action>
    </Menu>
    <Menu id="help" label="ヘルプ" active={active} setActive={setActive}>
      <Action close={close} shortcut="F1" onClick={p.onHelp}>クイックスタート</Action>
    </Menu>
  </nav>;
}
