"""Export helpers for the heatmap alignment workbench."""

from __future__ import annotations

import numpy as np
from heatmap_alignment_sources import CameraVideoSource


def first_usable_frame(source: CameraVideoSource) -> np.ndarray:
    last_exc: Exception | None = None
    for frame_idx in range(source.frame_count):
        try:
            return source.frame_at_index(frame_idx, access_hint="random")
        except ValueError as exc:
            last_exc = exc
    raise RuntimeError("Could not read any usable frame from the camera video.") from last_exc


def last_usable_frame(source: CameraVideoSource) -> np.ndarray:
    last_exc: Exception | None = None
    for frame_idx in range(source.frame_count - 1, -1, -1):
        try:
            return source.frame_at_index(frame_idx, access_hint="random")
        except ValueError as exc:
            last_exc = exc
    raise RuntimeError("Could not read any usable frame from the camera video.") from last_exc
