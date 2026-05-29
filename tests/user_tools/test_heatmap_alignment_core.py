from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

from scipy.io import savemat

from heatmap_alignment_core import (  # noqa: E402
    AlignmentResourceRuntime,
    AlignmentSession,
    CameraTrack,
    CameraVideoSource,
    ExportOverlaySettings,
    HeatmapPlotRenderer,
    HeatmapTrack,
    Leg2MatImportError,
    Leg2UltrasonicDatasourceSettings,
    PreprocessSettings,
    RenderSettings,
    SignalPlotViewSettings,
    TimelineState,
    ViewportGeometry,
    ViewportVisibilitySettings,
    _compute_leg2_stance_intervals,
    apply_viewport_visibility,
    build_alignment_resource_summaries,
    build_leg2_ultrasonic_signal_series,
    elide_path_middle,
    build_peak_distance_signal_series,
    compute_xcorr_diagnostics,
    derive_h5_signal_plot_color,
    import_leg2_mat_for_heatmap,
    import_peak_distance_json_for_heatmap,
    load_alignment_session,
    load_leg2_mat_ultrasonic,
    prepare_proxy_video,
    rectify_viewport,
    save_alignment_session,
    scale_viewport_corners,
    TimelineH5DragSnapshot,
    apply_timeline_h5_alignment_drag,
    timeline_h5_drag_affects_alignment,
    timeline_view_bounds_s,
    validate_alignment_session,
    visible_signal_y_range,
)
from sparse_iq_peak_distance_core import (  # noqa: E402
    DEFAULT_PEAK_THRESHOLD,
    STATUS_DETECTED,
    STATUS_NO_DETECTION,
    FramePeakMeasurement,
    PeakDistanceDatasourceSettings,
    PeakDistanceExportResult,
    PeakDistanceMetadata,
    write_peak_distance_json,
)


def _resolved_margin_pixels(presentation: object) -> tuple[float, float, float, float]:
    render_width, render_height = presentation.render_size
    return (
        presentation.left_margin * render_width,
        (1.0 - presentation.right_margin) * render_width,
        presentation.bottom_margin * render_height,
        (1.0 - presentation.top_margin) * render_height,
    )


def test_alignment_session_roundtrip(tmp_path: Path) -> None:
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

    session_path = tmp_path / "alignment.json"
    save_alignment_session(session, session_path)
    loaded = load_alignment_session(session_path)

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


def test_alignment_session_roundtrip_with_peak_distance_datasource(tmp_path: Path) -> None:
    camera_path = tmp_path / "camera.mp4"
    heatmap_path = tmp_path / "truth.h5"
    peak_json_path = tmp_path / "peaks.json"
    camera_path.write_bytes(b"")
    heatmap_path.write_bytes(b"")
    peak_json_path.write_text("{}", encoding="utf-8")

    session = AlignmentSession(
        camera_track=CameraTrack(path=str(camera_path), fps=30.0, duration_s=2.0, frame_count=60),
        heatmap_track=HeatmapTrack(path=str(heatmap_path), duration_s=2.0, fps=10.0),
        peak_distance_datasource=PeakDistanceDatasourceSettings(
            path=str(peak_json_path),
            visible=False,
        ),
    )

    session_path = tmp_path / "alignment_with_peaks.json"
    save_alignment_session(session, session_path)
    loaded = load_alignment_session(session_path)

    assert loaded.peak_distance_datasource.path == str(peak_json_path)
    assert loaded.peak_distance_datasource.visible is False


def test_alignment_session_roundtrip_with_signal_plot_view_settings(tmp_path: Path) -> None:
    camera_path = tmp_path / "camera.mp4"
    heatmap_path = tmp_path / "truth.h5"
    camera_path.write_bytes(b"")
    heatmap_path.write_bytes(b"")

    session = AlignmentSession(
        camera_track=CameraTrack(path=str(camera_path), fps=30.0, duration_s=2.0, frame_count=60),
        heatmap_track=HeatmapTrack(path=str(heatmap_path), duration_s=2.0, fps=10.0),
        signal_plot_view=SignalPlotViewSettings(
            x_range_mode="manual",
            y_range_mode="manual",
            manual_x_range=(0.5, 4.5),
            manual_y_range=(0.1, 2.5),
        ),
    )

    session_path = tmp_path / "alignment_with_signal_plot.json"
    save_alignment_session(session, session_path)
    loaded = load_alignment_session(session_path)

    assert loaded.signal_plot_view.x_range_mode == "manual"
    assert loaded.signal_plot_view.y_range_mode == "manual"
    assert loaded.signal_plot_view.manual_x_range == pytest.approx((0.5, 4.5))
    assert loaded.signal_plot_view.manual_y_range == pytest.approx((0.1, 2.5))


def test_alignment_session_defaults_missing_signal_plot_view_settings(tmp_path: Path) -> None:
    camera_path = tmp_path / "camera.mp4"
    heatmap_path = tmp_path / "truth.h5"
    camera_path.write_bytes(b"")
    heatmap_path.write_bytes(b"")
    session_path = tmp_path / "alignment.json"
    session_path.write_text(
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

    loaded = load_alignment_session(session_path)

    assert loaded.signal_plot_view == SignalPlotViewSettings()


def test_build_peak_distance_signal_series_segments_status_and_gaps() -> None:
    measurements = (
        FramePeakMeasurement(
            frame_index=0,
            source_tick=0,
            time_s=0.0,
            absolute_time=None,
            status=STATUS_DETECTED,
            peak_distance_m=1.0,
            candidate_peak_distance_m=1.0,
            peak_strength=10.0,
        ),
        FramePeakMeasurement(
            frame_index=1,
            source_tick=1,
            time_s=0.1,
            absolute_time=None,
            status=STATUS_NO_DETECTION,
            peak_distance_m=None,
            candidate_peak_distance_m=1.2,
            peak_strength=5.0,
        ),
        FramePeakMeasurement(
            frame_index=2,
            source_tick=2,
            time_s=0.2,
            absolute_time=None,
            status=STATUS_DETECTED,
            peak_distance_m=None,
            candidate_peak_distance_m=float("nan"),
            peak_strength=0.0,
        ),
        FramePeakMeasurement(
            frame_index=3,
            source_tick=3,
            time_s=0.3,
            absolute_time=None,
            status=STATUS_DETECTED,
            peak_distance_m=1.4,
            candidate_peak_distance_m=1.4,
            peak_strength=12.0,
        ),
    )

    series = build_peak_distance_signal_series(measurements)

    assert np.allclose(series.detected_time_s, [0.0, np.nan, 0.3], equal_nan=True)
    assert np.allclose(series.detected_distance_m, [1.0, np.nan, 1.4], equal_nan=True)
    assert np.allclose(series.candidate_time_s, [0.0, 0.1, np.nan], equal_nan=True)
    assert np.allclose(series.candidate_distance_m, [1.0, 1.2, np.nan], equal_nan=True)


def test_visible_signal_y_range_uses_active_x_window_and_includes_zero() -> None:
    series = build_peak_distance_signal_series(
        (
            FramePeakMeasurement(
                frame_index=0,
                source_tick=0,
                time_s=0.0,
                absolute_time=None,
                status=STATUS_DETECTED,
                peak_distance_m=1.0,
                candidate_peak_distance_m=1.0,
                peak_strength=1.0,
            ),
            FramePeakMeasurement(
                frame_index=1,
                source_tick=1,
                time_s=1.0,
                absolute_time=None,
                status=STATUS_DETECTED,
                peak_distance_m=3.0,
                candidate_peak_distance_m=3.0,
                peak_strength=1.0,
            ),
        )
    )

    y_range = visible_signal_y_range(series, x_min_s=-0.1, x_max_s=0.5)

    assert y_range is not None
    assert y_range[0] == pytest.approx(-0.05)
    assert y_range[1] == pytest.approx(1.05)


def test_derive_h5_signal_plot_color_lightens_on_dark_background() -> None:
    assert derive_h5_signal_plot_color() != "#22c55e"


def test_timeline_h5_drag_affects_alignment_when_non_h5_tracks_loaded() -> None:
    assert timeline_h5_drag_affects_alignment(camera_duration_s=1.0, leg2_duration_s=0.0)
    assert timeline_h5_drag_affects_alignment(camera_duration_s=0.0, leg2_duration_s=1.0)
    assert not timeline_h5_drag_affects_alignment(camera_duration_s=0.0, leg2_duration_s=0.0)


def test_apply_timeline_h5_alignment_drag_shifts_non_h5_offsets_together() -> None:
    snapshot = TimelineH5DragSnapshot(
        range_start_s=0.0,
        range_end_s=10.0,
        current_time_s=3.0,
        camera_offset_s=1.0,
        leg2_offset_s=2.0,
    )
    dragged = apply_timeline_h5_alignment_drag(snapshot, h5_desired_start_s=0.5)

    assert dragged.camera_offset_s == pytest.approx(1.5)
    assert dragged.leg2_offset_s == pytest.approx(2.5)
    assert dragged.current_time_s == pytest.approx(2.5)
    assert dragged.range_start_s == pytest.approx(-0.5)
    assert dragged.range_end_s == pytest.approx(9.5)


def test_apply_timeline_h5_alignment_drag_preserves_playhead_screen_fraction() -> None:
    snapshot = TimelineH5DragSnapshot(
        range_start_s=0.0,
        range_end_s=10.0,
        current_time_s=3.0,
        camera_offset_s=1.0,
        leg2_offset_s=2.0,
    )
    dragged = apply_timeline_h5_alignment_drag(snapshot, h5_desired_start_s=0.5)
    span_s = snapshot.range_end_s - snapshot.range_start_s
    frac_before = (snapshot.current_time_s - snapshot.range_start_s) / span_s
    dragged_span_s = dragged.range_end_s - dragged.range_start_s
    frac_after = (dragged.current_time_s - dragged.range_start_s) / dragged_span_s

    assert frac_after == pytest.approx(frac_before)


def test_apply_timeline_h5_alignment_drag_preserves_camera_bar_screen_fraction() -> None:
    snapshot = TimelineH5DragSnapshot(
        range_start_s=0.0,
        range_end_s=10.0,
        current_time_s=3.0,
        camera_offset_s=1.0,
        leg2_offset_s=0.0,
    )
    dragged = apply_timeline_h5_alignment_drag(snapshot, h5_desired_start_s=0.5)
    span_s = snapshot.range_end_s - snapshot.range_start_s
    camera_start_before = -snapshot.camera_offset_s
    camera_frac_before = (camera_start_before - snapshot.range_start_s) / span_s
    camera_start_after = -dragged.camera_offset_s
    dragged_span_s = dragged.range_end_s - dragged.range_start_s
    camera_frac_after = (camera_start_after - dragged.range_start_s) / dragged_span_s

    assert camera_frac_after == pytest.approx(camera_frac_before)


def test_h5_alignment_drag_leaves_peak_distance_signal_times_unchanged() -> None:
    measurements = (
        FramePeakMeasurement(
            frame_index=0,
            source_tick=0,
            time_s=0.5,
            absolute_time=None,
            status=STATUS_DETECTED,
            peak_distance_m=1.0,
            candidate_peak_distance_m=1.0,
            peak_strength=1.0,
        ),
    )
    series = build_peak_distance_signal_series(measurements)
    original_detected_times = series.detected_time_s.copy()

    apply_timeline_h5_alignment_drag(
        TimelineH5DragSnapshot(
            range_start_s=0.0,
            range_end_s=5.0,
            current_time_s=1.0,
            camera_offset_s=0.25,
            leg2_offset_s=0.5,
        ),
        h5_desired_start_s=0.75,
    )

    assert np.array_equal(series.detected_time_s, original_detected_times)


def test_timeline_view_bounds_s_adds_padding() -> None:
    bounds = timeline_view_bounds_s(
        heatmap_duration_s=10.0,
        camera_duration_s=0.0,
        camera_offset_s=0.0,
    )

    assert bounds[0] < 0.0
    assert bounds[1] > 10.0


def test_alignment_session_defaults_missing_viewport_visibility_settings(tmp_path: Path) -> None:
    camera_path = tmp_path / "camera.mp4"
    heatmap_path = tmp_path / "truth.h5"
    camera_path.write_bytes(b"")
    heatmap_path.write_bytes(b"")
    session_path = tmp_path / "alignment.json"
    session_path.write_text(
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

    loaded = load_alignment_session(session_path)

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


def _sample_peak_distance_export_result() -> PeakDistanceExportResult:
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
            status=STATUS_DETECTED,
            peak_distance_m=1.3,
            candidate_peak_distance_m=1.3,
            peak_strength=700.0,
        ),
    )
    return PeakDistanceExportResult(metadata=metadata, measurements=measurements)


def test_import_peak_distance_json_without_heatmap_defers_validation(tmp_path: Path) -> None:
    json_path = tmp_path / "peaks.json"
    write_peak_distance_json(_sample_peak_distance_export_result(), json_path)

    datasource, warnings = import_peak_distance_json_for_heatmap(json_path, None)

    assert warnings == []
    assert len(datasource.measurements) == 2


def _write_sample_leg2_mat(
    path: Path,
    *,
    include_trailing_zero_time: bool = False,
) -> None:
    time_out = np.array([10.0, 20.0, 30.0], dtype=np.float64)
    distance_mm = np.array([1200.0, 1500.0, np.nan], dtype=np.float64)
    filtered_mm = np.array([1180.0, 1490.0, 1600.0], dtype=np.float64)
    reliable_flag = np.array([1.0, 0.0, 1.0], dtype=np.float64)
    robust_fc = np.array([1.0, 1.0, 0.0], dtype=np.float64)
    if include_trailing_zero_time:
        time_out = np.append(time_out, 0.0)
        distance_mm = np.append(distance_mm, 999.0)
        filtered_mm = np.append(filtered_mm, 999.0)
        reliable_flag = np.append(reliable_flag, 1.0)
        robust_fc = np.append(robust_fc, 0.0)
    savemat(
        path,
        {
            "DataRecordCommon": {
                "timeOut": time_out,
                "ultrasonic_filtered": filtered_mm,
                "ReliableFlag": reliable_flag,
                "robustFC": robust_fc,
            },
            "Ultrasonic": {"Distance": distance_mm},
        },
    )


def test_load_leg2_mat_ultrasonic_success_and_unit_conversion(tmp_path: Path) -> None:
    mat_path = tmp_path / "leg2.mat"
    _write_sample_leg2_mat(mat_path)

    datasource = load_leg2_mat_ultrasonic(mat_path)

    assert datasource.time_s.tolist() == pytest.approx([0.0, 10.0, 20.0])
    assert datasource.raw_distance_m.tolist() == pytest.approx([1.2, 1.5, np.nan], nan_ok=True)
    assert datasource.filtered_distance_m.tolist() == pytest.approx([1.18, 1.49, 1.6])
    assert datasource.reliable_flag_mask.tolist() == [True, False, True]
    assert datasource.duration_s == pytest.approx(20.0)


def test_load_leg2_mat_ultrasonic_trims_trailing_zero_time(tmp_path: Path) -> None:
    mat_path = tmp_path / "leg2_trailing_zero.mat"
    _write_sample_leg2_mat(mat_path, include_trailing_zero_time=True)

    datasource = load_leg2_mat_ultrasonic(mat_path)

    assert datasource.time_s.size == 3
    assert datasource.raw_distance_m.size == 3
    assert datasource.filtered_distance_m.size == 3
    assert datasource.reliable_flag_mask.size == 3


def test_load_leg2_mat_ultrasonic_requires_filtered_signal(tmp_path: Path) -> None:
    mat_path = tmp_path / "leg2_missing_filtered.mat"
    savemat(
        mat_path,
        {
            "DataRecordCommon": {
                "timeOut": np.array([1.0, 2.0, 3.0], dtype=np.float64),
                "ReliableFlag": np.array([1.0, 1.0, 1.0], dtype=np.float64),
                "robustFC": np.array([1.0, 1.0, 0.0], dtype=np.float64),
            },
            "Ultrasonic": {"Distance": np.array([1000.0, 1100.0, 1200.0], dtype=np.float64)},
        },
    )

    with pytest.raises(Leg2MatImportError, match="ultrasonic_filtered"):
        load_leg2_mat_ultrasonic(mat_path)


def test_load_leg2_mat_ultrasonic_requires_reliable_flag(tmp_path: Path) -> None:
    mat_path = tmp_path / "leg2_missing_reliable_flag.mat"
    savemat(
        mat_path,
        {
            "DataRecordCommon": {
                "timeOut": np.array([1.0, 2.0, 3.0], dtype=np.float64),
                "ultrasonic_filtered": np.array([1000.0, 1100.0, 1200.0], dtype=np.float64),
                "robustFC": np.array([1.0, 1.0, 0.0], dtype=np.float64),
            },
            "Ultrasonic": {"Distance": np.array([1000.0, 1100.0, 1200.0], dtype=np.float64)},
        },
    )

    with pytest.raises(Leg2MatImportError, match="DataRecordCommon.ReliableFlag"):
        load_leg2_mat_ultrasonic(mat_path)


def test_load_leg2_mat_ultrasonic_rejects_length_mismatch(tmp_path: Path) -> None:
    mat_path = tmp_path / "leg2_mismatch.mat"
    savemat(
        mat_path,
        {
            "DataRecordCommon": {
                "timeOut": np.array([1.0, 2.0, 3.0], dtype=np.float64),
                "ultrasonic_filtered": np.array([1000.0, 1100.0], dtype=np.float64),
                "ReliableFlag": np.array([1.0, 1.0, 1.0], dtype=np.float64),
                "robustFC": np.array([1.0, 1.0, 0.0], dtype=np.float64),
            },
            "Ultrasonic": {"Distance": np.array([1000.0, 1100.0, 1200.0], dtype=np.float64)},
        },
    )

    with pytest.raises(Leg2MatImportError, match="Incompatible array lengths"):
        load_leg2_mat_ultrasonic(mat_path)


def test_build_leg2_ultrasonic_signal_series_segments_and_gaps(tmp_path: Path) -> None:
    mat_path = tmp_path / "leg2.mat"
    _write_sample_leg2_mat(mat_path)
    datasource = import_leg2_mat_for_heatmap(mat_path)

    series = build_leg2_ultrasonic_signal_series(
        datasource,
        signal_kind="raw",
        offset_s=0.5,
    )

    assert np.allclose(series.primary_time_s, [-0.5, np.nan], equal_nan=True)
    assert np.allclose(series.primary_distance_m, [1.2, np.nan], equal_nan=True)
    assert np.allclose(
        series.faded_time_s,
        [-0.5, 9.5, np.nan],
        equal_nan=True,
    )
    assert np.allclose(
        series.faded_distance_m,
        [1.2, 1.5, np.nan],
        equal_nan=True,
    )


def test_build_leg2_ultrasonic_signal_series_preserves_true_missing_value_gaps(
    tmp_path: Path,
) -> None:
    mat_path = tmp_path / "leg2.mat"
    _write_sample_leg2_mat(mat_path)
    datasource = import_leg2_mat_for_heatmap(mat_path)

    series = build_leg2_ultrasonic_signal_series(
        datasource,
        signal_kind="raw",
        offset_s=0.0,
    )

    assert np.isnan(series.primary_time_s[-1])
    assert np.isnan(series.faded_time_s[-1])


def test_compute_leg2_stance_intervals_single_stance_sample() -> None:
    """Stance mask [1, 0] should produce interval from time 0 to time 0 (single sample period)."""
    time_s = np.array([0.0, 1.0], dtype=np.float64)
    stance_phase_mask = np.array([1.0, 0.0], dtype=np.float64)

    intervals = _compute_leg2_stance_intervals(time_s, stance_phase_mask, offset_s=0.0)

    assert intervals.start_times_s.tolist() == [0.0]
    assert intervals.end_times_s.tolist() == [0.0]


def test_compute_leg2_stance_intervals_multiple_stance_samples() -> None:
    """Stance mask [1, 1, 0] should produce interval from time 0 to time 1."""
    time_s = np.array([0.0, 1.0, 2.0], dtype=np.float64)
    stance_phase_mask = np.array([1.0, 1.0, 0.0], dtype=np.float64)

    intervals = _compute_leg2_stance_intervals(time_s, stance_phase_mask, offset_s=0.0)

    assert intervals.start_times_s.tolist() == [0.0]
    assert intervals.end_times_s.tolist() == [1.0]


def test_compute_leg2_stance_intervals_swing_to_stance_to_swing() -> None:
    """Stance mask [0, 1, 0] should produce interval from time 1 to time 1."""
    time_s = np.array([0.0, 1.0, 2.0], dtype=np.float64)
    stance_phase_mask = np.array([0.0, 1.0, 0.0], dtype=np.float64)

    intervals = _compute_leg2_stance_intervals(time_s, stance_phase_mask, offset_s=0.0)

    assert intervals.start_times_s.tolist() == [1.0]
    assert intervals.end_times_s.tolist() == [1.0]


def test_compute_leg2_stance_intervals_ends_in_stance() -> None:
    """Stance mask [0, 1, 1] should produce interval from time 1 to time 2 (implicit end at last sample)."""
    time_s = np.array([0.0, 1.0, 2.0], dtype=np.float64)
    stance_phase_mask = np.array([0.0, 1.0, 1.0], dtype=np.float64)

    intervals = _compute_leg2_stance_intervals(time_s, stance_phase_mask, offset_s=0.0)

    assert intervals.start_times_s.tolist() == [1.0]
    assert intervals.end_times_s.tolist() == [2.0]


def test_compute_leg2_stance_intervals_with_track_offset() -> None:
    """Verify track offset is applied to all interval times."""
    time_s = np.array([0.0, 1.0, 2.0], dtype=np.float64)
    stance_phase_mask = np.array([1.0, 1.0, 0.0], dtype=np.float64)

    intervals = _compute_leg2_stance_intervals(time_s, stance_phase_mask, offset_s=0.5)

    # Offset -0.5 applied to times
    assert intervals.start_times_s.tolist() == pytest.approx([-0.5])
    assert intervals.end_times_s.tolist() == pytest.approx([0.5])


def test_build_peak_distance_signal_series_bridges_detected_transitions() -> None:
    measurements = (
        FramePeakMeasurement(
            frame_index=0,
            source_tick=0,
            time_s=0.0,
            absolute_time=None,
            status=STATUS_DETECTED,
            peak_distance_m=1.0,
            candidate_peak_distance_m=1.0,
            peak_strength=10.0,
        ),
        FramePeakMeasurement(
            frame_index=1,
            source_tick=1,
            time_s=0.1,
            absolute_time=None,
            status=STATUS_NO_DETECTION,
            peak_distance_m=None,
            candidate_peak_distance_m=1.2,
            peak_strength=5.0,
        ),
    )

    series = build_peak_distance_signal_series(measurements)

    assert np.allclose(series.detected_time_s, [0.0, np.nan], equal_nan=True)
    assert np.allclose(series.candidate_time_s, [0.0, 0.1], equal_nan=True)
    assert series.candidate_distance_m[0] == pytest.approx(1.0)


def test_alignment_session_roundtrip_with_leg2_ultrasonic_datasource(tmp_path: Path) -> None:
    camera_path = tmp_path / "camera.mp4"
    heatmap_path = tmp_path / "truth.h5"
    mat_path = tmp_path / "leg2.mat"
    camera_path.write_bytes(b"")
    heatmap_path.write_bytes(b"")
    _write_sample_leg2_mat(mat_path)

    session = AlignmentSession(
        camera_track=CameraTrack(path=str(camera_path), fps=30.0, duration_s=2.0, frame_count=60),
        heatmap_track=HeatmapTrack(path=str(heatmap_path), duration_s=2.0, fps=10.0),
        leg2_ultrasonic_datasource=Leg2UltrasonicDatasourceSettings(
            path=str(mat_path),
            visible=False,
            signal_kind="filtered",
            offset_s=0.25,
        ),
    )

    session_path = tmp_path / "alignment_with_leg2.json"
    save_alignment_session(session, session_path)
    loaded = load_alignment_session(session_path)

    assert loaded.leg2_ultrasonic_datasource.path == str(mat_path)
    assert loaded.leg2_ultrasonic_datasource.visible is False
    assert loaded.leg2_ultrasonic_datasource.signal_kind == "filtered"
    assert loaded.leg2_ultrasonic_datasource.offset_s == pytest.approx(0.25)


def test_alignment_session_defaults_missing_leg2_ultrasonic_fields(tmp_path: Path) -> None:
    camera_path = tmp_path / "camera.mp4"
    heatmap_path = tmp_path / "truth.h5"
    camera_path.write_bytes(b"")
    heatmap_path.write_bytes(b"")
    session_path = tmp_path / "alignment.json"
    session_path.write_text(
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

    loaded = load_alignment_session(session_path)

    assert loaded.leg2_ultrasonic_datasource.path == ""
    assert loaded.leg2_ultrasonic_datasource.visible is True
    assert loaded.leg2_ultrasonic_datasource.signal_kind == "raw"
    assert loaded.leg2_ultrasonic_datasource.offset_s == pytest.approx(0.0)


def test_timeline_view_bounds_s_includes_leg2_track() -> None:
    bounds = timeline_view_bounds_s(
        heatmap_duration_s=10.0,
        camera_duration_s=8.0,
        camera_offset_s=1.0,
        leg2_duration_s=6.0,
        leg2_offset_s=2.0,
        fit_padding_fraction=0.0,
    )

    assert bounds[0] == pytest.approx(-2.0)
    assert bounds[1] == pytest.approx(10.0)


def test_timeline_view_bounds_s_keeps_camera_and_leg2_offsets_independent() -> None:
    camera_bounds = timeline_view_bounds_s(
        heatmap_duration_s=5.0,
        camera_duration_s=4.0,
        camera_offset_s=1.5,
        leg2_duration_s=0.0,
        leg2_offset_s=0.0,
        fit_padding_fraction=0.0,
    )
    leg2_bounds = timeline_view_bounds_s(
        heatmap_duration_s=5.0,
        camera_duration_s=0.0,
        camera_offset_s=0.0,
        leg2_duration_s=4.0,
        leg2_offset_s=2.5,
        fit_padding_fraction=0.0,
    )

    assert camera_bounds == pytest.approx((-1.5, 5.0))
    assert leg2_bounds == pytest.approx((-2.5, 5.0))


def test_elide_path_middle_preserves_filename() -> None:
    path = "/very/long/parent/folders/trial_export.mp4"
    elided = elide_path_middle(path, 28)

    assert elided.endswith("/trial_export.mp4")
    assert "..." in elided
    assert len(elided) <= 28


def test_elide_path_middle_preserves_windows_separator_before_filename() -> None:
    path = r"C:\very\long\parent\folders\trial_export.mp4"
    elided = elide_path_middle(path, 30)

    assert elided.endswith(r"\trial_export.mp4")
    assert "..." in elided
    assert len(elided) <= 30


def test_build_alignment_resource_summaries_cover_fixed_slots() -> None:
    summaries = build_alignment_resource_summaries(
        AlignmentSession(),
        AlignmentResourceRuntime(),
    )

    assert [summary.kind for summary in summaries] == [
        "camera",
        "radar_h5",
        "radar_peak",
        "leg2_mat",
    ]
    assert all(summary.status == "unloaded" for summary in summaries)


def test_build_alignment_resource_summaries_mark_missing_remembered_paths() -> None:
    missing = Path("/tmp/does-not-exist-camera.mp4")
    session = AlignmentSession(
        camera_track=CameraTrack(path=str(missing)),
        heatmap_track=HeatmapTrack(path=""),
    )
    summaries = build_alignment_resource_summaries(
        session,
        AlignmentResourceRuntime(
            reload_errors=(("camera", f"File not found: {missing}"),),
        ),
    )

    camera_summary = summaries[0]
    assert camera_summary.status == "missing"
    assert camera_summary.path == str(missing)
    assert "reload" in camera_summary.actions


def test_build_alignment_resource_summaries_mark_invalid_remembered_paths() -> None:
    existing = Path(__file__).resolve()
    session = AlignmentSession(
        camera_track=CameraTrack(path=str(existing)),
        heatmap_track=HeatmapTrack(path=""),
    )
    summaries = build_alignment_resource_summaries(
        session,
        AlignmentResourceRuntime(
            reload_errors=(("camera", "Could not reload camera video."),),
        ),
    )

    assert summaries[0].status == "invalid"
    assert "inspect" in summaries[0].actions


def test_build_alignment_resource_summaries_mark_loaded_state() -> None:
    session = AlignmentSession(
        camera_track=CameraTrack(path="/tmp/cam.mp4", duration_s=2.0, fps=30.0, frame_count=60),
        heatmap_track=HeatmapTrack(path=""),
    )
    summaries = build_alignment_resource_summaries(
        session,
        AlignmentResourceRuntime(camera_loaded=True),
    )

    assert summaries[0].status == "loaded"
    assert "unload" in summaries[0].actions


def test_build_alignment_resource_summaries_mark_loaded_warning_state() -> None:
    session = AlignmentSession(
        camera_track=CameraTrack(path="/tmp/cam.mp4", duration_s=2.0, fps=30.0, frame_count=60),
        heatmap_track=HeatmapTrack(path=""),
    )
    summaries = build_alignment_resource_summaries(
        session,
        AlignmentResourceRuntime(
            camera_loaded=True,
            load_warnings=(("camera", "Proxy preview unavailable."),),
        ),
    )

    assert summaries[0].status == "warning"
    assert "inspect" in summaries[0].actions
    assert "Proxy preview unavailable." in summaries[0].messages
