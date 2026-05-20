## ADDED Requirements

### Requirement: Leg2 MAT ultrasonic datasource
The system SHALL allow the heatmap alignment GUI to import a Leg2 `.mat` log as an optional ultrasonic datasource alongside the camera video, H5 heatmap recording, and imported H5 peak-distance datasource.

#### Scenario: Import Leg2 MAT file
- **WHEN** the user imports a Leg2 `.mat` file with the expected ultrasonic fields
- **THEN** the system loads the Leg2 ultrasonic datasource without replacing the camera video, H5 heatmap track, or imported H5 peak-distance datasource

#### Scenario: Load Leg2 MAT on startup
- **WHEN** the user launches the heatmap alignment GUI with a Leg2 `.mat` startup argument
- **THEN** the system loads that file as the optional Leg2 ultrasonic datasource during startup

#### Scenario: Load session and Leg2 MAT on startup
- **WHEN** the user launches the heatmap alignment GUI with both a saved alignment session and a Leg2 `.mat` startup argument
- **THEN** the explicitly provided Leg2 `.mat` file replaces any Leg2 ultrasonic datasource stored in the loaded session after validation

#### Scenario: Unload Leg2 MAT datasource
- **WHEN** the user clears or unloads the Leg2 ultrasonic datasource
- **THEN** the system removes the Leg2 ultrasonic data and timeline track from the current session without changing the camera video, H5 heatmap track, or imported H5 peak-distance datasource

#### Scenario: Load session without Leg2 MAT datasource
- **WHEN** the user loads an alignment session that does not contain a Leg2 ultrasonic datasource
- **THEN** the system treats the datasource as absent and loads the existing camera, heatmap, peak-distance, and signal-plot state normally

### Requirement: Leg2 MAT ultrasonic extraction
The system SHALL extract the Leg2 ultrasonic datasource from hard-coded fields in the expected Leg2 `.mat` export structure.

#### Scenario: Extract required Leg2 fields
- **WHEN** a Leg2 `.mat` file is loaded
- **THEN** the system reads required fields from `DataRecordCommon.timeOut`, `Ultrasonic.Distance`, `DataRecordCommon.ultrasonic_filtered`, and `DataRecordCommon.robustFC`

#### Scenario: Normalize Leg2 elapsed time
- **WHEN** Leg2 ultrasonic time values are loaded successfully
- **THEN** the system subtracts the first retained time value so the Leg2 ultrasonic source starts at elapsed time zero

#### Scenario: Ignore trailing zero-time sample
- **WHEN** the Leg2 time array contains a trailing `0` value after valid nonzero time samples
- **THEN** the system excludes the trailing erroneous sample and corresponding ultrasonic values from the loaded datasource

#### Scenario: Convert ultrasonic distance units
- **WHEN** Leg2 ultrasonic distance values are loaded successfully
- **THEN** the system converts them from millimeters to meters before plotting or persisting loaded metadata

#### Scenario: Extract robust segmentation
- **WHEN** the loaded Leg2 `.mat` file is accepted
- **THEN** the system uses it as a per-sample robust/non-robust display segmentation mask for the selected ultrasonic signal

### Requirement: Leg2 MAT load validation
The system SHALL reject invalid Leg2 `.mat` loads with clear user-facing errors and SHALL leave any existing loaded Leg2 datasource unchanged when validation fails.

#### Scenario: Reject missing required fields
- **WHEN** the user imports a Leg2 `.mat` file missing any required field
- **THEN** the system rejects the import and reports which required field could not be loaded

#### Scenario: Reject incompatible array lengths
- **WHEN** the required Leg2 time, raw distance, filtered distance, and robust segmentation arrays have incompatible lengths after trailing zero-time cleanup
- **THEN** the system rejects the import and reports the array length incompatibility

#### Scenario: Reject invalid time axis
- **WHEN** the Leg2 time array is non-finite, empty after cleanup, or not usable as an increasing physical time axis
- **THEN** the system rejects the import and reports that the Leg2 time axis is invalid

#### Scenario: Reject invalid distance values
- **WHEN** a required Leg2 ultrasonic distance array cannot be interpreted as numeric distance samples
- **THEN** the system rejects the import and reports that the ultrasonic distance data is invalid

#### Scenario: Keep prior Leg2 datasource after failed import
- **WHEN** a Leg2 ultrasonic datasource is already loaded and a later Leg2 `.mat` import fails validation
- **THEN** the system keeps the previously loaded Leg2 datasource and its session settings unchanged

### Requirement: Leg2 MAT timeline track
The system SHALL display the loaded Leg2 ultrasonic datasource as its own colored track on the shared physical timeline.

#### Scenario: Display Leg2 timeline track
- **WHEN** a Leg2 ultrasonic datasource is loaded
- **THEN** the Timeline area displays a Leg2 `.mat` duration bar on a distinct track row using the Leg2 datasource color

#### Scenario: Drag Leg2 timeline track
- **WHEN** the user drags the Leg2 `.mat` duration bar horizontally
- **THEN** the system allows the Leg2 row to move partially or fully outside the visible timeline range, updates the stored Leg2-to-H5 offset in seconds when the drag is released, and refreshes dependent timeline and Signals views

#### Scenario: Preserve camera offset while dragging Leg2
- **WHEN** the user drags the Leg2 `.mat` duration bar
- **THEN** the system does not change the stored camera-to-H5 offset

#### Scenario: Preserve Leg2 offset while dragging camera
- **WHEN** the user drags the camera duration bar
- **THEN** the system does not change the stored Leg2-to-H5 offset

#### Scenario: Use source offset sign convention
- **WHEN** the Leg2 track has offset `offset_s`
- **THEN** Leg2 source time maps to shared H5 time using the same sign convention as the camera track, with the Leg2 timeline row start displayed at `-offset_s`

#### Scenario: Show Leg2 offset value
- **WHEN** a Leg2 ultrasonic datasource is loaded
- **THEN** the system displays the current Leg2-to-H5 offset or aligned track start value in the interface so the numerical alignment is visible

### Requirement: Leg2 ultrasonic signal display
The system SHALL display one selected Leg2 ultrasonic signal at a time in the existing Signals area using the Leg2 timeline color family.

#### Scenario: Plot selected raw ultrasonic signal
- **WHEN** the Leg2 ultrasonic datasource is loaded and raw ultrasonic display is selected
- **THEN** the Signals area plots raw ultrasonic distance over aligned shared timeline time in meters

#### Scenario: Plot selected filtered ultrasonic signal
- **WHEN** the Leg2 ultrasonic datasource is loaded and filtered ultrasonic display is selected
- **THEN** the Signals area plots filtered ultrasonic distance over aligned shared timeline time in meters

#### Scenario: Toggle raw and filtered ultrasonic display
- **WHEN** a Leg2 ultrasonic datasource is loaded
- **THEN** the system lets the user choose whether the Signals area displays the raw or filtered ultrasonic signal while keeping only one Leg2 ultrasonic signal visible at a time

#### Scenario: Use Leg2 track color for ultrasonic signal
- **WHEN** the Signals area plots a Leg2 ultrasonic signal
- **THEN** the plotted signal uses a readable plot color derived from the same color family as the Leg2 timeline track

#### Scenario: Segment ultrasonic signal by robust flag
- **WHEN** the selected Leg2 ultrasonic signal is visible
- **THEN** the Signals area renders robust samples as a slightly transparent primary signal and non-robust samples as a lower-alpha signal

#### Scenario: Preserve ultrasonic missing-value gaps
- **WHEN** a selected Leg2 ultrasonic sample has no plottable distance value
- **THEN** the Signals area leaves an actual gap rather than connecting a line through that sample

#### Scenario: Align Leg2 signal with timeline geometry
- **WHEN** the Signals plot x-axis is in Timeline mode and a Leg2 ultrasonic signal is visible
- **THEN** the Leg2 ultrasonic signal, Leg2 timeline bar, H5 peak-distance signal, and current-time indicators map the same shared time values to the same horizontal screen positions

#### Scenario: Show Leg2 signal legend entry
- **WHEN** the Signals area contains a visible Leg2 ultrasonic signal
- **THEN** the compact legend identifies whether the plotted Leg2 signal is raw or filtered ultrasonic distance

### Requirement: Leg2 MAT session persistence
The system SHALL persist optional Leg2 `.mat` datasource state in alignment session files.

#### Scenario: Save Leg2 MAT session state
- **WHEN** the user saves an alignment session with a Leg2 ultrasonic datasource loaded
- **THEN** the session file includes the Leg2 `.mat` path, Leg2-to-H5 offset, datasource visibility, and selected ultrasonic signal kind

#### Scenario: Restore Leg2 MAT session state
- **WHEN** the user loads an alignment session containing Leg2 ultrasonic datasource state
- **THEN** the system reloads the stored Leg2 `.mat` file and restores the Leg2-to-H5 offset, datasource visibility, selected signal kind, timeline track, and Signals plot display

#### Scenario: Warn when stored Leg2 MAT cannot be reloaded
- **WHEN** the user loads an alignment session whose stored Leg2 `.mat` file is missing or invalid
- **THEN** the system reports the Leg2 `.mat` reload failure while keeping the rest of the alignment session usable

#### Scenario: Preserve older sessions without Leg2 fields
- **WHEN** the user loads an older alignment session that does not contain Leg2 ultrasonic datasource state
- **THEN** the system defaults to no loaded Leg2 ultrasonic datasource without requiring session migration

### Requirement: Leg2 MAT export isolation
The system SHALL keep synced video export behavior unchanged by the Leg2 ultrasonic datasource.

#### Scenario: Export with visible Leg2 ultrasonic signal
- **WHEN** a Leg2 ultrasonic datasource is loaded or visible and the user exports a synced video
- **THEN** the exported video does not include the Leg2 ultrasonic signal and uses the existing camera plus H5 heatmap overlay export behavior

#### Scenario: Preserve export duration
- **WHEN** a Leg2 ultrasonic datasource extends before or after the H5 recording in aligned shared time
- **THEN** synced video export duration remains based on the H5 recording duration
