## MODIFIED Requirements

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

#### Scenario: Range mode context menu
- **WHEN** the user opens the Signals plot context menu
- **THEN** the X Axis submenu shows range min/max inputs and "Zoom to Fit"; no Auto/Manual toggle is present

#### Scenario: Disable x transformations
- **WHEN** the user opens the Signals plot right-click menu
- **THEN** Log X, FFT, Y vs. Y', dy/dx, Phase Map, Invert X, Mouse Mode, and the generic View All action are not present

### Requirement: Signal plot x-axis session fields ignored
The system SHALL NOT save the Signals plot x-axis range mode or manual x-range to the session file. When loading a session that contains these fields from a previous version, the system SHALL silently ignore them.

#### Scenario: Old session with x range mode loads cleanly
- **WHEN** the user loads a session file that contains `x_range_mode` or `manual_x_range` fields for the Signals plot
- **THEN** the session loads without error and those fields are ignored

#### Scenario: Saving session omits x range fields
- **WHEN** the user saves a session
- **THEN** the session file does not contain Signals plot x-axis range mode or manual x-range fields
