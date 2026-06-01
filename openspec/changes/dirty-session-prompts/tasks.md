## 1. Save policy alignment (prerequisite)

- [ ] 1.1 Change `_write_session_to_path` to validate with `allow_missing_sources=True` before calling `save_alignment_session`.
- [ ] 1.2 Remove the `camera_source` and `heatmap_source` in-memory gate from `save_session_action.setEnabled` in `_refresh_resources_ui` (Save Session stays enabled independently of loaded resources).
- [ ] 1.3 Add or adjust tests that Save succeeds with session JSON paths set but resources not loaded in memory.

## 2. Dirty state core

- [ ] 2.1 Add `_session_dirty`, `_mark_session_dirty()`, `_clear_session_dirty()`, and `_session_dirty_guard()` to `HeatmapAlignmentWindow`.
- [ ] 2.2 Update `_refresh_session_title()` to append `*` when dirty.
- [ ] 2.3 Implement `workbench_is_pristine()` and `session_equivalent_for_pristine()` (or core helper) for reliable default-session comparison.
- [ ] 2.4 Clear dirty in `_write_session_to_path` on success, at end of `load_session_from_path`, and after `_close_session` reset.

## 3. Mark dirty call sites (user-initiated only)

- [ ] 3.1 Mark dirty from alignment/render handlers: offset, render, preprocess, viewport visibility, viewport corners/drag, export overlay drag/geometry, signal plot view, timeline H5 drag (offset fields), leg2 offset; peak marker visibility; Leg2 signal visibility and signal kind; export overlay visible, preview enabled, and reset.
- [ ] 3.2 Mark dirty at **user-initiated** resource entry points: `_load_camera_video` / `load_camera_from_path` (UI only), `_load_h5_recording` / `load_h5_from_path` (UI only), peak/leg2 import paths, `unload_camera_video`, `unload_h5_recording`, peak/leg2 clear, successful `clear_all_resources`. Do **not** mark dirty in `_apply_camera_job_result`, `_apply_h5_job_result`, or reconcile/startup-driven `load_*_from_path` calls.
- [ ] 3.3 Wrap `load_session_from_path`, `_populate_controls_from_session`, and close-reset paths in `_session_dirty_guard()` for synchronous paths; ensure reconcile calls `load_*_from_path` without marking dirty.

## 4. Unsaved prompts and close branches

- [ ] 4.1 Implement `_prompt_save_discard_cancel(action)` with titles/text from design (dirty paths only).
- [ ] 4.2 Implement `_confirm_close_session_clean()` Yes/No for clean non-pristine Close Session.
- [ ] 4.3 Wire `_load_session`: dirty tri-state before file dialog; Save/Don't Save/Cancel; cancel file dialog after Don't Save leaves session dirty.
- [ ] 4.4 Wire `_close_session`: pristine+clean → silent; dirty → tri-state; clean non-pristine → Yes/No only.
- [ ] 4.5 Wire `closeEvent` / Quit: dirty → tri-state; clean → no prompt, then `_close_sources()` and exit.
- [ ] 4.6 Ensure `--session` startup and direct `load_session_from_path` in tests bypass the open prompt.

## 5. Tests and verification

- [ ] 5.1 GUI tests: title `*` when dirty, cleared after save/load.
- [ ] 5.2 GUI tests: mocked `QMessageBox` — Cancel on quit/open/close leaves state dirty; Don't Save then open proceeds; Don't Save then cancel open dialog stays dirty; Save calls write path.
- [ ] 5.3 GUI test: pristine Close Session does not show a dialog.
- [ ] 5.4 GUI test: clean non-pristine Close Session shows Yes/No only, not tri-state.
- [ ] 5.5 GUI test: clean Quit does not show a dialog.
- [ ] 5.6 GUI test: after `load_session_from_path`, wait for or simulate job completion — no `*` without user edit.
- [ ] 5.7 GUI test: clear all resources marks dirty; visibility/export toggles mark dirty.
- [ ] 5.8 GUI test: Save from unsaved prompt aborted when validation fails (session stays dirty, action cancelled).
- [ ] 5.9 Run repo test suite for `test_heatmap_alignment_gui.py` and confirm session-load reconcile tests still pass.
