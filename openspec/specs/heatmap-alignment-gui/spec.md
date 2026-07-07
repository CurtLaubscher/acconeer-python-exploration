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

### Requirement: Rendered heatmap coordinate context
The system SHALL provide lightweight physical-coordinate context for the rendered heatmap preview without changing the rendered heatmap body geometry used for comparison with the rectified camera viewport.

#### Scenario: Show distance extent labels
- **WHEN** an H5 recording is loaded and the rendered heatmap preview has valid distance-axis bounds
- **THEN** the system shows compact distance minimum and maximum labels aligned with the left and right edges of the rendered heatmap body

#### Scenario: Keep body geometry stable
- **WHEN** rendered heatmap coordinate labels or peak labels are visible
- **THEN** the system preserves the rendered heatmap body size and alignment used for direct visual comparison with the rectified viewport

#### Scenario: Show velocity extent near controls
- **WHEN** an H5 recording is loaded and the rendered heatmap preview has valid velocity-axis bounds
- **THEN** the system shows compact velocity minimum and maximum text in the rendered heatmap controls area near the color minimum and maximum controls without adding a vertical label gutter beside the heatmap body

#### Scenario: Update extent labels on H5 selection changes
- **WHEN** the loaded H5 recording or selected heatmap session, group, entry, or subsweep changes
- **THEN** the system updates the distance and velocity extent labels from the newly selected heatmap axes

### Requirement: Heatmap peak distance label
The system SHALL label the selected current-frame peak distance on the rendered heatmap preview and exported heatmap overlay when a valid peak marker is available for the current frame.

#### Scenario: Show current peak distance label
- **WHEN** a peak series is selected for the rendered heatmap marker and the current H5 frame has a valid peak distance
- **THEN** the system shows the current peak distance in the rendered heatmap distance-label area using meters with three decimal places

#### Scenario: Show peak position indicator
- **WHEN** the current peak distance label is visible
- **THEN** the system shows a small downward triangle position indicator at the peak distance x position directly above the rendered heatmap body

#### Scenario: Keep peak label readable near edges
- **WHEN** the current peak distance is close to the rendered heatmap distance minimum or maximum
- **THEN** the system keeps the peak indicator tied to the peak distance position while preventing the peak distance text from colliding with extent labels or leaving the label area

#### Scenario: Prioritize peak cue in narrow label area
- **WHEN** the rendered heatmap distance-label area is too narrow to show distance extent labels and the current peak distance cue without overlap
- **THEN** the system prioritizes the current peak distance cue and may hide one or both distance extent labels

#### Scenario: Hide peak indicator outside distance range
- **WHEN** the selected peak series has a valid peak distance outside the rendered heatmap distance-axis range for the current H5 selection
- **THEN** the system omits the peak distance label and peak position indicator

#### Scenario: Avoid duplicate in-body preview peak marker
- **WHEN** the current peak distance label and position indicator are visible
- **THEN** the rendered heatmap comparison preview body does not also display the legacy in-image peak annotation for the same selected peak

#### Scenario: Use compact exported peak marker
- **WHEN** the user exports a synced video with a selected peak series marker
- **THEN** the exported heatmap overlay uses a compact peak distance label and triangle position indicator rather than the legacy in-image peak annotation for the same selected peak

#### Scenario: Omit peak label without valid peak
- **WHEN** no peak series is selected or the selected peak series has no valid peak for the current H5 frame
- **THEN** the system omits the current peak distance label and peak position indicator

#### Scenario: Update peak label on current frame changes
- **WHEN** the shared current time changes to a different H5 frame
- **THEN** the system updates or omits the peak distance label and position indicator according to the selected peak series measurement for the new frame

### Requirement: Rendered heatmap hover coordinate readout
The system SHALL provide a tooltip-style hover readout for points inside the rendered heatmap body.

#### Scenario: Show hover readout inside body
- **WHEN** the pointer hovers over the rendered heatmap body while an H5 frame is available
- **THEN** the system shows a tooltip-style readout near the pointer with Distance, Velocity, and Magnitude values for the hovered heatmap coordinate

#### Scenario: Format hover readout values
- **WHEN** the hover readout is visible
- **THEN** the system formats Distance in meters with three decimals, Velocity in meters per second with three decimals, and Magnitude as an integer rounded to the nearest integer

#### Scenario: Update readout while moving pointer
- **WHEN** the pointer moves within the rendered heatmap body
- **THEN** the system updates the hover readout distance, velocity, and current-frame magnitude for the new hovered coordinate

#### Scenario: Update readout while current frame changes
- **WHEN** the pointer remains over the rendered heatmap body and playback or scrubbing changes the current H5 frame
- **THEN** the system keeps the hovered distance and velocity coordinate and updates the hover readout magnitude for the current frame

#### Scenario: Hide readout outside body
- **WHEN** the pointer leaves the rendered heatmap body
- **THEN** the system hides the hover readout and does not show stale coordinate or magnitude values

#### Scenario: Hide readout when H5 frame becomes unavailable
- **WHEN** the pointer remains over the rendered heatmap body and the current H5 frame becomes unavailable
- **THEN** the system hides the hover readout and does not show stale coordinate or magnitude values

### Requirement: Rendered heatmap bin-edge coordinate mapping
The system SHALL map rendered heatmap distance and velocity cues through displayed heatmap bin-edge extents derived from the heatmap bin centers.

For a distance axis with more than one bin, the displayed distance extent SHALL run from the first distance center minus half the representative bin spacing to the last distance center plus half the representative bin spacing. For a single distance bin, the system SHALL use a finite fallback spacing so the bin center maps to the center of the displayed heatmap body. Velocity coordinate mapping SHALL follow the same displayed heatmap body convention using the heatmap velocity bins and resolution.

#### Scenario: Peak indicator aligns with bin center
- **WHEN** the selected peak distance equals the first rendered heatmap distance-bin center
- **THEN** the compact rendered-heatmap peak position indicator is drawn at the center of the first displayed distance bin rather than at the left edge of the heatmap body

#### Scenario: Peak indicator aligns with last bin center
- **WHEN** the selected peak distance equals the last rendered heatmap distance-bin center
- **THEN** the compact rendered-heatmap peak position indicator is drawn at the center of the last displayed distance bin rather than at the right edge of the heatmap body

#### Scenario: Hover lookup uses displayed bin geometry
- **WHEN** the pointer hovers over the rendered heatmap body
- **THEN** the hover readout distance, velocity, and magnitude are resolved using the displayed bin-edge geometry so each displayed heatmap bin reports the physical coordinate and magnitude for that bin

#### Scenario: Hover readout remains stable at bin centers
- **WHEN** the pointer is positioned at the screen center of a displayed heatmap bin
- **THEN** the hover readout reports that bin's distance and velocity center values and reads magnitude from that same bin

#### Scenario: Detection strip aligns with heatmap body
- **WHEN** the rendered heatmap body and detection strip are visible
- **THEN** the displayed heatmap body has no additional frame or border inset that shifts it relative to the detection strip or compact peak position indicator

### Requirement: Nearest H5 frame selection
The system SHALL select the H5 heatmap frame whose recorded timestamp is nearest to the requested H5 time after clamping the requested time to the H5 recording duration.

#### Scenario: Select current frame before midpoint to next frame
- **WHEN** the requested H5 time falls after a frame timestamp but before the midpoint to the following frame timestamp
- **THEN** the system renders the earlier frame

#### Scenario: Select next frame after midpoint
- **WHEN** the requested H5 time falls after the midpoint between two adjacent frame timestamps
- **THEN** the system renders the later frame

#### Scenario: Clamp before first frame
- **WHEN** the requested H5 time is before the start of the H5 recording
- **THEN** the system renders the first H5 frame

#### Scenario: Clamp after last frame
- **WHEN** the requested H5 time is after the end of the H5 recording
- **THEN** the system renders the last H5 frame

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

### Requirement: Resizable Preview and Signals layout
The system SHALL allow the user to adjust the vertical space allocated to the Preview area and the Signals plot in the heatmap alignment workbench.

#### Scenario: Resize Preview and Signals vertically
- **WHEN** the user drags the divider between the Preview area and the Signals plot
- **THEN** the system reallocates vertical space between the Preview area and the Signals plot without changing the loaded resources, current time, alignment offsets, viewport geometry, or plotted signal data

#### Scenario: Preserve horizontal Preview resizing
- **WHEN** the user adjusts the vertical allocation between Preview and Signals
- **THEN** the existing horizontal resize behavior between Camera Video and the viewport/rendered-heatmap preview column remains available

#### Scenario: Keep Timeline fixed for current workflow
- **WHEN** the user adjusts the vertical allocation between Preview and Signals
- **THEN** the Timeline remains a fixed-height control area outside the Preview/Signals resize interaction

#### Scenario: Prevent preview control overlap
- **WHEN** the user drags the Preview/Signals divider to reduce the Preview area
- **THEN** the system prevents the Preview area from shrinking into a state where viewport or rendered-heatmap controls overlap their preview content

#### Scenario: Do not persist splitter sizes
- **WHEN** the user changes the Preview/Signals vertical allocation and later launches the workbench again
- **THEN** the system uses the default layout allocation rather than restoring the prior Preview/Signals splitter position

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

### Requirement: Preview synchronization preserves timeline x-range by default
The heatmap alignment GUI SHALL preserve the current shared timeline x-range during preview synchronization unless the caller explicitly requests a range reset. Preview synchronization that updates camera frames, heatmap frames, viewport previews, export overlay previews, current-time indicators, signal plots, resource rows, labels, or source-resolution viewport state SHALL NOT recompute the shared x-range by default.

#### Scenario: Plain preview refresh preserves zoom
- **WHEN** the workbench performs a preview refresh after the user has zoomed or panned the shared x-range
- **THEN** the shared x-range remains unchanged

#### Scenario: Source-resolution viewport result preserves zoom
- **WHEN** a source-resolution viewport worker result arrives after the user has zoomed or panned the shared x-range
- **THEN** the shared x-range remains unchanged

#### Scenario: Render and viewport display changes preserve zoom
- **WHEN** the user changes color limits, viewport corners, viewport visibility settings, export overlay settings, heatmap peak marker selection, Leg2 signal kind, or plotted signal visibility
- **THEN** the shared x-range remains unchanged

### Requirement: Resource mutations preserve timeline x-range
Resource load, reload, replace, unload, and background completion SHALL update resource state and displayed data without changing the current shared x-range. This applies to Camera Video, Radar Raw (H5), Radar Peak series, and Leg2 MAT resources. Clearing all resources while the current session remains open SHALL also preserve the current shared x-range.

#### Scenario: H5 load completion preserves zoom
- **WHEN** a Radar Raw (H5) background load completes after the user has zoomed or panned the shared x-range
- **THEN** the shared x-range remains unchanged

#### Scenario: Camera load completion preserves zoom
- **WHEN** a Camera Video background load completes after the user has zoomed or panned the shared x-range
- **THEN** the shared x-range remains unchanged

#### Scenario: Resource unload preserves zoom
- **WHEN** the user unloads Camera Video, Radar Raw (H5), Radar Peak series, or Leg2 MAT resources
- **THEN** the shared x-range remains unchanged

#### Scenario: Clear all resources preserves zoom
- **WHEN** the user clears all resources while keeping the current session open
- **THEN** the shared x-range remains unchanged

### Requirement: Session lifecycle controls timeline x-range resets
Opening or loading a session SHALL recompute the shared x-range from that session's resource domain and SHALL use the same behavior whether the workbench previously had no session resources or a different session loaded. Closing the session or resetting to a new empty session SHALL reset the shared x-range to the blank/default range `0..60 s`. The system SHALL NOT persist the current shared x-range in alignment session JSON as part of this behavior.

#### Scenario: Open session recomputes range
- **WHEN** the user opens an alignment session
- **THEN** the shared x-range recomputes from the opened session's loaded or requested resource domain

#### Scenario: Open session from populated workbench uses same range behavior
- **WHEN** the user opens an alignment session while another session or resources are already loaded
- **THEN** the shared x-range behavior matches opening the same session from an empty workbench

#### Scenario: Close session resets to blank range
- **WHEN** the user closes the current session and returns to an untitled empty workbench
- **THEN** the shared x-range resets to `0..60 s`

#### Scenario: Session save omits shared x-range
- **WHEN** the user saves an alignment session after zooming or panning
- **THEN** the saved session does not persist the current shared x-range

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
The system SHALL save and load JSON alignment session files containing the state needed to reproduce a manual alignment session, including optional imported or saved peak series resource references.

The system SHALL NOT embed generated peak measurement arrays in alignment session JSON. Unsaved generated peak series without a saved JSON path SHALL NOT be restored when the session is saved and later reloaded.

The system SHALL write alignment session version `3` after this change. Version `3` session JSON SHALL store peak series references in a `peak_series` list and SHALL NOT write the retired single `peak_distance_datasource` field.

#### Scenario: Save alignment session
- **WHEN** the user saves an alignment session
- **THEN** the system writes alignment session version `3`, source paths, selected H5 session/group/entry/subsweep, render color limits, camera viewport corners, viewport output dimensions, export overlay settings, temporal offset in seconds, preprocessing settings, optional imported or saved peak series metadata in `peak_series`, and optional imported Leg2 datasource metadata to JSON

#### Scenario: Save datasource state without retired visibility fields
- **WHEN** the user saves an alignment session with peak series or Leg2 MAT resources loaded
- **THEN** the system does not write retired single peak-distance datasource visibility or Leg2 ultrasonic datasource visibility fields as authoritative session state

#### Scenario: Load alignment session
- **WHEN** the user loads a saved alignment session
- **THEN** the system restores the session snapshot described by the JSON file using session load reconciliation so each primary resource slot and persisted optional resource reference is kept, loaded, or unloaded as needed, restores source selections, viewport geometry, render settings, temporal offset, preview state, persisted peak series references, and optional imported Leg2 datasource metadata, and always applies remaining non-resource session fields after reconciliation

#### Scenario: Load version 1 alignment session
- **WHEN** the user loads an alignment session with version `1`
- **THEN** the system migrates the session payload through all intermediate versions to version `3`, ignores retired peak-distance and Leg2 datasource visibility fields, converts any migrated single peak datasource path into `peak_series`, and loads the migrated session without warning if no other load error occurs

#### Scenario: Migrate single peak datasource session
- **WHEN** the user loads a version `2` session that stores one `peak_distance_datasource` path
- **THEN** the system migrates that path into one imported peak series resource row in the version `3` `peak_series` list

#### Scenario: Do not restore unsaved generated peaks
- **WHEN** the user saves an alignment session while unsaved generated peak series exist and later reloads that session
- **THEN** the system restores only peak series with saved/imported JSON paths and does not restore generated peak measurements that were never saved as JSON

#### Scenario: Reject unsupported future alignment session
- **WHEN** the user loads an alignment session with a version newer than the workbench supports
- **THEN** the system rejects the file with a clear unsupported-version load error

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
The system SHALL allow the heatmap alignment GUI to import one or more canonical peak-distance JSON files as optional peak series resources.

Each imported peak series SHALL append a resource row instead of replacing existing peak series. Imported peak series SHALL use the same canonical JSON validation behavior as the existing interactive peak-distance import path. When Radar Raw (H5) is loaded, imported peak series SHALL be validated against the loaded H5 where possible using frame count, real-time seconds, source selection metadata, and recording metadata.

#### Scenario: Import peak-distance JSON
- **WHEN** the user imports a canonical peak-distance JSON file
- **THEN** the system loads it as a new peak series resource without replacing camera video, H5 heatmap, Leg2 MAT, or existing peak series resources

#### Scenario: Import multiple peak-distance JSON files
- **WHEN** the user imports more than one canonical peak-distance JSON file
- **THEN** the system keeps each accepted file as a separate peak series resource row

#### Scenario: Load H5 and peak-distance JSON on startup
- **WHEN** the user launches the heatmap alignment GUI with both H5 recording and peak-distance JSON startup arguments
- **THEN** the system loads the H5 recording and imports the peak-distance JSON as a peak series using the same validation rules as interactive import

#### Scenario: Load session and peak-distance JSON on startup
- **WHEN** the user launches the heatmap alignment GUI with both a saved alignment session and a peak-distance JSON startup argument
- **THEN** the explicitly provided peak-distance JSON is imported as an additional peak series after the session load using the same validation rules as interactive import, unless that path is already present and the implementation chooses to avoid duplicate imported rows

#### Scenario: Validate imported datasource metadata
- **WHEN** an imported peak-distance JSON contains source-selection metadata
- **THEN** the system compares that metadata with the loaded H5 heatmap track when one is present and attaches a row-specific warning if the source selection appears incompatible

#### Scenario: Reject incompatible row count
- **WHEN** an imported peak-distance JSON has a different number of measurement objects than the loaded H5 heatmap recording has frames
- **THEN** the system rejects that import and leaves existing peak series resources unchanged

#### Scenario: Validate real-time axis
- **WHEN** an imported peak-distance JSON contains elapsed real-time seconds
- **THEN** the system verifies that the imported time range is compatible with the loaded H5 heatmap recording duration when one is present

#### Scenario: Preserve timeline rows
- **WHEN** an imported peak-distance JSON contains frames with no detection
- **THEN** the system preserves those rows so the imported peak series remains aligned to the source recording timeline

#### Scenario: Reject reduced CSV as datasource
- **WHEN** the user attempts to import a reduced CSV peak-distance export as a peak series
- **THEN** the system rejects it and asks for the canonical JSON peak-distance export

#### Scenario: Report invalid peak-distance JSON
- **WHEN** the user imports a JSON file that is not a canonical peak-distance JSON export
- **THEN** the system reports a user-oriented error message that identifies the file as an invalid peak-distance JSON file and presents technical parser details only as secondary context

#### Scenario: Display imported peak visualization by default
- **WHEN** a peak-distance JSON is imported as a peak series
- **THEN** the system makes that series available for Signals plot visualization and rendered-heatmap marker selection without requiring a separate datasource visibility checkbox

#### Scenario: Unload imported peak series
- **WHEN** the user unloads an imported peak series resource row
- **THEN** the system removes that peak series from the current session without changing the camera video, H5 heatmap track, Leg2 MAT resource, or other peak series

#### Scenario: Load session without imported datasource
- **WHEN** the user loads an alignment session that does not contain any imported or saved peak series references
- **THEN** the system treats peak series resources as absent and loads the existing camera and heatmap state normally

### Requirement: Peak-distance visualization
The system SHALL provide lightweight visualization for peak series resources in the heatmap alignment GUI.

The rendered heatmap marker and exported heatmap overlay marker SHALL use only the peak series selected by the rendered-heatmap peak selector. The system SHALL NOT draw all available peak series as heatmap markers at the same time.

#### Scenario: Render current peak on heatmap
- **WHEN** a peak series is selected in the rendered-heatmap peak selector and the current H5 frame has a detected peak for that series
- **THEN** the system renders a marker for that peak at its measured distance on or alongside the current heatmap view

#### Scenario: Handle no-detection frame in visualization
- **WHEN** a peak series is selected in the rendered-heatmap peak selector and the current H5 frame has no detection for that series
- **THEN** the system indicates the absence of a peak without drawing a misleading distance marker

#### Scenario: Export selected peak marker
- **WHEN** a peak series is selected in the rendered-heatmap peak selector and the user exports a synced video with a heatmap overlay
- **THEN** the exported heatmap overlay includes the detected peak marker from the selected peak series for each output frame that maps to a detected H5 peak row

#### Scenario: Do not render unselected peak markers
- **WHEN** multiple peak series exist and only one is selected in the rendered-heatmap peak selector
- **THEN** the rendered heatmap and exported overlay omit markers from the unselected peak series

### Requirement: Aligned signal plot
The system SHALL provide a separate Signals area above the Timeline area for reviewing imported time-series measurements against the shared physical timeline.

#### Scenario: Display signals area
- **WHEN** the user launches the alignment workbench
- **THEN** the system displays a boxed Signals area above the boxed Timeline area

#### Scenario: Plot multiple H5 peak distance signals
- **WHEN** one or more visible peak series resources exist
- **THEN** the Signals area plots each visible peak series over H5 elapsed time

#### Scenario: Use assigned peak series colors
- **WHEN** the Signals area plots multiple peak series
- **THEN** each peak series uses its assigned readable comparison color rather than all peak series using the H5 track color

#### Scenario: Show concise peak legend labels
- **WHEN** the Signals area legend identifies plotted peak series
- **THEN** each peak series legend text uses its concise display name, including enough algorithm or import context to distinguish it from other peak series

#### Scenario: Show detected and candidate distances
- **WHEN** a peak series contains detected frames and no-detection frames with candidate distances
- **THEN** the Signals area plots `candidate_peak_distance_m` values segmented by detection status, rendering detected frames as the primary signal and no-detection frames as a lower-alpha signal for that peak series

#### Scenario: Preserve missing-value gaps
- **WHEN** a peak-distance measurement has no plottable detected or candidate value
- **THEN** the Signals area leaves an actual gap rather than connecting a line through that measurement

#### Scenario: Show compact legend
- **WHEN** the Signals area contains one or more plotted signals
- **THEN** the system displays a compact legend identifying the plotted signal meanings

### Requirement: Current-time indicators
The system SHALL show current-time indicators in the Timeline and Signals areas with consistent scrub affordances and preserved range semantics.

#### Scenario: Show signal playhead
- **WHEN** the Signals area is visible
- **THEN** the system displays a vertical current-time indicator at the shared timeline current time

#### Scenario: Signal playhead follows current time
- **WHEN** playback, timeline scrubbing, signal playhead scrubbing, or time navigation changes the shared current time
- **THEN** the Signals current-time indicator moves to the updated time without changing the Signals plot range mode

#### Scenario: Signal playhead has interaction affordance
- **WHEN** the user hovers over the draggable Signals current-time indicator hit area
- **THEN** the system uses the same cursor or equivalent hover affordance used by the draggable Timeline current-time marker

#### Scenario: Drag signal playhead
- **WHEN** the user drags the Signals current-time indicator
- **THEN** the system updates the shared current time according to the Signals plot x-axis time mapping at the pointer position

#### Scenario: Clamp signal playhead drag to signal x-limits
- **WHEN** the user drags the Signals current-time indicator beyond the Signals plot's current x-axis limits
- **THEN** the system clamps the shared current time to the nearest current Signals x-axis limit

#### Scenario: Drag signal playhead in manual x mode
- **WHEN** the user drags the Signals current-time indicator while the Signals plot x-axis is in manual mode
- **THEN** the system uses the Signals plot's current manual x-axis scale to map pointer position to shared current time, even when that scale differs from the Timeline playhead scale

#### Scenario: Preserve signal plot range during signal playhead drag
- **WHEN** the user drags the Signals current-time indicator
- **THEN** the system does not change the Signals plot x-axis range, y-axis range, x-axis range mode, y-axis range mode, or the Timeline visible range

#### Scenario: Signal playhead scrub does not mark session dirty
- **WHEN** the user drags the Signals current-time indicator
- **THEN** the system changes only the shared current time and does not mark the current session dirty

#### Scenario: Ignore signal plot background for scrubbing
- **WHEN** the user presses or drags in the Signals plot outside the current-time indicator hit area
- **THEN** the system does not treat that interaction as current-time indicator scrubbing

#### Scenario: Timeline playhead has interaction affordance
- **WHEN** the user hovers over the draggable Timeline current-time marker hit area
- **THEN** the system uses a cursor or equivalent hover affordance that indicates the Timeline marker can be dragged

#### Scenario: Timeline playhead drag takes precedence over track drag
- **WHEN** the user starts a drag in the Timeline current-time marker hit area and the marker overlaps a timeline track bar
- **THEN** the system drags the current-time marker rather than the underlying track bar

#### Scenario: Match playhead visual affordance
- **WHEN** both the Timeline and Signals current-time indicators are visible
- **THEN** the system presents them as the same class of draggable playhead control, using matching interaction affordance and modest transparency so underlying content remains visible

### Requirement: Shared timeline and Signals x-range
The timeline widget and the Signals plot SHALL always share the same visible x-range via `TimelineRangeModel`. The user MAY zoom or pan the shared x-range using scroll wheel, middle-mouse drag, or right-click drag on either widget. The view SHALL NOT auto-fit after a track-bar drag is released.

#### Scenario: Timeline and Signals always synchronized
- **WHEN** the user zooms or pans on either the timeline or the Signals plot
- **THEN** both views update to show the same x-range immediately

#### Scenario: Track bar drag preserves zoom
- **WHEN** the user drags a track bar (camera or Leg2) and releases
- **THEN** the visible time range is unchanged from before the drag began

### Requirement: Signal plot range mode
The Signals plot x-axis SHALL always follow the shared `TimelineRangeModel`. There is no separate Manual x-axis mode. The x-axis right-click submenu SHALL show only range min/max inputs and a "Zoom to Fit" action.

#### Scenario: X axis follows timeline range
- **WHEN** the shared timeline range changes
- **THEN** the plot x-limits match the current timeline view bounds

#### Scenario: X axis aligns time mapping
- **WHEN** the Timeline and Signals plot are visible
- **THEN** the Signals plot data area and Timeline time-bar area map the same time values to the same horizontal screen positions

#### Scenario: Range mode context menu
- **WHEN** the user opens the Signals plot context menu
- **THEN** the X Axis submenu shows range min/max inputs and "Zoom to Fit"; no Auto/Manual toggle is present

#### Scenario: Disable x transformations
- **WHEN** the user opens the Signals plot right-click menu
- **THEN** Log X, FFT, Y vs. Y', dy/dx, Phase Map, Invert X, Mouse Mode, and the generic View All action are not present

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

### Requirement: Signal plot view persistence
The system SHALL persist Signals plot view settings in alignment session files.

#### Scenario: Save signal plot view settings
- **WHEN** the user saves an alignment session
- **THEN** the session file includes the Signals plot y-axis range mode and any active manual y range, but does not include the x-axis range mode or manual x range

#### Scenario: Restore signal plot view settings
- **WHEN** the user loads an alignment session containing Signals plot view settings
- **THEN** the system restores the saved y-axis range mode and manual y range, and ignores any saved x-axis range mode or manual x range

#### Scenario: Load older session without signal plot view settings
- **WHEN** the user loads an alignment session that does not contain Signals plot view settings
- **THEN** the system uses default Signals plot settings equivalent to x Timeline mode and y auto mode

### Requirement: Signal plot x-axis session fields ignored
The system SHALL NOT save the Signals plot x-axis range mode or manual x-range to the session file. When loading a session that contains these fields from a previous version, the system SHALL silently ignore them.

#### Scenario: Old session with x range mode loads cleanly
- **WHEN** the user loads a session file that contains `x_range_mode` or `manual_x_range` fields for the Signals plot
- **THEN** the session loads without error and those fields are ignored

#### Scenario: Saving session omits x range fields
- **WHEN** the user saves a session
- **THEN** the session file does not contain Signals plot x-axis range mode or manual x-range fields

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

#### Scenario: Select raw or filtered ultrasonic display from Signals area
- **WHEN** a Leg2 ultrasonic datasource is loaded
- **THEN** the Signals area lets the user choose whether the plot displays the raw or filtered ultrasonic signal while keeping only one Leg2 ultrasonic signal plotted at a time

#### Scenario: Use Leg2 track color for ultrasonic signal
- **WHEN** the Signals area plots a Leg2 ultrasonic signal
- **THEN** the plotted signal uses a readable plot color derived from the same color family as the Leg2 timeline track

#### Scenario: Segment ultrasonic signal by ReliableFlag
- **WHEN** the selected Leg2 ultrasonic signal is plotted
- **THEN** the Signals area renders samples where `DataRecordCommon.ReliableFlag` is true as a slightly transparent primary signal and samples where `DataRecordCommon.ReliableFlag` is false as a lower-alpha signal

#### Scenario: Preserve ultrasonic missing-value gaps
- **WHEN** a selected Leg2 ultrasonic sample has no plottable distance value
- **THEN** the Signals area leaves an actual gap rather than connecting a line through that sample

#### Scenario: Align Leg2 signal with timeline geometry
- **WHEN** the Signals plot x-axis is in Timeline mode and a Leg2 ultrasonic signal is plotted
- **THEN** the Leg2 ultrasonic signal, Leg2 timeline bar, H5 peak-distance signal, and current-time indicators map the same shared time values to the same horizontal screen positions

#### Scenario: Show Leg2 signal legend entry
- **WHEN** the Signals area contains a plotted Leg2 ultrasonic signal
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
- **THEN** the session file includes the Leg2 `.mat` path, Leg2-to-H5 offset, and selected ultrasonic signal kind, without persisting a Leg2 datasource visibility field

#### Scenario: Restore Leg2 MAT session state
- **WHEN** the user loads an alignment session containing Leg2 ultrasonic datasource state
- **THEN** the system reloads the stored Leg2 `.mat` file and restores the Leg2-to-H5 offset, selected signal kind, timeline track, and Signals plot display

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
The system SHALL provide a top-level Resources menu for heatmap alignment resource management.

The system SHALL keep Load terminology for primary Camera Video and Radar Raw (H5) actions. The system SHALL use Import terminology for optional external peak series files where those actions are touched by this change. The system SHALL prefer Unload terminology over Clear for resource removal where those actions are touched by this change.

#### Scenario: Show resource management entry
- **WHEN** the user chooses the menu action to manage resources
- **THEN** the system opens or focuses the Resources window

#### Scenario: Load resources from menu
- **WHEN** the user opens the Resources menu
- **THEN** the menu provides load or replace actions for Camera Video, Radar Raw (H5), and Leg2 MAT resources, and MAY provide append actions for Import Peak Series or Generate Peak Series

#### Scenario: Unload resources from menu
- **WHEN** the user opens the Resources menu
- **THEN** the menu provides unload actions for unloadable Camera Video, Radar Raw (H5), and Leg2 MAT resources, enabling each action only when it can apply to the current session state

#### Scenario: Peak row actions stay row-scoped
- **WHEN** the user wants to save, save as, reload, or unload a specific peak series
- **THEN** the system provides those actions from the corresponding peak series row in the Resources window rather than as ambiguous global peak actions

#### Scenario: Keep session actions in File menu
- **WHEN** the user opens the File menu
- **THEN** the menu remains the place for opening sessions, saving sessions, saving sessions as a new path, closing the current session, exporting synced video, and quitting the workbench

### Requirement: Resources window
The system SHALL provide a modeless Resources window that summarizes supported heatmap alignment resources and allows resource management without blocking the main alignment workflow.

The Resources window SHALL list single rows for Camera Video, Radar Raw (H5), and Leg2 MAT resource slots. The Resources window SHALL list zero or more peak series rows, one per generated or imported peak series resource, rather than one fixed Radar Peak (JSON) row.

#### Scenario: Open Resources window
- **WHEN** the user chooses the Resources window action
- **THEN** the system shows a modeless Resources window that can stay open while the main heatmap alignment window remains usable

#### Scenario: Reopen existing Resources window
- **WHEN** the Resources window is already open and the user chooses the Resources window action again
- **THEN** the system brings the existing Resources window to the foreground instead of creating a duplicate Resources window or moving the existing window from its user-chosen position

#### Scenario: List supported resource rows
- **WHEN** the Resources window is visible
- **THEN** the window lists rows for Camera Video, Radar Raw (H5), Leg2 MAT, and each current peak series resource

#### Scenario: No fixed peak row when no peak series exist
- **WHEN** no peak series resources exist
- **THEN** the Resources window does not need to show a fixed empty Radar Peak (JSON) slot row

#### Scenario: Refresh resource rows
- **WHEN** a resource is loaded, replaced, imported, generated, unloaded, reloaded, saved, or fails to load while the Resources window is visible
- **THEN** the window updates the affected resource rows without requiring the user to close and reopen the window

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
- **THEN** the row indicates whether the resource is loaded, unloaded, missing, invalid, loaded with warnings, generated unsaved, or another applicable concise state

#### Scenario: Show visual color marker
- **WHEN** a resource has a semantic timeline, signal, overlay, or warning color association
- **THEN** the row shows that association as a compact visual swatch or marker cell rather than as text labeled "Color"

#### Scenario: Show resource type and role
- **WHEN** the Resources window lists a resource row
- **THEN** the row identifies the resource type and current role, using user-facing names such as Camera Video, Radar Raw (H5), Peak Series, or Leg2 MAT

#### Scenario: Show peak series display name
- **WHEN** the Resources window lists a peak series row
- **THEN** the row shows the peak series display name so multiple generated or imported peak series can be distinguished

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
- **THEN** the row or selected-row details show useful resource-specific information such as camera duration and FPS, radar H5 frame count and duration, peak detection count and algorithm, or Leg2 sample and reliable-segment counts

#### Scenario: Show stale remembered path
- **WHEN** a loaded session remembers a resource path that cannot be reloaded
- **THEN** the corresponding resource row remains visible with the remembered path and a missing or invalid status

### Requirement: Resources window actions
The system SHALL allow users to manage resources from the Resources window.

#### Scenario: Load unloaded resource
- **WHEN** the user selects an unloaded primary resource row and invokes its load action
- **THEN** the system opens the appropriate file picker and starts loading that resource into the selected slot

#### Scenario: Replace loaded resource
- **WHEN** the user selects a loaded primary resource row and invokes its load or replace action
- **THEN** the system clears the currently active resource from that slot before starting the replacement load, presents the target as pending/loading, and does not allow the previous resource to remain active while the target is pending

#### Scenario: Import peak series from Resources window
- **WHEN** the user invokes Import Peak Series from the Resources window
- **THEN** the system opens the appropriate file picker and appends the imported peak series as a separate resource row after validation

#### Scenario: Generate peak series from Resources window
- **WHEN** Radar Raw (H5) is loaded, no H5 load or replacement is pending, and the user invokes Generate Peak Series from the Resources window
- **THEN** the system opens the Generate Peak Series dialog for the active loaded H5 resource

#### Scenario: Unload optional resource row
- **WHEN** the user selects a loaded optional resource row and invokes its unload action
- **THEN** the system clears that resource row without unloading unrelated resources

#### Scenario: Unload primary resource row
- **WHEN** the user selects a loaded Camera Video or Radar Raw (H5) row and invokes its unload action
- **THEN** the system clears that primary resource slot and dependent preview state without unloading unrelated resources that remain valid independently

#### Scenario: Unload camera preserves independent radar resources
- **WHEN** the user unloads Camera Video while Radar Raw (H5), peak series resources, or Leg2 MAT resources are loaded
- **THEN** the system clears camera-dependent preview, timeline, viewport, and export state while preserving the loaded radar and Leg2 resources that remain valid

#### Scenario: Unload H5 preserves independent signal resources
- **WHEN** the user unloads Radar Raw (H5) while peak series resources or Leg2 MAT resources are loaded
- **THEN** the system clears radar-H5-dependent rendered heatmap and radar timeline state while preserving loaded peak series and Leg2 MAT resources as signal resources when their loaded data remains available

#### Scenario: Signal resources without H5
- **WHEN** Radar Raw (H5) is not loaded and peak series resources, Leg2 MAT, both, or neither are loaded
- **THEN** the Signals and Timeline areas display whichever optional signal resources are loaded against the shared absolute zero-time coordinate

#### Scenario: Reload remembered resource
- **WHEN** the user selects a resource row with a remembered path and invokes reload
- **THEN** the system loads the remembered path using the same immediate-clear behavior as load or replace when the requested identity differs from the active resource identity

#### Scenario: Reveal resource path
- **WHEN** the Resources window or resource row context menu shows the action that opens the platform file browser
- **THEN** invoking that action reveals the resource path without changing loaded resources

#### Scenario: Context menu mirrors row actions
- **WHEN** the user opens a Resources row context menu
- **THEN** the context menu offers the same applicable row-scoped actions as the Resources window selected-row controls, including save, save as, reload, and unload for peak series rows when applicable

#### Scenario: Ignore empty table action target
- **WHEN** the user invokes a row action without a selected applicable resource row
- **THEN** the system is not required to start a load or replace action

#### Scenario: Clear all resources asks confirmation
- **WHEN** the user invokes Clear All Resources from the Resources window and confirms the action
- **THEN** the system clears loaded resources and dependent preview state while preserving the current session path

#### Scenario: Clear all resources message
- **WHEN** the user invokes Clear All Resources
- **THEN** the confirmation message tells the user that loaded resources will be cleared and the current session path will be kept

#### Scenario: Clear all resources with unsaved peaks
- **WHEN** unsaved generated peak series exist and the user invokes Clear All Resources
- **THEN** the system includes the unsaved peak-loss warning in the confirmation flow before discarding those peaks

#### Scenario: Save peak series from Resources window
- **WHEN** a peak series row with in-memory measurements is selected and the user invokes Save or Save As
- **THEN** the system writes that selected peak series to canonical peak-distance JSON according to the peak-save requirements

### Requirement: Session dirty state
The system SHALL use a single session-level dirty flag. Any **user-initiated** change to persisted `AlignmentSession` fields SHALL mark the session dirty, including viewport geometry, render and preprocess settings, timeline offset, export overlay settings and visibility, signal plot view settings, optional datasource paths and signal kind, and resource changes from explicit user load, unload, replace, import, or clear actions.

The system SHALL mark the session dirty when the user starts a resource load or replace from the UI (for example file dialogs or Resources window actions), not when background camera or H5 resource jobs complete.

The system SHALL NOT mark the session dirty when camera or H5 resource jobs complete after session open, session-load reconciliation, or `--session` startup, including updates inside `_apply_camera_job_result` and `_apply_h5_job_result`.

The system SHALL NOT mark the session dirty for ephemeral UI state that is not stored in the alignment session JSON, including timeline visible zoom or range.

The system SHALL NOT mark the session dirty when the user changes timeline playhead position (`current_time_s`) only.

The system SHALL suppress dirty marking during programmatic session load, control population from session, session reset after close, and reconcile-driven resource loads.

#### Scenario: Show dirty indicator in window title
- **WHEN** the session is dirty
- **THEN** the main heatmap alignment window title appends an asterisk (`*`) after the session name or untitled label

#### Scenario: Clear dirty indicator after save
- **WHEN** the user successfully saves the session to disk
- **THEN** the system clears the dirty flag and removes the asterisk from the window title

#### Scenario: Clear dirty indicator after open
- **WHEN** the user successfully opens a saved alignment session from disk
- **THEN** the system clears the dirty flag and removes the asterisk from the window title

#### Scenario: No dirty indicator after open when jobs complete
- **WHEN** the user opens a saved alignment session and background camera or H5 resource jobs complete without further user edits
- **THEN** the session remains not dirty and the window title does not show an asterisk

#### Scenario: Mark dirty on signal kind and export overlay controls
- **WHEN** the user changes Leg2 signal kind or toggles export overlay visibility, preview, or reset controls
- **THEN** the system marks the session dirty because those values are persisted in the alignment session JSON

### Requirement: Unsaved changes before destructive session navigation
When the session is dirty, or when any generated peak series is unsaved, the system SHALL prompt the user with **Save**, **Don't Save**, and **Cancel** before actions that would discard in-memory session state or unsaved peak series.

The prompt SHALL use conventional desktop wording: state that there are unsaved changes and ask whether to save them before quitting, closing the current session, or opening another session. The system SHALL NOT use internal terms such as "workbench" in the prompt text.

When generated peak series are unsaved, the prompt body SHALL additionally warn that unsaved peak-distance data will be lost and that saving the alignment session does not write peak JSON. The prompt SHALL NOT imply that choosing **Save** in that dialog saves peak JSON.

For **Open Session**, the system SHALL show the unsaved-changes prompt before the open file dialog when the current session is dirty or any generated peak series is unsaved.

For **Save** in the prompt, the system SHALL save to the current session path when known, or behave like Save Session As when the session is untitled. If save fails or the user cancels Save As, the system SHALL cancel the guarded action and leave the current session unchanged and dirty.

For **Don't Save**, the system SHALL proceed with the requested action without writing the current session to disk or unsaved generated peak series to JSON.

For **Cancel**, the system SHALL abort the requested action and leave the current session unchanged.

The system SHALL NOT show the unsaved-changes prompt when loading a session from `--session` on startup or when tests call session load helpers directly without the menu guard.

#### Scenario: Prompt before quit when dirty
- **WHEN** the user chooses Quit and the session is dirty or any generated peak series is unsaved
- **THEN** the system shows the unsaved-changes prompt before exiting

#### Scenario: Prompt before close session when dirty
- **WHEN** the user closes the current session and the session is dirty or any generated peak series is unsaved
- **THEN** the system shows the unsaved-changes prompt before clearing the session

#### Scenario: Prompt before open session when dirty
- **WHEN** the user chooses Open Session and the session is dirty or any generated peak series is unsaved
- **THEN** the system shows the unsaved-changes prompt before the open file dialog

#### Scenario: No prompt when clean
- **WHEN** the user quits, closes the session, or opens another session and neither the session nor any peak series is unsaved
- **THEN** the system does not show the unsaved-changes prompt for that action

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
- **THEN** the system updates the current session path to the chosen path, clears the dirty flag, and refreshes the main window title and Resources window session context

#### Scenario: Save session without requiring loaded camera and H5
- **WHEN** the user invokes Save Session or Save from an unsaved-changes prompt
- **THEN** the system allows save based on the current alignment session JSON and does not require camera video and H5 recording to be loaded in memory, using validation that permits missing or absent source files on disk when paths are recorded

#### Scenario: Open session updates identity
- **WHEN** the user opens a saved session successfully
- **THEN** the system updates the current session path to the opened path, clears the dirty flag, and refreshes the main window title and Resources window session context

#### Scenario: Close current session after dirty discard or clean confirmation
- **WHEN** the user invokes Close Session and proceeds after the unsaved-changes prompt (including Don't Save), or confirms close when the session is clean but not pristine, or closes a pristine clean session without a prompt
- **THEN** the system clears loaded resources and session state, forgets the current session path, clears the dirty flag, and returns to an untitled session without exiting the program

### Requirement: Main layout resource control cleanup
The system SHALL remove duplicated or misplaced resource and render controls from the main heatmap alignment layout after equivalent Resources menu/window actions or visualization-owned controls exist.

#### Scenario: Launch with resource menu available
- **WHEN** the user launches the heatmap alignment workbench
- **THEN** the main layout does not show the previous top-row load buttons for Camera Video, Radar Raw (H5), and session loading

#### Scenario: Keep render controls near rendered heatmap
- **WHEN** the user views the Rendered Heatmap panel
- **THEN** rendered-heatmap color minimum and maximum controls are available in that panel rather than in a separate bottom Render panel

#### Scenario: Keep Signals controls near Signals plot
- **WHEN** optional Leg2 MAT resources are loaded
- **THEN** the selected Leg2 signal kind control is available in the Signals area near the plot it affects

#### Scenario: Remove datasource visibility checkboxes
- **WHEN** optional Radar Peak (JSON) or Leg2 MAT resources are loaded
- **THEN** the main layout does not show Show Peak Marker or Show Leg2 Signal checkboxes for datasource-level visibility

#### Scenario: Remove bottom Render panel
- **WHEN** the user views the main heatmap alignment workflow
- **THEN** the main layout does not show the previous bottom Render panel containing mixed render, preprocess, peak, and Leg2 controls

#### Scenario: Keep alignment controls in main workflow
- **WHEN** the user views the Timeline and preview areas
- **THEN** playback, current-time, offset, nudge, viewport, rendered-heatmap, Signals, and export-preview controls remain available in the main workflow where they directly affect alignment or visual review

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
The system SHALL treat a pending same-resource load request as replaceable by the newest request while clearing any differing active resource from that slot before the new load begins.

The system SHALL NOT keep a previous active resource available as the active value for a slot while a different resource identity is pending for that slot. If the pending load fails, the slot SHALL remain empty or failed and SHALL NOT automatically restore the previous active resource.

#### Scenario: Supersede pending camera load
- **WHEN** a camera video load is pending and the user starts loading another camera video
- **THEN** the system supersedes the earlier pending camera load without asking the user to cancel it first

#### Scenario: Cancel superseded in-flight camera work promptly
- **WHEN** a camera video load is superseded while preview proxy generation or other in-flight camera preparation is still running
- **THEN** the system actively requests cancellation of the superseded work, including terminating an active preview-proxy ffmpeg process when possible, so the newest camera load request is not blocked waiting for discarded work to finish

#### Scenario: Ignore stale camera load result
- **WHEN** a superseded camera load finishes after a newer camera load request has started
- **THEN** the system ignores the stale result and does not apply it to the session or previews

#### Scenario: Clear previous camera before replacement
- **WHEN** a loaded camera video exists and the user starts loading a different camera video
- **THEN** the system clears the previous camera video, camera preview, camera-dependent viewport/export state, and active camera metadata before the replacement load is presented as pending

#### Scenario: Clear previous H5 before replacement
- **WHEN** a loaded Radar Raw (H5) recording exists and the user starts loading a different H5 recording or a different H5 selection identity
- **THEN** the system clears the previous active H5 recording, rendered heatmap state, H5 axes/hover caches, H5 timeline metadata, and H5-derived action readiness before the replacement load is presented as pending

#### Scenario: Failed camera replacement leaves slot failed
- **WHEN** a loaded camera video existed and a replacement camera video fails to load
- **THEN** the system leaves the camera slot empty or failed, reports the failure in the Resources window, and does not automatically restore the previous camera video

#### Scenario: Failed H5 replacement leaves slot failed
- **WHEN** a loaded Radar Raw (H5) recording existed and a replacement H5 recording fails to load
- **THEN** the system leaves the H5 slot empty or failed, reports the failure in the Resources window, and does not automatically restore the previous H5 recording

#### Scenario: Apply session resource path after replacement success
- **WHEN** a pending resource replacement finishes successfully
- **THEN** the system updates the active session resource path and metadata to the replacement resource

#### Scenario: Do not apply failed resource path to loaded metadata
- **WHEN** a pending resource replacement fails or is superseded
- **THEN** the system does not present the failed or superseded file as a loaded resource, while it may keep the failed target path visible as the row's pending or failed request for retry/reload purposes

#### Scenario: Preserve viewport for same-size camera replacement
- **WHEN** a replacement camera video successfully loads with the same source dimensions as the previously active camera video and the previous viewport geometry was preserved as session state
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

#### Scenario: Cancel pending load
- **WHEN** the user cancels a pending load or replacement for a resource slot
- **THEN** the system cancels or abandons the pending target, leaves the slot empty or failed if a different active resource was already cleared for that target, and does not restore stale data automatically

#### Scenario: Cancel wins before late success is applied
- **WHEN** the user cancels a pending resource job before that job's completion is accepted on the GUI thread
- **THEN** the system treats the job as cancelled, releases any late success payload, and does not apply the cancelled target as the active resource

#### Scenario: Show cancellation promptly
- **WHEN** the user cancels a pending resource job whose underlying file operation cannot stop immediately
- **THEN** the Resources window and affected previews show cancelling or cleared state promptly without waiting for the underlying operation to return

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
- **THEN** the system cancels or abandons those jobs, clears pending job state and stale slot state, and does not apply their completions to a later workbench instance

#### Scenario: Ignore worker completion after manager deletion
- **WHEN** a background resource worker completes after the workbench has been closed and its job manager QObject is no longer alive
- **THEN** the worker completion path exits without raising a traceback and without attempting to update deleted GUI objects

#### Scenario: Abandoned manager skips worker dispatch
- **WHEN** resource jobs are abandoned during window close, session close, or workbench reset to an empty session
- **THEN** late worker runnables observe the abandoned state before dispatch, release any completed payload without applying it, and do not raise a traceback

#### Scenario: Abandon jobs on session close
- **WHEN** the user closes the current session and returns to an empty workbench while a camera or H5 resource job is pending
- **THEN** the system cancels or abandons those jobs, clears pending job state and stale slot state, and does not apply their completions to the reset session

#### Scenario: Discard stale pending job payloads
- **WHEN** a superseded or otherwise ignored camera or H5 job completion would leave a pending result payload unused
- **THEN** the system discards that payload promptly so stale results cannot retain HDF5-backed records or other resources in manager state

#### Scenario: Do not abandon matching jobs on session open
- **WHEN** the user opens a saved alignment session and reconciliation selects **keep** for a camera or H5 slot with an in-flight job for the same resource identity
- **THEN** the system does not abandon that in-flight job solely because of the session open

### Requirement: H5 replacement preserves independent peak series
The system SHALL preserve peak series resources as optional signal resources when a different Radar Raw (H5) resource is requested or successfully replaces the current H5 recording, unless a session-open reconciliation or explicit clear/unload operation removes those peak resources.

The system SHALL NOT automatically unload all peak series solely because H5 changed. Imported peak series validation warnings SHALL remain row-specific. Generated peak series that remain after H5 replacement SHALL continue to behave as signal resources until the user unloads them, clears all resources, or opens another session. H5-derived actions SHALL NOT use preserved peak series or stale H5 data as a substitute for an active loaded H5 resource.

#### Scenario: Preserve peak series after H5 replacement request
- **WHEN** a new H5 recording is requested while peak series resources exist
- **THEN** the system may preserve existing peak series resources as independent signal resources while clearing the previous active H5 recording and H5-dependent rendered heatmap state

#### Scenario: Preserve peak series after different H5 replacement succeeds
- **WHEN** a new H5 recording successfully replaces a different active H5 recording while peak series resources exist
- **THEN** the system preserves the existing peak series resources and updates H5-dependent rendered heatmap state for the new H5

#### Scenario: Preserve peaks after failed H5 replacement without restoring H5
- **WHEN** a pending H5 replacement fails before becoming active
- **THEN** the system preserves independent peak series resources but leaves the H5 slot empty or failed instead of restoring the previously active H5 recording

### Requirement: Export availability during resource jobs
The system SHALL keep synced video export outside the background resource job system for this change while preventing export from starting with unstable or unavailable required resources.

#### Scenario: Disable export while camera is loading
- **WHEN** a camera video load or replacement is pending
- **THEN** the system disables starting synced video export

#### Scenario: Disable export while H5 is loading
- **WHEN** a Radar Raw (H5) load or replacement is pending
- **THEN** the system disables starting synced video export

#### Scenario: Allow export when required resources are stable
- **WHEN** camera video and Radar Raw (H5) resources are loaded and no required export resource is in an in-flight load, replace, or cancel phase
- **THEN** the system allows synced video export according to the existing export requirements

#### Scenario: Failed replacement does not allow export without resources
- **WHEN** a camera or H5 replacement fails after clearing the previous active required resource
- **THEN** the system keeps synced video export disabled until the required camera and H5 resources are loaded again

#### Scenario: Failed job status does not alone block export
- **WHEN** a resource job slot is in `failed` phase because the last load attempt failed but required export resources are loaded and stable
- **THEN** starting synced video export is not disabled solely because of the failed job phase

#### Scenario: Preserve existing export progress behavior
- **WHEN** synced video export is running
- **THEN** the system uses the existing export progress behavior and prevents starting a second export simultaneously

### Requirement: Session load reconciliation
The system SHALL load a saved alignment session by reconciling the session JSON snapshot against the active workbench state rather than unconditionally tearing down every loaded resource on each open.

Reconciliation SHALL iterate a registered set of resource slots (camera video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT for the current workbench) and, for each slot, SHALL choose one of:

- **keep** - the desired resource identity from the session matches the active loaded resource or an in-flight resource job for that slot; the system does not close, unload, abandon, or restart load work for that slot solely because of the session open
- **load** - the session requests a non-empty resource identity that does not match the active or in-flight identity, or the slot is not loaded; the system clears any differing active resource for that slot before starting load work for the desired identity
- **unload** - the session requests an empty path for that slot but the slot is still loaded; the system clears or unloads that resource so it does not remain active from a previous session

Resource identity SHALL be determined from session content, not from the session JSON file path on disk. Camera identity is the camera video path. H5 identity is the H5 file path plus session, group, entry, and subsweep indices. Radar Peak (JSON) identity is the peak-distance JSON path. Leg2 MAT identity is the Leg2 MAT path. An empty path means the slot is not requested.

After resource reconciliation, the system SHALL always apply non-resource session fields from the JSON snapshot, including viewport geometry, render settings, timeline state, export overlay, signal plot view, preview state, Leg2 offset, and selected Leg2 signal kind, even when one or more resource slots used **keep**.

Before starting H5 **load** actions, the system SHALL assign the desired session snapshot to the active workbench session object so H5 selection indices read during H5 load setup match the session being opened.

#### Scenario: Keep camera slot when identity matches
- **WHEN** the user loads a saved alignment session whose camera video path matches the active camera resource or matches the target of an in-flight camera resource job
- **THEN** the system reconciles the camera slot as **keep** and does not close the active camera source or abandon the in-flight camera job solely because of the session open

#### Scenario: Keep H5 slot when identity matches
- **WHEN** the user loads a saved alignment session whose H5 path and selection indices match the active H5 resource or match the target of an in-flight H5 job
- **THEN** the system reconciles the H5 slot as **keep** and does not close the active H5 source or abandon the in-flight H5 job solely because of the session open

#### Scenario: Load camera when session requests different identity
- **WHEN** the user loads a saved alignment session whose camera video path differs from the active camera resource and in-flight camera job target
- **THEN** the system clears the active camera slot and starts camera loading using the same background camera resource job behavior as an explicit camera load or reload

#### Scenario: Load H5 when session requests different identity
- **WHEN** the user loads a saved alignment session whose H5 path or selection indices differ from the active H5 resource and in-flight H5 job target
- **THEN** the system clears the active H5 slot and starts H5 loading using the same background H5 resource job behavior as an explicit H5 load or reload

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
- **THEN** the system still restores session fields from the JSON snapshot that are not satisfied by **keep** alone, such as viewport geometry, render settings, timeline state, preview state, export overlay settings, Leg2 offset, and selected Leg2 signal kind

#### Scenario: Keep GUI responsive when slots use keep
- **WHEN** the user opens a saved alignment session and all resource slots reconcile as **keep**
- **THEN** the system does not block the GUI thread on redundant camera proxy, H5, peak JSON, or Leg2 MAT reload work for those slots

#### Scenario: Keep GUI responsive during session open
- **WHEN** the user opens a saved alignment session that requires background camera or H5 resource work for slots reconciled as **load**
- **THEN** the system keeps the main window and Resources window responsive on the GUI thread while that work continues, using the same non-blocking resource job presentation as explicit resource loads

#### Scenario: Failed session-open load leaves slot failed
- **WHEN** the user opens a saved alignment session that requests a different camera or H5 resource and that resource fails to load
- **THEN** the corresponding slot remains empty or failed and the system does not restore the previous session's resource for that slot

### Requirement: In-app peak generation from loaded H5
The system SHALL allow the user to generate peak series measurements from the currently loaded Radar Raw (H5) recording without leaving the heatmap alignment workbench.

Generation SHALL use the loaded H5 session, group, entry, and subsweep indices from the active current heatmap track. Generation SHALL process all frames. Generation SHALL use the selected algorithm and threshold from the Generate Peak Series dialog.

The system SHALL enable Generate Peak Series only when Radar Raw (H5) is loaded, the active loaded H5 identity matches the current H5 slot/session request, and no H5 load, replacement, cancellation, or waiting job is pending. The system SHALL disable or omit Generate Peak Series when H5 is not loaded or when the H5 slot is pending, failed, cancelling, waiting, or stale.

Generation SHALL run synchronously on the GUI thread for v1 unless implementation measurements show that background execution is necessary, and SHALL reuse the in-memory H5 record rather than re-opening the file through `export_peak_distances()`.

#### Scenario: Generate peaks from loaded H5
- **WHEN** Radar Raw (H5) is loaded, no H5 load or replacement is pending, and the user confirms the Generate Peak Series dialog
- **THEN** the system computes peak-distance measurements from the active loaded H5 and appends them as a new unsaved peak series resource without writing JSON to disk

#### Scenario: Generate disabled without H5
- **WHEN** Radar Raw (H5) is not loaded
- **THEN** the system does not offer a usable Generate Peak Series action

#### Scenario: Generate disabled while H5 load is pending
- **WHEN** a Radar Raw (H5) load, replacement, waiting, or cancellation job is pending
- **THEN** the system does not offer a usable Generate Peak Series action and does not generate peaks from any previous H5 data

#### Scenario: Generate blocked from stale H5 object
- **WHEN** an old H5 object or peak series remains in memory but the active H5 slot no longer matches the current requested H5 identity
- **THEN** Generate Peak Series does not use that stale object and reports or presents H5 as unavailable for generation

#### Scenario: Refresh UI after generate
- **WHEN** peak generation completes successfully
- **THEN** the system updates the Signals plot, rendered-heatmap peak selector, rendered-heatmap marker, and Resources rows without requiring a separate import step

#### Scenario: Generate does not replace peak series
- **WHEN** the user invokes Generate Peak Series while peak series already exist
- **THEN** the system appends the newly generated peak series and preserves existing peak series

### Requirement: Peaks dirty state and Resources status
The system SHALL track unsaved state per peak series resource.

The system SHALL NOT add peak-series unsaved state to the main window title asterisk.

The system SHALL show generated unsaved state in the corresponding peak series Resources table Status column as **Generated (unsaved)** or an equivalent concise label. The system SHALL NOT add new table columns for this state.

#### Scenario: Show generated unsaved in Status column
- **WHEN** a peak series was generated and has not been saved to disk
- **THEN** that peak series resource row Status column shows **Generated (unsaved)** or an equivalent concise unsaved label

#### Scenario: Clear peak series unsaved state after save
- **WHEN** the user successfully saves a peak series to a JSON path
- **THEN** the system clears that peak series unsaved state and shows a normal loaded or saved status for that row

#### Scenario: Keep other peak unsaved states
- **WHEN** the user saves one unsaved peak series while another generated peak series remains unsaved
- **THEN** the system clears unsaved state only for the saved row

### Requirement: Save peaks from Resources
The system SHALL allow saving one selected peak series resource to canonical peak-distance JSON from the Resources window.

The system SHALL write JSON using the same format as `peak-distances` (`write_peak_distance_json` / `acconeer_peak_distances`).

Save SHALL be row-specific. Save SHALL write to the selected peak series path when one exists. If no path exists, Save SHALL behave like Save As and prompt for an output path. Save As SHALL always prompt for an output path. The default suggested filename SHALL be based on the loaded H5 stem, algorithm label, and `.json` extension when practical.

The system SHALL set or update the selected peak series path only after a successful save. The system SHALL mark the alignment session dirty when saved peak series path or persisted display metadata changes.

The system SHALL NOT write peak JSON automatically as part of Generate.

#### Scenario: Save generated peak series first save
- **WHEN** a generated peak series is unsaved, no JSON path is set for that row, and the user invokes Save on that row
- **THEN** the system prompts for an output path and writes canonical JSON on confirmation

#### Scenario: Save peak series to existing path
- **WHEN** a peak series has a JSON path and the user invokes Save on that row
- **THEN** the system confirms overwrite if the file exists and writes canonical JSON to that path

#### Scenario: Save As peak series
- **WHEN** peak-distance data exists for a selected peak series row and the user invokes Save As
- **THEN** the system prompts for an output path and writes canonical JSON to the selected path on confirmation

#### Scenario: Save disabled when selected row has no peak data
- **WHEN** no peak series row with in-memory measurements is selected
- **THEN** row-specific Save and Save As are disabled or omitted

#### Scenario: Save does not affect other peak series
- **WHEN** the user saves one peak series
- **THEN** the system does not write, unload, or change unsaved state for other peak series

### Requirement: Unsaved peaks in session navigation prompts
When any generated peak series is unsaved, the system SHALL include peak-loss warning text in the same unsaved-changes prompt used for a dirty alignment session on quit, close session, and open session, without showing a second modal solely for peaks.

The warning SHALL state that unsaved peak-distance data will be lost. The warning SHALL state that saving the alignment session does not write peak JSON. The warning SHALL NOT imply that choosing **Save** in that dialog writes peak JSON. The **Save** control SHALL retain its existing behavior (save alignment session only).

#### Scenario: Peaks-only unsaved still prompts
- **WHEN** one or more generated peak series are unsaved, the alignment session is not dirty, and the user quits, closes the session, or opens another session
- **THEN** the system shows the unsaved-changes prompt before proceeding

#### Scenario: Warn on quit with unsaved peaks
- **WHEN** the user quits while one or more generated peak series are unsaved
- **THEN** the unsaved-changes prompt includes text that unsaved peak-distance data will be lost and that saving the session does not save peak JSON

#### Scenario: Warn on open session with unsaved peaks
- **WHEN** the user opens another session while one or more generated peak series are unsaved
- **THEN** the same combined unsaved-changes prompt behavior applies as for quit

### Requirement: Confirmations for peak resource actions
The system SHALL confirm before unloading a peak series row when that row contains unsaved generated peak data.

The system SHALL confirm before Reload on a peak series row when that row contains unsaved generated peak data, because reload reads from disk and discards unsaved generated data.

The system SHALL prompt when the user saves the alignment session while any generated peak series is unsaved, warning that peak JSON is not saved with the session and that the user should save peak series from Resources first.

#### Scenario: Confirm unload with unsaved generated peaks
- **WHEN** a peak series row contains unsaved generated peak data and the user unloads that row
- **THEN** the system confirms that unsaved generated peak data for that row will be lost

#### Scenario: Confirm reload with unsaved generated peaks
- **WHEN** a peak series row contains unsaved generated peak data and the user invokes Reload on that row
- **THEN** the system shows a blocking confirmation that reload discards unsaved generated data and proceeds only if the user confirms

#### Scenario: Confirm save session with unsaved peaks
- **WHEN** one or more generated peak series are unsaved and the user invokes Save Session
- **THEN** the system warns that peak JSON is not included in the session save before continuing

#### Scenario: Session save does not persist generated peaks
- **WHEN** the user saves the alignment session while unsaved generated peak series exist and later reopens that session
- **THEN** the system loads saved/imported peak series from stored JSON paths, omits unsaved generated peak series that had no path, and does not restore unsaved generated peak measurements from the prior session

### Requirement: Multi-instance peak series resources
The system SHALL represent peak-distance outputs as zero or more peak series resources in the heatmap alignment workbench.

Each peak series resource SHALL have an in-session identity, display name, visible state for Signals plotting, assigned plot color, provenance, optional JSON path, measurements, and row-specific status or warning details. Peak series resources MAY be generated from the loaded H5 or imported from canonical peak-distance JSON.

The system SHALL allow multiple generated and imported peak series to coexist in the same session. Generating or importing a peak series SHALL append a new peak series row rather than replacing existing peak series.

The system SHALL keep Camera Video and Radar Raw (H5) as single primary loaded resources in this change. The system SHALL keep Leg2 MAT as a single optional resource in this change.

#### Scenario: Generate appends peak series
- **WHEN** Radar Raw (H5) is loaded and the user generates a peak series
- **THEN** the system appends a new unsaved peak series resource row without removing existing peak series rows

#### Scenario: Import appends peak series
- **WHEN** the user imports a canonical peak-distance JSON file
- **THEN** the system appends a new imported peak series resource row without removing existing peak series rows

#### Scenario: Multiple peak series coexist
- **WHEN** the user has generated or imported more than one peak series
- **THEN** the Resources window shows each peak series as a separate manageable resource row

#### Scenario: Preserve fixed primary resources
- **WHEN** this change is implemented
- **THEN** Camera Video and Radar Raw (H5) remain single primary resources and Leg2 MAT remains a single optional resource

### Requirement: Shared peak algorithm engine
The system SHALL provide a non-GUI peak algorithm engine used by both the heatmap alignment GUI and the `peak-distances` CLI.

The engine SHALL expose at least two algorithms: `zero_velocity_slice` with a concise user label such as `v0 slice`, and `sum_velocity` with a concise user label such as `sum v`. Each algorithm SHALL support the peak threshold parameter and SHALL use `DEFAULT_PEAK_THRESHOLD` as its default threshold unless the user supplies another value.

The GUI SHALL NOT implement peak algorithm selection or peak extraction directly in Qt plotting code.

#### Scenario: GUI and CLI share algorithms
- **WHEN** the GUI generates peaks and the CLI exports peaks for the same algorithm id and threshold
- **THEN** both paths use the same non-GUI algorithm implementation

#### Scenario: Generate with v0 slice
- **WHEN** the user selects the `v0 slice` algorithm and generates a peak series
- **THEN** the system computes peaks from the distance profile at the velocity bin nearest `0 m/s`

#### Scenario: Generate with sum v
- **WHEN** the user selects the `sum v` algorithm and generates a peak series
- **THEN** the system computes peaks from the profile formed by summing the distance/velocity map across velocity bins

### Requirement: Peak generation dialog
The system SHALL show a small Generate Peak Series dialog before generating peaks.

The dialog SHALL let the user choose the algorithm before generation, show the selected algorithm label, let the user edit the algorithm parameters supported in v1, and let the user edit the new peak series display name. The v1 parameter controls SHALL include threshold for both supported algorithms.

Generated default names SHALL be concise enough for Signals legends, for example `v0 slice, thresh 650` or `sum v, thresh 650`.

#### Scenario: Configure generated peak series
- **WHEN** the user invokes Generate Peak Series
- **THEN** the system presents a dialog for algorithm choice, threshold, and peak series name before running generation

#### Scenario: Generate uses entered params
- **WHEN** the user changes the threshold in the Generate Peak Series dialog and confirms generation
- **THEN** the new peak series is computed with the entered threshold and records that threshold in its metadata

#### Scenario: Cancel generation dialog
- **WHEN** the user cancels the Generate Peak Series dialog
- **THEN** the system does not compute peaks and does not append a peak series row

### Requirement: Rendered heatmap peak selector
The system SHALL provide a rendered-heatmap control that selects which peak series, if any, supplies the current-frame peak marker.

The selector SHALL include `None` and every loaded/generated peak series. The selector SHALL allow exactly one selected peak series at a time. The selector SHALL be independent of Signals plot visibility.

After successful Generate, the system SHALL select the newly generated peak series for the rendered heatmap marker by default.

#### Scenario: Select no heatmap peak marker
- **WHEN** the user chooses `None` in the rendered heatmap peak selector
- **THEN** the rendered heatmap view does not show a peak marker from any peak series

#### Scenario: Select one peak series marker
- **WHEN** multiple peak series exist and the user selects one of them in the rendered heatmap peak selector
- **THEN** the rendered heatmap view uses only that selected peak series for the current-frame peak marker

#### Scenario: Newly generated series becomes marker source
- **WHEN** peak generation completes successfully
- **THEN** the rendered heatmap peak selector selects the newly generated peak series

#### Scenario: Marker selection independent of signal visibility
- **WHEN** a peak series is hidden from the Signals plot but selected in the rendered heatmap peak selector
- **THEN** the rendered heatmap marker still uses that selected peak series

#### Scenario: Selected marker series unloaded
- **WHEN** the user unloads the peak series currently selected in the rendered heatmap peak selector
- **THEN** the selector falls back to `None` and the rendered heatmap stops using that series for peak markers
