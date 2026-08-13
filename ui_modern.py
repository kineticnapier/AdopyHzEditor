from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

import ui_polish as base_ui
from i18n import tr


_STYLE_SHEET = r"""
QWidget {
    color: #e8edf3;
    font-size: 10pt;
}
QMainWindow, QDialog {
    background: #20242a;
}

/* Audacity-like application chrome */
QMenuBar {
    background: #30353c;
    color: #edf1f5;
    border-bottom: 1px solid #181b1f;
    padding: 2px 5px;
}
QMenuBar::item {
    background: transparent;
    padding: 5px 8px;
    border-radius: 3px;
}
QMenuBar::item:selected {
    background: #46505b;
}
QMenu {
    background: #30353c;
    color: #f1f4f7;
    border: 1px solid #171a1e;
    padding: 5px;
}
QMenu::item {
    padding: 6px 24px 6px 10px;
    border-radius: 3px;
}
QMenu::item:selected {
    background: #1769aa;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background: #50565e;
    margin: 5px 7px;
}

/* Main transport / tools */
QToolBar#PrimaryToolbar {
    background: #3a4047;
    border: 0;
    border-bottom: 1px solid #191c20;
    padding: 7px 9px;
    spacing: 4px;
}
QToolBar#PrimaryToolbar::separator {
    background: #59616a;
    width: 1px;
    margin: 7px 7px;
}
QToolBar#PrimaryToolbar QToolButton {
    background: #454c54;
    color: #f0f3f6;
    border: 1px solid #22262b;
    border-radius: 5px;
    padding: 6px 9px;
    min-height: 30px;
}
QToolBar#PrimaryToolbar QToolButton:hover {
    background: #555e68;
    border-color: #68737f;
}
QToolBar#PrimaryToolbar QToolButton:pressed {
    background: #2c3238;
}
QToolBar#PrimaryToolbar QToolButton[role="open"] {
    background: #3d4650;
}
QToolBar#PrimaryToolbar QToolButton[role="play"] {
    background: #2e8b57;
    border-color: #1f6840;
    color: #ffffff;
    font-weight: 700;
    min-width: 44px;
}
QToolBar#PrimaryToolbar QToolButton[role="play"]:hover {
    background: #39a86b;
}
QToolBar#PrimaryToolbar QToolButton[role="mode"] {
    background: #333940;
    color: #c6cdd5;
}
QToolBar#PrimaryToolbar QToolButton[role="mode"]:checked {
    background: #1769aa;
    border-color: #0d4f85;
    color: #ffffff;
    font-weight: 600;
}
QLabel#TransportTime {
    color: #f6f8fa;
    background: #23272d;
    border: 1px solid #171a1e;
    border-radius: 4px;
    padding: 7px 10px;
}

/* Bottom navigation resembles a compact Audacity toolbar strip */
QToolBar#BottomToolbar {
    background: #343a41;
    border: 0;
    border-top: 1px solid #191c20;
    padding: 0;
}
QWidget#BottomSurface {
    background: transparent;
}
QWidget#BottomSurface QLabel[muted="true"] {
    color: #c4cbd3;
    font-size: 9pt;
}

/* Settings / inspector */
QDockWidget {
    background: #2b3036;
    color: #f0f3f6;
    border: 0;
}
QDockWidget::title {
    background: #343a41;
    color: #ffffff;
    border-bottom: 1px solid #1b1f23;
    padding: 8px 10px;
    font-weight: 700;
}
QToolBox#ModernSettingsToolBox {
    background: #2b3036;
}
QToolBox#ModernSettingsToolBox::tab {
    background: #3a4047;
    color: #e5e9ee;
    border: 1px solid #22262b;
    border-radius: 4px;
    padding: 8px 10px;
    margin: 2px 7px;
    min-height: 22px;
    font-weight: 600;
}
QToolBox#ModernSettingsToolBox::tab:hover {
    background: #454d56;
}
QToolBox#ModernSettingsToolBox::tab:selected {
    background: #1769aa;
    border-color: #0d4f85;
    color: #ffffff;
}
QToolBox#ModernSettingsToolBox QWidget[settingsPage="true"] {
    background: #272c32;
    border: 0;
}
QToolBox#ModernSettingsToolBox QWidget[settingsPage="true"] QLabel {
    color: #e3e7ec;
}

/* Controls */
QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
    background: #3a4148;
    color: #f2f4f7;
    border: 1px solid #171a1e;
    border-radius: 4px;
    padding: 4px 7px;
    min-height: 26px;
    selection-background-color: #1769aa;
}
QPushButton:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover {
    background: #48515a;
    border-color: #697580;
}
QPushButton:pressed {
    background: #2e343a;
}
QPushButton:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {
    border-color: #4aa8ff;
}
QPushButton:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled {
    background: #30353b;
    color: #7f8994;
    border-color: #252a2f;
}

QCheckBox {
    spacing: 7px;
    min-height: 24px;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
}
QCheckBox::indicator:unchecked {
    background: #30363d;
    border: 1px solid #7b8691;
    border-radius: 3px;
}
QCheckBox::indicator:checked {
    background: #1769aa;
    border: 1px solid #4aa8ff;
    border-radius: 3px;
}

QSlider::groove:horizontal {
    height: 5px;
    background: #20252a;
    border: 1px solid #111417;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #318bd0;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 14px;
    margin: -5px 0;
    background: #d9e6f2;
    border: 1px solid #0c5288;
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
    background: #343a41;
    color: #eef2f6;
    border: 1px solid #181b1f;
    selection-background-color: #1769aa;
    selection-color: #ffffff;
    outline: 0;
}

QScrollBar:vertical {
    background: #252a30;
    width: 11px;
    margin: 1px;
}
QScrollBar::handle:vertical {
    background: #58626d;
    min-height: 28px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #6b7783;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0;
}

QStatusBar {
    background: #30353c;
    color: #c2c9d1;
    border-top: 1px solid #191c20;
    font-size: 9pt;
}
QToolTip {
    background: #20252a;
    color: #ffffff;
    border: 1px solid #697580;
    padding: 5px 7px;
}
"""


def _apply_theme(app: QtWidgets.QApplication) -> None:
    app.setStyle("Fusion")
    font = app.font()
    if font.pointSizeF() < 10.0:
        font.setPointSizeF(10.0)
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
    toolbar.setMinimumHeight(50)

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
        fixed.setPointSizeF(max(10.0, fixed.pointSizeF()))
        window.time_label.setFont(fixed)
        window.time_label.setMinimumWidth(150)


def _mark_bottom_navigation(window) -> None:
    toolbar = base_ui._bottom_toolbar(window)
    if toolbar is None or not hasattr(window, "time_slider"):
        return

    toolbar.setObjectName("BottomToolbar")
    toolbar.setMovable(False)
    toolbar.setFloatable(False)
    toolbar.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.PreventContextMenu)
    toolbar.setMinimumHeight(74)

    bar = window.time_slider.parentWidget()
    if bar is None:
        return
    bar.setObjectName("BottomSurface")

    for label in bar.findChildren(QtWidgets.QLabel):
        label.setProperty("muted", True)
        label.setMinimumHeight(24)
        _repolish(label)

    window.pitch_down_button.setMinimumWidth(48)
    window.pitch_up_button.setMinimumWidth(48)
    window.fit_button.setMinimumWidth(68)


def _fix_form_text(layout: QtWidgets.QFormLayout) -> None:
    layout.setContentsMargins(14, 12, 14, 14)
    layout.setHorizontalSpacing(14)
    layout.setVerticalSpacing(9)
    layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    layout.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.DontWrapRows)
    layout.setLabelAlignment(
        QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
    )
    layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

    for row in range(layout.rowCount()):
        label_item = layout.itemAt(row, QtWidgets.QFormLayout.ItemRole.LabelRole)
        field_item = layout.itemAt(row, QtWidgets.QFormLayout.ItemRole.FieldRole)

        if label_item is not None:
            label = label_item.widget()
            if isinstance(label, QtWidgets.QLabel):
                label.setWordWrap(False)
                label.setMinimumHeight(28)
                label.setMinimumWidth(112)
                label.setAlignment(
                    QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
                )

        if field_item is not None:
            field = field_item.widget()
            if field is not None:
                field.setMinimumHeight(max(28, field.minimumHeight()))


def _mark_settings(window) -> None:
    toolbox = window.settings_toolbox
    toolbox.setObjectName("ModernSettingsToolBox")

    # The old 280 px dock was the main source of crushed form text.
    toolbox.setMinimumWidth(350)
    window.settings_dock.setMinimumWidth(350)
    window.settings_dock.resize(380, max(460, window.settings_dock.height()))

    for index in range(toolbox.count()):
        page = toolbox.widget(index)
        if page is None:
            continue

        page.setProperty("settingsPage", True)
        page.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = page.layout()
        if isinstance(layout, QtWidgets.QFormLayout):
            _fix_form_text(layout)

        _repolish(page)

    _repolish(toolbox)


def polish_main_window(window) -> None:
    if getattr(window, "_modern_ui_polished", False):
        return
    if not hasattr(window, "editor") or not hasattr(window, "settings_toolbox"):
        return

    window._modern_ui_polished = True
    window.setMinimumSize(1060, 660)

    # Keep widget ownership/layout structure intact. This layer only styles and
    # adjusts safe sizing properties.
    base_ui.polish_main_window(window)
    _mark_toolbar(window)
    _mark_bottom_navigation(window)
    _mark_settings(window)


def _polish_open_windows(app: QtWidgets.QApplication) -> None:
    for window in app.topLevelWidgets():
        if isinstance(window, QtWidgets.QMainWindow) and window.__class__.__name__ == "MainWindow":
            polish_main_window(window)


def install_modern_ui() -> None:
    """Install the Audacity-inspired visual shell without reparenting widgets."""
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
