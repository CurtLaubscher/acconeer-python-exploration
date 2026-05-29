## MODIFIED Requirements

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
