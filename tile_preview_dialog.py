from __future__ import annotations

import math
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
        self.center_item_limit = min(5000, max(0, self.preview_limit + 1))

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
        self.view.setBackgroundBrush(QtGui.QColor("#0b0d14"))
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

        controls.addWidget(QtWidgets.QLabel(tr("tile_preview.view_mode")))
        self.view_mode_combo = QtWidgets.QComboBox()
        self.view_mode_combo.addItem(tr("tile_preview.view_game"), "game")
        self.view_mode_combo.addItem(tr("tile_preview.view_technical"), "technical")
        self.view_mode_combo.addItem(tr("tile_preview.view_centers"), "centers")
        self.view_mode_combo.currentIndexChanged.connect(self.draw_preview)
        controls.addWidget(self.view_mode_combo)

        self.show_guide_check = QtWidgets.QCheckBox(tr("tile_preview.show_guide"))
        self.show_guide_check.setChecked(False)
        self.show_guide_check.stateChanged.connect(self.draw_preview)
        controls.addWidget(self.show_guide_check)

        self.show_seams_check = QtWidgets.QCheckBox(tr("tile_preview.show_seams"))
        self.show_seams_check.setChecked(True)
        self.show_seams_check.stateChanged.connect(self.draw_preview)
        controls.addWidget(self.show_seams_check)

        self.show_center_seam_check = QtWidgets.QCheckBox(tr("tile_preview.show_center_seam"))
        self.show_center_seam_check.setChecked(True)
        self.show_center_seam_check.stateChanged.connect(self.draw_preview)
        controls.addWidget(self.show_center_seam_check)

        self.show_centers_check = QtWidgets.QCheckBox(tr("tile_preview.show_centers"))
        self.show_centers_check.setChecked(False)
        self.show_centers_check.stateChanged.connect(self.draw_preview)
        controls.addWidget(self.show_centers_check)

        self.show_labels_check = QtWidgets.QCheckBox(tr("tile_preview.show_labels"))
        self.show_labels_check.setChecked(True)
        self.show_labels_check.stateChanged.connect(self.draw_preview)
        controls.addWidget(self.show_labels_check)

        self.show_numbers_check = QtWidgets.QCheckBox(tr("tile_preview.show_numbers"))
        self.show_numbers_check.setChecked(False)
        self.show_numbers_check.stateChanged.connect(self.draw_preview)
        controls.addWidget(self.show_numbers_check)

        self.number_step = QtWidgets.QSpinBox()
        self.number_step.setRange(1, 1000)
        self.number_step.setValue(25)
        self.number_step.setPrefix(tr("tile_preview.every_prefix"))
        self.number_step.setSuffix(tr("tile_preview.every_suffix"))
        self.number_step.valueChanged.connect(self.draw_preview)
        controls.addWidget(self.number_step)

        controls.addWidget(QtWidgets.QLabel(tr("tile_preview.scale")))
        self.scale_combo = QtWidgets.QComboBox()
        self.scale_combo.addItem(tr("tile_preview.scale_compact"), 11.0)
        self.scale_combo.addItem(tr("tile_preview.scale_normal"), 18.0)
        self.scale_combo.addItem(tr("tile_preview.scale_large"), 24.0)
        self.scale_combo.setCurrentIndex(1)
        self.scale_combo.currentIndexChanged.connect(self._scale_changed)
        controls.addWidget(self.scale_combo)

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
            text = self.scene.addText(tr("tile_preview.no_tiles"))
            text.setDefaultTextColor(QtGui.QColor("#e8e2d2"))
            return

        path = self._build_track_path()
        track_width = self._track_width()
        view_mode = str(self.view_mode_combo.currentData() or "game")

        if view_mode != "game":
            self._draw_background_grid()

        if view_mode == "game":
            self._add_game_like_tiles(path, track_width)
        elif view_mode == "technical":
            self._add_track(path, track_width)

        if self.show_guide_check.isChecked():
            self._add_guide_line(path)

        if view_mode != "centers" and self.show_center_seam_check.isChecked():
            self._add_center_seam(path)

        if view_mode != "centers" and self.show_seams_check.isChecked():
            self._add_seams(track_width)

        if view_mode == "centers" or self.show_centers_check.isChecked():
            self._add_center_points()

        if self.show_numbers_check.isChecked():
            step = max(1, int(self.number_step.value()))
            for index, (x, y, _angle) in enumerate(self.points[: self.center_item_limit]):
                if index > 0 and index % step == 0:
                    self._add_label(str(index), x * self.unit, y * self.unit, "#d9e4ef", 4)

        self._add_marker(self.points[0], tr("tile_preview.start"), QtGui.QColor("#22c55e"), track_width, -1)
        self._add_marker(self.points[-1], tr("tile_preview.end"), QtGui.QColor("#ef4444"), track_width, 1)

        self.scene.setSceneRect(self._points_scene_rect())

    def _points_scene_rect(self) -> QtCore.QRectF:
        min_x = min(x for x, _y, _angle in self.points) * self.unit
        max_x = max(x for x, _y, _angle in self.points) * self.unit
        min_y = min(y for _x, y, _angle in self.points) * self.unit
        max_y = max(y for _x, y, _angle in self.points) * self.unit
        padding = max(48.0, min(72.0, self.unit * 2.8))
        return QtCore.QRectF(
            QtCore.QPointF(min_x, min_y),
            QtCore.QPointF(max_x, max_y),
        ).normalized().adjusted(-padding, -padding, padding, padding)

    def _build_track_path(self) -> QtGui.QPainterPath:
        path = QtGui.QPainterPath()
        start_x, start_y, _start_angle = self.points[0]
        path.moveTo(start_x * self.unit, start_y * self.unit)
        for x, y, _angle in self.points[1:]:
            path.lineTo(x * self.unit, y * self.unit)
        return path

    def _track_width(self) -> float:
        return max(8.0, min(20.0, self.unit * 0.72))

    def _track_shape(self, path: QtGui.QPainterPath, track_width: float) -> QtGui.QPainterPath:
        stroker = QtGui.QPainterPathStroker()
        stroker.setWidth(track_width)
        stroker.setJoinStyle(QtCore.Qt.PenJoinStyle.MiterJoin)
        stroker.setCapStyle(QtCore.Qt.PenCapStyle.SquareCap)
        return stroker.createStroke(path)

    def _add_game_like_tiles(self, path: QtGui.QPainterPath, track_width: float) -> None:
        track_shape = self._track_shape(path, track_width)

        shadow = QtGui.QPainterPath(track_shape)
        shadow.translate(2.2, 2.8)
        shadow_color = QtGui.QColor("#000000")
        shadow_color.setAlpha(105)
        shadow_item = self.scene.addPath(shadow, QtGui.QPen(QtCore.Qt.PenStyle.NoPen), QtGui.QBrush(shadow_color))
        shadow_item.setZValue(0)

        base_item = self.scene.addPath(track_shape, QtGui.QPen(QtCore.Qt.PenStyle.NoPen), QtGui.QBrush(QtGui.QColor("#d8c58f")))
        base_item.setZValue(1)

        panel_limit = min(len(self.points) - 1, 5000)
        for index in range(panel_limit):
            polygon = self._segment_polygon(index, track_width)
            if polygon.isEmpty():
                continue
            panel_color = QtGui.QColor("#f0dfad" if index % 2 == 0 else "#c8b176")
            panel_color.setAlpha(38)
            panel = self.scene.addPolygon(polygon, QtGui.QPen(QtCore.Qt.PenStyle.NoPen), QtGui.QBrush(panel_color))
            panel.setZValue(1.15)

        edge_pen = QtGui.QPen(QtGui.QColor("#5d523c"), 2.2)
        edge_item = self.scene.addPath(track_shape, edge_pen, QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush))
        edge_item.setZValue(2.5)

    def _segment_polygon(self, index: int, track_width: float) -> QtGui.QPolygonF:
        if index < 0 or index >= len(self.points) - 1:
            return QtGui.QPolygonF()
        x1, y1, _angle1 = self.points[index]
        x2, y2, _angle2 = self.points[index + 1]
        px1 = x1 * self.unit
        py1 = y1 * self.unit
        px2 = x2 * self.unit
        py2 = y2 * self.unit
        dx = px2 - px1
        dy = py2 - py1
        length = math.hypot(dx, dy)
        if length <= 0.000001:
            return QtGui.QPolygonF()
        dx /= length
        dy /= length
        nx = -dy
        ny = dx
        half = track_width * 0.48
        return QtGui.QPolygonF(
            [
                QtCore.QPointF(px1 - nx * half, py1 - ny * half),
                QtCore.QPointF(px1 + nx * half, py1 + ny * half),
                QtCore.QPointF(px2 + nx * half, py2 + ny * half),
                QtCore.QPointF(px2 - nx * half, py2 - ny * half),
            ]
        )

    def _add_track(self, path: QtGui.QPainterPath, track_width: float) -> None:
        track_shape = self._track_shape(path, track_width)

        shadow = QtGui.QPainterPath(track_shape)
        shadow.translate(1.8, 2.2)
        shadow_color = QtGui.QColor("#000000")
        shadow_color.setAlpha(95)
        shadow_item = self.scene.addPath(shadow, QtGui.QPen(QtCore.Qt.PenStyle.NoPen), QtGui.QBrush(shadow_color))
        shadow_item.setZValue(0)

        outline_pen = QtGui.QPen(QtGui.QColor("#6f6040"), 2.0)
        fill_brush = QtGui.QBrush(QtGui.QColor("#d8c58f"))
        track_item = self.scene.addPath(track_shape, outline_pen, fill_brush)
        track_item.setZValue(1)

    def _add_guide_line(self, path: QtGui.QPainterPath) -> None:
        guide_color = QtGui.QColor("#8fa1b5")
        guide_color.setAlpha(85)
        pen = QtGui.QPen(
            guide_color,
            max(1.0, self.unit * 0.14),
            QtCore.Qt.PenStyle.SolidLine,
            QtCore.Qt.PenCapStyle.RoundCap,
            QtCore.Qt.PenJoinStyle.RoundJoin,
        )
        item = self.scene.addPath(path, pen)
        item.setZValue(1.5)

    def _add_center_seam(self, path: QtGui.QPainterPath) -> None:
        seam_color = QtGui.QColor("#7e704d")
        seam_color.setAlpha(185)
        pen = QtGui.QPen(
            seam_color,
            max(1.0, self.unit * 0.055),
            QtCore.Qt.PenStyle.SolidLine,
            QtCore.Qt.PenCapStyle.SquareCap,
            QtCore.Qt.PenJoinStyle.MiterJoin,
        )
        item = self.scene.addPath(path, pen)
        item.setZValue(2.15)

    def _seam_stride(self) -> int:
        count = len(self.points)
        if count <= 2500:
            return 1
        if count <= 5000:
            return 2
        if count <= 12000:
            return 5
        return 10

    def _local_direction(self, index: int) -> tuple[float, float]:
        if len(self.points) < 2:
            return (1.0, 0.0)
        if 0 < index < len(self.points) - 1:
            x1, y1, _angle1 = self.points[index - 1]
            x2, y2, _angle2 = self.points[index + 1]
        elif index > 0:
            x1, y1, _angle1 = self.points[index - 1]
            x2, y2, _angle2 = self.points[index]
        else:
            x1, y1, _angle1 = self.points[0]
            x2, y2, _angle2 = self.points[1]
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length <= 0.000001:
            return (1.0, 0.0)
        return (dx / length, dy / length)

    def _add_seams(self, track_width: float) -> None:
        stride = self._seam_stride()
        seam_color = QtGui.QColor("#7e704d")
        seam_color.setAlpha(215)
        pen = QtGui.QPen(seam_color, max(1.0, self.unit * 0.06))
        half = track_width * 0.48
        for index, (x, y, _angle) in enumerate(self.points):
            if index == 0 or index == len(self.points) - 1 or index % stride != 0:
                continue
            px = x * self.unit
            py = y * self.unit
            dx, dy = self._local_direction(index)
            nx = -dy
            ny = dx
            item = self.scene.addLine(px - nx * half, py - ny * half, px + nx * half, py + ny * half, pen)
            item.setZValue(2)

    def _add_center_points(self) -> None:
        pen = QtGui.QPen(QtGui.QColor("#574a33"), 0.8)
        brush = QtGui.QBrush(QtGui.QColor("#f2e6bd"))
        size = max(2.4, min(4.8, self.unit * 0.24))
        for index, (x, y, _angle) in enumerate(self.points[: self.center_item_limit]):
            if index == 0 or index == len(self.points) - 1:
                continue
            px = x * self.unit
            py = y * self.unit
            item = self.scene.addEllipse(px - size / 2, py - size / 2, size, size, pen, brush)
            item.setZValue(3)

    def _draw_background_grid(self) -> None:
        if len(self.points) < 2:
            return
        min_x = min(x for x, _y, _angle in self.points) * self.unit
        max_x = max(x for x, _y, _angle in self.points) * self.unit
        min_y = min(y for _x, y, _angle in self.points) * self.unit
        max_y = max(y for _x, y, _angle in self.points) * self.unit
        step = max(self.unit * 4.0, 48.0)
        pad = step
        left = math.floor((min_x - pad) / step) * step
        right = math.ceil((max_x + pad) / step) * step
        top = math.floor((min_y - pad) / step) * step
        bottom = math.ceil((max_y + pad) / step) * step
        line_count = max((right - left) / step, (bottom - top) / step)
        if line_count > 240:
            step *= math.ceil(line_count / 240)
        color = QtGui.QColor("#1b1f2a")
        color.setAlpha(90)
        pen = QtGui.QPen(color, 1.0)
        x = left
        while x <= right:
            item = self.scene.addLine(x, top, x, bottom, pen)
            item.setZValue(-10)
            x += step
        y = top
        while y <= bottom:
            item = self.scene.addLine(left, y, right, y, pen)
            item.setZValue(-10)
            y += step

    def _add_label(self, label: str, px: float, py: float, color: str, z: float) -> None:
        font = QtGui.QFont()
        font.setPointSize(8)
        text = self.scene.addSimpleText(label, font)
        text.setBrush(QtGui.QBrush(QtGui.QColor(color)))
        text_rect = text.boundingRect()
        bg_rect = QtCore.QRectF(
            px + 7,
            py - text_rect.height() - 5,
            text_rect.width() + 8,
            text_rect.height() + 4,
        )
        bg_color = QtGui.QColor("#101218")
        bg_color.setAlpha(210)
        bg = self.scene.addRect(bg_rect, QtGui.QPen(QtGui.QColor("#3a414c"), 0.8), QtGui.QBrush(bg_color))
        bg.setZValue(z)
        text.setPos(bg_rect.left() + 4, bg_rect.top() + 2)
        text.setZValue(z + 0.1)

    def _add_marker(
        self,
        point: tuple[float, float, float],
        label: str,
        color: QtGui.QColor,
        track_width: float,
        side: int,
    ) -> None:
        x, y, _angle = point
        px = x * self.unit
        py = y * self.unit
        size = max(14.0, min(20.0, track_width * 0.95))
        ring = QtGui.QColor(color)
        ring.setAlpha(235)
        fill = QtGui.QColor("#0b0d14")
        fill.setAlpha(235)
        pen = QtGui.QPen(ring, 2.4)
        brush = QtGui.QBrush(fill)
        item = self.scene.addEllipse(px - size / 2, py - size / 2, size, size, pen, brush)
        item.setZValue(5)
        center = self.scene.addEllipse(px - 2.5, py - 2.5, 5.0, 5.0, QtGui.QPen(QtCore.Qt.PenStyle.NoPen), QtGui.QBrush(ring))
        center.setZValue(5.1)
        if self.show_labels_check.isChecked():
            self._add_label(label, px + side * size * 0.9, py - size * 0.85, color.name(), 6)

    def _scale_changed(self) -> None:
        self.unit = float(self.scale_combo.currentData())
        self.draw_preview()
        self.reset_view()

    def reset_view(self) -> None:
        self.view.resetTransform()
        rect = self.scene.sceneRect()
        if rect.isValid() and not rect.isEmpty():
            self.view.fitInView(rect, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
