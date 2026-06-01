## Context

`AlignmentSession` in `heatmap_alignment_core.py` is the serializable source of truth for session JSON. The GUI mutates `self.session` from controls, timeline, viewport, resource load/unload, and optional datasource actions. Save/load/close entry points live in `HeatmapAlignmentWindow` (`heatmap_alignment_gui.py`, ~5700 lines).

Session-load-responsiveness added reconcile-on-open and explicitly deferred dirty prompts. This change closes that gap without altering reconcile rules. Camera and H5 loads started by reconcile or `--session` complete asynchronously in `_apply_camera_job_result` / `_apply_h5_job_result`; dirty marking must not treat that completion as a user edit.

## Goals / Non-Goals

**Goals:**

- One dirty flag for the whole session (not per resource category).
- `*` in the window title when dirty.
- Tri-state prompts on Open Session (before file dialog), Close Session, and Quit when **dirty**.
- **Quit** when **clean**: no dialog.
- **Close Session** when **pristine and clean**: no dialog.
- **Close Session** when **clean but not pristine**: simple Yes/No confirm (unload resources and reset session path); not tri-state.
- Mark dirty only from **user-initiated** actions that change persisted session fields.
- **Do not** mark dirty from async resource job completion after session open, reconcile, or startup load.
- Clear dirty after successful save, successful open, and close-to-empty reset.
- `_session_dirty_guard()` for synchronous programmatic load/populate/reset (belt-and-suspenders with entry-point rule).
- Save Session enabled without requiring camera and H5 loaded in memory.
- GUI save path uses `allow_missing_sources=True` (consistent with core `save_alignment_session`).
- Clear All Resources keeps its existing confirm; mark dirty after success.

**Non-Goals:**

- JSON snapshot diff dirty detection (Option B); note in `ideas.md` only.
- Unsaved prompt before Clear All Resources (beyond existing confirm).
- Persisting timeline visible zoom/range or playhead `current_time_s` policy changes.
- “Save anyway” when structural validation fails (deferred to `ideas.md`).
- Refactoring `heatmap_alignment_gui.py` structure (noted in `ideas.md`).
- Changing reconcile keep/load/unload logic.

## Decisions

### 1. Dirty detection: explicit flag (Option A)

**Decision:** `self._session_dirty: bool` with `_mark_session_dirty()`, `_clear_session_dirty()`, and `_session_dirty_guard()` context manager (counter) for synchronous load/populate/close reset.

**Rationale:** Simple, testable, matches Qt patterns. Call sites are listed in `tasks.md`.

**Alternative:** Compare `session.to_json_dict()` to a baseline at prompt time. Documented in `ideas.md` for possible future hardening.

### 2. When to mark dirty (user-initiated only)

**Decision:** Call `_mark_session_dirty()` only from **user-initiated** code paths that change persisted `AlignmentSession` fields:

- Control/signal handlers (offset, render, viewport, export overlay, signal plot, datasource visibility/kind, etc.).
- Explicit user resource actions: file dialogs, Resources menu/window load/replace/unload/import, Clear All Resources after confirm.

**Do not** call `_mark_session_dirty()` from:

- `_apply_camera_job_result` / `_apply_h5_job_result` (async completion syncs metadata after load; same handlers serve reconcile, startup, and user load).
- `_reconcile_session_load`, `load_session_from_path` (after open), `_populate_controls_from_session`, or session reset after close.

**Rationale:** After Open Session or `--session`, jobs may finish seconds later and update `camera_track` / `heatmap_track` / viewport dimensions. Marking dirty on job completion would show `*` and spurious save prompts although the user did not edit anything relative to the file just opened.

**User-initiated resource load:** Mark dirty when the user starts a load/replace (e.g. at entry of `load_camera_from_path` / `load_h5_from_path` / import helpers) only when invoked from UI actions—not when called from reconcile.

### 3. Dirty semantics

**Decision:** Dirty means “the in-memory session differs from the last saved baseline” (last successful Save/Save As, successful Open, or new/closed pristine session).

**Not dirty:** Ephemeral UI such as timeline visible zoom/range (`timeline_range_model`).

**Out of scope for marking dirty:** `timeline.current_time_s` scrubbing/playback only.

### 4. Prompt placement and flow

**Open Session (dirty):** Tri-state **before** `QFileDialog`. Cancel aborts. Save → Save or Save As; on failure/cancel, abort open. Don't Save → file dialog → `load_session_from_path` if a file is chosen. If the user cancels the file dialog after Don't Save, the session **remains dirty** and unchanged.

**Open Session (clean):** File dialog only.

**Quit (dirty):** Tri-state, then exit on proceed.

**Quit (clean):** No dialog; existing teardown (`_close_sources`, etc.).

**Close Session (dirty):** Tri-state, then reset on proceed.

**Close Session (pristine and clean):** No dialog.

**Close Session (clean, not pristine):** Single Yes/No confirmation that the session will be closed and resources unloaded (no tri-state; nothing unsaved to save). Example title: **Close Session?** Body: **Close this session and unload all resources?**

**CLI `--session`:** No prompt on startup.

**Tests:** Direct `load_session_from_path` unprompted; tests should assert no dirty/`*` after open when jobs complete if session was not user-edited.

### 5. Prompt copy (conventional Qt / desktop editor style)

Avoid internal terms like “workbench”. Prefer **session** and **Heatmap Alignment**.

| Action | Title | Informative text |
|--------|-------|------------------|
| Quit (dirty) | Quit Heatmap Alignment? | There are unsaved changes. Do you want to save them before quitting? |
| Close Session (dirty) | Close Session? | There are unsaved changes. Do you want to save them before closing this session? |
| Open Session (dirty) | Open Another Session? | There are unsaved changes. Do you want to save them before opening another session? |
| Close Session (clean, not pristine) | Close Session? | Close this session and unload all resources? |

Buttons for tri-state: Save | Don't Save | Cancel (default **Save**).

### 6. Save policy (camera/H5 not special)

**Decision:**

- Remove the `camera_source` and `heatmap_source` in-memory requirement for enabling Save Session (Save remains available for normal use; dirty state drives unsaved prompts).
- `_write_session_to_path` SHALL call `validate_alignment_session(..., allow_missing_sources=True)` before `save_alignment_session`.

**Validation failures** (degenerate viewport, bad corner count, unsupported version): show “Cannot save session” with reason; abort the guarded action and leave the session dirty. No “save anyway” in v1 — see `ideas.md`.

### 7. Pristine session

**Decision:** `workbench_is_pristine()` when: no `_current_session_path`, no `camera_source`/`heatmap_source`, no peak/leg2 datasource objects, and session JSON equivalent to a fresh `AlignmentSession()` via a dedicated helper (e.g. `session_equivalent_for_pristine(a, b)` in core or GUI) so float/list fields compare reliably.

A saved session path with only JSON paths and no in-memory resources is **not** pristine.

### 8. Clear All Resources

**Decision:** Keep existing Yes/No confirmation. After successful clear, `_mark_session_dirty()`. No tri-state on Clear All in v1.

### 9. Resource replace

**Decision:** Mark dirty at user-initiated load/replace entry points; no extra save prompt on replace.

### 10. Quit with in-flight resource jobs

**Decision:** Unsaved prompt runs first when dirty; on proceed, existing abandon/close paths unchanged. No separate “job still loading” dialog in v1.

### 11. Central helper

**Decision:** `_prompt_save_discard_cancel(action: Literal["open", "close", "quit"]) -> Literal["save", "discard", "cancel"]` for dirty paths. `_confirm_close_session_clean()` (Yes/No) for clean non-pristine Close Session only.

## Risks / Trade-offs

- **[Missed user-initiated `_mark_session_dirty` call site]** → Checklist in `tasks.md`; optional snapshot baseline in `ideas.md`.
- **[Async open must not set dirty]** → Enforced by entry-point-only rule; add test that waits for job completion after `load_session_from_path`.
- **[Open: Save then load two-step failure]** → If Save cancelled or fails, do not open.
- **[Reconcile unchanged]** → Prompt before file dialog; Don't Save then load discards in-memory edits.

## Migration Plan

No data migration. Quit becomes silent when clean. Close Session: silent only when pristine+clean; clean non-pristine keeps a single confirm.

## Open Questions

_None for implementation; deferred items tracked in `ideas.md`._
