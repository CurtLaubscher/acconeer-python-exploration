## Context

The repository already contains a standalone Sparse IQ heatmap video exporter in `user_tools/export_sparse_iq_heatmap_video.py` and uses PySide6 throughout the application stack. The new tool is intended for local research workflows where a tripod camera video contains a monitor displaying a radar heatmap, and the user wants to align that video with the underlying H5 radar recording.

The MVP is a human-in-the-loop alignment workbench, not an automatic alignment solver. It should make geometry, timing, and color/render settings visible and adjustable, then persist those choices as a reusable session file.

Status note: this change has reached MVP acceptance after live use across representative trials. Proxy-backed playback is accepted for MVP, xcorr is deferred, and synced video export is implemented and verified against representative data.

## Goals / Non-Goals

**Goals:**

- Provide a standalone PySide6 GUI in `user_tools/`.
- Model the camera video and H5-rendered heatmap as two tracks on one physical-seconds timeline.
- Render the heatmap truth directly from H5 data using shared logic with the existing Sparse IQ heatmap exporter.
- Let the user define one fixed four-corner camera viewport for a stationary tripod video.
- Rectify the camera viewport to the current viewport display resolution for human inspection.
- Support manual temporal alignment, scrubbing, playback preview, fine nudging, and session persistence.
- Support exporting a synced video with a plotted H5 heatmap overlay composited onto the original-resolution camera footage.
- Save and load JSON alignment session files.

**Non-Goals:**

- Automatically changing the alignment based on xcorr in the MVP.
- Supporting more than two tracks in the MVP.
- Supporting moving-camera/keyframed viewport geometry in the MVP.
- Playing camera audio in the MVP.
- Inverse colormap recovery from camera video.
- Full-resolution 4K GUI playback or background high-quality proxy generation in the MVP.
- Automatic xcorr alignment in the MVP.

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

The alignment session file will store temporal alignment as physical seconds, not frame indices. Camera video, H5 radar data, and future sources can then use their own sampling rates while still sharing one alignment model.

Alternatives considered: frame-index offsets are simpler for two constant-frame-rate videos but break down when camera video is VFR, radar FPS differs, or future non-video sources are added.

### Use one fixed quadrilateral per camera video

The MVP assumes a stationary tripod camera. The camera viewport is one four-corner polygon drawn on the source camera frame. The rectified viewport is derived from that single source of truth.

Alternatives considered: per-frame or keyframed viewport geometry would support camera motion but would substantially expand the UI and artifact model.

### Compare dense rendered images, not lattice bins

The MVP should avoid hard bin discretization and inverse colormap recovery. Xcorr diagnostics should compare the rectified camera heatmap and rendered truth heatmap as dense RGB images after configurable preprocessing such as resizing, cropping, normalization, or blur.

Alternatives considered: per-bin averaging could denoise the camera video but is sensitive to small grid misalignment; inverse colormap recovery is brittle under monitor/camera gamma, color balance, compression, and blur.

### Keep xcorr disabled in the v1 GUI

Early GUI testing showed that eager xcorr computation dominated H5 load time because it repeatedly sought and decoded camera frames. The core xcorr prototype can remain for future work, but the MVP defers xcorr and keeps the GUI xcorr controls disabled as a placeholder. Manual visual alignment is the authority for MVP.

### Use an app-managed preview proxy for GUI camera playback

The real camera video is 3840x2160 at about 60 fps. Live GUI interaction does not require full 4K decode cost on every preview refresh, so the current implementation generates or reuses a disposable local proxy video capped to a bounded preview resolution and opens that proxy for camera playback and scrubbing. The session file still stores the original camera-video path, not the proxy path. Existing session files with full-resolution corners are adapted to preview coordinates on load using the original source dimensions.

This is a v1 GUI trade-off: it improves responsiveness and keeps memory bounded, but it means saved viewport coordinates are preview-space coordinates. A future high-quality export or background 4K viewport renderer should explicitly map preview-space geometry back to source video coordinates.

### Drive playback from wall-clock time

Playback must use elapsed wall-clock time to decide the current video time. Timer callbacks are refresh opportunities, not the source of truth for media time. If rendering falls behind, the GUI should skip displayed frames instead of slowing the aligned timeline.

The current playback path also uses OpenCV `grab()` for skipped source frames and decodes only the displayed target frame. This avoids resizing/converting intermediate source frames that are never shown.

### Show alignment with compact timeline bars

The MVP should make temporal alignment visible with a compact two-track timeline. The H5 heatmap track is the fixed reference bar. The camera track is the draggable bar. Dragging the camera bar horizontally changes the stored camera-to-H5 offset, while dragging the playhead changes the current shared time. Existing numeric offset and nudge controls remain the precision path.

The first implementation should stay intentionally narrow: one fit-all shared time axis, row labels for `Camera` and `H5`, simple tick marks, and a vertical playhead. Zoom/pan and translucent overlap shading are deferred until live testing shows they are needed.

### Export synced video with a separate overlay rectangle

The export overlay is separate from the camera viewport quadrilateral. The viewport defines where the monitor heatmap appears in the camera footage for alignment. The export overlay defines where a rendered H5 heatmap plot should be composited in the final synced video.

The overlay should be an axis-aligned rectangle in preview-space coordinates, persisted in the alignment session with visibility and preview-render flags. The user can drag the center to move it, drag corners to resize both dimensions relative to the opposite corner, and drag edges to resize one dimension. The rectangle is intentionally not perspective-aware and does not preserve aspect ratio, because distance/velocity bin geometry and axis-label needs can vary across recordings.

The camera preview should be able to show or hide the overlay rectangle independently from showing or hiding a low-quality plotted heatmap preview inside that rectangle. If the overlay is hidden, the tool should not render the overlay preview. While the overlay rectangle is being dragged, freezing the preview plot is acceptable for MVP responsiveness.

Export should reopen and sample the original-resolution camera video rather than the GUI proxy. The overlay rectangle should be scaled from preview coordinates to original camera coordinates at export time. The exported video should cover exactly the H5 duration, use the higher of camera FPS and H5 FPS, render the H5 heatmap as a Matplotlib plot with axes/labels using a reused figure/canvas, and composite that plot into the scaled overlay rectangle. For each output frame, use `camera_time = h5_time + offset_s`; if that time is before or after the camera video, hold the nearest first or last camera frame.

Export can be synchronous for MVP if the GUI shows a busy/progress state, disables duplicate export starts, and keeps the user informed that export is running.

## Risks / Trade-offs

- Camera video decoding and frame seeking can be slow or inconsistent across codecs -> use OpenCV sequential playback on a cached local proxy video, skip undisplayed frames with `grab()`, and keep the session independent of decoded frame indices.
- H5 rendering may become expensive during scrubbing -> render on demand with caching; current real-file testing shows H5 rendering is not the dominant playback cost.
- Corner dragging may be imprecise on high-resolution videos -> provide direct manipulation plus nudge controls or numeric corner editing if needed.
- Xcorr may be misleading or expensive under bad color limits, glare, blur, or slow camera access -> keep manual visual alignment as the authority and avoid automatic xcorr in v1.
- Shared renderer refactoring could disturb the existing exporter -> keep refactoring narrow and preserve exporter CLI behavior.
- Preview-space geometry is not enough for future high-quality export -> future export/proxy work must map viewport corners between preview and source-video coordinate systems.
- Proxy generation adds one-time startup cost for a new video -> keep proxies in a deterministic local cache keyed by source path, file size, modification time, and proxy settings so subsequent loads are fast.
- Exporting from original-resolution camera footage can be slow -> show progress/busy state and keep GUI preview/export rendering paths separate.

## Migration Plan

This is a new standalone utility and does not require migration. Existing exporter behavior should remain compatible. If shared rendering helpers are introduced, validate that `export_sparse_iq_heatmap_video.py` still accepts the same arguments and produces equivalent output for representative H5 input.

## Post-MVP Considerations

- Should session schema version 1 remain preview-coordinate based, or should it be revised before archive to store both preview and source-video geometry?
- Does the initial two-track timeline need zoom/pan or overlap shading after live testing, or are duration bars plus playhead sufficient?
- Is the exported plotted heatmap styling legible enough at the default lower-left overlay size, or does MVP need explicit font/label scaling controls?
