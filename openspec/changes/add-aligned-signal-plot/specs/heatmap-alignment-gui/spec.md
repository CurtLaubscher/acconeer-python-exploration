## ADDED Requirements

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
