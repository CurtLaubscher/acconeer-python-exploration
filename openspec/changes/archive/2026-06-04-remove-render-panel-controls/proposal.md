## Why

The heatmap alignment workbench still has a bottom **Render** panel that mixes rendered-heatmap color controls, disabled xcorr/preprocess controls, and Signals datasource visibility controls. The viewport controls have already moved into the Viewport panel; the remaining Render panel contents should follow the same ownership pattern so controls live beside the preview or plot they affect.

Removing the redundant peak and Leg2 visibility checkboxes also avoids persisted hidden datasource state that can make a loaded session appear to have missing signals even though the resources are present.

## What Changes

- Remove the bottom **Render** panel from the main workbench layout.
- Move rendered-heatmap color minimum and maximum controls into the **Rendered Heatmap** panel.
- Move the Leg2 raw/filtered ultrasonic selector into the **Signals** area as a compact plot-scope control.
- Remove the **Show Peak Marker** and **Show Leg2 Signal** checkboxes; loaded peak and Leg2 datasources display by default, while temporary plot hiding remains available through the existing pyqtgraph legend interaction.
- Keep disabled xcorr/preprocess controls (`Blur`, `Downscale`, `Lag Window`, `Sample Count`) out of the main workflow until a future diagnostic feature reintroduces them intentionally.
- Introduce alignment session format version `2` with a small v1-to-v2 migration that drops retired datasource visibility fields while preserving older v1 session files.
- Continue saving dormant preprocess settings for now so removing the UI controls does not force unrelated xcorr/preprocess schema decisions.
- **BREAKING**: Session files saved after this change use alignment session version `2` and are not expected to be readable by older versions of the workbench.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `heatmap-alignment-gui`: Render/Signals control placement, removal of persisted datasource visibility controls, and alignment session v1-to-v2 migration behavior.

## Impact

- `user_tools/heatmap_alignment_gui.py` - main layout changes, Signals toolbar/selector placement, removal of checkbox wiring and datasource visibility handlers.
- `user_tools/heatmap_alignment_core.py` - alignment session version bump, v1-to-v2 payload migration, and removal of Leg2 datasource visibility persistence.
- `user_tools/sparse_iq_peak_distance_core.py` - removal of peak-distance datasource visibility persistence from the shared datasource settings.
- `tests/user_tools/` - session migration/roundtrip tests and focused GUI layout/control behavior tests.
- `openspec/specs/heatmap-alignment-gui/ideas.md` - keep future notes for dormant xcorr/preprocess controls and broader session-file warning/migration policy.
