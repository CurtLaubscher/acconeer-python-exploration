from __future__ import annotations

import sys
import unittest.mock
from pathlib import Path

import numpy as np
import pytest

from PySide6 import QtCore, QtGui, QtWidgets
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
    HeatmapDistanceHeader,
    ImagePreview,
    ResourcesWindow,
    SignalPlotWidget,
    TimelineRangeModel,
    _H5ResourceBackup,
    _CameraResourceBackup,
    build_argument_parser,
    format_track_offset_label,
    track_offset_label_rect,
    track_offset_label_should_show,
)
from heatmap_alignment_core import (  # noqa: E402
    TimelineH5DragSnapshot,
    AlignmentResourceRuntime,
    AlignmentSession,
    CameraTrack,
    ExportOverlaySettings,
    HeatmapPlotRenderer,
    HeatmapTrack,
    Leg2StanceIntervals,
    Leg2UltrasonicDatasourceSettings,
    Leg2UltrasonicSignalSeries,
    ResourceJobPresentation,
    SignalPlotViewSettings,
    build_alignment_resource_summaries,
    save_alignment_session,
    session_equivalent_for_pristine,
    validate_alignment_session,
)
from sparse_iq_peak_distance_core import (  # noqa: E402
    STATUS_DETECTED,
    FramePeakMeasurement,
    LoadedPeakDistanceDatasource,
    PeakDistanceMetadata,
)
from sparse_iq_heatmap_common import HeatmapAxes  # noqa: E402
from scipy.io import savemat


def _legend_item_labels(legend: object) -> list[str]:
    labels: list[str] = []
    for _sample, label in legend.items:
        labels.append(str(getattr(label, "text", label)))
    return labels


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


def _timeline_mouse_press(widget: AlignmentTimelineWidget, local_pos: QtCore.QPointF) -> None:
    global_pos = widget.mapToGlobal(local_pos.toPoint())
    event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonPress,
        local_pos,
        global_pos,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    widget.mousePressEvent(event)


def _timeline_mouse_move(widget: AlignmentTimelineWidget, local_pos: QtCore.QPointF) -> None:
    global_pos = widget.mapToGlobal(local_pos.toPoint())
    event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseMove,
        local_pos,
        global_pos,
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    widget.mouseMoveEvent(event)


def _timeline_mouse_release(widget: AlignmentTimelineWidget, local_pos: QtCore.QPointF) -> None:
    global_pos = widget.mapToGlobal(local_pos.toPoint())
    event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonRelease,
        local_pos,
        global_pos,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    widget.mouseReleaseEvent(event)


def test_timeline_playhead_press_takes_priority_over_camera_bar(
    qapplication: QApplication,
) -> None:
    range_model = TimelineRangeModel()
    range_model.set_track_state(
        camera_duration_s=5.0,
        heatmap_duration_s=5.0,
        camera_offset_s=0.0,
    )
    range_model.set_visible_range(-1.0, 6.0)
    widget = AlignmentTimelineWidget(range_model)
    widget.resize(900, 124)
    widget.show()
    qapplication.processEvents()
    widget.set_timeline_state(current_time_s=1.0)

    playhead_x = widget._time_to_x(1.0)
    camera_rect = widget._track_rect(0.0, 5.0, row=0)
    press_pos = QtCore.QPointF(playhead_x, camera_rect.center().y())
    assert widget._camera_track_hit_test(press_pos)
    assert widget._playhead_hit_test(press_pos)

    _timeline_mouse_press(widget, press_pos)

    assert widget._dragging_playhead
    assert not widget._dragging_camera


def test_timeline_h5_drag_shifts_camera_and_leg2_offsets_via_signal(
    qapplication: QApplication,
) -> None:
    range_model = TimelineRangeModel()
    range_model.set_track_state(
        camera_duration_s=4.0,
        heatmap_duration_s=5.0,
        camera_offset_s=1.0,
        leg2_duration_s=3.0,
        leg2_offset_s=2.0,
    )
    range_model.set_visible_range(-1.0, 6.0)
    widget = AlignmentTimelineWidget(range_model)
    widget.resize(900, 124)
    widget.show()
    qapplication.processEvents()
    widget.set_timeline_state(current_time_s=1.5)

    received: list[tuple[float, float, float, float, float]] = []

    def _on_h5_drag(*values: float) -> None:
        received.append(values)

    widget.h5_alignment_drag_changed.connect(_on_h5_drag)
    widget._dragging_h5 = True
    widget._h5_drag_anchor_s = 0.0
    widget._h5_drag_snapshot = TimelineH5DragSnapshot(
        range_start_s=-1.0,
        range_end_s=6.0,
        current_time_s=1.5,
        camera_offset_s=1.0,
        leg2_offset_s=2.0,
    )

    target_x = widget._time_to_x(0.5)
    move_pos = QtCore.QPointF(target_x, widget._track_rect(0.0, 5.0, row=1).center().y())
    _timeline_mouse_move(widget, move_pos)

    assert len(received) == 1
    range_start_s, range_end_s, current_time_s, camera_offset_s, leg2_offset_s = received[0]
    assert camera_offset_s == pytest.approx(1.5)
    assert leg2_offset_s == pytest.approx(2.5)
    assert current_time_s == pytest.approx(1.0)
    assert range_start_s == pytest.approx(-1.5)
    assert range_end_s == pytest.approx(5.5)


def test_timeline_h5_drag_repeat_move_at_same_pixel_is_stable(
    qapplication: QApplication,
) -> None:
    range_model = TimelineRangeModel()
    range_model.set_track_state(
        camera_duration_s=4.0,
        heatmap_duration_s=5.0,
        camera_offset_s=1.0,
        leg2_duration_s=3.0,
        leg2_offset_s=2.0,
    )
    range_model.set_visible_range(-1.0, 6.0)
    widget = AlignmentTimelineWidget(range_model)
    widget.resize(900, 124)
    widget.show()
    qapplication.processEvents()
    widget.set_timeline_state(current_time_s=1.5)

    received: list[tuple[float, float, float, float, float]] = []

    def _on_h5_drag(*values: float) -> None:
        received.append(values)
        range_model.set_visible_range(values[0], values[1])

    widget.h5_alignment_drag_changed.connect(_on_h5_drag)

    press_pos = widget._track_rect(0.0, 5.0, row=1).center()
    move_pos = QtCore.QPointF(widget._time_to_x(3.0), press_pos.y())

    _timeline_mouse_press(widget, press_pos)
    _timeline_mouse_move(widget, move_pos)
    _timeline_mouse_move(widget, move_pos)

    assert len(received) == 2
    assert received[0] == pytest.approx(received[1])
    widget.close()
    qapplication.processEvents()


def test_timeline_h5_drag_visible_range_follows_pointer_and_survives_release(
    qapplication: QApplication,
) -> None:
    window = HeatmapAlignmentWindow()
    window.session.camera_track = CameraTrack(duration_s=4.0)
    window.session.heatmap_track = HeatmapTrack(duration_s=5.0)
    window.session.timeline.current_time_s = 1.5
    window.session.timeline.offset_s = 1.0
    window._sync_previews(camera_access_hint="auto")

    timeline = window.timeline_view
    timeline.resize(900, 124)
    timeline.show()
    qapplication.processEvents()
    window.timeline_range_model.set_visible_range(-1.0, 6.0)

    press_pos = timeline._track_rect(0.0, 5.0, row=1).center()
    move_pos = QtCore.QPointF(timeline._time_to_x(3.0), press_pos.y())

    _timeline_mouse_press(timeline, press_pos)
    _timeline_mouse_move(timeline, move_pos)

    assert window.timeline_range_model.visible_range_s() == pytest.approx((-1.5, 5.5))
    assert window.session.timeline.current_time_s == pytest.approx(1.0)
    assert window.session.timeline.offset_s == pytest.approx(1.5)
    assert timeline._track_rect(0.0, 5.0, row=1).center().x() == pytest.approx(
        move_pos.x(), abs=1.0
    )

    _timeline_mouse_release(timeline, move_pos)

    assert window.timeline_range_model.visible_range_s() == pytest.approx((-1.5, 5.5))
    timeline.close()
    window.close()
    qapplication.processEvents()


def test_timeline_h5_only_press_does_not_start_h5_drag(
    qapplication: QApplication,
) -> None:
    range_model = TimelineRangeModel()
    range_model.set_track_state(
        camera_duration_s=0.0,
        heatmap_duration_s=5.0,
        camera_offset_s=0.0,
        leg2_duration_s=0.0,
        leg2_offset_s=0.0,
    )
    range_model.set_visible_range(-1.0, 6.0)
    initial_range = range_model.visible_range_s()
    widget = AlignmentTimelineWidget(range_model)
    widget.resize(900, 124)
    widget.show()
    qapplication.processEvents()
    widget.set_timeline_state(current_time_s=1.0)
    playhead_values: list[float] = []
    widget.playhead_changed.connect(playhead_values.append)

    h5_rect = widget._track_rect(0.0, 5.0, row=1)
    _timeline_mouse_press(widget, h5_rect.center())
    _timeline_mouse_move(
        widget,
        QtCore.QPointF(h5_rect.center().x() + 40.0, h5_rect.center().y()),
    )
    _timeline_mouse_release(widget, h5_rect.center())

    assert not widget._dragging_h5
    assert not widget._dragging_playhead
    assert playhead_values == []
    assert range_model.visible_range_s() == initial_range


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
                    "robustFC": np.array([1.0, 1.0, 0.0], dtype=np.float64),
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
        stance_intervals=Leg2StanceIntervals(
            start_times_s=np.array([], dtype=np.float64),
            end_times_s=np.array([], dtype=np.float64),
        ),
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
        "Stance phase",
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


def _ancestor_group_titles(widget: QtWidgets.QWidget) -> list[str]:
    titles: list[str] = []
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QtWidgets.QGroupBox):
            titles.append(parent.title())
        parent = parent.parentWidget()
    return titles


def _mapped_widget_rect(
    widget: QtWidgets.QWidget,
    *,
    relative_to: QtWidgets.QWidget,
) -> QtCore.QRect:
    return QtCore.QRect(widget.mapTo(relative_to, QtCore.QPoint(0, 0)), widget.size())


def test_render_panel_controls_moved_to_visualization_groups(
    qapplication: QApplication,
) -> None:
    window = HeatmapAlignmentWindow()
    qapplication.processEvents()

    group_titles = [group.title() for group in window.findChildren(QtWidgets.QGroupBox)]
    assert "Render" not in group_titles
    assert "Rendered Heatmap" in _ancestor_group_titles(window.color_min_spin)
    assert "Rendered Heatmap" in _ancestor_group_titles(window.color_max_spin)
    assert "Signals" in _ancestor_group_titles(window.leg2_signal_kind_combo)


def test_preview_and_signals_are_vertically_resizable(
    qapplication: QApplication,
) -> None:
    window = HeatmapAlignmentWindow()
    window.resize(900, 700)
    window.show()
    qapplication.processEvents()

    vertical_splitter = window.preview_signals_splitter
    horizontal_splitter = window.preview_splitter

    assert vertical_splitter.orientation() == QtCore.Qt.Orientation.Vertical
    assert vertical_splitter.childrenCollapsible() is False
    assert vertical_splitter.count() == 2
    assert vertical_splitter.widget(0) is horizontal_splitter
    assert vertical_splitter.widget(1) is window.signal_plot.parentWidget()
    assert vertical_splitter.sizes()[0] > vertical_splitter.sizes()[1]
    assert "Signals" in _ancestor_group_titles(window.signal_plot)

    assert horizontal_splitter.orientation() == QtCore.Qt.Orientation.Horizontal
    assert horizontal_splitter.childrenCollapsible() is False
    assert horizontal_splitter.parentWidget() is vertical_splitter
    assert horizontal_splitter.widget(0).minimumHeight() > 0
    assert horizontal_splitter.widget(1).minimumHeight() > 0
    assert window.signal_plot.parentWidget().minimumHeight() > 0
    assert window.camera_view.minimumSize() == QtCore.QSize(100, 40)
    assert window.viewport_view.minimumSize() == QtCore.QSize(100, 40)
    assert window.truth_view.minimumSize() == QtCore.QSize(100, 40)
    vertical_splitter.setSizes([80, 560])
    qapplication.processEvents()
    assert vertical_splitter.sizes()[0] >= horizontal_splitter.widget(1).minimumHeight()
    assert window.viewport_view.height() >= window.viewport_view.minimumHeight()
    assert window.truth_view.height() >= window.truth_view.minimumHeight()
    viewport_rect = _mapped_widget_rect(window.viewport_view, relative_to=window)
    viewport_controls_rect = _mapped_widget_rect(window.viewport_controls_widget, relative_to=window)
    truth_rect = _mapped_widget_rect(window.truth_view, relative_to=window)
    heatmap_controls_rect = _mapped_widget_rect(
        window.rendered_heatmap_controls_widget, relative_to=window
    )
    assert viewport_controls_rect.top() >= viewport_rect.bottom()
    assert heatmap_controls_rect.top() >= truth_rect.bottom()

    timeline_titles = [
        group.title()
        for group in window.findChildren(QtWidgets.QGroupBox)
        if group.title() == "Timeline"
    ]
    assert timeline_titles == ["Timeline"]
    timeline_group = next(
        group for group in window.findChildren(QtWidgets.QGroupBox) if group.title() == "Timeline"
    )
    assert timeline_group.parentWidget() is not vertical_splitter
    assert timeline_group.sizePolicy().verticalPolicy() == QtWidgets.QSizePolicy.Policy.Fixed
    window.close()


def test_color_min_max_spinboxes_step_by_100(qapplication: QApplication) -> None:
    window = HeatmapAlignmentWindow()
    assert window.color_min_spin.singleStep() == pytest.approx(100.0)
    assert window.color_max_spin.singleStep() == pytest.approx(100.0)


def test_color_min_lower_bound_is_zero(qapplication: QApplication) -> None:
    window = HeatmapAlignmentWindow()
    assert window.color_min_spin.minimum() == pytest.approx(0.0)


def test_loaded_peak_overlay_is_available_by_default(qapplication: QApplication) -> None:
    from heatmap_peak_distance_resource import PeakSeriesResource
    window = HeatmapAlignmentWindow()
    metadata = PeakDistanceMetadata(
        source_path="truth.h5",
        source_name="truth",
        session_index=0,
        group_index=0,
        entry_index=0,
        sensor_id=1,
        subsweep_index=0,
        source_frame_count=1,
        source_duration_s=0.1,
        ticks_per_second=1000,
        threshold=650.0,
        peak_extraction_method="sum_velocity",
        zero_velocity_bin_index=3,
        zero_velocity_m_s=0.0,
    )
    measurements = (
        FramePeakMeasurement(
            frame_index=4,
            source_tick=40,
            time_s=0.04,
            absolute_time=None,
            status=STATUS_DETECTED,
            peak_distance_m=1.25,
            candidate_peak_distance_m=1.25,
            peak_strength=20.0,
        ),
    )
    series = PeakSeriesResource(
        series_id="test-id",
        display_name="test peaks",
        provenance="imported",
        measurements=measurements,
        color="#3b82f6",
        metadata=metadata,
        json_path=Path("peaks.json"),
    )
    window._peak_series_list = [series]
    window._heatmap_peak_selector_id = series.series_id

    assert window._peak_overlay_for_frame(4) == pytest.approx((1.25, 0.0))


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


def test_resource_summaries_expose_pending_job_state() -> None:
    session = AlignmentSession(
        camera_track=CameraTrack(path="/tmp/example.mp4"),
        heatmap_track=HeatmapTrack(path="/tmp/example.h5"),
    )
    runtime = AlignmentResourceRuntime(
        camera_loaded=True,
        radar_h5_loaded=True,
        resource_jobs=(
            ResourceJobPresentation(
                kind="camera",
                phase="building",
                target_filename="replacement.mp4",
                detail="Building preview proxy for replacement.mp4...",
                cancellable=True,
            ),
        ),
    )

    summaries = build_alignment_resource_summaries(session, runtime)
    camera_summary = next(entry for entry in summaries if entry.kind == "camera")

    assert camera_summary.job_phase == "building"
    assert camera_summary.job_target_filename == "replacement.mp4"
    assert "replacement.mp4" in camera_summary.details
    assert "cancel" in camera_summary.actions


def test_export_disabled_while_resource_jobs_block(qapplication: QApplication) -> None:
    window = HeatmapAlignmentWindow()
    window.session.camera_track = CameraTrack(path="/tmp/example.mp4", duration_s=1.0, fps=1.0)
    window.session.heatmap_track = HeatmapTrack(path="/tmp/example.h5", duration_s=1.0, fps=1.0)
    window.camera_source = object()
    window.heatmap_source = object()
    window._refresh_resources_ui()
    assert window.export_synced_action.isEnabled() is True

    from heatmap_alignment_resource_jobs import begin_resource_job

    begin_resource_job(
        window._resource_job_manager.board(),
        "camera",
        target_path=Path("/tmp/other.mp4"),
        replaces_active=True,
    )
    window._refresh_resources_ui()
    assert window.export_synced_action.isEnabled() is False


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


def test_resource_summaries_expose_waiting_job_state() -> None:
    session = AlignmentSession(
        camera_track=CameraTrack(path="/tmp/example.mp4"),
        heatmap_track=HeatmapTrack(path="/tmp/example.h5"),
    )
    runtime = AlignmentResourceRuntime(
        camera_loaded=True,
        radar_h5_loaded=True,
        resource_jobs=(
            ResourceJobPresentation(
                kind="camera",
                phase="waiting",
                target_filename="replacement.mp4",
                detail="Waiting to build preview proxy for replacement.mp4...",
                cancellable=True,
            ),
        ),
    )

    summaries = build_alignment_resource_summaries(session, runtime)
    camera_summary = next(entry for entry in summaries if entry.kind == "camera")

    assert camera_summary.job_phase == "waiting"
    assert "Waiting" in camera_summary.details
    assert "replacement.mp4" in camera_summary.details


def test_resource_loading_overlays_support_empty_camera_view(
    qapplication: QApplication,
) -> None:
    window = HeatmapAlignmentWindow()

    window._update_resource_loading_overlays()

    assert window.camera_view._loading_overlay_active is False
    assert window.truth_view._loading_overlay_active is False
    assert window.viewport_view._loading_overlay_active is False


def test_image_preview_loading_overlay_suppresses_placeholder_title(
    qapplication: QApplication,
) -> None:
    from heatmap_alignment_gui import ImagePreview

    preview = ImagePreview("Rendered Heatmap")
    assert preview.text() == "Rendered Heatmap"

    preview.set_loading_overlay(True, "Loading trial01.h5...")
    assert preview.text() == ""

    preview.set_loading_overlay(False)
    assert preview.text() == "Rendered Heatmap"


def test_resource_loading_overlays_include_viewport_for_active_jobs(
    qapplication: QApplication,
) -> None:
    from heatmap_alignment_resource_jobs import begin_resource_job

    window = HeatmapAlignmentWindow()
    begin_resource_job(
        window._resource_job_manager.board(),
        "camera",
        target_path=Path("/tmp/replacement.mp4"),
        replaces_active=True,
        message="Loading replacement.mp4...",
    )

    window._update_resource_loading_overlays()

    assert window.viewport_view._loading_overlay_active is True
    assert "replacement.mp4" in window.viewport_view._loading_overlay_message


def test_resource_job_manager_cancel_completes_to_idle(
    qapplication: QApplication,
) -> None:
    from heatmap_alignment_gui import ResourceJobManager
    from heatmap_alignment_resource_jobs import begin_resource_job

    manager = ResourceJobManager()
    begin_resource_job(
        manager.board(),
        "radar_h5",
        target_path=Path("/tmp/trial.h5"),
        replaces_active=True,
    )

    assert manager.cancel_job("radar_h5") is True
    assert manager.board().radar_h5.phase == "idle"
    assert manager.board().radar_h5.cancel_requested is False


def test_resource_job_manager_cancel_before_success_discards_payload(
    qapplication: QApplication,
) -> None:
    from heatmap_alignment_gui import ResourceJobManager
    from heatmap_alignment_resource_jobs import LoadedH5ResourcePayload, begin_resource_job

    manager = ResourceJobManager()
    generation = begin_resource_job(
        manager.board(),
        "radar_h5",
        target_path=Path("/tmp/new.h5"),
        replaces_active=True,
    )
    manager.cancel_job("radar_h5")

    class _FakeRecord:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    record = _FakeRecord()
    payload = LoadedH5ResourcePayload(
        path=Path("/tmp/new.h5"),
        record=record,
        subsweep_idx=0,
        metadata=HeatmapTrack(path="/tmp/new.h5"),
        first_frame_shape=(10, 10),
    )

    manager._handle_job_success("radar_h5", generation, payload)

    assert record.closed is True
    assert manager.take_pending_result("radar_h5", generation) is None
    assert manager.board().radar_h5.phase == "idle"


def test_resource_job_manager_abandon_rejects_late_dispatch(
    qapplication: QApplication,
) -> None:
    from heatmap_alignment_gui import ResourceJobManager
    from heatmap_alignment_resource_jobs import LoadedH5ResourcePayload

    manager = ResourceJobManager()

    class _FakeRecord:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    record = _FakeRecord()
    payload = LoadedH5ResourcePayload(
        path=Path("/tmp/trial.h5"),
        record=record,
        subsweep_idx=0,
        metadata=HeatmapTrack(path="/tmp/trial.h5"),
        first_frame_shape=(10, 10),
    )

    manager.abandon_all_jobs()
    manager._dispatch_job_success("radar_h5", 1, payload)

    assert record.closed is True
    assert manager.take_pending_result("radar_h5", 1) is None


def test_start_resource_jobs_clear_abandoned_flag(
    qapplication: QApplication,
) -> None:
    from heatmap_alignment_gui import ResourceJobManager

    manager = ResourceJobManager()
    manager.abandon_all_jobs()
    assert manager._abandoned is True

    manager.start_camera_job(Path("/tmp/trial.mp4"), replaces_active=False)
    assert manager._abandoned is False

    manager.abandon_all_jobs()
    manager.start_h5_job(
        Path("/tmp/trial.h5"),
        replaces_active=False,
        session_idx=None,
        group_idx=None,
        entry_idx=None,
        subsweep_idx=None,
        color_min=0.0,
        color_max=3000.0,
        fixed_levels=True,
    )
    assert manager._abandoned is False


def test_resource_job_runnable_skips_dispatch_when_abandoned(
    qapplication: QApplication,
) -> None:
    from heatmap_alignment_gui import ResourceJobManager, _ResourceJobRunnable
    from heatmap_alignment_resource_jobs import LoadedH5ResourcePayload

    manager = ResourceJobManager()

    class _FakeRecord:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    record = _FakeRecord()
    payload = LoadedH5ResourcePayload(
        path=Path("/tmp/trial.h5"),
        record=record,
        subsweep_idx=0,
        metadata=HeatmapTrack(path="/tmp/trial.h5"),
        first_frame_shape=(10, 10),
    )

    manager.abandon_all_jobs()
    runnable = _ResourceJobRunnable(manager, "radar_h5", 1, lambda: payload)
    runnable.run()

    assert record.closed is True
    assert manager.take_pending_result("radar_h5", 1) is None


def test_resource_job_manager_supersede_cancels_prior_generation(
    qapplication: QApplication,
) -> None:
    from heatmap_alignment_gui import ResourceJobManager

    manager = ResourceJobManager()
    first_generation = manager.start_camera_job(
        Path("/tmp/first.mp4"),
        replaces_active=False,
    )
    second_generation = manager.start_camera_job(
        Path("/tmp/second.mp4"),
        replaces_active=False,
    )

    assert first_generation == 1
    assert second_generation == 2
    assert ("camera", first_generation) in manager._cancelled_generations


def test_resource_job_manager_abandon_releases_pending_h5_payload(
    qapplication: QApplication,
) -> None:
    from heatmap_alignment_gui import ResourceJobManager
    from heatmap_alignment_resource_jobs import LoadedH5ResourcePayload

    manager = ResourceJobManager()

    class _FakeRecord:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    record = _FakeRecord()
    payload = LoadedH5ResourcePayload(
        path=Path("/tmp/trial.h5"),
        record=record,
        subsweep_idx=0,
        metadata=HeatmapTrack(path="/tmp/trial.h5"),
        first_frame_shape=(10, 10),
    )
    manager._pending_results[("radar_h5", 1)] = payload

    manager.abandon_all_jobs()

    assert record.closed is True
    assert manager.board().radar_h5.phase == "idle"


def test_resource_job_manager_stale_success_releases_h5_payload(
    qapplication: QApplication,
) -> None:
    from heatmap_alignment_gui import ResourceJobManager
    from heatmap_alignment_resource_jobs import LoadedH5ResourcePayload, begin_resource_job

    manager = ResourceJobManager()
    old_generation = begin_resource_job(
        manager.board(),
        "radar_h5",
        target_path=Path("/tmp/old.h5"),
        replaces_active=False,
    )
    begin_resource_job(
        manager.board(),
        "radar_h5",
        target_path=Path("/tmp/new.h5"),
        replaces_active=False,
    )

    class _FakeRecord:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    record = _FakeRecord()
    payload = LoadedH5ResourcePayload(
        path=Path("/tmp/old.h5"),
        record=record,
        subsweep_idx=0,
        metadata=HeatmapTrack(path="/tmp/old.h5"),
        first_frame_shape=(10, 10),
    )

    manager._handle_job_success("radar_h5", old_generation, payload)

    assert record.closed is True
    assert manager.take_pending_result("radar_h5", old_generation) is None


def test_apply_h5_job_result_preserves_peak_series_for_different_replacement(
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from heatmap_alignment_resource_jobs import LoadedH5ResourcePayload
    from heatmap_peak_distance_resource import PeakSeriesResource

    window = HeatmapAlignmentWindow()
    # Populate with a peak series so we can verify it gets cleared.
    dummy_series = PeakSeriesResource(
        series_id="dummy",
        display_name="dummy",
        provenance="generated",
        measurements=(),
        color="#3b82f6",
    )
    window._peak_series_list = [dummy_series]

    monkeypatch.setattr(window, "_rebuild_overlay_plot_renderer", lambda: None)
    monkeypatch.setattr(window, "_reload_peak_distance_datasource_from_session", lambda: None)
    monkeypatch.setattr(window, "_update_heatmap_extent_labels", lambda: None)

    class _FakeHeatmapSource:
        def close(self) -> None:
            return None

    class _FakeRecord:
        session_idx = 0
        group_idx = 0
        entry_idx = 0
        duration_s = 1.0
        fps = 1.0
        results: list[object] = []

        def close(self) -> None:
            return None

    window._h5_replacement_backup = _H5ResourceBackup(
        heatmap_source=_FakeHeatmapSource(),
        heatmap_track=HeatmapTrack(path="/tmp/old.h5"),
        viewport_output_width=10,
        viewport_output_height=10,
    )
    payload = LoadedH5ResourcePayload(
        path=Path("/tmp/new.h5"),
        record=_FakeRecord(),
        subsweep_idx=0,
        metadata=HeatmapTrack(path="/tmp/new.h5"),
        first_frame_shape=(10, 10),
        resolved_fixed_color_level=100.0,
    )
    monkeypatch.setattr(
        "heatmap_alignment_gui.build_h5_truth_source_from_payload",
        lambda payload: _FakeHeatmapSource(),
    )

    window._apply_h5_job_result(payload)

    # Task 3.7: peak series are PRESERVED when a different H5 replaces the current one.
    assert len(window._peak_series_list) == 1
    assert window._peak_series_list[0].series_id == "dummy"
    assert window.session.heatmap_track.path == "/tmp/new.h5"


def test_restore_h5_replacement_backup_preserves_peak_datasource(
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = HeatmapAlignmentWindow()
    peak_marker = object()
    window.peak_distance_datasource = peak_marker

    class _FakeHeatmapSource:
        def close(self) -> None:
            return None

    backup_source = _FakeHeatmapSource()
    window._h5_replacement_backup = _H5ResourceBackup(
        heatmap_source=backup_source,
        heatmap_track=HeatmapTrack(path="/tmp/old.h5"),
        viewport_output_width=10,
        viewport_output_height=10,
    )
    window.heatmap_source = _FakeHeatmapSource()
    monkeypatch.setattr(window, "_rebuild_overlay_plot_renderer", lambda: None)
    monkeypatch.setattr(window, "_update_heatmap_extent_labels", lambda: None)

    window._restore_h5_replacement_backup()

    assert window.heatmap_source is backup_source
    assert window.peak_distance_datasource is peak_marker


def test_abandon_resource_jobs_clears_replacement_backups(
    qapplication: QApplication,
) -> None:
    window = HeatmapAlignmentWindow()
    window._camera_replacement_backup = object()
    window._h5_replacement_backup = object()

    window._abandon_resource_jobs()

    assert window._camera_replacement_backup is None
    assert window._h5_replacement_backup is None


def test_apply_camera_job_result_resets_incompatible_viewport(
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from heatmap_alignment_core import ProxyVideoResult, VideoProbe
    from heatmap_alignment_resource_jobs import CameraResourceJobResult

    window = HeatmapAlignmentWindow()
    incompatible_corners = [[100.0, 50.0], [900.0, 50.0], [900.0, 550.0], [100.0, 550.0]]
    window.session.viewport.corners = [list(point) for point in incompatible_corners]
    initialized: list[str] = []

    def _initialize_default_viewport_corners_native() -> None:
        initialized.append("default")
        window.session.viewport.corners = [[1.0, 1.0], [2.0, 1.0], [2.0, 2.0], [1.0, 2.0]]

    monkeypatch.setattr(
        window,
        "_initialize_default_viewport_corners_native",
        _initialize_default_viewport_corners_native,
    )
    monkeypatch.setattr(window, "_load_current_camera_frame", lambda access_hint="auto": None)
    monkeypatch.setattr(window, "_refresh_camera_view_corners", lambda: None)
    monkeypatch.setattr(window, "_initialize_default_export_overlay_if_needed", lambda: None)
    monkeypatch.setattr(window, "_native_viewport_corners", lambda: np.asarray(window.session.viewport.corners))

    class _FakeCameraSource:
        def close(self) -> None:
            return None

    window._camera_replacement_backup = _CameraResourceBackup(
        camera_source=_FakeCameraSource(),
        reference_width=1000,
        reference_height=600,
        camera_track=CameraTrack(path="/tmp/old.mp4"),
        current_camera_frame=None,
        viewport_corners=[list(point) for point in incompatible_corners],
        export_overlay=ExportOverlaySettings(),
    )

    monkeypatch.setattr(
        "heatmap_alignment_gui.CameraVideoSource",
        lambda path: _FakeCameraSource(),
    )

    probe = VideoProbe(
        path=Path("/tmp/new.mp4"),
        fps=30.0,
        frame_count=100,
        duration_s=3.0,
        width=1600,
        height=900,
    )
    result = CameraResourceJobResult(
        source_path=Path("/tmp/new.mp4"),
        proxy_result=ProxyVideoResult(
            source_path=Path("/tmp/new.mp4"),
            display_path=Path("/tmp/new.mp4"),
            source_probe=probe,
            proxy_path=None,
            state="original",
        ),
        camera_track=CameraTrack(path="/tmp/new.mp4", fps=30.0, duration_s=3.0, frame_count=100),
    )

    window._apply_camera_job_result(result)

    assert initialized == ["default"]
    assert window.session.viewport.corners == [[1.0, 1.0], [2.0, 1.0], [2.0, 2.0], [1.0, 2.0]]


# ---------------------------------------------------------------------------
# Session reconcile integration tests (tasks 4.1–4.7)
# ---------------------------------------------------------------------------


def _make_session_file(
    tmp_path: Path,
    *,
    camera_path: str = "",
    h5_path: str = "",
    session_idx: int = 0,
    group_idx: int = 0,
    entry_idx: int = 0,
    subsweep_idx: int = 0,
    offset_s: float = 0.0,
) -> Path:
    session = AlignmentSession(
        camera_track=CameraTrack(path=camera_path),
        heatmap_track=HeatmapTrack(
            path=h5_path,
            session_idx=session_idx,
            group_idx=group_idx,
            entry_idx=entry_idx,
            subsweep_idx=subsweep_idx,
        ),
    )
    session.timeline.offset_s = offset_s
    path = tmp_path / "session.json"
    save_alignment_session(session, path)
    return path


def test_reconcile_camera_keep_does_not_abandon_inflight_job(
    tmp_path: Path,
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 4.1: same camera identity → keep; in-flight job is not abandoned."""
    from heatmap_alignment_resource_jobs import begin_resource_job

    camera_file = tmp_path / "video.mp4"
    camera_file.write_bytes(b"")

    session_path = _make_session_file(tmp_path, camera_path=str(camera_file))

    window = HeatmapAlignmentWindow()

    # Simulate an in-flight camera job for the same path.
    begin_resource_job(
        window._resource_job_manager.board(),
        "camera",
        target_path=camera_file,
        replaces_active=False,
    )
    initial_generation = window._resource_job_manager.board().camera.generation

    load_camera_calls: list[Path] = []
    monkeypatch.setattr(
        window,
        "load_camera_from_path",
        lambda p, **kwargs: load_camera_calls.append(p),
    )

    window.load_session_from_path(session_path)

    # The in-flight job must not have been abandoned (generation unchanged).
    assert window._resource_job_manager.board().camera.generation == initial_generation
    assert load_camera_calls == [], "load_camera_from_path must not be called when identity matches"


def test_reconcile_h5_keep_does_not_abandon_inflight_job(
    tmp_path: Path,
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 4.1: same H5 identity → keep; in-flight job is not abandoned."""
    from heatmap_alignment_core import H5SlotIdentity
    from heatmap_alignment_resource_jobs import begin_resource_job

    h5_file = tmp_path / "record.h5"
    h5_file.write_bytes(b"")

    session_path = _make_session_file(tmp_path, h5_path=str(h5_file), subsweep_idx=0)

    window = HeatmapAlignmentWindow()

    # Pre-set the inflight H5 identity matching the session.
    window._inflight_h5_identity = H5SlotIdentity(
        path=str(h5_file), session_idx=0, group_idx=0, entry_idx=0, subsweep_idx=0
    )
    begin_resource_job(
        window._resource_job_manager.board(),
        "radar_h5",
        target_path=h5_file,
        replaces_active=False,
    )
    initial_generation = window._resource_job_manager.board().radar_h5.generation

    load_h5_calls: list[Path] = []
    monkeypatch.setattr(
        window,
        "load_h5_from_path",
        lambda p, **kwargs: load_h5_calls.append(p),
    )

    window.load_session_from_path(session_path)

    assert window._resource_job_manager.board().radar_h5.generation == initial_generation
    assert load_h5_calls == [], "load_h5_from_path must not be called when identity matches"


def test_reconcile_h5_load_when_identity_changes(
    tmp_path: Path,
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 4.2: changed H5 path → reconcile as load."""
    old_h5 = tmp_path / "old.h5"
    new_h5 = tmp_path / "new.h5"
    old_h5.write_bytes(b"")
    new_h5.write_bytes(b"")

    session_path = _make_session_file(tmp_path, h5_path=str(new_h5))

    window = HeatmapAlignmentWindow()
    # Pretend old H5 is loaded.
    window.session.heatmap_track = HeatmapTrack(path=str(old_h5))

    class _FakeHeatmapSource:
        path = old_h5
        record = type("rec", (), {"session_idx": 0, "group_idx": 0, "entry_idx": 0})()
        subsweep_idx = 0

    window.heatmap_source = _FakeHeatmapSource()  # type: ignore[assignment]

    load_h5_calls: list[Path] = []
    monkeypatch.setattr(
        window,
        "load_h5_from_path",
        lambda p, **kwargs: load_h5_calls.append(p),
    )
    monkeypatch.setattr(window, "_sync_previews", lambda **kwargs: None)

    window.load_session_from_path(session_path)

    assert len(load_h5_calls) == 1
    assert load_h5_calls[0] == new_h5


def test_reconcile_camera_unload_when_session_omits_path(
    tmp_path: Path,
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 4.3: empty camera path in session → unload when camera was loaded."""
    session_path = _make_session_file(tmp_path, camera_path="")

    window = HeatmapAlignmentWindow()
    # Pretend a camera was loaded.
    class _FakeCameraSource:
        def close(self) -> None:
            pass
    window.camera_source = _FakeCameraSource()  # type: ignore[assignment]
    window.session.camera_track = CameraTrack(path="/tmp/old.mp4")

    unloaded: list[str] = []
    original_unload_camera = window.unload_camera_video

    def _track_unload(**kwargs: object) -> None:
        unloaded.append("camera")
        original_unload_camera(**kwargs)

    monkeypatch.setattr(window, "unload_camera_video", _track_unload)

    window.load_session_from_path(session_path)

    assert "camera" in unloaded


def test_reconcile_h5_unload_when_session_omits_path(
    tmp_path: Path,
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 4.4: empty H5 path in session → unload when H5 was loaded."""
    session_path = _make_session_file(tmp_path, h5_path="")

    window = HeatmapAlignmentWindow()

    class _FakeHeatmapSource:
        path = Path("/tmp/old.h5")
        record = type("rec", (), {"session_idx": 0, "group_idx": 0, "entry_idx": 0, "close": lambda self: None})()
        subsweep_idx = 0
        def close(self) -> None:
            pass

    window.heatmap_source = _FakeHeatmapSource()  # type: ignore[assignment]
    window.session.heatmap_track = HeatmapTrack(path="/tmp/old.h5")

    unloaded: list[str] = []
    original_unload_h5 = window.unload_h5_recording

    def _track_unload(**kwargs: object) -> None:
        unloaded.append("h5")
        original_unload_h5(**kwargs)

    monkeypatch.setattr(window, "unload_h5_recording", _track_unload)

    window.load_session_from_path(session_path)

    assert "h5" in unloaded


def test_reconcile_leg2_and_peak_unload_when_session_omits_paths(
    tmp_path: Path,
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 4.5: empty peak/Leg2 paths → unload when datasources were loaded."""
    from heatmap_peak_distance_resource import PeakSeriesResource

    session_path = _make_session_file(tmp_path)  # no peak or leg2 paths

    window = HeatmapAlignmentWindow()
    # Pretend a peak series is loaded with a path so reconcile treats it as loaded.
    dummy_series = PeakSeriesResource(
        series_id="dummy",
        display_name="dummy",
        provenance="imported",
        measurements=(),
        color="#3b82f6",
        json_path=Path("/tmp/peaks.json"),
    )
    window._peak_series_list = [dummy_series]
    # Pretend a Leg2 datasource is loaded so reconcile can decide to unload it.
    window.session.leg2_ultrasonic_datasource.path = "/tmp/leg2.mat"
    window.leg2_ultrasonic_datasource = object()  # type: ignore[assignment]

    cleared: list[str] = []

    def _track_clear_leg2(**kwargs: object) -> None:
        cleared.append("leg2")
        window.leg2_ultrasonic_datasource = None

    monkeypatch.setattr(window, "_clear_leg2_ultrasonic_datasource", _track_clear_leg2)
    # Prevent real reload calls.
    monkeypatch.setattr(window, "_reload_peak_distance_datasource_from_session", lambda: None)
    monkeypatch.setattr(window, "_reload_leg2_ultrasonic_datasource_from_session", lambda: None)

    window.load_session_from_path(session_path)

    # Peak series are cleared directly (not via _clear_peak_distance_datasource).
    assert window._peak_series_list == []
    assert "leg2" in cleared


def test_reconcile_session_fields_applied_after_camera_keep(
    tmp_path: Path,
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 4.6: session fields (e.g. timeline offset) applied even when camera slot uses keep."""
    camera_file = tmp_path / "video.mp4"
    camera_file.write_bytes(b"")

    session_path = _make_session_file(tmp_path, camera_path=str(camera_file), offset_s=2.5)

    window = HeatmapAlignmentWindow()
    # Simulate camera already loaded with same path.
    class _FakeCameraSource:
        def close(self) -> None:
            pass
    window.camera_source = _FakeCameraSource()  # type: ignore[assignment]
    window.session.camera_track = CameraTrack(path=str(camera_file))

    # Prevent new loads and preview rendering.
    monkeypatch.setattr(window, "load_camera_from_path", lambda p, **kwargs: None)
    monkeypatch.setattr(window, "_sync_previews", lambda **kwargs: None)
    monkeypatch.setattr(window, "_load_current_camera_frame", lambda access_hint="auto": None)
    monkeypatch.setattr(window, "_refresh_camera_view_corners", lambda: None)

    window.load_session_from_path(session_path)

    # Session fields from the JSON must be applied regardless of keep.
    assert window.session.timeline.offset_s == pytest.approx(2.5)


def test_reconcile_session_fields_applied_after_h5_keep(
    tmp_path: Path,
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 4.7: session fields applied when H5 slot uses keep."""
    h5_file = tmp_path / "record.h5"
    h5_file.write_bytes(b"")

    session_path = _make_session_file(tmp_path, h5_path=str(h5_file), offset_s=1.25)

    window = HeatmapAlignmentWindow()

    class _FakeHeatmapSource:
        path = h5_file
        record = type("rec", (), {"session_idx": 0, "group_idx": 0, "entry_idx": 0})()
        subsweep_idx = 0

    window.heatmap_source = _FakeHeatmapSource()  # type: ignore[assignment]
    window.session.heatmap_track = HeatmapTrack(
        path=str(h5_file), session_idx=0, group_idx=0, entry_idx=0, subsweep_idx=0
    )
    window._inflight_h5_identity = None

    monkeypatch.setattr(window, "load_h5_from_path", lambda p, **kwargs: None)
    monkeypatch.setattr(window, "_reload_peak_distance_datasource_from_session", lambda: None)
    monkeypatch.setattr(window, "_sync_previews", lambda **kwargs: None)

    window.load_session_from_path(session_path)

    assert window.session.timeline.offset_s == pytest.approx(1.25)


# ---------------------------------------------------------------------------
# Dirty session and unsaved prompts (dirty-session-prompts)
# ---------------------------------------------------------------------------


def test_session_equivalent_for_pristine_matches_default() -> None:
    assert session_equivalent_for_pristine(AlignmentSession(), AlignmentSession())


def test_save_session_without_loaded_camera_or_h5(
    tmp_path: Path,
    qapplication: QApplication,
) -> None:
    session_path = tmp_path / "paths_only.json"
    window = HeatmapAlignmentWindow()
    window.session.camera_track.path = str(tmp_path / "missing_camera.mp4")
    window.session.heatmap_track.path = str(tmp_path / "missing.h5")
    window._current_session_path = session_path

    window._write_session_to_path(session_path)

    assert session_path.is_file()
    assert window._session_dirty is False


def test_title_shows_asterisk_when_dirty_and_clears_after_save(
    tmp_path: Path,
    qapplication: QApplication,
) -> None:
    session_path = tmp_path / "session.json"
    save_alignment_session(AlignmentSession(), session_path)

    window = HeatmapAlignmentWindow()
    window.load_session_from_path(session_path)
    assert "*" not in window.windowTitle()

    window.offset_spin.setValue(0.5)
    qapplication.processEvents()
    assert window._session_dirty is True
    assert window.windowTitle().endswith("*")

    window._write_session_to_path(session_path)
    assert window._session_dirty is False
    assert "*" not in window.windowTitle()


def test_cancel_on_quit_leaves_session_dirty(
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = HeatmapAlignmentWindow()
    window._mark_session_dirty()

    monkeypatch.setattr(
        window,
        "_prompt_save_discard_cancel",
        lambda action: "cancel",
    )

    event = QtGui.QCloseEvent()
    window.closeEvent(event)

    assert event.isAccepted() is False
    assert window._session_dirty is True


def test_dont_save_then_open_proceeds(
    tmp_path: Path,
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    save_alignment_session(AlignmentSession(), first_path)
    save_alignment_session(AlignmentSession(), second_path)

    window = HeatmapAlignmentWindow()
    window.load_session_from_path(first_path)
    window._mark_session_dirty()

    monkeypatch.setattr(
        window,
        "_prompt_save_discard_cancel",
        lambda action: "discard",
    )
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(second_path), ""),
    )

    window._load_session()

    assert window._current_session_path == second_path
    assert window._session_dirty is False


def test_dont_save_then_cancel_open_dialog_stays_dirty(
    tmp_path: Path,
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_path = tmp_path / "session.json"
    save_alignment_session(AlignmentSession(), session_path)

    window = HeatmapAlignmentWindow()
    window.load_session_from_path(session_path)
    window._mark_session_dirty()

    monkeypatch.setattr(
        window,
        "_prompt_save_discard_cancel",
        lambda action: "discard",
    )
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: ("", ""),
    )

    window._load_session()

    assert window._current_session_path == session_path
    assert window._session_dirty is True


def test_save_from_prompt_calls_write_path(
    tmp_path: Path,
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_path = tmp_path / "session.json"
    save_alignment_session(AlignmentSession(), session_path)

    window = HeatmapAlignmentWindow()
    window.load_session_from_path(session_path)
    window._mark_session_dirty()

    write_calls: list[Path] = []
    monkeypatch.setattr(
        window,
        "_write_session_to_path",
        lambda path: write_calls.append(path) or True,
    )
    monkeypatch.setattr(
        window,
        "_prompt_save_discard_cancel",
        lambda action: "save",
    )

    window._close_session()

    assert write_calls == [session_path]


def test_pristine_close_session_does_not_show_dialog(
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = HeatmapAlignmentWindow()
    prompt_called = False
    confirm_called = False

    def _fail_prompt(*_args: object, **_kwargs: object) -> str:
        nonlocal prompt_called
        prompt_called = True
        return "cancel"

    def _fail_confirm() -> bool:
        nonlocal confirm_called
        confirm_called = True
        return False

    monkeypatch.setattr(window, "_prompt_save_discard_cancel", _fail_prompt)
    monkeypatch.setattr(window, "_confirm_close_session_clean", _fail_confirm)
    monkeypatch.setattr(window, "_reset_session_after_close", lambda: None)

    window._close_session()

    assert prompt_called is False
    assert confirm_called is False


def test_clean_non_pristine_close_session_shows_yes_no_only(
    tmp_path: Path,
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_path = tmp_path / "session.json"
    save_alignment_session(AlignmentSession(), session_path)

    window = HeatmapAlignmentWindow()
    window.load_session_from_path(session_path)

    tri_state_called = False

    def _fail_tri_state(*_args: object, **_kwargs: object) -> str:
        nonlocal tri_state_called
        tri_state_called = True
        return "cancel"

    monkeypatch.setattr(window, "_prompt_save_discard_cancel", _fail_tri_state)
    monkeypatch.setattr(window, "_confirm_close_session_clean", lambda: False)

    window._close_session()

    assert tri_state_called is False


def test_clean_quit_does_not_show_dialog(
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = HeatmapAlignmentWindow()
    prompt_called = False

    monkeypatch.setattr(
        window,
        "_prompt_save_discard_cancel",
        lambda action: (_ for _ in ()).throw(AssertionError("unexpected prompt")) or "cancel",
    )

    def _track_prompt(*_args: object, **_kwargs: object) -> str:
        nonlocal prompt_called
        prompt_called = True
        return "cancel"

    monkeypatch.setattr(window, "_prompt_save_discard_cancel", _track_prompt)
    monkeypatch.setattr(window, "_close_sources", lambda: None)
    monkeypatch.setattr(
        window.viewport_source_resolution_timer,
        "stop",
        lambda: None,
    )
    monkeypatch.setattr(window._source_resolution_thread, "quit", lambda: None)
    monkeypatch.setattr(window._source_resolution_thread, "wait", lambda: None)

    event = QtGui.QCloseEvent()
    window.closeEvent(event)

    assert prompt_called is False
    assert event.isAccepted() is True


def test_no_dirty_after_camera_job_completion_on_session_open(
    tmp_path: Path,
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from heatmap_alignment_resource_jobs import CameraResourceJobResult, ProxyVideoResult
    from heatmap_alignment_core import VideoProbe

    camera_file = tmp_path / "video.mp4"
    camera_file.write_bytes(b"")
    session_path = _make_session_file(tmp_path, camera_path=str(camera_file))

    window = HeatmapAlignmentWindow()
    window.load_session_from_path(session_path)

    probe = VideoProbe(
        path=camera_file,
        fps=30.0,
        frame_count=100,
        duration_s=3.0,
        width=640,
        height=480,
    )
    result = CameraResourceJobResult(
        source_path=camera_file,
        proxy_result=ProxyVideoResult(
            source_path=camera_file,
            display_path=camera_file,
            source_probe=probe,
            proxy_path=None,
            state="original",
        ),
        camera_track=CameraTrack(path=str(camera_file), fps=30.0, duration_s=3.0, frame_count=100),
    )
    class _FakeCameraSource:
        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "heatmap_alignment_gui.CameraVideoSource",
        lambda path: _FakeCameraSource(),
    )
    monkeypatch.setattr(window, "_initialize_default_export_overlay_if_needed", lambda: None)
    monkeypatch.setattr(window, "_load_current_camera_frame", lambda access_hint="auto": None)
    monkeypatch.setattr(window, "_refresh_camera_view_corners", lambda: None)
    monkeypatch.setattr(window, "_native_viewport_corners", lambda: None)
    monkeypatch.setattr(window, "_initialize_default_viewport_corners_native", lambda: None)
    monkeypatch.setattr(window, "_update_controls_enabled_state", lambda: None)
    monkeypatch.setattr(window, "_refresh_resources_ui", lambda: None)

    window._apply_camera_job_result(result)

    assert window._session_dirty is False
    assert "*" not in window.windowTitle()


def test_clear_all_resources_marks_dirty(
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = HeatmapAlignmentWindow()
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "question",
        lambda *args, **kwargs: QtWidgets.QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(window, "unload_camera_video", lambda **kwargs: None)
    monkeypatch.setattr(window, "unload_h5_recording", lambda **kwargs: None)
    monkeypatch.setattr(window, "_clear_peak_distance_datasource", lambda **kwargs: None)
    monkeypatch.setattr(window, "_clear_leg2_ultrasonic_datasource", lambda **kwargs: None)

    window.clear_all_resources()

    assert window._session_dirty is True



def test_save_from_prompt_aborted_when_validation_fails(
    tmp_path: Path,
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = HeatmapAlignmentWindow()
    window._mark_session_dirty()
    window.session.viewport.corners = [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]

    monkeypatch.setattr(
        window,
        "_prompt_save_discard_cancel",
        lambda action: "save",
    )
    reset_called = False

    def _track_reset() -> None:
        nonlocal reset_called
        reset_called = True

    monkeypatch.setattr(window, "_reset_session_after_close", _track_reset)

    window._close_session()

    assert window._session_dirty is True
    assert reset_called is False
    with pytest.raises(ValueError):
        validate_alignment_session(window.session, allow_missing_sources=True)


# ---------------------------------------------------------------------------
# Signals playhead scrubbing tests
# ---------------------------------------------------------------------------


def _make_signal_plot_with_range(
    qapplication: QApplication,
    *,
    x_start: float,
    x_end: float,
    width: int = 800,
    height: int = 300,
    current_time_s: float = 0.0,
) -> SignalPlotWidget:
    plot = SignalPlotWidget()
    plot.resize(width, height)
    plot.show()
    qapplication.processEvents()
    plot.getPlotItem().getViewBox().setXRange(x_start, x_end, padding=0.0)
    qapplication.processEvents()
    plot.set_current_time_s(current_time_s)
    qapplication.processEvents()
    return plot


def _signal_plot_mouse_press(widget: SignalPlotWidget, local_pos: QtCore.QPointF) -> None:
    event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonPress,
        local_pos,
        widget.mapToGlobal(local_pos.toPoint()),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    widget.mousePressEvent(event)


def _signal_plot_mouse_move(widget: SignalPlotWidget, local_pos: QtCore.QPointF) -> None:
    event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseMove,
        local_pos,
        widget.mapToGlobal(local_pos.toPoint()),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    widget.mouseMoveEvent(event)


def _signal_plot_mouse_release(widget: SignalPlotWidget, local_pos: QtCore.QPointF) -> None:
    event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonRelease,
        local_pos,
        widget.mapToGlobal(local_pos.toPoint()),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    widget.mouseReleaseEvent(event)


def test_signal_playhead_drag_emits_scrubbed_signal(
    qapplication: QApplication,
) -> None:
    plot = _make_signal_plot_with_range(qapplication, x_start=0.0, x_end=10.0, current_time_s=5.0)

    scrubbed: list[float] = []
    plot.playhead_scrubbed.connect(scrubbed.append)

    playhead_x = plot._playhead_x_in_widget()
    assert playhead_x is not None

    press_pos = QtCore.QPointF(playhead_x, plot.height() / 2.0)
    _signal_plot_mouse_press(plot, press_pos)
    assert plot._dragging_playhead

    move_pos = QtCore.QPointF(playhead_x + 10.0, plot.height() / 2.0)
    _signal_plot_mouse_move(plot, move_pos)

    _signal_plot_mouse_release(plot, move_pos)
    assert not plot._dragging_playhead

    assert len(scrubbed) >= 2
    assert scrubbed[0] == pytest.approx(5.0, abs=0.5)
    assert scrubbed[-1] > scrubbed[0]


def test_signal_playhead_drag_in_manual_x_mode_uses_signal_plot_x_scale(
    qapplication: QApplication,
) -> None:
    plot = _make_signal_plot_with_range(qapplication, x_start=2.0, x_end=4.0, current_time_s=3.0)
    plot.set_view_settings(
        SignalPlotViewSettings(x_range_mode="manual", y_range_mode="auto", manual_x_range=(2.0, 4.0))
    )
    qapplication.processEvents()

    scrubbed: list[float] = []
    plot.playhead_scrubbed.connect(scrubbed.append)

    playhead_x = plot._playhead_x_in_widget()
    assert playhead_x is not None

    press_pos = QtCore.QPointF(playhead_x, plot.height() / 2.0)
    _signal_plot_mouse_press(plot, press_pos)
    assert plot._dragging_playhead

    move_pos = QtCore.QPointF(playhead_x + 20.0, plot.height() / 2.0)
    _signal_plot_mouse_move(plot, move_pos)
    _signal_plot_mouse_release(plot, move_pos)

    assert len(scrubbed) >= 2
    moved_time = scrubbed[-1]
    assert 2.0 <= moved_time <= 4.0


def test_signal_playhead_drag_preserves_ranges_modes_and_offsets(
    qapplication: QApplication,
) -> None:
    range_model = TimelineRangeModel()
    range_model.set_track_state(
        camera_duration_s=5.0,
        heatmap_duration_s=5.0,
        camera_offset_s=1.5,
        leg2_duration_s=3.0,
        leg2_offset_s=0.5,
    )
    range_model.set_visible_range(0.0, 10.0)

    plot = _make_signal_plot_with_range(qapplication, x_start=0.0, x_end=10.0, current_time_s=5.0)
    plot.set_view_settings(
        SignalPlotViewSettings(x_range_mode="manual", y_range_mode="manual", manual_x_range=(0.0, 10.0))
    )
    plot.attach_timeline_range_model(range_model)
    qapplication.processEvents()

    vb = plot.getPlotItem().getViewBox()
    x_range_before = vb.viewRange()[0]
    y_range_before = vb.viewRange()[1]
    timeline_range_before = range_model.visible_range_s()
    camera_offset_before = range_model.camera_offset_s
    leg2_offset_before = range_model.leg2_offset_s

    scrubbed: list[float] = []
    plot.playhead_scrubbed.connect(scrubbed.append)

    playhead_x = plot._playhead_x_in_widget()
    assert playhead_x is not None

    press_pos = QtCore.QPointF(playhead_x, plot.height() / 2.0)
    _signal_plot_mouse_press(plot, press_pos)
    move_pos = QtCore.QPointF(playhead_x + 15.0, plot.height() / 2.0)
    _signal_plot_mouse_move(plot, move_pos)
    _signal_plot_mouse_release(plot, move_pos)
    qapplication.processEvents()

    assert vb.viewRange()[0] == pytest.approx(x_range_before, abs=1e-6)
    assert vb.viewRange()[1] == pytest.approx(y_range_before, abs=1e-6)
    assert plot.view_settings().x_range_mode == "manual"
    assert plot.view_settings().y_range_mode == "manual"
    assert range_model.visible_range_s() == pytest.approx(timeline_range_before, abs=1e-6)
    assert range_model.camera_offset_s == pytest.approx(camera_offset_before, abs=1e-6)
    assert range_model.leg2_offset_s == pytest.approx(leg2_offset_before, abs=1e-6)
    assert len(scrubbed) >= 1


def test_signal_plot_background_click_does_not_scrub(
    qapplication: QApplication,
) -> None:
    plot = _make_signal_plot_with_range(qapplication, x_start=0.0, x_end=10.0, current_time_s=5.0)

    scrubbed: list[float] = []
    plot.playhead_scrubbed.connect(scrubbed.append)

    playhead_x = plot._playhead_x_in_widget()
    assert playhead_x is not None
    far_x = playhead_x + plot._playhead_hit_half_width_px * 3.0
    press_pos = QtCore.QPointF(far_x, plot.height() / 2.0)
    _signal_plot_mouse_press(plot, press_pos)

    assert not plot._dragging_playhead
    assert scrubbed == []


def test_signal_playhead_out_of_bounds_drag_clamps_and_releases_cleanly(
    qapplication: QApplication,
) -> None:
    plot = _make_signal_plot_with_range(qapplication, x_start=0.0, x_end=10.0, current_time_s=5.0)

    scrubbed: list[float] = []
    plot.playhead_scrubbed.connect(scrubbed.append)

    playhead_x = plot._playhead_x_in_widget()
    assert playhead_x is not None

    press_pos = QtCore.QPointF(playhead_x, plot.height() / 2.0)
    _signal_plot_mouse_press(plot, press_pos)
    assert plot._dragging_playhead

    far_right_pos = QtCore.QPointF(plot.width() + 200.0, plot.height() / 2.0)
    _signal_plot_mouse_move(plot, far_right_pos)
    assert len(scrubbed) >= 2
    vb = plot.getPlotItem().getViewBox()
    x_max = vb.viewRange()[0][1]
    assert scrubbed[-1] == pytest.approx(x_max, abs=1e-6)

    _signal_plot_mouse_release(plot, far_right_pos)
    assert not plot._dragging_playhead


# ---------------------------------------------------------------------------
# Task 6.4 – Generate dialog, heatmap selector, row-scoped save/unload
# ---------------------------------------------------------------------------


def test_generate_peak_series_dialog_defaults(qapplication: QApplication) -> None:
    """GeneratePeakSeriesDialog initialises with sum_velocity algorithm and default threshold."""
    from heatmap_alignment_gui import GeneratePeakSeriesDialog
    from sparse_iq_peak_distance_core import PEAK_EXTRACTION_METHOD_SUM_VELOCITY, DEFAULT_PEAK_THRESHOLD

    dlg = GeneratePeakSeriesDialog()
    assert dlg.algorithm_id == PEAK_EXTRACTION_METHOD_SUM_VELOCITY
    assert dlg.threshold == pytest.approx(DEFAULT_PEAK_THRESHOLD)


def test_generate_peak_series_dialog_display_name_uses_placeholder_when_empty(qapplication: QApplication) -> None:
    """display_name returns a generated placeholder when the name field is empty."""
    from heatmap_alignment_gui import GeneratePeakSeriesDialog

    dlg = GeneratePeakSeriesDialog(default_threshold=650.0)
    # Name field is empty by default → display_name falls back to generated placeholder.
    name = dlg.display_name
    assert "sum v" in name
    assert "650" in name


def test_generate_peak_series_dialog_display_name_uses_entered_text(qapplication: QApplication) -> None:
    """display_name returns user-entered text when the name field is not empty."""
    from heatmap_alignment_gui import GeneratePeakSeriesDialog

    dlg = GeneratePeakSeriesDialog()
    dlg._name_edit.setText("my custom name")
    assert dlg.display_name == "my custom name"


def test_generate_peak_series_dialog_algorithm_selection(qapplication: QApplication) -> None:
    """Selecting v0 slice sets algorithm_id to zero_velocity_slice."""
    from heatmap_alignment_gui import GeneratePeakSeriesDialog
    from sparse_iq_peak_distance_core import PEAK_EXTRACTION_METHOD_ZERO_VELOCITY_SLICE

    dlg = GeneratePeakSeriesDialog()
    dlg._algo_combo.setCurrentIndex(1)  # second item is zero_velocity_slice
    assert dlg.algorithm_id == PEAK_EXTRACTION_METHOD_ZERO_VELOCITY_SLICE
    assert "v0 slice" in dlg.display_name


def test_unload_peak_series_resets_heatmap_selector_id(qapplication: QApplication) -> None:
    """Task 4.6: unloading the selected peak series resets _heatmap_peak_selector_id to None."""
    from heatmap_peak_distance_resource import PeakSeriesResource

    window = HeatmapAlignmentWindow()
    series = PeakSeriesResource(
        series_id="sel-id", display_name="test", provenance="generated",
        measurements=(), color="#3b82f6", unsaved=False,
    )
    window._peak_series_list = [series]
    window._heatmap_peak_selector_id = series.series_id

    window._unload_peak_series(series.series_id, confirm=False)

    assert window._peak_series_list == []
    assert window._heatmap_peak_selector_id is None


def test_unload_peak_series_preserves_other_series(qapplication: QApplication) -> None:
    """Unloading one peak series does not affect other peak series."""
    from heatmap_peak_distance_resource import PeakSeriesResource

    window = HeatmapAlignmentWindow()
    s1 = PeakSeriesResource(series_id="id1", display_name="a", provenance="generated", measurements=(), color="#3b82f6")
    s2 = PeakSeriesResource(series_id="id2", display_name="b", provenance="imported", measurements=(), color="#f59e0b")
    window._peak_series_list = [s1, s2]
    window._heatmap_peak_selector_id = s2.series_id

    window._unload_peak_series(s1.series_id, confirm=False)

    assert len(window._peak_series_list) == 1
    assert window._peak_series_list[0].series_id == "id2"
    assert window._heatmap_peak_selector_id == "id2"  # selector unchanged


def test_save_peak_series_writes_json_and_clears_unsaved(
    qapplication: QApplication,
    tmp_path: Path,
) -> None:
    """_write_peak_series_to_path writes canonical JSON and marks the series as saved."""
    from heatmap_peak_distance_resource import PeakSeriesResource
    from sparse_iq_peak_distance_core import (
        FramePeakMeasurement, PeakDistanceMetadata, STATUS_DETECTED,
        PEAK_EXTRACTION_METHOD_SUM_VELOCITY, PEAK_DISTANCE_FORMAT,
    )
    import json as _json

    metadata = PeakDistanceMetadata(
        source_path="x.h5", source_name="x.h5",
        session_index=0, group_index=0, entry_index=0,
        sensor_id=1, subsweep_index=0,
        source_frame_count=1, source_duration_s=0.1,
        ticks_per_second=1000, threshold=650.0,
        peak_extraction_method=PEAK_EXTRACTION_METHOD_SUM_VELOCITY,
        zero_velocity_bin_index=3, zero_velocity_m_s=0.0,
    )
    measurements = (FramePeakMeasurement(0, 10, 0.0, None, STATUS_DETECTED, 1.2, 1.2, 700.0),)
    series = PeakSeriesResource(
        series_id="wid", display_name="test", provenance="generated",
        measurements=measurements, color="#3b82f6", metadata=metadata, unsaved=True,
    )
    window = HeatmapAlignmentWindow()
    window._peak_series_list = [series]

    output_path = tmp_path / "out.json"
    window._write_peak_series_to_path(series, output_path)

    assert output_path.exists()
    doc = _json.loads(output_path.read_text(encoding="utf-8"))
    assert doc["format"] == PEAK_DISTANCE_FORMAT
    assert series.unsaved is False
    assert series.json_path == output_path


def test_any_peaks_unsaved_reflects_per_series_state(qapplication: QApplication) -> None:
    """_any_peaks_unsaved returns True only when at least one series is unsaved."""
    from heatmap_peak_distance_resource import PeakSeriesResource

    window = HeatmapAlignmentWindow()
    assert not window._any_peaks_unsaved()

    saved = PeakSeriesResource(series_id="s1", display_name="a", provenance="imported", measurements=(), color="#3b82f6", unsaved=False)
    window._peak_series_list = [saved]
    assert not window._any_peaks_unsaved()

    unsaved = PeakSeriesResource(series_id="s2", display_name="b", provenance="generated", measurements=(), color="#f59e0b", unsaved=True)
    window._peak_series_list = [saved, unsaved]
    assert window._any_peaks_unsaved()


def test_peak_series_preserve_after_h5_replacement(
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 3.7: replacing H5 with a different file preserves peak series."""
    from heatmap_alignment_resource_jobs import LoadedH5ResourcePayload
    from heatmap_peak_distance_resource import PeakSeriesResource

    window = HeatmapAlignmentWindow()
    series = PeakSeriesResource(
        series_id="k1", display_name="my peaks", provenance="imported",
        measurements=(), color="#3b82f6", json_path=Path("/tmp/peaks.json"),
    )
    window._peak_series_list = [series]

    class _FakeHeatmapSource:
        def close(self) -> None: return None

    class _FakeRecord:
        session_idx = 0; group_idx = 0; entry_idx = 0
        duration_s = 1.0; fps = 1.0; results: list = []
        def close(self) -> None: return None

    window._h5_replacement_backup = _H5ResourceBackup(
        heatmap_source=_FakeHeatmapSource(),
        heatmap_track=HeatmapTrack(path="/tmp/old.h5"),
        viewport_output_width=10, viewport_output_height=10,
    )
    monkeypatch.setattr(window, "_rebuild_overlay_plot_renderer", lambda: None)
    monkeypatch.setattr(window, "_reload_peak_distance_datasource_from_session", lambda: None)
    monkeypatch.setattr(window, "_update_heatmap_extent_labels", lambda: None)
    monkeypatch.setattr("heatmap_alignment_gui.build_h5_truth_source_from_payload", lambda _: _FakeHeatmapSource())

    payload = LoadedH5ResourcePayload(
        path=Path("/tmp/new.h5"), record=_FakeRecord(), subsweep_idx=0,
        metadata=HeatmapTrack(path="/tmp/new.h5"),
        first_frame_shape=(10, 10), resolved_fixed_color_level=100.0,
    )
    window._apply_h5_job_result(payload)

    assert len(window._peak_series_list) == 1
    assert window._peak_series_list[0].series_id == "k1"


def test_signal_playhead_scrubbed_handler_updates_session_and_calls_scrub_previews(
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = HeatmapAlignmentWindow()

    reanchored: list[None] = []
    synced_hints: list[str] = []
    dirty_calls: list[None] = []

    monkeypatch.setattr(window, "_reanchor_playback_clock", lambda: reanchored.append(None))
    monkeypatch.setattr(
        window,
        "_sync_previews",
        lambda *, camera_access_hint="auto", **_kw: synced_hints.append(camera_access_hint),
    )
    monkeypatch.setattr(window, "_mark_session_dirty", lambda: dirty_calls.append(None))

    window._signal_playhead_scrubbed(3.75)

    assert window.session.timeline.current_time_s == pytest.approx(3.75)
    assert reanchored == [None]
    assert synced_hints == ["scrub"]
    assert dirty_calls == []


# ---------------------------------------------------------------------------
# Requirements 1-8: must-fix behavior tests
# ---------------------------------------------------------------------------


def test_generate_appends_without_replacing_existing_series(
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Req 1: a second Generate appends a new series, existing series unchanged."""
    from heatmap_peak_distance_resource import PeakSeriesResource
    from sparse_iq_peak_distance_core import (
        FramePeakMeasurement, STATUS_DETECTED, PEAK_EXTRACTION_METHOD_SUM_VELOCITY,
        PeakDistanceExportResult, PeakDistanceMetadata,
    )

    window = HeatmapAlignmentWindow()
    existing = PeakSeriesResource(
        series_id="existing", display_name="first", provenance="generated",
        measurements=(), color="#3b82f6", unsaved=False,
    )
    window._peak_series_list = [existing]

    class _FakeDialog:
        def exec(self):
            return 1
        algorithm_id = PEAK_EXTRACTION_METHOD_SUM_VELOCITY
        threshold = 650.0
        display_name = "second"

    class _FakeH5Source:
        class record:
            results = [object()]
            session_idx = 0; group_idx = 0; entry_idx = 0
        path = Path("/tmp/x.h5")
        subsweep_idx = 0

    window.heatmap_source = _FakeH5Source()

    fake_meta = PeakDistanceMetadata(
        source_path="/tmp/x.h5", source_name="x.h5",
        session_index=0, group_index=0, entry_index=0, sensor_id=1,
        subsweep_index=0, source_frame_count=1, source_duration_s=0.1,
        ticks_per_second=1000, threshold=650.0,
        peak_extraction_method=PEAK_EXTRACTION_METHOD_SUM_VELOCITY,
        zero_velocity_bin_index=3, zero_velocity_m_s=0.0,
    )
    fake_meas = (FramePeakMeasurement(0, 0, 0.0, None, STATUS_DETECTED, 1.2, 1.2, 700.0),)
    fake_result = PeakDistanceExportResult(metadata=fake_meta, measurements=fake_meas)

    monkeypatch.setattr("heatmap_alignment_gui.GeneratePeakSeriesDialog", lambda p: _FakeDialog())
    monkeypatch.setattr("heatmap_alignment_gui.generate_peak_distances_from_heatmap_record", lambda *a, **kw: fake_result)
    monkeypatch.setattr(window, "_refresh_signal_plot", lambda: None)
    monkeypatch.setattr(window, "_update_heatmap_peak_selector", lambda: None)
    monkeypatch.setattr(window, "_refresh_resources_ui", lambda: None)

    window._generate_peak_series()

    assert len(window._peak_series_list) == 2, "Generate must append, not replace"
    assert window._peak_series_list[0].series_id == "existing"
    assert window._peak_series_list[1].display_name == "second"
    assert window._peak_series_list[1].unsaved is True


def test_resource_summaries_emits_one_row_per_peak_series(qapplication: QApplication) -> None:
    """Req 2: resource_summaries returns one ResourceSummary per PeakSeriesResource."""
    from heatmap_peak_distance_resource import PeakSeriesResource
    window = HeatmapAlignmentWindow()
    s1 = PeakSeriesResource(series_id="id1", display_name="Alpha", provenance="generated",
                            measurements=(), color="#3b82f6", unsaved=True)
    s2 = PeakSeriesResource(series_id="id2", display_name="Beta", provenance="imported",
                            measurements=(), color="#f59e0b", json_path=Path("/tmp/b.json"), unsaved=False)
    window._peak_series_list = [s1, s2]
    summaries = window.resource_summaries()
    peak_rows = [s for s in summaries if s.kind == "radar_peak"]
    assert len(peak_rows) == 2
    assert peak_rows[0].series_id == "id1"
    assert peak_rows[0].status_label == "Generated (unsaved)"
    assert peak_rows[1].series_id == "id2"
    assert peak_rows[1].status_label == ""


def test_invoke_resource_action_save_targets_series_id(qapplication: QApplication) -> None:
    """Req 2: save must use series_id not a global fallback."""
    from heatmap_peak_distance_resource import PeakSeriesResource
    window = HeatmapAlignmentWindow()
    s1 = PeakSeriesResource(series_id="s1", display_name="A", provenance="generated",
                            measurements=(), color="#3b82f6", unsaved=True)
    s2 = PeakSeriesResource(series_id="s2", display_name="B", provenance="generated",
                            measurements=(), color="#f59e0b", unsaved=True)
    window._peak_series_list = [s1, s2]
    saved: list[str] = []
    window._save_peak_series = lambda sid: saved.append(sid)  # type: ignore
    window.invoke_resource_action("radar_peak", "save", series_id="s2")
    assert saved == ["s2"]


def test_invoke_resource_action_unload_targets_series_id(qapplication: QApplication) -> None:
    """Req 2: unload with series_id removes only the target."""
    from heatmap_peak_distance_resource import PeakSeriesResource
    window = HeatmapAlignmentWindow()
    s1 = PeakSeriesResource(series_id="keep", display_name="keep", provenance="imported",
                            measurements=(), color="#3b82f6")
    s2 = PeakSeriesResource(series_id="remove", display_name="remove", provenance="imported",
                            measurements=(), color="#f59e0b")
    window._peak_series_list = [s1, s2]
    window.invoke_resource_action("radar_peak", "unload", series_id="remove")
    assert len(window._peak_series_list) == 1
    assert window._peak_series_list[0].series_id == "keep"


def test_refresh_signal_plot_passes_all_visible_series(qapplication: QApplication) -> None:
    """Req 3: visible peak series all go to set_plotted_signals; invisible are excluded."""
    from heatmap_peak_distance_resource import PeakSeriesResource
    from sparse_iq_peak_distance_core import FramePeakMeasurement, STATUS_DETECTED
    meas = (FramePeakMeasurement(0, 0, 0.0, None, STATUS_DETECTED, 1.2, 1.2, 700.0),)
    window = HeatmapAlignmentWindow()
    s_vis1 = PeakSeriesResource(series_id="v1", display_name="v0 slice", provenance="generated",
                                measurements=meas, color="#3b82f6", visible=True)
    s_vis2 = PeakSeriesResource(series_id="v2", display_name="sum v", provenance="generated",
                                measurements=meas, color="#f59e0b", visible=True)
    s_hidden = PeakSeriesResource(series_id="h1", display_name="hidden", provenance="generated",
                                  measurements=meas, color="#ec4899", visible=False)
    window._peak_series_list = [s_vis1, s_vis2, s_hidden]
    captured: list = []
    orig = window.signal_plot.set_plotted_signals
    def _cap(**kw):
        captured.append(kw)
        orig(**kw)
    window.signal_plot.set_plotted_signals = _cap  # type: ignore
    window._refresh_signal_plot()
    assert captured
    psl = captured[0].get("peak_series_list", [])
    assert len(psl) == 2
    names = [n for n, _c, _s in psl]
    assert "v0 slice" in names and "sum v" in names and "hidden" not in names


def test_heatmap_peak_combo_exists(qapplication: QApplication) -> None:
    """Req 4: _heatmap_peak_combo must exist in the main window layout."""
    window = HeatmapAlignmentWindow()
    assert hasattr(window, "_heatmap_peak_combo")
    assert window._heatmap_peak_combo.count() >= 1
    assert window._heatmap_peak_combo.itemData(0) is None


def test_heatmap_peak_combo_lists_all_series(qapplication: QApplication) -> None:
    """Req 4: selector shows None + one item per series."""
    from heatmap_peak_distance_resource import PeakSeriesResource
    window = HeatmapAlignmentWindow()
    window._peak_series_list = [
        PeakSeriesResource(series_id="a", display_name="A", provenance="generated", measurements=(), color="#3b82f6"),
        PeakSeriesResource(series_id="b", display_name="B", provenance="imported", measurements=(), color="#f59e0b"),
    ]
    window._update_heatmap_peak_selector()
    assert window._heatmap_peak_combo.count() == 3
    assert window._heatmap_peak_combo.itemData(1) == "a"
    assert window._heatmap_peak_combo.itemData(2) == "b"


def test_heatmap_peak_combo_resets_to_none_when_selected_series_unloaded(qapplication: QApplication) -> None:
    """Req 4: selector resets to None after the selected series is unloaded."""
    from heatmap_peak_distance_resource import PeakSeriesResource
    window = HeatmapAlignmentWindow()
    s = PeakSeriesResource(series_id="s", display_name="s", provenance="generated", measurements=(), color="#3b82f6")
    window._peak_series_list = [s]
    window._heatmap_peak_selector_id = "s"
    window._update_heatmap_peak_selector()
    window._unload_peak_series("s", confirm=False)
    assert window._heatmap_peak_selector_id is None
    assert window._heatmap_peak_combo.currentData() is None


def test_resources_window_has_generate_and_import_buttons(qapplication: QApplication) -> None:
    """Req 2/8: Resources window must expose Generate Peak Series and Import Peak Series buttons."""
    window = HeatmapAlignmentWindow()
    window._show_resources_window()
    rw = window._resources_window
    assert hasattr(rw, "generate_peak_series_button")
    assert hasattr(rw, "import_peak_series_button")


def test_import_peak_series_from_path_appends(
    qapplication: QApplication,
    tmp_path: Path,
) -> None:
    """Req 5/6: _import_peak_series_from_path appends without replacing existing series."""
    from heatmap_peak_distance_resource import PeakSeriesResource
    from sparse_iq_peak_distance_core import (
        PeakDistanceExportResult, PeakDistanceMetadata,
        FramePeakMeasurement, STATUS_DETECTED, PEAK_EXTRACTION_METHOD_SUM_VELOCITY,
        write_peak_distance_json,
    )

    meta = PeakDistanceMetadata(
        source_path="/tmp/t.h5", source_name="t.h5",
        session_index=0, group_index=0, entry_index=0, sensor_id=1,
        subsweep_index=0, source_frame_count=1, source_duration_s=0.1,
        ticks_per_second=1000, threshold=650.0,
        peak_extraction_method=PEAK_EXTRACTION_METHOD_SUM_VELOCITY,
        zero_velocity_bin_index=3, zero_velocity_m_s=0.0,
    )
    meas = (FramePeakMeasurement(0, 0, 0.0, None, STATUS_DETECTED, 1.2, 1.2, 700.0),)
    result = PeakDistanceExportResult(metadata=meta, measurements=meas)
    json_path = tmp_path / "peaks.json"
    write_peak_distance_json(result, json_path)

    window = HeatmapAlignmentWindow()
    pre = PeakSeriesResource(series_id="pre", display_name="pre", provenance="imported",
                             measurements=(), color="#3b82f6")
    window._peak_series_list = [pre]

    ok = window._import_peak_series_from_path(json_path, mark_dirty=False)

    assert ok is True
    assert len(window._peak_series_list) == 2, "Must append, not replace"
    assert window._peak_series_list[0].series_id == "pre"
    assert window._peak_series_list[1].json_path == json_path


# ---------------------------------------------------------------------------
# UI polish: Resources window refresh after peak series unload
# ---------------------------------------------------------------------------


def test_resources_window_row_removed_immediately_after_unload(
    qapplication: QApplication,
) -> None:
    """Resources window table must lose the row immediately after _unload_peak_series.

    This tests the fix for the stale-table bug: unload calls _refresh_resources_ui so
    the row disappears without requiring close/reopen of the Resources window.
    """
    from heatmap_peak_distance_resource import PeakSeriesResource

    window = HeatmapAlignmentWindow()
    s1 = PeakSeriesResource(
        series_id="row1", display_name="First", provenance="imported",
        measurements=(), color="#3b82f6",
    )
    s2 = PeakSeriesResource(
        series_id="row2", display_name="Second", provenance="imported",
        measurements=(), color="#f59e0b",
    )
    window._peak_series_list = [s1, s2]

    # Open the Resources window so it will receive refreshes.
    window._show_resources_window()
    rw = window._resources_window
    assert rw is not None
    # Sync the initial state into the table.
    window._refresh_resources_ui()
    peak_rows_before = [
        rw.table.item(r, 1).text()
        for r in range(rw.table.rowCount())
        if rw._summaries[r].kind == "radar_peak" and rw._summaries[r].series_id
    ]
    assert "First" in peak_rows_before
    assert "Second" in peak_rows_before

    # Unload one series — _unload_peak_series must call _refresh_resources_ui().
    window._unload_peak_series("row1", confirm=False)

    peak_rows_after = [
        rw.table.item(r, 1).text()
        for r in range(rw.table.rowCount())
        if rw._summaries[r].kind == "radar_peak" and rw._summaries[r].series_id
    ]
    assert "First" not in peak_rows_after, "Unloaded row must vanish from the table immediately"
    assert "Second" in peak_rows_after, "Remaining row must still be present"


def test_generate_button_disabled_on_peak_series_row(qapplication: QApplication) -> None:
    """Generate button must be disabled when a peak series row is selected.

    The footer already has a dedicated Generate Peak Series button; the per-row
    Generate button would imply generation replaces the selected row, which is wrong.
    """
    from heatmap_peak_distance_resource import PeakSeriesResource

    window = HeatmapAlignmentWindow()
    s = PeakSeriesResource(
        series_id="s1", display_name="A peaks", provenance="generated",
        measurements=(), color="#3b82f6",
    )
    window._peak_series_list = [s]
    window._show_resources_window()
    rw = window._resources_window
    assert rw is not None
    window._refresh_resources_ui()

    # Select the peak series row.
    peak_row = next(
        (r for r in range(rw.table.rowCount()) if rw._summaries[r].series_id == "s1"),
        None,
    )
    assert peak_row is not None
    rw._select_table_row(peak_row)
    rw._update_details_for_selection()

    assert not rw.generate_button.isEnabled(), (
        "Generate button must be disabled for individual peak series rows"
    )
    assert not rw.replace_button.isEnabled(), (
        "Replace button must be disabled for individual peak series rows"
    )


# ---------------------------------------------------------------------------
# Coordinate context tests (add-rendered-heatmap-coordinate-context)
# ---------------------------------------------------------------------------


def test_image_preview_rendered_image_rect_returns_contents_rect(
    qapplication: QApplication,
) -> None:
    """rendered_image_rect() must equal contentsRect() on a sized widget."""
    widget = ImagePreview("Test")
    widget.resize(400, 300)
    assert widget.rendered_image_rect() == widget.contentsRect()


def test_heatmap_distance_header_initial_no_crash(
    qapplication: QApplication,
) -> None:
    """set_extent(None, None) and set_peak_distance(None) must not raise."""
    header = HeatmapDistanceHeader()
    header.set_extent(None, None)
    header.set_peak_distance(None)


def test_heatmap_distance_header_stores_extent(
    qapplication: QApplication,
) -> None:
    """set_extent must store _dist_min and _dist_max."""
    header = HeatmapDistanceHeader()
    header.set_extent(0.2, 2.5)
    assert header._dist_min == 0.2
    assert header._dist_max == 2.5


def test_heatmap_distance_header_stores_peak_distance(
    qapplication: QApplication,
) -> None:
    """set_peak_distance must store _peak_dist_m."""
    header = HeatmapDistanceHeader()
    header.set_extent(0.2, 2.5)
    header.set_peak_distance(1.0)
    assert header._peak_dist_m == 1.0


def test_heatmap_distance_header_peak_none_when_cleared(
    qapplication: QApplication,
) -> None:
    """set_peak_distance(None) after a value must set _peak_dist_m to None."""
    header = HeatmapDistanceHeader()
    header.set_peak_distance(1.0)
    header.set_peak_distance(None)
    assert header._peak_dist_m is None


def test_heatmap_alignment_window_has_distance_header(
    qapplication: QApplication,
) -> None:
    """HeatmapAlignmentWindow must expose _heatmap_distance_header."""
    window = HeatmapAlignmentWindow()
    assert hasattr(window, "_heatmap_distance_header")


def test_heatmap_alignment_window_has_vel_extent_label(
    qapplication: QApplication,
) -> None:
    """HeatmapAlignmentWindow must expose _heatmap_vel_extent_label."""
    window = HeatmapAlignmentWindow()
    assert hasattr(window, "_heatmap_vel_extent_label")


def test_heatmap_alignment_window_has_heatmap_axes_attribute(
    qapplication: QApplication,
) -> None:
    """_heatmap_axes must exist and be None before any H5 is loaded."""
    window = HeatmapAlignmentWindow()
    assert hasattr(window, "_heatmap_axes")
    assert window._heatmap_axes is None


def test_annotate_truth_frame_returns_frame_unchanged(
    qapplication: QApplication,
) -> None:
    """_annotate_truth_frame_with_peak must return the frame identity (no H5 loaded)."""
    window = HeatmapAlignmentWindow()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    result = window._annotate_truth_frame_with_peak(frame, 0)
    assert result is frame or np.array_equal(result, frame)


def test_hover_dvm_cache_initialized_none(
    qapplication: QApplication,
) -> None:
    """_hover_dvm_cache must be None on construction."""
    window = HeatmapAlignmentWindow()
    assert window._hover_dvm_cache is None


def test_hover_last_pos_initialized_none(
    qapplication: QApplication,
) -> None:
    """_hover_last_pos must be None on construction."""
    window = HeatmapAlignmentWindow()
    assert window._hover_last_pos is None


def test_refresh_hover_tooltip_no_crash_without_state(
    qapplication: QApplication,
) -> None:
    """_refresh_hover_tooltip must not raise when no H5 is loaded."""
    window = HeatmapAlignmentWindow()
    window._refresh_hover_tooltip()


def test_truth_view_has_mouse_tracking(
    qapplication: QApplication,
) -> None:
    """truth_view must have mouse tracking enabled."""
    window = HeatmapAlignmentWindow()
    assert window.truth_view.hasMouseTracking() is True


# ---------------------------------------------------------------------------
# Task 4.2 — Hover coordinate mapping, formatting, hide-on-leave, magnitude
# ---------------------------------------------------------------------------


def _make_hover_axes() -> HeatmapAxes:
    """Return a small synthetic HeatmapAxes for hover mapping tests."""
    distances_m = np.linspace(0.5, 1.5, 5)  # 5 distance bins
    velocities_m_s = np.linspace(-1.0, 1.0, 4)  # 4 velocity bins (vel_min=-1.0, vel_max=1.0)
    return HeatmapAxes(
        distances_m=distances_m,
        velocities_m_s=velocities_m_s,
        velocity_resolution=0.5,
    )


def _inject_hover_state(
    window: HeatmapAlignmentWindow,
    axes: HeatmapAxes,
    dvm: np.ndarray,
) -> None:
    """Inject axes and DVM cache directly into window hover state."""
    window._heatmap_axes = axes
    window._hover_dvm_cache = (0, dvm)


def test_hover_tooltip_top_left_maps_to_dist_min_and_vel_min(
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hovering the top-left corner must report dist_min and vel_min.

    truth_view renders DVM row 0 at the top of the image (no vertical flip).
    After fftshift, row 0 corresponds to vel_min, so screen-top == vel_min.
    """
    window = HeatmapAlignmentWindow()
    axes = _make_hover_axes()
    n_vel, n_dist = len(axes.velocities_m_s), len(axes.distances_m)
    dvm = np.arange(n_vel * n_dist, dtype=np.float32).reshape(n_vel, n_dist)
    _inject_hover_state(window, axes, dvm)

    window.truth_view.resize(200, 100)
    rect = window.truth_view.rendered_image_rect()

    # Position at the exact top-left corner of the rendered rect
    pos = QtCore.QPoint(rect.left(), rect.top())
    window._hover_last_pos = pos

    captured: list[str] = []

    def fake_show_text(global_pos: QtCore.QPoint, text: str, widget: QtWidgets.QWidget) -> None:
        captured.append(text)

    monkeypatch.setattr(QtWidgets.QToolTip, "showText", fake_show_text)

    window._refresh_hover_tooltip()

    assert len(captured) == 1
    text = captured[0]
    dist_min = float(axes.distances_m[0])
    vel_min = float(axes.velocities_m_s[0])
    assert "Distance: {:.3f} m".format(dist_min) in text
    assert "Velocity: {:.3f} m/s".format(vel_min) in text
    assert "Magnitude:" in text


def test_hover_tooltip_bottom_right_maps_to_near_dist_max_and_vel_max(
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hovering near the bottom-right must report distance and velocity near their maxima.

    Qt's rect.right() == rect.left() + rect.width() - 1 (last included pixel),
    so x_frac and y_frac are slightly below 1.0; reported values are close to
    dist_max and vel_max but not exactly equal.  The test verifies the formula
    direction: bottom → high velocity (positive), right → high distance.
    """
    window = HeatmapAlignmentWindow()
    axes = _make_hover_axes()
    n_vel, n_dist = len(axes.velocities_m_s), len(axes.distances_m)
    dvm = np.zeros((n_vel, n_dist), dtype=np.float32)
    _inject_hover_state(window, axes, dvm)

    window.truth_view.resize(200, 100)
    rect = window.truth_view.rendered_image_rect()

    # Position at the last included pixel inside the bottom-right corner
    pos = QtCore.QPoint(rect.right(), rect.bottom())
    window._hover_last_pos = pos

    captured: list[str] = []

    def fake_show_text(global_pos: QtCore.QPoint, text: str, widget: QtWidgets.QWidget) -> None:
        captured.append(text)

    monkeypatch.setattr(QtWidgets.QToolTip, "showText", fake_show_text)

    window._refresh_hover_tooltip()

    assert len(captured) == 1
    text = captured[0]

    # Parse reported values and verify they are in the upper half of each axis range
    dist_mid = (float(axes.distances_m[0]) + float(axes.distances_m[-1])) / 2.0
    vel_mid = (float(axes.velocities_m_s[0]) + float(axes.velocities_m_s[-1])) / 2.0
    import re
    dist_match = re.search(r"Distance: ([\d.]+) m", text)
    vel_match = re.search(r"Velocity: (-?[\d.]+) m/s", text)
    assert dist_match is not None
    assert vel_match is not None
    reported_dist = float(dist_match.group(1))
    reported_vel = float(vel_match.group(1))
    assert reported_dist > dist_mid, f"Expected dist > {dist_mid:.3f}, got {reported_dist:.3f}"
    assert reported_vel > vel_mid, f"Expected vel > {vel_mid:.3f}, got {reported_vel:.3f}"


def test_hover_tooltip_magnitude_matches_dvm_lookup(
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reported magnitude must equal dvm[vel_idx, dist_idx] for the hovered cell."""
    window = HeatmapAlignmentWindow()
    axes = _make_hover_axes()
    n_vel, n_dist = len(axes.velocities_m_s), len(axes.distances_m)
    # Fill DVM with unique values so we can identify which cell was looked up
    dvm = np.arange(n_vel * n_dist, dtype=np.float32).reshape(n_vel, n_dist) * 100.0
    _inject_hover_state(window, axes, dvm)

    window.truth_view.resize(200, 100)
    rect = window.truth_view.rendered_image_rect()

    # Hover at the top-left (vel_min = row 0, dist_min = col 0)
    pos = QtCore.QPoint(rect.left(), rect.top())
    window._hover_last_pos = pos

    captured: list[str] = []

    def fake_show_text(global_pos: QtCore.QPoint, text: str, widget: QtWidgets.QWidget) -> None:
        captured.append(text)

    monkeypatch.setattr(QtWidgets.QToolTip, "showText", fake_show_text)

    window._refresh_hover_tooltip()

    assert len(captured) == 1
    # dvm[0, 0] == 0 * 100 == 0; magnitude line should say "Magnitude: 0"
    assert "Magnitude: 0" in captured[0]


def test_hover_tooltip_hides_on_leave_event(
    qapplication: QApplication,
) -> None:
    """A Leave event from truth_view must clear _hover_last_pos."""
    window = HeatmapAlignmentWindow()
    axes = _make_hover_axes()
    n_vel, n_dist = len(axes.velocities_m_s), len(axes.distances_m)
    dvm = np.zeros((n_vel, n_dist), dtype=np.float32)
    _inject_hover_state(window, axes, dvm)

    window.truth_view.resize(200, 100)
    rect = window.truth_view.rendered_image_rect()
    window._hover_last_pos = QtCore.QPoint(rect.center())

    leave_event = QtCore.QEvent(QtCore.QEvent.Type.Leave)
    window.eventFilter(window.truth_view, leave_event)

    assert window._hover_last_pos is None


def test_hover_tooltip_magnitude_updates_on_dvm_cache_change(
    qapplication: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Updating _hover_dvm_cache and calling _refresh_hover_tooltip must report new magnitude."""
    window = HeatmapAlignmentWindow()
    axes = _make_hover_axes()
    n_vel, n_dist = len(axes.velocities_m_s), len(axes.distances_m)

    dvm_frame0 = np.zeros((n_vel, n_dist), dtype=np.float32)
    dvm_frame1 = np.full((n_vel, n_dist), 999.0, dtype=np.float32)

    window._heatmap_axes = axes
    window._hover_dvm_cache = (0, dvm_frame0)

    window.truth_view.resize(200, 100)
    rect = window.truth_view.rendered_image_rect()
    window._hover_last_pos = QtCore.QPoint(rect.left(), rect.top())

    captured: list[str] = []

    def fake_show_text(global_pos: QtCore.QPoint, text: str, widget: QtWidgets.QWidget) -> None:
        captured.append(text)

    monkeypatch.setattr(QtWidgets.QToolTip, "showText", fake_show_text)

    # First readout: magnitude 0
    window._refresh_hover_tooltip()
    assert "Magnitude: 0" in captured[-1]

    # Simulate frame change: update DVM cache to frame 1
    window._hover_dvm_cache = (1, dvm_frame1)
    window._refresh_hover_tooltip()
    assert "Magnitude: 999" in captured[-1]


# ---------------------------------------------------------------------------
# Task 4.3 — rendered_image_rect dimensions vs. viewport_view after header
# ---------------------------------------------------------------------------


def test_truth_view_rendered_image_rect_equals_contents_rect_after_resize(
    qapplication: QApplication,
) -> None:
    """truth_view.rendered_image_rect() must equal contentsRect() at any size."""
    window = HeatmapAlignmentWindow()
    window.truth_view.resize(320, 240)
    assert window.truth_view.rendered_image_rect() == window.truth_view.contentsRect()


def test_viewport_view_rendered_image_rect_equals_contents_rect_after_resize(
    qapplication: QApplication,
) -> None:
    """viewport_view.rendered_image_rect() must equal contentsRect() at any size."""
    window = HeatmapAlignmentWindow()
    window.viewport_view.resize(320, 240)
    assert window.viewport_view.rendered_image_rect() == window.viewport_view.contentsRect()


def test_truth_view_and_viewport_view_rendered_image_rect_same_when_same_size(
    qapplication: QApplication,
) -> None:
    """Both preview panes must report the same rendered_image_rect dimensions when sized equally.

    The HeatmapDistanceHeader sits outside truth_view, so truth_view.contentsRect()
    must not shrink relative to viewport_view when both are set to the same pixel size.
    """
    window = HeatmapAlignmentWindow()
    target_size = QtCore.QSize(320, 240)
    window.truth_view.resize(target_size)
    window.viewport_view.resize(target_size)
    truth_rect = window.truth_view.rendered_image_rect()
    viewport_rect = window.viewport_view.rendered_image_rect()
    assert truth_rect.size() == viewport_rect.size()


def test_truth_view_rendered_image_rect_narrow_width(
    qapplication: QApplication,
) -> None:
    """At narrow width (<120 px) truth_view.rendered_image_rect() still equals contentsRect().

    This is the case where HeatmapDistanceHeader hides its extent labels; the
    truth_view geometry must remain unaffected (no overlap from labels).
    """
    window = HeatmapAlignmentWindow()
    window.truth_view.resize(80, 100)
    assert window.truth_view.rendered_image_rect() == window.truth_view.contentsRect()


# ---------------------------------------------------------------------------
# Task 4.5 — Export smoke check: compact peak marker vs. legacy annotation
# ---------------------------------------------------------------------------


def _make_minimal_plot_renderer() -> HeatmapPlotRenderer:
    """Return a HeatmapPlotRenderer with a live matplotlib axes, bypassing H5 loading."""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    renderer = object.__new__(HeatmapPlotRenderer)
    # Minimal attributes expected by _rebuild_canvas / _draw_peak_marker
    renderer.extent = (0.5, 1.5, -1.0, 1.0)  # (dist_min, dist_max, vel_min, vel_max)
    mock_source = unittest.mock.MagicMock()
    mock_source.color_min = 0.0
    mock_source.color_max = 3000.0
    renderer.heatmap_source = mock_source
    renderer._peak_artists = []
    renderer._output_size = (0, 0)
    renderer._presentation = None
    renderer._figure = None
    renderer._canvas = None
    renderer._ax = None
    renderer._image = None

    # Build a minimal canvas so _ax is populated
    width, height = 120, 90
    dpi = 100.0
    figure = Figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    FigureCanvasAgg(figure)
    ax = figure.add_subplot(111)
    renderer._ax = ax
    renderer._figure = figure

    return renderer


def test_draw_peak_marker_creates_two_artists_for_valid_peak() -> None:
    """_draw_peak_marker with a valid peak_distance_m must add exactly 2 artists (marker + label)."""
    renderer = _make_minimal_plot_renderer()
    renderer._draw_peak_marker(1.0, None)
    assert len(renderer._peak_artists) == 2


def test_draw_peak_marker_creates_no_artists_when_peak_is_none() -> None:
    """_draw_peak_marker(None, ...) must leave _peak_artists empty."""
    renderer = _make_minimal_plot_renderer()
    renderer._draw_peak_marker(None, None)
    assert len(renderer._peak_artists) == 0


def test_draw_peak_marker_clears_previous_artists_on_new_call() -> None:
    """Calling _draw_peak_marker twice must not accumulate stale artists."""
    renderer = _make_minimal_plot_renderer()
    renderer._draw_peak_marker(1.0, None)
    first_artists = list(renderer._peak_artists)
    renderer._draw_peak_marker(1.2, None)
    assert len(renderer._peak_artists) == 2
    # Artists from the second call must differ from the first call
    assert renderer._peak_artists != first_artists


def test_annotate_truth_frame_returns_frame_unchanged_with_nonzero_frame_idx(
    qapplication: QApplication,
) -> None:
    """_annotate_truth_frame_with_peak must return frame unchanged for any frame_idx (no H5)."""
    window = HeatmapAlignmentWindow()
    frame = np.ones((50, 80, 3), dtype=np.uint8) * 128
    for idx in (0, 1, 5, 99):
        result = window._annotate_truth_frame_with_peak(frame, idx)
        assert np.array_equal(result, frame), f"Frame was modified for frame_idx={idx}"


# ---------------------------------------------------------------------------
# Task 4.4: Minimum-height / splitter overlap prevention
# ---------------------------------------------------------------------------


def test_rendered_heatmap_group_minimum_height_includes_distance_header(
    qapplication: QApplication,
) -> None:
    """Task 4.4: rendered_heatmap_group minimum height must account for the HeatmapDistanceHeader.

    _stacked_layout_minimum_height is called with rendered_heatmap_layout to set the group's
    minimumHeight.  HeatmapDistanceHeader has setFixedHeight(20), so the group minimum must be
    at least truth_view.minimumHeight() + header.minimumHeight() (plus layout spacing/margins).
    This confirms the splitter overlap-prevention logic still accounts for the new header row.
    """
    window = HeatmapAlignmentWindow()

    header = window._heatmap_distance_header
    truth_view = window.truth_view

    # Both components must contribute a positive minimum height.
    assert header.minimumHeight() > 0, "HeatmapDistanceHeader must have positive minimumHeight"
    assert truth_view.minimumHeight() > 0, "truth_view must have positive minimumHeight"

    # The rendered heatmap group minimum height must be at least the sum of the two main
    # content widgets' minimum heights (header + preview image).
    # This is the structural guarantee that adding the header cannot shrink the group
    # below the point where controls would overlap preview content.
    from PySide6 import QtWidgets

    # Find the rendered heatmap group box (parent of truth_view is the group).
    rendered_heatmap_group = None
    parent = truth_view.parent()
    while parent is not None:
        if isinstance(parent, QtWidgets.QGroupBox) and parent.title() == "Rendered Heatmap":
            rendered_heatmap_group = parent
            break
        parent = parent.parent()

    assert rendered_heatmap_group is not None, "Could not find 'Rendered Heatmap' QGroupBox"

    group_min_h = rendered_heatmap_group.minimumHeight()
    assert group_min_h >= header.minimumHeight() + truth_view.minimumHeight(), (
        f"rendered_heatmap_group minimumHeight ({group_min_h}) must be >= "
        f"header ({header.minimumHeight()}) + truth_view ({truth_view.minimumHeight()})"
    )


def test_rendered_heatmap_group_minimum_height_exceeds_no_header_baseline(
    qapplication: QApplication,
) -> None:
    """Task 4.4: the group minimum height must exceed truth_view alone by at least the header height.

    Before this change truth_view (200px) was the dominant content widget.  Adding the 20px
    HeatmapDistanceHeader above it must increase the computed minimum height so the splitter
    guard prevents the header from overlapping the preview area.
    """
    window = HeatmapAlignmentWindow()

    header = window._heatmap_distance_header
    truth_view = window.truth_view

    from PySide6 import QtWidgets

    rendered_heatmap_group = None
    parent = truth_view.parent()
    while parent is not None:
        if isinstance(parent, QtWidgets.QGroupBox) and parent.title() == "Rendered Heatmap":
            rendered_heatmap_group = parent
            break
        parent = parent.parent()

    assert rendered_heatmap_group is not None

    group_min_h = rendered_heatmap_group.minimumHeight()
    # The group minimum must exceed truth_view alone (pre-change baseline), confirming
    # that the header's fixed height was included in the minimum-height calculation.
    assert group_min_h > truth_view.minimumHeight(), (
        f"rendered_heatmap_group minimumHeight ({group_min_h}) must exceed "
        f"truth_view alone ({truth_view.minimumHeight()}); "
        f"header height {header.minimumHeight()} must be counted"
    )
