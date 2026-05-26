## Why

Peak-distance extraction currently handles one H5 recording per command invocation. Users who collect many recordings need a repeatable batch workflow that produces the same per-record JSON or CSV outputs without hand-writing shell loops or managing inconsistent output names.

## What Changes

- Extend the standalone `peak-distances` user-tool command to accept multiple inputs in one invocation.
- Support file inputs, glob-style input patterns, and directory inputs for discovering H5 recordings.
- Keep the existing one-source-file-to-one-output-file model for both JSON and CSV exports.
- Add batch output naming rules that preserve the current `<input_stem>_peak_distances.<format>` default.
- Add `--output-dir` for writing batch outputs to a selected directory.
- Reject ambiguous single-output usage, such as `--output` with multiple resolved inputs.
- Detect duplicate inputs, existing outputs, and batch output path collisions before processing, and report the conflicting paths.
- Keep batch selection options shared across all resolved inputs.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `closest-object-log-export`: Add batch input resolution, per-input output naming, directory output, collision handling, and batch summary behavior to the standalone peak-distance export workflow.

## Impact

- `user_tools/export_sparse_iq_peak_distances.py`: CLI argument parsing, input expansion, output path planning, batch execution, and reporting.
- `user_tools/sparse_iq_peak_distance_core.py`: No algorithm change expected; may gain small reusable helpers only if that keeps CLI code focused.
- `tests/user_tools/test_sparse_iq_peak_distance_core.py` and/or CLI-focused tests: coverage for batch planning, collision handling, and unchanged single-file behavior.
- `pyproject.toml`: No new runtime dependency expected; existing Hatch script remains the launch path.
