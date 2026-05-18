## Why

Exported heatmap plot overlays currently do not visually match the GUI overlay preview because plot styling is tied to fixed Matplotlib point sizes while the export overlay is rendered at original camera resolution. Users need the preview to be a reliable representation of exported output before spending time on video export.

## What Changes

- Add a shared overlay plot presentation model for the heatmap alignment workbench.
- Make preview and export render plotted heatmap overlays with matching visual proportions for fonts, ticks, labels, margins, and plot content.
- Use original camera/source-resolution overlay geometry as the styling basis so future high-resolution preview work can reuse the same presentation model.
- Keep the current export behavior and file format unchanged except for overlay plot appearance.
- Add focused coverage for preview/export plot parity and small-overlay readability.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `heatmap-alignment-gui`: The synced video export overlay preview SHALL visually match the exported plotted heatmap overlay presentation closely enough to be trusted before export.

## Impact

- Affected code: `user_tools/heatmap_alignment_core.py`, `user_tools/heatmap_alignment_gui.py`, and relevant tests.
- Affected behavior: overlay plot styling in GUI preview and exported synced videos.
- Dependencies: no new runtime dependencies expected.
- Compatibility: no saved session schema change expected.
