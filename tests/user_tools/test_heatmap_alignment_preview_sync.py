from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

import numpy as np

from heatmap_alignment_preview_sync import PreviewChange, PreviewSyncPlan, run_preview_sync  # noqa: E402


def test_preview_sync_plan_defaults() -> None:
    plan = PreviewSyncPlan()

    assert plan.camera_access_hint == "auto"
    assert plan.invalidate_source_resolution is True
    assert plan.timeline_visible_range_s is None
    assert plan.recompute_timeline_range is False
    assert plan.refresh_signal_data is True


def test_preview_sync_plan_custom_values() -> None:
    plan = PreviewSyncPlan(
        camera_access_hint="scrub",
        invalidate_source_resolution=False,
        timeline_visible_range_s=(1.0, 2.0),
        recompute_timeline_range=True,
        refresh_signal_data=False,
    )

    assert plan.camera_access_hint == "scrub"
    assert plan.invalidate_source_resolution is False
    assert plan.timeline_visible_range_s == (1.0, 2.0)
    assert plan.recompute_timeline_range is True
    assert plan.refresh_signal_data is False


def test_preview_sync_plan_from_signal_only_change() -> None:
    plan = PreviewSyncPlan.from_changes(PreviewChange.SIGNALS_ONLY)

    assert plan.invalidate_source_resolution is False
    assert plan.refresh_camera_frame is False
    assert plan.refresh_camera_corners is False
    assert plan.refresh_timeline_feedback is True
    assert plan.refresh_signal_data is True
    assert plan.refresh_heatmap_truth is False
    assert plan.refresh_export_overlay is False
    assert plan.refresh_viewport is False


def test_preview_sync_plan_from_export_overlay_change() -> None:
    plan = PreviewSyncPlan.from_changes(PreviewChange.EXPORT_OVERLAY)

    assert plan.invalidate_source_resolution is False
    assert plan.refresh_camera_frame is False
    assert plan.refresh_timeline_feedback is False
    assert plan.refresh_heatmap_truth is True
    assert plan.refresh_export_overlay is True
    assert plan.refresh_viewport is False


def test_preview_sync_plan_from_viewport_visibility_change() -> None:
    plan = PreviewSyncPlan.from_changes(PreviewChange.VIEWPORT_VISIBILITY)

    assert plan.invalidate_source_resolution is False
    assert plan.refresh_camera_frame is False
    assert plan.refresh_heatmap_truth is False
    assert plan.refresh_export_overlay is False
    assert plan.refresh_viewport is True


def test_preview_sync_plan_from_layout_change() -> None:
    plan = PreviewSyncPlan.from_changes(PreviewChange.LAYOUT)

    assert plan.invalidate_source_resolution is False
    assert plan.refresh_camera_frame is False
    assert plan.refresh_heatmap_truth is False
    assert plan.refresh_export_overlay is False
    assert plan.refresh_viewport is True


def test_preview_sync_plan_from_camera_time_change() -> None:
    plan = PreviewSyncPlan.from_changes(
        PreviewChange.CAMERA_TIME,
        camera_access_hint="scrub",
        refresh_signal_data=False,
    )

    assert plan.camera_access_hint == "scrub"
    assert plan.invalidate_source_resolution is True
    assert plan.refresh_camera_frame is True
    assert plan.refresh_timeline_feedback is True
    assert plan.refresh_signal_data is False
    assert plan.refresh_heatmap_truth is True
    assert plan.refresh_export_overlay is True
    assert plan.refresh_viewport is True


def test_preview_sync_plan_combines_change_flags() -> None:
    plan = PreviewSyncPlan.from_changes(PreviewChange.SIGNALS_ONLY | PreviewChange.LAYOUT)

    assert plan.invalidate_source_resolution is False
    assert plan.refresh_camera_frame is False
    assert plan.refresh_timeline_feedback is True
    assert plan.refresh_signal_data is True
    assert plan.refresh_heatmap_truth is False
    assert plan.refresh_export_overlay is False
    assert plan.refresh_viewport is True


class _RecordingPreviewHost:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._truth_frame = np.zeros((2, 2, 3), dtype=np.uint8)

    def _invalidate_source_resolution_viewport(self) -> None:
        self.calls.append("invalidate")

    def _load_current_camera_frame(self, *, access_hint: str) -> None:
        self.calls.append(f"camera:{access_hint}")

    def _refresh_camera_view_corners(self) -> None:
        self.calls.append("corners")

    def _sync_timeline_feedback(
        self,
        *,
        timeline_visible_range_s: tuple[float, float] | None,
        recompute_timeline_range: bool,
        refresh_signal_data: bool,
    ) -> None:
        self.calls.append(
            f"timeline:{timeline_visible_range_s}:{recompute_timeline_range}:{refresh_signal_data}"
        )

    def _sync_heatmap_truth_preview(self) -> tuple[int | None, np.ndarray | None]:
        self.calls.append("truth")
        return 7, self._truth_frame

    def _sync_export_overlay_preview(
        self,
        *,
        frame_idx: int | None,
        truth_frame: np.ndarray | None,
    ) -> None:
        self.calls.append(f"overlay:{frame_idx}:{truth_frame is not None}")

    def _sync_viewport_preview(
        self,
        *,
        truth_frame: np.ndarray | None,
        invalidate_source_resolution: bool,
    ) -> None:
        self.calls.append(f"viewport:{truth_frame is not None}:{invalidate_source_resolution}")


def test_run_preview_sync_runs_stages_in_order() -> None:
    host = _RecordingPreviewHost()
    plan = PreviewSyncPlan(
        camera_access_hint="scrub",
        timeline_visible_range_s=(1.0, 2.0),
        refresh_signal_data=False,
    )

    run_preview_sync(plan, host)

    assert host.calls == [
        "invalidate",
        "camera:scrub",
        "corners",
        "timeline:(1.0, 2.0):False:False",
        "truth",
        "overlay:7:True",
        "viewport:True:True",
    ]


def test_run_preview_sync_skips_invalidate_when_disabled() -> None:
    host = _RecordingPreviewHost()
    plan = PreviewSyncPlan(invalidate_source_resolution=False)

    run_preview_sync(plan, host)

    assert "invalidate" not in host.calls
    assert host.calls[0] == "camera:auto"


def test_run_preview_sync_can_refresh_only_signal_feedback() -> None:
    host = _RecordingPreviewHost()
    plan = PreviewSyncPlan.from_changes(PreviewChange.SIGNALS_ONLY)

    run_preview_sync(plan, host)

    assert host.calls == ["timeline:None:False:True"]
