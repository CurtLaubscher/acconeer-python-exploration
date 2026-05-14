## Context

The repository already contains a standalone Sparse IQ heatmap video exporter in `user_tools/export_sparse_iq_heatmap_video.py` and uses PySide6 throughout the application stack. The new tool is intended for local research workflows where a tripod camera video contains a monitor displaying a radar heatmap, and the user wants to align that video with the underlying H5 radar recording.

The MVP is a human-in-the-loop alignment workbench, not an automatic alignment solver. It should make geometry, timing, and color/render settings visible and adjustable, then persist those choices as a reusable artifact.

## Goals / Non-Goals

**Goals:**

- Provide a standalone PySide6 GUI in `user_tools/`.
- Model the camera video and H5-rendered heatmap as two tracks on one physical-seconds timeline.
- Render the heatmap truth directly from H5 data using shared logic with the existing Sparse IQ heatmap exporter.
- Let the user define one fixed four-corner camera viewport for a stationary tripod video.
- Rectify the camera viewport to the same pixel size and aspect ratio as the rendered heatmap.
- Support manual temporal alignment, scrubbing, playback preview, fine nudging, and xcorr diagnostics.
- Save and load JSON alignment artifacts.

**Non-Goals:**

- Automatically changing the alignment based on xcorr in the MVP.
- Supporting more than two tracks in the MVP.
- Supporting moving-camera/keyframed viewport geometry in the MVP.
- Exporting combined videos in the MVP.
- Playing camera audio in the MVP.
- Inverse colormap recovery from camera video.

## Decisions

### Use PySide6 for the GUI

The tool will use PySide6 because the project already depends on and pins PySide6. This keeps the tool in the Python/Qt ecosystem already used by the repository and avoids adding a browser frontend stack for draggable geometry and playback controls.

Alternatives considered: a browser UI with a Python backend would be strong for canvas-heavy interactions but introduces another frontend architecture; Streamlit or Gradio would be faster to scaffold but are weaker for precise corner dragging and synchronized timeline interaction.

### Use H5 rendering as the truth source

The generated/truth heatmap will be rendered from the raw H5 recording rather than loaded from a previously exported video. This allows color min/max changes, sensor/subsweep selection, and frame timing to remain controlled by the tool.

Alternatives considered: loading the exported heatmap video would be simpler initially but would make the workflow depend on a pre-rendered asset and would prevent on-the-fly render setting changes.

### Extract shared heatmap logic

Shared Sparse IQ heatmap computations should be moved out of `export_sparse_iq_heatmap_video.py` into a helper module when doing so avoids duplication. The exporter and GUI should use the same distance/velocity map calculation and H5 selection behavior.

Alternatives considered: duplicating the renderer in the GUI would be faster but risks future drift between the exporter and the alignment workbench.

### Store time alignment in seconds

The session artifact will store temporal alignment as physical seconds, not frame indices. Camera video, H5 radar data, and future sources can then use their own sampling rates while still sharing one alignment model.

Alternatives considered: frame-index offsets are simpler for two constant-frame-rate videos but break down when camera video is VFR, radar FPS differs, or future non-video sources are added.

### Use one fixed quadrilateral per camera video

The MVP assumes a stationary tripod camera. The camera viewport is one four-corner polygon drawn on the source camera frame. The rectified viewport is derived from that single source of truth.

Alternatives considered: per-frame or keyframed viewport geometry would support camera motion but would substantially expand the UI and artifact model.

### Compare dense rendered images, not lattice bins

The MVP should avoid hard bin discretization and inverse colormap recovery. Xcorr diagnostics should compare the rectified camera heatmap and rendered truth heatmap as dense RGB images after configurable preprocessing such as resizing, cropping, normalization, or blur.

Alternatives considered: per-bin averaging could denoise the camera video but is sensitive to small grid misalignment; inverse colormap recovery is brittle under monitor/camera gamma, color balance, compression, and blur.

## Risks / Trade-offs

- Camera video decoding and frame seeking can be slow or inconsistent across codecs -> use OpenCV for MVP, cache recently viewed frames, and keep the artifact independent of decoded frame indices.
- H5 rendering may become expensive during scrubbing -> render on demand with caching and keep preview resolution bounded by the truth heatmap size.
- Corner dragging may be imprecise on high-resolution videos -> provide direct manipulation plus nudge controls or numeric corner editing if needed.
- Xcorr may be misleading under bad color limits, glare, or blur -> display it as a diagnostic only in the MVP and keep manual visual alignment as the authority.
- Shared renderer refactoring could disturb the existing exporter -> keep refactoring narrow and preserve exporter CLI behavior.

## Migration Plan

This is a new standalone utility and does not require migration. Existing exporter behavior should remain compatible. If shared rendering helpers are introduced, validate that `export_sparse_iq_heatmap_video.py` still accepts the same arguments and produces equivalent output for representative H5 input.

## Open Questions

- Which JSON schema/version field should be used for alignment artifacts?
- Which xcorr preprocessing controls should be exposed in the first UI beyond color min/max and optional blur/downscale?
