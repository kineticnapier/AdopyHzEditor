from PySide6 import QtWidgets


def apply(box: QtWidgets.QToolBox) -> None:
    for button in box.findChildren(QtWidgets.QAbstractButton):
        button.setFixedHeight(0)
