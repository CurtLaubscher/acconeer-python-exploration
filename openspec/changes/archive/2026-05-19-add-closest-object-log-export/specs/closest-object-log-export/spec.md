## ADDED Requirements

### Requirement: Standalone peak-distance export
The system SHALL provide a standalone user-tool script that reads an Acconeer H5 Sparse IQ recording and exports derived peak-distance measurements.

#### Scenario: Export H5 log to JSON by default
- **WHEN** the user runs the peak-distance export script with an input H5 recording and no explicit format
- **THEN** the system writes one JSON file containing source metadata and one measurement object for each selected source frame

#### Scenario: Select recording entry
- **WHEN** the user provides session, group, entry, or subsweep selection options
- **THEN** the system analyzes the selected H5 recording entry using the same index resolution behavior as the Sparse IQ heatmap exporter

#### Scenario: Select export format
- **WHEN** the user passes `--format json` or `--format csv`
- **THEN** the system writes the selected output format and rejects unsupported format values

#### Scenario: Use repo-managed runtime
- **WHEN** the user launches the peak-distance export script through the repo-defined Hatch app environment or script
- **THEN** the system runs with the dependencies declared by the repository tooling

### Requirement: Zero-velocity peak algorithm
The system SHALL implement the initial measurement algorithm as a thresholded strongest-peak search in the distance/velocity-map slice nearest zero velocity.

#### Scenario: Measure peak distance
- **WHEN** a selected frame has a zero-velocity-slice peak whose strength is greater than the configured threshold
- **THEN** the system reports the distance-bin center of the strongest peak as the frame's peak distance

#### Scenario: Choose zero-velocity slice
- **WHEN** the distance/velocity map has no velocity bin exactly equal to `0 m/s`
- **THEN** the system uses the velocity bin whose physical velocity is closest to `0 m/s`

#### Scenario: Ignore non-zero velocity bins
- **WHEN** a stronger return exists outside the selected zero-velocity slice
- **THEN** the initial algorithm ignores that return when choosing the exported peak distance

#### Scenario: Apply threshold
- **WHEN** the strongest zero-velocity-slice peak is not greater than the configured threshold
- **THEN** the system records the frame as having no detection

#### Scenario: Configure threshold
- **WHEN** the user supplies a threshold value on the command line
- **THEN** the system uses that threshold for every analyzed frame and records the threshold in the exported data

#### Scenario: Use default threshold
- **WHEN** the user runs the peak-distance export script without supplying a threshold
- **THEN** the system uses `650` as the threshold and records that threshold in the exported data

### Requirement: Peak-distance JSON format
The system SHALL write peak-distance measurements in a stable JSON format that can be validated and imported by other user tools.

#### Scenario: Include metadata object
- **WHEN** the system exports peak-distance measurements as JSON
- **THEN** the JSON includes `format`, `version`, and `metadata` fields with source path, source name, session index, group index, entry index, sensor id, subsweep index, source frame count, source duration, tick rate, threshold, zero-velocity bin index, and zero-velocity velocity value

#### Scenario: Include measurement objects
- **WHEN** the system exports peak-distance measurements as JSON
- **THEN** the JSON includes a `measurements` array whose objects include `frame_index`, `source_tick`, `time_s`, `absolute_time`, `status`, `peak_distance_m`, `candidate_peak_distance_m`, and `peak_strength`

#### Scenario: Export absolute timestamps when available
- **WHEN** the loaded recording has a parseable record timestamp
- **THEN** each exported JSON measurement includes an `absolute_time` value for the analyzed frame

#### Scenario: Leave absolute timestamp empty when unavailable
- **WHEN** the loaded recording does not have a parseable record timestamp
- **THEN** each exported JSON measurement uses `null` for `absolute_time`

#### Scenario: Preserve no-detection frames
- **WHEN** the thresholded algorithm produces no detection for a frame
- **THEN** the exported JSON preserves that frame with `status` set to `no_detection`, `peak_distance_m` set to `null`, and `candidate_peak_distance_m` set to the strongest zero-velocity-slice peak distance

#### Scenario: Preserve detected candidate distance
- **WHEN** the thresholded algorithm produces a detection for a frame
- **THEN** the exported JSON sets both `peak_distance_m` and `candidate_peak_distance_m` to the detected peak distance

#### Scenario: Use portable JSON keys
- **WHEN** the system writes peak-distance JSON keys
- **THEN** every key uses only Latin letters, digits, and underscores, and no key starts with a digit

### Requirement: Reduced peak-distance CSV format
The system SHALL support a reduced CSV export format for manual inspection and spreadsheet workflows.

#### Scenario: Export reduced CSV
- **WHEN** the user runs the peak-distance export script with `--format csv`
- **THEN** the system writes a CSV containing only row-varying measurement columns and omits metadata that is guaranteed to be identical for every row

#### Scenario: Include reduced CSV columns
- **WHEN** the system exports reduced CSV measurements
- **THEN** the CSV includes `frame_index`, `source_tick`, `time_s`, `absolute_time`, `status`, `peak_distance_m`, `candidate_peak_distance_m`, and `peak_strength` columns

#### Scenario: Preserve no-detection rows in reduced CSV
- **WHEN** the thresholded algorithm produces no detection for a frame and the user exports reduced CSV
- **THEN** the CSV row preserves that frame with `status` set to `no_detection`, an empty `peak_distance_m`, the strongest below-threshold distance in `candidate_peak_distance_m`, and the strongest peak strength in `peak_strength`

#### Scenario: Use portable CSV column names
- **WHEN** the system writes reduced CSV columns
- **THEN** every column name uses only Latin letters, digits, and underscores, and no column name starts with a digit

#### Scenario: Report write failures
- **WHEN** the system cannot write the selected output file
- **THEN** the script exits with an error and does not report the export as successful
