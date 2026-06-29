## Why

The timeline always shows the full recording span, making it difficult to do precise track-offset adjustments on long recordings. Zooming in is not possible. The Signals plot supports zoom/pan independently but the two are conceptually the same time axis and should always move together.

## What Changes

- The timeline and Signals plot always share a single x-range — zoom or pan one, the other follows immediately
- The `TimelineRangeModel` becomes the single bidirectional authority for the shared x-range; both widgets push changes to it and subscribe to it
- Scroll-wheel zoom and right-click-drag zoom work on the timeline by forwarding the transformed mouse event to the Signals plot's ViewBox, which performs all zoom math; the resulting range change propagates back via `TimelineRangeModel`
- Middle-mouse-drag pans on both the timeline and Signals plot; left-drag on the Signals plot no longer pans and does not change the playhead or scrub
- Auto-fit-on-drag-release removed: releasing a dragged track bar no longer resets the view to show everything
- **"Zoom to Fit"** action added: resets the shared x-range to the full recording span; available as a right-click item on the timeline, and as an action in each of the Signals plot's X Axis and Y Axis submenus (each fitting only their respective axis)
- The generic "View All" action is removed from the Signals plot right-click menu
- Signals plot x-axis menu simplified: Auto/Manual toggle removed; range inputs (min/max) retained and wired to push to `TimelineRangeModel`; "Zoom to Fit" added
- Signals plot y-axis menu gains a "Zoom to Fit" action that fits only the y-axis
- Mouse Mode toggle removed from the Signals plot right-click menu; mouse behavior is fixed
- All x-axis-distorting transforms (Log X, FFT, Y vs. Y', dy/dx, Phase Map) and x-axis invert are permanently removed from the Signals plot menu (previously they were only disabled in Timeline mode; now there is no other mode)
- Off-screen playhead indicator: a small directional triangle is drawn at the left or right edge of the timeline when the playhead is outside the visible range; clicking the indicator pans the view to bring the playhead to ~20% from the near edge

## Capabilities

### New Capabilities

- `linked-timeline-signals-zoom`: Shared x-range zoom and pan between the timeline and Signals plot, with "Zoom to Fit" reset and off-screen playhead indicator

### Modified Capabilities

- `heatmap-alignment-gui`: The timeline widget gains zoom/pan interaction and a clickable off-screen playhead indicator; the Signals plot x-axis interaction model changes (left-drag no longer pans, menu simplified, x-distorting transforms removed permanently)

## Impact

- `user_tools/heatmap_alignment_timeline_widgets.py`: `TimelineRangeModel.recompute_visible_range` no longer called on drag release; `AlignmentTimelineWidget` gains `wheelEvent`, middle-drag pan forwarding, right-drag zoom forwarding, clickable off-screen playhead indicator; `SignalsPlotWidget` menu patching updated; `TimelineRangeModel.set_visible_range` becomes the push target for both widgets
- `user_tools/heatmap_alignment_core.py` / session: x-range not persisted (no session changes needed)
- `user_tools/heatmap_alignment_gui.py`: wiring between `TimelineRangeModel` and Signals plot updated; Signals plot mouse mode fixed
