from __future__ import annotations

"""Basic preview widgets for the heatmap alignment workbench."""

from typing import Literal

import numpy as np

from PySide6 import QtCore, QtGui, QtWidgets

from heatmap_alignment_core import detection_ratio_strip_rgb


def rgb_to_qpixmap(frame_rgb: np.ndarray) -> QtGui.QPixmap:
    if frame_rgb.ndim != 3 or frame_rgb.shape[2] != 3:
        raise ValueError("Expected RGB frame with shape (H, W, 3).")
    height, width, _ = frame_rgb.shape
    bytes_per_line = 3 * width
    image = QtGui.QImage(
        frame_rgb.data,
        width,
        height,
        bytes_per_line,
        QtGui.QImage.Format.Format_RGB888,
    )
    return QtGui.QPixmap.fromImage(image.copy())


class ImagePreview(QtWidgets.QLabel):
    resized = QtCore.Signal()

    def __init__(self, title: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 200)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.setFrameShape(QtWidgets.QFrame.Shape.Box)
        self.setStyleSheet("background: #0f1720; color: #d7dde6;")
        self.setText(title)
        self._title = title
        self._pixmap: QtGui.QPixmap | None = None
        self._loading_overlay_active = False
        self._loading_overlay_message = ""
        self._dim_content = False

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
        if active and self._pixmap is None:
            self.clear()
        elif not active and self._pixmap is None:
            self.setText(self._title)
        self.update()

    def set_frame(self, frame_rgb: np.ndarray | None) -> None:
        if frame_rgb is None:
            self._pixmap = None
            if not self._loading_overlay_active:
                self.setText(self._title)
            else:
                self.clear()
            self.update()
            return
        self.clear()
        self._pixmap = rgb_to_qpixmap(frame_rgb)
        self.update()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self.resized.emit()
        self.update()

    def rendered_image_rect(self) -> QtCore.QRect:
        return self.contentsRect()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        contents_rect = self.contentsRect()
        if self._pixmap is None and self._loading_overlay_active:
            painter = QtGui.QPainter(self)
            try:
                painter.fillRect(contents_rect, QtGui.QColor("#0f1720"))
                painter.fillRect(
                    contents_rect,
                    QtGui.QColor(15, 23, 32, 180),
                )
                painter.setPen(QtGui.QColor("#d7dde6"))
                painter.drawText(
                    contents_rect,
                    int(QtCore.Qt.AlignmentFlag.AlignCenter),
                    self._loading_overlay_message or "Loading...",
                )
            finally:
                painter.end()
            return
        super().paintEvent(event)
        if self._pixmap is None and not self._loading_overlay_active:
            return
        painter = QtGui.QPainter(self)
        try:
            if self._pixmap is not None:
                scaled = self._pixmap.scaled(
                    contents_rect.size(),
                    QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
                    QtCore.Qt.TransformationMode.FastTransformation,
                )
                if self._loading_overlay_active and self._dim_content:
                    painter.setOpacity(0.35)
                painter.drawPixmap(contents_rect.topLeft(), scaled)
                painter.setOpacity(1.0)
            if self._loading_overlay_active:
                painter.fillRect(
                    contents_rect,
                    QtGui.QColor(15, 23, 32, 180),
                )
                painter.setPen(QtGui.QColor("#d7dde6"))
                painter.drawText(
                    contents_rect,
                    int(QtCore.Qt.AlignmentFlag.AlignCenter),
                    self._loading_overlay_message or "Loading...",
                )
        finally:
            painter.end()


class DoubleRangeSlider(QtWidgets.QWidget):
    values_changed = QtCore.Signal(float, float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(26)
        self.setMinimumWidth(140)
        self._minimum = 0.0
        self._maximum = 1.0
        self._lower = 0.0
        self._upper = 1.0
        self._active_handle: Literal["lower", "upper"] | None = None
        self._handle_radius = 7.0

    def set_values(self, lower: float, upper: float) -> None:
        lower = float(np.clip(lower, self._minimum, self._maximum))
        upper = float(np.clip(upper, self._minimum, self._maximum))
        if lower > upper:
            lower, upper = upper, lower
        self._lower = lower
        self._upper = upper
        self.update()

    def values(self) -> tuple[float, float]:
        return self._lower, self._upper

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        try:
            rect = self.contentsRect().adjusted(8, 6, -8, -6)
            center_y = rect.center().y()
            left_x = rect.left()
            right_x = rect.right()
            lower_x = self._value_to_x(self._lower, rect)
            upper_x = self._value_to_x(self._upper, rect)

            track_color = QtGui.QColor("#334155") if self.isEnabled() else QtGui.QColor("#1f2937")
            active_color = QtGui.QColor("#38bdf8") if self.isEnabled() else QtGui.QColor("#475569")
            handle_color = QtGui.QColor("#e2e8f0") if self.isEnabled() else QtGui.QColor("#64748b")

            painter.setPen(QtGui.QPen(track_color, 3))
            painter.drawLine(QtCore.QPointF(left_x, center_y), QtCore.QPointF(right_x, center_y))
            painter.setPen(QtGui.QPen(active_color, 4))
            painter.drawLine(QtCore.QPointF(lower_x, center_y), QtCore.QPointF(upper_x, center_y))

            painter.setPen(QtGui.QPen(QtGui.QColor("#0f1720"), 1))
            painter.setBrush(QtGui.QBrush(handle_color))
            painter.drawEllipse(
                QtCore.QPointF(lower_x, center_y), self._handle_radius, self._handle_radius
            )
            painter.drawEllipse(
                QtCore.QPointF(upper_x, center_y), self._handle_radius, self._handle_radius
            )
        finally:
            painter.end()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if not self.isEnabled():
            return
        rect = self.contentsRect().adjusted(8, 6, -8, -6)
        lower_x = self._value_to_x(self._lower, rect)
        upper_x = self._value_to_x(self._upper, rect)
        x = event.position().x()
        if abs(x - lower_x) <= abs(x - upper_x):
            self._active_handle = "lower"
        else:
            self._active_handle = "upper"
        self._update_active_handle(event.position().x(), rect)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if not self.isEnabled() or self._active_handle is None:
            return
        rect = self.contentsRect().adjusted(8, 6, -8, -6)
        self._update_active_handle(event.position().x(), rect)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        del event
        self._active_handle = None

    def _update_active_handle(self, x: float, rect: QtCore.QRect) -> None:
        value = self._x_to_value(x, rect)
        min_gap = 1.0 / 255.0
        if self._active_handle == "lower":
            self._lower = min(value, self._upper - min_gap)
        elif self._active_handle == "upper":
            self._upper = max(value, self._lower + min_gap)
        self.update()
        self.values_changed.emit(self._lower, self._upper)

    def _value_to_x(self, value: float, rect: QtCore.QRect) -> float:
        span = max(self._maximum - self._minimum, 1e-6)
        fraction = (value - self._minimum) / span
        return rect.left() + fraction * rect.width()

    def _x_to_value(self, x: float, rect: QtCore.QRect) -> float:
        if rect.width() <= 0:
            return self._minimum
        fraction = np.clip((x - rect.left()) / rect.width(), 0.0, 1.0)
        return float(self._minimum + fraction * (self._maximum - self._minimum))


class DetectionStripWidget(QtWidgets.QWidget):
    """Fixed-height colorbar showing per-bin detection ratio, independent of velocity bins."""

    _STRIP_HEIGHT_PX = 12

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(self._STRIP_HEIGHT_PX)
        self._detection_ratio: np.ndarray | None = None

    def set_detection_ratio(self, detection_ratio: np.ndarray | None) -> None:
        self._detection_ratio = detection_ratio
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return
        if self._detection_ratio is None or len(self._detection_ratio) == 0:
            QtWidgets.QWidget.paintEvent(self, event)
            return
        strip_row = detection_ratio_strip_rgb(self._detection_ratio, w)  # (1, w, 3)
        row_uint8 = np.ascontiguousarray(strip_row[0])  # (w, 3)
        image = QtGui.QImage(
            row_uint8.data,
            w,
            1,
            3 * w,
            QtGui.QImage.Format.Format_RGB888,
        )
        pixmap = QtGui.QPixmap.fromImage(image.copy())
        painter = QtGui.QPainter(self)
        painter.drawPixmap(QtCore.QRect(0, 0, w, h), pixmap)
        painter.end()
