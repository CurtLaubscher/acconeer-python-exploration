## 1. Range Model Defaults

- [x] 1.1 Define a stable blank/default shared x-range of `0..60 s` for no-resource reset cases
- [x] 1.2 Update `TimelineRangeModel.recompute_visible_range()` or its helper path so no-resource "fit" uses `0..60 s`
- [x] 1.3 Add focused coverage for "Zoom to Fit" with no loaded resources resetting to `0..60 s`

## 2. Preview Sync Semantics

- [x] 2.1 Change preview synchronization so preserving the current shared x-range is the default behavior
- [x] 2.2 Add an explicit recompute/reset option or helper for call sites that intentionally reset the shared x-range
- [x] 2.3 Update `_sync_timeline_feedback()` so it does not recompute the shared x-range unless explicitly requested
- [x] 2.4 Update existing preserve-specific helper names/usages if needed so the code reads clearly after preserve-by-default behavior

## 3. Explicit Reset Call Sites

- [x] 3.1 Keep timeline and Signals "Zoom to Fit" actions wired to explicit recompute/reset behavior
- [x] 3.2 Ensure opening/loading a session explicitly recomputes the shared x-range from the opened session/resource domain
- [x] 3.3 Ensure opening a session from an empty workbench and opening a session from a populated workbench use the same range-reset behavior
- [x] 3.4 Ensure closing the current session or resetting to a new empty session explicitly resets the shared x-range to `0..60 s`

## 4. Preservation Call Sites

- [x] 4.1 Ensure camera and H5 background job completion preserves the current shared x-range
- [x] 4.2 Ensure camera/H5/Leg2/peak resource unload and clear-all-resources preserve the current shared x-range
- [x] 4.3 Ensure render/color, viewport, export overlay, peak selector, Leg2 signal kind, and signal visibility changes preserve the current shared x-range
- [x] 4.4 Ensure source-resolution viewport worker completion still preserves the current shared x-range
- [x] 4.5 Ensure track-bar drag release and current-time/playhead changes continue to preserve the current shared x-range

## 5. Regression Tests

- [x] 5.1 Add or update tests proving H5 background load completion preserves a zoomed/panned shared x-range
- [x] 5.2 Add or update tests proving camera background load completion preserves a zoomed/panned shared x-range
- [x] 5.3 Add tests for resource unload and clear-all-resources preserving the shared x-range
- [x] 5.4 Add representative tests for display-only refreshes preserving the shared x-range
- [x] 5.5 Add tests for explicit reset paths: Zoom to Fit, session open/load, and close-session/new-empty-session
- [x] 5.6 Run the targeted heatmap alignment user-tools tests and `git diff --check`
