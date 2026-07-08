from __future__ import annotations


"""Resources-window presentation summaries for the heatmap alignment workbench."""

from dataclasses import dataclass

from heatmap_alignment_core_models import AlignmentSession
from heatmap_alignment_resource_job_state import ResourceJobPhase
from heatmap_alignment_resource_model import (
    ResourceAction,
    ResourceKind,
    ResourceStatus,
)


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
    radar_distance_bin_width_m: float | None = None
    radar_velocity_bin_width_m_s: float | None = None
    peaks_dirty: bool = False
    reload_errors: tuple[tuple[ResourceKind, str], ...] = ()
    load_warnings: tuple[tuple[ResourceKind, str], ...] = ()
    resource_jobs: tuple[ResourceJobPresentation, ...] = ()


def _resource_messages(
    kind: ResourceKind,
    runtime: AlignmentResourceRuntime,
) -> tuple[str, ...]:
    from heatmap_alignment_resource_adapters import _resource_messages as _adapter_messages

    return _adapter_messages(kind, runtime)


def build_alignment_resource_summaries(
    session: AlignmentSession,
    runtime: AlignmentResourceRuntime,
    peak_series: list | None = None,
) -> tuple[ResourceSummary, ...]:
    """Build fixed-slot resource summaries for the Resources window."""

    from heatmap_alignment_resource_adapters import RESOURCE_ADAPTERS

    class _SummaryHost:
        camera_source = object() if runtime.camera_loaded else None
        heatmap_source = object() if runtime.radar_h5_loaded else None
        _peak_series_list = peak_series or []

        def __init__(self, session: AlignmentSession) -> None:
            self.session = session

        def _has_peaks_in_memory(self) -> bool:
            return runtime.radar_peak_loaded

        def _leg2_adapter(self):
            class _Adapter:
                def path_text(self) -> str:
                    return session.leg2_ultrasonic_datasource.path

                def has_path(self) -> bool:
                    return bool(session.leg2_ultrasonic_datasource.path)

                def is_loaded(self) -> bool:
                    return runtime.leg2_loaded

                def can_unload(self) -> bool:
                    return runtime.leg2_loaded or bool(session.leg2_ultrasonic_datasource.path)

            return _Adapter()

    host = _SummaryHost(session)
    summaries: list[ResourceSummary] = []
    for adapter in RESOURCE_ADAPTERS:
        summaries.extend(adapter.build_summaries(host, runtime))
    return tuple(summaries)
