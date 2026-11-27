import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import type {
  AppState,
  BackendApi,
  EditorSettings,
  KickPitchPayload,
  NoteDto,
  NoteMutationResult,
} from "./bridge";
import KickPitchSection from "./KickPitchSection";
import type { KickPitchPick } from "./kickPitchModel";
import type {
  TrackHoverInfo,
  TrackSelectionState,
} from "../editor/EditorCanvas";
import { midiLabel, midiToHz } from "../editor/musicMath";
import { commitNumericEdit } from "./numericInputModel";
import { isDialogCompositionKey, isPlainDialogEscape } from "../dialogs/dialogFocus";
import { selectionIdentityKey } from "./selectionIdentity";
import { setLayerActive, summarizeLayers } from "../editor/layers";
import { t, useLanguage } from "../i18n/index.ts";

type Page = "inspector" | "settings";
type Props = {
  api: BackendApi | null;
  settings: EditorSettings;
  notes: NoteDto[];
  selected: number[];
  audioName: string | null;
  busy: boolean;
  analysisAvailable: boolean;
  actualAnalysisSource: string;
  trackSelection: TrackSelectionState;
  hoveredTrack: TrackHoverInfo | null;
  onPatch(changes: Partial<EditorSettings>): Promise<void>;
  onStateAction(action: () => Promise<AppState>): Promise<void>;
  onQueuedMutation(
    call: () => Promise<NoteMutationResult>,
    selection?: (result: NoteMutationResult) => number[] | undefined,
  ): Promise<NoteMutationResult | undefined>;
  onStatus(text: string): void;
  onTrackSelectionChange(selection: TrackSelectionState): void;
  onConvertTracks(mode: "fixed" | "curve"): Promise<void>;
  viewStart: number;
  kickPitch: KickPitchPayload | null;
  kickPitchSelected: number[];
  onKickPitch(payload: KickPitchPayload | null, selectedIds: number[]): void;
  onKickPitchSelect(ids: number[]): void;
  kickPitchPicking: boolean;
  kickPitchPick: KickPitchPick | null;
  onKickPitchPickingChange(picking: boolean): void;
};

type CurveShapeState = { mode: string; p1: number; p2: number };
function parseCurveShape(value: string): CurveShapeState {
  const parts = String(value || "ease").split(":");
  if (parts[0] !== "custom")
    return { mode: parts[0] || "ease", p1: 0, p2: 100 };
  const a = Number(parts[1]),
    b = Number(parts[2]);
  return {
    mode: "custom",
    p1: Number.isFinite(a) ? a : 0,
    p2: Number.isFinite(b) ? b : 100,
  };
}
function clampCurvePercent(value: number) {
  return Math.max(-200, Math.min(300, value));
}

export default function SettingsPanel({
  api,
  settings,
  notes,
  selected,
  audioName,
  busy,
  analysisAvailable,
  actualAnalysisSource,
  trackSelection,
  hoveredTrack,
  onPatch,
  onStateAction,
  onQueuedMutation,
  onStatus,
  onTrackSelectionChange,
  onConvertTracks,
  viewStart,
  kickPitch,
  kickPitchSelected,
  onKickPitch,
  onKickPitchSelect,
  kickPitchPicking,
  kickPitchPick,
  onKickPitchPickingChange,
}: Props) {
  useLanguage();
  const [page, setPage] = useState<Page>("inspector");
  const one = selected.length === 1 ? notes[selected[0]] : null;
  const curveShape = parseCurveShape(settings.curveShape);
  const mutate = (call: () => Promise<NoteMutationResult>, sel = selected) =>
    void onQueuedMutation(call, () => sel);
  const setCurveShape = (mode: string) =>
    void onPatch({
      curveShape:
        mode === "custom" ? `custom:${curveShape.p1}:${curveShape.p2}` : mode,
    });
  const setCustomCurve = (p1: number, p2: number) =>
    void onPatch({
      curveShape: `custom:${clampCurvePercent(p1)}:${clampCurvePercent(p2)}`,
    });
  const requested =
    settings.analysisSource === "vorbis_direct" ? "Vorbis Direct" : "CQT";
  const actual = !analysisAvailable
    ? t("panel.not_analyzed")
    : actualAnalysisSource === "vorbis_direct"
      ? "Vorbis Direct"
      : "CQT";
  const fallback =
    analysisAvailable &&
    settings.analysisSource === "vorbis_direct" &&
    actualAnalysisSource !== "vorbis_direct";
  const selectionKey = selectionIdentityKey(selected, trackSelection.ids);
  useEffect(() => {
    if (selected.length || trackSelection.ids.length) setPage("inspector");
  }, [selectionKey]);

  return (
    <aside className="settings inspector-panel" aria-label={page === "inspector" ? t("panel.inspector") : t("panel.settings")}>
      <nav className="inspector-tabs" aria-label={t("panel.tabs")}>
        <button
          className={page === "inspector" ? "active" : ""}
          aria-pressed={page === "inspector"}
          onClick={() => setPage("inspector")}
        >
          {t("panel.inspector")}
        </button>
        <button
          className={page === "settings" ? "active" : ""}
          aria-pressed={page === "settings"}
          onClick={() => setPage("settings")}
        >
          {t("panel.settings")}
        </button>
      </nav>
      {!api && <p className="inspector-help" role="status">{t("panel.waiting")}</p>}
      <div className="settings-body" inert={!api} aria-busy={!api}>
        {page === "inspector" && (
          <>
            <LayerList
              notes={notes}
              muted={settings.mutedLayers ?? []}
              disabled={busy}
              onChange={(mutedLayers) => void onPatch({ mutedLayers })}
            />
            {selected.length === 0 && trackSelection.ids.length === 0 && (
              <div className="inspector-empty">
                <strong>{t("panel.no_selection")}</strong>
                <span>{t("panel.no_selection_hint")}</span>
              </div>
            )}
            {trackSelection.ids.length > 0 && (
              <section className="track-inspector" aria-label={t("panel.selected_track")}>
                <div className="inspector-summary">
                  <strong>Frequency Track</strong>
                  <span>{t("panel.tracks_selected", { count: trackSelection.ids.length })}</span>
                </div>
                <div className="property-readout">
                  <span>Track ID</span>
                  <b>
                    {trackSelection.ids.length === 1
                      ? `#${trackSelection.ids[0]}`
                      : t("panel.tracks_count", { count: trackSelection.ids.length })}
                  </b>
                </div>
                {trackSelection.range && (
                  <>
                    <div className="property-readout">
                      <span>{t("panel.time_range")}</span>
                      <b>
                        {trackSelection.range.startTime.toFixed(3)}–
                        {trackSelection.range.endTime.toFixed(3)} s
                      </b>
                    </div>
                    <div className="property-readout">
                      <span>{t("panel.pitch_range")}</span>
                      <b>
                        MIDI {trackSelection.range.minMidi.toFixed(1)}–
                        {trackSelection.range.maxMidi.toFixed(1)}
                      </b>
                    </div>
                    <label className="inline-check inspector-check">
                      <input
                        type="checkbox"
                        checked={trackSelection.useRange}
                        onChange={(event) =>
                          onTrackSelectionChange({
                            ...trackSelection,
                            useRange: event.target.checked,
                          })
                        }
                      />
                      {t("panel.cut_by_rect")}
                    </label>
                  </>
                )}
                {hoveredTrack &&
                  trackSelection.ids.includes(hoveredTrack.id) && (
                    <div className="track-detail">
                      <span>{hoveredTrack.noteName}</span>
                      <b>{hoveredTrack.frequency.toFixed(2)} Hz</b>
                      <small>
                        {hoveredTrack.duration.toFixed(3)} s · {t("panel.strength")}{" "}
                        {(hoveredTrack.magnitude * 100).toFixed(1)}%
                      </small>
                    </div>
                  )}
                <p className="inspector-help">{t("panel.track_hint")}</p>
                <div className="track-actions">
                  <button
                    className="primary-soft"
                    disabled={busy}
                    onClick={() => void onConvertTracks("fixed")}
                  >
                    {t("panel.make_fixed")}
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => void onConvertTracks("curve")}
                  >
                    {t("panel.make_curve")}
                  </button>
                </div>
                <button
                  className="wide quiet-button"
                  disabled={busy}
                  onClick={() =>
                    onTrackSelectionChange({
                      ids: [],
                      range: null,
                      useRange: false,
                    })
                  }
                >
                  {t("panel.clear_tracks")}
                </button>
              </section>
            )}
            {selected.length > 0 && (
              <div className="inspector-summary">
                <strong>
                  {one
                    ? (one.kind ?? "note") === "curve"
                      ? "Curve Note"
                      : "Note"
                    : `${selected.length} Notes`}
                </strong>
                <span>
                  {one
                    ? `${midiLabel(one.midi)} · ${midiToHz(one.midi).toFixed(2)} Hz`
                    : t("panel.notes_selected", { count: selected.length })}
                </span>
              </div>
            )}
            {one && api && (
              <Fragment key={`note-${selected[0]}`}>
                <Row label={t("panel.start")}>
                  <NumberInput
                    value={one.start}
                    min={0}
                    max={36000}
                    step="any"
                    suffix="s"
                    onChange={(v) =>
                      mutate(
                        () => api.set_note_properties(selected[0], { start: v }),
                        selected,
                      )
                    }
                  />
                </Row>
                <Row label={t("panel.end")}>
                  <NumberInput
                    value={one.end}
                    min={0}
                    max={36000}
                    step="any"
                    suffix="s"
                    onChange={(v) =>
                      mutate(
                        () => api.set_note_properties(selected[0], { end: v }),
                        selected,
                      )
                    }
                  />
                </Row>
                <Row label={t("panel.length")}>
                  <NumberInput
                    value={Math.max(0, one.end - one.start)}
                    min={0.001}
                    max={36000}
                    step="any"
                    suffix="s"
                    onChange={(v) =>
                      mutate(
                        () => api.set_note_properties(selected[0], { duration: v }),
                        selected,
                      )
                    }
                  />
                </Row>
                <Row label="MIDI">
                  <NumberInput
                    value={one.midi}
                    min={0}
                    max={127}
                    step="any"
                    onChange={(v) =>
                      mutate(
                        () => api.set_note_properties(selected[0], { midi: v }),
                        selected,
                      )
                    }
                  />
                </Row>
                <div className="property-readout">
                  <span>Pitch</span>
                  <b>
                    {midiLabel(one.midi)} · {midiToHz(one.midi).toFixed(2)} Hz
                  </b>
                </div>
                {(one.kind ?? "note") === "curve" && (
                  <Fold title={t("panel.curve")} open>
                    <Row label={t("panel.shape")}>
                      <Select
                        value={curveShape.mode}
                        options={[
                          ["ease", t("panel.shape_ease")],
                          ["s_curve", t("panel.shape_s_curve")],
                          ["sine", t("panel.shape_sine")],
                          ["expo_in", t("panel.shape_expo_in")],
                          ["expo_out", t("panel.shape_expo_out")],
                          ["linear", t("panel.shape_linear")],
                          ["ease_in", t("panel.shape_ease_in")],
                          ["ease_out", t("panel.shape_ease_out")],
                          ["custom", t("panel.shape_custom")],
                        ]}
                        onChange={setCurveShape}
                      />
                    </Row>
                    {curveShape.mode === "custom" && (
                      <>
                        <Row label="Bezier P1">
                          <NumberInput
                            value={curveShape.p1}
                            min={-200}
                            max={300}
                            step={1}
                            suffix="%"
                            onChange={(v) => setCustomCurve(v, curveShape.p2)}
                          />
                        </Row>
                        <Row label="Bezier P2">
                          <NumberInput
                            value={curveShape.p2}
                            min={-200}
                            max={300}
                            step={1}
                            suffix="%"
                            onChange={(v) => setCustomCurve(curveShape.p1, v)}
                          />
                        </Row>
                      </>
                    )}
                    <button
                      className="wide"
                      onClick={() =>
                        mutate(() => api.apply_curve_shape(selected), selected)
                      }
                    >
                      {t("panel.apply_shape")}
                    </button>
                    <Row label={t("panel.interpolation")}>
                      <Select
                        value={settings.curveInterpolation}
                        options={[
                          ["bezier_pitch", t("panel.interp_bezier_pitch")],
                          ["linear_pitch", t("panel.interp_linear_pitch")],
                          ["linear_hz", t("panel.interp_linear_hz")],
                          ["bezier_hz", t("panel.interp_bezier_hz")],
                        ]}
                        onChange={(v) =>
                          void onPatch({ curveInterpolation: v })
                        }
                      />
                    </Row>
                    <button
                      className="wide"
                      onClick={() =>
                        mutate(
                          () => api.apply_interpolation(
                            selected,
                            settings.curveInterpolation,
                          ),
                          selected,
                        )
                      }
                    >
                      {t("panel.apply_interpolation")}
                    </button>
                    <Row label={t("panel.target_angle")}>
                      <NumberInput
                        value={settings.targetAngle}
                        min={0.001}
                        max={359.999}
                        step="any"
                        suffix="°"
                        onChange={(v) => void onPatch({ targetAngle: v })}
                      />
                    </Row>
                    <div className="button-row">
                      <button
                        onClick={() =>
                          mutate(
                            () => api.apply_target_angle(
                              selected,
                              settings.targetAngle,
                            ),
                            selected,
                          )
                        }
                      >
                        {t("panel.apply_angle")}
                      </button>
                      <button
                        onClick={() =>
                          mutate(() => api.clear_target_angle(selected), selected)
                        }
                      >
                        {t("panel.clear_angle")}
                      </button>
                    </div>
                  </Fold>
                )}
              </Fragment>
            )}
            {selected.length > 1 && api && (
              <BulkEditor
                api={api}
                selected={selected}
                onQueuedMutation={onQueuedMutation}
                onStatus={onStatus}
              />
            )}
            <KickPitchSection
              api={api}
              busy={busy}
              audioLoaded={Boolean(audioName)}
              trackRange={trackSelection.range}
              viewStart={viewStart}
              kickPitch={kickPitch}
              selectedIds={kickPitchSelected}
              onKickPitch={onKickPitch}
              onSelectIds={onKickPitchSelect}
              picking={kickPitchPicking}
              pick={kickPitchPick}
              onPickingChange={onKickPitchPickingChange}
              onQueuedMutation={onQueuedMutation}
              onStatus={onStatus}
            />
          </>
        )}

        {page === "settings" && (
          <>
            <Fold title={t("panel.playback")} open>
              <Row label={t("panel.song_volume")}>
                <Range
                  value={settings.volume}
                  onChange={(v) => void onPatch({ volume: v })}
                />
              </Row>
              <Row label={t("panel.speed")}>
                <NumberInput
                  value={settings.speed}
                  min={0.1}
                  max={4}
                  step="any"
                  suffix="x"
                  onChange={(v) => void onPatch({ speed: v })}
                />
              </Row>
              <Row label={t("panel.note_preview")}>
                <input
                  type="checkbox"
                  checked={settings.notePreview}
                  onChange={(e) =>
                    void onPatch({ notePreview: e.target.checked })
                  }
                />
              </Row>
              <Row label={t("panel.preview_volume")}>
                <Range
                  value={settings.previewVolume}
                  disabled={!settings.notePreview}
                  onChange={(v) => void onPatch({ previewVolume: v })}
                />
              </Row>
              <Row label={t("panel.preview_sound")}>
                <Select
                  value={settings.previewSound}
                  disabled={!settings.notePreview}
                  options={[
                    ["sine", t("panel.sound_sine")],
                    ["piano", t("panel.sound_piano")],
                    ["organ", t("panel.sound_organ")],
                    ["square", t("panel.sound_square")],
                    ["triangle", t("panel.sound_triangle")],
                    ["adofai_kick", "ADOFAI Kick"],
                  ]}
                  onChange={(v) => void onPatch({ previewSound: v })}
                />
              </Row>
            </Fold>

            <Fold title={t("panel.grid_snap")}>
              <Row label={t("panel.grid")}>
                <input
                  type="checkbox"
                  checked={settings.gridEnabled}
                  onChange={(e) =>
                    void onPatch({ gridEnabled: e.target.checked })
                  }
                />
              </Row>
              <Row label={t("panel.snap")}>
                <input
                  type="checkbox"
                  checked={settings.snapEnabled}
                  onChange={(e) =>
                    void onPatch({ snapEnabled: e.target.checked })
                  }
                />
              </Row>
              <Row label="BPM">
                <NumberInput
                  value={settings.bpm}
                  min={1}
                  max={10000}
                  step="any"
                  onChange={(v) => void onPatch({ bpm: v })}
                />
              </Row>
              <Row label={t("panel.divisions")}>
                <NumberInput
                  value={settings.snapDiv}
                  min={1}
                  max={64}
                  step={1}
                  disabled={!settings.snapEnabled}
                  onChange={(v) => void onPatch({ snapDiv: v })}
                />
              </Row>
              <Row label={t("panel.offset")}>
                <NumberInput
                  value={settings.offsetMs}
                  min={-600000}
                  max={600000}
                  step="any"
                  suffix="ms"
                  onChange={(v) => void onPatch({ offsetMs: v })}
                />
              </Row>
              <Row label={t("panel.metronome")}>
                <input
                  type="checkbox"
                  checked={settings.metronomeEnabled}
                  onChange={(e) =>
                    void onPatch({ metronomeEnabled: e.target.checked })
                  }
                />
              </Row>
              <Row label={t("panel.metronome_volume")}>
                <Range
                  value={settings.metronomeVolume}
                  disabled={!settings.metronomeEnabled}
                  onChange={(v) => void onPatch({ metronomeVolume: v })}
                />
              </Row>
            </Fold>

            <Fold title={t("panel.display")}>
              <Row label={t("panel.contrast")}>
                <Range
                  value={settings.contrast}
                  min={0}
                  max={300}
                  onChange={(v) => void onPatch({ contrast: v })}
                />
              </Row>
              <Row label={t("panel.gamma")}>
                <Range
                  value={settings.gamma}
                  min={5}
                  max={500}
                  onChange={(v) => void onPatch({ gamma: v })}
                />
              </Row>
              <Row label={t("panel.enhance")}>
                <input
                  type="checkbox"
                  checked={settings.enhance}
                  onChange={(e) => void onPatch({ enhance: e.target.checked })}
                />
              </Row>
              <Row label={t("panel.render")}>
                <Select
                  value={settings.displayMode}
                  options={[
                    ["wavetone", t("panel.standard")],
                    ["ridge", t("panel.render_ridge")],
                    ["smooth", t("panel.render_smooth")],
                  ]}
                  onChange={(v) => void onPatch({ displayMode: v })}
                />
              </Row>
              <Row label={t("panel.harmonics")}>
                <Select
                  value={settings.harmonics}
                  options={[
                    ["off", t("panel.off")],
                    ["soft", t("panel.soft")],
                    ["strong", t("panel.strong")],
                  ]}
                  onChange={(v) => void onPatch({ harmonics: v })}
                />
              </Row>
              <Row label={t("panel.colormap")}>
                <Select
                  value={settings.colormap}
                  options={[
                    ["wavetone", "WaveTone"],
                    ["viridis", "Viridis"],
                    ["magma", "Magma"],
                    ["inferno", "Inferno"],
                    ["plasma", "Plasma"],
                    ["gray", t("panel.gray")],
                  ]}
                  onChange={(v) => void onPatch({ colormap: v })}
                />
              </Row>
            </Fold>

            <Fold title={t("panel.analysis")} open>
              <div
                className={fallback ? "analysis-state warn" : "analysis-state"}
              >
                <span>{t("panel.requested")}</span>
                <b>{requested}</b>
                <span>{t("panel.actual")}</span>
                <b>
                  {actual}
                  {fallback ? t("panel.fallback_mark") : ""}
                </b>
              </div>
              <Row label={t("panel.source")}>
                <Select
                  value={settings.analysisSource}
                  options={[
                    ["cqt", "CQT"],
                    ["vorbis_direct", t("panel.vorbis_experimental")],
                  ]}
                  onChange={(v) =>
                    void onPatch({
                      analysisSource: v as EditorSettings["analysisSource"],
                    })
                  }
                />
              </Row>
              {settings.analysisSource === "cqt" && (
                <>
                  <Row label={t("panel.quality")}>
                    <Select
                      value={settings.analysisProfile}
                      options={[
                        ["Fast", t("panel.quality_fast")],
                        ["Normal", t("panel.standard")],
                        ["Precise", t("panel.quality_precise")],
                        ["Full C0-C10", t("panel.quality_full")],
                      ]}
                      onChange={(v) => void onPatch({ analysisProfile: v })}
                    />
                  </Row>
                  <Row label={t("panel.cqt_resolution")}>
                    <Select
                      value={settings.cqtResolution}
                      options={[
                        ["profile default", t("panel.auto")],
                        ["100 cents", t("panel.cents", { n: 100 })],
                        ["50 cents", t("panel.cents", { n: 50 })],
                        ["25 cents", t("panel.cents", { n: 25 })],
                        ["12.5 cents", t("panel.cents", { n: 12.5 })],
                      ]}
                      onChange={(v) => void onPatch({ cqtResolution: v })}
                    />
                  </Row>
                </>
              )}
              {settings.analysisSource === "vorbis_direct" && (
                <>
                  <Row label={t("panel.direct_view")}>
                    <Select
                      value={settings.spectrumLayerMode}
                      options={[
                        ["raw", "Raw"],
                        ["tracks", "Tracks"],
                        ["both", "Raw + Tracks"],
                      ]}
                      onChange={(v) =>
                        void onPatch({
                          spectrumLayerMode:
                            v as EditorSettings["spectrumLayerMode"],
                        })
                      }
                    />
                  </Row>
                  <Row label={t("panel.threshold")}>
                    <Select
                      value={String(settings.spectrumThreshold)}
                      options={[
                        ["0", "0%"],
                        ["0.5", "0.5%"],
                        ["1", "1%"],
                        ["2", "2%"],
                        ["5", "5%"],
                        ["10", "10%"],
                      ]}
                      onChange={(v) =>
                        void onPatch({ spectrumThreshold: Number(v) })
                      }
                    />
                  </Row>
                  <Row label={t("panel.opacity")}>
                    <Range
                      value={settings.spectrumOpacity}
                      onChange={(v) => void onPatch({ spectrumOpacity: v })}
                    />
                  </Row>
                </>
              )}
              <button
                className="wide primary-soft"
                disabled={!api || !audioName || busy}
                onClick={() => void onStateAction(() => api!.reanalyze_audio())}
              >
                {t("panel.analyze_audio")}
              </button>
              {fallback && (
                <div className="compact-warning">{t("panel.fallback_warning")}</div>
              )}
            </Fold>

            <Fold title={t("panel.output")}>
              <Row label={t("panel.octave")}>
                <NumberInput
                  value={settings.exportOctave}
                  min={-4}
                  max={4}
                  step={1}
                  onChange={(v) => void onPatch({ exportOctave: v })}
                />
              </Row>
              <Row label={t("panel.semitone")}>
                <NumberInput
                  value={settings.exportSemitone}
                  min={-12}
                  max={12}
                  step={1}
                  onChange={(v) => void onPatch({ exportSemitone: v })}
                />
              </Row>
            </Fold>
          </>
        )}
      </div>
    </aside>
  );
}

function BulkEditor({
  api,
  selected,
  onQueuedMutation,
  onStatus,
}: {
  api: BackendApi;
  selected: number[];
  onQueuedMutation(
    call: () => Promise<NoteMutationResult>,
    selection?: (result: NoteMutationResult) => number[] | undefined,
  ): Promise<NoteMutationResult | undefined>;
  onStatus(text: string): void;
}) {
  useLanguage();
  const [timeDelta, setTimeDelta] = useState(0),
    [pitchDelta, setPitchDelta] = useState(0),
    [duration, setDuration] = useState(0.25);
  async function apply(changes: Parameters<BackendApi["bulk_edit_notes"]>[1]) {
    try {
      await onQueuedMutation(
        () => api.bulk_edit_notes(selected, changes),
        () => selected,
      );
    } catch (e) {
      onStatus(String(e));
    }
  }
  return (
    <Fold title={t("panel.bulk_edit")}>
      <Row label={t("panel.time_shift")}>
        <NumberInput
          value={timeDelta}
          min={-36000}
          max={36000}
          step="any"
          suffix="s"
          onChange={setTimeDelta}
        />
      </Row>
      <Row label={t("panel.pitch_shift")}>
        <NumberInput
          value={pitchDelta}
          min={-127}
          max={127}
          step="any"
          suffix={t("panel.semitone_unit")}
          onChange={setPitchDelta}
        />
      </Row>
      <button
        className="wide"
        onClick={() => void apply({ timeDelta, pitchDelta })}
      >
        {t("panel.apply_move")}
      </button>
      <Row label={t("panel.length")}>
        <NumberInput
          value={duration}
          min={0.001}
          max={36000}
          step="any"
          suffix="s"
          onChange={setDuration}
        />
      </Row>
      <button className="wide" onClick={() => void apply({ duration })}>
        {t("panel.apply_length")}
      </button>
      <div className="button-row">
        <button onClick={() => void apply({ align: "start" })}>
          {t("panel.align_start")}
        </button>
        <button onClick={() => void apply({ align: "end" })}>
          {t("panel.align_end")}
        </button>
      </div>
    </Fold>
  );
}

function LayerList({
  notes,
  muted,
  disabled,
  onChange,
}: {
  notes: NoteDto[];
  muted: string[];
  disabled: boolean;
  onChange(muted: string[]): void;
}) {
  useLanguage();
  const layers = summarizeLayers(notes);
  // A single unnamed layer means the project has no layers to choose from.
  if (layers.length === 0 || (layers.length === 1 && layers[0].name === "")) return null;
  const activeCount = layers.filter((l) => !muted.includes(l.name)).length;
  return (
    <section className="layer-list" aria-label={t("panel.layers")}>
      <div className="inspector-summary">
        <strong>{t("panel.layers")}</strong>
        <span>
          {t("panel.layers_in_use", { active: activeCount, total: layers.length })}
        </span>
      </div>
      {layers.map((layer) => (
        <label key={layer.name} className="inline-check layer-row">
          <input
            type="checkbox"
            checked={!muted.includes(layer.name)}
            disabled={disabled}
            onChange={(e) => onChange(setLayerActive(muted, layer.name, e.target.checked))}
          />
          <span className="layer-name">{layer.label}</span>
          <span className="layer-count">{layer.count}</span>
        </label>
      ))}
      <div className="layer-actions">
        <button type="button" disabled={disabled || muted.length === 0} onClick={() => onChange([])}>
          {t("panel.use_all")}
        </button>
        <button
          type="button"
          disabled={disabled || activeCount === 0}
          onClick={() => onChange(layers.map((l) => l.name))}
        >
          {t("panel.exclude_all")}
        </button>
      </div>
      <p className="inspector-help">{t("panel.layers_hint")}</p>
    </section>
  );
}
function Fold({
  title,
  open = false,
  children,
}: {
  title: string;
  open?: boolean;
  children: ReactNode;
}) {
  return (
    <details className="settings-fold" open={open}>
      <summary>{title}</summary>
      <div className="settings-fold-body">{children}</div>
    </details>
  );
}
function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="row">
      <span>{label}</span>
      <div>{children}</div>
    </label>
  );
}
function Range({
  value,
  min = 0,
  max = 100,
  disabled = false,
  onChange,
}: {
  value: number;
  min?: number;
  max?: number;
  disabled?: boolean;
  onChange(v: number): void;
}) {
  return (
    <div className="range-wrap">
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(+e.target.value)}
      />
      <output>{value}</output>
    </div>
  );
}
function NumberInput({
  value,
  min,
  max,
  step,
  suffix,
  disabled = false,
  onChange,
}: {
  value: number;
  min: number;
  max: number;
  step: number | "any";
  suffix?: string;
  disabled?: boolean;
  onChange(v: number): void;
}) {
  const fallback = Number.isFinite(value) ? value : 0,
    [text, setText] = useState(String(fallback)),
    [editing, setEditing] = useState(false);
  const cancelledRef = useRef(false);
  const editedRef = useRef(false);
  useEffect(() => {
    if (!editing) setText(String(fallback));
  }, [editing, fallback]);
  function commit() {
    // A disabled field may blur after its controlling setting changes.
    if (disabled) {
      cancelledRef.current = false;
      editedRef.current = false;
      setEditing(false);
      setText(String(fallback));
      return;
    }
    const next = commitNumericEdit(
      text,
      fallback,
      min,
      max,
      cancelledRef.current,
      step === 1,
      editedRef.current,
    );
    cancelledRef.current = false;
    editedRef.current = false;
    setEditing(false);
    setText(String(next));
    if (next !== fallback) onChange(next);
  }
  return (
    <div className="number-wrap">
      <input
        type="number"
        value={text}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        onFocus={() => {
          cancelledRef.current = false;
          editedRef.current = false;
          setEditing(true);
        }}
        onChange={(e) => { editedRef.current = true; setText(e.target.value); }}
        onBlur={commit}
        onKeyDown={(e) => {
          // Enter/Escape are owned by the IME until composition ends.
          if (isDialogCompositionKey(e.nativeEvent)) return;
          if (e.key === "Enter") e.currentTarget.blur();
          else if (isPlainDialogEscape(e)) {
            e.preventDefault();
            e.stopPropagation();
            cancelledRef.current = true;
            setText(String(fallback));
            e.currentTarget.blur();
          }
        }}
      />
      {suffix && <span>{suffix}</span>}
    </div>
  );
}
function Select({
  value,
  options,
  disabled = false,
  onChange,
}: {
  value: string;
  options: Array<[string, string]>;
  disabled?: boolean;
  onChange(v: string): void;
}) {
  return (
    <select
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
    >
      {options.map(([v, l]) => (
        <option key={v} value={v}>
          {l}
        </option>
      ))}
    </select>
  );
}
