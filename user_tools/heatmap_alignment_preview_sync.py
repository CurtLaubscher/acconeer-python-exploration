from __future__ import annotations

"""Preview synchronization plan and stage ordering for the alignment workbench."""

from dataclasses import dataclass
from enum import Flag, auto
from typing import Protocol

import numpy as np


class PreviewChange(Flag):
    """High-level reasons a preview sync is needed."""

    CAMERA_TIME = auto()
    CAMERA_SOURCE = auto()
    CAMERA_OFFSET = auto()
    VIEWPORT_GEOMETRY = auto()
    VIEWPORT_OUTPUT_SIZE = auto()
    VIEWPORT_VISIBILITY = auto()
    H5_SOURCE = auto()
    H5_RENDER_SETTINGS = auto()
    SIGNALS_ONLY = auto()
    EXPORT_OVERLAY = auto()
    LAYOUT = auto()


@dataclass(frozen=True)
class PreviewSyncPlan:
    """Inputs controlling one full preview refresh pass."""

    camera_access_hint: str = "auto"
    invalidate_source_resolution: bool = True
    timeline_visible_range_s: tuple[float, float] | None = None
    recompute_timeline_range: bool = False
    refresh_signal_data: bool = True
    refresh_camera_frame: bool = True
    refresh_camera_corners: bool = True
    refresh_timeline_feedback: bool = True
    refresh_heatmap_truth: bool = True
    refresh_export_overlay: bool = True
    refresh_viewport: bool = True

    @classmethod
    def from_changes(
        cls,
        changes: PreviewChange,
        *,
        camera_access_hint: str = "auto",
        timeline_visible_range_s: tuple[float, float] | None = None,
        recompute_timeline_range: bool = False,
        refresh_signal_data: bool = True,
    ) -> PreviewSyncPlan:
        """Build a sync plan from high-level change reasons.

        The mapping is intentionally conservative: direct ``PreviewSyncPlan``
        construction keeps the established full-sync behavior, while explicit
        change reasons opt in to only the affected preview products.
        """
        if not changes:
            return cls(
                camera_access_hint=camera_access_hint,
                timeline_visible_range_s=timeline_visible_range_s,
                recompute_timeline_range=recompute_timeline_range,
                refresh_signal_data=refresh_signal_data,
            )

        camera_frame_changes = (
            PreviewChange.CAMERA_TIME | PreviewChange.CAMERA_SOURCE | PreviewChange.CAMERA_OFFSET
        )
        viewport_decode_changes = camera_frame_changes | PreviewChange.VIEWPORT_GEOMETRY
        viewport_display_changes = (
            viewport_decode_changes
            | PreviewChange.VIEWPORT_OUTPUT_SIZE
            | PreviewChange.VIEWPORT_VISIBILITY
            | PreviewChange.LAYOUT
        )
        h5_frame_changes = (
            PreviewChange.CAMERA_TIME | PreviewChange.H5_SOURCE | PreviewChange.H5_RENDER_SETTINGS
        )
        timeline_changes = (
            PreviewChange.CAMERA_TIME
            | PreviewChange.CAMERA_SOURCE
            | PreviewChange.CAMERA_OFFSET
            | PreviewChange.H5_SOURCE
            | PreviewChange.SIGNALS_ONLY
        )

        return cls(
            camera_access_hint=camera_access_hint,
            invalidate_source_resolution=bool(changes & viewport_decode_changes),
            timeline_visible_range_s=timeline_visible_range_s,
            recompute_timeline_range=recompute_timeline_range,
            refresh_signal_data=refresh_signal_data and bool(
                changes & (PreviewChange.H5_SOURCE | PreviewChange.SIGNALS_ONLY)
            ),
            refresh_camera_frame=bool(changes & camera_frame_changes),
            refresh_camera_corners=bool(
                changes & (PreviewChange.CAMERA_SOURCE | PreviewChange.VIEWPORT_GEOMETRY)
            ),
            refresh_timeline_feedback=bool(changes & timeline_changes),
            refresh_heatmap_truth=bool(changes & (h5_frame_changes | PreviewChange.EXPORT_OVERLAY)),
            refresh_export_overlay=bool(
                changes
                & (
                    PreviewChange.CAMERA_TIME
                    | PreviewChange.H5_SOURCE
                    | PreviewChange.H5_RENDER_SETTINGS
                    | PreviewChange.EXPORT_OVERLAY
                )
            ),
            refresh_viewport=bool(changes & viewport_display_changes),
        )


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
    if plan.refresh_camera_frame:
        host._load_current_camera_frame(access_hint=plan.camera_access_hint)
    if plan.refresh_camera_corners:
        host._refresh_camera_view_corners()
    if plan.refresh_timeline_feedback:
        host._sync_timeline_feedback(
            timeline_visible_range_s=plan.timeline_visible_range_s,
            recompute_timeline_range=plan.recompute_timeline_range,
            refresh_signal_data=plan.refresh_signal_data,
        )
    frame_idx: int | None = None
    truth_frame: np.ndarray | None = None
    if plan.refresh_heatmap_truth:
        frame_idx, truth_frame = host._sync_heatmap_truth_preview()
    if plan.refresh_export_overlay:
        host._sync_export_overlay_preview(frame_idx=frame_idx, truth_frame=truth_frame)
    if plan.refresh_viewport:
        host._sync_viewport_preview(
            truth_frame=truth_frame,
            invalidate_source_resolution=plan.invalidate_source_resolution,
        )
