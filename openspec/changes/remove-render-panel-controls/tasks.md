## 1. Session Format

- [ ] 1.1 Bump the alignment session format to version 2 and add a narrow v1-to-v2 payload migration that runs before the existing version gate and before dataclass construction.
- [ ] 1.2 Remove peak-distance and Leg2 datasource visibility fields from their settings dataclasses, including the peak datasource settings in `sparse_iq_peak_distance_core.py`, and strip those keys from v1 payloads while preserving datasource paths, Leg2 offset, and selected Leg2 signal kind.
- [ ] 1.3 Ensure v2 session saves omit retired datasource visibility fields, including any explicit `to_json_dict()` filtering needed if a temporary transition keeps dormant runtime fields, while continuing to save dormant preprocess settings.
- [ ] 1.4 Keep unsupported newer session versions rejected with a clear load error.

## 2. UI Layout

- [ ] 2.1 Remove the bottom Render group from the main workbench layout.
- [ ] 2.2 Move rendered-heatmap color minimum and maximum controls into the Rendered Heatmap panel.
- [ ] 2.3 Move the Leg2 raw/filtered ultrasonic selector into a compact Signals-area control row.
- [ ] 2.4 Remove Show Peak Marker and Show Leg2 Signal checkboxes and their signal wiring.
- [ ] 2.5 Remove disabled blur, downscale, lag-window, and sample-count controls from the main workflow without removing the dormant session settings.

## 3. Runtime Behavior

- [ ] 3.1 Make loaded or generated peak-distance data display by default in the heatmap marker/export overlay path and the Signals plot.
- [ ] 3.2 Make loaded Leg2 ultrasonic data display by default in the Signals plot.
- [ ] 3.3 Keep Leg2 raw/filtered signal-kind changes persisted and dirty-tracked.
- [ ] 3.4 Remove dirty marking for retired peak and Leg2 datasource visibility controls.
- [ ] 3.5 Ensure session-load reconciliation no longer applies retired datasource visibility state while still applying Leg2 offset and signal kind.

## 4. Tests

- [ ] 4.1 Update session roundtrip tests for version 2 and omitted datasource visibility fields.
- [ ] 4.2 Add v1 session migration tests covering retired peak and Leg2 visibility fields, plus unsupported future-version rejection.
- [ ] 4.3 Update GUI tests that reference removed visibility checkboxes or Render panel controls.
- [ ] 4.4 Add focused GUI/layout tests for Rendered Heatmap color controls and Signals-area Leg2 selector placement where practical.
- [ ] 4.5 Add behavior tests confirming loaded peak and Leg2 datasources plot/display by default after migration and normal load, including the peak marker export-overlay path.

## 5. Validation

- [ ] 5.1 Run focused heatmap alignment core tests through the repo-defined Hatch test environment.
- [ ] 5.2 Run focused heatmap alignment GUI tests through the repo-defined Hatch test environment.
- [ ] 5.3 Run `openspec validate remove-render-panel-controls --strict`.
