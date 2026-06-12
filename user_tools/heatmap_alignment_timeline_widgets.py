from __future__ import annotations

"""Timeline and signal-plot widgets for the heatmap alignment workbench."""

import math
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

import numpy as np
from heatmap_alignment_core import (
    H5_TIMELINE_TRACK_COLOR_HEX,
    LEG2_TIMELINE_TRACK_COLOR_HEX,
    PLAYHEAD_ALPHA,
    PLAYHEAD_PEN_WIDTH,
    SIGNAL_PLOT_BACKGROUND_HEX,
    SIGNAL_PLOT_NO_DETECTION_ALPHA,
    SIGNAL_PLOT_PRIMARY_SEGMENT_ALPHA,
    TIMELINE_PLAYHEAD_COLOR_HEX,
    Leg2UltrasonicSignalSeries,
    PeakDistanceSignalSeries,
    SignalPlotViewSettings,
    TimelineH5DragSnapshot,
    apply_timeline_h5_alignment_drag,
    derive_signal_plot_color,
    timeline_h5_drag_affects_alignment,
    timeline_view_bounds_s,
    visible_signal_y_range,
    visible_signal_y_range_for_series,
)

from PySide6 import QtCore, QtGui, QtWidgets

import pyqtgraph as pg


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

TIMELINE_LABEL_GUTTER_PX = 72
TIMELINE_TRACK_OFFSET_LABEL_MARGIN_PX = 6.0
TIMELINE_OFFSET_LABEL_COLOR_HEX = "#94a3b8"


# ---------------------------------------------------------------------------
# Protocol used by AlignmentTimelineWidget to avoid importing the main window
# ---------------------------------------------------------------------------

@runtime_checkable
class _TimelineAxisGeometryHost(Protocol):
    def schedule_timeline_axis_geometry_sync(self) -> None: ...


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TimeAxisGeometry:
    left_px: float
    right_px: float


# ---------------------------------------------------------------------------
# TimelineRangeModel
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# SignalPlotWidget
# ---------------------------------------------------------------------------

class SignalPlotWidget(pg.PlotWidget):
    """Signals plot with timeline-following x auto mode and persisted range modes."""

    view_settings_changed = QtCore.Signal()
    axis_geometry_sync_requested = QtCore.Signal()
    playhead_scrubbed = QtCore.Signal(float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self.setBackground(SIGNAL_PLOT_BACKGROUND_HEX)
        self.setLabel("left", "Distance (m)")
        self.setLabel("bottom", "Time (s)")
        self.showGrid(x=True, y=True, alpha=0.2)
        self._view_settings = SignalPlotViewSettings()
        self._timeline_range_model: TimelineRangeModel | None = None
        self._leg2_series: Leg2UltrasonicSignalSeries | None = None
        self._leg2_visible = False
        self._applying_view = False
        self._stance_patch_items: list[QtWidgets.QGraphicsItem] = []
        # Multi-peak series: list of (display_name, detected_curve, candidate_curve)
        self._peak_curve_groups: list[tuple[str, object, object]] = []
        self._peak_series_data: list[tuple[str, PeakDistanceSignalSeries]] = []  # (name, series)
        leg2_plot_color = derive_signal_plot_color(LEG2_TIMELINE_TRACK_COLOR_HEX)
        primary_pen, faded_pen = _make_leg2_signal_plot_pens(leg2_plot_color)
        self._leg2_plot_color = leg2_plot_color
        self._leg2_plot_alpha = SIGNAL_PLOT_PRIMARY_SEGMENT_ALPHA
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
                _plot_color_with_alpha(TIMELINE_PLAYHEAD_COLOR_HEX, PLAYHEAD_ALPHA),
                width=PLAYHEAD_PEN_WIDTH,
            ),
        )
        self._current_time_line.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
        self._current_time_line.setHoverPen(None)
        self.addItem(self._current_time_line)
        self._dragging_playhead = False
        self._hover_on_playhead = False
        self._playhead_hit_half_width_px = 8.0
        self.setMouseTracking(True)
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

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._playhead_hit_test(
            event.position()
        ):
            self._dragging_playhead = True
            self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
            self.playhead_scrubbed.emit(self._time_from_widget_x(event.position().x(), clamp=True))
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._dragging_playhead:
            self.playhead_scrubbed.emit(self._time_from_widget_x(event.position().x(), clamp=True))
            return
        hover = self._playhead_hit_test(event.position())
        if hover != self._hover_on_playhead:
            self._hover_on_playhead = hover
            if hover:
                self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
            else:
                self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._dragging_playhead:
            self._dragging_playhead = False
            self._hover_on_playhead = self._playhead_hit_test(event.position())
            if self._hover_on_playhead:
                self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
            else:
                self.unsetCursor()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        if not self._dragging_playhead:
            self._hover_on_playhead = False
            self.unsetCursor()
        super().leaveEvent(event)

    def _playhead_hit_test(self, widget_pos: QtCore.QPointF) -> bool:
        playhead_widget_x = self._playhead_x_in_widget()
        if playhead_widget_x is None:
            return False
        return abs(widget_pos.x() - playhead_widget_x) <= self._playhead_hit_half_width_px

    def _playhead_x_in_widget(self) -> float | None:
        view_box = self.getPlotItem().getViewBox()
        scene_pt = view_box.mapViewToScene(QtCore.QPointF(self._current_time_line.value(), 0.0))
        widget_pt = self.mapFromScene(scene_pt)
        vb_scene_rect = view_box.mapToScene(view_box.boundingRect()).boundingRect()
        vb_widget_rect = self.mapFromScene(vb_scene_rect).boundingRect()
        center_y = vb_widget_rect.center().y()
        if not vb_widget_rect.contains(widget_pt.x(), center_y):
            return None
        return float(widget_pt.x())

    def _time_from_widget_x(self, widget_x: float, *, clamp: bool) -> float:
        view_box = self.getPlotItem().getViewBox()
        scene_pt = self.mapToScene(QtCore.QPoint(int(widget_x), 0))
        data_pt = view_box.mapSceneToView(scene_pt)
        time_s = float(data_pt.x())
        if clamp:
            x_min, x_max = view_box.viewRange()[0]
            time_s = max(float(x_min), min(float(x_max), time_s))
        return time_s

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
        peak_series_list: list | None = None,
        leg2_series: Leg2UltrasonicSignalSeries | None = None,
        leg2_visible: bool = False,
        leg2_legend_name: str = "",
        # Legacy single-series kwargs kept for test compatibility:
        peak_series: PeakDistanceSignalSeries | None = None,
        peak_visible: bool = False,
    ) -> None:
        # Build a normalised list: [(display_name, color, series), ...]
        # peak_series_list entries are (display_name, color_hex, PeakDistanceSignalSeries).
        if peak_series_list is not None:
            named_series = peak_series_list  # already [(name, color, series)]
        elif peak_series is not None and peak_visible:
            named_series = [("H5 peak", derive_signal_plot_color(H5_TIMELINE_TRACK_COLOR_HEX), peak_series)]
        else:
            named_series = []

        self._peak_series_data = [(name, s) for name, _color, s in named_series]
        self._leg2_series = leg2_series
        self._leg2_visible = leg2_visible and leg2_series is not None

        # Remove stale dynamic peak curves from the plot item.
        plot_item = self.getPlotItem()
        for _name, det_curve, cand_curve in self._peak_curve_groups:
            plot_item.removeItem(det_curve)
            plot_item.removeItem(cand_curve)
        self._peak_curve_groups = []

        # Create fresh curve pairs for each visible series.
        for display_name, color_hex, ps in named_series:
            plot_color = derive_signal_plot_color(color_hex)
            det_pen, cand_pen = _make_h5_signal_plot_pens(plot_color)
            det_curve = self.plot(pen=det_pen, connect="finite", name=f"{display_name} (detected)")
            cand_curve = self.plot(pen=cand_pen, connect="finite", name=f"{display_name} (no detection)")
            det_curve.setData(ps.detected_time_s, ps.detected_distance_m)
            cand_curve.setData(ps.candidate_time_s, ps.candidate_distance_m)
            self._peak_curve_groups.append((display_name, det_curve, cand_curve))

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
        for display_name, det_curve, cand_curve in self._peak_curve_groups:
            legend.addItem(det_curve, f"{display_name} (detected)")
            legend.addItem(cand_curve, f"{display_name} (no detection)")
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
        legend.setVisible(bool(self._peak_curve_groups) or self._leg2_visible)

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
        has_peak = bool(self._peak_series_data)
        if not has_peak and not self._leg2_visible:
            return
        x_range, _ = self.getViewBox().viewRange()
        if has_peak:
            y_range = visible_signal_y_range_for_series(
                tuple(series for _name, series in self._peak_series_data),
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


# ---------------------------------------------------------------------------
# AlignmentTimelineWidget
# ---------------------------------------------------------------------------

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
            playhead_color = QtGui.QColor(TIMELINE_PLAYHEAD_COLOR_HEX)
            playhead_color.setAlpha(PLAYHEAD_ALPHA)
            playhead_pen = QtGui.QPen(playhead_color, PLAYHEAD_PEN_WIDTH)

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
        if isinstance(parent_window, _TimelineAxisGeometryHost):
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
