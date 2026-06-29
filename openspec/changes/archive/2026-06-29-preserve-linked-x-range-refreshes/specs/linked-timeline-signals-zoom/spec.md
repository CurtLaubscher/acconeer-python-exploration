## ADDED Requirements

### Requirement: Non-navigation refreshes preserve shared x-range
The system SHALL preserve the current shared x-range for refreshes that are not direct timeline navigation and are not explicit range-reset operations. Resource load, reload, replace, unload, clear-all-resources, async worker completion, preview refresh, render setting changes, viewport changes, export overlay changes, peak selector changes, Leg2 signal changes, signal data refreshes, playback, and playhead scrubbing SHALL NOT recompute the shared x-range.

#### Scenario: Async resource completion preserves zoom
- **WHEN** a camera or H5 resource load finishes after the user has zoomed or panned the shared x-range
- **THEN** the shared x-range remains unchanged

#### Scenario: Resource unload preserves zoom
- **WHEN** the user unloads a camera, H5, Leg2, or peak-series resource
- **THEN** the shared x-range remains unchanged

#### Scenario: Display-only refresh preserves zoom
- **WHEN** the user changes render, viewport, export overlay, peak selector, Leg2 signal, or signal visibility settings
- **THEN** the shared x-range remains unchanged

#### Scenario: Clear all resources preserves zoom
- **WHEN** the user clears all loaded resources while keeping the current session open
- **THEN** the shared x-range remains unchanged

#### Scenario: Out-of-window data does not force fit
- **WHEN** a resource operation leaves all timeline tracks outside the current visible x-range
- **THEN** the shared x-range remains unchanged and the user may use "Zoom to Fit" to bring tracks into view

## MODIFIED Requirements

### Requirement: Zoom to Fit resets the time range
A "Zoom to Fit" action on the time axis SHALL reset the shared x-range to show the full recording span with padding. It SHALL be accessible from the timeline right-click menu and from the Signals plot X Axis submenu. When there are no loaded resources with a meaningful recording span, "Zoom to Fit" SHALL reset the shared x-range to the blank/default range `0..60 s`.

#### Scenario: Zoom to Fit from timeline context menu
- **WHEN** the user right-clicks the timeline and selects "Zoom to Fit"
- **THEN** the shared x-range resets to the full recording span and both the timeline and Signals plot show everything

#### Scenario: Zoom to Fit from Signals plot X Axis menu
- **WHEN** the user right-clicks the Signals plot and selects "Zoom to Fit" from the X Axis submenu
- **THEN** the shared x-range resets to the full recording span and both views update

#### Scenario: Zoom to Fit with no loaded resources
- **WHEN** the user invokes "Zoom to Fit" and no loaded resources have a meaningful recording span
- **THEN** the shared x-range resets to `0..60 s`
