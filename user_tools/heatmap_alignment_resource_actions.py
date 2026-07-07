"""Small resource-action helpers for the heatmap alignment workbench."""

from __future__ import annotations

from pathlib import Path

from heatmap_alignment_core_models import AlignmentSession
from heatmap_alignment_resource_summaries import ResourceKind
from heatmap_peak_distance_resource import PeakSeriesResource


def resource_path_for_kind(
    session: AlignmentSession,
    kind: ResourceKind,
    *,
    peak_series: list[PeakSeriesResource],
    leg2_path_text: str,
) -> str:
    if kind == "camera":
        return session.camera_track.path
    if kind == "radar_h5":
        return session.heatmap_track.path
    if kind == "radar_peak":
        for series in peak_series:
            if series.json_path is not None:
                return str(series.json_path)
        return ""
    return leg2_path_text


def containing_directory(path: Path) -> Path:
    return path if path.is_dir() else path.parent
