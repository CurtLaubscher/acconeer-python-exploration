# Heatmap Alignment Refactor Plan

This is an internal implementation checklist for splitting the heatmap alignment
workbench into smaller flat `user_tools` modules. It is not an OpenSpec change
and does not define product behavior.

## Goals

- Reduce the size and coupling of the largest heatmap alignment modules.
- Preserve saved-session JSON compatibility, CLI launch behavior, and user workflows.
- Keep old import facades during the first pass so tests and scripts can migrate safely.
- Commit each phase independently after focused tests and review.

## Non-goals

- Do not introduce a package directory in this pass.
- Do not redesign `HeatmapAlignmentWindow` into a full controller framework.
- Do not change accepted OpenSpec behavior unless a bug is found and explicitly fixed.
- Do not perform broad unrelated Ruff/format cleanup.

## Phases

### Phase 0 - Branch and Plan Artifact

- Add this plan.
- Review the plan artifact.
- Commit before moving code.

### Phase 1 - Timeline and Signal Widgets

- Extract timeline range/model and geometry helpers.
- Extract `SignalPlotWidget`.
- Extract `AlignmentTimelineWidget`.
- Keep `heatmap_alignment_timeline_widgets.py` as a compatibility facade.

### Phase 2 - Core Domains

- Extract session model/load/save/validation.
- Extract camera and H5 source adapters.
- Extract signal-series transforms and y-range helpers.
- Extract heatmap rendering helpers.
- Extract viewport/image processing helpers.
- Extract resource identity and reconcile helpers.
- Keep `heatmap_alignment_core.py` as a compatibility facade.

### Phase 3 - Main GUI Ownership Areas

- Extract recent-session support.
- Extract source-resolution viewport worker/helpers.
- Extract resource action helpers.
- Extract peak overlay coordination helpers.
- Extract export helpers.
- Keep `HeatmapAlignmentWindow` as the orchestration shell.

### Phase 4 - Import Consolidation and Cleanup

- Move internal imports to the new modules where it improves clarity.
- Keep compatibility facades where external scripts/tests still rely on them.
- Record deferred follow-ups here or in `openspec/specs/heatmap-alignment-gui/ideas.md`.

## Phase Gate

For every phase:

- Run focused Hatch tests for the moved area.
- Review the phase diff before committing.
- Fix required or major review findings before proceeding.
- Add tests when moved behavior lacks meaningful coverage.
- Commit the phase separately.

