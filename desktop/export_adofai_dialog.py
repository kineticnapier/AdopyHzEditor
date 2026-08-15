from __future__ import annotations

import csv
import io
from pathlib import Path

from PySide6 import QtGui, QtWidgets

from exporters.adofai import build_adofai_debug_rows, build_adofai_level, build_tile_preview_points
from desktop.help_dialog import HelpDialog
from i18n import tr
from desktop.tile_preview_dialog import TilePreviewDialog


class AdoFAIDebugPreviewDialog(QtWidgets.QDialog):
    COLUMNS = [
        "index",
        "floor_start",
        "floor_end",
        "start_s",
        "end_s",
        "duration_s",
        "pause_before_s",
        "kind",
        "interpolation",
        "phase_continuous",
        "note",
        "midi",
        "freq_hz",
        "method",
        "keycount",
        "whole",
        "frac",
        "change_x",
        "angle",
        "angle_min",
        "angle_max",
        "auto_angle",
        "target_angle",
        "target_angle_used",
        "target_angle_ignored",
        "final_angle_scaled",
        "final_angle_effective",
        "effective_bpm",
        "final_bpm",
        "tiles_est",
        "final_visual_used",
        "overlap",
        "warning",
    ]

    def __init__(self, rows: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.rows = rows
        self.setWindowTitle(tr("debug.title"))
        self.resize(1280, 720)

        layout = QtWidgets.QVBoxLayout(self)

        total_tiles = sum(int(r.get("tiles_est", 0) or 0) for r in rows)
        target_used = sum(1 for r in rows if r.get("target_angle_used"))
        target_ignored = sum(1 for r in rows if r.get("target_angle_ignored"))
        visual_fixed = sum(1 for r in rows if r.get("final_visual_used"))
        warnings = sum(1 for r in rows if r.get("warning"))

        summary = QtWidgets.QLabel(
            f"Rows: {len(rows)} / Estimated tiles: {total_tiles} / "
            f"Target angle used: {target_used} / ignored: {target_ignored} / "
            f"final visual corrections: {visual_fixed} / warnings: {warnings}"
        )
        layout.addWidget(summary)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)

        max_display = 5000
        shown = min(len(rows), max_display)
        self.table.setRowCount(shown)

        for r, row in enumerate(rows[:shown]):
            for c, key in enumerate(self.COLUMNS):
                value = row.get(key, "")
                item = QtWidgets.QTableWidgetItem(str(value))
                if key == "warning" and value:
                    item.setBackground(QtGui.QColor(255, 210, 120))
                elif key in ("target_angle_used", "target_angle_ignored", "final_visual_used") and value:
                    item.setBackground(QtGui.QColor(190, 220, 255))
                self.table.setItem(r, c, item)

        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        if len(rows) > max_display:
            layout.addWidget(QtWidgets.QLabel(f"Only first {max_display} rows are shown. Copy buttons still copy all rows."))

        buttons = QtWidgets.QHBoxLayout()

        copy_tsv = QtWidgets.QPushButton(tr("debug.copy_tsv"))
        copy_tsv.clicked.connect(lambda: self.copy_rows("tsv"))
        buttons.addWidget(copy_tsv)

        copy_csv = QtWidgets.QPushButton(tr("debug.copy_csv"))
        copy_csv.clicked.connect(lambda: self.copy_rows("csv"))
        buttons.addWidget(copy_csv)

        close_btn = QtWidgets.QPushButton(tr("debug.close"))
        close_btn.clicked.connect(self.accept)
        buttons.addStretch(1)
        buttons.addWidget(close_btn)

        layout.addLayout(buttons)

    def rows_as_tsv(self) -> str:
        lines = ["\t".join(self.COLUMNS)]
        for row in self.rows:
            lines.append("\t".join(str(row.get(k, "")) for k in self.COLUMNS))
        return "\n".join(lines)

    def rows_as_csv(self) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(self.COLUMNS)
        for row in self.rows:
            writer.writerow([row.get(k, "") for k in self.COLUMNS])
        return buf.getvalue()

    def copy_rows(self, fmt: str) -> None:
        text = self.rows_as_csv() if fmt == "csv" else self.rows_as_tsv()
        QtWidgets.QApplication.clipboard().setText(text)



class ExportAdoFAIDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, *, selected_only: bool = False) -> None:
        super().__init__(parent)
        self.selected_only = bool(selected_only)
        self.setWindowTitle(tr("export.title"))
        self.resize(780, 560)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        def add_translated_items(combo: QtWidgets.QComboBox, items: list[tuple[str, str]]) -> None:
            for value, label_key in items:
                combo.addItem(tr(label_key), value)

        def set_combo_value(combo: QtWidgets.QComboBox, value: str) -> None:
            idx = combo.findData(value)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        def combo_value(combo: QtWidgets.QComboBox) -> str:
            data = combo.currentData()
            return str(data) if data is not None else combo.currentText()

        self._combo_value = combo_value

        self.method = QtWidgets.QComboBox()
        add_translated_items(self.method, [
            ("rabbit_zip", "export.method.angle_compression"),
            ("angle_only", "export.method.angle_only"),
            ("harmony", "export.method.harmony"),
        ])

        self.base_bpm = QtWidgets.QDoubleSpinBox()
        self.base_bpm.setRange(1.0, 999999.0)
        self.base_bpm.setDecimals(6)
        default_bpm = 175.0
        if parent is not None and hasattr(parent, "grid_bpm"):
            default_bpm = float(parent.grid_bpm.value())
        self.base_bpm.setValue(default_bpm)

        self.angle_only_bpm = QtWidgets.QDoubleSpinBox()
        self.angle_only_bpm.setRange(1.0, 999999.0)
        self.angle_only_bpm.setDecimals(6)
        self.angle_only_bpm.setValue(max(1000.0, default_bpm * 10.0))
        self.angle_only_bpm.setToolTip(
            "Angle-onlyモードで最初に使うグローバルBPM。\n"
            "このBPMをsettings.bpmに入れ、各Hzは角度だけで合わせます。\n"
            "値を大きくすると角度が大きくなり、見た目が詰まりにくくなります。"
        )

        self.harmony_mode = QtWidgets.QComboBox()
        add_translated_items(self.harmony_mode, [
            ("off", "export.harmony_mode.off"),
            ("octave +12", "export.harmony_mode.octave_up"),
            ("fifth +7", "export.harmony_mode.fifth"),
            ("major third +4", "export.harmony_mode.major_third"),
            ("minor third +3", "export.harmony_mode.minor_third"),
            ("lower octave -12", "export.harmony_mode.octave_down"),
            ("major triad", "export.harmony_mode.major_triad"),
            ("minor triad", "export.harmony_mode.minor_triad"),
            ("sus4", "export.harmony_mode.sus4"),
            ("dominant 7", "export.harmony_mode.dominant7"),
            ("custom", "export.harmony_mode.custom"),
        ])
        set_combo_value(self.harmony_mode, "fifth +7")
        self.harmony_mode.setToolTip(
            "Harmony / Polyrhythmモードで追加する和声音。\n"
            "root音の周期列と和声音の周期列をmergeして1本のタイル列にします。"
        )

        self.harmony_custom_semitone = QtWidgets.QDoubleSpinBox()
        self.harmony_custom_semitone.setRange(-48.0, 48.0)
        self.harmony_custom_semitone.setDecimals(3)
        self.harmony_custom_semitone.setValue(7.0)
        self.harmony_custom_semitone.setSuffix(" semitone")
        self.harmony_custom_semitone.setToolTip("Harmony mode が custom のときの追加音程")

        self.harmony_epsilon_ms = QtWidgets.QDoubleSpinBox()
        self.harmony_epsilon_ms.setRange(0.000001, 10.0)
        self.harmony_epsilon_ms.setDecimals(6)
        self.harmony_epsilon_ms.setValue(0.001)
        self.harmony_epsilon_ms.setSuffix(" ms")
        self.harmony_epsilon_ms.setToolTip("完全同時刻になったtileを微小時間ずらす量")

        self.harmony_tuning = QtWidgets.QComboBox()
        add_translated_items(self.harmony_tuning, [
            ("equal temperament", "export.harmony_tuning.equal"),
            ("just intonation", "export.harmony_tuning.just"),
        ])
        set_combo_value(self.harmony_tuning, "equal temperament")
        self.harmony_tuning.setToolTip(
            "3音以上のHarmonyで使うチューニング。\n"
            "equal temperamentは元音程に正確。\n"
            "just intonationは4:5:6などの単純比に寄せてパターンを安定させます。"
        )

        self.harmony_root_mode = QtWidgets.QComboBox()
        add_translated_items(self.harmony_root_mode, [
            ("fixed root", "export.harmony_root.fixed"),
            ("least squares Hz", "export.harmony_root.ls_hz"),
            ("least squares cents", "export.harmony_root.ls_cents"),
            ("minimax cents", "export.harmony_root.minimax"),
        ])
        set_combo_value(self.harmony_root_mode, "minimax cents")
        self.harmony_root_mode.setToolTip(
            "Just Intonation時のroot周波数調整。\n"
            "fixed root: rootを元音程に固定\n"
            "least squares Hz: Hz誤差の二乗和を最小化\n"
            "least squares cents: cents誤差の二乗和を最小化\n"
            "minimax cents: 最大cents誤差を最小化"
        )

        self.harmony_timing_mode = QtWidgets.QComboBox()
        add_translated_items(self.harmony_timing_mode, [
            ("setspeed", "export.harmony_timing.setspeed"),
            ("angle-only", "export.harmony_timing.angle_only"),
            ("ratio-polyrhythm", "export.harmony_timing.ratio_poly"),
        ])
        set_combo_value(self.harmony_timing_mode, "angle-only")
        self.harmony_timing_mode.setToolTip(
            "Harmonyのtiming変換方法。\n"
            "setspeed: pitch由来の角度 + SetSpeedでtiming補正。\n"
            "angle-only: 1つのグローバルBPMで、次のzipまでの時間を角度に直接変換します。\n"
            "ratio-polyrhythm: 音程比を小整数比へ近似し、3:4や4:5:6の角度列を生成します。"
        )

        self.harmony_visual_mode = QtWidgets.QComboBox()
        add_translated_items(self.harmony_visual_mode, [
            ("raw", "export.harmony_visual.raw"),
            ("round 45°", "export.harmony_visual.round45"),
            ("round 90°", "export.harmony_visual.round90"),
            ("custom step", "export.harmony_visual.custom"),
        ])
        set_combo_value(self.harmony_visual_mode, "round 45°")
        self.harmony_visual_mode.setToolTip(
            "Harmonyの見た目角度を読みやすい角度へ寄せます。\n"
            "setspeed/angle-onlyでは必要に応じてSetSpeed補正します。ratio-polyrhythmでは角度timing優先でSetSpeed連打は出しません。"
        )

        self.harmony_visual_step = QtWidgets.QDoubleSpinBox()
        self.harmony_visual_step.setRange(1.0, 180.0)
        self.harmony_visual_step.setDecimals(3)
        self.harmony_visual_step.setValue(45.0)
        self.harmony_visual_step.setSuffix("°")
        self.harmony_visual_step.setToolTip("Harmony visual mode が custom step のときの角度刻み")

        self.harmony_poly_cycle_angle = QtWidgets.QDoubleSpinBox()
        self.harmony_poly_cycle_angle.setRange(1.0, 100000.0)
        self.harmony_poly_cycle_angle.setDecimals(3)
        self.harmony_poly_cycle_angle.setValue(720.0)
        self.harmony_poly_cycle_angle.setSuffix("°")
        self.harmony_poly_cycle_angle.setToolTip(
            "ratio-polyrhythmで1周期全体に割り当てる相対角度合計。\n"
            "3:4で720°にすると 180,60,120,120,60,180 のような列になります。\n"
            "周期の再生時間はHarmony用BPMから決まり、各tileのSetSpeedは使いません。"
        )

        self.harmony_poly_pseudo_angle = QtWidgets.QDoubleSpinBox()
        self.harmony_poly_pseudo_angle.setRange(1.0, 180.0)
        self.harmony_poly_pseudo_angle.setDecimals(3)
        self.harmony_poly_pseudo_angle.setValue(30.0)
        self.harmony_poly_pseudo_angle.setSuffix("°")
        self.harmony_poly_pseudo_angle.setToolTip(
            "旧ratio-polyrhythm用設定。\n"
            "stable97以降のratio-polyrhythmはScratch式に同時点を重複削除するため、通常は使われません。"
        )

        self.harmony_poly_max_denominator = QtWidgets.QSpinBox()
        self.harmony_poly_max_denominator.setRange(1, 256)
        self.harmony_poly_max_denominator.setValue(24)
        self.harmony_poly_max_denominator.setToolTip(
            "音程比を分数近似するときの最大分母。\n"
            "大きくすると精密になりますが、7:11:13系などで密度が増えやすくなります。"
        )

        self.harmony_poly_ratio_octave_mode = QtWidgets.QComboBox()
        add_translated_items(self.harmony_poly_ratio_octave_mode, [
            ("octave-folded", "export.ratio_octave.folded"),
            ("absolute", "export.ratio_octave.absolute"),
        ])
        set_combo_value(self.harmony_poly_ratio_octave_mode, "octave-folded")
        self.harmony_poly_ratio_octave_mode.setToolTip(
            "ratio-polyrhythmの比率生成でオクターブ差をどう扱うか。\n"
            "octave-folded: 2オクターブ差などを同じ音名として扱い、1:4を1:1にします。\n"
            "absolute: 実周波数比をそのまま使います。"
        )

        self.x_mode = QtWidgets.QComboBox()
        add_translated_items(self.x_mode, [
            ("floor", "export.x_mode.floor"),
            ("lowest_floor", "export.x_mode.lowest_floor"),
            ("round", "export.x_mode.round"),
            ("ceil", "export.x_mode.ceil"),
            ("fixed", "export.x_mode.fixed"),
            ("target_bpm", "export.x_mode.target_bpm"),
        ])
        self.x_mode.setToolTip(
            "変更用xの選び方\n"
            "floor = 各ノートの floor(Keycount)\n"
            "lowest_floor = 全ノート中の一番低い floor(Keycount) に固定\n"
            "fixed = 下の Fixed change x を使う\n"
            "target_bpm = 指定BPMになるように x を自動計算。最後の端数tileはhorizontal扱い"
        )

        self.fixed_x = QtWidgets.QDoubleSpinBox()
        self.fixed_x.setRange(0.000001, 100000.0)
        self.fixed_x.setDecimals(6)
        self.fixed_x.setValue(8.0)
        self.fixed_x.setToolTip("Change x mode が fixed のときに使う変更用x。lowest_floorでは無視されます。")

        self.target_bpm = QtWidgets.QDoubleSpinBox()
        self.target_bpm.setRange(1.0, 999999.0)
        self.target_bpm.setDecimals(6)
        self.target_bpm.setValue(max(1000.0, default_bpm * 10.0))
        self.target_bpm.setToolTip(
            "Change x mode が target_bpm のときに使うBPM。\n"
            "x = BPM * note_duration / 60 で計算し、SetSpeedがこのBPMになるようにします。"
        )



        self.max_tiles = QtWidgets.QSpinBox()
        self.max_tiles.setRange(0, 10000000)
        self.max_tiles.setValue(200000)
        self.max_tiles.setSingleStep(10000)
        self.max_tiles.setSpecialValueText("Unlimited")

        self.max_tiles_per_note = QtWidgets.QSpinBox()
        self.max_tiles_per_note.setRange(0, 1000000)
        self.max_tiles_per_note.setValue(5000)
        self.max_tiles_per_note.setSingleStep(500)
        self.max_tiles_per_note.setSpecialValueText("Unlimited")

        self.track_visual = QtWidgets.QComboBox()
        add_translated_items(self.track_visual, [
            ("normal", "export.track_visual.normal"),
            ("faint", "export.track_visual.faint"),
            ("very faint", "export.track_visual.very_faint"),
            ("hidden", "export.track_visual.hidden"),
        ])
        set_combo_value(self.track_visual, "normal")
        self.track_visual.setToolTip(
            "Angle Compression は見た目がスパゲッティ状になりやすいです。\n"
            "faint/hidden にするとトラック線を薄く/非表示にできます。"
        )

        self.visual_path_mode = QtWidgets.QComboBox()
        add_translated_items(self.visual_path_mode, [
            ("raw", "export.visual_path.raw"),
            ("upward", "export.visual_path.upward"),
            ("upward avoid", "export.visual_path.upward_avoid"),
            ("twirl upward", "export.visual_path.twirl_upward"),
        ])
        set_combo_value(self.visual_path_mode, "raw")
        self.visual_path_mode.setToolTip(
            "全export mode共通の見た目パス補正。\n"
            "raw: 角度をそのまま使う\n"
            "upward: 各タイルの絶対方向を指定角度へ寄せ、SetSpeedでtimingを補正する\n"
            "upward avoid: 通常方向が既存タイルに近づきそうな時だけ、上方向候補へ逃がす\n"
            "twirl upward: 下向きになりそうな時だけそのfloorにTwirlを挟む。relは変えず、そのtileから即反転式で置く"
        )

        self.visual_path_angle = QtWidgets.QDoubleSpinBox()
        self.visual_path_angle.setRange(0.0, 359.999)
        self.visual_path_angle.setDecimals(3)
        self.visual_path_angle.setValue(90.0)
        self.visual_path_angle.setSuffix("°")
        self.visual_path_angle.setToolTip("Visual path upward の絶対方向。90°=上方向")

        self.visual_position_mode = QtWidgets.QComboBox()
        add_translated_items(self.visual_position_mode, [
            ("off", "export.visual_position.off"),
            ("note step", "export.visual_position.note_step"),
        ])
        set_combo_value(self.visual_position_mode, "off")
        self.visual_position_mode.setToolTip(
            "PositionTrackによる見た目調整。\n"
            "note step: 2つ目以降のノート開始floorにPositionTrackを置き、以降のタイルを指定量ずらします。"
        )

        self.visual_position_x = QtWidgets.QDoubleSpinBox()
        self.visual_position_x.setRange(-100000.0, 100000.0)
        self.visual_position_x.setDecimals(6)
        self.visual_position_x.setValue(0.0)
        self.visual_position_x.setToolTip("PositionTrack positionOffset[0]")

        self.visual_position_y = QtWidgets.QDoubleSpinBox()
        self.visual_position_y.setRange(-100000.0, 100000.0)
        self.visual_position_y.setDecimals(6)
        self.visual_position_y.setValue(0.0)
        self.visual_position_y.setToolTip("PositionTrack positionOffset[1]")

        self.final_angle_mode = QtWidgets.QComboBox()
        add_translated_items(self.final_angle_mode, [
            ("scaled", "export.final_mode.scaled"),
            ("cardinal", "export.final_mode.cardinal"),
            ("horizontal", "export.final_mode.horizontal"),
            ("custom", "export.final_mode.custom"),
        ])
        set_combo_value(self.final_angle_mode, "scaled")
        self.final_angle_mode.setToolTip(
            "最後の端数タイルの見た目補正\n"
            "scaled: 従来通り。angle * frac\n"
            "cardinal: 最後の絶対角度を0/90/180/270付近へ寄せる\n"
            "horizontal: 最後の絶対角度を必ず0°または180°の横向きへ寄せる\n"
            "custom: 下の Custom final angle を使う。180°にすれば直進"
        )

        self.final_custom_angle = QtWidgets.QDoubleSpinBox()
        self.final_custom_angle.setRange(0.001, 359.999)
        self.final_custom_angle.setDecimals(6)
        self.final_custom_angle.setValue(180.0)
        self.final_custom_angle.setSuffix("°")
        self.final_custom_angle.setToolTip("Final tile mode が custom のときに使う相対角度")

        self.final_cardinal_step = QtWidgets.QDoubleSpinBox()
        self.final_cardinal_step.setRange(1.0, 180.0)
        self.final_cardinal_step.setDecimals(3)
        self.final_cardinal_step.setValue(90.0)
        self.final_cardinal_step.setSuffix("°")
        self.final_cardinal_step.setToolTip("cardinal modeの吸着角度。90=縦横、45=斜めも許可")

        self._song_source_path = str(getattr(parent, "current_audio", "") or "")
        self._auto_song_offset_ms = 0.0
        if parent is not None and hasattr(parent, "base_notes_for_export"):
            try:
                note_source = parent.base_notes_for_export(selected_only=self.selected_only)
                if note_source:
                    self._auto_song_offset_ms = round(
                        min(n.normalized().start for n in note_source) * 1000.0,
                        3,
                    )
            except Exception:
                self._auto_song_offset_ms = 0.0

        self.use_project_song = QtWidgets.QCheckBox(tr("export.song.use_project_audio"))
        self.use_project_song.setChecked(bool(self._song_source_path) and bool(getattr(parent, "adofai_use_project_song", True)))
        self.use_project_song.setToolTip("settings.songFilename に現在読み込んでいる音声ファイル名を入れます")

        self.copy_project_song = QtWidgets.QCheckBox(tr("export.song.copy_next_to_level"))
        self.copy_project_song.setChecked(bool(self._song_source_path) and bool(getattr(parent, "adofai_copy_project_song", True)))
        self.copy_project_song.setToolTip("ADOFAI出力先フォルダへ音声ファイルをコピーします。Release用に便利です。")

        self.song_offset_auto = QtWidgets.QCheckBox(tr("export.song_offset.use_first_note"))
        self.song_offset_auto.setChecked(bool(getattr(parent, "adofai_song_offset_auto", True)))
        self.song_offset_auto.setToolTip("最初のノート開始時刻をADOFAI settings.songOffset に使います")

        self.song_offset_ms = QtWidgets.QDoubleSpinBox()
        self.song_offset_ms.setRange(-3600000.0, 3600000.0)
        self.song_offset_ms.setDecimals(3)
        self.song_offset_ms.setSingleStep(1.0)
        self.song_offset_ms.setSuffix(" ms")
        manual_offset = float(getattr(parent, "adofai_song_offset_ms", self._auto_song_offset_ms))
        self.song_offset_ms.setValue(self._auto_song_offset_ms if self.song_offset_auto.isChecked() else manual_offset)
        self.song_offset_ms.setToolTip("ADOFAI settings.songOffset。自動時は最初のノート開始時刻です。")
        self.song_offset_auto.stateChanged.connect(self.update_song_offset_state)
        self.update_song_offset_state()

        self.debug_preview_button = QtWidgets.QPushButton(tr("export.debug_preview"))
        self.debug_preview_button.setToolTip(tr("export.debug_preview.tooltip"))
        self.debug_preview_button.clicked.connect(self.show_debug_preview)

        self.tile_preview_button = QtWidgets.QPushButton(tr("export.tile_preview"))
        self.tile_preview_button.setToolTip(tr("export.tile_preview.tooltip"))
        self.tile_preview_button.clicked.connect(self.show_tile_preview)

        self.export_help_button = QtWidgets.QPushButton(tr("export.help"))
        self.export_help_button.setToolTip(tr("export.help.tooltip"))
        self.export_help_button.clicked.connect(self.show_export_help)

        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(True)
        main_layout.addWidget(tabs, 1)

        def add_export_tab(title: str, rows: list[tuple[str, QtWidgets.QWidget]]) -> None:
            page = QtWidgets.QWidget()
            form = QtWidgets.QFormLayout(page)
            form.setContentsMargins(12, 12, 12, 12)
            form.setHorizontalSpacing(10)
            form.setVerticalSpacing(7)
            form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            for label, widget in rows:
                form.addRow(label, widget)

            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            scroll.setWidget(page)
            tabs.addTab(scroll, title)

        add_export_tab(tr("export.tab_basic"), [
            (tr("export.method"), self.method),
            (tr("export.base_bpm"), self.base_bpm),
            (tr("export.angle_only_bpm"), self.angle_only_bpm),
            (tr("export.track_visual"), self.track_visual),
            (tr("export.visual_path_mode"), self.visual_path_mode),
            (tr("export.visual_path_angle"), self.visual_path_angle),
            (tr("export.visual_position_mode"), self.visual_position_mode),
            (tr("export.visual_position_x"), self.visual_position_x),
            (tr("export.visual_position_y"), self.visual_position_y),
        ])

        add_export_tab(tr("export.tab_harmony"), [
            (tr("export.harmony_mode"), self.harmony_mode),
            (tr("export.harmony_custom_semitone"), self.harmony_custom_semitone),
            (tr("export.harmony_epsilon"), self.harmony_epsilon_ms),
            (tr("export.harmony_tuning"), self.harmony_tuning),
            (tr("export.harmony_root_mode"), self.harmony_root_mode),
            (tr("export.harmony_timing_mode"), self.harmony_timing_mode),
            (tr("export.harmony_visual_mode"), self.harmony_visual_mode),
            (tr("export.harmony_visual_step"), self.harmony_visual_step),
            (tr("export.harmony_poly_cycle_angle"), self.harmony_poly_cycle_angle),
            (tr("export.harmony_poly_max_denominator"), self.harmony_poly_max_denominator),
            (tr("export.harmony_poly_ratio_octave_mode"), self.harmony_poly_ratio_octave_mode),
        ])

        add_export_tab(tr("export.tab_advanced"), [
            (tr("export.change_x_mode"), self.x_mode),
            (tr("export.fixed_change_x"), self.fixed_x),
            (tr("export.target_bpm"), self.target_bpm),
            (tr("export.max_tiles"), self.max_tiles),
            (tr("export.max_tiles_per_note"), self.max_tiles_per_note),
        ])

        add_export_tab(tr("export.tab_final_tile"), [
            (tr("export.final_tile_mode"), self.final_angle_mode),
            (tr("export.custom_final_angle"), self.final_custom_angle),
            (tr("export.cardinal_step"), self.final_cardinal_step),
        ])

        add_export_tab(tr("export.tab_song"), [
            (tr("export.song"), self.use_project_song),
            (tr("export.copy_song"), self.copy_project_song),
            (tr("export.song_offset_auto"), self.song_offset_auto),
            (tr("export.song_offset_ms"), self.song_offset_ms),
        ])

        add_export_tab(tr("export.tab_preview_help"), [
            (tr("export.debug"), self.debug_preview_button),
            (tr("export.tile_preview_row"), self.tile_preview_button),
            (tr("export.help_row"), self.export_help_button),
        ])

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def update_song_offset_state(self) -> None:
        checked = bool(self.song_offset_auto.isChecked())
        if checked:
            self.song_offset_ms.setValue(self._auto_song_offset_ms)
        self.song_offset_ms.setEnabled(not checked)

    def store_workflow_to_parent(self) -> None:
        parent = self.parent()
        if parent is None:
            return
        parent.adofai_use_project_song = bool(self.use_project_song.isChecked())
        parent.adofai_copy_project_song = bool(self.copy_project_song.isChecked())
        parent.adofai_song_offset_auto = bool(self.song_offset_auto.isChecked())
        parent.adofai_song_offset_ms = float(self.song_offset_ms.value())

    def show_export_help(self) -> None:
        dlg = HelpDialog(self, initial_section="adofai_export")
        dlg.exec()

    def show_tile_preview(self) -> None:
        parent = self.parent()
        if parent is None or not hasattr(parent, "notes_with_output_octave"):
            QtWidgets.QMessageBox.warning(self, tr("tile_preview.title"), "Could not access editor notes.")
            return

        try:
            note_source = (
                parent.notes_with_export_pitch_offset(selected_only=self.selected_only)
                if hasattr(parent, "notes_with_export_pitch_offset")
                else parent.notes_with_output_octave()
            )
            opts = dict(self.options())
            opts.pop("_copy_song_to_export", None)
            opts.pop("_song_source_path", None)
            opts.pop("pretty", None)

            level, stats = build_adofai_level(note_source, **opts)
            points = build_tile_preview_points(level.get("angleData", []), max_preview_tiles=5000)
            dlg = TilePreviewDialog(points, stats, preview_limit=5000, parent=self)
            dlg.exec()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, tr("tile_preview.title"), str(e))

    def show_debug_preview(self) -> None:
        parent = self.parent()
        if parent is None or not hasattr(parent, "notes_with_output_octave"):
            QtWidgets.QMessageBox.warning(self, tr("debug.title"), "Could not access editor notes.")
            return

        try:
            note_source = (
                parent.notes_with_export_pitch_offset(selected_only=self.selected_only)
                if hasattr(parent, "notes_with_export_pitch_offset")
                else parent.notes_with_output_octave()
            )
            rows = build_adofai_debug_rows(note_source, **self.options())
            dlg = AdoFAIDebugPreviewDialog(rows, self)
            dlg.exec()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, tr("debug.title"), str(e))

    def options(self) -> dict:
        return {
            "method": self._combo_value(self.method),
            "base_bpm": float(self.base_bpm.value()),
            "angle_only_bpm": float(self.angle_only_bpm.value()),
            "harmony_mode": self._combo_value(self.harmony_mode),
            "harmony_custom_semitone": float(self.harmony_custom_semitone.value()),
            "harmony_epsilon_ms": float(self.harmony_epsilon_ms.value()),
            "harmony_tuning": self._combo_value(self.harmony_tuning),
            "harmony_root_mode": self._combo_value(self.harmony_root_mode),
            "harmony_timing_mode": self._combo_value(self.harmony_timing_mode),
            "harmony_visual_mode": self._combo_value(self.harmony_visual_mode),
            "harmony_visual_step": float(self.harmony_visual_step.value()),
            "harmony_poly_cycle_angle": float(self.harmony_poly_cycle_angle.value()),
            "harmony_poly_pseudo_angle": 30.0,
            "harmony_poly_max_denominator": int(self.harmony_poly_max_denominator.value()),
            "harmony_poly_ratio_octave_mode": self._combo_value(self.harmony_poly_ratio_octave_mode),
            "rabbit_x_mode": self._combo_value(self.x_mode),
            "rabbit_fixed_x": float(self.fixed_x.value()),
            "rabbit_target_bpm": float(self.target_bpm.value()),
            "max_tiles": int(self.max_tiles.value()),
            "max_tiles_per_note": int(self.max_tiles_per_note.value()),
            "track_visual": self._combo_value(self.track_visual),
            "visual_path_mode": self._combo_value(self.visual_path_mode),
            "visual_path_angle": float(self.visual_path_angle.value()),
            "visual_position_mode": self._combo_value(self.visual_position_mode),
            "visual_position_x": float(self.visual_position_x.value()),
            "visual_position_y": float(self.visual_position_y.value()),
            # Phase-continuous glide is now the standard behavior.
            "phase_continuous_glide": True,
            "final_angle_mode": self._combo_value(self.final_angle_mode),
            "final_custom_angle": float(self.final_custom_angle.value()),
            "final_cardinal_step": float(self.final_cardinal_step.value()),
            "song_filename": Path(self._song_source_path).name if self.use_project_song.isChecked() and self._song_source_path else None,
            "song_offset_ms": float(self.song_offset_ms.value()) if self.use_project_song.isChecked() else None,
            "_copy_song_to_export": bool(self.copy_project_song.isChecked() and self.use_project_song.isChecked() and self._song_source_path),
            "_song_source_path": self._song_source_path if self.use_project_song.isChecked() and self._song_source_path else None,
            "pretty": False,
        }
