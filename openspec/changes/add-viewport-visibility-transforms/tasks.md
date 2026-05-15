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
