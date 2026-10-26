import { useEffect, useRef, useState } from "react";
import AdoFAIExportDialog from "./dialogs/AdoFAIExportDialogJa";
import AppMenus from "./components/AppMenus";
import EditorCanvas from "./editor/EditorCanvas";
import HelpDialog from "./dialogs/HelpDialog";
import SettingsPanel from "./settings/SettingsPanel";
import { BlankWorkspaceDialog, HarmonicDiagramDialog, QuickHzDialog, UpdateDialog } from "./dialogs/ToolDialogs";
import Timeline from "./editor/Timeline";
import TopToolbar from "./components/TopToolbar";
import useEditorShortcuts from "./editor/useEditorShortcuts";
import "./dialogs.css";
import { getBackendApi, type AppState, type BackendApi, type EditorSettings, type NoteDto, type NoteMutationResult, type PlaybackState, type SpectrogramPayload, type ViewState } from "./api/bridge";
import { LatestRequestGate, SerialTaskQueue } from "./api/requestCoordinator";
import type { ToolBackendApi } from "./api/toolsBridge";

const defaultSettings:EditorSettings={volume:85,speed:1,notePreview:true,previewVolume:20,previewOctave:0,previewSound:"sine",exportOctave:0,exportSemitone:0,gridEnabled:false,metronomeEnabled:false,bpm:175,offsetMs:0,metronomeVolume:35,snapEnabled:false,snapDiv:1,contrast:115,gamma:75,enhance:true,displayMode:"wavetone",harmonics:"off",colormap:"wavetone",analysisProfile:"Normal",cqtResolution:"profile default",curveShape:"ease",curveInterpolation:"bezier_pitch",targetAngle:165};
const defaultView:ViewState={mode:"spec",start:0,windowSeconds:12,pitchBottom:12,visibleNotes:60};
const defaultPlayback:PlaybackState={time:0,duration:60,playing:false,available:false,error:null};
type ToolDialog="blank"|"quickHz"|"harmonic"|"update"|null;
type PendingDestructiveAction={label:string;run():void|Promise<void>;cancel?():void|Promise<void>};

function signedCents(value:number|undefined){const cents=Number.isFinite(value)?value!:0;return `${cents>=0?"+":""}${cents.toFixed(1)}c`;}

function UnsavedChangesDialog({label,onSave,onDiscard,onCancel}:{label:string;onSave():void;onDiscard():void;onCancel():void}){
  return <div className="modal-backdrop"><section className="modal-window"><header className="modal-title"><strong>未保存の変更</strong></header><div className="dialog-body export-dialog-body"><div className="info-card">「{label}」の前に変更を保存しますか？</div></div><div className="dialog-footer"><button className="primary" onClick={onSave}>保存</button><button onClick={onDiscard}>保存せず続行</button><button onClick={onCancel}>キャンセル</button></div></section></div>;
}

export default function App(){
  const[api,setApi]=useState<BackendApi|null>(null),[connected,setConnected]=useState(false),[settings,setSettings]=useState(defaultSettings),[view,setView]=useState(defaultView),[playback,setPlayback]=useState(defaultPlayback),[notes,setNotes]=useState<NoteDto[]>([]),[selected,setSelected]=useState<number[]>([]),[spectrum,setSpectrum]=useState<SpectrogramPayload|null>(null),[analysisAvailable,setAnalysisAvailable]=useState(false),[audioName,setAudioName]=useState<string|null>(null),[projectPath,setProjectPath]=useState<string|null>(null),[dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),[status,setStatus]=useState("準備完了");
  const[adoExportOpen,setAdoExportOpen]=useState(false),[helpSection,setHelpSection]=useState<string|null>(null),[toolDialog,setToolDialog]=useState<ToolDialog>(null),[followPlayback,setFollowPlayback]=useState(true);
  const[pendingDestructive,setPendingDestructive]=useState<PendingDestructiveAction|null>(null);
  const peakRequest=useRef(0);
  const spectrumRequests=useRef(new LatestRequestGate());
  const settingsRequests=useRef(new LatestRequestGate());
  const settingsQueue=useRef(new SerialTaskQueue());
  const mutationQueue=useRef(new SerialTaskQueue());
  const toolsApi=api as ToolBackendApi|null;

  function applyState(state:AppState){setSettings(state.settings);setView(state.view);setPlayback(state.playback);setNotes(state.notes);setSelected(old=>old.filter(i=>i>=0&&i<state.notes.length));setAnalysisAvailable(state.analysis.available);setAudioName(state.audio.name);setProjectPath(state.projectPath);setDirty(state.dirty);setBusy(state.busy);setStatus(state.status||"準備完了")}
  async function refreshSpectrum(backend=api){
    if(!backend)return;
    const request=spectrumRequests.current.issue();
    const p=await backend.get_spectrogram(1600);
    if(spectrumRequests.current.isCurrent(request))setSpectrum(p.available?p:null);
  }

  useEffect(()=>{
    let active=true;
    void (async()=>{
      while(active){
        const backend=await getBackendApi();
        if(!active)return;
        if(!backend){await new Promise(resolve=>window.setTimeout(resolve,500));continue;}
        setApi(backend);
        setConnected((await backend.ping()).ok);
        if(!active)return;
        const state=await backend.get_state();
        if(!active)return;
        applyState(state);
        if(state.analysis.available)await refreshSpectrum(backend);
        return;
      }
    })();
    return()=>{active=false};
  },[]);
  useEffect(()=>{if(!api)return;let active=true;const id=window.setInterval(()=>void api.get_playback_state().then(x=>{if(active)setPlayback(x)}).catch(()=>{}),50);return()=>{active=false;window.clearInterval(id)}},[api]);
  useEffect(()=>{if(!api||!analysisAvailable)return;const id=window.setTimeout(()=>void refreshSpectrum(api),140);return()=>window.clearTimeout(id)},[api,analysisAvailable,settings.contrast,settings.gamma,settings.enhance,settings.displayMode,settings.harmonics]);
  useEffect(()=>{
    if(!followPlayback||!playback.playing||view.windowSeconds<=0)return;
    const trigger=view.start+view.windowSeconds*.82;
    if(playback.time<view.start||playback.time>trigger){
      const max=Math.max(0,playback.duration-view.windowSeconds);
      const next=Math.max(0,Math.min(max,playback.time-view.windowSeconds*.2));
      if(Math.abs(next-view.start)>.001){setView(v=>({...v,start:next}));void api?.set_view({start:next});}
    }
  },[api,followPlayback,playback.duration,playback.playing,playback.time,view.start,view.windowSeconds]);

  async function patch(changes:Partial<EditorSettings>){
    setSettings(v=>({...v,...changes}));
    if(api){
      const request=settingsRequests.current.issue();
      const normalized=await settingsQueue.current.enqueue(()=>api.update_settings(changes));
      if(settingsRequests.current.isCurrent(request))setSettings(normalized);
      setDirty(true);
    }
  }
  async function updateView(changes:Partial<ViewState>){setView(v=>({...v,...changes}));if(api)setView(await api.set_view(changes))}
  async function fitView(){if(api)setView(await api.fit_view())}
  async function runStateAction(action:()=>Promise<AppState>,clearSelection=false){if(!api)return;setBusy(true);spectrumRequests.current.invalidate();try{const state=await action();applyState(state);if(clearSelection)setSelected([]);if(state.analysis.available)await refreshSpectrum(api);else setSpectrum(null)}catch(e){setStatus(String(e))}finally{setBusy(false)}}
  function requestDestructive(label:string,run:()=>void|Promise<void>,cancel?:()=>void|Promise<void>){if(dirty)setPendingDestructive({label,run,cancel});else void run()}
  async function cancelPendingDestructive(status?:string){const pending=pendingDestructive;setPendingDestructive(null);try{await pending?.cancel?.()}catch(e){setStatus(String(e));return}if(status)setStatus(status)}
  async function saveThenContinue(){const pending=pendingDestructive;if(!api||!pending)return;setBusy(true);let state:AppState|undefined;try{state=await api.save_project_dialog();applyState(state)}catch(e){setStatus(String(e))}finally{setBusy(false)}if(!state)return;if(state.dirty){await cancelPendingDestructive("保存がキャンセルされたため、操作を中止しました");return}setPendingDestructive(null);await pending.run()}
  function discardThenContinue(){const pending=pendingDestructive;if(!pending)return;setPendingDestructive(null);void pending.run()}
  function applyMutation(result:NoteMutationResult,selection?:number[],markDirty=true){setNotes(result.notes);setStatus(result.status);if(markDirty)setDirty(true);if(selection)setSelected(selection.filter(i=>i>=0&&i<result.notes.length));else setSelected(old=>old.filter(i=>i>=0&&i<result.notes.length))}
  async function queuedMutation(call:()=>Promise<NoteMutationResult>,selection:(result:NoteMutationResult)=>number[]|undefined,markDirty:(result:NoteMutationResult)=>boolean=()=>true){const result=await mutationQueue.current.enqueue(call);applyMutation(result,selection(result),markDirty(result));return result}
  async function addNote(start:number,end:number,midi:number,kind:"note"|"curve",endMidi:number){if(api)await queuedMutation(()=>api.add_note(start,end,midi,kind,endMidi),r=>r.index===undefined?[]:[r.index])}
  async function moveNotes(indices:number[],dx:number,dy:number){if(api&&indices.length)await queuedMutation(()=>api.move_notes(indices,dx,dy),()=>indices)}
  async function duplicateMove(indices:number[],dx:number,dy:number){if(api&&indices.length)await queuedMutation(()=>api.duplicate_notes_shifted(indices,dx,dy),r=>r.indices??[])}
  async function resizeNotes(indices:number[],edge:"start"|"end",delta:number){if(api&&indices.length)await queuedMutation(()=>api.resize_notes(indices,edge,delta),()=>indices)}
  async function deleteNotes(indices=selected){if(api&&indices.length)await queuedMutation(()=>api.delete_notes(indices),()=>[])}
  async function cutRange(indices:number[],start:number,end:number){if(api&&indices.length)await queuedMutation(()=>api.cut_notes_range(indices,start,end),r=>r.indices??[],r=>r.changed!==false)}
  async function duplicate(){if(api&&selected.length)await queuedMutation(()=>api.duplicate_notes(selected),r=>r.indices??[])}
  async function quantize(){if(api&&selected.length)await queuedMutation(()=>api.quantize_notes(selected),()=>selected)}
  async function splitSelected(){if(api&&selected.length)await queuedMutation(()=>api.split_notes(selected,playback.time),r=>r.indices?.length?r.indices:selected)}
  async function copySelected(){if(api)await mutationQueue.current.enqueue(()=>api.copy_notes(selected)).then(result=>setStatus(result.status))}
  async function cutSelected(){if(api)await queuedMutation(()=>api.cut_notes(selected),()=>[],r=>r.changed!==false)}
  async function pasteAtPlayback(){if(api)await queuedMutation(()=>api.paste_notes(playback.time),r=>r.indices??[],r=>r.changed!==false)}
  async function applyTargetAngle(){if(api)await queuedMutation(()=>api.apply_target_angle(selected),()=>selected,r=>r.changed!==false)}
  async function seekTo(t:number){if(api)setPlayback(await api.seek_to(t));else setPlayback(p=>({...p,time:t}))}
  async function togglePlayback(){if(api)setPlayback(await api.toggle_playback())}
  async function stopPlayback(){if(api)setPlayback(await api.stop_playback())}
  async function seekRelative(s:number){if(api)setPlayback(await api.seek_relative(s))}
  async function mode(v:ViewState["mode"]){await updateView({mode:v})}
  async function undo(){if(api)await queuedMutation(()=>api.undo(),()=>[],r=>r.changed!==false)}
  async function redo(){if(api)await queuedMutation(()=>api.redo(),()=>[],r=>r.changed!==false)}
  async function cursorMoved(time:number,midi:number){
    if(!api||!analysisAvailable)return;
    const request=++peakRequest.current;
    try{
      const peak=await api.get_cursor_peak(time,midi,5);
      if(request!==peakRequest.current||!peak.available)return;
      setStatus(`カーソル ${peak.time!.toFixed(3)}秒 / ${peak.cursorName}${signedCents(peak.cursorCents)} ${peak.cursorHz!.toFixed(2)}Hz | 近傍ピーク: ${peak.peakName}${signedCents(peak.peakCents)} ${peak.peakHz!.toFixed(2)}Hz (${peak.peakDb!.toFixed(1)} dB)`);
    }catch{/* Cursor diagnostics must not interrupt editing. */}
  }

  const stateAction=(fn:()=>Promise<AppState>)=>void runStateAction(fn),nudgeSeconds=settings.snapEnabled?60/Math.max(1,settings.bpm)/Math.max(1,settings.snapDiv):.01;
  const openAudioSafely=()=>api&&requestDestructive("音声を開く",()=>runStateAction(()=>api.open_audio()));
  const loadProjectSafely=()=>api&&requestDestructive("プロジェクトを読み込む",()=>runStateAction(()=>api.load_project_dialog(),true));
  useEffect(()=>{if(!api)return;const requested=()=>setPendingDestructive({label:"ウィンドウを閉じる",run:async()=>{await api.close_window()},cancel:async()=>{await api.cancel_window_close()}});window.addEventListener("adopyhz-close-requested",requested);return()=>window.removeEventListener("adopyhz-close-requested",requested)},[api]);
  useEditorShortcuts({disabled:Boolean(adoExportOpen||helpSection||toolDialog||pendingDestructive),api,notes,selected,playbackTime:playback.time,view,nudgeSeconds,openAudio:openAudioSafely,saveProject:()=>api&&stateAction(()=>api.save_project_dialog()),saveProjectAs:()=>api&&stateAction(()=>api.save_project_as_dialog()),loadProject:loadProjectSafely,importMidi:()=>api&&void runStateAction(()=>api.import_midi_dialog(),true),openAdoExport:()=>setAdoExportOpen(true),openHelp:()=>setHelpSection("quick_start"),setStatus,undo:()=>void undo(),redo:()=>void redo(),duplicate:()=>void duplicate(),quantize:()=>void quantize(),select:setSelected,copy:()=>void copySelected(),cut:()=>void cutSelected(),paste:()=>void pasteAtPlayback(),applyTargetAngle:()=>void applyTargetAngle(),move:(i,dx,dy)=>void moveNotes(i,dx,dy),stop:()=>void stopPlayback(),play:()=>void togglePlayback(),deleteSelected:()=>void deleteNotes(),mode:v=>void mode(v),seek:d=>void seekRelative(d),updateView:c=>void updateView(c)});

  const menus=toolsApi?<AppMenus hasSelection={selected.length>0} hasProject={Boolean(projectPath)} onSaveProjectAs={()=>api&&stateAction(()=>api.save_project_as_dialog())} onBlankWorkspace={()=>requestDestructive("空のワークスペースへ切り替える",()=>setToolDialog("blank"))} onLoadNotesOnly={()=>requestDestructive("ノートだけ読み込む",()=>runStateAction(()=>toolsApi.load_project_notes_only_dialog(),true))} onMergeProject={()=>void runStateAction(()=>toolsApi.merge_project_notes_dialog(),true)} onRelinkProjectAudio={()=>api&&stateAction(()=>api.relink_project_audio_dialog())} onExportSelectedMidi={()=>void toolsApi.export_selected_midi_dialog(selected).then(x=>setStatus(x.status))} onExportSelectedAdo={()=>{setAdoExportOpen(true);setStatus("ADOFAI出力で「選択ノートのみ」を使用できます")}} onDuplicate={()=>void duplicate()} onQuantize={()=>void quantize()} onSplit={()=>void splitSelected()} onHarmonicDiagram={()=>setToolDialog("harmonic")} onReanalyze={()=>stateAction(()=>toolsApi.reanalyze_audio())} onQuickHz={()=>setToolDialog("quickHz")} onUpdates={()=>setToolDialog("update")} onHelp={()=>setHelpSection("quick_start")}/>:null;

  return <div className="app">
    <TopToolbar connected={connected} busy={busy} audioName={audioName} dirty={dirty} playback={playback} view={view} menus={menus} onOpen={openAudioSafely} onLoadProject={loadProjectSafely} onSaveProject={()=>api&&stateAction(()=>api.save_project_dialog())} onSeek={t=>void seekTo(t)} onStop={()=>void stopPlayback()} onPlay={()=>void togglePlayback()} onSeekRelative={d=>void seekRelative(d)} onImportMidi={()=>api&&void runStateAction(()=>api.import_midi_dialog(),true)} onExportMidi={()=>void api?.export_midi_dialog().then(x=>setStatus(x.status))} onExportAdo={()=>setAdoExportOpen(true)} onHelp={()=>setHelpSection("quick_start")} onMode={v=>void mode(v)}/>
    <main className="workspace"><section className="editor"><EditorCanvas notes={notes} selected={selected} settings={settings} view={view} playback={playback} spectrum={spectrum} onSelect={setSelected} onAdd={addNote} onMove={moveNotes} onDuplicateMove={duplicateMove} onResize={resizeNotes} onDelete={deleteNotes} onCutRange={cutRange} onSeek={seekTo} onView={updateView} onCursorMove={(time,midi)=>void cursorMoved(time,midi)}/><Timeline view={view} playback={playback} followPlayback={followPlayback} onFollowPlayback={setFollowPlayback} onView={c=>void updateView(c)} onFit={()=>void fitView()}/></section><SettingsPanel api={api} settings={settings} notes={notes} selected={selected} playbackTime={playback.time} audioName={audioName} busy={busy} onPatch={patch} onStateAction={runStateAction} onMutation={applyMutation} onStatus={setStatus}/></main>
    <footer className="statusbar"><span>{busy?"処理中…":status}</span><span>{projectPath?projectPath.split(/[\\/]/).pop():"プロジェクトなし"} · ノート {notes.length}個</span></footer>
    {adoExportOpen&&api&&<AdoFAIExportDialog api={api} selected={selected} onClose={()=>setAdoExportOpen(false)} onStatus={setStatus} onHelp={s=>setHelpSection(s??"adofai_export")}/>} {helpSection&&api&&<HelpDialog api={api} initialSection={helpSection} onClose={()=>setHelpSection(null)}/>} {toolDialog==="blank"&&toolsApi&&<BlankWorkspaceDialog api={toolsApi} onClose={()=>setToolDialog(null)} onStatus={setStatus} onState={state=>{applyState(state);setSpectrum(null)}}/>} {toolDialog==="quickHz"&&toolsApi&&<QuickHzDialog api={toolsApi} onClose={()=>setToolDialog(null)} onStatus={setStatus}/>} {toolDialog==="harmonic"&&toolsApi&&<HarmonicDiagramDialog api={toolsApi} selected={selected} onClose={()=>setToolDialog(null)} onStatus={setStatus} onMutation={applyMutation}/>} {toolDialog==="update"&&toolsApi&&<UpdateDialog api={toolsApi} onClose={()=>setToolDialog(null)} onStatus={setStatus}/>} {pendingDestructive&&<UnsavedChangesDialog label={pendingDestructive.label} onSave={()=>void saveThenContinue()} onDiscard={discardThenContinue} onCancel={()=>void cancelPendingDestructive()}/>}
  </div>
}
