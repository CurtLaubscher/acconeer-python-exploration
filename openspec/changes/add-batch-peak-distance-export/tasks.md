## 1. Input And Output Planning

- [ ] 1.1 Refactor `export_sparse_iq_peak_distances.py` so the parser accepts one or more input arguments while preserving single-input behavior.
- [ ] 1.2 Implement input resolution for explicit files, glob patterns, and directory inputs matching `.h5` and `.hdf5` files.
- [ ] 1.3 Add `--recursive` handling for directory input discovery.
- [ ] 1.4 Add `--output-dir` handling and keep `--output` valid only for exactly one resolved input.
- [ ] 1.5 Implement output path planning with `<input_stem>_peak_distances.<format>` names beside sources by default or flat under `--output-dir`.
- [ ] 1.6 Normalize resolved inputs to absolute paths, sort them deterministically, and reject duplicate source files before processing.
- [ ] 1.7 Detect empty resolved input sets, output path collisions, and existing output files before processing.

## 2. Batch Execution

- [ ] 2.1 Reuse the existing single-file export flow for each planned input without changing the peak-distance algorithm.
- [ ] 2.2 Apply shared session, group, entry, subsweep, threshold, max-frame, every-n, and format options to every input.
- [ ] 2.3 Continue processing remaining planned inputs after a per-file export failure.
- [ ] 2.4 Print per-file success or failure messages that include the source and output paths where relevant.
- [ ] 2.5 Print a final batch summary with succeeded and failed counts.
- [ ] 2.6 Exit nonzero when any planned input fails or when input/output planning fails.

## 3. Tests And Validation

- [ ] 3.1 Add focused tests for input resolution across explicit files, glob patterns, non-recursive directories, and recursive directories.
- [ ] 3.2 Add tests for default beside-source output paths and `--output-dir` output paths for JSON and CSV formats.
- [ ] 3.3 Add tests that reject `--output` with multiple resolved inputs.
- [ ] 3.4 Add tests that reject duplicate resolved inputs, output path collisions, and existing output files before processing.
- [ ] 3.5 Add tests for zero-match input behavior and deterministic resolved-path ordering.
- [ ] 3.6 Add tests or integration coverage proving single-file behavior remains compatible.
- [ ] 3.7 Run the repo-defined focused test command through Hatch and fix any failures.
