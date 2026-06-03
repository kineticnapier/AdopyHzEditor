from __future__ import annotations

from typing import Any
import math

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
        self.unit = 20.0
        self.track_width = 14.0

        self.setWindowTitle(tr("tile_preview.title"))
        self.resize(1080, 760)

        layout = QtWidgets.QVBoxLayout(self)

        total_tiles = int(self.stats.get("floors_total", max(0, len(points) - 1)) or 0)
        shown_tiles = max(0, len(points) - 1)
        self.summary = QtWidgets.QLabel(tr("tile_preview.tile_limit", shown=shown_tiles, total=total_tiles, limit=self.preview_limit))
        layout.addWidget(self.summary)

        if total_tiles > shown_tiles:
            warning = QtWidgets.QLabel(tr("tile_preview.preview_limited", shown=shown_tiles, total=total_tiles))
            warning.setStyleSheet("color: #d7a64a;")
            layout.addWidget(warning)

        self.stats_label = QtWidgets.QLabel(self._stats_text())
        self.stats_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.stats_label)

        self.scene = QtWidgets.QGraphicsScene(self)
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        self.view.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        self.view.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setBackgroundBrush(QtGui.QColor("#0f1117"))
        layout.addWidget(self.view, 1)

        controls = QtWidgets.QHBoxLayout()

        self.show_seams = QtWidgets.QCheckBox(tr("tile_preview.show_seams"))
        self.show_seams.setChecked(True)
        self.show_seams.stateChanged.connect(self.draw_preview)
        controls.addWidget(self.show_seams)

        self.show_center = QtWidgets.QCheckBox(tr("tile_preview.show_center"))
        self.show_center.setChecked(True)
        self.show_center.stateChanged.connect(self.draw_preview)
        controls.addWidget(self.show_center)

        self.show_centers = QtWidgets.QCheckBox(tr("tile_preview.show_centers"))
        self.show_centers.setChecked(False)
        self.show_centers.stateChanged.connect(self.draw_preview)
        controls.addWidget(self.show_centers)

        controls.addSpacing(14)

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
            "harmony_mode",
            "songFilename",
            "song_offset_ms",
        ]
        parts = [f"{key}: {self.stats.get(key, '')}" for key in keys if key in self.stats]
        return tr("tile_preview.stats") + "  " + " / ".join(parts)

    def _path_from_points(self) -> QtGui.QPainterPath:
        path = QtGui.QPainterPath()
        if not self.points:
            return path
        x0, y0, _ = self.points[0]
        path.moveTo(x0 * self.unit, y0 * self.unit)
        for x, y, _angle in self.points[1:]:
            path.lineTo(x * self.unit, y * self.unit)
        return path

    def draw_preview(self) -> None:
        self.scene.clear()
        self._draw_background_grid()

        if not self.points:
            self.scene.addText(tr("tile_preview.no_tiles"))
            return

        center_path = self._path_from_points()

        # Outer dark stroke first, then beige floor fill, so it reads like one
        # ADOFAI-style connected track instead of separate beads.
        outline_stroker = QtGui.QPainterPathStroker()
        outline_stroker.setWidth(self.track_width + 4.0)
        outline_stroker.setJoinStyle(QtCore.Qt.PenJoinStyle.MiterJoin)
        outline_stroker.setCapStyle(QtCore.Qt.PenCapStyle.SquareCap)
        outline_shape = outline_stroker.createStroke(center_path)
        outline_item = self.scene.addPath(
            outline_shape,
            QtGui.QPen(QtGui.QColor("#463b26"), 1.2),
            QtGui.QBrush(QtGui.QColor("#6f6040")),
        )
        outline_item.setZValue(0)

        track_stroker = QtGui.QPainterPathStroker()
        track_stroker.setWidth(self.track_width)
        track_stroker.setJoinStyle(QtCore.Qt.PenJoinStyle.MiterJoin)
        track_stroker.setCapStyle(QtCore.Qt.PenCapStyle.SquareCap)
        track_shape = track_stroker.createStroke(center_path)
        track_item = self.scene.addPath(
            track_shape,
            QtGui.QPen(QtGui.QColor("#806f46"), 1.0),
            QtGui.QBrush(QtGui.QColor("#d8c58f")),
        )
        track_item.setZValue(1)

        if self.show_center.isChecked():
            center_item = self.scene.addPath(
                center_path,
                QtGui.QPen(QtGui.QColor("#826f43"), 1.15),
            )
            center_item.setZValue(3)

        if self.show_seams.isChecked():
            self._draw_seams()

        if self.show_centers.isChecked():
            self._draw_center_points()

        self._add_marker(self.points[0], tr("tile_preview.start"), QtGui.QColor("#22c55e"))
        self._add_marker(self.points[-1], tr("tile_preview.end"), QtGui.QColor("#ef4444"))

        rect = self.scene.itemsBoundingRect().adjusted(-80, -80, 80, 80)
        self.scene.setSceneRect(rect)

    def _draw_background_grid(self) -> None:
        # A subtle fixed grid helps judge shape without becoming the focus.
        pen = QtGui.QPen(QtGui.QColor("#1b1f2a"), 1.0)
        step = 80
        span = 12000
        for x in range(-span, span + 1, step):
            item = self.scene.addLine(x, -span, x, span, pen)
            item.setZValue(-10)
        for y in range(-span, span + 1, step):
            item = self.scene.addLine(-span, y, span, y, pen)
            item.setZValue(-10)

    def _local_direction(self, index: int) -> tuple[float, float]:
        n = len(self.points)
        if n < 2:
            return (1.0, 0.0)

        if 0 < index < n - 1:
            x0, y0, _ = self.points[index - 1]
            x1, y1, _ = self.points[index + 1]
        elif index > 0:
            x0, y0, _ = self.points[index - 1]
            x1, y1, _ = self.points[index]
        else:
            x0, y0, _ = self.points[index]
            x1, y1, _ = self.points[index + 1]

        dx = (x1 - x0) * self.unit
        dy = (y1 - y0) * self.unit
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return (1.0, 0.0)
        return (dx / length, dy / length)

    def _draw_seams(self) -> None:
        total = len(self.points)
        if total <= 2:
            return

        # Avoid drawing tens of thousands of seam lines if the preview limit is raised.
        step = max(1, int(math.ceil(total / 5000)))
        pen = QtGui.QPen(QtGui.QColor("#6b5c3a"), 1.0)
        pen.setCosmetic(True)

        for i in range(1, total - 1, step):
            x, y, _angle = self.points[i]
            px = x * self.unit
            py = y * self.unit
            dx, dy = self._local_direction(i)
            nx = -dy
            ny = dx
            half = self.track_width * 0.47

            item = self.scene.addLine(
                px - nx * half,
                py - ny * half,
                px + nx * half,
                py + ny * half,
                pen,
            )
            item.setZValue(4)

    def _draw_center_points(self) -> None:
        pen = QtGui.QPen(QtGui.QColor("#20242f"), 0.8)
        brush = QtGui.QBrush(QtGui.QColor("#f6e6b2"))
        step = max(1, int(math.ceil(len(self.points) / 2500)))
        size = 3.5
        for i, (x, y, _angle) in enumerate(self.points[::step]):
            px = x * self.unit
            py = y * self.unit
            item = self.scene.addEllipse(px - size / 2, py - size / 2, size, size, pen, brush)
            item.setZValue(5)

    def _add_marker(
        self,
        point: tuple[float, float, float],
        label: str,
        color: QtGui.QColor,
    ) -> None:
        x, y, _angle = point
        px = x * self.unit
        py = y * self.unit
        size = self.track_width + 8.0

        ring_pen = QtGui.QPen(color, 2.6)
        ring_pen.setCosmetic(True)
        marker = self.scene.addEllipse(px - size / 2, py - size / 2, size, size, ring_pen, QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush))
        marker.setZValue(8)

        dot = self.scene.addEllipse(px - 3.5, py - 3.5, 7.0, 7.0, QtGui.QPen(color, 1.0), QtGui.QBrush(color))
        dot.setZValue(9)

        text = self.scene.addText(label)
        text.setDefaultTextColor(color)
        text.setPos(px + size * 0.65, py - size * 0.75)
        text.setZValue(10)

    def reset_view(self) -> None:
        self.view.resetTransform()
        rect = self.scene.sceneRect()
        if rect.isValid() and not rect.isEmpty():
            self.view.fitInView(rect, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
