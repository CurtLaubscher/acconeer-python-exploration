from __future__ import annotations


"""PySide6 workbench for manual camera-to-heatmap alignment.

Launch this tool through Hatch so it uses the repo-managed GUI/runtime
dependencies:

    hatch run app:heatmap-align

or:

    hatch run app:python user_tools/heatmap_alignment_gui.py

The GUI keeps lightweight local settings for the last-used file dialog
locations.

Startup file arguments are supported, for example:

    hatch run app:heatmap-align -- --camera path\\to\\video.mp4 --h5 path\\to\\record.h5
    hatch run app:heatmap-align -- --h5 path\\to\\record.h5 --peaks path\\to\\peaks.json
    hatch run app:heatmap-align -- --mat path\\to\\leg2.mat
"""

import argparse
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from heatmap_alignment_core import (
    H5_TIMELINE_TRACK_COLOR_HEX,
    LEG2_TIMELINE_TRACK_COLOR_HEX,
    SIGNAL_PLAYHEAD_ALPHA,
    SIGNAL_PLOT_BACKGROUND_HEX,
    SIGNAL_PLOT_NO_DETECTION_ALPHA,
    SIGNAL_PLOT_PRIMARY_SEGMENT_ALPHA,
    TIMELINE_PLAYHEAD_COLOR_HEX,
    AlignmentResourceRuntime,
    AlignmentSession,
    CameraTrack,
    CameraVideoSource,
    ExportOverlaySettings,
    HeatmapPlotRenderer,
    HeatmapTrack,
    HeatmapTruthSource,
    Leg2MatImportError,
    Leg2UltrasonicSignalSeries,
    LoadedLeg2UltrasonicDatasource,
    LoadedPeakDistanceDatasource,
    PeakDistanceSignalSeries,
    ResourceAction,
    ResourceJobPresentation,
    ResourceKind,
    ResourceSummary,
    SignalPlotViewSettings,
    apply_viewport_visibility,
    build_alignment_resource_summaries,
    build_leg2_ultrasonic_signal_series,
    build_peak_distance_signal_series,
    derive_signal_plot_color,
    elide_path_middle,
    import_leg2_mat_for_heatmap,
    import_peak_distance_json_for_heatmap,
    load_alignment_session,
    rectify_viewport,
    save_alignment_session,
    scale_viewport_corners,
    TimelineH5DragSnapshot,
    apply_timeline_h5_alignment_drag,
    timeline_h5_drag_affects_alignment,
    timeline_view_bounds_s,
    validate_alignment_session,
    visible_signal_y_range,
)
from sparse_iq_heatmap_common import heatmap_axes, select_subsweep
from heatmap_alignment_resource_jobs import (
    CameraResourceJobResult,
    LoadedH5ResourcePayload,
    ResourceJobBoard,
    ResourceJobError,
    ResourceJobKind,
    ResourceJobSnapshot,
    ResourceJobSlotState,
    begin_resource_job,
    build_h5_truth_source_from_payload,
    clear_resource_job,
    complete_resource_job,
    load_h5_resource_payload,
    mark_resource_job_phase,
    release_resource_job_result,
    replacement_viewport_needs_default_reset,
    request_cancel_resource_job,
    resolve_replacement_viewport_corners,
    resource_job_blocks_export,
    resource_job_target_filename,
    run_camera_resource_job,
    should_apply_job_result,
)
from sparse_iq_peak_distance_core import (
    STATUS_DETECTED,
    PeakDistanceJsonImportError,
    annotate_heatmap_rgb_with_peak,
    measurement_for_frame,
)

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

import pyqtgraph as pg


RESOURCE_STATUS_LABELS = {
    "unloaded": "Unloaded",
    "loaded": "Loaded",
    "missing": "Missing",
    "invalid": "Invalid",
    "warning": "Warning",
}

RESOURCES_DETAILS_SECTION_SPACING_PX = 6
RESOURCES_DETAILS_PATH_BLOCK_TOP_MARGIN_PX = 6

RESOURCE_ACTION_LABELS: dict[ResourceAction, str] = {
    "load": "&Load...",
    "replace": "&Replace...",
    "unload": "&Unload",
    "reload": "&Reload",
    "reveal": "Show in &File Manager",
    "inspect": "Inspect &Warnings",
    "cancel": "&Cancel Load",
}

RESOURCE_JOB_STATUS_LABELS = {
    "idle": "Unloaded",
    "pending": "Loading",
    "loading": "Loading",
    "building": "Building",
    "waiting": "Waiting",
    "cancelling": "Cancelling",
    "failed": "Failed",
    "superseded": "Superseded",
}


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


def _plot_color_with_alpha(plot_color_hex: str, alpha: int) -> str:
    normalized = plot_color_hex.strip().lstrip("#")
    if len(normalized) != 6:
        raise ValueError(f"Expected #RRGGBB color, got {plot_color_hex!r}.")
    return f"#{normalized}{alpha:02x}"


def _make_h5_signal_plot_pens(plot_color_hex: str) -> tuple[QtGui.QPen, QtGui.QPen]:
    """Build solid detected and lower-alpha no-detection pens (both solid lines)."""
    detected_pen = pg.mkPen(plot_color_hex, width=2.5)
    candidate_pen = pg.mkPen(
        _plot_color_with_alpha(plot_color_hex, SIGNAL_PLOT_NO_DETECTION_ALPHA),
        width=2.5,
    )
    return detected_pen, candidate_pen


def _make_leg2_signal_plot_pens(plot_color_hex: str) -> tuple[QtGui.QPen, QtGui.QPen]:
    """Build primary (ReliableFlag) and faded segment pens for Leg2 ultrasonic curves."""
    primary_pen = pg.mkPen(
        _plot_color_with_alpha(plot_color_hex, SIGNAL_PLOT_PRIMARY_SEGMENT_ALPHA),
        width=2.5,
    )
    faded_pen = pg.mkPen(
        _plot_color_with_alpha(plot_color_hex, SIGNAL_PLOT_NO_DETECTION_ALPHA),
        width=2.5,
    )
    return primary_pen, faded_pen


TIMELINE_LABEL_GUTTER_PX = 72
TIMELINE_TRACK_OFFSET_LABEL_MARGIN_PX = 6.0
TIMELINE_OFFSET_LABEL_COLOR_HEX = "#94a3b8"


def format_track_offset_label(track_start_s: float) -> str:
    """Format a track's aligned start time relative to the H5 reference (shared timeline)."""
    # Negating a zero offset yields -0.0, which compares >= 0 but still formats with a minus sign.
    if math.isclose(track_start_s, 0.0, abs_tol=1e-9):
        return "+0.000 s"
    if track_start_s > 0.0:
        return f"+{track_start_s:.3f} s"
    return f"{track_start_s:.3f} s"


def track_offset_label_should_show(
    plot_rect: QtCore.QRectF,
    track_rect: QtCore.QRectF,
    *,
    label_width_px: float,
    margin_px: float = TIMELINE_TRACK_OFFSET_LABEL_MARGIN_PX,
) -> bool:
    if track_rect.width() <= 0.0:
        return False
    if track_rect.right() < plot_rect.left():
        return False
    if track_rect.left() > plot_rect.right():
        return False
    label_right_px = track_rect.left() - margin_px
    label_left_px = label_right_px - label_width_px
    return label_left_px >= plot_rect.left()


def track_offset_label_rect(
    plot_rect: QtCore.QRectF,
    track_rect: QtCore.QRectF,
    label_width_px: float,
    *,
    margin_px: float = TIMELINE_TRACK_OFFSET_LABEL_MARGIN_PX,
) -> QtCore.QRectF | None:
    if not track_offset_label_should_show(
        plot_rect,
        track_rect,
        label_width_px=label_width_px,
        margin_px=margin_px,
    ):
        return None
    label_right_px = track_rect.left() - margin_px
    label_left_px = label_right_px - label_width_px
    return QtCore.QRectF(
        label_left_px,
        track_rect.top(),
        label_width_px,
        track_rect.height(),
    )


@dataclass(frozen=True)
class TimeAxisGeometry:
    left_px: float
    right_px: float


class TimelineRangeModel(QtCore.QObject):
    """Single source of truth for the shared visible timeline x-range."""

    range_changed = QtCore.Signal(float, float)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._range_start_s = 0.0
        self._range_end_s = 1.0
        self._camera_duration_s = 0.0
        self._heatmap_duration_s = 0.0
        self._camera_offset_s = 0.0
        self._leg2_duration_s = 0.0
        self._leg2_offset_s = 0.0
        self._fit_padding_fraction = 0.12
        self._freeze_depth = 0
        self._frozen_range_start_s: float | None = None
        self._frozen_range_end_s: float | None = None

    def visible_range_s(self) -> tuple[float, float]:
        if self._freeze_depth > 0:
            if self._frozen_range_start_s is not None and self._frozen_range_end_s is not None:
                return self._frozen_range_start_s, self._frozen_range_end_s
        return self._range_start_s, self._range_end_s

    @property
    def camera_duration_s(self) -> float:
        return self._camera_duration_s

    @property
    def heatmap_duration_s(self) -> float:
        return self._heatmap_duration_s

    @property
    def camera_offset_s(self) -> float:
        return self._camera_offset_s

    @property
    def leg2_duration_s(self) -> float:
        return self._leg2_duration_s

    @property
    def leg2_offset_s(self) -> float:
        return self._leg2_offset_s

    def set_track_state(
        self,
        *,
        camera_duration_s: float,
        heatmap_duration_s: float,
        camera_offset_s: float,
        leg2_duration_s: float = 0.0,
        leg2_offset_s: float = 0.0,
    ) -> None:
        self._camera_duration_s = max(0.0, camera_duration_s)
        self._heatmap_duration_s = max(0.0, heatmap_duration_s)
        self._camera_offset_s = camera_offset_s
        self._leg2_duration_s = max(0.0, leg2_duration_s)
        self._leg2_offset_s = leg2_offset_s

    def begin_visible_range_freeze(self) -> None:
        if self._freeze_depth == 0:
            range_start_s, range_end_s = self.visible_range_s()
            self._frozen_range_start_s = range_start_s
            self._frozen_range_end_s = range_end_s
        self._freeze_depth += 1

    def end_visible_range_freeze(self, *, recompute: bool) -> None:
        self._freeze_depth = max(0, self._freeze_depth - 1)
        if self._freeze_depth > 0:
            return
        self._frozen_range_start_s = None
        self._frozen_range_end_s = None
        if recompute:
            self.recompute_visible_range()

    def recompute_visible_range(self) -> None:
        if self._freeze_depth > 0:
            return
        self.set_visible_range(
            *timeline_view_bounds_s(
                heatmap_duration_s=self._heatmap_duration_s,
                camera_duration_s=self._camera_duration_s,
                camera_offset_s=self._camera_offset_s,
                leg2_duration_s=self._leg2_duration_s,
                leg2_offset_s=self._leg2_offset_s,
                fit_padding_fraction=self._fit_padding_fraction,
            )
        )

    def set_visible_range(self, range_start_s: float, range_end_s: float) -> None:
        if math.isclose(range_start_s, self._range_start_s) and math.isclose(
            range_end_s, self._range_end_s
        ):
            return
        self._range_start_s = range_start_s
        self._range_end_s = range_end_s
        self.range_changed.emit(range_start_s, range_end_s)


class SignalPlotWidget(pg.PlotWidget):
    """Signals plot with timeline-following x auto mode and persisted range modes."""

    view_settings_changed = QtCore.Signal()
    axis_geometry_sync_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self.setBackground(SIGNAL_PLOT_BACKGROUND_HEX)
        self.setLabel("left", "Distance (m)")
        self.setLabel("bottom", "Time (s)")
        self.showGrid(x=True, y=True, alpha=0.2)
        self._view_settings = SignalPlotViewSettings()
        self._timeline_range_model: TimelineRangeModel | None = None
        self._peak_series: PeakDistanceSignalSeries | None = None
        self._leg2_series: Leg2UltrasonicSignalSeries | None = None
        self._peak_visible = False
        self._leg2_visible = False
        self._applying_view = False
        self._stance_patch_items: list[QtWidgets.QGraphicsItem] = []
        h5_plot_color = derive_signal_plot_color(H5_TIMELINE_TRACK_COLOR_HEX)
        leg2_plot_color = derive_signal_plot_color(LEG2_TIMELINE_TRACK_COLOR_HEX)
        detected_pen, candidate_pen = _make_h5_signal_plot_pens(h5_plot_color)
        primary_pen, faded_pen = _make_leg2_signal_plot_pens(leg2_plot_color)
        self._leg2_plot_color = leg2_plot_color
        self._leg2_plot_alpha = SIGNAL_PLOT_PRIMARY_SEGMENT_ALPHA
        self._candidate_curve = self.plot(
            pen=candidate_pen,
            connect="finite",
            name="H5 peak (no detection)",
        )
        self._detected_curve = self.plot(
            pen=detected_pen,
            connect="finite",
            name="H5 peak (detected)",
        )
        self._leg2_faded_curve = self.plot(
            pen=faded_pen,
            connect="finite",
            name="Leg2 ultrasonic (not valid)",
        )
        self._leg2_primary_curve = self.plot(
            pen=primary_pen,
            connect="finite",
            name="Leg2 ultrasonic (valid)",
        )
        self.addLegend(offset=(8, 8))
        self._current_time_line = pg.InfiniteLine(
            pos=0.0,
            angle=90,
            movable=False,
            pen=pg.mkPen(
                _plot_color_with_alpha(TIMELINE_PLAYHEAD_COLOR_HEX, SIGNAL_PLAYHEAD_ALPHA),
                width=1.0,
            ),
        )
        self._current_time_line.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
        self._current_time_line.setHoverPen(None)
        self.addItem(self._current_time_line)
        view_box = self.getPlotItem().getViewBox()
        view_box.disableAutoRange()
        view_box.sigRangeChanged.connect(self._view_box_range_changed)
        self._configure_range_mode_menu(view_box)
        left_axis = self.getAxis("left")
        if left_axis is not None:
            left_axis.setWidth(56)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self.axis_geometry_sync_requested.emit()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self.axis_geometry_sync_requested.emit()

    def viewbox_horizontal_extent_local(self) -> tuple[float, float]:
        """Return the ViewBox data area as left/right x in this widget's coordinates."""
        view_box = self.getPlotItem().getViewBox()
        view_width = float(view_box.boundingRect().width())
        left_px = float(self.mapFromScene(view_box.mapToScene(0.0, 0.0)).x())
        right_px = float(self.mapFromScene(view_box.mapToScene(view_width, 0.0)).x())
        return min(left_px, right_px), max(left_px, right_px)

    def view_settings(self) -> SignalPlotViewSettings:
        return self._view_settings

    def set_view_settings(self, settings: SignalPlotViewSettings) -> None:
        self._view_settings = SignalPlotViewSettings(
            x_range_mode=settings.x_range_mode,
            y_range_mode=settings.y_range_mode,
            manual_x_range=settings.manual_x_range,
            manual_y_range=settings.manual_y_range,
        )
        self._sync_range_mode_menu_checks()
        self._apply_view_settings()

    def attach_timeline_range_model(self, range_model: TimelineRangeModel) -> None:
        self._timeline_range_model = range_model
        range_model.range_changed.connect(self._on_timeline_visible_range_changed)
        self.sync_x_if_following()

    def set_current_time_s(self, time_s: float) -> None:
        self._current_time_line.setPos(float(time_s))

    def sync_x_if_following(self) -> None:
        """Apply the shared visible timeline range when x-axis follows the timeline."""
        if self._view_settings.x_range_mode != "auto" or self._timeline_range_model is None:
            return
        range_start_s, range_end_s = self._timeline_range_model.visible_range_s()
        self._applying_view = True
        try:
            self.setXRange(range_start_s, range_end_s, padding=0.0)
            if self._view_settings.y_range_mode == "auto":
                self._apply_y_auto_range()
        finally:
            self._applying_view = False

    def _on_timeline_visible_range_changed(self, range_start_s: float, range_end_s: float) -> None:
        del range_start_s, range_end_s
        self.sync_x_if_following()

    def set_plotted_signals(
        self,
        *,
        peak_series: PeakDistanceSignalSeries | None,
        peak_visible: bool,
        leg2_series: Leg2UltrasonicSignalSeries | None,
        leg2_visible: bool,
        leg2_legend_name: str,
    ) -> None:
        self._peak_series = peak_series
        self._leg2_series = leg2_series
        self._peak_visible = peak_visible and peak_series is not None
        self._leg2_visible = leg2_visible and leg2_series is not None

        if self._peak_visible and peak_series is not None:
            self._detected_curve.setData(
                peak_series.detected_time_s,
                peak_series.detected_distance_m,
            )
            self._candidate_curve.setData(
                peak_series.candidate_time_s,
                peak_series.candidate_distance_m,
            )
        else:
            self._detected_curve.setData([], [])
            self._candidate_curve.setData([], [])

        if self._leg2_visible and leg2_series is not None:
            self._leg2_primary_curve.setData(
                leg2_series.primary_time_s,
                leg2_series.primary_distance_m,
            )
            self._leg2_faded_curve.setData(
                leg2_series.faded_time_s,
                leg2_series.faded_distance_m,
            )
            self._leg2_primary_curve.opts["name"] = f"{leg2_legend_name} (valid)"
            self._leg2_faded_curve.opts["name"] = f"{leg2_legend_name} (not valid)"
        else:
            self._leg2_primary_curve.setData([], [])
            self._leg2_faded_curve.setData([], [])

        self._render_stance_patches()
        self._sync_signal_plot_legend()
        self._apply_view_settings()
        self._update_stance_patches_on_y_range()
        self.axis_geometry_sync_requested.emit()

    def _sync_signal_plot_legend(self) -> None:
        """Rebuild the compact legend so names and visibility match plotted curves."""
        legend = self.getPlotItem().legend
        if legend is None:
            return
        legend.clear()
        if self._peak_visible:
            legend.addItem(self._detected_curve, "H5 peak (detected)")
            legend.addItem(self._candidate_curve, "H5 peak (no detection)")
        if self._leg2_visible:
            legend.addItem(
                self._leg2_primary_curve,
                str(self._leg2_primary_curve.opts.get("name", "Leg2 ultrasonic (valid)")),
            )
            legend.addItem(
                self._leg2_faded_curve,
                str(self._leg2_faded_curve.opts.get("name", "Leg2 ultrasonic (not valid)")),
            )
            stance_legend_item = QtWidgets.QGraphicsRectItem(QtCore.QRectF(0, 0, 15, 15))
            patch_color = _plot_color_with_alpha(self._leg2_plot_color, self._leg2_plot_alpha)
            stance_legend_item.setPen(pg.mkPen(None))
            stance_legend_item.setBrush(pg.mkBrush(patch_color))
            legend.addItem(stance_legend_item, "Stance phase")
        legend.setVisible(self._peak_visible or self._leg2_visible)

    def _clear_stance_patches(self) -> None:
        """Remove all stance phase patch items from the plot."""
        plot_item = self.getPlotItem()
        view_box = plot_item.getViewBox()
        for item in self._stance_patch_items:
            view_box.removeItem(item)
        self._stance_patch_items.clear()

    def _render_stance_patches(self) -> None:
        """Render stance phase patches on the plot from leg2_series.stance_intervals."""
        self._clear_stance_patches()
        if not self._leg2_visible or self._leg2_series is None:
            return

        stance_intervals = self._leg2_series.stance_intervals
        if stance_intervals.start_times_s.size == 0:
            return

        plot_item = self.getPlotItem()
        view_box = plot_item.getViewBox()
        view_range = view_box.viewRange()
        y_min = view_range[1][0]

        patch_color = _plot_color_with_alpha(self._leg2_plot_color, self._leg2_plot_alpha)
        qbrush = pg.mkBrush(patch_color)

        for start_s, end_s in zip(
            stance_intervals.start_times_s, stance_intervals.end_times_s
        ):
            rect = QtCore.QRectF(
                float(start_s),
                float(y_min),
                float(end_s - start_s),
                float(0 - y_min),
            )
            patch = QtWidgets.QGraphicsRectItem(rect)
            patch.setPen(pg.mkPen(None))
            patch.setBrush(qbrush)
            patch.setZValue(-1)
            view_box.addItem(patch)
            self._stance_patch_items.append(patch)

    def _update_stance_patches_on_y_range(self) -> None:
        """Update stance patch y-values when y-limits change."""
        if not self._stance_patch_items or self._leg2_series is None:
            return

        plot_item = self.getPlotItem()
        view_box = plot_item.getViewBox()
        view_range = view_box.viewRange()
        y_min = view_range[1][0]

        stance_intervals = self._leg2_series.stance_intervals
        for patch_item, start_s, end_s in zip(
            self._stance_patch_items,
            stance_intervals.start_times_s,
            stance_intervals.end_times_s,
        ):
            rect = QtCore.QRectF(
                float(start_s),
                float(y_min),
                float(end_s - start_s),
                float(0 - y_min),
            )
            patch_item.setRect(rect)

    def _configure_range_mode_menu(self, view_box: pg.ViewBox) -> None:
        menu = view_box.menu
        if menu is None:
            return

        x_axis_menu = menu.ctrl[0]
        y_axis_menu = menu.ctrl[1]
        x_axis_menu.autoRadio.setText("Timeline")
        x_axis_menu.autoRadio.setToolTip("Match the Timeline x-range.")
        for axis_menu in (x_axis_menu, y_axis_menu):
            axis_menu.autoPercentSpin.setVisible(False)
            axis_menu.autoPanCheck.setVisible(False)
            axis_menu.visibleOnlyCheck.setVisible(False)

        try:
            x_axis_menu.autoRadio.clicked.disconnect(menu.xAutoClicked)
        except TypeError:
            pass
        try:
            x_axis_menu.manualRadio.clicked.disconnect(menu.xManualClicked)
        except TypeError:
            pass
        try:
            y_axis_menu.autoRadio.clicked.disconnect(menu.yAutoClicked)
        except TypeError:
            pass
        try:
            y_axis_menu.manualRadio.clicked.disconnect(menu.yManualClicked)
        except TypeError:
            pass

        x_axis_menu.autoRadio.clicked.connect(lambda: self._set_x_range_mode("auto"))
        x_axis_menu.manualRadio.clicked.connect(lambda: self._set_x_range_mode("manual"))
        y_axis_menu.autoRadio.clicked.connect(lambda: self._set_y_range_mode("auto"))
        y_axis_menu.manualRadio.clicked.connect(lambda: self._set_y_range_mode("manual"))

        original_update_state = menu.updateState

        def update_state() -> None:
            original_update_state()
            self._sync_range_mode_menu_checks()

        menu.updateState = update_state
        self._sync_range_mode_menu_checks()

    def _sync_range_mode_menu_checks(self) -> None:
        menu = self.getPlotItem().getViewBox().menu
        if menu is None:
            return
        x_axis_menu = menu.ctrl[0]
        y_axis_menu = menu.ctrl[1]
        x_axis_menu.autoRadio.setChecked(self._view_settings.x_range_mode == "auto")
        x_axis_menu.manualRadio.setChecked(self._view_settings.x_range_mode == "manual")
        y_axis_menu.autoRadio.setChecked(self._view_settings.y_range_mode == "auto")
        y_axis_menu.manualRadio.setChecked(self._view_settings.y_range_mode == "manual")
        self._sync_x_timeline_mode_menu_constraints()

    def _sync_x_timeline_mode_menu_constraints(self) -> None:
        plot_item = self.getPlotItem()
        view_box = plot_item.getViewBox()
        menu = view_box.menu
        if menu is None:
            return

        x_timeline = self._view_settings.x_range_mode == "auto"
        x_axis_menu = menu.ctrl[0]
        if x_timeline:
            x_axis_menu.invertCheck.setChecked(False)
            view_box.invertX(False)
            for transform_check in self._x_timeline_blocked_transform_checks():
                transform_check.setChecked(False)
            plot_item.setLogMode(x=False)

        x_axis_menu.invertCheck.setEnabled(not x_timeline)
        for transform_check in self._x_timeline_blocked_transform_checks():
            transform_check.setEnabled(not x_timeline)
        menu.viewAll.setEnabled(not x_timeline)

    def _x_timeline_blocked_transform_checks(self) -> tuple[QtWidgets.QCheckBox, ...]:
        plot_ctrl = self.getPlotItem().ctrl
        return (
            plot_ctrl.logXCheck,
            plot_ctrl.derivativeCheck,
            plot_ctrl.phasemapCheck,
            plot_ctrl.fftCheck,
        )

    def _set_x_range_mode(self, mode: Literal["auto", "manual"]) -> None:
        if self._view_settings.x_range_mode == mode:
            return
        if mode == "manual":
            x_range, _ = self.getViewBox().viewRange()
            self._view_settings.manual_x_range = (float(x_range[0]), float(x_range[1]))
        self._view_settings.x_range_mode = mode
        self._sync_range_mode_menu_checks()
        self._apply_view_settings()
        if mode == "auto":
            self.sync_x_if_following()
        self.view_settings_changed.emit()

    def _set_y_range_mode(self, mode: Literal["auto", "manual"]) -> None:
        if self._view_settings.y_range_mode == mode:
            return
        if mode == "manual":
            _, y_range = self.getViewBox().viewRange()
            self._view_settings.manual_y_range = (float(y_range[0]), float(y_range[1]))
        self._view_settings.y_range_mode = mode
        self._sync_range_mode_menu_checks()
        self._apply_view_settings()
        self.view_settings_changed.emit()

    def _apply_view_settings(self) -> None:
        view_box = self.getPlotItem().getViewBox()
        x_manual = self._view_settings.x_range_mode == "manual"
        y_manual = self._view_settings.y_range_mode == "manual"
        view_box.setMouseEnabled(x=x_manual, y=y_manual)

        self._applying_view = True
        try:
            if self._view_settings.x_range_mode == "manual" and self._view_settings.manual_x_range is not None:
                x_min_s, x_max_s = self._view_settings.manual_x_range
                self.setXRange(x_min_s, x_max_s, padding=0.0)
            elif self._view_settings.x_range_mode == "auto":
                self.sync_x_if_following()

            if self._view_settings.y_range_mode == "auto":
                self._apply_y_auto_range()
            elif self._view_settings.manual_y_range is not None:
                y_min_m, y_max_m = self._view_settings.manual_y_range
                self.setYRange(y_min_m, y_max_m, padding=0.0)
        finally:
            self._applying_view = False

    def _apply_y_auto_range(self) -> None:
        if not self._peak_visible and not self._leg2_visible:
            return
        x_range, _ = self.getViewBox().viewRange()
        if self._peak_visible and self._peak_series is not None:
            y_range = visible_signal_y_range(
                self._peak_series,
                x_min_s=float(x_range[0]),
                x_max_s=float(x_range[1]),
                leg2_series=self._leg2_series if self._leg2_visible else None,
            )
        elif self._leg2_visible and self._leg2_series is not None:
            empty_peak = PeakDistanceSignalSeries(
                detected_time_s=np.asarray([], dtype=np.float64),
                detected_distance_m=np.asarray([], dtype=np.float64),
                candidate_time_s=np.asarray([], dtype=np.float64),
                candidate_distance_m=np.asarray([], dtype=np.float64),
            )
            y_range = visible_signal_y_range(
                empty_peak,
                x_min_s=float(x_range[0]),
                x_max_s=float(x_range[1]),
                leg2_series=self._leg2_series,
            )
        else:
            return
        if y_range is None:
            return
        self.setYRange(y_range[0], y_range[1], padding=0.0)

    def _view_box_range_changed(self) -> None:
        if self._applying_view:
            return
        x_range, y_range = self.getViewBox().viewRange()
        changed = False
        if self._view_settings.x_range_mode == "manual":
            manual_x_range = (float(x_range[0]), float(x_range[1]))
            if manual_x_range != self._view_settings.manual_x_range:
                self._view_settings.manual_x_range = manual_x_range
                changed = True
        if self._view_settings.y_range_mode == "manual":
            manual_y_range = (float(y_range[0]), float(y_range[1]))
            if manual_y_range != self._view_settings.manual_y_range:
                self._view_settings.manual_y_range = manual_y_range
                changed = True
        elif self._view_settings.y_range_mode == "auto":
            self._applying_view = True
            try:
                self._apply_y_auto_range()
            finally:
                self._applying_view = False
        self._update_stance_patches_on_y_range()
        if changed:
            self.view_settings_changed.emit()


class AlignmentTimelineWidget(QtWidgets.QWidget):
    playhead_changed = QtCore.Signal(float)
    camera_offset_changed = QtCore.Signal(float)
    leg2_offset_changed = QtCore.Signal(float)
    h5_alignment_drag_changed = QtCore.Signal(float, float, float, float, float)
    h5_alignment_drag_finished = QtCore.Signal()

    def __init__(
        self,
        range_model: TimelineRangeModel,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._range_model = range_model
        self._range_model.range_changed.connect(lambda *_args: self.update())
        self.setMinimumHeight(124)
        self.setMouseTracking(True)
        self._current_time_s = 0.0
        self._dragging_camera = False
        self._dragging_leg2 = False
        self._dragging_h5 = False
        self._dragging_playhead = False
        self._camera_drag_anchor_s = 0.0
        self._leg2_drag_anchor_s = 0.0
        self._h5_drag_anchor_s = 0.0
        self._h5_drag_snapshot: TimelineH5DragSnapshot | None = None
        self._hover_on_camera_bar = False
        self._hover_on_leg2_bar = False
        self._hover_on_h5_bar = False
        self._hover_on_playhead = False
        self._playhead_hit_half_width_px = 8.0
        self._time_axis_left_px: float | None = None
        self._time_axis_right_px: float | None = None

    def set_time_axis_rect(self, left_px: float, right_px: float) -> None:
        if self._time_axis_left_px is not None:
            if math.isclose(left_px, self._time_axis_left_px) and math.isclose(
                right_px, self._time_axis_right_px
            ):
                return
        self._time_axis_left_px = left_px
        self._time_axis_right_px = right_px
        self.update()

    def set_timeline_state(self, *, current_time_s: float) -> None:
        self._current_time_s = current_time_s
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        try:
            painter.fillRect(self.rect(), QtGui.QColor("#0f1720"))
            plot_rect = self._plot_rect()
            if plot_rect.width() <= 1:
                return

            label_pen = QtGui.QPen(QtGui.QColor("#94a3b8"))
            axis_pen = QtGui.QPen(QtGui.QColor("#334155"), 1)
            tick_pen = QtGui.QPen(QtGui.QColor("#475569"), 1)
            camera_brush = QtGui.QBrush(QtGui.QColor("#f97316"))
            heatmap_brush = QtGui.QBrush(QtGui.QColor(H5_TIMELINE_TRACK_COLOR_HEX))
            leg2_brush = QtGui.QBrush(QtGui.QColor(LEG2_TIMELINE_TRACK_COLOR_HEX))
            playhead_pen = QtGui.QPen(QtGui.QColor(TIMELINE_PLAYHEAD_COLOR_HEX), 2.5)

            painter.setPen(label_pen)
            axis_y = plot_rect.top() + 16
            painter.drawText(QtCore.QRectF(8, axis_y - 10, 60, 20), "Time")
            painter.drawText(QtCore.QRectF(8, plot_rect.top() + 30, 60, 20), "Camera")
            painter.drawText(QtCore.QRectF(8, plot_rect.top() + 58, 60, 20), "H5")
            if self._range_model.leg2_duration_s > 0.0:
                painter.drawText(QtCore.QRectF(8, plot_rect.top() + 86, 60, 20), "Leg2")

            painter.setPen(axis_pen)
            painter.drawLine(
                QtCore.QPointF(plot_rect.left(), axis_y),
                QtCore.QPointF(plot_rect.right(), axis_y),
            )

            tick_count = 6
            painter.setPen(tick_pen)
            for idx in range(tick_count + 1):
                frac = idx / tick_count
                x = plot_rect.left() + frac * plot_rect.width()
                painter.drawLine(
                    QtCore.QPointF(x, axis_y - 4),
                    QtCore.QPointF(x, plot_rect.bottom()),
                )
                range_start_s, range_end_s = self._range_model.visible_range_s()
                tick_time = range_start_s + frac * (range_end_s - range_start_s)
                painter.drawText(
                    QtCore.QRectF(x - 24, plot_rect.top(), 48, 14),
                    QtCore.Qt.AlignmentFlag.AlignCenter,
                    f"{tick_time:.1f}",
                )

            camera_rect = self._track_rect(
                self._camera_track_start_s(),
                self._range_model.camera_duration_s,
                row=0,
            )
            heatmap_rect = self._track_rect(0.0, self._range_model.heatmap_duration_s, row=1)
            leg2_rect = self._track_rect(
                self._leg2_track_start_s(),
                self._range_model.leg2_duration_s,
                row=2,
            )

            if camera_rect.width() > 0:
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(camera_brush)
                painter.drawRoundedRect(camera_rect, 4, 4)
            if heatmap_rect.width() > 0:
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(heatmap_brush)
                painter.drawRoundedRect(heatmap_rect, 4, 4)
            if leg2_rect.width() > 0:
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(leg2_brush)
                painter.drawRoundedRect(leg2_rect, 4, 4)

            offset_label_pen = QtGui.QPen(QtGui.QColor(TIMELINE_OFFSET_LABEL_COLOR_HEX))
            painter.setPen(offset_label_pen)
            self._draw_track_offset_label(
                painter,
                plot_rect,
                camera_rect,
                self._camera_track_start_s(),
            )
            if self._range_model.leg2_duration_s > 0.0:
                self._draw_track_offset_label(
                    painter,
                    plot_rect,
                    leg2_rect,
                    self._leg2_track_start_s(),
                )

            playhead_x = self._time_to_x(self._current_time_s)
            painter.setPen(playhead_pen)
            painter.drawLine(
                QtCore.QPointF(playhead_x, axis_y - 6),
                QtCore.QPointF(playhead_x, plot_rect.bottom()),
            )
        finally:
            painter.end()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        press_time_s = self._time_at_x(event.position().x(), clamp=True)
        if self._playhead_hit_test(event.position()):
            self._dragging_playhead = True
            self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
            self.playhead_changed.emit(press_time_s)
            return

        if self._camera_track_hit_test(event.position()):
            self._dragging_camera = True
            self._range_model.begin_visible_range_freeze()
            self._camera_drag_anchor_s = press_time_s - self._camera_track_start_s()
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
            return

        if self._leg2_track_hit_test(event.position()):
            self._dragging_leg2 = True
            self._range_model.begin_visible_range_freeze()
            self._leg2_drag_anchor_s = press_time_s - self._leg2_track_start_s()
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
            return

        if self._h5_track_hit_test(event.position()):
            if not self._h5_alignment_drag_enabled():
                return
            self._dragging_h5 = True
            self._h5_drag_anchor_s = press_time_s
            range_start_s, range_end_s = self._range_model.visible_range_s()
            self._h5_drag_snapshot = TimelineH5DragSnapshot(
                range_start_s=range_start_s,
                range_end_s=range_end_s,
                current_time_s=self._current_time_s,
                camera_offset_s=self._range_model.camera_offset_s,
                leg2_offset_s=self._range_model.leg2_offset_s,
            )
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
            return

        self._dragging_playhead = True
        self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
        self.playhead_changed.emit(press_time_s)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._dragging_camera:
            position_time_s = self._time_at_x(event.position().x(), clamp=False)
            camera_track_start_s = position_time_s - self._camera_drag_anchor_s
            self.camera_offset_changed.emit(-camera_track_start_s)
            return
        if self._dragging_leg2:
            position_time_s = self._time_at_x(event.position().x(), clamp=False)
            leg2_track_start_s = position_time_s - self._leg2_drag_anchor_s
            self.leg2_offset_changed.emit(-leg2_track_start_s)
            return
        if self._dragging_h5:
            if self._h5_drag_snapshot is None:
                return
            position_time_s = self._time_at_x(
                event.position().x(),
                clamp=False,
                range_start_s=self._h5_drag_snapshot.range_start_s,
                range_end_s=self._h5_drag_snapshot.range_end_s,
            )
            h5_desired_start_s = position_time_s - self._h5_drag_anchor_s
            dragged = apply_timeline_h5_alignment_drag(
                self._h5_drag_snapshot,
                h5_desired_start_s=h5_desired_start_s,
            )
            self.h5_alignment_drag_changed.emit(
                dragged.range_start_s,
                dragged.range_end_s,
                dragged.current_time_s,
                dragged.camera_offset_s,
                dragged.leg2_offset_s,
            )
            return
        if self._dragging_playhead:
            position_time_s = self._time_at_x(event.position().x(), clamp=True)
            self.playhead_changed.emit(position_time_s)
            return

        hover_on_playhead = self._playhead_hit_test(event.position())
        hover_on_camera_bar = self._camera_track_hit_test(event.position())
        hover_on_leg2_bar = self._leg2_track_hit_test(event.position())
        hover_on_h5_bar = (
            self._h5_track_hit_test(event.position()) and self._h5_alignment_drag_enabled()
        )
        if hover_on_playhead != self._hover_on_playhead:
            self._hover_on_playhead = hover_on_playhead
            self._update_hover_cursor()
        if hover_on_camera_bar != self._hover_on_camera_bar:
            self._hover_on_camera_bar = hover_on_camera_bar
            self._update_hover_cursor()
        if hover_on_leg2_bar != self._hover_on_leg2_bar:
            self._hover_on_leg2_bar = hover_on_leg2_bar
            self._update_hover_cursor()
        if hover_on_h5_bar != self._hover_on_h5_bar:
            self._hover_on_h5_bar = hover_on_h5_bar
            self._update_hover_cursor()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        del event
        was_dragging_offset_track = self._dragging_camera or self._dragging_leg2
        was_dragging_h5 = self._dragging_h5
        self._dragging_camera = False
        self._dragging_leg2 = False
        self._dragging_h5 = False
        self._h5_drag_snapshot = None
        self._dragging_playhead = False
        if was_dragging_offset_track:
            self._range_model.end_visible_range_freeze(recompute=True)
        if was_dragging_h5:
            self.h5_alignment_drag_finished.emit()
        self.update()
        self._update_hover_cursor()

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        if (
            not self._dragging_camera
            and not self._dragging_leg2
            and not self._dragging_h5
            and not self._dragging_playhead
        ):
            self.unsetCursor()
            self._hover_on_camera_bar = False
            self._hover_on_leg2_bar = False
            self._hover_on_h5_bar = False
        super().leaveEvent(event)

    def _update_hover_cursor(self) -> None:
        if self._hover_on_playhead:
            self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
        elif self._hover_on_camera_bar or self._hover_on_leg2_bar or self._hover_on_h5_bar:
            self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        else:
            self.unsetCursor()

    def visible_time_bounds_s(self) -> tuple[float, float]:
        return self._range_model.visible_range_s()

    def _h5_alignment_drag_enabled(self) -> bool:
        return timeline_h5_drag_affects_alignment(
            camera_duration_s=self._range_model.camera_duration_s,
            leg2_duration_s=self._range_model.leg2_duration_s,
        )

    def _playhead_hit_test(self, widget_pos: QtCore.QPointF) -> bool:
        playhead_x = self._time_to_x(self._current_time_s)
        return abs(widget_pos.x() - playhead_x) <= self._playhead_hit_half_width_px

    def _camera_track_hit_test(self, widget_pos: QtCore.QPointF) -> bool:
        if self._range_model.camera_duration_s <= 0.0:
            return False
        return self._track_rect(
            self._camera_track_start_s(),
            self._range_model.camera_duration_s,
            row=0,
        ).contains(widget_pos)

    def _h5_track_hit_test(self, widget_pos: QtCore.QPointF) -> bool:
        if self._range_model.heatmap_duration_s <= 0.0:
            return False
        return self._track_rect(0.0, self._range_model.heatmap_duration_s, row=1).contains(
            widget_pos
        )

    def _leg2_track_hit_test(self, widget_pos: QtCore.QPointF) -> bool:
        if self._range_model.leg2_duration_s <= 0.0:
            return False
        return self._track_rect(
            self._leg2_track_start_s(),
            self._range_model.leg2_duration_s,
            row=2,
        ).contains(widget_pos)

    def _camera_track_start_s(self) -> float:
        return -self._range_model.camera_offset_s

    def _leg2_track_start_s(self) -> float:
        return -self._range_model.leg2_offset_s

    def _draw_track_offset_label(
        self,
        painter: QtGui.QPainter,
        plot_rect: QtCore.QRectF,
        track_rect: QtCore.QRectF,
        track_start_s: float,
    ) -> None:
        label_text = format_track_offset_label(track_start_s)
        label_width_px = float(painter.fontMetrics().horizontalAdvance(label_text))
        label_rect = track_offset_label_rect(
            plot_rect,
            track_rect,
            label_width_px,
        )
        if label_rect is None:
            return
        painter.drawText(
            label_rect,
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter,
            label_text,
        )

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        parent_window = self.window()
        if isinstance(parent_window, HeatmapAlignmentWindow):
            parent_window.schedule_timeline_axis_geometry_sync()

    def _plot_rect(self) -> QtCore.QRectF:
        rect = self.contentsRect()
        top_px = rect.top() + 6
        height_px = max(1, rect.height() - 12)
        if self._time_axis_left_px is not None and self._time_axis_right_px is not None:
            left_px = self._time_axis_left_px
            width_px = max(1.0, self._time_axis_right_px - self._time_axis_left_px)
        else:
            left_px = rect.left() + TIMELINE_LABEL_GUTTER_PX
            width_px = max(1.0, rect.width() - TIMELINE_LABEL_GUTTER_PX - 12)
        return QtCore.QRectF(left_px, top_px, width_px, height_px)

    def _track_rect(self, start_s: float, duration_s: float, *, row: int) -> QtCore.QRectF:
        plot_rect = self._plot_rect()
        row_top = plot_rect.top() + 30 + row * 28
        if duration_s <= 0.0:
            return QtCore.QRectF(plot_rect.left(), row_top, 0.0, 18.0)
        start_x = self._time_to_x(start_s)
        end_x = self._time_to_x(start_s + duration_s)
        left_x = min(start_x, end_x)
        width = max(0.0, abs(end_x - start_x))
        return QtCore.QRectF(left_x, row_top, width, 18.0)

    def _time_to_x(self, time_s: float) -> float:
        plot_rect = self._plot_rect()
        range_start_s, range_end_s = self._range_model.visible_range_s()
        span_s = max(1e-6, range_end_s - range_start_s)
        frac = (time_s - range_start_s) / span_s
        frac = min(1.0, max(0.0, frac))
        return plot_rect.left() + frac * plot_rect.width()

    def _time_at_x(
        self,
        x: float,
        *,
        clamp: bool,
        range_start_s: float | None = None,
        range_end_s: float | None = None,
    ) -> float:
        plot_rect = self._plot_rect()
        if range_start_s is None or range_end_s is None:
            range_start_s, range_end_s = self._range_model.visible_range_s()
        if plot_rect.width() <= 1:
            return range_start_s
        resolved_x = min(plot_rect.right(), max(plot_rect.left(), x)) if clamp else x
        frac = (resolved_x - plot_rect.left()) / plot_rect.width()
        return range_start_s + frac * (range_end_s - range_start_s)


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


class SourceResolutionViewportWorker(QtCore.QObject):
    render_finished = QtCore.Signal(object)

    @QtCore.Slot(object)
    def render_request(self, request: object) -> None:
        payload = dict(request) if isinstance(request, dict) else {}
        result: dict[str, object] = {"token": payload.get("token"), "frame": None, "error": None}
        try:
            camera_path = Path(str(payload["camera_path"]))
            source = CameraVideoSource(camera_path, max_preview_dimension=None)
            try:
                _, frame = source.frame_at_seconds(
                    float(payload["camera_time_s"]),
                    access_hint="random",
                )
            finally:
                source.close()
            viewport_frame = rectify_viewport(
                frame,
                np.asarray(payload["corners"], dtype=np.float32),
                tuple(int(value) for value in payload["output_size"]),
            )
            result["frame"] = viewport_frame
        except Exception as exc:
            result["error"] = str(exc)
        self.render_finished.emit(result)


class ResourceColorSwatchDelegate(QtWidgets.QStyledItemDelegate):
    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex,
    ) -> None:
        item_option = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(item_option, index)
        item_option.text = ""
        style = option.widget.style() if option.widget is not None else QtWidgets.QApplication.style()
        style.drawControl(
            QtWidgets.QStyle.ControlElement.CE_ItemViewItem,
            item_option,
            painter,
            option.widget,
        )

        color_hex = index.data(QtCore.Qt.ItemDataRole.UserRole)
        painter.save()
        try:
            rect = option.rect.adjusted(6, 8, -6, -8)
            if not color_hex:
                painter.setPen(QtGui.QPen(QtGui.QColor("#475569")))
                painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                painter.drawRect(rect)
                return
            color = QtGui.QColor(str(color_hex))
            if index.data(QtCore.Qt.ItemDataRole.UserRole + 1):
                color.setAlpha(96)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(rect, 3, 3)
        finally:
            painter.restore()


class _ResourceJobRunnable(QtCore.QRunnable):
    def __init__(
        self,
        manager: ResourceJobManager,
        kind: ResourceJobKind,
        generation: int,
        worker: object,
    ) -> None:
        super().__init__()
        self._manager = manager
        self._kind = kind
        self._generation = generation
        self._worker = worker
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            result = self._worker()
        except Exception as exc:
            if not self._manager._abandoned:
                self._manager._dispatch_job_failure(self._kind, self._generation, exc)
            return
        if self._manager._abandoned:
            self._manager._release_abandoned_worker_result(
                self._kind,
                self._generation,
                result,
            )
            return
        self._manager._dispatch_job_success(self._kind, self._generation, result)


class ResourceJobManager(QtCore.QObject):
    """Schedules camera and H5 resource jobs off the GUI thread."""

    job_state_changed = QtCore.Signal()
    job_succeeded = QtCore.Signal(str, int, object)
    job_failed = QtCore.Signal(str, int, str)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._board = ResourceJobBoard()
        self._thread_pool = QtCore.QThreadPool.globalInstance()
        self._proxy_active = False
        self._h5_active = False
        self._proxy_processes: dict[int, object] = {}
        self._pending_results: dict[tuple[ResourceJobKind, int], object] = {}
        self._cancelled_generations: set[tuple[ResourceJobKind, int]] = set()
        self._abandoned = False
        self.job_succeeded.connect(self._handle_job_success)
        self.job_failed.connect(self._handle_job_failure)

    def board(self) -> ResourceJobBoard:
        return self._board

    def snapshots(self) -> tuple[ResourceJobSnapshot, ...]:
        return (
            self._board.camera.snapshot("camera"),
            self._board.radar_h5.snapshot("radar_h5"),
        )

    def blocks_export(self) -> bool:
        return resource_job_blocks_export(self._board)

    def _generation_cancelled(self, kind: ResourceJobKind, generation: int) -> bool:
        return (kind, generation) in self._cancelled_generations

    def _cancel_generation(self, kind: ResourceJobKind, generation: int) -> None:
        if generation <= 0:
            return
        self._cancelled_generations.add((kind, generation))
        if kind != "camera":
            return
        process = self._proxy_processes.pop(generation, None)
        if process is None:
            return
        try:
            process.terminate()
        except OSError:
            pass

    def _release_job_result(self, kind: ResourceJobKind, generation: int, result: object) -> None:
        release_resource_job_result(kind, result)
        self._pending_results.pop((kind, generation), None)

    def _discard_all_pending_results(self) -> None:
        for (kind, generation), result in list(self._pending_results.items()):
            self._release_job_result(kind, generation, result)

    def abandon_all_jobs(self) -> None:
        self._abandoned = True
        for kind in ("camera", "radar_h5"):
            slot = self._board.slot(kind)
            if slot.phase not in ("idle", "failed"):
                self._cancel_generation(kind, slot.generation)
            clear_resource_job(self._board, kind)
        self._discard_all_pending_results()
        self.job_state_changed.emit()

    def _release_abandoned_worker_result(
        self,
        kind: ResourceJobKind,
        generation: int,
        result: object,
    ) -> None:
        self._release_job_result(kind, generation, result)

    def start_camera_job(
        self,
        camera_path: Path,
        *,
        replaces_active: bool,
        cache_root: Path | None = None,
    ) -> int:
        self._abandoned = False
        slot = self._board.camera
        if slot.phase not in ("idle", "failed"):
            self._cancel_generation("camera", slot.generation)
        generation = begin_resource_job(
            self._board,
            "camera",
            target_path=camera_path,
            replaces_active=replaces_active,
            initial_phase="pending",
            message=f"Loading {camera_path.name}...",
        )
        self._schedule_camera_job(generation, camera_path, cache_root=cache_root)
        self.job_state_changed.emit()
        return generation

    def start_h5_job(
        self,
        h5_path: Path,
        *,
        replaces_active: bool,
        session_idx: int | None,
        group_idx: int | None,
        entry_idx: int | None,
        subsweep_idx: int | None,
        color_min: float,
        color_max: float | None,
        fixed_levels: bool,
    ) -> int:
        self._abandoned = False
        slot = self._board.radar_h5
        if slot.phase not in ("idle", "failed"):
            self._cancel_generation("radar_h5", slot.generation)
        generation = begin_resource_job(
            self._board,
            "radar_h5",
            target_path=h5_path,
            replaces_active=replaces_active,
            initial_phase="loading",
            message=f"Loading {h5_path.name}...",
        )
        self._schedule_h5_job(
            generation,
            h5_path,
            session_idx=session_idx,
            group_idx=group_idx,
            entry_idx=entry_idx,
            subsweep_idx=subsweep_idx,
            color_min=color_min,
            color_max=color_max,
            fixed_levels=fixed_levels,
        )
        self.job_state_changed.emit()
        return generation

    def cancel_job(self, kind: ResourceJobKind) -> bool:
        if not request_cancel_resource_job(self._board, kind):
            return False
        slot = self._board.slot(kind)
        generation = slot.generation
        self._cancel_generation(kind, generation)
        pending = self._pending_results.pop((kind, generation), None)
        if pending is not None:
            self._release_job_result(kind, generation, pending)
        complete_resource_job(self._board, kind, generation, phase="idle")
        self.job_state_changed.emit()
        return True

    def _schedule_camera_job(
        self,
        generation: int,
        camera_path: Path,
        *,
        cache_root: Path | None,
    ) -> None:
        def _wait_for_proxy_slot() -> None:
            if self._proxy_active:
                mark_resource_job_phase(
                    self._board,
                    "camera",
                    generation,
                    "waiting",
                    message=f"Waiting to build preview proxy for {camera_path.name}...",
                )
                QtCore.QMetaObject.invokeMethod(
                    self,
                    "_emit_job_state_changed",
                    QtCore.Qt.ConnectionType.QueuedConnection,
                )
            while self._proxy_active:
                if self._generation_cancelled("camera", generation):
                    raise ResourceJobError("Camera load cancelled.")
                QtCore.QThread.msleep(25)

        def _worker() -> CameraResourceJobResult:
            _wait_for_proxy_slot()
            if self._generation_cancelled("camera", generation):
                raise ResourceJobError("Camera load cancelled.")
            self._proxy_active = True
            mark_resource_job_phase(
                self._board,
                "camera",
                generation,
                "building",
                message=f"Building preview proxy for {camera_path.name}...",
            )
            QtCore.QMetaObject.invokeMethod(
                self,
                "_emit_job_state_changed",
                QtCore.Qt.ConnectionType.QueuedConnection,
            )

            def _process_hook(process: object) -> None:
                self._proxy_processes[generation] = process

            try:
                return run_camera_resource_job(
                    camera_path,
                    cache_root=cache_root,
                    cancel_check=lambda: self._generation_cancelled("camera", generation),
                    process_hook=_process_hook,
                )
            finally:
                self._proxy_active = False
                self._proxy_processes.pop(generation, None)
                self._cancelled_generations.discard(("camera", generation))

        runnable = _ResourceJobRunnable(self, "camera", generation, _worker)
        self._thread_pool.start(runnable, priority=0)

    def _schedule_h5_job(
        self,
        generation: int,
        h5_path: Path,
        *,
        session_idx: int | None,
        group_idx: int | None,
        entry_idx: int | None,
        subsweep_idx: int | None,
        color_min: float,
        color_max: float | None,
        fixed_levels: bool,
    ) -> None:
        def _wait_for_h5_slot() -> None:
            if self._h5_active:
                mark_resource_job_phase(
                    self._board,
                    "radar_h5",
                    generation,
                    "waiting",
                    message=f"Waiting to load {h5_path.name}...",
                )
                QtCore.QMetaObject.invokeMethod(
                    self,
                    "_emit_job_state_changed",
                    QtCore.Qt.ConnectionType.QueuedConnection,
                )
            while self._h5_active:
                if self._generation_cancelled("radar_h5", generation):
                    raise ResourceJobError("H5 load cancelled.")
                QtCore.QThread.msleep(25)

        def _worker() -> LoadedH5ResourcePayload:
            _wait_for_h5_slot()
            if self._generation_cancelled("radar_h5", generation):
                raise ResourceJobError("H5 load cancelled.")
            self._h5_active = True
            try:
                return load_h5_resource_payload(
                    h5_path,
                    session_idx=session_idx,
                    group_idx=group_idx,
                    entry_idx=entry_idx,
                    subsweep_idx=subsweep_idx,
                    color_min=color_min,
                    color_max=color_max,
                    fixed_levels=fixed_levels,
                    cancel_check=lambda: self._generation_cancelled("radar_h5", generation),
                )
            finally:
                self._h5_active = False
                self._cancelled_generations.discard(("radar_h5", generation))

        runnable = _ResourceJobRunnable(self, "radar_h5", generation, _worker)
        self._thread_pool.start(runnable, priority=0)

    @QtCore.Slot()
    def _emit_job_state_changed(self) -> None:
        self.job_state_changed.emit()

    def _dispatch_job_success(
        self,
        kind: ResourceJobKind,
        generation: int,
        result: object,
    ) -> None:
        try:
            self.job_succeeded.emit(kind, generation, result)
        except RuntimeError as exc:
            if "Internal C++ object" not in str(exc):
                raise
            self._release_job_result(kind, generation, result)

    def _dispatch_job_failure(
        self,
        kind: ResourceJobKind,
        generation: int,
        error: Exception,
    ) -> None:
        try:
            self.job_failed.emit(kind, generation, str(error))
        except RuntimeError as exc:
            if "Internal C++ object" not in str(exc):
                raise
            return

    def _handle_job_success(
        self,
        kind: ResourceJobKind,
        generation: int,
        result: object,
    ) -> None:
        slot = self._board.slot(kind)
        if slot.cancel_requested or self._generation_cancelled(kind, generation):
            self._release_job_result(kind, generation, result)
            return
        if not should_apply_job_result(slot, generation):
            self._release_job_result(kind, generation, result)
            return
        complete_resource_job(self._board, kind, generation, phase="idle")
        self._pending_results[(kind, generation)] = result
        self.job_state_changed.emit()

    def _handle_job_failure(self, kind: ResourceJobKind, generation: int, message: str) -> None:
        slot = self._board.slot(kind)
        if not should_apply_job_result(slot, generation):
            return
        if slot.cancel_requested or self._generation_cancelled(kind, generation):
            complete_resource_job(self._board, kind, generation, phase="idle")
        else:
            complete_resource_job(
                self._board,
                kind,
                generation,
                phase="failed",
                message=message,
            )
        self.job_state_changed.emit()

    def take_pending_result(self, kind: ResourceJobKind, generation: int) -> object | None:
        return self._pending_results.pop((kind, generation), None)


class ElidedPathItemDelegate(QtWidgets.QStyledItemDelegate):
    def initStyleOption(
        self,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex,
    ) -> None:
        super().initStyleOption(option, index)
        full_path = str(index.data(QtCore.Qt.ItemDataRole.UserRole) or "")
        if not full_path:
            option.text = ""
            return
        metrics = option.fontMetrics
        available_px = max(24, option.rect.width() - 12)
        avg_char_px = max(1, metrics.horizontalAdvance("n"))
        max_chars = max(12, available_px // avg_char_px)
        option.text = elide_path_middle(full_path, max_chars)


class ResourcesWindow(QtWidgets.QDialog):
    """Modeless resource manager owned by the alignment main window."""

    def __init__(self, main_window: HeatmapAlignmentWindow) -> None:
        super().__init__(main_window)
        self._main_window = main_window
        self.setWindowTitle("Resources")
        self.setModal(False)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.resize(920, 520)

        layout = QtWidgets.QVBoxLayout(self)

        self.session_label = QtWidgets.QLabel()
        self.session_label.setWordWrap(True)
        layout.addWidget(self.session_label)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["", "Resource", "Role", "Status", "Path"])
        table_header = self.table.horizontalHeader()
        table_header.setStretchLastSection(True)
        table_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        table_header.setSectionsClickable(False)
        table_header.setHighlightSections(False)
        self.table.setColumnWidth(0, 34)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setCornerButtonEnabled(False)
        self.table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_row_context_menu)
        self.table.itemSelectionChanged.connect(self._update_details_for_selection)
        self.table.setItemDelegateForColumn(0, ResourceColorSwatchDelegate(self.table))
        self.table.setItemDelegateForColumn(4, ElidedPathItemDelegate(self.table))
        layout.addWidget(self.table, stretch=1)

        details_group = QtWidgets.QGroupBox("Selected Resource")
        details_layout = QtWidgets.QVBoxLayout(details_group)
        details_layout.setSpacing(0)
        self.details_identity_label = QtWidgets.QLabel()
        self.details_identity_label.setWordWrap(True)
        self.details_status_label = QtWidgets.QLabel()
        self.details_status_label.setWordWrap(True)
        self.details_messages_label = QtWidgets.QLabel()
        self.details_messages_label.setWordWrap(True)
        self.details_messages_label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.details_path_widget = QtWidgets.QWidget()
        path_block_layout = QtWidgets.QVBoxLayout(self.details_path_widget)
        path_block_layout.setContentsMargins(
            0,
            RESOURCES_DETAILS_PATH_BLOCK_TOP_MARGIN_PX,
            0,
            0,
        )
        path_block_layout.setSpacing(0)
        self.details_path_label = QtWidgets.QLabel()
        self.details_path_label.setWordWrap(True)
        self.details_path_label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        path_block_layout.addWidget(self.details_path_label)
        details_layout.addWidget(self.details_identity_label)
        details_layout.addSpacing(RESOURCES_DETAILS_SECTION_SPACING_PX)
        details_layout.addWidget(self.details_status_label)
        details_layout.addWidget(self.details_messages_label)
        details_layout.addWidget(self.details_path_widget)
        details_layout.addSpacing(RESOURCES_DETAILS_SECTION_SPACING_PX)

        action_row = QtWidgets.QHBoxLayout()
        self.load_button = QtWidgets.QPushButton(RESOURCE_ACTION_LABELS["load"])
        self.replace_button = QtWidgets.QPushButton(RESOURCE_ACTION_LABELS["replace"])
        self.unload_button = QtWidgets.QPushButton(RESOURCE_ACTION_LABELS["unload"])
        self.reload_button = QtWidgets.QPushButton(RESOURCE_ACTION_LABELS["reload"])
        self.reveal_button = QtWidgets.QPushButton(RESOURCE_ACTION_LABELS["reveal"])
        self.inspect_button = QtWidgets.QPushButton(RESOURCE_ACTION_LABELS["inspect"])
        self.cancel_button = QtWidgets.QPushButton(RESOURCE_ACTION_LABELS["cancel"])
        for button in (
            self.load_button,
            self.replace_button,
            self.unload_button,
            self.reload_button,
            self.reveal_button,
            self.inspect_button,
            self.cancel_button,
        ):
            action_row.addWidget(button)
        action_row.addStretch(1)
        details_layout.addLayout(action_row)
        layout.addWidget(details_group)

        self.load_button.clicked.connect(lambda: self._invoke_action("load"))
        self.replace_button.clicked.connect(lambda: self._invoke_action("replace"))
        self.unload_button.clicked.connect(lambda: self._invoke_action("unload"))
        self.reload_button.clicked.connect(lambda: self._invoke_action("reload"))
        self.reveal_button.clicked.connect(lambda: self._invoke_action("reveal"))
        self.inspect_button.clicked.connect(lambda: self._invoke_action("inspect"))
        self.cancel_button.clicked.connect(lambda: self._invoke_action("cancel"))

        bottom_row = QtWidgets.QHBoxLayout()
        self.clear_all_button = QtWidgets.QPushButton("Clear All Resources...")
        self.clear_all_button.clicked.connect(self._main_window.clear_all_resources)
        bottom_row.addWidget(self.clear_all_button)
        bottom_row.addStretch(1)
        self.close_button = QtWidgets.QPushButton("&Close")
        self.close_button.clicked.connect(self._dismiss)
        bottom_row.addWidget(self.close_button)
        layout.addLayout(bottom_row)

        self._summaries: tuple[ResourceSummary, ...] = ()

    def _dismiss(self) -> None:
        self.hide()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        event.accept()
        self.hide()

    @staticmethod
    def _configure_table_item(item: QtWidgets.QTableWidgetItem) -> None:
        item.setFlags(
            QtCore.Qt.ItemFlag.ItemIsSelectable
            | QtCore.Qt.ItemFlag.ItemIsEnabled
        )

    def _selected_table_row(self) -> int:
        selection_model = self.table.selectionModel()
        if selection_model is not None:
            selected_rows = selection_model.selectedRows()
            if selected_rows:
                return selected_rows[0].row()
        return self.table.currentRow()

    def _select_table_row(self, row: int) -> None:
        if row < 0 or row >= self.table.rowCount():
            return
        self.table.blockSignals(True)
        try:
            self.table.clearSelection()
            self.table.selectRow(row)
            self.table.setCurrentCell(row, 0)
        finally:
            self.table.blockSignals(False)

    def refresh(self, summaries: tuple[ResourceSummary, ...], session_path: Path | None) -> None:
        if session_path is None:
            self.session_label.setText("Session: Untitled Session")
        else:
            self.session_label.setText(f"Session: {session_path}")
        self._summaries = summaries
        selected_kind = self._selected_kind()
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(summaries))
            for row_index, summary in enumerate(summaries):
                swatch_item = QtWidgets.QTableWidgetItem()
                swatch_item.setData(QtCore.Qt.ItemDataRole.UserRole, summary.color_hex)
                swatch_item.setData(QtCore.Qt.ItemDataRole.UserRole + 1, summary.color_muted)
                self._configure_table_item(swatch_item)
                self.table.setItem(row_index, 0, swatch_item)

                name_item = QtWidgets.QTableWidgetItem(summary.display_name)
                self._configure_table_item(name_item)
                self.table.setItem(row_index, 1, name_item)

                role_item = QtWidgets.QTableWidgetItem(summary.role)
                self._configure_table_item(role_item)
                self.table.setItem(row_index, 2, role_item)

                status_text = RESOURCE_STATUS_LABELS[summary.status]
                if summary.job_phase not in ("idle", "superseded"):
                    status_text = RESOURCE_JOB_STATUS_LABELS[summary.job_phase]
                status_item = QtWidgets.QTableWidgetItem(status_text)
                self._configure_table_item(status_item)
                self.table.setItem(row_index, 3, status_item)

                path_item = QtWidgets.QTableWidgetItem()
                path_item.setData(QtCore.Qt.ItemDataRole.UserRole, summary.path)
                if summary.path:
                    path_item.setToolTip(summary.path)
                self._configure_table_item(path_item)
                self.table.setItem(row_index, 4, path_item)

            if selected_kind is not None:
                for row_index, summary in enumerate(summaries):
                    if summary.kind == selected_kind:
                        self._select_table_row(row_index)
                        break
            elif summaries:
                self._select_table_row(0)
        finally:
            self.table.blockSignals(False)
        self._update_details_for_selection()

    def _selected_summary(self) -> ResourceSummary | None:
        row = self._selected_table_row()
        if row < 0 or row >= len(self._summaries):
            return None
        return self._summaries[row]

    def _selected_kind(self) -> ResourceKind | None:
        summary = self._selected_summary()
        return None if summary is None else summary.kind

    def _update_details_for_selection(self) -> None:
        summary = self._selected_summary()
        if summary is None:
            self.details_identity_label.setText("")
            self.details_status_label.setText("")
            self.details_messages_label.setText("")
            self.details_messages_label.setVisible(False)
            self.details_path_label.clear()
            self.details_path_widget.setVisible(False)
            for button in (
                self.load_button,
                self.replace_button,
                self.unload_button,
                self.reload_button,
                self.reveal_button,
                self.inspect_button,
                self.cancel_button,
            ):
                button.setEnabled(False)
            return

        self.details_identity_label.setText(
            f"{summary.display_name} ({summary.role})"
        )
        self.details_status_label.setText(
            f"{RESOURCE_STATUS_LABELS[summary.status]}\n{summary.details}"
        )
        if summary.messages:
            self.details_messages_label.setText("\n".join(summary.messages))
            self.details_messages_label.setVisible(True)
        else:
            self.details_messages_label.clear()
            self.details_messages_label.setVisible(False)

        if summary.path:
            self.details_path_label.setText(f"Path: {summary.path}")
            self.details_path_widget.setVisible(True)
        else:
            self.details_path_label.clear()
            self.details_path_widget.setVisible(False)

        action_set = set(summary.actions)
        self.load_button.setEnabled("load" in action_set)
        self.replace_button.setEnabled("replace" in action_set)
        self.unload_button.setEnabled("unload" in action_set)
        self.reload_button.setEnabled("reload" in action_set)
        self.reveal_button.setEnabled("reveal" in action_set)
        self.inspect_button.setEnabled("inspect" in action_set)
        self.cancel_button.setEnabled("cancel" in action_set)

    def _invoke_action(self, action: ResourceAction) -> None:
        summary = self._selected_summary()
        if summary is None:
            return
        self._main_window.invoke_resource_action(summary.kind, action)

    def _show_row_context_menu(self, position: QtCore.QPoint) -> None:
        index = self.table.indexAt(position)
        if not index.isValid():
            return
        self._select_table_row(index.row())
        summary = self._selected_summary()
        if summary is None:
            return
        menu = QtWidgets.QMenu(self)
        for action in summary.actions:
            menu_action = menu.addAction(RESOURCE_ACTION_LABELS[action])
            menu_action.triggered.connect(
                lambda _checked=False, kind=summary.kind, chosen=action: (
                    self._main_window.invoke_resource_action(kind, chosen)
                )
            )
        menu.exec(self.table.viewport().mapToGlobal(position))


@dataclass
class _CameraResourceBackup:
    camera_source: CameraVideoSource
    reference_width: int
    reference_height: int
    camera_track: CameraTrack
    current_camera_frame: np.ndarray | None
    viewport_corners: list[list[float]]
    export_overlay: ExportOverlaySettings


@dataclass
class _H5ResourceBackup:
    heatmap_source: HeatmapTruthSource
    heatmap_track: HeatmapTrack
    viewport_output_width: int
    viewport_output_height: int


class HeatmapAlignmentWindow(QtWidgets.QMainWindow):
    """Main window for the manual alignment workbench."""

    source_resolution_viewport_render_requested = QtCore.Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Heatmap Alignment Workbench")
        self.resize(1600, 980)

        self.session = AlignmentSession()
        self._current_session_path: Path | None = None
        self._resources_window: ResourcesWindow | None = None
        self._resource_reload_errors: dict[ResourceKind, str] = {}
        self._resource_load_warnings: dict[ResourceKind, tuple[str, ...]] = {}
        self.camera_source: CameraVideoSource | None = None
        self.heatmap_source: HeatmapTruthSource | None = None
        self.current_camera_frame: np.ndarray | None = None
        self._camera_reference_width = 0
        self._camera_reference_height = 0
        self._overlay_plot_renderer: HeatmapPlotRenderer | None = None
        self.peak_distance_datasource: LoadedPeakDistanceDatasource | None = None
        self.leg2_ultrasonic_datasource: LoadedLeg2UltrasonicDatasource | None = None
        self._freeze_export_overlay_preview = False
        self._export_in_progress = False
        self.settings = QtCore.QSettings("Acconeer", "HeatmapAlignmentWorkbench")
        self._viewport_drag_start_corners: np.ndarray | None = None
        self._playback_started_at_s: float | None = None
        self._playback_started_video_time_s = 0.0
        self._source_resolution_viewport_frame: np.ndarray | None = None
        self._source_resolution_request_token = 0
        self._source_resolution_worker_busy = False
        self._pending_source_resolution_request: dict[str, object] | None = None
        self._resource_job_manager = ResourceJobManager(self)
        self._resource_job_manager.job_state_changed.connect(
            self._handle_resource_job_state_changed
        )
        self._camera_replacement_backup: _CameraResourceBackup | None = None
        self._h5_replacement_backup: _H5ResourceBackup | None = None

        self.viewport_source_resolution_timer = QtCore.QTimer(self)
        self.viewport_source_resolution_timer.setSingleShot(True)
        self.viewport_source_resolution_timer.setInterval(200)
        self.viewport_source_resolution_timer.timeout.connect(
            self._start_debounced_source_resolution_viewport
        )

        self._source_resolution_thread = QtCore.QThread(self)
        self._source_resolution_worker = SourceResolutionViewportWorker()
        self._source_resolution_worker.moveToThread(self._source_resolution_thread)
        self.source_resolution_viewport_render_requested.connect(
            self._source_resolution_worker.render_request,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )
        self._source_resolution_worker.render_finished.connect(
            self._handle_source_resolution_viewport_result
        )
        self._source_resolution_thread.start()

        self.play_timer = QtCore.QTimer(self)
        self.play_timer.timeout.connect(self._advance_playback)
        self.play_timer_interval_ms = 16
        self.timeline_range_model = TimelineRangeModel(self)
        self._timeline_axis_geometry_sync_timer = QtCore.QTimer(self)
        self._timeline_axis_geometry_sync_timer.setSingleShot(True)
        self._timeline_axis_geometry_sync_timer.timeout.connect(self._sync_timeline_axis_geometry)

        self._create_menu_bar()
        self._build_ui()
        self.signal_plot.attach_timeline_range_model(self.timeline_range_model)
        self._connect_signals()
        self._update_controls_enabled_state()
        self._refresh_session_title()
        self._refresh_resources_ui()
        self.statusBar().showMessage("Load camera video and H5 recording to begin.")
        QtCore.QTimer.singleShot(0, self.schedule_timeline_axis_geometry_sync)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.viewport_source_resolution_timer.stop()
        self._source_resolution_thread.quit()
        self._source_resolution_thread.wait()
        self._close_sources()
        super().closeEvent(event)

    def _abandon_resource_jobs(self) -> None:
        self._resource_job_manager.abandon_all_jobs()
        self._camera_replacement_backup = None
        self._h5_replacement_backup = None

    def _create_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        self.open_session_action = QtGui.QAction("Open Session...", self)
        self.open_session_action.triggered.connect(self._load_session)
        file_menu.addAction(self.open_session_action)

        self.save_session_action = QtGui.QAction("Save Session", self)
        self.save_session_action.setShortcut(QtGui.QKeySequence.StandardKey.Save)
        self.save_session_action.triggered.connect(self._save_session)
        file_menu.addAction(self.save_session_action)

        self.save_session_as_action = QtGui.QAction("Save Session As...", self)
        self.save_session_as_action.triggered.connect(self._save_session_as)
        file_menu.addAction(self.save_session_as_action)

        self.close_session_action = QtGui.QAction("Close Session", self)
        self.close_session_action.triggered.connect(self._close_session)
        file_menu.addAction(self.close_session_action)

        file_menu.addSeparator()

        self.export_synced_action = QtGui.QAction("Export Synced Video...", self)
        self.export_synced_action.triggered.connect(self._export_synced_video)
        file_menu.addAction(self.export_synced_action)

        file_menu.addSeparator()

        quit_action = QtGui.QAction("&Quit", self)
        quit_action.setShortcut(QtGui.QKeySequence.StandardKey.Quit)
        quit_action.setMenuRole(QtGui.QAction.MenuRole.QuitRole)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        resources_menu = self.menuBar().addMenu("&Resources")

        self.manage_resources_action = QtGui.QAction("&Manage Resources...", self)
        self.manage_resources_action.triggered.connect(self._show_resources_window)
        resources_menu.addAction(self.manage_resources_action)

        resources_menu.addSeparator()

        self.load_camera_action = QtGui.QAction("&Load Camera Video...", self)
        self.load_camera_action.triggered.connect(self._load_camera_video)
        resources_menu.addAction(self.load_camera_action)

        self.load_h5_action = QtGui.QAction("Load Radar Raw (&H5)...", self)
        self.load_h5_action.triggered.connect(self._load_h5_recording)
        resources_menu.addAction(self.load_h5_action)

        self.load_peak_action = QtGui.QAction("Load Radar Peak (&JSON)...", self)
        self.load_peak_action.triggered.connect(self._import_peak_distance_json)
        resources_menu.addAction(self.load_peak_action)

        self.load_leg2_action = QtGui.QAction("Load &Leg2 MAT...", self)
        self.load_leg2_action.triggered.connect(self._import_leg2_mat)
        resources_menu.addAction(self.load_leg2_action)

        resources_menu.addSeparator()

        self.unload_camera_action = QtGui.QAction("&Unload Camera Video", self)
        self.unload_camera_action.triggered.connect(self.unload_camera_video)
        resources_menu.addAction(self.unload_camera_action)

        self.unload_h5_action = QtGui.QAction("Unload Radar Raw (&H5)", self)
        self.unload_h5_action.triggered.connect(self.unload_h5_recording)
        resources_menu.addAction(self.unload_h5_action)

        self.unload_peak_action = QtGui.QAction("Clear Radar Peak (&JSON)", self)
        self.unload_peak_action.triggered.connect(self._clear_peak_distance_datasource)
        resources_menu.addAction(self.unload_peak_action)

        self.unload_leg2_action = QtGui.QAction("Clear &Leg2 MAT", self)
        self.unload_leg2_action.triggered.connect(self._clear_leg2_ultrasonic_datasource)
        resources_menu.addAction(self.unload_leg2_action)

        resources_menu.addSeparator()

        self.reload_camera_action = QtGui.QAction("&Reload Camera Video", self)
        self.reload_camera_action.triggered.connect(
            lambda: self.invoke_resource_action("camera", "reload")
        )
        resources_menu.addAction(self.reload_camera_action)

        self.reload_h5_action = QtGui.QAction("Reload Radar Raw (&H5)", self)
        self.reload_h5_action.triggered.connect(
            lambda: self.invoke_resource_action("radar_h5", "reload")
        )
        resources_menu.addAction(self.reload_h5_action)

        self.reload_peak_action = QtGui.QAction("Reload Radar Peak (&JSON)", self)
        self.reload_peak_action.triggered.connect(
            lambda: self.invoke_resource_action("radar_peak", "reload")
        )
        resources_menu.addAction(self.reload_peak_action)

        self.reload_leg2_action = QtGui.QAction("Reload &Leg2 MAT", self)
        self.reload_leg2_action.triggered.connect(
            lambda: self.invoke_resource_action("leg2_mat", "reload")
        )
        resources_menu.addAction(self.reload_leg2_action)

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(central)

        preview_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.camera_view = CornerEditorWidget()
        self.viewport_view = ViewportEditorWidget("Viewport")
        self.truth_view = ImagePreview("Rendered Heatmap")
        camera_group = self._wrap_group("Camera Video", self.camera_view)
        viewport_group = QtWidgets.QGroupBox("Viewport")
        viewport_layout = QtWidgets.QVBoxLayout(viewport_group)
        viewport_layout.addWidget(self.viewport_view)
        self.viewport_controls_widget = QtWidgets.QWidget()
        viewport_controls_layout = QtWidgets.QGridLayout(self.viewport_controls_widget)
        viewport_controls_layout.setContentsMargins(0, 0, 0, 0)
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        viewport_layout.addWidget(self.viewport_controls_widget)
        right_layout.addWidget(viewport_group)
        right_layout.addWidget(self._wrap_group("Rendered Heatmap", self.truth_view))
        preview_splitter.addWidget(camera_group)
        preview_splitter.addWidget(right_panel)
        preview_splitter.setChildrenCollapsible(False)
        preview_splitter.setStretchFactor(0, 3)
        preview_splitter.setStretchFactor(1, 2)
        layout.addWidget(preview_splitter, stretch=1)

        signals_group = QtWidgets.QGroupBox("Signals")
        signals_layout = QtWidgets.QVBoxLayout(signals_group)
        signals_layout.setContentsMargins(9, 9, 9, 9)
        self.signal_plot = SignalPlotWidget()
        self.signal_plot.setMinimumHeight(160)
        signals_layout.addWidget(self.signal_plot)
        layout.addWidget(signals_group)

        timeline_group = QtWidgets.QGroupBox("Timeline")
        timeline_layout = QtWidgets.QVBoxLayout(timeline_group)
        timeline_layout.setContentsMargins(9, 9, 9, 9)
        timeline_controls_layout = QtWidgets.QHBoxLayout()
        self.play_button = QtWidgets.QPushButton("Play")
        self.current_time_label = QtWidgets.QLabel("t = 0.000 s")
        self.timeline_view = AlignmentTimelineWidget(self.timeline_range_model)
        self.current_time_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.current_time_slider.setRange(0, 10000)
        self.offset_spin = QtWidgets.QDoubleSpinBox()
        self.offset_spin.setDecimals(3)
        self.offset_spin.setRange(-3600.0, 3600.0)
        self.offset_spin.setSingleStep(0.01)
        self.nudge_left_small = QtWidgets.QPushButton("-10 ms")
        self.nudge_right_small = QtWidgets.QPushButton("+10 ms")
        self.nudge_left_large = QtWidgets.QPushButton("-100 ms")
        self.nudge_right_large = QtWidgets.QPushButton("+100 ms")
        timeline_controls_layout.addWidget(self.play_button)
        timeline_controls_layout.addWidget(self.current_time_label)
        timeline_controls_layout.addWidget(QtWidgets.QLabel("Camera offset (s)"))
        timeline_controls_layout.addWidget(self.offset_spin)
        timeline_controls_layout.addWidget(self.nudge_left_large)
        timeline_controls_layout.addWidget(self.nudge_left_small)
        timeline_controls_layout.addWidget(self.nudge_right_small)
        timeline_controls_layout.addWidget(self.nudge_right_large)
        timeline_controls_layout.addStretch(1)
        timeline_layout.addLayout(timeline_controls_layout)
        timeline_layout.addWidget(self.timeline_view)
        timeline_layout.addWidget(self.current_time_slider)
        layout.addWidget(timeline_group)

        render_group = QtWidgets.QGroupBox("Render")
        render_layout = QtWidgets.QGridLayout(render_group)
        self.color_min_spin = QtWidgets.QDoubleSpinBox()
        self.color_min_spin.setRange(-1_000_000.0, 1_000_000.0)
        self.color_min_spin.setValue(0.0)
        self.color_min_spin.setDecimals(1)
        self.color_max_spin = QtWidgets.QDoubleSpinBox()
        self.color_max_spin.setRange(0.0, 1_000_000.0)
        self.color_max_spin.setValue(3000.0)
        self.color_max_spin.setDecimals(1)
        self.blur_spin = QtWidgets.QDoubleSpinBox()
        self.blur_spin.setRange(0.0, 20.0)
        self.blur_spin.setSingleStep(0.1)
        self.blur_spin.setEnabled(False)
        self.downscale_spin = QtWidgets.QDoubleSpinBox()
        self.downscale_spin.setRange(0.1, 1.0)
        self.downscale_spin.setSingleStep(0.05)
        self.downscale_spin.setValue(1.0)
        self.downscale_spin.setEnabled(False)
        self.lag_window_spin = QtWidgets.QDoubleSpinBox()
        self.lag_window_spin.setRange(0.1, 30.0)
        self.lag_window_spin.setValue(2.0)
        self.lag_window_spin.setEnabled(False)
        self.sample_count_spin = QtWidgets.QSpinBox()
        self.sample_count_spin.setRange(5, 300)
        self.sample_count_spin.setValue(30)
        self.sample_count_spin.setEnabled(False)
        self.viewport_enhance_checkbox = QtWidgets.QCheckBox("Enhance Viewport")
        self.viewport_map_to_viridis_checkbox = QtWidgets.QCheckBox("Map to Viridis")
        self.viewport_range_slider = DoubleRangeSlider()
        self.viewport_low_label = QtWidgets.QLabel("Low 0.00")
        self.viewport_high_label = QtWidgets.QLabel("High 1.00")
        self.viewport_gamma_spin = QtWidgets.QDoubleSpinBox()
        self.viewport_gamma_spin.setRange(0.1, 5.0)
        self.viewport_gamma_spin.setSingleStep(0.05)
        self.viewport_gamma_spin.setValue(1.0)
        self.viewport_gamma_spin.setDecimals(2)
        self.leg2_signal_kind_combo = QtWidgets.QComboBox()
        self.leg2_signal_kind_combo.addItem("Raw ultrasonic", "raw")
        self.leg2_signal_kind_combo.addItem("Filtered ultrasonic", "filtered")
        self.show_peak_marker_checkbox = QtWidgets.QCheckBox("Show Peak Marker")
        self.show_peak_marker_checkbox.setChecked(True)
        self.show_leg2_signal_checkbox = QtWidgets.QCheckBox("Show Leg2 Signal")
        self.show_leg2_signal_checkbox.setChecked(True)
        render_layout.addWidget(QtWidgets.QLabel("Color Min"), 0, 0)
        render_layout.addWidget(self.color_min_spin, 0, 1)
        render_layout.addWidget(QtWidgets.QLabel("Color Max"), 0, 2)
        render_layout.addWidget(self.color_max_spin, 0, 3)
        render_layout.addWidget(QtWidgets.QLabel("Blur"), 0, 4)
        render_layout.addWidget(self.blur_spin, 0, 5)
        render_layout.addWidget(QtWidgets.QLabel("Downscale"), 0, 6)
        render_layout.addWidget(self.downscale_spin, 0, 7)
        render_layout.addWidget(QtWidgets.QLabel("Lag Window (s)"), 1, 0)
        render_layout.addWidget(self.lag_window_spin, 1, 1)
        render_layout.addWidget(QtWidgets.QLabel("Sample Count"), 1, 2)
        render_layout.addWidget(self.sample_count_spin, 1, 3)
        render_layout.addWidget(self.show_peak_marker_checkbox, 2, 0, 1, 2)
        render_layout.addWidget(self.leg2_signal_kind_combo, 2, 2)
        render_layout.addWidget(self.show_leg2_signal_checkbox, 2, 3)
        viewport_controls_layout.addWidget(self.viewport_enhance_checkbox, 0, 0, 1, 2)
        viewport_controls_layout.addWidget(self.viewport_map_to_viridis_checkbox, 0, 2, 1, 2)
        viewport_controls_layout.addWidget(QtWidgets.QLabel("Range"), 1, 0)
        viewport_controls_layout.addWidget(self.viewport_low_label, 1, 1)
        viewport_controls_layout.addWidget(self.viewport_range_slider, 1, 2, 1, 3)
        viewport_controls_layout.addWidget(self.viewport_high_label, 1, 5)
        viewport_controls_layout.addWidget(QtWidgets.QLabel("Gamma"), 2, 0)
        viewport_controls_layout.addWidget(self.viewport_gamma_spin, 2, 1)
        viewport_controls_layout.setColumnStretch(2, 1)
        layout.addWidget(render_group, stretch=1)

        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self.leg2_signal_kind_combo.currentIndexChanged.connect(self._leg2_signal_kind_changed)
        self.show_peak_marker_checkbox.toggled.connect(self._peak_marker_visibility_changed)
        self.show_leg2_signal_checkbox.toggled.connect(self._leg2_signal_visibility_changed)
        self.play_button.clicked.connect(self._toggle_playback)
        self.timeline_view.playhead_changed.connect(self._timeline_playhead_changed)
        self.timeline_view.camera_offset_changed.connect(self._timeline_camera_offset_changed)
        self.timeline_view.leg2_offset_changed.connect(self._timeline_leg2_offset_changed)
        self.timeline_view.h5_alignment_drag_changed.connect(self._timeline_h5_alignment_drag_changed)
        self.timeline_view.h5_alignment_drag_finished.connect(
            self._timeline_h5_alignment_drag_finished
        )
        self.current_time_slider.valueChanged.connect(self._slider_to_time)
        self.offset_spin.valueChanged.connect(self._offset_changed)
        self.nudge_left_small.clicked.connect(lambda: self._nudge_offset(-0.010))
        self.nudge_right_small.clicked.connect(lambda: self._nudge_offset(0.010))
        self.nudge_left_large.clicked.connect(lambda: self._nudge_offset(-0.100))
        self.nudge_right_large.clicked.connect(lambda: self._nudge_offset(0.100))
        self.color_min_spin.valueChanged.connect(self._render_settings_changed)
        self.color_max_spin.valueChanged.connect(self._render_settings_changed)
        self.viewport_enhance_checkbox.toggled.connect(self._viewport_visibility_changed)
        self.viewport_map_to_viridis_checkbox.toggled.connect(self._viewport_visibility_changed)
        self.viewport_range_slider.values_changed.connect(self._viewport_visibility_range_changed)
        self.viewport_gamma_spin.valueChanged.connect(self._viewport_visibility_changed)
        self.blur_spin.valueChanged.connect(self._preprocess_settings_changed)
        self.downscale_spin.valueChanged.connect(self._preprocess_settings_changed)
        self.lag_window_spin.valueChanged.connect(self._preprocess_settings_changed)
        self.sample_count_spin.valueChanged.connect(self._preprocess_settings_changed)
        self.camera_view.corners_changed.connect(self._corners_changed)
        self.camera_view.export_overlay_changed.connect(self._export_overlay_changed)
        self.camera_view.export_overlay_visibility_changed.connect(
            self._set_export_overlay_visible
        )
        self.camera_view.export_overlay_preview_toggled.connect(
            self._set_export_overlay_preview_enabled
        )
        self.camera_view.export_overlay_reset_requested.connect(self._reset_export_overlay)
        self.camera_view.export_overlay_drag_active_changed.connect(
            self._set_export_overlay_drag_active
        )
        self.viewport_view.resized.connect(self._viewport_preview_resized)
        self.viewport_view.corner_dragged.connect(self._viewport_corner_dragged)
        self.viewport_view.edge_dragged.connect(self._viewport_edge_dragged)
        self.viewport_view.center_dragged.connect(self._viewport_center_dragged)
        self.viewport_view.drag_finished.connect(self._viewport_drag_finished)
        self.signal_plot.view_settings_changed.connect(self._signal_plot_view_settings_changed)
        self.signal_plot.axis_geometry_sync_requested.connect(
            self.schedule_timeline_axis_geometry_sync
        )

    def schedule_timeline_axis_geometry_sync(self) -> None:
        self._timeline_axis_geometry_sync_timer.start(0)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self.schedule_timeline_axis_geometry_sync()

    def _sync_timeline_axis_geometry(self) -> None:
        if not self.isVisible():
            return
        signal_left_px, signal_right_px = self.signal_plot.viewbox_horizontal_extent_local()
        if signal_right_px <= signal_left_px + 1.0:
            return

        timeline_width_px = self.timeline_view.width()
        if timeline_width_px <= 1:
            return

        left_global = self.signal_plot.mapToGlobal(QtCore.QPointF(signal_left_px, 0.0))
        right_global = self.signal_plot.mapToGlobal(QtCore.QPointF(signal_right_px, 0.0))
        timeline_left_px = self.timeline_view.mapFromGlobal(left_global).x()
        timeline_right_px = self.timeline_view.mapFromGlobal(right_global).x()

        if timeline_right_px <= timeline_left_px + 1.0:
            return
        self.timeline_view.set_time_axis_rect(timeline_left_px, timeline_right_px)

    def _wrap_group(self, title: str, widget: QtWidgets.QWidget) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(group)
        layout.addWidget(widget)
        return group

    def _close_sources(self) -> None:
        self._abandon_resource_jobs()
        self._set_playback_active(False, refresh_viewport=False)
        self.viewport_source_resolution_timer.stop()
        self._source_resolution_request_token += 1
        self._source_resolution_viewport_frame = None
        self._pending_source_resolution_request = None
        if self.camera_source is not None:
            self.camera_source.close()
            self.camera_source = None
        self._camera_reference_width = 0
        self._camera_reference_height = 0
        self._overlay_plot_renderer = None
        self._freeze_export_overlay_preview = False
        if self.heatmap_source is not None:
            self.heatmap_source.close()
            self.heatmap_source = None
        self.peak_distance_datasource = None
        self.leg2_ultrasonic_datasource = None
        self.camera_view.set_export_overlay_preview_frame(None)
        self.camera_view.set_corners(None)
        self.viewport_view.set_frame(None)

    def _load_camera_video(self) -> None:
        start_path = self._dialog_start_path("last_camera_path")
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load camera video",
            start_path,
            "Video files (*.mp4 *.mov *.avi *.mkv);;All files (*)",
        )
        if filename:
            self.load_camera_from_path(Path(filename))

    def load_camera_from_path(self, camera_path: Path) -> None:
        if not camera_path.exists():
            self._set_resource_reload_error("camera", f"File not found: {camera_path}")
            self._refresh_resources_ui()
            return
        replaces_active = self.camera_source is not None
        if replaces_active:
            self._camera_replacement_backup = self._snapshot_active_camera()
        self._set_resource_reload_error("camera", None)
        self._resource_job_manager.start_camera_job(
            camera_path,
            replaces_active=replaces_active,
        )
        self._update_resource_loading_overlays()
        self._refresh_resources_ui()
        self.statusBar().showMessage(f"Loading camera video: {camera_path.name}")

    def _load_h5_recording(self) -> None:
        start_path = self._dialog_start_path("last_h5_path")
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load H5 recording",
            start_path,
            "H5 files (*.h5 *.hdf5);;All files (*)",
        )
        if filename:
            self.load_h5_from_path(Path(filename))

    def load_h5_from_path(self, h5_path: Path) -> None:
        if not h5_path.exists():
            self._set_resource_reload_error("radar_h5", f"File not found: {h5_path}")
            self._refresh_resources_ui()
            return
        replaces_active = self.heatmap_source is not None
        if replaces_active:
            self._h5_replacement_backup = self._snapshot_active_h5()
        self._set_resource_reload_error("radar_h5", None)
        self._resource_job_manager.start_h5_job(
            h5_path,
            replaces_active=replaces_active,
            session_idx=self.session.heatmap_track.session_idx,
            group_idx=self.session.heatmap_track.group_idx,
            entry_idx=self.session.heatmap_track.entry_idx,
            subsweep_idx=self.session.heatmap_track.subsweep_idx,
            color_min=self.color_min_spin.value(),
            color_max=self.color_max_spin.value(),
            fixed_levels=True,
        )
        self._update_resource_loading_overlays()
        self._refresh_resources_ui()
        self.statusBar().showMessage(f"Loading H5 recording: {h5_path.name}")

    def _peak_csv_rejection_message(self) -> str:
        return (
            "Reduced CSV peak-distance exports cannot be imported here. "
            "Use the canonical JSON export from `hatch run app:peak-distances`."
        )

    def load_peak_distance_from_path(
        self,
        json_path: Path,
        *,
        show_dialogs: bool = False,
        require_heatmap: bool = False,
    ) -> bool:
        if require_heatmap and self.heatmap_source is None:
            if show_dialogs:
                QtWidgets.QMessageBox.information(
                    self,
                    "Import peak-distance JSON",
                    "Load an H5 recording before importing a peak-distance JSON file.",
                )
            return False

        if json_path.suffix.lower() == ".csv":
            message = self._peak_csv_rejection_message()
            if show_dialogs:
                QtWidgets.QMessageBox.warning(self, "Import peak-distance JSON", message)
            else:
                self.statusBar().showMessage(message)
            return False

        try:
            datasource, warnings = import_peak_distance_json_for_heatmap(
                json_path,
                self.heatmap_source,
            )
        except ValueError as exc:
            if isinstance(exc, PeakDistanceJsonImportError):
                message = exc.user_message()
                status_message = exc.primary_message
            else:
                message = str(exc)
                status_message = f"Could not load peak-distance JSON: {exc}"
            if show_dialogs:
                QtWidgets.QMessageBox.warning(self, "Import failed", message)
            else:
                self.statusBar().showMessage(status_message)
            self._set_resource_reload_error("radar_peak", status_message)
            self._refresh_resources_ui()
            return False

        self.peak_distance_datasource = datasource
        self.session.peak_distance_datasource.path = str(json_path)
        self.session.peak_distance_datasource.visible = self.show_peak_marker_checkbox.isChecked()
        self.settings.setValue("last_peak_json_path", str(json_path))
        self._set_resource_reload_error("radar_peak", None)
        self._set_resource_warnings("radar_peak", tuple(warnings))
        self._update_peak_datasource_controls()
        self._sync_previews(camera_access_hint="auto")

        if self.heatmap_source is None:
            message = (
                f"Loaded peak-distance JSON: {json_path.name} "
                "(H5 validation pending until a recording is loaded)."
            )
        else:
            message = f"Loaded peak-distance JSON: {json_path.name}"
        if warnings:
            warning_text = "\n".join(f"- {warning}" for warning in warnings)
            message = f"{message}\n\nWarnings:\n{warning_text}"
            if show_dialogs:
                QtWidgets.QMessageBox.warning(self, "Import warnings", message)
        self.statusBar().showMessage(message.splitlines()[0])
        self._refresh_resources_ui()
        return True

    def _import_peak_distance_json(self) -> None:
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import peak-distance JSON",
            self._dialog_start_path("last_peak_json_path"),
            "Peak-distance JSON (*.json);;All files (*)",
        )
        if not filename:
            return

        self.load_peak_distance_from_path(
            Path(filename),
            show_dialogs=True,
            require_heatmap=True,
        )

    def _clear_peak_distance_datasource(self) -> None:
        self.peak_distance_datasource = None
        self.session.peak_distance_datasource.path = ""
        self.session.peak_distance_datasource.visible = True
        self._set_resource_reload_error("radar_peak", None)
        self._set_resource_warnings("radar_peak", ())
        self._update_peak_datasource_controls()
        self._sync_previews(camera_access_hint="auto")
        self._refresh_resources_ui()
        self.statusBar().showMessage("Cleared imported peak-distance datasource.")

    def load_leg2_mat_from_path(
        self,
        mat_path: Path,
        *,
        show_dialogs: bool = False,
    ) -> bool:
        try:
            datasource = import_leg2_mat_for_heatmap(mat_path)
        except (Leg2MatImportError, TypeError) as exc:
            if isinstance(exc, Leg2MatImportError):
                message = exc.user_message()
                status_message = exc.user_message().splitlines()[0]
            else:
                message = f"Could not load Leg2 MAT: {exc}"
                status_message = message
            if show_dialogs:
                QtWidgets.QMessageBox.warning(self, "Import failed", message)
            else:
                self.statusBar().showMessage(status_message)
            self._set_resource_reload_error("leg2_mat", status_message)
            self._refresh_resources_ui()
            return False
        except ValueError as exc:
            message = str(exc)
            if show_dialogs:
                QtWidgets.QMessageBox.warning(self, "Import failed", message)
            else:
                self.statusBar().showMessage(f"Could not load Leg2 MAT: {message}")
            self._set_resource_reload_error("leg2_mat", message)
            self._refresh_resources_ui()
            return False

        self.leg2_ultrasonic_datasource = datasource
        self.session.leg2_ultrasonic_datasource.path = str(mat_path)
        self.session.leg2_ultrasonic_datasource.visible = self.show_leg2_signal_checkbox.isChecked()
        self.settings.setValue("last_leg2_mat_path", str(mat_path))
        self._set_resource_reload_error("leg2_mat", None)
        self._set_resource_warnings("leg2_mat", ())
        self._update_leg2_datasource_controls()
        self._sync_previews(camera_access_hint="auto")
        self._refresh_resources_ui()
        self.statusBar().showMessage(f"Loaded Leg2 MAT: {mat_path.name}")
        return True

    def _import_leg2_mat(self) -> None:
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import Leg2 MAT",
            self._dialog_start_path("last_leg2_mat_path"),
            "MATLAB files (*.mat);;All files (*)",
        )
        if not filename:
            return
        self.load_leg2_mat_from_path(Path(filename), show_dialogs=True)

    def _clear_leg2_ultrasonic_datasource(self) -> None:
        self.leg2_ultrasonic_datasource = None
        self.session.leg2_ultrasonic_datasource.path = ""
        self.session.leg2_ultrasonic_datasource.visible = True
        self.session.leg2_ultrasonic_datasource.offset_s = 0.0
        self._set_resource_reload_error("leg2_mat", None)
        self._set_resource_warnings("leg2_mat", ())
        self._update_leg2_datasource_controls()
        self._sync_previews(camera_access_hint="auto")
        self._refresh_resources_ui()
        self.statusBar().showMessage("Cleared Leg2 MAT ultrasonic datasource.")

    def _reload_leg2_ultrasonic_datasource_from_session(self) -> None:
        self.leg2_ultrasonic_datasource = None
        mat_path_text = self.session.leg2_ultrasonic_datasource.path
        if not mat_path_text:
            self._update_leg2_datasource_controls()
            return

        mat_path = Path(mat_path_text)
        if not mat_path.exists():
            self._set_resource_reload_error("leg2_mat", f"File not found: {mat_path}")
            self.statusBar().showMessage(
                f"Leg2 MAT not found and was not loaded: {mat_path}"
            )
            self._update_leg2_datasource_controls()
            self._refresh_resources_ui()
            return

        if not self.load_leg2_mat_from_path(mat_path, show_dialogs=False):
            self._set_resource_reload_error(
                "leg2_mat",
                f"Could not reload Leg2 MAT: {mat_path.name}",
            )
            self._update_leg2_datasource_controls()
            self._refresh_resources_ui()

    def _leg2_signal_kind_changed(self, _index: int) -> None:
        signal_kind = self.leg2_signal_kind_combo.currentData()
        if signal_kind not in ("raw", "filtered"):
            return
        self.session.leg2_ultrasonic_datasource.signal_kind = signal_kind
        self._sync_previews(camera_access_hint="auto")

    def _leg2_signal_visibility_changed(self, visible: bool) -> None:
        self.session.leg2_ultrasonic_datasource.visible = visible
        self._sync_previews(camera_access_hint="auto")

    def _update_leg2_datasource_controls(self) -> None:
        datasource = self.leg2_ultrasonic_datasource
        has_datasource = datasource is not None
        self.leg2_signal_kind_combo.setEnabled(has_datasource)
        self.show_leg2_signal_checkbox.setEnabled(has_datasource)
        self.timeline_view.update()

    def _reload_peak_distance_datasource_from_session(self) -> None:
        self.peak_distance_datasource = None
        json_path_text = self.session.peak_distance_datasource.path
        if not json_path_text:
            self._update_peak_datasource_controls()
            return

        json_path = Path(json_path_text)
        if not json_path.exists():
            self._set_resource_reload_error("radar_peak", f"File not found: {json_path}")
            self.statusBar().showMessage(
                f"Peak-distance JSON not found and was not loaded: {json_path}"
            )
            self._update_peak_datasource_controls()
            self._refresh_resources_ui()
            return

        if self.heatmap_source is None:
            if self.load_peak_distance_from_path(json_path, show_dialogs=False):
                return
            self._update_peak_datasource_controls()
            self._refresh_resources_ui()
            return

        try:
            datasource, warnings = import_peak_distance_json_for_heatmap(
                json_path,
                self.heatmap_source,
            )
        except ValueError as exc:
            if isinstance(exc, PeakDistanceJsonImportError):
                message = exc.primary_message
            else:
                message = f"Could not reload peak-distance JSON: {exc}"
            self._set_resource_reload_error("radar_peak", message)
            self.statusBar().showMessage(message)
            self._update_peak_datasource_controls()
            self._refresh_resources_ui()
            return

        self.peak_distance_datasource = datasource
        self._set_resource_reload_error("radar_peak", None)
        self._set_resource_warnings("radar_peak", tuple(warnings))
        if warnings:
            self.statusBar().showMessage(
                "Reloaded peak-distance JSON with warnings: " + "; ".join(warnings)
            )
        self._update_peak_datasource_controls()
        self._refresh_resources_ui()

    def _peak_marker_visibility_changed(self, visible: bool) -> None:
        self.session.peak_distance_datasource.visible = visible
        self._sync_previews(camera_access_hint="auto")

    def _update_peak_datasource_controls(self) -> None:
        datasource = self.peak_distance_datasource
        has_datasource = datasource is not None
        self.show_peak_marker_checkbox.setEnabled(has_datasource)

    def _peak_overlay_for_frame(self, frame_idx: int) -> tuple[float, float] | None:
        if (
            self.peak_distance_datasource is None
            or not self.session.peak_distance_datasource.visible
        ):
            return None
        measurement = measurement_for_frame(self.peak_distance_datasource, frame_idx)
        if measurement is None or measurement.status != STATUS_DETECTED:
            return None
        if measurement.peak_distance_m is None:
            return None
        return (
            measurement.peak_distance_m,
            self.peak_distance_datasource.metadata.zero_velocity_m_s,
        )

    def _annotate_truth_frame_with_peak(
        self,
        truth_frame: np.ndarray,
        frame_idx: int,
    ) -> np.ndarray:
        peak_overlay = self._peak_overlay_for_frame(frame_idx)
        if peak_overlay is None or self.heatmap_source is None:
            return truth_frame
        peak_distance_m, zero_velocity_m_s = peak_overlay
        subsweep = select_subsweep(self.heatmap_source.record, self.heatmap_source.subsweep_idx)
        axes = heatmap_axes(
            self.heatmap_source.record.metadata,
            self.heatmap_source.record.sensor_config,
            subsweep,
        )
        return annotate_heatmap_rgb_with_peak(
            truth_frame,
            axes=axes,
            peak_distance_m=peak_distance_m,
            zero_velocity_m_s=zero_velocity_m_s,
        )

    def _save_session(self) -> None:
        if self._current_session_path is None:
            self._save_session_as()
            return
        self._write_session_to_path(self._current_session_path)

    def _save_session_as(self) -> None:
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save session as",
            self._dialog_start_path("last_session_path"),
            "JSON files (*.json);;All files (*)",
        )
        if not filename:
            return
        self._write_session_to_path(Path(filename))

    def _write_session_to_path(self, session_path: Path) -> None:
        try:
            validate_alignment_session(self.session, allow_missing_sources=False)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Cannot save session", str(exc))
            return

        save_alignment_session(self.session, session_path)
        self._current_session_path = session_path
        self.settings.setValue("last_session_path", str(session_path))
        self._refresh_session_title()
        self._refresh_resources_ui()
        self.statusBar().showMessage(f"Saved session: {session_path}")

    def _load_session(self) -> None:
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open session",
            self._dialog_start_path("last_session_path"),
            "JSON files (*.json);;All files (*)",
        )
        if filename:
            self.load_session_from_path(Path(filename))

    def load_session_from_path(self, session_path: Path) -> None:
        session = load_alignment_session(session_path)
        self._close_sources()
        self.session = session
        self._current_session_path = session_path
        self._resource_reload_errors.clear()
        self._resource_load_warnings.clear()

        self._populate_controls_from_session()
        if session.camera_track.path:
            camera_path = Path(session.camera_track.path)
            if camera_path.exists():
                self.load_camera_from_path(camera_path)
            else:
                self._set_resource_reload_error("camera", f"File not found: {camera_path}")
        if session.heatmap_track.path:
            h5_path = Path(session.heatmap_track.path)
            if h5_path.exists():
                self.load_h5_from_path(h5_path)
            else:
                self._set_resource_reload_error("radar_h5", f"File not found: {h5_path}")
        else:
            self._reload_peak_distance_datasource_from_session()
        self._reload_leg2_ultrasonic_datasource_from_session()
        if self.camera_source is not None:
            self._load_current_camera_frame(access_hint="random")
            self._refresh_camera_view_corners()
            self.camera_view.set_export_overlay(self.session.export_overlay)
        self._update_controls_enabled_state()
        if self.camera_source is not None or self.heatmap_source is not None:
            self._sync_previews(camera_access_hint="auto")
        self.settings.setValue("last_session_path", str(session_path))
        if self.session.camera_track.path:
            self.settings.setValue("last_camera_path", self.session.camera_track.path)
        if self.session.heatmap_track.path:
            self.settings.setValue("last_h5_path", self.session.heatmap_track.path)
        self._refresh_session_title()
        self._refresh_resources_ui()
        self.statusBar().showMessage(f"Loaded session: {session_path}")

    def _snapshot_active_camera(self) -> _CameraResourceBackup:
        if self.camera_source is None:
            raise RuntimeError("Cannot snapshot camera resource when no camera is loaded.")
        return _CameraResourceBackup(
            camera_source=self.camera_source,
            reference_width=self._camera_reference_width,
            reference_height=self._camera_reference_height,
            camera_track=CameraTrack(
                path=self.session.camera_track.path,
                fps=self.session.camera_track.fps,
                duration_s=self.session.camera_track.duration_s,
                frame_count=self.session.camera_track.frame_count,
            ),
            current_camera_frame=(
                None
                if self.current_camera_frame is None
                else self.current_camera_frame.copy()
            ),
            viewport_corners=[list(point) for point in self.session.viewport.corners],
            export_overlay=ExportOverlaySettings(
                visible=self.session.export_overlay.visible,
                preview_enabled=self.session.export_overlay.preview_enabled,
                x=self.session.export_overlay.x,
                y=self.session.export_overlay.y,
                width=self.session.export_overlay.width,
                height=self.session.export_overlay.height,
            ),
        )

    def _snapshot_active_h5(self) -> _H5ResourceBackup:
        if self.heatmap_source is None:
            raise RuntimeError("Cannot snapshot H5 resource when no recording is loaded.")
        return _H5ResourceBackup(
            heatmap_source=self.heatmap_source,
            heatmap_track=HeatmapTrack(
                path=self.session.heatmap_track.path,
                session_idx=self.session.heatmap_track.session_idx,
                group_idx=self.session.heatmap_track.group_idx,
                entry_idx=self.session.heatmap_track.entry_idx,
                subsweep_idx=self.session.heatmap_track.subsweep_idx,
                duration_s=self.session.heatmap_track.duration_s,
                fps=self.session.heatmap_track.fps,
            ),
            viewport_output_width=self.session.viewport.output_width,
            viewport_output_height=self.session.viewport.output_height,
        )

    def _apply_camera_job_result(self, result: CameraResourceJobResult) -> None:
        if self._camera_replacement_backup is not None:
            self._camera_replacement_backup.camera_source.close()
        elif self.camera_source is not None:
            self.camera_source.close()
        self.camera_source = CameraVideoSource(result.proxy_result.display_path)
        self._camera_reference_width = result.proxy_result.source_probe.width
        self._camera_reference_height = result.proxy_result.source_probe.height
        previous_size = (0, 0)
        previous_corners: list[list[float]] | None = None
        if self._camera_replacement_backup is not None:
            previous_size = (
                self._camera_replacement_backup.reference_width,
                self._camera_replacement_backup.reference_height,
            )
            previous_corners = self._camera_replacement_backup.viewport_corners
        self.session.camera_track = result.camera_track
        self.session.timeline.current_time_s = 0.0
        resolved_corners = resolve_replacement_viewport_corners(
            existing_corners=previous_corners,
            previous_native_size=previous_size,
            replacement_native_size=(
                self._camera_reference_width,
                self._camera_reference_height,
            ),
        )
        if resolved_corners is not None:
            self.session.viewport.corners = resolved_corners
        elif replacement_viewport_needs_default_reset(
            previous_corners=previous_corners,
            previous_native_size=previous_size,
            replacement_native_size=(
                self._camera_reference_width,
                self._camera_reference_height,
            ),
        ) or not self.session.viewport.corners:
            self._initialize_default_viewport_corners_native()
        self._initialize_default_export_overlay_if_needed()
        self._load_current_camera_frame(access_hint="random")
        if self._native_viewport_corners() is None:
            self._initialize_default_viewport_corners_native()
        else:
            self._refresh_camera_view_corners()
        self.camera_view.set_export_overlay(self.session.export_overlay)
        self.settings.setValue("last_camera_path", str(result.source_path))
        self._camera_replacement_backup = None
        if result.proxy_result.state == "proxy_built":
            message = f"Loaded camera video with new preview proxy: {result.source_path.name}"
        elif result.proxy_result.state == "proxy_reused":
            message = f"Loaded camera video via cached preview proxy: {result.source_path.name}"
        else:
            message = f"Loaded camera video: {result.source_path.name}"
        self.statusBar().showMessage(message)

    def _apply_h5_job_result(self, payload: LoadedH5ResourcePayload) -> None:
        previous_path = ""
        if self._h5_replacement_backup is not None:
            previous_path = self._h5_replacement_backup.heatmap_track.path
            self._h5_replacement_backup.heatmap_source.close()
        elif self.heatmap_source is not None:
            self.heatmap_source.close()
        self.heatmap_source = build_h5_truth_source_from_payload(payload)
        self.session.heatmap_track = payload.metadata
        self.session.viewport.output_width = payload.first_frame_shape[1]
        self.session.viewport.output_height = payload.first_frame_shape[0]
        self._rebuild_overlay_plot_renderer()
        self.settings.setValue("last_h5_path", str(payload.path))
        if previous_path and previous_path != str(payload.path):
            self._clear_peak_distance_datasource()
        else:
            self._reload_peak_distance_datasource_from_session()
        self._h5_replacement_backup = None
        self.statusBar().showMessage(f"Loaded H5 recording: {payload.path.name}")

    def _restore_camera_replacement_backup(self) -> None:
        backup = self._camera_replacement_backup
        if backup is None:
            return
        if self.camera_source is not None and self.camera_source is not backup.camera_source:
            self.camera_source.close()
        self.camera_source = backup.camera_source
        self._camera_reference_width = backup.reference_width
        self._camera_reference_height = backup.reference_height
        self.session.camera_track = backup.camera_track
        self.session.viewport.corners = [list(point) for point in backup.viewport_corners]
        self.session.export_overlay = ExportOverlaySettings(
            visible=backup.export_overlay.visible,
            preview_enabled=backup.export_overlay.preview_enabled,
            x=backup.export_overlay.x,
            y=backup.export_overlay.y,
            width=backup.export_overlay.width,
            height=backup.export_overlay.height,
        )
        self.current_camera_frame = (
            None if backup.current_camera_frame is None else backup.current_camera_frame.copy()
        )
        if self.current_camera_frame is not None:
            self.camera_view.set_frame(self.current_camera_frame)
        else:
            self._load_current_camera_frame(access_hint="random")
        self._refresh_camera_view_corners()
        self.camera_view.set_export_overlay(self.session.export_overlay)
        self._camera_replacement_backup = None

    def _restore_h5_replacement_backup(self) -> None:
        backup = self._h5_replacement_backup
        if backup is None:
            return
        if self.heatmap_source is not None and self.heatmap_source is not backup.heatmap_source:
            self.heatmap_source.close()
        self.heatmap_source = backup.heatmap_source
        self.session.heatmap_track = backup.heatmap_track
        self.session.viewport.output_width = backup.viewport_output_width
        self.session.viewport.output_height = backup.viewport_output_height
        self._rebuild_overlay_plot_renderer()
        self._h5_replacement_backup = None

    def _handle_resource_job_state_changed(self) -> None:
        for kind in ("camera", "radar_h5"):
            slot = self._resource_job_manager.board().slot(kind)
            result = self._resource_job_manager.take_pending_result(kind, slot.generation)
            if result is not None:
                if kind == "camera":
                    self._apply_camera_job_result(result)
                else:
                    self._apply_h5_job_result(result)
                self._set_resource_reload_error(kind, None)
                self._update_controls_enabled_state()
                self._sync_previews(camera_access_hint="auto")
            elif slot.phase == "failed":
                if kind == "camera":
                    self._restore_camera_replacement_backup()
                else:
                    self._restore_h5_replacement_backup()
                self._set_resource_reload_error(kind, slot.message)
            elif slot.phase == "idle":
                if kind == "camera" and self._camera_replacement_backup is not None:
                    self._restore_camera_replacement_backup()
                elif kind == "radar_h5" and self._h5_replacement_backup is not None:
                    self._restore_h5_replacement_backup()
        self._update_resource_loading_overlays()
        self._refresh_resources_ui()

    def _resource_loading_overlay_message(self, slot: ResourceJobSlotState) -> str:
        if slot.message:
            return slot.message
        target = resource_job_target_filename(slot.target_path)
        if slot.phase == "waiting":
            return f"Waiting for {target}..."
        if slot.phase == "building":
            return f"Building preview proxy for {target}..."
        return f"Loading {target}..."

    _ACTIVE_RESOURCE_JOB_PHASES = ("pending", "loading", "building", "waiting", "cancelling")

    def _resource_job_slot_is_active(self, slot: ResourceJobSlotState) -> bool:
        return slot.phase in self._ACTIVE_RESOURCE_JOB_PHASES

    def _update_resource_loading_overlays(self) -> None:
        camera_slot = self._resource_job_manager.board().camera
        if self._resource_job_slot_is_active(camera_slot):
            self.camera_view.set_loading_overlay(
                True,
                self._resource_loading_overlay_message(camera_slot),
                dim_content=self.camera_source is not None,
            )
        else:
            self.camera_view.set_loading_overlay(False)

        h5_slot = self._resource_job_manager.board().radar_h5
        if self._resource_job_slot_is_active(h5_slot):
            self.truth_view.set_loading_overlay(
                True,
                self._resource_loading_overlay_message(h5_slot),
                dim_content=self.heatmap_source is not None,
            )
        else:
            self.truth_view.set_loading_overlay(False)

        camera_active = self._resource_job_slot_is_active(camera_slot)
        h5_active = self._resource_job_slot_is_active(h5_slot)
        if camera_active or h5_active:
            overlay_slot = camera_slot if camera_active else h5_slot
            self.viewport_view.set_loading_overlay(
                True,
                self._resource_loading_overlay_message(overlay_slot),
                dim_content=(
                    self.viewport_view._pixmap is not None
                    or self.camera_source is not None
                    or self.heatmap_source is not None
                ),
            )
        else:
            self.viewport_view.set_loading_overlay(False)

    def _resource_job_presentations(self) -> tuple[ResourceJobPresentation, ...]:
        presentations: list[ResourceJobPresentation] = []
        for snapshot in self._resource_job_manager.snapshots():
            if snapshot.phase == "idle":
                continue
            presentations.append(
                ResourceJobPresentation(
                    kind=snapshot.kind,
                    phase=snapshot.phase,
                    target_filename=resource_job_target_filename(snapshot.target_path),
                    detail=snapshot.message,
                    cancellable=snapshot.cancellable,
                )
            )
        return tuple(presentations)

    def _populate_controls_from_session(self) -> None:
        self.offset_spin.blockSignals(True)
        self.offset_spin.setValue(self.session.timeline.offset_s)
        self.offset_spin.blockSignals(False)
        self.color_min_spin.blockSignals(True)
        self.color_max_spin.blockSignals(True)
        self.viewport_enhance_checkbox.blockSignals(True)
        self.viewport_map_to_viridis_checkbox.blockSignals(True)
        self.viewport_gamma_spin.blockSignals(True)
        self.blur_spin.blockSignals(True)
        self.downscale_spin.blockSignals(True)
        self.lag_window_spin.blockSignals(True)
        self.sample_count_spin.blockSignals(True)
        self.color_min_spin.setValue(self.session.render.color_min)
        self.color_max_spin.setValue(self.session.render.color_max or 0.0)
        self.viewport_enhance_checkbox.setChecked(self.session.viewport_visibility.enabled)
        self.viewport_map_to_viridis_checkbox.setChecked(
            self.session.viewport_visibility.map_to_viridis
        )
        self.viewport_range_slider.set_values(
            self.session.viewport_visibility.low,
            self.session.viewport_visibility.high,
        )
        self.viewport_gamma_spin.setValue(self.session.viewport_visibility.gamma)
        self._update_viewport_visibility_labels()
        self.blur_spin.setValue(self.session.preprocess.blur_sigma)
        self.downscale_spin.setValue(self.session.preprocess.downscale_factor)
        self.lag_window_spin.setValue(self.session.preprocess.lag_window_s)
        self.sample_count_spin.setValue(self.session.preprocess.sample_count)
        self.color_min_spin.blockSignals(False)
        self.color_max_spin.blockSignals(False)
        self.viewport_enhance_checkbox.blockSignals(False)
        self.viewport_map_to_viridis_checkbox.blockSignals(False)
        self.viewport_gamma_spin.blockSignals(False)
        self.blur_spin.blockSignals(False)
        self.downscale_spin.blockSignals(False)
        self.lag_window_spin.blockSignals(False)
        self.sample_count_spin.blockSignals(False)
        self.show_peak_marker_checkbox.blockSignals(True)
        self.show_peak_marker_checkbox.setChecked(self.session.peak_distance_datasource.visible)
        leg2_kind = self.session.leg2_ultrasonic_datasource.signal_kind
        leg2_kind_index = self.leg2_signal_kind_combo.findData(leg2_kind)
        if leg2_kind_index >= 0:
            self.leg2_signal_kind_combo.setCurrentIndex(leg2_kind_index)
        self.show_leg2_signal_checkbox.setChecked(self.session.leg2_ultrasonic_datasource.visible)
        self._update_leg2_datasource_controls()
        self.show_peak_marker_checkbox.blockSignals(False)
        self._update_peak_datasource_controls()
        self._update_viewport_visibility_controls_enabled()
        self.signal_plot.set_view_settings(self._signal_plot_view_settings_copy())

    def _signal_plot_view_settings_copy(self) -> SignalPlotViewSettings:
        view = self.session.signal_plot_view
        return SignalPlotViewSettings(
            x_range_mode=view.x_range_mode,
            y_range_mode=view.y_range_mode,
            manual_x_range=view.manual_x_range,
            manual_y_range=view.manual_y_range,
        )

    def _signal_plot_view_settings_changed(self) -> None:
        self.session.signal_plot_view = self._signal_plot_view_settings_copy_from_plot()

    def _signal_plot_view_settings_copy_from_plot(self) -> SignalPlotViewSettings:
        view = self.signal_plot.view_settings()
        return SignalPlotViewSettings(
            x_range_mode=view.x_range_mode,
            y_range_mode=view.y_range_mode,
            manual_x_range=view.manual_x_range,
            manual_y_range=view.manual_y_range,
        )

    def _viewport_visibility_changed(self) -> None:
        self.session.viewport_visibility.enabled = self.viewport_enhance_checkbox.isChecked()
        self.session.viewport_visibility.map_to_viridis = (
            self.viewport_map_to_viridis_checkbox.isChecked()
        )
        self.session.viewport_visibility.gamma = self.viewport_gamma_spin.value()
        self._update_viewport_visibility_controls_enabled()
        self._sync_previews(
            camera_access_hint="auto",
            invalidate_source_resolution=False,
        )

    def _viewport_visibility_range_changed(self, low: float, high: float) -> None:
        self.session.viewport_visibility.low = low
        self.session.viewport_visibility.high = high
        self._update_viewport_visibility_labels()
        self._sync_previews(
            camera_access_hint="auto",
            invalidate_source_resolution=False,
        )

    def _update_viewport_visibility_labels(self) -> None:
        self.viewport_low_label.setText(f"Low {self.session.viewport_visibility.low:.2f}")
        self.viewport_high_label.setText(f"High {self.session.viewport_visibility.high:.2f}")

    def _update_viewport_visibility_controls_enabled(self) -> None:
        enabled = (
            self.camera_source is not None
            and self.heatmap_source is not None
            and self.viewport_enhance_checkbox.isChecked()
        )
        has_sources = self.camera_source is not None and self.heatmap_source is not None
        self.viewport_enhance_checkbox.setEnabled(has_sources)
        self.viewport_range_slider.setEnabled(enabled)
        self.viewport_map_to_viridis_checkbox.setEnabled(enabled)
        self.viewport_gamma_spin.setEnabled(enabled)
        self.viewport_low_label.setEnabled(enabled)
        self.viewport_high_label.setEnabled(enabled)

    def _offset_changed(self, value: float) -> None:
        self.session.timeline.offset_s = value
        self._sync_previews(camera_access_hint="auto")

    def _nudge_offset(self, delta_s: float) -> None:
        self.offset_spin.setValue(self.offset_spin.value() + delta_s)

    def _reanchor_playback_clock(self) -> None:
        if self.play_timer.isActive():
            self._playback_started_at_s = time.perf_counter()
            self._playback_started_video_time_s = self.session.timeline.current_time_s

    def _stop_playback(self) -> None:
        self._set_playback_active(False)

    def _slider_to_time(self, slider_value: int) -> None:
        range_start_s, range_end_s = self.timeline_range_model.visible_range_s()
        span_s = range_end_s - range_start_s
        self.session.timeline.current_time_s = (
            range_start_s if span_s <= 0 else range_start_s + span_s * slider_value / 10000.0
        )
        self._reanchor_playback_clock()
        self._sync_previews(camera_access_hint="scrub")

    def _timeline_playhead_changed(self, time_s: float) -> None:
        self.session.timeline.current_time_s = time_s
        self._reanchor_playback_clock()
        self._sync_previews(camera_access_hint="scrub")

    def _timeline_camera_offset_changed(self, offset_s: float) -> None:
        self.offset_spin.setValue(offset_s)

    def _timeline_leg2_offset_changed(self, offset_s: float) -> None:
        self.session.leg2_ultrasonic_datasource.offset_s = offset_s
        self._sync_previews(camera_access_hint="auto")

    def _timeline_h5_alignment_drag_changed(
        self,
        range_start_s: float,
        range_end_s: float,
        current_time_s: float,
        camera_offset_s: float,
        leg2_offset_s: float,
    ) -> None:
        self.session.timeline.current_time_s = current_time_s
        self.session.timeline.offset_s = camera_offset_s
        self.offset_spin.blockSignals(True)
        self.offset_spin.setValue(camera_offset_s)
        self.offset_spin.blockSignals(False)
        self.session.leg2_ultrasonic_datasource.offset_s = leg2_offset_s
        self._sync_timeline_h5_drag_preview(
            range_start_s=range_start_s,
            range_end_s=range_end_s,
        )

    def _timeline_h5_alignment_drag_finished(self) -> None:
        range_start_s, range_end_s = self.timeline_range_model.visible_range_s()
        self._sync_previews(
            camera_access_hint="auto",
            timeline_visible_range_s=(range_start_s, range_end_s),
        )

    def _sync_timeline_h5_drag_preview(
        self,
        *,
        range_start_s: float,
        range_end_s: float,
    ) -> None:
        leg2_duration_s = (
            self.leg2_ultrasonic_datasource.duration_s
            if self.leg2_ultrasonic_datasource is not None
            else 0.0
        )
        self.timeline_range_model.set_track_state(
            camera_duration_s=self.session.camera_track.duration_s,
            heatmap_duration_s=self.session.heatmap_track.duration_s,
            camera_offset_s=self.session.timeline.offset_s,
            leg2_duration_s=leg2_duration_s,
            leg2_offset_s=self.session.leg2_ultrasonic_datasource.offset_s,
        )
        self.timeline_range_model.set_visible_range(range_start_s, range_end_s)
        self._set_slider_from_current_time()
        self._set_timeline_view_state()
        self._refresh_signal_plot()
        self.current_time_label.setText(
            f"t = {self.session.timeline.current_time_s:.3f} s | offset = {self.session.timeline.offset_s:.3f} s"
        )

    def _toggle_playback(self) -> None:
        self._set_playback_active(not self.play_timer.isActive())

    def _advance_playback(self) -> None:
        if self._max_duration_s() <= 0:
            return
        _, range_end_s = self._timeline_bounds_s()

        if self._playback_started_at_s is None:
            self._playback_started_at_s = time.perf_counter()
            self._playback_started_video_time_s = self.session.timeline.current_time_s

        elapsed_s = max(0.0, time.perf_counter() - self._playback_started_at_s)
        next_time = min(self._playback_started_video_time_s + elapsed_s, range_end_s)
        self.session.timeline.current_time_s = next_time
        self._set_slider_from_current_time()
        self._sync_previews(camera_access_hint="playback")
        if math.isclose(next_time, range_end_s) or next_time >= range_end_s:
            self._set_playback_active(False)

    def _render_settings_changed(self) -> None:
        self.session.render.color_min = self.color_min_spin.value()
        self.session.render.color_max = self.color_max_spin.value()
        if self.heatmap_source is not None:
            self.heatmap_source.update_render_settings(
                color_min=self.session.render.color_min,
                color_max=self.session.render.color_max,
                fixed_levels=True,
            )
            self._rebuild_overlay_plot_renderer()
        self._sync_previews(camera_access_hint="auto")

    def _preprocess_settings_changed(self) -> None:
        self.session.preprocess.blur_sigma = self.blur_spin.value()
        self.session.preprocess.downscale_factor = self.downscale_spin.value()
        self.session.preprocess.lag_window_s = self.lag_window_spin.value()
        self.session.preprocess.sample_count = self.sample_count_spin.value()

    def _corners_changed(self, corners: list) -> None:
        native_corners = self._display_corners_to_native(np.asarray(corners, dtype=np.float32))
        self.session.viewport.corners = native_corners.tolist()
        self._sync_previews(camera_access_hint="auto")

    def _set_viewport_corners(self, corners: np.ndarray) -> None:
        self.session.viewport.corners = corners.tolist()
        self._refresh_camera_view_corners()
        self._sync_previews(camera_access_hint="auto")

    def _export_overlay_changed(self, x: float, y: float, width: float, height: float) -> None:
        self.session.export_overlay.x = x
        self.session.export_overlay.y = y
        self.session.export_overlay.width = width
        self.session.export_overlay.height = height

    def _set_export_overlay_visible(self, visible: bool) -> None:
        self.session.export_overlay.visible = visible
        self.camera_view.set_export_overlay(self.session.export_overlay)
        self._sync_previews(camera_access_hint="auto")

    def _set_export_overlay_preview_enabled(self, enabled: bool) -> None:
        self.session.export_overlay.preview_enabled = enabled
        self.camera_view.set_export_overlay(self.session.export_overlay)
        self._sync_previews(camera_access_hint="auto")

    def _set_export_overlay_drag_active(self, active: bool) -> None:
        self._freeze_export_overlay_preview = active
        if not active:
            self._sync_previews(camera_access_hint="auto")

    def _reset_export_overlay(self) -> None:
        self._initialize_default_export_overlay(force=True)
        self.camera_view.set_export_overlay(self.session.export_overlay)
        self._sync_previews(camera_access_hint="auto")

    def _load_current_camera_frame(self, *, access_hint: str = "auto") -> None:
        if self.camera_source is None:
            self.current_camera_frame = None
            self.camera_view.set_frame(None)
            return
        camera_time_s = self.session.timeline.current_time_s + self.session.timeline.offset_s
        if camera_time_s < 0.0 or camera_time_s > self.session.camera_track.duration_s:
            self.current_camera_frame = None
            self.camera_view.set_frame(None)
            return
        _, frame = self.camera_source.frame_at_seconds(
            camera_time_s,
            access_hint=access_hint,
        )
        self.current_camera_frame = frame
        self.camera_view.set_frame(frame)

    def _invalidate_source_resolution_viewport(self) -> None:
        self._source_resolution_request_token += 1
        self._source_resolution_viewport_frame = None
        self._pending_source_resolution_request = None
        self.viewport_source_resolution_timer.stop()

    def _source_resolution_request_payload(
        self,
        *,
        viewport_size: tuple[int, int],
    ) -> dict[str, object] | None:
        native_corners = self._native_viewport_corners()
        if self.camera_source is None or native_corners is None:
            return None
        if self.play_timer.isActive():
            return None
        width, height = viewport_size
        if width <= 0 or height <= 0:
            return None
        camera_time_s = self.session.timeline.current_time_s + self.session.timeline.offset_s
        if camera_time_s < 0.0 or camera_time_s > self.session.camera_track.duration_s:
            return None
        return {
            "token": self._source_resolution_request_token,
            "camera_path": self.session.camera_track.path,
            "camera_time_s": camera_time_s,
            "corners": native_corners.tolist(),
            "output_size": viewport_size,
        }

    def _schedule_source_resolution_viewport_refresh(
        self,
        *,
        viewport_size: tuple[int, int],
    ) -> None:
        request = self._source_resolution_request_payload(viewport_size=viewport_size)
        if request is None:
            self.viewport_source_resolution_timer.stop()
            self._pending_source_resolution_request = None
            return
        self._pending_source_resolution_request = request
        if not self.play_timer.isActive():
            self.viewport_source_resolution_timer.start()

    def _start_debounced_source_resolution_viewport(self) -> None:
        request = self._pending_source_resolution_request
        if request is None:
            return
        if self._source_resolution_worker_busy:
            return
        self._pending_source_resolution_request = None
        self._source_resolution_worker_busy = True
        self.source_resolution_viewport_render_requested.emit(request)

    def _handle_source_resolution_viewport_result(self, result: object) -> None:
        self._source_resolution_worker_busy = False
        payload = dict(result) if isinstance(result, dict) else {}
        if payload.get("token") == self._source_resolution_request_token:
            frame = payload.get("frame")
            self._source_resolution_viewport_frame = (
                frame.copy() if isinstance(frame, np.ndarray) else None
            )
            if self._source_resolution_viewport_frame is not None:
                self._sync_previews(
                    camera_access_hint="auto",
                    invalidate_source_resolution=False,
                )

        if self._pending_source_resolution_request is not None and not self.play_timer.isActive():
            self._start_debounced_source_resolution_viewport()

    def _set_playback_active(self, active: bool, *, refresh_viewport: bool = True) -> None:
        if active:
            self._playback_started_at_s = time.perf_counter()
            self._playback_started_video_time_s = self.session.timeline.current_time_s
            self.play_timer.start(self.play_timer_interval_ms)
            self.play_button.setText("Pause")
            if refresh_viewport:
                self._sync_previews(camera_access_hint="playback")
            return

        was_active = self.play_timer.isActive()
        self.play_timer.stop()
        self._playback_started_at_s = None
        self.play_button.setText("Play")
        if refresh_viewport and was_active:
            self._sync_previews(camera_access_hint="auto")

    def _set_slider_from_current_time(self) -> None:
        range_start_s, range_end_s = self.timeline_range_model.visible_range_s()
        span_s = range_end_s - range_start_s
        self.current_time_slider.blockSignals(True)
        value = (
            0
            if span_s <= 0
            else int(
                round(10000 * (self.session.timeline.current_time_s - range_start_s) / span_s)
            )
        )
        self.current_time_slider.setValue(int(np.clip(value, 0, 10000)))
        self.current_time_slider.blockSignals(False)

    def _update_timeline_range_from_session(self) -> None:
        leg2_duration_s = (
            self.leg2_ultrasonic_datasource.duration_s
            if self.leg2_ultrasonic_datasource is not None
            else 0.0
        )
        self.timeline_range_model.set_track_state(
            camera_duration_s=self.session.camera_track.duration_s,
            heatmap_duration_s=self.session.heatmap_track.duration_s,
            camera_offset_s=self.session.timeline.offset_s,
            leg2_duration_s=leg2_duration_s,
            leg2_offset_s=self.session.leg2_ultrasonic_datasource.offset_s,
        )
        self.timeline_range_model.recompute_visible_range()

    def _set_timeline_view_state(self) -> None:
        self.timeline_view.set_timeline_state(
            current_time_s=self.session.timeline.current_time_s,
        )

    def _timeline_bounds_s(self) -> tuple[float, float]:
        leg2_duration_s = (
            self.leg2_ultrasonic_datasource.duration_s
            if self.leg2_ultrasonic_datasource is not None
            else 0.0
        )
        return timeline_view_bounds_s(
            heatmap_duration_s=self.session.heatmap_track.duration_s,
            camera_duration_s=self.session.camera_track.duration_s,
            camera_offset_s=self.session.timeline.offset_s,
            leg2_duration_s=leg2_duration_s,
            leg2_offset_s=self.session.leg2_ultrasonic_datasource.offset_s,
            fit_padding_fraction=0.0,
        )

    def _initialize_default_export_overlay_if_needed(self) -> None:
        if (
            self.camera_source is None
            or self.session.export_overlay.width > 0.0
            and self.session.export_overlay.height > 0.0
        ):
            return
        self._initialize_default_export_overlay(force=True)

    def _initialize_default_export_overlay(self, *, force: bool = False) -> None:
        if self.camera_source is None:
            return
        if (
            not force
            and self.session.export_overlay.width > 0.0
            and self.session.export_overlay.height > 0.0
        ):
            return
        preview_width = self.camera_source.preview_width
        preview_height = self.camera_source.preview_height
        margin_x = preview_width * 0.03
        margin_y = preview_height * 0.03
        width = preview_width * 0.15
        height = preview_height * 0.15
        self.session.export_overlay.x = margin_x
        self.session.export_overlay.y = preview_height - margin_y - height
        self.session.export_overlay.width = width
        self.session.export_overlay.height = height

    def _camera_native_size(self) -> tuple[int, int]:
        return self._camera_reference_width, self._camera_reference_height

    def _camera_display_size(self) -> tuple[int, int]:
        if self.current_camera_frame is not None:
            return self.current_camera_frame.shape[1], self.current_camera_frame.shape[0]
        if self.camera_source is not None:
            return self.camera_source.preview_width, self.camera_source.preview_height
        return 0, 0

    def _native_viewport_corners(self) -> np.ndarray | None:
        if not self.session.viewport.corners:
            return None
        corners = np.asarray(self.session.viewport.corners, dtype=np.float32)
        if corners.shape != (4, 2):
            return None
        return corners

    def _display_corners_to_native(self, display_corners: np.ndarray) -> np.ndarray:
        native_width, native_height = self._camera_native_size()
        display_width, display_height = self._camera_display_size()
        if native_width <= 0 or native_height <= 0:
            return display_corners.astype(np.float32, copy=True)
        if display_width <= 0 or display_height <= 0:
            return display_corners.astype(np.float32, copy=True)
        return scale_viewport_corners(
            display_corners,
            from_size=(display_width, display_height),
            to_size=(native_width, native_height),
        )

    def _display_viewport_corners(self) -> np.ndarray | None:
        native_corners = self._native_viewport_corners()
        native_width, native_height = self._camera_native_size()
        display_width, display_height = self._camera_display_size()
        if native_corners is None:
            return None
        if native_width <= 0 or native_height <= 0:
            return native_corners
        if display_width <= 0 or display_height <= 0:
            return native_corners
        return scale_viewport_corners(
            native_corners,
            from_size=(native_width, native_height),
            to_size=(display_width, display_height),
        )

    def _refresh_camera_view_corners(self) -> None:
        display_corners = self._display_viewport_corners()
        self.camera_view.set_corners(None if display_corners is None else display_corners.tolist())

    def _initialize_default_viewport_corners_native(self) -> None:
        native_width, native_height = self._camera_native_size()
        if native_width <= 0 or native_height <= 0:
            return
        inset_x = native_width * 0.15
        inset_y = native_height * 0.15
        corners = np.array(
            [
                [inset_x, inset_y],
                [native_width - inset_x, inset_y],
                [native_width - inset_x, native_height - inset_y],
                [inset_x, native_height - inset_y],
            ],
            dtype=np.float32,
        )
        self.session.viewport.corners = corners.tolist()
        self._refresh_camera_view_corners()

    def _rebuild_overlay_plot_renderer(self) -> None:
        if self.heatmap_source is None:
            self._overlay_plot_renderer = None
            return
        self._overlay_plot_renderer = HeatmapPlotRenderer(
            self.heatmap_source, output_size=(160, 120)
        )

    def _overlay_presentation_source_size(self) -> tuple[int, int] | None:
        source_rect = self._scaled_export_overlay_rect(original=True)
        source_width = int(round(source_rect.width()))
        source_height = int(round(source_rect.height()))
        if source_width <= 0 or source_height <= 0:
            return None
        return source_width, source_height

    def _scaled_export_overlay_rect(self, *, original: bool) -> QtCore.QRectF:
        overlay = self.session.export_overlay
        if self.camera_source is None:
            return QtCore.QRectF()
        if original:
            scale_x = self._camera_reference_width / max(self.camera_source.preview_width, 1)
            scale_y = self._camera_reference_height / max(self.camera_source.preview_height, 1)
        else:
            scale_x = 1.0
            scale_y = 1.0
        return QtCore.QRectF(
            overlay.x * scale_x,
            overlay.y * scale_y,
            overlay.width * scale_x,
            overlay.height * scale_y,
        )

    def _max_duration_s(self) -> float:
        return max(
            self.session.camera_track.duration_s,
            self.session.heatmap_track.duration_s,
        )

    def _viewport_output_size(self, truth_frame: np.ndarray | None) -> tuple[int, int]:
        rect = self.viewport_view.contentsRect()
        if rect.width() > 1 and rect.height() > 1:
            return rect.width(), rect.height()
        if truth_frame is not None:
            return truth_frame.shape[1], truth_frame.shape[0]
        if self.session.viewport.output_width > 1 and self.session.viewport.output_height > 1:
            return self.session.viewport.output_width, self.session.viewport.output_height
        return 320, 200

    def _camera_point_from_viewport_point(
        self,
        viewport_x: float,
        viewport_y: float,
        viewport_size: tuple[int, int],
    ) -> np.ndarray | None:
        native_corners = self._native_viewport_corners()
        native_width, native_height = self._camera_native_size()
        if native_corners is None:
            return None
        width, height = viewport_size
        if native_width <= 0 or native_height <= 0 or width <= 0 or height <= 0:
            return None
        dst = np.array(
            [[0.0, 0.0], [width - 1.0, 0.0], [width - 1.0, height - 1.0], [0.0, height - 1.0]],
            dtype=np.float32,
        )
        transform = cv2.getPerspectiveTransform(native_corners, dst)
        inverse = np.linalg.inv(transform)
        point = np.array([viewport_x, viewport_y, 1.0], dtype=np.float64)
        mapped = inverse @ point
        if abs(mapped[2]) < 1e-9:
            return None
        mapped /= mapped[2]
        return np.array(
            [
                float(np.clip(mapped[0], 0, native_width - 1)),
                float(np.clip(mapped[1], 0, native_height - 1)),
            ],
            dtype=np.float32,
        )

    def _translate_camera_corners(
        self,
        indices: list[int],
        dx: float,
        dy: float,
        *,
        base_corners: np.ndarray | None = None,
    ) -> None:
        native_width, native_height = self._camera_native_size()
        if native_width <= 0 or native_height <= 0 or not self.session.viewport.corners:
            return
        corners = (
            np.asarray(base_corners, dtype=np.float32).copy()
            if base_corners is not None
            else np.asarray(self.session.viewport.corners, dtype=np.float32)
        )
        trial = corners.copy()
        trial[indices, 0] += dx
        trial[indices, 1] += dy

        subset = trial[indices]
        adjust_dx = 0.0
        adjust_dy = 0.0
        min_x = float(np.min(subset[:, 0]))
        max_x = float(np.max(subset[:, 0]))
        min_y = float(np.min(subset[:, 1]))
        max_y = float(np.max(subset[:, 1]))
        if min_x < 0.0:
            adjust_dx = -min_x
        elif max_x > native_width - 1:
            adjust_dx = (native_width - 1) - max_x
        if min_y < 0.0:
            adjust_dy = -min_y
        elif max_y > native_height - 1:
            adjust_dy = (native_height - 1) - max_y

        corners[indices, 0] = np.clip(corners[indices, 0] + dx + adjust_dx, 0, native_width - 1)
        corners[indices, 1] = np.clip(corners[indices, 1] + dy + adjust_dy, 0, native_height - 1)
        self._set_viewport_corners(corners)

    def _viewport_corner_dragged(
        self,
        index: int,
        start_x: float,
        start_y: float,
        current_x: float,
        current_y: float,
    ) -> None:
        viewport_size = self._viewport_output_size(None)
        if not self.session.viewport.corners:
            return
        if self._viewport_drag_start_corners is None:
            self._viewport_drag_start_corners = np.asarray(
                self.session.viewport.corners, dtype=np.float32
            )
        start_point = self._camera_point_from_viewport_point(start_x, start_y, viewport_size)
        current_point = self._camera_point_from_viewport_point(current_x, current_y, viewport_size)
        if start_point is None or current_point is None:
            return
        delta = start_point - current_point
        corners = self._viewport_drag_start_corners.copy()
        corners[index] = self._viewport_drag_start_corners[index] + delta
        native_width, native_height = self._camera_native_size()
        if native_width > 0 and native_height > 0:
            corners[index, 0] = np.clip(corners[index, 0], 0, native_width - 1)
            corners[index, 1] = np.clip(corners[index, 1], 0, native_height - 1)
        self._set_viewport_corners(corners)

    def _viewport_edge_dragged(
        self,
        edge_index: int,
        prev_x: float,
        prev_y: float,
        current_x: float,
        current_y: float,
    ) -> None:
        viewport_size = self._viewport_output_size(None)
        if not self.session.viewport.corners:
            return
        if self._viewport_drag_start_corners is None:
            self._viewport_drag_start_corners = np.asarray(
                self.session.viewport.corners, dtype=np.float32
            )
        prev_point = self._camera_point_from_viewport_point(prev_x, prev_y, viewport_size)
        current_point = self._camera_point_from_viewport_point(current_x, current_y, viewport_size)
        if prev_point is None or current_point is None:
            return
        delta = prev_point - current_point
        self._translate_camera_corners(
            [edge_index, (edge_index + 1) % 4],
            float(delta[0]),
            float(delta[1]),
            base_corners=self._viewport_drag_start_corners,
        )

    def _viewport_center_dragged(
        self,
        prev_x: float,
        prev_y: float,
        current_x: float,
        current_y: float,
    ) -> None:
        viewport_size = self._viewport_output_size(None)
        if not self.session.viewport.corners:
            return
        if self._viewport_drag_start_corners is None:
            self._viewport_drag_start_corners = np.asarray(
                self.session.viewport.corners, dtype=np.float32
            )
        prev_point = self._camera_point_from_viewport_point(prev_x, prev_y, viewport_size)
        current_point = self._camera_point_from_viewport_point(current_x, current_y, viewport_size)
        if prev_point is None or current_point is None:
            return
        delta = prev_point - current_point
        self._translate_camera_corners(
            [0, 1, 2, 3],
            float(delta[0]),
            float(delta[1]),
            base_corners=self._viewport_drag_start_corners,
        )

    def _sync_previews(
        self,
        *,
        camera_access_hint: str = "auto",
        invalidate_source_resolution: bool = True,
        timeline_visible_range_s: tuple[float, float] | None = None,
    ) -> None:
        if invalidate_source_resolution:
            self._invalidate_source_resolution_viewport()
        self._load_current_camera_frame(access_hint=camera_access_hint)
        self._refresh_camera_view_corners()
        self._update_timeline_range_from_session()
        if timeline_visible_range_s is not None:
            self.timeline_range_model.set_visible_range(*timeline_visible_range_s)
        self._set_slider_from_current_time()
        self._set_timeline_view_state()
        self._refresh_signal_plot()
        self.schedule_timeline_axis_geometry_sync()
        self.current_time_label.setText(
            f"t = {self.session.timeline.current_time_s:.3f} s | offset = {self.session.timeline.offset_s:.3f} s"
        )

        truth_frame = None
        if self.heatmap_source is not None and (
            0.0
            <= self.session.timeline.current_time_s
            <= self.session.heatmap_track.duration_s
        ):
            frame_idx, truth_frame = self.heatmap_source.frame_at_seconds(
                self.session.timeline.current_time_s
            )
            truth_frame = self._annotate_truth_frame_with_peak(truth_frame, frame_idx)
        self.truth_view.set_frame(truth_frame)
        if (
            not self.session.export_overlay.visible
            or not self.session.export_overlay.preview_enabled
        ):
            self.camera_view.set_export_overlay_preview_frame(None)
        elif (
            not self._freeze_export_overlay_preview
            and self._overlay_plot_renderer is not None
            and truth_frame is not None
            and self.session.export_overlay.width > 0.0
            and self.session.export_overlay.height > 0.0
        ):
            frame_idx, _ = self.heatmap_source.frame_at_seconds(
                self.session.timeline.current_time_s
            )
            presentation_source_size = self._overlay_presentation_source_size()
            peak_overlay = self._peak_overlay_for_frame(frame_idx)
            preview_frame = self._overlay_plot_renderer.render_frame(
                frame_idx,
                output_size=(
                    int(round(self.session.export_overlay.width)),
                    int(round(self.session.export_overlay.height)),
                ),
                source_size=presentation_source_size,
                peak_distance_m=None if peak_overlay is None else peak_overlay[0],
                zero_velocity_m_s=None if peak_overlay is None else peak_overlay[1],
            )
            self.camera_view.set_export_overlay_preview_frame(preview_frame)
        elif not self._freeze_export_overlay_preview:
            self.camera_view.set_export_overlay_preview_frame(None)

        viewport_frame = None
        low_resolution_viewport_frame = None
        if (
            self.current_camera_frame is not None
            and truth_frame is not None
            and self.session.viewport.corners
        ):
            viewport_size = self._viewport_output_size(truth_frame)
            display_corners = self._display_viewport_corners()
            try:
                if display_corners is not None:
                    low_resolution_viewport_frame = rectify_viewport(
                        self.current_camera_frame,
                        display_corners,
                        viewport_size,
                    )
            except ValueError:
                low_resolution_viewport_frame = None
            selected_viewport_frame = (
                self._source_resolution_viewport_frame
                if self._source_resolution_viewport_frame is not None
                else low_resolution_viewport_frame
            )
            try:
                if selected_viewport_frame is not None:
                    viewport_frame = apply_viewport_visibility(
                        selected_viewport_frame,
                        self.session.viewport_visibility,
                    )
            except ValueError:
                viewport_frame = None
            if invalidate_source_resolution:
                self._schedule_source_resolution_viewport_refresh(viewport_size=viewport_size)
        self.viewport_view.set_frame(viewport_frame)

    def _leg2_legend_name(self) -> str:
        if self.session.leg2_ultrasonic_datasource.signal_kind == "filtered":
            return "Leg2 filtered ultrasonic"
        return "Leg2 raw ultrasonic"

    def _refresh_signal_plot(self) -> None:
        peak_series = None
        if self.peak_distance_datasource is not None:
            peak_series = build_peak_distance_signal_series(
                self.peak_distance_datasource.measurements
            )
        peak_visible = (
            self.peak_distance_datasource is not None
            and self.session.peak_distance_datasource.visible
        )
        leg2_series = None
        if self.leg2_ultrasonic_datasource is not None:
            leg2_series = build_leg2_ultrasonic_signal_series(
                self.leg2_ultrasonic_datasource,
                signal_kind=self.session.leg2_ultrasonic_datasource.signal_kind,
                offset_s=self.session.leg2_ultrasonic_datasource.offset_s,
            )
        leg2_visible = (
            self.leg2_ultrasonic_datasource is not None
            and self.session.leg2_ultrasonic_datasource.visible
        )
        self.signal_plot.set_plotted_signals(
            peak_series=peak_series,
            peak_visible=peak_visible,
            leg2_series=leg2_series,
            leg2_visible=leg2_visible,
            leg2_legend_name=self._leg2_legend_name(),
        )
        self.signal_plot.set_current_time_s(self.session.timeline.current_time_s)

    def _update_controls_enabled_state(self) -> None:
        camera_job_busy = self._resource_job_manager.board().camera.phase not in (
            "idle",
            "failed",
        )
        has_camera = self.camera_source is not None and not camera_job_busy
        h5_job_busy = self._resource_job_manager.board().radar_h5.phase not in (
            "idle",
            "failed",
        )
        has_heatmap = self.heatmap_source is not None and not h5_job_busy
        has_optional_signal = (
            self.peak_distance_datasource is not None
            or self.leg2_ultrasonic_datasource is not None
        )
        enabled = has_camera or has_heatmap or has_optional_signal
        self.play_button.setEnabled(enabled)
        self.timeline_view.setEnabled(enabled)
        self.current_time_slider.setEnabled(enabled)
        self.offset_spin.setEnabled(has_camera)
        self.nudge_left_small.setEnabled(has_camera)
        self.nudge_right_small.setEnabled(has_camera)
        self.nudge_left_large.setEnabled(has_camera)
        self.nudge_right_large.setEnabled(has_camera)
        self._update_peak_datasource_controls()
        self._update_leg2_datasource_controls()
        self._update_viewport_visibility_controls_enabled()
        self._refresh_resources_ui()

    def _viewport_preview_resized(self) -> None:
        if (
            self.current_camera_frame is None
            or self.heatmap_source is None
            or not self.session.viewport.corners
        ):
            return
        self._sync_previews(camera_access_hint="auto")

    def _viewport_drag_finished(self) -> None:
        self._viewport_drag_start_corners = None

    def _resource_runtime(self) -> AlignmentResourceRuntime:
        peak_detected: int | None = None
        peak_total: int | None = None
        if self.peak_distance_datasource is not None:
            peak_total = len(self.peak_distance_datasource.measurements)
            peak_detected = sum(
                1
                for row in self.peak_distance_datasource.measurements
                if row.status == STATUS_DETECTED
            )
        leg2_valid: int | None = None
        leg2_samples: int | None = None
        if self.leg2_ultrasonic_datasource is not None:
            leg2_samples = int(self.leg2_ultrasonic_datasource.time_s.size)
            leg2_valid = int(np.count_nonzero(self.leg2_ultrasonic_datasource.reliable_flag_mask))

        return AlignmentResourceRuntime(
            camera_loaded=self.camera_source is not None,
            radar_h5_loaded=self.heatmap_source is not None,
            radar_peak_loaded=self.peak_distance_datasource is not None,
            leg2_loaded=self.leg2_ultrasonic_datasource is not None,
            peak_detected_count=peak_detected,
            peak_measurement_count=peak_total,
            leg2_valid_segment_count=leg2_valid,
            leg2_sample_count=leg2_samples,
            reload_errors=tuple(self._resource_reload_errors.items()),
            load_warnings=tuple(self._resource_load_warnings.items()),
            resource_jobs=self._resource_job_presentations(),
        )

    def resource_summaries(self) -> tuple[ResourceSummary, ...]:
        return build_alignment_resource_summaries(self.session, self._resource_runtime())

    def _refresh_session_title(self) -> None:
        if self._current_session_path is None:
            self.setWindowTitle("Heatmap Alignment Workbench — Untitled Session")
            return
        self.setWindowTitle(
            f"Heatmap Alignment Workbench — {self._current_session_path.name}"
        )

    def _refresh_resources_ui(self) -> None:
        summaries = self.resource_summaries()
        if self._resources_window is not None:
            self._resources_window.refresh(summaries, self._current_session_path)

        has_camera_path = bool(self.session.camera_track.path)
        has_h5_path = bool(self.session.heatmap_track.path)
        has_peak_path = bool(self.session.peak_distance_datasource.path)
        has_leg2_path = bool(self.session.leg2_ultrasonic_datasource.path)

        self.unload_camera_action.setEnabled(self.camera_source is not None)
        self.unload_h5_action.setEnabled(self.heatmap_source is not None)
        self.unload_peak_action.setEnabled(
            self.peak_distance_datasource is not None or has_peak_path
        )
        self.unload_leg2_action.setEnabled(
            self.leg2_ultrasonic_datasource is not None or has_leg2_path
        )
        self.reload_camera_action.setEnabled(has_camera_path)
        self.reload_h5_action.setEnabled(has_h5_path)
        self.reload_peak_action.setEnabled(has_peak_path)
        self.reload_leg2_action.setEnabled(has_leg2_path)

        self.save_session_action.setEnabled(
            self.camera_source is not None and self.heatmap_source is not None
        )
        self.export_synced_action.setEnabled(
            self.camera_source is not None
            and self.heatmap_source is not None
            and not self._export_in_progress
            and not self._resource_job_manager.blocks_export()
        )

    def _show_resources_window(self) -> None:
        if self._resources_window is None:
            self._resources_window = ResourcesWindow(self)
            self._refresh_resources_ui()
            self._resources_window.show()
            return

        saved_geometry = self._resources_window.geometry()
        self._refresh_resources_ui()
        self._resources_window.setGeometry(saved_geometry)
        self._resources_window.show()
        self._resources_window.raise_()

    def _set_resource_reload_error(self, kind: ResourceKind, message: str | None) -> None:
        if message:
            self._resource_reload_errors[kind] = message
        else:
            self._resource_reload_errors.pop(kind, None)

    def _set_resource_warnings(
        self,
        kind: ResourceKind,
        warnings: tuple[str, ...] | list[str],
    ) -> None:
        if warnings:
            self._resource_load_warnings[kind] = tuple(warnings)
        else:
            self._resource_load_warnings.pop(kind, None)

    def invoke_resource_action(self, kind: ResourceKind, action: ResourceAction) -> None:
        if action == "cancel":
            if kind in ("camera", "radar_h5"):
                if self._resource_job_manager.cancel_job(kind):
                    self._handle_resource_job_state_changed()
            return
        if action == "load":
            if kind == "camera":
                self._load_camera_video()
            elif kind == "radar_h5":
                self._load_h5_recording()
            elif kind == "radar_peak":
                self._import_peak_distance_json()
            elif kind == "leg2_mat":
                self._import_leg2_mat()
            return
        if action == "replace":
            self.invoke_resource_action(kind, "load")
            return
        if action == "unload":
            if kind == "camera":
                self.unload_camera_video()
            elif kind == "radar_h5":
                self.unload_h5_recording()
            elif kind == "radar_peak":
                self._clear_peak_distance_datasource()
            elif kind == "leg2_mat":
                self._clear_leg2_ultrasonic_datasource()
            return
        if action == "reload":
            self._reload_resource(kind)
            return
        if action == "reveal":
            self._reveal_resource_path(kind)
            return
        if action == "inspect":
            self._inspect_resource_messages(kind)

    def _resource_path_for_kind(self, kind: ResourceKind) -> str:
        if kind == "camera":
            return self.session.camera_track.path
        if kind == "radar_h5":
            return self.session.heatmap_track.path
        if kind == "radar_peak":
            return self.session.peak_distance_datasource.path
        return self.session.leg2_ultrasonic_datasource.path

    def _reload_resource(self, kind: ResourceKind) -> None:
        path_text = self._resource_path_for_kind(kind)
        if not path_text:
            return
        path = Path(path_text)
        if not path.exists():
            self._set_resource_reload_error(kind, f"File not found: {path}")
            self._refresh_resources_ui()
            return
        self._set_resource_reload_error(kind, None)
        if kind == "camera":
            self.load_camera_from_path(path)
        elif kind == "radar_h5":
            self.load_h5_from_path(path)
        elif kind == "radar_peak":
            self.load_peak_distance_from_path(path, show_dialogs=True, require_heatmap=False)
        elif kind == "leg2_mat":
            self.load_leg2_mat_from_path(path, show_dialogs=True)

    def _reveal_resource_path(self, kind: ResourceKind) -> None:
        path_text = self._resource_path_for_kind(kind)
        if not path_text:
            return
        path = Path(path_text)
        target = path if path.is_dir() else path.parent
        if not target.exists():
            QtWidgets.QMessageBox.warning(
                self,
                "Show in File Manager",
                f"Path does not exist:\n{path}",
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.resolve())))

    def _inspect_resource_messages(self, kind: ResourceKind) -> None:
        summary = next(
            (entry for entry in self.resource_summaries() if entry.kind == kind),
            None,
        )
        if summary is None or not summary.messages:
            return
        QtWidgets.QMessageBox.warning(
            self,
            f"{summary.display_name} details",
            "\n".join(summary.messages),
        )

    def unload_camera_video(self) -> None:
        self._resource_job_manager.cancel_job("camera")
        clear_resource_job(self._resource_job_manager.board(), "camera")
        self._camera_replacement_backup = None
        self.camera_view.set_loading_overlay(False)
        if self.camera_source is not None:
            self.camera_source.close()
            self.camera_source = None
        self._camera_reference_width = 0
        self._camera_reference_height = 0
        self.current_camera_frame = None
        self.session.camera_track = CameraTrack()
        self.session.export_overlay = ExportOverlaySettings()
        self.session.timeline.offset_s = 0.0
        self.camera_view.set_frame(None)
        self.camera_view.set_corners(None)
        self.camera_view.set_export_overlay(self.session.export_overlay)
        self.camera_view.set_export_overlay_preview_frame(None)
        self._set_resource_reload_error("camera", None)
        self._set_resource_warnings("camera", ())
        self._update_controls_enabled_state()
        self._sync_previews(camera_access_hint="auto")
        self._refresh_resources_ui()
        self.statusBar().showMessage("Unloaded camera video.")

    def unload_h5_recording(self) -> None:
        self._resource_job_manager.cancel_job("radar_h5")
        clear_resource_job(self._resource_job_manager.board(), "radar_h5")
        self._h5_replacement_backup = None
        self.truth_view.set_loading_overlay(False)
        if self.heatmap_source is not None:
            self.heatmap_source.close()
            self.heatmap_source = None
        self._overlay_plot_renderer = None
        self.session.heatmap_track = HeatmapTrack()
        self.truth_view.set_frame(None)
        self._set_resource_reload_error("radar_h5", None)
        self._set_resource_warnings("radar_h5", ())
        self._update_controls_enabled_state()
        self._sync_previews(camera_access_hint="auto")
        self._refresh_resources_ui()
        self.statusBar().showMessage("Unloaded radar raw H5 recording.")

    def clear_all_resources(self) -> None:
        reply = QtWidgets.QMessageBox.question(
            self,
            "Clear All Resources",
            (
                "Unload Camera Video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT "
                "from this workbench?\n\nThe current session path will be kept."
            ),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.unload_camera_video()
        self.unload_h5_recording()
        self._clear_peak_distance_datasource()
        self._clear_leg2_ultrasonic_datasource()
        self.statusBar().showMessage("Cleared all loaded resources.")

    def _close_session(self) -> None:
        reply = QtWidgets.QMessageBox.question(
            self,
            "Close Session",
            "Close the current session and return to an untitled empty workbench?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self._close_sources()
        self.session = AlignmentSession()
        self._current_session_path = None
        self._resource_reload_errors.clear()
        self._resource_load_warnings.clear()
        self._populate_controls_from_session()
        self._update_controls_enabled_state()
        self._sync_previews(camera_access_hint="auto")
        self._refresh_session_title()
        self._refresh_resources_ui()
        self.statusBar().showMessage("Closed session.")

    def _dialog_start_path(self, key: str) -> str:
        value = self.settings.value(key, "", type=str)
        if value:
            return str(Path(value).parent if Path(value).suffix else Path(value))
        return ""

    def _export_synced_video(self) -> None:
        if self.camera_source is None or self.heatmap_source is None or self._export_in_progress:
            return
        self._initialize_default_export_overlay_if_needed()
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export synced video",
            self._dialog_start_path("last_camera_path"),
            "MP4 files (*.mp4);;All files (*)",
        )
        if not filename:
            return

        self._export_in_progress = True
        self._update_controls_enabled_state()
        self.statusBar().showMessage("Exporting synced video...")
        progress = QtWidgets.QProgressDialog("Exporting synced video...", "Cancel", 0, 100, self)
        progress.setWindowTitle("Exporting")
        progress.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(True)
        progress.setAutoReset(False)
        progress.setValue(0)
        QtWidgets.QApplication.processEvents()

        try:
            self._write_synced_video(Path(filename), progress)
            self.statusBar().showMessage(f"Exported synced video: {filename}")
        except RuntimeError as exc:
            message = str(exc)
            if message == "Export cancelled.":
                self.statusBar().showMessage("Export cancelled.")
            else:
                QtWidgets.QMessageBox.warning(self, "Export failed", message)
                self.statusBar().showMessage("Export failed.")
        finally:
            progress.close()
            self._export_in_progress = False
            self._update_controls_enabled_state()

    @staticmethod
    def _first_usable_frame(source: CameraVideoSource) -> np.ndarray:
        last_exc: Exception | None = None
        for frame_idx in range(source.frame_count):
            try:
                return source.frame_at_index(frame_idx, access_hint="random")
            except ValueError as exc:
                last_exc = exc
        raise RuntimeError("Could not read any usable frame from the camera video.") from last_exc

    @staticmethod
    def _last_usable_frame(source: CameraVideoSource) -> np.ndarray:
        last_exc: Exception | None = None
        for frame_idx in range(source.frame_count - 1, -1, -1):
            try:
                return source.frame_at_index(frame_idx, access_hint="random")
            except ValueError as exc:
                last_exc = exc
        raise RuntimeError("Could not read any usable frame from the camera video.") from last_exc

    def _write_synced_video(
        self,
        output_path: Path,
        progress: QtWidgets.QProgressDialog,
    ) -> None:
        assert self.heatmap_source is not None
        output_path.parent.mkdir(parents=True, exist_ok=True)
        export_succeeded = False
        original_camera_source = CameraVideoSource(
            Path(self.session.camera_track.path), max_preview_dimension=None
        )
        try:
            export_rect = self._scaled_export_overlay_rect(original=True)
            export_fps = max(self.session.camera_track.fps, self.session.heatmap_track.fps, 1.0)
            output_frame_count = max(
                1, int(math.ceil(self.session.heatmap_track.duration_s * export_fps))
            )
            writer = cv2.VideoWriter(
                str(output_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                export_fps,
                (original_camera_source.preview_width, original_camera_source.preview_height),
            )
            if not writer.isOpened():
                raise RuntimeError(f"Could not open video writer for {output_path}.")

            plot_renderer = None
            if export_rect.width() > 0.0 and export_rect.height() > 0.0:
                plot_renderer = HeatmapPlotRenderer(
                    self.heatmap_source,
                    output_size=(
                        int(round(export_rect.width())),
                        int(round(export_rect.height())),
                    ),
                )
            first_camera_frame = self._first_usable_frame(original_camera_source)
            last_camera_frame = self._last_usable_frame(original_camera_source)
            try:
                for frame_idx in range(output_frame_count):
                    if progress.wasCanceled():
                        raise RuntimeError("Export cancelled.")
                    h5_time_s = min(frame_idx / export_fps, self.session.heatmap_track.duration_s)
                    camera_time_s = h5_time_s + self.session.timeline.offset_s
                    if camera_time_s < 0.0:
                        camera_frame = first_camera_frame
                    elif camera_time_s > self.session.camera_track.duration_s:
                        camera_frame = last_camera_frame
                    else:
                        _, camera_frame = original_camera_source.frame_at_seconds(
                            camera_time_s,
                            access_hint="playback",
                        )
                    composed = camera_frame.copy()
                    if plot_renderer is not None:
                        heatmap_frame_idx, _ = self.heatmap_source.frame_at_seconds(h5_time_s)
                        presentation_source_size = (
                            int(round(export_rect.width())),
                            int(round(export_rect.height())),
                        )
                        peak_overlay = self._peak_overlay_for_frame(heatmap_frame_idx)
                        overlay_rgb = plot_renderer.render_frame(
                            heatmap_frame_idx,
                            output_size=presentation_source_size,
                            source_size=presentation_source_size,
                            peak_distance_m=None if peak_overlay is None else peak_overlay[0],
                            zero_velocity_m_s=None if peak_overlay is None else peak_overlay[1],
                        )
                        left = int(round(export_rect.x()))
                        top = int(round(export_rect.y()))
                        right = min(composed.shape[1], left + overlay_rgb.shape[1])
                        bottom = min(composed.shape[0], top + overlay_rgb.shape[0])
                        if right > max(0, left) and bottom > max(0, top):
                            source_left = max(0, -left)
                            source_top = max(0, -top)
                            left = max(0, left)
                            top = max(0, top)
                            composed[top:bottom, left:right] = overlay_rgb[
                                source_top : source_top + (bottom - top),
                                source_left : source_left + (right - left),
                            ]
                    writer.write(cv2.cvtColor(composed, cv2.COLOR_RGB2BGR))
                    if (
                        frame_idx % max(1, output_frame_count // 100) == 0
                        or frame_idx == output_frame_count - 1
                    ):
                        progress.setValue(int(round(100 * (frame_idx + 1) / output_frame_count)))
                        QtWidgets.QApplication.processEvents()
            finally:
                writer.release()
            progress.setValue(100)
            export_succeeded = True
        finally:
            original_camera_source.close()
            if not export_succeeded and output_path.exists():
                output_path.unlink(missing_ok=True)
            elif export_succeeded:
                progress.setValue(100)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Launch the Heatmap Alignment Workbench. "
            "MVP limitations: manual alignment only, fixed viewport per video, "
            "no audio playback, no moving-camera viewport tracking, xcorr disabled."
        )
    )
    parser.add_argument(
        "--session",
        type=Path,
        default=None,
        help="Optional saved alignment session JSON to load on startup.",
    )
    parser.add_argument(
        "--camera",
        type=Path,
        default=None,
        help="Optional camera video to load on startup.",
    )
    parser.add_argument(
        "--h5",
        type=Path,
        default=None,
        help="Optional H5 recording to load on startup.",
    )
    parser.add_argument(
        "--peaks",
        type=Path,
        default=None,
        help="Optional canonical peak-distance JSON to load on startup.",
    )
    parser.add_argument(
        "--mat",
        type=Path,
        default=None,
        help="Optional Leg2 MAT ultrasonic log to load on startup.",
    )
    return parser


def main() -> None:
    """Launch the alignment GUI in the current Python environment."""

    args = build_argument_parser().parse_args()

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Heatmap Alignment Workbench")
    window = HeatmapAlignmentWindow()
    if args.session is not None:
        window.load_session_from_path(args.session)
    else:
        if args.camera is not None:
            window.load_camera_from_path(args.camera)
        if args.h5 is not None:
            window.load_h5_from_path(args.h5)

    if args.peaks is not None:
        window.load_peak_distance_from_path(args.peaks)

    if args.mat is not None:
        window.load_leg2_mat_from_path(args.mat)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
