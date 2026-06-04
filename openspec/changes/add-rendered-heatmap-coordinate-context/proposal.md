## Why

The rendered Sparse IQ heatmap preview is difficult to interpret in physical coordinates during alignment because it currently prioritizes body-to-body visual comparison over axis context. Users need lightweight distance and velocity context without introducing plot whitespace that changes the comparable heatmap body size relative to the rectified camera viewport.

## What Changes

- Add compact distance extent labels for the rendered heatmap preview.
- Add a current peak distance label and a small top indicator when the selected peak series has a valid peak for the current frame.
- Add compact velocity extent text near the rendered heatmap controls rather than around the heatmap body.
- Add a tooltip-style hover readout over the rendered heatmap body showing distance, velocity, and current-frame magnitude.
- Preserve the rendered heatmap body geometry used for comparison with the rectified viewport.
- Keep color scale/colorbar visibility out of scope for this change.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `heatmap-alignment-gui`: Add lightweight coordinate context and hover readout behavior for the rendered heatmap preview.

## Impact

- Affects `user_tools/heatmap_alignment_gui.py` rendered heatmap UI composition, controls, and mouse handling.
- Affects rendered heatmap coordinate mapping from H5 axes to preview pixel positions.
- May affect focused GUI tests for rendered heatmap labels, peak label behavior, and hover readout updates.
- No runtime dependency changes are expected.
