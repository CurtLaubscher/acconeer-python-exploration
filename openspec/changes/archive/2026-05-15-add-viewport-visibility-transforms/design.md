## Context

The heatmap alignment workbench currently rectifies the selected camera viewport and shows it next to the rendered H5 heatmap. In real trial usage, the camera-captured monitor heatmap can be hard to read because camera exposure, monitor brightness, glare, compression, and color response make the viewport visually different from the rendered truth.

This change adds lightweight viewport visibility transforms for manual comparison. It does not reintroduce xcorr. The goal is to make the human alignment task easier and to establish a better visual preprocessing path if xcorr is revisited later.

The first implementation of viewport transforms is fast enough, but live evaluation showed that transform quality is hard to assess when the viewport frame itself comes from the low-resolution proxy preview. This change is therefore broadened to include a paused source-resolution viewport preview rendered from the original camera video, plus native original-video coordinate storage for viewport geometry.

## Goals / Non-Goals

**Goals:**

- Provide a simple raw/enhanced toggle for the rectified viewport preview.
- Make low-contrast camera-captured heatmap structure easier to see.
- Keep the raw viewport view available.
- Persist enhancement enabled state and tuning values in alignment sessions.
- Keep transforms fast enough for scrubbing and playback preview.
- Store viewport geometry in original camera pixel coordinates.
- Provide an automatic source-resolution viewport preview after the viewport state has been idle briefly.
- Keep the source-resolution preview path responsive by invalidating stale work immediately and only accepting the latest result.

**Non-Goals:**

- Automatically aligning time or geometry.
- Re-enabling xcorr in this change.
- Changing exported synced video behavior.
- Changing the rendered H5 truth heatmap color controls.
- Adding grayscale or edge modes in the first implementation.
- Adding a broad image-processing workbench with many advanced controls.
- Building a general frame cache, predecode system, or source-resolution playback pipeline.
- Rendering source-resolution viewport frames while playback is active.
- Providing a visible source-resolution-render status indicator in the first implementation.

## Decisions

### Use a single enhancement toggle instead of transform modes

The UI should expose one primary `Enhance Viewport` toggle. When disabled, the viewport preview uses the raw rectified camera frame and the enhancement tuning controls are disabled. When enabled, the viewport preview uses the current enhancement settings.

This makes raw/enhanced comparison quick and keeps the mental model simpler than mutually exclusive modes. The user can tune one enhanced view and temporarily disable it without losing the chosen tuning values.

Alternatives considered: a mode selector with raw, contrast, grayscale, and edge views would be flexible but less directly tied to the real goal of making the viewport resemble the rendered viridis heatmap. Edge and grayscale modes may still be useful later, but they are not the first implementation target.

### Tune luminance first, then optionally map to viridis

The enhanced view should first apply low/high/gamma correction to the viewport image. The corrected image should preserve the original viewport colors when viridis mapping is disabled. When `Map to Viridis` is enabled, the implementation should compute corrected luminance and use that 1D scalar to look up viridis RGB values.

Initial tuning:

- `Low`: lower range handle for viewport intensity correction.
- `High`: upper range handle for viewport intensity correction.
- `Gamma`: curve control for viewport intensity correction.
- `Map to Viridis`: optional toggle that displays corrected luminance through the viridis ramp.

The conceptual transform is:

```text
corrected_rgb = clamp((camera_rgb - low) / (high - low), 0, 1) ** gamma
if map_to_viridis:
    scalar = luminance(corrected_rgb)
    enhanced_rgb = viridis(scalar)
else:
    enhanced_rgb = corrected_rgb
```

The low/high controls should be draggable range handles rather than typed-only numeric fields, because the user is tuning by eye during alignment.

Alternatives considered: nearest-color inverse projection onto the viridis ramp is conceptually direct but was measured to be far too slow when implemented per pixel. A cached 3D color lookup table would be faster, but a luminance-first 1D transform is simpler, much cheaper, and closer to the user's intent of correcting intensity before optional palette mapping. Inverse colormap recovery can still be revisited later if real data shows luminance mapping is insufficient.

### Place viewport controls near the viewport preview

Viewport enhancement controls should be visually associated with the `Viewport` preview rather than mixed into rendered heatmap color controls. This reduces ambiguity: the controls affect the rectified camera viewport only, not the camera source view, rendered H5 heatmap, or synced video export overlay.

Alternatives considered: keeping controls in the existing `Render` group is simpler, but that group already mixes H5 color limits, disabled xcorr/preprocess controls, and preview-related settings.

### Apply transforms only to the rectified viewport preview

Transforms should operate after rectification, on the viewport preview frame, not on the source camera view. The source camera remains the place for geometry editing, while the viewport preview is the place for visual comparison.

Alternatives considered: transforming the camera source view would make geometry handles harder to interpret and would conflate source inspection with comparison rendering.

### Store viewport geometry in original camera coordinates

Viewport corners should be stored in original camera pixel coordinates. The proxy/display preview should map those native corners into the displayed camera coordinate space for drawing and hit testing. Low-resolution live viewport rendering should scale the native corners down to the current display/proxy camera frame before rectifying that frame. Source-resolution viewport rendering should use the native corners directly against the original camera frame.

This gives one authoritative geometry coordinate space and makes source-resolution preview/export extensions less fragile. It also avoids accumulating future features on top of proxy-resolution coordinates.

Known saved sessions from the early MVP period are limited to a small number of JSON files, so this change may handle those pragmatically with manual correction rather than a broad migration system.

Alternatives considered: keeping proxy-coordinate session geometry and scaling only inside the source-resolution worker would be smaller, but it preserves an imprecise model and makes later original-resolution features harder to reason about.

### Keep camera-video dragging display-local

The camera-video quadrilateral editor should keep its drag math in the currently displayed camera image coordinate space. For center and edge drags, it should capture the cursor position and corners at mouse press, then compute each mouse-move frame from:

```text
delta = cursor_current - cursor_start
new_corners = start_corners + bounded_delta
```

The widget should emit updated displayed-image corners, and the main window should convert those displayed corners back to native original-video coordinates. This keeps the interaction intuitive in the camera panel while preserving the native-coordinate session model.

The camera-video editor should not accumulate deltas across mouse moves or apply the same delta twice. Corner dragging may remain direct-to-current-cursor because the user is placing one visible handle.

### Render source-resolution viewport after idle

The GUI should continue showing the fast low-resolution/proxy viewport immediately during scrubbing, playback, and geometry interaction. When viewport-relevant state changes, the GUI should immediately invalidate any pending source-resolution result, clear the source-resolution display source, show the low-resolution viewport, and restart a short debounce timer. If the state remains idle for approximately 200 ms and playback is not active, a background worker should render a source-resolution rectified viewport from the original camera video. The output image should remain sized for the current viewport preview; "source-resolution" refers to the input camera frame used before warping, not a large display image.

The worker result should be accepted only if it still matches the latest request token and relevant state. If a newer request exists, the old result should be ignored. The implementation should not attempt to forcibly kill an in-flight OpenCV decode/warp; latest-request-wins tokening is the cancellation model.

Playback state transitions should flow through a centralized helper or similarly controlled path. Starting playback should invalidate source-resolution viewport work immediately. Stopping playback should allow source-resolution scheduling through the same viewport refresh/debounce path used by other viewport-relevant updates.

The conceptual flow is:

```text
viewport-relevant update
    -> increment request token immediately
    -> clear source-resolution viewport result
    -> show low-resolution viewport immediately
    -> restart 200 ms debounce timer

debounce fires while paused
    -> worker opens/uses original camera source
    -> worker decodes current camera frame
    -> worker warps native-coordinate viewport
    -> GUI accepts result only if request token still matches
```

Viewport-relevant updates include shared time changes, offset changes, viewport geometry changes, camera source changes, and viewport output size changes. The implementation should centralize scheduling around the existing viewport preview refresh path where practical, instead of duplicating special-case scheduling in every input handler.

Alternatives considered: a manual `Render Source Frame` button would be simpler but less ergonomic during alignment. A full background frame cache or predictive predecode system is more powerful but beyond the current need.

### Apply enhancement after selecting preview source

Viewport visibility transforms should apply after the GUI chooses which rectified viewport frame to display. If a current source-resolution viewport result is available, enhancement applies to that frame. Otherwise, enhancement applies to the low-resolution/proxy viewport frame. This keeps enhancement semantics stable and lets the user evaluate the same transform against the best available viewport source.

### Persist settings in the alignment session

The enhancement enabled state and tuning values should be saved with the session so reloading a session reproduces the same comparison view. Existing sessions should load with defaults equivalent to current raw behavior.

Viewport geometry should also roundtrip in the native original-video coordinate model once this broadened change is implemented.

Alternatives considered: keeping transforms as UI-only state would be simpler but would make saved alignment work less reproducible.

### Keep implementation local and dependency-free

Transforms should use NumPy and OpenCV, which are already used by the workbench. The transform helper should live in `heatmap_alignment_core.py` so it can be unit tested independently of Qt.

Alternatives considered: using Matplotlib or PIL for transforms would add overhead and duplicate existing OpenCV image-processing capabilities.

## Risks / Trade-offs

- Too many controls could slow manual alignment -> use one enhance toggle, draggable low/high range handles, and one gamma control.
- Transformed previews may mislead users if they hide raw camera artifacts -> make raw/enhanced toggling immediate and visible.
- Viridis mapping from luminance may be imperfect under monitor/camera color shifts -> treat it as a manual visibility aid, not truth reconstruction.
- Transform processing could affect playback smoothness -> keep transforms lightweight and measure if live playback becomes uneven.
- Session schema changes can affect old files -> provide defaults when `viewport_visibility` is absent.
- Source-resolution preview work could fight playback/scrubbing -> disable scheduling during playback and debounce while the viewport state is changing.
- Worker cancellation is cooperative by obsolescence rather than forced interruption -> use request tokens and accept only the latest matching result.
- Native-coordinate session changes can affect old files -> rely on manual correction for the small known set of saved sessions rather than building a broad migration system.
