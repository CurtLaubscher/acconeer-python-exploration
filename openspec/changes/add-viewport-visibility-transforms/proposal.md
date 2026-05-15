## Why

Manual alignment is still harder than it needs to be because the camera-captured monitor heatmap can be low contrast or visually different from the rendered H5 heatmap. The workbench should provide a small, intuitive set of viewport visibility transforms so the user can make the rectified camera viewport easier to compare against the rendered truth while preserving the existing raw preview path.

## What Changes

- Add viewport enhancement controls for the rectified camera viewport.
- Provide a quick raw/enhanced toggle so the user can compare the original rectified viewport against the enhanced version without changing alignment state.
- Apply draggable low/high range handles and gamma adjustment to the viewport image before optional palette mapping.
- Add an optional `Map to Viridis` toggle that converts the corrected viewport luminance to the same 1D viridis scale used by the rendered H5 heatmap.
- When viridis mapping is disabled, show the original viewport colors after low/high/gamma correction rather than a grayscale representation.
- Keep transforms preview-only for alignment unless explicitly reused by a future diagnostic.
- Persist selected viewport visibility settings in alignment sessions so reloaded sessions reproduce the same comparison view.
- Keep xcorr deferred; this change prepares the visual comparison path without reintroducing automatic or expensive xcorr computation.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `heatmap-alignment-gui`: Add viewport visibility transform behavior to improve manual comparison between the rectified camera viewport and rendered H5 heatmap.

## Impact

- Affects `user_tools/heatmap_alignment_gui.py` viewport controls and preview refresh.
- Affects `user_tools/heatmap_alignment_core.py` session state and image transform helpers.
- Affects tests for session roundtrip and transform behavior.
- No new runtime dependency is expected; transforms should use NumPy/OpenCV already available to the tool.
