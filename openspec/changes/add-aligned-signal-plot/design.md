## Context

The heatmap alignment GUI is a PySide6 workbench with a compact shared timeline and an existing `pyqtgraph.PlotWidget` reserved for disabled xcorr diagnostics. Peak-distance JSON import already exists and can annotate the current H5 heatmap frame, but there is no wide time-series view for reviewing continuity, no-detection regions, or future signal sources.

The first target signal is H5-derived peak distance. Future Leg2 `.mat` ultrasonic import is a motivation for the layout and state model, but `.mat` loading is not part of this change.

## Goals / Non-Goals

**Goals:**
- Add a separate boxed Signals area above the Timeline area.
- Use the existing H5 timeline color convention for H5 peak-distance signal rendering.
- Show detected peak distances as a solid primary signal and no-detection candidate distances as lower-alpha signal points/segments.
- Preserve actual gaps for missing values.
- Let the timeline drive the signal plot x-range when x auto-range is enabled.
- Show a passive Signals current-time indicator that follows the Timeline playhead.
- Make the Timeline current-time marker visually and interactively read as the draggable control.
- Allow x and y range modes to be controlled independently.
- Persist signal plot range modes and manual ranges in session JSON.
- Remove visible disabled xcorr controls and dead GUI wiring from the main workbench.

**Non-Goals:**
- Do not add Leg2 `.mat` import.
- Do not add signal overlays to synced video export.
- Do not change current heatmap overlay export behavior.
- Do not implement automated alignment or xcorr suggestions.
- Do not remove lower-level xcorr helper code that may be reused later.

## Decisions

### Separate Signals Group Above Timeline

The signal plot will live in its own `QGroupBox` above the existing Timeline group. This keeps the timeline as the bottom-most temporal control while giving signal review enough horizontal space.

Alternative considered: merge signal plotting into `AlignmentTimelineWidget`. That would make shared x-coordinate rendering easy, but it would mix duration-bar interaction with richer plotting behavior and duplicate features already available through pyqtgraph.

### Use Pyqtgraph With Explicit Range Modes

The Signals area will use `pyqtgraph.PlotWidget` and keep a two-option model per axis. The x-axis automatic option is presented as Timeline mode because it follows the Timeline range and pixel geometry instead of pyqtgraph's default data-fit behavior. The compact menu label should be `Timeline` to avoid cropping in pyqtgraph's axis menu.

Range modes:
- X Timeline: signal x-range follows the current timeline bounds. User x zoom/pan is disabled.
- X manual: normal pyqtgraph x zoom/pan behavior is enabled and the selected x-range is preserved.
- Y auto: normal pyqtgraph-style y auto behavior is used, fitting visible signal data in the current x-window while including zero in the fitted range before padding.
- Y manual: normal pyqtgraph y zoom/pan behavior is enabled and the selected y-range is preserved.

This allows x and y behavior to be mixed independently, such as timeline-following x with manually adjusted y limits.

### Extend The Context Menu Instead Of Building Inline Controls

The plot context menu should expose range mode actions in the same interaction surface as pyqtgraph's existing view controls. The implementation should prefer overriding or relabeling the existing two-state auto/manual behavior rather than adding a custom three-state control.

The x-axis should not use pyqtgraph's stock "Auto Range" behavior directly, because for this plot the automatic x mode means "Timeline", not "fit visible signal data". Y auto can remain close to pyqtgraph's built-in behavior if it fits visible data in the active x-window and includes zero. Tooltip/help text can use fuller wording such as "Match the Timeline x-range; x zoom/pan is disabled" even though the visible axis-menu label is just `Timeline`.

### Timeline Drives Signal X-Range, Not The Reverse

The signal plot will not drive the timeline view. When x Timeline mode is enabled, signal plot x zoom/pan is disabled and the plot follows timeline bounds. When x manual is enabled, the user can inspect signal details without changing the timeline bars.

Matching numeric time limits is not sufficient for visual alignment. In x Timeline mode, the Signals plot data area and Timeline time-bar area must also share the same horizontal time-to-pixel mapping. The preferred implementation is to use the pyqtgraph Signals ViewBox/data rect as the geometry master, convert that rect into Timeline widget coordinates after layout settles, and make the Timeline draw bars, grid lines, and playhead within that same horizontal span. Timeline row labels should remain outside the shared time-mapping rect.

X-axis transformations that break linear shared time mapping should not be allowed while x Timeline mode is active. X inversion and Log X should be disabled or reset in Timeline mode. Actions that change the x-axis meaning away from physical time, such as Y vs. Y' and Power Spectrum/FFT, should also be disabled while x Timeline mode is active. The stock View All action should be disabled or prevented from changing the x range while x Timeline mode is active; it should not silently switch the plot to manual mode.

Y-axis behavior is otherwise unchanged by this polish pass. Y-only transformations such as Log Y and Subtract Mean may remain available if they only affect y presentation or y-values. If a y-only operation causes pyqtgraph to adjust x-limits as a side effect, the implementation should restore the Timeline-matched x-range afterward. `dy/dx` should only be enabled in Timeline mode if it preserves physical-time x-values and the Timeline-matched x-range.

### Current-Time Indicators

The Timeline remains the interactive place to change the shared current time. Its current-time marker should be slightly brighter or otherwise more prominent than the existing light-gray line and should expose a hover cursor over the draggable hit area so users can tell it can be dragged.

The Signals plot should show a subordinate current-time indicator at the same shared time, likely using a non-movable vertical pyqtgraph item. This indicator should be thinner and more muted than the Timeline playhead, with no handle, no hover cursor change, and no drag behavior. It provides readout alignment for plotted signals without making the Signals plot another timeline controller.

### Peak Distance Rendering

H5 peak-distance signals use the same semantic green as the H5 timeline bar. Because thin plot lines need different contrast than filled timeline bars, the implementation should derive readable plot pens from a base H5 track color. In dark mode this may mean lightening the base color; in light mode this may mean darkening it. Candidate/no-detection pens should use the same derived color at lower alpha.

Rendering rules:
- `candidate_peak_distance_m` is the plotted distance value when available.
- Measurements with detected status are drawn as the primary solid signal.
- Measurements with no-detection status are drawn with the same color at lower alpha.
- Missing or unavailable values are represented as gaps, using NaN-separated data rather than connecting through absent data.
- A compact legend identifies detected and candidate/no-detection signals.

### Session Persistence

Add serializable signal plot settings to `AlignmentSession`, including x/y range mode and manual x/y ranges. Missing settings in older session JSON should default to x auto, y auto, and empty manual ranges.

### Xcorr UI Removal

Remove the visible disabled xcorr group elements from the Render area and remove direct signal/control wiring that only serves that disabled UI. Keep lower-level xcorr helper functions if they are isolated and may support future diagnostic work.

## Risks / Trade-offs

- Pyqtgraph built-in context menu behavior may conflict with custom range mode semantics -> use explicit menu action labels and keep GUI-owned range mode as the source of truth.
- Disabling x zoom/pan in auto mode may surprise users familiar with normal pyqtgraph plots -> make the context menu mode obvious and allow switching to manual x range.
- Session schema changes can break older saved sessions if defaults are not handled -> load missing signal plot settings with defaults.
- Candidate no-detection signal can be mistaken for accepted detections -> render it with lower alpha and a distinct legend label.
- Removing visible xcorr controls may obscure future xcorr work -> keep the idea in `ideas.md` and retain isolated helper code for later proposals.
