import { useEffect, useMemo, useState } from "react";
import type { BackendApi, NoteMutationResult, NotePreset } from "./bridge";

type Props = {
  api: BackendApi | null;
  selected: number[];
  playbackTime: number;
  onMutation(result: NoteMutationResult, selection?: number[]): void;
  onStatus(text: string): void;
};

function describe(preset: NotePreset) {
  const midi = Number(preset.note.midi).toFixed(2);
  const sec = Number(preset.duration).toFixed(3);
  return `${preset.kind === "curve" ? "カーブ" : "固定音"} / MIDI ${midi} / ${sec}秒`;
}

export default function NotePresetPanel({ api, selected, playbackTime, onMutation, onStatus }: Props) {
  const [presets, setPresets] = useState<NotePreset[]>([]);
  const [name, setName] = useState("");
  const [chosen, setChosen] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!api) return;
    let alive = true;
    void api.get_note_presets().then((items) => {
      if (!alive) return;
      setPresets(items);
      setChosen((old) => old && items.some((x) => x.name === old) ? old : (items[0]?.name ?? ""));
    }).catch((e) => onStatus(String(e)));
    return () => { alive = false; };
  }, [api, onStatus]);

  const current = useMemo(() => presets.find((x) => x.name === chosen) ?? null, [presets, chosen]);

  async function save() {
    if (!api || selected.length !== 1 || !name.trim()) return;
    setBusy(true);
    try {
      const result = await api.save_note_preset(name.trim(), selected[0]);
      setPresets(result.presets);
      setChosen(name.trim());
      onStatus(result.status);
    } catch (e) {
      onStatus(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function insert() {
    if (!api || !chosen) return;
    setBusy(true);
    try {
      const result = await api.insert_note_preset(chosen, playbackTime);
      onMutation(result, result.indices ?? (result.index === undefined ? [] : [result.index]));
    } catch (e) {
      onStatus(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!api || !chosen) return;
    if (!window.confirm(`プリセット「${chosen}」を削除しますか？`)) return;
    setBusy(true);
    try {
      const result = await api.delete_note_preset(chosen);
      setPresets(result.presets);
      setChosen(result.presets[0]?.name ?? "");
      onStatus(result.status);
    } catch (e) {
      onStatus(String(e));
    } finally {
      setBusy(false);
    }
  }

  return <section className="note-presets">
    <h3>単音プリセット</h3>
    <div className="preset-save-row">
      <input value={name} maxLength={80} placeholder="プリセット名" onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void save(); }} />
      <button disabled={!api || busy || selected.length !== 1 || !name.trim()} onClick={() => void save()}>選択音を保存</button>
    </div>
    {presets.length === 0 ? <div className="hint">1個のノートを選択して保存すると、別の曲でも同じ音高・長さを再利用できます。</div> : <>
      <div className="preset-use-row">
        <select value={chosen} onChange={(e) => setChosen(e.target.value)}>{presets.map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}</select>
        <button className="primary-soft" disabled={!api || busy || !chosen} onClick={() => void insert()}>再生位置へ挿入</button>
        <button disabled={!api || busy || !chosen} onClick={() => void remove()}>削除</button>
      </div>
      {current && <div className="preset-description">{describe(current)}</div>}
    </>}
  </section>;
}
