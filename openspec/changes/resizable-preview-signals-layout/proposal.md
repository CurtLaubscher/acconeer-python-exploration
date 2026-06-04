## Why

The Signals plot can be hard to inspect when the heatmap alignment workbench window is small because preview panels, Signals, and Timeline compete for fixed vertical space. Users need a near-term way to trade preview height for signal readability without changing the alignment workflow.

## What Changes

- Make the Preview and Signals areas vertically resizable in the main workbench.
- Keep the Timeline at a fixed height for this version because the current workbench has a small fixed set of timeline rows.
- Preserve the existing horizontal resize behavior between Camera Video and the viewport/rendered-heatmap preview column.
- Do not persist splitter positions in this change; layout persistence should be handled consistently in a future layout-preference pass.
- Keep render-control layout cleanup, dockable panes, layout reset actions, and Timeline scalability outside this focused change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `heatmap-alignment-gui`: Add user-resizable vertical allocation between Preview and Signals while keeping Timeline fixed for the current fixed-resource workflow.

## Impact

- `user_tools/heatmap_alignment_gui.py`: main workbench layout construction and splitter setup.
- `openspec/specs/heatmap-alignment-gui/spec.md`: behavior contract for resizing Preview and Signals in the standalone workbench.
- No runtime dependencies or saved alignment session schema changes.
