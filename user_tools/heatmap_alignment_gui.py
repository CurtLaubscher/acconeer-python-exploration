from __future__ import annotations


"""PySide6 workbench for manual camera-to-heatmap alignment.

Launch this tool through Hatch so it uses the repo-managed GUI/runtime
dependencies:

    hatch run app:heatmap-align

or:

    hatch run app:python user_tools/heatmap_alignment_gui.py

The GUI keeps lightweight local settings for the last-used file dialog
locations.

Startup file arguments are supported, for example:

    hatch run app:heatmap-align -- --camera path\\to\\video.mp4 --h5 path\\to\\record.h5
    hatch run app:heatmap-align -- --h5 path\\to\\record.h5 --peaks path\\to\\peaks.json
    hatch run app:heatmap-align -- --mat path\\to\\leg2.mat
"""

import argparse
import copy
import math
import os
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Literal

import cv2
import numpy as np
from heatmap_alignment_core import (
    H5_TIMELINE_TRACK_COLOR_HEX,
    LEG2_TIMELINE_TRACK_COLOR_HEX,
    PLAYHEAD_ALPHA,
    PLAYHEAD_PEN_WIDTH,
    SIGNAL_PLOT_BACKGROUND_HEX,
    SIGNAL_PLOT_NO_DETECTION_ALPHA,
    SIGNAL_PLOT_PRIMARY_SEGMENT_ALPHA,
    TIMELINE_PLAYHEAD_COLOR_HEX,
    AlignmentSession,
    CameraTrack,
    CameraVideoSource,
    ExportOverlaySettings,
    H5SlotIdentity,
    HeatmapPlotRenderer,
    HeatmapTrack,
    HeatmapTruthSource,
    Leg2MatImportError,
    Leg2UltrasonicSignalSeries,
    LoadedLeg2UltrasonicDatasource,
    DetectionSignalSeries,
    SignalPlotViewSettings,
    apply_viewport_visibility,
    build_leg2_ultrasonic_signal_series,
    build_peak_distance_signal_series,
    derive_signal_plot_color,
    desired_h5_identity,
    elide_path_middle,
    import_leg2_mat_for_heatmap,
    import_peak_distance_json_for_heatmap,
    rectify_viewport,
    scale_viewport_corners,
    TimelineH5DragSnapshot,
    apply_timeline_h5_alignment_drag,
    timeline_h5_drag_affects_alignment,
    timeline_view_bounds_s,
    visible_signal_y_range,
    visible_signal_y_range_for_series,
)
from heatmap_alignment_resource_summaries import (
    AlignmentResourceRuntime,
    ResourceAction,
    ResourceJobPresentation,
    ResourceKind,
    ResourceSummary,
    build_alignment_resource_summaries,
)
from sparse_iq_heatmap_common import (
    axis_center_index_at_fraction,
    distance_bin_width_m,
    distance_velocity_map,
    finite_axis_bin_width,
    heatmap_axes,
    select_subsweep,
)
from heatmap_alignment_resource_jobs import (
    CameraResourceJobResult,
    LoadedH5ResourcePayload,
    ResourceJobBoard,
    ResourceJobError,
    ResourceJobKind,
    ResourceJobSnapshot,
    ResourceJobSlotState,
    begin_resource_job,
    build_h5_truth_source_from_payload,
    clear_resource_job,
    complete_resource_job,
    load_h5_resource_payload,
    mark_resource_job_phase,
    release_resource_job_result,
    replacement_viewport_needs_default_reset,
    request_cancel_resource_job,
    resolve_replacement_viewport_corners,
    resource_job_blocks_export,
    resource_job_target_filename,
    run_camera_resource_job,
    should_apply_job_result,
)
from sparse_iq_peak_distance_core import (
    ALGORITHM_LABEL_SUM_VELOCITY,
    ALGORITHM_LABEL_ZERO_VELOCITY_SLICE,
    DEFAULT_DIST_NORM_REFERENCE_DISTANCE_M,
    DEFAULT_DIST_NORM_THRESHOLD_MAX,
    DEFAULT_DIST_NORM_THRESHOLD_MIN,
    DEFAULT_PEAK_THRESHOLD,
    PEAK_EXTRACTION_METHOD_SUM_VELOCITY,
    PEAK_EXTRACTION_METHOD_ZERO_VELOCITY_SLICE,
    PEAK_SELECTION_METHOD_STRONGEST_PEAK,
    STATUS_DETECTED,
    PeakDistanceJsonImportError,
)
from heatmap_peak_distance_resource import (
    PeakSeriesResourceAdapter,
    PeakSeriesResource,
    active_peak_measurements,
    active_peak_zero_velocity_m_s,
    build_generated_peak_series,
    build_imported_peak_series,
    default_generated_name,
    default_imported_name,
    generate_detection_series_from_heatmap_record,
    peak_state_detected_counts,
)
from heatmap_leg2_resource import Leg2ResourceAdapter
from heatmap_alignment_preview_sync import PreviewSyncPlan, run_preview_sync
from heatmap_alignment_session_coordinator import (
    LoadSessionPlan,
    LoadedResourceState,
    plan_session_reconcile,
)
from heatmap_alignment_session_lifecycle import (
    SessionLifecycleState,
    SessionPromptAction,
    SessionTransitionGuard,
)
from heatmap_alignment_widgets import (
    DetectionStripWidget,
    DoubleRangeSlider,
    ImagePreview,
    rgb_to_qpixmap,
)

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

import pyqtgraph as pg


from heatmap_alignment_dialogs import (  # noqa: F401
    ElidedPathItemDelegate,
    GenerateDetectionSeriesDialog,
    HeatmapDistanceHeader,
    RESOURCE_ACTION_LABELS,
    RESOURCE_JOB_STATUS_LABELS,
    RESOURCE_STATUS_LABELS,
    RESOURCES_DETAILS_PATH_BLOCK_TOP_MARGIN_PX,
    RESOURCES_DETAILS_SECTION_SPACING_PX,
    RESOURCES_TABLE_RESOURCE_COLUMN_DEFAULT_WIDTH_PX,
    RESOURCES_TABLE_STATUS_COLUMN_DEFAULT_WIDTH_PX,
    ResourceColorSwatchDelegate,
    ResourcesWindow,
)

GeneratePeakSeriesDialog = GenerateDetectionSeriesDialog
generate_peak_distances_from_heatmap_record = generate_detection_series_from_heatmap_record


class RecentSessionStore:
    """Persist the Heatmap Alignment Workbench recent-session list."""

    SETTINGS_KEY = "recent_session_paths"
    LIMIT = 10

    def __init__(self, settings: QtCore.QSettings) -> None:
        self._settings = settings

    @staticmethod
    def normalized_path(path: Path | str) -> str:
        return str(Path(path).expanduser().resolve(strict=False))

    @staticmethod
    def _dedupe_key(path: str) -> str:
        return os.path.normcase(path)

    def paths(self) -> tuple[Path, ...]:
        return tuple(Path(path) for path in self._read_path_strings())

    def add(self, path: Path | str) -> None:
        normalized = self.normalized_path(path)
        new_key = self._dedupe_key(normalized)
        remaining = [
            existing
            for existing in self._read_path_strings()
            if self._dedupe_key(existing) != new_key
        ]
        self._write_path_strings([normalized, *remaining][: self.LIMIT])

    def remove(self, path: Path | str) -> None:
        normalized = self.normalized_path(path)
        remove_key = self._dedupe_key(normalized)
        self._write_path_strings(
            [
                existing
                for existing in self._read_path_strings()
                if self._dedupe_key(existing) != remove_key
            ]
        )

    def clear(self) -> None:
        self._settings.remove(self.SETTINGS_KEY)

    def _read_path_strings(self) -> list[str]:
        raw_value = self._settings.value(self.SETTINGS_KEY, [])
        if isinstance(raw_value, str):
            candidates = [raw_value]
        elif isinstance(raw_value, (list, tuple)):
            candidates = [value for value in raw_value if isinstance(value, str)]
        else:
            candidates = []

        result: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            candidate = candidate.strip()
            if not candidate:
                continue
            normalized = self.normalized_path(candidate)
            key = self._dedupe_key(normalized)
            if key in seen:
                continue
            seen.add(key)
            result.append(normalized)
            if len(result) == self.LIMIT:
                break
        return result

    def _write_path_strings(self, paths: list[str]) -> None:
        self._settings.setValue(self.SETTINGS_KEY, paths[: self.LIMIT])


from heatmap_alignment_timeline_widgets import (  # noqa: F401
    AlignmentTimelineWidget,
    SignalPlotWidget,
    TimeAxisGeometry,
    TimelineRangeModel,
    _make_h5_signal_plot_pens,
    _make_leg2_signal_plot_pens,
    _plot_color_with_alpha,
    format_track_offset_label,
    track_offset_label_rect,
    track_offset_label_should_show,
    TIMELINE_LABEL_GUTTER_PX,
    TIMELINE_OFFSET_LABEL_COLOR_HEX,
    TIMELINE_TRACK_OFFSET_LABEL_MARGIN_PX,
)


from heatmap_alignment_viewport_widgets import (  # noqa: F401
    CornerEditorWidget,
    ViewportEditorWidget,
)


class SourceResolutionViewportWorker(QtCore.QObject):
    render_finished = QtCore.Signal(object)

    @QtCore.Slot(object)
    def render_request(self, request: object) -> None:
        payload = dict(request) if isinstance(request, dict) else {}
        result: dict[str, object] = {"token": payload.get("token"), "frame": None, "error": None}
        try:
            camera_path = Path(str(payload["camera_path"]))
            source = CameraVideoSource(camera_path, max_preview_dimension=None)
            try:
                _, frame = source.frame_at_seconds(
                    float(payload["camera_time_s"]),
                    access_hint="random",
                )
            finally:
                source.close()
            viewport_frame = rectify_viewport(
                frame,
                np.asarray(payload["corners"], dtype=np.float32),
                tuple(int(value) for value in payload["output_size"]),
            )
            result["frame"] = viewport_frame
        except Exception as exc:
            result["error"] = str(exc)
        self.render_finished.emit(result)


from heatmap_alignment_resource_job_manager import (  # noqa: F401
    _ResourceJobRunnable,
    ResourceJobManager,
)


@dataclass
class _CameraResourceBackup:
    camera_source: CameraVideoSource
    reference_width: int
    reference_height: int
    camera_track: CameraTrack
    current_camera_frame: np.ndarray | None
    viewport_corners: list[list[float]]
    export_overlay: ExportOverlaySettings


@dataclass
class _H5ResourceBackup:
    heatmap_source: HeatmapTruthSource
    heatmap_track: HeatmapTrack
    viewport_output_width: int
    viewport_output_height: int


class HeatmapAlignmentWindow(QtWidgets.QMainWindow):
    """Main window for the manual alignment workbench."""

    source_resolution_viewport_render_requested = QtCore.Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Heatmap Alignment Workbench")
        self.resize(1600, 980)

        self.session = AlignmentSession()
        self._session_lifecycle = SessionLifecycleState()
        self._resources_window: ResourcesWindow | None = None
        self._resource_reload_errors: dict[ResourceKind, str] = {}
        self._resource_load_warnings: dict[ResourceKind, tuple[str, ...]] = {}
        self.camera_source: CameraVideoSource | None = None
        self.heatmap_source: HeatmapTruthSource | None = None
        self.current_camera_frame: np.ndarray | None = None
        self._camera_reference_width = 0
        self._camera_reference_height = 0
        self._overlay_plot_renderer: HeatmapPlotRenderer | None = None
        self._hover_dvm_cache: tuple[int, np.ndarray] | None = None
        self._hover_last_pos: QtCore.QPoint | None = None
        self._heatmap_axes = None
        self._peak_series_list: list[PeakSeriesResource] = []
        self._heatmap_peak_selector_id: str | None = None
        self.leg2_ultrasonic_datasource: LoadedLeg2UltrasonicDatasource | None = None
        self._freeze_export_overlay_preview = False
        self._export_in_progress = False
        self.settings = QtCore.QSettings("Acconeer", "HeatmapAlignmentWorkbench")
        self._viewport_drag_start_corners: np.ndarray | None = None
        self._playback_started_at_s: float | None = None
        self._playback_started_video_time_s = 0.0
        self._source_resolution_viewport_frame: np.ndarray | None = None
        self._source_resolution_request_token = 0
        self._source_resolution_worker_busy = False
        self._pending_source_resolution_request: dict[str, object] | None = None
        self._resource_job_manager = ResourceJobManager(self)
        self._resource_job_manager.job_state_changed.connect(
            self._handle_resource_job_state_changed
        )
        self.recent_sessions = RecentSessionStore(self.settings)
        self._camera_replacement_backup: _CameraResourceBackup | None = None
        self._h5_replacement_backup: _H5ResourceBackup | None = None
        self._inflight_h5_identity: H5SlotIdentity | None = None
        self._pending_peak_session_reload: bool = False

        self.viewport_source_resolution_timer = QtCore.QTimer(self)
        self.viewport_source_resolution_timer.setSingleShot(True)
        self.viewport_source_resolution_timer.setInterval(200)
        self.viewport_source_resolution_timer.timeout.connect(
            self._start_debounced_source_resolution_viewport
        )

        self._source_resolution_thread = QtCore.QThread(self)
        self._source_resolution_worker = SourceResolutionViewportWorker()
        self._source_resolution_worker.moveToThread(self._source_resolution_thread)
        self.source_resolution_viewport_render_requested.connect(
            self._source_resolution_worker.render_request,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )
        self._source_resolution_worker.render_finished.connect(
            self._handle_source_resolution_viewport_result
        )
        self._source_resolution_thread.start()

        self.play_timer = QtCore.QTimer(self)
        self.play_timer.timeout.connect(self._advance_playback)
        self.play_timer_interval_ms = 16
        self.timeline_range_model = TimelineRangeModel(self)
        self._timeline_axis_geometry_sync_timer = QtCore.QTimer(self)
        self._timeline_axis_geometry_sync_timer.setSingleShot(True)
        self._timeline_axis_geometry_sync_timer.timeout.connect(self._sync_timeline_axis_geometry)

        self._create_menu_bar()
        self._build_ui()
        self.signal_plot.attach_timeline_range_model(self.timeline_range_model)
        self.timeline_view.set_signals_plot(self.signal_plot)
        self._connect_signals()
        self._update_controls_enabled_state()
        self._refresh_session_title()
        self._refresh_resources_ui()
        self.statusBar().showMessage("Load camera video and H5 recording to begin.")
        QtCore.QTimer.singleShot(0, self.schedule_timeline_axis_geometry_sync)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if not self._handle_session_transition_guard("quit"):
            event.ignore()
            return
        self.viewport_source_resolution_timer.stop()
        self._source_resolution_thread.quit()
        self._source_resolution_thread.wait()
        self._close_sources()
        super().closeEvent(event)

    def _abandon_resource_jobs(self) -> None:
        self._resource_job_manager.abandon_all_jobs()
        self._discard_camera_replacement_backup()
        self._discard_h5_replacement_backup()
        self._pending_peak_session_reload = False

    def _discard_camera_replacement_backup(self) -> None:
        backup = self._camera_replacement_backup
        if isinstance(backup, _CameraResourceBackup):
            backup.camera_source.close()
        self._camera_replacement_backup = None

    def _discard_h5_replacement_backup(self) -> None:
        backup = self._h5_replacement_backup
        if isinstance(backup, _H5ResourceBackup):
            backup.heatmap_source.close()
        self._h5_replacement_backup = None
        self._inflight_h5_identity = None
        self._pending_peak_session_reload = False

    def _create_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        self.open_session_action = QtGui.QAction("Open Session...", self)
        self.open_session_action.triggered.connect(self._load_session)
        file_menu.addAction(self.open_session_action)

        self.save_session_action = QtGui.QAction("Save Session", self)
        self.save_session_action.setShortcut(QtGui.QKeySequence.StandardKey.Save)
        self.save_session_action.triggered.connect(self._save_session)
        file_menu.addAction(self.save_session_action)

        self.save_session_as_action = QtGui.QAction("Save Session As...", self)
        self.save_session_as_action.triggered.connect(self._save_session_as)
        file_menu.addAction(self.save_session_as_action)

        self.recent_sessions_menu = file_menu.addMenu("Recent Sessions")

        self.close_session_action = QtGui.QAction("Close Session", self)
        self.close_session_action.triggered.connect(self._close_session)
        file_menu.addAction(self.close_session_action)

        file_menu.addSeparator()

        self.export_synced_action = QtGui.QAction("Export Synced Video...", self)
        self.export_synced_action.triggered.connect(self._export_synced_video)
        file_menu.addAction(self.export_synced_action)

        file_menu.addSeparator()

        quit_action = QtGui.QAction("&Quit", self)
        quit_action.setShortcut(QtGui.QKeySequence.StandardKey.Quit)
        quit_action.setMenuRole(QtGui.QAction.MenuRole.QuitRole)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        resources_menu = self.menuBar().addMenu("&Resources")

        self.manage_resources_action = QtGui.QAction("&Manage Resources...", self)
        self.manage_resources_action.triggered.connect(self._show_resources_window)
        resources_menu.addAction(self.manage_resources_action)

        resources_menu.addSeparator()

        self.load_camera_action = QtGui.QAction("&Load Camera Video...", self)
        self.load_camera_action.triggered.connect(self._load_camera_video)
        resources_menu.addAction(self.load_camera_action)

        self.load_h5_action = QtGui.QAction("Load Radar Raw (&H5)...", self)
        self.load_h5_action.triggered.connect(self._load_h5_recording)
        resources_menu.addAction(self.load_h5_action)

        self.load_peak_action = QtGui.QAction("Import Peak Series (&JSON)...", self)
        self.load_peak_action.triggered.connect(self._import_peak_series)
        resources_menu.addAction(self.load_peak_action)

        self.load_leg2_action = QtGui.QAction("Load &Leg2 MAT...", self)
        self.load_leg2_action.triggered.connect(self._import_leg2_mat)
        resources_menu.addAction(self.load_leg2_action)

        self._refresh_recent_sessions_menu()

        resources_menu.addSeparator()

        self.unload_camera_action = QtGui.QAction("&Unload Camera Video", self)
        self.unload_camera_action.triggered.connect(self.unload_camera_video)
        resources_menu.addAction(self.unload_camera_action)

        self.unload_h5_action = QtGui.QAction("Unload Radar Raw (&H5)", self)
        self.unload_h5_action.triggered.connect(self.unload_h5_recording)
        resources_menu.addAction(self.unload_h5_action)

        self.unload_peak_action = QtGui.QAction("&Unload Peak Series", self)
        self.unload_peak_action.triggered.connect(self._unload_last_peak_series)
        resources_menu.addAction(self.unload_peak_action)

        self.unload_leg2_action = QtGui.QAction("Unload &Leg2 MAT", self)
        self.unload_leg2_action.triggered.connect(self._clear_leg2_ultrasonic_datasource)
        resources_menu.addAction(self.unload_leg2_action)

        resources_menu.addSeparator()

        self.reload_camera_action = QtGui.QAction("&Reload Camera Video", self)
        self.reload_camera_action.triggered.connect(
            lambda: self.invoke_resource_action("camera", "reload")
        )
        resources_menu.addAction(self.reload_camera_action)

        self.reload_h5_action = QtGui.QAction("Reload Radar Raw (&H5)", self)
        self.reload_h5_action.triggered.connect(
            lambda: self.invoke_resource_action("radar_h5", "reload")
        )
        resources_menu.addAction(self.reload_h5_action)

        self.reload_peak_action = QtGui.QAction("Reload Peak &Series", self)
        self.reload_peak_action.triggered.connect(
            lambda: self.invoke_resource_action("radar_peak", "reload")
        )
        resources_menu.addAction(self.reload_peak_action)

        self.reload_leg2_action = QtGui.QAction("Reload &Leg2 MAT", self)
        self.reload_leg2_action.triggered.connect(
            lambda: self.invoke_resource_action("leg2_mat", "reload")
        )
        resources_menu.addAction(self.reload_leg2_action)

    def _refresh_recent_sessions_menu(self) -> None:
        self.recent_sessions_menu.clear()
        recent_paths = self.recent_sessions.paths()
        if recent_paths:
            for session_path in recent_paths:
                action = QtGui.QAction(session_path.name, self)
                action.setToolTip(str(session_path))
                action.setStatusTip(str(session_path))
                action.triggered.connect(
                    lambda _checked=False, path=session_path: self._open_recent_session(path)
                )
                self.recent_sessions_menu.addAction(action)
        else:
            empty_action = QtGui.QAction("No Recent Sessions", self)
            empty_action.setEnabled(False)
            self.recent_sessions_menu.addAction(empty_action)

        self.recent_sessions_menu.addSeparator()
        clear_action = QtGui.QAction("Clear Recent Sessions", self)
        clear_action.setEnabled(bool(recent_paths))
        clear_action.triggered.connect(self._clear_recent_sessions)
        self.recent_sessions_menu.addAction(clear_action)

    def _record_recent_session(self, session_path: Path) -> None:
        self.recent_sessions.add(session_path)
        self._refresh_recent_sessions_menu()

    def _clear_recent_sessions(self) -> None:
        self.recent_sessions.clear()
        self._refresh_recent_sessions_menu()

    def _open_recent_session(self, session_path: Path) -> None:
        if not session_path.exists():
            message = f"Session file no longer exists: {session_path}"
            self.statusBar().showMessage(message)
            self.recent_sessions.remove(session_path)
            self._refresh_recent_sessions_menu()
            return

        self._open_session(LoadSessionPlan(session_path=session_path, prompt_for_unsaved=True))

    def _open_session(self, plan: LoadSessionPlan) -> bool:
        if plan.prompt_for_unsaved and not self._handle_session_transition_guard("open"):
            return False

        try:
            self.load_session_from_path(plan.session_path)
        except (OSError, ValueError) as exc:
            QtWidgets.QMessageBox.warning(self, "Open session failed", str(exc))
            self.statusBar().showMessage(f"Could not open session: {plan.session_path}")
            return False

        return True

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(central)

        self.preview_signals_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.preview_signals_splitter.setObjectName("preview_signals_splitter")
        self.preview_signals_splitter.setChildrenCollapsible(False)

        self.preview_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.preview_splitter.setObjectName("preview_splitter")
        self.camera_view = CornerEditorWidget()
        self.camera_view.setMinimumSize(100, 40)
        self.viewport_view = ViewportEditorWidget("Viewport")
        self.viewport_view.setMinimumSize(100, 40)
        self.truth_view = ImagePreview("Rendered Heatmap")
        self.truth_view.setMinimumSize(100, 40)
        self.truth_view.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.truth_view.setLineWidth(0)
        camera_group = self._wrap_group("Camera Video", self.camera_view)
        camera_group.setMinimumHeight(self._stacked_layout_minimum_height(camera_group.layout()))
        viewport_group = QtWidgets.QGroupBox("Viewport")
        viewport_layout = QtWidgets.QVBoxLayout(viewport_group)
        viewport_layout.addWidget(self.viewport_view)
        self.viewport_controls_widget = QtWidgets.QWidget()
        viewport_controls_layout = QtWidgets.QGridLayout(self.viewport_controls_widget)
        viewport_controls_layout.setContentsMargins(0, 0, 0, 0)
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        viewport_layout.addWidget(self.viewport_controls_widget)
        right_layout.addWidget(viewport_group)
        rendered_heatmap_group = QtWidgets.QGroupBox("Rendered Heatmap")
        rendered_heatmap_layout = QtWidgets.QVBoxLayout(rendered_heatmap_group)
        rendered_heatmap_layout.setSpacing(0)
        self._heatmap_distance_header = HeatmapDistanceHeader()
        rendered_heatmap_layout.addWidget(self._heatmap_distance_header)
        self._detection_strip = DetectionStripWidget()
        rendered_heatmap_layout.addWidget(self._detection_strip)
        rendered_heatmap_layout.addWidget(self.truth_view)
        self.truth_view.setMouseTracking(True)
        self.truth_view.installEventFilter(self)
        self.rendered_heatmap_controls_widget = QtWidgets.QWidget()
        rendered_heatmap_controls_layout = QtWidgets.QVBoxLayout(
            self.rendered_heatmap_controls_widget
        )
        rendered_heatmap_controls_layout.setContentsMargins(0, 0, 0, 0)
        rendered_heatmap_color_row = QtWidgets.QHBoxLayout()
        self.color_min_spin = QtWidgets.QDoubleSpinBox()
        self.color_min_spin.setRange(0.0, 1_000_000.0)
        self.color_min_spin.setValue(0.0)
        self.color_min_spin.setDecimals(1)
        self.color_min_spin.setSingleStep(100.0)
        self.color_max_spin = QtWidgets.QDoubleSpinBox()
        self.color_max_spin.setRange(0.0, 1_000_000.0)
        self.color_max_spin.setValue(3000.0)
        self.color_max_spin.setDecimals(1)
        self.color_max_spin.setSingleStep(100.0)
        rendered_heatmap_color_row.addWidget(QtWidgets.QLabel("Color Min"))
        rendered_heatmap_color_row.addWidget(self.color_min_spin)
        rendered_heatmap_color_row.addWidget(QtWidgets.QLabel("Color Max"))
        rendered_heatmap_color_row.addWidget(self.color_max_spin)
        rendered_heatmap_color_row.addStretch(1)
        self._heatmap_vel_extent_label = QtWidgets.QLabel("")
        self._heatmap_vel_extent_label.setStyleSheet("color: #d7dde6; font-size: 10px;")
        rendered_heatmap_color_row.addWidget(self._heatmap_vel_extent_label)
        rendered_heatmap_controls_layout.addLayout(rendered_heatmap_color_row)
        # Detection algorithm selector.
        rendered_heatmap_peak_row = QtWidgets.QHBoxLayout()
        rendered_heatmap_peak_row.addWidget(QtWidgets.QLabel("Detection Algorithm:"))
        self._heatmap_peak_combo = QtWidgets.QComboBox()
        self._heatmap_peak_combo.addItem("None", None)
        self._heatmap_peak_combo.setToolTip(
            "Select which detection series to use for the rendered heatmap marker. "
            "Independent of Signals plot visibility."
        )
        self._heatmap_peak_combo.currentIndexChanged.connect(self._on_heatmap_peak_combo_changed)
        rendered_heatmap_peak_row.addWidget(self._heatmap_peak_combo)
        rendered_heatmap_peak_row.addStretch(1)
        rendered_heatmap_controls_layout.addLayout(rendered_heatmap_peak_row)
        rendered_heatmap_layout.addWidget(self.rendered_heatmap_controls_widget)
        right_layout.addWidget(rendered_heatmap_group)
        self.preview_splitter.addWidget(camera_group)
        self.preview_splitter.addWidget(right_panel)
        self.preview_splitter.setChildrenCollapsible(False)
        self.preview_splitter.setStretchFactor(0, 3)
        self.preview_splitter.setStretchFactor(1, 2)

        signals_group = QtWidgets.QGroupBox("Signals")
        signals_group.setMinimumHeight(200)
        signals_layout = QtWidgets.QVBoxLayout(signals_group)
        signals_layout.setContentsMargins(9, 9, 9, 9)
        signals_controls_row = QtWidgets.QHBoxLayout()
        self.leg2_signal_kind_combo = QtWidgets.QComboBox()
        self.leg2_signal_kind_combo.addItem("Raw ultrasonic", "raw")
        self.leg2_signal_kind_combo.addItem("Filtered ultrasonic", "filtered")
        signals_controls_row.addWidget(self.leg2_signal_kind_combo)
        signals_controls_row.addStretch(1)
        signals_layout.addLayout(signals_controls_row)
        self.signal_plot = SignalPlotWidget()
        self.signal_plot.setMinimumHeight(160)
        signals_layout.addWidget(self.signal_plot)
        self.preview_signals_splitter.addWidget(self.preview_splitter)
        self.preview_signals_splitter.addWidget(signals_group)
        self.preview_signals_splitter.setStretchFactor(0, 3)
        self.preview_signals_splitter.setStretchFactor(1, 2)
        self.preview_signals_splitter.setSizes([360, 240])
        layout.addWidget(self.preview_signals_splitter, stretch=1)

        timeline_group = QtWidgets.QGroupBox("Timeline")
        timeline_group.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed
        )
        timeline_layout = QtWidgets.QVBoxLayout(timeline_group)
        timeline_layout.setContentsMargins(9, 9, 9, 9)
        timeline_controls_layout = QtWidgets.QHBoxLayout()
        self.play_button = QtWidgets.QPushButton("Play")
        self.current_time_label = QtWidgets.QLabel("t = 0.000 s")
        self.timeline_view = AlignmentTimelineWidget(self.timeline_range_model)
        self.current_time_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.current_time_slider.setRange(0, 10000)
        self.offset_spin = QtWidgets.QDoubleSpinBox()
        self.offset_spin.setDecimals(3)
        self.offset_spin.setRange(-3600.0, 3600.0)
        self.offset_spin.setSingleStep(0.01)
        self.nudge_left_small = QtWidgets.QPushButton("-10 ms")
        self.nudge_right_small = QtWidgets.QPushButton("+10 ms")
        self.nudge_left_large = QtWidgets.QPushButton("-100 ms")
        self.nudge_right_large = QtWidgets.QPushButton("+100 ms")
        timeline_controls_layout.addWidget(self.play_button)
        timeline_controls_layout.addWidget(self.current_time_label)
        timeline_controls_layout.addWidget(QtWidgets.QLabel("Camera offset (s)"))
        timeline_controls_layout.addWidget(self.offset_spin)
        timeline_controls_layout.addWidget(self.nudge_left_large)
        timeline_controls_layout.addWidget(self.nudge_left_small)
        timeline_controls_layout.addWidget(self.nudge_right_small)
        timeline_controls_layout.addWidget(self.nudge_right_large)
        timeline_controls_layout.addStretch(1)
        timeline_layout.addLayout(timeline_controls_layout)
        timeline_layout.addWidget(self.timeline_view)
        timeline_layout.addWidget(self.current_time_slider)
        layout.addWidget(timeline_group)

        self.viewport_enhance_checkbox = QtWidgets.QCheckBox("Enhance Viewport")
        self.viewport_map_to_viridis_checkbox = QtWidgets.QCheckBox("Map to Viridis")
        self.viewport_range_slider = DoubleRangeSlider()
        self.viewport_low_label = QtWidgets.QLabel("Low 0.00")
        self.viewport_high_label = QtWidgets.QLabel("High 1.00")
        self.viewport_gamma_spin = QtWidgets.QDoubleSpinBox()
        self.viewport_gamma_spin.setRange(0.1, 5.0)
        self.viewport_gamma_spin.setSingleStep(0.05)
        self.viewport_gamma_spin.setValue(1.0)
        self.viewport_gamma_spin.setDecimals(2)
        viewport_controls_layout.addWidget(self.viewport_enhance_checkbox, 0, 0, 1, 2)
        viewport_controls_layout.addWidget(self.viewport_map_to_viridis_checkbox, 0, 2, 1, 2)
        viewport_controls_layout.addWidget(QtWidgets.QLabel("Range"), 1, 0)
        viewport_controls_layout.addWidget(self.viewport_low_label, 1, 1)
        viewport_controls_layout.addWidget(self.viewport_range_slider, 1, 2, 1, 3)
        viewport_controls_layout.addWidget(self.viewport_high_label, 1, 5)
        viewport_controls_layout.addWidget(QtWidgets.QLabel("Gamma"), 2, 0)
        viewport_controls_layout.addWidget(self.viewport_gamma_spin, 2, 1)
        viewport_controls_layout.setColumnStretch(2, 1)
        viewport_group.setMinimumHeight(self._stacked_layout_minimum_height(viewport_layout))
        rendered_heatmap_group.setMinimumHeight(
            self._stacked_layout_minimum_height(rendered_heatmap_layout)
        )
        right_panel.setMinimumHeight(self._stacked_layout_minimum_height(right_layout))

        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self.leg2_signal_kind_combo.currentIndexChanged.connect(self._leg2_signal_kind_changed)
        self.play_button.clicked.connect(self._toggle_playback)
        self.timeline_view.playhead_changed.connect(self._timeline_playhead_changed)
        self.signal_plot.playhead_scrubbed.connect(self._signal_playhead_scrubbed)
        self.timeline_view.camera_offset_changed.connect(self._timeline_camera_offset_changed)
        self.timeline_view.leg2_offset_changed.connect(self._timeline_leg2_offset_changed)
        self.timeline_view.h5_alignment_drag_changed.connect(
            self._timeline_h5_alignment_drag_changed
        )
        self.timeline_view.h5_alignment_drag_finished.connect(
            self._timeline_h5_alignment_drag_finished
        )
        self.current_time_slider.valueChanged.connect(self._slider_to_time)
        self.offset_spin.valueChanged.connect(self._offset_changed)
        self.nudge_left_small.clicked.connect(lambda: self._nudge_offset(-0.010))
        self.nudge_right_small.clicked.connect(lambda: self._nudge_offset(0.010))
        self.nudge_left_large.clicked.connect(lambda: self._nudge_offset(-0.100))
        self.nudge_right_large.clicked.connect(lambda: self._nudge_offset(0.100))
        self.color_min_spin.valueChanged.connect(self._render_settings_changed)
        self.color_max_spin.valueChanged.connect(self._render_settings_changed)
        self.viewport_enhance_checkbox.toggled.connect(self._viewport_visibility_changed)
        self.viewport_map_to_viridis_checkbox.toggled.connect(self._viewport_visibility_changed)
        self.viewport_range_slider.values_changed.connect(self._viewport_visibility_range_changed)
        self.viewport_gamma_spin.valueChanged.connect(self._viewport_visibility_changed)
        self.camera_view.corners_changed.connect(self._corners_changed)
        self.camera_view.export_overlay_changed.connect(self._export_overlay_changed)
        self.camera_view.export_overlay_visibility_changed.connect(
            self._set_export_overlay_visible
        )
        self.camera_view.export_overlay_preview_toggled.connect(
            self._set_export_overlay_preview_enabled
        )
        self.camera_view.export_overlay_reset_requested.connect(self._reset_export_overlay)
        self.camera_view.export_overlay_drag_active_changed.connect(
            self._set_export_overlay_drag_active
        )
        self.viewport_view.resized.connect(self._viewport_preview_resized)
        self.viewport_view.corner_dragged.connect(self._viewport_corner_dragged)
        self.viewport_view.edge_dragged.connect(self._viewport_edge_dragged)
        self.viewport_view.center_dragged.connect(self._viewport_center_dragged)
        self.viewport_view.drag_finished.connect(self._viewport_drag_finished)
        self.signal_plot.view_settings_changed.connect(self._signal_plot_view_settings_changed)
        self.signal_plot.axis_geometry_sync_requested.connect(
            self.schedule_timeline_axis_geometry_sync
        )

    def schedule_timeline_axis_geometry_sync(self) -> None:
        self._timeline_axis_geometry_sync_timer.start(0)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self.schedule_timeline_axis_geometry_sync()

    def _sync_timeline_axis_geometry(self) -> None:
        if not self.isVisible():
            return
        signal_left_px, signal_right_px = self.signal_plot.viewbox_horizontal_extent_local()
        if signal_right_px <= signal_left_px + 1.0:
            return

        timeline_width_px = self.timeline_view.width()
        if timeline_width_px <= 1:
            return

        left_global = self.signal_plot.mapToGlobal(QtCore.QPointF(signal_left_px, 0.0))
        right_global = self.signal_plot.mapToGlobal(QtCore.QPointF(signal_right_px, 0.0))
        timeline_left_px = self.timeline_view.mapFromGlobal(left_global).x()
        timeline_right_px = self.timeline_view.mapFromGlobal(right_global).x()

        if timeline_right_px <= timeline_left_px + 1.0:
            return
        self.timeline_view.set_time_axis_rect(timeline_left_px, timeline_right_px)

    def _wrap_group(self, title: str, widget: QtWidgets.QWidget) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(group)
        layout.addWidget(widget)
        return group

    @staticmethod
    def _stacked_layout_minimum_height(layout: QtWidgets.QLayout) -> int:
        """Return the minimum height for this window's vertical stacked layouts."""
        margins = layout.contentsMargins()
        height = margins.top() + margins.bottom()
        visible_items = [
            layout.itemAt(index)
            for index in range(layout.count())
            if layout.itemAt(index) is not None
            and not HeatmapAlignmentWindow._item_is_hidden(layout.itemAt(index))
        ]
        if visible_items:
            height += max(0, layout.spacing()) * (len(visible_items) - 1)
        for item in visible_items:
            widget = item.widget()
            if widget is not None:
                height += max(widget.minimumHeight(), widget.minimumSizeHint().height())
                continue
            child_layout = item.layout()
            if child_layout is not None:
                height += HeatmapAlignmentWindow._stacked_layout_minimum_height(child_layout)
                continue
            height += item.minimumSize().height()
        return height

    @staticmethod
    def _item_is_hidden(item: QtWidgets.QLayoutItem) -> bool:
        widget = item.widget()
        return widget is not None and widget.isHidden()

    def _close_sources(self) -> None:
        self._abandon_resource_jobs()
        self._set_playback_active(False, refresh_viewport=False)
        self.viewport_source_resolution_timer.stop()
        self._source_resolution_request_token += 1
        self._source_resolution_viewport_frame = None
        self._pending_source_resolution_request = None
        if self.camera_source is not None:
            self.camera_source.close()
            self.camera_source = None
        self._camera_reference_width = 0
        self._camera_reference_height = 0
        self._overlay_plot_renderer = None
        self._freeze_export_overlay_preview = False
        if self.heatmap_source is not None:
            self.heatmap_source.close()
            self.heatmap_source = None
        self._peak_series_list = []
        self.leg2_ultrasonic_datasource = None
        self.camera_view.set_export_overlay_preview_frame(None)
        self.camera_view.set_corners(None)
        self.viewport_view.set_frame(None)

    def _clear_active_camera_resource(self) -> None:
        self._set_playback_active(False, refresh_viewport=False)
        if self.camera_source is not None:
            self.camera_source = None
        self._camera_reference_width = 0
        self._camera_reference_height = 0
        self.current_camera_frame = None
        self.session.camera_track = CameraTrack()
        self.session.export_overlay = ExportOverlaySettings()
        self.session.timeline.offset_s = 0.0
        self._freeze_export_overlay_preview = False
        self.camera_view.set_frame(None)
        self.camera_view.set_corners(None)
        self.camera_view.set_export_overlay(self.session.export_overlay)
        self.camera_view.set_export_overlay_preview_frame(None)
        self._source_resolution_request_token += 1
        self._source_resolution_viewport_frame = None
        self._pending_source_resolution_request = None
        self.viewport_view.set_frame(None)

    def _clear_active_h5_resource(self) -> None:
        self._set_playback_active(False, refresh_viewport=False)
        if self.heatmap_source is not None:
            self.heatmap_source = None
        self._overlay_plot_renderer = None
        self._hover_dvm_cache = None
        self._hover_last_pos = None
        self._heatmap_axes = None
        self.session.heatmap_track = HeatmapTrack()
        self.session.viewport.output_width = 0
        self.session.viewport.output_height = 0
        self.truth_view.set_frame(None)
        self._detection_strip.set_detection_ratio(None)
        QtWidgets.QToolTip.hideText()
        self._update_heatmap_peak_cue(None)
        self._update_heatmap_extent_labels()
        self.camera_view.set_export_overlay_preview_frame(None)
        self.viewport_view.set_frame(None)

    def _load_camera_video(self) -> None:
        start_path = self._dialog_start_path("last_camera_path")
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load camera video",
            start_path,
            "Video files (*.mp4 *.mov *.avi *.mkv);;All files (*)",
        )
        if filename:
            self.load_camera_from_path(Path(filename))

    def load_camera_from_path(self, camera_path: Path, *, mark_dirty: bool = True) -> None:
        if mark_dirty:
            self._mark_session_dirty()
        if not camera_path.exists():
            self._set_resource_reload_error("camera", f"File not found: {camera_path}")
            self._refresh_resources_ui()
            return
        replaces_active = self.camera_source is not None
        if replaces_active:
            self._camera_replacement_backup = self._snapshot_active_camera()
            self._clear_active_camera_resource()
        self.session.camera_track = CameraTrack(path=str(camera_path))
        self._set_resource_reload_error("camera", None)
        self._resource_job_manager.start_camera_job(
            camera_path,
            replaces_active=replaces_active,
        )
        self._update_controls_enabled_state()
        self._update_resource_loading_overlays()
        self._refresh_resources_ui()
        self.statusBar().showMessage(f"Loading camera video: {camera_path.name}")

    def _load_h5_recording(self) -> None:
        start_path = self._dialog_start_path("last_h5_path")
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load H5 recording",
            start_path,
            "H5 files (*.h5 *.hdf5);;All files (*)",
        )
        if filename:
            self.load_h5_from_path(Path(filename))

    def load_h5_from_path(self, h5_path: Path, *, mark_dirty: bool = True) -> None:
        if mark_dirty:
            self._mark_session_dirty()
        if not h5_path.exists():
            self._set_resource_reload_error("radar_h5", f"File not found: {h5_path}")
            self._refresh_resources_ui()
            return
        session_idx = self.session.heatmap_track.session_idx
        group_idx = self.session.heatmap_track.group_idx
        entry_idx = self.session.heatmap_track.entry_idx
        subsweep_idx = self.session.heatmap_track.subsweep_idx
        replaces_active = self.heatmap_source is not None
        if replaces_active:
            self._h5_replacement_backup = self._snapshot_active_h5()
            self._clear_active_h5_resource()
        self.session.heatmap_track = HeatmapTrack(
            path=str(h5_path),
            session_idx=session_idx,
            group_idx=group_idx,
            entry_idx=entry_idx,
            subsweep_idx=subsweep_idx,
        )
        self._set_resource_reload_error("radar_h5", None)
        self._inflight_h5_identity = H5SlotIdentity(
            path=str(h5_path),
            session_idx=session_idx,
            group_idx=group_idx,
            entry_idx=entry_idx,
            subsweep_idx=subsweep_idx,
        )
        self._resource_job_manager.start_h5_job(
            h5_path,
            replaces_active=replaces_active,
            session_idx=session_idx,
            group_idx=group_idx,
            entry_idx=entry_idx,
            subsweep_idx=subsweep_idx,
            color_min=self.color_min_spin.value(),
            color_max=self.color_max_spin.value(),
            fixed_levels=True,
        )
        self._update_controls_enabled_state()
        self._update_resource_loading_overlays()
        self._refresh_resources_ui()
        self.statusBar().showMessage(f"Loading H5 recording: {h5_path.name}")

    def _peak_csv_rejection_message(self) -> str:
        return (
            "Reduced CSV peak-distance exports cannot be imported here. "
            "Use the canonical JSON export from `hatch run app:peak-distances`."
        )

    def _confirm_action_dialog(
        self,
        *,
        title: str,
        question: str,
        informative: str = "",
        accept_label: str,
        reject_label: str = "Cancel",
    ) -> bool:
        """Show a confirmation with the question in the body and verb-labeled buttons."""
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Icon.Question)
        box.setWindowTitle(title)
        box.setText(question)
        if informative:
            box.setInformativeText(informative)
        box.setStandardButtons(
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        accept_button = box.button(QtWidgets.QMessageBox.StandardButton.Yes)
        reject_button = box.button(QtWidgets.QMessageBox.StandardButton.No)
        if accept_button is not None:
            accept_button.setText(accept_label)
        if reject_button is not None:
            reject_button.setText(reject_label)
        box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Yes)
        return box.exec() == QtWidgets.QMessageBox.StandardButton.Yes

    def _clear_peak_series(self, *, mark_dirty: bool = True, confirm: bool = True) -> None:
        if (
            confirm
            and self._any_peaks_unsaved()
            and not self._confirm_action_dialog(
                title="Discard peaks",
                question="Discard unsaved peak-distance data?",
                accept_label="Discard",
            )
        ):
            return
        if mark_dirty:
            self._mark_session_dirty()
        self._peak_series_list = []
        self._heatmap_peak_selector_id = None
        self._set_resource_reload_error("radar_peak", None)
        self._set_resource_warnings("radar_peak", ())
        self._sync_previews(camera_access_hint="auto")
        self._refresh_resources_ui()
        self.statusBar().showMessage("Peak series cleared.")

    def load_leg2_mat_from_path(
        self,
        mat_path: Path,
        *,
        show_dialogs: bool = False,
        mark_dirty: bool = True,
    ) -> bool:
        if mark_dirty:
            self._mark_session_dirty()
        try:
            datasource = import_leg2_mat_for_heatmap(mat_path)
        except (Leg2MatImportError, TypeError) as exc:
            if isinstance(exc, Leg2MatImportError):
                message = exc.user_message()
                status_message = exc.user_message().splitlines()[0]
            else:
                message = f"Could not load Leg2 MAT: {exc}"
                status_message = message
            if show_dialogs:
                QtWidgets.QMessageBox.warning(self, "Import failed", message)
            else:
                self.statusBar().showMessage(status_message)
            self._set_resource_reload_error("leg2_mat", status_message)
            self._refresh_resources_ui()
            return False
        except ValueError as exc:
            message = str(exc)
            if show_dialogs:
                QtWidgets.QMessageBox.warning(self, "Import failed", message)
            else:
                self.statusBar().showMessage(f"Could not load Leg2 MAT: {message}")
            self._set_resource_reload_error("leg2_mat", message)
            self._refresh_resources_ui()
            return False

        self.leg2_ultrasonic_datasource = datasource
        self._leg2_adapter().remember_path(mat_path)
        self.settings.setValue("last_leg2_mat_path", str(mat_path))
        self._set_resource_reload_error("leg2_mat", None)
        self._set_resource_warnings("leg2_mat", ())
        self._update_leg2_datasource_controls()
        self._sync_previews(camera_access_hint="auto")
        self._refresh_resources_ui()
        self.statusBar().showMessage(f"Loaded Leg2 MAT: {mat_path.name}")
        return True

    def _import_leg2_mat(self) -> None:
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import Leg2 MAT",
            self._dialog_start_path("last_leg2_mat_path"),
            "MATLAB files (*.mat);;All files (*)",
        )
        if not filename:
            return
        self.load_leg2_mat_from_path(Path(filename), show_dialogs=True)

    def _clear_leg2_ultrasonic_datasource(self, *, mark_dirty: bool = True) -> None:
        if mark_dirty:
            self._mark_session_dirty()
        self.leg2_ultrasonic_datasource = None
        self._leg2_adapter().clear_settings()
        self._set_resource_reload_error("leg2_mat", None)
        self._set_resource_warnings("leg2_mat", ())
        self._update_leg2_datasource_controls()
        self._sync_previews(camera_access_hint="auto")
        self._refresh_resources_ui()
        self.statusBar().showMessage("Cleared Leg2 MAT ultrasonic datasource.")

    def _reload_leg2_ultrasonic_datasource_from_session(self) -> None:
        self.leg2_ultrasonic_datasource = None
        mat_path_text = self.session.leg2_ultrasonic_datasource.path
        if not mat_path_text:
            self._update_leg2_datasource_controls()
            return

        mat_path = Path(mat_path_text)
        if not mat_path.exists():
            self._set_resource_reload_error("leg2_mat", f"File not found: {mat_path}")
            self.statusBar().showMessage(f"Leg2 MAT not found and was not loaded: {mat_path}")
            self._update_leg2_datasource_controls()
            self._refresh_resources_ui()
            return

        if not self.load_leg2_mat_from_path(mat_path, show_dialogs=False, mark_dirty=False):
            self._set_resource_reload_error(
                "leg2_mat",
                f"Could not reload Leg2 MAT: {mat_path.name}",
            )
            self._update_leg2_datasource_controls()
            self._refresh_resources_ui()

    def _leg2_signal_kind_changed(self, _index: int) -> None:
        signal_kind = self.leg2_signal_kind_combo.currentData()
        if signal_kind not in ("raw", "filtered"):
            return
        self._mark_session_dirty()
        self.session.leg2_ultrasonic_datasource.signal_kind = signal_kind
        self._sync_previews(camera_access_hint="auto")

    def _update_leg2_datasource_controls(self) -> None:
        self.leg2_signal_kind_combo.setEnabled(self._leg2_adapter().is_loaded())
        self.timeline_view.update()

    def _reload_peak_series_from_session(self) -> None:
        self._peak_series_list = []
        for entry in self.session.peak_series:
            json_path_text = entry.path
            if not json_path_text:
                continue

            json_path = Path(json_path_text)
            if not json_path.exists():
                self._set_resource_reload_error("radar_peak", f"File not found: {json_path}")
                self.statusBar().showMessage(
                    f"Peak-distance JSON not found and was not loaded: {json_path}"
                )
                self._refresh_resources_ui()
                continue

            try:
                datasource, warnings = import_peak_distance_json_for_heatmap(
                    json_path,
                    self.heatmap_source,
                )
            except Exception as exc:
                message = f"Could not reload peak-distance JSON: {exc}"
                self._set_resource_reload_error("radar_peak", message)
                self.statusBar().showMessage(message)
                self._refresh_resources_ui()
                continue

            series = build_imported_peak_series(
                datasource,
                json_path,
                display_name=entry.display_name or json_path.stem,
                existing_series=self._peak_series_list,
                color=entry.color or None,
                visible=entry.visible,
                heatmap_selected=entry.heatmap_selected,
                warnings=tuple(warnings),
            )
            self._peak_series_list.append(series)
            self._set_resource_reload_error("radar_peak", None)
            self.statusBar().showMessage(f"Reloaded peak-distance JSON: {json_path.name}")
        # Restore heatmap-selected series from persisted heatmap_selected flag.
        self._heatmap_peak_selector_id = None
        for s in self._peak_series_list:
            if s.heatmap_selected:
                self._heatmap_peak_selector_id = s.series_id
                break
        self._update_heatmap_peak_selector()
        self._refresh_signal_plot()
        self._refresh_current_heatmap_peak_overlay()
        self._refresh_resources_ui()

    # ------------------------------------------------------------------
    # Multi-peak series methods
    # ------------------------------------------------------------------

    def _generate_peak_series(self) -> None:
        """Open the Generate Peak Series dialog and add a new series."""
        if not self._h5_ready_for_generation():
            return
        heatmap_source = self.heatmap_source
        if heatmap_source is None:
            return
        h5_distance_bin_width_m, _ = self._active_h5_bin_widths()
        dialog = GeneratePeakSeriesDialog(
            self,
            distance_bin_width_m=h5_distance_bin_width_m or 0.0,
        )
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        self.statusBar().showMessage("Generating peak series...")
        threshold_max = getattr(dialog, "threshold_max", DEFAULT_DIST_NORM_THRESHOLD_MAX)
        threshold_min = getattr(dialog, "threshold_min", DEFAULT_DIST_NORM_THRESHOLD_MIN)
        reference_distance_m = getattr(
            dialog,
            "reference_distance_m",
            DEFAULT_DIST_NORM_REFERENCE_DISTANCE_M,
        )
        selection_method = getattr(
            dialog,
            "selection_method",
            PEAK_SELECTION_METHOD_STRONGEST_PEAK,
        )
        bridge_gap_m = getattr(dialog, "bridge_gap_m", 0.0)
        try:
            result = generate_peak_distances_from_heatmap_record(
                heatmap_source.record,
                h5_path=heatmap_source.path,
                subsweep_idx=heatmap_source.subsweep_idx,
                threshold=dialog.threshold,
                peak_extraction_method=dialog.algorithm_id,
                selection_method=selection_method,
                threshold_max=threshold_max,
                threshold_min=threshold_min,
                reference_distance_m=reference_distance_m,
                bridge_gap_m=bridge_gap_m,
            )
        except Exception as exc:
            QtWidgets.QApplication.restoreOverrideCursor()
            QtWidgets.QMessageBox.warning(
                self, "Generation failed", f"Could not generate peak series: {exc}"
            )
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        series = build_generated_peak_series(
            result,
            display_name=dialog.display_name,
            algorithm_id=dialog.algorithm_id,
            threshold=dialog.threshold,
            existing_series=self._peak_series_list,
            threshold_max=threshold_max,
            threshold_min=threshold_min,
            reference_distance_m=reference_distance_m,
            selection_method=selection_method,
            bridge_gap_m=bridge_gap_m,
        )
        self._peak_series_list.append(series)
        self._heatmap_peak_selector_id = series.series_id
        self._refresh_signal_plot()
        self._update_heatmap_peak_selector()
        self._refresh_current_heatmap_peak_overlay()
        self._refresh_resources_ui()
        counts = peak_state_detected_counts(result)
        if counts:
            detected, total = counts
            self.statusBar().showMessage(
                f"Generated peak series '{series.display_name}': {detected}/{total} frames detected."
            )
        else:
            self.statusBar().showMessage(f"Generated peak series '{series.display_name}'.")

    def _import_peak_series(self) -> None:
        """Open a file picker and import one or more peak-distance JSON files as new series.

        Uses the full H5-aware validation path (import_peak_distance_json_for_heatmap)
        to validate frame counts and metadata against the loaded H5 when present.
        """
        filenames, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Import Peak Series",
            self._dialog_start_path("last_peak_json_path"),
            "Peak-distance JSON (*.json);;All files (*)",
        )
        if not filenames:
            return

        existing_names = [s.display_name for s in self._peak_series_list]
        imported_count = 0
        for filename in filenames:
            json_path = Path(filename)
            if json_path.suffix.lower() == ".csv":
                QtWidgets.QMessageBox.warning(
                    self, "Import Peak Series", self._peak_csv_rejection_message()
                )
                continue
            try:
                datasource, warnings = import_peak_distance_json_for_heatmap(
                    json_path, self.heatmap_source
                )
            except ValueError as exc:
                if isinstance(exc, PeakDistanceJsonImportError):
                    message = exc.user_message()
                else:
                    message = str(exc)
                QtWidgets.QMessageBox.warning(self, "Import failed", message)
                continue
            except OSError as exc:
                QtWidgets.QMessageBox.warning(self, "Import failed", str(exc))
                continue

            display_name = default_imported_name(json_path, existing_names)
            existing_names.append(display_name)
            series = build_imported_peak_series(
                datasource,
                json_path,
                display_name=display_name,
                existing_series=self._peak_series_list,
                warnings=tuple(warnings),
            )
            self._peak_series_list.append(series)
            imported_count += 1
            self.settings.setValue("last_peak_json_path", str(json_path))
            if warnings:
                warning_text = "\n".join(f"- {w}" for w in warnings)
                QtWidgets.QMessageBox.warning(
                    self,
                    "Import warnings",
                    f"Imported '{json_path.name}' with warnings:\n{warning_text}",
                )

        if imported_count > 0:
            self._heatmap_peak_selector_id = self._peak_series_list[-1].series_id
            self._refresh_signal_plot()
            self._update_heatmap_peak_selector()
            self._refresh_current_heatmap_peak_overlay()
            self._refresh_resources_ui()
            self.statusBar().showMessage(f"Imported {imported_count} peak series.")
        self._mark_session_dirty()

    def _import_peak_series_from_path(self, json_path: Path, *, mark_dirty: bool = True) -> bool:
        """Programmatic append of a peak series from a path (no dialog).

        Used by startup args and tests. Returns True if the series was appended.
        Uses full H5-aware validation when H5 is loaded.
        """
        if json_path.suffix.lower() == ".csv":
            self.statusBar().showMessage(self._peak_csv_rejection_message())
            return False
        try:
            datasource, warnings = import_peak_distance_json_for_heatmap(
                json_path, self.heatmap_source
            )
        except (ValueError, OSError) as exc:
            status_msg = getattr(exc, "primary_message", str(exc))
            self.statusBar().showMessage(str(status_msg))
            self._set_resource_reload_error("radar_peak", str(status_msg))
            self._refresh_resources_ui()
            return False

        existing_names = [s.display_name for s in self._peak_series_list]
        display_name = default_imported_name(json_path, existing_names)
        series = build_imported_peak_series(
            datasource,
            json_path,
            display_name=display_name,
            existing_series=self._peak_series_list,
            warnings=tuple(warnings),
        )
        self._peak_series_list.append(series)
        self._heatmap_peak_selector_id = series.series_id
        self._set_resource_reload_error("radar_peak", None)
        self._set_resource_warnings("radar_peak", tuple(warnings))
        self._refresh_signal_plot()
        self._update_heatmap_peak_selector()
        self._refresh_current_heatmap_peak_overlay()
        self._refresh_resources_ui()
        if mark_dirty:
            self._mark_session_dirty()
        self.settings.setValue("last_peak_json_path", str(json_path))
        self.statusBar().showMessage(f"Imported peak series: {json_path.name}")
        return True

    def _unload_peak_series(self, series_id: str, *, confirm: bool = True) -> None:
        series = next((s for s in self._peak_series_list if s.series_id == series_id), None)
        if series is None:
            return
        if confirm and series.unsaved:
            confirmed = self._confirm_action_dialog(
                title="Discard unsaved peak series",
                question=f"Discard unsaved peak series '{series.display_name}'?",
                informative="This series has not been saved and will be lost.",
                accept_label="Discard",
            )
            if not confirmed:
                return
        self._peak_series_list = [s for s in self._peak_series_list if s.series_id != series_id]
        if self._heatmap_peak_selector_id == series_id:
            self._heatmap_peak_selector_id = None
        self._refresh_signal_plot()
        self._update_heatmap_peak_selector()
        self._refresh_current_heatmap_peak_overlay()
        self._refresh_resources_ui()
        self._mark_session_dirty()

    def _save_peak_series(self, series_id: str) -> None:
        series = next((s for s in self._peak_series_list if s.series_id == series_id), None)
        if series is None or not series.measurements:
            return
        if series.json_path:
            if series.json_path.exists() and not self._confirm_action_dialog(
                title="Overwrite peak series",
                question=f"Overwrite '{series.json_path.name}'?",
                informative="The existing file will be replaced.",
                accept_label="Overwrite",
            ):
                return
            self._write_peak_series_to_path(series, series.json_path)
        else:
            self._save_peak_series_as(series_id)

    def _save_peak_series_as(self, series_id: str) -> None:
        series = next((s for s in self._peak_series_list if s.series_id == series_id), None)
        if series is None or not series.measurements:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Peak Series", "", "JSON (*.json)"
        )
        if path:
            self._write_peak_series_to_path(series, Path(path))

    def _write_peak_series_to_path(self, series: PeakSeriesResource, output_path: Path) -> None:
        from sparse_iq_peak_distance_core import DetectionExportResult, write_peak_distance_json

        if series.metadata is None:
            return
        result = DetectionExportResult(metadata=series.metadata, measurements=series.measurements)
        try:
            write_peak_distance_json(result, output_path)
        except OSError as exc:
            QtWidgets.QMessageBox.warning(
                self, "Save peak series failed", f"Could not save peak series:\n{exc}"
            )
            return
        series.json_path = output_path
        series.unsaved = False
        self._mark_session_dirty()
        self._refresh_resources_ui()
        self.statusBar().showMessage(
            f"Saved peak series '{series.display_name}': {output_path.name}"
        )

    def _update_heatmap_peak_selector(self) -> None:
        if not hasattr(self, "_heatmap_peak_combo"):
            return
        self._heatmap_peak_combo.blockSignals(True)
        self._heatmap_peak_combo.clear()
        self._heatmap_peak_combo.addItem("None", None)
        for s in self._peak_series_list:
            self._heatmap_peak_combo.addItem(s.display_name, s.series_id)
        idx = self._heatmap_peak_combo.findData(self._heatmap_peak_selector_id)
        self._heatmap_peak_combo.setCurrentIndex(max(0, idx))
        self._heatmap_peak_combo.blockSignals(False)

    def _on_heatmap_peak_combo_changed(self, _index: int) -> None:
        self._heatmap_peak_selector_id = self._heatmap_peak_combo.currentData()
        self._refresh_current_heatmap_peak_overlay()

    def _active_peak_state(self):
        """Return measurements/metadata for the heatmap-selected peak series, or None."""
        return self._peak_adapter().active()

    def _peak_adapter(self) -> PeakSeriesResourceAdapter:
        return PeakSeriesResourceAdapter(
            self._peak_series_list,
            selected_series_id=self._heatmap_peak_selector_id or "",
        )

    def _leg2_adapter(self) -> Leg2ResourceAdapter:
        return Leg2ResourceAdapter(
            self.session.leg2_ultrasonic_datasource,
            self.leg2_ultrasonic_datasource,
        )

    def _resolve_peak_series_target(
        self,
        series_id: str = "",
        *,
        prefer_unsaved: bool = False,
        fallback_last: bool = False,
        fallback_active: bool = True,
    ) -> PeakSeriesResource | None:
        """Resolve a peak-series action target using the Resources row or UI selection."""
        return self._peak_adapter().resolve_target(
            series_id,
            prefer_unsaved=prefer_unsaved,
            fallback_last=fallback_last,
            fallback_active=fallback_active,
        )

    def _has_peaks_in_memory(self) -> bool:
        return self._peak_adapter().has_rows()

    def _any_peaks_unsaved(self) -> bool:
        return self._peak_adapter().any_unsaved()

    def _unload_last_peak_series(self) -> None:
        """Unload action from top-level menu: unload the selected series or the last one."""
        target = self._resolve_peak_series_target(fallback_last=True)
        if target is not None:
            self._unload_peak_series(target.series_id)

    def _peak_overlay_for_frame(
        self, frame_idx: int
    ) -> tuple[float, float, np.ndarray | None] | None:
        """Return (target_distance_m, zero_velocity_m_s, detection_ratio) for the active series.

        Returns None if no series is active or the frame has no detection.
        """
        peak_state = self._active_peak_state()
        if peak_state is None:
            return None
        measurements = active_peak_measurements(peak_state)
        if measurements is None:
            return None
        measurement = next((m for m in measurements if m.frame_index == frame_idx), None)
        if measurement is None or measurement.status != STATUS_DETECTED:
            # Still return detection_ratio even when no detection, so the strip renders.
            if measurement is not None:
                ratio = (
                    measurement.detection_ratio if len(measurement.detection_ratio) > 0 else None
                )
                return (
                    None,  # type: ignore[return-value]
                    active_peak_zero_velocity_m_s(peak_state),
                    ratio,
                )
            return None
        if measurement.target_distance_m is None:
            return None
        ratio = measurement.detection_ratio if len(measurement.detection_ratio) > 0 else None
        return (
            measurement.target_distance_m,
            active_peak_zero_velocity_m_s(peak_state),
            ratio,
        )

    def _annotate_truth_frame_with_peak(
        self,
        truth_frame: np.ndarray,
        frame_idx: int,
    ) -> np.ndarray:
        return truth_frame

    def _update_heatmap_extent_labels(self) -> None:
        if self.heatmap_source is None:
            self._heatmap_distance_header.set_extent(None, None)
            self._heatmap_vel_extent_label.setText("")
            self._heatmap_axes = None
            return
        subsweep = select_subsweep(self.heatmap_source.record, self.heatmap_source.subsweep_idx)
        axes = heatmap_axes(
            self.heatmap_source.record.metadata, self.heatmap_source.record.sensor_config, subsweep
        )
        self._heatmap_axes = axes
        self._heatmap_distance_header.set_extent(
            float(axes.distances_m[0]),
            float(axes.distances_m[-1]),
            finite_axis_bin_width(axes.distances_m),
        )
        v_limit = max(abs(float(axes.velocities_m_s[0])), abs(float(axes.velocities_m_s[-1])))
        self._heatmap_vel_extent_label.setText("Velocity limits: ±{:.3f} m/s".format(v_limit))

    def _update_heatmap_peak_cue(self, frame_idx: int | None) -> None:
        if frame_idx is None or self.heatmap_source is None:
            self._heatmap_distance_header.set_peak_distance(None)
            return
        peak_overlay = self._peak_overlay_for_frame(frame_idx)
        dist = None if peak_overlay is None else peak_overlay[0]
        if dist is None:
            self._heatmap_distance_header.set_peak_distance(None)
        else:
            if self._heatmap_axes is not None:
                d_min = float(self._heatmap_axes.distances_m[0])
                d_max = float(self._heatmap_axes.distances_m[-1])
                if dist < d_min or dist > d_max:
                    self._heatmap_distance_header.set_peak_distance(None)
                    return
            self._heatmap_distance_header.set_peak_distance(dist)

    def _current_heatmap_frame_index(self) -> int | None:
        if self.heatmap_source is None:
            return None
        current_time_s = self.session.timeline.current_time_s
        if current_time_s < 0.0 or current_time_s > self.session.heatmap_track.duration_s:
            return None
        frame_idx, _truth_frame = self.heatmap_source.frame_at_seconds(current_time_s)
        return frame_idx

    def _refresh_current_heatmap_peak_overlay(self, frame_idx: int | None = None) -> None:
        if frame_idx is None:
            frame_idx = self._current_heatmap_frame_index()
        if frame_idx is None:
            self._update_heatmap_peak_cue(None)
            self._detection_strip.set_detection_ratio(None)
            if self._hover_last_pos is not None:
                self._refresh_hover_tooltip()
            return

        self._update_heatmap_peak_cue(frame_idx)
        if self._hover_last_pos is not None:
            self._refresh_hover_tooltip()
        peak_overlay = self._peak_overlay_for_frame(frame_idx)
        self._detection_strip.set_detection_ratio(
            None if peak_overlay is None else peak_overlay[2]
        )

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if obj is self.truth_view:
            etype = event.type()
            if etype == QtCore.QEvent.Type.MouseMove:
                self._hover_last_pos = event.position().toPoint()
                self._refresh_hover_tooltip()
                return False
            if etype == QtCore.QEvent.Type.Leave:
                self._hover_last_pos = None
                QtWidgets.QToolTip.hideText()
                return False
        return super().eventFilter(obj, event)

    def _refresh_hover_tooltip(self) -> None:
        if (
            self._hover_last_pos is None
            or self._heatmap_axes is None
            or self._hover_dvm_cache is None
        ):
            QtWidgets.QToolTip.hideText()
            return
        rect = self.truth_view.rendered_image_rect()
        pos = self._hover_last_pos
        if not rect.contains(pos):
            QtWidgets.QToolTip.hideText()
            return
        axes = self._heatmap_axes
        x_frac = (pos.x() - rect.left()) / max(1, rect.width())
        y_frac = (pos.y() - rect.top()) / max(1, rect.height())
        dist_idx = axis_center_index_at_fraction(axes.distances_m, x_frac)
        vel_idx = axis_center_index_at_fraction(axes.velocities_m_s, y_frac)
        dist_val = float(axes.distances_m[dist_idx])
        vel_val = float(axes.velocities_m_s[vel_idx])
        dvm = self._hover_dvm_cache[1]
        magnitude = int(round(float(dvm[vel_idx, dist_idx])))
        text = "Distance: {:.3f} m\nVelocity: {:.3f} m/s\nMagnitude: {}".format(
            dist_val, vel_val, magnitude
        )

        # Append detection ratio from the active series if one is selected.
        frame_idx = self._hover_dvm_cache[0]
        active_series = self._active_peak_state()
        if active_series is not None:
            measurement = next(
                (m for m in active_series.measurements if m.frame_index == frame_idx), None
            )
            if (
                measurement is not None
                and measurement.detection_ratio is not None
                and len(measurement.detection_ratio) > dist_idx
            ):
                ratio_val = float(measurement.detection_ratio[dist_idx])
                text += "\nDetection ratio: {:.2f}".format(ratio_val)

        global_pos = self.truth_view.mapToGlobal(pos)
        QtWidgets.QToolTip.showText(global_pos, text, self.truth_view)

    def _save_session(self) -> None:
        if self._session_lifecycle.current_path is None:
            self._save_session_as()
            return
        self._write_session_to_path(self._session_lifecycle.current_path)

    def _save_session_as(self) -> None:
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save session as",
            self._dialog_start_path("last_session_path"),
            "JSON files (*.json);;All files (*)",
        )
        if not filename:
            return
        self._write_session_to_path(Path(filename))

    def _write_session_to_path(self, session_path: Path) -> bool:
        try:
            self._session_lifecycle.prepare_session_for_save(
                self.session,
                peak_entries=self._peak_adapter().saved_session_entries(),
            )
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Cannot save session", str(exc))
            return False

        if self._any_peaks_unsaved():
            reply = QtWidgets.QMessageBox.question(
                self,
                "Save session with unsaved peaks?",
                (
                    "The alignment session does not include generated peak-distance data.\n\n"
                    "To preserve peaks, save them from the Resources window (Save Peaks) before saving the session.\n\n"
                    "Save session anyway?"
                ),
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.Yes,
            )
            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                return False

        self._session_lifecycle.save_to_path(self.session, session_path)
        self.settings.setValue("last_session_path", str(session_path))
        self._clear_session_dirty()
        self._refresh_session_title()
        self._refresh_resources_ui()
        self._record_recent_session(session_path)
        self.statusBar().showMessage(f"Saved session: {session_path}")
        return True

    def _save_session_for_prompt(self) -> bool:
        if self._session_lifecycle.current_path is None:
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Save session as",
                self._dialog_start_path("last_session_path"),
                "JSON files (*.json);;All files (*)",
            )
            if not filename:
                return False
            return self._write_session_to_path(Path(filename))
        return self._write_session_to_path(self._session_lifecycle.current_path)

    def _load_session(self) -> None:
        if not self._handle_session_transition_guard("open"):
            return

        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open session",
            self._dialog_start_path("last_session_path"),
            "JSON files (*.json);;All files (*)",
        )
        if filename:
            self._open_session(
                LoadSessionPlan(session_path=Path(filename), prompt_for_unsaved=False)
            )

    def _loaded_h5_identity(self) -> H5SlotIdentity | None:
        """Return identity of the currently loaded H5 source, or None."""
        if self.heatmap_source is None:
            return None
        if not all(
            hasattr(self.heatmap_source, attr) for attr in ("path", "record", "subsweep_idx")
        ):
            return None
        if not all(
            hasattr(self.heatmap_source.record, attr)
            for attr in ("session_idx", "group_idx", "entry_idx")
        ):
            return None
        return H5SlotIdentity(
            path=str(self.heatmap_source.path),
            session_idx=self.heatmap_source.record.session_idx,
            group_idx=self.heatmap_source.record.group_idx,
            entry_idx=self.heatmap_source.record.entry_idx,
            subsweep_idx=self.heatmap_source.subsweep_idx,
        )

    def _h5_job_active(self) -> bool:
        return self._resource_job_manager.board().radar_h5.phase not in (
            "idle",
            "failed",
            "superseded",
        )

    def _h5_ready_for_generation(self) -> bool:
        if self.heatmap_source is None or self._h5_job_active():
            return False
        return self._loaded_h5_identity() == desired_h5_identity(self.session)

    def _reconcile_session_load(
        self,
        desired_session: AlignmentSession,
        prior_session: AlignmentSession,
    ) -> None:
        """Reconcile active workbench resources against the desired session snapshot.

        Per-slot registry approach: new resource types must add an entry here.
        See OpenSpec change: session-load-responsiveness.
        """
        # Reset on every reconcile so stale True from a previous session load cannot
        # survive into a later unrelated H5 job completion.
        self._pending_peak_session_reload = False

        # Build a plain-value snapshot of loaded/inflight state for the coordinator.
        if self.camera_source is not None:
            camera_loaded_path = prior_session.camera_track.path or None
        else:
            camera_loaded_path = None
        camera_slot = self._resource_job_manager.board().camera
        camera_inflight_path = (
            str(camera_slot.target_path)
            if camera_slot.target_path is not None
            and camera_slot.phase not in ("idle", "failed", "superseded")
            else None
        )
        loaded = LoadedResourceState(
            camera_loaded_path=camera_loaded_path,
            camera_inflight_path=camera_inflight_path,
            h5_loaded_identity=self._loaded_h5_identity(),
            h5_inflight_identity=self._inflight_h5_identity,
            loaded_peak_paths=frozenset(
                str(s.json_path) for s in self._peak_series_list if s.json_path is not None
            ),
            leg2_loaded_path=(
                prior_session.leg2_ultrasonic_datasource.path
                if self.leg2_ultrasonic_datasource is not None
                and prior_session.leg2_ultrasonic_datasource.path
                else None
            ),
        )
        plan = plan_session_reconcile(desired_session, loaded)

        # Execute per-slot actions
        if plan.camera_action == "unload":
            self.unload_camera_video(mark_dirty=False)
        elif plan.camera_action == "load":
            camera_path = Path(desired_session.camera_track.path)
            if camera_path.exists():
                self.load_camera_from_path(camera_path, mark_dirty=False)
            else:
                self._set_resource_reload_error("camera", f"File not found: {camera_path}")
        # camera "keep" — nothing to do

        if plan.h5_action == "unload":
            self.unload_h5_recording(mark_dirty=False)
        elif plan.h5_action == "load":
            h5_path = Path(desired_session.heatmap_track.path)
            if h5_path.exists():
                self.load_h5_from_path(h5_path, mark_dirty=False)
            else:
                self._set_resource_reload_error("radar_h5", f"File not found: {h5_path}")
        # h5 "keep" — nothing to do

        # Per-series peak reconciliation: unload series whose paths are no longer desired,
        # load series that are desired but not yet loaded, and drop unsaved generated
        # series that have no saved path (they cannot be represented in the session).
        # Always filter: drop pathless (unsaved generated) rows and any stale path rows.
        self._peak_series_list = [
            s
            for s in self._peak_series_list
            if s.json_path is not None and str(s.json_path) not in plan.peak_paths_to_unload
        ]
        if self._heatmap_peak_selector_id not in {s.series_id for s in self._peak_series_list}:
            self._heatmap_peak_selector_id = None
        if plan.peak_paths_to_load:
            if plan.h5_action != "load":
                self._reload_peak_series_from_session()
            else:
                # Defer peak reload until the in-flight H5 job completes.
                self._pending_peak_session_reload = True

        if plan.leg2_action == "unload":
            if self.leg2_ultrasonic_datasource is not None:
                self._clear_leg2_ultrasonic_datasource(mark_dirty=False)
        elif plan.leg2_action == "load":
            self._reload_leg2_ultrasonic_datasource_from_session()
        # leg2 "keep" — nothing to do

    def load_session_from_path(self, session_path: Path) -> None:
        with self._session_dirty_guard():
            desired_session = self._session_lifecycle.load_from_path(session_path)
            prior_session = self.session

            # Assign self.session BEFORE reconcile so load_h5_from_path reads correct indices.
            self.session = copy.deepcopy(desired_session)
            self._resource_reload_errors.clear()
            self._resource_load_warnings.clear()

            self._reconcile_session_load(desired_session, prior_session)

            # Restore session after reconcile: unload/clear helpers may mutate non-resource fields
            # (e.g. peak visibility). Reassign desired_session to guarantee populate reads it.
            self.session = desired_session

            # Populate controls after reconcile (jobs may still be in-flight).
            self._populate_controls_from_session()
            if self.camera_source is not None:
                # Force a clean seek to the session's starting position before the full sync.
                # "random" is correct here: the prior sequential-decode position is no longer
                # valid after loading a new session, so we must not assume continuity.
                self._load_current_camera_frame(access_hint="random")
                self._refresh_camera_view_corners()
                self.camera_view.set_export_overlay(self.session.export_overlay)
            self._update_controls_enabled_state()
            self._sync_previews(
                camera_access_hint="auto",
                recompute_timeline_range=True,
            )
            self.settings.setValue("last_session_path", str(session_path))
            if self.session.camera_track.path:
                self.settings.setValue("last_camera_path", self.session.camera_track.path)
            if self.session.heatmap_track.path:
                self.settings.setValue("last_h5_path", self.session.heatmap_track.path)
            self._refresh_resources_ui()
            self._record_recent_session(session_path)
            self.statusBar().showMessage(f"Loaded session: {session_path}")
        self._clear_session_dirty()
        self._refresh_session_title()

    def _snapshot_active_camera(self) -> _CameraResourceBackup:
        if self.camera_source is None:
            raise RuntimeError("Cannot snapshot camera resource when no camera is loaded.")
        return _CameraResourceBackup(
            camera_source=self.camera_source,
            reference_width=self._camera_reference_width,
            reference_height=self._camera_reference_height,
            camera_track=CameraTrack(
                path=self.session.camera_track.path,
                fps=self.session.camera_track.fps,
                duration_s=self.session.camera_track.duration_s,
                frame_count=self.session.camera_track.frame_count,
            ),
            current_camera_frame=(
                None if self.current_camera_frame is None else self.current_camera_frame.copy()
            ),
            viewport_corners=[list(point) for point in self.session.viewport.corners],
            export_overlay=ExportOverlaySettings(
                visible=self.session.export_overlay.visible,
                preview_enabled=self.session.export_overlay.preview_enabled,
                x=self.session.export_overlay.x,
                y=self.session.export_overlay.y,
                width=self.session.export_overlay.width,
                height=self.session.export_overlay.height,
            ),
        )

    def _snapshot_active_h5(self) -> _H5ResourceBackup:
        if self.heatmap_source is None:
            raise RuntimeError("Cannot snapshot H5 resource when no recording is loaded.")
        return _H5ResourceBackup(
            heatmap_source=self.heatmap_source,
            heatmap_track=HeatmapTrack(
                path=self.session.heatmap_track.path,
                session_idx=self.session.heatmap_track.session_idx,
                group_idx=self.session.heatmap_track.group_idx,
                entry_idx=self.session.heatmap_track.entry_idx,
                subsweep_idx=self.session.heatmap_track.subsweep_idx,
                duration_s=self.session.heatmap_track.duration_s,
                fps=self.session.heatmap_track.fps,
            ),
            viewport_output_width=self.session.viewport.output_width,
            viewport_output_height=self.session.viewport.output_height,
        )

    def _apply_camera_job_result(self, result: CameraResourceJobResult) -> None:
        if self._camera_replacement_backup is not None:
            self._camera_replacement_backup.camera_source.close()
        elif self.camera_source is not None:
            self.camera_source.close()
        self.camera_source = CameraVideoSource(result.proxy_result.display_path)
        self._camera_reference_width = result.proxy_result.source_probe.width
        self._camera_reference_height = result.proxy_result.source_probe.height
        previous_size = (0, 0)
        previous_corners: list[list[float]] | None = None
        if self._camera_replacement_backup is not None:
            previous_size = (
                self._camera_replacement_backup.reference_width,
                self._camera_replacement_backup.reference_height,
            )
            previous_corners = self._camera_replacement_backup.viewport_corners
        self.session.camera_track = result.camera_track
        resolved_corners = resolve_replacement_viewport_corners(
            existing_corners=previous_corners,
            previous_native_size=previous_size,
            replacement_native_size=(
                self._camera_reference_width,
                self._camera_reference_height,
            ),
        )
        if resolved_corners is not None:
            self.session.viewport.corners = resolved_corners
        elif (
            replacement_viewport_needs_default_reset(
                previous_corners=previous_corners,
                previous_native_size=previous_size,
                replacement_native_size=(
                    self._camera_reference_width,
                    self._camera_reference_height,
                ),
            )
            or not self.session.viewport.corners
        ):
            self._initialize_default_viewport_corners_native()
        self._initialize_default_export_overlay_if_needed()
        self._load_current_camera_frame(access_hint="random")
        if self._native_viewport_corners() is None:
            self._initialize_default_viewport_corners_native()
        else:
            self._refresh_camera_view_corners()
        self.camera_view.set_export_overlay(self.session.export_overlay)
        self.settings.setValue("last_camera_path", str(result.source_path))
        self._camera_replacement_backup = None
        if result.proxy_result.state == "proxy_built":
            message = f"Loaded camera video with new preview proxy: {result.source_path.name}"
        elif result.proxy_result.state == "proxy_reused":
            message = f"Loaded camera video via cached preview proxy: {result.source_path.name}"
        else:
            message = f"Loaded camera video: {result.source_path.name}"
        self.statusBar().showMessage(message)

    def _apply_h5_job_result(self, payload: LoadedH5ResourcePayload) -> None:
        previous_path = ""
        if self._h5_replacement_backup is not None:
            previous_path = self._h5_replacement_backup.heatmap_track.path
            self._h5_replacement_backup.heatmap_source.close()
        elif self.heatmap_source is not None:
            self.heatmap_source.close()
        self.heatmap_source = build_h5_truth_source_from_payload(payload)
        self.session.heatmap_track = payload.metadata
        self.session.viewport.output_width = payload.first_frame_shape[1]
        self.session.viewport.output_height = payload.first_frame_shape[0]
        self._rebuild_overlay_plot_renderer()
        self.settings.setValue("last_h5_path", str(payload.path))
        if self._pending_peak_session_reload:
            # Deferred by session-load reconcile: peak paths to load were waiting on this H5 job.
            self._pending_peak_session_reload = False
            self._reload_peak_series_from_session()
        elif not previous_path or previous_path == str(payload.path):
            # Same H5 identity (initial load or keep): restore persisted peak series only
            # when there are no live series yet; preserves unsaved generated rows.
            if not self._peak_series_list:
                self._reload_peak_series_from_session()
        # Different H5 without a pending session reload: preserve existing peak series as
        # optional signal resources. They remain valid signal data and the user can unload
        # them individually.
        self._h5_replacement_backup = None
        self._inflight_h5_identity = None
        self._update_heatmap_extent_labels()
        self.statusBar().showMessage(f"Loaded H5 recording: {payload.path.name}")

    def _handle_resource_job_state_changed(self) -> None:
        for kind in ("camera", "radar_h5"):
            slot = self._resource_job_manager.board().slot(kind)
            result = self._resource_job_manager.take_pending_result(kind, slot.generation)
            if result is not None:
                if kind == "camera":
                    self._apply_camera_job_result(result)
                else:
                    self._apply_h5_job_result(result)
                self._set_resource_reload_error(kind, None)
                self._update_controls_enabled_state()
                self._sync_previews(camera_access_hint="auto")
            elif slot.phase == "failed":
                if kind == "camera":
                    self._discard_camera_replacement_backup()
                else:
                    self._discard_h5_replacement_backup()
                self._set_resource_reload_error(kind, slot.message)
            elif slot.phase == "idle":
                if kind == "camera" and self._camera_replacement_backup is not None:
                    self._discard_camera_replacement_backup()
                elif kind == "radar_h5" and self._h5_replacement_backup is not None:
                    self._discard_h5_replacement_backup()
        self._update_resource_loading_overlays()
        self._refresh_resources_ui()

    def _resource_loading_overlay_message(self, slot: ResourceJobSlotState) -> str:
        if slot.message:
            return slot.message
        target = resource_job_target_filename(slot.target_path)
        if slot.phase == "waiting":
            return f"Waiting for {target}..."
        if slot.phase == "building":
            return f"Building preview proxy for {target}..."
        return f"Loading {target}..."

    _ACTIVE_RESOURCE_JOB_PHASES = ("pending", "loading", "building", "waiting", "cancelling")

    def _resource_job_slot_is_active(self, slot: ResourceJobSlotState) -> bool:
        return slot.phase in self._ACTIVE_RESOURCE_JOB_PHASES

    def _update_resource_loading_overlays(self) -> None:
        camera_slot = self._resource_job_manager.board().camera
        if self._resource_job_slot_is_active(camera_slot):
            self.camera_view.set_loading_overlay(
                True,
                self._resource_loading_overlay_message(camera_slot),
                dim_content=self.camera_source is not None,
            )
        else:
            self.camera_view.set_loading_overlay(False)

        h5_slot = self._resource_job_manager.board().radar_h5
        if self._resource_job_slot_is_active(h5_slot):
            self.truth_view.set_loading_overlay(
                True,
                self._resource_loading_overlay_message(h5_slot),
                dim_content=self.heatmap_source is not None,
            )
        else:
            self.truth_view.set_loading_overlay(False)

        camera_active = self._resource_job_slot_is_active(camera_slot)
        h5_active = self._resource_job_slot_is_active(h5_slot)
        if camera_active or h5_active:
            overlay_slot = camera_slot if camera_active else h5_slot
            self.viewport_view.set_loading_overlay(
                True,
                self._resource_loading_overlay_message(overlay_slot),
                dim_content=(
                    self.viewport_view._pixmap is not None
                    or self.camera_source is not None
                    or self.heatmap_source is not None
                ),
            )
        else:
            self.viewport_view.set_loading_overlay(False)

    def _resource_job_presentations(self) -> tuple[ResourceJobPresentation, ...]:
        presentations: list[ResourceJobPresentation] = []
        for snapshot in self._resource_job_manager.snapshots():
            if snapshot.phase == "idle":
                continue
            presentations.append(
                ResourceJobPresentation(
                    kind=snapshot.kind,
                    phase=snapshot.phase,
                    target_filename=resource_job_target_filename(snapshot.target_path),
                    detail=snapshot.message,
                    cancellable=snapshot.cancellable,
                )
            )
        return tuple(presentations)

    def _populate_controls_from_session(self) -> None:
        with self._session_dirty_guard():
            self._populate_controls_from_session_impl()

    def _populate_controls_from_session_impl(self) -> None:
        self.offset_spin.blockSignals(True)
        self.offset_spin.setValue(self.session.timeline.offset_s)
        self.offset_spin.blockSignals(False)
        self.color_min_spin.blockSignals(True)
        self.color_max_spin.blockSignals(True)
        self.viewport_enhance_checkbox.blockSignals(True)
        self.viewport_map_to_viridis_checkbox.blockSignals(True)
        self.viewport_gamma_spin.blockSignals(True)
        self.color_min_spin.setValue(self.session.render.color_min)
        self.color_max_spin.setValue(self.session.render.color_max or 0.0)
        self.viewport_enhance_checkbox.setChecked(self.session.viewport_visibility.enabled)
        self.viewport_map_to_viridis_checkbox.setChecked(
            self.session.viewport_visibility.map_to_viridis
        )
        self.viewport_range_slider.set_values(
            self.session.viewport_visibility.low,
            self.session.viewport_visibility.high,
        )
        self.viewport_gamma_spin.setValue(self.session.viewport_visibility.gamma)
        self._update_viewport_visibility_labels()
        self.color_min_spin.blockSignals(False)
        self.color_max_spin.blockSignals(False)
        self.viewport_enhance_checkbox.blockSignals(False)
        self.viewport_map_to_viridis_checkbox.blockSignals(False)
        self.viewport_gamma_spin.blockSignals(False)
        leg2_kind = self.session.leg2_ultrasonic_datasource.signal_kind
        leg2_kind_index = self.leg2_signal_kind_combo.findData(leg2_kind)
        if leg2_kind_index >= 0:
            self.leg2_signal_kind_combo.setCurrentIndex(leg2_kind_index)
        self._update_leg2_datasource_controls()
        self._update_viewport_visibility_controls_enabled()
        self.signal_plot.set_view_settings(self._signal_plot_view_settings_copy())

    def _signal_plot_view_settings_copy(self) -> SignalPlotViewSettings:
        view = self.session.signal_plot_view
        return SignalPlotViewSettings(
            x_range_mode="auto",
            y_range_mode=view.y_range_mode,
            manual_x_range=None,
            manual_y_range=view.manual_y_range,
        )

    def _signal_plot_view_settings_changed(self) -> None:
        self.session.signal_plot_view = self._signal_plot_view_settings_copy_from_plot()
        self._mark_session_dirty()

    def _signal_plot_view_settings_copy_from_plot(self) -> SignalPlotViewSettings:
        view = self.signal_plot.view_settings()
        return SignalPlotViewSettings(
            x_range_mode="auto",
            y_range_mode=view.y_range_mode,
            manual_x_range=None,
            manual_y_range=view.manual_y_range,
        )

    def _viewport_visibility_changed(self) -> None:
        self._mark_session_dirty()
        self.session.viewport_visibility.enabled = self.viewport_enhance_checkbox.isChecked()
        self.session.viewport_visibility.map_to_viridis = (
            self.viewport_map_to_viridis_checkbox.isChecked()
        )
        self.session.viewport_visibility.gamma = self.viewport_gamma_spin.value()
        self._update_viewport_visibility_controls_enabled()
        self._sync_previews(
            camera_access_hint="auto",
            invalidate_source_resolution=False,
        )

    def _viewport_visibility_range_changed(self, low: float, high: float) -> None:
        self._mark_session_dirty()
        self.session.viewport_visibility.low = low
        self.session.viewport_visibility.high = high
        self._update_viewport_visibility_labels()
        self._sync_previews(
            camera_access_hint="auto",
            invalidate_source_resolution=False,
        )

    def _update_viewport_visibility_labels(self) -> None:
        self.viewport_low_label.setText(f"Low {self.session.viewport_visibility.low:.2f}")
        self.viewport_high_label.setText(f"High {self.session.viewport_visibility.high:.2f}")

    def _update_viewport_visibility_controls_enabled(self) -> None:
        enabled = (
            self.camera_source is not None
            and self.heatmap_source is not None
            and self.viewport_enhance_checkbox.isChecked()
        )
        has_sources = self.camera_source is not None and self.heatmap_source is not None
        self.viewport_enhance_checkbox.setEnabled(has_sources)
        self.viewport_range_slider.setEnabled(enabled)
        self.viewport_map_to_viridis_checkbox.setEnabled(enabled)
        self.viewport_gamma_spin.setEnabled(enabled)
        self.viewport_low_label.setEnabled(enabled)
        self.viewport_high_label.setEnabled(enabled)

    def _offset_changed(self, value: float) -> None:
        self._mark_session_dirty()
        self.session.timeline.offset_s = value
        self._sync_previews(camera_access_hint="auto")

    def _nudge_offset(self, delta_s: float) -> None:
        self.offset_spin.setValue(self.offset_spin.value() + delta_s)

    def _reanchor_playback_clock(self) -> None:
        if self.play_timer.isActive():
            self._playback_started_at_s = time.perf_counter()
            self._playback_started_video_time_s = self.session.timeline.current_time_s

    def _stop_playback(self) -> None:
        self._set_playback_active(False)

    def _slider_to_time(self, slider_value: int) -> None:
        range_start_s, range_end_s = self.timeline_range_model.visible_range_s()
        span_s = range_end_s - range_start_s
        self.session.timeline.current_time_s = (
            range_start_s if span_s <= 0 else range_start_s + span_s * slider_value / 10000.0
        )
        self._reanchor_playback_clock()
        self._sync_previews_preserving_timeline_range(
            camera_access_hint="scrub",
            refresh_signal_data=False,
        )

    def _timeline_playhead_changed(self, time_s: float) -> None:
        self.session.timeline.current_time_s = time_s
        self._reanchor_playback_clock()
        self._sync_previews_preserving_timeline_range(
            camera_access_hint="scrub",
            refresh_signal_data=False,
        )

    def _signal_playhead_scrubbed(self, time_s: float) -> None:
        self.session.timeline.current_time_s = time_s
        self._reanchor_playback_clock()
        self._sync_previews_preserving_timeline_range(
            camera_access_hint="scrub",
            refresh_signal_data=False,
        )

    def _timeline_camera_offset_changed(self, offset_s: float) -> None:
        self.offset_spin.setValue(offset_s)

    def _timeline_leg2_offset_changed(self, offset_s: float) -> None:
        self._mark_session_dirty()
        self.session.leg2_ultrasonic_datasource.offset_s = offset_s
        self._sync_previews(camera_access_hint="auto")

    def _timeline_h5_alignment_drag_changed(
        self,
        range_start_s: float,
        range_end_s: float,
        current_time_s: float,
        camera_offset_s: float,
        leg2_offset_s: float,
    ) -> None:
        self.session.timeline.current_time_s = current_time_s
        self.session.timeline.offset_s = camera_offset_s
        self.offset_spin.blockSignals(True)
        self.offset_spin.setValue(camera_offset_s)
        self.offset_spin.blockSignals(False)
        self.session.leg2_ultrasonic_datasource.offset_s = leg2_offset_s
        self._sync_timeline_h5_drag_preview(
            range_start_s=range_start_s,
            range_end_s=range_end_s,
        )

    def _timeline_h5_alignment_drag_finished(self) -> None:
        self._mark_session_dirty()
        range_start_s, range_end_s = self.timeline_range_model.visible_range_s()
        self._sync_previews(
            camera_access_hint="auto",
            timeline_visible_range_s=(range_start_s, range_end_s),
        )

    def _sync_timeline_h5_drag_preview(
        self,
        *,
        range_start_s: float,
        range_end_s: float,
    ) -> None:
        leg2_duration_s = (
            self.leg2_ultrasonic_datasource.duration_s
            if self.leg2_ultrasonic_datasource is not None
            else 0.0
        )
        self.timeline_range_model.set_track_state(
            camera_duration_s=self.session.camera_track.duration_s,
            heatmap_duration_s=self.session.heatmap_track.duration_s,
            camera_offset_s=self.session.timeline.offset_s,
            leg2_duration_s=leg2_duration_s,
            leg2_offset_s=self.session.leg2_ultrasonic_datasource.offset_s,
        )
        self.timeline_range_model.set_visible_range(range_start_s, range_end_s)
        self._set_slider_from_current_time()
        self._set_timeline_view_state()
        self._refresh_signal_plot()
        self.current_time_label.setText(
            f"t = {self.session.timeline.current_time_s:.3f} s | offset = {self.session.timeline.offset_s:.3f} s"
        )

    def _toggle_playback(self) -> None:
        self._set_playback_active(not self.play_timer.isActive())

    def _advance_playback(self) -> None:
        if self._max_duration_s() <= 0:
            return
        _, range_end_s = self._timeline_bounds_s()

        if self._playback_started_at_s is None:
            self._playback_started_at_s = time.perf_counter()
            self._playback_started_video_time_s = self.session.timeline.current_time_s

        elapsed_s = max(0.0, time.perf_counter() - self._playback_started_at_s)
        next_time = min(self._playback_started_video_time_s + elapsed_s, range_end_s)
        self.session.timeline.current_time_s = next_time
        self._set_slider_from_current_time()
        self._sync_previews_preserving_timeline_range(
            camera_access_hint="playback",
            refresh_signal_data=False,
        )
        if math.isclose(next_time, range_end_s) or next_time >= range_end_s:
            self._set_playback_active(False)

    def _render_settings_changed(self) -> None:
        self._mark_session_dirty()
        self.session.render.color_min = self.color_min_spin.value()
        self.session.render.color_max = self.color_max_spin.value()
        if self.heatmap_source is not None:
            self.heatmap_source.update_render_settings(
                color_min=self.session.render.color_min,
                color_max=self.session.render.color_max,
                fixed_levels=True,
            )
            self._rebuild_overlay_plot_renderer()
        self._sync_previews(camera_access_hint="auto")

    def _corners_changed(self, corners: list) -> None:
        self._mark_session_dirty()
        native_corners = self._display_corners_to_native(np.asarray(corners, dtype=np.float32))
        self.session.viewport.corners = native_corners.tolist()
        self._sync_previews(camera_access_hint="auto")

    def _set_viewport_corners(self, corners: np.ndarray) -> None:
        self.session.viewport.corners = corners.tolist()
        self._refresh_camera_view_corners()
        self._sync_previews(camera_access_hint="auto")

    def _export_overlay_changed(self, x: float, y: float, width: float, height: float) -> None:
        self._mark_session_dirty()
        self.session.export_overlay.x = x
        self.session.export_overlay.y = y
        self.session.export_overlay.width = width
        self.session.export_overlay.height = height

    def _set_export_overlay_visible(self, visible: bool) -> None:
        self._mark_session_dirty()
        self.session.export_overlay.visible = visible
        self.camera_view.set_export_overlay(self.session.export_overlay)
        self._sync_previews(camera_access_hint="auto")

    def _set_export_overlay_preview_enabled(self, enabled: bool) -> None:
        self._mark_session_dirty()
        self.session.export_overlay.preview_enabled = enabled
        self.camera_view.set_export_overlay(self.session.export_overlay)
        self._sync_previews(camera_access_hint="auto")

    def _set_export_overlay_drag_active(self, active: bool) -> None:
        self._freeze_export_overlay_preview = active
        if not active:
            self._sync_previews(camera_access_hint="auto")

    def _reset_export_overlay(self) -> None:
        self._mark_session_dirty()
        self._initialize_default_export_overlay(force=True)
        self.camera_view.set_export_overlay(self.session.export_overlay)
        self._sync_previews(camera_access_hint="auto")

    def _load_current_camera_frame(self, *, access_hint: str = "auto") -> None:
        if self.camera_source is None:
            self.current_camera_frame = None
            self.camera_view.set_frame(None)
            return
        camera_time_s = self.session.timeline.current_time_s + self.session.timeline.offset_s
        if camera_time_s < 0.0 or camera_time_s > self.session.camera_track.duration_s:
            self.current_camera_frame = None
            self.camera_view.set_frame(None)
            return
        _, frame = self.camera_source.frame_at_seconds(
            camera_time_s,
            access_hint=access_hint,
        )
        self.current_camera_frame = frame
        self.camera_view.set_frame(frame)

    def _invalidate_source_resolution_viewport(self) -> None:
        self._source_resolution_request_token += 1
        self._source_resolution_viewport_frame = None
        self._pending_source_resolution_request = None
        self.viewport_source_resolution_timer.stop()

    def _source_resolution_request_payload(
        self,
        *,
        viewport_size: tuple[int, int],
    ) -> dict[str, object] | None:
        native_corners = self._native_viewport_corners()
        if self.camera_source is None or native_corners is None:
            return None
        if self.play_timer.isActive():
            return None
        width, height = viewport_size
        if width <= 0 or height <= 0:
            return None
        camera_time_s = self.session.timeline.current_time_s + self.session.timeline.offset_s
        if camera_time_s < 0.0 or camera_time_s > self.session.camera_track.duration_s:
            return None
        return {
            "token": self._source_resolution_request_token,
            "camera_path": self.session.camera_track.path,
            "camera_time_s": camera_time_s,
            "corners": native_corners.tolist(),
            "output_size": viewport_size,
        }

    def _schedule_source_resolution_viewport_refresh(
        self,
        *,
        viewport_size: tuple[int, int],
    ) -> None:
        request = self._source_resolution_request_payload(viewport_size=viewport_size)
        if request is None:
            self.viewport_source_resolution_timer.stop()
            self._pending_source_resolution_request = None
            return
        self._pending_source_resolution_request = request
        if not self.play_timer.isActive():
            self.viewport_source_resolution_timer.start()

    def _start_debounced_source_resolution_viewport(self) -> None:
        request = self._pending_source_resolution_request
        if request is None:
            return
        if self._source_resolution_worker_busy:
            return
        self._pending_source_resolution_request = None
        self._source_resolution_worker_busy = True
        self.source_resolution_viewport_render_requested.emit(request)

    def _handle_source_resolution_viewport_result(self, result: object) -> None:
        self._source_resolution_worker_busy = False
        payload = dict(result) if isinstance(result, dict) else {}
        if payload.get("token") == self._source_resolution_request_token:
            frame = payload.get("frame")
            self._source_resolution_viewport_frame = (
                frame.copy() if isinstance(frame, np.ndarray) else None
            )
            if self._source_resolution_viewport_frame is not None:
                self._sync_previews_preserving_timeline_range(
                    camera_access_hint="auto",
                    invalidate_source_resolution=False,
                    refresh_signal_data=False,
                )

        if self._pending_source_resolution_request is not None and not self.play_timer.isActive():
            self._start_debounced_source_resolution_viewport()

    def _set_playback_active(self, active: bool, *, refresh_viewport: bool = True) -> None:
        if active:
            self._playback_started_at_s = time.perf_counter()
            self._playback_started_video_time_s = self.session.timeline.current_time_s
            self.play_timer.start(self.play_timer_interval_ms)
            self.play_button.setText("Pause")
            if refresh_viewport:
                self._sync_previews_preserving_timeline_range(
                    camera_access_hint="playback",
                    refresh_signal_data=False,
                )
            return

        was_active = self.play_timer.isActive()
        self.play_timer.stop()
        self._playback_started_at_s = None
        self.play_button.setText("Play")
        if refresh_viewport and was_active:
            self._sync_previews_preserving_timeline_range(
                camera_access_hint="auto",
                refresh_signal_data=False,
            )

    def _set_slider_from_current_time(self) -> None:
        range_start_s, range_end_s = self.timeline_range_model.visible_range_s()
        span_s = range_end_s - range_start_s
        self.current_time_slider.blockSignals(True)
        value = (
            0
            if span_s <= 0
            else int(
                round(10000 * (self.session.timeline.current_time_s - range_start_s) / span_s)
            )
        )
        self.current_time_slider.setValue(int(np.clip(value, 0, 10000)))
        self.current_time_slider.blockSignals(False)

    def _update_timeline_range_from_session(self, *, recompute: bool) -> None:
        leg2_duration_s = (
            self.leg2_ultrasonic_datasource.duration_s
            if self.leg2_ultrasonic_datasource is not None
            else 0.0
        )
        self.timeline_range_model.set_track_state(
            camera_duration_s=self.session.camera_track.duration_s,
            heatmap_duration_s=self.session.heatmap_track.duration_s,
            camera_offset_s=self.session.timeline.offset_s,
            leg2_duration_s=leg2_duration_s,
            leg2_offset_s=self.session.leg2_ultrasonic_datasource.offset_s,
        )
        if recompute:
            self.timeline_range_model.recompute_visible_range()

    def _set_timeline_view_state(self) -> None:
        self.timeline_view.set_timeline_state(
            current_time_s=self.session.timeline.current_time_s,
        )

    def _timeline_bounds_s(self) -> tuple[float, float]:
        leg2_duration_s = (
            self.leg2_ultrasonic_datasource.duration_s
            if self.leg2_ultrasonic_datasource is not None
            else 0.0
        )
        return timeline_view_bounds_s(
            heatmap_duration_s=self.session.heatmap_track.duration_s,
            camera_duration_s=self.session.camera_track.duration_s,
            camera_offset_s=self.session.timeline.offset_s,
            leg2_duration_s=leg2_duration_s,
            leg2_offset_s=self.session.leg2_ultrasonic_datasource.offset_s,
            fit_padding_fraction=0.0,
        )

    def _initialize_default_export_overlay_if_needed(self) -> None:
        if (
            self.camera_source is None
            or self.session.export_overlay.width > 0.0
            and self.session.export_overlay.height > 0.0
        ):
            return
        self._initialize_default_export_overlay(force=True)

    def _initialize_default_export_overlay(self, *, force: bool = False) -> None:
        if self.camera_source is None:
            return
        if (
            not force
            and self.session.export_overlay.width > 0.0
            and self.session.export_overlay.height > 0.0
        ):
            return
        preview_width = self.camera_source.preview_width
        preview_height = self.camera_source.preview_height
        margin_x = preview_width * 0.03
        margin_y = preview_height * 0.03
        width = preview_width * 0.15
        height = preview_height * 0.15
        self.session.export_overlay.x = margin_x
        self.session.export_overlay.y = preview_height - margin_y - height
        self.session.export_overlay.width = width
        self.session.export_overlay.height = height

    def _camera_native_size(self) -> tuple[int, int]:
        return self._camera_reference_width, self._camera_reference_height

    def _camera_display_size(self) -> tuple[int, int]:
        if self.current_camera_frame is not None:
            return self.current_camera_frame.shape[1], self.current_camera_frame.shape[0]
        if self.camera_source is not None:
            return self.camera_source.preview_width, self.camera_source.preview_height
        return 0, 0

    def _native_viewport_corners(self) -> np.ndarray | None:
        if not self.session.viewport.corners:
            return None
        corners = np.asarray(self.session.viewport.corners, dtype=np.float32)
        if corners.shape != (4, 2):
            return None
        return corners

    def _display_corners_to_native(self, display_corners: np.ndarray) -> np.ndarray:
        native_width, native_height = self._camera_native_size()
        display_width, display_height = self._camera_display_size()
        if native_width <= 0 or native_height <= 0:
            return display_corners.astype(np.float32, copy=True)
        if display_width <= 0 or display_height <= 0:
            return display_corners.astype(np.float32, copy=True)
        return scale_viewport_corners(
            display_corners,
            from_size=(display_width, display_height),
            to_size=(native_width, native_height),
        )

    def _display_viewport_corners(self) -> np.ndarray | None:
        native_corners = self._native_viewport_corners()
        native_width, native_height = self._camera_native_size()
        display_width, display_height = self._camera_display_size()
        if native_corners is None:
            return None
        if native_width <= 0 or native_height <= 0:
            return native_corners
        if display_width <= 0 or display_height <= 0:
            return native_corners
        return scale_viewport_corners(
            native_corners,
            from_size=(native_width, native_height),
            to_size=(display_width, display_height),
        )

    def _refresh_camera_view_corners(self) -> None:
        display_corners = self._display_viewport_corners()
        self.camera_view.set_corners(None if display_corners is None else display_corners.tolist())

    def _initialize_default_viewport_corners_native(self) -> None:
        native_width, native_height = self._camera_native_size()
        if native_width <= 0 or native_height <= 0:
            return
        inset_x = native_width * 0.15
        inset_y = native_height * 0.15
        corners = np.array(
            [
                [inset_x, inset_y],
                [native_width - inset_x, inset_y],
                [native_width - inset_x, native_height - inset_y],
                [inset_x, native_height - inset_y],
            ],
            dtype=np.float32,
        )
        self.session.viewport.corners = corners.tolist()
        self._refresh_camera_view_corners()

    def _rebuild_overlay_plot_renderer(self) -> None:
        if self.heatmap_source is None:
            self._overlay_plot_renderer = None
            return
        self._overlay_plot_renderer = HeatmapPlotRenderer(
            self.heatmap_source, output_size=(160, 120)
        )

    def _overlay_presentation_source_size(self) -> tuple[int, int] | None:
        source_rect = self._scaled_export_overlay_rect(original=True)
        source_width = int(round(source_rect.width()))
        source_height = int(round(source_rect.height()))
        if source_width <= 0 or source_height <= 0:
            return None
        return source_width, source_height

    def _scaled_export_overlay_rect(self, *, original: bool) -> QtCore.QRectF:
        overlay = self.session.export_overlay
        if self.camera_source is None:
            return QtCore.QRectF()
        if original:
            scale_x = self._camera_reference_width / max(self.camera_source.preview_width, 1)
            scale_y = self._camera_reference_height / max(self.camera_source.preview_height, 1)
        else:
            scale_x = 1.0
            scale_y = 1.0
        return QtCore.QRectF(
            overlay.x * scale_x,
            overlay.y * scale_y,
            overlay.width * scale_x,
            overlay.height * scale_y,
        )

    def _max_duration_s(self) -> float:
        return max(
            self.session.camera_track.duration_s,
            self.session.heatmap_track.duration_s,
        )

    def _viewport_output_size(self, truth_frame: np.ndarray | None) -> tuple[int, int]:
        rect = self.viewport_view.contentsRect()
        if rect.width() > 1 and rect.height() > 1:
            return rect.width(), rect.height()
        if truth_frame is not None:
            return truth_frame.shape[1], truth_frame.shape[0]
        if self.session.viewport.output_width > 1 and self.session.viewport.output_height > 1:
            return self.session.viewport.output_width, self.session.viewport.output_height
        return 320, 200

    def _camera_point_from_viewport_point(
        self,
        viewport_x: float,
        viewport_y: float,
        viewport_size: tuple[int, int],
    ) -> np.ndarray | None:
        native_corners = self._native_viewport_corners()
        native_width, native_height = self._camera_native_size()
        if native_corners is None:
            return None
        width, height = viewport_size
        if native_width <= 0 or native_height <= 0 or width <= 0 or height <= 0:
            return None
        dst = np.array(
            [[0.0, 0.0], [width - 1.0, 0.0], [width - 1.0, height - 1.0], [0.0, height - 1.0]],
            dtype=np.float32,
        )
        transform = cv2.getPerspectiveTransform(native_corners, dst)
        inverse = np.linalg.inv(transform)
        point = np.array([viewport_x, viewport_y, 1.0], dtype=np.float64)
        mapped = inverse @ point
        if abs(mapped[2]) < 1e-9:
            return None
        mapped /= mapped[2]
        return np.array(
            [
                float(np.clip(mapped[0], 0, native_width - 1)),
                float(np.clip(mapped[1], 0, native_height - 1)),
            ],
            dtype=np.float32,
        )

    def _translate_camera_corners(
        self,
        indices: list[int],
        dx: float,
        dy: float,
        *,
        base_corners: np.ndarray | None = None,
    ) -> None:
        native_width, native_height = self._camera_native_size()
        if native_width <= 0 or native_height <= 0 or not self.session.viewport.corners:
            return
        corners = (
            np.asarray(base_corners, dtype=np.float32).copy()
            if base_corners is not None
            else np.asarray(self.session.viewport.corners, dtype=np.float32)
        )
        trial = corners.copy()
        trial[indices, 0] += dx
        trial[indices, 1] += dy

        subset = trial[indices]
        adjust_dx = 0.0
        adjust_dy = 0.0
        min_x = float(np.min(subset[:, 0]))
        max_x = float(np.max(subset[:, 0]))
        min_y = float(np.min(subset[:, 1]))
        max_y = float(np.max(subset[:, 1]))
        if min_x < 0.0:
            adjust_dx = -min_x
        elif max_x > native_width - 1:
            adjust_dx = (native_width - 1) - max_x
        if min_y < 0.0:
            adjust_dy = -min_y
        elif max_y > native_height - 1:
            adjust_dy = (native_height - 1) - max_y

        corners[indices, 0] = np.clip(corners[indices, 0] + dx + adjust_dx, 0, native_width - 1)
        corners[indices, 1] = np.clip(corners[indices, 1] + dy + adjust_dy, 0, native_height - 1)
        self._set_viewport_corners(corners)

    def _viewport_corner_dragged(
        self,
        index: int,
        start_x: float,
        start_y: float,
        current_x: float,
        current_y: float,
    ) -> None:
        viewport_size = self._viewport_output_size(None)
        if not self.session.viewport.corners:
            return
        if self._viewport_drag_start_corners is None:
            self._viewport_drag_start_corners = np.asarray(
                self.session.viewport.corners, dtype=np.float32
            )
        start_point = self._camera_point_from_viewport_point(start_x, start_y, viewport_size)
        current_point = self._camera_point_from_viewport_point(current_x, current_y, viewport_size)
        if start_point is None or current_point is None:
            return
        delta = start_point - current_point
        corners = self._viewport_drag_start_corners.copy()
        corners[index] = self._viewport_drag_start_corners[index] + delta
        native_width, native_height = self._camera_native_size()
        if native_width > 0 and native_height > 0:
            corners[index, 0] = np.clip(corners[index, 0], 0, native_width - 1)
            corners[index, 1] = np.clip(corners[index, 1], 0, native_height - 1)
        self._set_viewport_corners(corners)

    def _viewport_edge_dragged(
        self,
        edge_index: int,
        prev_x: float,
        prev_y: float,
        current_x: float,
        current_y: float,
    ) -> None:
        viewport_size = self._viewport_output_size(None)
        if not self.session.viewport.corners:
            return
        if self._viewport_drag_start_corners is None:
            self._viewport_drag_start_corners = np.asarray(
                self.session.viewport.corners, dtype=np.float32
            )
        prev_point = self._camera_point_from_viewport_point(prev_x, prev_y, viewport_size)
        current_point = self._camera_point_from_viewport_point(current_x, current_y, viewport_size)
        if prev_point is None or current_point is None:
            return
        delta = prev_point - current_point
        self._translate_camera_corners(
            [edge_index, (edge_index + 1) % 4],
            float(delta[0]),
            float(delta[1]),
            base_corners=self._viewport_drag_start_corners,
        )

    def _viewport_center_dragged(
        self,
        prev_x: float,
        prev_y: float,
        current_x: float,
        current_y: float,
    ) -> None:
        viewport_size = self._viewport_output_size(None)
        if not self.session.viewport.corners:
            return
        if self._viewport_drag_start_corners is None:
            self._viewport_drag_start_corners = np.asarray(
                self.session.viewport.corners, dtype=np.float32
            )
        prev_point = self._camera_point_from_viewport_point(prev_x, prev_y, viewport_size)
        current_point = self._camera_point_from_viewport_point(current_x, current_y, viewport_size)
        if prev_point is None or current_point is None:
            return
        delta = prev_point - current_point
        self._translate_camera_corners(
            [0, 1, 2, 3],
            float(delta[0]),
            float(delta[1]),
            base_corners=self._viewport_drag_start_corners,
        )

    def _sync_previews(
        self,
        *,
        camera_access_hint: str = "auto",
        invalidate_source_resolution: bool = True,
        timeline_visible_range_s: tuple[float, float] | None = None,
        recompute_timeline_range: bool = False,
        refresh_signal_data: bool = True,
    ) -> None:
        plan = PreviewSyncPlan(
            camera_access_hint=camera_access_hint,
            invalidate_source_resolution=invalidate_source_resolution,
            timeline_visible_range_s=timeline_visible_range_s,
            recompute_timeline_range=recompute_timeline_range,
            refresh_signal_data=refresh_signal_data,
        )
        run_preview_sync(plan, self)

    def _sync_previews_preserving_timeline_range(
        self,
        *,
        camera_access_hint: str = "auto",
        invalidate_source_resolution: bool = True,
        refresh_signal_data: bool = True,
    ) -> None:
        self._sync_previews(
            camera_access_hint=camera_access_hint,
            invalidate_source_resolution=invalidate_source_resolution,
            timeline_visible_range_s=self.timeline_range_model.visible_range_s(),
            refresh_signal_data=refresh_signal_data,
        )

    def _sync_timeline_feedback(
        self,
        *,
        timeline_visible_range_s: tuple[float, float] | None,
        recompute_timeline_range: bool,
        refresh_signal_data: bool,
    ) -> None:
        self._update_timeline_range_from_session(recompute=recompute_timeline_range)
        if timeline_visible_range_s is not None:
            self.timeline_range_model.set_visible_range(*timeline_visible_range_s)
        self._set_slider_from_current_time()
        self._set_timeline_view_state()
        self._refresh_signal_plot(refresh_data=refresh_signal_data)
        self.schedule_timeline_axis_geometry_sync()
        self.current_time_label.setText(
            f"t = {self.session.timeline.current_time_s:.3f} s | offset = {self.session.timeline.offset_s:.3f} s"
        )

    def _sync_heatmap_truth_preview(self) -> tuple[int | None, np.ndarray | None]:
        truth_frame: np.ndarray | None = None
        frame_idx: int | None = None
        if self.heatmap_source is not None and (
            0.0 <= self.session.timeline.current_time_s <= self.session.heatmap_track.duration_s
        ):
            frame_idx, truth_frame = self.heatmap_source.frame_at_seconds(
                self.session.timeline.current_time_s
            )
            truth_frame = self._annotate_truth_frame_with_peak(truth_frame, frame_idx)
        if self.heatmap_source is not None and frame_idx is not None:
            if self._hover_dvm_cache is None or self._hover_dvm_cache[0] != frame_idx:
                subframe = self.heatmap_source.record.results[frame_idx].subframes[
                    self.heatmap_source.subsweep_idx
                ]
                self._hover_dvm_cache = (frame_idx, distance_velocity_map(subframe))
            self._refresh_current_heatmap_peak_overlay(frame_idx)
        else:
            self._hover_dvm_cache = None
            self._refresh_current_heatmap_peak_overlay()
        self.truth_view.set_frame(truth_frame)
        return frame_idx, truth_frame

    def _sync_export_overlay_preview(
        self,
        *,
        frame_idx: int | None,
        truth_frame: np.ndarray | None,
    ) -> None:
        if (
            not self.session.export_overlay.visible
            or not self.session.export_overlay.preview_enabled
        ):
            self.camera_view.set_export_overlay_preview_frame(None)
        elif (
            not self._freeze_export_overlay_preview
            and self._overlay_plot_renderer is not None
            and truth_frame is not None
            and self.session.export_overlay.width > 0.0
            and self.session.export_overlay.height > 0.0
        ):
            if frame_idx is None:
                frame_idx, _ = self.heatmap_source.frame_at_seconds(
                    self.session.timeline.current_time_s
                )
            presentation_source_size = self._overlay_presentation_source_size()
            peak_overlay = self._peak_overlay_for_frame(frame_idx)
            preview_frame = self._overlay_plot_renderer.render_frame(
                frame_idx,
                output_size=(
                    int(round(self.session.export_overlay.width)),
                    int(round(self.session.export_overlay.height)),
                ),
                source_size=presentation_source_size,
                peak_distance_m=None if peak_overlay is None else peak_overlay[0],
                zero_velocity_m_s=None if peak_overlay is None else peak_overlay[1],
                detection_ratio=None if peak_overlay is None else peak_overlay[2],
            )
            self.camera_view.set_export_overlay_preview_frame(preview_frame)
        elif not self._freeze_export_overlay_preview:
            self.camera_view.set_export_overlay_preview_frame(None)

    def _sync_viewport_preview(
        self,
        *,
        truth_frame: np.ndarray | None,
        invalidate_source_resolution: bool,
    ) -> None:
        viewport_frame = None
        low_resolution_viewport_frame = None
        if (
            self.current_camera_frame is not None
            and truth_frame is not None
            and self.session.viewport.corners
        ):
            viewport_size = self._viewport_output_size(truth_frame)
            display_corners = self._display_viewport_corners()
            try:
                if display_corners is not None:
                    low_resolution_viewport_frame = rectify_viewport(
                        self.current_camera_frame,
                        display_corners,
                        viewport_size,
                    )
            except ValueError:
                low_resolution_viewport_frame = None
            selected_viewport_frame = (
                self._source_resolution_viewport_frame
                if self._source_resolution_viewport_frame is not None
                else low_resolution_viewport_frame
            )
            try:
                if selected_viewport_frame is not None:
                    viewport_frame = apply_viewport_visibility(
                        selected_viewport_frame,
                        self.session.viewport_visibility,
                    )
            except ValueError:
                viewport_frame = None
            if invalidate_source_resolution:
                self._schedule_source_resolution_viewport_refresh(viewport_size=viewport_size)
        self.viewport_view.set_frame(viewport_frame)

    def _leg2_legend_name(self) -> str:
        return self._leg2_adapter().legend_name()

    def _refresh_signal_plot(self, *, refresh_data: bool = True) -> None:
        if not refresh_data:
            self.signal_plot.set_current_time_s(self.session.timeline.current_time_s)
            return
        # Build list of (display_name, color_hex, DetectionSignalSeries) for visible series.
        peak_series_list = []
        for ps in self._peak_series_list:
            if ps.visible:
                signal_series = build_peak_distance_signal_series(ps.measurements)
                peak_series_list.append((ps.display_name, ps.color, signal_series))
        leg2_series = None
        if self.leg2_ultrasonic_datasource is not None:
            leg2_series = build_leg2_ultrasonic_signal_series(
                self.leg2_ultrasonic_datasource,
                signal_kind=self.session.leg2_ultrasonic_datasource.signal_kind,
                offset_s=self.session.leg2_ultrasonic_datasource.offset_s,
            )
        leg2_visible = self.leg2_ultrasonic_datasource is not None
        self.signal_plot.set_plotted_signals(
            peak_series_list=peak_series_list,
            leg2_series=leg2_series,
            leg2_visible=leg2_visible,
            leg2_legend_name=self._leg2_legend_name(),
        )
        self.signal_plot.set_current_time_s(self.session.timeline.current_time_s)

    def _update_controls_enabled_state(self) -> None:
        camera_job_busy = self._resource_job_manager.board().camera.phase not in (
            "idle",
            "failed",
        )
        has_camera = self.camera_source is not None and not camera_job_busy
        h5_job_busy = self._resource_job_manager.board().radar_h5.phase not in (
            "idle",
            "failed",
        )
        has_heatmap = self.heatmap_source is not None and not h5_job_busy
        has_optional_signal = (
            self._has_peaks_in_memory() or self.leg2_ultrasonic_datasource is not None
        )
        enabled = has_camera or has_heatmap or has_optional_signal
        self.play_button.setEnabled(enabled)
        self.timeline_view.setEnabled(enabled)
        self.current_time_slider.setEnabled(enabled)
        self.offset_spin.setEnabled(has_camera)
        self.nudge_left_small.setEnabled(has_camera)
        self.nudge_right_small.setEnabled(has_camera)
        self.nudge_left_large.setEnabled(has_camera)
        self.nudge_right_large.setEnabled(has_camera)
        self._update_leg2_datasource_controls()
        self._update_viewport_visibility_controls_enabled()
        self._refresh_resources_ui()

    def _viewport_preview_resized(self) -> None:
        if (
            self.current_camera_frame is None
            or self.heatmap_source is None
            or not self.session.viewport.corners
        ):
            return
        self._sync_previews(camera_access_hint="auto")

    def _viewport_drag_finished(self) -> None:
        if self._viewport_drag_start_corners is not None:
            self._mark_session_dirty()
        self._viewport_drag_start_corners = None

    def _resource_runtime(self) -> AlignmentResourceRuntime:
        peak_detected: int | None = None
        peak_total: int | None = None
        peak_state = self._active_peak_state()
        if peak_state is not None:
            counts = peak_state_detected_counts(peak_state)
            if counts is not None:
                peak_detected, peak_total = counts
        leg2_adapter = self._leg2_adapter()
        leg2_valid = leg2_adapter.valid_segment_count()
        leg2_samples = leg2_adapter.sample_count()
        radar_distance_bin_width, radar_velocity_bin_width = self._active_h5_bin_widths()

        return AlignmentResourceRuntime(
            camera_loaded=self.camera_source is not None,
            radar_h5_loaded=self._h5_ready_for_generation(),
            radar_peak_loaded=self._has_peaks_in_memory(),
            leg2_loaded=leg2_adapter.is_loaded(),
            peak_detected_count=peak_detected,
            peak_measurement_count=peak_total,
            radar_distance_bin_width_m=radar_distance_bin_width,
            radar_velocity_bin_width_m_s=radar_velocity_bin_width,
            peaks_dirty=self._any_peaks_unsaved(),
            leg2_valid_segment_count=leg2_valid,
            leg2_sample_count=leg2_samples,
            reload_errors=tuple(self._resource_reload_errors.items()),
            load_warnings=tuple(self._resource_load_warnings.items()),
            resource_jobs=self._resource_job_presentations(),
        )

    def _active_h5_bin_widths(self) -> tuple[float | None, float | None]:
        if self.heatmap_source is None:
            return None, None

        try:
            subsweep = select_subsweep(
                self.heatmap_source.record,
                self.heatmap_source.subsweep_idx,
            )
            axes = heatmap_axes(
                self.heatmap_source.record.metadata,
                self.heatmap_source.record.sensor_config,
                subsweep,
            )
        except (AttributeError, ValueError):
            return None, None

        return distance_bin_width_m(axes.distances_m), axes.velocity_resolution

    def resource_summaries(self) -> tuple[ResourceSummary, ...]:
        return build_alignment_resource_summaries(
            self.session, self._resource_runtime(), peak_series=self._peak_series_list or None
        )

    def _mark_session_dirty(self) -> None:
        if self._session_lifecycle.mark_dirty():
            self._refresh_session_title()

    def _clear_session_dirty(self) -> None:
        if self._session_lifecycle.clear_dirty():
            self._refresh_session_title()

    @contextmanager
    def _session_dirty_guard(self) -> Iterator[None]:
        with self._session_lifecycle.dirty_guard():
            yield

    def _loaded_resource_flags(self) -> tuple[bool, bool, bool, bool]:
        return (
            self.camera_source is not None,
            self.heatmap_source is not None,
            self._has_peaks_in_memory(),
            self.leg2_ultrasonic_datasource is not None,
        )

    def _session_transition_guard(self, action: SessionPromptAction) -> SessionTransitionGuard:
        has_camera, has_h5, has_peaks, has_leg2 = self._loaded_resource_flags()
        return self._session_lifecycle.transition_guard(
            action,
            self.session,
            peaks_unsaved=self._any_peaks_unsaved(),
            has_camera=has_camera,
            has_h5=has_h5,
            has_peaks=has_peaks,
            has_leg2=has_leg2,
        )

    def _handle_session_transition_guard(self, action: SessionPromptAction) -> bool:
        """Run required prompts for a transition; return False if the action should abort."""
        guard = self._session_transition_guard(action)
        if guard.prompt == "save_discard_cancel":
            choice = self._prompt_save_discard_cancel(action)
            if choice == "cancel":
                return False
            if choice == "save" and not self._save_session_for_prompt():
                return False
            return True
        if guard.prompt == "clean_close_confirm":
            return self._confirm_close_session_clean()
        return True

    def _prompt_save_discard_cancel(
        self,
        action: SessionPromptAction,
    ) -> Literal["save", "discard", "cancel"]:
        prompt = self._session_lifecycle.save_discard_cancel_prompt(
            action,
            peaks_unsaved=self._any_peaks_unsaved(),
        )
        message_box = QtWidgets.QMessageBox(self)
        message_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        message_box.setWindowTitle(prompt.title)
        message_box.setText(prompt.text)
        save_button = message_box.addButton(
            "Save",
            QtWidgets.QMessageBox.ButtonRole.AcceptRole,
        )
        discard_button = message_box.addButton(
            "Don't Save",
            QtWidgets.QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_button = message_box.addButton(
            QtWidgets.QMessageBox.StandardButton.Cancel,
        )
        message_box.setDefaultButton(save_button)
        message_box.exec()
        clicked = message_box.clickedButton()
        if clicked is save_button:
            return "save"
        if clicked is discard_button:
            return "discard"
        return "cancel"

    def _confirm_close_session_clean(self) -> bool:
        prompt = self._session_lifecycle.clean_close_session_prompt()
        reply = QtWidgets.QMessageBox.question(
            self,
            prompt.title,
            prompt.text,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        return reply == QtWidgets.QMessageBox.StandardButton.Yes

    def _refresh_session_title(self) -> None:
        self.setWindowTitle(self._session_lifecycle.window_title())

    def _refresh_resources_ui(self) -> None:
        summaries = self.resource_summaries()
        if self._resources_window is not None:
            self._resources_window.refresh(summaries, self._session_lifecycle.current_path)
            # Update generate/import buttons in Resources window footer.
            self._resources_window.generate_peak_series_button.setEnabled(
                self._h5_ready_for_generation()
            )
            self._resources_window.import_peak_series_button.setEnabled(True)

        has_camera_path = bool(self.session.camera_track.path)
        has_h5_path = bool(self.session.heatmap_track.path)
        has_peak_path = bool(self._peak_series_list) or bool(
            any(e.path for e in self.session.peak_series)
        )  # True when a saved series path exists (for reload/reveal actions)
        leg2_adapter = self._leg2_adapter()
        has_leg2_path = leg2_adapter.has_path()

        self.unload_camera_action.setEnabled(self.camera_source is not None)
        self.unload_h5_action.setEnabled(self.heatmap_source is not None)
        self.unload_peak_action.setEnabled(self._has_peaks_in_memory() or has_peak_path)
        self.unload_leg2_action.setEnabled(leg2_adapter.can_unload())
        self.reload_camera_action.setEnabled(has_camera_path)
        self.reload_h5_action.setEnabled(has_h5_path)
        self.reload_peak_action.setEnabled(has_peak_path)
        self.reload_leg2_action.setEnabled(has_leg2_path)

        self.export_synced_action.setEnabled(
            self.camera_source is not None
            and self.heatmap_source is not None
            and not self._export_in_progress
            and not self._resource_job_manager.blocks_export()
        )

    def _show_resources_window(self) -> None:
        if self._resources_window is None:
            self._resources_window = ResourcesWindow(self)
            self._refresh_resources_ui()
            self._resources_window.show()
            return

        saved_geometry = self._resources_window.geometry()
        self._refresh_resources_ui()
        self._resources_window.setGeometry(saved_geometry)
        self._resources_window.show()
        self._resources_window.raise_()

    def _set_resource_reload_error(self, kind: ResourceKind, message: str | None) -> None:
        if message:
            self._resource_reload_errors[kind] = message
        else:
            self._resource_reload_errors.pop(kind, None)

    def _set_resource_warnings(
        self,
        kind: ResourceKind,
        warnings: tuple[str, ...] | list[str],
    ) -> None:
        if warnings:
            self._resource_load_warnings[kind] = tuple(warnings)
        else:
            self._resource_load_warnings.pop(kind, None)

    def invoke_resource_action(
        self, kind: ResourceKind, action: ResourceAction, *, series_id: str = ""
    ) -> None:
        if action == "cancel":
            if kind in ("camera", "radar_h5"):
                if self._resource_job_manager.cancel_job(kind):
                    self._handle_resource_job_state_changed()
            return
        if action == "generate":
            if kind == "radar_peak":
                self._generate_peak_series()
            return
        if action == "save":
            if kind == "radar_peak":
                target = self._resolve_peak_series_target(series_id, prefer_unsaved=True)
                if target is not None:
                    self._save_peak_series(target.series_id)
            return
        if action == "save_as":
            if kind == "radar_peak":
                target = self._resolve_peak_series_target(series_id, fallback_last=True)
                if target is not None:
                    self._save_peak_series_as(target.series_id)
            return
        if action == "load":
            if kind == "camera":
                self._load_camera_video()
            elif kind == "radar_h5":
                self._load_h5_recording()
            elif kind == "radar_peak":
                self._import_peak_series()
            elif kind == "leg2_mat":
                self._import_leg2_mat()
            return
        if action == "replace":
            self.invoke_resource_action(kind, "load", series_id=series_id)
            return
        if action == "unload":
            if kind == "camera":
                self.unload_camera_video()
            elif kind == "radar_h5":
                self.unload_h5_recording()
            elif kind == "radar_peak":
                target = self._resolve_peak_series_target(series_id, fallback_last=True)
                if target is not None:
                    self._unload_peak_series(target.series_id)
            elif kind == "leg2_mat":
                self._clear_leg2_ultrasonic_datasource()
            return
        if action == "reload":
            if kind == "radar_peak" and series_id:
                self._reload_peak_series(series_id)
            else:
                self._reload_resource(kind)
            return
        if action == "reveal":
            if kind == "radar_peak" and series_id:
                ps = self._resolve_peak_series_target(
                    series_id,
                    fallback_active=False,
                    fallback_last=False,
                )
                if ps and ps.json_path:
                    self._reveal_path(ps.json_path)
            else:
                self._reveal_resource_path(kind)
            return
        if action == "inspect":
            self._inspect_resource_messages(kind)

    def _resource_path_for_kind(self, kind: ResourceKind) -> str:
        if kind == "camera":
            return self.session.camera_track.path
        if kind == "radar_h5":
            return self.session.heatmap_track.path
        if kind == "radar_peak":
            for s in self._peak_series_list:
                if s.json_path is not None:
                    return str(s.json_path)
            return ""
        return self._leg2_adapter().path_text()

    def _reload_resource(self, kind: ResourceKind) -> None:
        path_text = self._resource_path_for_kind(kind)
        if not path_text:
            return
        path = Path(path_text)
        if not path.exists():
            self._set_resource_reload_error(kind, f"File not found: {path}")
            self._refresh_resources_ui()
            return
        self._set_resource_reload_error(kind, None)
        if kind == "camera":
            self.load_camera_from_path(path)
        elif kind == "radar_h5":
            self.load_h5_from_path(path)
        elif kind == "radar_peak":
            if self._any_peaks_unsaved() and not self._confirm_action_dialog(
                title="Reload peak series",
                question="Reload saved peak series from disk?",
                informative="Unsaved generated peak data will be lost.",
                accept_label="Reload",
            ):
                return
            # Reload all session-persisted peak series; drop generated unsaved rows.
            self._reload_peak_series_from_session()
        elif kind == "leg2_mat":
            self.load_leg2_mat_from_path(path, show_dialogs=True)

    def _reload_peak_series(self, series_id: str) -> None:
        """Reload a specific peak series from its saved JSON path with H5-aware validation."""
        ps = next((s for s in self._peak_series_list if s.series_id == series_id), None)
        if ps is None or ps.json_path is None:
            return
        if ps.unsaved and not self._confirm_action_dialog(
            title="Reload peak series",
            question=f"Reload '{ps.display_name}' from disk?",
            informative="Unsaved generated data for this series will be lost.",
            accept_label="Reload",
        ):
            return
        try:
            datasource, warnings = import_peak_distance_json_for_heatmap(
                ps.json_path, self.heatmap_source
            )
        except (ValueError, OSError) as exc:
            QtWidgets.QMessageBox.warning(self, "Reload failed", str(exc))
            return
        ps.measurements = datasource.measurements
        ps.metadata = datasource.metadata
        ps.unsaved = False
        ps.warnings = tuple(warnings)
        self._refresh_signal_plot()
        self._refresh_current_heatmap_peak_overlay()
        self._refresh_resources_ui()

    def _reveal_path(self, path: Path) -> None:
        target = path if path.is_dir() else path.parent
        if not target.exists():
            QtWidgets.QMessageBox.warning(
                self, "Show in File Manager", f"Path does not exist:\n{path}"
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.resolve())))

    def _reveal_resource_path(self, kind: ResourceKind) -> None:
        path_text = self._resource_path_for_kind(kind)
        if not path_text:
            return
        path = Path(path_text)
        target = path if path.is_dir() else path.parent
        if not target.exists():
            QtWidgets.QMessageBox.warning(
                self,
                "Show in File Manager",
                f"Path does not exist:\n{path}",
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.resolve())))

    def _inspect_resource_messages(self, kind: ResourceKind) -> None:
        summary = next(
            (entry for entry in self.resource_summaries() if entry.kind == kind),
            None,
        )
        if summary is None or not summary.messages:
            return
        QtWidgets.QMessageBox.warning(
            self,
            f"{summary.display_name} details",
            "\n".join(summary.messages),
        )

    def unload_camera_video(self, *, mark_dirty: bool = True) -> None:
        if mark_dirty:
            self._mark_session_dirty()
        self._resource_job_manager.cancel_job("camera")
        clear_resource_job(self._resource_job_manager.board(), "camera")
        self._camera_replacement_backup = None
        self.camera_view.set_loading_overlay(False)
        if self.camera_source is not None:
            self.camera_source.close()
            self.camera_source = None
        self._camera_reference_width = 0
        self._camera_reference_height = 0
        self.current_camera_frame = None
        self.session.camera_track = CameraTrack()
        self.session.export_overlay = ExportOverlaySettings()
        self.session.timeline.offset_s = 0.0
        self.camera_view.set_frame(None)
        self.camera_view.set_corners(None)
        self.camera_view.set_export_overlay(self.session.export_overlay)
        self.camera_view.set_export_overlay_preview_frame(None)
        self._set_resource_reload_error("camera", None)
        self._set_resource_warnings("camera", ())
        self._update_controls_enabled_state()
        self._sync_previews(camera_access_hint="auto")
        self._refresh_resources_ui()
        self.statusBar().showMessage("Unloaded camera video.")

    def unload_h5_recording(self, *, mark_dirty: bool = True) -> None:
        if mark_dirty:
            self._mark_session_dirty()
        self._resource_job_manager.cancel_job("radar_h5")
        clear_resource_job(self._resource_job_manager.board(), "radar_h5")
        self._h5_replacement_backup = None
        self._inflight_h5_identity = None
        self._pending_peak_session_reload = False
        self.truth_view.set_loading_overlay(False)
        if self.heatmap_source is not None:
            self.heatmap_source.close()
            self.heatmap_source = None
        self._overlay_plot_renderer = None
        self.session.heatmap_track = HeatmapTrack()
        self.truth_view.set_frame(None)
        self._detection_strip.set_detection_ratio(None)
        self._hover_dvm_cache = None
        self._hover_last_pos = None
        QtWidgets.QToolTip.hideText()
        self._update_heatmap_extent_labels()
        self._set_resource_reload_error("radar_h5", None)
        self._set_resource_warnings("radar_h5", ())
        self._update_controls_enabled_state()
        self._sync_previews(camera_access_hint="auto")
        self._refresh_resources_ui()
        self.statusBar().showMessage("Unloaded radar raw H5 recording.")

    def clear_all_resources(self) -> None:
        peaks_warning = (
            "\n\nUnsaved generated peak-distance data will also be lost."
            if self._any_peaks_unsaved()
            else ""
        )
        reply = QtWidgets.QMessageBox.question(
            self,
            "Clear All Resources",
            (
                "Unload Camera Video, Radar Raw (H5), all Peak Series, and Leg2 MAT "
                f"from this workbench?{peaks_warning}\n\nThe current session path will be kept."
            ),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.unload_camera_video(mark_dirty=False)
        self.unload_h5_recording(mark_dirty=False)
        self._clear_peak_series(mark_dirty=False, confirm=False)
        self._clear_leg2_ultrasonic_datasource(mark_dirty=False)
        self._mark_session_dirty()
        self.statusBar().showMessage("Cleared all loaded resources.")

    def _close_session(self) -> None:
        if not self._handle_session_transition_guard("close"):
            return
        self._reset_session_after_close()

    def _reset_session_after_close(self) -> None:
        with self._session_dirty_guard():
            self._close_sources()
            reset = self._session_lifecycle.reset_after_close()
            self.session = reset.session
            self._resource_reload_errors.clear()
            self._resource_load_warnings.clear()
            self._populate_controls_from_session()
            self._update_controls_enabled_state()
            self._sync_previews(
                camera_access_hint="auto",
                recompute_timeline_range=True,
            )
            self._refresh_resources_ui()
            self.statusBar().showMessage("Closed session.")
        self._clear_session_dirty()
        self._refresh_session_title()

    def _dialog_start_path(self, key: str) -> str:
        value = self.settings.value(key, "", type=str)
        if value:
            return str(Path(value).parent if Path(value).suffix else Path(value))
        return ""

    def _export_synced_video(self) -> None:
        if self.camera_source is None or self.heatmap_source is None or self._export_in_progress:
            return
        self._initialize_default_export_overlay_if_needed()
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export synced video",
            self._dialog_start_path("last_camera_path"),
            "MP4 files (*.mp4);;All files (*)",
        )
        if not filename:
            return

        self._export_in_progress = True
        self._update_controls_enabled_state()
        self.statusBar().showMessage("Exporting synced video...")
        progress = QtWidgets.QProgressDialog("Exporting synced video...", "Cancel", 0, 100, self)
        progress.setWindowTitle("Exporting")
        progress.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(True)
        progress.setAutoReset(False)
        progress.setValue(0)
        QtWidgets.QApplication.processEvents()

        try:
            self._write_synced_video(Path(filename), progress)
            self.statusBar().showMessage(f"Exported synced video: {filename}")
        except RuntimeError as exc:
            message = str(exc)
            if message == "Export cancelled.":
                self.statusBar().showMessage("Export cancelled.")
            else:
                QtWidgets.QMessageBox.warning(self, "Export failed", message)
                self.statusBar().showMessage("Export failed.")
        finally:
            progress.close()
            self._export_in_progress = False
            self._update_controls_enabled_state()

    @staticmethod
    def _first_usable_frame(source: CameraVideoSource) -> np.ndarray:
        last_exc: Exception | None = None
        for frame_idx in range(source.frame_count):
            try:
                return source.frame_at_index(frame_idx, access_hint="random")
            except ValueError as exc:
                last_exc = exc
        raise RuntimeError("Could not read any usable frame from the camera video.") from last_exc

    @staticmethod
    def _last_usable_frame(source: CameraVideoSource) -> np.ndarray:
        last_exc: Exception | None = None
        for frame_idx in range(source.frame_count - 1, -1, -1):
            try:
                return source.frame_at_index(frame_idx, access_hint="random")
            except ValueError as exc:
                last_exc = exc
        raise RuntimeError("Could not read any usable frame from the camera video.") from last_exc

    def _write_synced_video(
        self,
        output_path: Path,
        progress: QtWidgets.QProgressDialog,
    ) -> None:
        assert self.heatmap_source is not None
        output_path.parent.mkdir(parents=True, exist_ok=True)
        export_succeeded = False
        original_camera_source = CameraVideoSource(
            Path(self.session.camera_track.path), max_preview_dimension=None
        )
        try:
            export_rect = self._scaled_export_overlay_rect(original=True)
            export_fps = max(self.session.camera_track.fps, self.session.heatmap_track.fps, 1.0)
            overlap_start_s = max(0.0, -self.session.timeline.offset_s)
            overlap_end_s = min(
                self.session.heatmap_track.duration_s,
                self.session.camera_track.duration_s - self.session.timeline.offset_s,
            )
            if overlap_end_s <= overlap_start_s:
                raise RuntimeError(
                    "The H5 recording and video do not overlap in time. "
                    "Adjust the alignment offset before exporting."
                )
            output_frame_count = max(
                1, int(math.ceil((overlap_end_s - overlap_start_s) * export_fps))
            )
            writer = cv2.VideoWriter(
                str(output_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                export_fps,
                (original_camera_source.preview_width, original_camera_source.preview_height),
            )
            if not writer.isOpened():
                raise RuntimeError(f"Could not open video writer for {output_path}.")

            plot_renderer = None
            if export_rect.width() > 0.0 and export_rect.height() > 0.0:
                plot_renderer = HeatmapPlotRenderer(
                    self.heatmap_source,
                    output_size=(
                        int(round(export_rect.width())),
                        int(round(export_rect.height())),
                    ),
                )
            first_camera_frame = self._first_usable_frame(original_camera_source)
            last_camera_frame = self._last_usable_frame(original_camera_source)
            try:
                for frame_idx in range(output_frame_count):
                    if progress.wasCanceled():
                        raise RuntimeError("Export cancelled.")
                    h5_time_s = min(overlap_start_s + frame_idx / export_fps, overlap_end_s)
                    camera_time_s = h5_time_s + self.session.timeline.offset_s
                    if camera_time_s < 0.0:
                        camera_frame = first_camera_frame
                    elif camera_time_s > self.session.camera_track.duration_s:
                        camera_frame = last_camera_frame
                    else:
                        _, camera_frame = original_camera_source.frame_at_seconds(
                            camera_time_s,
                            access_hint="playback",
                        )
                    composed = camera_frame.copy()
                    if plot_renderer is not None:
                        heatmap_frame_idx, _ = self.heatmap_source.frame_at_seconds(h5_time_s)
                        presentation_source_size = (
                            int(round(export_rect.width())),
                            int(round(export_rect.height())),
                        )
                        peak_overlay = self._peak_overlay_for_frame(heatmap_frame_idx)
                        overlay_rgb = plot_renderer.render_frame(
                            heatmap_frame_idx,
                            output_size=presentation_source_size,
                            source_size=presentation_source_size,
                            peak_distance_m=None if peak_overlay is None else peak_overlay[0],
                            zero_velocity_m_s=None if peak_overlay is None else peak_overlay[1],
                            detection_ratio=None if peak_overlay is None else peak_overlay[2],
                        )
                        left = int(round(export_rect.x()))
                        top = int(round(export_rect.y()))
                        right = min(composed.shape[1], left + overlay_rgb.shape[1])
                        bottom = min(composed.shape[0], top + overlay_rgb.shape[0])
                        if right > max(0, left) and bottom > max(0, top):
                            source_left = max(0, -left)
                            source_top = max(0, -top)
                            left = max(0, left)
                            top = max(0, top)
                            composed[top:bottom, left:right] = overlay_rgb[
                                source_top : source_top + (bottom - top),
                                source_left : source_left + (right - left),
                            ]
                    writer.write(cv2.cvtColor(composed, cv2.COLOR_RGB2BGR))
                    if (
                        frame_idx % max(1, output_frame_count // 100) == 0
                        or frame_idx == output_frame_count - 1
                    ):
                        progress.setValue(int(round(100 * (frame_idx + 1) / output_frame_count)))
                        QtWidgets.QApplication.processEvents()
            finally:
                writer.release()
            progress.setValue(100)
            export_succeeded = True
        finally:
            original_camera_source.close()
            if not export_succeeded and output_path.exists():
                output_path.unlink(missing_ok=True)
            elif export_succeeded:
                progress.setValue(100)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Launch the Heatmap Alignment Workbench. "
            "MVP limitations: manual alignment only, fixed viewport per video, "
            "no audio playback, no moving-camera viewport tracking, xcorr disabled."
        )
    )
    parser.add_argument(
        "--session",
        type=Path,
        default=None,
        help="Optional saved alignment session JSON to load on startup.",
    )
    parser.add_argument(
        "--camera",
        type=Path,
        default=None,
        help="Optional camera video to load on startup.",
    )
    parser.add_argument(
        "--h5",
        type=Path,
        default=None,
        help="Optional H5 recording to load on startup.",
    )
    parser.add_argument(
        "--peaks",
        type=Path,
        default=None,
        help="Optional canonical peak-distance JSON to load on startup.",
    )
    parser.add_argument(
        "--mat",
        type=Path,
        default=None,
        help="Optional Leg2 MAT ultrasonic log to load on startup.",
    )
    return parser


def main() -> None:
    """Launch the alignment GUI in the current Python environment."""

    args = build_argument_parser().parse_args()

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Heatmap Alignment Workbench")
    window = HeatmapAlignmentWindow()
    window.show()

    if args.session is not None:
        session_path = args.session
        peaks_path = args.peaks
        mat_path = args.mat

        def _load_session_on_start() -> None:
            if not window._open_session(
                LoadSessionPlan(session_path=session_path, prompt_for_unsaved=False)
            ):
                return
            if peaks_path is not None:
                window._import_peak_series_from_path(peaks_path, mark_dirty=False)
            if mat_path is not None:
                window.load_leg2_mat_from_path(mat_path, mark_dirty=False)

        QtCore.QTimer.singleShot(0, _load_session_on_start)
    else:

        def _load_resources_on_start() -> None:
            if args.camera is not None:
                window.load_camera_from_path(args.camera, mark_dirty=False)
            if args.h5 is not None:
                window.load_h5_from_path(args.h5, mark_dirty=False)
            if args.peaks is not None:
                window._import_peak_series_from_path(args.peaks, mark_dirty=False)
            if args.mat is not None:
                window.load_leg2_mat_from_path(args.mat, mark_dirty=False)

        QtCore.QTimer.singleShot(0, _load_resources_on_start)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
