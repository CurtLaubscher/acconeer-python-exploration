## 1. Timeline Interaction Model

- [x] 1.1 Add explicit Timeline hit testing helpers for playhead, camera, H5, and Leg2 track regions.
- [x] 1.2 Update Timeline mouse press handling so playhead hit testing takes priority over all track bars.
- [x] 1.3 Add Timeline drag state for H5 relative-drag gestures without adding a persisted H5 offset.
- [x] 1.4 During H5 drag, update visible timeline x-limits, shared current time, and every loaded non-H5 offset-bearing track so the H5 bar follows the pointer and other timeline items keep the expected screen-relative positions.
- [x] 1.5 Treat H5 drag as a no-op when no non-H5 offset-bearing tracks are loaded.
- [x] 1.6 Keep H5-derived peak-distance data coupled to H5 during H5 drag rather than shifting it as an independent track.

## 2. UI Feedback And Refresh

- [x] 2.1 Show the draggable track cursor for the H5 bar only when H5 drag can affect at least one non-H5 offset-bearing track.
- [x] 2.2 Refresh Timeline, Signals, camera preview, H5 preview, and offset controls through the existing sync path after H5 drag updates alignment state.
- [x] 2.3 Preserve the playhead's screen-relative position during H5 drag by moving shared current time with the visible x-range.

## 3. Tests

- [x] 3.1 Add a focused GUI test proving a press on the playhead hit area starts playhead dragging instead of dragging an overlapping track bar.
- [x] 3.2 Add a focused GUI or model test proving H5 dragging shifts camera and Leg2 offsets together while leaving H5 without a persisted offset.
- [x] 3.3 Add a focused test proving H5-only drag leaves current time, visible x-limits, and alignment state unchanged.
- [x] 3.4 Add a focused test proving H5-derived peak-distance signal timing remains coupled to H5 while non-H5 offsets shift.

## 4. Verification

- [x] 4.1 Run the focused heatmap alignment GUI tests through the repo-managed Hatch environment.
- [x] 4.2 Launch the GUI with `hatch run app:heatmap-align` and manually verify playhead priority, camera drag, Leg2 drag, H5 drag with non-H5 tracks, and H5-only no-op behavior.
- [x] 4.3 Verify Signals and Timeline current-time indicators remain horizontally aligned after H5 dragging and normal scrubbing.
