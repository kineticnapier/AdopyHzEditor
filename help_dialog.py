from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from app_info import APP_VERSION, GITHUB_RELEASES_URL
from i18n import tr


HELP_SECTIONS: list[tuple[str, str, str]] = [
    ("quick_start", "help.quick_start.title", "help.quick_start.body"),
    ("controls", "help.controls.title", "help.controls.body"),
    ("adofai_export", "help.adofai_export.title", "help.adofai_export.body"),
    ("curve_glide", "help.curve_glide.title", "help.curve_glide.body"),
    ("troubleshooting", "help.troubleshooting.title", "help.troubleshooting.body"),
    ("about", "help.about.title", "help.about.body"),
]


class HelpDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, *, initial_section: str = "quick_start") -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("help.window_title"))
        self.resize(860, 640)

        layout = QtWidgets.QVBoxLayout(self)

        header = QtWidgets.QLabel(tr("help.header"))
        header.setWordWrap(True)
        layout.addWidget(header)

        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs, 1)

        self._section_to_index: dict[str, int] = {}

        for index, (section_id, title_key, body_key) in enumerate(HELP_SECTIONS):
            browser = QtWidgets.QTextBrowser()
            browser.setOpenExternalLinks(True)
            browser.setReadOnly(True)
            browser.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)

            body = tr(
                body_key,
                version=APP_VERSION,
                releases_url=GITHUB_RELEASES_URL,
            )
            browser.setPlainText(body)

            self.tabs.addTab(browser, tr(title_key))
            self._section_to_index[section_id] = index

        if initial_section in self._section_to_index:
            self.tabs.setCurrentIndex(self._section_to_index[initial_section])

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def select_section(self, section_id: str) -> None:
        index = self._section_to_index.get(section_id)
        if index is not None:
            self.tabs.setCurrentIndex(index)
