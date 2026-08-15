from __future__ import annotations

from PySide6 import QtCore, QtWidgets

import desktop.ui_modern as ui_modern
from desktop.toolbox_fix import apply as apply_toolbox_fix


_COMPACT_RAIL_STYLE = r"""
QFrame#SettingsCategoryRail QPushButton {
    min-height: 0px;
    max-height: 28px;
    padding: 3px 8px;
}
"""


def install_final_ui_tweaks() -> None:
    if getattr(ui_modern, "_adopy_final_tweaks_installed", False):
        return
    ui_modern._adopy_final_tweaks_installed = True

    if _COMPACT_RAIL_STYLE not in ui_modern._STYLE_SHEET:
        ui_modern._STYLE_SHEET += _COMPACT_RAIL_STYLE

    original_build_settings_sidebar = ui_modern._build_settings_sidebar

    def build_settings_sidebar_with_fixed_categories(window) -> None:
        original_build_settings_sidebar(window)

        buttons = getattr(window, "_audacity_settings_buttons", [])
        for button in buttons:
            button.setFixedHeight(28)
            button.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )

        apply_toolbox_fix(window.settings_toolbox)

        if buttons:
            rail = buttons[0].parentWidget()
            if rail is not None:
                layout = rail.layout()
                if isinstance(layout, QtWidgets.QVBoxLayout):
                    layout.setContentsMargins(4, 4, 4, 4)
                    layout.setSpacing(1)
                    layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

    ui_modern._build_settings_sidebar = build_settings_sidebar_with_fixed_categories
