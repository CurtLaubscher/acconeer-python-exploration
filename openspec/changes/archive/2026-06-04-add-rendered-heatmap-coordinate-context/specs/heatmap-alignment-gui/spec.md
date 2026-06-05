## ADDED Requirements

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
