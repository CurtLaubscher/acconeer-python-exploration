## Context

The heatmap alignment GUI renders Sparse IQ heatmap frames as discrete distance/velocity bins, but several UI paths currently derive positions from first/last bin centers as if they were image edges. The Matplotlib overlay renderer already uses half-bin extents for the heatmap body, while the compact distance header and hover readout use center-to-center interpolation. H5 time lookup also differs from camera lookup by selecting the first frame timestamp at or after the requested time.

## Goals / Non-Goals

**Goals:**

- Make rendered heatmap cue placement and hover lookup use one explicit bin-edge geometry model.
- Make H5 current-time frame lookup choose the nearest recorded frame timestamp.
- Keep the fix localized and covered by focused unit tests.
- Preserve saved session compatibility and existing user workflows.

**Non-Goals:**

- Change timeline off-screen playhead behavior.
- Rework timeline track duration geometry.
- Change camera video time-to-frame lookup.
- Redesign rendered heatmap layout, labels, export styling, or peak-generation algorithms.

## Decisions

Use bin-edge extents derived from bin centers for rendered heatmap screen mapping. Distance bin centers remain the physical values reported in `axes.distances_m`, but widget x positions should map through an extent of first center minus half a bin to last center plus half a bin. Velocity mapping should follow the same displayed-image model, using the existing velocity resolution. This matches the plotted heatmap body and avoids treating a bin center as the left or right image edge.

Keep peak distances as physical center coordinates. Peak extraction already returns values from the distance axis centers, so the marker should not modify the measurement value. Only the coordinate-to-pixel projection changes.

Use nearest timestamp for H5 frame selection. Given irregular or regular H5 ticks, select the frame whose tick is closest to the requested time's tick after clamping to the recording duration. This aligns the rendered H5 frame with the user's playhead expectation and with camera lookup's nearest-frame behavior.

Prefer small helper functions over duplicated formulas. The implementation should centralize half-bin extent calculation and coordinate-to-bin lookup enough that the header, hover readout, and tests exercise the same convention without introducing a broad rendering abstraction.

## Risks / Trade-offs

- Existing tests may assert prior edge-biased positions -> update tests to assert the intended bin-center behavior directly.
- H5 frame selection changes around half-frame boundaries -> add boundary tests so the new behavior is explicit.
- Irregular H5 ticks may make a simple FPS-style calculation wrong -> compare against actual recorded ticks rather than deriving frame index from duration alone.
