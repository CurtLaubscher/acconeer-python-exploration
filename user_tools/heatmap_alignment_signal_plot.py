"""Signal plot widget for the heatmap alignment workbench."""

from __future__ import annotations

from typing import Literal

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
    DetectionSignalSeries,
    Leg2UltrasonicSignalSeries,
    SignalPlotViewSettings,
    derive_signal_plot_color,
    visible_signal_y_range,
    visible_signal_y_range_for_series,
)
from heatmap_alignment_timeline_model import TimelineRangeModel

from PySide6 import QtCore, QtGui, QtWidgets

import pyqtgraph as pg


def _plot_color_with_alpha(plot_color_hex: str, alpha: int) -> str:
    normalized = plot_color_hex.strip().lstrip("#")
    if len(normalized) != 6:
        msg = f"Expected #RRGGBB color, got {plot_color_hex!r}."
        raise ValueError(msg)
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
        self._peak_series_data: list[tuple[str, DetectionSignalSeries]] = []  # (name, series)
        leg2_plot_color = derive_signal_plot_color(LEG2_TIMELINE_TRACK_COLOR_HEX)
        primary_pen, faded_pen = _make_leg2_signal_plot_pens(leg2_plot_color)
        self._leg2_plot_color = leg2_plot_color
        self._leg2_plot_alpha = SIGNAL_PLOT_PRIMARY_SEGMENT_ALPHA
        self._leg2_faded_curve = self.plot(
            pen=faded_pen,
            connect="finite",
            name="Leg2 ultrasonic (not valid)",
        )
        self._leg2_faded_curve.curve.setSegmentedLineMode("on")
        self._leg2_primary_curve = self.plot(
            pen=primary_pen,
            connect="finite",
            name="Leg2 ultrasonic (valid)",
        )
        self._leg2_primary_curve.curve.setSegmentedLineMode("on")
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
        view_box.setMouseMode(pg.ViewBox.PanMode)
        view_box.setMouseEnabled(x=True, y=True)
        self._patch_viewbox_disable_left_drag(view_box)
        view_box.sigRangeChanged.connect(self._view_box_range_changed)
        self._configure_signals_menu(view_box)
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
            x_range_mode="auto",
            y_range_mode=settings.y_range_mode,
            manual_x_range=None,
            manual_y_range=settings.manual_y_range,
        )
        self._sync_y_range_mode_menu()
        self._apply_y_settings()

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
        """Apply the shared visible timeline range to the x-axis."""
        if self._timeline_range_model is None:
            return
        range_start_s, range_end_s = self._timeline_range_model.visible_range_s()
        self._applying_view = True
        try:
            self.setXRange(range_start_s, range_end_s, padding=0.0)
            if self._view_settings.y_range_mode == "auto":
                self._apply_y_auto_range()
        finally:
            self._applying_view = False

    def _on_timeline_visible_range_changed(self, _start: float, _end: float) -> None:
        self.sync_x_if_following()

    def set_plotted_signals(
        self,
        *,
        peak_series_list: list | None = None,
        leg2_series: Leg2UltrasonicSignalSeries | None = None,
        leg2_visible: bool = False,
        leg2_legend_name: str = "",
        # Legacy single-series kwargs kept for test compatibility:
        peak_series: DetectionSignalSeries | None = None,
        peak_visible: bool = False,
    ) -> None:
        # Build a normalised list: [(display_name, color, series), ...]
        # peak_series_list entries are (display_name, color_hex, DetectionSignalSeries).
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
            cand_curve = self.plot(
                pen=cand_pen, connect="finite", name=f"{display_name} (no detection)"
            )
            det_curve.curve.setSegmentedLineMode("on")
            cand_curve.curve.setSegmentedLineMode("on")
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
        self.sync_x_if_following()
        self._apply_y_settings()
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

    def _patch_viewbox_disable_left_drag(self, view_box: pg.ViewBox) -> None:
        original_drag = view_box.mouseDragEvent

        def _filtered_drag(ev, axis=None):
            if ev.button() == QtCore.Qt.MouseButton.LeftButton:
                ev.ignore()
                return
            original_drag(ev, axis=axis)

        view_box.mouseDragEvent = _filtered_drag

    def _configure_signals_menu(self, view_box: pg.ViewBox) -> None:
        """Remove obsolete menu items and add Zoom to Fit actions."""
        menu = view_box.menu
        if menu is None:
            return

        # Remove View All, Mouse Mode
        menu.viewAll.setVisible(False)
        for action in menu.mouseModes:
            action.setVisible(False)
        mouse_mode_action = next(
            (a for a in menu.actions() if a.text() == "Mouse Mode"), None
        )
        if mouse_mode_action is not None:
            mouse_mode_action.setVisible(False)

        # X Axis: hide Auto/Manual radios, hide Invert, wire range inputs to model
        x_ctrl = menu.ctrl[0]
        x_ctrl.autoRadio.setVisible(False)
        x_ctrl.manualRadio.setVisible(False)
        x_ctrl.invertCheck.setVisible(False)
        x_ctrl.autoPercentSpin.setVisible(False)
        x_ctrl.autoPanCheck.setVisible(False)
        x_ctrl.visibleOnlyCheck.setVisible(False)

        # Disconnect pyqtgraph's default x range text handler, reconnect to model push
        try:
            x_ctrl.minText.editingFinished.disconnect(menu.xRangeTextChanged)
        except (TypeError, RuntimeError):
            pass
        try:
            x_ctrl.maxText.editingFinished.disconnect(menu.xRangeTextChanged)
        except (TypeError, RuntimeError):
            pass
        x_ctrl.minText.editingFinished.connect(self._x_range_text_committed)
        x_ctrl.maxText.editingFinished.connect(self._x_range_text_committed)

        # Y Axis: keep Auto/Manual but simplify
        y_ctrl = menu.ctrl[1]
        y_ctrl.autoPercentSpin.setVisible(False)
        y_ctrl.autoPanCheck.setVisible(False)
        y_ctrl.visibleOnlyCheck.setVisible(False)
        try:
            y_ctrl.autoRadio.clicked.disconnect(menu.yAutoClicked)
        except (TypeError, RuntimeError):
            pass
        try:
            y_ctrl.manualRadio.clicked.disconnect(menu.yManualClicked)
        except (TypeError, RuntimeError):
            pass
        y_ctrl.autoRadio.clicked.connect(lambda: self._set_y_range_mode("auto"))
        y_ctrl.manualRadio.clicked.connect(lambda: self._set_y_range_mode("manual"))

        # Add "Zoom to Fit" to X Axis submenu
        x_axis_action = next((a for a in menu.actions() if "X" in a.text()), None)
        if x_axis_action is not None and x_axis_action.menu() is not None:
            zoom_fit_x = QtGui.QAction("Zoom to Fit", x_axis_action.menu())
            zoom_fit_x.triggered.connect(self._zoom_to_fit_x)
            x_axis_action.menu().addAction(zoom_fit_x)

        # Add "Zoom to Fit" to Y Axis submenu
        y_axis_action = next((a for a in menu.actions() if "Y" in a.text()), None)
        if y_axis_action is not None and y_axis_action.menu() is not None:
            zoom_fit_y = QtGui.QAction("Zoom to Fit", y_axis_action.menu())
            zoom_fit_y.triggered.connect(self._zoom_to_fit_y)
            y_axis_action.menu().addAction(zoom_fit_y)

        # Hide x-distorting transforms from PlotItem ctrlMenu
        plot_ctrl = self.getPlotItem().ctrl
        for check in (
            plot_ctrl.logXCheck,
            plot_ctrl.derivativeCheck,
            plot_ctrl.phasemapCheck,
            plot_ctrl.fftCheck,
        ):
            check.setVisible(False)
            check.setChecked(False)

        # Patch updateState to keep our simplified x range display in sync
        original_update_state = menu.updateState

        def _update_state() -> None:
            original_update_state()
            self._sync_y_range_mode_menu()

        menu.updateState = _update_state
        self._sync_y_range_mode_menu()

    def _x_range_text_committed(self) -> None:
        if self._timeline_range_model is None:
            return
        menu = self.getPlotItem().getViewBox().menu
        if menu is None:
            return
        x_ctrl = menu.ctrl[0]
        try:
            x_min = float(x_ctrl.minText.text())
            x_max = float(x_ctrl.maxText.text())
        except ValueError:
            return
        if x_min >= x_max:
            return
        self._timeline_range_model.set_visible_range(x_min, x_max)

    def _zoom_to_fit_x(self) -> None:
        if self._timeline_range_model is not None:
            self._timeline_range_model.recompute_visible_range()

    def _zoom_to_fit_y(self) -> None:
        self._applying_view = True
        try:
            self._apply_y_auto_range()
        finally:
            self._applying_view = False

    def _sync_y_range_mode_menu(self) -> None:
        menu = self.getPlotItem().getViewBox().menu
        if menu is None:
            return
        y_ctrl = menu.ctrl[1]
        y_ctrl.autoRadio.setChecked(self._view_settings.y_range_mode == "auto")
        y_ctrl.manualRadio.setChecked(self._view_settings.y_range_mode == "manual")

    def _set_y_range_mode(self, mode: Literal["auto", "manual"]) -> None:
        if self._view_settings.y_range_mode == mode:
            return
        if mode == "manual":
            _, y_range = self.getViewBox().viewRange()
            self._view_settings.manual_y_range = (float(y_range[0]), float(y_range[1]))
        self._view_settings.y_range_mode = mode
        self._sync_y_range_mode_menu()
        self._apply_y_settings()
        self.view_settings_changed.emit()

    def _apply_y_settings(self) -> None:
        self._applying_view = True
        try:
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
            empty_peak = DetectionSignalSeries(
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
        if self._timeline_range_model is not None:
            self._timeline_range_model.set_visible_range(float(x_range[0]), float(x_range[1]))
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
