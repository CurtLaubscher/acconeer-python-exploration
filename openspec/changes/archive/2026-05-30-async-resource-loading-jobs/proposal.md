## Why

Loading camera videos currently blocks the heatmap alignment GUI while preview proxies are generated, which measured at roughly 10-46 seconds per video for the current multi-trial dataset. H5 loading can also block the UI for several seconds, making repeated manual trial alignment feel slow and unresponsive.

## Status

Initial async resource loading landed on branch `claub/async-resource-loading-jobs` in commit `51fc67ce`, followed by review-correction work for lifecycle, viewport, H5-handoff, waiting-state, and test coverage gaps. Sections 1–8 on branch `claub/async-resource-loading-jobs-clean` are complete. Section 9 documents pre-archive corrections from branch review (export semantics after failed replacement restore, worker shutdown hardening, H5 worker cleanup, and resource-job type cleanup).

## What Changes

- Add a background resource job model for heavy resource preparation work in the heatmap alignment GUI.
- Load or prepare Camera Video and Radar Raw (H5) resources without freezing the main UI.
- Treat preview proxy generation as a camera resource job and show camera loading/proxy-building state until the low-quality proxy is ready.
- Allow different resource types to load concurrently when they do not conflict, while preserving bounded concurrency for expensive work.
- Make same-resource replacement use latest-request-wins behavior: a new load request supersedes any pending load for that resource type and should actively cancel in-flight superseded work when possible so the newest request is not blocked behind discarded proxy or H5 preparation.
- Keep the previously active resource in effect until a replacement resource successfully loads; restore the previous preview/state if replacement fails.
- Update the Resources window and affected preview panels to show loading, waiting, failure, and cancellation state with target filenames.
- Automatically unload Radar Peak (JSON) when a different Radar Raw (H5) resource successfully replaces the current H5.
- Keep synced video export modal/synchronous behavior out of scope for this change; starting export is disabled while required camera or H5 resources are in an in-flight load/replace/cancel phase, but not solely because the last load attempt failed after the previous active resources were restored.
- Cancel or abandon active camera/H5 resource jobs safely on window close and session close so late completions cannot repopulate a reset workbench.
- Defer batch preparation, export job conversion, unsaved-session prompts, in-app peak calculation, and background MAT/peak JSON loading to future changes; peak JSON and Leg2 MAT remain synchronous imports for this change except where H5 replacement clearing requires peak unload.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `heatmap-alignment-gui`: Add asynchronous resource job behavior for camera and H5 loading, resource replacement semantics, loading-state presentation, and export availability while resources are loading.

## Impact

- Affected code: `user_tools/heatmap_alignment_gui.py`, `user_tools/heatmap_alignment_core.py`, and focused GUI/core tests under `tests/user_tools/`.
- Affected UI: Resources window rows/actions, camera preview panel, rendered heatmap panel, resource load/reload/replace actions, export action enablement.
- No new runtime dependencies are expected; implementation should use existing PySide6/Qt threading or process primitives already available in the app environment.
- Existing session JSON format should remain compatible. Session resource paths should update only after replacement loads succeed.
