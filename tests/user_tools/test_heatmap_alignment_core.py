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
    HeatmapPlotRenderer,
    PreprocessSettings,
    RenderSettings,
    TimelineState,
    ViewportGeometry,
    ViewportVisibilitySettings,
    apply_viewport_visibility,
    compute_xcorr_diagnostics,
    load_alignment_artifact,
    prepare_proxy_video,
    rectify_viewport,
    save_alignment_artifact,
    scale_viewport_corners,
    validate_alignment_session,
)


def _resolved_margin_pixels(presentation: object) -> tuple[float, float, float, float]:
    render_width, render_height = presentation.render_size
    return (
        presentation.left_margin * render_width,
        (1.0 - presentation.right_margin) * render_width,
        presentation.bottom_margin * render_height,
        (1.0 - presentation.top_margin) * render_height,
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
        viewport_visibility=ViewportVisibilitySettings(
            enabled=True,
            map_to_viridis=True,
            low=0.1,
            high=0.9,
            gamma=1.4,
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
    assert loaded.viewport_visibility.enabled is True
    assert loaded.viewport_visibility.map_to_viridis is True
    assert loaded.viewport_visibility.low == pytest.approx(0.1)
    assert loaded.viewport_visibility.gamma == pytest.approx(1.4)


def test_alignment_artifact_defaults_missing_viewport_visibility_settings(tmp_path: Path) -> None:
    camera_path = tmp_path / "camera.mp4"
    heatmap_path = tmp_path / "truth.h5"
    camera_path.write_bytes(b"")
    heatmap_path.write_bytes(b"")
    artifact_path = tmp_path / "alignment.json"
    artifact_path.write_text(
        """
{
  "version": 1,
  "camera_track": {"path": "%CAMERA%", "fps": 30.0, "duration_s": 1.0, "frame_count": 30},
  "heatmap_track": {
    "path": "%HEATMAP%",
    "session_idx": 0,
    "group_idx": 0,
    "entry_idx": 0,
    "subsweep_idx": 0,
    "duration_s": 1.0,
    "fps": 10.0
  },
  "viewport": {
    "corners": [[0.0, 0.0], [9.0, 0.0], [9.0, 5.0], [0.0, 5.0]],
    "output_width": 10,
    "output_height": 6
  },
  "render": {"color_min": 0.0, "color_max": 3000.0, "fixed_levels": true},
  "preprocess": {
    "blur_sigma": 0.0,
    "downscale_factor": 1.0,
    "lag_window_s": 2.0,
    "sample_count": 30
  },
  "timeline": {"current_time_s": 0.0, "offset_s": 0.0},
  "export_overlay": {"visible": true, "preview_enabled": true, "x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}
}
        """.strip()
        .replace("%CAMERA%", str(camera_path).replace("\\", "\\\\"))
        .replace("%HEATMAP%", str(heatmap_path).replace("\\", "\\\\")),
        encoding="utf-8",
    )

    loaded = load_alignment_artifact(artifact_path)

    assert loaded.viewport_visibility == ViewportVisibilitySettings()


def test_validate_alignment_session_rejects_bad_corners() -> None:
    session = AlignmentSession(
        viewport=ViewportGeometry(
            corners=[[0.0, 0.0], [1.0, 1.0]], output_width=1, output_height=1
        )
    )

    with pytest.raises(ValueError, match="exactly four"):
        validate_alignment_session(session, allow_missing_sources=True)


def test_rectify_viewport_preserves_identity_mapping() -> None:
    frame = np.arange(4 * 5 * 3, dtype=np.uint8).reshape(4, 5, 3)
    corners = np.array([[0, 0], [4, 0], [4, 3], [0, 3]], dtype=np.float32)

    rectified = rectify_viewport(frame, corners, (5, 4))

    assert rectified.shape == frame.shape
    assert np.allclose(rectified, frame)


def test_scale_viewport_corners_maps_native_geometry_to_proxy_size() -> None:
    native_corners = np.array(
        [[300.0, 150.0], [1700.0, 150.0], [1700.0, 930.0], [300.0, 930.0]],
        dtype=np.float32,
    )

    scaled = scale_viewport_corners(
        native_corners,
        from_size=(2000, 1000),
        to_size=(1000, 500),
    )

    expected = np.array(
        [[150.0, 75.0], [850.0, 75.0], [850.0, 465.0], [150.0, 465.0]],
        dtype=np.float32,
    )
    assert np.allclose(scaled, expected)


def test_scale_viewport_corners_roundtrips_between_native_and_proxy_sizes() -> None:
    native_corners = np.array(
        [[120.5, 90.0], [1880.0, 110.0], [1790.0, 980.0], [140.0, 950.0]],
        dtype=np.float32,
    )

    preview_corners = scale_viewport_corners(
        native_corners,
        from_size=(1920, 1080),
        to_size=(960, 540),
    )
    restored = scale_viewport_corners(
        preview_corners,
        from_size=(960, 540),
        to_size=(1920, 1080),
    )

    assert np.allclose(restored, native_corners)


def test_heatmap_plot_renderer_uses_matching_style_proportions_for_preview_and_export() -> None:
    source_size = (360, 270)
    preview_render_size = (240, 180)
    export_render_size = source_size

    preview = HeatmapPlotRenderer.derive_presentation(
        source_size=source_size,
        render_size=preview_render_size,
    )
    export = HeatmapPlotRenderer.derive_presentation(
        source_size=source_size,
        render_size=export_render_size,
    )

    preview_scale = min(
        preview.render_size[0] / preview.source_size[0],
        preview.render_size[1] / preview.source_size[1],
    )

    assert preview.font_size_pt == pytest.approx(export.font_size_pt * preview_scale, rel=0.05)
    assert preview.tick_label_size_pt == pytest.approx(
        export.tick_label_size_pt * preview_scale,
        rel=0.05,
    )
    assert preview.tick_length_pt == pytest.approx(export.tick_length_pt * preview_scale, rel=0.05)
    assert preview.axis_line_width_pt == pytest.approx(
        export.axis_line_width_pt * preview_scale,
        rel=0.10,
    )
    preview_left, preview_right, preview_bottom, preview_top = _resolved_margin_pixels(preview)
    export_left, export_right, export_bottom, export_top = _resolved_margin_pixels(export)
    assert preview_left == pytest.approx(export_left * preview_scale, rel=0.05)
    assert preview_right == pytest.approx(export_right * preview_scale, rel=0.05)
    assert preview_bottom == pytest.approx(export_bottom * preview_scale, rel=0.05)
    assert preview_top == pytest.approx(export_top * preview_scale, rel=0.05)


def test_heatmap_plot_renderer_keeps_fixed_source_style_across_overlay_sizes() -> None:
    small_export = HeatmapPlotRenderer.derive_presentation(
        source_size=(360, 270),
        render_size=(360, 270),
    )
    large_export = HeatmapPlotRenderer.derive_presentation(
        source_size=(1280, 960),
        render_size=(1280, 960),
    )

    assert small_export.font_size_pt == pytest.approx(30.0)
    assert small_export.tick_label_size_pt == pytest.approx(22.0)
    assert small_export.tick_length_pt == pytest.approx(8.0)
    assert small_export.axis_line_width_pt == pytest.approx(2.0)
    assert _resolved_margin_pixels(small_export) == pytest.approx((170.0, 35.0, 115.0, 35.0))
    assert large_export.font_size_pt == pytest.approx(small_export.font_size_pt)
    assert large_export.tick_label_size_pt == pytest.approx(small_export.tick_label_size_pt)
    assert large_export.tick_length_pt == pytest.approx(small_export.tick_length_pt)
    assert large_export.axis_line_width_pt == pytest.approx(small_export.axis_line_width_pt)
    assert _resolved_margin_pixels(large_export) == pytest.approx((170.0, 35.0, 115.0, 35.0))


def test_heatmap_plot_renderer_scales_fixed_source_style_for_preview() -> None:
    source_size = (1280, 960)
    preview_render_size = (512, 384)

    preview = HeatmapPlotRenderer.derive_presentation(
        source_size=source_size,
        render_size=preview_render_size,
    )
    export = HeatmapPlotRenderer.derive_presentation(
        source_size=source_size,
        render_size=source_size,
    )

    preview_scale = min(
        preview.render_size[0] / preview.source_size[0],
        preview.render_size[1] / preview.source_size[1],
    )

    assert export.font_size_pt == pytest.approx(30.0)
    assert export.tick_label_size_pt == pytest.approx(22.0)
    assert export.tick_length_pt == pytest.approx(8.0)
    assert export.axis_line_width_pt == pytest.approx(2.0)
    assert preview.font_size_pt == pytest.approx(export.font_size_pt * preview_scale)
    assert preview.tick_label_size_pt == pytest.approx(export.tick_label_size_pt * preview_scale)
    assert preview.tick_length_pt == pytest.approx(export.tick_length_pt * preview_scale)
    assert preview.axis_line_width_pt == pytest.approx(export.axis_line_width_pt * preview_scale)
    preview_left, preview_right, preview_bottom, preview_top = _resolved_margin_pixels(preview)
    export_left, export_right, export_bottom, export_top = _resolved_margin_pixels(export)
    assert preview_left == pytest.approx(export_left * preview_scale)
    assert preview_right == pytest.approx(export_right * preview_scale)
    assert preview_bottom == pytest.approx(export_bottom * preview_scale)
    assert preview_top == pytest.approx(export_top * preview_scale)


def test_heatmap_plot_renderer_bounds_compact_overlay_presentation() -> None:
    compact = HeatmapPlotRenderer.derive_presentation(
        source_size=(72, 54),
        render_size=(72, 54),
    )

    left_margin_px, right_margin_px, bottom_margin_px, top_margin_px = _resolved_margin_pixels(
        compact
    )

    assert compact.font_size_pt == pytest.approx(30.0)
    assert compact.tick_label_size_pt == pytest.approx(22.0)
    assert compact.tick_length_pt == pytest.approx(8.0)
    assert compact.axis_line_width_pt == pytest.approx(2.0)
    assert left_margin_px + right_margin_px == pytest.approx(40.0)
    assert bottom_margin_px + top_margin_px == pytest.approx(22.0)
    assert compact.render_size[0] * (compact.right_margin - compact.left_margin) == pytest.approx(
        32.0
    )
    assert compact.render_size[1] * (compact.top_margin - compact.bottom_margin) == pytest.approx(
        32.0
    )


def test_heatmap_plot_renderer_preserves_tiny_render_size() -> None:
    tiny = HeatmapPlotRenderer.derive_presentation(
        source_size=(16, 12),
        render_size=(12, 9),
    )

    assert tiny.source_size == (32, 32)
    assert tiny.render_size == (12, 9)
    assert tiny.font_size_pt == pytest.approx(8.4375)
    assert tiny.tick_label_size_pt == pytest.approx(6.1875)
    assert tiny.tick_length_pt == pytest.approx(2.25)
    assert tiny.axis_line_width_pt == pytest.approx(0.5625)
    left_margin_px, right_margin_px, bottom_margin_px, top_margin_px = _resolved_margin_pixels(
        tiny
    )
    assert left_margin_px + right_margin_px == pytest.approx(3.0)
    assert bottom_margin_px + top_margin_px == pytest.approx(0.0)
    assert tiny.render_size[0] * (tiny.right_margin - tiny.left_margin) == pytest.approx(9.0)
    assert tiny.render_size[1] * (tiny.top_margin - tiny.bottom_margin) == pytest.approx(9.0)


def test_apply_viewport_visibility_returns_raw_when_disabled() -> None:
    frame = np.array(
        [
            [[10, 20, 30], [40, 50, 60]],
            [[70, 80, 90], [100, 110, 120]],
        ],
        dtype=np.uint8,
    )

    transformed = apply_viewport_visibility(
        frame,
        ViewportVisibilitySettings(enabled=False),
    )

    assert np.array_equal(transformed, frame)


def test_apply_viewport_visibility_corrects_original_colors_without_viridis_mapping() -> None:
    frame = np.array(
        [
            [[64, 128, 255], [32, 96, 160]],
        ],
        dtype=np.uint8,
    )

    transformed = apply_viewport_visibility(
        frame,
        ViewportVisibilitySettings(
            enabled=True,
            map_to_viridis=False,
            low=0.25,
            high=1.0,
            gamma=1.0,
        ),
    )

    assert transformed.shape == frame.shape
    assert transformed.dtype == np.uint8
    expected = np.array(
        [
            [[0, 86, 255], [0, 43, 128]],
        ],
        dtype=np.uint8,
    )
    assert np.array_equal(transformed, expected)


def test_apply_viewport_visibility_maps_corrected_luminance_to_viridis() -> None:
    import heatmap_alignment_core as core

    frame = np.array(
        [
            [[0, 0, 0], [128, 128, 128], [255, 255, 255]],
        ],
        dtype=np.uint8,
    )

    transformed = apply_viewport_visibility(
        frame,
        ViewportVisibilitySettings(
            enabled=True,
            map_to_viridis=True,
            low=0.0,
            high=1.0,
            gamma=1.0,
        ),
    )

    viridis = core._viridis_lookup_table_rgb()
    expected = np.array([[viridis[0], viridis[128], viridis[255]]], dtype=np.uint8)

    assert transformed.shape == frame.shape
    assert transformed.dtype == np.uint8
    assert np.array_equal(transformed, expected)


class _FakeVideoCapture:
    def __init__(self, path: str) -> None:
        del path
        self.frames = [np.full((2, 3, 3), fill_value=value, dtype=np.uint8) for value in range(6)]
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


def test_camera_video_source_prefers_sequential_decode_for_playback(
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


def test_prepare_proxy_video_skips_proxy_for_small_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
