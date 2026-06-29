## Why

Loading or replacing resources can leave old resource data active while the new target is still pending. This lets H5-derived actions such as Generate Peak Series use stale data, and can also show old camera, heatmap, or signal content underneath loading states during session open or resource replacement.

## What Changes

- Change single-slot resource load/replace semantics so a differing active resource is cleared immediately before the new load begins.
- Apply the same stale-state clearing rule during saved-session reconciliation when a desired resource identity differs from the active loaded identity.
- Leave a slot empty or failed when a load/replace fails; do not automatically restore the previous resource.
- Keep matching-identity session reconciliation as **keep**, including matching in-flight jobs, so unchanged resources are not torn down unnecessarily.
- Require H5-derived actions, especially Generate Peak Series, to operate only when the current requested H5 identity is fully loaded and no H5 load/replace is pending.
- Keep the resource-slot model structured around identities and slots so future work can generalize from one camera/H5/Leg2 slot to multiple resources of the same type.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `heatmap-alignment-gui`: Change resource replacement, session load reconciliation, resource loading presentation, export availability after failed loads, and in-app H5 peak generation readiness requirements.

## Impact

- `user_tools/heatmap_alignment_gui.py`: Clear active slot state before differing load/replace/session reconciliation loads; remove or narrow replacement backup/restore behavior; guard H5-derived actions against pending/stale resources.
- `user_tools/heatmap_alignment_session_coordinator.py` and `user_tools/heatmap_alignment_core.py`: Update reconcile semantics from "load while preserving/restoring active resource" to "clear differing active resource before load".
- `user_tools/heatmap_alignment_resource_summaries.py`: Ensure actions and row status reflect pending loads without exposing actions that would use stale active data.
- Tests in `tests/user_tools/`: Update existing replacement/restore expectations and add coverage for Generate Peak Series during H5 load, session open with changed resources, failed replacements leaving slots empty, and stale preview/action isolation.
