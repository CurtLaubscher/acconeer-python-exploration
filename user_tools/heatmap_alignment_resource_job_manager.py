from __future__ import annotations


"""Resource job scheduling for the heatmap alignment workbench."""

import threading
from pathlib import Path

from heatmap_alignment_camera_resource_job import (
    CameraResourceJobResult,
    run_camera_resource_job,
)
from heatmap_alignment_h5_resource_job import (
    LoadedH5ResourcePayload,
    load_h5_resource_payload,
    release_resource_job_result,
)
from heatmap_alignment_resource_job_state import (
    ResourceJobBoard,
    ResourceJobError,
    ResourceJobKind,
    ResourceJobSnapshot,
    begin_resource_job,
    clear_resource_job,
    complete_resource_job,
    mark_resource_job_phase,
    request_cancel_resource_job,
    resource_job_blocks_export,
    should_apply_job_result,
)

from PySide6 import QtCore


class _ResourceJobRunnable(QtCore.QRunnable):
    def __init__(
        self,
        manager: ResourceJobManager,
        kind: ResourceJobKind,
        generation: int,
        worker: object,
    ) -> None:
        super().__init__()
        self._manager = manager
        self._kind = kind
        self._generation = generation
        self._worker = worker
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            result = self._worker()
        except Exception as exc:
            if not self._manager._is_abandoned():
                self._manager._dispatch_job_failure(self._kind, self._generation, exc)
            return
        if self._manager._is_abandoned():
            self._manager._release_abandoned_worker_result(
                self._kind,
                self._generation,
                result,
            )
            return
        self._manager._dispatch_job_success(self._kind, self._generation, result)


class ResourceJobManager(QtCore.QObject):
    """Schedules camera and H5 resource jobs off the GUI thread."""

    job_state_changed = QtCore.Signal()
    job_progress = QtCore.Signal(str, int, str, str)
    job_succeeded = QtCore.Signal(str, int, object)
    job_failed = QtCore.Signal(str, int, str)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._board = ResourceJobBoard()
        self._thread_pool = QtCore.QThreadPool.globalInstance()
        self._worker_state_lock = threading.Lock()
        self._proxy_active = False
        self._h5_active = False
        self._proxy_processes: dict[int, object] = {}
        self._pending_results: dict[tuple[ResourceJobKind, int], object] = {}
        self._cancelled_generations: set[tuple[ResourceJobKind, int]] = set()
        self._abandoned = False
        self.job_progress.connect(self._handle_job_progress)
        self.job_succeeded.connect(self._handle_job_success)
        self.job_failed.connect(self._handle_job_failure)

    def board(self) -> ResourceJobBoard:
        return self._board

    def snapshots(self) -> tuple[ResourceJobSnapshot, ...]:
        return (
            self._board.camera.snapshot("camera"),
            self._board.radar_h5.snapshot("radar_h5"),
        )

    def blocks_export(self) -> bool:
        return resource_job_blocks_export(self._board)

    def _is_abandoned(self) -> bool:
        with self._worker_state_lock:
            return self._abandoned

    def _set_abandoned(self, abandoned: bool) -> None:
        with self._worker_state_lock:
            self._abandoned = abandoned

    def _generation_cancelled(self, kind: ResourceJobKind, generation: int) -> bool:
        with self._worker_state_lock:
            return (kind, generation) in self._cancelled_generations

    def _cancel_generation(self, kind: ResourceJobKind, generation: int) -> None:
        if generation <= 0:
            return
        with self._worker_state_lock:
            self._cancelled_generations.add((kind, generation))
            process = self._proxy_processes.pop(generation, None) if kind == "camera" else None
        if process is None:
            return
        try:
            process.terminate()
        except OSError:
            pass

    def _discard_cancelled_generation(self, kind: ResourceJobKind, generation: int) -> None:
        with self._worker_state_lock:
            self._cancelled_generations.discard((kind, generation))

    def _emit_job_progress(
        self,
        kind: ResourceJobKind,
        generation: int,
        phase: str,
        message: str,
    ) -> None:
        try:
            self.job_progress.emit(kind, generation, phase, message)
        except RuntimeError as exc:
            if "Internal C++ object" not in str(exc):
                raise

    def _acquire_worker_slot(
        self, kind: ResourceJobKind, generation: int, waiting_message: str
    ) -> None:
        waiting_reported = False
        while True:
            with self._worker_state_lock:
                if (kind, generation) in self._cancelled_generations:
                    raise ResourceJobError(
                        "Camera load cancelled." if kind == "camera" else "H5 load cancelled."
                    )
                active = self._proxy_active if kind == "camera" else self._h5_active
                if not active:
                    if kind == "camera":
                        self._proxy_active = True
                    else:
                        self._h5_active = True
                    return
            if not waiting_reported:
                self._emit_job_progress(kind, generation, "waiting", waiting_message)
                waiting_reported = True
            QtCore.QThread.msleep(25)

    def _release_worker_slot(self, kind: ResourceJobKind) -> None:
        with self._worker_state_lock:
            if kind == "camera":
                self._proxy_active = False
            else:
                self._h5_active = False

    def _register_proxy_process(self, generation: int, process: object) -> None:
        with self._worker_state_lock:
            self._proxy_processes[generation] = process

    def _unregister_proxy_process(self, generation: int) -> None:
        with self._worker_state_lock:
            self._proxy_processes.pop(generation, None)

    def _release_job_result(self, kind: ResourceJobKind, generation: int, result: object) -> None:
        release_resource_job_result(kind, result)
        self._pending_results.pop((kind, generation), None)

    def _discard_all_pending_results(self) -> None:
        for (kind, generation), result in list(self._pending_results.items()):
            self._release_job_result(kind, generation, result)

    def abandon_all_jobs(self) -> None:
        self._set_abandoned(True)
        for kind in ("camera", "radar_h5"):
            slot = self._board.slot(kind)
            if slot.phase not in ("idle", "failed"):
                self._cancel_generation(kind, slot.generation)
            clear_resource_job(self._board, kind)
        self._discard_all_pending_results()
        self.job_state_changed.emit()

    def _release_abandoned_worker_result(
        self,
        kind: ResourceJobKind,
        generation: int,
        result: object,
    ) -> None:
        self._release_job_result(kind, generation, result)

    def start_camera_job(
        self,
        camera_path: Path,
        *,
        replaces_active: bool,
        cache_root: Path | None = None,
    ) -> int:
        self._set_abandoned(False)
        slot = self._board.camera
        if slot.phase not in ("idle", "failed"):
            self._cancel_generation("camera", slot.generation)
        generation = begin_resource_job(
            self._board,
            "camera",
            target_path=camera_path,
            replaces_active=replaces_active,
            initial_phase="pending",
            message=f"Loading {camera_path.name}...",
        )
        self._schedule_camera_job(generation, camera_path, cache_root=cache_root)
        self.job_state_changed.emit()
        return generation

    def start_h5_job(
        self,
        h5_path: Path,
        *,
        replaces_active: bool,
        session_idx: int | None,
        group_idx: int | None,
        entry_idx: int | None,
        subsweep_idx: int | None,
        color_min: float,
        color_max: float | None,
        fixed_levels: bool,
    ) -> int:
        self._set_abandoned(False)
        slot = self._board.radar_h5
        if slot.phase not in ("idle", "failed"):
            self._cancel_generation("radar_h5", slot.generation)
        generation = begin_resource_job(
            self._board,
            "radar_h5",
            target_path=h5_path,
            replaces_active=replaces_active,
            initial_phase="loading",
            message=f"Loading {h5_path.name}...",
        )
        self._schedule_h5_job(
            generation,
            h5_path,
            session_idx=session_idx,
            group_idx=group_idx,
            entry_idx=entry_idx,
            subsweep_idx=subsweep_idx,
            color_min=color_min,
            color_max=color_max,
            fixed_levels=fixed_levels,
        )
        self.job_state_changed.emit()
        return generation

    def cancel_job(self, kind: ResourceJobKind) -> bool:
        if not request_cancel_resource_job(self._board, kind):
            return False
        slot = self._board.slot(kind)
        generation = slot.generation
        self._cancel_generation(kind, generation)
        pending = self._pending_results.pop((kind, generation), None)
        if pending is not None:
            self._release_job_result(kind, generation, pending)
        complete_resource_job(self._board, kind, generation, phase="idle")
        self.job_state_changed.emit()
        return True

    def _schedule_camera_job(
        self,
        generation: int,
        camera_path: Path,
        *,
        cache_root: Path | None,
    ) -> None:
        def _worker() -> CameraResourceJobResult:
            self._acquire_worker_slot(
                "camera",
                generation,
                f"Waiting to build preview proxy for {camera_path.name}...",
            )
            try:
                if self._generation_cancelled("camera", generation):
                    raise ResourceJobError("Camera load cancelled.")
                self._emit_job_progress(
                    "camera",
                    generation,
                    "building",
                    f"Building preview proxy for {camera_path.name}...",
                )

                def _process_hook(process: object) -> None:
                    self._register_proxy_process(generation, process)

                return run_camera_resource_job(
                    camera_path,
                    cache_root=cache_root,
                    cancel_check=lambda: self._generation_cancelled("camera", generation),
                    process_hook=_process_hook,
                )
            finally:
                self._release_worker_slot("camera")
                self._unregister_proxy_process(generation)
                self._discard_cancelled_generation("camera", generation)

        runnable = _ResourceJobRunnable(self, "camera", generation, _worker)
        self._thread_pool.start(runnable, priority=0)

    def _schedule_h5_job(
        self,
        generation: int,
        h5_path: Path,
        *,
        session_idx: int | None,
        group_idx: int | None,
        entry_idx: int | None,
        subsweep_idx: int | None,
        color_min: float,
        color_max: float | None,
        fixed_levels: bool,
    ) -> None:
        def _worker() -> LoadedH5ResourcePayload:
            self._acquire_worker_slot(
                "radar_h5",
                generation,
                f"Waiting to load {h5_path.name}...",
            )
            try:
                if self._generation_cancelled("radar_h5", generation):
                    raise ResourceJobError("H5 load cancelled.")
                self._emit_job_progress(
                    "radar_h5",
                    generation,
                    "loading",
                    f"Loading {h5_path.name}...",
                )
                return load_h5_resource_payload(
                    h5_path,
                    session_idx=session_idx,
                    group_idx=group_idx,
                    entry_idx=entry_idx,
                    subsweep_idx=subsweep_idx,
                    color_min=color_min,
                    color_max=color_max,
                    fixed_levels=fixed_levels,
                    cancel_check=lambda: self._generation_cancelled("radar_h5", generation),
                )
            finally:
                self._release_worker_slot("radar_h5")
                self._discard_cancelled_generation("radar_h5", generation)

        runnable = _ResourceJobRunnable(self, "radar_h5", generation, _worker)
        self._thread_pool.start(runnable, priority=0)

    def _dispatch_job_success(
        self,
        kind: ResourceJobKind,
        generation: int,
        result: object,
    ) -> None:
        try:
            self.job_succeeded.emit(kind, generation, result)
        except RuntimeError as exc:
            if "Internal C++ object" not in str(exc):
                raise
            self._release_job_result(kind, generation, result)

    def _dispatch_job_failure(
        self,
        kind: ResourceJobKind,
        generation: int,
        error: Exception,
    ) -> None:
        try:
            self.job_failed.emit(kind, generation, str(error))
        except RuntimeError as exc:
            if "Internal C++ object" not in str(exc):
                raise
            return

    def _handle_job_progress(
        self,
        kind: ResourceJobKind,
        generation: int,
        phase: str,
        message: str,
    ) -> None:
        slot = self._board.slot(kind)
        if (
            self._is_abandoned()
            or self._generation_cancelled(kind, generation)
            or generation != slot.generation
            or slot.phase in ("idle", "failed", "superseded", "cancelling")
            or slot.cancel_requested
        ):
            return
        mark_resource_job_phase(
            self._board,
            kind,
            generation,
            phase,
            message=message,
        )
        self.job_state_changed.emit()

    def _handle_job_success(
        self,
        kind: ResourceJobKind,
        generation: int,
        result: object,
    ) -> None:
        slot = self._board.slot(kind)
        if slot.cancel_requested or self._generation_cancelled(kind, generation):
            self._release_job_result(kind, generation, result)
            return
        if not should_apply_job_result(slot, generation):
            self._release_job_result(kind, generation, result)
            return
        complete_resource_job(self._board, kind, generation, phase="idle")
        self._pending_results[(kind, generation)] = result
        self.job_state_changed.emit()

    def _handle_job_failure(self, kind: ResourceJobKind, generation: int, message: str) -> None:
        slot = self._board.slot(kind)
        if not should_apply_job_result(slot, generation):
            return
        if slot.cancel_requested or self._generation_cancelled(kind, generation):
            complete_resource_job(self._board, kind, generation, phase="idle")
        else:
            complete_resource_job(
                self._board,
                kind,
                generation,
                phase="failed",
                message=message,
            )
        self.job_state_changed.emit()

    def take_pending_result(self, kind: ResourceJobKind, generation: int) -> object | None:
        return self._pending_results.pop((kind, generation), None)
