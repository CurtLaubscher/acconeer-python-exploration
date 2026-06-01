## Context

The heatmap alignment workbench loads Radar Raw (H5) through background jobs and optional Radar Peak (JSON) synchronously from disk. Peak extraction lives in `sparse_iq_peak_distance_core.py` and matches the CLI `peak-distances` script. The archived closest-object-log-export change deferred an in-app "Calculate Peaks" action; this change delivers that workflow with explicit save semantics and a removable adapter boundary.

Generation from an already-open `HeatmapRecord` is fast (on the order of 0.1 ms per frame for DVM + v=0 argmax on Leg2-sized recordings). Re-opening the H5 via `export_peak_distances()` is much slower and must not be used on the GUI path.

## Goals / Non-Goals

**Goals:**

- Generate peak-distance measurements from the **currently loaded** H5 (session/group/entry/subsweep from `heatmap_track`) without leaving the app.
- Update Signals plot and heatmap peak overlay immediately after generate, same as a successful JSON import.
- Support **Save peaks** / **Save peaks as…** to canonical JSON; set `session.peak_distance_datasource.path` only after a successful save.
- Track **peaks dirty** when in-memory peaks differ from last saved file; show **Generated (unsaved)** (or equivalent) in the Resources row status.
- Integrate unsaved-peaks messaging into existing session quit/close/open prompts and add a confirm when saving session while peaks are dirty.
- Keep peak logic behind a small adapter module callable from GUI and future background jobs.

**Non-Goals:**

- Threshold spinbox or algorithm selection UI (threshold remains default `650` in code for v1).
- Sum-over-velocity or baseline-subtraction algorithm changes.
- CSV export from the GUI.
- `every_n` / `max_frames` in the GUI (always all frames).
- Full resource registry or virtual-resource framework beyond one adapter.
- Background `ResourceJobManager` job for v1 (optional later; adapter API should allow it).
- Skipping validation on CLI import paths; only lighten validation when peaks are generated from the loaded H5 in-session.

## Decisions

### Thin peak-distance resource adapter

Add a focused module (for example `heatmap_peak_distance_resource.py`) that owns:

- `generate_from_heatmap_record(record, *, h5_path, subsweep_idx, threshold) -> PeakDistanceExportResult`
- In-memory peak state separate from file-backed `LoadedPeakDistanceDatasource`
- Peaks dirty flag, last-saved path bookkeeping, and GUI refresh hooks
- Which `ResourceAction` values apply for the Radar Peak row

The main window registers this adapter in the existing Resources flow instead of scattering peak-generate conditionals. Removing radar peaks later means deleting the adapter and one registration site.

### In-memory peak state (not `Path("")`)

While peaks are **generated and unsaved**, hold a `PeakDistanceExportResult` (or thin wrapper) plus `peaks_dirty` in the adapter / main window. Do **not** construct a `LoadedPeakDistanceDatasource` with a fake or empty `path` — that type requires a real on-disk `Path` for import/reload semantics.

After **Load** from JSON or a successful **Save**, use `LoadedPeakDistanceDatasource` as today. The GUI may use a small union such as `PeakDistanceResourceState = GeneratedPeakState | LoadedPeakDistanceDatasource` internally; only the adapter and peak refresh paths need to branch.

### Generate uses in-memory H5 only

When Radar Raw is loaded, call `analyze_heatmap_record` on `HeatmapTruthSource`'s record (or equivalent loaded payload) with frame indices for all frames. Do not call `export_peak_distances()` on the GUI path because it re-opens the HDF5 file.

**Threading:** v1 runs synchronously on the GUI thread with `QApplication.setOverrideCursor(Qt.WaitCursor)` (or equivalent) and a short status-bar message. The adapter exposes a single `generate(...)` entry point so a future worker can call the same function.

### Provenance and path semantics

| State | Memory | `session.peak_distance_datasource.path` | Resources status (example) |
|-------|--------|----------------------------------------|----------------------------|
| Empty | none | `""` | Unloaded |
| External | loaded from JSON | path on disk | Loaded |
| Generated unsaved | `PeakDistanceExportResult` in adapter | previous path retained or `""` | Status column: **Generated (unsaved)** |
| Saved / loaded file | `LoadedPeakDistanceDatasource` | path written on save | Status column: **Loaded** (or equivalent) |

After **Generate** when a path was already set (for example from a prior load of another H5's JSON), keep the path in the table for **Save** targeting; mark peaks dirty; do not modify the file on disk until save. Copy in confirmations must say the **file on disk is unchanged** until the user saves peaks.

After first **Save** / **Save peaks as…**, clear peaks dirty and treat as external. If the saved path differs from the previous session path, mark the alignment session dirty.

### Save UX

- **Save peaks:** enabled when peaks are **dirty** and peak data is in memory. If no path is set, open a file dialog (same as Save peaks as…, default `{h5_stem}_peak_distances.json` beside the loaded H5). If a path is shown in the resource row, write JSON there with overwrite confirmation.
- **Save peaks as…:** enabled whenever peak data is **in memory** (loaded or generated), including when not dirty — so the user can write a copy or new path without regenerating. Disabled only when no peaks are in memory.
- Use **Save** wording, not **Export**, to reflect dirty tracking for **Save peaks**.

### Resources window actions

Extend selected-row actions for Radar Peak only:

- **Generate** — requires loaded H5; replaces in-memory peaks; confirm when replacing existing in-memory peaks.
- **Save peaks** / **Save peaks as…** — as above.
- **Load**, **Reload**, **Unload** — unchanged semantics; **Reload** shows a **blocking confirm** (proceed / cancel) if peaks dirty; **Unload** confirms if peaks dirty.

Do not add Generate to the main menu or Signals area in v1. Generate remains enabled after a successful generate (user may regenerate).

### Dirty and prompts

- **Peaks dirty** does not add `*` to the main window title.
- **Session dirty** rules unchanged except: successful save of peaks to a **new** path may mark session dirty when the stored path changes.
- On quit / close session / open session when `session_dirty` **or** `peaks_dirty`: one existing-style prompt. Update guard conditions from `if self._session_dirty` to `if self._session_dirty or self._peaks_dirty` in quit, close session, and open session paths.
- When peaks are dirty, add prompt body text that unsaved peak-distance data will be lost and that **saving the alignment session does not write peak JSON**. The **Save** button behavior is unchanged (it saves the alignment session only); wording must not imply Save writes peak JSON.
- **Save Session** while peaks dirty: show an additional confirm or paragraph warning before proceeding (peak JSON is not included in the session file).

### Validation after generate

Skip full `validate_peak_distance_import` when peaks were just generated from the loaded H5 (metadata is built from the same record). Continue full validation for file import and reload from disk.

### Resources Status column text

Show **Generated (unsaved)** in the existing Resources table **Status** column when peaks are generated and `peaks_dirty`. Do not add new columns. After save or load from disk, show the normal loaded status label. Implementation may use a display string on `ResourceSummary` rather than a new `ResourceStatus` enum value, as long as the Status column shows the correct user-facing text.

## Risks / Trade-offs

- **Stale path after regenerate:** Session JSON may list a path while memory holds newer unsaved peaks; Reload loads stale file — mitigated by reload warning when peaks dirty and quit/open warnings.
- **GUI freeze on very large recordings:** Acceptable for v1; monitor and move adapter `generate` to `ResourceJobManager` if needed.
- **Adapter incomplete extraction:** Risk of leftover peak conditionals in the main window; tasks include a grep pass for `radar_peak` generate paths.
- **Session save with unsaved peaks:** Saving the session persists the remembered peak JSON path (or empty) but not generated in-memory peaks; reopening loads from that path or omits peaks — documented in spec.

## Open Questions

- None blocking v1; threshold UI and algorithm variants belong in a follow-up change.
