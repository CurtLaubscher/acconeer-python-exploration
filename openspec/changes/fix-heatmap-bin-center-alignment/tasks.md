## 1. Coordinate Semantics

- [x] 1.1 Add or centralize helper logic for deriving finite distance and velocity bin-edge extents from heatmap axis center values.
- [x] 1.2 Update compact rendered-heatmap distance header peak cue placement to project peak distance through bin-edge extents rather than first/last bin centers.
- [x] 1.3 Update rendered-heatmap hover readout mapping so distance, velocity, and magnitude lookup use displayed bin-edge geometry and resolve to the displayed bin under the pointer.
- [x] 1.4 Remove the rendered heatmap body frame inset so the heatmap body, detection strip, and compact peak indicator share the same horizontal drawable extent.

## 2. H5 Frame Selection

- [x] 2.1 Update H5 time-to-frame lookup to select the nearest recorded tick after clamping requested time to the H5 duration.
- [x] 2.2 Preserve correct behavior at the first frame, last frame, exact frame timestamps, and midpoint boundaries.

## 3. Tests

- [x] 3.1 Add focused tests for distance header peak indicator placement at first, interior, and last distance-bin centers.
- [x] 3.2 Add focused tests for rendered heatmap hover lookup at displayed bin centers and near bin boundaries.
- [x] 3.3 Add focused tests for nearest H5 frame selection before and after adjacent-frame midpoints, including clamping before the first and after the last frame.
- [x] 3.4 Add a focused test that the rendered heatmap preview has no frame border inset.

## 4. Verification

- [x] 4.1 Run the focused Hatch-managed test targets for the updated heatmap alignment GUI/core behavior.
- [x] 4.2 Run `openspec status --change "fix-heatmap-bin-center-alignment"` and resolve any artifact validation issues before implementation handoff.
