## Context

The heatmap alignment workbench imports Leg2 ultrasonic signals from `.mat` files and displays them on a shared timeline alongside H5 heatmap and camera video. Users manually align these sources by dragging tracks and observing feature correspondence. The Leg2 `.mat` files contain a `robustFC` field in `DataRecordCommon` that indicates foot contact (stance phase), but this information is currently unused. Adding stance phase visualization will provide users with clear biomechanical reference points (foot contact transitions) that are easy to match to video observations and signal features.

**Current architecture:**
- `LoadedLeg2UltrasonicDatasource` holds time, raw distance, filtered distance, and reliable flag
- `Leg2UltrasonicSignalSeries` segments the signal by reliable flag for primary/faded rendering
- `SignalPlotWidget` plots H5 peak distance and Leg2 ultrasonic as curves with pyqtgraph
- Signal plot y-axis auto-scales based on plotted data arrays (not visual overlays)

**Key constraints:**
- Stance patches must not interfere with y-axis auto-scaling (they are visual-only overlays)
- Patches use the same color and transparency as the Leg2 ultrasonic primary segment
- Patches move with the Leg2 track offset like the signal itself
- No new UI controls or dialogs are required; visualization is always on

## Goals / Non-Goals

**Goals:**
- Extract `robustFC` from Leg2 `.mat` and store it in the datasource
- Render stance intervals as filled patch regions below the signal during stance phases
- Integrate stance visualization into the existing signal plot without introducing complexity
- Provide clear legend labeling so users understand the visualization
- Ensure color and styling consistency with the Leg2 ultrasonic signal

**Non-Goals:**
- Add user controls or toggles for stance phase visibility (always visible once Leg2 is loaded)
- Add thresholds, smoothing, or filtering of the `robustFC` signal
- Implement automated offset suggestions based on stance transitions (manual alignment remains the authority)
- Support `stance_Dist` or `swing_Dist` variables (out of scope; focus on `robustFC`)
- Build a generic `.mat` variable browser (hard-code paths as currently done)

## Decisions

### Decision 1: Extend data structures to hold stance phase mask
**Choice:** Add a `stance_phase_mask` array (boolean) to `LoadedLeg2UltrasonicDatasource` alongside existing fields.

**Rationale:** This keeps the datasource self-contained and follows the existing pattern of holding per-sample metadata (reliable flag, time axis). The mask is extracted once at load time and reused throughout the session.

**Alternative considered:** Store stance phase only in the plot series object. Rejected because the underlying data should be available in the datasource for potential future use (e.g., assisted alignment, peak detection filtering).

### Decision 2: Segment stance intervals by edge transitions
**Choice:** Identify rising (0→1) and falling (1→0) edges in the `robustFC` array to define patch intervals. Each interval spans from rising edge to falling edge.

**Rationale:** Edge-based segmentation produces clean patch boundaries aligned with actual gait phase transitions. This avoids rendering disconnected pixels or jittery edges if samples straddle transitions.

**Alternative considered:** Render individual pixels/samples as small rectangles. Rejected because it would produce visually noisy output and is less efficient.

### Decision 3: Use pyqtgraph FillBetween or rect items for rendering
**Choice:** Overlay filled region items (likely `pg.FillBetween` or custom `QGraphicsRectItem`s) on the plot during paint time, using the Leg2 signal color with primary-segment alpha.

**Rationale:** pyqtgraph's native region primitives keep rendering consistent with the rest of the plot and avoid manual paint event complexity. Filling from plot's lower y-limit up to y=0 is straightforward.

**Alternative considered:** Draw patches in a custom paint event. Rejected because it adds state management complexity and requires careful coordinate mapping. Using plot items is cleaner and integrates better with the existing plot architecture.

### Decision 4: Compute stance intervals once, store as series data
**Choice:** Build a `Leg2StanceIntervals` structure (or similar) during signal series construction that holds (start_time, end_time) tuples for each stance interval.

**Rationale:** Pre-computing intervals at signal series construction time avoids redundant edge detection on every render or offset change. The intervals move with the track offset naturally because they are time-based.

**Alternative considered:** Compute intervals on every render. Rejected because it is inefficient and couples the rendering logic to data processing.

### Decision 5: Stance patches fill from plot's visual bottom to y=0
**Choice:** Stance patches always fill from the plot's lower visual boundary (determined by the current y-limit) up to y=0, ensuring they remain visible and prominent regardless of y-axis range. Patch y-values are recomputed whenever y-limits change (during zoom, signal updates, or auto-scaling).

**Rationale:** Stance phase is biomechanical context critical for alignment. Making it always visible—regardless of coincidental y-limits—ensures users can reliably reference gait transitions. Updating patch coordinates on y-range changes is a lightweight operation in the render path. This approach is robust and handles any future signal range without edge cases.

**Alternative considered:** Fill to fixed y=0 regardless of plot bounds. Rejected because if auto-scaled range is (0.05m, 0.5m), patches would be invisible or nearly so, defeating their purpose. Always-visible is more reliable.

### Decision 6: Always-visible legend entry with no toggle
**Choice:** Add "Stance phase" to the signal plot legend whenever Leg2 ultrasonic is visible. No user control to hide it.

**Rationale:** Keeping stance phase permanently visible makes it a trusted reference for alignment. A toggle would add complexity without clear user benefit; if users don't need it, they can simply ignore the visualization.

**Alternative considered:** Add a checkbox to show/hide stance phase. Rejected because it adds UI clutter and is unnecessary for a lightweight visualization that does not obstruct the signal.

## Risks / Trade-offs

**Risk: Edge detection edge cases**
- Scenario: If `robustFC` has a short spike (1 sample of stance) or is noisy, edge detection could produce many thin patches.
- Mitigation: Assume `robustFC` is clean (it's a controller-generated boolean flag, not a filtered measurement). If needed in future, add minimum-interval filtering, but defer until observed in practice.

**Risk: Performance with many stance intervals**
- Scenario: Long recordings with many gait cycles could produce many patch regions.
- Mitigation: Pre-compute intervals once; rendering many filled items is fast in pyqtgraph. Defer optimization if profiling shows overhead.

**Risk: Color consistency after theme changes**
- Scenario: If Leg2 track color is ever changed, patches need to update automatically.
- Mitigation: Use the existing color derivation system (`derive_signal_plot_color()` and `SIGNAL_PLOT_PRIMARY_SEGMENT_ALPHA`). Patches inherit Leg2 color automatically.

**Trade-off: Always visible vs. optional**
- Decision trades discoverability (users always see stance phase) for simplicity (no toggle). Users who align only ultrasonic signals without video can still see stance context without asking for it.

**Trade-off: Dynamic patch updates on y-range changes**
- Stance patches are recomputed when y-limits change to ensure they always reach from plot bottom to y=0. This adds a small render-path update but guarantees visibility in all scenarios and is simpler than alternative heuristics (artificial minimums, clipping logic).

## Migration Plan

This is a new feature; no migration needed for existing sessions or code.

1. Commit changes to core data structures and import logic
2. Commit changes to signal plot rendering
3. Test with sample `.mat` files to verify stance patch display and alignment behavior
4. Archive OpenSpec change once ready

## Open Questions

None at this time. Design is clear and ready for implementation.
