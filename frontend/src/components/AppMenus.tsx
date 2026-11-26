import { useEffect, useId, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from "react";
import { consumeMenuEscape } from "./menuEscape";
import { t, useLanguage } from "../i18n/index.ts";
import { canTransferDeferredMenuFocus, focusAdjacentMenu, focusOpenedMenuEdgeItem, isPlainMenuNavigationEvent, menuHoverFocusOrigin, nextMenuId, restoreMenuTriggerFocus } from "./menuNavigation";

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
  onMoveOctave(semitones:number):void;
  onSplit():void;
  onReanalyze():void;
  onUpdates():void;
  onPreferences():void;
  onHelp():void;
};

type MenuId="file"|"edit"|"analyze"|"options"|"help";
type MenuProps={id:MenuId;label:string;active:MenuId|null;setActive(v:MenuId|null):void;children:ReactNode};

function Menu({id,label,active,setActive,children}:MenuProps){
  const open=active===id;
  const popupId=useId(),triggerId=useId(),popupRef=useRef<HTMLDivElement>(null);
  const focusItem=(edge:"first"|"last")=>{
    const focusedBeforeOpen=document.activeElement;
    window.requestAnimationFrame(()=>focusOpenedMenuEdgeItem(
      popupRef.current,edge,focusedBeforeOpen,document.activeElement,document.body,document.documentElement
    ));
  };
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
  useLanguage();
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
  const menuIds:MenuId[]=["file","edit","analyze","options","help"];
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
  return <nav className="app-menus" aria-label={t("menu.app")} ref={rootRef} onKeyDown={traverseMenus} onBlur={event=>{if(active&&!event.currentTarget.contains(event.relatedTarget as Node|null))setActive(null)}}>
    <Menu id="file" label={t("menu.file")} active={active} setActive={setActive}>
      <Action close={close} shortcut="Ctrl+O" onClick={p.onOpenAudio}>{t("menu.open_audio")}</Action>
      <Action close={close} shortcut="Ctrl+L" onClick={p.onLoadProject}>{t("menu.open_project")}</Action>
      <Action close={close} shortcut="Ctrl+S" onClick={p.onSaveProject}>{t("menu.save")}</Action>
      <Action close={close} shortcut="Ctrl+Shift+S" onClick={p.onSaveProjectAs}>{t("menu.save_as")}</Action>
      <hr/>
      <Action close={close} shortcut="Ctrl+I" onClick={p.onImportMidi}>{t("menu.import_midi")}</Action>
      <Action close={close} shortcut="Ctrl+M" onClick={p.onExportMidi}>{t("menu.export_midi")}</Action>
      <Action close={close} shortcut="Ctrl+E" onClick={p.onExportAdo}>{t("menu.export_adofai")}</Action>
      <hr/>
      <Action close={close} onClick={p.onBlankWorkspace}>{t("menu.blank_workspace")}</Action>
      <Action close={close} onClick={p.onLoadNotesOnly}>{t("menu.load_notes_only")}</Action>
      <Action close={close} onClick={p.onMergeProject}>{t("menu.merge_project")}</Action>
      <Action close={close} disabled={!p.hasProject} onClick={p.onRelinkProjectAudio}>{t("menu.relink_audio")}</Action>
      <hr/>
      <Action close={close} disabled={!p.hasSelection} onClick={p.onExportSelectedMidi}>{t("menu.export_selected_midi")}</Action>
      <Action close={close} disabled={!p.hasSelection} onClick={p.onExportSelectedAdo}>{t("menu.export_selected_adofai")}</Action>
    </Menu>
    <Menu id="edit" label={t("menu.edit")} active={active} setActive={setActive}>
      <Action close={close} shortcut="Ctrl+Z" onClick={p.onUndo}>{t("menu.undo")}</Action>
      <Action close={close} shortcut="Ctrl+Y" onClick={p.onRedo}>{t("menu.redo")}</Action>
      <hr/>
      <Action close={close} shortcut="Ctrl+D" disabled={!p.hasSelection} onClick={p.onDuplicate}>{t("menu.duplicate")}</Action>
      <Action close={close} shortcut="Q" disabled={!p.hasSelection} onClick={p.onQuantize}>{t("menu.quantize")}</Action>
      <Action close={close} shortcut="Ctrl+Shift+PageUp" disabled={!p.hasSelection} onClick={()=>p.onMoveOctave(12)}>{t("menu.octave_up")}</Action>
      <Action close={close} shortcut="Ctrl+Shift+PageDown" disabled={!p.hasSelection} onClick={()=>p.onMoveOctave(-12)}>{t("menu.octave_down")}</Action>
      <Action close={close} disabled={!p.hasSelection} onClick={p.onSplit}>{t("menu.split")}</Action>
    </Menu>
    <Menu id="analyze" label={t("menu.analyze")} active={active} setActive={setActive}>
      <Action close={close} onClick={p.onReanalyze}>{t("menu.reanalyze")}</Action>
    </Menu>
    <Menu id="options" label={t("menu.options")} active={active} setActive={setActive}>
      <Action close={close} onClick={p.onPreferences}>{t("menu.preferences")}</Action>
      <Action close={close} onClick={p.onUpdates}>{t("menu.check_updates")}</Action>
    </Menu>
    <Menu id="help" label={t("menu.help")} active={active} setActive={setActive}>
      <Action close={close} shortcut="F1" onClick={p.onHelp}>{t("menu.quick_start")}</Action>
    </Menu>
  </nav>;
}
