## Context

The `peak-distances` Hatch script currently accepts one H5 recording and writes one JSON or CSV export. The calculation itself is already isolated in reusable peak-distance core code, while the CLI owns argument parsing, output path selection, and user-facing reporting.

The batch feature should behave like repeated single-file exports with better input discovery, naming, validation, and summary reporting. It should not change the peak-distance algorithm or the canonical JSON/CSV formats.

## Goals / Non-Goals

**Goals:**

- Preserve existing single-file command behavior and default output naming.
- Allow one command invocation to process multiple H5 recordings.
- Support explicit files, glob-style patterns, and directories.
- Keep all selection and algorithm options shared across every resolved input.
- Write one output file per input H5 file for both JSON and CSV.
- Fail early when input resolution or output path planning is ambiguous, duplicated, colliding, or would overwrite existing files.
- Provide a concise batch summary and a nonzero exit code when any input fails.
- Keep batch planning and execution separated so future parallel execution can be added without redesigning input/output handling.

**Non-Goals:**

- Do not create combined JSON or aggregate CSV exports.
- Do not add per-file thresholds or per-file session/group/entry/subsweep selections.
- Do not add user-facing parallel processing in the first implementation.
- Do not change the heatmap alignment GUI import format.
- Do not add new runtime dependencies.

## Decisions

### Keep Single-File Export As The Unit Of Work

Each resolved H5 input should call the existing single-file export path and produce exactly one output file. This preserves the current metadata model, where a peak-distance JSON file describes one source recording and one selected recording entry.

Alternative considered: combined batch JSON. That would require a new outer format and would not be directly importable by the existing heatmap alignment workflow.

### Use Multi-Input Positional Arguments

The CLI should change from one positional `input` path to one-or-more input arguments. Each argument can resolve to a file, a glob pattern, or a directory. Mixed input forms should be pooled into one resolved list of files to process.

Alternative considered: add a separate `--input-dir` option. Positional inputs are more compact and allow mixed use, such as one explicit file plus one directory.

### Treat Directory Inputs As Non-Recursive By Default

Directory inputs should discover `.h5` and `.hdf5` files case-insensitively directly inside that directory. `--recursive` should opt into recursive discovery. The `.hdf5` extension is included for batch discovery to match common HDF5 naming and the heatmap GUI file filters; explicit single-file inputs remain valid when the underlying record loader can open them.

Alternative considered: recursive directory traversal by default. That is more surprising, can process far more data than intended, and increases collision risk when paired with a flat output directory.

### Validate The Resolved Input Pool Before Output Planning

Each raw input should be resolved into zero or more candidate H5 files, then normalized to resolved absolute paths. The command should fail before export work if no H5 files are resolved across the complete input set. If one directory is empty but another input resolves files, the batch should continue using the resolved files. Duplicate resolved files should be treated as an error, including cases where the same file is named explicitly and also discovered through a directory or glob.

Resolved inputs should be processed in deterministic resolved-path order. This keeps logs and tests stable while remaining close to user intent for simple commands.

### Preserve Current Output Naming

The default output name remains `<input_stem>_peak_distances.json` or `<input_stem>_peak_distances.csv`. Without `--output-dir`, each output is written beside its input. With `--output-dir`, outputs are written flat into that directory using the same basename.

Alternative considered: include parent directory names or hashes in all batch output filenames. That reduces collisions but makes the common case less readable and harder to compare with source files.

### Reject Ambiguous Or Colliding Output Plans Before Processing

`--output` remains valid only when exactly one H5 input is resolved, regardless of whether that single input came from a file, glob, or directory. Multiple resolved inputs must use default beside-source output paths or `--output-dir`. If `--output-dir` points to an existing file, if two resolved inputs map to the same output path, or if any planned output already exists, the command should fail before processing and list the conflicting paths.

Alternative considered: overwrite or auto-disambiguate. Silent overwrite risks data loss, while automatic disambiguation creates filenames users did not choose. A later `--overwrite` option can be added if rerun workflows need it.

### Continue Batch Processing After Per-File Export Failures

After input resolution and output planning succeed, batch mode should attempt every planned export. Failed files should be reported in the final summary, and the process should exit nonzero if any file failed.

Alternative considered: stop on first per-file failure. Continuing gives users a more useful batch result, especially when one bad recording should not block unrelated recordings.

### Keep Execution Parallel-Ready Without Adding `--jobs`

Implementation should make planning produce simple per-file jobs containing an input path, output path, format, and shared export options. The first implementation should execute those jobs serially. A future `--jobs` option could run independent jobs concurrently after measuring memory and HDF5 behavior, without changing parsing, input resolution, collision detection, or output naming.

Alternative considered: add `--jobs` immediately. That may be useful later, but it adds Windows multiprocessing, output ordering, memory pressure, and progress-reporting complexity before batch behavior itself has been proven.

## Risks / Trade-offs

- Broad input expansion can accidentally include unwanted files -> Directory inputs are non-recursive by default, and resolved file count should be reported before or during processing.
- Flat `--output-dir` can collide for same-stem inputs from different folders -> Detect collisions before processing and require the user to choose beside-source output or rename inputs.
- Existing output files can cause accidental overwrite on reruns -> Treat existing planned outputs as preflight errors in v1.
- Continuing after per-file failures can leave partial batch output -> Summary reporting and nonzero exit status make partial success explicit.
- Internal glob handling can behave differently from shell expansion -> Treat both shell-expanded files and raw glob strings as input sources, and cover Windows behavior in tests.
