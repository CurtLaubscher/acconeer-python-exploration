"""Thin adapter that isolates peak-distance generation from the main GUI.

This module is the boundary that can be removed to strip peak features from a
generic sync tool.  It contains no Qt imports and is fully testable without a
display.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from sparse_iq_peak_distance_core import (
    DEFAULT_PEAK_THRESHOLD,
    PEAK_ALGORITHM_REGISTRY,
    PEAK_EXTRACTION_METHOD_SUM_VELOCITY,
    STATUS_DETECTED,
    FramePeakMeasurement,
    LoadedPeakDistanceDatasource,
    PeakDistanceExportResult,
    analyze_heatmap_record,
    write_peak_distance_json,
)

PeakDistanceResourceState = PeakDistanceExportResult | LoadedPeakDistanceDatasource

PEAK_SERIES_PALETTE: list[str] = [
    "#3b82f6",
    "#f59e0b",
    "#ec4899",
    "#8b5cf6",
    "#14b8a6",
    "#f97316",
    "#6366f1",
    "#84cc16",
]


@dataclass
class PeakSeriesResource:
    series_id: str
    display_name: str
    provenance: str  # "generated" or "imported"
    measurements: tuple  # tuple[FramePeakMeasurement, ...]
    color: str
    json_path: Path | None = None
    algorithm_id: str | None = None
    algorithm_params: dict = field(default_factory=dict)
    metadata: object = None  # PeakDistanceMetadata | None
    visible: bool = True
    unsaved: bool = False
    warnings: tuple = ()
    heatmap_selected: bool = False


def assign_peak_series_color(existing_series: list[PeakSeriesResource]) -> str:
    """Return the next palette color not already in use by existing_series."""
    used_colors = {s.color for s in existing_series}
    for color in PEAK_SERIES_PALETTE:
        if color not in used_colors:
            return color
    # All palette colors are in use; wrap around to the first one.
    return PEAK_SERIES_PALETTE[0]


def default_generated_name(algorithm_id: str, threshold: float) -> str:
    """Return a human-readable default name for a generated peak series.

    Example: "v0 slice, thresh 650"
    """
    label = PEAK_ALGORITHM_REGISTRY.get(algorithm_id, algorithm_id)
    thresh_int = int(threshold)
    return f"{label}, thresh {thresh_int}"


def default_imported_name(json_path: Path, existing_names: list[str]) -> str:
    """Return a display name derived from the file stem, with a numeric suffix if needed."""
    stem = json_path.stem
    if stem not in existing_names:
        return stem
    counter = 2
    while True:
        candidate = f"{stem} ({counter})"
        if candidate not in existing_names:
            return candidate
        counter += 1


def generate_peak_distances_from_heatmap_record(
    heatmap_record,
    *,
    h5_path: Path,
    subsweep_idx: int,
    threshold: float = DEFAULT_PEAK_THRESHOLD,
    peak_extraction_method: str = PEAK_EXTRACTION_METHOD_SUM_VELOCITY,
) -> PeakDistanceExportResult:
    frame_indices = list(range(len(heatmap_record.results)))
    return analyze_heatmap_record(
        heatmap_record,
        h5_path=h5_path,
        subsweep_idx=subsweep_idx,
        frame_indices=frame_indices,
        threshold=threshold,
        peak_extraction_method=peak_extraction_method,
    )


def active_peak_measurements(state: PeakDistanceResourceState | None):
    if state is None:
        return None
    return state.measurements


def active_peak_zero_velocity_m_s(state: PeakDistanceResourceState | None):
    if state is None:
        return None
    return state.metadata.zero_velocity_m_s


def save_peak_state_to_path(
    state: PeakDistanceResourceState,
    output_path: Path,
) -> LoadedPeakDistanceDatasource:
    """Write canonical JSON and return a LoadedPeakDistanceDatasource for the saved file."""
    if isinstance(state, PeakDistanceExportResult):
        write_peak_distance_json(state, output_path)
        return LoadedPeakDistanceDatasource(
            path=output_path,
            metadata=state.metadata,
            measurements=state.measurements,
        )
    else:
        result = PeakDistanceExportResult(
            metadata=state.metadata,
            measurements=state.measurements,
        )
        write_peak_distance_json(result, output_path)
        return LoadedPeakDistanceDatasource(
            path=output_path,
            metadata=state.metadata,
            measurements=state.measurements,
        )


def peak_state_detected_counts(state: PeakDistanceResourceState | None) -> tuple[int, int] | None:
    if state is None:
        return None
    measurements = state.measurements
    detected = sum(1 for m in measurements if m.status == STATUS_DETECTED)
    return detected, len(measurements)
