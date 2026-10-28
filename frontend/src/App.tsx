import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import AdoFAIExportDialog from "./dialogs/AdoFAIExportDialogJa";
import AppMenus from "./components/AppMenus";
import EditorCanvas, { type TrackHoverInfo, type TrackSelectionState } from "./editor/EditorCanvas";
import HelpDialog from "./dialogs/HelpDialog";
import SettingsPanel from "./settings/SettingsPanel";
import { BlankWorkspaceDialog, HarmonicDiagramDialog, QuickHzDialog, UpdateDialog } from "./dialogs/ToolDialogs";
import { useDialogAccessibility } from "./dialogs/useDialogAccessibility";
import Timeline from "./editor/Timeline";
import TopToolbar from "./components/TopToolbar";
import useEditorShortcuts from "./editor/useEditorShortcuts";
import { DirectSpectrumRegionCache, followViewportStart, nextPrefetchStart, spectrumLayersForMode, spectrumRegion, spectrumRegionKey } from "./editor/directSpectrum";
import type { TrackSelectionRange } from "./editor/trackSelection";
import { midiLabel, midiToHz } from "./editor/musicMath";
import { formatCursorPeakLabel } from "./editor/cursorStatus";
import { shouldShowCanvasEmptyHint } from "./editor/emptyState";
import "./dialogs.css";
import { getBackendApi, type AppState, type BackendApi, type DirectSpectrumPayload, type EditorSettings, type FrequencyTrackPayload, type NoteDto, type NoteMutationResult, type PlaybackState, type SpectrogramPayload, type ViewState } from "./api/bridge";
import { LatestRequestGate, SerialTaskQueue } from "./api/requestCoordinator";
import type { ToolBackendApi } from "./api/toolsBridge";

const defaultSettings:EditorSettings={volume:85,speed:1,notePreview:true,previewVolume:20,previewOctave:0,previewSound:"sine",exportOctave:0,exportSemitone:0,gridEnabled:false,metronomeEnabled:false,bpm:175,offsetMs:0,metronomeVolume:35,snapEnabled:false,snapDiv:1,contrast:115,gamma:75,enhance:true,displayMode:"wavetone",harmonics:"off",colormap:"wavetone",analysisProfile:"Normal",cqtResolution:"profile default",analysisSource:"cqt",spectrumThreshold:2,spectrumOpacity:70,spectrumLayerMode:"both",curveShape:"ease",curveInterpolation:"bezier_pitch",targetAngle:165};
const defaultView:ViewState={mode:"spec",start:0,windowSeconds:12,pitchBottom:12,visibleNotes:60};
const defaultPlayback:PlaybackState={time:0,duration:60,playing:false,available:false,error:null};
type ToolDialog="blank"|"quickHz"|"harmonic"|"update"|null;
type PendingDestructiveAction={label:string;run():void|Promise<void>;cancel?():void|Promise<void>};

function UnsavedChangesDialog({label,onSave,onDiscard,onCancel}:{label:string;onSave():void;onDiscard():void;onCancel():void}){
  const{dialogRef,titleId}=useDialogAccessibility(onCancel);
  return <div className="modal-backdrop"><section ref={dialogRef} tabIndex={-1} className="modal-window" role="dialog" aria-modal="true" aria-labelledby={titleId}><header className="modal-title"><strong id={titleId}>未保存の変更</strong></header><div className="dialog-body export-dialog-body"><div className="info-card">「{label}」の前に変更を保存しますか？</div></div><div className="dialog-footer"><button className="primary" onClick={onSave}>保存</button><button onClick={onDiscard}>保存せず続行</button><button onClick={onCancel}>キャンセル</button></div></section></div>;
}

export default function App(){
  const[api,setApi]=useState<BackendApi|null>(null),[connected,setConnected]=useState(false),[settings,setSettings]=useState(defaultSettings),[view,setView]=useState(defaultView),[playback,setPlayback]=useState(defaultPlayback),[notes,setNotes]=useState<NoteDto[]>([]),[selected,setSelected]=useState<number[]>([]),[spectrum,setSpectrum]=useState<SpectrogramPayload|null>(null),[directSpectrum,setDirectSpectrum]=useState<DirectSpectrumPayload|null>(null),[frequencyTracks,setFrequencyTracks]=useState<FrequencyTrackPayload|null>(null),[analysisAvailable,setAnalysisAvailable]=useState(false),[analysisSource,setAnalysisSource]=useState("cqt"),[analysisRevision,setAnalysisRevision]=useState(0),[viewportSize,setViewportSize]=useState({width:800,height:500}),[audioName,setAudioName]=useState<string|null>(null),[projectPath,setProjectPath]=useState<string|null>(null),[dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),[status,setStatus]=useState("準備完了");
  const[adoExportOpen,setAdoExportOpen]=useState(false),[helpSection,setHelpSection]=useState<string|null>(null),[toolDialog,setToolDialog]=useState<ToolDialog>(null),[followPlayback,setFollowPlayback]=useState(true);
  const[panelOpen,setPanelOpen]=useState(true),[trackSelection,setTrackSelection]=useState<TrackSelectionState>({ids:[],range:null,useRange:false}),[hoveredTrack,setHoveredTrack]=useState<TrackHoverInfo|null>(null);
  const[cursorReadout,setCursorReadout]=useState<{time:number;midi:number;peak?:string}|null>(null);
  const[pendingDestructive,setPendingDestructive]=useState<PendingDestructiveAction|null>(null);
  const peakRequest=useRef(0);
  const spectrumRequests=useRef(new LatestRequestGate());
  const settingsRequests=useRef(new LatestRequestGate());
  const settingsQueue=useRef(new SerialTaskQueue());
  const mutationQueue=useRef(new SerialTaskQueue());
  const spectrumRequest=useRef(0);
  const desiredSpectrumKey=useRef("");
  const trackRequest=useRef(0);
  const desiredTrackKey=useRef("");
  const spectrumLoader=useMemo(()=>api?new DirectSpectrumRegionCache(region=>api.get_spectrum_region(region.startTime,region.endTime,region.minMidi,region.maxMidi,region.pixelWidth,region.pixelHeight,region.threshold)):null,[api]);
  const trackLoader=useMemo(()=>api?new DirectSpectrumRegionCache<FrequencyTrackPayload>(region=>api.get_frequency_track_region(region.startTime,region.endTime,region.minMidi,region.maxMidi,region.pixelWidth,region.pixelHeight)):null,[api]);
  const spectrumLayers=spectrumLayersForMode(settings.spectrumLayerMode);
  const visibleSpectrum=analysisAvailable&&analysisSource!=="vorbis_direct"?spectrum:null;
  const visibleDirectSpectrum=analysisAvailable&&analysisSource==="vorbis_direct"&&spectrumLayers.raw?directSpectrum:null;
  const visibleFrequencyTracks=analysisAvailable&&analysisSource==="vorbis_direct"&&spectrumLayers.tracks?frequencyTracks:null;
  const toolsApi=api as ToolBackendApi|null;

  function applyState(state:AppState){setSettings(state.settings);setView(state.view);setPlayback(state.playback);setNotes(state.notes);setSelected(old=>old.filter(i=>i>=0&&i<state.notes.length));setTrackSelection({ids:[],range:null,useRange:false});setHoveredTrack(null);setAnalysisAvailable(state.analysis.available);setAnalysisSource(state.analysis.source??"cqt");setAnalysisRevision(v=>v+1);setAudioName(state.audio.name);setProjectPath(state.projectPath);setDirty(state.dirty);setBusy(state.busy);setStatus(state.status||"準備完了")}
  async function refreshSpectrum(backend=api,range:Pick<ViewState,"start"|"windowSeconds">=view){
    if(!backend)return;
    const request=spectrumRequests.current.issue();
    const columns=Math.max(256,Math.min(4096,Math.ceil(window.innerWidth*(window.devicePixelRatio||1))));
    const payload=await backend.get_spectrogram(columns,range.start,range.start+range.windowSeconds);
    if(spectrumRequests.current.isCurrent(request))setSpectrum(payload.available?payload:null);
  }

  useEffect(()=>{
    let active=true;
    void (async()=>{
      while(active){
        const backend=await getBackendApi();
        if(!active)return;
        if(!backend){await new Promise(resolve=>window.setTimeout(resolve,500));continue;}
        setApi(backend);setConnected((await backend.ping()).ok);
        if(!active)return;
        const state=await backend.get_state();
        if(!active)return;
        applyState(state);
        if(state.analysis.available&&state.analysis.source!=="vorbis_direct")await refreshSpectrum(backend,state.view);
        return;
      }
    })();
    return()=>{active=false};
  },[]);
  useEffect(()=>{if(!api)return;let active=true;const id=window.setInterval(()=>void api.get_playback_state().then(x=>{if(active)setPlayback(x)}).catch(()=>{}),50);return()=>{active=false;window.clearInterval(id)}},[api]);
  useEffect(()=>{if(!api||!analysisAvailable||analysisSource==="vorbis_direct")return;const id=window.setTimeout(()=>void refreshSpectrum(api,view),140);return()=>window.clearTimeout(id)},[api,analysisAvailable,analysisSource,settings.contrast,settings.gamma,settings.enhance,settings.displayMode,settings.harmonics,view.start,view.windowSeconds]);
  useLayoutEffect(()=>{
    spectrumLoader?.invalidate();
    spectrumRequest.current+=1;
  },[spectrumLoader,analysisAvailable,analysisSource,analysisRevision,settings.spectrumThreshold,view.windowSeconds,view.pitchBottom,view.visibleNotes,viewportSize.width,viewportSize.height]);
  useLayoutEffect(()=>{
    const request=++spectrumRequest.current;
    if(!spectrumLoader||!analysisAvailable||analysisSource!=="vorbis_direct"||!spectrumLayers.raw){desiredSpectrumKey.current="";setDirectSpectrum(null);return}
    const region=spectrumRegion(view,viewportSize,settings.spectrumThreshold),key=spectrumRegionKey(region);
    desiredSpectrumKey.current=key;
    const prefetch=()=>{
      if(!followPlayback||!playback.playing)return;
      const next=nextPrefetchStart(view.start,view.windowSeconds,playback.duration);
      if(next!==null)spectrumLoader.prefetch(spectrumRegion(view,viewportSize,settings.spectrumThreshold,next));
    };
    const cached=spectrumLoader.peek(region);
    if(cached){setDirectSpectrum(cached.available?cached:null);prefetch();return}
    setDirectSpectrum(null);
    void spectrumLoader.load(region).then(payload=>{
      if(request!==spectrumRequest.current||key!==desiredSpectrumKey.current||!payload)return;
      setDirectSpectrum(payload.available?payload:null);
      prefetch();
    }).catch(e=>{if(request===spectrumRequest.current)setStatus(String(e))});
  },[spectrumLoader,analysisAvailable,analysisSource,analysisRevision,spectrumLayers.raw,settings.spectrumThreshold,view.start,view.windowSeconds,view.pitchBottom,view.visibleNotes,viewportSize.width,viewportSize.height,followPlayback,playback.playing,playback.duration]);
  useLayoutEffect(()=>{
    trackLoader?.invalidate();
    trackRequest.current+=1;
  },[trackLoader,analysisAvailable,analysisSource,analysisRevision,view.windowSeconds,view.pitchBottom,view.visibleNotes,viewportSize.width,viewportSize.height]);
  useLayoutEffect(()=>{
    const request=++trackRequest.current;
    if(!trackLoader||!analysisAvailable||analysisSource!=="vorbis_direct"||!spectrumLayers.tracks){desiredTrackKey.current="";setFrequencyTracks(null);return}
    const region=spectrumRegion(view,viewportSize,0),key=spectrumRegionKey(region);
    desiredTrackKey.current=key;
    const prefetch=()=>{
      if(!followPlayback||!playback.playing)return;
      const next=nextPrefetchStart(view.start,view.windowSeconds,playback.duration);
      if(next!==null)trackLoader.prefetch(spectrumRegion(view,viewportSize,0,next));
    };
    const cached=trackLoader.peek(region);
    if(cached){setFrequencyTracks(cached.available?cached:null);prefetch();return}
    setFrequencyTracks(null);
    void trackLoader.load(region).then(payload=>{
      if(request!==trackRequest.current||key!==desiredTrackKey.current||!payload)return;
      setFrequencyTracks(payload.available?payload:null);
      prefetch();
    }).catch(e=>{if(request===trackRequest.current)setStatus(String(e))});
  },[trackLoader,analysisAvailable,analysisSource,analysisRevision,spectrumLayers.tracks,view.start,view.windowSeconds,view.pitchBottom,view.visibleNotes,viewportSize.width,viewportSize.height,followPlayback,playback.playing,playback.duration]);
  useEffect(()=>{
    if(!followPlayback||!playback.playing||view.windowSeconds<=0)return;
    const next=followViewportStart(view.start,view.windowSeconds,playback.time,playback.duration);
    if(next!==null){setView(v=>({...v,start:next}));void api?.set_view({start:next});}
  },[api,followPlayback,playback.duration,playback.playing,playback.time,view.start,view.windowSeconds]);

  async function patch(changes:Partial<EditorSettings>){
    const sourceChanged=changes.analysisSource!==undefined&&changes.analysisSource!==settings.analysisSource;
    if(sourceChanged){setAnalysisAvailable(false);setSpectrum(null);setDirectSpectrum(null);setFrequencyTracks(null)}
    setSettings(v=>({...v,...changes}));
    if(api){
      const request=settingsRequests.current.issue();
      const normalized=await settingsQueue.current.enqueue(()=>api.update_settings(changes));
      if(settingsRequests.current.isCurrent(request))setSettings(normalized);
      setDirty(true);
    }
  }
  async function updateView(changes:Partial<ViewState>){setFollowPlayback(false);setView(v=>({...v,...changes}));if(api)setView(await api.set_view(changes))}
  async function fitView(){setFollowPlayback(false);if(api)setView(await api.fit_view())}
  async function runStateAction(action:()=>Promise<AppState>,clearSelection=false){
    if(!api)return;
    setBusy(true);spectrumRequests.current.invalidate();spectrumRequest.current+=1;trackRequest.current+=1;
    try{
      const state=await action();applyState(state);if(clearSelection)setSelected([]);
      if(state.analysis.available&&state.analysis.source!=="vorbis_direct")await refreshSpectrum(api,state.view);else setSpectrum(null);
      if(!state.analysis.available){setDirectSpectrum(null);setFrequencyTracks(null)}
    }catch(e){setStatus(String(e))}finally{setBusy(false)}
  }
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
    setCursorReadout({time,midi});
    if(!api||!analysisAvailable||analysisSource==="vorbis_direct")return;
    const request=++peakRequest.current;
    try{
      const peak=await api.get_cursor_peak(time,midi,5);
      if(request!==peakRequest.current)return;
      const label=formatCursorPeakLabel(peak);
      if(label!==null)setCursorReadout({time:peak.time??time,midi,peak:label});
    }catch{/* Cursor diagnostics must not interrupt editing. */}
  }
  async function findTracks(range:TrackSelectionRange){
    if(!api)return [];
    try{
      const result=await api.find_frequency_tracks(range.startTime,range.endTime,range.minMidi,range.maxMidi);
      setStatus(result.status);
      return result.trackIds;
    }catch(e){setStatus(String(e));return []}
  }
  async function convertTracks(trackIds:number[],conversionMode:"fixed"|"curve",range:TrackSelectionRange|null){
    if(!api||!trackIds.length)return;
    setBusy(true);
    try{
      const result=await api.create_notes_from_tracks(trackIds,conversionMode,range?.startTime??null,range?.endTime??null);
      applyMutation(result,result.indices??[],result.changed!==false);
    }catch(e){setStatus(String(e))}finally{setBusy(false)}
  }
  async function convertSelectedTracks(conversionMode:"fixed"|"curve"){
    await convertTracks(trackSelection.ids,conversionMode,trackSelection.useRange?trackSelection.range:null);
  }

  const stateAction=(fn:()=>Promise<AppState>)=>void runStateAction(fn),nudgeSeconds=settings.snapEnabled?60/Math.max(1,settings.bpm)/Math.max(1,settings.snapDiv):.01;
  const openAudioSafely=()=>api&&requestDestructive("音声を開く",()=>runStateAction(()=>api.open_audio()));
  const loadProjectSafely=()=>api&&requestDestructive("プロジェクトを読み込む",()=>runStateAction(()=>api.load_project_dialog(),true));
  useEffect(()=>{if(!api)return;const requested=()=>setPendingDestructive({label:"ウィンドウを閉じる",run:async()=>{await api.close_window()},cancel:async()=>{await api.cancel_window_close()}});window.addEventListener("adopyhz-close-requested",requested);return()=>window.removeEventListener("adopyhz-close-requested",requested)},[api]);
  useEditorShortcuts({disabled:Boolean(adoExportOpen||helpSection||toolDialog||pendingDestructive),api,notes,selected,playbackTime:playback.time,view,nudgeSeconds,openAudio:openAudioSafely,saveProject:()=>api&&stateAction(()=>api.save_project_dialog()),saveProjectAs:()=>api&&stateAction(()=>api.save_project_as_dialog()),loadProject:loadProjectSafely,importMidi:()=>api&&void runStateAction(()=>api.import_midi_dialog(),true),openAdoExport:()=>setAdoExportOpen(true),openHelp:()=>setHelpSection("quick_start"),setStatus,undo:()=>void undo(),redo:()=>void redo(),duplicate:()=>void duplicate(),quantize:()=>void quantize(),select:setSelected,copy:()=>void copySelected(),cut:()=>void cutSelected(),paste:()=>void pasteAtPlayback(),applyTargetAngle:()=>void applyTargetAngle(),move:(i,dx,dy)=>void moveNotes(i,dx,dy),stop:()=>void stopPlayback(),play:()=>void togglePlayback(),deleteSelected:()=>void deleteNotes(),mode:v=>void mode(v),seek:d=>void seekRelative(d),updateView:c=>void updateView(c)});

  const menus=toolsApi?<AppMenus hasSelection={selected.length>0} hasProject={Boolean(projectPath)} onOpenAudio={openAudioSafely} onLoadProject={loadProjectSafely} onSaveProject={()=>api&&stateAction(()=>api.save_project_dialog())} onSaveProjectAs={()=>api&&stateAction(()=>api.save_project_as_dialog())} onImportMidi={()=>api&&void runStateAction(()=>api.import_midi_dialog(),true)} onExportMidi={()=>void api?.export_midi_dialog().then(x=>setStatus(x.status))} onExportAdo={()=>setAdoExportOpen(true)} onBlankWorkspace={()=>requestDestructive("空のワークスペースへ切り替える",()=>setToolDialog("blank"))} onLoadNotesOnly={()=>requestDestructive("ノートだけ読み込む",()=>runStateAction(()=>toolsApi.load_project_notes_only_dialog(),true))} onMergeProject={()=>void runStateAction(()=>toolsApi.merge_project_notes_dialog(),true)} onRelinkProjectAudio={()=>api&&stateAction(()=>api.relink_project_audio_dialog())} onExportSelectedMidi={()=>void toolsApi.export_selected_midi_dialog(selected).then(x=>setStatus(x.status))} onExportSelectedAdo={()=>{setAdoExportOpen(true);setStatus("ADOFAI出力で「選択ノートのみ」を使用できます")}} onUndo={()=>void undo()} onRedo={()=>void redo()} onDuplicate={()=>void duplicate()} onQuantize={()=>void quantize()} onSplit={()=>void splitSelected()} onHarmonicDiagram={()=>setToolDialog("harmonic")} onReanalyze={()=>stateAction(()=>toolsApi.reanalyze_audio())} onQuickHz={()=>setToolDialog("quickHz")} onUpdates={()=>setToolDialog("update")} onHelp={()=>setHelpSection("quick_start")}/>:null;

  return <div className="app">
    <TopToolbar connected={connected} audioName={audioName} dirty={dirty} playback={playback} view={view} menus={menus} panelOpen={panelOpen} onTogglePanel={()=>setPanelOpen(value=>!value)} onSeek={t=>void seekTo(t)} onStop={()=>void stopPlayback()} onPlay={()=>void togglePlayback()} onMode={v=>void mode(v)}/>
    <main className={panelOpen?"workspace":"workspace panel-collapsed"}><section className="editor"><div className="editor-stage"><EditorCanvas notes={notes} selected={selected} settings={settings} view={view} playback={playback} spectrum={visibleSpectrum} directSpectrum={visibleDirectSpectrum} frequencyTracks={visibleFrequencyTracks} trackSelection={trackSelection} onViewportSize={setViewportSize} onSelect={setSelected} onAdd={addNote} onMove={moveNotes} onDuplicateMove={duplicateMove} onResize={resizeNotes} onDelete={deleteNotes} onCutRange={cutRange} onSeek={seekTo} onView={updateView} onCursorMove={(time,midi)=>void cursorMoved(time,midi)} onTrackHover={setHoveredTrack} onTrackSelectionChange={selection=>{setTrackSelection(selection);if(selection.ids.length)setPanelOpen(true)}} onFindTracks={findTracks}/>{shouldShowCanvasEmptyHint(audioName,notes.length)&&<div className="canvas-empty" aria-hidden="true"><strong>ノートを追加するか、音源を開く</strong><span>ドラッグでノート作成 / ファイル → 音声を開く… <kbd>Ctrl+O</kbd></span><small>音源がない空のワークスペースでも採譜できます。</small></div>}</div><div className="canvas-readout" aria-live="off"><span>{cursorReadout?`${cursorReadout.time.toFixed(3)} s`:"—.—— s"}</span><span>{cursorReadout?`MIDI ${cursorReadout.midi.toFixed(2)}`:"MIDI —"}</span><span>{cursorReadout?`${midiLabel(cursorReadout.midi)} · ${midiToHz(cursorReadout.midi).toFixed(2)} Hz`:"Pitch —"}</span>{hoveredTrack&&<strong>Track #{hoveredTrack.id} · {hoveredTrack.noteName} · {hoveredTrack.duration.toFixed(3)} s · ${(hoveredTrack.magnitude*100).toFixed(1)}%</strong>}{!hoveredTrack&&cursorReadout?.peak&&<strong>{cursorReadout.peak}</strong>}</div><Timeline view={view} playback={playback} followPlayback={followPlayback} onFollowPlayback={setFollowPlayback} onView={c=>void updateView(c)} onFit={()=>void fitView()}/></section>{panelOpen&&<SettingsPanel api={api} settings={settings} notes={notes} selected={selected} audioName={audioName} busy={busy} analysisAvailable={analysisAvailable} actualAnalysisSource={analysisSource} trackSelection={trackSelection} hoveredTrack={hoveredTrack} onPatch={patch} onStateAction={runStateAction} onMutation={applyMutation} onStatus={setStatus} onTrackSelectionChange={setTrackSelection} onConvertTracks={convertSelectedTracks}/>}</main>
    <footer className="statusbar" role="status" aria-live="polite"><span>{busy?"処理中…":status}</span><span>{projectPath?projectPath.split(/[\\/]/).pop():"プロジェクトなし"} · Note {notes.length}個</span></footer>
    {adoExportOpen&&api&&<AdoFAIExportDialog api={api} selected={selected} onClose={()=>setAdoExportOpen(false)} onStatus={setStatus} onHelp={s=>{setAdoExportOpen(false);setHelpSection(s??"adofai_export")}}/>} {helpSection&&api&&<HelpDialog api={api} initialSection={helpSection} onClose={()=>setHelpSection(null)}/>} {toolDialog==="blank"&&toolsApi&&<BlankWorkspaceDialog api={toolsApi} onClose={()=>setToolDialog(null)} onStatus={setStatus} onState={state=>{applyState(state);setSpectrum(null);setDirectSpectrum(null);setFrequencyTracks(null)}}/>} {toolDialog==="quickHz"&&toolsApi&&<QuickHzDialog api={toolsApi} onClose={()=>setToolDialog(null)} onStatus={setStatus}/>} {toolDialog==="harmonic"&&toolsApi&&<HarmonicDiagramDialog api={toolsApi} selected={selected} onClose={()=>setToolDialog(null)} onStatus={setStatus} onMutation={applyMutation}/>} {toolDialog==="update"&&toolsApi&&<UpdateDialog api={toolsApi} onClose={()=>setToolDialog(null)} onStatus={setStatus}/>}
    {pendingDestructive&&<UnsavedChangesDialog label={pendingDestructive.label} onSave={()=>void saveThenContinue()} onDiscard={discardThenContinue} onCancel={()=>void cancelPendingDestructive()}/>}
  </div>;
}
