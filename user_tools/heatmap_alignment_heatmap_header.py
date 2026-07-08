from __future__ import annotations


"""Heatmap distance header widget for the heatmap alignment workbench."""

import numpy as np
from sparse_iq_heatmap_common import axis_bin_edge_extent

from PySide6 import QtCore, QtGui, QtWidgets


class HeatmapDistanceHeader(QtWidgets.QWidget):
    """Compact header showing distance extent labels and peak distance cue."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._dist_min: float | None = None
        self._dist_max: float | None = None
        self._distance_bin_width_m: float | None = None
        self._peak_dist_m: float | None = None
        self.setFixedHeight(20)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_extent(
        self,
        dist_min: float | None,
        dist_max: float | None,
        distance_bin_width_m: float | None = None,
    ) -> None:
        self._dist_min = dist_min
        self._dist_max = dist_max
        self._distance_bin_width_m = distance_bin_width_m
        self.update()

    def set_peak_distance(self, peak_dist_m: float | None) -> None:
        self._peak_dist_m = peak_dist_m
        self.update()

    def peak_x_for_width(self, width_px: int) -> float | None:
        if (
            self._peak_dist_m is None
            or self._dist_min is None
            or self._dist_max is None
            or width_px <= 0
        ):
            return None

        axis_values = np.array([self._dist_min, self._dist_max], dtype=np.float64)
        fallback_width = abs(self._dist_max - self._dist_min) or 1.0
        x_min, x_max = axis_bin_edge_extent(
            axis_values,
            bin_width=self._distance_bin_width_m,
            fallback_width=fallback_width,
        )
        if x_max <= x_min:
            return None

        x_frac = (self._peak_dist_m - x_min) / (x_max - x_min)
        x_frac = max(0.0, min(1.0, x_frac))
        return x_frac * width_px

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        try:
            w = self.width()
            h = self.height()
            fg = QtGui.QColor("#d7dde6")
            painter.setPen(fg)

            font = painter.font()
            font.setPointSizeF(max(6.0, font.pointSizeF() * 0.85))
            painter.setFont(font)
            fm = QtGui.QFontMetrics(font)

            # Reserve the bottom pixels for the triangle so text sits in the upper band.
            triangle_size = 5
            text_h = h - triangle_size - 2  # text rect height, clear of the triangle

            # Gap between adjacent labels (pixels).
            label_gap = 4
            # Left margin where extent labels are drawn.
            margin = 4

            has_peak = (
                self._peak_dist_m is not None
                and self._dist_min is not None
                and self._dist_max is not None
                and (
                    self._dist_max != self._dist_min
                    or (
                        self._distance_bin_width_m is not None and self._distance_bin_width_m > 0.0
                    )
                )
            )

            # Measure extent labels when we have the data (regardless of show_extents threshold).
            left_text = right_text = ""
            left_w = right_w = 0
            if self._dist_min is not None and self._dist_max is not None:
                left_text = "{:.3f} m".format(self._dist_min)
                right_text = "{:.3f} m".format(self._dist_max)
                left_w = fm.horizontalAdvance(left_text)
                right_w = fm.horizontalAdvance(right_text)

            # Measure peak label.
            peak_text = ""
            peak_text_w = 0
            peak_x = 0.0
            if has_peak:
                peak_text = "{:.3f} m".format(self._peak_dist_m)
                peak_text_w = fm.horizontalAdvance(peak_text)
                peak_x = self.peak_x_for_width(w) or 0.0

            # Decide whether extent labels can coexist with the peak label without overlap.
            # Extent labels sit at [margin, margin+left_w] and [w-margin-right_w, w-margin].
            # Peak text center is clamped within [peak_left_bound, peak_right_bound].
            # If the available gap is too small, suppress extent labels to keep peak cue visible.
            half_peak = peak_text_w // 2
            if has_peak and w >= 120 and left_w > 0:
                # Space available for the peak label center, bounded by extent labels.
                peak_left_bound = margin + left_w + label_gap + half_peak
                peak_right_bound = w - margin - right_w - label_gap - half_peak
                show_extents = peak_left_bound <= peak_right_bound
            else:
                show_extents = w >= 120 and left_w > 0
                peak_left_bound = margin + half_peak
                peak_right_bound = w - margin - half_peak

            if show_extents:
                painter.drawText(
                    margin,
                    0,
                    w - 2 * margin,
                    text_h,
                    int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                    left_text,
                )
                painter.drawText(
                    margin,
                    0,
                    w - 2 * margin,
                    text_h,
                    int(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter),
                    right_text,
                )

            if has_peak:
                # Clamp peak label center to avoid running off the widget edges.
                text_center = max(
                    margin + half_peak,
                    min(w - margin - half_peak, peak_x),
                )
                # Further clamp within the measured extent-label bounds when extents are shown.
                if show_extents:
                    text_center = max(peak_left_bound, min(peak_right_bound, text_center))
                text_left = text_center - half_peak

                # Draw peak label text in the same upper band as extent labels.
                painter.setPen(fg)
                painter.drawText(
                    text_left,
                    0,
                    peak_text_w + 2,
                    text_h,
                    int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                    peak_text,
                )

                # Triangle always tracks true peak_x regardless of label clamping.
                tri_tip_y = h - 1
                tri_top_y = tri_tip_y - triangle_size
                path = QtGui.QPainterPath()
                path.moveTo(peak_x, tri_tip_y)
                path.lineTo(peak_x - triangle_size, tri_top_y)
                path.lineTo(peak_x + triangle_size, tri_top_y)
                path.closeSubpath()
                painter.setBrush(fg)
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.drawPath(path)
        finally:
            painter.end()
