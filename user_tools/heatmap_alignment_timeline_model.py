"""Timeline range model and geometry helpers for the heatmap alignment workbench."""

from __future__ import annotations

import math
from dataclasses import dataclass

from heatmap_alignment_core import timeline_view_bounds_s

from PySide6 import QtCore


TIMELINE_TRACK_OFFSET_LABEL_MARGIN_PX = 6.0


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
        self._range_end_s = 60.0
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
        if (
            self._freeze_depth > 0
            and self._frozen_range_start_s is not None
            and self._frozen_range_end_s is not None
        ):
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
