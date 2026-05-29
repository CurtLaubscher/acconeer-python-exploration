## Why

Timeline interaction currently has two rough edges in the heatmap alignment workbench: clicking the Timeline current-time marker can accidentally grab the track bar underneath it, and the H5 bar visually behaves as a fixed special case even when the user wants to shift the alignment frame around the H5 recording. These refinements make common drag gestures match what the user appears to be grabbing while preserving the current H5-as-origin session model.

## What Changes

- Give the Timeline current-time marker first priority for click/drag hit testing when it overlaps a timeline track bar.
- Allow the H5 duration bar to be dragged as a relative alignment handle without introducing a persisted H5 offset.
- During H5 dragging, keep the UX consistent with grabbing the H5 block: the H5 bar follows the pointer, the playhead keeps its screen-relative position, and loaded non-H5 offset-bearing tracks update their stored offsets as needed without persisting an H5 offset.
- Keep H5-only dragging as a no-op when there are no non-H5 offset-bearing tracks to shift.
- Capture the longer-term idea that H5 should eventually have its own offset in a global-reference timeline model.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `heatmap-alignment-gui`: Timeline current-time marker and H5 duration-bar drag behavior changes in the existing heatmap alignment workbench.

## Impact

- Affected code:
  - `user_tools/heatmap_alignment_gui.py`
  - `user_tools/heatmap_alignment_core.py` if shared timeline helpers need small refactoring for H5 drag deltas
  - `tests/user_tools/test_heatmap_alignment_gui.py`
  - `tests/user_tools/test_heatmap_alignment_core.py` if helper behavior changes
  - `openspec/specs/heatmap-alignment-gui/ideas.md`
- No new runtime dependencies.
- No alignment session schema migration is intended for this short-term refinement.
