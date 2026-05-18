## 1. Session And Core Transform Model

- [x] 1.1 Add viewport visibility settings to the alignment session model with raw-mode defaults for older sessions.
- [x] 1.2 Implement core viewport enhancement helpers for corrected original-color display, luminance-to-viridis mapping, low/high range, and gamma adjustment.
- [x] 1.3 Add focused tests for transform output shape/type, disabled-enhancement identity behavior, corrected-color behavior, viridis mapping behavior, and session roundtrip persistence.

## 2. GUI Controls And Preview Wiring

- [x] 2.1 Move compact viewport enhancement controls near the viewport preview without enabling xcorr or changing rendered H5 color controls.
- [x] 2.2 Apply the selected transform only to the rectified viewport preview, leaving the camera source view and rendered H5 preview unchanged.
- [x] 2.3 Add a raw/enhanced toggle that disables low/high/gamma and viridis mapping controls while enhancement is off without losing the tuned values.
- [x] 2.4 Add draggable low/high range controls, gamma tuning, and a `Map to Viridis` toggle for the corrected viewport.
- [x] 2.5 Ensure visibility control changes refresh the viewport preview immediately during scrubbing and playback.
- [x] 2.6 Populate controls from loaded sessions and preserve defaults for sessions without viewport visibility settings.

## 3. Verification

- [x] 3.1 Verify compile and focused unit tests for the new transform/session behavior.
- [x] 3.2 Smoke-test the GUI with representative camera/H5 data to confirm raw/enhanced toggling, draggable range tuning, gamma updates, and viridis mapping behave as expected.
- [x] 3.3 Run `openspec validate add-viewport-visibility-transforms --strict`.

## 4. Native Viewport Geometry

- [x] 4.1 Store viewport corners in original camera video coordinates and adapt camera preview drawing/hit testing to map them into the displayed proxy/preview coordinate space.
- [x] 4.2 Adapt fast low-resolution viewport rectification to scale native corners into the active display/proxy frame coordinate space.
- [x] 4.3 Preserve native viewport geometry through session save/load.
- [x] 4.4 Manually correct the small known set of existing saved session JSON files if their viewport coordinates were saved in proxy/display coordinates.
- [x] 4.5 Add focused tests for native-coordinate geometry mapping and session roundtrip behavior where practical.

## 5. Source-Resolution Paused Viewport Preview

- [x] 5.1 Add a single latest-request-wins source-resolution viewport worker that decodes from the original camera video and rectifies using native viewport corners.
- [x] 5.2 Immediately invalidate stale source-resolution viewport results on viewport-relevant updates and show the low-resolution viewport preview.
- [x] 5.3 Debounce new source-resolution viewport work by approximately 200 ms while playback is paused.
- [x] 5.4 Skip source-resolution viewport scheduling while playback is active, with playback state transitions routed through a centralized helper or controlled path.
- [x] 5.5 Apply viewport visibility enhancement after choosing the source-resolution or low-resolution viewport frame.
- [x] 5.6 Fall back to the low-resolution viewport preview if source-resolution rendering fails.
- [x] 5.7 Smoke-test scrubbing, paused idle rendering, geometry dragging, and enhancement toggles against representative data.
- [x] 5.8 Run `openspec validate add-viewport-visibility-transforms --strict`.

## 6. Camera Preview Drag Correction

- [x] 6.1 Fix camera-video viewport edge and center dragging to compute movement from drag-start cursor position to current cursor position and apply the bounded delta exactly once.
- [x] 6.2 Verify camera-video corner, edge, and center dragging still update native viewport geometry correctly.
- [x] 6.3 Run compile, focused tests, and `openspec validate add-viewport-visibility-transforms --strict`.
