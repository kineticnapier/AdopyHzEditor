import { useState, type ReactNode } from "react";
import type { AppState, BackendApi, EditorSettings, NoteDto, NoteMutationResult } from "./bridge";

type Page="inspector"|"settings";
type Props={
  api:BackendApi|null;
  settings:EditorSettings;
  notes:NoteDto[];
  selected:number[];
  audioName:string|null;
  busy:boolean;
  analysisAvailable:boolean;
  actualAnalysisSource:string;
  onPatch(changes:Partial<EditorSettings>):Promise<void>;
  onStateAction(action:()=>Promise<AppState>):Promise<void>;
  onMutation(result:NoteMutationResult,nextSelection?:number[]):void;
  onStatus(text:string):void;
};

type CurveShapeState={mode:string;p1:number;p2:number};
function parseCurveShape(value:string):CurveShapeState{
  const parts=String(value||"ease").split(":");
  if(parts[0]!=="custom")return{mode:parts[0]||"ease",p1:0,p2:100};
  const a=Number(parts[1]),b=Number(parts[2]);
  return{mode:"custom",p1:Number.isFinite(a)?a:0,p2:Number.isFinite(b)?b:100};
}
function clampCurvePercent(value:number){return Math.max(-200,Math.min(300,value));}
function midiToHz(midi:number){return 440*2**((midi-69)/12);}
function midiLabel(midi:number){const names=["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"],rounded=Math.round(midi);return `${names[((rounded%12)+12)%12]}${Math.floor(rounded/12)-1}`;}

export default function SettingsPanel({api,settings,notes,selected,audioName,busy,analysisAvailable,actualAnalysisSource,onPatch,onStateAction,onMutation,onStatus}:Props){
  const[page,setPage]=useState<Page>("inspector");
  const one=selected.length===1?notes[selected[0]]:null;
  const curveShape=parseCurveShape(settings.curveShape);
  const mutate=(p:Promise<NoteMutationResult>,sel=selected)=>void p.then(x=>onMutation(x,sel)).catch(e=>onStatus(String(e)));
  const setCurveShape=(mode:string)=>void onPatch({curveShape:mode==="custom"?`custom:${curveShape.p1}:${curveShape.p2}`:mode});
  const setCustomCurve=(p1:number,p2:number)=>void onPatch({curveShape:`custom:${clampCurvePercent(p1)}:${clampCurvePercent(p2)}`});
  const requested=settings.analysisSource==="vorbis_direct"?"Vorbis Direct":"CQT";
  const actual=!analysisAvailable?"未解析":actualAnalysisSource==="vorbis_direct"?"Vorbis Direct":"CQT";
  const fallback=analysisAvailable&&settings.analysisSource==="vorbis_direct"&&actualAnalysisSource!=="vorbis_direct";

  return <aside className="settings inspector-panel">
    <h2>{page==="inspector"?"インスペクタ":"設定"}</h2>
    <nav className="inspector-tabs">
      <button className={page==="inspector"?"active":""} onClick={()=>setPage("inspector")}>Inspector</button>
      <button className={page==="settings"?"active":""} onClick={()=>setPage("settings")}>Settings</button>
    </nav>
    <div className="settings-body">
      {page==="inspector"&&<>
        {selected.length===0&&<div className="inspector-empty"><strong>選択なし</strong><span>ノートを選択するとプロパティを編集できます。</span></div>}
        {selected.length>0&&<div className="inspector-summary"><strong>{one?(one.kind??"note")==="curve"?"Curve Note":"Note":`${selected.length} Notes`}</strong><span>{one?`${midiLabel(one.midi)} · ${midiToHz(one.midi).toFixed(2)} Hz`:`${selected.length}個選択中`}</span></div>}
        {one&&api&&<>
          <Row label="開始"><NumberInput value={one.start} min={0} max={36000} step={0.001} suffix="s" onChange={v=>mutate(api.set_note_properties(selected[0],{start:v}),selected)}/></Row>
          <Row label="終了"><NumberInput value={one.end} min={0} max={36000} step={0.001} suffix="s" onChange={v=>mutate(api.set_note_properties(selected[0],{end:v}),selected)}/></Row>
          <Row label="長さ"><NumberInput value={Math.max(0,one.end-one.start)} min={0.001} max={36000} step={0.001} suffix="s" onChange={v=>mutate(api.set_note_properties(selected[0],{duration:v}),selected)}/></Row>
          <Row label="MIDI"><NumberInput value={one.midi} min={0} max={127} step={0.01} onChange={v=>mutate(api.set_note_properties(selected[0],{midi:v}),selected)}/></Row>
          <div className="property-readout"><span>Pitch</span><b>{midiLabel(one.midi)} · {midiToHz(one.midi).toFixed(2)} Hz</b></div>
          {(one.kind??"note")==="curve"&&<Fold title="カーブ" open>
            <Row label="形状"><Select value={curveShape.mode} options={[["ease","イーズ"],["s_curve","S字"],["sine","サイン"],["expo_in","指数イン"],["expo_out","指数アウト"],["linear","直線"],["ease_in","イーズイン"],["ease_out","イーズアウト"],["custom","カスタム Bézier"]]} onChange={setCurveShape}/></Row>
            {curveShape.mode==="custom"&&<>
              <Row label="Bezier P1"><NumberInput value={curveShape.p1} min={-200} max={300} step={1} suffix="%" onChange={v=>setCustomCurve(v,curveShape.p2)}/></Row>
              <Row label="Bezier P2"><NumberInput value={curveShape.p2} min={-200} max={300} step={1} suffix="%" onChange={v=>setCustomCurve(curveShape.p1,v)}/></Row>
            </>}
            <button className="wide" onClick={()=>void api.apply_curve_shape(selected).then(x=>onMutation(x,selected))}>形状を適用</button>
            <Row label="補間"><Select value={settings.curveInterpolation} options={[["bezier_pitch","ベジェ（音高）"],["linear_pitch","直線（音高）"],["linear_hz","直線（Hz）"],["bezier_hz","ベジェ（Hz）"]]} onChange={v=>void onPatch({curveInterpolation:v})}/></Row>
            <button className="wide" onClick={()=>void api.apply_interpolation(selected).then(x=>onMutation(x,selected))}>補間を適用</button>
            <Row label="目標角度"><NumberInput value={settings.targetAngle} min={.001} max={359.999} step={.001} suffix="°" onChange={v=>void onPatch({targetAngle:v})}/></Row>
            <div className="button-row"><button onClick={()=>void api.apply_target_angle(selected).then(x=>onMutation(x,selected))}>角度を適用</button><button onClick={()=>void api.clear_target_angle(selected).then(x=>onMutation(x,selected))}>角度を解除</button></div>
          </Fold>}
        </>}
        {selected.length>1&&api&&<BulkEditor api={api} selected={selected} onMutation={onMutation} onStatus={onStatus}/>} 
      </>}

      {page==="settings"&&<>
        <Fold title="再生" open>
          <Row label="楽曲音量"><Range value={settings.volume} onChange={v=>void onPatch({volume:v})}/></Row>
          <Row label="再生速度"><NumberInput value={settings.speed} min={.1} max={4} step={.05} suffix="x" onChange={v=>void onPatch({speed:v})}/></Row>
          <Row label="ノート試聴"><input type="checkbox" checked={settings.notePreview} onChange={e=>void onPatch({notePreview:e.target.checked})}/></Row>
          <Row label="試聴音量"><Range value={settings.previewVolume} disabled={!settings.notePreview} onChange={v=>void onPatch({previewVolume:v})}/></Row>
          <Row label="試聴音色"><Select value={settings.previewSound} disabled={!settings.notePreview} options={[["sine","サイン波"],["piano","ピアノ"],["organ","オルガン"],["square","矩形波"],["triangle","三角波"]]} onChange={v=>void onPatch({previewSound:v})}/></Row>
        </Fold>

        <Fold title="グリッド / スナップ">
          <Row label="グリッド"><input type="checkbox" checked={settings.gridEnabled} onChange={e=>void onPatch({gridEnabled:e.target.checked})}/></Row>
          <Row label="スナップ"><input type="checkbox" checked={settings.snapEnabled} onChange={e=>void onPatch({snapEnabled:e.target.checked})}/></Row>
          <Row label="BPM"><NumberInput value={settings.bpm} min={1} max={10000} step={.1} onChange={v=>void onPatch({bpm:v})}/></Row>
          <Row label="分割数"><NumberInput value={settings.snapDiv} min={1} max={64} step={1} disabled={!settings.snapEnabled} onChange={v=>void onPatch({snapDiv:v})}/></Row>
          <Row label="オフセット"><NumberInput value={settings.offsetMs} min={-600000} max={600000} step={1} suffix="ms" onChange={v=>void onPatch({offsetMs:v})}/></Row>
          <Row label="メトロノーム"><input type="checkbox" checked={settings.metronomeEnabled} onChange={e=>void onPatch({metronomeEnabled:e.target.checked})}/></Row>
          <Row label="メトロ音量"><Range value={settings.metronomeVolume} disabled={!settings.metronomeEnabled} onChange={v=>void onPatch({metronomeVolume:v})}/></Row>
        </Fold>

        <Fold title="表示">
          <Row label="コントラスト"><Range value={settings.contrast} min={0} max={300} onChange={v=>void onPatch({contrast:v})}/></Row>
          <Row label="ガンマ"><Range value={settings.gamma} min={5} max={500} onChange={v=>void onPatch({gamma:v})}/></Row>
          <Row label="強調"><input type="checkbox" checked={settings.enhance} onChange={e=>void onPatch({enhance:e.target.checked})}/></Row>
          <Row label="描画"><Select value={settings.displayMode} options={[["wavetone","標準"],["ridge","輪郭"],["smooth","滑らか"]]} onChange={v=>void onPatch({displayMode:v})}/></Row>
          <Row label="倍音表示"><Select value={settings.harmonics} options={[["off","オフ"],["soft","弱"],["strong","強"]]} onChange={v=>void onPatch({harmonics:v})}/></Row>
          <Row label="配色"><Select value={settings.colormap} options={[["wavetone","WaveTone"],["viridis","Viridis"],["magma","Magma"],["inferno","Inferno"],["plasma","Plasma"],["gray","グレー"]]} onChange={v=>void onPatch({colormap:v})}/></Row>
        </Fold>

        <Fold title="解析" open>
          <div className={fallback?"analysis-state warn":"analysis-state"}><span>Requested</span><b>{requested}</b><span>Actual</span><b>{actual}{fallback?" · fallback":""}</b></div>
          <Row label="解析元"><Select value={settings.analysisSource} options={[["cqt","CQT"],["vorbis_direct","Vorbis Direct（実験）"]]} onChange={v=>void onPatch({analysisSource:v as EditorSettings["analysisSource"]})}/></Row>
          {settings.analysisSource==="cqt"&&<>
            <Row label="解析品質"><Select value={settings.analysisProfile} options={[["Fast","高速"],["Normal","標準"],["Precise","高精度"],["Full C0-C10","全域 C0-C10"]]} onChange={v=>void onPatch({analysisProfile:v})}/></Row>
            <Row label="CQT解像度"><Select value={settings.cqtResolution} options={[["profile default","自動"],["100 cents","100セント"],["50 cents","50セント"],["25 cents","25セント"],["12.5 cents","12.5セント"],["41 EDO","41平均律"],["53 EDO","53平均律"]]} onChange={v=>void onPatch({cqtResolution:v})}/></Row>
          </>}
          {settings.analysisSource==="vorbis_direct"&&<>
            <Row label="Direct表示"><Select value={settings.spectrumLayerMode} options={[["raw","Raw"],["tracks","Tracks"],["both","Raw + Tracks"]]} onChange={v=>void onPatch({spectrumLayerMode:v as EditorSettings["spectrumLayerMode"]})}/></Row>
            <Row label="しきい値"><Select value={String(settings.spectrumThreshold)} options={[["0","0%"],["0.5","0.5%"],["1","1%"],["2","2%"],["5","5%"],["10","10%"]]} onChange={v=>void onPatch({spectrumThreshold:Number(v)})}/></Row>
            <Row label="表示濃度"><Range value={settings.spectrumOpacity} onChange={v=>void onPatch({spectrumOpacity:v})}/></Row>
          </>}
          <button className="wide primary-soft" disabled={!api||!audioName||busy} onClick={()=>void onStateAction(()=>api!.reanalyze_audio())}>音声を解析</button>
          {fallback&&<div className="compact-warning">この音源では Vorbis Direct を使用できないため CQT にフォールバックしています。</div>}
        </Fold>

        <Fold title="出力">
          <Row label="オクターブ"><NumberInput value={settings.exportOctave} min={-4} max={4} step={1} onChange={v=>void onPatch({exportOctave:v})}/></Row>
          <Row label="半音"><NumberInput value={settings.exportSemitone} min={-12} max={12} step={1} onChange={v=>void onPatch({exportSemitone:v})}/></Row>
        </Fold>
      </>}
    </div>
  </aside>;
}

function BulkEditor({api,selected,onMutation,onStatus}:{api:BackendApi;selected:number[];onMutation(result:NoteMutationResult,nextSelection?:number[]):void;onStatus(text:string):void}){
  const[timeDelta,setTimeDelta]=useState(0),[pitchDelta,setPitchDelta]=useState(0),[duration,setDuration]=useState(0.25);
  async function apply(changes:Parameters<BackendApi["bulk_edit_notes"]>[1]){try{const r=await api.bulk_edit_notes(selected,changes);onMutation(r,selected)}catch(e){onStatus(String(e))}}
  return <Fold title="一括編集">
    <Row label="時間移動"><NumberInput value={timeDelta} min={-36000} max={36000} step={0.001} suffix="s" onChange={setTimeDelta}/></Row>
    <Row label="音高移動"><NumberInput value={pitchDelta} min={-127} max={127} step={0.01} suffix="半音" onChange={setPitchDelta}/></Row>
    <button className="wide" onClick={()=>void apply({timeDelta,pitchDelta})}>移動を適用</button>
    <Row label="長さ"><NumberInput value={duration} min={0.001} max={36000} step={0.001} suffix="s" onChange={setDuration}/></Row>
    <button className="wide" onClick={()=>void apply({duration})}>長さを適用</button>
    <div className="button-row"><button onClick={()=>void apply({align:"start"})}>開始を揃える</button><button onClick={()=>void apply({align:"end"})}>終了を揃える</button></div>
  </Fold>;
}

function Fold({title,open=false,children}:{title:string;open?:boolean;children:ReactNode}){return <details className="settings-fold" open={open}><summary>{title}</summary><div className="settings-fold-body">{children}</div></details>}
function Row({label,children}:{label:string;children:ReactNode}){return <label className="row"><span>{label}</span><div>{children}</div></label>}
function Range({value,min=0,max=100,disabled=false,onChange}:{value:number;min?:number;max?:number;disabled?:boolean;onChange(v:number):void}){return <div className="range-wrap"><input type="range" min={min} max={max} value={value} disabled={disabled} onChange={e=>onChange(+e.target.value)}/><output>{value}</output></div>}
function NumberInput({value,min,max,step,suffix,disabled=false,onChange}:{value:number;min:number;max:number;step:number;suffix?:string;disabled?:boolean;onChange(v:number):void}){return <div className="number-wrap"><input type="number" value={Number.isFinite(value)?value:0} min={min} max={max} step={step} disabled={disabled} onChange={e=>{const v=+e.target.value;if(Number.isFinite(v))onChange(v)}}/>{suffix&&<span>{suffix}</span>}</div>}
function Select({value,options,disabled=false,onChange}:{value:string;options:Array<[string,string]>;disabled?:boolean;onChange(v:string):void}){return <select value={value} disabled={disabled} onChange={e=>onChange(e.target.value)}>{options.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select>}
