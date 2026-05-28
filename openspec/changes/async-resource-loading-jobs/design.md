## Context

The heatmap alignment GUI currently performs resource loading on the main Qt UI path. Measurements on a multi-trial dataset showed first-time camera preview proxy generation takes about 10-46 seconds per MP4, while H5 initialization takes about 2-6 seconds for valid files. Peak JSON and current Leg2 MAT imports are effectively negligible for the measured dataset, but they share the same resource-management surface and should not prevent later migration to background loading if file sizes grow.

The GUI already has a modeless Resources window, a disposable camera preview proxy system, and a source-resolution viewport worker. This change should extend those patterns into a small resource job system rather than adding one-off async code paths for each load button.

## Goals / Non-Goals

**Goals:**

- Keep the main alignment UI responsive while camera videos and H5 recordings are loading or being prepared.
- Represent long-running resource work as cancellable/supersedable jobs with resource-specific state in the Resources window.
- Allow different resource types to load concurrently when they do not conflict.
- Make same-resource replacement newest-request-wins without prompting while the prior request is still pending.
- Keep previously active resources in effect until replacement succeeds, while visually indicating that a replacement is pending.
- Require the low-quality camera preview proxy before enabling normal camera playback/scrubbing for a newly loaded video.
- Preserve existing export behavior except for disabling export while required resources are loading or replacing.

**Non-Goals:**

- Converting synced video export into a background/non-modal job.
- Adding batch trial preparation or multi-file queue UX.
- Adding unsaved-session dirty-state prompts.
- Adding in-app peak calculation or removing peak JSON import support.
- Adding a full generic arbitrary-resource framework beyond the current Camera Video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT slots.
- Falling back to sluggish full-resolution interactive video preview if preview proxy generation fails.

## Decisions

### Use a resource job manager with per-resource generations

Introduce a GUI-owned job manager that starts background jobs and emits Qt signals for progress, completion, failure, and cancellation. Each resource slot gets a monotonically increasing generation token. When a job completes, the main UI applies the result only if the token still matches the resource slot's current pending generation.

Rationale: cancellation may not stop immediately, especially for subprocess-backed proxy generation or file I/O. Generation checks make stale results harmless even when the underlying work finishes later.

Alternative considered: block replacement until the prior job exits. This keeps state simpler but preserves the frustrating UI behavior and makes same-resource replacement feel slow.

### Keep Qt widgets and active session mutation on the main thread

Background jobs should produce plain result payloads such as metadata, proxy path, warnings, loaded value objects that are safe to transfer, or error text. The main thread remains responsible for updating widgets and mutating the active session.

Rationale: Qt widgets are not thread-safe, and mutating the session from worker threads would make stale/superseded job handling fragile.

### Resolve H5 ownership before moving H5 work off-thread

H5 jobs must not construct a thread-owned `HeatmapTruthSource` and then hand that live HDF5-backed object to the UI thread. The implementation must either return immutable loaded data that is safe for UI ownership, or keep H5 access owned by a worker/actor thread with explicit asynchronous frame/render requests.

Rationale: the measured H5 initialization cost is large enough to move off the GUI path, but HDF5/file-backed object ownership can be unsafe or unclear across threads. The change should remove the freeze without replacing it with thread-affinity bugs.

Alternative considered: have the worker validate/probe H5 and then let the UI construct the current `HeatmapTruthSource`. This avoids thread ownership risk but likely keeps the 2-6 second GUI freeze, so it does not satisfy the user-visible goal.

### Keep active resources until replacements succeed

When replacing an already loaded resource, the existing active resource remains the active session resource until the new load succeeds. The affected preview panel should clear or dim and show a loading overlay for the target filename so the user does not mistake old visual content for the replacement. If the replacement fails or is cancelled, the previous resource and preview are restored.

Rationale: failed replacements should not leave the session half-mutated or discard useful alignment work.

Alternative considered: immediately clear the active resource and session path when a replacement starts. This is simpler but causes failed loads to destroy the user's current usable state.

### Require proxy readiness for normal camera interaction

For newly loaded high-resolution camera videos, camera playback and scrubbing should become available only after the preview proxy is ready. The GUI should not use the original full-resolution video as an interactive fallback during proxy generation.

Rationale: the full-resolution path previously made the UI feel sluggish. A clear loading state is preferable to an apparently available but unresponsive interaction path.

### Commit preview proxies atomically

Preview proxy generation should write to a temporary output path and promote the file to the final cache path only after ffmpeg succeeds. Cancelled, failed, or superseded jobs must not leave a final cache-path file that later loads can treat as valid.

Rationale: existing proxy reuse is based on the final cache path existing. Writing directly to that path during a cancellable background job risks leaving zero-byte or partial proxy files that can poison future loads.

### Preserve viewport geometry for compatible camera replacements

When a replacement camera has the same source dimensions as the active camera, the existing native viewport corners should be preserved exactly after the replacement succeeds. When dimensions differ but aspect ratio is compatible, the implementation may proportionally scale the native viewport if the result remains valid. When aspect ratio is incompatible or the scaled geometry is invalid, the viewport should be reset or repaired to a valid default.

Rationale: repeated trials from the same experiment are likely to have the heatmap display in roughly the same place, so preserving viewport placement saves work. Different aspect ratios may indicate cropping, padding, rotation, or a different capture layout where automatic scaling could look plausible but be wrong.

### Use bounded parallelism by job category

The first implementation should allow camera and H5 work to overlap, but avoid unbounded concurrency. Proxy/transcode jobs should run one at a time. H5/resource-load jobs may run alongside one proxy job. Preview-frame jobs should use latest-request-wins behavior rather than queueing stale work.

Rationale: ffmpeg proxy builds can consume substantial CPU/disk bandwidth. Bounded parallelism preserves responsiveness while still allowing useful cross-resource work.

### Keep export synchronous/modal for this change

Synced video export remains out of the resource job system. The export action should be unavailable while camera or H5 resources required by export are loading, replacing, or otherwise not in a stable loaded state.

Rationale: background export requires a complete snapshot of all export-relevant state. That is valuable future work, but adding it here increases risk and scope.

### Clear peak JSON on successful H5 replacement

When a different H5 successfully replaces the current H5, the imported Radar Peak (JSON) datasource should be cleared automatically.

Rationale: peak JSON is derived from a specific H5 source and is overwhelmingly likely to be invalid after H5 replacement. Automatic clearing is less error-prone than keeping a stale datasource with warnings.

## Risks / Trade-offs

- [Risk] Background results apply after the user has requested a different file. -> Use per-resource generation tokens and ignore stale completions.
- [Risk] Worker-owned OpenCV/HDF5 objects are unsafe to use from the main thread. -> Do not hand live thread-owned HDF5/OpenCV handles to the UI; use immutable loaded data or a worker-owned actor with explicit requests.
- [Risk] Cancelled proxy generation leaves a partial cache file. -> Write to a temporary path and atomically promote only successful proxy output.
- [Risk] Proxy failure leaves camera unusable. -> Report the proxy failure in the Resources window and affected camera panel; allow replacement/retry rather than silently falling back to full-resolution interaction.
- [Risk] Resource panel becomes too busy if many future jobs exist. -> Scope this change to current resource rows; defer a separate jobs drawer/table until there are enough job types to justify it.
- [Risk] Export becomes confusing while resources are pending. -> Keep export unchanged and disable it unless required camera and H5 resources are stable and loaded.
- [Risk] Tests involving Qt threads are flaky on Windows. -> Favor focused unit tests for job state/reducer behavior and minimal GUI tests for user-visible resource states.

## Migration Plan

- Preserve existing session JSON compatibility.
- Introduce pending-resource state as runtime GUI state only.
- Update resource summaries and Resources window rows to include loading, waiting, cancelling, and failed job states.
- Keep existing synchronous APIs available internally while migrating camera and H5 load actions to the job manager.
- Leave export implementation unchanged.

## Open Questions

- Should proxy progress be a real percentage if ffmpeg progress parsing is straightforward, or an indeterminate busy state for the first implementation?
- Should current MAT and peak JSON loads be routed through the job manager immediately for consistency, or remain synchronous until larger files demonstrate a need?
