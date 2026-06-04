## 1. Peak Algorithm Engine

- [ ] 1.1 Define shared non-GUI peak algorithm descriptors for `zero_velocity_slice` and `sum_velocity`, including concise labels and threshold defaults
- [ ] 1.2 Refactor `sparse_iq_peak_distance_core.py` so GUI and CLI algorithm selection call the same implementation path
- [ ] 1.3 Add a `--method` CLI argument to `export_sparse_iq_peak_distances.py` that maps to the shared `sum_velocity` default and `zero_velocity_slice` algorithm ids while preserving existing default behavior
- [ ] 1.4 Add a peak method parameter to `generate_peak_distances_from_heatmap_record(...)` and forward it to `analyze_heatmap_record(...)`
- [ ] 1.5 Fix imported metadata fallback so JSON without `peak_extraction_method` defaults to `sum_velocity`, matching existing export behavior
- [ ] 1.6 Add focused tests proving both algorithms produce expected measurements through the shared engine

## 2. Peak Series Resource Model

- [ ] 2.1 Add a peak series resource state model with id, display name, provenance, optional path, algorithm metadata, measurements, visibility, color, unsaved state, and row warnings
- [ ] 2.2 Replace single active peak state helpers with a collection of peak series resources while preserving existing camera, H5, and Leg2 state shapes
- [ ] 2.3 Add stable peak color assignment and concise default naming such as `v0 slice, thresh 650` and `sum v, thresh 650`
- [ ] 2.4 Bump `SESSION_VERSION` from `2` to `3` and add a v2-to-v3 migration that converts `peak_distance_datasource.path` into one `peak_series` entry when present
- [ ] 2.5 Ensure existing v1 sessions migrate through v1-to-v2 and then v2-to-v3 before constructing `AlignmentSession`
- [ ] 2.6 Save only imported/saved peak series references and display settings in the `peak_series` session JSON list; omit generated unsaved series without paths
- [ ] 2.7 Remove or replace `desired_peak_identity()` and the single-slot peak reconciliation logic with per-series session reconciliation

## 3. Resources Window And Menu UX

- [ ] 3.1 Update Resources terminology for touched peak actions: Import Peak Series, Generate Peak Series, Save, Save As, Reload, and Unload
- [ ] 3.2 Change Import Peak Series so accepted JSON files append peak series rows instead of replacing existing peaks
- [ ] 3.3 Add a Generate Peak Series dialog with algorithm choice, threshold, and editable concise display name
- [ ] 3.4 Implement Generate Peak Series so it appends an unsaved generated peak series row and selects it for rendered-heatmap marker display
- [ ] 3.5 Implement row-specific Save, Save As, Reload, and Unload actions for peak series
- [ ] 3.6 Keep primary Camera Video and Radar Raw (H5) load/unload actions intact and keep Leg2 as a single optional resource
- [ ] 3.7 Preserve peak series as optional signal resources when H5 is replaced, without adding a broader parent-H5 dependency system

## 4. Plotting And Heatmap Marker

- [ ] 4.1 Refactor Signals plot inputs to accept multiple visible peak series instead of one primary peak and one temporary compare series
- [ ] 4.2 Plot each visible peak series using its assigned color and concise legend label
- [ ] 4.3 Add a rendered-heatmap peak selector with `None` plus all peak series resources
- [ ] 4.4 Use only the selected peak series for rendered-heatmap and exported-overlay peak markers
- [ ] 4.5 Remove `TEMPORARY_COMPARE_PEAK_EXTRACTION_ON_SIGNAL_PLOT`, `_temporary_peak_series_for_method`, and related hardcoded comparison plot wiring
- [ ] 4.6 Reset the rendered-heatmap peak selector to `None` when the selected peak series is unloaded

## 5. Unsaved State And Persistence

- [ ] 5.1 Track unsaved state per generated peak series and show it in that row's Resources status without adding a main-window title asterisk
- [ ] 5.2 Include unsaved peak-series loss text in existing quit, close session, and open session prompts
- [ ] 5.3 Warn before saving an alignment session while generated peak series remain unsaved
- [ ] 5.4 Confirm before unloading, reloading, or clearing all resources when unsaved generated peak series would be lost
- [ ] 5.5 Ensure session save/reload restores saved/imported peak series by path and does not restore unsaved generated measurements

## 6. Tests And Verification

- [ ] 6.1 Add unit tests for peak series resource creation, import append, generate append, save path behavior, and per-row unsaved state
- [ ] 6.2 Add session migration and persistence tests for older single-peak sessions and new multi-peak session JSON
- [ ] 6.3 Add resource summary tests for multiple peak rows, row actions, status labels, warnings, and color/name assignment
- [ ] 6.4 Add focused GUI tests or integration tests for Generate dialog behavior, rendered-heatmap selector options, and row-scoped save/unload actions where practical
- [ ] 6.5 Run targeted tests with repo-managed Hatch tooling from `pyproject.toml`
- [ ] 6.6 Grep the GUI for remaining temporary compare overlay code and single active peak assumptions before marking implementation complete
