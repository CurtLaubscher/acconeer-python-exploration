"""Fixed resource adapters for the heatmap alignment workbench."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from heatmap_alignment_resource_actions import resource_path_for_kind
from heatmap_alignment_resource_model import (
    CAMERA_RESOURCE,
    LEG2_MAT_RESOURCE,
    RADAR_H5_RESOURCE,
    RADAR_PEAK_RESOURCE,
    ResourceDescriptor,
    ResourceKind,
)


if TYPE_CHECKING:
    from heatmap_alignment_resource_summaries import AlignmentResourceRuntime, ResourceSummary


class ResourceAdapter(Protocol):
    descriptor: ResourceDescriptor

    @property
    def kind(self) -> ResourceKind: ...

    def path_text(self, host: Any) -> str: ...
    def has_path(self, host: Any) -> bool: ...
    def is_loaded(self, host: Any) -> bool: ...
    def can_unload(self, host: Any) -> bool: ...
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

    def build_summaries(
        self,
        host: Any,
        runtime: AlignmentResourceRuntime,
    ) -> tuple[ResourceSummary, ...]:
        del host, runtime
        return ()


class CameraResourceAdapter(_BaseResourceAdapter):
    descriptor = CAMERA_RESOURCE

    def path_text(self, host: Any) -> str:
        return host.session.camera_track.path

    def is_loaded(self, host: Any) -> bool:
        return host.camera_source is not None


class RadarH5ResourceAdapter(_BaseResourceAdapter):
    descriptor = RADAR_H5_RESOURCE

    def path_text(self, host: Any) -> str:
        return host.session.heatmap_track.path

    def is_loaded(self, host: Any) -> bool:
        return host.heatmap_source is not None


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
