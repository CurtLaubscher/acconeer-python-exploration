# closest-object-log-export Specification

## Purpose
TBD - created by archiving change add-closest-object-log-export. Update Purpose after archive.
## Requirements
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

### Requirement: Batch peak-distance export
The system SHALL allow the standalone peak-distance export command to process multiple H5 recordings in one invocation while writing one output file per resolved input recording.

#### Scenario: Export multiple explicit H5 files
- **WHEN** the user runs the peak-distance export script with multiple H5 file inputs
- **THEN** the system analyzes each resolved input using the same format, threshold, session, group, entry, subsweep, frame limit, and frame step options
- **AND** the system writes one peak-distance export file for each input

#### Scenario: Pool mixed input forms
- **WHEN** the user provides positional inputs containing a mix of explicit H5 files, glob patterns, and directories
- **THEN** the system resolves all inputs into one pool of H5 recordings to process
- **AND** the system plans and processes the resolved inputs using one shared batch workflow

#### Scenario: Expand glob input patterns
- **WHEN** the user provides an input argument containing glob pattern syntax that matches H5 recordings
- **THEN** the system resolves the matching H5 files and processes each resolved file as a batch input

#### Scenario: Discover files from directory input
- **WHEN** the user provides a directory input without recursive discovery enabled
- **THEN** the system processes `.h5` and `.hdf5` recordings directly inside that directory using case-insensitive extension matching
- **AND** the system does not process H5 recordings in nested child directories

#### Scenario: Discover files from recursive directory input
- **WHEN** the user provides a directory input with recursive discovery enabled
- **THEN** the system processes `.h5` and `.hdf5` recordings inside that directory and its nested child directories using case-insensitive extension matching

#### Scenario: Reject empty resolved input set
- **WHEN** the user provides inputs that resolve to no H5 recordings across the complete input set
- **THEN** the system exits with an error before processing any inputs
- **AND** the error explains that no H5 recordings were found

#### Scenario: Allow some empty directory inputs when other inputs resolve
- **WHEN** one directory input contains no H5 recordings but at least one other input resolves to an H5 recording
- **THEN** the system processes the resolved H5 recordings

#### Scenario: Reject duplicate resolved inputs
- **WHEN** the input arguments resolve the same H5 recording more than once using resolved absolute path comparison
- **THEN** the system exits with an error before processing any inputs
- **AND** the error identifies the duplicated source path

#### Scenario: Write batch outputs beside source files by default
- **WHEN** the user runs a batch export without `--output` or `--output-dir`
- **THEN** the system writes each output beside its source recording using `<input_stem>_peak_distances.json` for JSON exports or `<input_stem>_peak_distances.csv` for CSV exports

#### Scenario: Write batch outputs to an output directory
- **WHEN** the user runs a batch export with `--output-dir`
- **THEN** the system writes each output into that directory using `<input_stem>_peak_distances.json` for JSON exports or `<input_stem>_peak_distances.csv` for CSV exports

#### Scenario: Reject output directory path that is a file
- **WHEN** the user provides `--output-dir` and that path exists as a file
- **THEN** the system exits with an error before processing any inputs
- **AND** the error identifies the invalid output directory path

#### Scenario: Reject single output path for multiple inputs
- **WHEN** the user provides `--output` and the input arguments resolve to more than one H5 recording
- **THEN** the system exits with an error before processing any inputs
- **AND** the error explains that `--output` is only valid for a single resolved input

#### Scenario: Reject batch output path collisions
- **WHEN** two or more resolved batch inputs would write to the same output path
- **THEN** the system exits with an error before processing any inputs
- **AND** the error identifies the conflicting output path and source inputs

#### Scenario: Reject existing output files
- **WHEN** any planned output path already exists
- **THEN** the system exits with an error before processing any inputs
- **AND** the error identifies the existing output path

#### Scenario: Use deterministic processing order
- **WHEN** the system has resolved the input pool
- **THEN** the system plans and processes inputs in deterministic resolved-path order

#### Scenario: Report batch completion summary
- **WHEN** the system completes a batch export attempt
- **THEN** the system reports how many inputs succeeded and how many failed
- **AND** the process exits with a nonzero status if any input failed

#### Scenario: Preserve single-file output behavior
- **WHEN** the user runs the peak-distance export script with exactly one resolved H5 input
- **THEN** the system preserves the existing default output naming and explicit `--output` behavior

