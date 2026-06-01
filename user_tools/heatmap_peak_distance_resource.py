"""Thin adapter that isolates peak-distance generation from the main GUI.

This module is the boundary that can be removed to strip peak features from a
generic sync tool.  It contains no Qt imports and is fully testable without a
display.
"""

from __future__ import annotations

from pathlib import Path

from sparse_iq_peak_distance_core import (
    DEFAULT_PEAK_THRESHOLD,
    STATUS_DETECTED,
    LoadedPeakDistanceDatasource,
    PeakDistanceExportResult,
    analyze_heatmap_record,
    write_peak_distance_json,
)

PeakDistanceResourceState = PeakDistanceExportResult | LoadedPeakDistanceDatasource


def generate_peak_distances_from_heatmap_record(
    heatmap_record,
    *,
    h5_path: Path,
    subsweep_idx: int,
    threshold: float = DEFAULT_PEAK_THRESHOLD,
) -> PeakDistanceExportResult:
    frame_indices = list(range(len(heatmap_record.results)))
    return analyze_heatmap_record(
        heatmap_record,
        h5_path=h5_path,
        subsweep_idx=subsweep_idx,
        frame_indices=frame_indices,
        threshold=threshold,
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
