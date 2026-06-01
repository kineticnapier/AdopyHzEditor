from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from i18n import tr


class TilePreviewDialog(QtWidgets.QDialog):
    def __init__(
        self,
        points: list[tuple[float, float, float]],
        stats: dict[str, Any],
        *,
        preview_limit: int = 5000,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.points = points
        self.stats = dict(stats)
        self.preview_limit = int(preview_limit)
        self.unit = 18.0

        self.setWindowTitle(tr("tile_preview.title"))
        self.resize(1000, 720)

        layout = QtWidgets.QVBoxLayout(self)

        total_tiles = int(self.stats.get("floors_total", max(0, len(points) - 1)) or 0)
        shown_tiles = max(0, len(points) - 1)
        self.summary = QtWidgets.QLabel(tr("tile_preview.tile_limit", shown=shown_tiles, total=total_tiles, limit=self.preview_limit))
        layout.addWidget(self.summary)

        if total_tiles > shown_tiles:
            warning = QtWidgets.QLabel(tr("tile_preview.preview_limited", shown=shown_tiles, total=total_tiles))
            warning.setStyleSheet("color: #9a5b00;")
            layout.addWidget(warning)

        self.stats_label = QtWidgets.QLabel(self._stats_text())
        self.stats_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.stats_label)

        self.scene = QtWidgets.QGraphicsScene(self)
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        self.view.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        self.view.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setBackgroundBrush(QtGui.QColor("#f7f7f7"))
        layout.addWidget(self.view, 1)

        controls = QtWidgets.QHBoxLayout()

        zoom_in = QtWidgets.QPushButton(tr("tile_preview.zoom_in"))
        zoom_in.clicked.connect(lambda: self.view.scale(1.25, 1.25))
        controls.addWidget(zoom_in)

        zoom_out = QtWidgets.QPushButton(tr("tile_preview.zoom_out"))
        zoom_out.clicked.connect(lambda: self.view.scale(0.8, 0.8))
        controls.addWidget(zoom_out)

        reset = QtWidgets.QPushButton(tr("tile_preview.reset_view"))
        reset.clicked.connect(self.reset_view)
        controls.addWidget(reset)

        controls.addStretch(1)

        close_btn = QtWidgets.QPushButton(tr("tile_preview.close"))
        close_btn.clicked.connect(self.accept)
        controls.addWidget(close_btn)

        layout.addLayout(controls)

        self.draw_preview()
        QtCore.QTimer.singleShot(0, self.reset_view)

    def _stats_text(self) -> str:
        keys = [
            "method",
            "tiles_total",
            "floors_total",
            "actions_total",
            "first_note_offset_seconds",
            "songFilename",
            "song_offset_ms",
        ]
        parts = [f"{key}: {self.stats.get(key, '')}" for key in keys]
        return tr("tile_preview.stats") + "  " + " / ".join(parts)

    def draw_preview(self) -> None:
        self.scene.clear()
        if not self.points:
            self.scene.addText(tr("tile_preview.no_tiles"))
            return

        path = QtGui.QPainterPath()
        start_x, start_y, _start_angle = self.points[0]
        path.moveTo(start_x * self.unit, start_y * self.unit)
        for x, y, _angle in self.points[1:]:
            path.lineTo(x * self.unit, y * self.unit)

        path_item = self.scene.addPath(path, QtGui.QPen(QtGui.QColor("#3d4652"), 1.6))
        path_item.setZValue(0)

        tile_pen = QtGui.QPen(QtGui.QColor("#4d5967"), 0.8)
        tile_brush = QtGui.QBrush(QtGui.QColor("#fdfdfd"))
        marker_size = 8.0
        tile_size = 4.2

        for index, (x, y, _angle) in enumerate(self.points):
            px = x * self.unit
            py = y * self.unit
            if index == 0 or index == len(self.points) - 1:
                continue
            self.scene.addEllipse(px - tile_size / 2, py - tile_size / 2, tile_size, tile_size, tile_pen, tile_brush)

        self._add_marker(self.points[0], tr("tile_preview.start"), QtGui.QColor("#2b8a3e"), marker_size)
        self._add_marker(self.points[-1], tr("tile_preview.end"), QtGui.QColor("#c92a2a"), marker_size)

        rect = self.scene.itemsBoundingRect().adjusted(-40, -40, 40, 40)
        self.scene.setSceneRect(rect)

    def _add_marker(
        self,
        point: tuple[float, float, float],
        label: str,
        color: QtGui.QColor,
        size: float,
    ) -> None:
        x, y, _angle = point
        px = x * self.unit
        py = y * self.unit
        pen = QtGui.QPen(color, 1.5)
        brush = QtGui.QBrush(color)
        item = self.scene.addEllipse(px - size / 2, py - size / 2, size, size, pen, brush)
        item.setZValue(2)
        text = self.scene.addText(label)
        text.setDefaultTextColor(color)
        text.setPos(px + size, py - size)
        text.setZValue(3)

    def reset_view(self) -> None:
        self.view.resetTransform()
        rect = self.scene.sceneRect()
        if rect.isValid() and not rect.isEmpty():
            self.view.fitInView(rect, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
