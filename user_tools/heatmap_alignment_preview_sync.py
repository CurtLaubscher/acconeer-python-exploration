from __future__ import annotations

"""Preview synchronization plan and stage ordering for the alignment workbench."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PreviewSyncPlan:
    """Inputs controlling one full preview refresh pass."""

    camera_access_hint: str = "auto"
    invalidate_source_resolution: bool = True
    timeline_visible_range_s: tuple[float, float] | None = None
    refresh_signal_data: bool = True
