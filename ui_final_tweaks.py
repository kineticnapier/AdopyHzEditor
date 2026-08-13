from __future__ import annotations

from PySide6 import QtCore, QtWidgets

import ui_modern


def install_final_ui_tweaks() -> None:
    if getattr(ui_modern, "_adopy_final_tweaks_installed", False):
        return
    ui_modern._adopy_final_tweaks_installed = True

    original_build_settings_sidebar = ui_modern._build_settings_sidebar

    def build_settings_sidebar_with_fixed_categories(window) -> None:
        original_build_settings_sidebar(window)

        buttons = getattr(window, "_audacity_settings_buttons", [])
        for button in buttons:
            button.setFixedHeight(36)
            button.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )

        if buttons:
            rail = buttons[0].parentWidget()
            if rail is not None:
                layout = rail.layout()
                if isinstance(layout, QtWidgets.QVBoxLayout):
                    layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

    ui_modern._build_settings_sidebar = build_settings_sidebar_with_fixed_categories
