from __future__ import annotations


"""H5 resource job payload loading for heatmap alignment."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from heatmap_alignment_core_models import HeatmapTrack
from heatmap_alignment_resource_job_state import ResourceJobError, ResourceJobKind
from heatmap_alignment_sources import HeatmapTruthSource


H5_OWNERSHIP_MODEL = (
    "worker-loaded HeatmapRecord handoff: workers load the H5 off the GUI thread and return "
    "LoadedH5ResourcePayload; the main thread adopts it via HeatmapTruthSource.from_loaded_record "
    "without repeating initialization."
)


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

    try:
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
    except Exception:
        record.close()
        raise


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
