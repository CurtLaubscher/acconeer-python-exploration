"""Fixed resource adapters for the heatmap alignment workbench."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from heatmap_alignment_resource_actions import resource_path_for_kind
from heatmap_alignment_resource_model import (
    CAMERA_RESOURCE,
    LEG2_MAT_RESOURCE,
    RADAR_H5_RESOURCE,
    RADAR_PEAK_RESOURCE,
    ResourceAction,
    ResourceDescriptor,
    ResourceKind,
    ResourceStatus,
)


if TYPE_CHECKING:
    from heatmap_alignment_resource_summaries import (
        AlignmentResourceRuntime,
        ResourceJobPresentation,
        ResourceSummary,
    )


class ResourceAdapter(Protocol):
    descriptor: ResourceDescriptor

    @property
    def kind(self) -> ResourceKind: ...

    def path_text(self, host: Any) -> str: ...
    def has_path(self, host: Any) -> bool: ...
    def is_loaded(self, host: Any) -> bool: ...
    def can_unload(self, host: Any) -> bool: ...
    def reveal_path_text(self, host: Any, *, series_id: str = "") -> str: ...
    def invoke_action(
        self,
        coordinator: Any,
        host: Any,
        action: ResourceAction,
        *,
        series_id: str = "",
    ) -> bool: ...
    def build_summaries(
        self,
        host: Any,
        runtime: AlignmentResourceRuntime,
    ) -> tuple[ResourceSummary, ...]: ...


class _BaseResourceAdapter:
    descriptor: ResourceDescriptor

    @property
    def kind(self) -> ResourceKind:
        return self.descriptor.kind

    def has_path(self, host: Any) -> bool:
        return bool(self.path_text(host))

    def can_unload(self, host: Any) -> bool:
        return self.is_loaded(host)

    def reveal_path_text(self, host: Any, *, series_id: str = "") -> str:
        del series_id
        return self.path_text(host)

    def invoke_action(
        self,
        coordinator: Any,
        host: Any,
        action: ResourceAction,
        *,
        series_id: str = "",
    ) -> bool:
        del series_id
        if action in ("load", "replace"):
            self.load(host)
            return True
        if action == "unload":
            self.unload(host)
            return True
        if action == "reload":
            self.reload(coordinator, host)
            return True
        return False

    def load(self, host: Any) -> None:
        del host

    def unload(self, host: Any) -> None:
        del host

    def reload(self, coordinator: Any, host: Any) -> None:
        path_text = self.path_text(host)
        if not path_text:
            return
        path = Path(path_text)
        if not path.exists():
            coordinator.set_reload_error(self.kind, f"File not found: {path}")
            coordinator.refresh_resources_ui()
            return
        coordinator.set_reload_error(self.kind, None)
        self.load_from_path(host, path)

    def load_from_path(self, host: Any, path: Path) -> None:
        del host, path

    def build_summaries(
        self,
        host: Any,
        runtime: AlignmentResourceRuntime,
    ) -> tuple[ResourceSummary, ...]:
        del host, runtime
        return ()


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
    if job is not None and job.phase in (
        "pending",
        "loading",
        "building",
        "waiting",
        "cancelling",
    ):
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


class CameraResourceAdapter(_BaseResourceAdapter):
    descriptor = CAMERA_RESOURCE

    def path_text(self, host: Any) -> str:
        return host.session.camera_track.path

    def is_loaded(self, host: Any) -> bool:
        return host.camera_source is not None

    def invoke_action(
        self,
        coordinator: Any,
        host: Any,
        action: ResourceAction,
        *,
        series_id: str = "",
    ) -> bool:
        if action == "cancel":
            if host._resource_job_manager.cancel_job(self.kind):
                host._handle_resource_job_state_changed()
            return True
        return super().invoke_action(coordinator, host, action, series_id=series_id)

    def load(self, host: Any) -> None:
        host._load_camera_video()

    def unload(self, host: Any) -> None:
        host.unload_camera_video()

    def load_from_path(self, host: Any, path: Path) -> None:
        host.load_camera_from_path(path)

    def build_summaries(
        self,
        host: Any,
        runtime: AlignmentResourceRuntime,
    ) -> tuple[ResourceSummary, ...]:
        from heatmap_alignment_resource_summaries import ResourceSummary

        descriptor = self.descriptor
        path_text = self.path_text(host)
        camera_job = _resource_job_presentation("camera", runtime)
        camera_messages = _resource_messages("camera", runtime)
        camera_status = _resource_status(
            path_text=path_text,
            loaded=runtime.camera_loaded,
            messages=camera_messages,
            job=camera_job,
        )
        camera_details = "No camera video loaded."
        if camera_job is not None and camera_job.phase not in ("idle", "superseded"):
            target = camera_job.target_filename or Path(path_text).name
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
                f"{host.session.camera_track.frame_count} frames, "
                f"{host.session.camera_track.fps:.3f} fps, "
                f"{host.session.camera_track.duration_s:.3f} s"
            )
        elif path_text:
            camera_details = "Remembered camera path is not currently loaded."

        return (
            ResourceSummary(
                kind=descriptor.kind,
                display_name=descriptor.display_name,
                role=descriptor.role,
                status=camera_status,
                path=path_text,
                color_hex=descriptor.color_hex,
                color_muted=not runtime.camera_loaded,
                details=camera_details,
                messages=camera_messages,
                actions=_resource_actions(
                    status=camera_status,
                    path_text=path_text,
                    can_unload=runtime.camera_loaded,
                    messages=camera_messages,
                    job=camera_job,
                ),
                job_phase=camera_job.phase if camera_job is not None else "idle",
                job_target_filename=camera_job.target_filename if camera_job is not None else "",
                job_detail=camera_job.detail if camera_job is not None else "",
                job_cancellable=camera_job.cancellable if camera_job is not None else False,
            ),
        )


class RadarH5ResourceAdapter(_BaseResourceAdapter):
    descriptor = RADAR_H5_RESOURCE

    def path_text(self, host: Any) -> str:
        return host.session.heatmap_track.path

    def is_loaded(self, host: Any) -> bool:
        return host.heatmap_source is not None

    def invoke_action(
        self,
        coordinator: Any,
        host: Any,
        action: ResourceAction,
        *,
        series_id: str = "",
    ) -> bool:
        if action == "cancel":
            if host._resource_job_manager.cancel_job(self.kind):
                host._handle_resource_job_state_changed()
            return True
        return super().invoke_action(coordinator, host, action, series_id=series_id)

    def load(self, host: Any) -> None:
        host._load_h5_recording()

    def unload(self, host: Any) -> None:
        host.unload_h5_recording()

    def load_from_path(self, host: Any, path: Path) -> None:
        host.load_h5_from_path(path)

    def build_summaries(
        self,
        host: Any,
        runtime: AlignmentResourceRuntime,
    ) -> tuple[ResourceSummary, ...]:
        from heatmap_alignment_resource_summaries import ResourceSummary

        descriptor = self.descriptor
        path_text = self.path_text(host)
        h5_job = _resource_job_presentation("radar_h5", runtime)
        h5_messages = _resource_messages("radar_h5", runtime)
        h5_status = _resource_status(
            path_text=path_text,
            loaded=runtime.radar_h5_loaded,
            messages=h5_messages,
            job=h5_job,
        )
        h5_details = "No radar raw H5 recording loaded."
        if h5_job is not None and h5_job.phase not in ("idle", "superseded"):
            target = h5_job.target_filename or Path(path_text).name
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
                int(
                    round(
                        host.session.heatmap_track.duration_s
                        * max(host.session.heatmap_track.fps, 0.0)
                    )
                ),
            )
            if host.session.heatmap_track.fps > 0:
                frame_count = int(
                    round(host.session.heatmap_track.duration_s * host.session.heatmap_track.fps)
                )
            h5_details = (
                f"{frame_count} frames, "
                f"{host.session.heatmap_track.fps:.3f} fps, "
                f"{host.session.heatmap_track.duration_s:.3f} s"
            )
            bin_details: list[str] = []
            if runtime.radar_distance_bin_width_m is not None:
                bin_details.append(f"distance bin {runtime.radar_distance_bin_width_m:.6g} m")
            if runtime.radar_velocity_bin_width_m_s is not None:
                bin_details.append(f"velocity bin {runtime.radar_velocity_bin_width_m_s:.6g} m/s")
            if bin_details:
                h5_details = f"{h5_details}\n{', '.join(bin_details)}"
        elif path_text:
            h5_details = "Remembered H5 path is not currently loaded."

        return (
            ResourceSummary(
                kind=descriptor.kind,
                display_name=descriptor.display_name,
                role=descriptor.role,
                status=h5_status,
                path=path_text,
                color_hex=descriptor.color_hex,
                color_muted=not runtime.radar_h5_loaded,
                details=h5_details,
                messages=h5_messages,
                actions=_resource_actions(
                    status=h5_status,
                    path_text=path_text,
                    can_unload=runtime.radar_h5_loaded,
                    messages=h5_messages,
                    job=h5_job,
                ),
                job_phase=h5_job.phase if h5_job is not None else "idle",
                job_target_filename=h5_job.target_filename if h5_job is not None else "",
                job_detail=h5_job.detail if h5_job is not None else "",
                job_cancellable=h5_job.cancellable if h5_job is not None else False,
            ),
        )


class RadarPeakResourceAdapter(_BaseResourceAdapter):
    descriptor = RADAR_PEAK_RESOURCE

    def path_text(self, host: Any) -> str:
        return resource_path_for_kind(
            host.session,
            self.kind,
            peak_series=host._peak_series_list,
        )

    def has_path(self, host: Any) -> bool:
        return bool(host._peak_series_list) or bool(
            any(entry.path for entry in host.session.peak_series)
        )

    def is_loaded(self, host: Any) -> bool:
        return host._has_peaks_in_memory()

    def can_unload(self, host: Any) -> bool:
        return self.is_loaded(host) or self.has_path(host)

    def reveal_path_text(self, host: Any, *, series_id: str = "") -> str:
        if series_id:
            peak_series = host._resolve_peak_series_target(
                series_id,
                fallback_active=False,
                fallback_last=False,
            )
            if peak_series and peak_series.json_path:
                return str(peak_series.json_path)
            return ""
        return self.path_text(host)

    def invoke_action(
        self,
        coordinator: Any,
        host: Any,
        action: ResourceAction,
        *,
        series_id: str = "",
    ) -> bool:
        if action == "generate":
            host._generate_peak_series()
            return True
        if action == "save":
            target = host._resolve_peak_series_target(series_id, prefer_unsaved=True)
            if target is not None:
                host._save_peak_series(target.series_id)
            return True
        if action == "save_as":
            target = host._resolve_peak_series_target(series_id, fallback_last=True)
            if target is not None:
                host._save_peak_series_as(target.series_id)
            return True
        if action in ("load", "replace"):
            host._import_peak_series()
            return True
        if action == "unload":
            target = host._resolve_peak_series_target(series_id, fallback_last=True)
            if target is not None:
                host._unload_peak_series(target.series_id)
            return True
        if action == "reload":
            if series_id:
                host._reload_peak_series(series_id)
            else:
                self.reload(coordinator, host)
            return True
        return False

    def reload(self, coordinator: Any, host: Any) -> None:
        path_text = self.path_text(host)
        if not path_text:
            return
        path = Path(path_text)
        if not path.exists():
            coordinator.set_reload_error(self.kind, f"File not found: {path}")
            coordinator.refresh_resources_ui()
            return
        coordinator.set_reload_error(self.kind, None)
        if host._any_peaks_unsaved() and not host._confirm_action_dialog(
            title="Reload peak series",
            question="Reload saved peak series from disk?",
            informative="Unsaved generated peak data will be lost.",
            accept_label="Reload",
        ):
            return
        host._reload_peak_series_from_session()

    def build_summaries(
        self,
        host: Any,
        runtime: AlignmentResourceRuntime,
    ) -> tuple[ResourceSummary, ...]:
        from heatmap_alignment_resource_summaries import ResourceSummary

        descriptor = self.descriptor
        peak_series = host._peak_series_list or None
        peak_messages = _resource_messages("radar_peak", runtime)
        if peak_series:
            summaries: list[ResourceSummary] = []
            for ps in peak_series:
                ps_actions: list[ResourceAction] = []
                if ps.unsaved:
                    ps_actions.append("save")
                ps_actions.extend(["save_as", "unload"])
                if ps.json_path:
                    ps_actions.append("reload")
                    ps_actions.append("reveal")
                ps_status_label = "Generated (unsaved)" if ps.unsaved else ""
                detected = sum(
                    1 for m in ps.measurements if getattr(m, "status", "") == "detected"
                )
                total = len(ps.measurements)
                if ps.unsaved:
                    ps_details = f"{detected}/{total} detected frames (unsaved)"
                elif ps.json_path:
                    ps_details = f"{detected}/{total} detected frames"
                else:
                    ps_details = f"{detected}/{total} detected frames"
                summaries.append(
                    ResourceSummary(
                        kind=descriptor.kind,
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
            return tuple(summaries)

        peak_actions: list[ResourceAction] = ["load"]
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
        return (
            ResourceSummary(
                kind=descriptor.kind,
                display_name=descriptor.display_name,
                role=descriptor.role,
                status="loaded" if runtime.radar_peak_loaded else "unloaded",
                path="",
                color_hex=descriptor.color_hex,
                color_muted=not runtime.radar_peak_loaded,
                details=peak_details,
                messages=peak_messages,
                actions=tuple(peak_actions),
                status_label=peak_status_label,
            ),
        )


class Leg2MatResourceAdapter(_BaseResourceAdapter):
    descriptor = LEG2_MAT_RESOURCE

    def path_text(self, host: Any) -> str:
        return host._leg2_adapter().path_text()

    def has_path(self, host: Any) -> bool:
        return host._leg2_adapter().has_path()

    def is_loaded(self, host: Any) -> bool:
        return host._leg2_adapter().is_loaded()

    def can_unload(self, host: Any) -> bool:
        return host._leg2_adapter().can_unload()

    def load(self, host: Any) -> None:
        host._import_leg2_mat()

    def unload(self, host: Any) -> None:
        host._clear_leg2_ultrasonic_datasource()

    def load_from_path(self, host: Any, path: Path) -> None:
        host.load_leg2_mat_from_path(path, show_dialogs=True)

    def build_summaries(
        self,
        host: Any,
        runtime: AlignmentResourceRuntime,
    ) -> tuple[ResourceSummary, ...]:
        from heatmap_alignment_resource_summaries import ResourceSummary

        descriptor = self.descriptor
        path_text = self.path_text(host)
        leg2_messages = _resource_messages("leg2_mat", runtime)
        leg2_status = _resource_status(
            path_text=path_text,
            loaded=runtime.leg2_loaded,
            messages=leg2_messages,
        )
        leg2_details = "No Leg2 MAT loaded."
        if runtime.leg2_loaded and runtime.leg2_sample_count is not None:
            valid = runtime.leg2_valid_segment_count or 0
            total = runtime.leg2_sample_count
            leg2_details = f"{total} samples, {valid}/{total} reliable segments"
        elif path_text:
            leg2_details = "Remembered Leg2 MAT path is not currently loaded."

        return (
            ResourceSummary(
                kind=descriptor.kind,
                display_name=descriptor.display_name,
                role=descriptor.role,
                status=leg2_status,
                path=path_text,
                color_hex=descriptor.color_hex,
                color_muted=not runtime.leg2_loaded,
                details=leg2_details,
                messages=leg2_messages,
                actions=_resource_actions(
                    status=leg2_status,
                    path_text=path_text,
                    can_unload=runtime.leg2_loaded or bool(path_text),
                    messages=leg2_messages,
                ),
            ),
        )


CAMERA_ADAPTER = CameraResourceAdapter()
RADAR_H5_ADAPTER = RadarH5ResourceAdapter()
RADAR_PEAK_ADAPTER = RadarPeakResourceAdapter()
LEG2_MAT_ADAPTER = Leg2MatResourceAdapter()

RESOURCE_ADAPTERS: tuple[ResourceAdapter, ...] = (
    CAMERA_ADAPTER,
    RADAR_H5_ADAPTER,
    RADAR_PEAK_ADAPTER,
    LEG2_MAT_ADAPTER,
)
RESOURCE_ADAPTER_BY_KIND: dict[ResourceKind, ResourceAdapter] = {
    adapter.kind: adapter for adapter in RESOURCE_ADAPTERS
}


def resource_adapter(kind: ResourceKind) -> ResourceAdapter:
    return RESOURCE_ADAPTER_BY_KIND[kind]
