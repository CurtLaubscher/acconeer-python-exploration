## Why

The Signals plot is where users inspect time-series events, so a visible current-time line that cannot be grabbed feels inconsistent with the draggable Timeline playhead. Enabling direct scrubbing from the Signals playhead lets users move "now" at the point of inspection without changing the existing timeline or plot range model.

## What Changes

- Make the Signals current-time indicator draggable from its line/hit area.
- Use the same cursor and interaction affordance as the Timeline playhead.
- Update only the shared current time during Signals playhead dragging.
- Preserve the Signals plot range, range modes, and independent x/y behavior while scrubbing.
- Keep the plot background as normal plot interaction space; only the playhead hit area becomes a scrub handle.
- Apply modest transparency to both current-time playheads so underlying signal and timeline content remains visible.
- Keep playhead movement excluded from session dirty tracking.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `heatmap-alignment-gui`: Signals current-time indicator interaction changes from passive readout to draggable scrub handle while preserving timeline/range semantics.

## Impact

- `user_tools/heatmap_alignment_gui.py`: Signals playhead input handling, cursor affordance, current-time signal emission, and playhead styling.
- `tests/user_tools/test_heatmap_alignment_gui.py`: focused tests for Signals playhead dragging, cursor/hit-area behavior, and range-mode preservation.
- `openspec/specs/heatmap-alignment-gui/spec.md`: current-time indicator requirements and scenarios.
