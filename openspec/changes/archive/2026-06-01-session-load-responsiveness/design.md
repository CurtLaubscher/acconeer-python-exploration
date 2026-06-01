## Context

The heatmap alignment workbench loads camera video (often via background preview-proxy jobs), H5 recordings (background jobs), and optional peak JSON / Leg2 MAT (synchronous) when the user opens a saved session. `load_session_from_path` always calls `_close_sources()`, which abandons in-flight camera/H5 jobs and closes active sources, then restarts every resource even when paths are unchanged.

Per-resource **Reload** in the Resources window uses replacement semantics (`replaces_active=True`) and does **not** call `_close_sources`. That difference explains why “open the same session again” feels worse than “open a different session after waiting” or than reloading a single resource.

Measured on representative trial data (post-proxy fix): `load_session_from_path` returns in ~0.5 s (Leg2 `loadmat` on the GUI thread dominates); camera proxy cold build ~20+ s and H5 init ~2–3 s run in background jobs. UI freezes users report align with abandoning in-flight proxy/H5 work and main-thread churn during re-open, not with the function return time alone.

Constraints from product discussion:

- No modal “loading session” window; use Resources rows and preview overlays.
- Reconcile from **session JSON content** (resource paths and indices), not from the session file path on disk.
- Leg2 MAT and peak JSON remain synchronous for this change; future background loading stays in `ideas.md`.
- Dirty-session prompts are out of scope.
- **Correctness over blind skip:** session open must not leave resources loaded when the new session omits them (e.g. Leg2 path cleared).

## Goals / Non-Goals

**Goals:**

- Keep the main window and Resources window responsive during Open Session and `--session` startup while resources load.
- Implement **session snapshot reconciliation**: for each registered resource slot, decide `keep`, `load`, or `unload` from desired session state vs active workbench state.
- Use **keep** only when identity matches (loaded or in-flight job target); use **load** when identity differs or slot should be loaded but is not; use **unload** when desired path is empty but the slot is still loaded.
- Do not abandon in-flight camera/H5 jobs when reconciliation selects **keep** for that slot.
- Always apply full session JSON fields (viewport, offsets, render, timeline, export overlay, signal plot view, optional datasource settings, etc.) after resource reconciliation.
- Show the main window before deferred session load when using `--session`.
- Preserve existing background job model for camera and H5.

**Non-Goals:**

- Background jobs for Leg2 MAT or peak JSON.
- Cooperative cancellation inside H5 `fixed_color_level` scan.
- Dirty-session warnings on open.
- Batch or multi-session loading.
- Changing preview-proxy encode policy.
- Diffing arbitrary widget/UI state beyond `AlignmentSession` and registered resource slots.

## Decisions

### 1. Session load is reconcile, not “skip if equal” only

**Decision:** `load_session_from_path` runs a single reconcile pass:

1. Parse session JSON into `AlignmentSession` (`desired_session`).
2. For each entry in a **registered resource slot registry** (camera, radar_h5, radar_peak, leg2_mat for v1), compute desired identity from `desired_session` (path empty vs set; H5 indices where applicable).
3. Compare to active workbench state (loaded sources, in-flight job `target_path` and H5 indices).
4. Assign `self.session = desired_session` and session path metadata **before** issuing any **load** actions that read indices or paths from `self.session` (required for `load_h5_from_path`; camera path is passed explicitly but session assignment keeps ordering consistent).
5. Emit and execute per-slot action:
   - **keep** — identity matches; no close, no new job, no abandon of in-flight work for that slot.
   - **load** — desired path set and identity differs or slot not loaded → existing load/reload APIs (see Decision 9).
   - **unload** — desired path empty and slot is loaded → existing unload/clear APIs for that slot (`unload_camera_video`, `unload_h5_recording`, `_clear_peak_distance_datasource`, `_clear_leg2_ultrasonic_datasource`).
6. Apply session fields to controls via `_populate_controls_from_session()` and related updates **after** reconcile actions are issued (jobs may still be in-flight).
7. Refresh Resources UI, previews, and status as appropriate.

**Rationale:** Preserves performance when files unchanged while guaranteeing the new session does not retain resources it no longer references.

**Alternative:** Skip reload only, never unload → risks stale optional datasources; rejected.

**Alternative:** Always `_close_sources()` → current freeze/redundant work; rejected except for empty workbench reset.

### 2. Resource identity (not session file path)

**Decision:** Identity comes from session **content**: camera path; H5 path + session/group/entry/subsweep; peak JSON path; Leg2 MAT path. Empty path means slot is **not wanted**.

**Rationale:** User may save the same logical session to a new file; only referenced files matter.

### 3. Slot registry for extensibility

**Decision:** Reconciliation iterates a single registry. Each entry SHALL encapsulate at least:

- slot kind and label used by Resources
- how to derive desired identity from `AlignmentSession`
- how to read active identity (loaded source and in-flight job target, including H5 indices)
- callables or methods for **keep** (no-op), **load**, and **unload**

The reconcile loop only dispatches the action returned per entry; adding a fifth datasource requires a new registry entry and tests, not new branches inside the loop.

**Rationale:** Reduces risk that a “fifth resource” is forgotten on session open because only one code path lists all slots.

**Alternative:** Ad hoc if/else in `load_session_from_path` only → rejected as brittle.

### 4. When to use full `_close_sources()`

**Decision:** Reserve full `_close_sources()` (abandon all jobs, clear everything) for **Close Session** / empty workbench reset and window close—not for every Open Session. Open Session uses per-slot unload/load/keep only.

**Rationale:** Open Session is “apply new snapshot,” not “nuke workbench unconditionally.”

### 5. In-flight same-identity jobs are not abandoned

**Decision:** Reconcile **keep** for a slot must not call `abandon_all_jobs` or start a duplicate job for that identity. Open Session does not call `_close_sources()`, so matching in-flight camera/H5 jobs are not abandoned structurally; there is no separate “keep guard” beyond per-slot actions.

**Rationale:** Fixes second-open-while-proxy-building stall.

### 6. Session fields always applied after reconcile

**Decision:** Refactor `load_session_from_path` so `_populate_controls_from_session()` (and related session field writes) run **after** reconcile actions are issued, not before resource loads as today. This applies regardless of how many slots used **keep**. Preview refresh (`_sync_previews`, camera frame load) follows the same post-reconcile phase as today.

**Rationale:** JSON may change offsets/viewport without changing file paths; running populate before reconcile would fight the new ordering and H5 index assignment.

### 7. CLI: `show()` before session load

**Decision:** In `main()`, construct window, `show()`, then `QTimer.singleShot(0, ...)` for `--session` load.

### 8. Leg2 / peak on sync path

**Decision:** **load** and **unload** for peak/Leg2 use existing synchronous import/clear helpers (`_reload_peak_distance_datasource_from_session`, `_reload_leg2_ultrasonic_datasource_from_session`, `_clear_peak_distance_datasource`, `_clear_leg2_ultrasonic_datasource`). **keep** when the desired path is non-empty, equals the loaded datasource path, and the datasource object is present (no sync re-import). Non-path datasource settings still come from session JSON in the post-reconcile apply phase.

### 9. Reconcile **load** uses replacement semantics, not pre-clear

**Decision:** For camera and H5, reconcile **load** calls `load_camera_from_path` / `load_h5_from_path` without calling unload/clear first. When a resource is already loaded, those paths set `replaces_active=True`, snapshot the active resource, and keep it as fallback until replacement succeeds—same as Resources **Reload**. This applies only when the new session **requests** a (different) identity, not when the slot is omitted (**unload** clears the slot so nothing remains loaded).

**Rationale:** Pre-clearing before load would drop restore-on-failure behavior. **Unload** is the correct action when the new session does not want a slot; users must not see the previous session’s camera or H5 left active after open.

**Alternative:** Close active source before load → rejected (regresses pending replacement and restore-on-failure).

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Stale resource if file on disk changes but path unchanged | Same as today; Resources → Reload; optional future mtime in identity |
| Implementer only adds **keep** branch and forgets **unload** | Spec scenarios and tests for **unload** on all four slots (camera, H5, peak, Leg2) |
| New resource added without registry entry | Document in design/tasks; require registry update in same PR as new slot |
| Partial reconcile (camera keep, H5 load) | Per-slot tests; Resources row state per slot |
| Race between job completion and session apply | Main-thread reconcile; job generations unchanged |
| H5 load uses stale indices from `self.session` | Assign `desired_session` to `self.session` before `load_h5_from_path` (Decision 1 step 4) |

## Migration Plan

No data migration. Behavior change is backward compatible for session JSON.

Rollback: revert reconcile orchestration; returns to always-close-and-reload.

## Open Questions

_None for v1; peak/Leg2 **keep** predicate is defined in Decision 8._
