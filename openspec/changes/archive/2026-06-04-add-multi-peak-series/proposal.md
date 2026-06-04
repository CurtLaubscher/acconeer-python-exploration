## Why

Peak finding is currently a short-term experimental need inside a heatmap alignment workbench that should keep moving toward a more general sync tool. The current single Radar Peak slot and temporary hardcoded comparison overlay make it slow to compare algorithms and encourage peak-specific code to leak into plotting and resource management.

Users need to generate, import, compare, and save multiple peak-distance series from the same loaded H5 without leaving the app or replacing the prior result each time.

## What Changes

- Replace the single active Radar Peak resource slot with **multiple peak series resources** that can be generated or imported independently.
- Add a small peak algorithm engine shared by the GUI and CLI, initially with two algorithms: `v=0 slice` and `sum v`, both using a threshold parameter.
- Add an in-app Generate flow that lets the user choose an algorithm, set its parameters in a small dialog, and append a new unsaved peak series row.
- Change peak JSON loading into **Import Peak Series...**, appending an imported peak series row instead of replacing the existing peak series.
- Let the Signals plot show multiple visible peak series at the same time, with concise legend labels and automatically assigned comparison colors.
- Add a rendered-heatmap peak selector that chooses `None` or exactly one peak series for the current-frame marker, independent of Signals plot visibility.
- Make Save / Save As / Unload row-specific peak-series actions in the Resources window.
- Keep generated unsaved peak data out of alignment session JSON. Saved/imported peak series are restored by path; generated unsaved series are lost on session close/open unless explicitly saved.
- Migrate existing single `peak_distance_datasource` session state into the new peak-series list as one imported peak series.
- Remove the current hardcoded temporary comparison overlay path; multi-series resources replace it.
- Update Resources terminology: keep **Load** for primary Camera Video and Radar Raw (H5), use **Import** for optional external peak series, and use **Unload** instead of **Clear** for resource removal where touched.
- Add brief README context for future agents and move out-of-scope follow-up ideas to `ideas.md`.

## Capabilities

### New Capabilities

_None — behavior extends the existing heatmap alignment workbench._

### Modified Capabilities

- `heatmap-alignment-gui`: Multi-instance peak series resources, shared peak algorithms, generate/import append workflows, multi-series Signals display, rendered-heatmap peak selection, row-scoped peak save/unload behavior, session persistence migration, and removal of the temporary comparison overlay.

## Impact

- `user_tools/sparse_iq_peak_distance_core.py` — expose peak algorithms through a shared non-GUI engine/registry callable by GUI and CLI.
- `user_tools/export_sparse_iq_peak_distances.py` — keep using the same peak engine as the GUI for CLI output and add a `--method` option while preserving the current default behavior.
- `user_tools/heatmap_peak_distance_resource.py` — evolve from single peak state to peak-series resource helpers and save/import/generate utilities; add a peak algorithm/method parameter to generation helpers and forward it to `analyze_heatmap_record`.
- `user_tools/heatmap_alignment_core.py` — session model migration, resource summaries, resource runtime state, concise names/colors, signal-series building for multiple peak resources.
- `user_tools/heatmap_alignment_gui.py` — Resources-window actions, Generate dialog, peak-series row actions, Signals plot refresh, rendered-heatmap selector, startup/session reconciliation, and temporary overlay removal.
- `user_tools/heatmap_alignment_resource_jobs.py` — confirm no behavior changes are needed because peak generation remains synchronous in v1 and peak JSON import remains row-scoped.
- `openspec/specs/heatmap-alignment-gui/ideas.md` — move follow-up polish items that are not part of this proposal.
- `README.md` — add a short development note pointing future agents at the peak-series direction and OpenSpec artifacts.
- Tests: peak algorithm engine, generated/imported peak-series state, resource summaries, session migration/persistence, save/import behavior, signal plot data assembly, and focused GUI behavior where practical.
