## Why

Loading camera videos currently blocks the heatmap alignment GUI while preview proxies are generated, which measured at roughly 10-46 seconds per video for the current multi-trial dataset. H5 loading can also block the UI for several seconds, making repeated manual trial alignment feel slow and unresponsive.

## What Changes

- Add a background resource job model for heavy resource preparation work in the heatmap alignment GUI.
- Load or prepare Camera Video and Radar Raw (H5) resources without freezing the main UI.
- Treat preview proxy generation as a camera resource job and show camera loading/proxy-building state until the low-quality proxy is ready.
- Allow different resource types to load concurrently when they do not conflict, while preserving bounded concurrency for expensive work.
- Make same-resource replacement use latest-request-wins behavior: a new load request supersedes any pending load for that resource type.
- Keep the previously active resource in effect until a replacement resource successfully loads; restore the previous preview/state if replacement fails.
- Update the Resources window and affected preview panels to show loading, waiting, failure, and cancellation state with target filenames.
- Automatically unload Radar Peak (JSON) when a different Radar Raw (H5) resource successfully replaces the current H5.
- Keep synced video export modal/synchronous behavior out of scope for this change; export remains unchanged except that starting export is disabled while required camera or H5 resources are loading or replacing.
- Defer batch preparation, export job conversion, unsaved-session prompts, and in-app peak calculation to future changes.

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
