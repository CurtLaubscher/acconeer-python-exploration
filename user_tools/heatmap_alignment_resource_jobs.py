from __future__ import annotations


"""Background resource job state and worker helpers for heatmap alignment.

H5 ownership model (task 3.1): workers load a full ``HeatmapRecord`` off the GUI thread,
then hand it to the main thread via ``LoadedH5ResourcePayload``. The main thread constructs
``HeatmapTruthSource.from_loaded_record()`` without repeating file initialization. After
handoff, only the main-thread ``HeatmapTruthSource`` owns the HDF5-backed record.
"""

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

import numpy as np

from heatmap_alignment_core import (
    CameraTrack,
    HeatmapTrack,
    HeatmapTruthSource,
    ProxyVideoResult,
    _find_ffmpeg,
    _proxy_cache_path,
    _scaled_video_dimensions,
    probe_video,
    scale_viewport_corners,
)

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

H5_OWNERSHIP_MODEL = (
    "worker-loaded HeatmapRecord handoff: workers load the H5 off the GUI thread and return "
    "LoadedH5ResourcePayload; the main thread adopts it via HeatmapTruthSource.from_loaded_record "
    "without repeating initialization."
)

_PROXY_TEMP_SUFFIX = ".partial"


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
    return result_generation == slot.generation and slot.phase not in ("superseded", "idle")


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
        if phase in ("pending", "loading", "building", "waiting", "cancelling", "failed"):
            return True
    return False


def resource_job_row_status(
    *,
    loaded: bool,
    base_status: str,
    job: ResourceJobSnapshot | None,
) -> str:
    if job is None or job.phase == "idle":
        return base_status
    if job.phase == "pending":
        return "Loading"
    if job.phase == "loading":
        return "Loading"
    if job.phase == "building":
        return "Building"
    if job.phase == "waiting":
        return "Waiting"
    if job.phase == "cancelling":
        return "Cancelling"
    if job.phase == "failed":
        return "Failed"
    if job.phase == "superseded":
        return "Superseded"
    if loaded:
        return base_status
    return base_status


def resource_job_target_filename(path: Path | None) -> str:
    if path is None:
        return ""
    return path.name


@dataclass(frozen=True)
class LoadedH5ResourcePayload:
    """Immutable H5 load result safe to adopt on the main GUI thread."""

    path: Path
    record: object
    subsweep_idx: int
    metadata: HeatmapTrack
    first_frame_shape: tuple[int, int]
    color_min: float = 0.0
    color_max: float | None = 3000.0
    fixed_levels: bool = True
    resolved_fixed_color_level: float | None = None


def load_h5_resource_payload(
    h5_path: Path,
    *,
    session_idx: int | None = None,
    group_idx: int | None = None,
    entry_idx: int | None = None,
    subsweep_idx: int | None = None,
    color_min: float = 0.0,
    color_max: float | None = 3000.0,
    fixed_levels: bool = True,
    cancel_check: Callable[[], bool] | None = None,
) -> LoadedH5ResourcePayload:
    from sparse_iq_heatmap_common import (
        heatmap_frame_rgb,
        load_heatmap_record,
        resolve_selection_indices,
    )

    if cancel_check and cancel_check():
        raise ResourceJobError("H5 load cancelled.")

    (
        resolved_session_idx,
        resolved_group_idx,
        resolved_entry_idx,
        resolved_subsweep_idx,
    ) = resolve_selection_indices(
        h5_path=h5_path,
        session_idx=session_idx,
        group_idx=group_idx,
        entry_idx=entry_idx,
        subsweep_idx=subsweep_idx,
    )
    if cancel_check and cancel_check():
        raise ResourceJobError("H5 load cancelled.")

    record = load_heatmap_record(
        h5_path,
        resolved_session_idx,
        resolved_group_idx,
        resolved_entry_idx,
    )
    if cancel_check and cancel_check():
        record.close()
        raise ResourceJobError("H5 load cancelled.")

    resolved_color_max = color_max
    if fixed_levels:
        from sparse_iq_heatmap_common import fixed_color_level

        resolved_color_max = fixed_color_level(
            color_max=color_max,
            results=record.results,
            subsweep_idx=resolved_subsweep_idx,
            frame_indices=list(range(len(record.results))),
        )

    first_frame = heatmap_frame_rgb(
        record,
        subsweep_idx=resolved_subsweep_idx,
        frame_idx=0,
        color_min=color_min,
        color_max=resolved_color_max,
    )
    metadata = HeatmapTrack(
        path=str(h5_path),
        session_idx=record.session_idx,
        group_idx=record.group_idx,
        entry_idx=record.entry_idx,
        subsweep_idx=resolved_subsweep_idx,
        duration_s=record.duration_s,
        fps=record.fps,
    )
    resolved_level: float | None = None
    if fixed_levels:
        resolved_level = resolved_color_max

    return LoadedH5ResourcePayload(
        path=h5_path,
        record=record,
        subsweep_idx=resolved_subsweep_idx,
        metadata=metadata,
        first_frame_shape=(first_frame.shape[0], first_frame.shape[1]),
        color_min=color_min,
        color_max=color_max,
        fixed_levels=fixed_levels,
        resolved_fixed_color_level=resolved_level,
    )


def build_h5_truth_source_from_payload(payload: LoadedH5ResourcePayload) -> HeatmapTruthSource:
    return HeatmapTruthSource.from_loaded_record(
        payload.record,
        path=payload.path,
        subsweep_idx=payload.subsweep_idx,
        color_min=payload.color_min,
        color_max=payload.color_max,
        fixed_levels=payload.fixed_levels,
        resolved_fixed_color_level=payload.resolved_fixed_color_level,
    )


def release_resource_job_result(kind: ResourceJobKind, result: object) -> None:
    """Release disposable resources held by an ignored or abandoned job result."""

    if kind != "radar_h5" or not isinstance(result, LoadedH5ResourcePayload):
        return
    record = result.record
    close = getattr(record, "close", None)
    if callable(close):
        close()


@dataclass(frozen=True)
class CameraResourceJobResult:
    source_path: Path
    proxy_result: ProxyVideoResult
    camera_track: CameraTrack


def _proxy_temp_path(proxy_path: Path) -> Path:
    return proxy_path.with_name(proxy_path.name + _PROXY_TEMP_SUFFIX)


def _cleanup_proxy_temp(proxy_path: Path) -> None:
    temp_path = _proxy_temp_path(proxy_path)
    if temp_path.exists():
        temp_path.unlink()


def _promote_proxy_temp(proxy_path: Path) -> None:
    temp_path = _proxy_temp_path(proxy_path)
    if not temp_path.exists():
        raise ProxyBuildError("Preview proxy output is missing.")
    proxy_path.parent.mkdir(parents=True, exist_ok=True)
    if proxy_path.exists():
        proxy_path.unlink()
    os.replace(temp_path, proxy_path)


def build_preview_proxy_video(
    source_path: Path,
    *,
    max_dimension: int = 1280,
    cache_root: Path | None = None,
    cancel_check: Callable[[], bool] | None = None,
    process_hook: Callable[[subprocess.Popen[str]], None] | None = None,
) -> ProxyVideoResult:
    source_probe = probe_video(source_path)
    if max(source_probe.width, source_probe.height) <= max_dimension:
        return ProxyVideoResult(
            source_path=source_path,
            display_path=source_path,
            source_probe=source_probe,
            proxy_path=None,
            state="original",
        )

    ffmpeg_path = _find_ffmpeg()
    if ffmpeg_path is None:
        raise ProxyBuildError("ffmpeg was not found; preview proxy generation is required.")

    proxy_path = _proxy_cache_path(
        source_path,
        source_probe=source_probe,
        max_dimension=max_dimension,
        cache_root=cache_root,
    )
    if proxy_path.exists():
        return ProxyVideoResult(
            source_path=source_path,
            display_path=proxy_path,
            source_probe=source_probe,
            proxy_path=proxy_path,
            state="proxy_reused",
        )

    if cancel_check and cancel_check():
        raise ProxyBuildError("Preview proxy generation cancelled.")

    scaled_width, scaled_height = _scaled_video_dimensions(
        source_probe.width,
        source_probe.height,
        max_dimension,
    )
    temp_path = _proxy_temp_path(proxy_path)
    _cleanup_proxy_temp(proxy_path)
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_path,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source_path),
        "-vf",
        f"scale={scaled_width}:{scaled_height}",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        str(temp_path),
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if process_hook is not None:
        process_hook(process)
    try:
        stdout, stderr = process.communicate()
    except Exception:
        process.kill()
        process.communicate()
        _cleanup_proxy_temp(proxy_path)
        raise
    if cancel_check and cancel_check():
        if process.poll() is None:
            process.kill()
            process.communicate()
        _cleanup_proxy_temp(proxy_path)
        raise ProxyBuildError("Preview proxy generation cancelled.")
    if process.returncode != 0:
        _cleanup_proxy_temp(proxy_path)
        detail = (stderr or stdout or "").strip()
        message = "Preview proxy generation failed."
        if detail:
            message = f"{message}\n\n{detail}"
        raise ProxyBuildError(message)
    try:
        _promote_proxy_temp(proxy_path)
    except OSError as exc:
        _cleanup_proxy_temp(proxy_path)
        raise ProxyBuildError(f"Could not finalize preview proxy: {exc}") from exc
    return ProxyVideoResult(
        source_path=source_path,
        display_path=proxy_path,
        source_probe=source_probe,
        proxy_path=proxy_path,
        state="proxy_built",
    )


def run_camera_resource_job(
    camera_path: Path,
    *,
    cache_root: Path | None = None,
    cancel_check: Callable[[], bool] | None = None,
    process_hook: Callable[[subprocess.Popen[str]], None] | None = None,
) -> CameraResourceJobResult:
    if cancel_check and cancel_check():
        raise ResourceJobError("Camera load cancelled.")
    proxy_result = build_preview_proxy_video(
        camera_path,
        cache_root=cache_root,
        cancel_check=cancel_check,
        process_hook=process_hook,
    )
    if proxy_result.state not in ("original", "proxy_reused", "proxy_built"):
        raise ProxyBuildError("Preview proxy is required for this camera video.")
    return CameraResourceJobResult(
        source_path=camera_path,
        proxy_result=proxy_result,
        camera_track=CameraTrack(
            path=str(camera_path),
            fps=proxy_result.source_probe.fps,
            duration_s=proxy_result.source_probe.duration_s,
            frame_count=proxy_result.source_probe.frame_count,
        ),
    )


def _corners_within_bounds(
    corners: np.ndarray,
    width: int,
    height: int,
) -> bool:
    if corners.shape != (4, 2):
        return False
    xs = corners[:, 0]
    ys = corners[:, 1]
    if np.any(xs < 0.0) or np.any(ys < 0.0):
        return False
    if np.any(xs > width - 1) or np.any(ys > height - 1):
        return False
    min_x = float(np.min(xs))
    max_x = float(np.max(xs))
    min_y = float(np.min(ys))
    max_y = float(np.max(ys))
    return (max_x - min_x) >= 8.0 and (max_y - min_y) >= 8.0


def _aspect_ratio(size: tuple[int, int]) -> float:
    width, height = size
    if width <= 0 or height <= 0:
        return 0.0
    return width / height


def resolve_replacement_viewport_corners(
    *,
    existing_corners: list[list[float]] | None,
    previous_native_size: tuple[int, int],
    replacement_native_size: tuple[int, int],
    aspect_ratio_tolerance: float = 0.02,
) -> list[list[float]] | None:
    """Preserve, scale, or reset viewport corners for a camera replacement."""

    if not existing_corners:
        return None

    corners = np.asarray(existing_corners, dtype=np.float32)
    prev_w, prev_h = previous_native_size
    new_w, new_h = replacement_native_size
    if prev_w <= 0 or prev_h <= 0 or new_w <= 0 or new_h <= 0:
        return None

    if (prev_w, prev_h) == (new_w, new_h):
        if _corners_within_bounds(corners, new_w, new_h):
            return corners.tolist()
        return None

    prev_ratio = _aspect_ratio((prev_w, prev_h))
    new_ratio = _aspect_ratio((new_w, new_h))
    if prev_ratio <= 0.0 or new_ratio <= 0.0:
        return None
    if abs(prev_ratio - new_ratio) > aspect_ratio_tolerance:
        return None

    scaled = scale_viewport_corners(
        corners,
        from_size=(prev_w, prev_h),
        to_size=(new_w, new_h),
    )
    if _corners_within_bounds(scaled, new_w, new_h):
        return scaled.tolist()
    return None


def replacement_viewport_needs_default_reset(
    *,
    previous_corners: list[list[float]] | None,
    previous_native_size: tuple[int, int],
    replacement_native_size: tuple[int, int],
) -> bool:
    """Return True when a replacement should reset viewport corners to defaults."""

    if not previous_corners or previous_native_size == (0, 0):
        return False
    return (
        resolve_replacement_viewport_corners(
            existing_corners=previous_corners,
            previous_native_size=previous_native_size,
            replacement_native_size=replacement_native_size,
        )
        is None
    )
