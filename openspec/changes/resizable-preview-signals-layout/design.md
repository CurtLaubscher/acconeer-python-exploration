## Context

The heatmap alignment workbench currently stacks the Preview area, Signals plot, and Timeline in a single vertical layout. The Preview area already contains a horizontal `QSplitter` that lets users resize Camera Video against the viewport/rendered-heatmap column, but there is no equivalent control for trading Preview height against Signals height.

The immediate usability issue is signal readability in small windows. Timeline scalability is a future concern, but the current workbench still has a small fixed set of timeline rows, so the Timeline does not need to become a full track editor in this change.

## Goals / Non-Goals

**Goals:**
- Let users vertically resize Preview and Signals in the main workbench.
- Keep Timeline fixed-height and predictable for the current fixed-resource workflow.
- Preserve the existing horizontal Preview splitter behavior.
- Keep the change local to workbench layout behavior.

**Non-Goals:**
- Persist splitter sizes or add a reset-layout action.
- Introduce dockable/draggable panes.
- Redesign render controls or solve viewport/control overlap.
- Make Timeline scalable for arbitrary resource counts.
- Change alignment session JSON or any resource/session data model.

## Decisions

Use a vertical `QSplitter` for Preview and Signals only. Preview and Signals are the two areas where additional height directly improves inspection. Timeline remains outside that splitter so it keeps its current compact role as a control surface.

Keep the existing horizontal Preview splitter nested inside the Preview pane. This preserves the current camera-versus-viewport/rendered-heatmap resizing model while adding only the missing vertical control.

Do not persist the new vertical splitter size in this change. The existing horizontal splitter is not currently persisted, and persisting only the new vertical splitter would make layout behavior inconsistent. A future layout-preference pass can persist all splitter sizes together and provide reset behavior.

Use sensible stretch factors and minimum sizes in implementation, but do not encode exact pixel values or ratios in the spec. Those values should be tuned during implementation based on how the workbench feels at realistic window sizes.

## Risks / Trade-offs

- Preview or Signals can become too small to use -> Set practical minimum sizes on the resizable panes and keep splitter children non-collapsible.
- Users may expect layout choices to persist -> Defer persistence until all layout panes can be handled consistently, and keep the default allocation useful on each launch.
- Timeline may eventually need more space for arbitrary resources -> Keep that future model out of scope and note it in `ideas.md` for a later Timeline scalability change.
