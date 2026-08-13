from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

import ui_polish as base_ui
from i18n import tr


_STYLE_SHEET = r"""
QWidget {
    color: #e7eaf0;
    font-size: 10pt;
}
QMainWindow, QDialog {
    background: #0d1015;
}
QMenuBar {
    background: #10141a;
    color: #b9c0cc;
    border: 0;
    padding: 2px 6px;
}
QMenuBar::item {
    background: transparent;
    border-radius: 6px;
    padding: 5px 8px;
}
QMenuBar::item:selected {
    background: #1b2029;
    color: #ffffff;
}
QMenu {
    background: #161a21;
    color: #e7eaf0;
    border: 1px solid #262d38;
    border-radius: 8px;
    padding: 6px;
}
QMenu::item {
    border-radius: 5px;
    padding: 6px 24px 6px 10px;
}
QMenu::item:selected {
    background: #252b36;
}
QMenu::separator {
    height: 1px;
    background: #272e38;
    margin: 5px 8px;
}

QToolBar#PrimaryToolbar {
    background: #10141a;
    border: 0;
    border-bottom: 1px solid #1c222b;
    padding: 6px 10px;
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
    padding-left: 12px;
    padding-right: 12px;
}
QToolBar#PrimaryToolbar QToolButton[role="play"] {
    background: #7657ff;
    color: #ffffff;
    font-weight: 600;
    padding-left: 13px;
    padding-right: 13px;
}
QToolBar#PrimaryToolbar QToolButton[role="play"]:hover {
    background: #8469ff;
}
QToolBar#PrimaryToolbar QToolButton[role="mode"] {
    background: #151a21;
    color: #919aa7;
    border-radius: 7px;
    padding-left: 9px;
    padding-right: 9px;
}
QToolBar#PrimaryToolbar QToolButton[role="mode"]:checked {
    background: #2a2545;
    color: #c9c0ff;
}
QLabel#TransportTime {
    color: #aeb6c2;
    background: #151a21;
    border-radius: 8px;
    padding: 6px 10px;
}

QToolBar#BottomToolbar {
    background: #10141a;
    border: 0;
    border-top: 1px solid #1c222b;
    padding: 0;
}
QWidget#BottomSurface {
    background: transparent;
}
QWidget#BottomSurface QLabel[muted="true"] {
    color: #737d8b;
    font-size: 9pt;
}
QWidget#BottomSurface QPushButton,
QWidget#BottomSurface QSpinBox,
QWidget#BottomSurface QDoubleSpinBox {
    min-height: 26px;
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
    padding: 8px 10px;
    font-weight: 600;
}
QWidget#SettingsShell {
    background: #10141a;
}
QFrame#SettingsTabs {
    background: #151a21;
    border: 1px solid #202732;
    border-radius: 11px;
}
QFrame#SettingsTabs QPushButton {
    background: transparent;
    color: #87919f;
    border: 0;
    border-radius: 7px;
    min-height: 28px;
    padding: 4px 5px;
    font-size: 9pt;
}
QFrame#SettingsTabs QPushButton:hover {
    background: #1d232c;
    color: #dce1e8;
}
QFrame#SettingsTabs QPushButton:checked {
    background: #2a2545;
    color: #c9c0ff;
    font-weight: 600;
}
QStackedWidget#SettingsStack {
    background: transparent;
}
QScrollArea#SettingsScroll {
    background: transparent;
    border: 0;
}
QScrollArea#SettingsScroll > QWidget > QWidget {
    background: transparent;
}
QWidget#SettingsPage {
    background: #151a21;
    border: 1px solid #202732;
    border-radius: 12px;
}
QWidget#SettingsPage QLabel {
    color: #939dab;
}
QWidget#SettingsPage QCheckBox {
    color: #dce1e8;
    spacing: 7px;
}
QWidget#SettingsPage QPushButton,
QWidget#SettingsPage QComboBox,
QWidget#SettingsPage QSpinBox,
QWidget#SettingsPage QDoubleSpinBox,
QWidget#SettingsPage QLineEdit {
    min-height: 28px;
}

QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
    background: #1b2028;
    color: #e7eaf0;
    border: 1px solid #2a323d;
    border-radius: 7px;
    padding: 4px 8px;
    selection-background-color: #7657ff;
}
QPushButton:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover {
    background: #202630;
    border-color: #394352;
}
QPushButton:pressed {
    background: #262d38;
}
QPushButton:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {
    border-color: #7657ff;
}
QPushButton:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled {
    background: #15191f;
    color: #596271;
    border-color: #202630;
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
    color: #e7eaf0;
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
    color: #e7eaf0;
    border: 1px solid #343d49;
    border-radius: 6px;
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
            button.setProperty("role", "open")
        elif text == "▶":
            button.setProperty("role", "play")
        elif action.isCheckable():
            button.setProperty("role", "mode")
        else:
            button.setProperty("role", "normal")
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
    toolbar.setMinimumHeight(74)

    bar = window.time_slider.parentWidget()
    if bar is None:
        return
    bar.setObjectName("BottomSurface")

    for label in bar.findChildren(QtWidgets.QLabel):
        label.setProperty("muted", True)
        _repolish(label)

    window.fit_button.setProperty("role", "ghost")
    window.pitch_down_button.setMinimumWidth(46)
    window.pitch_up_button.setMinimumWidth(46)
    window.fit_button.setMinimumWidth(64)


def _tune_form_layout(page: QtWidgets.QWidget) -> None:
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


def _modernize_settings_panel(window) -> None:
    if getattr(window, "_modern_settings_shell", None) is not None:
        return

    toolbox = window.settings_toolbox
    count = toolbox.count()
    if count <= 0:
        return

    current = max(0, toolbox.currentIndex())
    titles = [toolbox.itemText(index) for index in range(count)]
    pages: list[QtWidgets.QWidget] = []
    for _ in range(count):
        page = toolbox.widget(0)
        toolbox.removeItem(0)
        pages.append(page)

    shell = QtWidgets.QWidget(window.settings_dock)
    shell.setObjectName("SettingsShell")
    root = QtWidgets.QVBoxLayout(shell)
    root.setContentsMargins(10, 10, 10, 10)
    root.setSpacing(10)

    tabs_frame = QtWidgets.QFrame(shell)
    tabs_frame.setObjectName("SettingsTabs")
    tabs_layout = QtWidgets.QGridLayout(tabs_frame)
    tabs_layout.setContentsMargins(4, 4, 4, 4)
    tabs_layout.setHorizontalSpacing(4)
    tabs_layout.setVerticalSpacing(4)

    stack = QtWidgets.QStackedWidget(shell)
    stack.setObjectName("SettingsStack")

    group = QtWidgets.QButtonGroup(shell)
    group.setExclusive(True)
    buttons: list[QtWidgets.QPushButton] = []

    for index, (title, page) in enumerate(zip(titles, pages)):
        button = QtWidgets.QPushButton(title, tabs_frame)
        button.setCheckable(True)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(
            lambda _checked=False, page_index=index: stack.setCurrentIndex(page_index)
        )
        group.addButton(button, index)
        buttons.append(button)
        tabs_layout.addWidget(button, index // 3, index % 3)

        page.setObjectName("SettingsPage")
        page.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        _tune_form_layout(page)

        scroll = QtWidgets.QScrollArea(stack)
        scroll.setObjectName("SettingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        stack.addWidget(scroll)

    if buttons:
        current = min(current, len(buttons) - 1)
        buttons[current].setChecked(True)
        stack.setCurrentIndex(current)

    root.addWidget(tabs_frame)
    root.addWidget(stack, 1)

    window.settings_dock.setWidget(shell)
    window.settings_dock.setMinimumWidth(310)
    window.settings_dock.resize(330, max(440, window.settings_dock.height()))
    window._modern_settings_shell = shell
    window._modern_settings_stack = stack
    window._modern_settings_buttons = buttons
    window._modern_settings_group = group

    toolbox.deleteLater()


def polish_main_window(window) -> None:
    if getattr(window, "_modern_ui_polished", False):
        return
    if not hasattr(window, "editor") or not hasattr(window, "settings_toolbox"):
        return

    window._modern_ui_polished = True
    window.setMinimumSize(1000, 640)

    base_ui._polish_toolbar(window)
    base_ui._polish_bottom_navigation(window)
    base_ui._split_analysis_page(window)
    base_ui._localize_settings(window)
    base_ui._connect_dependencies(window)

    _mark_toolbar(window)
    _mark_bottom_navigation(window)
    _modernize_settings_panel(window)


def _polish_open_windows(app: QtWidgets.QApplication) -> None:
    for window in app.topLevelWidgets():
        if isinstance(window, QtWidgets.QMainWindow) and window.__class__.__name__ == "MainWindow":
            polish_main_window(window)


def install_modern_ui() -> None:
    """Install the modern UI shell without changing editor/audio/export behavior."""
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
