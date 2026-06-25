## Purpose

Generate a per-frame detection series from a Sparse IQ heatmap recording, supporting multiple peak extraction algorithms. Each measurement includes a scalar target distance and a per-bin detection ratio array.

## Requirements

### Requirement: Generate detection series from heatmap recording

The system SHALL generate a detection series by analyzing each frame of a loaded H5 heatmap recording using the selected algorithm and threshold parameters.

#### Scenario: Generate with sum-velocity algorithm

- **GIVEN** an H5 heatmap recording is loaded
- **WHEN** the user selects the `sum_velocity` algorithm and triggers generation
- **THEN** the system sums the distance-velocity map over the velocity axis, divides by the flat threshold to produce a per-bin ratio, and records the peak detection result for each frame

#### Scenario: Generate with zero-velocity-slice algorithm

- **GIVEN** an H5 heatmap recording is loaded
- **WHEN** the user selects the `zero_velocity_slice` algorithm and triggers generation
- **THEN** the system extracts the zero-velocity row of the distance-velocity map, divides by the flat threshold to produce a per-bin ratio, and records the peak detection result for each frame

#### Scenario: Generate with distance-normalized algorithm

- **GIVEN** an H5 heatmap recording is loaded
- **WHEN** the user selects the `distance_normalized` algorithm and triggers generation with `threshold_max`, `threshold_min`, and `reference_distance_m` parameters
- **THEN** the system computes a distance-varying threshold curve (`max(threshold_max * (1 - d / reference_distance_m), threshold_min)`), divides the summed-velocity profile by this curve to produce a per-bin ratio, and records the peak detection result for each frame

### Requirement: Per-bin detection ratio stored on each measurement

The system SHALL store a per-bin detection ratio array (`profile / threshold_at_bin`) on each `FrameDetectionMeasurement`, available for downstream rendering without recomputation.

#### Scenario: Detection ratio present after generation

- **GIVEN** a detection series has been generated with any algorithm
- **WHEN** a frame measurement is accessed
- **THEN** `measurement.detection_ratio` is a 1D array with one value per distance bin, where values above 1.0 indicate detected signal

### Requirement: Detection status derived from ratio

The system SHALL mark a frame as detected when the maximum detection ratio exceeds 1.0.

#### Scenario: Frame marked detected

- **GIVEN** a detection series has been generated
- **WHEN** the peak ratio at the argmax distance bin exceeds 1.0
- **THEN** `measurement.status` is `STATUS_DETECTED` and `measurement.target_distance_m` is populated

#### Scenario: Frame marked not detected

- **GIVEN** a detection series has been generated
- **WHEN** no distance bin ratio exceeds 1.0
- **THEN** `measurement.status` is not `STATUS_DETECTED` and `measurement.target_distance_m` is None
