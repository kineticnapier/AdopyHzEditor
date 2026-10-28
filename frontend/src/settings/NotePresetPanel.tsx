import { useEffect, useMemo, useRef, useState } from "react";
import type { BackendApi, NoteMutationResult, NotePreset } from "./bridge";
import { presetInsertSelection } from "./presetSelection";
import { LatestRequestGate } from "../api/requestCoordinator";
import "./presets.css";

type Props = {
  api: BackendApi | null;
  selected: number[];
  playbackTime: number;
  onQueuedMutation(call: () => Promise<NoteMutationResult>, selection?: (result: NoteMutationResult) => number[] | undefined): Promise<NoteMutationResult | undefined>;
  onQueuedPresetAction<T>(call: () => Promise<T>): Promise<T | undefined>;
  onStatus(text: string): void;
};

function describe(preset: NotePreset) {
  const midi = Number(preset.note.midi).toFixed(2);
  const sec = Number(preset.duration).toFixed(3);
  return `${preset.kind === "curve" ? "カーブ" : "固定音"} / MIDI ${midi} / ${sec}秒`;
}

export default function NotePresetPanel({ api, selected, playbackTime, onQueuedMutation, onQueuedPresetAction, onStatus }: Props) {
  const [presets, setPresets] = useState<NotePreset[]>([]);
  const [name, setName] = useState("");
  const [chosen, setChosen] = useState("");
  const [busy, setBusy] = useState(false);
  const listRequests = useRef(new LatestRequestGate());

  useEffect(() => {
    const request = listRequests.current.issue();
    if (!api) return;
    let alive = true;
    void api.get_note_presets().then((items) => {
      if (!alive || !listRequests.current.isCurrent(request)) return;
      setPresets(items);
      setChosen((old) => old && items.some((x) => x.name === old) ? old : (items[0]?.name ?? ""));
    }).catch((e) => {
      if (alive && listRequests.current.isCurrent(request)) onStatus(String(e));
    });
    return () => { alive = false; listRequests.current.invalidate(); };
  }, [api, onStatus]);

  const current = useMemo(() => presets.find((x) => x.name === chosen) ?? null, [presets, chosen]);

  async function save() {
    if (!api || selected.length !== 1 || !name.trim()) return;
    setBusy(true);
    try {
      const presetName = name.trim();
      const selectedIndex = selected[0];
      const result = await onQueuedPresetAction(() => api.save_note_preset(presetName, selectedIndex));
      if (!result) return;
      listRequests.current.invalidate();
      setPresets(result.presets);
      setChosen(presetName);
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
      await onQueuedMutation(
        () => api.insert_note_preset(chosen, playbackTime),
        presetInsertSelection,
      );
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
      const presetName = chosen;
      const result = await onQueuedPresetAction(() => api.delete_note_preset(presetName));
      if (!result) return;
      listRequests.current.invalidate();
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
      <input aria-label="プリセット名" value={name} maxLength={80} placeholder="プリセット名" onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void save(); }} />
      <button disabled={!api || busy || selected.length !== 1 || !name.trim()} onClick={() => void save()}>選択音を保存</button>
    </div>
    {presets.length === 0 ? <div className="hint">1個のノートを選択して保存すると、別の曲でも同じ音高・長さを再利用できます。</div> : <>
      <div className="preset-use-row">
        <select aria-label="保存済みプリセット" value={chosen} onChange={(e) => setChosen(e.target.value)}>{presets.map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}</select>
        <button className="primary-soft" disabled={!api || busy || !chosen} onClick={() => void insert()}>再生位置へ挿入</button>
        <button disabled={!api || busy || !chosen} onClick={() => void remove()}>削除</button>
      </div>
      {current && <div className="preset-description">{describe(current)}</div>}
    </>}
  </section>;
}
