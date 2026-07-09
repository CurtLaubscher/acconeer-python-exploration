from __future__ import annotations


"""Resource job state and board transitions for heatmap alignment."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from heatmap_alignment_job_lifecycle import JobResultStatus


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

ACTIVE_RESOURCE_JOB_PHASES: tuple[ResourceJobPhase, ...] = (
    "pending",
    "loading",
    "building",
    "waiting",
    "cancelling",
)


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
    return classify_job_result(slot, result_generation) == JobResultStatus.ACCEPTED


def classify_job_result(
    slot: ResourceJobSlotState,
    result_generation: int,
    *,
    generation_cancelled: bool = False,
) -> JobResultStatus:
    if generation_cancelled or slot.cancel_requested or slot.phase == "cancelling":
        return JobResultStatus.CANCELLED
    if result_generation != slot.generation or slot.phase in ("superseded", "idle"):
        return JobResultStatus.STALE
    return JobResultStatus.ACCEPTED


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
        if phase in ACTIVE_RESOURCE_JOB_PHASES:
            return True
    return False


def resource_job_target_filename(path: Path | None) -> str:
    if path is None:
        return ""
    return path.name


def resource_job_slot_is_active(slot: ResourceJobSlotState) -> bool:
    return slot.phase in ACTIVE_RESOURCE_JOB_PHASES


def resource_job_loading_overlay_message(slot: ResourceJobSlotState) -> str:
    if slot.message:
        return slot.message
    target = resource_job_target_filename(slot.target_path)
    if slot.phase == "waiting":
        return f"Waiting for {target}..."
    if slot.phase == "building":
        return f"Building preview proxy for {target}..."
    return f"Loading {target}..."
