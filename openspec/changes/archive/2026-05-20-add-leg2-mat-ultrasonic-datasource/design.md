## Context

The heatmap alignment workbench currently aligns an H5 heatmap track and a camera video track on a shared physical timeline. It also supports an optional H5-derived peak-distance JSON datasource rendered in the Signals plot. The accepted Signals plot behavior already provides timeline-matched x-axis geometry, current-time indicators, y auto-scaling, and a compact legend.

Leg2 `.mat` logs contain ultrasonic distance data that should be compared against the H5 peak-distance signal and camera video. The first implementation should stay narrowly targeted to the known Leg2 export shape rather than building a general MATLAB variable browser or a generic multi-source framework.

The repo-managed `app` Hatch environment already includes the `algo` optional dependency group, which includes `scipy`, so MATLAB v5 `.mat` loading should not require a new runtime dependency unless implementation discovers a format that needs different support.

## Goals / Non-Goals

**Goals:**

- Load a Leg2 `.mat` file interactively and from a startup argument.
- Extract the known ultrasonic time, raw distance, filtered distance, and reliable ultrasonic-use flag arrays.
- Add a dedicated Leg2 `.mat` timeline track with its own color and draggable offset.
- Display one selected ultrasonic signal at a time in the existing Signals plot.
- Provide load and unload controls for Leg2 `.mat` files similar to the existing Peak-Distance JSON controls.
- Persist the loaded `.mat` datasource, selected signal, visibility, and offset in alignment sessions and artifact-style startup flows.
- Preserve existing H5/camera/peak-distance behavior for sessions without a `.mat` datasource.

**Non-Goals:**

- Generic `.mat` variable browsing or arbitrary signal selection.
- Automatic offset estimation, 1D signal cross-correlation, image cross-correlation, or any alignment suggestion.
- Dedicated `.mat` offset nudge/spin controls.
- Track linking, multi-select, fixed-track controls, or a generalized resource panel.
- Exporting the ultrasonic signal into synced videos.
- Supporting every MATLAB `.mat` variant if it requires a broader loader architecture; MATLAB v7.3/HDF5 support can be added later if real files require it.

## Decisions

### Add A Leg2-Specific Datasource Model

Create a small Leg2 ultrasonic datasource model in `heatmap_alignment_core.py` rather than overgeneralizing the existing peak-distance datasource. The model should separate persisted settings from loaded data:

- persisted settings: path, visible flag, selected signal kind, offset seconds
- loaded data: elapsed time seconds, raw distance meters, filtered distance meters, reliable ultrasonic-use mask, display metadata

This mirrors the existing optional peak-distance datasource pattern while allowing the `.mat` source to own timing and offset independently of H5 frames.

Alternative considered: introduce a generic pluggable resource/track datasource framework now. That would fit future ideas, but it is larger than this feature needs and would make the first `.mat` import harder to review.

### Use Known Leg2 Field Paths And Fail Clearly

The importer should target the known exported paths:

- `DataRecordCommon.timeOut` for time
- `Ultrasonic.Distance` for raw ultrasonic distance
- `DataRecordCommon.ultrasonic_filtered` for filtered ultrasonic distance
- `DataRecordCommon.ReliableFlag` for reliable ultrasonic-use segmentation

All four arrays are required for this first known-schema importer. If any required field is missing, invalid, or length-incompatible after trailing zero-time cleanup, the importer should reject the file with a user-facing error that names the field or mismatch that caused the failure.

The importer should remove only erroneous trailing zero-time samples that occur after valid samples. After cleanup, time must be finite, length-compatible, and strictly increasing enough to define a physical x-axis. Invalid data should produce a user-facing load error and leave any previously loaded `.mat` datasource unchanged.

Alternative considered: silently truncate mismatched arrays or fall back to sample index. That could hide data-quality errors during alignment, so the first version should reject invalid required data and explain why, such as an array length mismatch.

### Normalize Time And Units At Import

The importer should subtract the first retained `timeOut` sample so the Leg2 source uses elapsed seconds starting at zero. Ultrasonic distance values should be converted from millimeters to meters at import. This keeps plotting and alignment units consistent with H5 peak-distance measurements.

Alternative considered: preserve absolute Leg2 timestamps in the plot. Absolute `timeOut` values are not directly meaningful in the shared H5 timeline and would make the offset model less obvious.

### Represent Leg2 As A Timeline Track

The `.mat` datasource should add a third timeline row with its own semantic color and duration. Dragging the `.mat` row should behave like dragging the camera/video row, including allowing the row to be dragged partially or fully outside the visible timeline range. On release, it should update the Leg2-to-H5 offset using the same sign convention as the camera row: source time equals shared H5 time plus source offset, and the timeline row start is `-offset_s`.

The H5 track may still be the practical reference for this proposal, but the timeline implementation should avoid assuming that every non-H5 track is the camera. This keeps the work compatible with later linked/fixed track ideas without implementing those ideas now.

Numerical offset or aligned-start labels should be drawn as part of the Timeline row for offset-bearing tracks rather than in a separate control strip. For each offset-bearing track, place the label just outside the left side of that track's bar, right-aligned toward the bar with a small margin. Use plain floating text with no pill/background. If the bar is too close to the visible edge or outside the visible timeline range, hide or clip the label so it does not overlap unrelated content or appear detached from the track. The current fixed H5 reference track does not need a label while it starts at shared time zero.

Alternative considered: attach the ultrasonic signal only to the Signals plot without a timeline track. That would make the offset state invisible and harder to align manually.

### Plot One Ultrasonic Signal At A Time

The Signals plot should show either raw or filtered ultrasonic distance, not both simultaneously by default. A compact UI control should let the user choose raw versus filtered. The selected signal should share the Leg2 track color family. Samples where `DataRecordCommon.ReliableFlag` is true/1 should render as the primary signal with slight transparency so overlapping plotted signals remain visible. Samples where `DataRecordCommon.ReliableFlag` is false/0 should render lower alpha using the same faded style as the existing non-primary distance segments. Missing values should remain gaps.

Alternative considered: plot raw and filtered simultaneously. That can clutter the limited Signals area and make flag-based segmentation harder to read.

### Keep Segmented Signals Visually Continuous

Any Signals plot series split into primary and faded/lower-alpha portions should remain visually continuous across condition changes. The primary portion is used where the condition is satisfied, such as detected H5 peaks or Leg2 ultrasonic samples where `DataRecordCommon.ReliableFlag` is true. The faded portion should bridge the adjacent plottable samples where the condition is not satisfied, including the transition into and out of primary regions, so the user does not see artificial breaks caused only by styling segmentation.

True missing values remain different: if a sample has no plottable x/y value, the plot should leave a real gap rather than interpolating through it.

### Reuse Existing Signals Plot Range Behavior

The Leg2 signal should use the existing Signals plot range modes, timeline-matched x-axis behavior, legend, y auto-scaling, and passive current-time indicator. The plotted x-values should be transformed into shared timeline coordinates using the Leg2 offset so they line up with the `.mat` timeline row, H5 peak distance, and current-time indicator.

Alternative considered: add a separate plot or independent axis for Leg2 ultrasonic data. Since the units are meters, the existing distance-oriented Signals plot is sufficient for this first version.

### Persist Session And Startup State

Alignment sessions should gain optional Leg2 `.mat` datasource settings. Loading older sessions must default to no `.mat` datasource. Loading a session with a stored `.mat` path should attempt to reload it using the same validation path as interactive import; missing or invalid files should report a clear warning while keeping the rest of the session usable.

Add a startup argument such as `--mat` for parity with `--h5`, `--camera`, `--artifact`, and `--peaks`. If both a saved session and explicit `--mat` are provided, the explicit startup `.mat` should replace any stored session `.mat` datasource after the session loads, matching the existing peak-distance override pattern.

## Risks / Trade-offs

- [MAT export shape varies] -> Keep the importer errors specific and include field names so new variants can be added deliberately.
- [Large `.mat` files load slowly] -> Keep the first pass focused on needed arrays and leave on-demand/resource-quality controls as future work unless real files prove impossible to load.
- [Multiple draggable tracks make timeline behavior more complex] -> Scope this to one additional draggable track and add tests for camera and Leg2 offset independence.
- [ReliableFlag semantics may differ between logs] -> Treat `DataRecordCommon.ReliableFlag` as display segmentation only; do not drop samples or change alignment state based on it.
- [Session reload can fail when files move] -> Keep the GUI usable and report the `.mat` reload failure without invalidating the camera/H5 alignment session.
