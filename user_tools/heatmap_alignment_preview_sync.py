from __future__ import annotations

"""Preview synchronization plan and stage ordering for the alignment workbench."""

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class PreviewSyncPlan:
    """Inputs controlling one full preview refresh pass."""

    camera_access_hint: str = "auto"
    invalidate_source_resolution: bool = True
    timeline_visible_range_s: tuple[float, float] | None = None
    recompute_timeline_range: bool = False
    refresh_signal_data: bool = True


class PreviewSyncHost(Protocol):
    """Host surface used to run one preview synchronization pass."""

    def _invalidate_source_resolution_viewport(self) -> None: ...

    def _load_current_camera_frame(self, *, access_hint: str) -> None: ...

    def _refresh_camera_view_corners(self) -> None: ...

    def _sync_timeline_feedback(
        self,
        *,
        timeline_visible_range_s: tuple[float, float] | None,
        recompute_timeline_range: bool,
        refresh_signal_data: bool,
    ) -> None: ...

    def _sync_heatmap_truth_preview(self) -> tuple[int | None, np.ndarray | None]: ...

    def _sync_export_overlay_preview(
        self,
        *,
        frame_idx: int | None,
        truth_frame: np.ndarray | None,
    ) -> None: ...

    def _sync_viewport_preview(
        self,
        *,
        truth_frame: np.ndarray | None,
        invalidate_source_resolution: bool,
    ) -> None: ...


def run_preview_sync(plan: PreviewSyncPlan, host: PreviewSyncHost) -> None:
    """Run preview stages in the workbench's established order."""
    if plan.invalidate_source_resolution:
        host._invalidate_source_resolution_viewport()
    host._load_current_camera_frame(access_hint=plan.camera_access_hint)
    host._refresh_camera_view_corners()
    host._sync_timeline_feedback(
        timeline_visible_range_s=plan.timeline_visible_range_s,
        recompute_timeline_range=plan.recompute_timeline_range,
        refresh_signal_data=plan.refresh_signal_data,
    )
    frame_idx, truth_frame = host._sync_heatmap_truth_preview()
    host._sync_export_overlay_preview(frame_idx=frame_idx, truth_frame=truth_frame)
    host._sync_viewport_preview(
        truth_frame=truth_frame,
        invalidate_source_resolution=plan.invalidate_source_resolution,
    )
