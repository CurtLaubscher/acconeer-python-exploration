"""Peak overlay selection helpers for heatmap alignment previews and exports."""

from __future__ import annotations

import numpy as np
from heatmap_peak_distance_resource import active_peak_measurements, active_peak_zero_velocity_m_s
from sparse_iq_peak_distance_core import STATUS_DETECTED


PeakOverlay = tuple[float | None, float | None, np.ndarray | None]


def peak_overlay_for_frame(peak_state: object | None, frame_idx: int) -> PeakOverlay | None:
    """Return peak marker and detection-ratio data for one heatmap frame."""

    if peak_state is None:
        return None
    measurements = active_peak_measurements(peak_state)
    if measurements is None:
        return None
    measurement = next((m for m in measurements if m.frame_index == frame_idx), None)
    if measurement is None:
        return None

    ratio = measurement.detection_ratio if len(measurement.detection_ratio) > 0 else None
    zero_velocity_m_s = active_peak_zero_velocity_m_s(peak_state)
    if measurement.status != STATUS_DETECTED:
        return None, zero_velocity_m_s, ratio
    if measurement.target_distance_m is None:
        return None
    return measurement.target_distance_m, zero_velocity_m_s, ratio
