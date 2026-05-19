from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

from sparse_iq_heatmap_common import elapsed_time_seconds  # noqa: E402
from sparse_iq_peak_distance_core import (  # noqa: E402
    DEFAULT_PEAK_THRESHOLD,
    INVALID_PEAK_DISTANCE_JSON_MESSAGE,
    PEAK_DISTANCE_FORMAT,
    PEAK_DISTANCE_VERSION,
    REDUCED_PEAK_DISTANCE_CSV_COLUMNS,
    STATUS_DETECTED,
    STATUS_NO_DETECTION,
    FramePeakMeasurement,
    PeakDistanceExportResult,
    PeakDistanceJsonImportError,
    PeakDistanceMetadata,
    load_peak_distance_json,
    peak_distance_document,
    reduced_measurements_to_dataframe,
    strongest_peak_in_zero_velocity_slice,
    validate_peak_distance_import,
    write_peak_distance_csv,
    write_peak_distance_json,
    zero_velocity_bin_index,
)


def test_zero_velocity_bin_index_chooses_nearest_to_zero() -> None:
    velocities_m_s = np.array([-2.0, -0.5, 0.2, 1.0])
    result = zero_velocity_bin_index(velocities_m_s)
    assert result.bin_index == 2
    assert result.velocity_m_s == pytest.approx(0.2)


def test_strongest_peak_slices_zero_velocity_row_not_distance_column() -> None:
    # Shape is (n_velocities, n_distances). A far hotspot must not be read from a
    # near-distance column when the zero-velocity row is weak there.
    dvm = np.zeros((4, 6), dtype=np.float64)
    dvm[2, 0] = 50.0
    dvm[2, 5] = 900.0
    distances_m = np.array([0.05, 0.10, 0.15, 0.20, 0.25, 1.50])

    _, candidate_peak_distance_m, peak_distance_m, _ = strongest_peak_in_zero_velocity_slice(
        dvm,
        distances_m,
        zero_velocity_bin=2,
        threshold=0.0,
    )

    assert candidate_peak_distance_m == pytest.approx(1.50)
    assert peak_distance_m == pytest.approx(1.50)


def test_strongest_peak_exports_distance_when_above_threshold() -> None:
    dvm = np.zeros((3, 5), dtype=np.float64)
    dvm[1, 3] = 750.0
    distances_m = np.array([0.4, 0.8, 1.2, 1.6, 2.0])

    status, candidate_peak_distance_m, peak_distance_m, peak_strength = (
        strongest_peak_in_zero_velocity_slice(
            dvm,
            distances_m,
            zero_velocity_bin=1,
            threshold=500.0,
        )
    )

    assert status == STATUS_DETECTED
    assert candidate_peak_distance_m == pytest.approx(1.6)
    assert peak_distance_m == pytest.approx(1.6)
    assert peak_strength == pytest.approx(750.0)


def test_strongest_peak_preserves_candidate_when_below_threshold() -> None:
    dvm = np.ones((2, 3), dtype=np.float64) * 100.0
    distances_m = np.array([0.5, 1.0, 1.5])

    status, candidate_peak_distance_m, peak_distance_m, peak_strength = (
        strongest_peak_in_zero_velocity_slice(
            dvm,
            distances_m,
            zero_velocity_bin=0,
            threshold=DEFAULT_PEAK_THRESHOLD,
        )
    )

    assert status == STATUS_NO_DETECTION
    assert candidate_peak_distance_m == pytest.approx(0.5)
    assert peak_distance_m is None
    assert peak_strength == pytest.approx(100.0)


def test_elapsed_time_seconds_uses_first_tick_as_zero() -> None:
    ticks = np.array([100, 150, 200], dtype=np.int64)
    assert elapsed_time_seconds(ticks, ticks_per_second=100, frame_idx=1) == pytest.approx(0.5)


def _sample_export_result() -> PeakDistanceExportResult:
    metadata = PeakDistanceMetadata(
        source_path=str(Path("C:/logs/recording.h5")),
        source_name="recording.h5",
        session_index=0,
        group_index=0,
        entry_index=0,
        sensor_id=1,
        subsweep_index=0,
        source_frame_count=2,
        source_duration_s=0.1,
        ticks_per_second=100,
        threshold=DEFAULT_PEAK_THRESHOLD,
        zero_velocity_bin_index=4,
        zero_velocity_m_s=0.0,
    )
    measurements = (
        FramePeakMeasurement(
            frame_index=0,
            source_tick=10,
            time_s=0.0,
            absolute_time=None,
            status=STATUS_DETECTED,
            peak_distance_m=1.2,
            candidate_peak_distance_m=1.2,
            peak_strength=800.0,
        ),
        FramePeakMeasurement(
            frame_index=1,
            source_tick=20,
            time_s=0.1,
            absolute_time=None,
            status=STATUS_NO_DETECTION,
            peak_distance_m=None,
            candidate_peak_distance_m=0.9,
            peak_strength=120.0,
        ),
    )
    return PeakDistanceExportResult(metadata=metadata, measurements=measurements)


def test_json_roundtrip_preserves_metadata_and_measurements(tmp_path: Path) -> None:
    output_path = tmp_path / "peaks.json"
    result = _sample_export_result()
    write_peak_distance_json(result, output_path)
    loaded = load_peak_distance_json(output_path)

    assert loaded.metadata.source_name == "recording.h5"
    assert loaded.metadata.threshold == pytest.approx(DEFAULT_PEAK_THRESHOLD)
    assert len(loaded.measurements) == 2
    assert loaded.measurements[0].status == STATUS_DETECTED
    assert loaded.measurements[1].peak_distance_m is None
    assert loaded.measurements[1].candidate_peak_distance_m == pytest.approx(0.9)


def test_peak_distance_document_shape() -> None:
    document = peak_distance_document(_sample_export_result())
    assert document["format"] == PEAK_DISTANCE_FORMAT
    assert document["version"] == PEAK_DISTANCE_VERSION
    assert document["metadata"]["sensor_id"] == 1
    assert document["measurements"][1]["absolute_time"] is None
    assert document["measurements"][1]["peak_distance_m"] is None


def test_reduced_csv_has_only_measurement_columns(tmp_path: Path) -> None:
    output_path = tmp_path / "peaks.csv"
    result = _sample_export_result()
    write_peak_distance_csv(result, output_path)
    frame = pd.read_csv(output_path)

    assert list(frame.columns) == list(REDUCED_PEAK_DISTANCE_CSV_COLUMNS)
    assert "source_path" not in frame.columns
    assert "threshold" not in frame.columns
    assert pd.isna(frame.iloc[1]["peak_distance_m"])


def test_write_peak_distance_json_fails_for_invalid_output_path(tmp_path: Path) -> None:
    blocked_path = tmp_path / "blocked.json"
    blocked_path.mkdir()
    with pytest.raises(OSError, match="Could not write peak-distance JSON"):
        write_peak_distance_json(_sample_export_result(), blocked_path)


def test_load_peak_distance_json_rejects_csv_import(tmp_path: Path) -> None:
    csv_path = tmp_path / "peaks.csv"
    csv_path.write_text("frame_index,status\n0,detected\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Reduced CSV peak-distance exports cannot be imported"):
        load_peak_distance_json(csv_path)


def test_validate_peak_distance_import_rejects_frame_count_mismatch(tmp_path: Path) -> None:
    json_path = tmp_path / "peaks.json"
    write_peak_distance_json(_sample_export_result(), json_path)
    datasource = load_peak_distance_json(json_path)

    with pytest.raises(ValueError, match="2 measurements but the loaded"):
        validate_peak_distance_import(
            datasource,
            heatmap_frame_count=3,
            heatmap_duration_s=1.0,
            heatmap_path=Path("recording.h5"),
            session_idx=0,
            group_idx=0,
            entry_idx=0,
            subsweep_idx=0,
            sensor_id=1,
        )


def test_load_peak_distance_json_rejects_unsupported_format(tmp_path: Path) -> None:
    json_path = tmp_path / "peaks.json"
    json_path.write_text(
        json.dumps({"format": "other", "version": 1, "metadata": {}, "measurements": []}),
        encoding="utf-8",
    )
    with pytest.raises(PeakDistanceJsonImportError) as exc_info:
        load_peak_distance_json(json_path)

    error = exc_info.value
    assert error.primary_message == INVALID_PEAK_DISTANCE_JSON_MESSAGE
    assert "The file format is 'other'" in error.detail
    assert error.user_message().startswith(INVALID_PEAK_DISTANCE_JSON_MESSAGE)
    assert "The file format is 'other'" in error.user_message()


def test_load_peak_distance_json_rejects_unrelated_json_without_format_field(
    tmp_path: Path,
) -> None:
    json_path = tmp_path / "session.json"
    json_path.write_text(json.dumps({"name": "alignment", "frames": []}), encoding="utf-8")

    with pytest.raises(PeakDistanceJsonImportError) as exc_info:
        load_peak_distance_json(json_path)

    error = exc_info.value
    assert error.primary_message == INVALID_PEAK_DISTANCE_JSON_MESSAGE
    assert "peak-distances" in error.detail
    assert "None" not in error.detail
    assert "Unsupported format" not in error.detail


def test_load_peak_distance_json_reports_malformed_json_with_user_oriented_message(
    tmp_path: Path,
) -> None:
    json_path = tmp_path / "peaks.json"
    json_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(PeakDistanceJsonImportError) as exc_info:
        load_peak_distance_json(json_path)

    error = exc_info.value
    assert error.primary_message == INVALID_PEAK_DISTANCE_JSON_MESSAGE
    assert error.detail.startswith("JSON parse error:")


def test_reduced_measurements_to_dataframe_uses_stable_column_order() -> None:
    frame = reduced_measurements_to_dataframe(_sample_export_result())
    assert list(frame.columns) == list(REDUCED_PEAK_DISTANCE_CSV_COLUMNS)
