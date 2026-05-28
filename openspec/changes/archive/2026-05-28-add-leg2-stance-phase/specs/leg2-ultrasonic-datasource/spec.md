## MODIFIED Requirements

### Requirement: Import Leg2 ultrasonic signal from `.mat`
The system SHALL import ultrasonic distance data and metadata from a Leg2 `.mat` file, including raw and filtered distance signals, per-sample reliability flags, and per-sample stance phase indicator.

#### Scenario: Load Leg2 `.mat` with ultrasonic signals
- **WHEN** the user loads a Leg2 `.mat` file
- **THEN** the system extracts `DataRecordCommon.timeOut`, `Ultrasonic.Distance`, `DataRecordCommon.ultrasonic_filtered`, `DataRecordCommon.ReliableFlag`, and `DataRecordCommon.robustFC`, and displays the imported signal on the Signals plot

#### Scenario: Validate Leg2 `.mat` time axis consistency
- **WHEN** the user loads a Leg2 `.mat` file
- **THEN** the system verifies that all data arrays (distance, filtered distance, reliable flag, and stance phase) have the same length and that the time axis is strictly increasing

#### Scenario: Reject Leg2 `.mat` with incompatible data
- **WHEN** the user attempts to load a Leg2 `.mat` file with mismatched array lengths or invalid time axis
- **THEN** the system raises a clear error describing which fields are incompatible

#### Scenario: Reject Leg2 `.mat` missing required fields
- **WHEN** the user attempts to load a Leg2 `.mat` file missing required fields (time axis, distance, reliable flag, or stance phase)
- **THEN** the system raises a clear error indicating which required fields are missing

### Requirement: Plot Leg2 ultrasonic signal with reliability segmentation
The system SHALL plot the Leg2 ultrasonic distance on the Signals plot, segmenting the curve by the `ReliableFlag` to show high-confidence and lower-confidence portions at different opacity levels.

#### Scenario: Display segmented ultrasonic signal
- **WHEN** a Leg2 ultrasonic signal is plotted
- **THEN** the system shows the distance curve with primary opacity where `ReliableFlag` is true and faded opacity where false

#### Scenario: Update plot when signal kind changes
- **WHEN** the user switches between raw and filtered ultrasonic signals
- **THEN** the system updates the plotted curve while maintaining the reliability-based segmentation

### Requirement: Align Leg2 signal with timeline
The system SHALL allow the user to adjust the Leg2 track offset on the shared timeline so ultrasonic signal features can be manually aligned with H5 heatmap and camera video.

#### Scenario: Drag Leg2 track offset
- **WHEN** the user drags the Leg2 track on the timeline
- **THEN** the system updates the Leg2 time offset and the Signals plot immediately reflects the new alignment

#### Scenario: Apply signal offset to stance phase
- **WHEN** the Leg2 track offset changes
- **THEN** both the ultrasonic signal and stance phase patches move together on the Signals plot, maintaining temporal coherence
