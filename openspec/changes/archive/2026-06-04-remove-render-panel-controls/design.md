## Context

The workbench layout has already moved viewport enhancement controls into the Viewport panel. The remaining bottom **Render** panel now mixes several unrelated control families:

- Rendered heatmap color min/max.
- Disabled xcorr/preprocess controls (`Blur`, `Downscale`, `Lag Window`, `Sample Count`).
- Peak and Leg2 visibility checkboxes.
- The Leg2 raw/filtered signal selector.

This layout makes the bottom panel a catch-all rather than a domain-specific surface. It also persists peak and Leg2 datasource visibility in session JSON, so an old session can hide loaded signals without an obvious restore path after the redundant checkboxes are removed.

The current alignment session format is version `1` and rejects any other version. It has no migration chain today.

## Goals / Non-Goals

**Goals:**

- Remove the bottom Render panel from the primary workflow.
- Put rendered-heatmap color controls in the Rendered Heatmap panel.
- Put the Leg2 raw/filtered selector in the Signals area.
- Remove peak and Leg2 datasource visibility checkboxes and persisted hidden-state behavior.
- Add a minimal session v1-to-v2 migration so existing v1 session files remain loadable.
- Keep dormant preprocess settings in the session payload for now.

**Non-Goals:**

- Reintroduce xcorr/preprocess diagnostics or decide their final UI.
- Persist plot legend hide/show state.
- Build a general-purpose schema validation framework.
- Preserve backward compatibility from version 2 session files to older workbench builds.
- Redesign the Resources window or resource adapter model.

## Decisions

### Use panel ownership instead of a shared Render strip

Rendered-heatmap color limits belong in the Rendered Heatmap panel because they directly change that preview and its exported overlay rendering. The Leg2 raw/filtered selector belongs in the Signals area because it changes the plotted Leg2 series, not the heatmap preview.

Alternative considered: keep a smaller bottom Render panel for color limits and signal controls. That preserves the current implementation shape but leaves the same conceptual problem: controls remain separated from the visual surfaces they affect.

### Remove datasource visibility controls instead of relocating them

Peak and Leg2 visibility checkboxes duplicate the existing pyqtgraph legend hide/show interaction and make datasource state do two jobs: resource availability and visualization state. After this change, a loaded peak datasource is available to the heatmap marker/export overlay and Signals plot by default, and a loaded Leg2 datasource is plotted by default. Temporary curve hiding remains a Signals legend/view concern.

Alternative considered: move the checkboxes into Rendered Heatmap and Signals. That would keep backwards behavior, but it also keeps the persisted hidden-state trap and makes the UI busier without adding much value.

### Introduce session format version 2 with a narrow migration

Version 2 removes peak and Leg2 datasource visibility as authoritative session state. The v1-to-v2 migration should operate on the decoded JSON payload before dataclass construction:

- Accept payloads with `version == 1`.
- Remove `peak_distance_datasource.visible` and `leg2_ultrasonic_datasource.visible` when present.
- Set `version` to `2`.
- Preserve all other fields, including dormant `preprocess` settings.

The migration must run before the current `from_json_dict(...)` version gate rejects non-current versions. After migration, dataclass construction and validation should see a version `2` payload.

Version 2 should remove the retired visibility attributes from the peak-distance and Leg2 datasource settings dataclasses. If a short transition requires either visibility attribute to remain as a dormant runtime field, `to_json_dict()` still needs to remove it from the serialized payload because the current `asdict(self)` path would otherwise keep writing it.

Successful migration should not warn. Unsupported newer versions should continue to fail clearly, and structurally invalid old sessions should still fail with a user-visible load error.

Alternative considered: leave `SESSION_VERSION = 1` and silently ignore visibility fields. That is smaller, but it under-states the saved-format behavior change and still requires compatibility filtering if the dataclass fields are removed.

### Keep preprocess fields dormant

The disabled preprocess controls are removed from the main UI, but their session fields remain readable and writable. This avoids coupling a UI cleanup to an xcorr/preprocess data-model decision. A future xcorr/preprocess change can either reintroduce those settings with a better UI or retire them through a dedicated migration.

## Risks / Trade-offs

- [Older workbench builds cannot load v2 sessions] -> Accept this for the current single-user tool; document the breaking direction in the proposal and specs.
- [Removing visibility fields changes old hidden sessions] -> Migration intentionally makes loaded datasources visible, avoiding hidden resources with no restore control.
- [Signals legend hiding is temporary rather than persisted] -> Treat persistent per-curve visibility as future Signals plot view state only if users need it.
- [Dormant preprocess fields remain in saved JSON] -> Keep them for compatibility now and track future cleanup in `ideas.md`.
