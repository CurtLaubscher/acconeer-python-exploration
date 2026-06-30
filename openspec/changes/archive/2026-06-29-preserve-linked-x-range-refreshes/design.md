## Context

The heatmap alignment workbench now has one linked x-range shared by the custom Timeline widget and the pyqtgraph Signals plot. The intended interaction model is that pan/zoom changes come from user navigation or explicit "Zoom to Fit" actions. In practice, the preview refresh pipeline still recomputes the timeline range as a side effect: `_sync_timeline_feedback()` calls `_update_timeline_range_from_session()`, which calls `TimelineRangeModel.recompute_visible_range()`, and only preserves the previous range when a caller passes `timeline_visible_range_s`.

That default is fragile. Any new call to `_sync_previews()` without the preservation argument can reset the shared range after a delayed worker completion or unrelated UI refresh. This has already happened for source-resolution viewport completion and resource-job completion.

## Goals / Non-Goals

**Goals:**
- Make shared x-range preservation the default behavior for preview refreshes and resource mutations.
- Require explicit, intent-revealing code for operations that recompute/reset the shared x-range.
- Preserve x-range across camera/H5 load, reload, replace, unload, clear-all-resources, async job completion, source-resolution viewport completion, render/color/viewport/export changes, peak selector changes, Leg2 signal changes, signal data refreshes, scrubbing, and playback.
- Keep opening/loading a session as a range-resetting operation that recomputes to the session/resource domain.
- Keep close-session/new-empty-session as a range-resetting operation that returns to a stable blank range.
- Define the no-resource fallback range as `0..60 s`.

**Non-Goals:**
- Persisting zoom state in session JSON.
- Adding out-of-view track indicators.
- Fixing the timeline playhead line/hit-test when the playhead is outside the visible range.
- Changing y-axis auto/manual behavior.

## Decisions

### D1: Preserve x-range by default

`_sync_previews()` should preserve the existing shared x-range unless the caller explicitly requests a range recompute/reset.

Alternative: keep `_sync_previews()` as a recompute-by-default function and audit each call site to pass the current range where appropriate. Rejected because the current bug class is caused by missed call sites; preserving by default makes future refreshes safe.

### D2: Use explicit reset/recompute entry points

Range-resetting operations should use a clearly named path or parameter, such as an explicit `recompute_timeline_range=True` plan flag or a dedicated helper. Valid reset callers are "Zoom to Fit", session load/open, and close-session/new-empty-session. Track-drag paths that intentionally pan while preserving zoom should continue to use direct `TimelineRangeModel.set_visible_range(...)`.

### D3: Keep resource changes from changing x-range

Resource load/reload/replace/unload and async completion update the timeline track state and plotted data, but do not change the visible x-range. If the new data lies completely outside the current window, the timeline may show no bars until the user pans, zooms, or chooses "Zoom to Fit".

This favors spatial stability over automatic discovery. Future off-screen track indicators can make this state more discoverable without clobbering user navigation.

### D4: Use `0..60 s` as the blank/default range

When there are no resources to fit, explicit reset operations use `0..60 s`. This gives the empty timeline a practical scale for this workflow and avoids disabling "Zoom to Fit" based on resource state.

Alternative: disable "Zoom to Fit" when no resources are loaded. Rejected because it adds avoidable UI state logic while still requiring some internal blank range.

## Risks / Trade-offs

- Preserving a range outside newly loaded data can temporarily show an empty timeline -> Users can choose "Zoom to Fit"; future track off-screen indicators should improve discoverability.
- Changing `_sync_previews()` semantics may affect many call sites -> Add focused tests for representative call-site classes: async completion, resource unload, display-only changes, explicit reset, and session load.
- Existing helper names may imply recompute behavior -> Rename or introduce intent-revealing helpers so future changes do not reintroduce implicit reset behavior.
