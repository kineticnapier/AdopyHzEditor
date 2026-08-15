from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtWidgets

from i18n import tr
from quick_hz_tools import (
    AppendGeneratedDataToChart,
    CalculateHzInfo,
    GenerateOutputText,
    HzToolError,
    ReadChartTailFloor,
    SaveChartAs,
)


class QuickHzToolsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("quick_hz.title"))
        self.resize(900, 720)
        self._chart_path: Path | None = None
        self._last_output_text = ""

        main_layout = QtWidgets.QVBoxLayout(self)

        form_group = QtWidgets.QGroupBox(tr("quick_hz.calc_group"))
        form = QtWidgets.QFormLayout(form_group)

        self.bpm = QtWidgets.QDoubleSpinBox()
        self.bpm.setRange(0.0, 999999.0)
        self.bpm.setDecimals(6)
        self.bpm.setValue(self._default_bpm(parent))
        self.bpm.setSingleStep(1.0)
        form.addRow(tr("quick_hz.bpm"), self.bpm)

        self.hz = QtWidgets.QDoubleSpinBox()
        self.hz.setRange(0.0, 100000.0)
        self.hz.setDecimals(6)
        self.hz.setValue(16.0)
        self.hz.setSingleStep(1.0)
        form.addRow(tr("quick_hz.hz"), self.hz)

        self.start_floor = QtWidgets.QSpinBox()
        self.start_floor.setRange(0, 10000000)
        self.start_floor.setValue(0)
        form.addRow(tr("quick_hz.start_floor"), self.start_floor)

        count_row = QtWidgets.QHBoxLayout()
        self.use_end_floor = QtWidgets.QCheckBox(tr("quick_hz.use_end_floor"))
        self.generate_count = QtWidgets.QSpinBox()
        self.generate_count.setRange(0, 10000000)
        self.generate_count.setValue(16)
        self.end_floor = QtWidgets.QSpinBox()
        self.end_floor.setRange(0, 10000000)
        self.end_floor.setValue(16)
        self.end_floor.setEnabled(False)
        count_row.addWidget(QtWidgets.QLabel(tr("quick_hz.count")))
        count_row.addWidget(self.generate_count)
        count_row.addSpacing(12)
        count_row.addWidget(self.use_end_floor)
        count_row.addWidget(self.end_floor)
        form.addRow(tr("quick_hz.generate"), count_row)

        self.add_set_speed = QtWidgets.QCheckBox(tr("quick_hz.add_setspeed"))
        self.add_set_speed.setChecked(True)
        form.addRow("", self.add_set_speed)

        main_layout.addWidget(form_group)

        result_group = QtWidgets.QGroupBox(tr("quick_hz.result_group"))
        result_layout = QtWidgets.QFormLayout(result_group)
        self.interval_ms_label = QtWidgets.QLabel("-")
        self.beat_ms_label = QtWidgets.QLabel("-")
        self.beats_per_hit_label = QtWidgets.QLabel("-")
        self.relative_angle_label = QtWidgets.QLabel("-")
        result_layout.addRow(tr("quick_hz.interval_ms"), self.interval_ms_label)
        result_layout.addRow(tr("quick_hz.beat_ms"), self.beat_ms_label)
        result_layout.addRow(tr("quick_hz.beats_per_hit"), self.beats_per_hit_label)
        result_layout.addRow(tr("quick_hz.relative_angle"), self.relative_angle_label)
        main_layout.addWidget(result_group)

        output_group = QtWidgets.QGroupBox(tr("quick_hz.output_group"))
        output_layout = QtWidgets.QVBoxLayout(output_group)
        self.output_text = QtWidgets.QPlainTextEdit()
        self.output_text.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.output_text.setPlaceholderText(tr("quick_hz.output_placeholder"))
        output_layout.addWidget(self.output_text, 1)

        output_buttons = QtWidgets.QHBoxLayout()
        self.recalculate_btn = QtWidgets.QPushButton(tr("quick_hz.recalculate"))
        self.copy_btn = QtWidgets.QPushButton(tr("quick_hz.copy"))
        self.save_txt_btn = QtWidgets.QPushButton(tr("quick_hz.save_txt"))
        output_buttons.addWidget(self.recalculate_btn)
        output_buttons.addStretch(1)
        output_buttons.addWidget(self.copy_btn)
        output_buttons.addWidget(self.save_txt_btn)
        output_layout.addLayout(output_buttons)
        main_layout.addWidget(output_group, 1)

        chart_group = QtWidgets.QGroupBox(tr("quick_hz.chart_group"))
        chart_layout = QtWidgets.QVBoxLayout(chart_group)

        chart_row = QtWidgets.QHBoxLayout()
        self.chart_path_label = QtWidgets.QLabel(tr("quick_hz.no_chart"))
        self.chart_path_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.choose_chart_btn = QtWidgets.QPushButton(tr("quick_hz.choose_chart"))
        chart_row.addWidget(self.chart_path_label, 1)
        chart_row.addWidget(self.choose_chart_btn)
        chart_layout.addLayout(chart_row)

        append_row = QtWidgets.QHBoxLayout()
        self.overwrite_chart = QtWidgets.QCheckBox(tr("quick_hz.overwrite"))
        self.append_chart_btn = QtWidgets.QPushButton(tr("quick_hz.append_chart"))
        append_row.addWidget(self.overwrite_chart)
        append_row.addStretch(1)
        append_row.addWidget(self.append_chart_btn)
        chart_layout.addLayout(append_row)

        main_layout.addWidget(chart_group)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        main_layout.addWidget(self.status)

        close_buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)
        main_layout.addWidget(close_buttons)

        self.use_end_floor.toggled.connect(self._on_use_end_floor_changed)
        self.recalculate_btn.clicked.connect(self.recalculate)
        self.copy_btn.clicked.connect(self.copy_output)
        self.save_txt_btn.clicked.connect(self.save_output_text)
        self.choose_chart_btn.clicked.connect(self.choose_chart)
        self.append_chart_btn.clicked.connect(self.append_to_chart)

        for widget in (
            self.bpm,
            self.hz,
            self.start_floor,
            self.generate_count,
            self.end_floor,
            self.add_set_speed,
        ):
            if hasattr(widget, "valueChanged"):
                widget.valueChanged.connect(lambda *args: self.recalculate())
            elif hasattr(widget, "stateChanged"):
                widget.stateChanged.connect(lambda *args: self.recalculate())

        self.recalculate()

    @staticmethod
    def _default_bpm(parent) -> float:
        try:
            if parent is not None and hasattr(parent, "grid_bpm"):
                return float(parent.grid_bpm.value())
        except Exception:
            pass
        return 175.0

    def _set_status(self, text: str, *, error: bool = False) -> None:
        self.status.setText(text)
        self.status.setStyleSheet("color: #b00020;" if error else "")

    def _on_use_end_floor_changed(self, checked: bool) -> None:
        self.generate_count.setEnabled(not checked)
        self.end_floor.setEnabled(checked)
        self.recalculate()

    def _count_value(self) -> int:
        start = int(self.start_floor.value())
        if self.use_end_floor.isChecked():
            end = int(self.end_floor.value())
            if end <= start:
                raise HzToolError(tr("quick_hz.error_end_floor"))
            return end - start
        count = int(self.generate_count.value())
        if count <= 0:
            raise HzToolError(tr("quick_hz.error_count"))
        return count

    def _calculate(self):
        info = CalculateHzInfo(float(self.bpm.value()), float(self.hz.value()))
        count = self._count_value()
        return info, int(self.start_floor.value()), count

    def recalculate(self) -> None:
        try:
            info, start_floor, count = self._calculate()
            self.interval_ms_label.setText(f"{info.interval_ms:.6f} ms")
            self.beat_ms_label.setText(f"{info.beat_ms:.6f} ms")
            self.beats_per_hit_label.setText(f"{info.beats_per_hit:.9f} ({info.beat_fraction_text})")
            self.relative_angle_label.setText(f"{info.relative_angle:.9f}°")
            self._last_output_text = GenerateOutputText(info, start_floor, count, add_set_speed=bool(self.add_set_speed.isChecked()))
            self.output_text.setPlainText(self._last_output_text)
            self._set_status(tr("quick_hz.status_ready"))
        except Exception as exc:
            self.interval_ms_label.setText("-")
            self.beat_ms_label.setText("-")
            self.beats_per_hit_label.setText("-")
            self.relative_angle_label.setText("-")
            self._last_output_text = ""
            self.output_text.setPlainText("")
            self._set_status(str(exc), error=True)

    def copy_output(self) -> None:
        text = self.output_text.toPlainText()
        if not text.strip():
            self._set_status(tr("quick_hz.error_no_output"), error=True)
            return
        QtWidgets.QApplication.clipboard().setText(text)
        self._set_status(tr("quick_hz.status_copied"))

    def save_output_text(self) -> None:
        text = self.output_text.toPlainText()
        if not text.strip():
            self._set_status(tr("quick_hz.error_no_output"), error=True)
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            tr("quick_hz.save_txt_title"),
            "quick_hz_output.txt",
            "Text File (*.txt);;All Files (*)",
        )
        if not path:
            self._set_status(tr("quick_hz.status_cancelled"))
            return
        if not path.lower().endswith(".txt"):
            path += ".txt"
        try:
            Path(path).write_text(text, encoding="utf-8")
        except Exception as exc:
            self._set_status(tr("quick_hz.error_save_txt", error=exc), error=True)
            return
        self._set_status(tr("quick_hz.status_saved_txt", path=path))

    def choose_chart(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            tr("quick_hz.choose_chart_title"),
            "",
            "ADOFAI Level (*.adofai);;All Files (*)",
        )
        if not path:
            self._set_status(tr("quick_hz.status_cancelled"))
            return

        self._chart_path = Path(path)
        self.chart_path_label.setText(str(self._chart_path))
        try:
            tail = ReadChartTailFloor(self._chart_path)
            self.start_floor.setValue(tail)
            if self.use_end_floor.isChecked() and self.end_floor.value() <= tail:
                self.end_floor.setValue(tail + max(1, self.generate_count.value()))
            self._set_status(tr("quick_hz.status_chart_loaded", floor=tail))
        except Exception as exc:
            self._set_status(str(exc), error=True)

    def append_to_chart(self) -> None:
        if self._chart_path is None:
            self._set_status(tr("quick_hz.error_no_chart"), error=True)
            return

        try:
            info, _preview_start, count = self._calculate()
            data, result = AppendGeneratedDataToChart(
                self._chart_path,
                info,
                count,
                start_floor=None,
                add_set_speed=bool(self.add_set_speed.isChecked()),
            )
            output_path = SaveChartAs(
                data,
                self._chart_path,
                overwrite=bool(self.overwrite_chart.isChecked()),
            )
        except Exception as exc:
            self._set_status(str(exc), error=True)
            return

        self._set_status(
            tr(
                "quick_hz.status_appended",
                tiles=result.angle_data_added,
                actions=result.actions_added,
                path=output_path,
            )
        )
