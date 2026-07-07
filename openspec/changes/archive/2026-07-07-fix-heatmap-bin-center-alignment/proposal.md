## Why

Rendered heatmap alignment cues currently mix bin-center, bin-edge, and frame-selection semantics. This makes peak markers, hover readouts, and H5 frame selection feel subtly shifted by about half a distance bin or half a frame during manual alignment review.

## What Changes

- Define rendered heatmap distance-axis screen mapping in terms of bin-edge extents derived from the distance bin centers.
- Align the compact peak distance header marker and label with the same distance-bin geometry used by the rendered heatmap body.
- Align rendered heatmap hover distance, velocity, and magnitude lookup with the displayed heatmap bin geometry.
- Select the H5 heatmap frame nearest to the requested current time instead of selecting the first frame timestamp at or after that time.
- Add focused tests for distance cue placement, hover bin lookup, and H5 time-to-frame selection semantics.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `heatmap-alignment-gui`: Clarify and correct rendered heatmap bin-center/bin-edge mapping and H5 nearest-frame selection behavior.

## Impact

- Affected code:
  - `user_tools/sparse_iq_heatmap_common.py`
  - `user_tools/heatmap_alignment_gui.py`
  - `user_tools/heatmap_alignment_dialogs.py`
  - Focused tests under `tests/user_tools/`
- No runtime dependency changes are expected.
- Saved session schema and exported artifact formats are not expected to change.
