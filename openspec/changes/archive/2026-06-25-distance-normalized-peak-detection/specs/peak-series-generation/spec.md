## NEW Requirements

### Requirement: Peak extraction algorithm selection
The system SHALL offer three peak extraction algorithms in the Generate Detection Series dialog: `sum_velocity` (labeled `"sum v"`), `zero_velocity_slice` (labeled `"v0 slice"`), and `distance_normalized` (labeled `"dist normalized"`).

#### Scenario: All three algorithms available
- **WHEN** the Generate Detection Series dialog is opened
- **THEN** the algorithm combo box SHALL contain exactly three options: `"sum v"`, `"v0 slice"`, and `"dist normalized"`

#### Scenario: sum_velocity algorithm selected
- **WHEN** user selects `"sum v"` and confirms
- **THEN** peak detection SHALL use the sum-over-velocity method with a flat scalar threshold, and `detection_ratio` SHALL be `sum_profile / threshold`

#### Scenario: zero_velocity_slice algorithm selected
- **WHEN** user selects `"v0 slice"` and confirms
- **THEN** peak detection SHALL use the zero-velocity slice method with a flat scalar threshold, and `detection_ratio` SHALL be `zero_slice_profile / threshold`

#### Scenario: distance_normalized algorithm selected
- **WHEN** user selects `"dist normalized"` and confirms
- **THEN** peak detection SHALL use the distance-normalized method, and `detection_ratio` SHALL be `sum_profile / threshold_curve(distances_m)`

### Requirement: Per-bin detection ratio stored on each measurement
Each `FrameDetectionMeasurement` SHALL carry a `detection_ratio` array of shape `(n_distance_bins,)` containing the per-bin ratio of signal profile to threshold at each distance bin.

For all algorithms, a ratio > 1.0 at a bin means the signal exceeds threshold at that distance.

#### Scenario: Detection ratio available after generation
- **WHEN** a detection series is generated with any algorithm
- **THEN** each `FrameDetectionMeasurement` SHALL have a non-None `detection_ratio` array with length equal to the number of distance bins

### Requirement: "Detection Algorithm" dropdown replaces "Peak Marker"
The rendered heatmap panel's dropdown for selecting the active detection series SHALL be labeled **"Detection Algorithm"** (previously "Peak Marker"). It SHALL continue to drive both the triangle distance marker and the detection ratio strip.

#### Scenario: Dropdown drives strip and marker
- **WHEN** a detection series is selected in the "Detection Algorithm" dropdown
- **THEN** both the triangle marker and the detection ratio strip SHALL reflect that series' data for the current frame

### Requirement: Hover tooltip shows detection ratio for active series
When hovering over the rendered heatmap and a detection series is active, the hover tooltip SHALL include a `Detection ratio` line showing the per-bin ratio from the active series' measurement at the hovered distance bin for the current frame.

The detection ratio SHALL be the same value regardless of which velocity bin is hovered at that distance.

When no detection series is active, the `Detection ratio` line SHALL be omitted from the tooltip.

#### Scenario: Hover with active detection series
- **WHEN** the user hovers over the heatmap at distance bin `d` and a detection series is active
- **THEN** the tooltip SHALL show `Detection ratio: {value:.2f}` using `detection_ratio[d]` from the current frame's measurement

#### Scenario: Hover with no active detection series
- **WHEN** the user hovers over the heatmap and no detection series is selected
- **THEN** the tooltip SHALL NOT include a detection ratio line

### Requirement: Terminology updated from "peak" to "detection"
Internal type names SHALL use "detection" rather than "peak":
- `FramePeakMeasurement` → `FrameDetectionMeasurement`
- `PeakDistanceSeries` → `DetectionSeries`
- `PeakDistanceMetadata` → `DetectionMetadata`
- `PeakDistanceExportResult` → `DetectionExportResult`
- `PeakDistanceSignalSeries` → `DetectionSignalSeries`
- `GeneratePeakSeriesDialog` → `GenerateDetectionSeriesDialog`
- `generate_peak_distances_from_heatmap_record` → `generate_detection_series_from_heatmap_record`
- Field `peak_distance_m` → `target_distance_m`
- Field `candidate_peak_distance_m` → `candidate_distance_m`

#### Scenario: No public API breakage
- **WHEN** the renames are applied
- **THEN** all call sites within `user_tools/` SHALL be updated and no references to old names SHALL remain
