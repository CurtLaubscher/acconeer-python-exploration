## 1. Shared Rendering Foundation

- [x] 1.1 Extract reusable Sparse IQ heatmap loading, selection, DVM computation, distance/velocity axis, and color-limit rendering helpers from `user_tools/export_sparse_iq_heatmap_video.py`.
- [x] 1.2 Update `user_tools/export_sparse_iq_heatmap_video.py` to use the shared helpers while preserving its CLI options and output behavior.
- [x] 1.3 Add focused tests or smoke checks for H5 selection defaults, DVM calculation shape, and exporter compatibility where feasible.

## 2. Alignment Data Model

- [x] 2.1 Define alignment session dataclasses for camera track, H5 heatmap track, shared timeline state, viewport geometry, render settings, preprocessing settings, and artifact version.
- [x] 2.2 Implement JSON save/load for alignment sessions, including source paths, selected H5 session/group/entry/subsweep, color limits, viewport corners, output dimensions, and offset seconds.
- [x] 2.3 Add validation for missing paths, malformed sessions, invalid quadrilaterals, and incompatible session versions.

## 3. Video And Heatmap Frame Services

- [x] 3.1 Implement OpenCV-backed camera video metadata loading, frame lookup by physical seconds, and RGB frame conversion.
- [x] 3.2 Implement H5 heatmap frame lookup by physical seconds using recording ticks and nearest-frame selection.
- [x] 3.3 Implement viewport rectification from camera-frame quadrilateral to the current viewport display dimensions.
- [x] 3.4 Add lightweight frame caching for camera frames and rendered H5 heatmap frames.
- [x] 3.5 Add low-resolution camera preview frames for v1 GUI interaction instead of full-4K GUI frames.
- [x] 3.6 Optimize sequential playback by using OpenCV `grab()` for skipped source frames and decoding only displayed frames.

## 4. PySide6 GUI

- [x] 4.1 Create a standalone PySide6 entry point in `user_tools/` for the alignment workbench.
- [x] 4.2 Build camera video, rectified viewport, and rendered heatmap preview panels.
- [x] 4.3 Add interactive viewport corner handles on the camera preview with drag updates to the rectified viewport.
- [x] 4.4 Add load/save actions for camera video, H5 recording, and alignment session files.
- [x] 4.5 Add color min/max controls for the H5-rendered heatmap with immediate preview updates.
- [x] 4.6 Add draggable viewport edges and center-region translation in the camera preview.
- [x] 4.7 Add viewport-side corner, edge, and center dragging for fine geometry adjustments.
- [x] 4.8 Add horizontal splitter resizing between camera and comparison previews.
- [x] 4.9 Add basic application menu and quit action.
- [x] 4.10 Remember last-used load/save directories without auto-restoring sessions on startup.
- [x] 4.11 Improve preview rendering/interaction polish after live testing feedback.

## 5. Timeline And Playback

- [x] 5.1 Implement a shared seconds-based timeline with current-time marker, track offset state, and scrub controls.
- [x] 5.2 Add manual temporal nudge controls that update the camera-to-H5 offset in seconds.
- [x] 5.3 Add basic synchronized playback controls for advancing camera, rectified viewport, and rendered heatmap previews without MVP audio playback.
- [x] 5.4 Ensure scrubbing and playback use physical seconds rather than frame-index offsets.
- [x] 5.5 Use wall-clock playback timing so slow refreshes skip displayed frames instead of slowing the video clock.
- [x] 5.6 Evaluate and improve remaining playback jitter using an app-managed proxy-video cache for GUI playback and scrubbing.
- [x] 5.7 Add a compact two-track timeline view with H5 fixed, camera draggable, shared time ticks, and a playhead; defer zoom/pan and overlap shading until after live testing.

## 6. Xcorr Diagnostics

- [x] 6.1 Prototype dense RGB preprocessing and xcorr diagnostics in core code.
- [x] 6.2 Disable GUI xcorr execution for v1 after performance testing showed it was too expensive on load.
- [x] 6.3 Decide whether MVP requires a lightweight xcorr display, a manual-only placeholder, or defers xcorr entirely to future work.

## 7. Synced Video Export

- [x] 7.1 Add export overlay session state with visible/preview flags and preview-space rectangle coordinates.
- [x] 7.2 Add an adjustable export overlay rectangle on the camera preview, with center drag to move, corner drag to resize both axes, edge drag to resize one axis, and right-click show/hide/reset actions.
- [x] 7.3 Render a low-quality plotted heatmap preview with axes into the export overlay when overlay preview is enabled, freezing the rendered preview while the overlay rectangle is being dragged.
- [x] 7.4 Add an `Export Synced Video` action that composites a plotted H5 heatmap with axes over the original-resolution camera video for exactly the H5 duration.
- [x] 7.5 During export, output at the higher of camera FPS and H5 FPS, sample camera frames at `h5_time + offset_s`, and hold the closest first/last camera frame when the requested camera time is outside camera coverage.
- [x] 7.6 Show export progress/busy state and prevent duplicate export starts while export is running.

## 8. Verification

- [x] 8.1 Verify the workbench can load a representative camera video and H5 recording, define a viewport, and show comparable rectified/truth previews.
- [x] 8.2 Verify saved sessions can be reloaded to reproduce viewport geometry, render settings, and offset seconds.
- [x] 8.3 Verify exporter behavior still works after shared-renderer refactoring.
- [x] 8.4 Document launch command and MVP limitations in the tool help text or repository documentation.
- [x] 8.5 Add AGENTS guidance to use Hatch-managed environments and keep `pyproject.toml` as the source of truth for dependencies and scripts.
- [x] 8.6 Add Hatch app dependency/script updates for OpenCV and `heatmap-align`.
- [x] 8.7 Re-test the live GUI against the real camera/H5 pair after proxy-cache playback and export-overlay changes.
- [x] 8.8 Export a representative synced video and verify duration, overlay placement, axis labels, offset handling, and first/last camera-frame hold behavior.
- [x] 8.9 Update final OpenSpec requirements before archive so accepted MVP behavior matches implementation.
