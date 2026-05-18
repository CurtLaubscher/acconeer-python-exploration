## 1. Renderer Style Model

- [ ] 1.1 Add an internal overlay plot style model that derives font sizes, tick sizes, line widths, and margins from source-space overlay dimensions plus actual render dimensions.
- [ ] 1.2 Update `HeatmapPlotRenderer` to apply the derived style consistently when rebuilding the Matplotlib canvas.
- [ ] 1.3 Add bounded style limits so compact overlays keep labels, ticks, margins, and heatmap body inside the overlay image without one-off call-site scaling.

## 2. Preview And Export Wiring

- [ ] 2.1 Pass source-space overlay dimensions or equivalent presentation context into the GUI overlay preview renderer.
- [ ] 2.2 Pass the same presentation context into the export overlay renderer so export is the source-resolution presentation authority.
- [ ] 2.3 Preserve existing overlay geometry, export duration, FPS selection, progress handling, and session persistence behavior.

## 3. Verification

- [ ] 3.1 Add focused tests or renderer-level checks that preview and export derive matching plot style proportions from the same overlay geometry.
- [ ] 3.2 Add coverage for compact overlay dimensions to verify derived style bounds and preview/export parity.
- [ ] 3.3 Run the repo-defined relevant test or tooling command for the changed files and document any manual GUI/export verification still needed.
