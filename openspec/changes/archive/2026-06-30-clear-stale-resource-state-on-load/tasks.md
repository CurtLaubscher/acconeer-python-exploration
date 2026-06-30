## 1. Resource Slot Clearing Semantics

- [x] 1.1 Add or refactor helpers that clear active camera slot state without clearing unrelated independent resources
- [x] 1.2 Add or refactor helpers that clear active H5 slot state, including rendered heatmap state, axes, hover caches, timeline metadata, renderer state, and H5 action readiness
- [x] 1.3 Ensure direct resource load/replace paths clear differing active camera/H5 resources before starting new background jobs
- [x] 1.4 Remove or narrow camera/H5 replacement backup restore behavior so failed differing replacements do not restore old active resources
- [x] 1.5 Ensure failed, cancelled, and superseded load attempts leave slots empty/failed unless a matching active resource was never cleared

## 2. Session Reconciliation

- [x] 2.1 Update session reconcile semantics so **load** actions pre-clear differing active slot resources before starting load work
- [x] 2.2 Preserve **keep** behavior for matching active identities and matching in-flight identities
- [x] 2.3 Ensure session open with changed camera/H5 resources cannot show or use old active resources while new loads are pending
- [x] 2.4 Ensure session-open load failures leave changed slots empty/failed instead of restoring the prior session's resources
- [x] 2.5 Keep reconciliation logic slot/identity oriented so future multi-resource support can reuse the same pattern

## 3. H5 Readiness And Peak Generation

- [x] 3.1 Add a single H5 readiness predicate for H5-derived actions that checks active source, identity match, and no pending/waiting/loading/cancelling H5 job
- [x] 3.2 Use the readiness predicate to hide or disable Generate Peak Series in the Resources UI while H5 is pending, failed, stale, or unavailable
- [x] 3.3 Guard the Generate Peak Series command itself so it cannot use stale H5 data even if invoked directly while H5 is not ready
- [x] 3.4 Ensure preserved peak series can remain independent signal resources without making H5-derived generation appear available

## 4. Loading Presentation And Dependent State

- [x] 4.1 Ensure camera, rendered heatmap, viewport, timeline, and Signals views do not draw stale resource content beneath loading/unavailable text
- [x] 4.2 Ensure Resources rows show pending/failed target state clearly after active resources are cleared
- [x] 4.3 Ensure export remains disabled when required camera/H5 slots are empty, failed, or pending after a failed replacement
- [x] 4.4 Ensure close-session/reset and abandoned-job paths clear pending state without restoring stale resource backups

## 5. Regression Tests

- [x] 5.1 Update existing replacement tests that expect camera/H5 restore-on-failure behavior to expect empty/failed slots instead
- [x] 5.2 Add tests for direct H5 replacement clearing old `heatmap_source` before the new H5 finishes loading
- [x] 5.3 Add tests proving Generate Peak Series is unavailable and command-guarded during pending H5 load/replacement
- [x] 5.4 Add tests for session open with changed H5 clearing old H5 data before the new load completes
- [x] 5.5 Add tests for session-open H5 load failure leaving the H5 slot empty/failed rather than restored
- [x] 5.6 Add representative tests for camera replacement/session-open clearing old camera preview state
- [x] 5.7 Add tests that matching-identity session open still keeps active or in-flight resources without unnecessary teardown
- [x] 5.8 Run targeted heatmap alignment user-tools tests and `git diff --check`
