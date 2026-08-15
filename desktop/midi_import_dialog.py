from __future__ import annotations

from typing import Any

from PySide6 import QtWidgets

from i18n import tr


def get_midi_import_options(
    parent: QtWidgets.QWidget | None = None,
    *,
    has_existing_notes: bool = False,
) -> dict[str, Any] | None:
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle(tr("dialog.import_midi.options_title"))
    dialog.setModal(True)

    layout = QtWidgets.QVBoxLayout(dialog)

    info = QtWidgets.QLabel(tr("dialog.import_midi.options_text"))
    info.setWordWrap(True)
    layout.addWidget(info)

    mode_group = QtWidgets.QGroupBox(tr("dialog.import_midi.apply_group"))
    mode_layout = QtWidgets.QVBoxLayout(mode_group)
    replace_radio = QtWidgets.QRadioButton(tr("dialog.import_midi.replace"))
    append_radio = QtWidgets.QRadioButton(tr("dialog.import_midi.append"))
    replace_radio.setChecked(True)
    mode_layout.addWidget(replace_radio)
    if has_existing_notes:
        mode_layout.addWidget(append_radio)
    else:
        append_radio.setEnabled(False)
    layout.addWidget(mode_group)

    cleanup_group = QtWidgets.QGroupBox(tr("dialog.import_midi.cleanup_group"))
    form = QtWidgets.QFormLayout(cleanup_group)

    overlap_combo = QtWidgets.QComboBox()
    overlap_combo.addItem(tr("dialog.import_midi.overlap_merge"), "merge")
    overlap_combo.addItem(tr("dialog.import_midi.overlap_trim"), "trim")
    overlap_combo.addItem(tr("dialog.import_midi.overlap_off"), "off")
    form.addRow(tr("dialog.import_midi.overlap_mode"), overlap_combo)

    min_duration = QtWidgets.QDoubleSpinBox()
    min_duration.setRange(0.0, 5000.0)
    min_duration.setDecimals(1)
    min_duration.setSingleStep(5.0)
    min_duration.setSuffix(" ms")
    min_duration.setValue(20.0)
    form.addRow(tr("dialog.import_midi.min_duration"), min_duration)

    min_velocity = QtWidgets.QSpinBox()
    min_velocity.setRange(0, 127)
    min_velocity.setValue(1)
    form.addRow(tr("dialog.import_midi.min_velocity"), min_velocity)

    time_scale = QtWidgets.QDoubleSpinBox()
    time_scale.setRange(0.01, 100.0)
    time_scale.setDecimals(4)
    time_scale.setSingleStep(0.1)
    time_scale.setValue(1.0)
    time_scale.setSuffix(" x")
    form.addRow(tr("dialog.import_midi.time_scale"), time_scale)

    apply_tempo = QtWidgets.QCheckBox(tr("dialog.import_midi.apply_tempo"))
    apply_tempo.setChecked(True)
    form.addRow("", apply_tempo)

    hint = QtWidgets.QLabel(tr("dialog.import_midi.cleanup_hint"))
    hint.setWordWrap(True)
    form.addRow("", hint)

    layout.addWidget(cleanup_group)

    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.StandardButton.Ok
        | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
        parent=dialog,
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return None

    return {
        "mode": "append" if append_radio.isChecked() and has_existing_notes else "replace",
        "overlap_mode": overlap_combo.currentData(),
        "min_duration_seconds": float(min_duration.value()) / 1000.0,
        "min_velocity": int(min_velocity.value()),
        "time_scale": float(time_scale.value()),
        "apply_tempo": bool(apply_tempo.isChecked()),
    }
