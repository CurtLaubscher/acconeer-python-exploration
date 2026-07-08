from __future__ import annotations


"""Resource job state and board transitions for heatmap alignment."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


ResourceJobKind = Literal["camera", "radar_h5"]
ResourceJobPhase = Literal[
    "idle",
    "pending",
    "loading",
    "building",
    "waiting",
    "cancelling",
    "failed",
    "superseded",
]


class ResourceJobError(RuntimeError):
    """Raised when a background resource job fails."""


class ProxyBuildError(ResourceJobError):
    """Raised when preview proxy generation fails."""


@dataclass(frozen=True)
class ResourceJobSnapshot:
    kind: ResourceJobKind
    generation: int
    phase: ResourceJobPhase = "idle"
    target_path: Path | None = None
    message: str = ""
    cancellable: bool = False
    replaces_active: bool = False


@dataclass
class ResourceJobSlotState:
    generation: int = 0
    active_generation: int = 0
    phase: ResourceJobPhase = "idle"
    target_path: Path | None = None
    message: str = ""
    cancellable: bool = False
    replaces_active: bool = False
    cancel_requested: bool = False

    def snapshot(self, kind: ResourceJobKind) -> ResourceJobSnapshot:
        return ResourceJobSnapshot(
            kind=kind,
            generation=self.generation,
            phase=self.phase,
            target_path=self.target_path,
            message=self.message,
            cancellable=self.cancellable,
            replaces_active=self.replaces_active,
        )


@dataclass
class ResourceJobBoard:
    camera: ResourceJobSlotState = field(default_factory=ResourceJobSlotState)
    radar_h5: ResourceJobSlotState = field(default_factory=ResourceJobSlotState)

    def slot(self, kind: ResourceJobKind) -> ResourceJobSlotState:
        if kind == "camera":
            return self.camera
        return self.radar_h5


def next_generation(current: int) -> int:
    return current + 1


def should_apply_job_result(slot: ResourceJobSlotState, result_generation: int) -> bool:
    return (
        result_generation == slot.generation
        and slot.phase not in ("superseded", "idle", "cancelling")
        and not slot.cancel_requested
    )


def begin_resource_job(
    board: ResourceJobBoard,
    kind: ResourceJobKind,
    *,
    target_path: Path,
    replaces_active: bool,
    initial_phase: ResourceJobPhase = "pending",
    message: str = "",
) -> int:
    slot = board.slot(kind)
    if slot.phase not in ("idle", "failed"):
        slot.phase = "superseded"
    slot.generation = next_generation(slot.generation)
    slot.active_generation = slot.generation
    slot.phase = initial_phase
    slot.target_path = target_path
    slot.message = message
    slot.cancellable = True
    slot.replaces_active = replaces_active
    slot.cancel_requested = False
    return slot.generation


def mark_resource_job_phase(
    board: ResourceJobBoard,
    kind: ResourceJobKind,
    generation: int,
    phase: ResourceJobPhase,
    *,
    message: str | None = None,
) -> None:
    slot = board.slot(kind)
    if generation != slot.generation:
        return
    slot.phase = phase
    if message is not None:
        slot.message = message


def request_cancel_resource_job(board: ResourceJobBoard, kind: ResourceJobKind) -> bool:
    slot = board.slot(kind)
    if slot.phase in ("idle", "failed", "superseded") or not slot.cancellable:
        return False
    slot.cancel_requested = True
    if slot.phase not in ("cancelling",):
        slot.phase = "cancelling"
        slot.message = "Cancelling..."
    return True


def complete_resource_job(
    board: ResourceJobBoard,
    kind: ResourceJobKind,
    generation: int,
    *,
    phase: ResourceJobPhase,
    message: str = "",
) -> None:
    slot = board.slot(kind)
    if generation != slot.generation:
        return
    slot.phase = phase
    slot.message = message
    slot.cancellable = False
    slot.cancel_requested = False
    if phase in ("idle", "failed", "superseded"):
        slot.target_path = None
        slot.replaces_active = False


def clear_resource_job(board: ResourceJobBoard, kind: ResourceJobKind) -> None:
    slot = board.slot(kind)
    slot.phase = "idle"
    slot.message = ""
    slot.target_path = None
    slot.cancellable = False
    slot.replaces_active = False
    slot.cancel_requested = False


def resource_job_blocks_export(board: ResourceJobBoard) -> bool:
    for kind in ("camera", "radar_h5"):
        phase = board.slot(kind).phase
        if phase in ("pending", "loading", "building", "waiting", "cancelling"):
            return True
    return False


def resource_job_target_filename(path: Path | None) -> str:
    if path is None:
        return ""
    return path.name
