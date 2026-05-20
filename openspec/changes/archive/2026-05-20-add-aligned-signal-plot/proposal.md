## Why

Manual temporal alignment is easier when derived signals can be reviewed over the same physical time axis as the camera and H5 tracks. The heatmap alignment GUI already imports H5 peak-distance JSON, but the current visualization is only frame-local and the disabled xcorr UI occupies space that would be more useful for signal review.

## What Changes

- Add a separate boxed Signals area above the existing Timeline area.
- Plot imported H5 peak-distance data over time using the H5 track color convention.
- Show detected H5 peaks as the primary solid signal and no-detection candidate distances as a lower-alpha signal, while preserving actual gaps for missing values.
- Keep the Signals x-axis synchronized to the Timeline range and pixel geometry when x Timeline mode is enabled.
- Allow per-axis range mode control so x can use Timeline or manual mode and y can use auto or manual mode.
- Persist signal plot range modes and manual ranges in alignment sessions.
- Add a compact signal legend.
- Remove the visible disabled xcorr UI and dead GUI control wiring from the main workbench, while keeping lower-level xcorr helper code available for future diagnostic work.
- Keep synced video export unchanged.
- Keep Leg2 `.mat` import out of this change; this proposal only prepares the signal-review surface that a later `.mat` datasource can use.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `heatmap-alignment-gui`: Add an aligned signal plot for imported H5 peak-distance measurements and remove the visible disabled xcorr UI from the workbench.

## Impact

- Affects `user_tools/heatmap_alignment_gui.py` for layout, signal plotting, range controls, persistence integration, and xcorr UI removal.
- Affects `user_tools/heatmap_alignment_core.py` for serializable signal plot view settings in `AlignmentSession`.
- May affect focused tests or validation helpers for session serialization and peak-distance signal rendering behavior.
- Uses existing application dependencies, especially `pyqtgraph`; no new runtime dependency is expected.
