from PySide6 import QtCore, QtWidgets


def apply(box: QtWidgets.QToolBox) -> None:
    buttons = box.findChildren(
        QtWidgets.QAbstractButton,
        options=QtCore.Qt.FindChildOption.FindDirectChildrenOnly,
    )
    for button in buttons:
        button.setFixedHeight(0)
        button.setMinimumHeight(0)
        button.setMaximumHeight(0)
        button.hide()
