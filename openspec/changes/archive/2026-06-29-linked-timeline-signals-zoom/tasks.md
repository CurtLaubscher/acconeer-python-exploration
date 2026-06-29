## 1. Remove Auto-Fit on Drag Release

- [x] 1.1 Change `end_visible_range_freeze(recompute=True)` → `recompute=False` in `AlignmentTimelineWidget.mouseReleaseEvent` for camera and Leg2 track-bar drag release
- [x] 1.2 Verify no other call sites pass `recompute=True` that should also change; update if found

## 2. Make TimelineRangeModel Bidirectional

- [x] 2.1 Confirm `TimelineRangeModel.set_visible_range` has no internal guards that would swallow calls from Signals ViewBox range changes
- [x] 2.2 Update `SignalsPlotWidget._view_box_range_changed` to call `TimelineRangeModel.set_visible_range` when the ViewBox range changes due to user interaction (guarded by `_applying_view` to prevent loops)
- [x] 2.3 Verify the `_applying_view` guard prevents infinite feedback loops (ViewBox zoom → model → Signals → ViewBox again)

## 3. Fix Signals Plot Mouse Behavior

- [x] 3.1 Configure the Signals plot ViewBox so left-mouse drag does NOT pan and does NOT scrub the playhead; middle-drag continues to pan
- [x] 3.2 Disable middle-drag rubber-band rect zoom (fix mouse mode so middle-drag is pan-only, not rect-zoom)
- [x] 3.3 Verify middle-drag pans the Signals plot and the range propagates to the timeline via `TimelineRangeModel`

## 4. Event Forwarding: Timeline → Signals ViewBox

- [x] 4.1 Implement a helper `_timeline_x_to_signals_x(cursor_x)` that converts a pixel x on the timeline to the equivalent pixel x on the Signals plot ViewBox using the shared time-range math
- [x] 4.2 Implement `AlignmentTimelineWidget.wheelEvent`: transform cursor x using the helper, construct a synthetic `QWheelEvent` with the transformed position and suppressed vertical component, and dispatch it to the Signals plot ViewBox
- [x] 4.3 Implement middle-drag pan forwarding in `AlignmentTimelineWidget`: on middle-button press/move/release, construct and forward synthetic `QMouseEvent`s to the Signals plot ViewBox with transformed x coordinates
- [x] 4.4 Implement right-click-drag zoom forwarding in `AlignmentTimelineWidget`: forward right-button press/move/release events to the Signals plot ViewBox with transformed x coordinates
- [x] 4.5 Ensure forwarded right-click events do not trigger the Signals plot context menu or other unintended pyqtgraph right-click behaviors

## 5. Signals Plot Right-Click Menu

- [x] 5.1 Remove the Auto/Manual x-axis toggle from the Signals plot right-click menu
- [x] 5.2 Remove the Mouse Mode submenu from the Signals plot right-click menu
- [x] 5.3 Remove the generic "View All" action from the Signals plot right-click menu
- [x] 5.4 Permanently remove x-distorting transforms from the Signals plot menu: Log X, Power Spectrum (FFT), Y vs. Y', dy/dx, Phase Map, and Invert X (these were previously only disabled in Timeline mode; now they are gone entirely)
- [x] 5.5 Wire the x-axis range min/max input fields to call `TimelineRangeModel.set_visible_range` on commit instead of setting the ViewBox directly
- [x] 5.6 Add a "Zoom to Fit" action to the X Axis submenu that calls `TimelineRangeModel.recompute_visible_range()`
- [x] 5.7 Add a "Zoom to Fit" action to the Y Axis submenu that fits the y-axis to visible signal data in the current x-window (same as existing y auto-range logic)

## 6. Timeline Context Menu

- [x] 6.1 Add a right-click context menu to `AlignmentTimelineWidget` with a "Zoom to Fit" action
- [x] 6.2 Wire "Zoom to Fit" to call `TimelineRangeModel.recompute_visible_range()`
- [x] 6.3 Ensure the timeline context menu does not appear when the right-click is the start of a right-drag zoom gesture (show menu only on right-click-release with minimal movement)

## 7. Session Compatibility

- [x] 7.1 Remove `x_range_mode` and `manual_x_range` from the Signals plot session save path
- [x] 7.2 Ensure loading a session containing those fields does not error (ignore unknown/stale fields gracefully)

## 8. Off-Screen Playhead Indicator

- [x] 8.1 In `AlignmentTimelineWidget.paintEvent`, after drawing the normal playhead, check if `playhead_time_s` is outside `[range_start_s, range_end_s]`
- [x] 8.2 If off-screen to the right, draw a small filled triangle (≈8px) pointing right at the right edge of the timeline plot area using the playhead color
- [x] 8.3 If off-screen to the left, draw a small filled triangle pointing left at the left edge of the timeline plot area using the playhead color
- [x] 8.4 Ensure no indicator is drawn when the playhead is within the visible range
- [x] 8.5 In `AlignmentTimelineWidget.mousePressEvent`, detect a click on the off-screen indicator triangle and pan the shared x-range so the playhead lands at ~20% from the near edge (preserving current zoom span)
