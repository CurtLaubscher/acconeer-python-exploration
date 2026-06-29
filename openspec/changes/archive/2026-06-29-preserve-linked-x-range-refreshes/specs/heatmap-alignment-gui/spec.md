## ADDED Requirements

### Requirement: Preview synchronization preserves timeline x-range by default
The heatmap alignment GUI SHALL preserve the current shared timeline x-range during preview synchronization unless the caller explicitly requests a range reset. Preview synchronization that updates camera frames, heatmap frames, viewport previews, export overlay previews, current-time indicators, signal plots, resource rows, labels, or source-resolution viewport state SHALL NOT recompute the shared x-range by default.

#### Scenario: Plain preview refresh preserves zoom
- **WHEN** the workbench performs a preview refresh after the user has zoomed or panned the shared x-range
- **THEN** the shared x-range remains unchanged

#### Scenario: Source-resolution viewport result preserves zoom
- **WHEN** a source-resolution viewport worker result arrives after the user has zoomed or panned the shared x-range
- **THEN** the shared x-range remains unchanged

#### Scenario: Render and viewport display changes preserve zoom
- **WHEN** the user changes color limits, viewport corners, viewport visibility settings, export overlay settings, heatmap peak marker selection, Leg2 signal kind, or plotted signal visibility
- **THEN** the shared x-range remains unchanged

### Requirement: Resource mutations preserve timeline x-range
Resource load, reload, replace, unload, and background completion SHALL update resource state and displayed data without changing the current shared x-range. This applies to Camera Video, Radar Raw (H5), Radar Peak series, and Leg2 MAT resources. Clearing all resources while the current session remains open SHALL also preserve the current shared x-range.

#### Scenario: H5 load completion preserves zoom
- **WHEN** a Radar Raw (H5) background load completes after the user has zoomed or panned the shared x-range
- **THEN** the shared x-range remains unchanged

#### Scenario: Camera load completion preserves zoom
- **WHEN** a Camera Video background load completes after the user has zoomed or panned the shared x-range
- **THEN** the shared x-range remains unchanged

#### Scenario: Resource unload preserves zoom
- **WHEN** the user unloads Camera Video, Radar Raw (H5), Radar Peak series, or Leg2 MAT resources
- **THEN** the shared x-range remains unchanged

#### Scenario: Clear all resources preserves zoom
- **WHEN** the user clears all resources while keeping the current session open
- **THEN** the shared x-range remains unchanged

### Requirement: Session lifecycle controls timeline x-range resets
Opening or loading a session SHALL recompute the shared x-range from that session's resource domain and SHALL use the same behavior whether the workbench previously had no session resources or a different session loaded. Closing the session or resetting to a new empty session SHALL reset the shared x-range to the blank/default range `0..60 s`. The system SHALL NOT persist the current shared x-range in alignment session JSON as part of this behavior.

#### Scenario: Open session recomputes range
- **WHEN** the user opens an alignment session
- **THEN** the shared x-range recomputes from the opened session's loaded or requested resource domain

#### Scenario: Open session from populated workbench uses same range behavior
- **WHEN** the user opens an alignment session while another session or resources are already loaded
- **THEN** the shared x-range behavior matches opening the same session from an empty workbench

#### Scenario: Close session resets to blank range
- **WHEN** the user closes the current session and returns to an untitled empty workbench
- **THEN** the shared x-range resets to `0..60 s`

#### Scenario: Session save omits shared x-range
- **WHEN** the user saves an alignment session after zooming or panning
- **THEN** the saved session does not persist the current shared x-range
