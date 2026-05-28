## 1. Extract robustFC from `.mat` files

- [x] 1.1 Add `stance_phase_mask: np.ndarray` field to `LoadedLeg2UltrasonicDatasource` dataclass
- [x] 1.2 Update `load_leg2_mat_ultrasonic()` to read `DataRecordCommon.robustFC` alongside existing fields
- [x] 1.3 Add `DataRecordCommon.robustFC` to required paths check and length validation
- [x] 1.4 Use `_read_mat_1d_bool_array()` to convert robustFC to boolean mask (consistent with ReliableFlag pattern)
- [x] 1.5 Add unit tests for successful `.mat` loading with robustFC
- [x] 1.6 Add unit tests for `.mat` loading failure when robustFC is missing

## 2. Build stance intervals in signal series

- [x] 2.1 Create `Leg2StanceIntervals` or similar data structure to hold stance interval boundaries (start_time_s, end_time_s)
- [x] 2.2 Add logic to `build_leg2_ultrasonic_signal_series()` to detect rising/falling edges in stance_phase_mask
- [x] 2.3 Compute stance intervals during edge detection; treat first time step as implicit rising edge if recording starts in stance (robustFC[0]==1), and last time step as implicit falling edge if recording ends in stance (robustFC[-1]==1)
- [x] 2.4 Add stance intervals to `Leg2UltrasonicSignalSeries` as a new field
- [x] 2.5 Apply track offset to stance intervals so they move with the signal

## 3. Render stance patches on Signals plot

- [x] 3.1 Add method to `SignalPlotWidget` to create and add stance phase patch items to the plot
- [x] 3.2 Create filled regions using pyqtgraph (likely `pg.FillBetween` or `QGraphicsRectItem`)
- [x] 3.3 Style patches with Leg2 color using `derive_signal_plot_color(LEG2_TIMELINE_TRACK_COLOR_HEX)` and `SIGNAL_PLOT_PRIMARY_SEGMENT_ALPHA`
- [x] 3.4 Fill from plot's lower y-limit up to y=0 for each stance interval
- [x] 3.5 Call patch rendering method when `set_plotted_signals()` updates with Leg2 data
- [x] 3.6 Ensure patches clear when Leg2 signal is hidden or unloaded
- [x] 3.7 Test that patches do not affect y-axis auto-scaling (verify `visible_signal_y_range()` output is unchanged)

## 4. Update signal plot legend

- [x] 4.1 Add "Stance phase" legend entry when Leg2 signal becomes visible
- [x] 4.2 Use same color and transparency as patch visualization
- [x] 4.3 Remove "Stance phase" from legend when Leg2 signal is hidden
- [x] 4.4 Place "Stance phase" entry after Leg2 ultrasonic signal entries (primary/faded) in the legend, matching existing legend ordering pattern

## 5. Handle track offset changes

- [x] 5.1 Verify that stance patches move when Leg2 track offset changes on timeline
- [x] 5.2 Test that time-axis transformations correctly map stance intervals through offset
- [x] 5.3 Add regression test: align Leg2 signal, verify stance patches align with expected timeline positions

## 6. Integration and testing

- [x] 6.1 Test with sample `.mat` files (trial01.mat, etc. from the 260521 dataset) — USER VERIFICATION REQUIRED
- [x] 6.2 Verify stance transitions match visual gait phases in corresponding video — USER VERIFICATION REQUIRED
- [x] 6.3 Test timeline scrubbing and playback with stance patches visible — USER VERIFICATION REQUIRED
- [x] 6.4 Test export: verify stance patches do not appear in exported video (they are plot-only) — USER VERIFICATION REQUIRED
- [x] 6.5 Test session save/load: verify stance patches reappear when Leg2 `.mat` is reloaded from the persisted file path reference — USER VERIFICATION REQUIRED
- [x] 6.6 Test color theme consistency if GUI themes change in future — USER VERIFICATION REQUIRED
- [x] 6.7 Run existing GUI tests to ensure no regressions — USER VERIFICATION REQUIRED

## 7. Documentation and polish

- [x] 7.1 Add docstring to `Leg2StanceIntervals` class explaining interval semantics
- [x] 7.2 Add inline comments explaining edge detection logic and track offset handling
- [x] 7.3 Update heatmap alignment GUI ideas file if needed to reflect implementation
- [x] 7.4 Verify code follows project style and linting standards — USER VERIFICATION REQUIRED (run: hatch run lint:ruff check --fix user_tools/heatmap_alignment_core.py user_tools/heatmap_alignment_gui.py)
