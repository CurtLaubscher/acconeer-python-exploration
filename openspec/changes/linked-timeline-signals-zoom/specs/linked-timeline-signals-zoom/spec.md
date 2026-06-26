## ADDED Requirements

### Requirement: Shared x-range zoom via scroll wheel
The timeline and Signals plot SHALL share a single x-range; scroll-wheel zoom on either widget SHALL update the shared range and both views SHALL reflect the change immediately. Zoom SHALL be centered on the cursor's time position.

#### Scenario: Scroll wheel zoom on timeline
- **WHEN** the user scrolls the mouse wheel over the timeline widget
- **THEN** the visible time range narrows (zoom in) or widens (zoom out) centered on the time at the cursor position, and the Signals plot x-range updates to match

#### Scenario: Scroll wheel zoom on Signals plot
- **WHEN** the user scrolls the mouse wheel over the Signals plot
- **THEN** the visible time range narrows or widens centered on the cursor's time position, and the timeline x-range updates to match

### Requirement: Shared x-range pan via middle-mouse drag
Middle-mouse drag on either the timeline or the Signals plot SHALL pan the shared x-range. Left-mouse drag on the Signals plot SHALL NOT change the time range and SHALL NOT scrub the playhead.

#### Scenario: Middle-drag pan on timeline
- **WHEN** the user presses the middle mouse button and drags horizontally over the timeline
- **THEN** the visible time range shifts in the direction of the drag and the Signals plot follows

#### Scenario: Middle-drag pan on Signals plot
- **WHEN** the user presses the middle mouse button and drags horizontally over the Signals plot
- **THEN** the visible time range shifts in the direction of the drag and the timeline follows

#### Scenario: Left-drag on Signals plot has no effect on range
- **WHEN** the user presses the left mouse button and drags over the Signals plot background
- **THEN** the visible time range does NOT change

### Requirement: Right-click-drag zoom on timeline
Right-click drag on the timeline SHALL zoom the shared x-range using the same gesture behavior as pyqtgraph's ViewBox right-drag zoom.

#### Scenario: Right-drag zoom on timeline
- **WHEN** the user right-click drags on the timeline widget
- **THEN** the visible time range zooms proportionally to the drag distance and the Signals plot follows

### Requirement: Zoom to Fit resets the time range
A "Zoom to Fit" action on the time axis SHALL reset the shared x-range to show the full recording span with padding. It SHALL be accessible from the timeline right-click menu and from the Signals plot X Axis submenu.

#### Scenario: Zoom to Fit from timeline context menu
- **WHEN** the user right-clicks the timeline and selects "Zoom to Fit"
- **THEN** the shared x-range resets to the full recording span and both the timeline and Signals plot show everything

#### Scenario: Zoom to Fit from Signals plot X Axis menu
- **WHEN** the user right-clicks the Signals plot and selects "Zoom to Fit" from the X Axis submenu
- **THEN** the shared x-range resets to the full recording span and both views update

### Requirement: Zoom to Fit for y-axis
A "Zoom to Fit" action in the Signals plot Y Axis submenu SHALL fit the y-axis to the visible signal data in the current x-window.

#### Scenario: Zoom to Fit from Signals plot Y Axis menu
- **WHEN** the user right-clicks the Signals plot and selects "Zoom to Fit" from the Y Axis submenu
- **THEN** the y-axis limits fit the visible signal data without changing the x-range

### Requirement: Signals plot x-axis menu shows range inputs and Zoom to Fit only
The Signals plot x-axis right-click submenu SHALL show manual range min/max input fields and a "Zoom to Fit" action. The Auto/Manual toggle SHALL be removed. Entering values in the range inputs SHALL update the shared x-range.

#### Scenario: Range inputs update shared range
- **WHEN** the user types a value into the x-axis min or max input in the Signals plot menu
- **THEN** the shared x-range updates to the entered limits and the timeline reflects the change

### Requirement: X-distorting transforms and Mouse Mode removed from Signals plot menu
Log X, Power Spectrum (FFT), Y vs. Y', dy/dx, Phase Map, Invert X, and the Mouse Mode toggle SHALL be permanently removed from the Signals plot right-click menu. The generic "View All" action SHALL also be removed.

#### Scenario: X-distorting transforms not available
- **WHEN** the user opens the Signals plot right-click menu
- **THEN** Log X, FFT, Y vs. Y', dy/dx, Phase Map, Invert X, Mouse Mode, and View All are not present

### Requirement: No auto-fit on track-bar drag release
Releasing a dragged track bar (camera, Leg2) SHALL NOT reset the x-range to show the full recording span. The view SHALL remain at the zoom level the user had before and during the drag.

#### Scenario: Camera track drag release preserves zoom
- **WHEN** the user drags the camera track bar and releases the mouse
- **THEN** the visible time range remains unchanged from before the drag

### Requirement: Clickable off-screen playhead indicator
When the playhead is outside the current visible x-range, the timeline SHALL display a small directional triangle at the corresponding edge. Clicking the triangle SHALL pan the shared x-range so the playhead is visible at approximately 20% from the near edge, preserving the current zoom level.

#### Scenario: Playhead off-screen to the right
- **WHEN** the playhead time is greater than the visible range end
- **THEN** a small triangle pointing right is drawn at the right edge of the timeline plot area

#### Scenario: Playhead off-screen to the left
- **WHEN** the playhead time is less than the visible range start
- **THEN** a small triangle pointing left is drawn at the left edge of the timeline plot area

#### Scenario: Clicking indicator brings playhead into view
- **WHEN** the user clicks the off-screen playhead indicator triangle
- **THEN** the shared x-range pans so the playhead is visible at approximately 20% from the near edge and the zoom level is unchanged

#### Scenario: No indicator when playhead is on-screen
- **WHEN** the playhead time is within the current visible range
- **THEN** no directional triangle indicator is shown at either edge
