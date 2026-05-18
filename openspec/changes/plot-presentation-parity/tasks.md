## 1. Renderer Style Model

- [x] 1.1 Add an internal overlay plot style model that derives font sizes, tick sizes, line widths, and margins from source-space overlay dimensions plus actual render dimensions.
- [x] 1.2 Update `HeatmapPlotRenderer` to apply the derived style consistently when rebuilding the Matplotlib canvas.
- [x] 1.3 Add bounded style limits so compact overlays keep labels, ticks, margins, and heatmap body inside the overlay image without one-off call-site scaling.

## 2. Preview And Export Wiring

- [x] 2.1 Pass source-space overlay dimensions or equivalent presentation context into the GUI overlay preview renderer.
- [x] 2.2 Pass the same presentation context into the export overlay renderer so export is the source-resolution presentation authority.
- [x] 2.3 Preserve existing overlay geometry, export duration, FPS selection, progress handling, and session persistence behavior.

## 3. Verification

- [x] 3.1 Add focused tests or renderer-level checks that preview and export derive matching plot style proportions from the same overlay geometry.
- [x] 3.2 Add coverage for compact overlay dimensions to verify derived style bounds and preview/export parity.
- [x] 3.3 Run the repo-defined relevant test or tooling command for the changed files and document any manual GUI/export verification still needed.

## 4. Explicit Source-Space Defaults

- [x] 4.1 Replace overlay-size-driven source font/tick/line growth with fixed source-space default plot style values.
- [x] 4.2 Keep preview/export parity by scaling the fixed source-space style into lower-resolution preview renders.
- [x] 4.3 Update focused tests to verify source style remains fixed across different overlay sizes and preview style scales from that fixed source style.
- [x] 4.4 Run the relevant repo-defined tests and `openspec validate "plot-presentation-parity" --strict`.

## 5. Margin And Default Size Tuning

- [x] 5.1 Replace percentage subplot margin defaults with source-space pixel margin defaults that scale with render resolution.
- [x] 5.2 Add compact-overlay margin bounds so fixed pixel margins do not collapse or invert the heatmap body.
- [x] 5.3 Increase the hard-coded default font, tick, and line style values for better readability.
- [x] 5.4 Update focused tests to verify fixed source-space margins, preview-scaled margins, compact bounds, and larger default style values.
- [x] 5.5 Run the relevant repo-defined tests and `openspec validate "plot-presentation-parity" --strict`.
