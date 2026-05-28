## ADDED Requirements

### Requirement: Extract stance phase from Leg2 `.mat`
The system SHALL extract the `robustFC` field from `DataRecordCommon.robustFC` in Leg2 `.mat` files as a boolean array indicating stance phase (true) and swing phase (false).

#### Scenario: Load Leg2 `.mat` with stance phase
- **WHEN** the user loads a Leg2 `.mat` file
- **THEN** the system successfully extracts `DataRecordCommon.robustFC` and stores it alongside the ultrasonic distance and reliable flag data

#### Scenario: Reject Leg2 `.mat` missing robustFC
- **WHEN** the user attempts to load a Leg2 `.mat` file that does not contain `DataRecordCommon.robustFC`
- **THEN** the system raises a clear error indicating the missing required field

### Requirement: Visualize stance phase on Signals plot
The system SHALL display stance phase as filled patch regions on the Signals plot, spanning from the plot's lower y-limit up to y=0, with colors and transparency matching the Leg2 ultrasonic signal line.

#### Scenario: Display stance phase patches
- **WHEN** a Leg2 ultrasonic signal is plotted
- **THEN** the system renders filled patch regions below the signal during stance phase intervals (robustFC == 1)

#### Scenario: Stance patches respect track offset
- **WHEN** the user adjusts the Leg2 track offset on the timeline
- **THEN** the stance phase patches move with the ultrasonic signal, maintaining temporal alignment

#### Scenario: Stance patches do not affect auto y-scaling
- **WHEN** the Signals plot auto-scales the y-axis
- **THEN** the computed y-range depends only on the plotted signal data (ultrasonic distance values), not the stance phase patches

### Requirement: Label stance phase in signal legend
The system SHALL add a "Stance phase" entry to the Signals plot legend when Leg2 ultrasonic signal is visible.

#### Scenario: Stance phase appears in legend
- **WHEN** the Leg2 ultrasonic signal is plotted
- **THEN** the signal plot legend includes a "Stance phase" entry with a colored rectangle indicator matching the patch color and transparency

#### Scenario: Legend hides with signal
- **WHEN** the Leg2 ultrasonic signal is hidden or unloaded
- **THEN** the "Stance phase" legend entry is removed from the signal plot legend

### Requirement: Stance patch color consistency
The system SHALL use the same base color as the Leg2 ultrasonic signal line with the same transparency (primary segment alpha) for stance phase patches.

#### Scenario: Patch color matches ultrasonic signal
- **WHEN** stance phase patches are rendered
- **THEN** the patch fill color and transparency visually coordinate with the Leg2 ultrasonic signal line color
