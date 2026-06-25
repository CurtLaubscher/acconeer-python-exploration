## Purpose

Provide a distance-normalized peak extraction algorithm that applies a distance-varying threshold curve, making detection threshold physically uniform (ratio > 1.0 = detected) regardless of distance. Includes a per-bin detection ratio strip visible above the heatmap in both the live panel and video export.

## Requirements

### Requirement: Distance-normalized algorithm

The system SHALL provide a `distance_normalized` peak extraction algorithm that normalizes the summed-velocity profile by a threshold curve that decreases linearly with distance.

#### Scenario: Threshold curve applied

- **GIVEN** `threshold_max`, `threshold_min`, and `reference_distance_m` are configured
- **WHEN** the distance-normalized algorithm processes a frame
- **THEN** each distance bin's threshold is `max(threshold_max * (1 - d / reference_distance_m), threshold_min)`, and detection is `ratio[argmax] > 1.0`

#### Scenario: Default parameters match analysis script

- **WHEN** the distance-normalized algorithm is selected with no parameter override
- **THEN** defaults are `threshold_max=1250.0`, `threshold_min=300.0`, `reference_distance_m=0.700`, matching `plot_sparse_iq_strength_analysis.py`

### Requirement: Detection ratio strip in live panel

The system SHALL display a thin detection ratio colorbar above the rendered heatmap in the live panel, independent of velocity bin count.

#### Scenario: Strip visible with active detection series

- **GIVEN** a detection series has been generated or loaded with detection ratio data
- **WHEN** the user scrubs to a frame
- **THEN** a thin strip above the heatmap shows per-bin detection ratio using a cool colormap below 1.0 and a warm colormap above 1.0

#### Scenario: Strip blank with no active series

- **WHEN** no detection series is active
- **THEN** the strip area is blank

#### Scenario: Strip height independent of velocity bins

- **WHEN** the heatmap recording has any number of velocity bins (including 1)
- **THEN** the strip height is fixed and does not scale with the velocity axis

### Requirement: Detection ratio strip in video export

The system SHALL include the detection ratio strip in exported videos via a GridSpec layout inside `HeatmapPlotRenderer`.

#### Scenario: Strip rendered in export overlay

- **GIVEN** a detection series with ratio data is active during video export
- **WHEN** a frame is rendered for export
- **THEN** the export overlay includes a thin strip above the heatmap showing the same threshold-split colormap as the live panel

### Requirement: Detection ratio in hover tooltip

The system SHALL show the per-bin detection ratio value at the hovered distance in the heatmap hover tooltip when a detection series is active.

#### Scenario: Tooltip shows ratio

- **GIVEN** a detection series is active and the user hovers over the rendered heatmap
- **THEN** the tooltip appends `Detection ratio: {value:.2f}` for the distance bin at the hovered position
