"""Source-resolution viewport rendering helpers for heatmap alignment."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from heatmap_alignment_sources import CameraVideoSource
from heatmap_alignment_viewport_processing import rectify_viewport

from PySide6 import QtCore


def render_source_resolution_viewport_request(payload: dict[str, object]) -> np.ndarray:
    camera_path = Path(str(payload["camera_path"]))
    source = CameraVideoSource(camera_path, max_preview_dimension=None)
    try:
        _, frame = source.frame_at_seconds(
            float(payload["camera_time_s"]),
            access_hint="random",
        )
    finally:
        source.close()
    return rectify_viewport(
        frame,
        np.asarray(payload["corners"], dtype=np.float32),
        tuple(int(value) for value in payload["output_size"]),
    )


class SourceResolutionViewportWorker(QtCore.QObject):
    render_finished = QtCore.Signal(object)

    @QtCore.Slot(object)
    def render_request(self, request: object) -> None:
        payload = dict(request) if isinstance(request, dict) else {}
        result: dict[str, object] = {"token": payload.get("token"), "frame": None, "error": None}
        try:
            result["frame"] = render_source_resolution_viewport_request(payload)
        except Exception as exc:
            result["error"] = str(exc)
        self.render_finished.emit(result)
