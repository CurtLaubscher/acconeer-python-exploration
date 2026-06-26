from __future__ import annotations

"""Resources-window presentation summaries for the heatmap alignment workbench."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from heatmap_alignment_core import (
    CAMERA_TIMELINE_TRACK_COLOR_HEX,
    H5_TIMELINE_TRACK_COLOR_HEX,
    LEG2_TIMELINE_TRACK_COLOR_HEX,
    AlignmentSession,
)
from heatmap_alignment_resource_jobs import ResourceJobPhase

ResourceKind = Literal["camera", "radar_h5", "radar_peak", "leg2_mat"]
ResourceStatus = Literal["unloaded", "loaded", "missing", "invalid", "warning"]
ResourceAction = Literal[
    "load",
    "replace",
    "unload",
    "reload",
    "reveal",
    "inspect",
    "cancel",
    "generate",
    "save",
    "save_as",
]
@dataclass(frozen=True)
class ResourceSummary:
    """Scan-friendly summary for one heatmap alignment resource slot."""

    kind: ResourceKind
    display_name: str
    role: str
    status: ResourceStatus
    path: str
    color_hex: str | None
    color_muted: bool
    details: str
    messages: tuple[str, ...]
    actions: tuple[ResourceAction, ...]
    job_phase: ResourceJobPhase = "idle"
    job_target_filename: str = ""
    job_detail: str = ""
    job_cancellable: bool = False
    status_label: str = ""
    series_id: str = ""


@dataclass(frozen=True)
class ResourceJobPresentation:
    kind: ResourceKind
    phase: ResourceJobPhase = "idle"
    target_filename: str = ""
    detail: str = ""
    cancellable: bool = False


@dataclass(frozen=True)
class AlignmentResourceRuntime:
    """Runtime load state used when building resource summaries."""

    camera_loaded: bool = False
    radar_h5_loaded: bool = False
    radar_peak_loaded: bool = False
    leg2_loaded: bool = False
    peak_detected_count: int | None = None
    peak_measurement_count: int | None = None
    leg2_valid_segment_count: int | None = None
    leg2_sample_count: int | None = None
    peaks_dirty: bool = False
    reload_errors: tuple[tuple[ResourceKind, str], ...] = ()
    load_warnings: tuple[tuple[ResourceKind, str], ...] = ()
    resource_jobs: tuple[ResourceJobPresentation, ...] = ()


def _resource_job_presentation(
    kind: ResourceKind,
    runtime: AlignmentResourceRuntime,
) -> ResourceJobPresentation | None:
    for entry in runtime.resource_jobs:
        if entry.kind == kind:
            return entry
    return None


def _resource_messages(
    kind: ResourceKind,
    runtime: AlignmentResourceRuntime,
) -> tuple[str, ...]:
    reload_error_texts = [text for key, text in runtime.reload_errors if key == kind]
    messages: list[str] = list(reload_error_texts)
    messages.extend(text for key, text in runtime.load_warnings if key == kind)
    job = _resource_job_presentation(kind, runtime)
    if job is not None and job.phase == "failed" and job.detail:
        if job.detail not in reload_error_texts:
            messages = [job.detail, *messages]
    return tuple(messages)


def _resource_status(
    *,
    path_text: str,
    loaded: bool,
    messages: tuple[str, ...],
    job: ResourceJobPresentation | None = None,
) -> ResourceStatus:
    if job is not None and job.phase not in ("idle", "superseded"):
        if job.phase == "failed":
            return "invalid"
        if job.phase in ("pending", "loading", "building", "waiting", "cancelling"):
            return "warning" if loaded else "unloaded"
    if loaded:
        if messages:
            return "warning"
        return "loaded"
    if not path_text:
        return "unloaded"
    path = Path(path_text)
    if not path.exists():
        return "missing"
    if messages:
        return "invalid"
    return "unloaded"


def _resource_actions(
    *,
    status: ResourceStatus,
    path_text: str,
    can_unload: bool,
    messages: tuple[str, ...],
    job: ResourceJobPresentation | None = None,
) -> tuple[ResourceAction, ...]:
    actions: list[ResourceAction] = []
    if job is not None and job.phase in ("pending", "loading", "building", "waiting", "cancelling"):
        if job.cancellable:
            actions.append("cancel")
        if status in ("loaded", "warning"):
            actions.extend(("replace", "unload"))
        elif path_text:
            actions.append("reload")
        if path_text:
            actions.append("reveal")
        if messages:
            actions.append("inspect")
        deduped: list[ResourceAction] = []
        for action in actions:
            if action not in deduped:
                deduped.append(action)
        return tuple(deduped)

    if status in ("unloaded", "missing", "invalid"):
        actions.append("load")
    elif status in ("loaded", "warning"):
        actions.extend(("replace", "unload"))

    if path_text:
        if status in ("missing", "invalid", "unloaded") or status in ("loaded", "warning"):
            actions.append("reload")
        actions.append("reveal")

    if messages:
        actions.append("inspect")

    if can_unload and "unload" not in actions and status in ("loaded", "warning"):
        actions.append("unload")

    deduped = []
    for action in actions:
        if action not in deduped:
            deduped.append(action)
    return tuple(deduped)


def build_alignment_resource_summaries(
    session: AlignmentSession,
    runtime: AlignmentResourceRuntime,
    peak_series: list | None = None,
) -> tuple[ResourceSummary, ...]:
    """Build fixed-slot resource summaries for the Resources window."""

    summaries: list[ResourceSummary] = []

    camera_path = session.camera_track.path
    camera_job = _resource_job_presentation("camera", runtime)
    camera_messages = _resource_messages("camera", runtime)
    camera_status = _resource_status(
        path_text=camera_path,
        loaded=runtime.camera_loaded,
        messages=camera_messages,
        job=camera_job,
    )
    camera_details = "No camera video loaded."
    if camera_job is not None and camera_job.phase not in ("idle", "superseded"):
        target = camera_job.target_filename or Path(camera_path).name
        if camera_job.phase == "building":
            camera_details = f"Building preview proxy for {target}..."
        elif camera_job.phase == "waiting":
            camera_details = camera_job.detail or f"Waiting for {target}..."
        elif camera_job.phase == "cancelling":
            camera_details = f"Cancelling load for {target}..."
        elif camera_job.phase == "failed":
            camera_details = camera_job.detail or f"Failed to load {target}."
        else:
            camera_details = camera_job.detail or f"Loading {target}..."
    elif runtime.camera_loaded:
        camera_details = (
            f"{session.camera_track.frame_count} frames, "
            f"{session.camera_track.fps:.3f} fps, "
            f"{session.camera_track.duration_s:.3f} s"
        )
    elif camera_path:
        camera_details = "Remembered camera path is not currently loaded."
    summaries.append(
        ResourceSummary(
            kind="camera",
            display_name="Camera Video",
            role="Primary",
            status=camera_status,
            path=camera_path,
            color_hex=CAMERA_TIMELINE_TRACK_COLOR_HEX,
            color_muted=not runtime.camera_loaded,
            details=camera_details,
            messages=camera_messages,
            actions=_resource_actions(
                status=camera_status,
                path_text=camera_path,
                can_unload=runtime.camera_loaded,
                messages=camera_messages,
                job=camera_job,
            ),
            job_phase=camera_job.phase if camera_job is not None else "idle",
            job_target_filename=camera_job.target_filename if camera_job is not None else "",
            job_detail=camera_job.detail if camera_job is not None else "",
            job_cancellable=camera_job.cancellable if camera_job is not None else False,
        )
    )

    h5_path = session.heatmap_track.path
    h5_job = _resource_job_presentation("radar_h5", runtime)
    h5_messages = _resource_messages("radar_h5", runtime)
    h5_status = _resource_status(
        path_text=h5_path,
        loaded=runtime.radar_h5_loaded,
        messages=h5_messages,
        job=h5_job,
    )
    h5_details = "No radar raw H5 recording loaded."
    if h5_job is not None and h5_job.phase not in ("idle", "superseded"):
        target = h5_job.target_filename or Path(h5_path).name
        if h5_job.phase == "cancelling":
            h5_details = f"Cancelling load for {target}..."
        elif h5_job.phase == "waiting":
            h5_details = h5_job.detail or f"Waiting for {target}..."
        elif h5_job.phase == "failed":
            h5_details = h5_job.detail or f"Failed to load {target}."
        else:
            h5_details = h5_job.detail or f"Loading {target}..."
    elif runtime.radar_h5_loaded:
        frame_count = max(
            1,
            int(round(session.heatmap_track.duration_s * max(session.heatmap_track.fps, 0.0))),
        )
        if session.heatmap_track.fps > 0:
            frame_count = int(round(session.heatmap_track.duration_s * session.heatmap_track.fps))
        h5_details = (
            f"{frame_count} frames, "
            f"{session.heatmap_track.fps:.3f} fps, "
            f"{session.heatmap_track.duration_s:.3f} s"
        )
    elif h5_path:
        h5_details = "Remembered H5 path is not currently loaded."
    summaries.append(
        ResourceSummary(
            kind="radar_h5",
            display_name="Radar Raw (H5)",
            role="Primary",
            status=h5_status,
            path=h5_path,
            color_hex=H5_TIMELINE_TRACK_COLOR_HEX,
            color_muted=not runtime.radar_h5_loaded,
            details=h5_details,
            messages=h5_messages,
            actions=_resource_actions(
                status=h5_status,
                path_text=h5_path,
                can_unload=runtime.radar_h5_loaded,
                messages=h5_messages,
                job=h5_job,
            ),
            job_phase=h5_job.phase if h5_job is not None else "idle",
            job_target_filename=h5_job.target_filename if h5_job is not None else "",
            job_detail=h5_job.detail if h5_job is not None else "",
            job_cancellable=h5_job.cancellable if h5_job is not None else False,
        )
    )

    peak_messages = _resource_messages("radar_peak", runtime)
    if peak_series:
        # Emit one ResourceSummary per peak series resource.
        for ps in peak_series:
            ps_actions: list[ResourceAction] = []
            if ps.unsaved:
                ps_actions.append("save")
            ps_actions.extend(["save_as", "unload"])
            if ps.json_path:
                ps_actions.append("reload")
                ps_actions.append("reveal")
            ps_status_label = "Generated (unsaved)" if ps.unsaved else ""
            detected = sum(1 for m in ps.measurements if getattr(m, "status", "") == "detected")
            total = len(ps.measurements)
            if ps.unsaved:
                ps_details = f"{detected}/{total} detected frames (unsaved)"
            elif ps.json_path:
                ps_details = f"{detected}/{total} detected frames"
            else:
                ps_details = f"{detected}/{total} detected frames"
            summaries.append(
                ResourceSummary(
                    kind="radar_peak",
                    display_name=ps.display_name,
                    role="Generated" if ps.provenance == "generated" else "Imported",
                    status="loaded",
                    path=str(ps.json_path) if ps.json_path else "",
                    color_hex=ps.color,
                    color_muted=False,
                    details=ps_details,
                    messages=tuple(ps.warnings) + (peak_messages or ()),
                    actions=tuple(ps_actions),
                    status_label=ps_status_label,
                    series_id=ps.series_id,
                )
            )
    else:
        # Fallback: one aggregate row for tests and the empty-list state.
        peak_actions: list[ResourceAction] = []
        if runtime.radar_h5_loaded:
            peak_actions.append("generate")
        if runtime.radar_peak_loaded:
            if runtime.peaks_dirty:
                peak_actions.append("save")
            peak_actions.append("save_as")
        peak_status_label = ""
        peak_details = "No peak distances generated or loaded."
        if runtime.radar_peak_loaded:
            detected = runtime.peak_detected_count or 0
            total = runtime.peak_measurement_count or 0
            peak_details = f"{detected}/{total} detected frames"
            if runtime.peaks_dirty:
                peak_status_label = "Generated (unsaved)"
                peak_details += " (unsaved)"
        summaries.append(
            ResourceSummary(
                kind="radar_peak",
                display_name="Radar Peak Distances",
                role="Optional signal",
                status="loaded" if runtime.radar_peak_loaded else "unloaded",
                path="",
                color_hex=None,
                color_muted=not runtime.radar_peak_loaded,
                details=peak_details,
                messages=peak_messages,
                actions=tuple(peak_actions),
                status_label=peak_status_label,
            )
        )

    leg2_path = session.leg2_ultrasonic_datasource.path
    leg2_messages = _resource_messages("leg2_mat", runtime)
    leg2_status = _resource_status(
        path_text=leg2_path,
        loaded=runtime.leg2_loaded,
        messages=leg2_messages,
    )
    leg2_details = "No Leg2 MAT loaded."
    if runtime.leg2_loaded and runtime.leg2_sample_count is not None:
        valid = runtime.leg2_valid_segment_count or 0
        total = runtime.leg2_sample_count
        leg2_details = f"{total} samples, {valid}/{total} reliable segments"
    elif leg2_path:
        leg2_details = "Remembered Leg2 MAT path is not currently loaded."
    summaries.append(
        ResourceSummary(
            kind="leg2_mat",
            display_name="Leg2 MAT",
            role="Optional signal",
            status=leg2_status,
            path=leg2_path,
            color_hex=LEG2_TIMELINE_TRACK_COLOR_HEX,
            color_muted=not runtime.leg2_loaded,
            details=leg2_details,
            messages=leg2_messages,
            actions=_resource_actions(
                status=leg2_status,
                path_text=leg2_path,
                can_unload=runtime.leg2_loaded or bool(leg2_path),
                messages=leg2_messages,
            ),
        )
    )

    return tuple(summaries)
