## ADDED Requirements

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
