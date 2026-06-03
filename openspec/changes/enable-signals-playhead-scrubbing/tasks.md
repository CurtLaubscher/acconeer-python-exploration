## 1. Signals Playhead Interaction

- [ ] 1.1 Add a Signals playhead drag signal or callback path that updates shared current time through the same main-window scrub behavior as Timeline playhead changes.
- [ ] 1.2 Add Signals playhead hit testing so hover, press, and drag only activate near the current-time indicator line.
- [ ] 1.3 Map Signals playhead drag positions through the Signals plot ViewBox x-axis so manual x mode uses the plot's current time-to-pixel scale.
- [ ] 1.4 Preserve Signals x/y ranges, x/y range modes, Timeline visible range, offsets, and session dirty state during Signals playhead dragging.

## 2. Affordance And Styling

- [ ] 2.1 Apply the same drag cursor affordance to the Signals playhead hit area as the Timeline playhead hit area.
- [ ] 2.2 Introduce named playhead opacity/alpha styling and apply modest transparency to both Timeline and Signals playheads.
- [ ] 2.3 Tune the Signals playhead hit area and opacity through visual inspection without hard-coded unexplained magic values.

## 3. Tests

- [ ] 3.1 Add a GUI test proving dragging the Signals playhead updates `session.timeline.current_time_s` and refreshes scrub state.
- [ ] 3.2 Add a GUI test proving Signals manual x mode maps drag position through the Signals plot x scale.
- [ ] 3.3 Add a GUI test proving Signals playhead dragging preserves plot range modes, visible ranges, and Timeline visible range.
- [ ] 3.4 Add a GUI test proving clicks outside the Signals playhead hit area do not scrub current time.

## 4. Verification

- [ ] 4.1 Run the focused GUI tests with the repo-managed Hatch test environment.
- [ ] 4.2 Launch the heatmap alignment GUI with `hatch run app:heatmap-align` and manually verify Timeline-mode scrubbing, manual-x-mode scrubbing, cursor changes, and playhead visibility.
- [ ] 4.3 Run OpenSpec validation/status for `enable-signals-playhead-scrubbing` and resolve any artifact issues.
