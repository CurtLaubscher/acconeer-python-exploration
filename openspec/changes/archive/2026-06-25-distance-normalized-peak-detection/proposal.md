## Why

The heatmap alignment tool's peak detection uses a flat absolute threshold, but radar signal strength falls off with distance — so a threshold that filters noise at 0.2m will miss real detections at 0.6m. A distance-varying normalization makes the threshold physically meaningful (ratio > 1.0 = detected, regardless of distance). Additionally, the existing "Peak Marker" overlay only shows a single scalar distance; there is no at-a-glance view of where across the full distance range the signal exceeds threshold for a given frame.

## What Changes

- Add a third peak extraction algorithm `distance_normalized`: normalizes the summed-velocity profile by a distance-varying threshold curve; detection threshold is always 1.0
- All three algorithms now compute and store a **per-bin detection ratio** (`profile / threshold_at_bin`) in `FrameDetectionMeasurement`, enabling downstream use without recomputation
- The rendered heatmap gains a **thin detection strip** above the heatmap showing the per-bin detection ratio for the active detection series — all three algorithms populate it; the live panel uses a separate Qt widget stacked above `truth_view`, the video export overlay uses a GridSpec strip inside `HeatmapPlotRenderer`
- Rename all "peak" terminology in types and UI to "detection" to better reflect intent: `FramePeakMeasurement` → `FrameDetectionMeasurement`, `PeakDistanceSeries` → `DetectionSeries`, etc.
- Rename the "Peak Marker" dropdown in the rendered heatmap panel to **"Detection Algorithm"**
- Rename `peak_distance_m` / `candidate_peak_distance_m` fields to `target_distance_m` / `candidate_distance_m`

## Capabilities

### New Capabilities

- `distance-normalized-peak-detection`: Third peak extraction algorithm with distance-varying threshold curve and tunable parameters (`threshold_max`, `threshold_min`, `reference_distance_m`)
- `detection-ratio-strip`: Thin strip rendered above the heatmap showing per-bin detection ratio for the active detection series; present for all three algorithms

### New Capabilities (bootstrapped)

- `peak-series-generation`: Generates a detection series from a heatmap recording; supports three algorithms (`sum_velocity`, `zero_velocity_slice`, `distance_normalized`); all algorithms produce a per-bin detection ratio array alongside the scalar result; terminology updated from "peak series" to "detection series"

## Impact

- `user_tools/sparse_iq_peak_distance_core.py`: New algorithm, new constants, `FramePeakMeasurement` → `FrameDetectionMeasurement` with `detection_ratio` array field, field renames
- `user_tools/heatmap_peak_distance_resource.py`: Type renames, `algorithm_params` and `default_generated_name()` updated, `generate_peak_distances_from_heatmap_record()` → `generate_detection_series_from_heatmap_record()`
- `user_tools/heatmap_alignment_core.py`: `HeatmapPlotRenderer` refactored to GridSpec layout; new `_draw_detection_strip()` method; `render_frame()` accepts `detection_ratio` array; `PeakDistanceSignalSeries` → `DetectionSignalSeries`; `detection_ratio_strip_rgb()` helper added for Qt widget use
- `user_tools/heatmap_alignment_widgets.py`: New `DetectionStripWidget` — a thin fixed-height Qt widget that renders the detection ratio colorbar above `truth_view` in the live panel
- `user_tools/heatmap_alignment_dialogs.py`: `GeneratePeakSeriesDialog` → `GenerateDetectionSeriesDialog`; new conditional spinboxes for `distance_normalized`
- `user_tools/heatmap_alignment_gui.py`: All call sites updated for renames; "Peak Marker" label → "Detection Algorithm"; passes `detection_ratio` through to renderer
