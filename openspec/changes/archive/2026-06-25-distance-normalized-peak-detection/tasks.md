## 1. Terminology Rename

- [x] 1.1 Rename `FramePeakMeasurement` → `FrameDetectionMeasurement` and `peak_distance_m` → `target_distance_m`, `candidate_peak_distance_m` → `candidate_distance_m` in `sparse_iq_peak_distance_core.py`; update all references in `user_tools/`
- [x] 1.2 Rename `PeakDistanceMetadata` → `DetectionMetadata`, `PeakDistanceExportResult` → `DetectionExportResult` in `sparse_iq_peak_distance_core.py`; update all references
- [x] 1.3 Rename `PeakDistanceSignalSeries` → `DetectionSignalSeries` in `heatmap_alignment_core.py`; update all references
- [x] 1.4 Rename `PeakDistanceSeries` → `DetectionSeries` and `generate_peak_distances_from_heatmap_record` → `generate_detection_series_from_heatmap_record` in `heatmap_peak_distance_resource.py`; update all references
- [x] 1.5 Rename `GeneratePeakSeriesDialog` → `GenerateDetectionSeriesDialog` in `heatmap_alignment_dialogs.py`; update all references
- [x] 1.6 Update the "Peak Marker" UI label to "Detection Algorithm" in `heatmap_alignment_gui.py`

## 2. Per-Bin Detection Ratio

- [x] 2.1 Add `detection_ratio: np.ndarray` field to `FrameDetectionMeasurement`
- [x] 2.2 Update `_strongest_peak_from_distance_profile()` to accept and return the ratio profile (it already computes argmax on a profile — now that profile is always a ratio)
- [x] 2.3 Update `sum_velocity` path: compute `ratio = sum_profile / threshold` before calling `_strongest_peak_from_distance_profile()`; store `ratio` on measurement
- [x] 2.4 Update `zero_velocity_slice` path: compute `ratio = zero_slice_profile / threshold`; store `ratio` on measurement
- [x] 2.5 Update `analyze_heatmap_record()` to populate `detection_ratio` on each `FrameDetectionMeasurement`

## 3. Distance-Normalized Algorithm

- [x] 3.1 Add `PEAK_EXTRACTION_METHOD_DISTANCE_NORMALIZED = "distance_normalized"` and default constants `DEFAULT_DIST_NORM_THRESHOLD_MAX=1250.0`, `DEFAULT_DIST_NORM_THRESHOLD_MIN=300.0`, `DEFAULT_DIST_NORM_REFERENCE_DISTANCE_M=0.700` to `sparse_iq_peak_distance_core.py`
- [x] 3.2 Implement `strongest_peak_distance_normalized(dvm, distances_m, *, threshold_max, threshold_min, reference_distance_m)` — compute threshold curve, compute ratio, call `_strongest_peak_from_distance_profile()` with `threshold=1.0`
- [x] 3.3 Update `_extract_strongest_peak()` dispatch to handle `distance_normalized`, passing `distances_m` and the three params through
- [x] 3.4 Update `analyze_heatmap_record()` to accept `threshold_max`, `threshold_min`, `reference_distance_m` kwargs and thread them into dispatch

## 4. Resource Layer

- [x] 4.1 Update `generate_detection_series_from_heatmap_record()` to accept and pass through `threshold_max`, `threshold_min`, `reference_distance_m` kwargs
- [x] 4.2 Update `DetectionMetadata` to include optional `threshold_max`, `threshold_min`, `reference_distance_m` fields
- [x] 4.3 Update `algorithm_params` dict population to store the three new params for `distance_normalized` series
- [x] 4.4 Add `distance_normalized` name pattern to `default_generated_name()`, e.g. `"dist norm, ref {reference_distance_m:.2f}m"`

## 5. Dialog UI

- [x] 5.1 Add `"dist normalized"` entry to the algorithm combo box in `GenerateDetectionSeriesDialog`
- [x] 5.2 Add three `QDoubleSpinBox` widgets for `threshold_max`, `threshold_min`, `reference_distance_m` with appropriate ranges and defaults
- [x] 5.3 Wire `currentIndexChanged` on the combo to show/hide the three spinboxes based on selected algorithm
- [x] 5.4 Expose the three values as properties on `GenerateDetectionSeriesDialog`

## 6. Renderer — GridSpec Refactor

- [x] 6.1 Refactor `HeatmapPlotRenderer` from `add_subplot(111)` to a 2-row `GridSpec` with height ratios approximately `[1, 12]` (strip ~8%, heatmap ~92%); update `derive_presentation()` and `subplots_adjust()` margin math accordingly
- [x] 6.2 Add `_strip_ax` as a second axes sharing the x-axis with `_ax`; add `_strip_image` artist initialized to blank
- [x] 6.3 Update `render_frame()` signature to accept `detection_ratio: np.ndarray | None = None`
- [x] 6.4 Implement `_draw_detection_strip(detection_ratio)` — draws a 1-row `pcolormesh` on `_strip_ax` using the threshold-split colormap from `plot_sparse_iq_strength_analysis.py`; clears to blank when `detection_ratio` is None
- [x] 6.5 Call `_draw_detection_strip()` from `render_frame()`

## 7. Hover Tooltip

- [x] 7.1 Update `_refresh_hover_tooltip()` in `heatmap_alignment_gui.py` to look up the active series' `FrameDetectionMeasurement` for the current frame and append `Detection ratio: {value:.2f}` using `detection_ratio[dist_bin_idx]` when a series is active
- [x] 7.2 Ensure the dist_bin_idx lookup maps the hovered pixel's distance coordinate to the correct index in `detection_ratio` (same distance axis as the heatmap)

## 8. Caller Wiring

- [x] 8.1 Update `_peak_overlay_for_frame()` in `heatmap_alignment_gui.py` to also return `detection_ratio` from the active series measurement (extend tuple or use a small dataclass)
- [x] 8.2 Update live preview render call to pass `detection_ratio` to `render_frame()`
- [x] 8.3 Update video export render call to pass `detection_ratio` to `render_frame()`
- [x] 8.4 Update `_generate_peak_series()` call site to read the three new dialog properties and pass them to `generate_detection_series_from_heatmap_record()`
