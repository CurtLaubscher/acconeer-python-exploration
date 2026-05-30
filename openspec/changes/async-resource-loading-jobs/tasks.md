## Status

Initial implementation landed in commit `51fc67ce`. Review follow-up corrections from section 7 are implemented on branch `claub/async-resource-loading-jobs`.
Acceptance testing found additional cancel, shutdown, and loading-overlay issues; section 8 acceptance-test fixes are implemented on branch `claub/async-resource-loading-jobs-clean`. Section 9 captures pre-archive corrections identified during branch review.

**Task counts (sections 1–8):** 47 total, 47 complete, 0 remaining.

**Task counts (section 9, pre-archive):** 5 total, 0 complete, 5 remaining.

## 1. Job State Foundation

- [x] 1.1 Add runtime resource job state models for pending, loading, building, waiting, cancelling, failed, and superseded states without changing saved session JSON.
- [x] 1.2 Add per-resource generation tokens so stale or superseded job completions cannot mutate the active session or previews.
- [x] 1.3 Add a GUI-owned resource job manager that runs work off the main Qt event loop and reports progress, completion, failure, and cancellation back to the main thread.
- [x] 1.4 Add bounded scheduling so proxy/transcode work is limited separately from other resource-loading work.

## 2. Camera Resource Jobs

- [x] 2.1 Move camera video probing and preview proxy generation into a background resource job.
- [x] 2.2 Apply camera replacement results only after the proxy-backed preview source is ready.
- [x] 2.3 Keep the previous active camera resource available internally until a replacement camera succeeds, fails, or is cancelled.
- [x] 2.4 Restore the previous active camera preview/state when a replacement camera load fails or is cancelled.
- [x] 2.5 Treat proxy generation failure as a camera load failure and expose the failure reason without falling back to full-resolution interactive preview.
- [x] 2.6 Generate preview proxies through temporary output files and promote them to final cache paths only after successful completion.
- [x] 2.7 Preserve existing native viewport geometry exactly for same-dimension camera replacements, scale only for compatible aspect ratios where valid, and reset or repair invalid geometry otherwise.

## 3. H5 Resource Jobs

- [x] 3.1 Choose and document the H5 ownership implementation: immutable loaded data safe for UI ownership, or worker-owned H5 actor with explicit async frame/render requests.
- [x] 3.2 Move Radar Raw (H5) loading and initial rendered-heatmap preparation into a background resource job without transferring unsafe worker-owned HDF5 handles to the UI thread.
- [x] 3.3 Keep the previous active H5 resource available internally until a replacement H5 succeeds, fails, or is cancelled.
- [x] 3.4 Restore the previous active H5 rendered-heatmap state when a replacement H5 load fails or is cancelled.
- [x] 3.5 Clear imported Radar Peak (JSON) datasource state after a different H5 successfully replaces the active H5.
- [x] 3.6 Preserve the previous H5 and peak datasource if an H5 replacement fails before becoming active.

## 4. Resources UI And Preview States

- [x] 4.1 Extend resource summaries and Resources window rows to show pending load/build/wait/cancel/failure state and target filenames.
- [x] 4.2 Add row-scoped cancel actions for cancellable pending resource jobs.
- [x] 4.3 Show camera preview loading/proxy-building overlays while a target camera is pending.
- [x] 4.4 Show rendered heatmap loading overlays while a target H5 is pending.
- [x] 4.5 Clear or visibly dim affected preview content during replacement so stale active-resource visuals are not mistaken for the pending target.
- [x] 4.6 Keep different resource type load actions available while another resource type is loading, subject to resource-specific dependencies.

## 5. Resource Actions And Export Availability

- [x] 5.1 Update load/reload/replace actions so same-resource requests automatically supersede pending jobs without requiring a prompt.
- [x] 5.2 Disable synced video export while camera or H5 resources required by export are in an in-flight load/replace/cancel phase. *(Original wording also listed `failed`; section 9.1 corrects export blocking so `failed` job status alone does not disable export after a restored replacement.)*
- [x] 5.3 Preserve existing modal/synchronous synced video export behavior and progress UI.
- [x] 5.4 Keep session resource paths and metadata unchanged until a pending resource replacement succeeds.

## 6. Tests And Verification

- [x] 6.1 Add unit tests for resource job state transitions, generation-token stale-result handling, and same-resource supersede behavior.
- [x] 6.2 Add tests for camera replacement success, failure restore, viewport preservation/reset behavior, and proxy failure reporting using lightweight fakes or synthetic files.
- [x] 6.3 Add tests proving cancelled, failed, or superseded proxy generation cannot leave a reusable final cache-path proxy file.
- [x] 6.4 Add tests for H5 replacement success, failure restore, safe H5 ownership behavior, and automatic peak datasource clearing on different H5 success.
- [x] 6.5 Add GUI-focused tests for Resources window loading/failure/cancel row presentation where practical.
- [x] 6.6 Run focused heatmap alignment tests through the Hatch-managed test environment and document any known Windows Qt teardown noise separately from assertion failures.

## 7. Review Corrections

- [x] 7.1 When a same-resource load supersedes a pending job, actively request cancellation of the superseded in-flight work, including terminating active preview-proxy ffmpeg processes when possible, so the newest request can start promptly instead of waiting for discarded work to finish.
- [x] 7.2 On window close and session close, cancel or abandon active camera/H5 resource jobs, clear job board state and replacement backups, and prevent late completions from applying to a closed or reset workbench.
- [x] 7.3 On successful camera replacement, when aspect ratio is incompatible or scaled viewport geometry is invalid, explicitly reset or repair native viewport corners to a valid default instead of retaining previous-camera corners that are out of bounds for the replacement source.
- [x] 7.4 Add direct H5 replacement coverage: success apply, failure restore, safe ownership/handoff after worker load, automatic peak datasource clearing on different H5 success, and preserving prior H5/peaks on failed replacement.
- [x] 7.5 Emit and present the `waiting` job phase while a resource job is queued behind bounded expensive-work slots, so Resources rows and overlays distinguish waiting from actively loading/building.
- [x] 7.6 Carry the worker-computed resolved fixed color level in the H5 load payload (or equivalent immutable handoff data) so main-thread adoption does not repeat expensive color-level computation and reintroduce H5 UI freeze risk.
- [x] 7.7 Discard and release stale or superseded pending job results promptly so ignored completions cannot retain record handles or other payload resources in manager state.
- [x] 7.8 Clarify proxy success messaging (`proxy_built` vs `proxy_reused`) and document that large-camera proxy preparation requires ffmpeg; synchronous `prepare_proxy_video()` callers should treat missing ffmpeg as an explicit error rather than a full-resolution interactive fallback.

## 8. Acceptance Test Fixes

- [x] 8.1 Ensure loading overlays suppress or replace underlying placeholder text so panels never show stacked labels such as `Rendered Heatmap` underneath `Loading <file>...`.
- [x] 8.2 Apply loading overlay state consistently to all affected preview panels, including the viewport preview when either camera or H5 resource dependencies are pending, replacing, waiting, or cancelling.
- [x] 8.3 Make resource-job cancellation visibly immediate in the UI: after the user cancels, the pending target should enter cancelling/restored state promptly even if the underlying H5/file operation cannot stop immediately.
- [x] 8.4 Ensure cancel-before-apply wins over late worker success: if cancellation is requested before a worker result is accepted on the GUI thread, release the result payload and keep or restore the previous active resource instead of applying the cancelled target.
- [x] 8.5 Make worker success/failure dispatch safe during app shutdown or workbench teardown so late QRunnable completion cannot emit through a deleted `ResourceJobManager` Qt object or print a traceback.
- [x] 8.6 Add focused regression tests for loading-overlay text, viewport loading presentation, cancel-before-late-success handling, and worker completion after abandon/shutdown where practical.

## 9. Pre-Archive Corrections

- [ ] 9.1 Allow synced video export when required camera and H5 sources are loaded and stable even if the corresponding resource job slot is in `failed` phase after a replacement failure that restored the previous active resources; keep export disabled during in-flight phases (`pending`, `loading`, `building`, `waiting`, `cancelling`).
- [ ] 9.2 Set an abandoned/shutdown flag in `abandon_all_jobs()` and have `_ResourceJobRunnable.run()` return without dispatch when abandoned; keep emit-time `RuntimeError` guards as backstop; add focused regression coverage.
- [ ] 9.3 Release the `HeatmapRecord` in `load_h5_resource_payload()` when worker preparation fails after `load_heatmap_record()` succeeds but before returning `LoadedH5ResourcePayload`.
- [ ] 9.4 Consolidate `ResourceJobPhase` to a single module and remove the duplicate literal in `heatmap_alignment_core.py`.
- [ ] 9.5 Remove unused `resource_job_row_status()` or wire a single status path; keep Resources row labels consistent with `RESOURCE_JOB_STATUS_LABELS`.
