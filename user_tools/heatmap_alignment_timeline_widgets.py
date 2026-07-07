"""Compatibility facade for timeline and signal-plot widgets.

New code should import from the focused modules directly:
`heatmap_alignment_timeline_model`, `heatmap_alignment_signal_plot`, and
`heatmap_alignment_timeline_widget`.
"""

from __future__ import annotations

from heatmap_alignment_signal_plot import (
    SignalPlotWidget,
    _make_h5_signal_plot_pens,
    _make_leg2_signal_plot_pens,
    _plot_color_with_alpha,
    visible_signal_y_range,
    visible_signal_y_range_for_series,
)
from heatmap_alignment_timeline_model import (
    TIMELINE_TRACK_OFFSET_LABEL_MARGIN_PX,
    TimeAxisGeometry,
    TimelineRangeModel,
    format_track_offset_label,
    track_offset_label_rect,
    track_offset_label_should_show,
)
from heatmap_alignment_timeline_widget import (
    TIMELINE_LABEL_GUTTER_PX,
    TIMELINE_OFFSET_LABEL_COLOR_HEX,
    AlignmentTimelineWidget,
)


__all__ = [
    "AlignmentTimelineWidget",
    "SignalPlotWidget",
    "TIMELINE_LABEL_GUTTER_PX",
    "TIMELINE_OFFSET_LABEL_COLOR_HEX",
    "TIMELINE_TRACK_OFFSET_LABEL_MARGIN_PX",
    "TimeAxisGeometry",
    "TimelineRangeModel",
    "_make_h5_signal_plot_pens",
    "_make_leg2_signal_plot_pens",
    "_plot_color_with_alpha",
    "format_track_offset_label",
    "track_offset_label_rect",
    "track_offset_label_should_show",
    "visible_signal_y_range",
    "visible_signal_y_range_for_series",
]
