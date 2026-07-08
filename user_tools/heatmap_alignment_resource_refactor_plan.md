# Heatmap Alignment Resource Refactor Plan

This is an internal implementation checklist for the resource-oriented follow-up
to the heatmap alignment modularization. It is not an OpenSpec change and does
not define product behavior.

## Goals

- Reduce resource-related ownership in `HeatmapAlignmentWindow`.
- Prepare the code for future arbitrary resources without changing current UI
  behavior.
- Keep session JSON, CLI behavior, resource labels, and user workflows unchanged.
- Commit each phase independently after focused tests and review.

## Non-goals

- Do not add arbitrary user-visible resource counts in this pass.
- Do not change accepted OpenSpec behavior.
- Do not introduce a package directory or broad controller framework.
- Do not keep pure compatibility facades as the final intended shape.
- Do not perform broad unrelated Ruff or format cleanup.

## Facade Policy

Temporary facades are acceptable inside a phase when they keep the behavior move
reviewable. The final cleanup phase should migrate repo imports and tests to the
focused owner modules, then delete pure re-export modules where practical.

## Phases

### Phase 0 - Plan Artifact - In Progress

- Add this plan.
- Review the plan artifact.
- Commit before moving code.

### Phase 1 - Resource Model and Summaries

- Add `heatmap_alignment_resource_model.py` with resource kinds, actions,
  statuses, and fixed resource descriptors.
- Refactor resource summary construction around descriptors and per-kind
  builders.
- Preserve existing `ResourceSummary` output.

### Phase 2 - Resource Coordinator

- Add a small `ResourceCoordinator` and host protocol.
- Move Resources window lifecycle, reload errors/warnings, summaries, menu/action
  enabled state, resource action dispatch, path lookup, reveal, and inspect
  handling out of `HeatmapAlignmentWindow`.
- Keep actual load, unload, save, generate, and reload mutation methods on the
  window.

### Phase 3 - Resource Job Split

- Split resource job state and board transitions from camera and H5 job
  execution.
- Preserve cancellation, superseded-job, replacement, proxy, and H5 handoff
  behavior.

### Phase 4 - Dialog Split

- Split Resources window/delegates, Generate Peak Series dialog, and Heatmap
  distance header out of `heatmap_alignment_dialogs.py`.
- Preserve labels, layout, signals, and test seams.

### Phase 5 - GUI Ownership Cleanup

- Move remaining resource-specific helper methods out of `HeatmapAlignmentWindow`
  where ownership is now clear.
- Keep playback, timeline, and preview methods on the window unless resource
  extraction creates an obvious owner.

### Phase 6 - Facade and Import Cleanup

- Migrate repo code and tests to focused modules.
- Delete pure compatibility facade modules where practical.
- Remove compatibility aliases from `heatmap_alignment_gui.py` unless a real
  monkeypatch seam should remain.
- Update this plan with completed phases and deferred follow-ups.

## Phase Gate

For every phase:

- Run focused Hatch tests for the moved area.
- Run scoped Ruff checks for import ordering and undefined names on touched
  Python files.
- Review the phase diff before committing.
- Fix required or major review findings before proceeding.
- Add tests when moved behavior lacks meaningful coverage.
- Commit the phase separately.

