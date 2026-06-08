from __future__ import annotations

import sys
from pathlib import Path
import csv
import io
import numpy as np
import webbrowser
import shutil
import math
from fractions import Fraction

from PySide6 import QtCore, QtGui, QtWidgets

from audio_analysis import analyze_cqt, analysis_profile_options, has_analysis_cache, Spectrogram
from audio_player import AudioPlayer, decode_audio_file
from editor_view import EditorView
from export_midi import export_midi
from export_adofai import export_adofai, build_adofai_debug_rows, build_adofai_level, build_tile_preview_points
from project_io import save_project, load_project
from help_dialog import HelpDialog
from tile_preview_dialog import TilePreviewDialog
from note_model import Note
from i18n import tr, current_language, set_language
from app_info import APP_VERSION, GITHUB_RELEASES_URL


class AnalysisWorker(QtCore.QObject):
    finished = QtCore.Signal(object, str, str, bool, str, bool, int)
    failed = QtCore.Signal(str, str, str, bool, str, bool, int)

    def __init__(
        self,
        path: str,
        opts: dict,
        signature: str,
        reset_notes: bool,
        profile: str,
        clear_project: bool,
        request_id: int,
    ) -> None:
        super().__init__()
        self.path = path
        self.opts = dict(opts)
        self.signature = signature
        self.reset_notes = bool(reset_notes)
        self.profile = profile
        self.clear_project = bool(clear_project)
        self.request_id = int(request_id)

    @QtCore.Slot()
    def run(self) -> None:
        try:
            spec = analyze_cqt(self.path, use_cache=True, **self.opts)
            self.finished.emit(
                spec,
                self.path,
                self.signature,
                self.reset_notes,
                self.profile,
                self.clear_project,
                self.request_id,
            )
        except Exception as e:
            self.failed.emit(
                str(e),
                self.path,
                self.signature,
                self.reset_notes,
                self.profile,
                self.clear_project,
                self.request_id,
            )



class PlaybackLoadWorker(QtCore.QObject):
    finished = QtCore.Signal(object, int, str, int)
    failed = QtCore.Signal(str, str, int)

    def __init__(self, path: str, request_id: int) -> None:
        super().__init__()
        self.path = path
        self.request_id = int(request_id)

    @QtCore.Slot()
    def run(self) -> None:
        try:
            audio, sr = decode_audio_file(self.path, sr=44100)
            self.finished.emit(audio, int(sr), self.path, self.request_id)
        except Exception as e:
            self.failed.emit(repr(e), self.path, self.request_id)



class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle(tr("app.title"))
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
        self._current_analysis_signature: str | None = None
        self._analysis_thread: QtCore.QThread | None = None
        self._analysis_worker: AnalysisWorker | None = None
        self._analysis_request_id = 0
        self._analysis_cursor_active = False
        self._playback_thread: QtCore.QThread | None = None
        self._playback_worker: PlaybackLoadWorker | None = None
        self._playback_request_id = 0
        self._ignore_scroll_signal = False
        self._suppress_dirty = False
        self._dirty = False
        self.note_clipboard: list[Note] = []

        # ADOFAI export workflow defaults. These are saved into project settings.
        self.adofai_use_project_song = True
        self.adofai_copy_project_song = True
        self.adofai_song_offset_auto = True
        self.adofai_song_offset_ms = 0.0

        # Editable blank workspace defaults used when no audio is loaded.
        self.blank_workspace_duration = 60.0
        self.blank_workspace_midi_min = 12
        self.blank_workspace_midi_max = 120

        self._make_menus()
        self._make_toolbar()
        self._make_bottom_controls()
        self._make_shortcuts()
        self.apply_curve_shape()
        self.apply_curve_interpolation()
        self._connect_dirty_signals()
        self.update_window_title()

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.update_playhead_from_player)
        self.timer.start()

        if not self.player.available:
            self.statusBar().showMessage(f"Playback disabled: {self.player.error}")
        else:
            self.statusBar().showMessage(tr("status.open_audio"))

    def update_window_title(self) -> None:
        mark = "*" if self._dirty else ""
        project = f" - {self.current_project.name}" if self.current_project else ""
        self.setWindowTitle(f"{tr('app.title')}{mark}{project}")

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
            getattr(self, "export_octave", None),
            getattr(self, "export_semitone", None),
            getattr(self, "note_vol", None),
            getattr(self, "note_sound_enabled", None),
            getattr(self, "volume", None),
            getattr(self, "playback_speed", None),
            getattr(self, "analysis_profile", None),
            getattr(self, "cqt_resolution", None),
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

    def confirm_discard_unsaved(self, title: str | None = None) -> bool:
        if not self._dirty:
            return True

        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        box.setWindowTitle(title or tr("dialog.unsaved.title"))
        box.setText(tr("dialog.unsaved.text"))
        box.setInformativeText(tr("dialog.unsaved.info"))
        save_btn = box.addButton(tr("dialog.unsaved.save"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        discard_btn = box.addButton(tr("dialog.unsaved.discard"), QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton(tr("dialog.unsaved.cancel"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
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
        if self._analysis_thread is not None and self._analysis_thread.isRunning():
            box = QtWidgets.QMessageBox(self)
            box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            box.setWindowTitle(tr("dialog.analysis_running.title"))
            box.setText(tr("dialog.analysis_running.text"))
            box.setInformativeText(tr("dialog.analysis_running.info"))
            quit_btn = box.addButton(tr("dialog.analysis_running.quit"), QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
            cancel_btn = box.addButton(tr("dialog.unsaved.cancel"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(cancel_btn)
            box.exec()
            if box.clickedButton() != quit_btn:
                event.ignore()
                return
            self._analysis_request_id += 1

        self._playback_request_id += 1

        if self.confirm_discard_unsaved("Close AdopyHzEditor"):
            event.accept()
        else:
            event.ignore()

    def _make_menus(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu(tr("menu.file"))
        file_menu.addAction(tr("menu.open_audio"), self.open_audio, QtGui.QKeySequence("Ctrl+O"))
        file_menu.addAction(tr("menu.blank_workspace"), self.configure_blank_workspace)
        file_menu.addAction(tr("menu.save_project"), self.save_project_as, QtGui.QKeySequence("Ctrl+S"))
        file_menu.addAction(tr("menu.load_project"), self.load_project_from_file, QtGui.QKeySequence("Ctrl+L"))
        file_menu.addAction(tr("menu.load_project_notes_only"), self.load_project_notes_only)
        file_menu.addSeparator()
        file_menu.addAction(tr("menu.export_midi"), self.export_midi_file, QtGui.QKeySequence("Ctrl+M"))
        file_menu.addAction(tr("menu.export_adofai"), self.export_adofai_file, QtGui.QKeySequence("Ctrl+E"))

        edit_menu = menubar.addMenu(tr("menu.edit"))
        edit_menu.addAction(tr("menu.undo"), self.editor.undo)
        edit_menu.addAction(tr("menu.redo"), self.editor.redo)
        edit_menu.addSeparator()
        edit_menu.addAction(tr("menu.copy"), self.copy_selected_notes)
        edit_menu.addAction(tr("menu.cut"), self.cut_selected_notes)
        edit_menu.addAction(tr("menu.paste"), self.paste_notes)
        edit_menu.addSeparator()
        edit_menu.addAction(tr("menu.insert_harmonic_diagram"), self.insert_harmonic_diagram)
        edit_menu.addSeparator()
        edit_menu.addAction(tr("menu.select_all"), self.editor.select_all_notes, QtGui.QKeySequence("Ctrl+A"))
        edit_menu.addAction(tr("menu.clear_selection"), self.editor.clear_selection, QtGui.QKeySequence("Esc"))
        edit_menu.addAction(tr("menu.delete_selected"), self.editor.delete_selected, QtGui.QKeySequence("Delete"))

        play_menu = menubar.addMenu(tr("menu.play"))
        play_menu.addAction(tr("menu.play_pause"), self.toggle_playback)
        play_menu.addAction(tr("menu.stop"), self.stop_playback, QtGui.QKeySequence("Ctrl+Space"))
        play_menu.addAction(tr("menu.seek_back_1"), lambda: self.seek_relative(-1.0), QtGui.QKeySequence("Left"))
        play_menu.addAction(tr("menu.seek_forward_1"), lambda: self.seek_relative(1.0), QtGui.QKeySequence("Right"))

        analyze_menu = menubar.addMenu(tr("menu.analyze"))
        analyze_menu.addAction(tr("menu.redraw_spectrogram"), self.apply_visual)
        analyze_menu.addAction(tr("menu.reanalyze_audio"), self.reanalyze_current_audio)

        view_menu = menubar.addMenu(tr("menu.view"))
        self.view_menu = view_menu
        view_menu.addAction(tr("menu.view_spectrogram"), lambda: self.editor.set_mode(0), QtGui.QKeySequence("1"))
        view_menu.addAction(tr("menu.view_notes"), lambda: self.editor.set_mode(1), QtGui.QKeySequence("2"))
        view_menu.addAction(tr("menu.view_both"), lambda: self.editor.set_mode(2), QtGui.QKeySequence("3"))
        view_menu.addAction(tr("menu.fit_all"), self.fit_all)

        options_menu = menubar.addMenu(tr("menu.options"))
        language_menu = options_menu.addMenu(tr("menu.language"))
        en_action = language_menu.addAction(tr("menu.language_en"))
        ja_action = language_menu.addAction(tr("menu.language_ja"))
        en_action.setCheckable(True)
        ja_action.setCheckable(True)
        lang_group = QtGui.QActionGroup(self)
        lang_group.setExclusive(True)
        lang_group.addAction(en_action)
        lang_group.addAction(ja_action)
        en_action.setChecked(current_language() == "en")
        ja_action.setChecked(current_language() == "ja")
        en_action.triggered.connect(lambda: self.change_language("en"))
        ja_action.triggered.connect(lambda: self.change_language("ja"))
        options_menu.addSeparator()
        options_menu.addAction(tr("menu.check_updates"), lambda: self.check_for_updates(silent=False))

        help_menu = menubar.addMenu(tr("menu.help"))
        help_menu.addAction(tr("help.quick_start.title"), lambda: self.open_help("quick_start"), QtGui.QKeySequence("F1"))
        help_menu.addAction(tr("help.controls.title"), lambda: self.open_help("controls"))
        help_menu.addAction(tr("help.adofai_export.title"), lambda: self.open_help("adofai_export"))
        help_menu.addAction(tr("help.pitch_export.title"), lambda: self.open_help("pitch_export"))
        help_menu.addAction(tr("help.curve_glide.title"), lambda: self.open_help("curve_glide"))
        help_menu.addAction(tr("help.troubleshooting.title"), lambda: self.open_help("troubleshooting"))
        help_menu.addSeparator()
        help_menu.addAction(tr("help.about.title"), lambda: self.open_help("about"))

    def open_help(self, section: str = "quick_start") -> None:
        dlg = HelpDialog(self, initial_section=section)
        dlg.exec()

    def change_language(self, lang: str) -> None:
        set_language(lang)
        QtWidgets.QMessageBox.information(
            self,
            tr("dialog.language.title"),
            tr("dialog.language.restart"),
        )


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

        # Keep the main toolbar focused on file/export/playback/view actions only.
        action("↶", lambda: self.seek_to(0.0), tip=tr("toolbar.first"))
        action("■", self.stop_playback, "Ctrl+Space", tr("toolbar.stop"))
        action("▶", self.toggle_playback, tip=tr("toolbar.play"))
        action("◀", lambda: self.seek_relative(-1.0), tip=tr("toolbar.back"))
        action("▶", lambda: self.seek_relative(1.0), tip=tr("toolbar.forward"))
        tb.addSeparator()

        action("MIDI", self.export_midi_file, "Ctrl+M", tr("dialog.export_midi.title"))
        action("Hz", self.export_adofai_file, "Ctrl+E", tr("dialog.export_adofai.title"))
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


    def _make_bottom_controls(self) -> None:
        # Bottom bar: navigation/viewport only.
        bar = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout(bar)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setHorizontalSpacing(5)
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

        self.pitch_down_button = QtWidgets.QPushButton("Pitch ↓")
        self.pitch_down_button.clicked.connect(lambda: self.move_pitch(-12))
        self.pitch_up_button = QtWidgets.QPushButton("Pitch ↑")
        self.pitch_up_button.clicked.connect(lambda: self.move_pitch(+12))

        layout.addWidget(QtWidgets.QLabel("Time"), 0, 0)
        layout.addWidget(self.time_slider, 0, 1)
        layout.addWidget(QtWidgets.QLabel("Visible"), 0, 2)
        layout.addWidget(self.visible_sec, 0, 3)
        layout.addWidget(QtWidgets.QLabel("Pitch bottom"), 0, 4)
        layout.addWidget(self.pitch_bottom, 0, 5)
        layout.addWidget(self.pitch_down_button, 0, 6)
        layout.addWidget(self.pitch_up_button, 0, 7)
        layout.addWidget(QtWidgets.QLabel("Visible notes"), 0, 8)
        layout.addWidget(self.visible_notes, 0, 9)
        layout.addWidget(self.fit_button, 0, 10)

        bottom_tb = QtWidgets.QToolBar("Navigation")
        bottom_tb.setMovable(False)
        bottom_tb.addWidget(bar)
        self.addToolBar(QtCore.Qt.ToolBarArea.BottomToolBarArea, bottom_tb)

        # Right side settings panel: all non-essential editing settings.
        self.settings_dock = QtWidgets.QDockWidget("Settings", self)
        self.settings_dock.setObjectName("SettingsDock")
        self.settings_dock.setAllowedAreas(
            QtCore.Qt.DockWidgetArea.LeftDockWidgetArea
            | QtCore.Qt.DockWidgetArea.RightDockWidgetArea
        )

        self.settings_toolbox = QtWidgets.QToolBox()
        self.settings_toolbox.setMinimumWidth(300)
        self.settings_dock.setWidget(self.settings_toolbox)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.settings_dock)

        if hasattr(self, "view_menu"):
            self.view_menu.addSeparator()
            self.settings_dock_toggle_action = self.settings_dock.toggleViewAction()
            self.settings_dock_toggle_action.setText("Settings Panel")
            self.view_menu.addAction(self.settings_dock_toggle_action)

        def make_page() -> tuple[QtWidgets.QWidget, QtWidgets.QFormLayout]:
            page = QtWidgets.QWidget()
            form = QtWidgets.QFormLayout(page)
            form.setContentsMargins(8, 8, 8, 8)
            form.setHorizontalSpacing(8)
            form.setVerticalSpacing(6)
            form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            return page, form

        def hbox(*widgets: QtWidgets.QWidget) -> QtWidgets.QWidget:
            box = QtWidgets.QWidget()
            row = QtWidgets.QHBoxLayout(box)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(5)
            for w in widgets:
                row.addWidget(w)
            row.addStretch(1)
            return box

        # Playback page
        playback_page, playback_form = make_page()

        self.volume = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(85)
        self.volume.valueChanged.connect(lambda v: self.player.set_volume(v / 100.0))

        self.playback_speed = QtWidgets.QDoubleSpinBox()
        self.playback_speed.setRange(0.10, 4.00)
        self.playback_speed.setDecimals(2)
        self.playback_speed.setSingleStep(0.05)
        self.playback_speed.setValue(1.00)
        self.playback_speed.setSuffix("x")
        self.playback_speed.valueChanged.connect(self.apply_playback_speed)

        self.note_sound_enabled = QtWidgets.QCheckBox("Enable note preview")
        self.note_sound_enabled.setChecked(True)
        self.note_sound_enabled.setToolTip("追加したノート音を再生")
        self.note_sound_enabled.stateChanged.connect(self.apply_note_sound_settings)

        self.note_vol = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.note_vol.setRange(0, 100)
        self.note_vol.setValue(20)
        self.note_vol.valueChanged.connect(self.apply_note_sound_settings)

        self.note_octave = QtWidgets.QSpinBox()
        self.note_octave.setRange(-4, 4)
        self.note_octave.setValue(0)
        self.note_octave.setToolTip("Preview Oct: ノートプレビュー音だけをオクターブ単位で上下。画面上のノート位置や出力には影響しません。")
        self.note_octave.valueChanged.connect(self.apply_note_sound_settings)

        playback_form.addRow("Song Vol", self.volume)
        playback_form.addRow("Speed", self.playback_speed)
        playback_form.addRow("Note Preview", self.note_sound_enabled)
        playback_form.addRow("Note Vol", self.note_vol)
        playback_form.addRow("Preview Oct", self.note_octave)
        self.settings_toolbox.addItem(playback_page, "Playback")

        # Export pitch page
        export_page, export_form = make_page()

        self.export_octave = QtWidgets.QSpinBox()
        self.export_octave.setRange(-4, 4)
        self.export_octave.setValue(0)
        self.export_octave.setToolTip("Export Oct: MIDI/ADOFAI出力だけをオクターブ単位で上下。プレビュー音と画面上のノート位置には影響しません。")

        self.export_semitone = QtWidgets.QSpinBox()
        self.export_semitone.setRange(-12, 12)
        self.export_semitone.setValue(0)
        self.export_semitone.setToolTip("Export Semi: MIDI/ADOFAI出力だけを半音単位で上下。Export Octと合算されます。")

        export_help = QtWidgets.QLabel(
            "Export pitch = note pitch + Export Oct × 12 + Export Semi"
        )
        export_help.setWordWrap(True)

        export_form.addRow("Export Oct", self.export_octave)
        export_form.addRow("Export Semi", self.export_semitone)
        export_form.addRow("", export_help)
        self.settings_toolbox.addItem(export_page, "Export Pitch")

        # Grid / Snap page
        grid_page, grid_form = make_page()

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
        self.metro_vol.valueChanged.connect(self.apply_timing_helpers)

        self.snap_enabled = QtWidgets.QCheckBox("Snap")
        self.snap_enabled.setChecked(False)
        self.snap_enabled.stateChanged.connect(self.apply_timing_helpers)

        self.snap_div = QtWidgets.QSpinBox()
        self.snap_div.setRange(1, 64)
        self.snap_div.setValue(1)
        self.snap_div.setToolTip("Snap subdivision per beat. 1 = beat, 4 = quarter-beat grid")
        self.snap_div.valueChanged.connect(self.apply_timing_helpers)

        grid_form.addRow("Grid", self.grid_enabled)
        grid_form.addRow("Metronome", self.metro_enabled)
        grid_form.addRow("BPM", self.grid_bpm)
        grid_form.addRow("Offset", self.grid_offset_ms)
        grid_form.addRow("Metro Vol", self.metro_vol)
        grid_form.addRow("Snap", self.snap_enabled)
        grid_form.addRow("Snap div", self.snap_div)
        self.settings_toolbox.addItem(grid_page, "Grid / Snap")

        # View / Analysis page
        view_page, view_form = make_page()

        self.contrast = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.contrast.setRange(0, 300)
        self.contrast.setValue(115)
        self.contrast.valueChanged.connect(self.apply_visual)

        self.gamma = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.gamma.setRange(5, 500)
        self.gamma.setValue(75)
        self.gamma.valueChanged.connect(self.apply_visual)

        self.enhance = QtWidgets.QCheckBox("Enhance")
        self.enhance.setChecked(True)
        self.enhance.stateChanged.connect(self.apply_visual)

        self.display_mode = QtWidgets.QComboBox()
        self.display_mode.addItems(["wavetone", "ridge", "smooth"])
        self.display_mode.setCurrentText("wavetone")
        self.display_mode.setToolTip(
            "wavetone: 見やすいブロック表示\n"
            "ridge: ピッチの山だけを残す\n"
            "smooth: 従来のなめらかなスペクトログラム"
        )
        self.display_mode.currentTextChanged.connect(self.apply_visual)

        self.harmonics = QtWidgets.QComboBox()
        self.harmonics.addItems(["off", "soft", "strong"])
        self.harmonics.currentTextChanged.connect(self.apply_visual)

        self.cmap = QtWidgets.QComboBox()
        self.cmap.addItems(["wavetone", "viridis", "magma", "inferno", "plasma", "gray"])
        self.cmap.setCurrentText("wavetone")
        self.cmap.currentTextChanged.connect(self.apply_visual)

        self.analysis_profile = QtWidgets.QComboBox()
        self.analysis_profile.addItems(["Fast", "Normal", "Precise", "Full C0-C10"])
        self.analysis_profile.setCurrentText("Normal")
        self.analysis_profile.setToolTip(
            "Fast: C1-C7 / rougher time resolution\n"
            "Normal: balanced\n"
            "Precise: 3 bins/semitone, better note visibility, slower\n"
            "Full C0-C10: widest range, slower"
        )

        self.cqt_resolution = QtWidgets.QComboBox()
        self.cqt_resolution.addItems([
            "profile default",
            "100 cents",
            "50 cents",
            "25 cents",
            "12.5 cents",
            "41 EDO",
            "53 EDO",
        ])
        self.cqt_resolution.setCurrentText("profile default")
        self.cqt_resolution.setToolTip(
            "Microtonal CQT display resolution.\n"
            "profile default keeps the old behavior.\n"
            "50/25/12.5 cents keeps sub-semitone CQT bins visible instead of folding them into semitone rows."
        )

        view_form.addRow("Contrast", self.contrast)
        view_form.addRow("Gamma", self.gamma)
        view_form.addRow("Enhance", self.enhance)
        view_form.addRow("Display", self.display_mode)
        view_form.addRow("Harmonics", self.harmonics)
        view_form.addRow("Colormap", self.cmap)
        view_form.addRow("Analysis", self.analysis_profile)
        view_form.addRow("CQT Resolution", self.cqt_resolution)
        self.settings_toolbox.addItem(view_page, "View / Analysis")

        # Curve / Angle page
        curve_page, curve_form = make_page()

        self.curve_shape = QtWidgets.QComboBox()
        self.curve_shape.addItems(["ease", "s_curve", "linear", "ease_in", "ease_out"])
        self.curve_shape.setCurrentText("ease")
        self.curve_shape.setToolTip(
            "Alt+ドラッグで作るBezier/Glideノートの初期カーブ\n"
            "ease: 標準の曲線\n"
            "s_curve: 強めのS字\n"
            "linear: 直線\n"
            "ease_in/ease_out: 片側に寄った曲線"
        )
        self.curve_shape.currentTextChanged.connect(self.apply_curve_shape)

        self.curve_interpolation = QtWidgets.QComboBox()
        self.curve_interpolation.addItems(["bezier_pitch", "linear_pitch", "linear_hz", "bezier_hz"])
        self.curve_interpolation.setCurrentText("bezier_pitch")
        self.curve_interpolation.setToolTip(
            "Glide/Bezierノートの補間方式\n"
            "bezier_pitch: MIDI/semitone上でBezier。従来方式\n"
            "linear_pitch: MIDI/semitone上で直線。周波数比が一定\n"
            "linear_hz: Hz上で直線。物理周波数が一定速度で変化\n"
            "bezier_hz: Hz上でBezier"
        )
        self.curve_interpolation.currentTextChanged.connect(self.apply_curve_interpolation)

        self.apply_interpolation_button = QtWidgets.QPushButton("Apply Interp")
        self.apply_interpolation_button.setToolTip("選択中のCurve/Glideノートに補間方式を適用")
        self.apply_interpolation_button.clicked.connect(self.apply_interpolation_to_selected)

        self.target_angle = QtWidgets.QDoubleSpinBox()
        self.target_angle.setRange(0.001, 359.999)
        self.target_angle.setDecimals(6)
        self.target_angle.setValue(165.0)
        self.target_angle.setSuffix("°")
        self.target_angle.setToolTip("選択中ノート/zipのAngle Compression角度を上書きします")

        self.apply_target_angle_button = QtWidgets.QPushButton("Apply Angle")
        self.apply_target_angle_button.setToolTip("選択中ノートへTarget Angleを設定")
        self.apply_target_angle_button.clicked.connect(self.apply_target_angle_to_selected)

        self.clear_target_angle_button = QtWidgets.QPushButton("Clear Angle")
        self.clear_target_angle_button.setToolTip("選択中ノートのTarget Angleを解除して自動計算に戻す")
        self.clear_target_angle_button.clicked.connect(self.clear_target_angle_for_selected)

        curve_form.addRow("Curve", self.curve_shape)
        curve_form.addRow("Interp", self.curve_interpolation)
        curve_form.addRow("", self.apply_interpolation_button)
        curve_form.addRow("Target Angle", self.target_angle)
        curve_form.addRow("", hbox(self.apply_target_angle_button, self.clear_target_angle_button))
        self.settings_toolbox.addItem(curve_page, "Curve / Angle")


    def _make_shortcuts(self) -> None:
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self, activated=self.editor.undo)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Y"), self, activated=self.editor.redo)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+Z"), self, activated=self.editor.redo)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+C"), self, activated=self.copy_selected_notes)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+X"), self, activated=self.cut_selected_notes)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+V"), self, activated=self.paste_notes)
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
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Alt+A"), self, activated=self.apply_target_angle_to_selected)
        QtGui.QShortcut(QtGui.QKeySequence("F1"), self, activated=lambda: self.open_help("quick_start"))

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
                octave_shift=self.current_preview_octave_shift(),
            )

    def sync_notes_to_player(self) -> None:
        if hasattr(self.player, "set_preview_notes"):
            self.player.set_preview_notes(self.editor.notes)

        if hasattr(self.player, "set_virtual_duration"):
            spec = self.editor.spectrogram
            duration = float(spec.duration) if spec is not None else 0.0
            if self.editor.notes:
                duration = max(duration, max(float(n.end) for n in self.editor.notes))
            self.player.set_virtual_duration(duration)

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
        self.note_clipboard = [n.with_time_offset(-min_start) for n in selected]
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
            pasted = n.with_time_offset(base).normalized()
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

    def apply_target_angle_to_selected(self) -> None:
        indices = self.selected_note_indices()
        if not indices:
            self.statusBar().showMessage("No selected notes for Target Angle")
            return

        angle = float(self.target_angle.value())
        self.editor.push_undo()
        for i in indices:
            self.editor.notes[i] = self.editor.notes[i].with_target_angle(angle)

        self.editor.redraw_notes()
        self.editor.notes_changed.emit()
        self.mark_dirty()
        self.statusBar().showMessage(f"Applied Target Angle {angle:.6f}° to {len(indices)} note(s)")

    def clear_target_angle_for_selected(self) -> None:
        indices = self.selected_note_indices()
        if not indices:
            self.statusBar().showMessage("No selected notes to clear Target Angle")
            return

        self.editor.push_undo()
        for i in indices:
            self.editor.notes[i] = self.editor.notes[i].with_target_angle(None)

        self.editor.redraw_notes()
        self.editor.notes_changed.emit()
        self.mark_dirty()
        self.statusBar().showMessage(f"Cleared Target Angle from {len(indices)} note(s)")

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


    def apply_curve_shape(self) -> None:
        if hasattr(self.editor, "set_curve_shape"):
            self.editor.set_curve_shape(self.curve_shape.currentText() if hasattr(self, "curve_shape") else "ease")

    def apply_curve_interpolation(self) -> None:
        if hasattr(self.editor, "set_curve_interpolation"):
            self.editor.set_curve_interpolation(
                self.curve_interpolation.currentText() if hasattr(self, "curve_interpolation") else "bezier_pitch"
            )

    def apply_interpolation_to_selected(self) -> None:
        indices = self.selected_note_indices()
        if not indices:
            self.statusBar().showMessage("No selected curve notes for interpolation")
            return

        mode = self.curve_interpolation.currentText() if hasattr(self, "curve_interpolation") else "bezier_pitch"
        curve_indices = [i for i in indices if self.editor.notes[i].is_curve]
        if not curve_indices:
            self.statusBar().showMessage("Selected notes do not include curve/glide notes")
            return

        self.editor.push_undo()
        changed = 0
        for i in curve_indices:
            self.editor.notes[i] = self.editor.notes[i].with_interpolation(mode)
            changed += 1

        self.editor.redraw_notes()
        self.editor.notes_changed.emit()
        self.mark_dirty()
        self.statusBar().showMessage(f"Applied interpolation {mode} to {changed} curve note(s)")

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
        if not self.confirm_discard_unsaved(tr("dialog.open_audio.title")):
            return

        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            tr("dialog.open_audio.title"),
            "",
            "Audio Files (*.wav *.ogg *.mp3 *.flac *.m4a);;All Files (*)",
        )
        if not path:
            return
        self.load_audio(path, reset_notes=True)

    def reanalyze_current_audio(self) -> None:
        if not self.current_audio:
            self.statusBar().showMessage(tr("status.open_audio"))
            return
        self.load_audio(self.current_audio, reset_notes=False, clear_project=False, force_reanalysis=True)

    def analysis_options(self) -> dict:
        profile = self.analysis_profile.currentText() if hasattr(self, "analysis_profile") else "Normal"
        opts = analysis_profile_options(profile)

        resolution = self.cqt_resolution.currentText() if hasattr(self, "cqt_resolution") else "profile default"
        res_key = (resolution or "profile default").lower().replace(" ", "_")
        microtonal_map = {
            "100_cents": 12,
            "50_cents": 24,
            "25_cents": 48,
            "12.5_cents": 96,
            "12_5_cents": 96,
            "41_edo": 41,
            "53_edo": 53,
        }
        if res_key in microtonal_map:
            bpo = int(microtonal_map[res_key])
            opts["cqt_bins_per_octave"] = bpo
            opts["bins_per_semitone"] = max(1, int(round(bpo / 12.0)))
            opts["fold_to_semitone"] = bpo == 12
            # Keep high-resolution / non-12 CQT stable; hybrid_cqt can be rough
            # with many bins per octave in some librosa versions.
            if bpo != 12:
                opts["engine"] = "cqt"

        return opts

    def analysis_signature(self, path: str, opts: dict | None = None) -> str:
        """Signature for the currently displayed spectrogram analysis."""
        import json

        p = Path(path)
        opts = dict(opts or self.analysis_options())
        try:
            stat = p.stat()
            payload = {
                "path": str(p.resolve()),
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                **opts,
            }
        except Exception:
            payload = {"path": str(p), **opts}
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)

    def has_same_loaded_analysis(self, path: str, opts: dict | None = None) -> bool:
        sig = self.analysis_signature(path, opts)
        return (
            self.editor.spectrogram is not None
            and self.current_audio == str(Path(path).resolve())
            and self._current_analysis_signature == sig
        )

    def load_audio(
        self,
        path: str,
        *,
        reset_notes: bool = True,
        clear_project: bool = True,
        force_reanalysis: bool = False,
    ) -> None:
        opts = self.analysis_options()
        profile = self.analysis_profile.currentText() if hasattr(self, "analysis_profile") else "Normal"
        abs_path = str(Path(path).resolve())
        signature = self.analysis_signature(abs_path, opts)

        if not force_reanalysis and self.has_same_loaded_analysis(abs_path, opts):
            if clear_project:
                self.current_project = None
            self.current_audio = abs_path
            if reset_notes:
                self._suppress_dirty = True
                try:
                    self.editor.set_notes([])
                finally:
                    self._suppress_dirty = False
                self.note_clipboard.clear()
                self.sync_notes_to_player()
            self.update_time_labels()
            self.update_view_from_controls()
            self.apply_timing_helpers()
            if self.player.available and getattr(self.player, "audio", None) is None:
                QtCore.QTimer.singleShot(1, lambda p=abs_path: self.load_audio_for_playback(p))
            self.statusBar().showMessage(tr("status.reused_spectrogram", name=Path(path).name, profile=profile))
            return

        if self._analysis_thread is not None and self._analysis_thread.isRunning():
            self.statusBar().showMessage(tr("status.audio_analysis_running"))
            return

        if reset_notes:
            self._suppress_dirty = True
            try:
                self.editor.set_notes([])
            finally:
                self._suppress_dirty = False
            self.note_clipboard.clear()
            self.sync_notes_to_player()

        cache_status = "cache hit" if has_analysis_cache(abs_path, **opts) else "cache miss"
        self.statusBar().showMessage(
            tr("status.loading_cqt", profile=profile, cache_status=cache_status, sr=opts["sr"], hop=opts["hop_length"])
        )

        self._analysis_request_id += 1
        request_id = self._analysis_request_id

        thread = QtCore.QThread(self)
        worker = AnalysisWorker(abs_path, opts, signature, reset_notes, profile, clear_project, request_id)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(self.on_audio_analysis_finished)
        worker.failed.connect(self.on_audio_analysis_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.on_audio_analysis_thread_finished)

        self._analysis_thread = thread
        self._analysis_worker = worker
        if not self._analysis_cursor_active:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
            self._analysis_cursor_active = True
        thread.start()

    @QtCore.Slot(object, str, str, bool, str, bool, int)
    def on_audio_analysis_finished(
        self,
        spec,
        path: str,
        signature: str,
        reset_notes: bool,
        profile: str,
        clear_project: bool,
        request_id: int,
    ) -> None:
        if request_id != self._analysis_request_id:
            return
        self.apply_loaded_spectrogram(spec, path, signature, reset_notes, profile, clear_project)

    @QtCore.Slot(str, str, str, bool, str, bool, int)
    def on_audio_analysis_failed(
        self,
        message: str,
        path: str,
        signature: str,
        reset_notes: bool,
        profile: str,
        clear_project: bool,
        request_id: int,
    ) -> None:
        if request_id != self._analysis_request_id:
            return
        QtWidgets.QMessageBox.critical(self, tr("dialog.load_failed"), message)
        self.statusBar().showMessage(tr("status.analysis_failed", name=Path(path).name))

    @QtCore.Slot()
    def on_audio_analysis_thread_finished(self) -> None:
        self._analysis_thread = None
        self._analysis_worker = None
        if self._analysis_cursor_active:
            QtWidgets.QApplication.restoreOverrideCursor()
            self._analysis_cursor_active = False
        self._ignore_scroll_signal = False

    def apply_loaded_spectrogram(
        self,
        spec,
        path: str,
        signature: str,
        reset_notes: bool,
        profile: str,
        clear_project: bool,
    ) -> None:
        self.current_audio = str(Path(path).resolve())
        self._current_analysis_signature = signature
        if clear_project:
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
        try:
            self.time_slider.setValue(0)
            self.visible_sec.setValue(min(12.0, max(0.5, spec.duration)))
            self.pitch_bottom.setRange(spec.midi_min, spec.midi_max)
            self.pitch_bottom.setValue(spec.midi_min)
            self.visible_notes.setRange(6, spec.midi_max - spec.midi_min + 1)
            self.visible_notes.setValue(min(60, spec.midi_max - spec.midi_min + 1))
        finally:
            self._ignore_scroll_signal = False

        self.editor.set_playhead(0.0)
        self.update_time_labels()
        self.update_view_from_controls()
        self.apply_timing_helpers()

        # Display the spectrogram first, then decode playback audio after returning to the event loop.
        if self.player.available:
            QtCore.QTimer.singleShot(1, lambda p=str(path): self.load_audio_for_playback(p))

        self.set_dirty(False if reset_notes else self._dirty)
        self.statusBar().showMessage(
            tr("status.loaded_spectrogram", name=Path(path).name, profile=profile)
        )

    def load_audio_for_playback(self, path: str) -> None:
        if not self.player.available:
            return

        abs_path = str(Path(path).resolve())
        if self.current_audio is None or abs_path != self.current_audio:
            return

        if self._playback_thread is not None and self._playback_thread.isRunning():
            self.statusBar().showMessage(tr("status.playback_loading"))
            return

        self._playback_request_id += 1
        request_id = self._playback_request_id

        self.statusBar().showMessage(tr("status.loading_playback_background"))

        thread = QtCore.QThread(self)
        worker = PlaybackLoadWorker(abs_path, request_id)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(self.on_playback_audio_loaded)
        worker.failed.connect(self.on_playback_audio_load_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.on_playback_audio_thread_finished)

        self._playback_thread = thread
        self._playback_worker = worker
        thread.start()

    @QtCore.Slot(object, int, str, int)
    def on_playback_audio_loaded(self, audio, sr: int, path: str, request_id: int) -> None:
        if request_id != self._playback_request_id:
            return
        abs_path = str(Path(path).resolve())
        if self.current_audio is None or abs_path != self.current_audio:
            return

        try:
            self.player.set_audio(audio, int(sr))
            if hasattr(self.player, "set_volume"):
                self.player.set_volume(self.volume.value() / 100.0)
            self.sync_notes_to_player()
            self.apply_playback_speed()
            self.apply_timing_helpers()
            self.statusBar().showMessage(tr("status.playback_ready", name=Path(path).name))
        except Exception as e:
            self.statusBar().showMessage(tr("status.playback_load_failed", error=repr(e)))

    @QtCore.Slot(str, str, int)
    def on_playback_audio_load_failed(self, message: str, path: str, request_id: int) -> None:
        if request_id != self._playback_request_id:
            return
        self.statusBar().showMessage(tr("status.playback_load_failed", error=message))

    @QtCore.Slot()
    def on_playback_audio_thread_finished(self) -> None:
        self._playback_thread = None
        self._playback_worker = None


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
            self.statusBar().showMessage(tr("status.open_audio"))
            return
        if not self.player.available:
            self.statusBar().showMessage(tr("status.playback_unavailable", error=self.player.error))
            return

        if not self.player.playing:
            self.sync_notes_to_player()
            self.apply_playback_speed()

            if getattr(self.player, "audio", None) is None and self.current_audio:
                self.statusBar().showMessage(tr("status.playback_loading"))
                QtCore.QTimer.singleShot(1, lambda p=self.current_audio: self.load_audio_for_playback(p))
                return

            if getattr(self.player, "audio", None) is None:
                has_notes = bool(getattr(self.editor, "notes", []))
                metro_on = bool(self.metro_enabled.isChecked()) if hasattr(self, "metro_enabled") else False
                if not has_notes and not metro_on:
                    self.statusBar().showMessage(tr("status.no_audio_or_notes"))
                    return

            self.player.seek(self.editor.playhead_time())

        self.player.toggle()
        if self.player.playing and getattr(self.player, "audio", None) is None:
            self.statusBar().showMessage(tr("status.playing_notes_only"))
        else:
            self.statusBar().showMessage(tr("status.playing") if self.player.playing else tr("status.paused", time=self.editor.playhead_time()))

    def stop_playback(self) -> None:
        self.player.stop()
        self.editor.set_playhead(0.0)
        self.update_time_labels()
        self.statusBar().showMessage(tr("status.stopped"))

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
            # Backward-compatible alias: old projects used note_octave for preview/export together.
            "note_octave": int(self.note_octave.value()) if hasattr(self, "note_octave") else 0,
            "preview_octave": int(self.note_octave.value()) if hasattr(self, "note_octave") else 0,
            "export_octave": int(self.export_octave.value()) if hasattr(self, "export_octave") else 0,
            "export_semitone": int(self.export_semitone.value()) if hasattr(self, "export_semitone") else 0,
            "note_volume": int(self.note_vol.value()) if hasattr(self, "note_vol") else 20,
            "note_sound_enabled": bool(self.note_sound_enabled.isChecked()) if hasattr(self, "note_sound_enabled") else True,
            "song_volume": int(self.volume.value()) if hasattr(self, "volume") else 85,
            "playback_speed": float(self.playback_speed.value()) if hasattr(self, "playback_speed") else 1.0,
            "analysis_profile": self.analysis_profile.currentText() if hasattr(self, "analysis_profile") else "Normal",
            "cqt_resolution": self.cqt_resolution.currentText() if hasattr(self, "cqt_resolution") else "profile default",
            "display_mode": self.display_mode.currentText() if hasattr(self, "display_mode") else "wavetone",
            "cmap": self.cmap.currentText() if hasattr(self, "cmap") else "wavetone",
            "curve_shape": self.curve_shape.currentText() if hasattr(self, "curve_shape") else "ease",
            "curve_interpolation": self.curve_interpolation.currentText() if hasattr(self, "curve_interpolation") else "bezier_pitch",
            "adofai_use_project_song": bool(getattr(self, "adofai_use_project_song", True)),
            "adofai_copy_project_song": bool(getattr(self, "adofai_copy_project_song", True)),
            "adofai_song_offset_auto": bool(getattr(self, "adofai_song_offset_auto", True)),
            "adofai_song_offset_ms": float(getattr(self, "adofai_song_offset_ms", 0.0)),
            "blank_workspace_duration": float(getattr(self, "blank_workspace_duration", 60.0)),
            "blank_workspace_midi_min": int(getattr(self, "blank_workspace_midi_min", 12)),
            "blank_workspace_midi_max": int(getattr(self, "blank_workspace_midi_max", 120)),
        }

    def apply_project_settings(self, settings: dict) -> None:
        if not settings:
            return

        blockers = []
        for name in (
            "grid_bpm", "grid_offset_ms", "grid_enabled", "metro_enabled", "metro_vol",
            "snap_enabled", "snap_div", "note_octave", "export_octave", "export_semitone", "note_vol", "note_sound_enabled",
            "volume", "playback_speed", "analysis_profile", "cqt_resolution", "display_mode", "cmap", "curve_shape", "curve_interpolation",
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
            old_single_octave = int(settings["note_octave"]) if "note_octave" in settings else 0
            has_new_pitch_controls = (
                "preview_octave" in settings
                or "export_octave" in settings
                or "export_semitone" in settings
            )

            if hasattr(self, "note_octave"):
                if "preview_octave" in settings:
                    self.note_octave.setValue(int(settings["preview_octave"]))
                elif "note_octave" in settings:
                    # Backward compatibility: old projects used one Oct value for
                    # both preview and export.
                    self.note_octave.setValue(old_single_octave)

            if hasattr(self, "export_octave"):
                if "export_octave" in settings:
                    self.export_octave.setValue(int(settings["export_octave"]))
                elif "note_octave" in settings and not has_new_pitch_controls:
                    # Preserve old project export behavior.
                    self.export_octave.setValue(old_single_octave)

            if hasattr(self, "export_semitone") and "export_semitone" in settings:
                self.export_semitone.setValue(int(settings["export_semitone"]))
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
            if hasattr(self, "cqt_resolution") and "cqt_resolution" in settings:
                idx = self.cqt_resolution.findText(str(settings["cqt_resolution"]))
                if idx >= 0:
                    self.cqt_resolution.setCurrentIndex(idx)
            if hasattr(self, "display_mode") and "display_mode" in settings:
                idx = self.display_mode.findText(str(settings["display_mode"]))
                if idx >= 0:
                    self.display_mode.setCurrentIndex(idx)
            if hasattr(self, "cmap") and "cmap" in settings:
                idx = self.cmap.findText(str(settings["cmap"]))
                if idx >= 0:
                    self.cmap.setCurrentIndex(idx)
            if hasattr(self, "curve_shape") and "curve_shape" in settings:
                idx = self.curve_shape.findText(str(settings["curve_shape"]))
                if idx >= 0:
                    self.curve_shape.setCurrentIndex(idx)
            if hasattr(self, "curve_interpolation") and "curve_interpolation" in settings:
                idx = self.curve_interpolation.findText(str(settings["curve_interpolation"]))
                if idx >= 0:
                    self.curve_interpolation.setCurrentIndex(idx)

            if "adofai_use_project_song" in settings:
                self.adofai_use_project_song = bool(settings["adofai_use_project_song"])
            if "adofai_copy_project_song" in settings:
                self.adofai_copy_project_song = bool(settings["adofai_copy_project_song"])
            if "adofai_song_offset_auto" in settings:
                self.adofai_song_offset_auto = bool(settings["adofai_song_offset_auto"])
            if "adofai_song_offset_ms" in settings:
                self.adofai_song_offset_ms = float(settings["adofai_song_offset_ms"])

            if "blank_workspace_duration" in settings:
                self.blank_workspace_duration = max(1.0, float(settings["blank_workspace_duration"]))
            if "blank_workspace_midi_min" in settings:
                self.blank_workspace_midi_min = int(max(0, min(127, int(settings["blank_workspace_midi_min"]))))
            if "blank_workspace_midi_max" in settings:
                self.blank_workspace_midi_max = int(max(0, min(127, int(settings["blank_workspace_midi_max"]))))
            if self.blank_workspace_midi_max <= self.blank_workspace_midi_min:
                self.blank_workspace_midi_max = min(127, self.blank_workspace_midi_min + 12)
        finally:
            for widget in blockers:
                widget.blockSignals(False)

        self.apply_timing_helpers()
        self.apply_note_sound_settings()
        self.apply_playback_speed()
        self.apply_curve_shape()
        self.apply_curve_interpolation()
        if hasattr(self.player, "set_volume") and hasattr(self, "volume"):
            self.player.set_volume(self.volume.value() / 100.0)
        self.statusBar().showMessage(tr("status.project_settings_applied"))

    def save_project_as(self) -> bool:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            tr("dialog.save_project.title"),
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
            QtWidgets.QMessageBox.critical(self, tr("dialog.save_failed"), str(e))
            return False

    def load_project_notes_only(self) -> None:
        self.load_project_from_file(notes_only=True)

    def estimate_blank_spectrogram_bounds(self, notes: list[Note] | None = None) -> tuple[float, int, int]:
        """
        Return a sane black spectrogram size when no audio is loaded.

        Duration follows the loaded notes so notes still remain visible.
        Pitch range defaults to C0-C10, but expands if notes are outside it.
        """
        src = notes if notes is not None else self.editor.notes
        duration = float(getattr(self, "blank_workspace_duration", 60.0))
        midi_min = int(getattr(self, "blank_workspace_midi_min", 12))
        midi_max = int(getattr(self, "blank_workspace_midi_max", 120))

        if src:
            duration = max(12.0, max(float(n.end) for n in src) + 2.0)
            pitches: list[float] = []
            for n in src:
                nn = n.normalized()
                pitches.append(float(nn.midi))
                if nn.midi_end is not None:
                    pitches.append(float(nn.midi_end))
                if nn.ctrl1_midi is not None:
                    pitches.append(float(nn.ctrl1_midi))
                if nn.ctrl2_midi is not None:
                    pitches.append(float(nn.ctrl2_midi))

            if pitches:
                midi_min = min(12, max(0, int(min(pitches)) - 12))
                midi_max = max(120, min(127, int(max(pitches)) + 12))

        duration = max(1.0, float(duration))
        midi_min = int(max(0, min(127, midi_min)))
        midi_max = int(max(midi_min + 12, min(127, midi_max)))
        return duration, midi_min, midi_max

    def make_blank_spectrogram(
        self,
        notes: list[Note] | None = None,
        *,
        duration: float | None = None,
        midi_min: int | None = None,
        midi_max: int | None = None,
    ) -> Spectrogram:
        """
        Create a black placeholder spectrogram.

        This is used when a project is loaded without loading/analyzing audio,
        so stale spectrogram/audio from the previous project cannot remain.
        """
        auto_duration, auto_midi_min, auto_midi_max = self.estimate_blank_spectrogram_bounds(notes)
        duration = auto_duration if duration is None else max(1.0, float(duration))
        midi_min = auto_midi_min if midi_min is None else int(max(0, min(127, int(midi_min))))
        midi_max = auto_midi_max if midi_max is None else int(max(0, min(127, int(midi_max))))
        if midi_max <= midi_min:
            midi_max = min(127, midi_min + 12)
        hop = 0.05
        frames = max(2, int(duration / hop) + 1)
        rows = int(midi_max - midi_min + 1)
        db = np.zeros((rows, frames), dtype=np.float32)
        frame_times = np.linspace(0.0, duration, frames, dtype=np.float32)
        return Spectrogram(
            audio_path="",
            db=db,
            duration=float(duration),
            midi_min=int(midi_min),
            midi_max=int(midi_max),
            frame_times=frame_times,
            sr=22050,
        )

    def unload_audio_to_blank_spectrogram(self, notes: list[Note] | None = None, *, message: str = "Audio not loaded") -> None:
        """
        Drop any previous audio/spectrogram and show a black CQT placeholder.
        """
        self._analysis_request_id += 1  # invalidate any pending analysis result
        self.current_audio = None
        self._current_analysis_signature = None

        if hasattr(self.player, "clear_audio"):
            self.player.clear_audio()
        else:
            self.player.stop()
            self.player.audio = None

        spec = self.make_blank_spectrogram(notes)
        self.blank_workspace_duration = float(spec.duration)
        self.blank_workspace_midi_min = int(spec.midi_min)
        self.blank_workspace_midi_max = int(spec.midi_max)
        self.editor.set_spectrogram(spec)

        self._ignore_scroll_signal = True
        try:
            self.time_slider.setValue(0)
            self.visible_sec.setValue(min(12.0, max(0.5, spec.duration)))
            self.pitch_bottom.setRange(spec.midi_min, spec.midi_max)
            self.pitch_bottom.setValue(spec.midi_min)
            self.visible_notes.setRange(6, spec.midi_max - spec.midi_min + 1)
            self.visible_notes.setValue(min(60, spec.midi_max - spec.midi_min + 1))
        finally:
            self._ignore_scroll_signal = False

        self.editor.set_playhead(0.0)
        self.update_time_labels()
        self.update_view_from_controls()
        self.apply_timing_helpers()
        self.sync_notes_to_player()
        self.statusBar().showMessage(message)

    def apply_blank_workspace(
        self,
        *,
        duration: float,
        midi_min: int,
        midi_max: int,
        message: str | None = None,
        mark_dirty: bool = True,
    ) -> None:
        """
        Replace the current spectrogram/audio with an editable black workspace.

        Existing notes are preserved. This is mainly for experiments without
        loading an audio file.
        """
        duration = max(1.0, float(duration))
        midi_min = int(max(0, min(127, int(midi_min))))
        midi_max = int(max(0, min(127, int(midi_max))))
        if midi_max <= midi_min:
            midi_max = min(127, midi_min + 12)

        self.blank_workspace_duration = duration
        self.blank_workspace_midi_min = midi_min
        self.blank_workspace_midi_max = midi_max

        self._analysis_request_id += 1
        self._playback_request_id += 1
        self.current_audio = None
        self._current_analysis_signature = None

        if hasattr(self.player, "clear_audio"):
            self.player.clear_audio()
        else:
            self.player.stop()
            self.player.audio = None

        spec = self.make_blank_spectrogram(
            self.editor.notes,
            duration=duration,
            midi_min=midi_min,
            midi_max=midi_max,
        )
        self.editor.set_spectrogram(spec)

        self._ignore_scroll_signal = True
        try:
            self.time_slider.setValue(0)
            self.visible_sec.setValue(min(12.0, max(0.5, spec.duration)))
            self.pitch_bottom.setRange(spec.midi_min, spec.midi_max)
            self.pitch_bottom.setValue(spec.midi_min)
            self.visible_notes.setRange(6, spec.midi_max - spec.midi_min + 1)
            self.visible_notes.setValue(min(60, spec.midi_max - spec.midi_min + 1))
        finally:
            self._ignore_scroll_signal = False

        self.editor.set_playhead(0.0)
        self.update_time_labels()
        self.update_view_from_controls()
        self.apply_timing_helpers()
        self.sync_notes_to_player()

        if mark_dirty:
            self.mark_dirty()
        self.statusBar().showMessage(
            message or tr(
                "status.blank_workspace_set",
                duration=round(duration, 3),
                midi_min=midi_min,
                midi_max=midi_max,
            )
        )

    def configure_blank_workspace(self) -> None:
        spec = getattr(self.editor, "spectrogram", None)
        duration_default = float(
            getattr(spec, "duration", None)
            if spec is not None
            else getattr(self, "blank_workspace_duration", 60.0)
        )
        midi_min_default = int(
            getattr(spec, "midi_min", None)
            if spec is not None
            else getattr(self, "blank_workspace_midi_min", 12)
        )
        midi_max_default = int(
            getattr(spec, "midi_max", None)
            if spec is not None
            else getattr(self, "blank_workspace_midi_max", 120)
        )

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(tr("dialog.blank_workspace.title"))
        layout = QtWidgets.QVBoxLayout(dialog)

        info = QtWidgets.QLabel(tr("dialog.blank_workspace.info"))
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QtWidgets.QFormLayout()
        layout.addLayout(form)

        duration_box = QtWidgets.QDoubleSpinBox()
        duration_box.setRange(1.0, 36000.0)
        duration_box.setDecimals(3)
        duration_box.setSingleStep(10.0)
        duration_box.setSuffix(" s")
        duration_box.setValue(max(1.0, duration_default))

        midi_min_box = QtWidgets.QSpinBox()
        midi_min_box.setRange(0, 127)
        midi_min_box.setValue(max(0, min(127, midi_min_default)))

        midi_max_box = QtWidgets.QSpinBox()
        midi_max_box.setRange(0, 127)
        midi_max_box.setValue(max(0, min(127, midi_max_default)))

        def keep_order() -> None:
            if midi_max_box.value() <= midi_min_box.value():
                midi_max_box.setValue(min(127, midi_min_box.value() + 12))

        midi_min_box.valueChanged.connect(lambda *_: keep_order())
        midi_max_box.valueChanged.connect(lambda *_: keep_order())

        form.addRow(tr("dialog.blank_workspace.duration"), duration_box)
        form.addRow(tr("dialog.blank_workspace.midi_min"), midi_min_box)
        form.addRow(tr("dialog.blank_workspace.midi_max"), midi_max_box)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        self.apply_blank_workspace(
            duration=float(duration_box.value()),
            midi_min=int(midi_min_box.value()),
            midi_max=int(midi_max_box.value()),
        )

    def choose_project_audio_load_mode(self, audio: str | None) -> str:
        if not audio:
            return "skip"

        if not Path(audio).exists():
            box = QtWidgets.QMessageBox(self)
            box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            box.setWindowTitle(tr("dialog.missing_audio.title"))
            box.setText(tr("dialog.missing_audio.text"))
            box.setInformativeText(tr("dialog.missing_audio.info", path=str(audio)))
            locate_btn = box.addButton(tr("dialog.missing_audio.locate"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
            notes_btn = box.addButton(tr("dialog.load_audio.notes_only"), QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
            cancel_btn = box.addButton(tr("dialog.load_audio.cancel"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(locate_btn)
            box.exec()

            clicked = box.clickedButton()
            if clicked == locate_btn:
                return "locate"
            if clicked == notes_btn:
                return "skip"
            if clicked == cancel_btn:
                return "cancel"
            return "cancel"

        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Icon.Question)
        box.setWindowTitle(tr("dialog.load_audio.title"))
        box.setText(tr("dialog.load_audio.text"))
        box.setInformativeText(tr("dialog.load_audio.info"))
        load_btn = box.addButton(tr("dialog.load_audio.load"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        notes_btn = box.addButton(tr("dialog.load_audio.notes_only"), QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton(tr("dialog.load_audio.cancel"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(load_btn)
        box.exec()

        clicked = box.clickedButton()
        if clicked == load_btn:
            return "load"
        if clicked == notes_btn:
            return "skip"
        if clicked == cancel_btn:
            return "cancel"
        return "cancel"

    def locate_missing_project_audio(self, missing_audio: str | None = None) -> str | None:
        start_dir = ""
        if missing_audio:
            try:
                p = Path(str(missing_audio))
                if p.parent.exists():
                    start_dir = str(p.parent)
            except Exception:
                start_dir = ""

        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            tr("dialog.locate_audio.title"),
            start_dir,
            "Audio Files (*.wav *.ogg *.mp3 *.flac *.m4a);;All Files (*)",
        )
        return path or None

    def load_project_from_file(self, *, notes_only: bool = False) -> None:
        if not self.confirm_discard_unsaved(tr("dialog.load_project.title")):
            return

        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            tr("dialog.load_project.title"),
            "",
            "AdopyHzEditor Project (*.adopyhz);;Old Project (*.ahe.json *.json);;JSON (*.json);;All Files (*)",
        )
        if not path:
            return
        try:
            audio, notes, settings = load_project(path)
            self._suppress_dirty = True
            try:
                # Apply settings first so the saved analysis_profile is used when loading audio.
                self.apply_project_settings(settings)
                self.editor.set_notes(notes)
            finally:
                self._suppress_dirty = False

            self.current_project = Path(path)
            self.set_dirty(False)
            self.sync_notes_to_player()

            mode = "skip" if notes_only else self.choose_project_audio_load_mode(audio)
            if mode == "cancel":
                return
            if mode == "locate":
                located = self.locate_missing_project_audio(audio)
                if not located:
                    self.unload_audio_to_blank_spectrogram(
                        notes,
                        message=tr("status.loaded_notes_only", name=Path(path).name),
                    )
                    return
                audio = located
                self.set_dirty(True)
            if mode in ("load", "locate") and audio and Path(audio).exists():
                self.load_audio(audio, reset_notes=False, clear_project=False)
                self.statusBar().showMessage(tr("status.loaded_project_audio", name=Path(path).name))
            else:
                self.unload_audio_to_blank_spectrogram(
                    notes,
                    message=tr("status.loaded_notes_only", name=Path(path).name),
                )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, tr("dialog.load_failed"), str(e))

    def parse_ratio_fraction(self, text: str) -> Fraction:
        s = str(text).strip()
        if not s:
            raise ValueError("empty ratio")
        # Accept 7/3, 1.25, 5:4, and simple whitespace.
        if ":" in s:
            a, b = s.split(":", 1)
            value = Fraction(a.strip()) / Fraction(b.strip())
        else:
            value = Fraction(s)
        if value <= 0:
            raise ValueError("ratio must be positive")
        return value

    def parse_ratio_text(self, text: str) -> float:
        return float(self.parse_ratio_fraction(text))

    def octave_fold_ratio(self, ratio: float, *, low: float = 1.0, high: float = 2.0) -> float:
        """
        Fold a frequency ratio by powers of 2.
        """
        return float(self.octave_fold_fraction(Fraction(float(ratio)), low=low, high=high))

    def octave_fold_fraction(self, ratio: Fraction, *, low: float = 1.0, high: float = 2.0) -> Fraction:
        """
        Fold a frequency ratio by powers of 2 while keeping exact rational values
        where possible.
        """
        r = Fraction(ratio)
        if r <= 0:
            raise ValueError("ratio must be positive")
        low_f = max(1e-12, float(low))
        high_f = max(low_f * 1.000001, float(high))
        while float(r) < low_f:
            r *= 2
        while float(r) >= high_f:
            r /= 2
        return r

    def _factor_int(self, value: int) -> dict[int, int]:
        n = abs(int(value))
        factors: dict[int, int] = {}
        d = 2
        while d * d <= n:
            while n % d == 0:
                factors[d] = factors.get(d, 0) + 1
                n //= d
            d += 1 if d == 2 else 2
        if n > 1:
            factors[n] = factors.get(n, 0) + 1
        return factors

    def dimension_ratio_fraction(self, ratio: Fraction) -> Fraction:
        """
        Convert a rational ratio into the Caftaphata-style dimension
        representative.

        Supported dimension generators:

            1d -> (2/1)^n
            2d -> (3/2)^n
            3d -> (5/4)^n
            4d -> (7/4)^n
            5d -> (11/4)^n

        Example:
            2d^m * 3d^n -> (3^m * 5^n) / (2^m * 4^n)
        """
        r = Fraction(ratio)
        if r <= 0:
            raise ValueError("ratio must be positive")

        generators = {
            2: Fraction(2, 1),
            3: Fraction(3, 2),
            5: Fraction(5, 4),
            7: Fraction(7, 4),
            11: Fraction(11, 4),
        }

        exponents: dict[int, int] = {}
        for p, e in self._factor_int(r.numerator).items():
            exponents[p] = exponents.get(p, 0) + e
        for p, e in self._factor_int(r.denominator).items():
            exponents[p] = exponents.get(p, 0) - e

        out = Fraction(1, 1)
        for p, e in sorted(exponents.items()):
            gen = generators.get(p)
            if gen is None:
                raise ValueError(f"unsupported dimension prime: {p}")
            if e >= 0:
                out *= gen ** e
            else:
                out /= gen ** (-e)
        return out

    def format_ratio_value(self, ratio: Fraction | float, *, decimals: int = 6) -> str:
        frac = ratio if isinstance(ratio, Fraction) else Fraction(float(ratio)).limit_denominator(1000000)
        value = float(frac)
        if frac.denominator <= 100000 and abs(value) < 100000:
            return f"{frac.numerator}/{frac.denominator} ({value:.{decimals}f})"
        return f"{value:.{decimals}f}"

    def caftaphata_pitch_number(self, ratio: float, *, edo: int = 41, offset: int = 2) -> int:
        edo = max(1, int(edo))
        n = int(offset) + int(round(edo * math.log2(max(1e-12, float(ratio)))))
        return n % edo

    def insert_harmonic_diagram(self) -> None:
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(tr("dialog.harmonic_diagram.title"))
        dialog.setMinimumWidth(520)
        dialog.resize(560, 720)
        layout = QtWidgets.QVBoxLayout(dialog)

        info = QtWidgets.QLabel(tr("dialog.harmonic_diagram.info"))
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QtWidgets.QFormLayout()
        layout.addLayout(form)

        root_hz = QtWidgets.QDoubleSpinBox()
        root_hz.setRange(0.001, 100000.0)
        root_hz.setDecimals(6)
        root_hz.setSingleStep(1.0)
        root_hz.setSuffix(" Hz")
        root_hz.setValue(261.625565)

        try:
            if self.editor.selected_indices:
                idx = next(iter(self.editor.selected_indices))
                if 0 <= idx < len(self.editor.notes):
                    root_hz.setValue(440.0 * (2.0 ** ((float(self.editor.notes[idx].midi) - 69.0) / 12.0)))
        except Exception:
            pass

        root_shift = QtWidgets.QLineEdit("1")
        root_shift.setToolTip("基準音倍率です。local値と同じ次元生成元で変換してから掛けます。例: 1, 1/3, 7/3, 5/3")

        base_1d_offset = QtWidgets.QSpinBox()
        base_1d_offset.setRange(-64, 64)
        base_1d_offset.setValue(0)
        base_1d_offset.setToolTip(
            "基準音倍率に追加する1次元補正です。"
            "最終的な基準倍率に (2/1)^offset を掛けます。例: 1/9で+1なら 4/9*2 = 8/9"
        )

        harmonics = QtWidgets.QLineEdit("1/3,1,3,7,9")
        harmonics.setToolTip("例: 1/3,1,3,7,9 または 1,3,7,9,21")

        start_box = QtWidgets.QDoubleSpinBox()
        start_box.setRange(0.0, 36000.0)
        start_box.setDecimals(6)
        start_box.setSingleStep(0.25)
        start_box.setSuffix(" s")
        start_box.setValue(float(self.editor.playhead_time()) if hasattr(self.editor, "playhead_time") else 0.0)

        duration_box = QtWidgets.QDoubleSpinBox()
        duration_box.setRange(0.001, 36000.0)
        duration_box.setDecimals(6)
        duration_box.setSingleStep(0.25)
        duration_box.setSuffix(" s")
        duration_box.setValue(1.0)

        time_unit = QtWidgets.QComboBox()
        time_unit.addItems([
            "seconds",
            "beats",
        ])
        time_unit.setCurrentText("seconds")
        time_unit.setToolTip("Start/Durationを秒で入力するか、拍で入力するかを切り替えます。")

        bpm_box = QtWidgets.QDoubleSpinBox()
        bpm_box.setRange(1.0, 2000.0)
        bpm_box.setDecimals(6)
        bpm_box.setSingleStep(1.0)
        bpm_box.setSuffix(" BPM")
        bpm_box.setValue(float(self.grid_bpm.value()) if hasattr(self, "grid_bpm") else 120.0)
        bpm_box.setToolTip("Time unit = beats のときに、拍数を秒へ変換するBPMです。")

        edo_box = QtWidgets.QSpinBox()
        edo_box.setRange(1, 999)
        edo_box.setValue(41)

        offset_box = QtWidgets.QSpinBox()
        offset_box.setRange(-999, 999)
        offset_box.setValue(2)

        preview = QtWidgets.QLabel()
        preview.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        preview.setWordWrap(True)

        form.addRow(tr("dialog.harmonic_diagram.root_hz"), root_hz)
        form.addRow(tr("dialog.harmonic_diagram.root_shift"), root_shift)
        form.addRow(tr("dialog.harmonic_diagram.base_1d_offset"), base_1d_offset)
        form.addRow(tr("dialog.harmonic_diagram.harmonics"), harmonics)
        form.addRow(tr("dialog.harmonic_diagram.time_unit"), time_unit)
        form.addRow(tr("dialog.harmonic_diagram.bpm"), bpm_box)
        form.addRow(tr("dialog.harmonic_diagram.start"), start_box)
        form.addRow(tr("dialog.harmonic_diagram.duration"), duration_box)
        form.addRow(tr("dialog.harmonic_diagram.edo"), edo_box)
        form.addRow(tr("dialog.harmonic_diagram.offset"), offset_box)
        form.addRow(tr("dialog.harmonic_diagram.preview"), preview)

        def harmonic_time_values() -> tuple[float, float]:
            start_value = float(start_box.value())
            duration_value = float(duration_box.value())
            if time_unit.currentText() == "beats":
                beat_sec = 60.0 / max(1e-9, float(bpm_box.value()))
                return start_value * beat_sec, duration_value * beat_sec
            return start_value, duration_value

        def one_d_offset_factor() -> Fraction:
            offset = int(base_1d_offset.value())
            if offset >= 0:
                return Fraction(2, 1) ** offset
            return Fraction(1, 2) ** (-offset)

        def diagram_components(multiplier: Fraction, local: Fraction) -> tuple[Fraction, Fraction, Fraction, Fraction]:
            """
            Return:
              raw_global_ratio, placed_ratio, base_dimension_ratio_with_1d_offset, local_dimension_ratio

            Chalaxata/Caftaphata-style insertion:
              1. convert the base multiplier by the fixed dimension generators
              2. apply Base 1D offset as (2/1)^offset
              3. convert the diagram/local value by the same fixed dimension generators
              4. placed_ratio = base_dimension_ratio_with_1d_offset * local_dimension_ratio
            """
            raw_global = multiplier * local
            base_rep = self.dimension_ratio_fraction(multiplier) * one_d_offset_factor()
            local_rep = self.dimension_ratio_fraction(local)
            return raw_global, base_rep * local_rep, base_rep, local_rep

        def update_time_unit_ui() -> None:
            beat_mode = time_unit.currentText() == "beats"
            bpm_box.setEnabled(beat_mode)
            if beat_mode:
                start_box.setSuffix(" beat")
                duration_box.setSuffix(" beat")
                start_box.setSingleStep(1.0)
                duration_box.setSingleStep(1.0)
            else:
                start_box.setSuffix(" s")
                duration_box.setSuffix(" s")
                start_box.setSingleStep(0.25)
                duration_box.setSingleStep(0.25)
            update_preview()

        def update_preview() -> None:
            try:
                shift = self.parse_ratio_fraction(root_shift.text())
                vals = [self.parse_ratio_fraction(x) for x in harmonics.text().replace(";", ",").split(",") if x.strip()]
                if not vals:
                    preview.setText("No harmonics")
                    return
                start_sec, duration_sec = harmonic_time_values()
                if time_unit.currentText() == "beats":
                    lines = [f"time: {start_box.value():g} beat + {duration_box.value():g} beat @ {bpm_box.value():g} BPM = {start_sec:.6f}s - {start_sec + duration_sec:.6f}s"]
                else:
                    lines = [f"time: {start_sec:.6f}s - {start_sec + duration_sec:.6f}s"]

                base_rep = self.dimension_ratio_fraction(shift)
                offset_factor = one_d_offset_factor()
                effective_base = base_rep * offset_factor
                lines.append(
                    "base multiplier: "
                    f"{self.format_ratio_value(shift)} -> dimension {self.format_ratio_value(base_rep)} "
                    f"* 2^{int(base_1d_offset.value())} = {self.format_ratio_value(effective_base)}"
                )

                for v in vals:
                    raw_ratio, ratio, multiplier_rep, local_rep = diagram_components(shift, v)

                    hz = float(root_hz.value()) * float(ratio)
                    midi = 69.0 + 12.0 * math.log2(max(1e-12, hz) / 440.0)
                    pc = self.caftaphata_pitch_number(float(raw_ratio), edo=edo_box.value(), offset=offset_box.value())

                    detail = (
                        f"local {self.format_ratio_value(v)} -> dimension {self.format_ratio_value(local_rep)}, "
                        f"base_dimension×local_dimension {self.format_ratio_value(ratio)}"
                    )

                    lines.append(f"{detail}, {hz:.6f} Hz, MIDI {midi:.6f}, #{pc}")
                preview.setText("\n".join(lines))
            except Exception as e:
                preview.setText(f"Invalid ratio: {e}")

        for w in (root_hz, base_1d_offset, start_box, duration_box, bpm_box, edo_box, offset_box):
            w.valueChanged.connect(lambda *_: update_preview())
        time_unit.currentTextChanged.connect(lambda *_: update_time_unit_ui())
        root_shift.textChanged.connect(lambda *_: update_preview())
        harmonics.textChanged.connect(lambda *_: update_preview())
        update_time_unit_ui()

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        try:
            shift = self.parse_ratio_fraction(root_shift.text())
            vals = [self.parse_ratio_fraction(x) for x in harmonics.text().replace(";", ",").split(",") if x.strip()]
            if not vals:
                raise ValueError("harmonics list is empty")

            start, duration = harmonic_time_values()
            end = start + duration
            root_hz_value = float(root_hz.value())

            self.editor.push_undo()
            inserted = []
            for v in vals:
                raw_ratio, ratio, _multiplier_rep, _local_rep = diagram_components(shift, v)
                hz = root_hz_value * float(ratio)
                midi = 69.0 + 12.0 * math.log2(max(1e-12, hz) / 440.0)
                self.editor.notes.append(Note(start, end, midi).normalized())
                inserted.append(self.caftaphata_pitch_number(float(raw_ratio), edo=edo_box.value(), offset=offset_box.value()))

            self.editor.selected_indices = set(range(len(self.editor.notes) - len(vals), len(self.editor.notes)))
            self.editor.selected_index = min(self.editor.selected_indices) if self.editor.selected_indices else None
            self.editor.redraw_notes()
            self.editor.notes_changed.emit()
            self.mark_dirty()
            self.statusBar().showMessage(
                tr(
                    "status.harmonic_diagram_inserted",
                    count=len(vals),
                    numbers=", ".join(str(x) for x in inserted),
                )
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, tr("dialog.harmonic_diagram.title"), str(e))

    def check_for_updates(self, *, silent: bool = False) -> None:
        """
        Open the GitHub Releases page instead of doing in-app HTTPS/download/update.

        This intentionally avoids PyInstaller SSL/OpenSSL issues and keeps the
        update flow safe and predictable.
        """
        if silent:
            return

        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Icon.Information)
        box.setWindowTitle(tr("update.title"))
        box.setText(tr("update.open_releases_text", version=APP_VERSION))
        box.setInformativeText(tr("update.open_releases_info"))

        open_btn = box.addButton(tr("update.open_releases"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = box.addButton(tr("update.later"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(open_btn)
        box.exec()

        if box.clickedButton() == open_btn:
            try:
                webbrowser.open(GITHUB_RELEASES_URL)
                self.statusBar().showMessage(tr("status.opened_releases"))
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("update.title"),
                    tr("update.open_failed", error=repr(e), url=GITHUB_RELEASES_URL),
                )

    def current_preview_octave_shift(self) -> int:
        return int(self.note_octave.value()) if hasattr(self, "note_octave") else 0

    def current_export_octave_shift(self) -> int:
        return int(self.export_octave.value()) if hasattr(self, "export_octave") else 0

    def current_export_semitone_shift(self) -> int:
        return int(self.export_semitone.value()) if hasattr(self, "export_semitone") else 0

    def current_export_pitch_shift(self) -> int:
        return self.current_export_octave_shift() * 12 + self.current_export_semitone_shift()

    # Backward-compatible name for older internal callers. It now means Preview Oct.
    def current_octave_shift(self) -> int:
        return self.current_preview_octave_shift()

    def describe_export_pitch_shift(self) -> str:
        oct_shift = self.current_export_octave_shift()
        semi_shift = self.current_export_semitone_shift()
        total = self.current_export_pitch_shift()
        return f"Export Oct {oct_shift:+d}, Semi {semi_shift:+d} ({total:+d} semitone)"

    def notes_with_export_pitch_offset(self) -> list[Note]:
        """
        Apply explicit export pitch controls without moving notes on screen.

        Preview Oct is intentionally ignored here. Export pitch is:
            note_pitch + export_octave * 12 + export_semitone

        Curve notes keep their Bezier/Glide shape and shift all control points.
        """
        shift = self.current_export_pitch_shift()
        result: list[Note] = []
        for n in self.editor.notes:
            nn = n.normalized().with_pitch_offset(shift)
            # Clamp only for MIDI-ish note range. Fractional pitch is preserved.
            if nn.is_curve:
                result.append(Note(
                    nn.start,
                    nn.end,
                    max(0.0, min(127.0, nn.midi)),
                    nn.velocity,
                    "curve",
                    None if nn.midi_end is None else max(0.0, min(127.0, nn.midi_end)),
                    None if nn.ctrl1_midi is None else max(0.0, min(127.0, nn.ctrl1_midi)),
                    None if nn.ctrl2_midi is None else max(0.0, min(127.0, nn.ctrl2_midi)),
                    nn.interpolation,
                    nn.target_angle,
                ).normalized())
            else:
                result.append(Note(
                    nn.start,
                    nn.end,
                    max(0.0, min(127.0, nn.midi)),
                    nn.velocity,
                    target_angle=nn.target_angle,
                ).normalized())
        return result

    # Backward-compatible name for older internal callers.
    def notes_with_output_octave(self) -> list[Note]:
        return self.notes_with_export_pitch_offset()

    def export_midi_file(self) -> None:
        if not self.editor.notes:
            QtWidgets.QMessageBox.information(self, tr("dialog.no_notes.title"), tr("dialog.no_notes.text"))
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("dialog.export_midi.title"), "", "MIDI File (*.mid);;All Files (*)")
        if not path:
            return
        if not path.lower().endswith((".mid", ".midi")):
            path += ".mid"
        try:
            export_midi(self.notes_with_export_pitch_offset(), path)
            self.statusBar().showMessage(f"Exported MIDI: {Path(path).name} / {self.describe_export_pitch_shift()}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, tr("dialog.midi_export_failed"), str(e))

    def export_adofai_file(self) -> None:
        if not self.editor.notes:
            QtWidgets.QMessageBox.information(self, tr("dialog.no_notes.title"), tr("dialog.no_notes.text"))
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("dialog.export_adofai.title"), "", "ADOFAI Level (*.adofai);;All Files (*)")
        if not path:
            return
        if not path.lower().endswith(".adofai"):
            path += ".adofai"

        dialog = ExportAdoFAIDialog(self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        try:
            if hasattr(dialog, "store_workflow_to_parent"):
                dialog.store_workflow_to_parent()

            opts = dialog.options()
            copy_song = bool(opts.pop("_copy_song_to_export", False))
            song_source_path = opts.pop("_song_source_path", None)

            stats = export_adofai(self.notes_with_export_pitch_offset(), path, **opts)

            if copy_song and song_source_path:
                src = Path(str(song_source_path))
                dst = Path(path).resolve().parent / src.name
                try:
                    if src.exists():
                        same_file = False
                        try:
                            same_file = src.resolve() == dst.resolve()
                        except Exception:
                            same_file = False
                        if not same_file:
                            shutil.copy2(src, dst)
                        stats["song_copied"] = "already next to level" if same_file else dst.name
                    else:
                        stats["song_copy_warning"] = f"source missing: {src}"
                except Exception as copy_error:
                    stats["song_copy_warning"] = repr(copy_error)

            QtWidgets.QMessageBox.information(self, tr("dialog.export_complete.title"), "\n".join(f"{k}: {v}" for k, v in stats.items()))
            self.statusBar().showMessage(f"Exported ADOFAI: {Path(path).name} / {self.describe_export_pitch_shift()}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, tr("dialog.adofai_export_failed"), str(e))


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
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("export.title"))
        self.resize(780, 560)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        self.method = QtWidgets.QComboBox()
        self.method.addItems([
            "Angle Compression: corrected Keycount formula",
            "Angle-only: one BPM + angle only",
            "Harmony / Polyrhythm: merged impulse trains",
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
        self.harmony_mode.addItems([
            "off",
            "octave +12",
            "fifth +7",
            "major third +4",
            "minor third +3",
            "lower octave -12",
            "major triad",
            "minor triad",
            "sus4",
            "dominant 7",
            "custom",
        ])
        self.harmony_mode.setCurrentText("fifth +7")
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
        self.harmony_tuning.addItems([
            "equal temperament",
            "just intonation",
        ])
        self.harmony_tuning.setCurrentText("equal temperament")
        self.harmony_tuning.setToolTip(
            "3音以上のHarmonyで使うチューニング。\n"
            "equal temperamentは元音程に正確。\n"
            "just intonationは4:5:6などの単純比に寄せてパターンを安定させます。"
        )

        self.harmony_root_mode = QtWidgets.QComboBox()
        self.harmony_root_mode.addItems([
            "fixed root",
            "least squares Hz",
            "least squares cents",
            "minimax cents",
        ])
        self.harmony_root_mode.setCurrentText("minimax cents")
        self.harmony_root_mode.setToolTip(
            "Just Intonation時のroot周波数調整。\n"
            "fixed root: rootを元音程に固定\n"
            "least squares Hz: Hz誤差の二乗和を最小化\n"
            "least squares cents: cents誤差の二乗和を最小化\n"
            "minimax cents: 最大cents誤差を最小化"
        )

        self.harmony_timing_mode = QtWidgets.QComboBox()
        self.harmony_timing_mode.addItems([
            "setspeed",
            "angle-only",
        ])
        self.harmony_timing_mode.setCurrentText("angle-only")
        self.harmony_timing_mode.setToolTip(
            "Harmonyのtiming変換方法。\n"
            "setspeed: pitch由来の角度 + SetSpeedでtiming補正。\n"
            "angle-only: 1つのグローバルBPMで、次のzipまでの時間を角度に直接変換します。"
        )

        self.harmony_visual_mode = QtWidgets.QComboBox()
        self.harmony_visual_mode.addItems([
            "raw",
            "round 45°",
            "round 90°",
            "custom step",
        ])
        self.harmony_visual_mode.setCurrentText("round 45°")
        self.harmony_visual_mode.setToolTip(
            "Harmonyの見た目角度を読みやすい角度へ寄せます。\n"
            "タイミングは SetSpeed と new_angle / old_angle で補正します。"
        )

        self.harmony_visual_step = QtWidgets.QDoubleSpinBox()
        self.harmony_visual_step.setRange(1.0, 180.0)
        self.harmony_visual_step.setDecimals(3)
        self.harmony_visual_step.setValue(45.0)
        self.harmony_visual_step.setSuffix("°")
        self.harmony_visual_step.setToolTip("Harmony visual mode が custom step のときの角度刻み")

        self.x_mode = QtWidgets.QComboBox()
        self.x_mode.addItems(["floor", "lowest_floor", "round", "ceil", "fixed", "target_bpm"])
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
        self.track_visual.addItems(["normal", "faint", "very faint", "hidden"])
        self.track_visual.setCurrentText("normal")
        self.track_visual.setToolTip(
            "Angle Compression は見た目がスパゲッティ状になりやすいです。\n"
            "faint/hidden にするとトラック線を薄く/非表示にできます。"
        )

        self.visual_path_mode = QtWidgets.QComboBox()
        self.visual_path_mode.addItems(["raw", "upward", "upward avoid", "twirl upward"])
        self.visual_path_mode.setCurrentText("raw")
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
        self.visual_position_mode.addItems(["off", "note step"])
        self.visual_position_mode.setCurrentText("off")
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
        self.final_angle_mode.addItems(["scaled", "cardinal", "horizontal", "custom"])
        self.final_angle_mode.setCurrentText("scaled")
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
        if parent is not None and hasattr(parent, "editor") and getattr(parent.editor, "notes", None):
            try:
                self._auto_song_offset_ms = round(min(n.normalized().start for n in parent.editor.notes) * 1000.0, 3)
            except Exception:
                self._auto_song_offset_ms = 0.0

        self.use_project_song = QtWidgets.QCheckBox("Use project audio as ADOFAI song")
        self.use_project_song.setChecked(bool(self._song_source_path) and bool(getattr(parent, "adofai_use_project_song", True)))
        self.use_project_song.setToolTip("settings.songFilename に現在読み込んでいる音声ファイル名を入れます")

        self.copy_project_song = QtWidgets.QCheckBox("Copy song next to .adofai")
        self.copy_project_song.setChecked(bool(self._song_source_path) and bool(getattr(parent, "adofai_copy_project_song", True)))
        self.copy_project_song.setToolTip("ADOFAI出力先フォルダへ音声ファイルをコピーします。Release用に便利です。")

        self.song_offset_auto = QtWidgets.QCheckBox("Use first note start")
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
            note_source = parent.notes_with_export_pitch_offset() if hasattr(parent, "notes_with_export_pitch_offset") else parent.notes_with_output_octave()
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
            note_source = parent.notes_with_export_pitch_offset() if hasattr(parent, "notes_with_export_pitch_offset") else parent.notes_with_output_octave()
            rows = build_adofai_debug_rows(note_source, **self.options())
            dlg = AdoFAIDebugPreviewDialog(rows, self)
            dlg.exec()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, tr("debug.title"), str(e))

    def options(self) -> dict:
        return {
            "method": (
                "angle_only" if self.method.currentIndex() == 1
                else "harmony" if self.method.currentIndex() == 2
                else "rabbit_zip"
            ),
            "base_bpm": float(self.base_bpm.value()),
            "angle_only_bpm": float(self.angle_only_bpm.value()),
            "harmony_mode": self.harmony_mode.currentText(),
            "harmony_custom_semitone": float(self.harmony_custom_semitone.value()),
            "harmony_epsilon_ms": float(self.harmony_epsilon_ms.value()),
            "harmony_tuning": self.harmony_tuning.currentText(),
            "harmony_root_mode": self.harmony_root_mode.currentText(),
            "harmony_timing_mode": self.harmony_timing_mode.currentText(),
            "harmony_visual_mode": self.harmony_visual_mode.currentText(),
            "harmony_visual_step": float(self.harmony_visual_step.value()),
            "rabbit_x_mode": self.x_mode.currentText(),
            "rabbit_fixed_x": float(self.fixed_x.value()),
            "rabbit_target_bpm": float(self.target_bpm.value()),
            "max_tiles": int(self.max_tiles.value()),
            "max_tiles_per_note": int(self.max_tiles_per_note.value()),
            "track_visual": self.track_visual.currentText(),
            "visual_path_mode": self.visual_path_mode.currentText(),
            "visual_path_angle": float(self.visual_path_angle.value()),
            "visual_position_mode": self.visual_position_mode.currentText(),
            "visual_position_x": float(self.visual_position_x.value()),
            "visual_position_y": float(self.visual_position_y.value()),
            # Phase-continuous glide is now the standard behavior.
            "phase_continuous_glide": True,
            "final_angle_mode": self.final_angle_mode.currentText(),
            "final_custom_angle": float(self.final_custom_angle.value()),
            "final_cardinal_step": float(self.final_cardinal_step.value()),
            "song_filename": Path(self._song_source_path).name if self.use_project_song.isChecked() and self._song_source_path else None,
            "song_offset_ms": float(self.song_offset_ms.value()) if self.use_project_song.isChecked() else None,
            "_copy_song_to_export": bool(self.copy_project_song.isChecked() and self.use_project_song.isChecked() and self._song_source_path),
            "_song_source_path": self._song_source_path if self.use_project_song.isChecked() and self._song_source_path else None,
            "pretty": False,
        }


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
