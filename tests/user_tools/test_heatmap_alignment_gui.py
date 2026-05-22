from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from PySide6 import QtCore
from PySide6.QtWidgets import QApplication


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

from heatmap_alignment_gui import (  # noqa: E402
    RESOURCE_ACTION_LABELS,
    AlignmentTimelineWidget,
    CornerEditorWidget,
    HeatmapAlignmentWindow,
    ResourcesWindow,
    SignalPlotWidget,
    TimelineRangeModel,
    build_argument_parser,
    format_track_offset_label,
    track_offset_label_rect,
    track_offset_label_should_show,
)
from heatmap_alignment_core import (  # noqa: E402
    AlignmentResourceRuntime,
    AlignmentSession,
    CameraTrack,
    HeatmapTrack,
    Leg2UltrasonicDatasourceSettings,
    Leg2UltrasonicSignalSeries,
    PeakDistanceSignalSeries,
    build_alignment_resource_summaries,
    load_alignment_session,
    save_alignment_session,
)
from scipy.io import savemat


def _legend_item_labels(legend: object) -> list[str]:
    labels: list[str] = []
    for _sample, label in legend.items:
        labels.append(str(getattr(label, "text", label)))
    return labels


@pytest.fixture(autouse=True, scope="module")
def qapplication() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication()


def test_build_argument_parser_accepts_peaks() -> None:
    parser = build_argument_parser()
    args = parser.parse_args(["--h5", "trial.h5", "--peaks", "peaks.json"])

    assert args.h5 == Path("trial.h5")
    assert args.peaks == Path("peaks.json")


def test_build_argument_parser_accepts_session() -> None:
    parser = build_argument_parser()
    args = parser.parse_args(["--session", "session.json", "--mat", "leg2.mat"])

    assert args.session == Path("session.json")
    assert args.mat == Path("leg2.mat")


def test_build_argument_parser_rejects_legacy_artifact_flag() -> None:
    parser = build_argument_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--artifact", "session.json"])


def test_timeline_range_model_exposes_independent_leg2_offset() -> None:
    model = TimelineRangeModel()
    model.set_track_state(
        camera_duration_s=4.0,
        heatmap_duration_s=5.0,
        camera_offset_s=1.0,
        leg2_duration_s=3.0,
        leg2_offset_s=2.0,
    )

    assert model.camera_offset_s == pytest.approx(1.0)
    assert model.leg2_offset_s == pytest.approx(2.0)


def test_format_track_offset_label_uses_track_start_relative_to_h5() -> None:
    assert format_track_offset_label(-1.25) == "-1.250 s"
    assert format_track_offset_label(0.5) == "+0.500 s"
    assert format_track_offset_label(0.0) == "+0.000 s"
    assert format_track_offset_label(-0.0) == "+0.000 s"


def test_track_offset_label_should_show_when_label_fits_left_of_bar() -> None:
    plot_rect = QtCore.QRectF(100.0, 0.0, 400.0, 80.0)
    track_rect = QtCore.QRectF(200.0, 30.0, 120.0, 18.0)

    assert track_offset_label_should_show(plot_rect, track_rect, label_width_px=72.0) is True
    label_rect = track_offset_label_rect(plot_rect, track_rect, label_width_px=72.0)

    assert label_rect is not None
    assert label_rect.right() == pytest.approx(194.0)
    assert label_rect.left() == pytest.approx(122.0)


def test_track_offset_label_should_hide_when_bar_is_off_screen() -> None:
    plot_rect = QtCore.QRectF(100.0, 0.0, 400.0, 80.0)
    track_rect = QtCore.QRectF(20.0, 30.0, 50.0, 18.0)

    assert track_offset_label_should_show(plot_rect, track_rect, label_width_px=72.0) is False


def test_track_offset_label_should_hide_when_label_would_clip_plot_edge() -> None:
    plot_rect = QtCore.QRectF(100.0, 0.0, 400.0, 80.0)
    track_rect = QtCore.QRectF(150.0, 30.0, 40.0, 18.0)

    assert track_offset_label_should_show(plot_rect, track_rect, label_width_px=72.0) is False


def test_alignment_timeline_widget_leg2_track_start_uses_offset_sign_convention(
    qapplication: QApplication,
) -> None:
    range_model = TimelineRangeModel()
    range_model.set_track_state(
        camera_duration_s=0.0,
        heatmap_duration_s=5.0,
        camera_offset_s=0.0,
        leg2_duration_s=4.0,
        leg2_offset_s=1.25,
    )
    widget = AlignmentTimelineWidget(range_model)

    assert widget._leg2_track_start_s() == pytest.approx(-1.25)


def test_startup_session_takes_precedence_over_camera_and_h5(
    tmp_path: Path, qapplication: QApplication
) -> None:
    session_path = tmp_path / "session.json"
    startup_camera = tmp_path / "startup_camera.mp4"
    startup_h5 = tmp_path / "startup.h5"
    startup_camera.write_bytes(b"")
    startup_h5.write_bytes(b"")

    session = AlignmentSession(
        camera_track=CameraTrack(path=""),
        heatmap_track=HeatmapTrack(path=""),
    )
    save_alignment_session(session, session_path)

    window = HeatmapAlignmentWindow()

    def _fail_if_called(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("camera/H5 startup loads must not run when --session is provided")

    window.load_camera_from_path = _fail_if_called  # type: ignore[method-assign]
    window.load_h5_from_path = _fail_if_called  # type: ignore[method-assign]

    args = build_argument_parser().parse_args(
        [
            "--session",
            str(session_path),
            "--camera",
            str(startup_camera),
            "--h5",
            str(startup_h5),
        ]
    )
    if args.session is not None:
        window.load_session_from_path(args.session)
    else:
        if args.camera is not None:
            window.load_camera_from_path(args.camera)
        if args.h5 is not None:
            window.load_h5_from_path(args.h5)


def test_startup_mat_overrides_session_leg2_path(tmp_path: Path, qapplication: QApplication) -> None:
    session_mat = tmp_path / "session_leg2.mat"
    startup_mat = tmp_path / "startup_leg2.mat"
    session_path = tmp_path / "session.json"
    for mat_path in (session_mat, startup_mat):
        savemat(
            mat_path,
            {
                "DataRecordCommon": {
                    "timeOut": np.array([0.0, 1.0, 2.0], dtype=np.float64),
                    "ultrasonic_filtered": np.array([1000.0, 1100.0, 1200.0], dtype=np.float64),
                    "ReliableFlag": np.array([1.0, 1.0, 1.0], dtype=np.float64),
                },
                "Ultrasonic": {"Distance": np.array([1000.0, 1100.0, 1200.0], dtype=np.float64)},
            },
        )

    session = AlignmentSession(
        camera_track=CameraTrack(path=""),
        heatmap_track=HeatmapTrack(path=""),
        leg2_ultrasonic_datasource=Leg2UltrasonicDatasourceSettings(
            path=str(session_mat),
            signal_kind="filtered",
            offset_s=0.75,
        ),
    )
    save_alignment_session(session, session_path)

    window = HeatmapAlignmentWindow()
    window.load_session_from_path(session_path)
    assert window.session.leg2_ultrasonic_datasource.path == str(session_mat)

    assert window.load_leg2_mat_from_path(startup_mat) is True
    assert window.session.leg2_ultrasonic_datasource.path == str(startup_mat)
    assert window.leg2_ultrasonic_datasource is not None
    assert window.leg2_ultrasonic_datasource.path == startup_mat


def _sample_leg2_signal_series() -> Leg2UltrasonicSignalSeries:
    return Leg2UltrasonicSignalSeries(
        primary_time_s=np.array([0.0, 1.0], dtype=np.float64),
        primary_distance_m=np.array([1.2, 1.3], dtype=np.float64),
        faded_time_s=np.array([0.5, np.nan], dtype=np.float64),
        faded_distance_m=np.array([1.25, np.nan], dtype=np.float64),
    )


def test_signal_plot_legend_shows_leg2_valid_and_not_valid_labels(
    qapplication: QApplication,
) -> None:
    plot = SignalPlotWidget()
    plot.resize(480, 240)
    plot.show()
    qapplication.processEvents()

    plot.set_plotted_signals(
        peak_series=None,
        peak_visible=False,
        leg2_series=_sample_leg2_signal_series(),
        leg2_visible=True,
        leg2_legend_name="Leg2 raw ultrasonic",
    )
    qapplication.processEvents()

    legend = plot.getPlotItem().legend
    assert legend is not None
    assert legend.isVisible()
    assert _legend_item_labels(legend) == [
        "Leg2 raw ultrasonic (valid)",
        "Leg2 raw ultrasonic (not valid)",
    ]


def test_signal_plot_legend_hides_when_no_signals_plotted(
    qapplication: QApplication,
) -> None:
    plot = SignalPlotWidget()
    plot.resize(480, 240)
    plot.show()
    qapplication.processEvents()

    plot.set_plotted_signals(
        peak_series=None,
        peak_visible=False,
        leg2_series=None,
        leg2_visible=False,
        leg2_legend_name="Leg2 raw ultrasonic",
    )
    qapplication.processEvents()

    legend = plot.getPlotItem().legend
    assert legend is not None
    assert legend.isVisible() is False
    assert _legend_item_labels(legend) == []


def test_timeline_plot_rect_uses_configured_time_axis_span(
    qapplication: QApplication,
) -> None:
    range_model = TimelineRangeModel()
    range_model.set_track_state(
        camera_duration_s=0.0,
        heatmap_duration_s=10.0,
        camera_offset_s=0.0,
        leg2_duration_s=4.0,
        leg2_offset_s=0.0,
    )
    timeline = AlignmentTimelineWidget(range_model)
    timeline.resize(900, 124)
    timeline.show()
    qapplication.processEvents()

    timeline.set_time_axis_rect(220.0, 760.0)
    plot_rect = timeline._plot_rect()

    assert plot_rect.left() == pytest.approx(220.0)
    assert plot_rect.right() == pytest.approx(760.0)


def test_resources_menu_and_file_menu_actions_exist(qapplication: QApplication) -> None:
    window = HeatmapAlignmentWindow()
    menu_bar = window.menuBar()
    action_texts: set[str] = set()
    menu_titles: set[str] = set()
    for bar_action in menu_bar.actions():
        menu = bar_action.menu()
        if menu is None:
            continue
        menu_titles.add(menu.title().replace("&", ""))
        for menu_action in menu.actions():
            if menu_action.isSeparator():
                continue
            action_texts.add(menu_action.text().replace("&", ""))

    assert "File" in menu_titles
    assert "Resources" in menu_titles
    assert "Manage Resources..." in action_texts
    assert "&Manage Resources..." in {
        menu_action.text()
        for bar_action in menu_bar.actions()
        if bar_action.menu() is not None
        for menu_action in bar_action.menu().actions()
        if not menu_action.isSeparator()
    }
    assert "Save Session" in action_texts
    assert "Close Session" in action_texts
    assert "Load Camera Video..." in action_texts
    assert "Unload Camera Video" in action_texts


def test_resources_window_lists_fixed_resource_slots(qapplication: QApplication) -> None:
    window = HeatmapAlignmentWindow()
    resources = ResourcesWindow(window)
    summaries = build_alignment_resource_summaries(
        window.session,
        AlignmentResourceRuntime(),
    )
    resources.refresh(summaries, None)

    assert resources.table.rowCount() == 4
    assert resources.table.item(0, 1).text() == "Camera Video"
    assert resources.table.item(3, 1).text() == "Leg2 MAT"


def test_resources_window_reuses_single_instance(qapplication: QApplication) -> None:
    window = HeatmapAlignmentWindow()
    window._show_resources_window()
    first = window._resources_window
    window._show_resources_window()

    assert window._resources_window is first


def test_resource_action_labels_use_show_in_file_manager() -> None:
    assert "File Manager" in RESOURCE_ACTION_LABELS["reveal"].replace("&", "")


def test_resources_table_header_is_not_clickable(qapplication: QApplication) -> None:
    window = HeatmapAlignmentWindow()
    resources = ResourcesWindow(window)

    header = resources.table.horizontalHeader()
    assert header.sectionsClickable() is False
    assert header.highlightSections() is False


def test_resources_window_details_hide_path_when_unloaded(
    qapplication: QApplication,
) -> None:
    window = HeatmapAlignmentWindow()
    resources = ResourcesWindow(window)
    summaries = build_alignment_resource_summaries(
        window.session,
        AlignmentResourceRuntime(),
    )
    resources.refresh(summaries, None)
    resources._select_table_row(0)
    qapplication.processEvents()

    assert resources.details_identity_label.text() == "Camera Video (Primary)"
    assert "Unloaded" in resources.details_status_label.text()
    assert resources.details_path_widget.isVisible() is False


def test_resources_window_details_path_is_single_line_block(
    qapplication: QApplication,
) -> None:
    window = HeatmapAlignmentWindow()
    resources = ResourcesWindow(window)
    session = AlignmentSession(
        camera_track=CameraTrack(path="/tmp/example_camera.mp4"),
        heatmap_track=HeatmapTrack(path=""),
    )
    summaries = build_alignment_resource_summaries(
        session,
        AlignmentResourceRuntime(),
    )
    resources.refresh(summaries, None)
    resources._select_table_row(0)
    resources.show()
    qapplication.processEvents()

    assert resources.details_path_widget.isVisible() is True
    assert resources.details_path_label.text() == "Path: /tmp/example_camera.mp4"
    assert "\n" not in resources.details_path_label.text()


def test_resources_window_bottom_row_layout(qapplication: QApplication) -> None:
    window = HeatmapAlignmentWindow()
    resources = ResourcesWindow(window)
    resources.show()
    qapplication.processEvents()

    clear_rect = resources.clear_all_button.geometry()
    close_rect = resources.close_button.geometry()
    assert clear_rect.left() < close_rect.left()
    assert abs(clear_rect.center().y() - close_rect.center().y()) <= 2


def test_resources_window_close_button_hides_without_changing_state(
    qapplication: QApplication,
) -> None:
    window = HeatmapAlignmentWindow()
    window.session.camera_track = CameraTrack(path="/tmp/example_camera.mp4")
    window.session.heatmap_track = HeatmapTrack(path="/tmp/example.h5")
    window._current_session_path = Path("/tmp/session.json")

    window._show_resources_window()
    resources = window._resources_window
    assert resources is not None
    resources.show()
    qapplication.processEvents()
    assert resources.isVisible()

    resources.close_button.click()
    qapplication.processEvents()

    assert resources.isVisible() is False
    assert window._resources_window is resources
    assert window.session.camera_track.path == "/tmp/example_camera.mp4"
    assert window.session.heatmap_track.path == "/tmp/example.h5"
    assert window._current_session_path == Path("/tmp/session.json")
    assert window.camera_source is None
    assert window.heatmap_source is None


def test_show_resources_window_preserves_geometry(qapplication: QApplication) -> None:
    window = HeatmapAlignmentWindow()
    window._show_resources_window()
    resources = window._resources_window
    assert resources is not None

    resources.setGeometry(140, 160, 700, 500)
    qapplication.processEvents()
    expected_geometry = resources.geometry()

    window._show_resources_window()
    qapplication.processEvents()

    assert resources.geometry() == expected_geometry


def test_resource_menu_enablement_tracks_loaded_state(qapplication: QApplication) -> None:
    window = HeatmapAlignmentWindow()
    window._refresh_resources_ui()

    assert window.unload_camera_action.isEnabled() is False
    assert window.reload_camera_action.isEnabled() is False

    window.session.camera_track = CameraTrack(path="/tmp/example.mp4")
    window._refresh_resources_ui()

    assert window.reload_camera_action.isEnabled() is True


def test_timeline_time_axis_tracks_signal_plot_viewbox(
    qapplication: QApplication,
) -> None:
    window = HeatmapAlignmentWindow()
    window.resize(1024, 720)
    window.show()
    qapplication.processEvents()

    window._sync_timeline_axis_geometry()
    qapplication.processEvents()

    signal_left_px, signal_right_px = window.signal_plot.viewbox_horizontal_extent_local()
    assert signal_right_px > signal_left_px + 1.0

    timeline_left_px = window.timeline_view._time_axis_left_px
    timeline_right_px = window.timeline_view._time_axis_right_px
    assert timeline_left_px is not None
    assert timeline_right_px is not None
    assert timeline_right_px > timeline_left_px + 1.0

    left_global = window.signal_plot.mapToGlobal(QtCore.QPointF(signal_left_px, 0.0))
    right_global = window.signal_plot.mapToGlobal(QtCore.QPointF(signal_right_px, 0.0))
    expected_left_px = window.timeline_view.mapFromGlobal(left_global).x()
    expected_right_px = window.timeline_view.mapFromGlobal(right_global).x()

    assert timeline_left_px == pytest.approx(expected_left_px, abs=1.0)
    assert timeline_right_px == pytest.approx(expected_right_px, abs=1.0)


def test_corner_editor_edge_drag_applies_delta_once() -> None:
    widget = CornerEditorWidget()
    widget.set_frame(np.zeros((100, 100, 3), dtype=np.uint8))
    widget.set_corners(
        np.array(
            [[10.0, 10.0], [90.0, 10.0], [90.0, 90.0], [10.0, 90.0]],
            dtype=np.float32,
        )
    )
    widget._drag_edge = 0
    widget._start_drag_image_pos = QtCore.QPointF(20.0, 20.0)
    widget._start_drag_corners = widget.current_corners()

    widget._translate_drag(QtCore.QPointF(30.0, 25.0))

    assert np.allclose(
        widget.current_corners(),
        np.array(
            [[19.0, 15.0], [99.0, 15.0], [90.0, 90.0], [10.0, 90.0]],
            dtype=np.float32,
        ),
    )


def test_corner_editor_center_drag_uses_bounded_drag_start_delta() -> None:
    widget = CornerEditorWidget()
    widget.set_frame(np.zeros((100, 100, 3), dtype=np.uint8))
    widget.set_corners(
        np.array(
            [[10.0, 10.0], [90.0, 10.0], [90.0, 90.0], [10.0, 90.0]],
            dtype=np.float32,
        )
    )
    widget._drag_center = True
    widget._start_drag_image_pos = QtCore.QPointF(50.0, 50.0)
    widget._start_drag_corners = widget.current_corners()

    widget._translate_drag(QtCore.QPointF(80.0, 70.0))

    assert np.allclose(
        widget.current_corners(),
        np.array(
            [[19.0, 19.0], [99.0, 19.0], [99.0, 99.0], [19.0, 99.0]],
            dtype=np.float32,
        ),
    )
