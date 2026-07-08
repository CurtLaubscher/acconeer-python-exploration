from __future__ import annotations


"""UI-neutral session flow plans and outcomes for the alignment workbench.

Orchestration boundary (refactor track):
- ``SessionLifecycleState`` owns mutable path/dirty state and pure prompt/guard helpers.
- This module owns multi-step flow inputs and results without Qt dependencies.
- ``HeatmapAlignmentWindow`` owns widgets, dialogs, resource teardown, and preview refresh.

A future coordinator can compose lifecycle helpers into load/close/open sequences while
returning objects from this module. Do not import PySide6 or GUI modules here.
"""

from dataclasses import dataclass
from pathlib import Path

from heatmap_alignment_core_models import AlignmentSession
from heatmap_alignment_reconcile import (
    H5SlotIdentity,
    ReconcileAction,
    desired_camera_identity,
    desired_h5_identity,
    desired_leg2_identity,
    desired_peak_identities,
    reconcile_camera_action,
    reconcile_h5_action,
    reconcile_sync_slot_action,
)
from heatmap_alignment_session_lifecycle import ClosedSessionReset


__all__ = [
    "ClosedSessionReset",
    "LoadSessionPlan",
    "LoadedResourceState",
    "SessionReconcilePlan",
    "plan_session_reconcile",
]


@dataclass(frozen=True)
class LoadSessionPlan:
    """Inputs for opening a saved session file in the workbench."""

    session_path: Path
    prompt_for_unsaved: bool = True


@dataclass(frozen=True)
class LoadedResourceState:
    """Snapshot of currently loaded/inflight resource identities at session-load time.

    All fields are plain values; no Qt widgets, no job manager object.
    The GUI builds this from its live state before calling plan_session_reconcile.
    """

    camera_loaded_path: str | None
    camera_inflight_path: str | None
    h5_loaded_identity: H5SlotIdentity | None
    h5_inflight_identity: H5SlotIdentity | None
    loaded_peak_paths: frozenset[str]
    leg2_loaded_path: str | None


@dataclass(frozen=True)
class SessionReconcilePlan:
    """UI-neutral per-slot actions produced by plan_session_reconcile.

    Each action field is 'keep', 'load', or 'unload'.
    peak_paths_to_load / peak_paths_to_unload carry the set-diff so the GUI
    does not need to recompute it.
    """

    camera_action: ReconcileAction
    h5_action: ReconcileAction
    peak_paths_to_load: frozenset[str]
    peak_paths_to_unload: frozenset[str]
    leg2_action: ReconcileAction


def plan_session_reconcile(
    desired_session: AlignmentSession,
    loaded: LoadedResourceState,
) -> SessionReconcilePlan:
    """Compute per-slot reconcile actions for a session load without touching the GUI.

    Composes existing core reconcile functions with the loaded/inflight state snapshot
    provided by the caller. Does not access Qt widgets, job managers, or file system.
    """
    camera_action = reconcile_camera_action(
        desired_camera_identity(desired_session),
        loaded_path=loaded.camera_loaded_path,
        inflight_path=loaded.camera_inflight_path,
    )
    h5_action = reconcile_h5_action(
        desired_h5_identity(desired_session),
        loaded_identity=loaded.h5_loaded_identity,
        inflight_identity=loaded.h5_inflight_identity,
    )
    peak_desired_paths = frozenset(
        identity.path for identity in desired_peak_identities(desired_session)
    )
    leg2_action = reconcile_sync_slot_action(
        desired_leg2_identity(desired_session),
        loaded_path=loaded.leg2_loaded_path,
    )
    return SessionReconcilePlan(
        camera_action=camera_action,
        h5_action=h5_action,
        peak_paths_to_load=peak_desired_paths - loaded.loaded_peak_paths,
        peak_paths_to_unload=loaded.loaded_peak_paths - peak_desired_paths,
        leg2_action=leg2_action,
    )
