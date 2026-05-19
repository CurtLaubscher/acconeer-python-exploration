## 1. Exporter Core

- [x] 1.1 Add a reusable peak-distance export config and result-row data model outside Qt GUI code.
- [x] 1.2 Implement zero-velocity-bin selection from the physical velocity axis.
- [x] 1.3 Implement frame-level strongest-peak extraction from the zero-velocity distance slice with threshold gating and a default threshold of `650`.
- [x] 1.4 Implement recording-level analysis over selected H5 frames with elapsed timestamps, optional absolute timestamps, detection status, and source-selection metadata.
- [x] 1.5 Add focused unit tests for zero-velocity-bin selection, strongest-peak selection, threshold behavior, no-detection frames, and timestamp generation using synthetic Sparse IQ-like data.

## 2. Standalone JSON/CSV Export

- [x] 2.1 Add a standalone `user_tools` script for H5 peak-distance export.
- [x] 2.2 Add command-line options for input/output paths, H5 selection indices, subsweep selection, threshold defaulting to `650`, `--format json|csv` defaulting to `json`, and optional frame limiting or stride if useful.
- [x] 2.3 Add a repo-managed Hatch app script named `peak-distances` in `pyproject.toml`.
- [x] 2.4 Implement canonical JSON serialization with `format`, `version`, `metadata`, and `measurements` fields.
- [x] 2.5 Implement reduced CSV serialization with stable columns: `frame_index`, `source_tick`, `time_s`, `absolute_time`, `status`, `peak_distance_m`, `candidate_peak_distance_m`, and `peak_strength`.
- [x] 2.6 Add or update export tests that verify JSON metadata, JSON measurements, reduced CSV columns, no-detection rows, `candidate_peak_distance_m`, and failure behavior for invalid output paths.

## 3. Heatmap Alignment Datasource Import

- [x] 3.1 Update the alignment session model to treat the imported distance-measurement datasource path as a canonical JSON file while preserving defaults for older sessions.
- [x] 3.2 Replace CSV datasource import parsing with JSON import parsing for generated peak-distance files, including validation of required JSON fields and source-selection metadata.
- [x] 3.3 Update GUI entry points and file filters to import canonical peak-distance JSON files and clear the optional distance-measurement datasource.
- [x] 3.4 Validate imported JSON measurement count and elapsed real-time range against the loaded H5 heatmap track, hard-failing frame-count mismatches.
- [x] 3.5 Preserve imported JSON datasource metadata when saving and loading alignment sessions.
- [x] 3.6 Add a show/hide control for the imported peak-distance datasource.
- [x] 3.7 Render the current frame's imported JSON peak marker on or alongside the heatmap view and handle no-detection frames clearly.
- [x] 3.8 Render visible imported peak markers into synced video heatmap overlays.
- [x] 3.9 Add a heatmap alignment GUI startup argument, for example `--peaks`, that loads a canonical peak-distance JSON datasource using the same validation path as interactive import.
- [x] 3.10 If both a session and `--peaks` are provided, load the session first and let the explicit `--peaks` datasource replace any datasource stored in the session after validation.
- [x] 3.11 Improve invalid peak-distance JSON import errors so the primary message is user-oriented and technical parser details are secondary.

## 4. Future GUI Calculation Readiness

- [x] 4.1 Keep the exporter core callable independently from both the CLI script and a future heatmap app "Calculate Peaks" button.
- [x] 4.2 Avoid adding threshold-preview UI in this change unless repeated CLI export iteration proves insufficient.

## 5. Verification

- [x] 5.1 Run the focused tests through the repo-managed Hatch test environment.
- [x] 5.2 Run Ruff formatting/checks through the repo-defined Hatch scripts for touched files.
- [x] 5.3 Run the repo-defined type checker for touched Python files; use basedpyright if added to repo tooling, otherwise use the existing Hatch mypy environment.
- [x] 5.4 Smoke-test the standalone exporter with default JSON output and optional reduced CSV output.
- [x] 5.5 Smoke-test importing a generated JSON file into the heatmap alignment GUI and save/reloading an alignment session.
- [x] 5.6 Smoke-test launching the heatmap alignment GUI with H5 and peak-distance JSON startup arguments.
