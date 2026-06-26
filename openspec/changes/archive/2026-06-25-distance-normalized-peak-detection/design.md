## Context

The heatmap alignment tool detects peaks in Sparse IQ recordings using `sparse_iq_peak_distance_core.py`. Two algorithms exist: `sum_velocity` and `zero_velocity_slice`. Both apply a flat scalar threshold to raw FFT magnitude and produce only a scalar result per frame — no spatial information about which distance bins are near or above threshold is preserved.

The analysis script `user_tools/plot_sparse_iq_strength_analysis.py` already implements a working distance-varying normalization: `threshold_curve(d) = max(threshold_max * (1 - d / reference_distance_m), threshold_min)`. This design adds that as a third algorithm and unifies all three algorithms around a shared **per-bin detection ratio** concept, enabling a new spatial overlay in the renderer.

## Goals / Non-Goals

**Goals:**
- Add `distance_normalized` as a third peak extraction algorithm
- Unify all three algorithms: each produces a `detection_ratio` array (`profile / threshold_at_bin`) stored on `FrameDetectionMeasurement`
- Reuse `_strongest_peak_from_distance_profile()` unchanged — all algorithms pass it a ratio profile with `threshold=1.0`
- Add a thin detection strip above the heatmap showing the `detection_ratio` array for the active series — a Qt widget in the live panel, GridSpec strip in the export renderer
- Rename "peak" terminology to "detection" throughout types, functions, and UI labels
- Rename `peak_distance_m` → `target_distance_m`, `candidate_peak_distance_m` → `candidate_distance_m`

**Non-Goals:**
- Changing the signals plot (distance vs. time) — it is unaffected
- Displaying hover values for algorithms other than the active detection series
- Persisting per-session defaults for new parameters
- Renaming the Python files themselves (symbol renames only)

## Decisions

### D1: Per-bin detection ratio is the universal currency

All three algorithms normalize their 1D distance profile by their threshold before any detection logic:
- `sum_velocity`: `ratio = sum_profile / scalar_threshold`
- `zero_velocity_slice`: `ratio = zero_slice_profile / scalar_threshold`
- `distance_normalized`: `ratio = sum_profile / threshold_curve(distances_m)`

Detection is then `ratio[argmax] > 1.0` for all three. `_strongest_peak_from_distance_profile()` is called with `threshold=1.0` in all cases — zero changes to that function. The `detection_ratio` array is stored on `FrameDetectionMeasurement` for use by the renderer.

Alternative: only store ratio for `distance_normalized`, keep raw for others. Rejected — forces renderer to know which algorithm produced which measurement; violates DRY since the ratio would be recomputed at render time.

### D2: `FrameDetectionMeasurement` stores `detection_ratio: np.ndarray`

The full per-bin ratio array is stored alongside the scalar `target_distance_m`. This is the only place it's computed; the renderer receives it directly with no recomputation.

Memory note: at ~50–200 distance bins per frame and thousands of frames, storing float64 arrays is non-trivial. Using float32 and only storing for the active display series (not all series) could be a future optimization; for now store for all.

### D3: Two-surface strip — Qt widget for live panel, GridSpec for export

The detection strip is rendered on two separate surfaces:

**Live panel (`DetectionStripWidget`):** A thin fixed-height Qt widget inserted into the `rendered_heatmap_layout` between the distance header and `truth_view`. It uses `paintEvent` with `detection_ratio_strip_rgb()` to draw a scaled colorbar. Height is fixed in pixels and independent of velocity bin count — this is critical because `truth_view` renders the raw DVM frame which can be as small as 1 velocity bin tall, so any approach proportional to the frame would be swallowed.

**Export overlay (`HeatmapPlotRenderer`):** Refactored from `add_subplot(111)` to a 2-row GridSpec: a thin strip row on top, the heatmap below. The strip shares the x-axis with the heatmap. Strip height is proportional to total figure height, which is acceptable for export since the frame size is not a constraint.

Alternative of prepending rows to the raw numpy frame before passing to `truth_view`: rejected — strip height would be proportional to velocity bin count, producing an unusable strip with 1-bin trials and an oversized one with many bins.

### D4: Strip renders blank when no active detection series

Both surfaces clear to blank when no detection series is active. `render_frame()` accepts an optional `detection_ratio: np.ndarray | None` parameter — when `None`, the GridSpec strip is left blank. `DetectionStripWidget.set_detection_ratio(None)` produces an empty widget with no paint output. When a ratio array is provided, both surfaces draw the threshold-split colormap from `plot_sparse_iq_strength_analysis.py` — below 1.0 is cool, above 1.0 is warm.

### D5: "Detection Algorithm" dropdown drives strip

The existing "Peak Marker" dropdown (renamed "Detection Algorithm") already selects the active series. That same selection drives which series' `detection_ratio` is passed to the renderer. Consistent with existing marker behavior — no new UI element needed.

### D6: Terminology rename — symbols only, not files

`FramePeakMeasurement` → `FrameDetectionMeasurement`, `PeakDistanceSeries` → `DetectionSeries`, `PeakDistanceMetadata` → `DetectionMetadata`, `PeakDistanceExportResult` → `DetectionExportResult`, `PeakDistanceSignalSeries` → `DetectionSignalSeries`, `GeneratePeakSeriesDialog` → `GenerateDetectionSeriesDialog`, `generate_peak_distances_from_heatmap_record` → `generate_detection_series_from_heatmap_record`. File names unchanged to minimize git history noise.

### D7: Default values match `plot_sparse_iq_strength_analysis.py`

`threshold_max=1250.0`, `threshold_min=300.0`, `reference_distance_m=0.700` — consistent defaults make tool output directly comparable to the analysis script.

### D8: Hover tooltip shows detection ratio for the active series at the hovered distance bin

The existing hover tooltip shows magnitude at the hovered (distance, velocity) bin. When a detection series is active, a `Detection ratio: {value:.2f}` line is appended, looked up from the active series' `FrameDetectionMeasurement.detection_ratio[dist_bin_idx]` for the current frame. The ratio is per-distance-bin (summed over velocity), so it is the same regardless of which velocity the user hovers at — the label makes this clear.

When no series is active, the line is omitted.

## Risks / Trade-offs

- Storing `detection_ratio` arrays on all measurements increases memory usage. → Acceptable for now; optimize later if needed.
- GridSpec refactor touches `HeatmapPlotRenderer` margins math (`derive_presentation()`, `subplots_adjust()`). → Careful but bounded change; strip height is proportional so it scales correctly at small preview sizes.
- `detection_ratio` semantics differ slightly between algorithms (flat vs. curved threshold), but the renderer treats them identically. → This is intentional and the right abstraction.

## Open Questions

None.
