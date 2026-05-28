## Why

Manual alignment of video, radar heatmap, and Leg2 ultrasonic signals is difficult without biomechanical context. Knowing when the foot is in contact with the ground (stance phase) provides a clear reference point for matching signal features to video observations. The `.mat` files already contain this information (`robustFC`), but it is not currently visualized in the alignment workbench, missing an opportunity to make temporal alignment faster and more accurate.

## What Changes

- Extract the `robustFC` field (robust foot contact indicator) from Leg2 `.mat` files during import
- Display stance phase as filled patches on the Signals plot, spanning from the lower y-limit up to y=0 during stance intervals
- Add "Stance phase" to the signal plot legend so the visualization is clearly labeled
- Use the same color as the Leg2 ultrasonic signal with primary-segment transparency for visual consistency
- Patches remain independent of y-axis auto-scaling (visual overlay only, does not affect computed y-range)

## Capabilities

### New Capabilities

- `leg2-stance-phase-visualization`: Display Leg2 gait phase (stance/swing) on the Signals plot as a temporal context aid for manual video-to-signal alignment

### Modified Capabilities

- `leg2-ultrasonic-datasource`: Extended to include stance phase mask from `DataRecordCommon.robustFC`

## Impact

- **Code**: Extends `heatmap_alignment_core.py` (Leg2 import, data structures) and `heatmap_alignment_gui.py` (Signals plot rendering)
- **Data**: Leg2 `.mat` import now reads one additional required field (`DataRecordCommon.robustFC`)
- **UI**: Signals plot adds stance phase fill regions and legend entry; no new controls or dialogs
- **User Workflow**: Alignment becomes faster because gait transitions are immediately visible and easy to match to video observations
