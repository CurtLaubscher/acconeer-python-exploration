## Context

The heatmap alignment workbench currently has one optional Radar Peak (JSON) datasource slot. In-app generation produces one active peak result; importing JSON also replaces that one slot. The GUI also contains a temporary comparison overlay that computes a second hardcoded algorithm and passes it directly to the Signals plot.

That shape is adequate for a single algorithm but not for exploring peak-finding approaches. The desired workflow is to load one H5, generate several peak series with different algorithms or thresholds, compare them in the Signals plot, pick one for the rendered heatmap marker, and save the useful series as canonical JSON.

The broader product direction is a general sync workbench with arbitrary resources later. This change should move toward multi-instance optional resources where it naturally helps peak series, but it must not become a full plugin/resource-framework rewrite.

## Goals / Non-Goals

**Goals:**

- Support 0..N peak series resources in one workbench session.
- Let Generate append a new unsaved peak series instead of replacing existing peaks.
- Let Import Peak Series append an external JSON peak series instead of replacing existing peaks.
- Share the same pure peak algorithm engine between GUI generation and the `peak-distances` CLI.
- Start with two algorithms: `v=0 slice` and `sum v`; both expose threshold.
- Keep algorithm logic outside Qt and outside plot-specific code.
- Show multiple peak series in the Signals plot with stable comparison colors and concise legend names.
- Let the rendered heatmap show `None` or one selected peak series marker.
- Keep Save / Save As / Unload row-specific for peak series.
- Preserve saved/imported peak series by path in session JSON; do not embed measurement arrays.
- Migrate older single peak datasource session fields into one imported peak series on load.
- Remove the temporary hardcoded compare overlay.

**Non-Goals:**

- Full arbitrary resource framework or plugin/adapter registry for all resource types.
- Multi-instance Leg2 MAT resources; Leg2 remains a single optional slot.
- Making Camera Video or Radar Raw (H5) optional/import-style resources.
- Background peak generation unless synchronous generation proves too slow during implementation.
- Embedding generated peak measurements in alignment session JSON.
- Auto-regenerating unsaved peak series on session load.
- Generic algorithm-parameter schema beyond the small hardcoded v1 dialog.
- Peak marker style redesign beyond supporting one selected peak series; marker polish remains a future idea.
- Legend grouping for detected/no-detection curve pairs; this remains a future idea.

## Decisions

### Peak series are multi-instance optional resources

Represent peak outputs as a list of peak series resource instances rather than one `radar_peak` slot. Each instance should carry:

- Stable in-session id
- Display name
- Provenance: generated or imported/saved
- Optional JSON path
- Algorithm id and parameters when generated or when metadata is available
- Measurements
- Visible state for the Signals plot
- Color
- Unsaved state
- Row-level warnings/errors

This keeps the resource table and signal plot aligned with the user's mental model: each generated or imported peak result is a separate thing that can be shown, hidden, saved, or unloaded.

Alternative considered: keep one Radar Peak slot and add ad hoc comparison curves. That would scale poorly past two algorithms and keep temporary experiment code in the plot path.

### Use a modest reusable resource shape, not a full framework

Implement enough shared shape for multi-instance peak series to reduce hardcoded peak branching in Resources rows and signal plotting. Do not convert Camera Video, Radar Raw (H5), or Leg2 MAT into a fully generic resource registry unless that is the simplest way to support peak series.

This is a step toward a future arbitrary resource framework. It should leave reusable pieces where they naturally emerge, especially row summaries, row actions, colors, and signal plot series assembly. It should not block on a complete abstraction.

### Generate and import append rows

Generate opens a small dialog, runs the selected algorithm against the loaded H5, and appends a new unsaved peak series row. Import Peak Series opens a JSON picker, validates the file using the existing import validation path, and appends a row.

Neither operation replaces existing peak series. Replacing remains a row-specific action only if implementation chooses to offer it later; v1 only needs append plus unload.

### Peak algorithms are pure and shared

Move algorithm selection behind a small non-GUI engine/registry in or near `sparse_iq_peak_distance_core.py`. The registry should initially define:

- `zero_velocity_slice` with concise label `v0 slice`
- `sum_velocity` with concise label `sum v`

Both algorithms expose threshold, defaulting to the existing `DEFAULT_PEAK_THRESHOLD`. The GUI and CLI call the same algorithm functions. The CLI keeps existing behavior by default, and adds a `--method` option whose values map to the same ids used by the GUI.

Update `generate_peak_distances_from_heatmap_record(...)` in `heatmap_peak_distance_resource.py` to accept the selected peak method/algorithm id and forward it to `analyze_heatmap_record(...)`; the helper must no longer rely on the analysis default when the GUI is generating a selected algorithm.

The v1 parameter UI can be hardcoded per algorithm. Add comments where appropriate that the dialog plumbing is intentionally temporary until peak generation is removed or a generic parameter model becomes worthwhile.

### Concise names and automatic colors

Generated rows should default to short names such as `v0 slice, thresh 650` or `sum v, thresh 650`. The Generate dialog may allow editing the name before appending. Imported rows should use `Path(json_path).stem` as the default display name, with a short numeric suffix when needed for uniqueness.

Assign peak-series colors from a stable palette in append order. Do not reuse the H5 green for every peak series; comparison readability matters more than H5 lineage for multi-peak review.

### Signals plot shows many peak series

The Signals plot should accept a collection of peak signal series rather than one primary peak plus one compare peak. Each visible peak series is plotted with its assigned color. Detected and no-detection/candidate segments may remain separate curve objects internally, but the legend label should identify the peak series and algorithm concisely.

The existing temporary compare cache and global flag should be removed.

### Rendered heatmap marker selects one series

Add a selector in the rendered heatmap controls with `None` plus all peak series resources. The selected series controls the current-frame marker and export overlay marker. This selector is independent of Signals visibility: a hidden series may still be selected for the heatmap marker if the user chooses it.

After Generate, select the newly generated series for the heatmap marker by default.

### Save semantics are row-specific

For a generated unsaved row:

- Save writes to the row's existing path if one exists.
- If no path exists, Save behaves like Save As.
- Save As always prompts for a path.

For an imported/saved row:

- Save writes to the row's path after overwrite confirmation when applicable.
- Save As always prompts and updates that row to the new path on success.

Successful save clears that row's unsaved state and may mark the alignment session dirty if persisted row path/display metadata changes.

### Session persistence stores references, not measurements

Do not embed generated peak measurement arrays in the alignment session JSON. Store saved/imported peak series as path-based optional resources with their display settings, color, visibility, and marker selection state. Generated unsaved rows with no saved path are not restored after session close/open.

Do not auto-regenerate unsaved rows on load. Auto-regeneration would make session loading slower and could silently change results when algorithms evolve.

The new session JSON field is `peak_series`. It contains a list of peak series reference objects. Each saved object should include at least `path`, `display_name`, `color`, and `visible`; marker selection may be represented as a single selected peak id/path elsewhere in session state or as a boolean on one list item, as long as only one saved/imported series restores as the heatmap marker source. The old `peak_distance_datasource` key should be absent from newly saved version 3 sessions.

Bump `SESSION_VERSION` from `2` to `3`. Older session payloads with one `peak_distance_datasource` should migrate to one peak series row when a path is present. Sessions without peak data remain valid.

The existing v1-to-v2 migration should run before the new v2-to-v3 migration. A v1 file therefore becomes a v2 payload first, then the v2-to-v3 step converts `peak_distance_datasource` into `peak_series`.

### Session reconciliation for peak series

Session load reconciliation must change from one `desired_peak_identity(...)` slot to per-series reconciliation:

- For each persisted peak series path in the loaded session, keep an already loaded runtime series when the path and loaded measurements match that persisted entry closely enough.
- Load persisted peak series paths that are not already active.
- Unload runtime peak series that are not present in the incoming session unless they are explicitly added by startup override arguments after session load.
- Preserve row-specific validation warnings/errors on the row they belong to.

When `--peaks` is provided with `--session`, load the session first, then append the startup peak JSON as an additional imported peak series using the same validation path as interactive import. If the same path was already restored from the session, implementation may either keep one row and report that the startup import was already present or append a duplicate only if duplicate imports are explicitly supported; prefer avoiding accidental duplicate rows for the same path.

### Validation stays full for import, light for generate

Imported JSON keeps the existing validation behavior against loaded H5 metadata when possible, with warnings/errors attached to the specific imported row. Generated peak series came from the loaded H5 and only need basic sanity checks before appending.

No broader parent-H5 dependency model is required for v1.

### H5 replacement keeps peak series as optional signals

The old single-slot requirement cleared Radar Peak (JSON) when a different H5 replaced the current H5. In the multi-peak model, peak series are optional signal resources and should not be automatically cleared solely because the H5 changed. Imported rows already carry row-level validation warnings when metadata does not match the loaded H5. Generated rows are scratch resources; if they remain after H5 replacement, they should continue to behave as signal resources until the user unloads them or clears all resources.

This intentionally avoids a broader parent-H5 dependency system for v1.

### Menu terminology

Keep Load / Unload for Camera Video and Radar Raw (H5). For peaks, use Import Peak Series and Generate Peak Series for append actions. Save, Save As, and Unload are row-specific actions in the Resources window. Avoid "Clear" in touched peak-resource UI.

Top-level Resources menu may keep primary load/unload actions. Peak-specific per-row actions should live in the Resources window; optional top-level Import Peak Series and Generate Peak Series are acceptable because they append new rows and do not require a selected row.

## Risks / Trade-offs

- **Resource model scope creep** -> Keep the design focused on peak series. Reuse general pieces where easy, but do not convert all resources to a plugin system.
- **Large GUI refactor risk** -> Preserve existing camera/H5/Leg2 behavior and change only the paths necessary for multi-peak rows, plotting, and session persistence.
- **Legend width** -> Use concise display names and algorithm abbreviations; avoid verbose parameter dumps in legend labels.
- **Too many plotted curves** -> Let the user control Signals visibility per peak series; heatmap marker shows only one selected series.
- **Accidental loss of generated peaks** -> Show unsaved state per row and include unsaved peak warnings in destructive session/resource actions. Do not imply session save writes peak JSON.
- **Import/generate model asymmetry** -> Treat both imported and generated peak outputs as peak series rows so the UI and code do not diverge.
- **CLI behavior regression** -> Keep CLI defaults compatible and add tests proving GUI and CLI use the same algorithm ids/core.
- **Session migration errors** -> Add tests for loading older single-peak sessions and saving the new multi-peak session shape.

## Migration Plan

- Add a new session representation for peak series while preserving load support for the existing single `peak_distance_datasource` field.
- Bump `SESSION_VERSION` to `3`.
- On load, run v1-to-v2 migration if needed, then convert an existing v2 single peak datasource path into one imported peak series row.
- On save, write the new `peak_series` list and omit unsaved generated rows without paths.
- Keep startup `--peaks` behavior by importing the provided JSON as an appended peak series after session/H5 load.
- Remove the temporary comparison overlay once the multi-series plot path is available.

## Open Questions

- None blocking this proposal.
