"""Peak-distance JSON import helpers for heatmap alignment."""

from __future__ import annotations

from pathlib import Path

from heatmap_alignment_sources import HeatmapTruthSource
from sparse_iq_peak_distance_core import (
    LoadedPeakDistanceDatasource,
    analyze_heatmap_record,
    load_peak_distance_json,
    validate_peak_distance_import,
)


def import_peak_distance_json_for_heatmap(
    json_path: Path,
    heatmap_source: HeatmapTruthSource | None = None,
) -> tuple[LoadedPeakDistanceDatasource, list[str]]:
    datasource = load_peak_distance_json(json_path)
    if heatmap_source is None:
        return datasource, []

    warnings = validate_peak_distance_import(
        datasource,
        heatmap_frame_count=len(heatmap_source.record.results),
        heatmap_duration_s=heatmap_source.record.duration_s,
        heatmap_path=heatmap_source.path,
        session_idx=heatmap_source.record.session_idx,
        group_idx=heatmap_source.record.group_idx,
        entry_idx=heatmap_source.record.entry_idx,
        subsweep_idx=heatmap_source.subsweep_idx,
        sensor_id=heatmap_source.record.sensor_id,
    )
    warnings.extend(
        _recompute_missing_peak_detection_ratios(datasource, heatmap_source)
    )
    return datasource, warnings


def _recompute_missing_peak_detection_ratios(
    datasource: LoadedPeakDistanceDatasource,
    heatmap_source: HeatmapTruthSource,
) -> list[str]:
    missing = [m for m in datasource.measurements if len(m.detection_ratio) == 0]
    if not missing:
        return []

    metadata = datasource.metadata
    recomputed = analyze_heatmap_record(
        heatmap_source.record,
        h5_path=heatmap_source.path,
        subsweep_idx=heatmap_source.subsweep_idx,
        frame_indices=[m.frame_index for m in missing],
        threshold=metadata.threshold,
        peak_extraction_method=metadata.peak_extraction_method,
        threshold_max=metadata.threshold_max,
        threshold_min=metadata.threshold_min,
        reference_distance_m=metadata.reference_distance_m,
    )
    ratios_by_frame = {
        measurement.frame_index: measurement.detection_ratio
        for measurement in recomputed.measurements
    }
    for measurement in missing:
        ratio = ratios_by_frame.get(measurement.frame_index)
        if ratio is not None:
            measurement.detection_ratio = ratio

    return [
        (
            "Peak-distance JSON did not include detection-ratio strip data; "
            "recomputed ratios from the loaded H5 recording."
        )
    ]
