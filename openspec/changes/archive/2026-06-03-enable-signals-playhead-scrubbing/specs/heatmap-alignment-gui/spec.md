## MODIFIED Requirements

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
