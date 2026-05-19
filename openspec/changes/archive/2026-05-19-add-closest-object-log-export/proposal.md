## Why

Users can render Sparse IQ heatmaps from recorded H5 logs, but they do not yet have a repeatable way to derive a simple distance-measurement time series from those logs. Adding a standalone peak-distance exporter creates a new file-backed datasource that can later be imported into the heatmap alignment/video workflow alongside camera and heatmap data.

## What Changes

- Add a standalone user-tool script that reads an Acconeer H5 log and exports derived peak-distance measurements.
- Reuse or separate existing Sparse IQ heatmap loading and distance/velocity-map helpers where appropriate, using the heatmap exporter as the reference implementation rather than coupling the new script to the heatmap alignment GUI.
- Implement the initial measurement algorithm as a simple zero-velocity-slice peak finder: compute each frame's distance/velocity magnitude map, select the velocity bin nearest `0 m/s`, find the strongest distance peak in that slice, and export it when it is above a user-configurable threshold that defaults to `650`.
- Preserve no-detection frames in the exported measurements so the generated data remains aligned to the source log timeline.
- Export JSON by default as the canonical one-file datasource format, including metadata and measurements without repeating constant metadata on every row.
- Support a reduced CSV export mode for spreadsheet/manual inspection, containing only row-varying measurement columns and omitting metadata that is guaranteed to be identical for all rows.
- Extend the heatmap alignment/video workflow so it can import the generated JSON as an optional distance-measurement datasource.
- Extend the alignment session format to persist optional imported distance-measurement datasource metadata while keeping older sessions loadable.
- Defer in-GUI peak calculation and threshold preview to a future iteration, while keeping the standalone exporter structured so a future "Calculate Peaks" button can call the same core logic.

## Capabilities

### New Capabilities

- `closest-object-log-export`: Standalone peak-distance export from recorded Sparse IQ logs, with canonical JSON output and optional reduced CSV output.

### Modified Capabilities

- `heatmap-alignment-gui`: Import and persist an optional generated JSON distance-measurement datasource for use in the heatmap alignment/video workflow.

## Impact

- Affected user tools: a new script under `user_tools/`, shared Sparse IQ helper code near `user_tools/sparse_iq_heatmap_common.py`, and `user_tools/heatmap_alignment_gui.py` / `user_tools/heatmap_alignment_core.py` for optional JSON datasource import and session persistence.
- Affected Hatch tooling: add a repo-managed `pyproject.toml` app-environment script named `peak-distances` for the standalone exporter.
- Affected tests: focused unit tests for the zero-velocity peak algorithm, JSON export/import tests, and reduced CSV export tests using synthetic data.
- Output formats: canonical JSON with metadata and measurements, plus optional reduced CSV with stable underscore-separated measurement columns for spreadsheet/manual inspection.
- Dependencies: use existing project dependencies such as NumPy and pandas where appropriate; update `pyproject.toml` only if implementation requires a new runtime dependency.
