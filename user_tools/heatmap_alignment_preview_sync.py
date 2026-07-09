from __future__ import annotations

"""Preview synchronization plan and stage ordering for the alignment workbench."""

from dataclasses import dataclass
from enum import Enum, Flag, auto
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


class PreviewWork(Flag):
    """Named work items that one preview sync may perform."""

    INVALIDATE_SOURCE_RESOLUTION = auto()
    CAMERA_FRAME = auto()
    CAMERA_CORNERS = auto()
    TIMELINE_FEEDBACK = auto()
    SIGNAL_DATA = auto()
    HEATMAP_TRUTH = auto()
    EXPORT_OVERLAY = auto()
    VIEWPORT = auto()


class PreviewOutput(Flag):
    """Derived preview outputs affected by one sync."""

    CAMERA_FRAME = auto()
    CAMERA_CORNERS = auto()
    TIMELINE_FEEDBACK = auto()
    SIGNAL_DATA = auto()
    HEATMAP_TRUTH = auto()
    EXPORT_OVERLAY = auto()
    VIEWPORT = auto()
    SOURCE_RESOLUTION_VIEWPORT = auto()


@dataclass(frozen=True)
class PreviewOutputEffects:
    """Derived preview outputs refreshed or invalidated by one sync."""

    refreshed: PreviewOutput = PreviewOutput(0)
    invalidated: PreviewOutput = PreviewOutput(0)

    @property
    def affected(self) -> PreviewOutput:
        return self.refreshed | self.invalidated


class PreviewOutputStatus(Enum):
    """Tracked freshness state for a derived preview output."""

    UNKNOWN = "unknown"
    FRESH = "fresh"
    STALE = "stale"


class PreviewOutputState:
    """Mutable freshness tracker for derived preview outputs."""

    def __init__(self) -> None:
        self._statuses: dict[PreviewOutput, PreviewOutputStatus] = {}

    def status(self, output: PreviewOutput) -> PreviewOutputStatus:
        return self._statuses.get(output, PreviewOutputStatus.UNKNOWN)

    def apply(self, effects: PreviewOutputEffects) -> None:
        for output in PreviewOutput:
            if output & effects.invalidated:
                self._statuses[output] = PreviewOutputStatus.STALE
            if output & effects.refreshed:
                self._statuses[output] = PreviewOutputStatus.FRESH


def preview_work_for_changes(
    changes: PreviewChange,
    *,
    refresh_signal_data: bool = True,
) -> PreviewWork:
    """Map high-level change reasons to the preview work they require."""
    work = PreviewWork(0)

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

    if not changes:
        work |= (
            PreviewWork.INVALIDATE_SOURCE_RESOLUTION
            | PreviewWork.CAMERA_FRAME
            | PreviewWork.CAMERA_CORNERS
            | PreviewWork.TIMELINE_FEEDBACK
            | PreviewWork.HEATMAP_TRUTH
            | PreviewWork.EXPORT_OVERLAY
            | PreviewWork.VIEWPORT
        )
        if refresh_signal_data:
            work |= PreviewWork.SIGNAL_DATA
        return work

    if changes & viewport_decode_changes:
        work |= PreviewWork.INVALIDATE_SOURCE_RESOLUTION
    if changes & camera_frame_changes:
        work |= PreviewWork.CAMERA_FRAME
    if changes & (PreviewChange.CAMERA_SOURCE | PreviewChange.VIEWPORT_GEOMETRY):
        work |= PreviewWork.CAMERA_CORNERS
    if changes & timeline_changes:
        work |= PreviewWork.TIMELINE_FEEDBACK
    if refresh_signal_data and changes & (PreviewChange.H5_SOURCE | PreviewChange.SIGNALS_ONLY):
        work |= PreviewWork.SIGNAL_DATA
    if changes & (h5_frame_changes | PreviewChange.EXPORT_OVERLAY):
        work |= PreviewWork.HEATMAP_TRUTH
    if changes & (
        PreviewChange.CAMERA_TIME
        | PreviewChange.H5_SOURCE
        | PreviewChange.H5_RENDER_SETTINGS
        | PreviewChange.EXPORT_OVERLAY
    ):
        work |= PreviewWork.EXPORT_OVERLAY
    if changes & viewport_display_changes:
        work |= PreviewWork.VIEWPORT

    return work


def preview_outputs_for_work(work: PreviewWork) -> PreviewOutput:
    """Map named preview work to the derived outputs it refreshes or invalidates."""
    return preview_output_effects_for_work(work).affected


def preview_output_effects_for_work(work: PreviewWork) -> PreviewOutputEffects:
    """Map named preview work to refreshed and invalidated derived outputs."""
    outputs = PreviewOutput(0)
    invalidated = PreviewOutput(0)
    if work & PreviewWork.CAMERA_FRAME:
        outputs |= PreviewOutput.CAMERA_FRAME
    if work & PreviewWork.CAMERA_CORNERS:
        outputs |= PreviewOutput.CAMERA_CORNERS
    if work & PreviewWork.TIMELINE_FEEDBACK:
        outputs |= PreviewOutput.TIMELINE_FEEDBACK
    if work & PreviewWork.SIGNAL_DATA:
        outputs |= PreviewOutput.SIGNAL_DATA
    if work & PreviewWork.HEATMAP_TRUTH:
        outputs |= PreviewOutput.HEATMAP_TRUTH
    if work & PreviewWork.EXPORT_OVERLAY:
        outputs |= PreviewOutput.EXPORT_OVERLAY
    if work & PreviewWork.VIEWPORT:
        outputs |= PreviewOutput.VIEWPORT
    if work & PreviewWork.INVALIDATE_SOURCE_RESOLUTION:
        invalidated |= PreviewOutput.SOURCE_RESOLUTION_VIEWPORT
    return PreviewOutputEffects(refreshed=outputs, invalidated=invalidated)


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

    @property
    def work(self) -> PreviewWork:
        """Named work represented by this plan."""
        work = PreviewWork(0)
        if self.invalidate_source_resolution:
            work |= PreviewWork.INVALIDATE_SOURCE_RESOLUTION
        if self.refresh_camera_frame:
            work |= PreviewWork.CAMERA_FRAME
        if self.refresh_camera_corners:
            work |= PreviewWork.CAMERA_CORNERS
        if self.refresh_timeline_feedback:
            work |= PreviewWork.TIMELINE_FEEDBACK
            if self.refresh_signal_data:
                work |= PreviewWork.SIGNAL_DATA
        if self.refresh_heatmap_truth:
            work |= PreviewWork.HEATMAP_TRUTH
        if self.refresh_export_overlay:
            work |= PreviewWork.EXPORT_OVERLAY
        if self.refresh_viewport:
            work |= PreviewWork.VIEWPORT
        return work

    @property
    def outputs(self) -> PreviewOutput:
        """Derived preview outputs affected by this plan."""
        return preview_outputs_for_work(self.work)

    @property
    def output_effects(self) -> PreviewOutputEffects:
        """Derived preview outputs refreshed or invalidated by this plan."""
        return preview_output_effects_for_work(self.work)

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
        change reasons opt in to only the affected preview outputs.
        """
        work = preview_work_for_changes(changes, refresh_signal_data=refresh_signal_data)

        return cls(
            camera_access_hint=camera_access_hint,
            invalidate_source_resolution=bool(work & PreviewWork.INVALIDATE_SOURCE_RESOLUTION),
            timeline_visible_range_s=timeline_visible_range_s,
            recompute_timeline_range=recompute_timeline_range,
            refresh_signal_data=bool(work & PreviewWork.SIGNAL_DATA),
            refresh_camera_frame=bool(work & PreviewWork.CAMERA_FRAME),
            refresh_camera_corners=bool(work & PreviewWork.CAMERA_CORNERS),
            refresh_timeline_feedback=bool(work & PreviewWork.TIMELINE_FEEDBACK),
            refresh_heatmap_truth=bool(work & PreviewWork.HEATMAP_TRUTH),
            refresh_export_overlay=bool(work & PreviewWork.EXPORT_OVERLAY),
            refresh_viewport=bool(work & PreviewWork.VIEWPORT),
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


def run_preview_sync(plan: PreviewSyncPlan, host: PreviewSyncHost) -> PreviewOutputEffects:
    """Run preview stages in the workbench's established order."""
    work = plan.work
    if work & PreviewWork.INVALIDATE_SOURCE_RESOLUTION:
        host._invalidate_source_resolution_viewport()
    if work & PreviewWork.CAMERA_FRAME:
        host._load_current_camera_frame(access_hint=plan.camera_access_hint)
    if work & PreviewWork.CAMERA_CORNERS:
        host._refresh_camera_view_corners()
    if work & PreviewWork.TIMELINE_FEEDBACK:
        host._sync_timeline_feedback(
            timeline_visible_range_s=plan.timeline_visible_range_s,
            recompute_timeline_range=plan.recompute_timeline_range,
            refresh_signal_data=bool(work & PreviewWork.SIGNAL_DATA),
        )
    frame_idx: int | None = None
    truth_frame: np.ndarray | None = None
    if work & PreviewWork.HEATMAP_TRUTH:
        frame_idx, truth_frame = host._sync_heatmap_truth_preview()
    if work & PreviewWork.EXPORT_OVERLAY:
        host._sync_export_overlay_preview(frame_idx=frame_idx, truth_frame=truth_frame)
    if work & PreviewWork.VIEWPORT:
        host._sync_viewport_preview(
            truth_frame=truth_frame,
            invalidate_source_resolution=bool(work & PreviewWork.INVALIDATE_SOURCE_RESOLUTION),
        )
    return plan.output_effects
