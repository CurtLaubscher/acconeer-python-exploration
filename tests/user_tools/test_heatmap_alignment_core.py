from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

from heatmap_alignment_core import (  # noqa: E402
    AlignmentSession,
    CameraTrack,
    CameraVideoSource,
    ExportOverlaySettings,
    HeatmapTrack,
    PreprocessSettings,
    RenderSettings,
    TimelineState,
    ViewportGeometry,
    compute_xcorr_diagnostics,
    load_alignment_artifact,
    prepare_proxy_video,
    rectify_viewport,
    save_alignment_artifact,
    validate_alignment_session,
)


def test_alignment_artifact_roundtrip(tmp_path: Path) -> None:
    camera_path = tmp_path / "camera.mp4"
    heatmap_path = tmp_path / "truth.h5"
    camera_path.write_bytes(b"")
    heatmap_path.write_bytes(b"")

    session = AlignmentSession(
        camera_track=CameraTrack(path=str(camera_path), fps=60.0, duration_s=5.0, frame_count=300),
        heatmap_track=HeatmapTrack(
            path=str(heatmap_path),
            session_idx=0,
            group_idx=0,
            entry_idx=0,
            subsweep_idx=0,
            duration_s=4.0,
            fps=10.0,
        ),
        viewport=ViewportGeometry(
            corners=[[0.0, 0.0], [9.0, 0.0], [9.0, 5.0], [0.0, 5.0]],
            output_width=10,
            output_height=6,
        ),
        render=RenderSettings(color_min=0.0, color_max=5000.0, fixed_levels=True),
        preprocess=PreprocessSettings(
            blur_sigma=1.0,
            downscale_factor=0.5,
            lag_window_s=1.0,
            sample_count=12,
        ),
        timeline=TimelineState(current_time_s=1.0, offset_s=0.2),
        export_overlay=ExportOverlaySettings(
            visible=False,
            preview_enabled=False,
            x=12.0,
            y=24.0,
            width=128.0,
            height=96.0,
        ),
    )

    artifact_path = tmp_path / "alignment.json"
    save_alignment_artifact(session, artifact_path)
    loaded = load_alignment_artifact(artifact_path)

    assert loaded.viewport.output_width == 10
    assert loaded.timeline.offset_s == pytest.approx(0.2)
    assert loaded.preprocess.sample_count == 12
    assert loaded.export_overlay.visible is False
    assert loaded.export_overlay.preview_enabled is False
    assert loaded.export_overlay.width == pytest.approx(128.0)


def test_validate_alignment_session_rejects_bad_corners() -> None:
    session = AlignmentSession(
        viewport=ViewportGeometry(corners=[[0.0, 0.0], [1.0, 1.0]], output_width=1, output_height=1)
    )

    with pytest.raises(ValueError, match="exactly four"):
        validate_alignment_session(session, allow_missing_sources=True)


def test_rectify_viewport_preserves_identity_mapping() -> None:
    frame = np.arange(4 * 5 * 3, dtype=np.uint8).reshape(4, 5, 3)
    corners = np.array([[0, 0], [4, 0], [4, 3], [0, 3]], dtype=np.float32)

    rectified = rectify_viewport(frame, corners, (5, 4))

    assert rectified.shape == frame.shape
    assert np.allclose(rectified, frame)


class _FakeVideoCapture:
    def __init__(self, path: str) -> None:
        del path
        self.frames = [
            np.full((2, 3, 3), fill_value=value, dtype=np.uint8)
            for value in range(6)
        ]
        self.pos = 0
        self.set_calls = 0
        self.read_calls = 0
        self.grab_calls = 0

    def isOpened(self) -> bool:
        return True

    def get(self, prop_id: int) -> float:
        if prop_id == 5:  # cv2.CAP_PROP_FPS
            return 10.0
        if prop_id == 7:  # cv2.CAP_PROP_FRAME_COUNT
            return float(len(self.frames))
        if prop_id == 3:  # cv2.CAP_PROP_FRAME_WIDTH
            return float(self.frames[0].shape[1])
        if prop_id == 4:  # cv2.CAP_PROP_FRAME_HEIGHT
            return float(self.frames[0].shape[0])
        return 0.0

    def set(self, prop_id: int, value: float) -> bool:
        if prop_id == 1:  # cv2.CAP_PROP_POS_FRAMES
            self.set_calls += 1
            self.pos = int(value)
            return True
        return False

    def read(self) -> tuple[bool, np.ndarray | None]:
        self.read_calls += 1
        if self.pos < 0 or self.pos >= len(self.frames):
            return False, None
        frame = self.frames[self.pos]
        self.pos += 1
        return True, frame.copy()

    def grab(self) -> bool:
        self.grab_calls += 1
        if self.pos < 0 or self.pos >= len(self.frames):
            return False
        self.pos += 1
        return True

    def release(self) -> None:
        return None


def test_camera_video_source_prefers_sequential_decode_for_playback(monkeypatch: pytest.MonkeyPatch) -> None:
    import heatmap_alignment_core as core

    fake_capture = _FakeVideoCapture("dummy")
    monkeypatch.setattr(core.cv2, "VideoCapture", lambda path: fake_capture)
    monkeypatch.setattr(core.cv2, "CAP_PROP_FPS", 5)
    monkeypatch.setattr(core.cv2, "CAP_PROP_FRAME_COUNT", 7)
    monkeypatch.setattr(core.cv2, "CAP_PROP_FRAME_WIDTH", 3)
    monkeypatch.setattr(core.cv2, "CAP_PROP_FRAME_HEIGHT", 4)
    monkeypatch.setattr(core.cv2, "CAP_PROP_POS_FRAMES", 1)
    monkeypatch.setattr(core.cv2, "COLOR_BGR2RGB", 999)
    monkeypatch.setattr(core.cv2, "cvtColor", lambda frame, code: frame if code == 999 else frame)

    source = CameraVideoSource(Path("dummy.mp4"))
    source.frame_at_index(0, access_hint="random")
    source.frame_at_index(1, access_hint="playback")
    source.frame_at_index(2, access_hint="playback")
    source.frame_at_index(1, access_hint="scrub")

    assert fake_capture.set_calls == 1
    assert fake_capture.read_calls == 3
    assert fake_capture.grab_calls == 0
    assert source.cache_info()["currsize"] == 3


def test_camera_video_source_uses_grab_for_skipped_playback_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import heatmap_alignment_core as core

    fake_capture = _FakeVideoCapture("dummy")
    monkeypatch.setattr(core.cv2, "VideoCapture", lambda path: fake_capture)
    monkeypatch.setattr(core.cv2, "CAP_PROP_FPS", 5)
    monkeypatch.setattr(core.cv2, "CAP_PROP_FRAME_COUNT", 7)
    monkeypatch.setattr(core.cv2, "CAP_PROP_FRAME_WIDTH", 3)
    monkeypatch.setattr(core.cv2, "CAP_PROP_FRAME_HEIGHT", 4)
    monkeypatch.setattr(core.cv2, "CAP_PROP_POS_FRAMES", 1)
    monkeypatch.setattr(core.cv2, "COLOR_BGR2RGB", 999)
    monkeypatch.setattr(core.cv2, "cvtColor", lambda frame, code: frame if code == 999 else frame)

    source = CameraVideoSource(Path("dummy.mp4"))
    source.frame_at_index(0, access_hint="random")
    source.frame_at_index(2, access_hint="playback")

    assert fake_capture.set_calls == 1
    assert fake_capture.grab_calls == 1
    assert fake_capture.read_calls == 2


def test_prepare_proxy_video_skips_proxy_for_small_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    import heatmap_alignment_core as core

    source_path = Path("small.mp4")
    monkeypatch.setattr(
        core,
        "probe_video",
        lambda path: core.VideoProbe(
            path=path,
            fps=30.0,
            frame_count=90,
            duration_s=3.0,
            width=640,
            height=480,
        ),
    )

    result = prepare_proxy_video(source_path, max_dimension=1280)

    assert result.display_path == source_path
    assert result.proxy_path is None
    assert result.state == "original"


def test_prepare_proxy_video_reuses_cached_proxy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import heatmap_alignment_core as core

    source_path = tmp_path / "large.mp4"
    source_path.write_bytes(b"source")
    proxy_path = tmp_path / "proxy.mp4"
    proxy_path.write_bytes(b"proxy")

    monkeypatch.setattr(
        core,
        "probe_video",
        lambda path: core.VideoProbe(
            path=path,
            fps=60.0,
            frame_count=600,
            duration_s=10.0,
            width=3840,
            height=2160,
        ),
    )
    monkeypatch.setattr(core, "_find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(
        core,
        "_proxy_cache_path",
        lambda source_path, source_probe, max_dimension, cache_root: proxy_path,
    )

    result = prepare_proxy_video(source_path, max_dimension=1280, cache_root=tmp_path)

    assert result.display_path == proxy_path
    assert result.proxy_path == proxy_path
    assert result.state == "proxy_reused"


class _FakeCameraSource:
    def __init__(self, duration_s: float = 4.0, fps: float = 10.0) -> None:
        self.duration_s = duration_s
        self.fps = fps

    def frame_at_seconds(self, time_s: float) -> tuple[int, np.ndarray]:
        frame = _frame_for_time(time_s)
        return int(round(time_s * self.fps)), frame


class _FakeHeatmapSource:
    class _Record:
        def __init__(self, duration_s: float, fps: float) -> None:
            self.duration_s = duration_s
            self.fps = fps

    def __init__(self, duration_s: float = 4.0, fps: float = 10.0) -> None:
        self.record = self._Record(duration_s, fps)

    def frame_at_seconds(self, time_s: float) -> tuple[int, np.ndarray]:
        frame = _frame_for_time(time_s)
        return int(round(time_s * self.record.fps)), frame


def _frame_for_time(time_s: float) -> np.ndarray:
    phase = int(round(time_s * 10)) % 16
    base = np.zeros((16, 16, 3), dtype=np.uint8)
    base[:, :, 1] = np.arange(16, dtype=np.uint8)[:, None] * 8
    base[:, phase, 0] = 255
    base[:, phase, 2] = np.arange(16, dtype=np.uint8) * 12
    return base


def test_compute_xcorr_diagnostics_peaks_near_zero_lag() -> None:
    session = AlignmentSession(
        viewport=ViewportGeometry(
            corners=[[0.0, 0.0], [15.0, 0.0], [15.0, 15.0], [0.0, 15.0]],
            output_width=16,
            output_height=16,
        ),
        preprocess=PreprocessSettings(
            blur_sigma=0.0,
            downscale_factor=1.0,
            lag_window_s=0.3,
            sample_count=8,
        ),
        timeline=TimelineState(current_time_s=0.5, offset_s=0.0),
    )

    lag_values, scores = compute_xcorr_diagnostics(
        _FakeCameraSource(),
        _FakeHeatmapSource(),
        session,
    )

    best_lag = lag_values[np.nanargmax(scores)]
    assert best_lag == pytest.approx(0.0, abs=0.11)
