from __future__ import annotations


"""Viewport and corner-editor widgets for the heatmap alignment workbench."""

import math

import numpy as np
from heatmap_alignment_core_models import ExportOverlaySettings
from heatmap_alignment_widgets import ImagePreview, rgb_to_qpixmap

from PySide6 import QtCore, QtGui, QtWidgets


class ViewportEditorWidget(ImagePreview):
    corner_dragged = QtCore.Signal(int, float, float, float, float)
    edge_dragged = QtCore.Signal(int, float, float, float, float)
    center_dragged = QtCore.Signal(float, float, float, float)
    drag_finished = QtCore.Signal()

    def __init__(self, title: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.setMouseTracking(True)
        self._drag_index: int | None = None
        self._drag_edge: int | None = None
        self._drag_center = False
        self._start_viewport_pos: QtCore.QPointF | None = None
        self._handle_radius = 14.0
        self._edge_hit_distance = 18.0
        self._center_fraction = 0.6
        self._center_min_size = 64.0

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._pixmap is None:
            return
        handle_index = self._handle_hit_test(event.position())
        if handle_index is not None:
            self._drag_index = handle_index
            self._start_viewport_pos = self._widget_to_viewport(event.position(), clamp=False)
            self.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
            return

        edge_index = self._edge_hit_test(event.position())
        if edge_index is not None:
            self._drag_edge = edge_index
            self._start_viewport_pos = self._widget_to_viewport(event.position(), clamp=False)
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
            return

        if self._center_hit_test(event.position()):
            self._drag_center = True
            self._start_viewport_pos = self._widget_to_viewport(event.position(), clamp=False)
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
            return

        self.unsetCursor()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._pixmap is None:
            return
        current_pos = self._widget_to_viewport(event.position(), clamp=False)
        if self._drag_index is not None and self._start_viewport_pos is not None:
            self.corner_dragged.emit(
                self._drag_index,
                self._start_viewport_pos.x(),
                self._start_viewport_pos.y(),
                current_pos.x(),
                current_pos.y(),
            )
            return
        if self._drag_edge is not None and self._start_viewport_pos is not None:
            self.edge_dragged.emit(
                self._drag_edge,
                self._start_viewport_pos.x(),
                self._start_viewport_pos.y(),
                current_pos.x(),
                current_pos.y(),
            )
            return
        if self._drag_center and self._start_viewport_pos is not None:
            self.center_dragged.emit(
                self._start_viewport_pos.x(),
                self._start_viewport_pos.y(),
                current_pos.x(),
                current_pos.y(),
            )
            return
        self._update_hover_cursor(event.position())

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self._drag_index = None
        self._drag_edge = None
        self._drag_center = False
        self._start_viewport_pos = None
        self.drag_finished.emit()
        self._update_hover_cursor(event.position())

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        if self._drag_index is None and self._drag_edge is None and not self._drag_center:
            self.unsetCursor()
        super().leaveEvent(event)

    def _corners(self) -> list[QtCore.QPointF]:
        rect = self.contentsRect()
        return [
            QtCore.QPointF(rect.left(), rect.top()),
            QtCore.QPointF(rect.right(), rect.top()),
            QtCore.QPointF(rect.right(), rect.bottom()),
            QtCore.QPointF(rect.left(), rect.bottom()),
        ]

    def _handle_hit_test(self, widget_pos: QtCore.QPointF) -> int | None:
        for idx, corner in enumerate(self._corners()):
            if QtCore.QLineF(corner, widget_pos).length() <= self._handle_radius * 2.0:
                return idx
        return None

    def _edge_hit_test(self, widget_pos: QtCore.QPointF) -> int | None:
        corners = self._corners()
        for idx in range(4):
            start = corners[idx]
            end = corners[(idx + 1) % 4]
            if self._point_to_segment_distance(widget_pos, start, end) <= self._edge_hit_distance:
                return idx
        return None

    def _center_hit_test(self, widget_pos: QtCore.QPointF) -> bool:
        rect = self.contentsRect()
        center_width = min(
            rect.width(), max(rect.width() * self._center_fraction, self._center_min_size)
        )
        center_height = min(
            rect.height(), max(rect.height() * self._center_fraction, self._center_min_size)
        )
        center_rect = QtCore.QRectF(
            rect.center().x() - center_width / 2.0,
            rect.center().y() - center_height / 2.0,
            center_width,
            center_height,
        )
        return center_rect.contains(widget_pos)

    def _widget_to_viewport(
        self,
        widget_pos: QtCore.QPointF,
        *,
        clamp: bool = True,
    ) -> QtCore.QPointF:
        rect = self.contentsRect()
        if self._pixmap is None or rect.width() <= 1 or rect.height() <= 1:
            return QtCore.QPointF(0.0, 0.0)
        width = max(1, self._pixmap.width())
        height = max(1, self._pixmap.height())
        x = (widget_pos.x() - rect.left()) * width / rect.width()
        y = (widget_pos.y() - rect.top()) * height / rect.height()
        if clamp:
            x = float(np.clip(x, 0, width - 1))
            y = float(np.clip(y, 0, height - 1))
        return QtCore.QPointF(float(x), float(y))

    def _update_hover_cursor(self, widget_pos: QtCore.QPointF) -> None:
        if self._pixmap is None:
            self.unsetCursor()
            return
        if self._handle_hit_test(widget_pos) is not None:
            self.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
            return
        if self._edge_hit_test(widget_pos) is not None:
            self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
            return
        if self._center_hit_test(widget_pos):
            self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
            return
        self.unsetCursor()

    @staticmethod
    def _point_to_segment_distance(
        point: QtCore.QPointF,
        start: QtCore.QPointF,
        end: QtCore.QPointF,
    ) -> float:
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return math.hypot(point.x() - start.x(), point.y() - start.y())
        t = ((point.x() - start.x()) * dx + (point.y() - start.y()) * dy) / (dx * dx + dy * dy)
        t = min(1.0, max(0.0, t))
        proj_x = start.x() + t * dx
        proj_y = start.y() + t * dy
        return math.hypot(point.x() - proj_x, point.y() - proj_y)


class CornerEditorWidget(QtWidgets.QWidget):
    corners_changed = QtCore.Signal(list)
    export_overlay_changed = QtCore.Signal(float, float, float, float)
    export_overlay_visibility_changed = QtCore.Signal(bool)
    export_overlay_preview_toggled = QtCore.Signal(bool)
    export_overlay_reset_requested = QtCore.Signal()
    export_overlay_drag_active_changed = QtCore.Signal(bool)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(480, 260)
        self.setMouseTracking(True)
        self._frame_rgb: np.ndarray | None = None
        self._pixmap: QtGui.QPixmap | None = None
        self._corners: np.ndarray | None = None
        self._drag_index: int | None = None
        self._drag_edge: int | None = None
        self._drag_center = False
        self._start_drag_image_pos: QtCore.QPointF | None = None
        self._start_drag_corners: np.ndarray | None = None
        self._handle_radius = 10.0
        self._edge_hit_distance = 14.0
        self._center_fraction = 0.6
        self._center_min_size = 56.0
        self._export_overlay_rect: QtCore.QRectF | None = None
        self._export_overlay_visible = True
        self._export_overlay_preview_enabled = True
        self._export_overlay_preview_rgb: np.ndarray | None = None
        self._export_overlay_preview_pixmap: QtGui.QPixmap | None = None
        self._overlay_drag_corner: int | None = None
        self._overlay_drag_edge: int | None = None
        self._overlay_drag_center = False
        self._overlay_drag_anchor_image_pos: QtCore.QPointF | None = None
        self._overlay_drag_start_rect: QtCore.QRectF | None = None
        self._loading_overlay_active = False
        self._loading_overlay_message = ""
        self._dim_content = False

    def set_frame(self, frame_rgb: np.ndarray | None) -> None:
        self._frame_rgb = frame_rgb
        self._pixmap = rgb_to_qpixmap(frame_rgb) if frame_rgb is not None else None
        self.update()

    def set_loading_overlay(
        self,
        active: bool,
        message: str = "",
        *,
        dim_content: bool = True,
    ) -> None:
        self._loading_overlay_active = active
        self._loading_overlay_message = message
        self._dim_content = dim_content
        self.update()

    def set_corners(self, corners: list[list[float]] | np.ndarray | None) -> None:
        if corners is None or len(corners) == 0:
            self._corners = None
        else:
            self._corners = np.array(corners, dtype=np.float32)
        self.update()

    def set_export_overlay(self, overlay: ExportOverlaySettings) -> None:
        self._export_overlay_visible = overlay.visible
        self._export_overlay_preview_enabled = overlay.preview_enabled
        if overlay.width > 0.0 and overlay.height > 0.0:
            self._export_overlay_rect = QtCore.QRectF(
                overlay.x,
                overlay.y,
                overlay.width,
                overlay.height,
            )
        else:
            self._export_overlay_rect = None
        self.update()

    def set_export_overlay_preview_frame(self, frame_rgb: np.ndarray | None) -> None:
        self._export_overlay_preview_rgb = frame_rgb
        self._export_overlay_preview_pixmap = (
            rgb_to_qpixmap(frame_rgb) if frame_rgb is not None else None
        )
        self.update()

    def current_corners(self) -> np.ndarray | None:
        return None if self._corners is None else self._corners.copy()

    def initialize_default_corners(self) -> None:
        if self._frame_rgb is None:
            return
        height, width = self._frame_rgb.shape[:2]
        inset_x = width * 0.15
        inset_y = height * 0.15
        self._corners = np.array(
            [
                [inset_x, inset_y],
                [width - inset_x, inset_y],
                [width - inset_x, height - inset_y],
                [inset_x, height - inset_y],
            ],
            dtype=np.float32,
        )
        self.corners_changed.emit(self._corners.tolist())
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        try:
            painter.fillRect(self.rect(), QtGui.QColor("#0f1720"))

            if self._pixmap is None:
                if not self._loading_overlay_active:
                    painter.setPen(QtGui.QColor("#d7dde6"))
                    painter.drawText(
                        self.rect(),
                        QtCore.Qt.AlignmentFlag.AlignCenter,
                        "Camera Video",
                    )
                self._paint_loading_overlay(painter)
                return

            target_rect = self._target_rect()
            if self._loading_overlay_active and self._dim_content:
                painter.setOpacity(0.35)
            painter.drawPixmap(target_rect.toRect(), self._pixmap)
            painter.setOpacity(1.0)
            self._paint_export_overlay(painter)
            if self._corners is None:
                self._paint_loading_overlay(painter)
                return

            display_corners = [
                self._image_to_widget(QtCore.QPointF(float(x), float(y))) for x, y in self._corners
            ]
            pen = QtGui.QPen(QtGui.QColor("#ff4d4f"), 2)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.drawPolygon(QtGui.QPolygonF(display_corners))
            brush = QtGui.QBrush(QtGui.QColor("#ffb703"))
            painter.setBrush(brush)
            for point in display_corners:
                painter.drawEllipse(point, self._handle_radius, self._handle_radius)
            self._paint_loading_overlay(painter)
        finally:
            painter.end()

    def _paint_loading_overlay(self, painter: QtGui.QPainter) -> None:
        if not self._loading_overlay_active:
            return
        painter.fillRect(
            self.rect(),
            QtGui.QColor(15, 23, 32, 180),
        )
        painter.setPen(QtGui.QColor("#d7dde6"))
        painter.drawText(
            self.rect(),
            int(QtCore.Qt.AlignmentFlag.AlignCenter),
            self._loading_overlay_message or "Loading...",
        )

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._frame_rgb is None:
            return
        if event.button() == QtCore.Qt.MouseButton.RightButton:
            return

        image_pos = self._widget_to_image(event.position())
        if self._corners is not None:
            handle_index = self._handle_hit_test(event.position())
            if handle_index is not None:
                self._drag_index = handle_index
                self.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
                return

            edge_index = self._edge_hit_test(event.position())
            if edge_index is not None:
                self._drag_edge = edge_index
                self._start_drag_image_pos = image_pos
                self._start_drag_corners = self._corners.copy()
                self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
                return

            if self._center_hit_test(image_pos):
                self._drag_center = True
                self._start_drag_image_pos = image_pos
                self._start_drag_corners = self._corners.copy()
                self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
                return

        if self._export_overlay_visible and self._export_overlay_rect is not None:
            overlay_corner = self._export_overlay_corner_hit_test(event.position())
            if overlay_corner is not None:
                self._overlay_drag_corner = overlay_corner
                self._overlay_drag_anchor_image_pos = image_pos
                self._overlay_drag_start_rect = QtCore.QRectF(self._export_overlay_rect)
                self.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
                self.export_overlay_drag_active_changed.emit(True)
                return

            overlay_edge = self._export_overlay_edge_hit_test(event.position())
            if overlay_edge is not None:
                self._overlay_drag_edge = overlay_edge
                self._overlay_drag_anchor_image_pos = image_pos
                self._overlay_drag_start_rect = QtCore.QRectF(self._export_overlay_rect)
                self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
                self.export_overlay_drag_active_changed.emit(True)
                return

            if self._export_overlay_center_hit_test(image_pos):
                self._overlay_drag_center = True
                self._overlay_drag_anchor_image_pos = image_pos
                self._overlay_drag_start_rect = QtCore.QRectF(self._export_overlay_rect)
                self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
                self.export_overlay_drag_active_changed.emit(True)
                return

        self.unsetCursor()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._frame_rgb is None:
            return

        if self._overlay_drag_corner is not None:
            self._resize_export_overlay_from_corner(self._widget_to_image(event.position()))
            return

        if self._overlay_drag_edge is not None:
            self._resize_export_overlay_from_edge(self._widget_to_image(event.position()))
            return

        if self._overlay_drag_center:
            self._translate_export_overlay(self._widget_to_image(event.position()))
            return

        if self._corners is None:
            self._update_hover_cursor(event.position())
            return

        if self._drag_index is not None:
            image_pos = self._widget_to_image(event.position())
            height, width = self._frame_rgb.shape[:2]
            image_x = float(np.clip(image_pos.x(), 0, width - 1))
            image_y = float(np.clip(image_pos.y(), 0, height - 1))
            self._corners[self._drag_index] = [image_x, image_y]
            self.corners_changed.emit(self._corners.tolist())
            self.update()
            return

        if self._drag_edge is not None or self._drag_center:
            image_pos = self._widget_to_image(event.position())
            self._translate_drag(image_pos)
            return

        self._update_hover_cursor(event.position())

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self._drag_index = None
        self._drag_edge = None
        self._drag_center = False
        self._start_drag_image_pos = None
        self._start_drag_corners = None
        overlay_was_active = (
            self._overlay_drag_corner is not None
            or self._overlay_drag_edge is not None
            or self._overlay_drag_center
        )
        self._overlay_drag_corner = None
        self._overlay_drag_edge = None
        self._overlay_drag_center = False
        self._overlay_drag_anchor_image_pos = None
        self._overlay_drag_start_rect = None
        if overlay_was_active:
            self.export_overlay_drag_active_changed.emit(False)
        self._update_hover_cursor(event.position())

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        if (
            self._drag_index is None
            and self._drag_edge is None
            and not self._drag_center
            and self._overlay_drag_corner is None
            and self._overlay_drag_edge is None
            and not self._overlay_drag_center
        ):
            self.unsetCursor()
        super().leaveEvent(event)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        if self._frame_rgb is None:
            return
        menu = QtWidgets.QMenu(self)
        show_overlay_action = menu.addAction("Show Export Overlay")
        show_overlay_action.setCheckable(True)
        show_overlay_action.setChecked(self._export_overlay_visible)
        show_preview_action = menu.addAction("Show Overlay Preview")
        show_preview_action.setCheckable(True)
        show_preview_action.setChecked(self._export_overlay_preview_enabled)
        show_preview_action.setEnabled(self._export_overlay_visible)
        reset_overlay_action = menu.addAction("Reset Export Overlay")
        action = menu.exec(event.globalPos())
        if action is show_overlay_action:
            self.export_overlay_visibility_changed.emit(show_overlay_action.isChecked())
        elif action is show_preview_action:
            self.export_overlay_preview_toggled.emit(show_preview_action.isChecked())
        elif action is reset_overlay_action:
            self.export_overlay_reset_requested.emit()

    def _target_rect(self) -> QtCore.QRectF:
        if self._pixmap is None:
            return QtCore.QRectF(self.rect())
        scaled = self._pixmap.size()
        scaled.scale(self.size(), QtCore.Qt.AspectRatioMode.KeepAspectRatio)
        x = (self.width() - scaled.width()) / 2
        y = (self.height() - scaled.height()) / 2
        return QtCore.QRectF(x, y, scaled.width(), scaled.height())

    def _image_to_widget(self, point: QtCore.QPointF) -> QtCore.QPointF:
        if self._frame_rgb is None:
            return point
        height, width = self._frame_rgb.shape[:2]
        rect = self._target_rect()
        scale_x = rect.width() / width
        scale_y = rect.height() / height
        return QtCore.QPointF(rect.left() + point.x() * scale_x, rect.top() + point.y() * scale_y)

    def _widget_to_image(self, point: QtCore.QPointF) -> QtCore.QPointF:
        if self._frame_rgb is None:
            return point
        height, width = self._frame_rgb.shape[:2]
        rect = self._target_rect()
        scale_x = width / rect.width()
        scale_y = height / rect.height()
        return QtCore.QPointF(
            (point.x() - rect.left()) * scale_x, (point.y() - rect.top()) * scale_y
        )

    def _display_corners(self) -> list[QtCore.QPointF]:
        if self._corners is None:
            return []
        return [
            self._image_to_widget(QtCore.QPointF(float(x), float(y))) for x, y in self._corners
        ]

    def _handle_hit_test(self, widget_pos: QtCore.QPointF) -> int | None:
        for idx, corner in enumerate(self._display_corners()):
            if QtCore.QLineF(corner, widget_pos).length() <= self._handle_radius * 2.0:
                return idx
        return None

    def _edge_hit_test(self, widget_pos: QtCore.QPointF) -> int | None:
        display_corners = self._display_corners()
        if len(display_corners) != 4:
            return None
        for idx in range(4):
            start = display_corners[idx]
            end = display_corners[(idx + 1) % 4]
            if self._point_to_segment_distance(widget_pos, start, end) <= self._edge_hit_distance:
                return idx
        return None

    def _center_hit_test(self, image_pos: QtCore.QPointF) -> bool:
        if self._corners is None:
            return False
        min_x = float(np.min(self._corners[:, 0]))
        max_x = float(np.max(self._corners[:, 0]))
        min_y = float(np.min(self._corners[:, 1]))
        max_y = float(np.max(self._corners[:, 1]))
        width = max_x - min_x
        height = max_y - min_y
        center_width = min(width, max(width * self._center_fraction, self._center_min_size))
        center_height = min(height, max(height * self._center_fraction, self._center_min_size))
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        return (
            abs(image_pos.x() - center_x) <= center_width / 2.0
            and abs(image_pos.y() - center_y) <= center_height / 2.0
        )

    def _translate_drag(self, image_pos: QtCore.QPointF) -> None:
        if (
            self._corners is None
            or self._frame_rgb is None
            or self._start_drag_image_pos is None
            or self._start_drag_corners is None
        ):
            return
        height, width = self._frame_rgb.shape[:2]
        dx = image_pos.x() - self._start_drag_image_pos.x()
        dy = image_pos.y() - self._start_drag_image_pos.y()

        if self._drag_edge is None:
            indices = [0, 1, 2, 3]
        else:
            indices = [self._drag_edge, (self._drag_edge + 1) % 4]

        trial = self._start_drag_corners.copy()
        trial[indices, 0] += dx
        trial[indices, 1] += dy

        min_dx = 0.0
        max_dx = 0.0
        min_dy = 0.0
        max_dy = 0.0
        subset = trial[indices]
        min_x = float(np.min(subset[:, 0]))
        max_x = float(np.max(subset[:, 0]))
        min_y = float(np.min(subset[:, 1]))
        max_y = float(np.max(subset[:, 1]))
        if min_x < 0.0:
            min_dx = -min_x
        if max_x > width - 1:
            max_dx = (width - 1) - max_x
        if min_y < 0.0:
            min_dy = -min_y
        if max_y > height - 1:
            max_dy = (height - 1) - max_y

        adjusted_dx = dx + min_dx + max_dx
        adjusted_dy = dy + min_dy + max_dy
        self._corners = self._start_drag_corners.copy()
        self._corners[indices, 0] = np.clip(
            self._start_drag_corners[indices, 0] + adjusted_dx,
            0,
            width - 1,
        )
        self._corners[indices, 1] = np.clip(
            self._start_drag_corners[indices, 1] + adjusted_dy,
            0,
            height - 1,
        )
        self.corners_changed.emit(self._corners.tolist())
        self.update()

    def _update_hover_cursor(self, widget_pos: QtCore.QPointF) -> None:
        if self._frame_rgb is None:
            self.unsetCursor()
            return
        image_pos = self._widget_to_image(widget_pos)
        if self._corners is None:
            if self._export_overlay_visible and self._export_overlay_rect is not None:
                if self._export_overlay_corner_hit_test(widget_pos) is not None:
                    self.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
                    return
                if self._export_overlay_edge_hit_test(widget_pos) is not None:
                    self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
                    return
                if self._export_overlay_center_hit_test(image_pos):
                    self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
                    return
            self.unsetCursor()
            return
        if self._handle_hit_test(widget_pos) is not None:
            self.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
            return
        if self._edge_hit_test(widget_pos) is not None:
            self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
            return
        if self._center_hit_test(image_pos):
            self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
            return
        if self._export_overlay_visible and self._export_overlay_rect is not None:
            if self._export_overlay_corner_hit_test(widget_pos) is not None:
                self.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
                return
            if self._export_overlay_edge_hit_test(widget_pos) is not None:
                self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
                return
            if self._export_overlay_center_hit_test(image_pos):
                self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
                return
        self.unsetCursor()

    def _paint_export_overlay(self, painter: QtGui.QPainter) -> None:
        if not self._export_overlay_visible or self._export_overlay_rect is None:
            return
        top_left = self._image_to_widget(
            QtCore.QPointF(self._export_overlay_rect.left(), self._export_overlay_rect.top())
        )
        bottom_right = self._image_to_widget(
            QtCore.QPointF(self._export_overlay_rect.right(), self._export_overlay_rect.bottom())
        )
        display_rect = QtCore.QRectF(top_left, bottom_right).normalized()
        if (
            self._export_overlay_preview_enabled
            and self._export_overlay_preview_pixmap is not None
        ):
            painter.drawPixmap(display_rect.toRect(), self._export_overlay_preview_pixmap)

        pen = QtGui.QPen(QtGui.QColor("#38bdf8"), 2)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawRect(display_rect)

        handle_brush = QtGui.QBrush(QtGui.QColor("#7dd3fc"))
        painter.setBrush(handle_brush)
        for point in self._export_overlay_display_corners():
            painter.drawEllipse(point, self._handle_radius, self._handle_radius)

    def _export_overlay_display_corners(self) -> list[QtCore.QPointF]:
        if self._export_overlay_rect is None:
            return []
        rect = self._export_overlay_rect
        return [
            self._image_to_widget(QtCore.QPointF(rect.left(), rect.top())),
            self._image_to_widget(QtCore.QPointF(rect.right(), rect.top())),
            self._image_to_widget(QtCore.QPointF(rect.right(), rect.bottom())),
            self._image_to_widget(QtCore.QPointF(rect.left(), rect.bottom())),
        ]

    def _export_overlay_corner_hit_test(self, widget_pos: QtCore.QPointF) -> int | None:
        for idx, corner in enumerate(self._export_overlay_display_corners()):
            if QtCore.QLineF(corner, widget_pos).length() <= self._handle_radius * 2.0:
                return idx
        return None

    def _export_overlay_edge_hit_test(self, widget_pos: QtCore.QPointF) -> int | None:
        corners = self._export_overlay_display_corners()
        if len(corners) != 4:
            return None
        for idx in range(4):
            start = corners[idx]
            end = corners[(idx + 1) % 4]
            if self._point_to_segment_distance(widget_pos, start, end) <= self._edge_hit_distance:
                return idx
        return None

    def _export_overlay_center_hit_test(self, image_pos: QtCore.QPointF) -> bool:
        return self._export_overlay_rect is not None and self._export_overlay_rect.contains(
            image_pos
        )

    def _translate_export_overlay(self, image_pos: QtCore.QPointF) -> None:
        if (
            self._overlay_drag_anchor_image_pos is None
            or self._overlay_drag_start_rect is None
            or self._frame_rgb is None
        ):
            return
        height, width = self._frame_rgb.shape[:2]
        dx = image_pos.x() - self._overlay_drag_anchor_image_pos.x()
        dy = image_pos.y() - self._overlay_drag_anchor_image_pos.y()
        rect = QtCore.QRectF(self._overlay_drag_start_rect)
        rect.translate(dx, dy)
        if rect.left() < 0.0:
            rect.moveLeft(0.0)
        if rect.right() > width - 1:
            rect.moveRight(width - 1)
        if rect.top() < 0.0:
            rect.moveTop(0.0)
        if rect.bottom() > height - 1:
            rect.moveBottom(height - 1)
        self._set_export_overlay_rect(rect)

    def _resize_export_overlay_from_corner(self, image_pos: QtCore.QPointF) -> None:
        if (
            self._overlay_drag_corner is None
            or self._overlay_drag_start_rect is None
            or self._frame_rgb is None
        ):
            return
        rect = self._overlay_drag_start_rect
        opposite_points = [
            QtCore.QPointF(rect.right(), rect.bottom()),
            QtCore.QPointF(rect.left(), rect.bottom()),
            QtCore.QPointF(rect.left(), rect.top()),
            QtCore.QPointF(rect.right(), rect.top()),
        ]
        opposite = opposite_points[self._overlay_drag_corner]
        self._set_export_overlay_rect(
            self._normalized_overlay_rect(
                opposite,
                self._clamp_image_point(image_pos),
            )
        )

    def _resize_export_overlay_from_edge(self, image_pos: QtCore.QPointF) -> None:
        if self._overlay_drag_edge is None or self._overlay_drag_start_rect is None:
            return
        point = self._clamp_image_point(image_pos)
        rect = QtCore.QRectF(self._overlay_drag_start_rect)
        if self._overlay_drag_edge == 0:
            rect.setTop(min(point.y(), rect.bottom() - 1.0))
        elif self._overlay_drag_edge == 1:
            rect.setRight(max(point.x(), rect.left() + 1.0))
        elif self._overlay_drag_edge == 2:
            rect.setBottom(max(point.y(), rect.top() + 1.0))
        else:
            rect.setLeft(min(point.x(), rect.right() - 1.0))
        self._set_export_overlay_rect(rect.normalized())

    def _normalized_overlay_rect(
        self,
        point_a: QtCore.QPointF,
        point_b: QtCore.QPointF,
    ) -> QtCore.QRectF:
        left = min(point_a.x(), point_b.x())
        right = max(point_a.x(), point_b.x())
        top = min(point_a.y(), point_b.y())
        bottom = max(point_a.y(), point_b.y())
        if math.isclose(left, right):
            right = left + 1.0
        if math.isclose(top, bottom):
            bottom = top + 1.0
        return QtCore.QRectF(left, top, right - left, bottom - top)

    def _clamp_image_point(self, point: QtCore.QPointF) -> QtCore.QPointF:
        if self._frame_rgb is None:
            return point
        height, width = self._frame_rgb.shape[:2]
        return QtCore.QPointF(
            float(np.clip(point.x(), 0.0, width - 1.0)),
            float(np.clip(point.y(), 0.0, height - 1.0)),
        )

    def _set_export_overlay_rect(self, rect: QtCore.QRectF) -> None:
        self._export_overlay_rect = rect.normalized()
        self.export_overlay_changed.emit(
            float(self._export_overlay_rect.x()),
            float(self._export_overlay_rect.y()),
            float(self._export_overlay_rect.width()),
            float(self._export_overlay_rect.height()),
        )
        self.update()

    @staticmethod
    def _point_to_segment_distance(
        point: QtCore.QPointF,
        start: QtCore.QPointF,
        end: QtCore.QPointF,
    ) -> float:
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return math.hypot(point.x() - start.x(), point.y() - start.y())
        t = ((point.x() - start.x()) * dx + (point.y() - start.y()) * dy) / (dx * dx + dy * dy)
        t = min(1.0, max(0.0, t))
        proj_x = start.x() + t * dx
        proj_y = start.y() + t * dy
        return math.hypot(point.x() - proj_x, point.y() - proj_y)
