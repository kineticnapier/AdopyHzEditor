from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from i18n import tr


_STYLE_SHEET = r"""
QMainWindow, QDialog {
    background: #202225;
    color: #e8e8e8;
}
QMenuBar, QMenu, QToolBar, QStatusBar, QDockWidget {
    background: #282b30;
    color: #e8e8e8;
}
QMenuBar::item:selected, QMenu::item:selected {
    background: #3a3f46;
}
QToolBar {
    border: 0;
    spacing: 3px;
    padding: 3px 5px;
}
QToolBar::separator {
    background: #444950;
    width: 1px;
    margin: 4px 5px;
}
QToolButton {
    background: transparent;
    color: #e8e8e8;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 7px;
}
QToolButton:hover {
    background: #34383f;
}
QToolButton:pressed, QToolButton:checked {
    background: #3d4754;
    border-color: #5b9bd5;
}
QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
    background: #30343a;
    color: #e8e8e8;
    border: 1px solid #444950;
    border-radius: 4px;
    padding: 3px 6px;
    min-height: 20px;
}
QPushButton:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover {
    border-color: #65707c;
}
QPushButton:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QSlider:disabled {
    color: #747a82;
    background: #282b30;
}
QCheckBox {
    spacing: 6px;
}
QToolBox::tab {
    background: #2c3036;
    color: #cfd3d8;
    border: 1px solid #3c4148;
    border-radius: 3px;
    padding: 6px 8px;
    margin-top: 2px;
}
QToolBox::tab:selected {
    background: #39414a;
    color: #ffffff;
    border-color: #5b9bd5;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #444950;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 12px;
    margin: -5px 0;
    background: #9aa4af;
    border-radius: 6px;
}
QStatusBar {
    border-top: 1px solid #353a40;
}
QDockWidget::title {
    background: #282b30;
    padding: 5px 7px;
}
"""


def _apply_theme(app: QtWidgets.QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(_STYLE_SHEET)


def _toolbar(window) -> QtWidgets.QToolBar | None:
    for toolbar in window.findChildren(QtWidgets.QToolBar):
        if toolbar.windowTitle() == "Main":
            return toolbar
    return None


def _bottom_toolbar(window) -> QtWidgets.QToolBar | None:
    for toolbar in window.findChildren(QtWidgets.QToolBar):
        if toolbar.windowTitle() == "Navigation":
            return toolbar
    return None


def _action_by_text(toolbar: QtWidgets.QToolBar, text: str, occurrence: int = 0):
    matches = [action for action in toolbar.actions() if action.text() == text]
    return matches[occurrence] if occurrence < len(matches) else None


def _sync_mode_actions(window, actions: list[QtGui.QAction]) -> None:
    mode = int(getattr(window.editor, "mode", 0)) % 3
    for index, action in enumerate(actions):
        action.setChecked(index == mode)


def _polish_toolbar(window) -> None:
    toolbar = _toolbar(window)
    if toolbar is None:
        return

    toolbar.setMovable(False)
    toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)

    first = _action_by_text(toolbar, "↶")
    stop = _action_by_text(toolbar, "■")
    play = _action_by_text(toolbar, "▶", 0)
    back = _action_by_text(toolbar, "◀")
    forward = _action_by_text(toolbar, "▶", 1)
    midi_import = _action_by_text(toolbar, "MIDI↓")
    midi_export = _action_by_text(toolbar, "MIDI")
    adofai_export = _action_by_text(toolbar, "Hz")
    spec = _action_by_text(toolbar, "Spec")
    notes = _action_by_text(toolbar, "Note")
    both = _action_by_text(toolbar, "Both")

    if first is not None:
        try:
            first.triggered.disconnect()
        except (RuntimeError, TypeError):
            pass
        first.triggered.connect(window.open_audio)
        first.setText(tr("ui.toolbar.open"))
        first.setToolTip(tr("dialog.open_audio.title"))

    if stop is not None:
        stop.setText("■")
        stop.setToolTip(tr("toolbar.stop"))
    if play is not None:
        play.setText("▶")
        play.setToolTip(tr("toolbar.play"))
    if back is not None:
        back.setText("−1s")
        back.setToolTip(tr("toolbar.back"))
    if forward is not None:
        forward.setText("+1s")
        forward.setToolTip(tr("toolbar.forward"))
    if midi_import is not None:
        midi_import.setText("MIDI ↓")
        midi_import.setToolTip(tr("dialog.import_midi.title"))
    if midi_export is not None:
        midi_export.setText("MIDI ↑")
        midi_export.setToolTip(tr("dialog.export_midi.title"))
    if adofai_export is not None:
        adofai_export.setText("ADOFAI ↑")
        adofai_export.setToolTip(tr("dialog.export_adofai.title"))

    mode_actions = [action for action in (spec, notes, both) if action is not None]
    if len(mode_actions) == 3:
        labels = [
            tr("ui.toolbar.mode_spec"),
            tr("ui.toolbar.mode_notes"),
            tr("ui.toolbar.mode_both"),
        ]
        group = QtGui.QActionGroup(window)
        group.setExclusive(True)
        for action, label in zip(mode_actions, labels):
            action.setText(label)
            action.setCheckable(True)
            group.addAction(action)
            action.triggered.connect(lambda _checked=False: _sync_mode_actions(window, mode_actions))
        window._ui_mode_action_group = group

        original_set_mode = window.editor.set_mode

        def set_mode_with_ui(mode: int) -> None:
            original_set_mode(mode)
            _sync_mode_actions(window, mode_actions)

        window.editor.set_mode = set_mode_with_ui
        _sync_mode_actions(window, mode_actions)

    if hasattr(window, "time_label"):
        window.time_label.setMinimumWidth(132)
        window.time_label.setMaximumWidth(160)
        window.time_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        window.time_label.setToolTip(tr("ui.toolbar.time_tip"))


def _clear_layout(layout: QtWidgets.QLayout, keep: set[QtWidgets.QWidget]) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None and widget not in keep:
            widget.deleteLater()


def _polish_bottom_navigation(window) -> None:
    toolbar = _bottom_toolbar(window)
    if toolbar is None or not hasattr(window, "time_slider"):
        return

    bar = window.time_slider.parentWidget()
    layout = bar.layout() if bar is not None else None
    if not isinstance(layout, QtWidgets.QGridLayout):
        return

    controls = {
        window.time_slider,
        window.visible_sec,
        window.pitch_bottom,
        window.pitch_down_button,
        window.pitch_up_button,
        window.visible_notes,
        window.fit_button,
    }
    _clear_layout(layout, controls)

    layout.setContentsMargins(8, 4, 8, 4)
    layout.setHorizontalSpacing(6)
    layout.setVerticalSpacing(3)

    timeline_label = QtWidgets.QLabel(tr("ui.nav.timeline"), bar)
    window_label = QtWidgets.QLabel(tr("ui.nav.window"), bar)
    pitch_label = QtWidgets.QLabel(tr("ui.nav.pitch"), bar)
    range_label = QtWidgets.QLabel(tr("ui.nav.range"), bar)

    window.pitch_down_button.setText("−12")
    window.pitch_up_button.setText("+12")
    window.pitch_down_button.setToolTip(tr("ui.nav.pitch_down_tip"))
    window.pitch_up_button.setToolTip(tr("ui.nav.pitch_up_tip"))
    window.fit_button.setText(tr("ui.nav.fit"))

    window.time_slider.setMinimumWidth(280)
    window.visible_sec.setMinimumWidth(80)
    window.pitch_bottom.setMinimumWidth(62)
    window.visible_notes.setMinimumWidth(62)

    layout.addWidget(timeline_label, 0, 0)
    layout.addWidget(window.time_slider, 0, 1, 1, 9)
    layout.addWidget(window_label, 1, 0)
    layout.addWidget(window.visible_sec, 1, 1)
    layout.addWidget(pitch_label, 1, 2)
    layout.addWidget(window.pitch_bottom, 1, 3)
    layout.addWidget(window.pitch_down_button, 1, 4)
    layout.addWidget(window.pitch_up_button, 1, 5)
    layout.addWidget(range_label, 1, 6)
    layout.addWidget(window.visible_notes, 1, 7)
    layout.addWidget(window.fit_button, 1, 8)
    layout.setColumnStretch(9, 1)

    toolbar.setMovable(False)


def _page_index_for_widget(toolbox: QtWidgets.QToolBox, widget: QtWidgets.QWidget) -> int:
    for index in range(toolbox.count()):
        page = toolbox.widget(index)
        if page is widget or page.isAncestorOf(widget):
            return index
    return -1


def _form_for(widget: QtWidgets.QWidget) -> QtWidgets.QFormLayout | None:
    parent = widget.parentWidget()
    while parent is not None:
        layout = parent.layout()
        if isinstance(layout, QtWidgets.QFormLayout):
            return layout
        parent = parent.parentWidget()
    return None


def _set_form_label(field: QtWidgets.QWidget, text: str) -> None:
    form = _form_for(field)
    if form is None:
        return
    label = form.labelForField(field)
    if isinstance(label, QtWidgets.QLabel):
        label.setText(text)


def _remove_form_field(form: QtWidgets.QFormLayout, field: QtWidgets.QWidget) -> None:
    label = form.labelForField(field)
    if label is not None:
        form.removeWidget(label)
        label.deleteLater()
    form.removeWidget(field)


def _new_form_page() -> tuple[QtWidgets.QWidget, QtWidgets.QFormLayout]:
    page = QtWidgets.QWidget()
    form = QtWidgets.QFormLayout(page)
    form.setContentsMargins(8, 8, 8, 8)
    form.setHorizontalSpacing(8)
    form.setVerticalSpacing(6)
    form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    return page, form


def _split_analysis_page(window) -> None:
    toolbox = window.settings_toolbox
    if getattr(window, "_ui_analysis_page", None) is not None:
        return

    view_index = _page_index_for_widget(toolbox, window.analysis_profile)
    if view_index < 0:
        return
    view_page = toolbox.widget(view_index)
    view_form = view_page.layout()
    if not isinstance(view_form, QtWidgets.QFormLayout):
        return

    analysis_page, analysis_form = _new_form_page()
    for field, key in (
        (window.analysis_profile, "ui.field.analysis_profile"),
        (window.cqt_resolution, "ui.field.cqt_resolution"),
    ):
        _remove_form_field(view_form, field)
        analysis_form.addRow(tr(key), field)

    toolbox.insertItem(view_index + 1, analysis_page, tr("ui.settings.analysis"))
    window._ui_analysis_page = analysis_page


def _localize_settings(window) -> None:
    toolbox = window.settings_toolbox
    window.settings_dock.setWindowTitle(tr("ui.settings.title"))
    if hasattr(window, "settings_dock_toggle_action"):
        window.settings_dock_toggle_action.setText(tr("ui.settings.panel_menu"))

    category_fields = (
        (window.volume, "ui.settings.playback"),
        (window.export_octave, "ui.settings.export_pitch"),
        (window.grid_enabled, "ui.settings.timing"),
        (window.contrast, "ui.settings.display"),
        (window.analysis_profile, "ui.settings.analysis"),
        (window.curve_shape, "ui.settings.curve"),
    )
    for field, key in category_fields:
        index = _page_index_for_widget(toolbox, field)
        if index >= 0:
            toolbox.setItemText(index, tr(key))

    form_labels = (
        (window.volume, "ui.field.song_volume"),
        (window.playback_speed, "ui.field.speed"),
        (window.note_sound_enabled, "ui.field.note_preview"),
        (window.note_vol, "ui.field.note_volume"),
        (window.note_octave, "ui.field.preview_octave"),
        (window.note_instrument, "ui.field.preview_sound"),
        (window.export_octave, "ui.field.export_octave"),
        (window.export_semitone, "ui.field.export_semitone"),
        (window.grid_enabled, "ui.field.grid"),
        (window.metro_enabled, "ui.field.metronome"),
        (window.grid_bpm, "ui.field.bpm"),
        (window.grid_offset_ms, "ui.field.offset"),
        (window.metro_vol, "ui.field.metronome_volume"),
        (window.snap_enabled, "ui.field.snap"),
        (window.snap_div, "ui.field.snap_division"),
        (window.contrast, "ui.field.contrast"),
        (window.gamma, "ui.field.gamma"),
        (window.enhance, "ui.field.enhance"),
        (window.display_mode, "ui.field.display"),
        (window.harmonics, "ui.field.harmonics"),
        (window.cmap, "ui.field.colormap"),
        (window.analysis_profile, "ui.field.analysis_profile"),
        (window.cqt_resolution, "ui.field.cqt_resolution"),
        (window.curve_shape, "ui.field.curve"),
        (window.curve_interpolation, "ui.field.interpolation"),
        (window.target_angle, "ui.field.target_angle"),
    )
    for field, key in form_labels:
        _set_form_label(field, tr(key))

    window.note_sound_enabled.setText(tr("ui.button.enable_note_preview"))
    window.apply_interpolation_button.setText(tr("ui.button.apply_interp"))
    window.apply_target_angle_button.setText(tr("ui.button.apply_angle"))
    window.clear_target_angle_button.setText(tr("ui.button.clear_angle"))

    window.note_sound_enabled.setToolTip(tr("ui.tip.note_preview"))
    window.note_octave.setToolTip(tr("ui.tip.preview_octave"))
    window.note_instrument.setToolTip(tr("ui.tip.preview_sound"))
    window.export_octave.setToolTip(tr("ui.tip.export_octave"))
    window.export_semitone.setToolTip(tr("ui.tip.export_semitone"))
    window.snap_div.setToolTip(tr("ui.tip.snap_division"))
    window.display_mode.setToolTip(tr("ui.tip.display_mode"))
    window.analysis_profile.setToolTip(tr("ui.tip.analysis_profile"))
    window.cqt_resolution.setToolTip(tr("ui.tip.cqt_resolution"))
    window.curve_shape.setToolTip(tr("ui.tip.curve_shape"))
    window.curve_interpolation.setToolTip(tr("ui.tip.curve_interpolation"))
    window.apply_interpolation_button.setToolTip(tr("ui.tip.apply_interp"))
    window.target_angle.setToolTip(tr("ui.tip.target_angle"))
    window.apply_target_angle_button.setToolTip(tr("ui.tip.apply_angle"))
    window.clear_target_angle_button.setToolTip(tr("ui.tip.clear_angle"))


def _refresh_dependencies(window) -> None:
    note_preview = window.note_sound_enabled.isChecked()
    for widget in (window.note_vol, window.note_octave, window.note_instrument):
        widget.setEnabled(note_preview)

    window.metro_vol.setEnabled(window.metro_enabled.isChecked())
    window.snap_div.setEnabled(window.snap_enabled.isChecked())


def _connect_dependencies(window) -> None:
    window.note_sound_enabled.toggled.connect(lambda _checked: _refresh_dependencies(window))
    window.metro_enabled.toggled.connect(lambda _checked: _refresh_dependencies(window))
    window.snap_enabled.toggled.connect(lambda _checked: _refresh_dependencies(window))
    _refresh_dependencies(window)


def polish_main_window(window) -> None:
    if getattr(window, "_ui_polished", False):
        return
    if not hasattr(window, "editor") or not hasattr(window, "settings_toolbox"):
        return

    window._ui_polished = True
    window.setMinimumSize(980, 620)

    _polish_toolbar(window)
    _polish_bottom_navigation(window)

    window.settings_toolbox.setMinimumWidth(260)
    window.settings_dock.setMinimumWidth(260)
    window.settings_dock.resize(270, max(400, window.settings_dock.height()))

    _split_analysis_page(window)
    _localize_settings(window)
    _connect_dependencies(window)


def _polish_open_windows(app: QtWidgets.QApplication) -> None:
    for window in app.topLevelWidgets():
        if isinstance(window, QtWidgets.QMainWindow) and window.__class__.__name__ == "MainWindow":
            polish_main_window(window)


def install_ui_polish() -> None:
    """Install the compact UI layer without changing editor/audio/export logic."""
    if getattr(QtWidgets, "_adopy_ui_polish_installed", False):
        return
    QtWidgets._adopy_ui_polish_installed = True

    original_application = QtWidgets.QApplication
    existing = original_application.instance()
    if existing is not None:
        _apply_theme(existing)
        QtCore.QTimer.singleShot(0, lambda: _polish_open_windows(existing))
        return

    class PolishedApplication(original_application):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            _apply_theme(self)

        def exec(self) -> int:
            _polish_open_windows(self)
            return super().exec()

    QtWidgets.QApplication = PolishedApplication
