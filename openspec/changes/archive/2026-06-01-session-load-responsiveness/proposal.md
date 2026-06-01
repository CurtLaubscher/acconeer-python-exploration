## Why

Opening or re-opening an alignment session can make the workbench feel frozen for several seconds, especially when the user loads the same session again while camera proxy or H5 resource jobs from the prior open are still running. Session open currently always tears down active resources (`_close_sources`), abandons in-flight jobs, and reloads every referenced file from scratch—even when the session’s resource paths and H5 selection are unchanged. Proxy generation now works again, so cold proxy builds and redundant reloads are visible again. This change keeps the GUI responsive during session load without a dedicated loading window.

## What Changes

- Replace unconditional `_close_sources()` on Open Session with **session snapshot reconciliation**: derive desired resource state from the loaded session JSON, compare each known resource slot to active workbench state, and run **keep** (skip redundant reload), **load/replace**, or **unload** per slot.
- **Keep** camera or H5 slots when resource identity already matches what is loaded or in-flight; do not abandon in-flight jobs for the same identity.
- **Unload** optional or primary resources when the new session omits or clears a path but that resource remains loaded (prevents stale peak JSON, Leg2 MAT, or future slots from leaking across session opens).
- **Always** apply non-resource session fields from JSON (viewport, offsets, render, timeline, export overlay, signal plot view, datasource visibility, etc.) after resource reconciliation, including when resource reloads are skipped.
- Centralize reconciliation over a **registered set of resource slots** (camera, H5, peak JSON, Leg2 MAT) so adding a future datasource requires one registry entry rather than ad hoc session-open logic.
- **Unload** camera and H5 when the new session omits those paths, using the same unload entry points as the Resources window (not leaving prior-session media active).
- Keep **Leg2 MAT and peak JSON** on the existing synchronous import path for this change (no new background jobs for those types).
- **CLI startup (scope B):** show the main window promptly, then schedule session load on the event loop so startup does not block painting before the first frame.
- Use existing **Resources** row/job presentation for loading state; no modal “loading session” dialog.
- **Non-goals:** dirty-session prompts before open; moving Leg2/peak to background jobs; H5 cooperative cancel inside `fixed_color_level`; batch session loading; full UI-state diff beyond session dataclass and resource slots.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `heatmap-alignment-gui`: Session load reconciliation (keep/load/unload per slot), GUI responsiveness during open/re-open, CLI window visibility before session load completes.

## Impact

- `user_tools/heatmap_alignment_gui.py` — session reconcile orchestration, resource job interaction, `main()` startup ordering.
- `user_tools/heatmap_alignment_core.py` — helpers to derive desired resource state and compare identities.
- Tests under `tests/user_tools/` for reconcile actions, unload-on-clear, skip in-flight jobs, and startup scheduling.
