"""Resource replacement backup models for the heatmap alignment workbench."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from heatmap_alignment_core_models import CameraTrack, ExportOverlaySettings, HeatmapTrack
from heatmap_alignment_sources import CameraVideoSource, HeatmapTruthSource


@dataclass
class CameraResourceBackup:
    camera_source: CameraVideoSource
    reference_width: int
    reference_height: int
    camera_track: CameraTrack
    current_camera_frame: np.ndarray | None
    viewport_corners: list[list[float]]
    export_overlay: ExportOverlaySettings


@dataclass
class H5ResourceBackup:
    heatmap_source: HeatmapTruthSource
    heatmap_track: HeatmapTrack
    viewport_output_width: int
    viewport_output_height: int
