"""Resource UI/action coordinator for the heatmap alignment workbench."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from heatmap_alignment_dialogs import ResourcesWindow
from heatmap_alignment_resource_actions import containing_directory, resource_path_for_kind
from heatmap_alignment_resource_model import ResourceAction, ResourceKind
from heatmap_alignment_resource_summaries import (
    AlignmentResourceRuntime,
    ResourceSummary,
    build_alignment_resource_summaries,
)
from heatmap_peak_distance_resource import peak_state_detected_counts

from PySide6 import QtWidgets
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


class ResourceCoordinatorHost(Protocol):
    session: object
    camera_source: object | None
    heatmap_source: object | None
    _export_in_progress: bool
    _peak_series_list: list
    _resource_job_manager: object
    _session_lifecycle: object
    unload_camera_action: object
    unload_h5_action: object
    unload_peak_action: object
    unload_leg2_action: object
    reload_camera_action: object
    reload_h5_action: object
    reload_peak_action: object
    reload_leg2_action: object
    export_synced_action: object

    def _h5_ready_for_generation(self) -> bool: ...
    def _handle_resource_job_state_changed(self) -> None: ...
    def _has_peaks_in_memory(self) -> bool: ...
    def _any_peaks_unsaved(self) -> bool: ...
    def _active_peak_state(self): ...
    def _leg2_adapter(self): ...
    def _active_h5_bin_widths(self) -> tuple[float | None, float | None]: ...
    def _resource_job_presentations(self) -> tuple: ...
    def _generate_peak_series(self) -> None: ...
    def _resolve_peak_series_target(self, *args, **kwargs): ...
    def _save_peak_series(self, series_id: str) -> None: ...
    def _save_peak_series_as(self, series_id: str) -> None: ...
    def _load_camera_video(self) -> None: ...
    def _load_h5_recording(self) -> None: ...
    def _import_peak_series(self) -> None: ...
    def _import_leg2_mat(self) -> None: ...
    def unload_camera_video(self) -> None: ...
    def unload_h5_recording(self) -> None: ...
    def _unload_peak_series(self, series_id: str) -> None: ...
    def _clear_leg2_ultrasonic_datasource(self) -> None: ...
    def _reload_peak_series(self, series_id: str) -> None: ...
    def _confirm_action_dialog(self, **kwargs) -> bool: ...
    def load_camera_from_path(self, path: Path) -> None: ...
    def load_h5_from_path(self, path: Path) -> None: ...
    def _reload_peak_series_from_session(self) -> None: ...
    def load_leg2_mat_from_path(self, path: Path, *, show_dialogs: bool = True) -> None: ...


class ResourceCoordinator:
    def __init__(self, host: ResourceCoordinatorHost) -> None:
        self._host = host
        self.reload_errors: dict[ResourceKind, str] = {}
        self.load_warnings: dict[ResourceKind, tuple[str, ...]] = {}
        self.resources_window: ResourcesWindow | None = None

    def resource_runtime(self) -> AlignmentResourceRuntime:
        host = self._host
        peak_detected: int | None = None
        peak_total: int | None = None
        peak_state = host._active_peak_state()
        if peak_state is not None:
            counts = peak_state_detected_counts(peak_state)
            if counts is not None:
                peak_detected, peak_total = counts
        leg2_adapter = host._leg2_adapter()
        radar_distance_bin_width, radar_velocity_bin_width = host._active_h5_bin_widths()

        return AlignmentResourceRuntime(
            camera_loaded=host.camera_source is not None,
            radar_h5_loaded=host._h5_ready_for_generation(),
            radar_peak_loaded=host._has_peaks_in_memory(),
            leg2_loaded=leg2_adapter.is_loaded(),
            peak_detected_count=peak_detected,
            peak_measurement_count=peak_total,
            radar_distance_bin_width_m=radar_distance_bin_width,
            radar_velocity_bin_width_m_s=radar_velocity_bin_width,
            peaks_dirty=host._any_peaks_unsaved(),
            leg2_valid_segment_count=leg2_adapter.valid_segment_count(),
            leg2_sample_count=leg2_adapter.sample_count(),
            reload_errors=tuple(self.reload_errors.items()),
            load_warnings=tuple(self.load_warnings.items()),
            resource_jobs=host._resource_job_presentations(),
        )

    def resource_summaries(self) -> tuple[ResourceSummary, ...]:
        host = self._host
        return build_alignment_resource_summaries(
            host.session,
            self.resource_runtime(),
            peak_series=host._peak_series_list or None,
        )

    def refresh_resources_ui(self) -> None:
        host = self._host
        summaries = self.resource_summaries()
        if self.resources_window is not None:
            self.resources_window.refresh(summaries, host._session_lifecycle.current_path)
            self.resources_window.generate_peak_series_button.setEnabled(
                host._h5_ready_for_generation()
            )
            self.resources_window.import_peak_series_button.setEnabled(True)

        has_camera_path = bool(host.session.camera_track.path)
        has_h5_path = bool(host.session.heatmap_track.path)
        has_peak_path = bool(host._peak_series_list) or bool(
            any(entry.path for entry in host.session.peak_series)
        )
        leg2_adapter = host._leg2_adapter()
        has_leg2_path = leg2_adapter.has_path()

        host.unload_camera_action.setEnabled(host.camera_source is not None)
        host.unload_h5_action.setEnabled(host.heatmap_source is not None)
        host.unload_peak_action.setEnabled(host._has_peaks_in_memory() or has_peak_path)
        host.unload_leg2_action.setEnabled(leg2_adapter.can_unload())
        host.reload_camera_action.setEnabled(has_camera_path)
        host.reload_h5_action.setEnabled(has_h5_path)
        host.reload_peak_action.setEnabled(has_peak_path)
        host.reload_leg2_action.setEnabled(has_leg2_path)

        host.export_synced_action.setEnabled(
            host.camera_source is not None
            and host.heatmap_source is not None
            and not host._export_in_progress
            and not host._resource_job_manager.blocks_export()
        )

    def show_resources_window(self) -> None:
        if self.resources_window is None:
            self.resources_window = ResourcesWindow(self._host)
            self.refresh_resources_ui()
            self.resources_window.show()
            return

        saved_geometry = self.resources_window.geometry()
        self.refresh_resources_ui()
        self.resources_window.setGeometry(saved_geometry)
        self.resources_window.show()
        self.resources_window.raise_()

    def set_reload_error(self, kind: ResourceKind, message: str | None) -> None:
        if message:
            self.reload_errors[kind] = message
        else:
            self.reload_errors.pop(kind, None)

    def set_warnings(self, kind: ResourceKind, warnings: tuple[str, ...] | list[str]) -> None:
        if warnings:
            self.load_warnings[kind] = tuple(warnings)
        else:
            self.load_warnings.pop(kind, None)

    def invoke_resource_action(
        self,
        kind: ResourceKind,
        action: ResourceAction,
        *,
        series_id: str = "",
    ) -> None:
        host = self._host
        if action == "cancel":
            if kind in ("camera", "radar_h5"):
                if host._resource_job_manager.cancel_job(kind):
                    host._handle_resource_job_state_changed()
            return
        if action == "generate":
            if kind == "radar_peak":
                host._generate_peak_series()
            return
        if action == "save":
            if kind == "radar_peak":
                target = host._resolve_peak_series_target(series_id, prefer_unsaved=True)
                if target is not None:
                    host._save_peak_series(target.series_id)
            return
        if action == "save_as":
            if kind == "radar_peak":
                target = host._resolve_peak_series_target(series_id, fallback_last=True)
                if target is not None:
                    host._save_peak_series_as(target.series_id)
            return
        if action == "load":
            self._load_resource(kind)
            return
        if action == "replace":
            self.invoke_resource_action(kind, "load", series_id=series_id)
            return
        if action == "unload":
            self._unload_resource(kind, series_id=series_id)
            return
        if action == "reload":
            if kind == "radar_peak" and series_id:
                host._reload_peak_series(series_id)
            else:
                self.reload_resource(kind)
            return
        if action == "reveal":
            if kind == "radar_peak" and series_id:
                peak_series = host._resolve_peak_series_target(
                    series_id,
                    fallback_active=False,
                    fallback_last=False,
                )
                if peak_series and peak_series.json_path:
                    self.reveal_path(peak_series.json_path)
            else:
                self.reveal_resource_path(kind)
            return
        if action == "inspect":
            self.inspect_resource_messages(kind)

    def _load_resource(self, kind: ResourceKind) -> None:
        host = self._host
        if kind == "camera":
            host._load_camera_video()
        elif kind == "radar_h5":
            host._load_h5_recording()
        elif kind == "radar_peak":
            host._import_peak_series()
        elif kind == "leg2_mat":
            host._import_leg2_mat()

    def _unload_resource(self, kind: ResourceKind, *, series_id: str = "") -> None:
        host = self._host
        if kind == "camera":
            host.unload_camera_video()
        elif kind == "radar_h5":
            host.unload_h5_recording()
        elif kind == "radar_peak":
            target = host._resolve_peak_series_target(series_id, fallback_last=True)
            if target is not None:
                host._unload_peak_series(target.series_id)
        elif kind == "leg2_mat":
            host._clear_leg2_ultrasonic_datasource()

    def resource_path_for_kind(self, kind: ResourceKind) -> str:
        host = self._host
        return resource_path_for_kind(
            host.session,
            kind,
            peak_series=host._peak_series_list,
            leg2_path_text=host._leg2_adapter().path_text(),
        )

    def reload_resource(self, kind: ResourceKind) -> None:
        host = self._host
        path_text = self.resource_path_for_kind(kind)
        if not path_text:
            return
        path = Path(path_text)
        if not path.exists():
            self.set_reload_error(kind, f"File not found: {path}")
            self.refresh_resources_ui()
            return
        self.set_reload_error(kind, None)
        if kind == "camera":
            host.load_camera_from_path(path)
        elif kind == "radar_h5":
            host.load_h5_from_path(path)
        elif kind == "radar_peak":
            if host._any_peaks_unsaved() and not host._confirm_action_dialog(
                title="Reload peak series",
                question="Reload saved peak series from disk?",
                informative="Unsaved generated peak data will be lost.",
                accept_label="Reload",
            ):
                return
            host._reload_peak_series_from_session()
        elif kind == "leg2_mat":
            host.load_leg2_mat_from_path(path, show_dialogs=True)

    def reveal_path(self, path: Path) -> None:
        target = containing_directory(path)
        if not target.exists():
            QtWidgets.QMessageBox.warning(
                self._host,
                "Show in File Manager",
                f"Path does not exist:\n{path}",
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.resolve())))

    def reveal_resource_path(self, kind: ResourceKind) -> None:
        path_text = self.resource_path_for_kind(kind)
        if not path_text:
            return
        path = Path(path_text)
        target = containing_directory(path)
        if not target.exists():
            QtWidgets.QMessageBox.warning(
                self._host,
                "Show in File Manager",
                f"Path does not exist:\n{path}",
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.resolve())))

    def inspect_resource_messages(self, kind: ResourceKind) -> None:
        summary = next((entry for entry in self.resource_summaries() if entry.kind == kind), None)
        if summary is None or not summary.messages:
            return
        QtWidgets.QMessageBox.warning(
            self._host,
            f"{summary.display_name} details",
            "\n".join(summary.messages),
        )
