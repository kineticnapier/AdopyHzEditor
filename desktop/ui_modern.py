from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

import desktop.ui_polish as base_ui
from i18n import tr

_STYLE_SHEET = r"""
QWidget { color: #eef2f6; font-size: 10pt; }
QMainWindow, QDialog { background: #20242a; }
QMenuBar { background: #30353c; color: #edf1f5; border-bottom: 1px solid #181b1f; padding: 2px 5px; }
QMenuBar::item { background: transparent; padding: 5px 8px; border-radius: 3px; }
QMenuBar::item:selected { background: #46505b; }
QMenu { background: #30353c; color: #f1f4f7; border: 1px solid #171a1e; padding: 5px; }
QMenu::item { padding: 6px 24px 6px 10px; border-radius: 3px; }
QMenu::item:selected { background: #1769aa; color: #ffffff; }
QMenu::separator { height: 1px; background: #50565e; margin: 5px 7px; }
QToolBar#PrimaryToolbar { background: #3a4047; border: 0; border-bottom: 1px solid #191c20; padding: 7px 9px; spacing: 4px; }
QToolBar#PrimaryToolbar::separator { background: #59616a; width: 1px; margin: 7px 7px; }
QToolBar#PrimaryToolbar QToolButton { background: #454c54; color: #f0f3f6; border: 1px solid #22262b; border-radius: 5px; padding: 6px 9px; min-height: 30px; }
QToolBar#PrimaryToolbar QToolButton:hover { background: #555e68; border-color: #68737f; }
QToolBar#PrimaryToolbar QToolButton:pressed { background: #2c3238; }
QToolBar#PrimaryToolbar QToolButton[role="open"] { background: #3d4650; }
QToolBar#PrimaryToolbar QToolButton[role="play"] { background: #2e8b57; border-color: #1f6840; color: #ffffff; font-weight: 700; min-width: 44px; }
QToolBar#PrimaryToolbar QToolButton[role="play"]:hover { background: #39a86b; }
QToolBar#PrimaryToolbar QToolButton[role="mode"] { background: #333940; color: #c6cdd5; }
QToolBar#PrimaryToolbar QToolButton[role="mode"]:checked { background: #1769aa; border-color: #0d4f85; color: #ffffff; font-weight: 600; }
QLabel#TransportTime { color: #f6f8fa; background: #23272d; border: 1px solid #171a1e; border-radius: 4px; padding: 7px 10px; }
QWidget#AudacityNavBar { background: #343a41; border-top: 1px solid #191c20; }
QWidget#AudacityNavBar QLabel { color: #c4cbd3; min-height: 24px; }
QDockWidget { background: #2b3036; color: #f0f3f6; border: 0; }
QDockWidget::title { background: #343a41; color: #ffffff; border-bottom: 1px solid #1b1f23; padding: 8px 10px; font-weight: 700; }
QWidget#AudacitySettingsShell { background: #272c32; }
QFrame#SettingsCategoryRail { background: #2f343a; border-bottom: 1px solid #171a1e; }
QFrame#SettingsCategoryRail QPushButton { background: transparent; color: #d6dbe1; border: 0; border-radius: 4px; padding: 4px 5px; min-height: 30px; text-align: center; }
QFrame#SettingsCategoryRail QPushButton:hover { background: #454d56; }
QFrame#SettingsCategoryRail QPushButton:checked { background: #1769aa; color: #ffffff; font-weight: 700; }
QToolBox#AudacitySettingsPages { background: #272c32; border: 0; }
QToolBox#AudacitySettingsPages::tab { background: transparent; color: transparent; border: 0; margin: 0; padding: 0; min-height: 0px; max-height: 0px; }
QToolBox#AudacitySettingsPages QWidget[settingsPage="true"] { background: #272c32; border: 0; }
QToolBox#AudacitySettingsPages QWidget[settingsPage="true"] QLabel { color: #e3e7ec; }
QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit { background: #3a4148; color: #f2f4f7; border: 1px solid #171a1e; border-radius: 4px; padding: 4px 7px; min-height: 26px; selection-background-color: #1769aa; }
QPushButton:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover { background: #48515a; border-color: #697580; }
QPushButton:pressed { background: #2e343a; }
QPushButton:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus { border-color: #4aa8ff; }
QPushButton:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled { background: #30353b; color: #7f8994; border-color: #252a2f; }
QCheckBox { spacing: 7px; min-height: 24px; }
QCheckBox::indicator { width: 15px; height: 15px; }
QCheckBox::indicator:unchecked { background: #30363d; border: 1px solid #7b8691; border-radius: 3px; }
QCheckBox::indicator:checked { background: #1769aa; border: 1px solid #4aa8ff; border-radius: 3px; }
QSlider::groove:horizontal { height: 5px; background: #20252a; border: 1px solid #111417; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #318bd0; border-radius: 2px; }
QSlider::handle:horizontal { width: 14px; margin: -5px 0; background: #d9e6f2; border: 1px solid #0c5288; border-radius: 7px; }
QComboBox::drop-down { border: 0; width: 22px; }
QComboBox QAbstractItemView { background: #343a41; color: #eef2f6; border: 1px solid #181b1f; selection-background-color: #1769aa; selection-color: #ffffff; outline: 0; }
QScrollBar:vertical { background: #252a30; width: 11px; margin: 1px; }
QScrollBar::handle:vertical { background: #58626d; min-height: 28px; border-radius: 4px; }
QScrollBar::handle:vertical:hover { background: #6b7783; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; height: 0; }
QStatusBar { background: #30353c; color: #c2c9d1; border-top: 1px solid #191c20; font-size: 9pt; }
QToolTip { background: #20252a; color: #ffffff; border: 1px solid #697580; padding: 5px 7px; }
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


def _find_toolbar(window, title: str) -> QtWidgets.QToolBar | None:
    for toolbar in window.findChildren(QtWidgets.QToolBar):
        if toolbar.windowTitle() == title:
            return toolbar
    return None


def _mark_toolbar(window) -> None:
    toolbar = _find_toolbar(window, "Main")
    if toolbar is None:
        return
    toolbar.setObjectName("PrimaryToolbar")
    toolbar.setMovable(False)
    toolbar.setFloatable(False)
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


def _move_navigation_into_central(window) -> None:
    if getattr(window, "_audacity_nav_moved", False):
        return
    bottom_toolbar = _find_toolbar(window, "Navigation")
    editor = window.takeCentralWidget()
    if editor is None:
        return
    shell = QtWidgets.QWidget(window)
    root = QtWidgets.QVBoxLayout(shell)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)
    root.addWidget(editor, 1)
    nav = QtWidgets.QWidget(shell)
    nav.setObjectName("AudacityNavBar")
    grid = QtWidgets.QGridLayout(nav)
    grid.setContentsMargins(10, 6, 10, 7)
    grid.setHorizontalSpacing(7)
    grid.setVerticalSpacing(3)
    controls = (
        window.time_slider,
        window.visible_sec,
        window.pitch_bottom,
        window.pitch_down_button,
        window.pitch_up_button,
        window.visible_notes,
        window.fit_button,
    )
    old_bar = window.time_slider.parentWidget()
    old_layout = old_bar.layout() if old_bar is not None else None
    for control in controls:
        if old_layout is not None:
            old_layout.removeWidget(control)
        control.setParent(nav)
    grid.addWidget(QtWidgets.QLabel(tr("ui.nav.timeline"), nav), 0, 0)
    grid.addWidget(window.time_slider, 0, 1, 1, 9)
    grid.addWidget(QtWidgets.QLabel(tr("ui.nav.window"), nav), 1, 0)
    grid.addWidget(window.visible_sec, 1, 1)
    grid.addWidget(QtWidgets.QLabel(tr("ui.nav.pitch"), nav), 1, 2)
    grid.addWidget(window.pitch_bottom, 1, 3)
    grid.addWidget(window.pitch_down_button, 1, 4)
    grid.addWidget(window.pitch_up_button, 1, 5)
    grid.addWidget(QtWidgets.QLabel(tr("ui.nav.range"), nav), 1, 6)
    grid.addWidget(window.visible_notes, 1, 7)
    grid.addWidget(window.fit_button, 1, 8)
    grid.setColumnStretch(9, 1)
    root.addWidget(nav, 0)
    window.setCentralWidget(shell)
    if bottom_toolbar is not None:
        bottom_toolbar.hide()
        window.removeToolBar(bottom_toolbar)
        window._audacity_legacy_bottom_toolbar = bottom_toolbar
    window._audacity_nav_moved = True
    window._audacity_central_shell = shell
    window._audacity_nav_bar = nav


def _fix_page_form(page: QtWidgets.QWidget) -> None:
    layout = page.layout()
    if not isinstance(layout, QtWidgets.QFormLayout):
        return
    layout.setContentsMargins(12, 10, 12, 12)
    layout.setHorizontalSpacing(10)
    layout.setVerticalSpacing(8)
    layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    layout.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.DontWrapRows)
    layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
    layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)
    for row in range(layout.rowCount()):
        label_item = layout.itemAt(row, QtWidgets.QFormLayout.ItemRole.LabelRole)
        field_item = layout.itemAt(row, QtWidgets.QFormLayout.ItemRole.FieldRole)
        if label_item is not None:
            label = label_item.widget()
            if isinstance(label, QtWidgets.QLabel):
                label.setWordWrap(False)
                label.setMinimumHeight(28)
                label.setMinimumWidth(100)
                label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        if field_item is not None:
            field = field_item.widget()
            if field is not None:
                field.setMinimumHeight(max(28, field.minimumHeight()))
                if isinstance(field, QtWidgets.QLabel):
                    field.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)


def _short_category_title(text: str) -> str:
    return {
        "出力音程": "出力",
        "グリッド / スナップ": "グリッド",
        "グリッド/スナップ": "グリッド",
        "カーブ / 角度": "カーブ",
        "カーブ/角度": "カーブ",
        "Export Pitch": "Export",
        "Grid / Snap": "Grid",
        "Curve / Angle": "Curve",
    }.get(text, text)


def _build_settings_sidebar(window) -> None:
    if getattr(window, "_audacity_settings_shell", None) is not None:
        return
    toolbox = window.settings_toolbox
    dock = window.settings_dock
    count = toolbox.count()
    if count <= 0:
        return
    titles = [toolbox.itemText(index) for index in range(count)]
    current = max(0, toolbox.currentIndex())
    toolbox.setParent(None)
    shell = QtWidgets.QWidget(dock)
    shell.setObjectName("AudacitySettingsShell")
    root = QtWidgets.QVBoxLayout(shell)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)
    rail = QtWidgets.QFrame(shell)
    rail.setObjectName("SettingsCategoryRail")
    rail.setFixedHeight(42)
    rail_layout = QtWidgets.QHBoxLayout(rail)
    rail_layout.setContentsMargins(4, 4, 4, 4)
    rail_layout.setSpacing(2)
    group = QtWidgets.QButtonGroup(shell)
    group.setExclusive(True)
    buttons: list[QtWidgets.QPushButton] = []
    for index, title in enumerate(titles):
        button = QtWidgets.QPushButton(_short_category_title(title), rail)
        button.setToolTip(title)
        button.setCheckable(True)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        button.clicked.connect(
            lambda _checked=False, page_index=index: toolbox.setCurrentIndex(page_index)
        )
        group.addButton(button, index)
        buttons.append(button)
        rail_layout.addWidget(button, 1)
    toolbox.setObjectName("AudacitySettingsPages")
    toolbox.setMinimumWidth(280)
    for index in range(count):
        page = toolbox.widget(index)
        if page is not None:
            page.setProperty("settingsPage", True)
            page.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
            _fix_page_form(page)
    root.addWidget(rail, 0)
    root.addWidget(toolbox, 1)
    dock.setWidget(shell)
    dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
    dock.setMinimumWidth(400)
    dock.resize(420, max(500, dock.height()))

    def sync_button(index: int) -> None:
        if 0 <= index < len(buttons):
            buttons[index].setChecked(True)

    toolbox.currentChanged.connect(sync_button)
    current = min(current, len(buttons) - 1)
    toolbox.setCurrentIndex(current)
    sync_button(current)
    window._audacity_settings_shell = shell
    window._audacity_settings_group = group
    window._audacity_settings_buttons = buttons


def polish_main_window(window) -> None:
    if getattr(window, "_modern_ui_polished", False):
        return
    if not hasattr(window, "editor") or not hasattr(window, "settings_toolbox"):
        return
    window._modern_ui_polished = True
    base_ui.polish_main_window(window)
    _mark_toolbar(window)
    _move_navigation_into_central(window)
    _build_settings_sidebar(window)
    window.setMinimumSize(1080, 680)


def _polish_open_windows(app: QtWidgets.QApplication) -> None:
    for window in app.topLevelWidgets():
        if isinstance(window, QtWidgets.QMainWindow) and window.__class__.__name__ == "MainWindow":
            polish_main_window(window)


def install_modern_ui() -> None:
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
