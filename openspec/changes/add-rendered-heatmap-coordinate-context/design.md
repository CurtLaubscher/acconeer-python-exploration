## Context

The heatmap alignment workbench compares a rectified camera viewport against a rendered Sparse IQ heatmap. Existing plotted overlay/export rendering can include axes and plot labels, but using full plot chrome in the rendered heatmap comparison panel risks changing the body size users compare against the rectified viewport. The new coordinate context should therefore be lightweight UI/annotation around the rendered heatmap body, not a general conversion of the comparison preview into a full Matplotlib-style plot.

The rendered heatmap already has physical distance and velocity axes available through the Sparse IQ heatmap helpers, and peak series can provide a current-frame peak distance. The workbench can use those existing values to label extents, position the peak indicator, and map hover coordinates back into distance/velocity bins.

## Goals / Non-Goals

**Goals:**

- Make the rendered heatmap preview understandable in physical coordinates during manual alignment.
- Preserve the comparable rendered heatmap body geometry relative to the rectified viewport.
- Keep annotations compact enough for live use, avoiding large ticks, axes, and whitespace.
- Provide a hover readout for distance, velocity, and current-frame magnitude.
- Replace the legacy in-body selected peak marker style with compact label/triangle markers in both preview and export overlay rendering.
- Keep layout details tunable during implementation without requiring spec churn.

**Non-Goals:**

- Do not add full axes, tick grids, or Matplotlib plot chrome to the comparison preview.
- Do not add rendered heatmap colorbar or color scale visibility in this change.
- Do not change broader export overlay formatting beyond the selected peak marker presentation.
- Do not change the peak extraction algorithms or selected peak series model.

## Decisions

### Use Lightweight UI Annotations Instead Of Full Plot Axes

Distance extent labels and the peak distance label should live in a compact header aligned to the rendered heatmap body. Velocity extent context should live near the rendered heatmap controls, such as the color min/max controls, rather than adding a vertical axis gutter beside the heatmap.

Prefer placing the velocity extent text alongside the color min/max control row so it reads as current heatmap metadata without adding height to the rendered heatmap preview area.

Alternative considered: render full axes/ticks around the heatmap. That provides familiar chart semantics but risks making the heatmap body smaller than the rectified viewport panel unless both panels adopt matching gutters. It also pulls in label density, margins, tick formatting, and clipping problems that are broader than the immediate alignment need.

### Keep The Heatmap Body As The Geometry Anchor

Coordinate labels and the peak marker should be positioned relative to the rendered heatmap body, but must not change the body width or height used for direct visual comparison. The body geometry remains the authoritative region for viewport comparison and hover mapping.

Alternative considered: include labels inside the rendered image itself. That may simplify rendering, but it can obscure heatmap content and makes it easier to accidentally tie annotation layout to the rendered raster dimensions.

### Use A Clamped Peak Label With An Independently Tracking Indicator

When a selected peak exists for the current frame, show the peak distance text in the same header row as the x extent labels. A small downward triangle indicator sits below the label and directly above the heatmap body. The text clamps within available header space to avoid colliding with extent labels or leaving bounds, while the triangle continues to track the true peak x coordinate when possible.

At very narrow widths, it is acceptable to hide the static x extent labels before sacrificing the moving peak label and triangle. If the available width is too small even for the moving label, keep the triangle indicator as the highest-priority peak position cue.

The header label and indicator should replace the legacy in-image peak annotation for the same selected peak in the rendered heatmap comparison preview and exported heatmap overlays. Keeping both would add redundant peak cues and preserve the visually noisy body overlay that this direction is meant to avoid.

Export overlays should use an equivalent compact label/triangle treatment where space allows, while preserving existing export overlay layout and avoiding a return to full plot-axis work in this change.

Alternative considered: always keep x extent labels visible and hide the moving peak text near collisions. That preserves static coordinate context, but it is less useful when the user is specifically tracking the current peak position in a constrained preview.

### Use A Tooltip-Style Hover Readout

Hovering over the rendered heatmap body should show a tooltip-like readout near the cursor. It should use normal theme-appropriate UI colors and display one value per line: distance, velocity, and magnitude. Distance and velocity come from the cursor coordinate; magnitude comes from the current H5 frame at that coordinate and refreshes when playback/current time changes while the cursor remains over the body.

Magnitude should come from the raw float distance/velocity map for the current frame, not from rendered RGB pixels. The implementation should avoid recomputing the map independently for every pointer move when a current-frame map can be reused from the render/update path.

Alternative considered: use a fixed readout panel near controls. A fixed panel avoids covering the heatmap, but the tooltip is more directly connected to the inspected point and matches the exploratory workflow.

## Risks / Trade-offs

- Annotation collision near narrow preview widths -> Clamp labels where practical; at very narrow widths, hide static x extent labels before hiding the moving peak label, and keep the triangle indicator as the fallback position cue.
- Tooltip obscures heatmap details -> Keep it compact, use normal tooltip styling, and hide it immediately when the pointer leaves the heatmap body.
- Magnitude readout can become stale during playback -> Store the last hovered heatmap coordinate and refresh the tooltip content on current-frame updates while the pointer remains over the body.
- Body geometry can drift from the rectified viewport if labels are implemented as plot margins -> Treat annotations as external UI/overlay chrome and verify body dimensions remain matched.
