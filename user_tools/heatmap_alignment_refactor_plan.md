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

### Phase 0 - Branch and Plan Artifact - Completed

- Add this plan.
- Review the plan artifact.
- Commit before moving code.

Status: completed in `c107e5ec`.

### Phase 1 - Timeline and Signal Widgets - Completed

- Extract timeline range/model and geometry helpers.
- Extract `SignalPlotWidget`.
- Extract `AlignmentTimelineWidget`.
- Keep `heatmap_alignment_timeline_widgets.py` as a compatibility facade.

Status: completed in `c1be21ed`.

### Phase 2 - Core Domains - Completed

- Extract session model/load/save/validation.
- Extract camera and H5 source adapters.
- Extract signal-series transforms and y-range helpers.
- Extract heatmap rendering helpers.
- Extract viewport/image processing helpers.
- Extract resource identity and reconcile helpers.
- Keep `heatmap_alignment_core.py` as a compatibility facade.

Status: completed in `9bce2275`.

### Phase 3 - Main GUI Ownership Areas - Completed

- Extract recent-session support.
- Extract source-resolution viewport worker/helpers.
- Extract resource action helpers.
- Extract peak overlay coordination helpers.
- Extract export helpers.
- Keep `HeatmapAlignmentWindow` as the orchestration shell.

Status: completed in `a446a877`.

### Phase 4 - Import Consolidation and Cleanup - Completed

- Move internal imports to the new modules where it improves clarity.
- Keep compatibility facades where external scripts/tests still rely on them.
- Record deferred follow-ups here or in `openspec/specs/heatmap-alignment-gui/ideas.md`.

Status: completed in this cleanup commit.

## Phase Gate

For every phase:

- Run focused Hatch tests for the moved area.
- Review the phase diff before committing.
- Fix required or major review findings before proceeding.
- Add tests when moved behavior lacks meaningful coverage.
- Commit the phase separately.

## Deferred Follow-ups

- Keep `heatmap_alignment_core.py` and `heatmap_alignment_timeline_widgets.py` as compatibility
  facades for now. They still protect tests, ad hoc scripts, and older user workflows during the
  first modularization pass.
- `HeatmapAlignmentWindow` remains large. A later pass can move more coupled workflow methods into
  narrow service modules once the current flat module boundaries have settled.
