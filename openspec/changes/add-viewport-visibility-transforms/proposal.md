## Why

Manual alignment is still harder than it needs to be because the camera-captured monitor heatmap can be low contrast or visually different from the rendered H5 heatmap. The workbench should provide a small, intuitive set of viewport visibility transforms so the user can make the rectified camera viewport easier to compare against the rendered truth while preserving the existing raw preview path.

Early live evaluation showed that the visibility transform is difficult to judge when the rectified viewport is sourced from the low-resolution proxy preview. The workbench should therefore support a source-resolution paused viewport preview sourced from the original camera video, and should store viewport geometry in original-video coordinates so future source-resolution rendering uses the most accurate coordinate space.

## What Changes

- Add viewport enhancement controls for the rectified camera viewport.
- Provide a quick raw/enhanced toggle so the user can compare the original rectified viewport against the enhanced version without changing alignment state.
- Apply draggable low/high range handles and gamma adjustment to the viewport image before optional palette mapping.
- Add an optional `Map to Viridis` toggle that converts the corrected viewport luminance to the same 1D viridis scale used by the rendered H5 heatmap.
- When viridis mapping is disabled, show the original viewport colors after low/high/gamma correction rather than a grayscale representation.
- Keep transforms preview-only for alignment unless explicitly reused by a future diagnostic.
- Persist selected viewport visibility settings in alignment sessions so reloaded sessions reproduce the same comparison view.
- Store viewport geometry in original camera pixel coordinates rather than proxy/display coordinates.
- Add an automatic source-resolution rectified viewport preview that renders from the original camera video after the viewport state has been idle briefly.
- Immediately invalidate stale source-resolution preview work when time, offset, geometry, camera source, or viewport output state changes.
- Use one background worker with latest-request-wins behavior for source-resolution viewport rendering.
- Apply viewport visibility transforms after choosing the low-resolution live viewport frame or the source-resolution viewport frame.
- Keep xcorr deferred; this change prepares the visual comparison path without reintroducing automatic or expensive xcorr computation.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `heatmap-alignment-gui`: Add viewport visibility transform behavior and source-resolution paused viewport preview behavior to improve manual comparison between the rectified camera viewport and rendered H5 heatmap.

## Impact

- Affects `user_tools/heatmap_alignment_gui.py` viewport controls and preview refresh.
- Affects `user_tools/heatmap_alignment_core.py` session state, coordinate handling, and image transform helpers.
- Affects tests for session roundtrip and transform behavior.
- Existing saved session JSON files from early MVP usage may need one-time manual coordinate correction because there are only a few known files and no broad compatibility migration is required.
- No new runtime dependency is expected; transforms should use NumPy/OpenCV already available to the tool.
