## Context

The heatmap alignment workbench has two time-axis views: `AlignmentTimelineWidget` (a fully custom QPainter widget) and `SignalsPlotWidget` (a pyqtgraph plot). They already share a `TimelineRangeModel` as a common x-range source, but that model is currently write-only from the user's perspective — it auto-fits to show all content and resets on every track-bar drag release. Neither widget allows the user to zoom or pan the shared x-range.

`AlignmentTimelineWidget` has no pyqtgraph ViewBox — zoom and pan math would need to be implemented from scratch if done in the widget itself. `SignalsPlotWidget` already has a full pyqtgraph ViewBox with scroll-wheel zoom, right-click-drag zoom, and middle-drag pan implemented and tested.

Currently `SignalsPlotWidget` disables x-distorting transforms (Log X, FFT, Y vs. Y', dy/dx, Phase Map, Invert X) only when x-axis is in Timeline mode; they re-enable in Manual mode. Since this change removes Manual mode entirely, those transforms will always be disabled — they are permanently removed from the menu.

## Goals / Non-Goals

**Goals:**
- Let users zoom and pan the shared timeline/signals x-range
- Keep the two views pixel-perfectly synchronized at all times
- Reuse pyqtgraph's existing zoom/pan math rather than reimplementing it
- Add "Zoom to Fit" to each axis independently (x resets to full recording span; y fits visible data)
- Add clickable off-screen playhead indicator to the timeline
- Remove the auto-fit-on-drag-release behavior
- Simplify the Signals plot right-click menu: remove Auto/Manual x toggle, Mouse Mode toggle, generic View All, and permanently remove x-distorting transforms

**Non-Goals:**
- Independent zoom/pan for timeline vs. signals (always linked)
- Persisting zoom state in session JSON
- Vertical zoom in the timeline
- Keyboard zoom shortcuts (can be added later)

## Decisions

### D1: Signals ViewBox is the zoom/pan authority; Timeline forwards events

`AlignmentTimelineWidget` is a custom QPainter widget with no ViewBox. Rather than reimplementing pyqtgraph's wheel zoom factor, right-click-drag zoom, and pan math in the custom widget, the timeline forwards transformed mouse events to the Signals plot's ViewBox. The ViewBox performs all math, updates its own range, and the resulting `sigRangeChanged` propagates back to `TimelineRangeModel` via the existing `_view_box_range_changed` callback, which then signals the timeline to repaint.

Alternative: implement zoom math manually in the timeline using the ViewBox's `wheelScaleFactor`. Rejected — would need to be reimplemented for each gesture (wheel, right-drag, middle-drag) and would risk diverging from pyqtgraph's behavior if their implementation changes.

### D2: X-coordinate transform for event forwarding

The cursor's time position on the timeline and its equivalent position on the Signals plot must match for zoom to feel correct (zoom is always centered on the cursor's time). The transform:

```
time_s = range_start_s + (cursor_x / timeline_width) * (range_end_s - range_start_s)
signals_x = signals_plot_rect.left() + (time_s - range_start_s) / (range_end_s - range_start_s) * signals_plot_rect.width()
```

Currently the two panels are side-by-side and their time axes are pixel-aligned, so this is near-identity. But encoding the transform explicitly makes it robust to future layout changes where the panels' plot areas no longer share the same pixel column positions.

For event forwarding, a synthetic `QWheelEvent` / `QMouseEvent` is constructed with the transformed x position and dispatched to the Signals plot ViewBox. Vertical mouse position is set to the center of the Signals plot (vertical zoom is disabled on the Signals ViewBox x-axis).

### D3: TimelineRangeModel becomes fully bidirectional

Currently `TimelineRangeModel` is read by both widgets but written only by internal recompute logic. In the new model, `set_visible_range` becomes the push path for any widget that wants to change the range (drag of a track bar, Zoom to Fit, range input fields, forwarded wheel events). The existing `range_changed` signal already notifies all subscribers.

Loop prevention: the existing `_applying_view` flag in `SignalsPlotWidget` prevents a range update received from `TimelineRangeModel` from being re-emitted back. The chain is: ViewBox zoom → `_view_box_range_changed` → `TimelineRangeModel.set_visible_range` → `range_changed` → Signals `_on_timeline_visible_range_changed` → sets `_applying_view=True` → `setXRange` (no re-emit) → done.

This pattern is extensible: any future plot that subscribes to `TimelineRangeModel.range_changed` and sets its own `_applying_view` guard will participate in the shared range correctly without any other changes.

### D4: Auto-fit-on-drag-release removed

`end_visible_range_freeze(recompute=True)` is called on track-bar mouse release, which currently calls `recompute_visible_range()` and resets to Fit All. This will change to `recompute=False` — the freeze is released but the range is left wherever the user had it. The range freeze during drag is still valuable (keeps the view stable while the user is dragging), so `begin_visible_range_freeze` / `end_visible_range_freeze` are retained.

### D5: Signals plot menu simplified — one mode, fixed behavior

Since there is now only one x-axis mode (always linked to `TimelineRangeModel`), the following are removed from the right-click menu:
- Auto/Manual x-axis toggle
- Mouse Mode submenu (1-button vs 3-button; fixing to 3-button behavior)
- Generic "View All" action (replaced by per-axis "Zoom to Fit")
- X-distorting transforms: Log X, FFT/Power Spectrum, Y vs. Y', dy/dx, Phase Map, Invert X — permanently removed (not just disabled)

The x-axis submenu retains only: range min/max input fields (wired to `TimelineRangeModel.set_visible_range`) and a "Zoom to Fit" action (calls `TimelineRangeModel.recompute_visible_range()`).

The y-axis submenu gains a "Zoom to Fit" action (fits y to visible data in current x-window, same as existing y auto-range behavior). Y-only transforms (Log Y, Subtract Mean) are retained as they do not affect the time axis.

Menu patching is done at widget init time by inspecting the pyqtgraph menu structure and hiding/removing specific widgets. This is not a stable public API but the minimum-touch approach reduces future maintenance risk.

### D6: Off-screen playhead indicator — clickable

When `playhead_time_s` is outside `[range_start_s, range_end_s]`, a small filled triangle (≈8px) is drawn at the left or right edge of the timeline plot area pointing inward toward the playhead. Clicking the triangle pans the shared x-range so the playhead lands at ~20% from the near edge (keeping the current zoom level, just shifting the window). This is implemented in `AlignmentTimelineWidget.paintEvent` and `mousePressEvent`.

### D7: Left-drag no longer pans the Signals plot

The new behavior: middle-drag pans, left-drag has no effect on the time range and does not scrub the playhead. This is configured via pyqtgraph ViewBox mouse settings to remove left-button pan while keeping middle-button pan.

### D8: Middle-drag rect zoom disabled

pyqtgraph's 3-button mouse mode supports a middle-drag rubber-band rect zoom that zooms both axes simultaneously. This is disabled by fixing the mouse mode and not exposing the mode toggle, keeping middle-drag as pan-only.

## Risks / Trade-offs

- **Synthetic event dispatch**: constructing and forwarding `QWheelEvent`/`QMouseEvent` to a widget the user didn't click on is slightly unusual. If Qt's event system adds guards against synthetic events in a future version, the forwarding approach would break. Mitigation: isolate the forwarding in a single helper method so it's easy to replace with direct ViewBox API calls if needed.
- **pyqtgraph menu patching**: pyqtgraph's right-click menu structure is not a stable public API. Removing items requires inspecting internal widget structure. Mitigation: do the minimum necessary; avoid deep restructuring; encapsulate all patching in one method.
- **recompute=False on release**: existing callers of `end_visible_range_freeze` pass `recompute=True`. Changing to `False` will affect all drag-release paths. Confirm no other code path depends on the auto-fit-on-release behavior before changing.

## Open Questions

None.
