from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from audio_analysis import analyze_cqt, analysis_profile_options
from audio_player import AudioPlayer
from editor_view import EditorView
from export_midi import export_midi
from export_adofai import export_adofai
from project_io import save_project, load_project
from note_model import Note


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("AdopyHzEditor")
        self.resize(1320, 820)

        self.editor = EditorView()
        self.setCentralWidget(self.editor)
        self.editor.status_changed.connect(self.statusBar().showMessage)
        self.editor.playhead_moved.connect(self.on_playhead_dragged)
        self.editor.notes_changed.connect(self.on_notes_changed)
        self.editor.plot.wheel_navigate.connect(self.on_plot_wheel)

        self.player = AudioPlayer()
        self.current_audio: str | None = None
        self.current_project: Path | None = None
        self._ignore_scroll_signal = False
        self._suppress_dirty = False
        self._dirty = False
        self.note_clipboard: list[Note] = []

        self._make_menus()
        self._make_toolbar()
        self._make_bottom_controls()
        self._make_shortcuts()
        self._connect_dirty_signals()
        self.update_window_title()

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.update_playhead_from_player)
        self.timer.start()

        if not self.player.available:
            self.statusBar().showMessage(f"Playback disabled: {self.player.error}")
        else:
            self.statusBar().showMessage("Open an audio file")

    def update_window_title(self) -> None:
        mark = "*" if self._dirty else ""
        project = f" - {self.current_project.name}" if self.current_project else ""
        self.setWindowTitle(f"AdopyHzEditor{mark}{project}")

    def set_dirty(self, dirty: bool = True) -> None:
        if self._suppress_dirty and dirty:
            return
        if self._dirty != bool(dirty):
            self._dirty = bool(dirty)
            self.update_window_title()

    def mark_dirty(self) -> None:
        self.set_dirty(True)

    def on_notes_changed(self) -> None:
        self.sync_notes_to_player()
        self.mark_dirty()

    def _connect_dirty_signals(self) -> None:
        """
        Mark project dirty when project-affecting controls change.
        View-only controls such as contrast/gamma are intentionally excluded.
        """
        widgets = [
            getattr(self, "grid_bpm", None),
            getattr(self, "grid_offset_ms", None),
            getattr(self, "grid_enabled", None),
            getattr(self, "metro_enabled", None),
            getattr(self, "metro_vol", None),
            getattr(self, "snap_enabled", None),
            getattr(self, "snap_div", None),
            getattr(self, "note_octave", None),
            getattr(self, "note_vol", None),
            getattr(self, "note_sound_enabled", None),
            getattr(self, "volume", None),
            getattr(self, "playback_speed", None),
            getattr(self, "analysis_profile", None),
        ]

        for w in widgets:
            if w is None:
                continue
            if hasattr(w, "valueChanged"):
                w.valueChanged.connect(lambda *args: self.mark_dirty())
            if hasattr(w, "stateChanged"):
                w.stateChanged.connect(lambda *args: self.mark_dirty())
            if hasattr(w, "currentTextChanged"):
                w.currentTextChanged.connect(lambda *args: self.mark_dirty())

    def confirm_discard_unsaved(self, title: str = "Unsaved changes") -> bool:
        if not self._dirty:
            return True

        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText("保存していない変更があります。")
        box.setInformativeText("続行する前に保存しますか？")
        save_btn = box.addButton("保存", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        discard_btn = box.addButton("保存せず続行", QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton("キャンセル", QtWidgets.QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save_btn)
        box.exec()

        clicked = box.clickedButton()
        if clicked == save_btn:
            return self.save_project_as()
        if clicked == discard_btn:
            return True
        if clicked == cancel_btn:
            return False
        return False

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.confirm_discard_unsaved("Close AdopyHzEditor"):
            event.accept()
        else:
            event.ignore()

    def _make_menus(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("ファイル(&F)")
        file_menu.addAction("開く(&O)", self.open_audio, QtGui.QKeySequence("Ctrl+O"))
        file_menu.addAction("プロジェクト保存(&S)", self.save_project_as, QtGui.QKeySequence("Ctrl+S"))
        file_menu.addAction("プロジェクト読込(&L)", self.load_project_from_file, QtGui.QKeySequence("Ctrl+L"))
        file_menu.addSeparator()
        file_menu.addAction("MIDI出力", self.export_midi_file, QtGui.QKeySequence("Ctrl+M"))
        file_menu.addAction("ADOFAI Hz出力", self.export_adofai_file, QtGui.QKeySequence("Ctrl+E"))

        edit_menu = menubar.addMenu("編集(&E)")
        edit_menu.addAction("元に戻す", self.editor.undo)
        edit_menu.addAction("やり直し", self.editor.redo)
        edit_menu.addSeparator()
        edit_menu.addAction("コピー", self.copy_selected_notes)
        edit_menu.addAction("切り取り", self.cut_selected_notes)
        edit_menu.addAction("貼り付け", self.paste_notes)
        edit_menu.addSeparator()
        edit_menu.addAction("すべて選択", self.editor.select_all_notes, QtGui.QKeySequence("Ctrl+A"))
        edit_menu.addAction("選択解除", self.editor.clear_selection, QtGui.QKeySequence("Esc"))
        edit_menu.addAction("選択ノート削除", self.editor.delete_selected, QtGui.QKeySequence("Delete"))

        play_menu = menubar.addMenu("再生(&P)")
        play_menu.addAction("再生/一時停止", self.toggle_playback)
        play_menu.addAction("停止", self.stop_playback, QtGui.QKeySequence("Ctrl+Space"))
        play_menu.addAction("1秒戻る", lambda: self.seek_relative(-1.0), QtGui.QKeySequence("Left"))
        play_menu.addAction("1秒進む", lambda: self.seek_relative(1.0), QtGui.QKeySequence("Right"))

        analyze_menu = menubar.addMenu("解析(&A)")
        analyze_menu.addAction("スペクトログラム再描画", self.apply_visual)

        view_menu = menubar.addMenu("表示(&V)")
        view_menu.addAction("スペクトログラム重視", lambda: self.editor.set_mode(0), QtGui.QKeySequence("1"))
        view_menu.addAction("ノート重視", lambda: self.editor.set_mode(1), QtGui.QKeySequence("2"))
        view_menu.addAction("両方表示", lambda: self.editor.set_mode(2), QtGui.QKeySequence("3"))
        view_menu.addAction("全体表示", self.fit_all)

        menubar.addMenu("オプション(&O)")
        help_menu = menubar.addMenu("ヘルプ(&H)")
        help_menu.addAction("操作メモ", lambda: QtWidgets.QMessageBox.information(
            self,
            "操作メモ",
            "左ドラッグ: ノート作成\n"
            "左クリック: 再生棒移動/ノート選択\n"
            "Ctrl+左クリック: 複数選択の追加/解除\n"
            "Shift+左クリック: 範囲選択\n"
            "右クリック: ノート削除\n"
            "Space: 再生/一時停止\n"
            "Snap: BPMグリッドへ吸着"
        ))

    def _make_toolbar(self) -> None:
        tb = QtWidgets.QToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QtCore.QSize(18, 18))
        self.addToolBar(tb)

        def action(text: str, slot, shortcut: str | None = None, tip: str | None = None):
            a = QtGui.QAction(text, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(QtGui.QKeySequence(shortcut))
            if tip:
                a.setToolTip(tip)
            tb.addAction(a)
            return a

        # WaveToneっぽい、小さめの操作列
        action("↶", lambda: self.seek_to(0.0), tip="先頭へ")
        action("■", self.stop_playback, "Ctrl+Space", "停止")
        action("▶", self.toggle_playback, tip="再生/一時停止")
        action("◀", lambda: self.seek_relative(-1.0), tip="1秒戻る")
        action("▶", lambda: self.seek_relative(1.0), tip="1秒進む")
        tb.addSeparator()

        action("MIDI", self.export_midi_file, "Ctrl+M", "Export MIDI")
        action("Hz", self.export_adofai_file, "Ctrl+E", "Export ADOFAI Hz")
        tb.addSeparator()

        action("Spec", lambda: self.editor.set_mode(0), "1")
        action("Note", lambda: self.editor.set_mode(1), "2")
        action("Both", lambda: self.editor.set_mode(2), "3")
        tb.addSeparator()

        self.time_label = QtWidgets.QLabel("0:00.000/0:00.000")
        self.time_label.setMinimumWidth(118)
        self.time_label.setMaximumWidth(132)
        self.time_label.setToolTip("Current time / total length")
        tb.addWidget(self.time_label)
        tb.addSeparator()

        panel = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(panel)
        grid.setContentsMargins(2, 0, 2, 0)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(1)

        self.volume = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(85)
        self.volume.setFixedWidth(92)
        self.volume.valueChanged.connect(lambda v: self.player.set_volume(v / 100.0))

        self.playback_speed = QtWidgets.QDoubleSpinBox()
        self.playback_speed.setRange(0.10, 4.00)
        self.playback_speed.setDecimals(2)
        self.playback_speed.setSingleStep(0.05)
        self.playback_speed.setValue(1.00)
        self.playback_speed.setSuffix("x")
        self.playback_speed.setFixedWidth(72)
        self.playback_speed.valueChanged.connect(self.apply_playback_speed)

        self.note_sound_enabled = QtWidgets.QCheckBox()
        self.note_sound_enabled.setChecked(True)
        self.note_sound_enabled.setToolTip("追加したノート音を再生")
        self.note_sound_enabled.stateChanged.connect(self.apply_note_sound_settings)

        self.note_vol = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.note_vol.setRange(0, 100)
        self.note_vol.setValue(20)
        self.note_vol.setFixedWidth(92)
        self.note_vol.valueChanged.connect(self.apply_note_sound_settings)

        self.note_octave = QtWidgets.QSpinBox()
        self.note_octave.setRange(-4, 4)
        self.note_octave.setValue(0)
        self.note_octave.setFixedWidth(78)
        self.note_octave.setToolTip("プレビュー/MIDI/ADOFAI出力だけをオクターブ単位で上下。画面上のノート位置は変えません。")
        self.note_octave.valueChanged.connect(self.apply_note_sound_settings)

        self.contrast = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.contrast.setRange(0, 300)
        self.contrast.setValue(115)
        self.contrast.setFixedWidth(92)
        self.contrast.valueChanged.connect(self.apply_visual)

        self.gamma = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.gamma.setRange(5, 500)
        self.gamma.setValue(75)
        self.gamma.setFixedWidth(92)
        self.gamma.valueChanged.connect(self.apply_visual)

        grid.addWidget(QtWidgets.QLabel("Song Vol"), 0, 0)
        song_box = QtWidgets.QWidget()
        song_layout = QtWidgets.QHBoxLayout(song_box)
        song_layout.setContentsMargins(0, 0, 0, 0)
        song_layout.setSpacing(3)
        song_layout.addWidget(self.volume)
        song_layout.addWidget(QtWidgets.QLabel("Speed"))
        song_layout.addWidget(self.playback_speed)
        grid.addWidget(song_box, 0, 1)
        grid.addWidget(QtWidgets.QLabel("Note Vol"), 1, 0)
        note_box = QtWidgets.QWidget()
        note_layout = QtWidgets.QHBoxLayout(note_box)
        note_layout.setContentsMargins(0, 0, 0, 0)
        note_layout.setSpacing(3)
        note_layout.addWidget(self.note_sound_enabled)
        note_layout.addWidget(self.note_vol)
        note_layout.addWidget(QtWidgets.QLabel("Oct"))
        note_layout.addWidget(self.note_octave, 0)
        grid.addWidget(note_box, 1, 1)

        grid.addWidget(QtWidgets.QLabel("Contrast"), 0, 2)
        grid.addWidget(self.contrast, 0, 3)
        grid.addWidget(QtWidgets.QLabel("Gamma"), 1, 2)
        grid.addWidget(self.gamma, 1, 3)

        tb.addWidget(panel)

        tb.addSeparator()
        self.enhance = QtWidgets.QCheckBox("Enhance")
        self.enhance.setChecked(True)
        self.enhance.stateChanged.connect(self.apply_visual)
        tb.addWidget(self.enhance)

        tb.addWidget(QtWidgets.QLabel(" Display "))
        self.display_mode = QtWidgets.QComboBox()
        self.display_mode.addItems(["wavetone", "ridge", "smooth"])
        self.display_mode.setCurrentText("wavetone")
        self.display_mode.setToolTip(
            "wavetone: 見やすいブロック表示\n"
            "ridge: ピッチの山だけを残す\n"
            "smooth: 従来のなめらかなスペクトログラム"
        )
        self.display_mode.currentTextChanged.connect(self.apply_visual)
        tb.addWidget(self.display_mode)

        tb.addWidget(QtWidgets.QLabel(" Harmonics "))
        self.harmonics = QtWidgets.QComboBox()
        self.harmonics.addItems(["off", "soft", "strong"])
        self.harmonics.currentTextChanged.connect(self.apply_visual)
        tb.addWidget(self.harmonics)

        self.cmap = QtWidgets.QComboBox()
        self.cmap.addItems(["wavetone", "viridis", "magma", "inferno", "plasma", "gray"])
        self.cmap.setCurrentText("wavetone")
        self.cmap.currentTextChanged.connect(self.apply_visual)
        tb.addWidget(self.cmap)

        tb.addWidget(QtWidgets.QLabel(" Analysis "))
        self.analysis_profile = QtWidgets.QComboBox()
        self.analysis_profile.addItems(["Fast", "Normal", "Full C0-C10"])
        self.analysis_profile.setCurrentText("Normal")
        self.analysis_profile.setToolTip(
            "Fast: C1-C7 / rougher time resolution\n"
            "Normal: balanced\n"
            "Full C0-C10: widest range, slower"
        )
        tb.addWidget(self.analysis_profile)

    def _make_bottom_controls(self) -> None:
        bar = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout(bar)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setColumnStretch(1, 1)

        self.time_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.time_slider.setRange(0, 100000)
        self.time_slider.valueChanged.connect(self.on_time_slider)

        self.visible_sec = QtWidgets.QDoubleSpinBox()
        self.visible_sec.setRange(0.5, 300.0)
        self.visible_sec.setDecimals(1)
        self.visible_sec.setValue(12.0)
        self.visible_sec.setSuffix(" s")
        self.visible_sec.valueChanged.connect(self.update_view_from_controls)

        self.pitch_bottom = QtWidgets.QSpinBox()
        self.pitch_bottom.setRange(12, 120)
        self.pitch_bottom.setValue(12)
        self.pitch_bottom.valueChanged.connect(self.update_view_from_controls)

        self.visible_notes = QtWidgets.QSpinBox()
        self.visible_notes.setRange(6, 109)
        self.visible_notes.setValue(60)
        self.visible_notes.valueChanged.connect(self.update_view_from_controls)

        self.fit_button = QtWidgets.QPushButton("Fit")
        self.fit_button.clicked.connect(self.fit_all)

        self.grid_enabled = QtWidgets.QCheckBox("Grid")
        self.grid_enabled.setChecked(False)
        self.grid_enabled.stateChanged.connect(self.apply_timing_helpers)

        self.metro_enabled = QtWidgets.QCheckBox("Metronome")
        self.metro_enabled.setChecked(False)
        self.metro_enabled.stateChanged.connect(self.apply_timing_helpers)

        self.grid_bpm = QtWidgets.QDoubleSpinBox()
        self.grid_bpm.setRange(1.0, 2000.0)
        self.grid_bpm.setDecimals(6)
        self.grid_bpm.setValue(175.0)
        self.grid_bpm.setSingleStep(1.0)
        self.grid_bpm.valueChanged.connect(self.apply_timing_helpers)

        self.grid_offset_ms = QtWidgets.QDoubleSpinBox()
        self.grid_offset_ms.setRange(-600000.0, 600000.0)
        self.grid_offset_ms.setDecimals(3)
        self.grid_offset_ms.setValue(0.0)
        self.grid_offset_ms.setSuffix(" ms")
        self.grid_offset_ms.setSingleStep(1.0)
        self.grid_offset_ms.valueChanged.connect(self.apply_timing_helpers)

        self.metro_vol = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.metro_vol.setRange(0, 100)
        self.metro_vol.setValue(35)
        self.metro_vol.setFixedWidth(80)
        self.metro_vol.valueChanged.connect(self.apply_timing_helpers)

        self.snap_enabled = QtWidgets.QCheckBox("Snap")
        self.snap_enabled.setChecked(False)
        self.snap_enabled.stateChanged.connect(self.apply_timing_helpers)

        self.snap_div = QtWidgets.QSpinBox()
        self.snap_div.setRange(1, 64)
        self.snap_div.setValue(1)
        self.snap_div.setToolTip("Snap subdivision per beat. 1 = beat, 4 = quarter-beat grid")
        self.snap_div.valueChanged.connect(self.apply_timing_helpers)

        layout.addWidget(QtWidgets.QLabel("Time"), 0, 0)
        layout.addWidget(self.time_slider, 0, 1)
        layout.addWidget(QtWidgets.QLabel("Visible"), 0, 2)
        layout.addWidget(self.visible_sec, 0, 3)
        self.pitch_down_button = QtWidgets.QPushButton("Pitch ↓")
        self.pitch_down_button.clicked.connect(lambda: self.move_pitch(-12))
        self.pitch_up_button = QtWidgets.QPushButton("Pitch ↑")
        self.pitch_up_button.clicked.connect(lambda: self.move_pitch(+12))

        layout.addWidget(QtWidgets.QLabel("Pitch bottom"), 0, 4)
        layout.addWidget(self.pitch_bottom, 0, 5)
        layout.addWidget(self.pitch_down_button, 0, 6)
        layout.addWidget(self.pitch_up_button, 0, 7)
        layout.addWidget(QtWidgets.QLabel("Visible notes"), 0, 8)
        layout.addWidget(self.visible_notes, 0, 9)
        layout.addWidget(self.fit_button, 0, 10)

        layout.addWidget(self.grid_enabled, 1, 0)
        layout.addWidget(self.metro_enabled, 1, 1)
        layout.addWidget(QtWidgets.QLabel("BPM"), 1, 2)
        layout.addWidget(self.grid_bpm, 1, 3)
        layout.addWidget(QtWidgets.QLabel("Offset"), 1, 4)
        layout.addWidget(self.grid_offset_ms, 1, 5)
        layout.addWidget(QtWidgets.QLabel("Metro Vol"), 1, 6)
        layout.addWidget(self.metro_vol, 1, 7)
        layout.addWidget(self.snap_enabled, 1, 8)
        layout.addWidget(QtWidgets.QLabel("Snap div"), 1, 9)
        layout.addWidget(self.snap_div, 1, 10)

        self.addToolBarBreak()
        bottom_tb = QtWidgets.QToolBar("View")
        bottom_tb.setMovable(False)
        bottom_tb.addWidget(bar)
        self.addToolBar(QtCore.Qt.ToolBarArea.BottomToolBarArea, bottom_tb)

    def _make_shortcuts(self) -> None:
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self, activated=self.editor.undo)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Y"), self, activated=self.editor.redo)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+Z"), self, activated=self.editor.redo)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+C"), self, activated=self.copy_selected_notes)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+X"), self, activated=self.cut_selected_notes)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+V"), self, activated=self.paste_notes)
        QtGui.QShortcut(QtGui.QKeySequence("Delete"), self, activated=self.editor.delete_selected)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+A"), self, activated=self.editor.select_all_notes)
        QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, activated=self.editor.clear_selection)
        QtGui.QShortcut(QtGui.QKeySequence("Tab"), self, activated=self.editor.cycle_mode)
        QtGui.QShortcut(QtGui.QKeySequence("Space"), self, activated=self.toggle_playback)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Space"), self, activated=self.stop_playback)
        QtGui.QShortcut(QtGui.QKeySequence("Left"), self, activated=lambda: self.seek_relative(-1.0))
        QtGui.QShortcut(QtGui.QKeySequence("Right"), self, activated=lambda: self.seek_relative(1.0))
        QtGui.QShortcut(QtGui.QKeySequence("Shift+Left"), self, activated=lambda: self.seek_relative(-5.0))
        QtGui.QShortcut(QtGui.QKeySequence("Shift+Right"), self, activated=lambda: self.seek_relative(5.0))

        # Vertical navigation
        QtGui.QShortcut(QtGui.QKeySequence("W"), self, activated=lambda: self.move_pitch(+12))
        QtGui.QShortcut(QtGui.QKeySequence("S"), self, activated=lambda: self.move_pitch(-12))
        QtGui.QShortcut(QtGui.QKeySequence("Up"), self, activated=lambda: self.move_pitch(+1))
        QtGui.QShortcut(QtGui.QKeySequence("Down"), self, activated=lambda: self.move_pitch(-1))
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Up"), self, activated=lambda: self.move_pitch(+12))
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Down"), self, activated=lambda: self.move_pitch(-12))

        # Selected note movement
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+Left"), self, activated=lambda: self.nudge_selected_notes(-1, 0))
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+Right"), self, activated=lambda: self.nudge_selected_notes(+1, 0))
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+Up"), self, activated=lambda: self.nudge_selected_notes(0, +1))
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+Down"), self, activated=lambda: self.nudge_selected_notes(0, -1))

    def format_time(self, seconds: float) -> str:
        seconds = max(0.0, float(seconds))
        m = int(seconds // 60)
        s = int(seconds % 60)
        ms = int(round((seconds - int(seconds)) * 1000))
        if ms >= 1000:
            s += 1
            ms = 0
        return f"{m}:{s:02d}.{ms:03d}"

    def update_time_labels(self) -> None:
        if hasattr(self, "time_label"):
            t = self.editor.playhead_time()
            spec = self.editor.spectrogram
            total = spec.duration if spec is not None else 0.0
            self.time_label.setText(f"{self.format_time(t)}/{self.format_time(total)}")

    def apply_note_sound_settings(self) -> None:
        if hasattr(self.player, "set_note_sound"):
            self.player.set_note_sound(
                enabled=self.note_sound_enabled.isChecked() if hasattr(self, "note_sound_enabled") else True,
                volume=float(self.note_vol.value()) / 100.0 if hasattr(self, "note_vol") else 0.20,
                octave_shift=int(self.note_octave.value()) if hasattr(self, "note_octave") else 0,
            )

    def sync_notes_to_player(self) -> None:
        if hasattr(self.player, "set_preview_notes"):
            self.player.set_preview_notes(self.editor.notes)
        self.apply_note_sound_settings()

    def nudge_selected_notes(self, time_steps: int, pitch_steps: int) -> None:
        dt = 0.0
        if time_steps:
            dt = self.editor.default_nudge_seconds() * int(time_steps)
        self.editor.nudge_selected(dx=dt, dy=int(pitch_steps))
        self.sync_notes_to_player()

    def apply_playback_speed(self) -> None:
        if hasattr(self.player, "set_playback_speed"):
            speed = float(self.playback_speed.value()) if hasattr(self, "playback_speed") else 1.0
            self.player.set_playback_speed(speed)

    def selected_note_indices(self) -> list[int]:
        if hasattr(self.editor, "selected_indices") and self.editor.selected_indices:
            return sorted(i for i in self.editor.selected_indices if 0 <= i < len(self.editor.notes))
        if getattr(self.editor, "selected_index", None) is not None:
            i = int(self.editor.selected_index)
            if 0 <= i < len(self.editor.notes):
                return [i]
        return []

    def copy_selected_notes(self) -> None:
        indices = self.selected_note_indices()
        if not indices:
            self.statusBar().showMessage("No selected notes to copy")
            return

        selected = [self.editor.notes[i].normalized() for i in indices]
        min_start = min(n.start for n in selected)
        self.note_clipboard = [
            Note(n.start - min_start, n.end - min_start, n.midi, n.velocity)
            for n in selected
        ]
        count = len(self.note_clipboard)
        self.statusBar().showMessage(f"Copied {count} note{'s' if count != 1 else ''}")

    def cut_selected_notes(self) -> None:
        self.copy_selected_notes()
        if self.note_clipboard:
            count = len(self.note_clipboard)
            self.editor.delete_selected()
            self.sync_notes_to_player()
            self.statusBar().showMessage(f"Cut {count} note{'s' if count != 1 else ''}")

    def paste_notes(self) -> None:
        if not self.note_clipboard:
            self.statusBar().showMessage("Clipboard is empty")
            return

        base = self.editor.playhead_time()
        self.editor.push_undo()
        new_indices = []
        for n in self.note_clipboard:
            pasted = Note(base + n.start, base + n.end, n.midi, n.velocity).normalized()
            self.editor.notes.append(pasted)
            new_indices.append(len(self.editor.notes) - 1)

        if hasattr(self.editor, "set_selection_indices"):
            self.editor.set_selection_indices(new_indices)
        else:
            self.editor.selected_index = new_indices[0] if new_indices else None
            self.editor.redraw_notes()

        self.editor.notes_changed.emit()
        self.sync_notes_to_player()
        self.statusBar().showMessage(f"Pasted {len(new_indices)} note{'s' if len(new_indices) != 1 else ''} at {self.format_time(base)}")

    def apply_timing_helpers(self) -> None:
        offset_sec = float(self.grid_offset_ms.value()) / 1000.0
        bpm = float(self.grid_bpm.value())

        self.editor.set_beat_grid(
            enabled=self.grid_enabled.isChecked(),
            bpm=bpm,
            offset_sec=offset_sec,
        )
        self.player.set_metronome(
            enabled=self.metro_enabled.isChecked(),
            bpm=bpm,
            offset_sec=offset_sec,
            volume=float(self.metro_vol.value()) / 100.0,
        )
        if hasattr(self.editor, "set_snap_grid"):
            self.editor.set_snap_grid(
                enabled=self.snap_enabled.isChecked() if hasattr(self, "snap_enabled") else False,
                bpm=bpm,
                offset_sec=offset_sec,
                division=int(self.snap_div.value()) if hasattr(self, "snap_div") else 1,
            )

    def apply_visual(self) -> None:
        self.editor.set_visual_options(
            contrast=self.contrast.value() / 100.0,
            gamma=self.gamma.value() / 100.0,
            enhance=self.enhance.isChecked(),
            cmap=self.cmap.currentText(),
            harmonic_mode=self.harmonics.currentText() if hasattr(self, "harmonics") else "off",
            display_mode=self.display_mode.currentText() if hasattr(self, "display_mode") else "smooth",
        )

    def open_audio(self) -> None:
        if not self.confirm_discard_unsaved("Open new audio"):
            return

        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Audio",
            "",
            "Audio Files (*.wav *.ogg *.mp3 *.flac *.m4a);;All Files (*)",
        )
        if not path:
            return
        self.load_audio(path, reset_notes=True)

    def analysis_options(self) -> dict:
        profile = self.analysis_profile.currentText() if hasattr(self, "analysis_profile") else "Normal"
        return analysis_profile_options(profile)

    def load_audio(self, path: str, *, reset_notes: bool = True) -> None:
        opts = self.analysis_options()
        profile = self.analysis_profile.currentText() if hasattr(self, "analysis_profile") else "Normal"

        self.statusBar().showMessage(
            f"Analyzing CQT ({profile}, sr={opts['sr']}, hop={opts['hop_length']})..."
        )
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            spec = analyze_cqt(path, use_cache=True, **opts)
            self.current_audio = str(Path(path))
            self.current_project = None
            self.editor.set_spectrogram(spec)

            if reset_notes:
                self._suppress_dirty = True
                try:
                    self.editor.set_notes([])
                finally:
                    self._suppress_dirty = False
                self.note_clipboard.clear()
                self.sync_notes_to_player()

            self._ignore_scroll_signal = True
            self.time_slider.setValue(0)
            self.visible_sec.setValue(min(12.0, max(0.5, spec.duration)))
            self.pitch_bottom.setRange(spec.midi_min, spec.midi_max)
            self.pitch_bottom.setValue(spec.midi_min)
            self.visible_notes.setRange(6, spec.midi_max - spec.midi_min + 1)
            self.visible_notes.setValue(min(60, spec.midi_max - spec.midi_min + 1))
            self._ignore_scroll_signal = False

            self.editor.set_playhead(0.0)
            self.update_time_labels()
            self.update_view_from_controls()
            self.apply_timing_helpers()

            # Perceived-speed improvement:
            # Display the spectrogram first, then decode playback audio after returning to the event loop.
            if self.player.available:
                QtCore.QTimer.singleShot(1, lambda p=str(path): self.load_audio_for_playback(p))

            self.set_dirty(False if reset_notes else self._dirty)
            self.statusBar().showMessage(
                f"Loaded spectrogram: {Path(path).name} / {profile} / playback loading..."
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Load failed", str(e))
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            self._ignore_scroll_signal = False

    def load_audio_for_playback(self, path: str) -> None:
        if not self.player.available:
            return
        if self.current_audio is None or str(Path(path)) != self.current_audio:
            return

        try:
            self.statusBar().showMessage("Loading audio for playback...")
            self.player.load(path)
            if hasattr(self.player, "set_volume"):
                self.player.set_volume(self.volume.value() / 100.0)
            self.sync_notes_to_player()
            self.apply_playback_speed()
            self.apply_timing_helpers()
            self.statusBar().showMessage(f"Playback ready: {Path(path).name} / Space: play-pause")
        except Exception as e:
            self.statusBar().showMessage(f"Playback load failed, editor still usable: {e!r}")

    def slider_to_start(self) -> float:
        spec = self.editor.spectrogram
        if spec is None:
            return 0.0
        window = float(self.visible_sec.value())
        max_start = max(0.0, spec.duration - window)
        return max_start * self.time_slider.value() / 100000.0

    def start_to_slider(self, start: float) -> int:
        spec = self.editor.spectrogram
        if spec is None:
            return 0
        max_start = max(0.0, spec.duration - float(self.visible_sec.value()))
        if max_start <= 1e-9:
            return 0
        return int(round(max(0.0, min(1.0, start / max_start)) * 100000))

    def on_time_slider(self, value: int) -> None:
        if self._ignore_scroll_signal:
            return
        self.update_view_from_controls()

    def update_view_from_controls(self) -> None:
        if self._ignore_scroll_signal:
            return
        spec = self.editor.spectrogram
        if spec is None:
            return
        self.editor.set_view(
            self.slider_to_start(),
            float(self.visible_sec.value()),
            int(self.pitch_bottom.value()),
            int(self.visible_notes.value()),
        )

    def move_pitch(self, delta: int) -> None:
        spec = self.editor.spectrogram
        if spec is None:
            return

        visible = int(self.visible_notes.value())
        lo = int(spec.midi_min)
        hi = int(spec.midi_max - visible + 1)
        if hi < lo:
            hi = lo

        new_value = max(lo, min(hi, int(self.pitch_bottom.value()) + int(delta)))

        self._ignore_scroll_signal = True
        self.pitch_bottom.setValue(new_value)
        self._ignore_scroll_signal = False
        self.update_view_from_controls()

        direction = "up" if delta > 0 else "down"
        self.statusBar().showMessage(f"Pitch moved {direction}: bottom MIDI {new_value}")

    def fit_all(self) -> None:
        spec = self.editor.spectrogram
        if spec is None:
            return
        self._ignore_scroll_signal = True
        self.time_slider.setValue(0)
        self.visible_sec.setValue(spec.duration)
        self.pitch_bottom.setValue(spec.midi_min)
        self.visible_notes.setValue(spec.midi_max - spec.midi_min + 1)
        self._ignore_scroll_signal = False
        self.update_view_from_controls()

    def ensure_playhead_visible(self, t: float) -> None:
        spec = self.editor.spectrogram
        if spec is None:
            return
        start = self.slider_to_start()
        window = float(self.visible_sec.value())
        if t < start or t > start + window:
            new_start = max(0.0, min(t - window * 0.25, max(0.0, spec.duration - window)))
            self._ignore_scroll_signal = True
            self.time_slider.setValue(self.start_to_slider(new_start))
            self._ignore_scroll_signal = False
            self.update_view_from_controls()

    def on_plot_wheel(self, delta: int, mods_value: int) -> None:
        spec = self.editor.spectrogram
        if spec is None or delta == 0:
            return

        sign = 1 if delta > 0 else -1
        shift = bool(mods_value & int(QtCore.Qt.KeyboardModifier.ShiftModifier.value))
        ctrl = bool(mods_value & int(QtCore.Qt.KeyboardModifier.ControlModifier.value))
        alt = bool(mods_value & int(QtCore.Qt.KeyboardModifier.AltModifier.value))

        # Shift + wheel: vertical scroll
        if shift:
            self.move_pitch(+sign * 3)
            return

        # Alt + wheel: vertical zoom
        if alt:
            v = int(self.visible_notes.value())
            # wheel up -> zoom in -> fewer visible notes
            nv = v - sign * 4
            nv = max(self.visible_notes.minimum(), min(self.visible_notes.maximum(), nv))
            self.visible_notes.setValue(nv)
            self.update_view_from_controls()
            self.statusBar().showMessage(f"Visible notes: {nv}")
            return

        # Ctrl + wheel: horizontal zoom
        if ctrl:
            v = float(self.visible_sec.value())
            # wheel up -> zoom in -> shorter window
            nv = v * (0.85 if sign > 0 else 1.18)
            nv = max(self.visible_sec.minimum(), min(self.visible_sec.maximum(), nv))
            self.visible_sec.setValue(nv)
            self.update_view_from_controls()
            self.statusBar().showMessage(f"Visible seconds: {nv:.2f}")
            return

        # normal wheel: horizontal scroll
        step = 2500 * (-sign)
        self.time_slider.setValue(max(self.time_slider.minimum(), min(self.time_slider.maximum(), self.time_slider.value() + step)))

    def toggle_playback(self) -> None:
        if not self.current_audio and self.editor.spectrogram is None:
            self.statusBar().showMessage("Open an audio file first")
            return
        if not self.player.available:
            self.statusBar().showMessage(f"Playback unavailable: {self.player.error}")
            return
        if getattr(self.player, "audio", None) is None:
            if self.current_audio:
                self.statusBar().showMessage("Playback audio is still loading. Try again in a moment.")
                QtCore.QTimer.singleShot(1, lambda p=self.current_audio: self.load_audio_for_playback(p))
            else:
                self.statusBar().showMessage("Open an audio file first")
            return

        if not self.player.playing:
            self.sync_notes_to_player()
            self.apply_playback_speed()
            self.player.seek(self.editor.playhead_time())
        self.player.toggle()
        self.statusBar().showMessage("Playing" if self.player.playing else f"Paused at {self.editor.playhead_time():.3f}s")

    def stop_playback(self) -> None:
        self.player.stop()
        self.editor.set_playhead(0.0)
        self.update_time_labels()
        self.statusBar().showMessage("Stopped")

    def seek_relative(self, seconds: float) -> None:
        self.seek_to(self.editor.playhead_time() + seconds)

    def seek_to(self, seconds: float) -> None:
        spec = self.editor.spectrogram
        if spec is not None:
            seconds = max(0.0, min(seconds, spec.duration))
        else:
            seconds = max(0.0, seconds)
        self.player.seek(seconds)
        self.editor.set_playhead(seconds)
        self.update_time_labels()
        self.ensure_playhead_visible(seconds)

    def update_playhead_from_player(self) -> None:
        if self.player.playing:
            t = self.player.time
            self.editor.set_playhead(t)
            self.update_time_labels()
            self.ensure_playhead_visible(t)

    def on_playhead_dragged(self, seconds: float) -> None:
        self.seek_to(seconds)
        self.update_time_labels()

    def get_project_settings(self) -> dict:
        return {
            "grid_bpm": float(self.grid_bpm.value()) if hasattr(self, "grid_bpm") else 175.0,
            "grid_offset_ms": float(self.grid_offset_ms.value()) if hasattr(self, "grid_offset_ms") else 0.0,
            "grid_enabled": bool(self.grid_enabled.isChecked()) if hasattr(self, "grid_enabled") else False,
            "metronome_enabled": bool(self.metro_enabled.isChecked()) if hasattr(self, "metro_enabled") else False,
            "metronome_volume": int(self.metro_vol.value()) if hasattr(self, "metro_vol") else 35,
            "snap_enabled": bool(self.snap_enabled.isChecked()) if hasattr(self, "snap_enabled") else False,
            "snap_div": int(self.snap_div.value()) if hasattr(self, "snap_div") else 1,
            "note_octave": int(self.note_octave.value()) if hasattr(self, "note_octave") else 0,
            "note_volume": int(self.note_vol.value()) if hasattr(self, "note_vol") else 20,
            "note_sound_enabled": bool(self.note_sound_enabled.isChecked()) if hasattr(self, "note_sound_enabled") else True,
            "song_volume": int(self.volume.value()) if hasattr(self, "volume") else 85,
            "playback_speed": float(self.playback_speed.value()) if hasattr(self, "playback_speed") else 1.0,
            "analysis_profile": self.analysis_profile.currentText() if hasattr(self, "analysis_profile") else "Normal",
            "display_mode": self.display_mode.currentText() if hasattr(self, "display_mode") else "wavetone",
            "cmap": self.cmap.currentText() if hasattr(self, "cmap") else "wavetone",
        }

    def apply_project_settings(self, settings: dict) -> None:
        if not settings:
            return

        blockers = []
        for name in (
            "grid_bpm", "grid_offset_ms", "grid_enabled", "metro_enabled", "metro_vol",
            "snap_enabled", "snap_div", "note_octave", "note_vol", "note_sound_enabled",
            "volume", "playback_speed", "analysis_profile", "display_mode", "cmap",
        ):
            widget = getattr(self, name, None)
            if widget is not None and hasattr(widget, "blockSignals"):
                blockers.append(widget)
                widget.blockSignals(True)

        try:
            if hasattr(self, "grid_bpm") and "grid_bpm" in settings:
                self.grid_bpm.setValue(float(settings["grid_bpm"]))
            if hasattr(self, "grid_offset_ms") and "grid_offset_ms" in settings:
                self.grid_offset_ms.setValue(float(settings["grid_offset_ms"]))
            if hasattr(self, "grid_enabled") and "grid_enabled" in settings:
                self.grid_enabled.setChecked(bool(settings["grid_enabled"]))
            if hasattr(self, "metro_enabled") and "metronome_enabled" in settings:
                self.metro_enabled.setChecked(bool(settings["metronome_enabled"]))
            if hasattr(self, "metro_vol") and "metronome_volume" in settings:
                self.metro_vol.setValue(int(settings["metronome_volume"]))
            if hasattr(self, "snap_enabled") and "snap_enabled" in settings:
                self.snap_enabled.setChecked(bool(settings["snap_enabled"]))
            if hasattr(self, "snap_div") and "snap_div" in settings:
                self.snap_div.setValue(int(settings["snap_div"]))
            if hasattr(self, "note_octave") and "note_octave" in settings:
                self.note_octave.setValue(int(settings["note_octave"]))
            if hasattr(self, "note_vol") and "note_volume" in settings:
                self.note_vol.setValue(int(settings["note_volume"]))
            if hasattr(self, "note_sound_enabled") and "note_sound_enabled" in settings:
                self.note_sound_enabled.setChecked(bool(settings["note_sound_enabled"]))
            if hasattr(self, "volume") and "song_volume" in settings:
                self.volume.setValue(int(settings["song_volume"]))
            if hasattr(self, "playback_speed") and "playback_speed" in settings:
                self.playback_speed.setValue(float(settings["playback_speed"]))
            if hasattr(self, "analysis_profile") and "analysis_profile" in settings:
                idx = self.analysis_profile.findText(str(settings["analysis_profile"]))
                if idx >= 0:
                    self.analysis_profile.setCurrentIndex(idx)
            if hasattr(self, "display_mode") and "display_mode" in settings:
                idx = self.display_mode.findText(str(settings["display_mode"]))
                if idx >= 0:
                    self.display_mode.setCurrentIndex(idx)
            if hasattr(self, "cmap") and "cmap" in settings:
                idx = self.cmap.findText(str(settings["cmap"]))
                if idx >= 0:
                    self.cmap.setCurrentIndex(idx)
        finally:
            for widget in blockers:
                widget.blockSignals(False)

        self.apply_timing_helpers()
        self.apply_note_sound_settings()
        self.apply_playback_speed()
        if hasattr(self.player, "set_volume") and hasattr(self, "volume"):
            self.player.set_volume(self.volume.value() / 100.0)
        self.statusBar().showMessage("Project settings applied")

    def save_project_as(self) -> bool:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Project",
            str(self.current_project) if self.current_project else "",
            "AdopyHzEditor Project (*.adopyhz);;Old Project (*.ahe.json *.json);;All Files (*)",
        )
        if not path:
            return False
        if Path(path).suffix == "":
            path += ".adopyhz"
        try:
            save_project(path, audio_path=self.current_audio, notes=self.editor.notes, settings=self.get_project_settings())
            self.current_project = Path(path)
            self.set_dirty(False)
            self.statusBar().showMessage(f"Saved: {Path(path).name}")
            return True
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save failed", str(e))
            return False

    def load_project_from_file(self) -> None:
        if not self.confirm_discard_unsaved("Load project"):
            return

        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load Project",
            "",
            "AdopyHzEditor Project (*.adopyhz);;Old Project (*.ahe.json *.json);;JSON (*.json);;All Files (*)",
        )
        if not path:
            return
        try:
            audio, notes, settings = load_project(path)
            self._suppress_dirty = True
            try:
                if audio and Path(audio).exists():
                    self.load_audio(audio, reset_notes=False)
                self.editor.set_notes(notes)
                self.apply_project_settings(settings)
            finally:
                self._suppress_dirty = False

            self.current_project = Path(path)
            self.set_dirty(False)
            self.sync_notes_to_player()
            self.statusBar().showMessage(f"Loaded project: {Path(path).name}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Load failed", str(e))

    def current_octave_shift(self) -> int:
        return int(self.note_octave.value()) if hasattr(self, "note_octave") else 0

    def notes_with_output_octave(self) -> list[Note]:
        """
        Apply Oct to preview/export pitch without moving notes on screen.
        This is used by both MIDI and ADOFAI export.
        """
        shift = self.current_octave_shift() * 12
        result: list[Note] = []
        for n in self.editor.notes:
            nn = n.normalized()
            midi = max(0, min(127, int(nn.midi) + shift))
            result.append(Note(nn.start, nn.end, midi, nn.velocity))
        return result

    def export_midi_file(self) -> None:
        if not self.editor.notes:
            QtWidgets.QMessageBox.information(self, "No notes", "There are no notes to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export MIDI", "", "MIDI File (*.mid);;All Files (*)")
        if not path:
            return
        if not path.lower().endswith((".mid", ".midi")):
            path += ".mid"
        try:
            export_midi(self.notes_with_output_octave(), path)
            self.statusBar().showMessage(f"Exported MIDI: {Path(path).name} / Oct {self.current_octave_shift():+d}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "MIDI export failed", str(e))

    def export_adofai_file(self) -> None:
        if not self.editor.notes:
            QtWidgets.QMessageBox.information(self, "No notes", "There are no notes to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export ADOFAI Hz", "", "ADOFAI Level (*.adofai);;All Files (*)")
        if not path:
            return
        if not path.lower().endswith(".adofai"):
            path += ".adofai"

        dialog = ExportAdoFAIDialog(self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        try:
            stats = export_adofai(self.notes_with_output_octave(), path, **dialog.options())
            QtWidgets.QMessageBox.information(self, "Export complete", "\n".join(f"{k}: {v}" for k, v in stats.items()))
            self.statusBar().showMessage(f"Exported ADOFAI: {Path(path).name} / Oct {self.current_octave_shift():+d}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "ADOFAI export failed", str(e))


class ExportAdoFAIDialog(QtWidgets.QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ADOFAI Hz Export Options")
        layout = QtWidgets.QFormLayout(self)

        self.method = QtWidgets.QComboBox()
        self.method.addItems(["Angle Compression: corrected Keycount formula", "Direct 180°: BPM = Hz × 60"])

        self.base_bpm = QtWidgets.QDoubleSpinBox()
        self.base_bpm.setRange(1.0, 999999.0)
        self.base_bpm.setDecimals(6)
        default_bpm = 175.0
        if parent is not None and hasattr(parent, "grid_bpm"):
            default_bpm = float(parent.grid_bpm.value())
        self.base_bpm.setValue(default_bpm)

        self.x_mode = QtWidgets.QComboBox()
        self.x_mode.addItems(["floor", "lowest_floor", "round", "ceil", "fixed"])
        self.x_mode.setToolTip(
            "変更用xの選び方\n"
            "floor = 各ノートの floor(Keycount)\n"
            "lowest_floor = 全ノート中の一番低い floor(Keycount) に固定\n"
            "fixed = 下の Fixed change x を使う"
        )

        self.fixed_x = QtWidgets.QDoubleSpinBox()
        self.fixed_x.setRange(0.000001, 100000.0)
        self.fixed_x.setDecimals(6)
        self.fixed_x.setValue(8.0)
        self.fixed_x.setToolTip("Change x mode が fixed のときに使う変更用x。lowest_floorでは無視されます。")



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

        layout.addRow("Method", self.method)
        layout.addRow("Base BPM", self.base_bpm)
        layout.addRow("Change x mode", self.x_mode)
        layout.addRow("Fixed change x", self.fixed_x)
        layout.addRow("Max total tiles", self.max_tiles)
        layout.addRow("Max tiles per note", self.max_tiles_per_note)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def options(self) -> dict:
        return {
            "method": "direct_180" if self.method.currentIndex() == 1 else "rabbit_zip",
            "base_bpm": float(self.base_bpm.value()),
            "rabbit_x_mode": self.x_mode.currentText(),
            "rabbit_fixed_x": float(self.fixed_x.value()),
            "max_tiles": int(self.max_tiles.value()),
            "max_tiles_per_note": int(self.max_tiles_per_note.value()),
            "pretty": False,
        }


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
