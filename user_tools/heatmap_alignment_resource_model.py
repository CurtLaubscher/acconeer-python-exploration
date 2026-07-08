"""Shared resource model definitions for the heatmap alignment workbench."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from heatmap_alignment_core_models import (
    CAMERA_TIMELINE_TRACK_COLOR_HEX,
    H5_TIMELINE_TRACK_COLOR_HEX,
    LEG2_TIMELINE_TRACK_COLOR_HEX,
)


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
class ResourceDescriptor:
    kind: ResourceKind
    display_name: str
    role: str
    color_hex: str | None = None


CAMERA_RESOURCE = ResourceDescriptor(
    kind="camera",
    display_name="Camera Video",
    role="Primary",
    color_hex=CAMERA_TIMELINE_TRACK_COLOR_HEX,
)
RADAR_H5_RESOURCE = ResourceDescriptor(
    kind="radar_h5",
    display_name="Radar Raw (H5)",
    role="Primary",
    color_hex=H5_TIMELINE_TRACK_COLOR_HEX,
)
RADAR_PEAK_RESOURCE = ResourceDescriptor(
    kind="radar_peak",
    display_name="Radar Peak Distances",
    role="Optional signal",
)
LEG2_MAT_RESOURCE = ResourceDescriptor(
    kind="leg2_mat",
    display_name="Leg2 MAT",
    role="Optional signal",
    color_hex=LEG2_TIMELINE_TRACK_COLOR_HEX,
)

RESOURCE_DESCRIPTORS = (
    CAMERA_RESOURCE,
    RADAR_H5_RESOURCE,
    RADAR_PEAK_RESOURCE,
    LEG2_MAT_RESOURCE,
)
RESOURCE_DESCRIPTOR_BY_KIND = {descriptor.kind: descriptor for descriptor in RESOURCE_DESCRIPTORS}


def resource_descriptor(kind: ResourceKind) -> ResourceDescriptor:
    return RESOURCE_DESCRIPTOR_BY_KIND[kind]
