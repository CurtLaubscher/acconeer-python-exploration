## Context

The heatmap alignment workbench has single primary slots for Camera Video and Radar Raw (H5), plus optional peak-series resources and a Leg2 MAT datasource. Camera and H5 loads can run in background jobs. The current replacement model keeps the previous loaded resource active until the replacement succeeds, with backup/restore behavior when a replacement fails.

That model protects users from failed replacement attempts, but it also creates stale-state ambiguity. During a pending H5 replacement or session open, old `heatmap_source` data can still be read by Generate Peak Series or preview paths while the UI says a different H5 is loading. Similar stale content can appear underneath loading overlays in camera, rendered heatmap, viewport, timeline, and signal views.

## Goals / Non-Goals

**Goals:**
- Clear active slot state immediately when a load/replace/session-open request targets a different resource identity.
- Prevent H5-derived actions from using stale H5 data while a different H5 is pending.
- Leave failed loads as failed/empty slots rather than automatically restoring the previous active resource.
- Preserve efficient **keep** behavior when session reconciliation finds the desired resource already active or already in flight.
- Keep the slot/reconcile structure compatible with future multi-resource work.

**Non-Goals:**
- Adding multiple simultaneous camera or H5 resources in this change.
- Making peak generation asynchronous.
- Solving large Signals plot performance issues.
- Persisting resource job state in session JSON.
- Redesigning the Resources window layout.

## Decisions

### D1: Differing loads clear the active slot before starting work

For one-slot resources, loading a different identity is a destructive transition for the old active value. The old value is closed/cleared before the new job starts or before a synchronous import begins. The slot then presents the requested target as pending, loading, failed, or active.

Alternative: keep old active data until replacement succeeds, but hide or block all stale read paths. Rejected because it is easy to miss a path and because old visuals under loading states are misleading during alignment work.

### D2: Failed replacement does not restore old data

If a differing replacement fails, the slot remains empty or failed with a clear Resources row message. The user can retry, load another file, or reopen a session. The app does not automatically restore the previous resource because restoration may itself be slow or unwanted, and because it reintroduces ambiguity about what resource is active.

### D3: Session reconciliation stays identity-based and slot-oriented

Session open still reconciles desired resource identities against active and in-flight state:

- **keep**: desired identity matches active or in-flight state; do not clear or restart.
- **load**: desired identity differs and is non-empty; clear the old active slot and start loading the desired identity.
- **unload**: desired identity is empty; clear the old active slot.

This keeps the path extensible for future multiple resources by preserving explicit identity comparison and per-slot actions rather than adding one-off session-load teardown code.

### D4: H5 readiness requires active identity match and no pending H5 job

Generate Peak Series and other H5-derived actions must check that the active H5 source exists, the H5 job slot is not pending/loading/waiting/cancelling for another target, and the active H5 identity matches the current session/requested identity. A remembered H5 path or stale `heatmap_source` object is not enough.

### D5: Optional peak series remain independent signal resources unless session load clears them

Generated/imported peak series can remain valid signal resources after H5 unload or replacement when the user directly replaces H5, but session open reconciles peak resources from the saved session and drops unsaved/pathless generated rows. The key change is that peak generation cannot create a new series from stale H5 while another H5 is pending.

## Risks / Trade-offs

- Failed replacement leaves the user with no active resource -> Mitigate with clear failed state, retry/reload actions, and no silent stale visuals.
- Clearing camera immediately can blank preview/viewport while a new proxy builds -> This is expected; show loading state and avoid mixed old/new visuals.
- Existing tests encode restore-on-failure behavior -> Update tests to match the new safety contract.
- Slot clearing code may miss derived caches -> Add targeted tests for H5 source, rendered heatmap/axes/hover cache, peak generation, resource summaries, and session reconciliation.
- Future multi-resource support may need different UX -> Keep identity/reconcile helpers slot-based so the current change does not hard-code more global teardown assumptions.
