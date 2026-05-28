## 1. Job State Foundation

- [ ] 1.1 Add runtime resource job state models for pending, loading, building, waiting, cancelling, failed, and superseded states without changing saved session JSON.
- [ ] 1.2 Add per-resource generation tokens so stale or superseded job completions cannot mutate the active session or previews.
- [ ] 1.3 Add a GUI-owned resource job manager that runs work off the main Qt event loop and reports progress, completion, failure, and cancellation back to the main thread.
- [ ] 1.4 Add bounded scheduling so proxy/transcode work is limited separately from other resource-loading work.

## 2. Camera Resource Jobs

- [ ] 2.1 Move camera video probing and preview proxy generation into a background resource job.
- [ ] 2.2 Apply camera replacement results only after the proxy-backed preview source is ready.
- [ ] 2.3 Keep the previous active camera resource available internally until a replacement camera succeeds, fails, or is cancelled.
- [ ] 2.4 Restore the previous active camera preview/state when a replacement camera load fails or is cancelled.
- [ ] 2.5 Treat proxy generation failure as a camera load failure and expose the failure reason without falling back to full-resolution interactive preview.
- [ ] 2.6 Generate preview proxies through temporary output files and promote them to final cache paths only after successful completion.
- [ ] 2.7 Preserve existing native viewport geometry exactly for same-dimension camera replacements, scale only for compatible aspect ratios where valid, and reset or repair invalid geometry otherwise.

## 3. H5 Resource Jobs

- [ ] 3.1 Choose and document the H5 ownership implementation: immutable loaded data safe for UI ownership, or worker-owned H5 actor with explicit async frame/render requests.
- [ ] 3.2 Move Radar Raw (H5) loading and initial rendered-heatmap preparation into a background resource job without transferring unsafe worker-owned HDF5 handles to the UI thread.
- [ ] 3.3 Keep the previous active H5 resource available internally until a replacement H5 succeeds, fails, or is cancelled.
- [ ] 3.4 Restore the previous active H5 rendered-heatmap state when a replacement H5 load fails or is cancelled.
- [ ] 3.5 Clear imported Radar Peak (JSON) datasource state after a different H5 successfully replaces the active H5.
- [ ] 3.6 Preserve the previous H5 and peak datasource if an H5 replacement fails before becoming active.

## 4. Resources UI And Preview States

- [ ] 4.1 Extend resource summaries and Resources window rows to show pending load/build/wait/cancel/failure state and target filenames.
- [ ] 4.2 Add row-scoped cancel actions for cancellable pending resource jobs.
- [ ] 4.3 Show camera preview loading/proxy-building overlays while a target camera is pending.
- [ ] 4.4 Show rendered heatmap loading overlays while a target H5 is pending.
- [ ] 4.5 Clear or visibly dim affected preview content during replacement so stale active-resource visuals are not mistaken for the pending target.
- [ ] 4.6 Keep different resource type load actions available while another resource type is loading, subject to resource-specific dependencies.

## 5. Resource Actions And Export Availability

- [ ] 5.1 Update load/reload/replace actions so same-resource requests automatically supersede pending jobs without requiring a prompt.
- [ ] 5.2 Disable synced video export while camera or H5 resources required by export are loading, replacing, cancelling, or failed.
- [ ] 5.3 Preserve existing modal/synchronous synced video export behavior and progress UI.
- [ ] 5.4 Keep session resource paths and metadata unchanged until a pending resource replacement succeeds.

## 6. Tests And Verification

- [ ] 6.1 Add unit tests for resource job state transitions, generation-token stale-result handling, and same-resource supersede behavior.
- [ ] 6.2 Add tests for camera replacement success, failure restore, viewport preservation/reset behavior, and proxy failure reporting using lightweight fakes or synthetic files.
- [ ] 6.3 Add tests proving cancelled, failed, or superseded proxy generation cannot leave a reusable final cache-path proxy file.
- [ ] 6.4 Add tests for H5 replacement success, failure restore, safe H5 ownership behavior, and automatic peak datasource clearing on different H5 success.
- [ ] 6.5 Add GUI-focused tests for Resources window loading/failure/cancel row presentation where practical.
- [ ] 6.6 Run focused heatmap alignment tests through the Hatch-managed test environment and document any known Windows Qt teardown noise separately from assertion failures.
