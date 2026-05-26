## ADDED Requirements

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
