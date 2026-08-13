from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

import ui_polish as base_ui
from i18n import tr


_STYLE_SHEET = r"""
QWidget {
    color: #e8ebf2;
    font-size: 10pt;
}
QMainWindow, QDialog {
    background: #0d1015;
}
QMenuBar {
    background: #10141a;
    color: #b8c0cc;
    border: 0;
    padding: 2px 6px;
}
QMenuBar::item {
    background: transparent;
    border-radius: 6px;
    padding: 5px 8px;
}
QMenuBar::item:selected {
    background: #1a2028;
    color: #ffffff;
}
QMenu {
    background: #161b22;
    color: #e8ebf2;
    border: 1px solid #262e39;
    padding: 6px;
}
QMenu::item {
    border-radius: 5px;
    padding: 6px 24px 6px 10px;
}
QMenu::item:selected {
    background: #242b35;
}
QMenu::separator {
    height: 1px;
    background: #29313c;
    margin: 5px 8px;
}

QToolBar#PrimaryToolbar {
    background: #10141a;
    border: 0;
    border-bottom: 1px solid #1d232c;
    padding: 7px 10px;
    spacing: 4px;
}
QToolBar#PrimaryToolbar::separator {
    background: transparent;
    width: 10px;
}
QToolBar#PrimaryToolbar QToolButton {
    background: transparent;
    color: #aeb6c2;
    border: 0;
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 28px;
}
QToolBar#PrimaryToolbar QToolButton:hover {
    background: #1a2028;
    color: #ffffff;
}
QToolBar#PrimaryToolbar QToolButton:pressed {
    background: #252c36;
}
QToolBar#PrimaryToolbar QToolButton[role="open"] {
    background: #1b2029;
    color: #f3f5f8;
}
QToolBar#PrimaryToolbar QToolButton[role="play"] {
    background: #7657ff;
    color: #ffffff;
    font-weight: 600;
    padding-left: 14px;
    padding-right: 14px;
}
QToolBar#PrimaryToolbar QToolButton[role="play"]:hover {
    background: #866dff;
}
QToolBar#PrimaryToolbar QToolButton[role="mode"] {
    background: #151a21;
    color: #929ba8;
}
QToolBar#PrimaryToolbar QToolButton[role="mode"]:checked {
    background: #2b2646;
    color: #d0c8ff;
}
QLabel#TransportTime {
    color: #b4bdc9;
    background: #151a21;
    border-radius: 8px;
    padding: 6px 10px;
}

QToolBar#BottomToolbar {
    background: #10141a;
    border: 0;
    border-top: 1px solid #1d232c;
    padding: 0;
}
QWidget#BottomSurface {
    background: transparent;
}
QWidget#BottomSurface QLabel[muted="true"] {
    color: #747f8e;
    font-size: 9pt;
}

QDockWidget {
    background: #10141a;
    color: #dce1e8;
    border: 0;
}
QDockWidget::title {
    background: #10141a;
    color: #dce1e8;
    border-bottom: 1px solid #1d232c;
    padding: 9px 11px;
    font-weight: 600;
}
QToolBox#ModernSettingsToolBox {
    background: #10141a;
}
QToolBox#ModernSettingsToolBox::tab {
    background: transparent;
    color: #87919f;
    border: 0;
    border-radius: 8px;
    padding: 8px 10px;
    margin: 2px 8px;
    font-weight: 500;
}
QToolBox#ModernSettingsToolBox::tab:hover {
    background: #181e26;
    color: #dce1e8;
}
QToolBox#ModernSettingsToolBox::tab:selected {
    background: #292441;
    color: #d0c8ff;
    font-weight: 600;
}
QToolBox#ModernSettingsToolBox QWidget[settingsPage="true"] {
    background: #151a21;
    border: 0;
    border-radius: 12px;
}
QToolBox#ModernSettingsToolBox QWidget[settingsPage="true"] QLabel {
    color: #929cab;
}

QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
    background: #1b2028;
    color: #e8ebf2;
    border: 1px solid #2a323d;
    border-radius: 7px;
    padding: 4px 8px;
    min-height: 24px;
    selection-background-color: #7657ff;
}
QPushButton:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover {
    background: #202630;
    border-color: #3a4553;
}
QPushButton:pressed {
    background: #272e39;
}
QPushButton:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {
    border-color: #7657ff;
}
QPushButton:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled {
    background: #15191f;
    color: #5c6572;
    border-color: #202630;
}

QCheckBox {
    spacing: 7px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
}
QCheckBox::indicator:unchecked {
    background: #181d24;
    border: 1px solid #3a4350;
    border-radius: 5px;
}
QCheckBox::indicator:checked {
    background: #7657ff;
    border: 1px solid #7657ff;
    border-radius: 5px;
}

QSlider::groove:horizontal {
    height: 4px;
    background: #262d37;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #7657ff;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -5px 0;
    background: #d7d2ff;
    border: 2px solid #7657ff;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #ffffff;
}

QComboBox::drop-down {
    border: 0;
    width: 22px;
}
QComboBox QAbstractItemView {
    background: #171c23;
    color: #e8ebf2;
    border: 1px solid #2a323d;
    selection-background-color: #2a2545;
    selection-color: #ffffff;
    outline: 0;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #303844;
    min-height: 28px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #414b5a;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0;
}

QStatusBar {
    background: #0f1318;
    color: #778291;
    border-top: 1px solid #1b2129;
    font-size: 9pt;
}
QToolTip {
    background: #1a2028;
    color: #e8ebf2;
    border: 1px solid #343d49;
    padding: 5px 7px;
}
"""


def _apply_theme(app: QtWidgets.QApplication) -> None:
    app.setStyle("Fusion")
    font = app.font()
    if font.pointSizeF() < 9.5:
        font.setPointSizeF(9.5)
        app.setFont(font)
    app.setStyleSheet(_STYLE_SHEET)


def _repolish(widget: QtWidgets.QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def _mark_toolbar(window) -> None:
    toolbar = base_ui._toolbar(window)
    if toolbar is None:
        return

    toolbar.setObjectName("PrimaryToolbar")
    toolbar.setMovable(False)
    toolbar.setFloatable(False)
    toolbar.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.PreventContextMenu)
    toolbar.setMinimumHeight(46)

    for action in toolbar.actions():
        button = toolbar.widgetForAction(action)
        if not isinstance(button, QtWidgets.QToolButton):
            continue

        text = action.text()
        if text == tr("ui.toolbar.open"):
            role = "open"
        elif text == "▶":
            role = "play"
        elif action.isCheckable():
            role = "mode"
        else:
            role = "normal"
        button.setProperty("role", role)
        _repolish(button)

    if hasattr(window, "time_label"):
        window.time_label.setObjectName("TransportTime")
        fixed = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        fixed.setPointSizeF(max(9.0, fixed.pointSizeF()))
        window.time_label.setFont(fixed)


def _mark_bottom_navigation(window) -> None:
    toolbar = base_ui._bottom_toolbar(window)
    if toolbar is None or not hasattr(window, "time_slider"):
        return

    toolbar.setObjectName("BottomToolbar")
    toolbar.setMovable(False)
    toolbar.setFloatable(False)
    toolbar.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.PreventContextMenu)
    toolbar.setMinimumHeight(72)

    bar = window.time_slider.parentWidget()
    if bar is None:
        return
    bar.setObjectName("BottomSurface")

    for label in bar.findChildren(QtWidgets.QLabel):
        label.setProperty("muted", True)
        _repolish(label)

    window.pitch_down_button.setMinimumWidth(46)
    window.pitch_up_button.setMinimumWidth(46)
    window.fit_button.setMinimumWidth(64)


def _mark_settings(window) -> None:
    toolbox = window.settings_toolbox
    toolbox.setObjectName("ModernSettingsToolBox")
    toolbox.setMinimumWidth(280)
    window.settings_dock.setMinimumWidth(280)
    window.settings_dock.resize(300, max(420, window.settings_dock.height()))

    for index in range(toolbox.count()):
        page = toolbox.widget(index)
        if page is None:
            continue
        page.setProperty("settingsPage", True)
        page.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = page.layout()
        if isinstance(layout, QtWidgets.QFormLayout):
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setHorizontalSpacing(12)
            layout.setVerticalSpacing(10)
            layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            layout.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapLongRows)
            layout.setLabelAlignment(
                QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
        _repolish(page)
    _repolish(toolbox)


def polish_main_window(window) -> None:
    if getattr(window, "_modern_ui_polished", False):
        return
    if not hasattr(window, "editor") or not hasattr(window, "settings_toolbox"):
        return

    window._modern_ui_polished = True
    window.setMinimumSize(1000, 640)

    # Keep the proven-safe UI structure from ui_polish. Modernization below is
    # visual only: no page removal, reparenting, replacement, or deleteLater().
    base_ui.polish_main_window(window)
    _mark_toolbar(window)
    _mark_bottom_navigation(window)
    _mark_settings(window)


def _polish_open_windows(app: QtWidgets.QApplication) -> None:
    for window in app.topLevelWidgets():
        if isinstance(window, QtWidgets.QMainWindow) and window.__class__.__name__ == "MainWindow":
            polish_main_window(window)


def install_modern_ui() -> None:
    """Install a visual-only modern shell without changing widget ownership."""
    if getattr(QtWidgets, "_adopy_modern_ui_installed", False):
        return
    QtWidgets._adopy_modern_ui_installed = True

    original_application = QtWidgets.QApplication
    existing = original_application.instance()
    if existing is not None:
        _apply_theme(existing)
        QtCore.QTimer.singleShot(0, lambda: _polish_open_windows(existing))
        return

    class ModernApplication(original_application):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            _apply_theme(self)

        def exec(self) -> int:
            _polish_open_windows(self)
            return super().exec()

    QtWidgets.QApplication = ModernApplication
