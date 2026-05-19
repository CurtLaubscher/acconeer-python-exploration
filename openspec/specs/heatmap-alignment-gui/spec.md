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
The system SHALL represent camera video time and H5 heatmap time on a shared timeline measured in physical seconds.

#### Scenario: Scrub shared timeline
- **WHEN** the user moves the current-time marker on the timeline
- **THEN** the system updates the camera video frame, rectified viewport frame, and rendered heatmap frame for the corresponding aligned times

#### Scenario: Adjust temporal offset
- **WHEN** the user drags a track or uses nudge controls to change alignment
- **THEN** the system updates the stored camera-to-H5 offset in seconds and refreshes the displayed previews

#### Scenario: View track placement
- **WHEN** both the camera video and H5 heatmap are loaded
- **THEN** the system displays compact horizontal duration bars on a shared seconds axis, with the H5 heatmap as the fixed reference track and the camera video as the draggable alignment track

#### Scenario: Drag camera track
- **WHEN** the user drags the camera duration bar horizontally
- **THEN** the system updates the stored camera-to-H5 offset and refreshes the displayed previews while keeping the H5 bar fixed

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
- **THEN** the system restores the source selections, viewport geometry, render settings, temporal offset, preview state, and optional imported distance-measurement datasource metadata described by the session file

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

