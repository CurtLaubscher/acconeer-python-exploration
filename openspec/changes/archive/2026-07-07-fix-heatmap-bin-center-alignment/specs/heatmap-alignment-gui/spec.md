## ADDED Requirements

### Requirement: Rendered heatmap bin-edge coordinate mapping
The system SHALL map rendered heatmap distance and velocity cues through displayed heatmap bin-edge extents derived from the heatmap bin centers.

For a distance axis with more than one bin, the displayed distance extent SHALL run from the first distance center minus half the representative bin spacing to the last distance center plus half the representative bin spacing. For a single distance bin, the system SHALL use a finite fallback spacing so the bin center maps to the center of the displayed heatmap body. Velocity coordinate mapping SHALL follow the same displayed heatmap body convention using the heatmap velocity bins and resolution.

#### Scenario: Peak indicator aligns with bin center
- **WHEN** the selected peak distance equals the first rendered heatmap distance-bin center
- **THEN** the compact rendered-heatmap peak position indicator is drawn at the center of the first displayed distance bin rather than at the left edge of the heatmap body

#### Scenario: Peak indicator aligns with last bin center
- **WHEN** the selected peak distance equals the last rendered heatmap distance-bin center
- **THEN** the compact rendered-heatmap peak position indicator is drawn at the center of the last displayed distance bin rather than at the right edge of the heatmap body

#### Scenario: Hover lookup uses displayed bin geometry
- **WHEN** the pointer hovers over the rendered heatmap body
- **THEN** the hover readout distance, velocity, and magnitude are resolved using the displayed bin-edge geometry so each displayed heatmap bin reports the physical coordinate and magnitude for that bin

#### Scenario: Hover readout remains stable at bin centers
- **WHEN** the pointer is positioned at the screen center of a displayed heatmap bin
- **THEN** the hover readout reports that bin's distance and velocity center values and reads magnitude from that same bin

#### Scenario: Detection strip aligns with heatmap body
- **WHEN** the rendered heatmap body and detection strip are visible
- **THEN** the displayed heatmap body has no additional frame or border inset that shifts it relative to the detection strip or compact peak position indicator

### Requirement: Nearest H5 frame selection
The system SHALL select the H5 heatmap frame whose recorded timestamp is nearest to the requested H5 time after clamping the requested time to the H5 recording duration.

#### Scenario: Select current frame before midpoint to next frame
- **WHEN** the requested H5 time falls after a frame timestamp but before the midpoint to the following frame timestamp
- **THEN** the system renders the earlier frame

#### Scenario: Select next frame after midpoint
- **WHEN** the requested H5 time falls after the midpoint between two adjacent frame timestamps
- **THEN** the system renders the later frame

#### Scenario: Clamp before first frame
- **WHEN** the requested H5 time is before the start of the H5 recording
- **THEN** the system renders the first H5 frame

#### Scenario: Clamp after last frame
- **WHEN** the requested H5 time is after the end of the H5 recording
- **THEN** the system renders the last H5 frame
