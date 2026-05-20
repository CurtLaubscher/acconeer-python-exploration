## 1. Session Model

- [x] 1.1 Add serializable Signals plot view settings to `AlignmentSession`, including x/y range modes and optional manual x/y ranges.
- [x] 1.2 Update session JSON load behavior so older session files default to x auto mode and y auto mode when Signals plot settings are missing.
- [x] 1.3 Add focused serialization coverage or a lightweight verification path for saving and loading the new settings.

## 2. Signals UI

- [x] 2.1 Remove the visible disabled xcorr controls, xcorr status label, and xcorr plot from the main GUI layout.
- [x] 2.2 Keep isolated lower-level xcorr helper code available for future diagnostic work while removing dead GUI wiring that only served the disabled xcorr UI.
- [x] 2.3 Add a boxed Signals area above the Timeline group using a `pyqtgraph.PlotWidget`.
- [x] 2.4 Add a compact legend for visible signal curves.

## 3. Peak-Distance Signal Rendering

- [x] 3.1 Build H5 peak-distance plot data from the imported peak-distance datasource using H5 elapsed time.
- [x] 3.2 Derive readable plot pens from the base H5 timeline color so the H5 signal remains color-associated but legible on the current plot background.
- [x] 3.3 Plot `candidate_peak_distance_m` values segmented by detection status, using the primary H5 plot pen for detected frames and a lower-alpha version for no-detection frames.
- [x] 3.4 Preserve actual gaps for missing or unavailable values by using NaN-separated plot data.
- [x] 3.5 Refresh the Signals plot when peak-distance datasource load, clear, visibility, timeline, or current session state changes.

## 4. Range Modes

- [x] 4.1 Implement GUI-owned x-axis and y-axis range mode state for the Signals plot.
- [x] 4.2 In x Timeline mode, make the Signals x-range follow the timeline bounds and disable direct x zoom/pan.
- [x] 4.3 In x manual mode, enable direct x zoom/pan without changing the timeline bounds.
- [x] 4.4 In y auto mode, fit y-limits to visible signal data in the active x-window while including zero in the fitted range.
- [x] 4.5 In y manual mode, enable direct y zoom/pan without changing x-axis range mode.
- [x] 4.6 Add two-option Signals plot context menu actions for x/y range modes and keep their checked state synchronized with session state, using `Timeline` as the compact x-axis timeline-following label.
- [x] 4.7 Align the Timeline time-bar drawing rect to the Signals plot data rect so matching time values share the same horizontal screen position in x Timeline mode.
- [x] 4.8 Disable or reset X inversion, Log X, and stock View All behavior while x Timeline mode is active so plot actions cannot break shared linear time mapping.

## 5. Verification

- [x] 5.1 Run focused formatting/lint checks for touched user tool files using repo-defined Hatch tooling.
- [x] 5.2 Launch the GUI with the repo-defined `hatch run app:heatmap-align` command and verify the Signals area appears above Timeline.
- [x] 5.3 Verify an imported peak-distance JSON plots detected and no-detection candidate distances with correct color, alpha, legend, and missing-value gaps.
- [x] 5.4 Verify x auto follows timeline bounds, x manual allows independent plot inspection, and y range mode works independently from x range mode.
- [x] 5.5 Verify saving and reloading a session preserves Signals plot view settings.
- [x] 5.6 Verify synced video export behavior is unchanged and does not include the Signals plot.
- [x] 5.7 Verify Signals and Timeline current-time indicators remain horizontally aligned after resize, mode switching, playback, and scrubbing.
