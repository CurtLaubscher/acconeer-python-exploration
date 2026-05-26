## 1. Input And Output Planning

- [x] 1.1 Refactor `export_sparse_iq_peak_distances.py` so the parser accepts one or more input arguments while preserving single-input behavior.
- [x] 1.2 Implement input resolution for explicit files, glob patterns, and directory inputs matching `.h5` and `.hdf5` files.
- [x] 1.3 Add `--recursive` handling for directory input discovery.
- [x] 1.4 Add `--output-dir` handling and keep `--output` valid only for exactly one resolved input.
- [x] 1.5 Implement output path planning with `<input_stem>_peak_distances.<format>` names beside sources by default or flat under `--output-dir`.
- [x] 1.6 Normalize resolved inputs to absolute paths, sort them deterministically, and reject duplicate source files before processing.
- [x] 1.7 Detect empty resolved input sets, output path collisions, and existing output files before processing.
- [x] 1.8 Reject an `--output-dir` path that exists as a file before processing.

## 2. Batch Execution

- [x] 2.1 Reuse the existing single-file export flow for each planned input without changing the peak-distance algorithm.
- [x] 2.2 Apply shared session, group, entry, subsweep, threshold, max-frame, every-n, and format options to every input.
- [x] 2.3 Continue processing remaining planned inputs after a per-file export failure.
- [x] 2.4 Print per-file success or failure messages that include the source and output paths where relevant.
- [x] 2.5 Print a final batch summary with succeeded and failed counts.
- [x] 2.6 Exit nonzero when any planned input fails or when input/output planning fails.

## 3. Tests And Validation

- [x] 3.1 Add focused tests for input resolution across explicit files, glob patterns, non-recursive directories, and recursive directories.
- [x] 3.2 Add tests for default beside-source output paths and `--output-dir` output paths for JSON and CSV formats.
- [x] 3.3 Add tests that reject `--output` with multiple resolved inputs.
- [x] 3.4 Add tests that reject duplicate resolved inputs, output path collisions, and existing output files before processing.
- [x] 3.5 Add tests for zero-match input behavior and deterministic resolved-path ordering.
- [x] 3.6 Add tests or integration coverage proving single-file behavior remains compatible.
- [x] 3.7 Run the repo-defined focused test command through Hatch and fix any failures.
