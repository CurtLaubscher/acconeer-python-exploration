## 1. Desired state and reconcile model

- [x] 1.1 Add helpers to derive per-slot desired resource identity from `AlignmentSession` (empty path = slot not requested) and compare to loaded sources and in-flight job targets (including H5 indices)
- [x] 1.2 Define a resource slot registry (camera, radar_h5, radar_peak, leg2_mat) where each entry encapsulates identity comparison, active/in-flight state access, and keep/load/unload dispatch so a future slot is one new entry, not new branches in the reconcile loop
- [x] 1.3 Add unit tests for reconcile decisions: **keep**, **load**, and **unload** for all four slots (empty-path unload, in-flight job target match, H5 index mismatch)

## 2. Session load orchestration

- [x] 2.1 Replace unconditional `_close_sources()` at the start of `load_session_from_path` with `reconcile_session_load(desired_session)` that executes keep/load/unload per registered slot
- [x] 2.2 Implement **keep** for camera/H5 without close, abandon, or duplicate job when identity matches loaded or in-flight state
- [x] 2.3 Assign `self.session` (and session path metadata) from the parsed desired snapshot **before** any **load** actions that read `self.session` (required for H5 indices in `load_h5_from_path`)
- [x] 2.4 Implement **load** via existing `load_camera_from_path` / `load_h5_from_path` when identity differs or slot not loaded; do not call unload/clear first—rely on existing `replaces_active` replacement and restore-on-failure when a resource is already loaded
- [x] 2.5 Implement **unload** when desired path is empty but the slot is loaded: `unload_camera_video`, `unload_h5_recording`, `_clear_peak_distance_datasource`, `_clear_leg2_ultrasonic_datasource` (same entry points as Resources **Unload** / menu actions, not `_close_sources` internals)
- [x] 2.6 Implement peak/Leg2 **load**/**keep** via `_reload_peak_distance_datasource_from_session` / `_reload_leg2_ultrasonic_datasource_from_session`; **keep** when path is non-empty, equals the loaded datasource path, and the datasource object is present
- [x] 2.7 Refactor so `_populate_controls_from_session()` and related session-field application run **after** reconcile actions are issued (not before resource loads as today); then refresh Resources UI, previews, and status as today
- [x] 2.8 Keep full `_close_sources()` only for Close Session / empty workbench reset and window close—not for every Open Session

## 3. CLI startup (scope B)

- [x] 3.1 Defer `--session` load until after `window.show()` using `QTimer.singleShot(0, ...)`
- [x] 3.2 Manually verify cold `--session`: main window is painted and interactive before the Resources row for camera or H5 shows a loading state from deferred session load

## 4. Tests

- [x] 4.1 Test: same camera/H5 identity does not abandon in-flight job (mock job manager)
- [x] 4.2 Test: changed H5 identity (path or indices) reconciles as **load**
- [x] 4.3 Test: session with empty camera path reconciles as **unload** when camera was loaded
- [x] 4.4 Test: session with empty H5 path reconciles as **unload** when H5 was loaded
- [x] 4.5 Test: session with empty Leg2 or peak path reconciles as **unload** when datasource was loaded
- [x] 4.6 Test: session fields (e.g. timeline offset) still applied when camera slot uses **keep**
- [x] 4.7 Test: session fields still applied when H5 slot uses **keep** (path and indices unchanged)

## 5. Documentation

- [x] 5.1 Document in code (brief module or function docstring) that new resource types must register a reconcile slot—point to OpenSpec requirement
