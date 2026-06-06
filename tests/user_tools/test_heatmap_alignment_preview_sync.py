from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

from heatmap_alignment_preview_sync import PreviewSyncPlan  # noqa: E402


def test_preview_sync_plan_defaults() -> None:
    plan = PreviewSyncPlan()

    assert plan.camera_access_hint == "auto"
    assert plan.invalidate_source_resolution is True
    assert plan.timeline_visible_range_s is None
    assert plan.refresh_signal_data is True


def test_preview_sync_plan_custom_values() -> None:
    plan = PreviewSyncPlan(
        camera_access_hint="scrub",
        invalidate_source_resolution=False,
        timeline_visible_range_s=(1.0, 2.0),
        refresh_signal_data=False,
    )

    assert plan.camera_access_hint == "scrub"
    assert plan.invalidate_source_resolution is False
    assert plan.timeline_visible_range_s == (1.0, 2.0)
    assert plan.refresh_signal_data is False
