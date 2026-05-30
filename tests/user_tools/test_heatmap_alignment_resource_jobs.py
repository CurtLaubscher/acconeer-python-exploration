from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

from heatmap_alignment_resource_jobs import (  # noqa: E402
    LoadedH5ResourcePayload,
    ProxyBuildError,
    ResourceJobBoard,
    begin_resource_job,
    build_h5_truth_source_from_payload,
    build_preview_proxy_video,
    complete_resource_job,
    release_resource_job_result,
    replacement_viewport_needs_default_reset,
    request_cancel_resource_job,
    resolve_replacement_viewport_corners,
    resource_job_blocks_export,
    should_apply_job_result,
)
from heatmap_alignment_core import (  # noqa: E402
    HeatmapTrack,
    HeatmapTruthSource,
    VideoProbe,
    _proxy_cache_path,
    prepare_proxy_video,
)


def test_begin_resource_job_supersedes_pending_generation() -> None:
    board = ResourceJobBoard()
    first = begin_resource_job(
        board,
        "camera",
        target_path=Path("first.mp4"),
        replaces_active=False,
    )
    second = begin_resource_job(
        board,
        "camera",
        target_path=Path("second.mp4"),
        replaces_active=False,
    )

    assert first == 1
    assert second == 2
    assert board.camera.phase == "pending"
    assert board.camera.target_path == Path("second.mp4")


def test_should_apply_job_result_ignores_cancelled_generation() -> None:
    board = ResourceJobBoard()
    generation = begin_resource_job(
        board,
        "radar_h5",
        target_path=Path("trial.h5"),
        replaces_active=True,
    )
    request_cancel_resource_job(board, "radar_h5")

    assert should_apply_job_result(board.radar_h5, generation) is False


def test_should_apply_job_result_ignores_stale_generation() -> None:
    board = ResourceJobBoard()
    generation = begin_resource_job(
        board,
        "radar_h5",
        target_path=Path("trial.h5"),
        replaces_active=True,
    )
    board.radar_h5.generation = generation + 1
    board.radar_h5.phase = "pending"

    assert should_apply_job_result(board.radar_h5, generation) is False


def test_resource_job_blocks_export_while_pending() -> None:
    board = ResourceJobBoard()
    begin_resource_job(
        board,
        "camera",
        target_path=Path("trial.mp4"),
        replaces_active=False,
    )

    assert resource_job_blocks_export(board) is True

    complete_resource_job(board, "camera", board.camera.generation, phase="idle")
    assert resource_job_blocks_export(board) is False


def test_resource_job_blocks_export_ignores_failed_phase() -> None:
    board = ResourceJobBoard()
    begin_resource_job(
        board,
        "camera",
        target_path=Path("trial.mp4"),
        replaces_active=True,
    )
    complete_resource_job(
        board,
        "camera",
        board.camera.generation,
        phase="failed",
        message="Camera load failed.",
    )
    begin_resource_job(
        board,
        "radar_h5",
        target_path=Path("trial.h5"),
        replaces_active=True,
    )
    complete_resource_job(
        board,
        "radar_h5",
        board.radar_h5.generation,
        phase="failed",
        message="H5 load failed.",
    )

    assert resource_job_blocks_export(board) is False


def test_load_h5_resource_payload_closes_record_when_render_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from heatmap_alignment_resource_jobs import load_h5_resource_payload

    class _FakeRecord:
        def __init__(self) -> None:
            self.closed = False
            self.session_idx = 0
            self.group_idx = 0
            self.entry_idx = 0
            self.duration_s = 1.0
            self.fps = 10.0
            self.results = []

        def close(self) -> None:
            self.closed = True

    record = _FakeRecord()
    h5_path = tmp_path / "trial.h5"
    h5_path.write_bytes(b"")

    monkeypatch.setattr(
        "sparse_iq_heatmap_common.resolve_selection_indices",
        lambda **kwargs: (0, 0, 0, 0),
    )
    monkeypatch.setattr(
        "sparse_iq_heatmap_common.load_heatmap_record",
        lambda *args: record,
    )
    def _heatmap_frame_rgb_failure(*args: object, **kwargs: object) -> None:
        raise RuntimeError("render failed")

    monkeypatch.setattr(
        "sparse_iq_heatmap_common.heatmap_frame_rgb",
        _heatmap_frame_rgb_failure,
    )

    with pytest.raises(RuntimeError, match="render failed"):
        load_h5_resource_payload(h5_path, fixed_levels=False)

    assert record.closed is True


def test_resolve_replacement_viewport_corners_preserves_same_size() -> None:
    corners = [[10.0, 20.0], [100.0, 20.0], [100.0, 80.0], [10.0, 80.0]]

    resolved = resolve_replacement_viewport_corners(
        existing_corners=corners,
        previous_native_size=(200, 120),
        replacement_native_size=(200, 120),
    )

    assert resolved == corners


def test_resolve_replacement_viewport_corners_scales_compatible_aspect_ratio() -> None:
    corners = [[100.0, 50.0], [900.0, 50.0], [900.0, 550.0], [100.0, 550.0]]

    resolved = resolve_replacement_viewport_corners(
        existing_corners=corners,
        previous_native_size=(1000, 600),
        replacement_native_size=(2000, 1200),
    )

    assert resolved is not None
    scaled = np.asarray(resolved, dtype=np.float32)
    assert scaled[0, 0] == pytest.approx(200.0)
    assert scaled[2, 0] == pytest.approx(1800.0)


def test_resolve_replacement_viewport_corners_resets_incompatible_aspect_ratio() -> None:
    corners = [[100.0, 50.0], [900.0, 50.0], [900.0, 550.0], [100.0, 550.0]]

    assert (
        resolve_replacement_viewport_corners(
            existing_corners=corners,
            previous_native_size=(1000, 600),
            replacement_native_size=(1600, 900),
        )
        is None
    )


def test_build_preview_proxy_promotes_only_after_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import heatmap_alignment_resource_jobs as jobs

    source_path = tmp_path / "large.mp4"
    source_path.write_bytes(b"source")
    probe = VideoProbe(
        path=source_path,
        fps=30.0,
        frame_count=300,
        duration_s=10.0,
        width=3840,
        height=2160,
    )
    proxy_path = _proxy_cache_path(
        source_path,
        source_probe=probe,
        max_dimension=1280,
        cache_root=tmp_path,
    )

    monkeypatch.setattr(jobs, "probe_video", lambda path: probe)
    monkeypatch.setattr(jobs, "_find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(
        jobs,
        "_proxy_cache_path",
        lambda source_path, source_probe, max_dimension, cache_root: proxy_path,
    )

    class _FakeProcess:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.returncode = 0

        def communicate(self) -> tuple[str, str]:
            temp_path = jobs._proxy_temp_path(proxy_path)
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_bytes(b"partial")
            return "", ""

    monkeypatch.setattr(jobs.subprocess, "Popen", _FakeProcess)

    result = build_preview_proxy_video(source_path, cache_root=tmp_path)

    assert result.display_path == proxy_path
    assert proxy_path.exists()
    assert not jobs._proxy_temp_path(proxy_path).exists()


def test_build_preview_proxy_does_not_leave_final_cache_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import heatmap_alignment_resource_jobs as jobs

    source_path = tmp_path / "large.mp4"
    source_path.write_bytes(b"source")
    probe = VideoProbe(
        path=source_path,
        fps=30.0,
        frame_count=300,
        duration_s=10.0,
        width=3840,
        height=2160,
    )
    proxy_path = _proxy_cache_path(
        source_path,
        source_probe=probe,
        max_dimension=1280,
        cache_root=tmp_path,
    )

    monkeypatch.setattr(jobs, "probe_video", lambda path: probe)
    monkeypatch.setattr(jobs, "_find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(
        jobs,
        "_proxy_cache_path",
        lambda source_path, source_probe, max_dimension, cache_root: proxy_path,
    )

    class _FailingProcess:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.returncode = 1

        def communicate(self) -> tuple[str, str]:
            temp_path = jobs._proxy_temp_path(proxy_path)
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_bytes(b"partial")
            return "", "ffmpeg failed"

    monkeypatch.setattr(jobs.subprocess, "Popen", _FailingProcess)

    with pytest.raises(ProxyBuildError):
        build_preview_proxy_video(source_path, cache_root=tmp_path)

    assert not proxy_path.exists()
    assert not jobs._proxy_temp_path(proxy_path).exists()


def test_cancel_request_marks_job_cancelling() -> None:
    board = ResourceJobBoard()
    begin_resource_job(
        board,
        "camera",
        target_path=Path("trial.mp4"),
        replaces_active=False,
    )

    assert request_cancel_resource_job(board, "camera") is True
    assert board.camera.phase == "cancelling"
    assert board.camera.cancel_requested is True


def test_replacement_viewport_needs_default_reset_for_incompatible_aspect() -> None:
    corners = [[100.0, 50.0], [900.0, 50.0], [900.0, 550.0], [100.0, 550.0]]

    assert replacement_viewport_needs_default_reset(
        previous_corners=corners,
        previous_native_size=(1000, 600),
        replacement_native_size=(1600, 900),
    )


def test_replacement_viewport_does_not_need_default_reset_for_first_load() -> None:
    assert not replacement_viewport_needs_default_reset(
        previous_corners=None,
        previous_native_size=(0, 0),
        replacement_native_size=(1920, 1080),
    )


def test_release_resource_job_result_closes_h5_record() -> None:
    class _FakeRecord:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    record = _FakeRecord()
    payload = LoadedH5ResourcePayload(
        path=Path("trial.h5"),
        record=record,
        subsweep_idx=0,
        metadata=HeatmapTrack(path="trial.h5"),
        first_frame_shape=(10, 10),
        resolved_fixed_color_level=123.0,
    )

    release_resource_job_result("radar_h5", payload)

    assert record.closed is True


def test_from_loaded_record_reuses_worker_resolved_color_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolve_calls: list[str] = []

    def _unexpected_resolve(self: HeatmapTruthSource) -> float:
        resolve_calls.append("resolve")
        return 1.0

    monkeypatch.setattr(HeatmapTruthSource, "_resolve_fixed_color_level", _unexpected_resolve)

    class _FakeRecord:
        session_idx = 0
        group_idx = 0
        entry_idx = 0
        duration_s = 1.0
        fps = 1.0
        results: list[object] = []

        def close(self) -> None:
            return None

    source = HeatmapTruthSource.from_loaded_record(
        _FakeRecord(),
        path=Path("trial.h5"),
        subsweep_idx=0,
        resolved_fixed_color_level=321.0,
    )

    assert source._fixed_color_level == 321.0
    assert resolve_calls == []


def test_build_h5_truth_source_from_payload_uses_worker_color_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolve_calls: list[str] = []

    def _unexpected_resolve(self: HeatmapTruthSource) -> float:
        resolve_calls.append("resolve")
        return 1.0

    monkeypatch.setattr(HeatmapTruthSource, "_resolve_fixed_color_level", _unexpected_resolve)

    class _FakeRecord:
        session_idx = 0
        group_idx = 0
        entry_idx = 0
        duration_s = 1.0
        fps = 1.0
        results: list[object] = []

        def close(self) -> None:
            return None

    payload = LoadedH5ResourcePayload(
        path=Path("trial.h5"),
        record=_FakeRecord(),
        subsweep_idx=0,
        metadata=HeatmapTrack(path="trial.h5"),
        first_frame_shape=(10, 10),
        resolved_fixed_color_level=456.0,
    )

    source = build_h5_truth_source_from_payload(payload)

    assert source._fixed_color_level == 456.0
    assert resolve_calls == []


def test_prepare_proxy_video_requires_ffmpeg_for_large_sources(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import heatmap_alignment_core as core

    source_path = tmp_path / "large.mp4"
    source_path.write_bytes(b"source")
    probe = VideoProbe(
        path=source_path,
        fps=30.0,
        frame_count=300,
        duration_s=10.0,
        width=3840,
        height=2160,
    )

    monkeypatch.setattr(core, "probe_video", lambda path: probe)
    monkeypatch.setattr(core, "_find_ffmpeg", lambda: None)

    with pytest.raises(RuntimeError, match="ffmpeg was not found"):
        prepare_proxy_video(source_path, max_dimension=1280)
