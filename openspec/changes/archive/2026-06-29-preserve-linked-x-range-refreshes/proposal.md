## Why

The linked timeline/Signals x-range can still be reset by non-navigation refreshes, especially when background camera or H5 resource loads finish after the user has already zoomed or panned. This makes the view jump unexpectedly and weakens the "Zoom to Fit is explicit" interaction model.

## What Changes

- Make the shared x-range a preserved view state by default across preview refreshes, async worker completion, resource load/reload/replace/unload, clear-all-resources, render/color/viewport/export changes, peak selector changes, Leg2 signal changes, and signal data refreshes.
- Require explicit range-reset intent for automatic recompute/reset paths.
- Keep explicit "Zoom to Fit" as the user-facing way to reset the current shared x-range to the loaded recording span.
- Define the blank/default shared x-range as `0..60 s` when there are no loaded resources to fit.
- Keep opening/loading a session as a range-resetting operation that recomputes the shared x-range from the loaded/session domain; opening from an empty workbench and opening from another session should use the same behavior.
- Keep close-session/new-empty-session as a range-resetting operation that returns to the blank/default range.
- Do not add out-of-view track indicators or playhead visibility fixes in this change; capture those as future ideas only.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `linked-timeline-signals-zoom`: Clarify that non-navigation refreshes preserve the shared x-range and only explicit reset/session-reset paths recompute it.
- `heatmap-alignment-gui`: Define resource load/unload, preview refresh, session load, close-session, clear-all-resources, and blank-range behavior for the shared timeline x-range.

## Impact

- `user_tools/heatmap_alignment_gui.py`: Preview synchronization and resource/session callbacks will need explicit preserve-vs-reset semantics instead of recomputing the timeline range by default.
- `user_tools/heatmap_alignment_timeline_widgets.py`: `TimelineRangeModel` may need a stable blank/default range and explicit reset behavior for no-resource cases.
- `tests/user_tools/test_heatmap_alignment_gui.py` and related timeline tests: Add regression coverage for async resource completion and non-navigation refreshes preserving the shared x-range; keep tests for explicit reset behavior.
- `openspec/specs/heatmap-alignment-gui/ideas.md`: Add deferred ideas for off-screen track indicators and a timeline playhead out-of-range visibility bug.
