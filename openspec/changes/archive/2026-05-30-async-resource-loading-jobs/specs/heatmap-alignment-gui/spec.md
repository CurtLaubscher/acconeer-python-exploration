## ADDED Requirements

### Requirement: Background resource jobs
The system SHALL run long-running heatmap alignment resource preparation work without blocking the main GUI event loop.

#### Scenario: Load camera video without freezing UI
- **WHEN** the user starts loading a camera video that requires preview proxy generation
- **THEN** the system keeps the main window and Resources window responsive while the camera resource job is running

#### Scenario: Load H5 recording without freezing UI
- **WHEN** the user starts loading a Radar Raw (H5) recording
- **THEN** the system keeps the main window and Resources window responsive while the H5 resource job is running

#### Scenario: Load different resource types concurrently
- **WHEN** one resource type is loading and the user starts loading a different resource type
- **THEN** the system accepts the second load request without requiring the first load request to finish first

#### Scenario: Bound expensive resource concurrency
- **WHEN** multiple expensive resource jobs are requested
- **THEN** the system schedules them with bounded concurrency so proxy generation and file loading do not create unbounded background work

### Requirement: Pending resource replacement
The system SHALL treat a pending same-resource load request as replaceable by the newest request while preserving the last successfully loaded resource until a replacement succeeds.

#### Scenario: Supersede pending camera load
- **WHEN** a camera video load is pending and the user starts loading another camera video
- **THEN** the system supersedes the earlier pending camera load without asking the user to cancel it first

#### Scenario: Cancel superseded in-flight camera work promptly
- **WHEN** a camera video load is superseded while preview proxy generation or other in-flight camera preparation is still running
- **THEN** the system actively requests cancellation of the superseded work, including terminating an active preview-proxy ffmpeg process when possible, so the newest camera load request is not blocked waiting for discarded work to finish

#### Scenario: Ignore stale camera load result
- **WHEN** a superseded camera load finishes after a newer camera load request has started
- **THEN** the system ignores the stale result and does not apply it to the session or previews

#### Scenario: Restore previous camera after replacement failure
- **WHEN** a loaded camera video exists and a replacement camera video fails to load
- **THEN** the system keeps the previous camera video as the active camera resource and restores its usable preview state

#### Scenario: Restore previous H5 after replacement failure
- **WHEN** a loaded Radar Raw (H5) recording exists and a replacement H5 recording fails to load
- **THEN** the system keeps the previous H5 recording as the active H5 resource and restores its usable rendered-heatmap state

#### Scenario: Apply session resource path after replacement success
- **WHEN** a pending resource replacement finishes successfully
- **THEN** the system updates the active session resource path and metadata to the replacement resource

#### Scenario: Do not apply failed resource path to session
- **WHEN** a pending resource replacement fails or is superseded
- **THEN** the system does not update the active session resource path to the failed or superseded file

#### Scenario: Preserve viewport for same-size camera replacement
- **WHEN** a replacement camera video successfully loads with the same source dimensions as the previously active camera video
- **THEN** the system preserves the existing native viewport corner coordinates for the replacement camera

#### Scenario: Handle different-size camera replacement viewport
- **WHEN** a replacement camera video successfully loads with different source dimensions than the previously active camera video
- **THEN** the system either proportionally scales the existing viewport when the source aspect ratio is compatible and the scaled viewport remains valid, or resets or repairs the viewport to a valid default

#### Scenario: Do not retain invalid viewport after incompatible camera replacement
- **WHEN** a replacement camera video successfully loads and the previous viewport corners cannot be preserved or scaled into valid geometry for the replacement source dimensions
- **THEN** the system resets or repairs the viewport to a valid default instead of retaining previous-camera corners that are out of bounds for the replacement source

### Requirement: Camera proxy readiness
The system SHALL require a usable low-quality camera preview source before enabling normal camera playback and scrubbing for a newly loaded high-resolution camera video.

#### Scenario: Show proxy loading state
- **WHEN** a camera video preview proxy is being generated
- **THEN** the camera preview panel shows a loading state identifying the target video filename rather than enabling sluggish full-resolution interaction

#### Scenario: Enable camera interaction after proxy ready
- **WHEN** the camera preview proxy is ready and the camera resource is applied
- **THEN** the system enables normal camera preview, playback, scrubbing, and viewport interaction for that camera

#### Scenario: Report proxy generation failure
- **WHEN** preview proxy generation fails for a camera video that requires a proxy
- **THEN** the system marks the camera load as failed and exposes the failure reason in the resource UI without falling back to full-resolution interactive preview

#### Scenario: Require ffmpeg for large-camera proxy preparation
- **WHEN** a camera video requires preview proxy generation and ffmpeg is unavailable
- **THEN** the system reports the camera load as failed with an explicit ffmpeg-missing reason rather than enabling full-resolution interactive preview as a fallback

#### Scenario: Reuse cached proxy quickly
- **WHEN** a camera video has an existing valid preview proxy
- **THEN** the system may apply the camera resource after reusing the cached proxy without rebuilding it

### Requirement: Preview proxy cache integrity
The system SHALL prevent failed, cancelled, or superseded preview proxy generation from leaving partial files that can be reused as valid cached proxies.

#### Scenario: Promote proxy only after successful generation
- **WHEN** the system generates a preview proxy for a camera video
- **THEN** it writes the in-progress proxy output to a temporary path and promotes it to the final cache path only after successful proxy generation

#### Scenario: Do not reuse cancelled proxy output
- **WHEN** preview proxy generation is cancelled, fails, or is superseded before successful completion
- **THEN** the system does not leave a final cache-path proxy file for that incomplete output

### Requirement: H5 background load ownership
The system SHALL complete background H5 loading without transferring unsafe worker-owned HDF5-backed state to the main GUI thread.

#### Scenario: Avoid unsafe H5 handle transfer
- **WHEN** a background H5 load job completes
- **THEN** the system either applies immutable loaded data that is safe for main-thread ownership or keeps H5-backed access owned by a worker with explicit asynchronous requests

#### Scenario: Avoid reintroducing H5 UI freeze
- **WHEN** a background H5 load job succeeds
- **THEN** the system does not perform another long-running H5 initialization step on the main GUI thread before presenting the loaded H5 resource

#### Scenario: Reuse worker-computed H5 render settings on adoption
- **WHEN** a background H5 load job computed resolved fixed color levels or other expensive render settings off the GUI thread
- **THEN** the main thread adopts those worker-computed settings from the load payload instead of repeating the same expensive computation during resource application

#### Scenario: Release H5 record on worker preparation failure
- **WHEN** background H5 loading fails after opening the heatmap record but before producing an immutable load payload
- **THEN** the system releases the HDF5-backed record handle

### Requirement: Resource loading presentation
The system SHALL present pending, failed, and cancelled resource work in the Resources window and affected preview panels.

#### Scenario: Show loading resource row
- **WHEN** a resource load or replacement is pending
- **THEN** the Resources window shows that resource row as loading, building, waiting, or cancelling with the target filename visible

#### Scenario: Show waiting while queued for bounded work
- **WHEN** a resource job is accepted but blocked waiting for a bounded expensive-work slot such as the single preview-proxy transcode slot
- **THEN** the Resources window and affected preview presentation show the job as waiting for that target filename rather than as actively loading or building

#### Scenario: Show affected panel loading overlay
- **WHEN** the camera or rendered heatmap preview cannot show the pending target resource yet
- **THEN** the affected preview panel shows a loading overlay with the target filename instead of stale unlabeled preview content

#### Scenario: Use filename in loading overlay
- **WHEN** a resource panel or preview overlay identifies a pending load target
- **THEN** the visible loading text includes the filename without requiring the full path

#### Scenario: Provide resource job cancellation
- **WHEN** a cancellable resource job is pending
- **THEN** the Resources window provides a row-scoped cancel action for that pending job

#### Scenario: Cancel pending replacement
- **WHEN** the user cancels a pending replacement for a resource that already has an active loaded value
- **THEN** the system leaves the active loaded resource in effect and restores its usable preview state

#### Scenario: Cancel wins before late success is applied
- **WHEN** the user cancels a pending resource job before that job's completion is accepted on the GUI thread
- **THEN** the system treats the job as cancelled, releases any late success payload, and does not apply the cancelled target as the active resource

#### Scenario: Show cancellation promptly
- **WHEN** the user cancels a pending resource job whose underlying file operation cannot stop immediately
- **THEN** the Resources window and affected previews show cancelling or restored state promptly without waiting for the underlying operation to return

#### Scenario: Do not stack placeholder and loading text
- **WHEN** a preview panel is showing a loading overlay and does not yet have target content to display
- **THEN** the panel shows a single coherent loading message rather than drawing placeholder panel text underneath the loading message

#### Scenario: Show viewport loading state for pending dependencies
- **WHEN** the viewport preview depends on a camera or H5 resource that is pending, replacing, waiting, or cancelling
- **THEN** the viewport preview shows the same resource-loading state as an affected panel instead of presenting stale viewport content as if it belonged to the pending target

### Requirement: Workbench lifecycle during resource jobs
The system SHALL cancel or abandon active camera and H5 resource jobs safely when the workbench is closed or reset so late completions cannot mutate a closed session.

#### Scenario: Abandon jobs on window close
- **WHEN** the main workbench window closes while a camera or H5 resource job is pending
- **THEN** the system cancels or abandons those jobs, clears pending job state and replacement backups, and does not apply their completions to a later workbench instance

#### Scenario: Ignore worker completion after manager deletion
- **WHEN** a background resource worker completes after the workbench has been closed and its job manager QObject is no longer alive
- **THEN** the worker completion path exits without raising a traceback and without attempting to update deleted GUI objects

#### Scenario: Abandoned manager skips worker dispatch
- **WHEN** resource jobs are abandoned during window close, session close, or workbench reset
- **THEN** late worker runnables observe the abandoned state before dispatch, release any completed payload without applying it, and do not raise a traceback

#### Scenario: Abandon jobs on session close
- **WHEN** the user closes the current session and returns to an empty workbench while a camera or H5 resource job is pending
- **THEN** the system cancels or abandons those jobs, clears pending job state and replacement backups, and does not apply their completions to the reset session

#### Scenario: Discard stale pending job payloads
- **WHEN** a superseded or otherwise ignored camera or H5 job completion would leave a pending result payload unused
- **THEN** the system discards that payload promptly so stale results cannot retain HDF5-backed records or other resources in manager state

### Requirement: H5 replacement clears peak datasource
The system SHALL clear imported Radar Peak (JSON) datasource state when a different Radar Raw (H5) resource successfully replaces the current H5 recording.

#### Scenario: Clear peaks after different H5 replacement
- **WHEN** a new H5 recording successfully replaces a different active H5 recording
- **THEN** the system unloads the imported Radar Peak (JSON) datasource and updates the Resources window accordingly

#### Scenario: Preserve peaks after failed H5 replacement
- **WHEN** a pending H5 replacement fails before becoming active
- **THEN** the system preserves the previously active H5 recording and any peak datasource that remained valid for it

### Requirement: Export availability during resource jobs
The system SHALL keep synced video export outside the background resource job system for this change while preventing export from starting with unstable required resources.

#### Scenario: Disable export while camera is loading
- **WHEN** a camera video load or replacement is pending
- **THEN** the system disables starting synced video export

#### Scenario: Disable export while H5 is loading
- **WHEN** a Radar Raw (H5) load or replacement is pending
- **THEN** the system disables starting synced video export

#### Scenario: Allow export when required resources are stable
- **WHEN** camera video and Radar Raw (H5) resources are loaded and no required export resource is in an in-flight load, replace, or cancel phase
- **THEN** the system allows synced video export according to the existing export requirements

#### Scenario: Allow export after failed replacement with restore
- **WHEN** a camera or H5 replacement fails and the system restores the previously active required resources
- **THEN** the system allows synced video export when camera and H5 are loaded and no required export resource is in an in-flight job phase

#### Scenario: Failed job status does not alone block export
- **WHEN** a resource job slot is in `failed` phase because the last load attempt failed but required export resources remain loaded and stable
- **THEN** starting synced video export is not disabled solely because of the failed job phase

#### Scenario: Preserve existing export progress behavior
- **WHEN** synced video export is running
- **THEN** the system uses the existing export progress behavior and prevents starting a second export simultaneously
