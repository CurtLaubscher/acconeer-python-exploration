## Context

The heatmap alignment GUI renders two plotted heatmap overlays through `HeatmapPlotRenderer`: a GUI overlay preview in preview-camera coordinates and the exported video overlay in original-camera coordinates. The export path scales the overlay rectangle from preview dimensions to source dimensions, but the Matplotlib plot uses fixed point-sized labels, ticks, and margins. As a result, exported labels can appear proportionally smaller than the preview when the original video is viewed at normal display size.

Viewport geometry is already moving toward original camera coordinates. This change should follow the same direction for export overlay presentation: source/original geometry is the stable basis, and lower-resolution preview is a downsampled representation of that presentation.

## Goals / Non-Goals

**Goals:**

- Make the GUI overlay preview and exported overlay use the same presentation model.
- Base presentation sizing on original camera/source-resolution overlay geometry, not only the current preview widget size.
- Centralize plot style selection so font sizes, tick sizes, line widths, and margins are not scaled independently across call sites.
- Improve small-overlay readability without changing the export video workflow.
- Keep the design compatible with future higher-resolution preview rendering.

**Non-Goals:**

- Add a full export options dialog.
- Add user-facing style presets, axes toggles, or colorbar toggles in this change.
- Change camera/H5 alignment behavior, viewport color matching, xcorr behavior, or session schema.
- Replace Matplotlib or change the Sparse IQ heatmap truth-rendering algorithm.

## Decisions

### Use Source-Space Plot Presentation As The Basis

The exported original-camera overlay is the presentation authority. Preview rendering should derive from the same source-space overlay rectangle and then render an appropriately scaled preview image. This avoids treating the current low-resolution GUI preview as the canonical layout and prepares for future high-resolution preview modes.

Alternative considered: keep preview as scale `1.0` and multiply export styling by the camera-to-preview ratio. That fixes the immediate mismatch, but it encodes the current low-resolution preview as the design basis and makes future source-resolution preview work more awkward.

### Centralize Style Derivation In The Renderer Layer

`HeatmapPlotRenderer` should accept enough context to apply one source-space plot style and scale that style for lower-resolution preview rendering. The shared style should cover labels, tick labels, tick lengths, axis line widths, image interpolation, and subplot margins. Call sites should not manually scale individual Matplotlib properties.

Alternative considered: scale only `tick_params(labelsize=...)` during export. That is smaller, but it leaves margins, labels, tick marks, and future style properties inconsistent.

### Use Explicit Source-Space Defaults Instead Of Auto-Growing With Overlay Size

The default source-space plot style should be explicit, for example fixed font, tick, line, and source-space pixel margin values used by export/source rendering. Preview should scale those values by the render-to-source ratio. The implementation should not grow font sizes or margins automatically as the export overlay gets larger; future user-configurable plot styling can replace these defaults directly.

Alternative considered: compute source font sizes from overlay dimensions with upper and lower clamps. That preserved parity after preview scaling, but it made normal output dependent on hidden saturation thresholds and would fight a future user-controlled font size setting.

### Scale Margins Like Other Source-Space Style Values

Margins should be defined as source-space pixel defaults, then scaled for lower-resolution preview rendering in the same way as fonts, tick marks, and line widths. Matplotlib requires fractional subplot margins, so the renderer should convert the scaled pixel margins into fractions for the actual render size. Compact overlays may shrink margins enough to preserve a valid plot body, but normal overlays should not allocate whitespace as a fixed percentage of overlay size.

### Keep Presentation Settings Internal For This Change

This proposal should establish parity and readable defaults first. Axes visibility, colorbar visibility, compact/full modes, and export quality controls are related but should be proposed separately so this change remains easy to review and validate.

Alternative considered: include axes/colorbar toggles now. That expands UI, persistence, and testing surface before the core presentation model is stable.

## Risks / Trade-offs

- Source-space styling may make the current low-resolution preview text look slightly smaller or tighter than before. Mitigation: choose readable source-space defaults and scale preview from them consistently.
- Exact pixel parity is unrealistic because preview and export are rendered at different resolutions and then viewed/scaled differently. Mitigation: require matching visual proportions rather than byte-identical images.
- Matplotlib layout can clip labels if margins are too aggressive. Mitigation: keep margins in the shared source-space style, convert them consistently for each render size, and cover compact overlays in tests.
- Rendering more carefully sized figures may expose performance cost during scrubbing. Mitigation: keep the existing overlay preview freeze behavior while dragging and reuse renderer/canvas rebuilds only when output size or style context changes.
