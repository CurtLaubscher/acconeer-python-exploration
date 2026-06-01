"""Unit tests for heatmap_peak_distance_resource adapter (Task 5.1) and
build_alignment_resource_summaries peak-related behaviour (Task 5.2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

from heatmap_alignment_core import (  # noqa: E402
    AlignmentResourceRuntime,
    AlignmentSession,
    build_alignment_resource_summaries,
)
from heatmap_peak_distance_resource import (  # noqa: E402
    active_peak_measurements,
    active_peak_zero_velocity_m_s,
    generate_peak_distances_from_heatmap_record,
    peak_state_detected_counts,
    save_peak_state_to_path,
)
from sparse_iq_peak_distance_core import (  # noqa: E402
    PEAK_DISTANCE_FORMAT,
    STATUS_DETECTED,
    STATUS_NO_DETECTION,
    FramePeakMeasurement,
    LoadedPeakDistanceDatasource,
    PeakDistanceExportResult,
    PeakDistanceMetadata,
)


# ---------------------------------------------------------------------------
# Shared fixture helper
# ---------------------------------------------------------------------------


def _make_export_result() -> PeakDistanceExportResult:
    """Return a PeakDistanceExportResult with 3 frames (2 detected, 1 not)."""
    metadata = PeakDistanceMetadata(
        source_path="/tmp/test.h5",
        source_name="test.h5",
        session_index=0,
        group_index=0,
        entry_index=0,
        sensor_id=1,
        subsweep_index=0,
        source_frame_count=3,
        source_duration_s=0.3,
        ticks_per_second=1000,
        threshold=650.0,
        zero_velocity_bin_index=5,
        zero_velocity_m_s=0.0,
    )
    measurements = (
        FramePeakMeasurement(0, 100, 0.0, None, STATUS_DETECTED, 1.5, 1.5, 700.0),
        FramePeakMeasurement(1, 200, 0.1, None, STATUS_NO_DETECTION, None, 1.6, 300.0),
        FramePeakMeasurement(2, 300, 0.2, None, STATUS_DETECTED, 1.4, 1.4, 750.0),
    )
    return PeakDistanceExportResult(metadata=metadata, measurements=measurements)


def _make_loaded_datasource(path: Path | None = None) -> LoadedPeakDistanceDatasource:
    result = _make_export_result()
    return LoadedPeakDistanceDatasource(
        path=path or Path("/tmp/peaks.json"),
        metadata=result.metadata,
        measurements=result.measurements,
    )


# ---------------------------------------------------------------------------
# Task 5.1 – Adapter tests
# ---------------------------------------------------------------------------


class TestPeakStateDetectedCounts:
    def test_returns_none_when_state_is_none(self) -> None:
        assert peak_state_detected_counts(None) is None

    def test_from_export_result(self) -> None:
        result = _make_export_result()
        counts = peak_state_detected_counts(result)
        assert counts == (2, 3)

    def test_from_loaded_datasource(self) -> None:
        datasource = _make_loaded_datasource()
        counts = peak_state_detected_counts(datasource)
        assert counts == (2, 3)

    def test_all_detected(self) -> None:
        metadata = _make_export_result().metadata
        measurements = (
            FramePeakMeasurement(0, 0, 0.0, None, STATUS_DETECTED, 1.0, 1.0, 700.0),
            FramePeakMeasurement(1, 1, 0.1, None, STATUS_DETECTED, 1.1, 1.1, 800.0),
        )
        result = PeakDistanceExportResult(metadata=metadata, measurements=measurements)
        assert peak_state_detected_counts(result) == (2, 2)

    def test_none_detected(self) -> None:
        metadata = _make_export_result().metadata
        measurements = (
            FramePeakMeasurement(0, 0, 0.0, None, STATUS_NO_DETECTION, None, 1.0, 200.0),
        )
        result = PeakDistanceExportResult(metadata=metadata, measurements=measurements)
        assert peak_state_detected_counts(result) == (0, 1)


class TestActivePeakMeasurements:
    def test_returns_none_when_state_is_none(self) -> None:
        assert active_peak_measurements(None) is None

    def test_from_export_result(self) -> None:
        result = _make_export_result()
        assert active_peak_measurements(result) is result.measurements

    def test_from_loaded_datasource(self) -> None:
        datasource = _make_loaded_datasource()
        assert active_peak_measurements(datasource) is datasource.measurements


class TestActivePeakZeroVelocityMs:
    def test_returns_none_when_state_is_none(self) -> None:
        assert active_peak_zero_velocity_m_s(None) is None

    def test_from_export_result(self) -> None:
        result = _make_export_result()
        assert active_peak_zero_velocity_m_s(result) == pytest.approx(0.0)

    def test_from_loaded_datasource(self) -> None:
        datasource = _make_loaded_datasource()
        assert active_peak_zero_velocity_m_s(datasource) == pytest.approx(0.0)

    def test_reflects_metadata_value(self) -> None:
        result = _make_export_result()
        # Build a version with a non-zero value to confirm it is read from metadata
        meta = PeakDistanceMetadata(
            source_path=result.metadata.source_path,
            source_name=result.metadata.source_name,
            session_index=result.metadata.session_index,
            group_index=result.metadata.group_index,
            entry_index=result.metadata.entry_index,
            sensor_id=result.metadata.sensor_id,
            subsweep_index=result.metadata.subsweep_index,
            source_frame_count=result.metadata.source_frame_count,
            source_duration_s=result.metadata.source_duration_s,
            ticks_per_second=result.metadata.ticks_per_second,
            threshold=result.metadata.threshold,
            zero_velocity_bin_index=result.metadata.zero_velocity_bin_index,
            zero_velocity_m_s=0.15,
        )
        modified = PeakDistanceExportResult(metadata=meta, measurements=result.measurements)
        assert active_peak_zero_velocity_m_s(modified) == pytest.approx(0.15)


class TestSavePeakStateToPath:
    def test_save_export_result_writes_canonical_json(self, tmp_path: Path) -> None:
        result = _make_export_result()
        output_path = tmp_path / "peaks.json"

        save_peak_state_to_path(result, output_path)

        assert output_path.exists()
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload.get("format") == PEAK_DISTANCE_FORMAT

    def test_save_export_result_returns_loaded_datasource(self, tmp_path: Path) -> None:
        result = _make_export_result()
        output_path = tmp_path / "peaks.json"

        loaded = save_peak_state_to_path(result, output_path)

        assert isinstance(loaded, LoadedPeakDistanceDatasource)
        assert loaded.path == output_path

    def test_save_export_result_datasource_preserves_measurements(self, tmp_path: Path) -> None:
        result = _make_export_result()
        output_path = tmp_path / "peaks.json"

        loaded = save_peak_state_to_path(result, output_path)

        assert loaded.measurements == result.measurements

    def test_save_loaded_datasource_writes_canonical_json(self, tmp_path: Path) -> None:
        datasource = _make_loaded_datasource()
        output_path = tmp_path / "resaved.json"

        save_peak_state_to_path(datasource, output_path)

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload.get("format") == PEAK_DISTANCE_FORMAT

    def test_save_loaded_datasource_returns_new_path(self, tmp_path: Path) -> None:
        datasource = _make_loaded_datasource(path=tmp_path / "old.json")
        new_path = tmp_path / "new_location.json"

        result_datasource = save_peak_state_to_path(datasource, new_path)

        assert result_datasource.path == new_path

    def test_save_preserves_metadata(self, tmp_path: Path) -> None:
        result = _make_export_result()
        output_path = tmp_path / "peaks.json"

        loaded = save_peak_state_to_path(result, output_path)

        assert loaded.metadata == result.metadata


# ---------------------------------------------------------------------------
# Task 5.2 – Resource summary tests for radar_peak slot
# ---------------------------------------------------------------------------


def _peak_summary(session: AlignmentSession, runtime: AlignmentResourceRuntime):
    summaries = build_alignment_resource_summaries(session, runtime)
    return next(s for s in summaries if s.kind == "radar_peak")


def test_radar_peak_summary_generated_unsaved_status() -> None:
    """Status label is 'Generated (unsaved)' when peaks_dirty."""
    session = AlignmentSession()
    runtime = AlignmentResourceRuntime(
        radar_h5_loaded=True,
        radar_peak_loaded=True,
        peaks_dirty=True,
        peak_detected_count=2,
        peak_measurement_count=3,
    )
    peak_summary = _peak_summary(session, runtime)

    assert peak_summary.status_label == "Generated (unsaved)"
    assert "generate" in peak_summary.actions
    assert "save" in peak_summary.actions
    assert "save_as" in peak_summary.actions


def test_radar_peak_summary_clean_state() -> None:
    """No status_label override and no save action when peaks are not dirty."""
    session = AlignmentSession()
    runtime = AlignmentResourceRuntime(
        radar_h5_loaded=True,
        radar_peak_loaded=True,
        peaks_dirty=False,
        peak_detected_count=2,
        peak_measurement_count=3,
    )
    peak_summary = _peak_summary(session, runtime)

    assert peak_summary.status_label == ""
    assert "generate" in peak_summary.actions
    assert "save" not in peak_summary.actions
    assert "save_as" in peak_summary.actions


def test_radar_peak_summary_no_h5() -> None:
    """Generate and save_as disabled when H5 not loaded."""
    session = AlignmentSession()
    runtime = AlignmentResourceRuntime(
        radar_h5_loaded=False,
        radar_peak_loaded=False,
    )
    peak_summary = _peak_summary(session, runtime)

    assert "generate" not in peak_summary.actions
    assert "save_as" not in peak_summary.actions


def test_radar_peak_summary_save_as_when_loaded_not_dirty() -> None:
    """Save As enabled when peaks are in memory but not dirty."""
    session = AlignmentSession()
    runtime = AlignmentResourceRuntime(
        radar_h5_loaded=True,
        radar_peak_loaded=True,
        peaks_dirty=False,
    )
    peak_summary = _peak_summary(session, runtime)

    assert "save_as" in peak_summary.actions
    assert "save" not in peak_summary.actions


def test_radar_peak_summary_details_includes_detected_count_when_loaded() -> None:
    """Details string mentions detected/total frame counts when peaks are loaded."""
    session = AlignmentSession()
    runtime = AlignmentResourceRuntime(
        radar_h5_loaded=True,
        radar_peak_loaded=True,
        peaks_dirty=False,
        peak_detected_count=5,
        peak_measurement_count=10,
    )
    peak_summary = _peak_summary(session, runtime)

    assert "5" in peak_summary.details
    assert "10" in peak_summary.details


def test_radar_peak_summary_details_includes_unsaved_suffix_when_dirty() -> None:
    """Details string mentions generated/unsaved status when dirty."""
    session = AlignmentSession()
    runtime = AlignmentResourceRuntime(
        radar_h5_loaded=True,
        radar_peak_loaded=True,
        peaks_dirty=True,
        peak_detected_count=3,
        peak_measurement_count=5,
    )
    peak_summary = _peak_summary(session, runtime)

    assert "unsaved" in peak_summary.details.lower() or "generated" in peak_summary.details.lower()


def test_radar_peak_summary_generate_action_present_when_h5_loaded_and_peaks_not_loaded() -> None:
    """Generate action appears even when no peaks are loaded yet, as long as H5 is ready."""
    session = AlignmentSession()
    runtime = AlignmentResourceRuntime(
        radar_h5_loaded=True,
        radar_peak_loaded=False,
        peaks_dirty=False,
    )
    peak_summary = _peak_summary(session, runtime)

    assert "generate" in peak_summary.actions


def test_radar_peak_summary_kind_is_radar_peak() -> None:
    """Verify the radar_peak slot is always present with the correct kind."""
    summaries = build_alignment_resource_summaries(AlignmentSession(), AlignmentResourceRuntime())
    kinds = [s.kind for s in summaries]
    assert "radar_peak" in kinds


# ---------------------------------------------------------------------------
# Task 5.1 supplement: generate_peak_distances_from_heatmap_record
# ---------------------------------------------------------------------------

class TestGeneratePeakDistancesFromHeatmapRecord:
    """Verify generate_peak_distances_from_heatmap_record delegates correctly."""

    def test_calls_analyze_heatmap_record_with_all_frames_and_default_threshold(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """analyze_heatmap_record is called with all frame indices and threshold 650."""
        import heatmap_peak_distance_resource as adapter_mod

        captured: dict = {}

        def fake_analyze(heatmap_record, *, h5_path, subsweep_idx, frame_indices, threshold):
            captured["frame_indices"] = frame_indices
            captured["threshold"] = threshold
            captured["h5_path"] = h5_path
            captured["subsweep_idx"] = subsweep_idx
            # Return a minimal real result using the real fixture helper
            return _make_export_result()

        monkeypatch.setattr(adapter_mod, "analyze_heatmap_record", fake_analyze)

        class _FakeResult:
            pass

        class _FakeRecord:
            results = [_FakeResult(), _FakeResult(), _FakeResult()]  # 3 frames

        h5_path = tmp_path / "test.h5"
        result = generate_peak_distances_from_heatmap_record(
            _FakeRecord(),
            h5_path=h5_path,
            subsweep_idx=2,
        )

        assert captured["frame_indices"] == [0, 1, 2]
        assert captured["threshold"] == 650.0
        assert captured["h5_path"] == h5_path
        assert captured["subsweep_idx"] == 2
        assert result is not None

    def test_passes_explicit_threshold_override(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An explicit threshold is forwarded to analyze_heatmap_record."""
        import heatmap_peak_distance_resource as adapter_mod

        captured: dict = {}

        def fake_analyze(heatmap_record, *, h5_path, subsweep_idx, frame_indices, threshold):
            captured["threshold"] = threshold
            return _make_export_result()

        monkeypatch.setattr(adapter_mod, "analyze_heatmap_record", fake_analyze)

        class _FakeRecord:
            results = [object()]

        generate_peak_distances_from_heatmap_record(
            _FakeRecord(),
            h5_path=tmp_path / "x.h5",
            subsweep_idx=0,
            threshold=999.0,
        )

        assert captured["threshold"] == 999.0
