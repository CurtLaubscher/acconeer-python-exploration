## Context

The existing Sparse IQ heatmap exporter and heatmap alignment GUI already know how to open H5 recordings, resolve session/group/entry/subsweep selections, compute distance/velocity magnitude maps, and derive physical distance and velocity axes. The new feature should use those patterns as implementation guidance, but the primary workflow is separate: take a recorded H5 log, generate derived peak-distance data, and save that data as a reusable file.

The generated file then becomes a new optional datasource for the heatmap alignment/video workflow. This keeps data generation reproducible and scriptable while still allowing aligned videos or sessions to include the derived distance measurements later.

## Goals / Non-Goals

**Goals:**

- Provide a standalone CLI-style user-tool script for H5 peak-distance export.
- Keep the core peak calculation independent of Qt so it can be tested and later reused by a heatmap app "Calculate Peaks" action.
- Implement the first algorithm as the strongest peak in the velocity bin nearest `0 m/s`, gated by a user-configurable threshold whose default is `650`.
- Export deterministic JSON results that include source metadata and per-frame measurements without repeating constant metadata in every measurement.
- Support a reduced CSV export mode for manual inspection and spreadsheet workflows.
- Allow the heatmap alignment/video workflow to import the generated JSON as an optional distance-measurement datasource.
- Allow users to show/hide and unload the optional imported distance-measurement datasource.
- Validate imported JSON files against the loaded H5 recording using frame count, elapsed real-time range, and source-selection metadata when available.
- Persist optional imported distance-measurement datasource state in alignment sessions while retaining backwards compatibility with existing session files.

**Non-Goals:**

- Build a threshold-preview GUI in the initial implementation.
- Add a heatmap app "Calculate Peaks" button in the initial implementation.
- Claim the first algorithm is a tuned closest-object detector; it is an exploratory zero-velocity peak extractor.
- Replace the existing A121 distance detector or provide live distance tracking.
- Make the first implementation robust against all noise cases before seeing real output quality.
- Support every possible export format in the first implementation.

## Decisions

### Ship a scriptable exporter before a preview app

Add a standalone script, for example `user_tools/export_sparse_iq_peak_distances.py`, callable through the repo-managed Hatch app environment as `hatch run app:peak-distances`. The script should accept input/output paths, H5 selection options, subsweep selection, threshold defaulting to `650`, frame limiting/stride options if useful, and `--format json|csv` defaulting to `json`.

Rationale: the algorithm is deliberately exploratory. A CLI lets users generate data repeatedly, compare thresholds, and inspect JSON or reduced CSV output before investing in threshold-preview UI. The same core function can later be called by an in-app button.

Alternative considered: build a PySide preview app first. That would improve threshold tuning, but it front-loads UI work before the basic signal quality is known.

### Reuse heatmap helpers without coupling to the alignment GUI

Place shared loading, selection, axis, and distance/velocity-map behavior in reusable helper code, extending `sparse_iq_heatmap_common.py` or adding a focused companion module if the new code would make that module too broad. Do not put the exporter algorithm inside `HeatmapAlignmentWindow`.

Rationale: the exporter and future GUI button should share tested non-GUI logic. The alignment GUI should consume generated JSON files and may later call the same exporter core, but it should not be the owner of the algorithm.

Alternative considered: add the analysis directly to the heatmap alignment GUI. That conflicts with the desired standalone data-generation workflow and makes CLI use harder.

### Use zero-velocity strongest-peak extraction first

For each selected frame, compute the distance/velocity magnitude map, find the velocity axis entry closest to `0 m/s`, read that velocity slice across distance, find the maximum-strength distance bin in the slice, and export that distance if the strength is above the configured threshold. If the peak is not above threshold, export the frame with a no-detection status.

Rationale: this is simple, transparent, and easy to validate against the rendered heatmap. It intentionally answers "what is the strongest zero-velocity peak?" rather than the final tuned "closest object" requirement.

Alternative considered: collapse all velocity bins into one score per distance and choose the nearest thresholded bin. That is closer to a future closest-object detector but adds tuning questions before the first data inspection pass.

### Export JSON as the canonical datasource format

Use JSON as the canonical output and GUI import format. JSON keeps source metadata in one place, keeps measurements as a per-frame array, and avoids repeating long fields such as source paths in every row.

Initial JSON shape:

```json
{
  "format": "acconeer_peak_distances",
  "version": 1,
  "metadata": {
    "source_path": "...",
    "source_name": "...",
    "session_index": 0,
    "group_index": 0,
    "entry_index": 0,
    "sensor_id": 1,
    "subsweep_index": 0,
    "source_frame_count": 123,
    "source_duration_s": 1.23,
    "ticks_per_second": 1000000,
    "threshold": 650,
    "zero_velocity_bin_index": 0,
    "zero_velocity_m_s": 0.0
  },
  "measurements": [
    {
      "frame_index": 0,
      "source_tick": 0,
      "time_s": 0.0,
      "absolute_time": null,
      "status": "detected",
      "peak_distance_m": 0.42,
      "candidate_peak_distance_m": 0.42,
      "peak_strength": 812.0
    }
  ]
}
```

Measurement and metadata keys should use only Latin letters, digits, and underscores, and no key should start with a digit.

Rationale: JSON is one file, preserves metadata without repetition, and supports strong GUI validation without sidecar files or non-standard CSV preambles.

Alternative considered: CSV with metadata preamble comments. That is common in scientific tooling but can be awkward in spreadsheet software and other generic CSV readers.

### Support reduced CSV as an optional inspection format

Support `--format csv` as a reduced export mode for spreadsheet/manual inspection. The reduced CSV should omit metadata that is guaranteed to be constant for every row and should not be the canonical GUI import format for this change.

Reduced CSV columns:

- `frame_index`
- `source_tick`
- `time_s`
- `absolute_time`
- `status`
- `peak_distance_m`
- `candidate_peak_distance_m`
- `peak_strength`

Rationale: the reduced CSV remains clean for humans and spreadsheet tools without carrying repeated metadata. It is intentionally weaker for validation than JSON.

Alternative considered: keep repeated metadata columns in CSV. That is maximally self-contained per row but creates noisy and bulky files.

### Import generated JSON as an optional alignment datasource

Extend the alignment/video session model with an optional distance-measurement datasource that references the JSON path and stores enough import metadata to validate timeline compatibility. Existing sessions should load with this datasource absent.

Rationale: the generated peak-distance JSON is conceptually distinct from the heatmap H5 source. Treating it as an optional datasource keeps the current camera/heatmap alignment model intact while allowing videos or future UI layers to visualize/import derived measurements.

Alternative considered: bake peak data into the H5 heatmap track state. That would blur source data with derived data and make regeneration/threshold changes harder to reason about.

### Make peak JSON import errors user-oriented

When peak JSON import fails because the selected file is not a canonical peak-distance JSON export, show a message that names the user-level problem first, for example "This is not a peak-distance JSON file generated by peak-distances." Technical details such as the missing or unsupported `format` value should be included only as secondary context.

Rationale: users need to know which file kind to provide. Raw parser details are useful for debugging but are not a good primary error message.

### Support peak datasource startup loading

Add a heatmap alignment GUI startup argument for loading a canonical peak-distance JSON datasource, for example `--peaks path/to/peaks.json`. The startup path should reuse the same JSON import and validation logic as the interactive import action.

If a saved alignment session is also supplied, load the session first and then apply the explicit `--peaks` datasource so command-line arguments can override the session's stored peak datasource for quick comparisons. If an H5 recording is loaded through the session or `--h5`, validate the peak datasource against that H5 source using the normal import rules.

Rationale: users who generate peak-distance JSON from the CLI should be able to open the heatmap alignment GUI with the H5 and peaks file already loaded, and they should be able to compare alternate peak outputs without editing the saved session.

### Hard-fail clear JSON/H5 length mismatches

When importing a peak-distance JSON file with an H5 heatmap recording loaded, require the measurement row count to match the H5 frame count. A length mismatch means the JSON is not the per-frame datasource for that H5 selection and should fail import rather than ask for confirmation.

Rationale: the generated datasource is expected to have one row per H5 frame. Since no separate alignment is planned for this datasource, mismatched lengths are more likely to hide a wrong file than represent a recoverable workflow.

Alternative considered: allow an explicit override. That may be useful for future downsampled or filtered peak data, but it would weaken the initial validation model.

### Visualize peaks as an optional overlay first

Start with a show/hide toggle and a current-frame peak marker on or alongside the heatmap view. The marker should use the imported row for the current H5 frame and avoid drawing a distance when that row has no detection. A separate time-series plot or timeline strip can be added later if users need better whole-recording review.

Rationale: the marker directly explains how the imported peak relates to the heatmap that produced it, has low layout cost, and also maps cleanly to synced video export if peak visualization becomes part of the exported overlay.

Alternative considered: add a full peak-distance time-series plot immediately. That will be useful for continuity review, but it adds more UI surface before the basic import/overlay workflow is proven.

## Risks / Trade-offs

- Threshold choice may require several CLI runs -> keep the CLI fast and deterministic; defer preview UI until real data shows it is needed.
- The zero-velocity strongest peak may not correspond to the closest object -> name columns and docs around `peak_distance_m` / `zero_velocity` rather than overclaiming final closest-object accuracy.
- JSON import can drift from the H5 timeline if generated from a different log or selection -> include source path/selection metadata and validate it when importing.
- Source paths can change after export -> treat path/name mismatches as warnings when frame count, duration, tick rate, and selection metadata match.
- Session format changes can break older artifacts -> make the distance datasource optional with defaults for missing fields and preserve current session load behavior.
- Future in-app calculation could duplicate CLI options -> design the core algorithm API as reusable config/result functions, with CLI and future GUI button as thin wrappers.

## Migration Plan

Add the standalone exporter and JSON import path without changing existing camera/heatmap requirements. Extend the alignment session schema with an optional distance-measurement datasource field; when loading older sessions, default that field to absent. Rollback is removing the optional datasource handling and exporter script; existing alignment artifacts remain compatible if the new session field is optional.
