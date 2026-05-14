## ADDED Requirements

### Requirement: Standalone alignment workbench
The system SHALL provide a standalone PySide6 user tool for aligning one camera video track with one H5-rendered Sparse IQ heatmap track.

#### Scenario: Launch alignment workbench
- **WHEN** the user launches the alignment workbench
- **THEN** the system displays controls for loading a camera video, loading an H5 radar recording, viewing both sources, adjusting alignment, and saving or loading an alignment artifact

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
The system SHALL rectify the selected camera viewport to the same pixel size and aspect ratio as the rendered heatmap preview.

#### Scenario: Display comparable previews
- **WHEN** both the camera video and H5 recording are loaded and a viewport is defined
- **THEN** the system displays the rectified camera viewport and rendered heatmap at directly comparable dimensions

### Requirement: Shared physical timeline
The system SHALL represent camera video time and H5 heatmap time on a shared timeline measured in physical seconds.

#### Scenario: Scrub shared timeline
- **WHEN** the user moves the current-time marker on the timeline
- **THEN** the system updates the camera video frame, rectified viewport frame, and rendered heatmap frame for the corresponding aligned times

#### Scenario: Adjust temporal offset
- **WHEN** the user drags a track or uses nudge controls to change alignment
- **THEN** the system updates the stored camera-to-H5 offset in seconds and refreshes the displayed previews

### Requirement: Manual playback preview
The system SHALL provide basic playback controls for previewing the aligned camera video and rendered heatmap together without requiring MVP audio playback.

#### Scenario: Play aligned tracks
- **WHEN** the user starts playback
- **THEN** the system advances the shared current time and updates the camera, rectified viewport, and rendered heatmap previews according to the current offset

### Requirement: Xcorr diagnostic display
The system SHALL display a cross-correlation diagnostic between the rectified camera viewport and rendered heatmap without automatically changing the alignment in the MVP.

#### Scenario: View xcorr plot
- **WHEN** both tracks are loaded and the user views the xcorr panel
- **THEN** the system displays a correlation score plot over a local lag range around the current temporal offset

#### Scenario: Preserve manual alignment authority
- **WHEN** the xcorr diagnostic has a peak at a different lag than the current offset
- **THEN** the system does not change the current offset unless the user manually adjusts it

### Requirement: Alignment artifact persistence
The system SHALL save and load JSON alignment artifacts containing the state needed to reproduce a manual alignment session.

#### Scenario: Save alignment artifact
- **WHEN** the user saves an alignment artifact
- **THEN** the system writes source paths, selected H5 session/group/entry/subsweep, render color limits, camera viewport corners, viewport output dimensions, temporal offset in seconds, and preprocessing settings to JSON

#### Scenario: Load alignment artifact
- **WHEN** the user loads a saved alignment artifact
- **THEN** the system restores the source selections, viewport geometry, render settings, temporal offset, and preview state described by the artifact

### Requirement: Extensible track model
The system SHALL structure alignment state so the MVP's camera video and H5 heatmap are represented as tracks on a shared timeline.

#### Scenario: Persist MVP tracks
- **WHEN** the system saves an alignment artifact
- **THEN** the artifact represents the camera video and H5 heatmap as distinct tracks with their source configuration and timing state
