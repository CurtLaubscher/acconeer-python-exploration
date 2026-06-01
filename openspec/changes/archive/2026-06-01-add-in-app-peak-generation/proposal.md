## Why

Peak-distance JSON for the heatmap alignment workbench is produced today only via the standalone `peak-distances` CLI. Users who already loaded an H5 recording must leave the app, export JSON, and import it back to review peaks on the Signals plot and heatmap overlay. That loop is slow for iterative alignment work and for exporting peaks to external tools (for example MATLAB) that consume the canonical JSON file.

The exporter core (`export_peak_distances` / `analyze_heatmap_record`) was intentionally kept outside the GUI so an in-app action could reuse it later. Measurement on typical Leg2 trials is sub-second when the H5 is already in memory, so synchronous generation in the Resources window is practical for v1.

## What Changes

- Add **Generate peaks** for the Radar Peak (JSON) resource slot when Radar Raw (H5) is loaded, computing peaks from the in-memory H5 using the existing zero-velocity-slice algorithm and default threshold `650`.
- Keep generated peaks **in memory only** until the user saves; after save, treat the slot like a normal loaded JSON file (`external` with path).
- Track **peaks dirty** separately from session dirty; show status such as **Generated (unsaved)** in the Resources row (not in the main window title).
- Add **Save peaks** (when peaks dirty) and **Save peaks as…** (whenever peaks are in memory) in the Resources window for the Radar Peak row, with overwrite confirmation when writing to an existing path.
- Fold unsaved-peaks warnings into the **existing** session unsaved-changes prompts (quit, close session, open session) when `session_dirty` or `peaks_dirty`, without a second modal chain; clarify that saving the alignment session does not write peak JSON (Save in that dialog still saves the session only).
- Warn when saving the alignment session while peaks are dirty; confirm before unload/clear/reload/generate-replace when unsaved generated data would be lost.
- Introduce a thin **peak-distance resource adapter** (session fields, Resources actions, generate/save/load) without a full resource registry; shape APIs so a future background job can call the same generate core.
- Defer threshold UI, algorithm changes (sum-over-velocity), CSV export from the GUI, and background job integration.

## Capabilities

### New Capabilities

_None — behavior extends the existing heatmap alignment workbench._

### Modified Capabilities

- `heatmap-alignment-gui`: In-app peak generation from loaded H5, peaks dirty/save workflow, Resources-window actions and status, and unsaved-prompt integration.

## Impact

- `user_tools/sparse_iq_peak_distance_core.py` — reuse `analyze_heatmap_record`, `write_peak_distance_json`, `peak_distance_document`; optional thin helper to build result from open `HeatmapRecord`.
- `user_tools/heatmap_alignment_core.py` — peaks dirty/runtime flags, resource summaries, `ResourceAction` extensions, unsaved-prompt helpers.
- `user_tools/heatmap_alignment_gui.py` — Resources actions, generate/save handlers, confirmations, refresh Signals and peak overlay after generate/save.
- `openspec/specs/heatmap-alignment-gui/ideas.md` — already notes modular adapters and derived resources (reference only).
- Tests: core adapter/dirty/save behavior; focused GUI or integration tests optional.
