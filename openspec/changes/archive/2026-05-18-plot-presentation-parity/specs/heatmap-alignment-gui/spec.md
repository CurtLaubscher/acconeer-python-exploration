## MODIFIED Requirements

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
