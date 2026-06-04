## 1. Coordinate Data And Layout

- [ ] 1.1 Expose or reuse rendered heatmap body geometry so labels, peak indicator, and hover mapping are anchored to the painted image rect rather than the whole widget; `ImagePreview` can letterbox its pixmap, so add a `rendered_image_rect()` method or equivalent if needed.
- [ ] 1.2 Add rendered heatmap distance extent labels aligned to the heatmap body left and right edges.
- [ ] 1.3 Add compact velocity extent text near the rendered heatmap controls, using the active H5/subsweep velocity bounds.
- [ ] 1.4 Refresh distance and velocity extent text when the H5 resource or selected session, group, entry, or subsweep changes.

## 2. Peak Distance Indicator

- [ ] 2.1 Add a current peak distance label in the rendered heatmap distance-label area when the selected peak series has a valid current-frame peak.
- [ ] 2.2 Add a small downward indicator directly above the heatmap body at the current peak distance position.
- [ ] 2.3 Clamp or otherwise resolve peak label placement near the distance extent labels while keeping the indicator tied to the peak position.
- [ ] 2.4 Omit the peak label and indicator when no selected peak series has a valid current-frame peak or when the peak distance is outside the rendered heatmap distance-axis range.
- [ ] 2.5 Suppress the legacy in-image rendered heatmap peak annotation in the rendered heatmap comparison preview when the header peak label and indicator are used for the selected peak; do not change the export overlay path.

## 3. Hover Readout

- [ ] 3.1 Add pointer tracking for the rendered heatmap painted image rect and map pointer positions to distance and velocity coordinates; note that the DVM shape is `(velocity_bins, distance_bins)`, so hover x maps to distance and hover y maps to velocity.
- [ ] 3.2 Maintain a last-frame DVM cache keyed by current H5 frame index for hover magnitude lookup; populate it by calling `distance_velocity_map()` on the current-frame subframe rather than sampling rendered RGB pixels, reuse it while the frame is unchanged, and invalidate it when the current H5 frame changes.
- [ ] 3.3 Show a tooltip-style readout near the pointer with Distance, Velocity, and Magnitude values while hovering over the heatmap body.
- [ ] 3.4 Format Distance and Velocity with three decimals and Magnitude as an integer rounded to the nearest integer.
- [ ] 3.5 Refresh the hover magnitude when playback or scrubbing changes the current H5 frame while the pointer remains over the heatmap body.
- [ ] 3.6 Hide the hover readout when the pointer leaves the heatmap body or no current H5 frame is available, and clear the DVM cache when the H5 source is unloaded.

## 4. Verification

- [ ] 4.1 Add or update focused tests for extent label refresh, peak label visibility, and no-stale-label behavior.
- [ ] 4.2 Add or update focused tests for hover coordinate mapping, formatting, hide-on-leave, and magnitude refresh on current-frame changes.
- [ ] 4.3 Add or update verification that the rendered heatmap painted image rect dimensions remain matched to the rectified viewport painted image rect after the coordinate context UI is added, including a narrow preview case where labels may collide.
- [ ] 4.4 Verify the preview minimum-height/splitter behavior still prevents rendered heatmap controls and coordinate labels from overlapping preview content.
- [ ] 4.5 Add or update an export smoke check confirming preview-only legacy marker suppression does not remove exported heatmap overlay peak annotation behavior.
- [ ] 4.6 Run the relevant repo-defined Hatch test or check command from `pyproject.toml` for the changed heatmap alignment GUI behavior.
