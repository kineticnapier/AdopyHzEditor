import { useState, type ReactNode } from "react";
import NotePresetPanel from "./NotePresetPanel";
import type { AppState, BackendApi, EditorSettings, NoteDto, NoteMutationResult } from "./bridge";

type Page = "note" | "playback" | "export" | "grid" | "view" | "analysis" | "curve";
const pages: Array<[Page, string]> = [["note","ノート"],["playback","再生"],["export","出力"],["grid","グリッド"],["view","表示"],["analysis","解析"],["curve","カーブ"]];
type Props = {
  api: BackendApi | null;
  settings: EditorSettings;
  notes: NoteDto[];
  selected: number[];
  playbackTime: number;
  audioName: string | null;
  busy: boolean;
  onPatch(changes: Partial<EditorSettings>): Promise<void>;
  onStateAction(action:()=>Promise<AppState>):Promise<void>;
  onMutation(result:NoteMutationResult,nextSelection?:number[]):void;
  onStatus(text:string):void;
};

export default function SettingsPanel({ api, settings, notes, selected, playbackTime, audioName, busy, onPatch, onStateAction, onMutation, onStatus }: Props) {
  const [page,setPage]=useState<Page>("note");
  const one=selected.length===1?notes[selected[0]]:null;
  const mutate=(p:Promise<NoteMutationResult>,sel=selected)=>void p.then(x=>onMutation(x,sel)).catch(e=>onStatus(String(e)));
  return <aside className="settings"><h2>設定</h2><nav>{pages.map(([id,label])=><button key={id} className={page===id?"active":""} onClick={()=>setPage(id)}>{label}</button>)}</nav><div className="settings-body">
    {page==="note"&&<>
      {selected.length===0&&<div className="hint">ノートを選択すると、位置・長さ・音高を数値でも編集できます。</div>}
      {selected.length>0&&<div className="hint">選択中: {selected.length}個 {one?`（${(one.kind??"note")==="curve"?"カーブ":"固定音"}）`:""}</div>}
      {one&&api&&<>
        <Row label="開始"><NumberInput value={one.start} min={0} max={36000} step={0.001} suffix=" 秒" onChange={v=>mutate(api.set_note_properties(selected[0],{start:v}),selected)} /></Row>
        <Row label="終了"><NumberInput value={one.end} min={0} max={36000} step={0.001} suffix=" 秒" onChange={v=>mutate(api.set_note_properties(selected[0],{end:v}),selected)} /></Row>
        <Row label="長さ"><NumberInput value={Math.max(0,one.end-one.start)} min={0.001} max={36000} step={0.001} suffix=" 秒" onChange={v=>mutate(api.set_note_properties(selected[0],{duration:v}),selected)} /></Row>
        <Row label="音高"><NumberInput value={one.midi} min={0} max={127} step={0.01} onChange={v=>mutate(api.set_note_properties(selected[0],{midi:v}),selected)} /></Row>
      </>}
      <div className="note-action-grid">
        <button disabled={!api||selected.length===0} onClick={()=>api&&void api.duplicate_notes(selected).then(x=>onMutation(x,x.indices??[]))}>複製</button>
        <button disabled={!api||selected.length===0} onClick={()=>api&&mutate(api.quantize_notes(selected),selected)}>クオンタイズ</button>
        <button disabled={!api||selected.length===0} onClick={()=>api&&void api.split_notes(selected,playbackTime).then(x=>onMutation(x,x.indices??selected)).catch(e=>onStatus(String(e)))}>再生位置で分割</button>
      </div>
      {selected.length>0&&api&&<BulkEditor api={api} selected={selected} onMutation={onMutation} onStatus={onStatus}/>} 
      <NotePresetPanel api={api} selected={selected} playbackTime={playbackTime} onMutation={onMutation} onStatus={onStatus}/>
      <div className="hint">中央ドラッグ: 移動 / 左右端: 長さ変更 / Alt+選択音ドラッグ: 複製 / Ctrl+ドラッグ: 範囲選択 / Alt+空白ドラッグ: カーブ作成</div>
    </>}
    {page==="playback"&&<>
      <Row label="楽曲音量"><Range value={settings.volume} onChange={v=>void onPatch({volume:v})}/></Row>
      <Row label="再生速度"><NumberInput value={settings.speed} min={.1} max={4} step={.05} suffix=" 倍" onChange={v=>void onPatch({speed:v})}/></Row>
      <Row label="ノート試聴"><input type="checkbox" checked={settings.notePreview} onChange={e=>void onPatch({notePreview:e.target.checked})}/></Row>
      <Row label="試聴音量"><Range value={settings.previewVolume} disabled={!settings.notePreview} onChange={v=>void onPatch({previewVolume:v})}/></Row>
      <Row label="試聴オクターブ"><NumberInput value={settings.previewOctave} min={-4} max={4} step={1} disabled={!settings.notePreview} onChange={v=>void onPatch({previewOctave:v})}/></Row>
      <Row label="試聴音色"><Select value={settings.previewSound} disabled={!settings.notePreview} options={[["sine","サイン波"],["piano","ピアノ"],["organ","オルガン"],["square","矩形波"],["triangle","三角波"]]} onChange={v=>void onPatch({previewSound:v})}/></Row>
    </>}
    {page==="export"&&<>
      <Row label="出力オクターブ"><NumberInput value={settings.exportOctave} min={-4} max={4} step={1} onChange={v=>void onPatch({exportOctave:v})}/></Row>
      <Row label="出力半音"><NumberInput value={settings.exportSemitone} min={-12} max={12} step={1} onChange={v=>void onPatch({exportSemitone:v})}/></Row>
      <div className="hint">出力音高 = ノート音高 + オクターブ×12 + 半音</div>
    </>}
    {page==="grid"&&<>
      <Row label="グリッド"><input type="checkbox" checked={settings.gridEnabled} onChange={e=>void onPatch({gridEnabled:e.target.checked})}/></Row>
      <Row label="メトロノーム"><input type="checkbox" checked={settings.metronomeEnabled} onChange={e=>void onPatch({metronomeEnabled:e.target.checked})}/></Row>
      <Row label="BPM"><NumberInput value={settings.bpm} min={1} max={10000} step={.1} onChange={v=>void onPatch({bpm:v})}/></Row>
      <Row label="オフセット"><NumberInput value={settings.offsetMs} min={-600000} max={600000} step={1} suffix=" ms" onChange={v=>void onPatch({offsetMs:v})}/></Row>
      <Row label="メトロ音量"><Range value={settings.metronomeVolume} disabled={!settings.metronomeEnabled} onChange={v=>void onPatch({metronomeVolume:v})}/></Row>
      <Row label="スナップ"><input type="checkbox" checked={settings.snapEnabled} onChange={e=>void onPatch({snapEnabled:e.target.checked})}/></Row>
      <Row label="分割数"><NumberInput value={settings.snapDiv} min={1} max={64} step={1} disabled={!settings.snapEnabled} onChange={v=>void onPatch({snapDiv:v})}/></Row>
    </>}
    {page==="view"&&<>
      <Row label="コントラスト"><Range value={settings.contrast} min={0} max={300} onChange={v=>void onPatch({contrast:v})}/></Row>
      <Row label="ガンマ"><Range value={settings.gamma} min={5} max={500} onChange={v=>void onPatch({gamma:v})}/></Row>
      <Row label="強調"><input type="checkbox" checked={settings.enhance} onChange={e=>void onPatch({enhance:e.target.checked})}/></Row>
      <Row label="描画"><Select value={settings.displayMode} options={[["wavetone","標準"],["ridge","輪郭"],["smooth","滑らか"]]} onChange={v=>void onPatch({displayMode:v})}/></Row>
      <Row label="倍音表示"><Select value={settings.harmonics} options={[["off","オフ"],["soft","弱"],["strong","強"]]} onChange={v=>void onPatch({harmonics:v})}/></Row>
      <Row label="配色"><Select value={settings.colormap} options={[["wavetone","WaveTone"],["viridis","Viridis"],["magma","Magma"],["inferno","Inferno"],["plasma","Plasma"],["gray","グレー"]]} onChange={v=>void onPatch({colormap:v})}/></Row>
    </>}
    {page==="analysis"&&<>
      <Row label="解析品質"><Select value={settings.analysisProfile} options={[["Fast","高速"],["Normal","標準"],["Precise","高精度"],["Full C0-C10","全域 C0-C10"]]} onChange={v=>void onPatch({analysisProfile:v})}/></Row>
      <Row label="CQT解像度"><Select value={settings.cqtResolution} options={[["profile default","自動"],["100 cents","100セント"],["50 cents","50セント"],["25 cents","25セント"],["12.5 cents","12.5セント"],["41 EDO","41平均律"],["53 EDO","53平均律"]]} onChange={v=>void onPatch({cqtResolution:v})}/></Row>
      <button className="wide" disabled={!api||!audioName||busy} onClick={()=>void onStateAction(()=>api!.reanalyze_audio())}>音声を再解析</button><div className="hint">解析設定の変更は再解析後に反映されます。</div>
    </>}
    {page==="curve"&&<>
      <Row label="カーブ形状"><Select value={settings.curveShape} options={[["ease","イーズ"],["s_curve","S字"],["linear","直線"],["ease_in","イーズイン"],["ease_out","イーズアウト"]]} onChange={v=>void onPatch({curveShape:v})}/></Row>
      <Row label="補間"><Select value={settings.curveInterpolation} options={[["bezier_pitch","ベジェ（音高）"],["linear_pitch","直線（音高）"],["linear_hz","直線（Hz）"],["bezier_hz","ベジェ（Hz）"]]} onChange={v=>void onPatch({curveInterpolation:v})}/></Row>
      <button className="wide" disabled={!api||selected.length===0} onClick={()=>void api!.apply_interpolation(selected).then(x=>onMutation(x,selected))}>補間を適用</button>
      <Row label="目標角度"><NumberInput value={settings.targetAngle} min={.001} max={359.999} step={.001} suffix="°" onChange={v=>void onPatch({targetAngle:v})}/></Row>
      <div className="button-row"><button disabled={!api||selected.length===0} onClick={()=>void api!.apply_target_angle(selected).then(x=>onMutation(x,selected))}>角度を適用</button><button disabled={!api||selected.length===0} onClick={()=>void api!.clear_target_angle(selected).then(x=>onMutation(x,selected))}>角度を解除</button></div>
    </>}
  </div></aside>;
}

function BulkEditor({api,selected,onMutation,onStatus}:{api:BackendApi;selected:number[];onMutation(result:NoteMutationResult,nextSelection?:number[]):void;onStatus(text:string):void}){
  const[timeDelta,setTimeDelta]=useState(0),[pitchDelta,setPitchDelta]=useState(0),[duration,setDuration]=useState(0.25);
  async function apply(changes:Parameters<BackendApi["bulk_edit_notes"]>[1]){try{const r=await api.bulk_edit_notes(selected,changes);onMutation(r,selected)}catch(e){onStatus(String(e))}}
  return <details className="note-tools-fold"><summary>一括編集</summary><div className="bulk-note-tools">
    <Row label="時間移動"><NumberInput value={timeDelta} min={-36000} max={36000} step={0.001} suffix=" 秒" onChange={setTimeDelta}/></Row>
    <Row label="音高移動"><NumberInput value={pitchDelta} min={-127} max={127} step={0.01} suffix=" 半音" onChange={setPitchDelta}/></Row>
    <button className="wide" onClick={()=>void apply({timeDelta,pitchDelta})}>移動を適用</button>
    <Row label="長さを統一"><NumberInput value={duration} min={0.001} max={36000} step={0.001} suffix=" 秒" onChange={setDuration}/></Row>
    <button className="wide" onClick={()=>void apply({duration})}>長さを適用</button>
    <div className="button-row"><button onClick={()=>void apply({align:"start"})}>開始を揃える</button><button onClick={()=>void apply({align:"end"})}>終了を揃える</button></div>
  </div></details>
}

function Row({label,children}:{label:string;children:ReactNode}){return <label className="row"><span>{label}</span><div>{children}</div></label>}
function Range({value,min=0,max=100,disabled=false,onChange}:{value:number;min?:number;max?:number;disabled?:boolean;onChange(v:number):void}){return <div className="range-wrap"><input type="range" min={min} max={max} value={value} disabled={disabled} onChange={e=>onChange(+e.target.value)}/><output>{value}</output></div>}
function NumberInput({value,min,max,step,suffix,disabled=false,onChange}:{value:number;min:number;max:number;step:number;suffix?:string;disabled?:boolean;onChange(v:number):void}){return <div className="number-wrap"><input type="number" value={Number.isFinite(value)?value:0} min={min} max={max} step={step} disabled={disabled} onChange={e=>{const v=+e.target.value;if(Number.isFinite(v))onChange(v)}}/>{suffix&&<span>{suffix}</span>}</div>}
function Select({value,options,disabled=false,onChange}:{value:string;options:Array<[string,string]>;disabled?:boolean;onChange(v:string):void}){return <select value={value} disabled={disabled} onChange={e=>onChange(e.target.value)}>{options.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select>}
