## 1. Peak generation core and adapter

- [x] 1.1 Add `generate_peak_distances_from_heatmap_record(...)` in `user_tools/heatmap_peak_distance_resource.py` that calls `analyze_heatmap_record` on an open `HeatmapRecord` with all frames and default threshold `650`
- [x] 1.2 Add in-memory peak state (`PeakDistanceExportResult` + `peaks_dirty` + optional remembered path); use `LoadedPeakDistanceDatasource` only after load from disk or successful save — do not use `Path("")` sentinel
- [x] 1.3 Extend `ResourceAction` in `heatmap_alignment_core.py` with `generate`, `save`, and `save_as`; gate peak-specific actions in `_resource_actions` on `kind == "radar_peak"`
- [x] 1.4 Extend `AlignmentResourceRuntime` with `peaks_dirty` (and related flags); update `build_alignment_resource_summaries` so the Status column shows **Generated (unsaved)** when appropriate and enable Generate / Save / Save as per rules

## 2. Resources window UI

- [x] 2.1 Add Generate, Save peaks, and Save peaks as… buttons; enable Save peaks when dirty, Save peaks as when peaks in memory, Generate when H5 loaded
- [x] 2.2 Implement `invoke_resource_action` handlers for `generate`, `save`, and `save_as` on `radar_peak`
- [x] 2.3 Add busy cursor and status-bar feedback during synchronous generate (no `ResourceJobManager` in v1)
- [x] 2.4 Refresh Signals plot, peak overlay, and Resources rows after generate and save

## 3. Save and path semantics

- [x] 3.1 Implement Save peaks: dialog when no path; overwrite confirm when path set; default `{h5_stem}_peak_distances.json` beside loaded H5
- [x] 3.2 Implement Save peaks as…: always dialog; enabled whenever peaks in memory
- [x] 3.3 Set `session.peak_distance_datasource.path` only after successful save; clear peaks dirty; mark session dirty when path changes; promote in-memory state to `LoadedPeakDistanceDatasource` after save
- [x] 3.4 Keep displayed path in resource row after Generate when previously set; do not write disk on Generate

## 4. Confirmations and dirty prompts

- [x] 4.1 Confirm Generate when replacing in-memory peaks; message clarifies files on disk are unchanged until save
- [x] 4.2 Confirm unload/clear Radar Peak when peaks dirty
- [x] 4.3 Blocking confirm before Reload when peaks dirty (proceed / cancel)
- [x] 4.4 Update quit, close session, and open session guards to `self._session_dirty or self._peaks_dirty`; add peaks-loss body text to the single unsaved prompt (no second modal); leave Save button behavior unchanged
- [x] 4.5 Warn on Save Session when peaks dirty
- [x] 4.6 Extend Clear All Resources confirm to mention unsaved generated peaks when peaks dirty

## 5. Tests and verification

- [x] 5.1 Add unit tests for adapter generate-from-record, in-memory vs loaded state, and peaks dirty / save path bookkeeping
- [x] 5.2 Add tests for resource summaries: Status **Generated (unsaved)**, Generate requires H5, Save peaks when dirty, Save peaks as when peaks in memory
- [x] 5.3 Grep `heatmap_alignment_gui.py` for peak load/generate conditionals that should live in the adapter only
  Note: grep of heatmap_alignment_gui.py confirms peak generate/load logic is consolidated in adapter; remaining peak references in GUI are for UI wiring, session path bookkeeping, and visibility toggle (expected).
- [ ] 5.4 Manual check: Generate → Signals update → Save peaks as → session path; Regenerate with retained path → Save overwrite confirm; Save peaks as after save (not dirty)
  Note: Implementation complete — verify manually by running: hatch run app:heatmap-alignment
