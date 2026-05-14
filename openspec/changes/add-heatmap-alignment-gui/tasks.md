## 1. Shared Rendering Foundation

- [ ] 1.1 Extract reusable Sparse IQ heatmap loading, selection, DVM computation, distance/velocity axis, and color-limit rendering helpers from `user_tools/export_sparse_iq_heatmap_video.py`.
- [ ] 1.2 Update `user_tools/export_sparse_iq_heatmap_video.py` to use the shared helpers while preserving its CLI options and output behavior.
- [ ] 1.3 Add focused tests or smoke checks for H5 selection defaults, DVM calculation shape, and exporter compatibility where feasible.

## 2. Alignment Data Model

- [ ] 2.1 Define alignment session dataclasses for camera track, H5 heatmap track, shared timeline state, viewport geometry, render settings, preprocessing settings, and artifact version.
- [ ] 2.2 Implement JSON save/load for alignment artifacts, including source paths, selected H5 session/group/entry/subsweep, color limits, viewport corners, output dimensions, and offset seconds.
- [ ] 2.3 Add validation for missing paths, malformed artifacts, invalid quadrilaterals, and incompatible artifact versions.

## 3. Video And Heatmap Frame Services

- [ ] 3.1 Implement OpenCV-backed camera video metadata loading, frame lookup by physical seconds, and RGB frame conversion.
- [ ] 3.2 Implement H5 heatmap frame lookup by physical seconds using recording ticks and nearest-frame selection.
- [ ] 3.3 Implement viewport rectification from camera-frame quadrilateral to rendered heatmap dimensions.
- [ ] 3.4 Add lightweight frame caching for camera frames, rectified viewport frames, and rendered H5 heatmap frames.

## 4. PySide6 GUI

- [ ] 4.1 Create a standalone PySide6 entry point in `user_tools/` for the alignment workbench.
- [ ] 4.2 Build camera video, rectified viewport, and rendered heatmap preview panels.
- [ ] 4.3 Add interactive viewport corner handles on the camera preview with drag updates to the rectified viewport.
- [ ] 4.4 Add load/save actions for camera video, H5 recording, and alignment artifact files.
- [ ] 4.5 Add color min/max controls for the H5-rendered heatmap with immediate preview updates.

## 5. Timeline And Playback

- [ ] 5.1 Implement a shared seconds-based timeline with current-time marker, track offset state, and scrub controls.
- [ ] 5.2 Add manual temporal nudge controls that update the camera-to-H5 offset in seconds.
- [ ] 5.3 Add basic synchronized playback controls for advancing camera, rectified viewport, and rendered heatmap previews without MVP audio playback.
- [ ] 5.4 Ensure scrubbing and playback use physical seconds rather than frame-index offsets.

## 6. Xcorr Diagnostics

- [ ] 6.1 Implement dense RGB preprocessing for xcorr diagnostics, including global sequence normalization and optional blur/downscale settings.
- [ ] 6.2 Compute correlation scores over a local lag range around the current offset without changing the stored offset.
- [ ] 6.3 Display the xcorr curve and current-offset marker in the GUI.

## 7. Verification

- [ ] 7.1 Verify the workbench can load a representative camera video and H5 recording, define a viewport, and show comparable rectified/truth previews.
- [ ] 7.2 Verify saved artifacts can be reloaded to reproduce viewport geometry, render settings, and offset seconds.
- [ ] 7.3 Verify exporter behavior still works after shared-renderer refactoring.
- [ ] 7.4 Document launch command and MVP limitations in the tool help text or repository documentation.
