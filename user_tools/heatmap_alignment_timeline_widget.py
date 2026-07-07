"""Timeline track widget for the heatmap alignment workbench."""

from __future__ import annotations

import math
from typing import Protocol, runtime_checkable

from heatmap_alignment_core import (
    H5_TIMELINE_TRACK_COLOR_HEX,
    LEG2_TIMELINE_TRACK_COLOR_HEX,
    PLAYHEAD_ALPHA,
    PLAYHEAD_PEN_WIDTH,
    TIMELINE_PLAYHEAD_COLOR_HEX,
    TimelineH5DragSnapshot,
    apply_timeline_h5_alignment_drag,
    timeline_h5_drag_affects_alignment,
)
from heatmap_alignment_signal_plot import SignalPlotWidget
from heatmap_alignment_timeline_model import (
    TimelineRangeModel,
    format_track_offset_label,
    track_offset_label_rect,
)

from PySide6 import QtCore, QtGui, QtWidgets


TIMELINE_LABEL_GUTTER_PX = 72
TIMELINE_OFFSET_LABEL_COLOR_HEX = "#94a3b8"


# ---------------------------------------------------------------------------
# Protocol used by AlignmentTimelineWidget to avoid importing the main window
# ---------------------------------------------------------------------------

@runtime_checkable
class _TimelineAxisGeometryHost(Protocol):
    def schedule_timeline_axis_geometry_sync(self) -> None: ...


# ---------------------------------------------------------------------------
# AlignmentTimelineWidget
# ---------------------------------------------------------------------------

class AlignmentTimelineWidget(QtWidgets.QWidget):
    playhead_changed = QtCore.Signal(float)
    camera_offset_changed = QtCore.Signal(float)
    leg2_offset_changed = QtCore.Signal(float)
    h5_alignment_drag_changed = QtCore.Signal(float, float, float, float, float)
    h5_alignment_drag_finished = QtCore.Signal()

    _OFFSCREEN_INDICATOR_SIZE_PX = 8
    _CONTEXT_MENU_MOVEMENT_THRESHOLD_PX = 4.0

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
        self._middle_dragging = False
        self._right_dragging = False
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
        self._signals_plot: SignalPlotWidget | None = None
        self._right_press_pos: QtCore.QPointF | None = None
        self._offscreen_indicator_rect: QtCore.QRectF | None = None

    def set_signals_plot(self, signals_plot: SignalPlotWidget) -> None:
        self._signals_plot = signals_plot

    def set_time_axis_rect(self, left_px: float, right_px: float) -> None:
        if (
            self._time_axis_left_px is not None
            and math.isclose(left_px, self._time_axis_left_px)
            and math.isclose(right_px, self._time_axis_right_px)
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

            playhead_color_indicator = QtGui.QColor(TIMELINE_PLAYHEAD_COLOR_HEX)
            playhead_color_indicator.setAlpha(PLAYHEAD_ALPHA)
            self._draw_offscreen_playhead_indicator(painter, plot_rect, playhead_color_indicator)
        finally:
            painter.end()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self._middle_dragging = True
            self._forward_mouse_to_signals_viewbox(event)
            event.accept()
            return

        if event.button() == QtCore.Qt.MouseButton.RightButton:
            self._right_dragging = False
            self._right_press_pos = event.position()
            event.accept()
            return

        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return

        if self._handle_offscreen_indicator_click(event.position()):
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
        if self._middle_dragging:
            self._forward_mouse_to_signals_viewbox(event, QtCore.Qt.MouseButton.MiddleButton)
            event.accept()
            return

        if self._right_press_pos is not None:
            delta = event.position() - self._right_press_pos
            if not self._right_dragging and (
                abs(delta.x()) > self._CONTEXT_MENU_MOVEMENT_THRESHOLD_PX
                or abs(delta.y()) > self._CONTEXT_MENU_MOVEMENT_THRESHOLD_PX
            ):
                self._right_dragging = True
                # Send a synthetic right press to the signals plot at the original press position
                if self._signals_plot is not None:
                    local_pos = self._signals_local_pos(self._right_press_pos.x())
                    viewport = self._signals_plot.viewport()
                    vp_pos = viewport.mapFrom(self._signals_plot, local_pos.toPoint())
                    global_pos = viewport.mapToGlobal(vp_pos)
                    press_event = QtGui.QMouseEvent(
                        QtCore.QEvent.Type.MouseButtonPress,
                        QtCore.QPointF(vp_pos),
                        QtCore.QPointF(global_pos),
                        QtCore.Qt.MouseButton.RightButton,
                        QtCore.Qt.MouseButton.RightButton,
                        event.modifiers(),
                    )
                    QtWidgets.QApplication.sendEvent(viewport, press_event)
            if self._right_dragging:
                self._forward_mouse_to_signals_viewbox(event, QtCore.Qt.MouseButton.RightButton)
                event.accept()
                return

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
        if event.button() == QtCore.Qt.MouseButton.MiddleButton and self._middle_dragging:
            self._middle_dragging = False
            self._forward_mouse_to_signals_viewbox(event)
            event.accept()
            return

        if event.button() == QtCore.Qt.MouseButton.RightButton:
            if self._right_dragging:
                self._right_dragging = False
                self._right_press_pos = None
                self._forward_mouse_to_signals_viewbox(event, QtCore.Qt.MouseButton.RightButton)
                event.accept()
                return
            # Right click with minimal movement → show context menu
            self._right_press_pos = None
            self._show_timeline_context_menu(event.globalPosition().toPoint())
            event.accept()
            return

        was_dragging_offset_track = self._dragging_camera or self._dragging_leg2
        was_dragging_h5 = self._dragging_h5
        self._dragging_camera = False
        self._dragging_leg2 = False
        self._dragging_h5 = False
        self._h5_drag_snapshot = None
        self._dragging_playhead = False
        if was_dragging_offset_track:
            self._range_model.end_visible_range_freeze(recompute=False)
        if was_dragging_h5:
            self.h5_alignment_drag_finished.emit()
        self.update()
        self._update_hover_cursor()

    def _show_timeline_context_menu(self, global_pos: QtCore.QPoint) -> None:
        menu = QtWidgets.QMenu(self)
        zoom_fit = menu.addAction("Zoom to Fit")
        zoom_fit.triggered.connect(self._range_model.recompute_visible_range)
        menu.exec(global_pos)

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        if (
            not self._dragging_camera
            and not self._dragging_leg2
            and not self._dragging_h5
            and not self._dragging_playhead
            and not self._middle_dragging
            and not self._right_dragging
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

    # ------------------------------------------------------------------
    # Event forwarding helpers
    # ------------------------------------------------------------------

    def _timeline_x_to_signals_x(self, cursor_x: float) -> float:
        """Convert a pixel x on this timeline to the equivalent pixel x on the Signals ViewBox."""
        if self._signals_plot is None:
            return 0.0
        plot_rect = self._plot_rect()
        if plot_rect.width() <= 1:
            return 0.0
        range_start_s, range_end_s = self._range_model.visible_range_s()
        span_s = max(1e-6, range_end_s - range_start_s)
        time_s = range_start_s + (cursor_x - plot_rect.left()) / plot_rect.width() * span_s
        view_box = self._signals_plot.getPlotItem().getViewBox()
        vb_scene_rect = view_box.mapToScene(view_box.boundingRect()).boundingRect()
        vb_widget_rect = self._signals_plot.mapFromScene(vb_scene_rect).boundingRect()
        frac = (time_s - range_start_s) / span_s
        return vb_widget_rect.left() + frac * vb_widget_rect.width()

    def _signals_local_pos(self, timeline_x: float) -> QtCore.QPointF:
        """Return position in signals_plot widget coords corresponding to timeline_x."""
        if self._signals_plot is None:
            return QtCore.QPointF(0, 0)
        signals_x = self._timeline_x_to_signals_x(timeline_x)
        view_box = self._signals_plot.getPlotItem().getViewBox()
        vb_scene_rect = view_box.mapToScene(view_box.boundingRect()).boundingRect()
        vb_widget_rect = self._signals_plot.mapFromScene(vb_scene_rect).boundingRect()
        center_y = vb_widget_rect.center().y()
        return QtCore.QPointF(signals_x, center_y)

    def _forward_wheel_to_signals(self, event: QtGui.QWheelEvent) -> None:
        if self._signals_plot is None:
            return
        local_pos = self._signals_local_pos(event.position().x())
        # Convert to viewport coordinates (viewport may have a small offset vs. PlotWidget)
        viewport = self._signals_plot.viewport()
        vp_pos = viewport.mapFrom(self._signals_plot, local_pos.toPoint())
        vp_posf = QtCore.QPointF(vp_pos)
        global_pos = viewport.mapToGlobal(vp_pos)
        synthetic = QtGui.QWheelEvent(
            vp_posf,
            QtCore.QPointF(global_pos),
            event.pixelDelta(),
            QtCore.QPoint(0, event.angleDelta().y()),
            event.buttons(),
            event.modifiers(),
            event.phase(),
            event.isInverted(),
        )
        QtWidgets.QApplication.sendEvent(viewport, synthetic)

    def _forward_mouse_to_signals_viewbox(
        self,
        event: QtGui.QMouseEvent,
        override_button: QtCore.Qt.MouseButton | None = None,
    ) -> None:
        if self._signals_plot is None:
            return
        local_pos = self._signals_local_pos(event.position().x())
        viewport = self._signals_plot.viewport()
        vp_pos = viewport.mapFrom(self._signals_plot, local_pos.toPoint())
        vp_posf = QtCore.QPointF(vp_pos)
        global_pos = viewport.mapToGlobal(vp_pos)
        button = override_button if override_button is not None else event.button()
        buttons = event.buttons()
        # For press events, add the pressed button to buttons mask
        if event.type() == QtCore.QEvent.Type.MouseButtonPress:
            buttons = buttons | button
        elif event.type() == QtCore.QEvent.Type.MouseButtonRelease:
            buttons = buttons & ~button
        synthetic = QtGui.QMouseEvent(
            event.type(),
            vp_posf,
            QtCore.QPointF(global_pos),
            button,
            buttons,
            event.modifiers(),
        )
        QtWidgets.QApplication.sendEvent(viewport, synthetic)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        self._forward_wheel_to_signals(event)
        event.accept()

    # ------------------------------------------------------------------
    # Off-screen playhead indicator
    # ------------------------------------------------------------------

    def _draw_offscreen_playhead_indicator(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF, playhead_color: QtGui.QColor) -> None:
        range_start_s, range_end_s = self._range_model.visible_range_s()
        t = self._current_time_s
        sz = self._OFFSCREEN_INDICATOR_SIZE_PX
        self._offscreen_indicator_rect = None
        if t > range_end_s:
            # Arrow pointing right at right edge
            cx = plot_rect.right() - sz * 0.5
            cy = plot_rect.top() + 16  # same y as playhead
            poly = QtGui.QPolygonF([
                QtCore.QPointF(cx - sz, cy - sz * 0.6),
                QtCore.QPointF(cx + sz * 0.5, cy),
                QtCore.QPointF(cx - sz, cy + sz * 0.6),
            ])
            self._offscreen_indicator_rect = QtCore.QRectF(cx - sz, cy - sz * 0.6, sz * 1.5, sz * 1.2)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QBrush(playhead_color))
            painter.drawPolygon(poly)
        elif t < range_start_s:
            # Arrow pointing left at left edge
            cx = plot_rect.left() + sz * 0.5
            cy = plot_rect.top() + 16
            poly = QtGui.QPolygonF([
                QtCore.QPointF(cx + sz, cy - sz * 0.6),
                QtCore.QPointF(cx - sz * 0.5, cy),
                QtCore.QPointF(cx + sz, cy + sz * 0.6),
            ])
            self._offscreen_indicator_rect = QtCore.QRectF(cx - sz * 0.5, cy - sz * 0.6, sz * 1.5, sz * 1.2)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QBrush(playhead_color))
            painter.drawPolygon(poly)

    def _handle_offscreen_indicator_click(self, widget_pos: QtCore.QPointF) -> bool:
        if self._offscreen_indicator_rect is None:
            return False
        if not self._offscreen_indicator_rect.contains(widget_pos):
            return False
        range_start_s, range_end_s = self._range_model.visible_range_s()
        span_s = range_end_s - range_start_s
        t = self._current_time_s
        if t > range_end_s:
            new_start = t - span_s * 0.8
        else:
            new_start = t - span_s * 0.2
        self._range_model.set_visible_range(new_start, new_start + span_s)
        return True
