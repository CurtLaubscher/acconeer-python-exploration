"""Resource identity and session-reconcile helpers for heatmap alignment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from heatmap_alignment_core_models import AlignmentSession


ReconcileAction = Literal["keep", "load", "unload"]


@dataclass(frozen=True)
class CameraSlotIdentity:
    """Identity of the camera slot: just its file path."""
    path: str


@dataclass(frozen=True)
class H5SlotIdentity:
    """Identity of the H5 slot: path plus the four selection indices."""
    path: str
    session_idx: int
    group_idx: int
    entry_idx: int
    subsweep_idx: int


@dataclass(frozen=True)
class SyncSlotIdentity:
    """Identity of a synchronous-import slot (peak JSON or Leg2 MAT): just path."""
    path: str


def desired_camera_identity(session: AlignmentSession) -> CameraSlotIdentity | None:
    """Return desired camera identity, or None when path is empty (slot not wanted)."""
    path = session.camera_track.path
    return CameraSlotIdentity(path=path) if path else None


def desired_h5_identity(session: AlignmentSession) -> H5SlotIdentity | None:
    """Return desired H5 identity, or None when path is empty (slot not wanted)."""
    path = session.heatmap_track.path
    if not path:
        return None
    return H5SlotIdentity(
        path=path,
        session_idx=session.heatmap_track.session_idx,
        group_idx=session.heatmap_track.group_idx,
        entry_idx=session.heatmap_track.entry_idx,
        subsweep_idx=session.heatmap_track.subsweep_idx,
    )


def desired_peak_identities(session: AlignmentSession) -> list:
    """Return desired peak series identities from session.peak_series."""
    return [SyncSlotIdentity(path=entry.path) for entry in session.peak_series if entry.path]


def desired_leg2_identity(session: AlignmentSession) -> SyncSlotIdentity | None:
    """Return desired Leg2 MAT identity, or None when path is empty."""
    path = session.leg2_ultrasonic_datasource.path
    return SyncSlotIdentity(path=path) if path else None


def reconcile_camera_action(
    desired: CameraSlotIdentity | None,
    *,
    loaded_path: str | None,
    inflight_path: str | None,
) -> ReconcileAction:
    """Return the reconcile action for the camera slot.

    desired=None means the session does not want a camera resource.
    loaded_path/inflight_path are None when no resource is active/in-flight.
    """
    if desired is None:
        if loaded_path is not None or inflight_path is not None:
            return "unload"
        return "keep"
    active = CameraSlotIdentity(path=loaded_path) if loaded_path else None
    inflight = CameraSlotIdentity(path=inflight_path) if inflight_path else None
    if desired == active or desired == inflight:
        return "keep"
    return "load"


def reconcile_h5_action(
    desired: H5SlotIdentity | None,
    *,
    loaded_identity: H5SlotIdentity | None,
    inflight_identity: H5SlotIdentity | None,
) -> ReconcileAction:
    """Return the reconcile action for the H5 slot.

    desired=None means the session does not want an H5 resource.
    """
    if desired is None:
        if loaded_identity is not None or inflight_identity is not None:
            return "unload"
        return "keep"
    if desired == loaded_identity or desired == inflight_identity:
        return "keep"
    return "load"


def reconcile_sync_slot_action(
    desired: SyncSlotIdentity | None,
    *,
    loaded_path: str | None,
) -> ReconcileAction:
    """Return the reconcile action for a synchronous-import slot (peak or Leg2).

    keep requires: desired path set, matches loaded path, datasource object present.
    The caller must pass loaded_path=None when the datasource object is not present.
    """
    if desired is None:
        return "unload" if loaded_path is not None else "keep"
    if loaded_path is not None and desired.path == loaded_path:
        return "keep"
    return "load"


def elide_path_middle(path_text: str, max_chars: int) -> str:
    """Elide a path in the middle while preserving the filename when possible."""

    if max_chars < 4 or len(path_text) <= max_chars:
        return path_text

    path = Path(path_text)
    filename = path.name or path_text
    if not filename:
        return path_text[:max_chars]

    if path_text.endswith(filename):
        separator_index = len(path_text) - len(filename) - 1
        if separator_index >= 0 and path_text[separator_index] in "/\\":
            suffix = path_text[separator_index:]
        else:
            suffix = filename
    else:
        suffix = filename

    if len(suffix) >= max_chars:
        return f"...{suffix[-(max_chars - 3) :]}"

    ellipsis = "..."
    prefix_budget = max_chars - len(suffix) - len(ellipsis)
    if prefix_budget <= 0:
        return suffix[:max_chars]

    prefix = path_text[:prefix_budget]
    return f"{prefix}{ellipsis}{suffix}"
