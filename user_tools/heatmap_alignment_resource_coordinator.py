"""Resource UI/action coordinator for the heatmap alignment workbench."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from heatmap_alignment_resource_actions import containing_directory
from heatmap_alignment_resource_adapters import resource_adapter
from heatmap_alignment_resource_job_state import resource_job_target_filename
from heatmap_alignment_resource_model import ResourceAction, ResourceKind
from heatmap_alignment_resource_summaries import (
    AlignmentResourceRuntime,
    ResourceJobPresentation,
    ResourceSummary,
    build_alignment_resource_summaries,
)
from heatmap_alignment_resources_window import ResourcesWindow
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
            resource_jobs=self._resource_job_presentations(),
        )

    def _resource_job_presentations(self) -> tuple[ResourceJobPresentation, ...]:
        presentations: list[ResourceJobPresentation] = []
        for snapshot in self._host._resource_job_manager.snapshots():
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

        camera_adapter = resource_adapter("camera")
        h5_adapter = resource_adapter("radar_h5")
        peak_adapter = resource_adapter("radar_peak")
        leg2_adapter = resource_adapter("leg2_mat")

        host.unload_camera_action.setEnabled(camera_adapter.can_unload(host))
        host.unload_h5_action.setEnabled(h5_adapter.can_unload(host))
        host.unload_peak_action.setEnabled(peak_adapter.can_unload(host))
        host.unload_leg2_action.setEnabled(leg2_adapter.can_unload(host))
        host.reload_camera_action.setEnabled(camera_adapter.has_path(host))
        host.reload_h5_action.setEnabled(h5_adapter.has_path(host))
        host.reload_peak_action.setEnabled(peak_adapter.has_path(host))
        host.reload_leg2_action.setEnabled(leg2_adapter.has_path(host))

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
        if action == "reveal":
            self.reveal_resource_path(kind, series_id=series_id)
            return
        if action == "inspect":
            self.inspect_resource_messages(kind)
            return
        resource_adapter(kind).invoke_action(self, self._host, action, series_id=series_id)

    def resource_path_for_kind(self, kind: ResourceKind) -> str:
        return resource_adapter(kind).path_text(self._host)

    def reload_resource(self, kind: ResourceKind) -> None:
        resource_adapter(kind).reload(self, self._host)

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

    def reveal_resource_path(self, kind: ResourceKind, *, series_id: str = "") -> None:
        path_text = resource_adapter(kind).reveal_path_text(self._host, series_id=series_id)
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
