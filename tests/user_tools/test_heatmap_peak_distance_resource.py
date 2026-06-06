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

from heatmap_alignment_core import AlignmentSession  # noqa: E402
from heatmap_alignment_resource_summaries import (  # noqa: E402
    AlignmentResourceRuntime,
    build_alignment_resource_summaries,
)
from heatmap_peak_distance_resource import (  # noqa: E402
    PeakSeriesResource,
    PeakSeriesResourceAdapter,
    active_peak_measurements,
    active_peak_zero_velocity_m_s,
    build_generated_peak_series,
    build_imported_peak_series,
    generate_peak_distances_from_heatmap_record,
    peak_state_detected_counts,
    save_peak_state_to_path,
)
from sparse_iq_peak_distance_core import (  # noqa: E402
    PEAK_DISTANCE_FORMAT,
    PEAK_EXTRACTION_METHOD_SUM_VELOCITY,
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
        peak_extraction_method=PEAK_EXTRACTION_METHOD_SUM_VELOCITY,
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
            peak_extraction_method=result.metadata.peak_extraction_method,
            zero_velocity_bin_index=result.metadata.zero_velocity_bin_index,
            zero_velocity_m_s=0.15,
        )
        modified = PeakDistanceExportResult(metadata=meta, measurements=result.measurements)
        assert active_peak_zero_velocity_m_s(modified) == pytest.approx(0.15)


class TestPeakSeriesFactories:
    def test_build_imported_peak_series_sets_saved_imported_fields(self) -> None:
        datasource = _make_loaded_datasource(Path("/tmp/peaks.json"))

        series = build_imported_peak_series(
            datasource,
            Path("/tmp/peaks.json"),
            display_name="Imported",
            existing_series=[],
            color="#f59e0b",
            visible=False,
            heatmap_selected=True,
            warnings=("warning",),
        )

        assert series.provenance == "imported"
        assert series.display_name == "Imported"
        assert series.measurements == datasource.measurements
        assert series.metadata == datasource.metadata
        assert series.color == "#f59e0b"
        assert series.json_path == Path("/tmp/peaks.json")
        assert series.visible is False
        assert series.heatmap_selected is True
        assert series.unsaved is False
        assert series.warnings == ("warning",)
        assert series.series_id

    def test_build_imported_peak_series_assigns_next_color(self) -> None:
        existing = [
            build_imported_peak_series(
                _make_loaded_datasource(),
                Path("/tmp/first.json"),
                display_name="First",
                existing_series=[],
            )
        ]

        series = build_imported_peak_series(
            _make_loaded_datasource(),
            Path("/tmp/second.json"),
            display_name="Second",
            existing_series=existing,
        )

        assert series.color != existing[0].color

    def test_build_generated_peak_series_sets_unsaved_generated_fields(self) -> None:
        result = _make_export_result()

        series = build_generated_peak_series(
            result,
            display_name="Generated",
            algorithm_id=PEAK_EXTRACTION_METHOD_SUM_VELOCITY,
            threshold=650.0,
            existing_series=[],
        )

        assert series.provenance == "generated"
        assert series.display_name == "Generated"
        assert series.measurements == result.measurements
        assert series.metadata == result.metadata
        assert series.algorithm_id == PEAK_EXTRACTION_METHOD_SUM_VELOCITY
        assert series.algorithm_params == {"threshold": 650.0}
        assert series.json_path is None
        assert series.visible is True
        assert series.heatmap_selected is False
        assert series.warnings == ()
        assert series.unsaved is True
        assert series.series_id


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

        def fake_analyze(heatmap_record, *, h5_path, subsweep_idx, frame_indices, threshold, peak_extraction_method=None):
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

        def fake_analyze(heatmap_record, *, h5_path, subsweep_idx, frame_indices, threshold, peak_extraction_method=None):
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


# ---------------------------------------------------------------------------
# add-multi-peak-series: PeakSeriesResource and helpers
# ---------------------------------------------------------------------------

class TestPeakSeriesResource:
    def test_dataclass_defaults(self):
        from heatmap_peak_distance_resource import PeakSeriesResource
        s = PeakSeriesResource(
            series_id="abc", display_name="test", provenance="generated",
            measurements=(), color="#3b82f6"
        )
        assert s.series_id == "abc"
        assert s.visible is True
        assert s.unsaved is False
        assert s.json_path is None
        assert s.algorithm_id is None


class TestPeakSeriesResourceAdapter:
    def test_active_returns_selected_series(self) -> None:
        selected = PeakSeriesResource(
            series_id="selected",
            display_name="selected",
            provenance="imported",
            measurements=(),
            color="#3b82f6",
        )
        other = PeakSeriesResource(
            series_id="other",
            display_name="other",
            provenance="imported",
            measurements=(),
            color="#f59e0b",
        )

        adapter = PeakSeriesResourceAdapter([other, selected], selected_series_id="selected")

        assert adapter.active() is selected

    def test_resolve_target_uses_explicit_then_active_then_unsaved(self) -> None:
        active = PeakSeriesResource(
            series_id="active",
            display_name="active",
            provenance="imported",
            measurements=(),
            color="#3b82f6",
        )
        unsaved = PeakSeriesResource(
            series_id="unsaved",
            display_name="unsaved",
            provenance="generated",
            measurements=(),
            color="#f59e0b",
            unsaved=True,
        )
        explicit = PeakSeriesResource(
            series_id="explicit",
            display_name="explicit",
            provenance="imported",
            measurements=(),
            color="#ec4899",
        )
        adapter = PeakSeriesResourceAdapter(
            [active, unsaved, explicit],
            selected_series_id="active",
        )

        assert adapter.resolve_target("explicit", prefer_unsaved=True) is explicit
        assert adapter.resolve_target(prefer_unsaved=True) is active
        assert (
            PeakSeriesResourceAdapter([active, unsaved]).resolve_target(prefer_unsaved=True)
            is unsaved
        )

    def test_resolve_target_can_fall_back_to_last_or_require_explicit(self) -> None:
        first = PeakSeriesResource(
            series_id="first",
            display_name="first",
            provenance="imported",
            measurements=(),
            color="#3b82f6",
        )
        last = PeakSeriesResource(
            series_id="last",
            display_name="last",
            provenance="imported",
            measurements=(),
            color="#f59e0b",
        )
        adapter = PeakSeriesResourceAdapter([first, last], selected_series_id="first")

        assert adapter.resolve_target(fallback_last=True) is first
        assert (
            adapter.resolve_target(fallback_active=False, fallback_last=False)
            is None
        )
        assert (
            PeakSeriesResourceAdapter([first, last]).resolve_target(fallback_last=True)
            is last
        )

    def test_saved_session_entries_include_saved_rows_only(self) -> None:
        saved = PeakSeriesResource(
            series_id="saved",
            display_name="saved",
            provenance="imported",
            measurements=(),
            color="#3b82f6",
            json_path=Path("/tmp/saved.json"),
            visible=False,
        )
        unsaved = PeakSeriesResource(
            series_id="unsaved",
            display_name="unsaved",
            provenance="generated",
            measurements=(),
            color="#f59e0b",
            unsaved=True,
        )
        adapter = PeakSeriesResourceAdapter([saved, unsaved], selected_series_id="saved")

        entries = adapter.saved_session_entries()

        assert len(entries) == 1
        assert Path(entries[0].path) == Path("/tmp/saved.json")
        assert entries[0].display_name == "saved"
        assert entries[0].visible is False
        assert entries[0].heatmap_selected is True


class TestPeakSeriesHelpers:
    def test_assign_color_empty_list(self):
        from heatmap_peak_distance_resource import PEAK_SERIES_PALETTE, assign_peak_series_color
        assert assign_peak_series_color([]) == PEAK_SERIES_PALETTE[0]

    def test_assign_color_skips_used(self):
        from heatmap_peak_distance_resource import PEAK_SERIES_PALETTE, assign_peak_series_color
        s1 = PeakSeriesResource(series_id="1", display_name="a", provenance="generated", measurements=(), color=PEAK_SERIES_PALETTE[0])
        assert assign_peak_series_color([s1]) == PEAK_SERIES_PALETTE[1]

    def test_default_generated_name_sum_velocity(self):
        from heatmap_peak_distance_resource import default_generated_name
        name = default_generated_name("sum_velocity", 650.0)
        assert "sum v" in name
        assert "650" in name

    def test_default_generated_name_zero_velocity_slice(self):
        from heatmap_peak_distance_resource import default_generated_name
        name = default_generated_name("zero_velocity_slice", 650.0)
        assert "v0 slice" in name
        assert "650" in name

    def test_default_imported_name_basic(self, tmp_path):
        from heatmap_peak_distance_resource import default_imported_name
        p = tmp_path / "my_peaks.json"
        assert default_imported_name(p, []) == "my_peaks"

    def test_default_imported_name_conflict(self, tmp_path):
        from heatmap_peak_distance_resource import default_imported_name
        p = tmp_path / "my_peaks.json"
        name = default_imported_name(p, ["my_peaks"])
        assert name != "my_peaks"
        assert "my_peaks" in name

    def test_assign_color_wraps_around_palette(self):
        """When all palette colors are used, assignment wraps back to first."""
        from heatmap_peak_distance_resource import PeakSeriesResource, PEAK_SERIES_PALETTE, assign_peak_series_color
        existing = [
            PeakSeriesResource(
                series_id=str(i), display_name=f"s{i}", provenance="generated",
                measurements=(), color=PEAK_SERIES_PALETTE[i % len(PEAK_SERIES_PALETTE)]
            )
            for i in range(len(PEAK_SERIES_PALETTE))
        ]
        color = assign_peak_series_color(existing)
        assert color == PEAK_SERIES_PALETTE[0]

    def test_palette_excludes_h5_green(self):
        """H5 green is not in the comparison palette."""
        from heatmap_peak_distance_resource import PEAK_SERIES_PALETTE
        assert "#22c55e" not in PEAK_SERIES_PALETTE

    def test_default_generated_name_threshold_integer_display(self):
        """Threshold is shown as integer when it is a whole number."""
        from heatmap_peak_distance_resource import default_generated_name
        name = default_generated_name("sum_velocity", 650.0)
        assert "650" in name
        assert "650.0" not in name  # should not show decimal for whole number


# ---------------------------------------------------------------------------
# Task 6.3 – Resource summary tests for multi-peak-series behavior
# ---------------------------------------------------------------------------


def test_peak_series_resource_color_assignment_is_stable():
    """assign_peak_series_color returns palette colors deterministically."""
    from heatmap_peak_distance_resource import PeakSeriesResource, PEAK_SERIES_PALETTE, assign_peak_series_color
    c1 = assign_peak_series_color([])
    s1 = PeakSeriesResource(series_id="1", display_name="a", provenance="generated", measurements=(), color=c1)
    c2 = assign_peak_series_color([s1])
    assert c1 != c2
    assert c1 == PEAK_SERIES_PALETTE[0]
    assert c2 == PEAK_SERIES_PALETTE[1]


def test_peak_series_unsaved_flag_per_series():
    """Unsaved state is tracked independently per series."""
    from heatmap_peak_distance_resource import PeakSeriesResource
    s1 = PeakSeriesResource(series_id="1", display_name="a", provenance="generated", measurements=(), color="#3b82f6", unsaved=True)
    s2 = PeakSeriesResource(series_id="2", display_name="b", provenance="imported", measurements=(), color="#f59e0b", unsaved=False)
    assert s1.unsaved is True
    assert s2.unsaved is False
    assert any(s.unsaved for s in [s1, s2])
    assert not all(s.unsaved for s in [s1, s2])


def test_radar_peak_summary_generate_action_requires_h5():
    """'generate' action only appears when H5 is loaded."""
    peak_no_h5 = _peak_summary(AlignmentSession(), AlignmentResourceRuntime(
        radar_h5_loaded=False, radar_peak_loaded=False
    ))
    peak_with_h5 = _peak_summary(AlignmentSession(), AlignmentResourceRuntime(
        radar_h5_loaded=True, radar_peak_loaded=False
    ))
    assert "generate" not in peak_no_h5.actions
    assert "generate" in peak_with_h5.actions


def test_radar_peak_summary_multiple_statuses_no_regression():
    """build_alignment_resource_summaries handles loaded+dirty and loaded+clean correctly."""
    # Loaded + clean (save should not appear; save_as should)
    clean = _peak_summary(AlignmentSession(), AlignmentResourceRuntime(
        radar_peak_loaded=True, peaks_dirty=False,
        peak_detected_count=5, peak_measurement_count=10,
    ))
    assert "save" not in clean.actions
    assert "save_as" in clean.actions
    assert clean.status_label == ""  # no unsaved label when clean

    # Loaded + dirty (both save and save_as appear; status_label set)
    dirty = _peak_summary(AlignmentSession(), AlignmentResourceRuntime(
        radar_peak_loaded=True, peaks_dirty=True,
        peak_detected_count=5, peak_measurement_count=10,
    ))
    assert "save" in dirty.actions
    assert "save_as" in dirty.actions
    assert dirty.status_label == "Generated (unsaved)"
