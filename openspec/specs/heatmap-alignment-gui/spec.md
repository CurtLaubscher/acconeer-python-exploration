## Purpose

Provide a standalone workbench for manually aligning one camera video track with one H5-rendered Sparse IQ heatmap track, saving that alignment as a session, and exporting a synced video with a plotted heatmap overlay.
## Requirements
### Requirement: Standalone alignment workbench
The system SHALL provide a standalone PySide6 user tool for aligning one camera video track with one H5-rendered Sparse IQ heatmap track.

#### Scenario: Launch alignment workbench
- **WHEN** the user launches the alignment workbench
- **THEN** the system displays controls for loading a camera video, loading an H5 radar recording, viewing both sources, adjusting alignment, and saving or loading an alignment session

### Requirement: H5 heatmap truth rendering
The system SHALL render the ground-truth heatmap directly from the selected H5 radar recording using the same Sparse IQ distance/velocity map logic used by the existing heatmap video exporter.

#### Scenario: Load H5 recording
- **WHEN** the user loads an H5 radar recording
- **THEN** the system selects the default session, group, entry, and subsweep using exporter-compatible selection behavior and displays a rendered heatmap frame

#### Scenario: Adjust color limits
- **WHEN** the user changes the rendered heatmap color minimum or maximum
- **THEN** the system updates the rendered heatmap preview using the new limits without requiring a pre-rendered heatmap video

### Requirement: Camera viewport definition
The system SHALL allow the user to define one fixed four-corner viewport over the heatmap body visible in the camera video.

#### Scenario: Drag viewport corner
- **WHEN** the user drags a viewport corner in the camera video view
- **THEN** the system updates the viewport quadrilateral and the rectified viewport preview

#### Scenario: Stationary viewport reuse
- **WHEN** the user scrubs to another camera video time
- **THEN** the system applies the same viewport quadrilateral to the new camera frame

### Requirement: Rectified viewport preview
The system SHALL rectify the selected camera viewport to a display resolution suitable for direct visual comparison with the rendered heatmap preview.

#### Scenario: Display comparable previews
- **WHEN** both the camera video and H5 recording are loaded and a viewport is defined
- **THEN** the system displays the rectified camera viewport and rendered heatmap in same-shaped preview regions suitable for manual visual comparison

### Requirement: Viewport visibility transforms
The system SHALL allow the user to toggle and tune viewport enhancement for the rectified camera viewport preview to make manual comparison against the rendered H5 heatmap easier.

#### Scenario: Disable viewport enhancement
- **WHEN** the user disables viewport enhancement
- **THEN** the system displays the rectified camera viewport without additional visibility transformation and disables enhancement tuning controls

#### Scenario: Enable viewport enhancement
- **WHEN** the user enables viewport enhancement
- **THEN** the system displays the rectified camera viewport after low/high/gamma correction while leaving the camera source view and rendered H5 heatmap preview unchanged

#### Scenario: Tune viewport range
- **WHEN** the user drags the low or high range handles for viewport enhancement
- **THEN** the system updates the enhanced viewport preview using the selected correction range

#### Scenario: Tune viewport curve
- **WHEN** the user adjusts the viewport enhancement gamma control
- **THEN** the system updates the enhanced viewport preview using the selected correction curve

#### Scenario: Map corrected viewport to viridis
- **WHEN** the user enables viridis mapping while viewport enhancement is enabled
- **THEN** the system converts the corrected viewport luminance to viridis colors using a 1D lookup

#### Scenario: Preserve corrected original colors
- **WHEN** the user disables viridis mapping while viewport enhancement is enabled
- **THEN** the system displays the corrected viewport using the original viewport colors rather than grayscale

#### Scenario: Persist viewport visibility settings
- **WHEN** the user saves and reloads an alignment session
- **THEN** the system restores the viewport enhancement enabled state, viridis mapping state, correction range, and gamma value

#### Scenario: Load older session without visibility settings
- **WHEN** the user loads an alignment session that does not contain viewport visibility settings
- **THEN** the system uses defaults equivalent to the raw viewport preview behavior

#### Scenario: Preserve manual alignment authority
- **WHEN** viewport visibility transforms are enabled
- **THEN** the system does not automatically change temporal offset or viewport geometry based on the transformed preview

### Requirement: Native viewport geometry coordinates
The system SHALL store viewport geometry in original camera video pixel coordinates so source-resolution viewport operations use the native source coordinate space.

#### Scenario: Display native viewport geometry on proxy preview
- **WHEN** the camera source is displayed through a proxy or preview-resolution video
- **THEN** the system maps the native viewport corners into the preview coordinate space for drawing, hit testing, and editing

#### Scenario: Drag viewport edge in camera preview
- **WHEN** the user drags a viewport edge in the camera source preview
- **THEN** the system moves the two edge corners according to the current cursor position relative to the drag start position in displayed camera-image coordinates

#### Scenario: Drag viewport center in camera preview
- **WHEN** the user drags the viewport center in the camera source preview
- **THEN** the system moves all viewport corners according to the current cursor position relative to the drag start position in displayed camera-image coordinates

#### Scenario: Rectify low-resolution viewport from native geometry
- **WHEN** the system renders the fast viewport preview from the proxy or preview-resolution camera frame
- **THEN** the system scales the native viewport corners to that frame's coordinate space before rectification

#### Scenario: Rectify source-resolution viewport from native geometry
- **WHEN** the system renders a source-resolution viewport preview from the original camera video
- **THEN** the system uses the native viewport corners directly against the original-resolution camera frame

#### Scenario: Persist native viewport geometry
- **WHEN** the user saves and reloads an alignment session
- **THEN** the viewport geometry remains expressed in original camera video pixel coordinates

### Requirement: Source-resolution paused viewport preview
The system SHALL render a source-resolution rectified viewport preview from the original camera video after viewport state remains idle briefly while playback is paused.

#### Scenario: Invalidate stale source-resolution viewport immediately
- **WHEN** viewport-relevant state changes
- **THEN** the system immediately invalidates any pending source-resolution viewport result and displays the fast low-resolution viewport preview

#### Scenario: Debounce source-resolution viewport work
- **WHEN** viewport-relevant state stops changing while playback is paused
- **THEN** the system waits approximately 200 ms before starting source-resolution viewport rendering

#### Scenario: Use latest source-resolution request only
- **WHEN** a source-resolution viewport worker finishes with a stale request token
- **THEN** the system ignores that result and keeps the current viewport preview

#### Scenario: Accept current source-resolution request
- **WHEN** a source-resolution viewport worker finishes with the latest matching request token
- **THEN** the system displays the source-resolution rectified viewport preview

#### Scenario: Skip source-resolution preview during playback
- **WHEN** playback is active
- **THEN** the system does not schedule source-resolution viewport rendering

#### Scenario: Enhance source-resolution viewport when available
- **WHEN** viewport enhancement is enabled and a current source-resolution viewport result is available
- **THEN** the system applies the viewport visibility transform to the source-resolution viewport frame before display

#### Scenario: Fall back to low-resolution viewport
- **WHEN** no current source-resolution viewport result is available or source-resolution rendering fails
- **THEN** the system displays the fast low-resolution viewport preview

### Requirement: Shared physical timeline
The system SHALL represent camera video time, H5 heatmap time, and loaded offset-bearing datasource time on a shared timeline measured in physical seconds.

#### Scenario: Scrub shared timeline
- **WHEN** the user moves the current-time marker on the timeline
- **THEN** the system updates the camera video frame, rectified viewport frame, and rendered heatmap frame for the corresponding aligned times

#### Scenario: Drag non-H5 offset-bearing track
- **WHEN** the user drags a non-H5 offset-bearing track horizontally
- **THEN** the system updates that track's stored offset in seconds and refreshes the displayed previews

#### Scenario: Use existing camera offset controls
- **WHEN** the user uses the existing camera offset spinbox or nudge controls to change alignment
- **THEN** the system updates the stored camera-to-H5 offset in seconds and refreshes the displayed previews

#### Scenario: View track placement
- **WHEN** both the camera video and H5 heatmap are loaded
- **THEN** the system displays compact horizontal duration bars on a shared seconds axis, with the H5 heatmap as the fixed reference track and the camera video as a draggable alignment track

#### Scenario: Drag camera track
- **WHEN** the user drags the camera duration bar horizontally
- **THEN** the system updates the stored camera-to-H5 offset and refreshes the displayed previews while keeping the H5 bar fixed

#### Scenario: Drag H5 track as relative alignment handle
- **WHEN** the user drags the H5 duration bar horizontally while at least one non-H5 offset-bearing track is loaded
- **THEN** the H5 bar follows the pointer, the Timeline playhead keeps its screen-relative position, loaded non-H5 offset-bearing tracks preserve their screen-relative positions, and the system updates non-H5 offsets as needed without persisting an H5 offset

#### Scenario: Preserve H5-derived datasource alignment during H5 drag
- **WHEN** the user drags the H5 duration bar while an H5-derived peak-distance datasource is loaded
- **THEN** the system keeps the H5-derived peak-distance datasource coupled to the H5 recording rather than treating it as an independently shifted non-H5 track

#### Scenario: No-op H5-only drag
- **WHEN** the user drags the H5 duration bar and no non-H5 offset-bearing track is loaded
- **THEN** the system does not change the shared current time, visible timeline x-limits, or persisted alignment state

### Requirement: Manual playback preview
The system SHALL provide basic playback controls for previewing the aligned camera video and rendered heatmap together without requiring MVP audio playback.

#### Scenario: Play aligned tracks
- **WHEN** the user starts playback
- **THEN** the system advances the shared current time according to elapsed physical time and updates the camera, rectified viewport, and rendered heatmap previews according to the current offset

#### Scenario: Slow preview refresh
- **WHEN** preview rendering cannot keep up with every source frame
- **THEN** the system skips displayed frames as needed rather than slowing the shared playback clock

### Requirement: Disposable GUI preview proxy
The system SHALL be allowed to use a disposable local preview proxy for camera playback and scrubbing, while keeping alignment session files pointed at the original camera-video path.

#### Scenario: Load large camera video for GUI preview
- **WHEN** the user loads a camera video whose native resolution is higher than the GUI preview target
- **THEN** the system may generate or reuse a local preview proxy for GUI playback and scrubbing instead of decoding the original source directly on each preview refresh

#### Scenario: Save session after proxy-backed preview
- **WHEN** the user saves an alignment session after working against a preview proxy
- **THEN** the session file stores the original camera-video path rather than the disposable local proxy path

### Requirement: Xcorr diagnostic placeholder
The system SHALL defer xcorr diagnostics in the MVP and SHALL NOT run expensive xcorr computation during source load or normal manual preview interaction.

#### Scenario: Load sources without xcorr
- **WHEN** the user loads a camera video or H5 recording
- **THEN** the system does not run cross-correlation automatically

#### Scenario: Preserve manual alignment authority
- **WHEN** the xcorr diagnostic has a peak at a different lag than the current offset
- **THEN** the system does not change the current offset unless the user manually adjusts it

### Requirement: Alignment session persistence
The system SHALL save and load JSON alignment session files containing the state needed to reproduce a manual alignment session, including any optional imported distance-measurement datasource.

#### Scenario: Save alignment session
- **WHEN** the user saves an alignment session
- **THEN** the system writes source paths, selected H5 session/group/entry/subsweep, render color limits, camera viewport corners, viewport output dimensions, export overlay settings, temporal offset in seconds, preprocessing settings, and optional imported distance-measurement datasource metadata to JSON

#### Scenario: Load alignment session
- **WHEN** the user loads a saved alignment session
- **THEN** the system restores the session snapshot described by the JSON file using session load reconciliation so each resource slot is kept, loaded, or unloaded as needed, restores source selections, viewport geometry, render settings, temporal offset, preview state, and optional imported distance-measurement datasource metadata, and always applies remaining non-resource session fields after reconciliation

### Requirement: Session startup CLI
The system SHALL allow the heatmap alignment GUI to load a saved alignment session on startup using a session-specific command-line argument.

#### Scenario: Load session on startup
- **WHEN** the user launches the heatmap alignment GUI with a saved alignment session path passed to `--session`
- **THEN** the system loads that saved alignment session after the main window is shown, scheduled on the GUI event loop so startup can paint the workbench before resource loading begins

#### Scenario: Session startup takes precedence over source startup arguments
- **WHEN** the user launches the heatmap alignment GUI with `--session` and individual camera or H5 startup arguments
- **THEN** the system loads the saved alignment session as the source of camera, H5, viewport, render, and alignment state rather than partially overriding it with the individual camera or H5 arguments

#### Scenario: Optional datasource startup arguments may override session datasources
- **WHEN** the user launches the heatmap alignment GUI with `--session` and an explicit optional datasource startup argument such as peak-distance JSON or Leg2 MAT
- **THEN** the system loads the saved alignment session first and then applies the explicit optional datasource startup argument using the same override behavior as the corresponding datasource requirement

#### Scenario: Reject legacy artifact startup argument
- **WHEN** the user launches the heatmap alignment GUI with the legacy `--artifact` startup argument
- **THEN** the command-line parser rejects the argument and presents help that lists `--session` as the saved alignment session startup argument

### Requirement: Synced video export overlay
The system SHALL let the user place a rectangular export overlay on the camera preview and use it to export a synced video with an H5 heatmap plot composited onto original-resolution camera footage. The plotted heatmap overlay presentation SHALL be derived from a shared source-space style model so the GUI overlay preview and exported overlay have matching visual proportions for labels, ticks, margins, axes, and heatmap content.

#### Scenario: Adjust export overlay
- **WHEN** the user drags the export overlay center, edge, or corner on the camera preview
- **THEN** the system updates the preview-space overlay rectangle by moving it, resizing one dimension, or resizing both dimensions respectively

#### Scenario: Toggle export overlay visibility
- **WHEN** the user toggles export overlay visibility from the camera preview context menu
- **THEN** the system shows or hides the overlay controls and does not render the overlay preview while the overlay is hidden

#### Scenario: Preview export overlay content
- **WHEN** the export overlay and overlay preview are visible
- **THEN** the system renders a low-quality plotted H5 heatmap with axes inside the overlay rectangle on top of the camera preview using the same source-space presentation model as export

#### Scenario: Match exported overlay presentation
- **WHEN** the export overlay preview is visible and the user exports a synced video using the same overlay rectangle
- **THEN** the exported plotted heatmap overlay uses matching visual proportions for plot labels, tick labels, tick marks, axes, margins, and heatmap body relative to the overlay shown in the GUI preview

#### Scenario: Bound compact overlay presentation
- **WHEN** the export overlay rectangle is too small to fit the normal plot presentation cleanly
- **THEN** the system uses bounded plot styling so labels, ticks, margins, and heatmap body remain inside the plotted overlay image while preserving preview/export visual parity

#### Scenario: Export synced video
- **WHEN** the user exports a synced video
- **THEN** the system writes an MP4 for exactly the H5 recording duration, using the higher of camera FPS and H5 FPS, original-resolution camera frames, the H5 frame at each output time, and a plotted H5 heatmap composited into the scaled export overlay rectangle

#### Scenario: Export outside camera coverage
- **WHEN** the H5 output time maps before the first camera frame or after the last camera frame using the current offset
- **THEN** the system holds the closest first or last camera frame while continuing to render the H5 overlay for that output time

#### Scenario: Show export progress
- **WHEN** synced video export is running
- **THEN** the system shows a busy/progress state and prevents starting a second export simultaneously

### Requirement: Extensible track model
The system SHALL structure alignment state so the MVP's camera video and H5 heatmap are represented as tracks on a shared timeline.

#### Scenario: Persist MVP tracks
- **WHEN** the system saves an alignment session
- **THEN** the session file represents the camera video and H5 heatmap as distinct tracks with their source configuration and timing state

### Requirement: Imported distance-measurement datasource
The system SHALL allow the heatmap alignment GUI to import a generated peak-distance JSON file as an optional datasource alongside the camera video and H5 heatmap recording.

#### Scenario: Import peak-distance JSON
- **WHEN** the user imports a peak-distance JSON file generated from a recorded H5 log
- **THEN** the system loads the distance measurements as an optional datasource without replacing the camera video or H5 heatmap track

#### Scenario: Load peak-distance JSON on startup
- **WHEN** the user launches the heatmap alignment GUI with a peak-distance JSON startup argument
- **THEN** the system loads that file as the optional distance-measurement datasource during startup

#### Scenario: Load H5 and peak-distance JSON on startup
- **WHEN** the user launches the heatmap alignment GUI with both H5 recording and peak-distance JSON startup arguments
- **THEN** the system loads the H5 recording and validates the peak-distance datasource against it using the same import rules as interactive import

#### Scenario: Load session and peak-distance JSON on startup
- **WHEN** the user launches the heatmap alignment GUI with both a saved alignment session and a peak-distance JSON startup argument
- **THEN** the explicitly provided peak-distance JSON replaces any peak-distance datasource stored in the loaded session after validation

#### Scenario: Validate imported datasource metadata
- **WHEN** the imported peak-distance JSON contains source-selection metadata
- **THEN** the system compares that metadata with the loaded H5 heatmap track when one is present and warns the user if the source selection appears incompatible

#### Scenario: Reject incompatible row count
- **WHEN** the imported peak-distance JSON has a different number of measurement objects than the loaded H5 heatmap recording has frames
- **THEN** the system rejects the import and leaves the current peak-distance datasource unchanged

#### Scenario: Validate real-time axis
- **WHEN** the imported peak-distance JSON contains elapsed real-time seconds
- **THEN** the system verifies that the imported time range is compatible with the loaded H5 heatmap recording duration when one is present

#### Scenario: Preserve timeline rows
- **WHEN** the imported peak-distance JSON contains frames with no detection
- **THEN** the system preserves those rows so the imported datasource remains aligned to the source recording timeline

#### Scenario: Reject reduced CSV as datasource
- **WHEN** the user attempts to import a reduced CSV peak-distance export as the heatmap alignment datasource
- **THEN** the system rejects it and asks for the canonical JSON peak-distance export

#### Scenario: Report invalid peak-distance JSON
- **WHEN** the user imports a JSON file that is not a canonical peak-distance JSON export
- **THEN** the system reports a user-oriented error message that identifies the file as an invalid peak-distance JSON file and presents technical parser details only as secondary context

#### Scenario: Toggle peak visualization
- **WHEN** an imported peak-distance datasource is loaded
- **THEN** the system allows the user to show or hide its visualization without unloading the datasource

#### Scenario: Unload peak datasource
- **WHEN** the user clears or unloads the imported peak-distance datasource
- **THEN** the system removes the imported peak measurements from the current session without changing the camera video or H5 heatmap track

#### Scenario: Load session without imported datasource
- **WHEN** the user loads an alignment session that does not contain an imported distance-measurement datasource
- **THEN** the system treats the datasource as absent and loads the existing camera and heatmap state normally

### Requirement: Peak-distance visualization
The system SHALL provide a lightweight visualization for an imported peak-distance datasource in the heatmap alignment GUI.

#### Scenario: Render current peak on heatmap
- **WHEN** an imported peak-distance datasource is visible and the current H5 frame has a detected peak
- **THEN** the system renders a marker for that peak at its measured distance on or alongside the current heatmap view

#### Scenario: Hide peak visualization
- **WHEN** the user hides the imported peak-distance datasource
- **THEN** the system stops rendering peak-distance markers or plots while keeping the imported datasource available in the session

#### Scenario: Handle no-detection frame in visualization
- **WHEN** an imported peak-distance datasource is visible and the current H5 frame has no detection
- **THEN** the system indicates the absence of a peak without drawing a misleading distance marker

#### Scenario: Export visible peak marker
- **WHEN** an imported peak-distance datasource is visible and the user exports a synced video with a heatmap overlay
- **THEN** the exported heatmap overlay includes the detected peak marker for each output frame that maps to a detected H5 peak row

### Requirement: Aligned signal plot
The system SHALL provide a separate Signals area above the Timeline area for reviewing imported time-series measurements against the shared physical timeline.

#### Scenario: Display signals area
- **WHEN** the user launches the alignment workbench
- **THEN** the system displays a boxed Signals area above the boxed Timeline area

#### Scenario: Plot H5 peak distance signal
- **WHEN** an imported peak-distance JSON datasource is loaded and visible
- **THEN** the Signals area plots H5 peak distance over H5 elapsed time

#### Scenario: Use H5 track color for peak distance
- **WHEN** the Signals area plots H5-derived peak-distance data
- **THEN** the plotted H5 peak-distance signal uses a readable plot color derived from the same color family as the H5 timeline track

#### Scenario: Show detected and candidate distances
- **WHEN** the imported peak-distance datasource contains detected frames and no-detection frames with candidate distances
- **THEN** the Signals area plots `candidate_peak_distance_m` values segmented by detection status, rendering detected frames as the primary solid signal and no-detection frames as a lower-alpha signal

#### Scenario: Preserve missing-value gaps
- **WHEN** a peak-distance measurement has no plottable detected or candidate value
- **THEN** the Signals area leaves an actual gap rather than connecting a line through that measurement

#### Scenario: Show compact legend
- **WHEN** the Signals area contains one or more visible plotted signals
- **THEN** the system displays a compact legend identifying the plotted signal meanings

### Requirement: Current-time indicators
The system SHALL show current-time indicators in the Timeline and Signals areas with distinct interaction affordances.

#### Scenario: Show passive signal playhead
- **WHEN** the Signals area is visible
- **THEN** the system displays a passive vertical current-time indicator at the shared timeline current time

#### Scenario: Signal playhead follows current time
- **WHEN** playback, timeline scrubbing, or time navigation changes the shared current time
- **THEN** the Signals current-time indicator moves to the updated time without changing the Signals plot range mode

#### Scenario: Signal playhead is not draggable
- **WHEN** the user hovers or drags over the Signals current-time indicator
- **THEN** the system does not show a drag cursor or change the shared current time from the Signals indicator interaction

#### Scenario: Timeline playhead has interaction affordance
- **WHEN** the user hovers over the draggable Timeline current-time marker hit area
- **THEN** the system uses a cursor or equivalent hover affordance that indicates the Timeline marker can be dragged

#### Scenario: Timeline playhead drag takes precedence over track drag
- **WHEN** the user starts a drag in the Timeline current-time marker hit area and the marker overlaps a timeline track bar
- **THEN** the system drags the current-time marker rather than the underlying track bar

#### Scenario: Distinguish active and passive playheads
- **WHEN** both the Timeline and Signals current-time indicators are visible
- **THEN** the Timeline current-time marker appears brighter or otherwise more prominent than the passive Signals current-time indicator

### Requirement: Signal plot range modes
The system SHALL support independent x-axis and y-axis range modes for the Signals plot.

#### Scenario: X Timeline mode follows timeline
- **WHEN** the Signals plot x-axis is in Timeline mode
- **THEN** the plot x-limits match the current timeline view bounds

#### Scenario: X Timeline mode aligns time mapping
- **WHEN** the Signals plot x-axis is in Timeline mode and the Timeline is visible
- **THEN** the Signals plot data area and Timeline time-bar area map the same time values to the same horizontal screen positions

#### Scenario: Disable x navigation in Timeline mode
- **WHEN** the Signals plot x-axis is in Timeline mode
- **THEN** direct x-axis zoom and pan interaction in the Signals plot is disabled

#### Scenario: Label Timeline mode compactly
- **WHEN** the user opens the Signals plot x-axis range mode menu
- **THEN** the timeline-following x-axis mode is labeled "Timeline"

#### Scenario: Disable x transformations in Timeline mode
- **WHEN** the Signals plot x-axis is in Timeline mode
- **THEN** plot actions or transformations that change the x-axis meaning away from linear physical time, or change the timeline-matched x-axis range, are disabled or prevented from affecting the x-axis

#### Scenario: Disable view-all in Timeline mode
- **WHEN** the Signals plot x-axis is in Timeline mode
- **THEN** generic plot actions that would change the x-axis range, including the stock "View All" action, are disabled or prevented from changing the x-axis range

#### Scenario: Manual x navigation
- **WHEN** the user switches the Signals plot x-axis to manual mode
- **THEN** direct x-axis zoom and pan interaction in the Signals plot is enabled without changing the timeline view bounds

#### Scenario: Independent y range mode
- **WHEN** the Signals plot x-axis and y-axis have different range modes
- **THEN** the system applies each axis mode independently

#### Scenario: Y auto fits visible data
- **WHEN** the Signals plot y-axis is in auto mode
- **THEN** the y-limits fit the visible signal data in the current x-window

#### Scenario: Y auto includes zero
- **WHEN** the Signals plot y-axis is in auto mode
- **THEN** the y-limits include zero and the visible signal data before padding is applied

#### Scenario: Manual y navigation
- **WHEN** the user switches the Signals plot y-axis to manual mode
- **THEN** direct y-axis zoom and pan interaction in the Signals plot is enabled without changing the x-axis range mode

#### Scenario: Range mode context menu
- **WHEN** the user opens the Signals plot context menu
- **THEN** the system provides two-option auto/manual controls for the x-axis and y-axis range modes

### Requirement: Signal plot view persistence
The system SHALL persist Signals plot view settings in alignment session files.

#### Scenario: Save signal plot view settings
- **WHEN** the user saves an alignment session
- **THEN** the session file includes the Signals plot x-axis range mode, y-axis range mode, and any active manual x/y ranges

#### Scenario: Restore signal plot view settings
- **WHEN** the user loads an alignment session containing Signals plot view settings
- **THEN** the system restores the saved x-axis range mode, y-axis range mode, and manual x/y ranges

#### Scenario: Load older session without signal plot view settings
- **WHEN** the user loads an alignment session that does not contain Signals plot view settings
- **THEN** the system uses default Signals plot settings equivalent to x Timeline mode and y auto mode

### Requirement: Remove visible xcorr controls
The system SHALL remove disabled xcorr controls from the main heatmap alignment GUI while preserving manual alignment authority.

#### Scenario: Launch without disabled xcorr UI
- **WHEN** the user launches the alignment workbench
- **THEN** the system does not show disabled xcorr buttons, xcorr status labels, or an xcorr plot in the main layout

#### Scenario: Keep loading free of xcorr computation
- **WHEN** the user loads a camera video, H5 recording, or peak-distance JSON datasource
- **THEN** the system does not run cross-correlation automatically

### Requirement: Signal plot does not affect synced video export
The system SHALL keep synced video export behavior unchanged by the Signals plot.

#### Scenario: Export with visible signal plot
- **WHEN** the Signals plot is visible and the user exports a synced video
- **THEN** the exported video does not include the Signals plot and uses the existing camera plus H5 heatmap overlay export behavior

### Requirement: Leg2 MAT ultrasonic datasource
The system SHALL allow the heatmap alignment GUI to import a Leg2 `.mat` log as an optional ultrasonic datasource alongside the camera video, H5 heatmap recording, and imported H5 peak-distance datasource.

#### Scenario: Import Leg2 MAT file
- **WHEN** the user imports a Leg2 `.mat` file with the expected ultrasonic fields
- **THEN** the system loads the Leg2 ultrasonic datasource without replacing the camera video, H5 heatmap track, or imported H5 peak-distance datasource

#### Scenario: Load Leg2 MAT on startup
- **WHEN** the user launches the heatmap alignment GUI with a Leg2 `.mat` startup argument
- **THEN** the system loads that file as the optional Leg2 ultrasonic datasource during startup

#### Scenario: Load session and Leg2 MAT on startup
- **WHEN** the user launches the heatmap alignment GUI with both a saved alignment session and a Leg2 `.mat` startup argument
- **THEN** the explicitly provided Leg2 `.mat` file replaces any Leg2 ultrasonic datasource stored in the loaded session after validation

#### Scenario: Unload Leg2 MAT datasource
- **WHEN** the user clears or unloads the Leg2 ultrasonic datasource
- **THEN** the system removes the Leg2 ultrasonic data and timeline track from the current session without changing the camera video, H5 heatmap track, or imported H5 peak-distance datasource

#### Scenario: Load session without Leg2 MAT datasource
- **WHEN** the user loads an alignment session that does not contain a Leg2 ultrasonic datasource
- **THEN** the system treats the datasource as absent and loads the existing camera, heatmap, peak-distance, and signal-plot state normally

### Requirement: Leg2 MAT ultrasonic extraction
The system SHALL extract the Leg2 ultrasonic datasource from hard-coded fields in the expected Leg2 `.mat` export structure.

#### Scenario: Extract required Leg2 fields
- **WHEN** a Leg2 `.mat` file is loaded
- **THEN** the system reads required fields from `DataRecordCommon.timeOut`, `Ultrasonic.Distance`, `DataRecordCommon.ultrasonic_filtered`, and `DataRecordCommon.ReliableFlag`

#### Scenario: Normalize Leg2 elapsed time
- **WHEN** Leg2 ultrasonic time values are loaded successfully
- **THEN** the system subtracts the first retained time value so the Leg2 ultrasonic source starts at elapsed time zero

#### Scenario: Ignore trailing zero-time sample
- **WHEN** the Leg2 time array contains a trailing `0` value after valid nonzero time samples
- **THEN** the system excludes the trailing erroneous sample and corresponding ultrasonic values from the loaded datasource

#### Scenario: Convert ultrasonic distance units
- **WHEN** Leg2 ultrasonic distance values are loaded successfully
- **THEN** the system converts them from millimeters to meters before plotting or persisting loaded metadata

#### Scenario: Extract ultrasonic-use segmentation
- **WHEN** the loaded Leg2 `.mat` file is accepted
- **THEN** the system uses `DataRecordCommon.ReliableFlag` as a per-sample primary/faded display segmentation mask for the selected ultrasonic signal

### Requirement: Leg2 MAT load validation
The system SHALL reject invalid Leg2 `.mat` loads with clear user-facing errors and SHALL leave any existing loaded Leg2 datasource unchanged when validation fails.

#### Scenario: Reject missing required fields
- **WHEN** the user imports a Leg2 `.mat` file missing any required field
- **THEN** the system rejects the import and reports which required field could not be loaded

#### Scenario: Reject incompatible array lengths
- **WHEN** the required Leg2 time, raw distance, filtered distance, and `ReliableFlag` segmentation arrays have incompatible lengths after trailing zero-time cleanup
- **THEN** the system rejects the import and reports the array length incompatibility

#### Scenario: Reject invalid time axis
- **WHEN** the Leg2 time array is non-finite, empty after cleanup, or not usable as an increasing physical time axis
- **THEN** the system rejects the import and reports that the Leg2 time axis is invalid

#### Scenario: Reject invalid distance values
- **WHEN** a required Leg2 ultrasonic distance array cannot be interpreted as numeric distance samples
- **THEN** the system rejects the import and reports that the ultrasonic distance data is invalid

#### Scenario: Keep prior Leg2 datasource after failed import
- **WHEN** a Leg2 ultrasonic datasource is already loaded and a later Leg2 `.mat` import fails validation
- **THEN** the system keeps the previously loaded Leg2 datasource and its session settings unchanged

### Requirement: Leg2 MAT timeline track
The system SHALL display the loaded Leg2 ultrasonic datasource as its own colored track on the shared physical timeline.

#### Scenario: Display Leg2 timeline track
- **WHEN** a Leg2 ultrasonic datasource is loaded
- **THEN** the Timeline area displays a Leg2 `.mat` duration bar on a distinct track row using the Leg2 datasource color

#### Scenario: Drag Leg2 timeline track
- **WHEN** the user drags the Leg2 `.mat` duration bar horizontally
- **THEN** the system allows the Leg2 row to move partially or fully outside the visible timeline range, updates the stored Leg2-to-H5 offset in seconds when the drag is released, and refreshes dependent timeline and Signals views

#### Scenario: Preserve camera offset while dragging Leg2
- **WHEN** the user drags the Leg2 `.mat` duration bar
- **THEN** the system does not change the stored camera-to-H5 offset

#### Scenario: Preserve Leg2 offset while dragging camera
- **WHEN** the user drags the camera duration bar
- **THEN** the system does not change the stored Leg2-to-H5 offset

#### Scenario: Use source offset sign convention
- **WHEN** the Leg2 track has offset `offset_s`
- **THEN** Leg2 source time maps to shared H5 time using the same sign convention as the camera track, with the Leg2 timeline row start displayed at `-offset_s`

### Requirement: Timeline track offset labels
The system SHALL display numerical alignment values inside the Timeline area for timeline tracks that have an editable offset from the shared reference.

#### Scenario: Show offset labels for offset tracks
- **WHEN** the Timeline area displays a track with an editable offset from the shared reference
- **THEN** the system displays that track's current offset or aligned start value in the Timeline area on the same row as the corresponding track bar

#### Scenario: Place offset label near track bar
- **WHEN** the system displays an offset label for a timeline track
- **THEN** the label appears just outside the left side of the track bar, right-aligned toward the bar, with a small margin and no pill or background container

#### Scenario: Omit fixed reference offset label
- **WHEN** the H5 reference track remains fixed at shared time zero
- **THEN** the system is not required to display an offset label for the H5 reference track

#### Scenario: Avoid clipped offset labels
- **WHEN** a timeline track bar is near, at, or beyond the visible timeline edge such that its offset label would be clipped or misleading
- **THEN** the system hides, clips, or otherwise suppresses the label so it does not overlap unrelated timeline content or appear detached from its track

### Requirement: Leg2 ultrasonic signal display
The system SHALL display one selected Leg2 ultrasonic signal at a time in the existing Signals area using the Leg2 timeline color family.

#### Scenario: Plot selected raw ultrasonic signal
- **WHEN** the Leg2 ultrasonic datasource is loaded and raw ultrasonic display is selected
- **THEN** the Signals area plots raw ultrasonic distance over aligned shared timeline time in meters

#### Scenario: Plot selected filtered ultrasonic signal
- **WHEN** the Leg2 ultrasonic datasource is loaded and filtered ultrasonic display is selected
- **THEN** the Signals area plots filtered ultrasonic distance over aligned shared timeline time in meters

#### Scenario: Toggle raw and filtered ultrasonic display
- **WHEN** a Leg2 ultrasonic datasource is loaded
- **THEN** the system lets the user choose whether the Signals area displays the raw or filtered ultrasonic signal while keeping only one Leg2 ultrasonic signal visible at a time

#### Scenario: Use Leg2 track color for ultrasonic signal
- **WHEN** the Signals area plots a Leg2 ultrasonic signal
- **THEN** the plotted signal uses a readable plot color derived from the same color family as the Leg2 timeline track

#### Scenario: Segment ultrasonic signal by ReliableFlag
- **WHEN** the selected Leg2 ultrasonic signal is visible
- **THEN** the Signals area renders samples where `DataRecordCommon.ReliableFlag` is true as a slightly transparent primary signal and samples where `DataRecordCommon.ReliableFlag` is false as a lower-alpha signal

#### Scenario: Preserve ultrasonic missing-value gaps
- **WHEN** a selected Leg2 ultrasonic sample has no plottable distance value
- **THEN** the Signals area leaves an actual gap rather than connecting a line through that sample

#### Scenario: Align Leg2 signal with timeline geometry
- **WHEN** the Signals plot x-axis is in Timeline mode and a Leg2 ultrasonic signal is visible
- **THEN** the Leg2 ultrasonic signal, Leg2 timeline bar, H5 peak-distance signal, and current-time indicators map the same shared time values to the same horizontal screen positions

#### Scenario: Show Leg2 signal legend entry
- **WHEN** the Signals area contains a visible Leg2 ultrasonic signal
- **THEN** the compact legend identifies whether the plotted Leg2 signal is raw or filtered ultrasonic distance

### Requirement: Segmented signal continuity
The system SHALL render any Signals plot series that uses primary and faded or lower-alpha regions so styling changes do not introduce artificial visual gaps.

#### Scenario: Bridge segmented signal transitions
- **WHEN** the Signals area plots a signal split into primary and faded or lower-alpha regions based on a per-sample condition
- **THEN** adjacent plottable samples remain visually connected across condition changes by using the faded or lower-alpha region to bridge into and out of primary regions

#### Scenario: Keep primary region condition-based
- **WHEN** the Signals area plots a segmented signal
- **THEN** the primary non-faded region is used where the signal's primary condition is satisfied

#### Scenario: Preserve true missing-value gaps
- **WHEN** a segmented signal sample has no plottable x-value or y-value
- **THEN** the Signals area leaves an actual gap rather than using a faded or lower-alpha region to bridge through the missing sample

### Requirement: Leg2 MAT session persistence
The system SHALL persist optional Leg2 `.mat` datasource state in alignment session files.

#### Scenario: Save Leg2 MAT session state
- **WHEN** the user saves an alignment session with a Leg2 ultrasonic datasource loaded
- **THEN** the session file includes the Leg2 `.mat` path, Leg2-to-H5 offset, datasource visibility, and selected ultrasonic signal kind

#### Scenario: Restore Leg2 MAT session state
- **WHEN** the user loads an alignment session containing Leg2 ultrasonic datasource state
- **THEN** the system reloads the stored Leg2 `.mat` file and restores the Leg2-to-H5 offset, datasource visibility, selected signal kind, timeline track, and Signals plot display

#### Scenario: Warn when stored Leg2 MAT cannot be reloaded
- **WHEN** the user loads an alignment session whose stored Leg2 `.mat` file is missing or invalid
- **THEN** the system reports the Leg2 `.mat` reload failure while keeping the rest of the alignment session usable

#### Scenario: Preserve older sessions without Leg2 fields
- **WHEN** the user loads an older alignment session that does not contain Leg2 ultrasonic datasource state
- **THEN** the system defaults to no loaded Leg2 ultrasonic datasource without requiring session migration

### Requirement: Leg2 MAT export isolation
The system SHALL keep synced video export behavior unchanged by the Leg2 ultrasonic datasource.

#### Scenario: Export with visible Leg2 ultrasonic signal
- **WHEN** a Leg2 ultrasonic datasource is loaded or visible and the user exports a synced video
- **THEN** the exported video does not include the Leg2 ultrasonic signal and uses the existing camera plus H5 heatmap overlay export behavior

#### Scenario: Preserve export duration
- **WHEN** a Leg2 ultrasonic datasource extends before or after the H5 recording in aligned shared time
- **THEN** synced video export duration remains based on the H5 recording duration

### Requirement: Resources menu
The system SHALL provide a top-level Resources menu for heatmap alignment datasource management.

#### Scenario: Show resource management entry
- **WHEN** the user opens the Resources menu
- **THEN** the menu provides an action to open the Resources window

#### Scenario: Load resources from menu
- **WHEN** the user opens the Resources menu
- **THEN** the menu provides load or replace actions for Camera Video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT resources

#### Scenario: Unload resources from menu
- **WHEN** the user opens the Resources menu
- **THEN** the menu provides unload or clear actions for unloadable Camera Video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT resources, enabling each action only when it can apply to the current session state

#### Scenario: Keep session actions in File menu
- **WHEN** the user opens the File menu
- **THEN** the menu remains the place for opening sessions, saving sessions, saving sessions as a new path, closing the current session, exporting synced video, and quitting the workbench

### Requirement: Resources window
The system SHALL provide a modeless Resources window that summarizes supported heatmap alignment resources and allows resource management without blocking the main alignment workflow.

#### Scenario: Open Resources window
- **WHEN** the user chooses the Resources window action
- **THEN** the system shows a modeless Resources window that can stay open while the main heatmap alignment window remains usable

#### Scenario: Reopen existing Resources window
- **WHEN** the Resources window is already open and the user chooses the Resources window action again
- **THEN** the system brings the existing Resources window to the foreground instead of creating a duplicate Resources window or moving the existing window from its user-chosen position

#### Scenario: List supported resource slots
- **WHEN** the Resources window is visible
- **THEN** the window lists rows for Camera Video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT resource slots even when those resources are not loaded

#### Scenario: Refresh resource rows
- **WHEN** a resource is loaded, replaced, unloaded, cleared, reloaded, or fails to load while the Resources window is visible
- **THEN** the window updates the affected resource row without requiring the user to close and reopen the window

#### Scenario: Show current session context
- **WHEN** a session path is known
- **THEN** the Resources window shows the current session path as contextual information without treating the session as a datasource row

#### Scenario: Show obvious window dismissal action
- **WHEN** the Resources window is visible
- **THEN** the window provides an obvious in-window dismissal action such as a Close button or window-local close menu item

#### Scenario: Dismiss Resources window without changing state
- **WHEN** the user invokes the Resources window dismissal action
- **THEN** the system closes or hides only the Resources window without unloading resources, closing the current session, exiting the main workbench, or changing alignment state

### Requirement: Resource row presentation
The system SHALL present each resource row with scan-friendly status, visual identity, path, and detail information.

#### Scenario: Show resource status
- **WHEN** the Resources window lists a resource row
- **THEN** the row indicates whether the resource is loaded, unloaded, missing, invalid, or loaded with warnings

#### Scenario: Show visual color marker
- **WHEN** a resource has a semantic timeline, signal, overlay, or warning color association
- **THEN** the row shows that association as a compact visual swatch or marker cell rather than as text labeled "Color"

#### Scenario: Show resource type and role
- **WHEN** the Resources window lists a resource row
- **THEN** the row identifies the resource type and current role, using user-facing names such as Camera Video, Radar Raw (H5), Radar Peak (JSON), or Leg2 MAT

#### Scenario: Show full path with filename preserved
- **WHEN** a resource row has a file path
- **THEN** the table displays the full path when it fits and uses middle elision when it does not fit, preserving the full filename at the end of the path when the available width allows it

#### Scenario: Preserve separator before elided filename
- **WHEN** a resource path is middle-elided and the available width allows preserving the filename
- **THEN** the elided path includes the path separator immediately before the filename in the preserved suffix

#### Scenario: Show unelided path in details
- **WHEN** the user selects a resource row with a file path
- **THEN** the selected-row details provide access to the unelided full path

#### Scenario: Show selected resource identity first
- **WHEN** the user selects a resource row
- **THEN** the selected-resource details area presents the resource type or name before status, metadata, warnings, or path details

#### Scenario: Omit empty path details
- **WHEN** the user selects an unloaded resource row without a remembered path
- **THEN** the selected-resource details area omits the path detail instead of showing a placeholder path value

#### Scenario: Show resource details
- **WHEN** a resource row has loaded metadata
- **THEN** the row or selected-row details show useful resource-specific information such as camera duration and FPS, radar H5 frame count and duration, radar peak detection count, or Leg2 sample and reliable-segment counts

#### Scenario: Show stale remembered path
- **WHEN** a loaded session remembers a resource path that cannot be reloaded
- **THEN** the corresponding resource row remains visible with the remembered path and a missing or invalid status

### Requirement: Resources window actions
The system SHALL allow users to manage resources from the Resources window.

#### Scenario: Load empty resource slot
- **WHEN** the user selects an unloaded resource row and invokes its load action
- **THEN** the system opens the appropriate file picker and loads the selected resource type using the same validation behavior as the existing interactive load path

#### Scenario: Replace loaded resource
- **WHEN** the user selects a loaded resource row and invokes its load or replace action
- **THEN** the system opens the appropriate file picker and replaces that resource only after the new file validates successfully

#### Scenario: Unload selected resource
- **WHEN** the user selects a loaded optional resource row and invokes its unload or clear action
- **THEN** the system removes that resource from the current session without changing unrelated resources

#### Scenario: Unload primary resource
- **WHEN** the user selects a loaded Camera Video or Radar Raw (H5) row and invokes its unload action
- **THEN** the system clears the selected primary resource and also clears or disables only the preview, timeline, signal, or export state that directly depends on that primary resource

#### Scenario: Unload camera without clearing radar resources
- **WHEN** the user unloads Camera Video while Radar Raw (H5), Radar Peak (JSON), or Leg2 MAT resources are loaded
- **THEN** the system clears camera-dependent preview, timeline, viewport, and export state while preserving the loaded radar and Leg2 resources that remain valid

#### Scenario: Unload radar raw without clearing optional signal resources
- **WHEN** the user unloads Radar Raw (H5) while Radar Peak (JSON) or Leg2 MAT resources are loaded
- **THEN** the system clears radar-H5-dependent rendered heatmap and radar timeline state while preserving loaded Radar Peak (JSON) and Leg2 MAT resources as signal resources when their loaded data remains available

#### Scenario: Display optional signal resources without radar raw
- **WHEN** Radar Raw (H5) is not loaded and Radar Peak (JSON), Leg2 MAT, both, or neither are loaded
- **THEN** the Signals and Timeline areas display whichever optional signal resources are loaded against the shared absolute zero-time coordinate

#### Scenario: Reload remembered resource
- **WHEN** the user selects a resource row with a remembered path and invokes reload
- **THEN** the system attempts to load that remembered path using the same validation behavior as the corresponding resource load path

#### Scenario: Reveal resource path
- **WHEN** the user selects a resource row with an existing file path and invokes reveal path
- **THEN** the system opens the platform file browser at that path or its containing folder when supported

#### Scenario: Label file manager action clearly
- **WHEN** the Resources window or resource row context menu shows the action that opens the platform file browser
- **THEN** the action is labeled "Show in File Manager"

#### Scenario: Inspect resource warnings
- **WHEN** the user selects a resource row with warnings or load errors
- **THEN** the Resources window provides a way to inspect the warning or error details without relying only on the status bar

#### Scenario: Use row context menu actions
- **WHEN** the user opens a context menu on a resource row
- **THEN** the context menu offers the same applicable row-scoped actions as the Resources window selected-row controls, such as load or replace, unload or clear, reload, reveal path, and inspect warnings

#### Scenario: Omit double-click load behavior
- **WHEN** the user double-clicks a resource row
- **THEN** the system is not required to start a load or replace action

#### Scenario: Clear all resources
- **WHEN** the user invokes Clear All Resources from the Resources window and confirms the action
- **THEN** the system unloads Camera Video, Radar Raw (H5), Radar Peak (JSON), Leg2 MAT, and dependent preview, timeline, and signal state while preserving the current session path

#### Scenario: Confirm clear all resources
- **WHEN** the user invokes Clear All Resources
- **THEN** the confirmation message tells the user that loaded resources will be cleared and the current session path will be kept

### Requirement: Session identity and file actions
The system SHALL expose current session identity and expected session save/close actions while keeping session state separate from datasource rows.

#### Scenario: Show untitled session in title
- **WHEN** no current session path is known
- **THEN** the main heatmap alignment window title identifies the session as untitled

#### Scenario: Show current session name in title
- **WHEN** a current session path is known
- **THEN** the main heatmap alignment window title includes the current session filename

#### Scenario: Save existing session
- **WHEN** the user invokes Save Session and a current session path is known
- **THEN** the system saves the current alignment session to that path without prompting for a new path

#### Scenario: Save untitled session
- **WHEN** the user invokes Save Session and no current session path is known
- **THEN** the system behaves like Save Session As and asks the user for a session output path

#### Scenario: Save session as new path
- **WHEN** the user invokes Save Session As and successfully saves to a chosen path
- **THEN** the system updates the current session path to the chosen path and refreshes the main window title and Resources window session context

#### Scenario: Open session updates identity
- **WHEN** the user opens a saved session successfully
- **THEN** the system updates the current session path to the opened path and refreshes the main window title and Resources window session context

#### Scenario: Close current session
- **WHEN** the user invokes Close Session and confirms the action
- **THEN** the system clears loaded resources and session state, forgets the current session path, and returns the workbench to an untitled session without exiting the program

### Requirement: Main layout resource control cleanup
The system SHALL remove duplicated resource load and unload controls from the main heatmap alignment layout after equivalent Resources menu and Resources window actions exist.

#### Scenario: Launch with resource menu available
- **WHEN** the user launches the heatmap alignment workbench
- **THEN** the main layout does not show the previous top-row load buttons for Camera Video, Radar Raw (H5), and session loading

#### Scenario: Keep visualization controls near visualizations
- **WHEN** optional Radar Peak (JSON) or Leg2 MAT resources are loaded
- **THEN** visualization controls such as marker visibility, signal visibility, and selected Leg2 signal kind remain available near the relevant preview or signal controls

#### Scenario: Remove optional datasource load buttons from render panel
- **WHEN** the user views the render controls
- **THEN** the render panel does not show Radar Peak (JSON) or Leg2 MAT import and clear buttons that duplicate Resources menu or Resources window actions

#### Scenario: Keep alignment controls in main workflow
- **WHEN** the user views the Timeline and preview areas
- **THEN** playback, current-time, offset, nudge, viewport, render, and export-preview controls remain available in the main workflow where they directly affect alignment or visual review

### Requirement: Resource model extensibility
The system SHALL structure resource summaries so the Resources window can later represent multiple resource instances without changing the first-pass one-camera, one-H5 workflow.

#### Scenario: Represent current resources as summaries
- **WHEN** the Resources window builds its table rows
- **THEN** it derives rows from resource summary data that includes resource type, role, status, path, semantic color marker, details, warnings, and available actions

#### Scenario: Preserve current workflow constraints
- **WHEN** the Resources window is implemented for this change
- **THEN** it supports the current single Camera Video, single Radar Raw (H5), single Radar Peak (JSON), and single Leg2 MAT resource slots without requiring generic arbitrary resource loading

### Requirement: Resources table interaction polish
The system SHALL keep Resources table selection and header behavior simple and predictable.

#### Scenario: Select one resource row
- **WHEN** the user selects a resource in the Resources table
- **THEN** the table selects at most one full resource row and does not show a separate selected cell state that conflicts with the selected row

#### Scenario: Preserve selected-row painting with custom delegates
- **WHEN** the Resources table uses custom cell delegates for swatches, paths, or other presentation
- **THEN** those delegates preserve normal selected-row background behavior

#### Scenario: Ignore modifier multi-select
- **WHEN** the user uses Ctrl or Shift while selecting Resources table rows
- **THEN** the table does not enter a multi-row or mixed cell-selection state

#### Scenario: Keep headers non-interactive unless sorting exists
- **WHEN** the Resources table does not support sorting or column actions
- **THEN** clicking column headers does not sort, change resource selection, or create persistent header selection state

### Requirement: Resource manager keyboard access
The system SHALL expose basic keyboard mnemonics for resource management actions without adding custom Escape-key behavior to the modeless Resources window.

#### Scenario: Show menu and action mnemonics
- **WHEN** the user uses keyboard menu navigation
- **THEN** the Resources menu and common resource actions expose Qt mnemonics where natural

#### Scenario: Do not add custom Escape close behavior
- **WHEN** the Resources window is focused and the user presses Escape
- **THEN** the system is not required to close the Resources window beyond any default platform or Qt behavior already present

### Requirement: Background resource jobs
The system SHALL run long-running heatmap alignment resource preparation work without blocking the main GUI event loop.

#### Scenario: Load camera video without freezing UI
- **WHEN** the user starts loading a camera video that requires preview proxy generation
- **THEN** the system keeps the main window and Resources window responsive while the camera resource job is running

#### Scenario: Load H5 recording without freezing UI
- **WHEN** the user starts loading a Radar Raw (H5) recording
- **THEN** the system keeps the main window and Resources window responsive while the H5 resource job is running

#### Scenario: Load different resource types concurrently
- **WHEN** one resource type is loading and the user starts loading a different resource type
- **THEN** the system accepts the second load request without requiring the first load request to finish first

#### Scenario: Bound expensive resource concurrency
- **WHEN** multiple expensive resource jobs are requested
- **THEN** the system schedules them with bounded concurrency so proxy generation and file loading do not create unbounded background work

### Requirement: Pending resource replacement
The system SHALL treat a pending same-resource load request as replaceable by the newest request while preserving the last successfully loaded resource until a replacement succeeds.

#### Scenario: Supersede pending camera load
- **WHEN** a camera video load is pending and the user starts loading another camera video
- **THEN** the system supersedes the earlier pending camera load without asking the user to cancel it first

#### Scenario: Cancel superseded in-flight camera work promptly
- **WHEN** a camera video load is superseded while preview proxy generation or other in-flight camera preparation is still running
- **THEN** the system actively requests cancellation of the superseded work, including terminating an active preview-proxy ffmpeg process when possible, so the newest camera load request is not blocked waiting for discarded work to finish

#### Scenario: Ignore stale camera load result
- **WHEN** a superseded camera load finishes after a newer camera load request has started
- **THEN** the system ignores the stale result and does not apply it to the session or previews

#### Scenario: Restore previous camera after replacement failure
- **WHEN** a loaded camera video exists and a replacement camera video fails to load
- **THEN** the system keeps the previous camera video as the active camera resource and restores its usable preview state

#### Scenario: Restore previous H5 after replacement failure
- **WHEN** a loaded Radar Raw (H5) recording exists and a replacement H5 recording fails to load
- **THEN** the system keeps the previous H5 recording as the active H5 resource and restores its usable rendered-heatmap state

#### Scenario: Apply session resource path after replacement success
- **WHEN** a pending resource replacement finishes successfully
- **THEN** the system updates the active session resource path and metadata to the replacement resource

#### Scenario: Do not apply failed resource path to session
- **WHEN** a pending resource replacement fails or is superseded
- **THEN** the system does not update the active session resource path to the failed or superseded file

#### Scenario: Preserve viewport for same-size camera replacement
- **WHEN** a replacement camera video successfully loads with the same source dimensions as the previously active camera video
- **THEN** the system preserves the existing native viewport corner coordinates for the replacement camera

#### Scenario: Handle different-size camera replacement viewport
- **WHEN** a replacement camera video successfully loads with different source dimensions than the previously active camera video
- **THEN** the system either proportionally scales the existing viewport when the source aspect ratio is compatible and the scaled viewport remains valid, or resets or repairs the viewport to a valid default

#### Scenario: Do not retain invalid viewport after incompatible camera replacement
- **WHEN** a replacement camera video successfully loads and the previous viewport corners cannot be preserved or scaled into valid geometry for the replacement source dimensions
- **THEN** the system resets or repairs the viewport to a valid default instead of retaining previous-camera corners that are out of bounds for the replacement source

### Requirement: Camera proxy readiness
The system SHALL require a usable low-quality camera preview source before enabling normal camera playback and scrubbing for a newly loaded high-resolution camera video.

#### Scenario: Show proxy loading state
- **WHEN** a camera video preview proxy is being generated
- **THEN** the camera preview panel shows a loading state identifying the target video filename rather than enabling sluggish full-resolution interaction

#### Scenario: Enable camera interaction after proxy ready
- **WHEN** the camera preview proxy is ready and the camera resource is applied
- **THEN** the system enables normal camera preview, playback, scrubbing, and viewport interaction for that camera

#### Scenario: Report proxy generation failure
- **WHEN** preview proxy generation fails for a camera video that requires a proxy
- **THEN** the system marks the camera load as failed and exposes the failure reason in the resource UI without falling back to full-resolution interactive preview

#### Scenario: Require ffmpeg for large-camera proxy preparation
- **WHEN** a camera video requires preview proxy generation and ffmpeg is unavailable
- **THEN** the system reports the camera load as failed with an explicit ffmpeg-missing reason rather than enabling full-resolution interactive preview as a fallback

#### Scenario: Reuse cached proxy quickly
- **WHEN** a camera video has an existing valid preview proxy
- **THEN** the system may apply the camera resource after reusing the cached proxy without rebuilding it

### Requirement: Preview proxy cache integrity
The system SHALL prevent failed, cancelled, or superseded preview proxy generation from leaving partial files that can be reused as valid cached proxies.

#### Scenario: Promote proxy only after successful generation
- **WHEN** the system generates a preview proxy for a camera video
- **THEN** it writes the in-progress proxy output to a temporary path and promotes it to the final cache path only after successful proxy generation

#### Scenario: Do not reuse cancelled proxy output
- **WHEN** preview proxy generation is cancelled, fails, or is superseded before successful completion
- **THEN** the system does not leave a final cache-path proxy file for that incomplete output

### Requirement: H5 background load ownership
The system SHALL complete background H5 loading without transferring unsafe worker-owned HDF5-backed state to the main GUI thread.

#### Scenario: Avoid unsafe H5 handle transfer
- **WHEN** a background H5 load job completes
- **THEN** the system either applies immutable loaded data that is safe for main-thread ownership or keeps H5-backed access owned by a worker with explicit asynchronous requests

#### Scenario: Avoid reintroducing H5 UI freeze
- **WHEN** a background H5 load job succeeds
- **THEN** the system does not perform another long-running H5 initialization step on the main GUI thread before presenting the loaded H5 resource

#### Scenario: Reuse worker-computed H5 render settings on adoption
- **WHEN** a background H5 load job computed resolved fixed color levels or other expensive render settings off the GUI thread
- **THEN** the main thread adopts those worker-computed settings from the load payload instead of repeating the same expensive computation during resource application

#### Scenario: Release H5 record on worker preparation failure
- **WHEN** background H5 loading fails after opening the heatmap record but before producing an immutable load payload
- **THEN** the system releases the HDF5-backed record handle

### Requirement: Resource loading presentation
The system SHALL present pending, failed, and cancelled resource work in the Resources window and affected preview panels.

#### Scenario: Show loading resource row
- **WHEN** a resource load or replacement is pending
- **THEN** the Resources window shows that resource row as loading, building, waiting, or cancelling with the target filename visible

#### Scenario: Show waiting while queued for bounded work
- **WHEN** a resource job is accepted but blocked waiting for a bounded expensive-work slot such as the single preview-proxy transcode slot
- **THEN** the Resources window and affected preview presentation show the job as waiting for that target filename rather than as actively loading or building

#### Scenario: Show affected panel loading overlay
- **WHEN** the camera or rendered heatmap preview cannot show the pending target resource yet
- **THEN** the affected preview panel shows a loading overlay with the target filename instead of stale unlabeled preview content

#### Scenario: Use filename in loading overlay
- **WHEN** a resource panel or preview overlay identifies a pending load target
- **THEN** the visible loading text includes the filename without requiring the full path

#### Scenario: Provide resource job cancellation
- **WHEN** a cancellable resource job is pending
- **THEN** the Resources window provides a row-scoped cancel action for that pending job

#### Scenario: Cancel pending replacement
- **WHEN** the user cancels a pending replacement for a resource that already has an active loaded value
- **THEN** the system leaves the active loaded resource in effect and restores its usable preview state

#### Scenario: Cancel wins before late success is applied
- **WHEN** the user cancels a pending resource job before that job's completion is accepted on the GUI thread
- **THEN** the system treats the job as cancelled, releases any late success payload, and does not apply the cancelled target as the active resource

#### Scenario: Show cancellation promptly
- **WHEN** the user cancels a pending resource job whose underlying file operation cannot stop immediately
- **THEN** the Resources window and affected previews show cancelling or restored state promptly without waiting for the underlying operation to return

#### Scenario: Do not stack placeholder and loading text
- **WHEN** a preview panel is showing a loading overlay and does not yet have target content to display
- **THEN** the panel shows a single coherent loading message rather than drawing placeholder panel text underneath the loading message

#### Scenario: Show viewport loading state for pending dependencies
- **WHEN** the viewport preview depends on a camera or H5 resource that is pending, replacing, waiting, or cancelling
- **THEN** the viewport preview shows the same resource-loading state as an affected panel instead of presenting stale viewport content as if it belonged to the pending target

### Requirement: Workbench lifecycle during resource jobs
The system SHALL cancel or abandon active camera and H5 resource jobs safely when the workbench is closed or reset to an empty session so late completions cannot mutate a closed session, and SHALL reconcile resource slots on saved session open so unchanged identities use **keep** without abandoning matching in-flight jobs.

#### Scenario: Abandon jobs on window close
- **WHEN** the main workbench window closes while a camera or H5 resource job is pending
- **THEN** the system cancels or abandons those jobs, clears pending job state and replacement backups, and does not apply their completions to a later workbench instance

#### Scenario: Ignore worker completion after manager deletion
- **WHEN** a background resource worker completes after the workbench has been closed and its job manager QObject is no longer alive
- **THEN** the worker completion path exits without raising a traceback and without attempting to update deleted GUI objects

#### Scenario: Abandoned manager skips worker dispatch
- **WHEN** resource jobs are abandoned during window close, session close, or workbench reset to an empty session
- **THEN** late worker runnables observe the abandoned state before dispatch, release any completed payload without applying it, and do not raise a traceback

#### Scenario: Abandon jobs on session close
- **WHEN** the user closes the current session and returns to an empty workbench while a camera or H5 resource job is pending
- **THEN** the system cancels or abandons those jobs, clears pending job state and replacement backups, and does not apply their completions to the reset session

#### Scenario: Discard stale pending job payloads
- **WHEN** a superseded or otherwise ignored camera or H5 job completion would leave a pending result payload unused
- **THEN** the system discards that payload promptly so stale results cannot retain HDF5-backed records or other resources in manager state

#### Scenario: Do not abandon matching jobs on session open
- **WHEN** the user opens a saved alignment session and reconciliation selects **keep** for a camera or H5 slot with an in-flight job for the same resource identity
- **THEN** the system does not abandon that in-flight job solely because of the session open

### Requirement: H5 replacement clears peak datasource
The system SHALL clear imported Radar Peak (JSON) datasource state when a different Radar Raw (H5) resource successfully replaces the current H5 recording.

#### Scenario: Clear peaks after different H5 replacement
- **WHEN** a new H5 recording successfully replaces a different active H5 recording
- **THEN** the system unloads the imported Radar Peak (JSON) datasource and updates the Resources window accordingly

#### Scenario: Preserve peaks after failed H5 replacement
- **WHEN** a pending H5 replacement fails before becoming active
- **THEN** the system preserves the previously active H5 recording and any peak datasource that remained valid for it

### Requirement: Export availability during resource jobs
The system SHALL keep synced video export outside the background resource job system for this change while preventing export from starting with unstable required resources.

#### Scenario: Disable export while camera is loading
- **WHEN** a camera video load or replacement is pending
- **THEN** the system disables starting synced video export

#### Scenario: Disable export while H5 is loading
- **WHEN** a Radar Raw (H5) load or replacement is pending
- **THEN** the system disables starting synced video export

#### Scenario: Allow export when required resources are stable
- **WHEN** camera video and Radar Raw (H5) resources are loaded and no required export resource is in an in-flight load, replace, or cancel phase
- **THEN** the system allows synced video export according to the existing export requirements

#### Scenario: Allow export after failed replacement with restore
- **WHEN** a camera or H5 replacement fails and the system restores the previously active required resources
- **THEN** the system allows synced video export when camera and H5 are loaded and no required export resource is in an in-flight job phase

#### Scenario: Failed job status does not alone block export
- **WHEN** a resource job slot is in `failed` phase because the last load attempt failed but required export resources remain loaded and stable
- **THEN** starting synced video export is not disabled solely because of the failed job phase

#### Scenario: Preserve existing export progress behavior
- **WHEN** synced video export is running
- **THEN** the system uses the existing export progress behavior and prevents starting a second export simultaneously

### Requirement: Session load reconciliation
The system SHALL load a saved alignment session by reconciling the session JSON snapshot against the active workbench state rather than unconditionally tearing down every loaded resource on each open.

Reconciliation SHALL iterate a registered set of resource slots (camera video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT for the current workbench) and, for each slot, SHALL choose one of:

- **keep** — the desired resource identity from the session matches the active loaded resource or an in-flight resource job for that slot; the system does not close, unload, abandon, or restart load work for that slot solely because of the session open
- **load** — the session requests a non-empty resource identity that does not match the active or in-flight identity, or the slot is not loaded; the system loads or replaces that resource using the same behavior as an explicit resource load or reload, including pending replacement and restore-on-failure when a different resource was already loaded, without pre-clearing the active resource before starting the load
- **unload** — the session requests an empty path for that slot but the slot is still loaded; the system clears or unloads that resource so it does not remain active from a previous session

Resource identity SHALL be determined from session content, not from the session JSON file path on disk. Camera identity is the camera video path. H5 identity is the H5 file path plus session, group, entry, and subsweep indices. Radar Peak (JSON) identity is the peak-distance JSON path. Leg2 MAT identity is the Leg2 MAT path. An empty path means the slot is not requested.

After resource reconciliation, the system SHALL always apply non-resource session fields from the JSON snapshot, including viewport geometry, render settings, timeline state, export overlay, signal plot view, preview state, and optional datasource visibility or offset settings, even when one or more resource slots used **keep**.

Before starting H5 **load** actions, the system SHALL assign the desired session snapshot to the active workbench session object so H5 selection indices read during `load_h5_from_path` match the session being opened.

#### Scenario: Keep camera slot when identity matches
- **WHEN** the user loads a saved alignment session whose camera video path matches the active camera resource or matches the target of an in-flight camera resource job
- **THEN** the system reconciles the camera slot as **keep** and does not close the active camera source or abandon the in-flight camera job solely because of the session open

#### Scenario: Keep H5 slot when identity matches
- **WHEN** the user loads a saved alignment session whose H5 path and selection indices match the active H5 resource or match the target of an in-flight H5 resource job
- **THEN** the system reconciles the H5 slot as **keep** and does not close the active H5 source or abandon the in-flight H5 job solely because of the session open

#### Scenario: Load camera when session requests different identity
- **WHEN** the user loads a saved alignment session whose camera video path differs from the active camera resource and in-flight camera job target
- **THEN** the system reconciles the camera slot as **load** and starts camera loading using the same background camera resource job behavior as an explicit camera load or reload

#### Scenario: Load H5 when session requests different identity
- **WHEN** the user loads a saved alignment session whose H5 path or selection indices differ from the active H5 resource and in-flight H5 job target
- **THEN** the system reconciles the H5 slot as **load** and starts H5 loading using the same background H5 resource job behavior as an explicit H5 load or reload

#### Scenario: Unload camera when session omits path
- **WHEN** the user loads a saved alignment session whose camera video path is empty and a camera video resource is still loaded from a previous session
- **THEN** the system reconciles the camera slot as **unload** and unloads the camera video so no camera resource remains active

#### Scenario: Unload H5 when session omits path
- **WHEN** the user loads a saved alignment session whose H5 path is empty and a radar raw H5 resource is still loaded from a previous session
- **THEN** the system reconciles the H5 slot as **unload** and unloads the H5 recording so no H5 resource remains active

#### Scenario: Unload peak JSON when session omits path
- **WHEN** the user loads a saved alignment session whose peak-distance JSON path is empty and a peak-distance datasource is still loaded from a previous session
- **THEN** the system reconciles the Radar Peak (JSON) slot as **unload** and clears the peak-distance datasource

#### Scenario: Unload Leg2 MAT when session omits path
- **WHEN** the user loads a saved alignment session whose Leg2 MAT path is empty and a Leg2 MAT datasource is still loaded from a previous session
- **THEN** the system reconciles the Leg2 MAT slot as **unload** and clears the Leg2 MAT datasource

#### Scenario: Apply session fields after reconciliation
- **WHEN** the user loads a saved alignment session and one or more resource slots reconcile as **keep**
- **THEN** the system still restores session fields from the JSON snapshot that are not satisfied by **keep** alone, such as viewport geometry, render settings, timeline state, preview state, and export overlay settings

#### Scenario: Keep GUI responsive when slots use keep
- **WHEN** the user opens a saved alignment session and all resource slots reconcile as **keep**
- **THEN** the system does not block the GUI thread on redundant camera proxy, H5, peak JSON, or Leg2 MAT reload work for those slots

#### Scenario: Keep GUI responsive during session open
- **WHEN** the user opens a saved alignment session that requires background camera or H5 resource work for slots reconciled as **load**
- **THEN** the system keeps the main window and Resources window responsive on the GUI thread while that work continues, using the same non-blocking resource job presentation as explicit resource loads

#### Scenario: No modal session loading dialog
- **WHEN** the user opens a saved alignment session
- **THEN** the system does not show a dedicated modal loading dialog for the session; loading state appears through existing Resources rows and affected preview loading presentation

