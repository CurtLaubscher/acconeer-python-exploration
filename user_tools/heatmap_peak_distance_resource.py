"""Thin adapter that isolates peak-distance generation from the main GUI.

This module is the boundary that can be removed to strip peak features from a
generic sync tool.  It contains no Qt imports and is fully testable without a
display.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Sequence
from uuid import uuid4

from heatmap_alignment_core import PeakSeriesSessionEntry
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


@dataclass(frozen=True)
class PeakSeriesResourceAdapter:
    """Qt-free adapter for peak-series rows and selection semantics."""

    series: Sequence[PeakSeriesResource]
    selected_series_id: str = ""

    def active(self) -> PeakSeriesResource | None:
        if not self.selected_series_id:
            return None
        return next((s for s in self.series if s.series_id == self.selected_series_id), None)

    def resolve_target(
        self,
        series_id: str = "",
        *,
        prefer_unsaved: bool = False,
        fallback_last: bool = False,
        fallback_active: bool = True,
    ) -> PeakSeriesResource | None:
        """Resolve a row-scoped action target from id, selection, or fallback policy."""
        if series_id:
            target = next((s for s in self.series if s.series_id == series_id), None)
            if target is not None:
                return target
            # Preserve GUI behavior: stale row ids are non-fatal and may fall
            # through to the current selection or action-specific default.
        if fallback_active:
            target = self.active()
            if target is not None:
                return target
        if prefer_unsaved:
            target = next((s for s in self.series if s.unsaved), None)
            if target is not None:
                return target
        if fallback_last and self.series:
            return self.series[-1]
        return None

    def has_rows(self) -> bool:
        return bool(self.series)

    def any_unsaved(self) -> bool:
        return any(s.unsaved for s in self.series)

    def saved_session_entries(self) -> list[PeakSeriesSessionEntry]:
        return [
            PeakSeriesSessionEntry(
                path=str(s.json_path),
                display_name=s.display_name,
                color=s.color,
                visible=s.visible,
                heatmap_selected=s.series_id == self.selected_series_id,
            )
            for s in self.series
            if s.json_path is not None
        ]


def assign_peak_series_color(existing_series: list[PeakSeriesResource]) -> str:
    """Return the next palette color not already in use by existing_series."""
    used_colors = {s.color for s in existing_series}
    for color in PEAK_SERIES_PALETTE:
        if color not in used_colors:
            return color
    # All palette colors are in use; wrap around to the first one.
    return PEAK_SERIES_PALETTE[0]


def build_imported_peak_series(
    datasource: LoadedPeakDistanceDatasource,
    json_path: Path,
    *,
    display_name: str,
    existing_series: list[PeakSeriesResource],
    color: str | None = None,
    visible: bool = True,
    heatmap_selected: bool = False,
    warnings: tuple[str, ...] = (),
) -> PeakSeriesResource:
    """Create a runtime peak-series row from a saved JSON datasource."""
    return PeakSeriesResource(
        series_id=str(uuid4()),
        display_name=display_name,
        provenance="imported",
        measurements=datasource.measurements,
        metadata=datasource.metadata,
        color=color or assign_peak_series_color(existing_series),
        json_path=json_path,
        visible=visible,
        heatmap_selected=heatmap_selected,
        unsaved=False,
        warnings=warnings,
    )


def build_generated_peak_series(
    result: PeakDistanceExportResult,
    *,
    display_name: str,
    algorithm_id: str,
    threshold: float,
    existing_series: list[PeakSeriesResource],
) -> PeakSeriesResource:
    """Create an unsaved runtime peak-series row from generated measurements."""
    return PeakSeriesResource(
        series_id=str(uuid4()),
        display_name=display_name,
        provenance="generated",
        measurements=result.measurements,
        metadata=result.metadata,
        algorithm_id=algorithm_id,
        algorithm_params={"threshold": threshold},
        color=assign_peak_series_color(existing_series),
        unsaved=True,
    )


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
