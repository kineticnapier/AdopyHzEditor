from __future__ import annotations

from PySide6 import QtCore, QtWidgets

import ui_modern as base_ui
from i18n import tr

_EXTRA_STYLE = r"""
QFrame#SettingsCategoryRail { background: #2f343a; border-right: 1px solid #171a1e; }
QFrame#SettingsCategoryRail QPushButton { background: transparent; color: #d6dbe1; border: 0; border-radius: 4px; padding: 8px 10px; min-height: 34px; text-align: left; }
QFrame#SettingsCategoryRail QPushButton:hover { background: #454d56; }
QFrame#SettingsCategoryRail QPushButton:checked { background: #1769aa; color: #ffffff; font-weight: 700; }
QToolBox#AudacitySettingsPages { background: #272c32; border: 0; }
QToolBox#AudacitySettingsPages::tab { background: transparent; color: transparent; border: 0; margin: 0; padding: 0; min-height: 0px; max-height: 0px; }
QWidget#AudacitySettingsShell { background: #272c32; }
QWidget#AudacityNavBar { background: #343a41; border-top: 1px solid #191c20; }
QWidget#AudacityNavBar QLabel { color: #c4cbd3; min-height: 24px; }
"""


def _find_toolbar(window, title: str) -> QtWidgets.QToolBar | None:
    for toolbar in window.findChildren(QtWidgets.QToolBar):
        if toolbar.windowTitle() == title:
            return toolbar
    return None


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

    controls = (window.time_slider, window.visible_sec, window.pitch_bottom, window.pitch_down_button, window.pitch_up_button, window.visible_notes, window.fit_button)
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
    layout.setContentsMargins(14, 12, 14, 14)
    layout.setHorizontalSpacing(14)
    layout.setVerticalSpacing(10)
    layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    layout.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.DontWrapRows)
    layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
    layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)

    for row in range(layout.rowCount()):
        label_item = layout.itemAt(row, QtWidgets.QFormLayout.ItemRole.LabelRole)
        field_item = layout.itemAt(row, QtWidgets.QFormLayout.ItemRole.FieldRole)
        if label_item is not None:
            label = label_item.widget()
            if isinstance(label, QtWidgets.QLabel):
                label.setWordWrap(False)
                label.setMinimumHeight(30)
                label.setMinimumWidth(118)
        if field_item is not None:
            field = field_item.widget()
            if field is not None:
                field.setMinimumHeight(max(30, field.minimumHeight()))


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
    root = QtWidgets.QHBoxLayout(shell)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    rail = QtWidgets.QFrame(shell)
    rail.setObjectName("SettingsCategoryRail")
    rail.setFixedWidth(142)
    rail_layout = QtWidgets.QVBoxLayout(rail)
    rail_layout.setContentsMargins(7, 8, 7, 8)
    rail_layout.setSpacing(4)

    group = QtWidgets.QButtonGroup(shell)
    group.setExclusive(True)
    buttons: list[QtWidgets.QPushButton] = []
    for index, title in enumerate(titles):
        button = QtWidgets.QPushButton(title, rail)
        button.setCheckable(True)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _checked=False, page_index=index: toolbox.setCurrentIndex(page_index))
        group.addButton(button, index)
        buttons.append(button)
        rail_layout.addWidget(button)
    rail_layout.addStretch(1)

    toolbox.setObjectName("AudacitySettingsPages")
    toolbox.setMinimumWidth(330)
    for index in range(count):
        page = toolbox.widget(index)
        if page is not None:
            _fix_page_form(page)

    root.addWidget(rail, 0)
    root.addWidget(toolbox, 1)
    dock.setWidget(shell)
    dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
    dock.setMinimumWidth(500)
    dock.resize(520, max(520, dock.height()))

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


def install_audacity_ui() -> None:
    if getattr(QtWidgets, "_adopy_audacity_ui_installed", False):
        return
    QtWidgets._adopy_audacity_ui_installed = True
    if _EXTRA_STYLE not in base_ui._STYLE_SHEET:
        base_ui._STYLE_SHEET += _EXTRA_STYLE

    original_polish = base_ui.polish_main_window
    def combined_polish(window) -> None:
        original_polish(window)
        if getattr(window, "_audacity_layout_polished", False):
            return
        window._audacity_layout_polished = True
        _move_navigation_into_central(window)
        _build_settings_sidebar(window)
        window.setMinimumSize(1180, 680)

    base_ui.polish_main_window = combined_polish
    base_ui.install_modern_ui()
