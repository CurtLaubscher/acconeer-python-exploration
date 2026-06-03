## Context

The heatmap alignment GUI currently has two current-time indicators on the shared physical timeline: an interactive Timeline playhead in `AlignmentTimelineWidget` and a passive Signals plot line implemented as a non-movable `pyqtgraph.InfiniteLine`. Earlier aligned-signal-plot work intentionally made the Timeline the only place to drag "now", while the Signals line only provided visual alignment.

That distinction is now too restrictive. The Signals plot is the main inspection surface for peak-distance and Leg2 time-series data, and users naturally expect to scrub from the visible current-time line while inspecting a signal. The change should preserve the existing range model: dragging the Signals playhead changes shared current time only, not plot range, plot range mode, timeline bounds, offsets, or dirty state.

## Goals / Non-Goals

**Goals:**

- Let users drag the Signals current-time indicator from a narrow hit area around the line.
- Make the Signals and Timeline playhead drag affordances feel consistent.
- Preserve Signals plot x/y range modes and current visible ranges during Signals playhead scrubbing.
- Allow Signals manual-x mode to scrub according to the Signals plot's current time-to-pixel mapping, even when that differs from the Timeline mapping.
- Apply a shared, named playhead transparency policy so both playheads obscure less underlying content.
- Keep playhead-only current-time changes excluded from session dirty tracking.

**Non-Goals:**

- Do not turn the entire Signals plot background into a scrub surface.
- Do not make Signals plot drag gestures update timeline visible bounds or range modes.
- Do not persist playhead position policy changes or revisit `timeline.current_time_s` dirty tracking.
- Do not change duration-bar dragging, track offset behavior, or H5 alignment-drag semantics.

## Decisions

### Signals Playhead Emits Current-Time Changes

The Signals plot should expose a dedicated signal for current-time changes caused by its playhead drag. The main window can handle that signal through the same behavior as Timeline scrubbing: assign `session.timeline.current_time_s`, re-anchor playback timing, and refresh previews with the scrub hint.

Alternative considered: make the `InfiniteLine` directly movable and observe pyqtgraph's item-change signals without an explicit widget-level signal. That is compact, but it makes it easier for pyqtgraph range or item behavior to leak into application semantics. A widget-level signal keeps the shared-time contract explicit and mirrors the existing Timeline widget boundary.

### Playhead Hit Area, Not Plot Background

Mouse press and hover handling should only activate scrubbing near the Signals playhead. Background plot interactions should remain governed by the current pyqtgraph mode, especially in manual x mode where users may pan or zoom the signal view.

Alternative considered: click-to-scrub anywhere in the Signals plot. That is efficient for navigation, but it conflicts with normal plot inspection and would expand this change beyond "make the now line draggable".

### Manual X Mode Uses Signals Pixel Mapping

When Signals x is manual, the Signals plot can display a different x range than the Timeline. Dragging the Signals playhead should convert pointer x-position through the Signals ViewBox, so the scrubbed time follows the Signals plot's current x scale. This means the time delta per pixel can differ between the Signals and Timeline playheads, which is expected behavior.

Alternative considered: force Signals scrubbing through the Timeline visible range model. That would keep both handles numerically identical per screen pixel, but it would make the Signals handle feel wrong when the plot is manually zoomed.

### Matching Affordance And Shared Transparency

The Signals playhead should use the same horizontal resize cursor as the Timeline playhead and should look/feel like the same class of handle. Both playheads should use a named alpha value rather than a magic number; a modest transparency in the 10-20% range should keep underlying signal and bar content readable without making the playhead hard to find.

Alternative considered: keep the Signals playhead visually subordinate. That matched the old passive-readout contract, but once both indicators are draggable, visual subordination makes the Signals control look less trustworthy than the Timeline control.

## Risks / Trade-offs

- [Pyqtgraph item dragging may change view state or fight plot interactions] -> Prefer explicit mouse handling or tightly constrained `InfiniteLine` behavior that emits current-time changes without changing ranges.
- [Signals and Timeline handles scrub different amounts per pixel in manual x mode] -> Capture this as expected behavior and keep the cursor/line interaction local to the plot's current x mapping.
- [Making both playheads visually identical may reduce the old active/passive distinction] -> The distinction is no longer behaviorally valid; range-mode preservation provides the important boundary.
- [Playhead transparency can reduce contrast on dense signal regions] -> Use a named constant that can be tuned after visual testing rather than scattering hard-coded alpha values.

## Open Questions

- Exact default alpha: start around 80-90% opacity (10-20% transparency), then tune by visual inspection.
- Exact Signals hit-area width: likely match the Timeline playhead hit width unless pyqtgraph item geometry makes a slightly different value feel better.
- Whether the Timeline's existing empty-background click-to-scrub behavior should remain as-is; this proposal does not change it.
