## MODIFIED Requirements

### Requirement: Resources window actions
The system SHALL allow users to manage resources from the Resources window.

#### Scenario: Load unloaded resource
- **WHEN** the user selects an unloaded primary resource row and invokes its load action
- **THEN** the system opens the appropriate file picker and starts loading that resource into the selected slot

#### Scenario: Replace loaded resource
- **WHEN** the user selects a loaded primary resource row and invokes its load or replace action
- **THEN** the system clears the currently active resource from that slot before starting the replacement load, presents the target as pending/loading, and does not allow the previous resource to remain active while the target is pending

#### Scenario: Import peak series from Resources window
- **WHEN** the user invokes Import Peak Series from the Resources window
- **THEN** the system opens the appropriate file picker and appends the imported peak series as a separate resource row after validation

#### Scenario: Generate peak series from Resources window
- **WHEN** Radar Raw (H5) is loaded, no H5 load or replacement is pending, and the user invokes Generate Peak Series from the Resources window
- **THEN** the system opens the Generate Peak Series dialog for the active loaded H5 resource

#### Scenario: Unload optional resource row
- **WHEN** the user selects a loaded optional resource row and invokes its unload action
- **THEN** the system clears that resource row without unloading unrelated resources

#### Scenario: Unload primary resource row
- **WHEN** the user selects a loaded Camera Video or Radar Raw (H5) row and invokes its unload action
- **THEN** the system clears that primary resource slot and dependent preview state without unloading unrelated resources that remain valid independently

#### Scenario: Unload camera preserves independent radar resources
- **WHEN** the user unloads Camera Video while Radar Raw (H5), peak series resources, or Leg2 MAT resources are loaded
- **THEN** the system clears camera-dependent preview, timeline, viewport, and export state while preserving the loaded radar and Leg2 resources that remain valid

#### Scenario: Unload H5 preserves independent signal resources
- **WHEN** the user unloads Radar Raw (H5) while peak series resources or Leg2 MAT resources are loaded
- **THEN** the system clears radar-H5-dependent rendered heatmap and radar timeline state while preserving loaded peak series and Leg2 MAT resources as signal resources when their loaded data remains available

#### Scenario: Signal resources without H5
- **WHEN** Radar Raw (H5) is not loaded and peak series resources, Leg2 MAT, both, or neither are loaded
- **THEN** the Signals and Timeline areas display whichever optional signal resources are loaded against the shared absolute zero-time coordinate

#### Scenario: Reload remembered resource
- **WHEN** the user selects a resource row with a remembered path and invokes reload
- **THEN** the system loads the remembered path using the same immediate-clear behavior as load or replace when the requested identity differs from the active resource identity

#### Scenario: Reveal resource path
- **WHEN** the Resources window or resource row context menu shows the action that opens the platform file browser
- **THEN** invoking that action reveals the resource path without changing loaded resources

#### Scenario: Context menu mirrors row actions
- **WHEN** the user opens a Resources row context menu
- **THEN** the context menu offers the same applicable row-scoped actions as the Resources window selected-row controls, including save, save as, reload, and unload for peak series rows when applicable

#### Scenario: Ignore empty table action target
- **WHEN** the user invokes a row action without a selected applicable resource row
- **THEN** the system is not required to start a load or replace action

#### Scenario: Clear all resources asks confirmation
- **WHEN** the user invokes Clear All Resources from the Resources window and confirms the action
- **THEN** the system clears loaded resources and dependent preview state while preserving the current session path

#### Scenario: Clear all resources message
- **WHEN** the user invokes Clear All Resources
- **THEN** the confirmation message tells the user that loaded resources will be cleared and the current session path will be kept

#### Scenario: Clear all resources with unsaved peaks
- **WHEN** unsaved generated peak series exist and the user invokes Clear All Resources
- **THEN** the system includes the unsaved peak-loss warning in the confirmation flow before discarding those peaks

#### Scenario: Save peak series from Resources window
- **WHEN** a peak series row with in-memory measurements is selected and the user invokes Save or Save As
- **THEN** the system writes that selected peak series to canonical peak-distance JSON according to the peak-save requirements

### Requirement: Pending resource replacement
The system SHALL treat a pending same-resource load request as replaceable by the newest request while clearing any differing active resource from that slot before the new load begins.

The system SHALL NOT keep a previous active resource available as the active value for a slot while a different resource identity is pending for that slot. If the pending load fails, the slot SHALL remain empty or failed and SHALL NOT automatically restore the previous active resource.

#### Scenario: Supersede pending camera load
- **WHEN** a camera video load is pending and the user starts loading another camera video
- **THEN** the system supersedes the earlier pending camera load without asking the user to cancel it first

#### Scenario: Cancel superseded in-flight camera work promptly
- **WHEN** a camera video load is superseded while preview proxy generation or other in-flight camera preparation is still running
- **THEN** the system actively requests cancellation of the superseded work, including terminating an active preview-proxy ffmpeg process when possible, so the newest camera load request is not blocked waiting for discarded work to finish

#### Scenario: Ignore stale camera load result
- **WHEN** a superseded camera load finishes after a newer camera load request has started
- **THEN** the system ignores the stale result and does not apply it to the session or previews

#### Scenario: Clear previous camera before replacement
- **WHEN** a loaded camera video exists and the user starts loading a different camera video
- **THEN** the system clears the previous camera video, camera preview, camera-dependent viewport/export state, and active camera metadata before the replacement load is presented as pending

#### Scenario: Clear previous H5 before replacement
- **WHEN** a loaded Radar Raw (H5) recording exists and the user starts loading a different H5 recording or a different H5 selection identity
- **THEN** the system clears the previous active H5 recording, rendered heatmap state, H5 axes/hover caches, H5 timeline metadata, and H5-derived action readiness before the replacement load is presented as pending

#### Scenario: Failed camera replacement leaves slot failed
- **WHEN** a loaded camera video existed and a replacement camera video fails to load
- **THEN** the system leaves the camera slot empty or failed, reports the failure in the Resources window, and does not automatically restore the previous camera video

#### Scenario: Failed H5 replacement leaves slot failed
- **WHEN** a loaded Radar Raw (H5) recording existed and a replacement H5 recording fails to load
- **THEN** the system leaves the H5 slot empty or failed, reports the failure in the Resources window, and does not automatically restore the previous H5 recording

#### Scenario: Apply session resource path after replacement success
- **WHEN** a pending resource replacement finishes successfully
- **THEN** the system updates the active session resource path and metadata to the replacement resource

#### Scenario: Do not apply failed resource path to loaded metadata
- **WHEN** a pending resource replacement fails or is superseded
- **THEN** the system does not present the failed or superseded file as a loaded resource, while it may keep the failed target path visible as the row's pending or failed request for retry/reload purposes

#### Scenario: Preserve viewport for same-size camera replacement
- **WHEN** a replacement camera video successfully loads with the same source dimensions as the previously active camera video and the previous viewport geometry was preserved as session state
- **THEN** the system preserves the existing native viewport corner coordinates for the replacement camera

#### Scenario: Handle different-size camera replacement viewport
- **WHEN** a replacement camera video successfully loads with different source dimensions than the previously active camera video
- **THEN** the system either proportionally scales the existing viewport when the source aspect ratio is compatible and the scaled viewport remains valid, or resets or repairs the viewport to a valid default

#### Scenario: Do not retain invalid viewport after incompatible camera replacement
- **WHEN** a replacement camera video successfully loads and the previous viewport corners cannot be preserved or scaled into valid geometry for the replacement source dimensions
- **THEN** the system resets or repairs the viewport to a valid default instead of retaining previous-camera corners that are out of bounds for the replacement source

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

#### Scenario: Cancel pending load
- **WHEN** the user cancels a pending load or replacement for a resource slot
- **THEN** the system cancels or abandons the pending target, leaves the slot empty or failed if a different active resource was already cleared for that target, and does not restore stale data automatically

#### Scenario: Cancel wins before late success is applied
- **WHEN** the user cancels a pending resource job before that job's completion is accepted on the GUI thread
- **THEN** the system treats the job as cancelled, releases any late success payload, and does not apply the cancelled target as the active resource

#### Scenario: Show cancellation promptly
- **WHEN** the user cancels a pending resource job whose underlying file operation cannot stop immediately
- **THEN** the Resources window and affected previews show cancelling or cleared state promptly without waiting for the underlying operation to return

#### Scenario: Do not stack placeholder and loading text
- **WHEN** a preview panel is showing a loading overlay and does not yet have target content to display
- **THEN** the panel shows a single coherent loading message rather than drawing placeholder panel text underneath the loading message

#### Scenario: Show viewport loading state for pending dependencies
- **WHEN** the viewport preview depends on a camera or H5 resource that is pending, replacing, waiting, or cancelling
- **THEN** the viewport preview shows the same resource-loading state as an affected panel instead of presenting stale viewport content as if it belonged to the pending target

### Requirement: Workbench lifecycle during resource jobs
The system SHALL cancel or abandon active camera and H5 resource jobs safely when the workbench is closed or reset to an empty session so late completions cannot mutate a closed session, and SHALL reconcile resource slots on saved session open so unchanged identities use **keep** without abandoning matching in-flight jobs.

#### Scenario: Abandon jobs on window close
- **WHEN** the main workbench window closes while a camera or H5 resource job is pending
- **THEN** the system cancels or abandons those jobs, clears pending job state and stale slot state, and does not apply their completions to a later workbench instance

#### Scenario: Ignore worker completion after manager deletion
- **WHEN** a background resource worker completes after the workbench has been closed and its job manager QObject is no longer alive
- **THEN** the worker completion path exits without raising a traceback and without attempting to update deleted GUI objects

#### Scenario: Abandoned manager skips worker dispatch
- **WHEN** resource jobs are abandoned during window close, session close, or workbench reset to an empty session
- **THEN** late worker runnables observe the abandoned state before dispatch, release any completed payload without applying it, and do not raise a traceback

#### Scenario: Abandon jobs on session close
- **WHEN** the user closes the current session and returns to an empty workbench while a camera or H5 resource job is pending
- **THEN** the system cancels or abandons those jobs, clears pending job state and stale slot state, and does not apply their completions to the reset session

#### Scenario: Discard stale pending job payloads
- **WHEN** a superseded or otherwise ignored camera or H5 job completion would leave a pending result payload unused
- **THEN** the system discards that payload promptly so stale results cannot retain HDF5-backed records or other resources in manager state

#### Scenario: Do not abandon matching jobs on session open
- **WHEN** the user opens a saved alignment session and reconciliation selects **keep** for a camera or H5 slot with an in-flight job for the same resource identity
- **THEN** the system does not abandon that in-flight job solely because of the session open

### Requirement: H5 replacement preserves independent peak series
The system SHALL preserve peak series resources as optional signal resources when a different Radar Raw (H5) resource is requested or successfully replaces the current H5 recording, unless a session-open reconciliation or explicit clear/unload operation removes those peak resources.

The system SHALL NOT automatically unload all peak series solely because H5 changed. Imported peak series validation warnings SHALL remain row-specific. Generated peak series that remain after H5 replacement SHALL continue to behave as signal resources until the user unloads them, clears all resources, or opens another session. H5-derived actions SHALL NOT use preserved peak series or stale H5 data as a substitute for an active loaded H5 resource.

#### Scenario: Preserve peak series after H5 replacement request
- **WHEN** a new H5 recording is requested while peak series resources exist
- **THEN** the system may preserve existing peak series resources as independent signal resources while clearing the previous active H5 recording and H5-dependent rendered heatmap state

#### Scenario: Preserve peak series after different H5 replacement succeeds
- **WHEN** a new H5 recording successfully replaces a different active H5 recording while peak series resources exist
- **THEN** the system preserves the existing peak series resources and updates H5-dependent rendered heatmap state for the new H5

#### Scenario: Preserve peaks after failed H5 replacement without restoring H5
- **WHEN** a pending H5 replacement fails before becoming active
- **THEN** the system preserves independent peak series resources but leaves the H5 slot empty or failed instead of restoring the previously active H5 recording

### Requirement: Export availability during resource jobs
The system SHALL keep synced video export outside the background resource job system for this change while preventing export from starting with unstable or unavailable required resources.

#### Scenario: Disable export while camera is loading
- **WHEN** a camera video load or replacement is pending
- **THEN** the system disables starting synced video export

#### Scenario: Disable export while H5 is loading
- **WHEN** a Radar Raw (H5) load or replacement is pending
- **THEN** the system disables starting synced video export

#### Scenario: Allow export when required resources are stable
- **WHEN** camera video and Radar Raw (H5) resources are loaded and no required export resource is in an in-flight load, replace, or cancel phase
- **THEN** the system allows synced video export according to the existing export requirements

#### Scenario: Failed replacement does not allow export without resources
- **WHEN** a camera or H5 replacement fails after clearing the previous active required resource
- **THEN** the system keeps synced video export disabled until the required camera and H5 resources are loaded again

#### Scenario: Failed job status does not alone block export
- **WHEN** a resource job slot is in `failed` phase because the last load attempt failed but required export resources are loaded and stable
- **THEN** starting synced video export is not disabled solely because of the failed job phase

#### Scenario: Preserve existing export progress behavior
- **WHEN** synced video export is running
- **THEN** the system uses the existing export progress behavior and prevents starting a second export simultaneously

### Requirement: Session load reconciliation
The system SHALL load a saved alignment session by reconciling the session JSON snapshot against the active workbench state rather than unconditionally tearing down every loaded resource on each open.

Reconciliation SHALL iterate a registered set of resource slots (camera video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT for the current workbench) and, for each slot, SHALL choose one of:

- **keep** - the desired resource identity from the session matches the active loaded resource or an in-flight resource job for that slot; the system does not close, unload, abandon, or restart load work for that slot solely because of the session open
- **load** - the session requests a non-empty resource identity that does not match the active or in-flight identity, or the slot is not loaded; the system clears any differing active resource for that slot before starting load work for the desired identity
- **unload** - the session requests an empty path for that slot but the slot is still loaded; the system clears or unloads that resource so it does not remain active from a previous session

Resource identity SHALL be determined from session content, not from the session JSON file path on disk. Camera identity is the camera video path. H5 identity is the H5 file path plus session, group, entry, and subsweep indices. Radar Peak (JSON) identity is the peak-distance JSON path. Leg2 MAT identity is the Leg2 MAT path. An empty path means the slot is not requested.

After resource reconciliation, the system SHALL always apply non-resource session fields from the JSON snapshot, including viewport geometry, render settings, timeline state, export overlay, signal plot view, preview state, Leg2 offset, and selected Leg2 signal kind, even when one or more resource slots used **keep**.

Before starting H5 **load** actions, the system SHALL assign the desired session snapshot to the active workbench session object so H5 selection indices read during H5 load setup match the session being opened.

#### Scenario: Keep camera slot when identity matches
- **WHEN** the user loads a saved alignment session whose camera video path matches the active camera resource or matches the target of an in-flight camera resource job
- **THEN** the system reconciles the camera slot as **keep** and does not close the active camera source or abandon the in-flight camera job solely because of the session open

#### Scenario: Keep H5 slot when identity matches
- **WHEN** the user loads a saved alignment session whose H5 path and selection indices match the active H5 resource or match the target of an in-flight H5 job
- **THEN** the system reconciles the H5 slot as **keep** and does not close the active H5 source or abandon the in-flight H5 job solely because of the session open

#### Scenario: Load camera when session requests different identity
- **WHEN** the user loads a saved alignment session whose camera video path differs from the active camera resource and in-flight camera job target
- **THEN** the system clears the active camera slot and starts camera loading using the same background camera resource job behavior as an explicit camera load or reload

#### Scenario: Load H5 when session requests different identity
- **WHEN** the user loads a saved alignment session whose H5 path or selection indices differ from the active H5 resource and in-flight H5 job target
- **THEN** the system clears the active H5 slot and starts H5 loading using the same background H5 resource job behavior as an explicit H5 load or reload

#### Scenario: Unload camera when session omits path
- **WHEN** the user loads a saved alignment session whose camera video path is empty and a camera video resource is still loaded from a previous session
- **THEN** the system reconciles the camera slot as **unload** and unloads the camera video so no camera resource remains active

#### Scenario: Unload H5 when session omits path
- **WHEN** the user loads a saved alignment session whose H5 path is empty and a radar raw H5 resource is still loaded from a previous session
- **THEN** the system reconciles the H5 slot as **unload** and unloads the H5 recording so no H5 resource remains active

#### Scenario: Unload peak JSON when session omits path
- **WHEN** the user loads a saved alignment session whose peak-distance JSON path is empty and a peak-distance datasource is still loaded from a previous session
- **THEN** the system reconciles the Radar Peak (JSON) slot as **unload** and clears the peak-distance datasource

#### Scenario: Unload Leg2 MAT when session omits path
- **WHEN** the user loads a saved alignment session whose Leg2 MAT path is empty and a Leg2 MAT datasource is still loaded from a previous session
- **THEN** the system reconciles the Leg2 MAT slot as **unload** and clears the Leg2 MAT datasource

#### Scenario: Apply session fields after reconciliation
- **WHEN** the user loads a saved alignment session and one or more resource slots reconcile as **keep**
- **THEN** the system still restores session fields from the JSON snapshot that are not satisfied by **keep** alone, such as viewport geometry, render settings, timeline state, preview state, export overlay settings, Leg2 offset, and selected Leg2 signal kind

#### Scenario: Keep GUI responsive when slots use keep
- **WHEN** the user opens a saved alignment session and all resource slots reconcile as **keep**
- **THEN** the system does not block the GUI thread on redundant camera proxy, H5, peak JSON, or Leg2 MAT reload work for those slots

#### Scenario: Keep GUI responsive during session open
- **WHEN** the user opens a saved alignment session that requires background camera or H5 resource work for slots reconciled as **load**
- **THEN** the system keeps the main window and Resources window responsive on the GUI thread while that work continues, using the same non-blocking resource job presentation as explicit resource loads

#### Scenario: Failed session-open load leaves slot failed
- **WHEN** the user opens a saved alignment session that requests a different camera or H5 resource and that resource fails to load
- **THEN** the corresponding slot remains empty or failed and the system does not restore the previous session's resource for that slot

### Requirement: In-app peak generation from loaded H5
The system SHALL allow the user to generate peak series measurements from the currently loaded Radar Raw (H5) recording without leaving the heatmap alignment workbench.

Generation SHALL use the loaded H5 session, group, entry, and subsweep indices from the active current heatmap track. Generation SHALL process all frames. Generation SHALL use the selected algorithm and threshold from the Generate Peak Series dialog.

The system SHALL enable Generate Peak Series only when Radar Raw (H5) is loaded, the active loaded H5 identity matches the current H5 slot/session request, and no H5 load, replacement, cancellation, or waiting job is pending. The system SHALL disable or omit Generate Peak Series when H5 is not loaded or when the H5 slot is pending, failed, cancelling, waiting, or stale.

Generation SHALL run synchronously on the GUI thread for v1 unless implementation measurements show that background execution is necessary, and SHALL reuse the in-memory H5 record rather than re-opening the file through `export_peak_distances()`.

#### Scenario: Generate peaks from loaded H5
- **WHEN** Radar Raw (H5) is loaded, no H5 load or replacement is pending, and the user confirms the Generate Peak Series dialog
- **THEN** the system computes peak-distance measurements from the active loaded H5 and appends them as a new unsaved peak series resource without writing JSON to disk

#### Scenario: Generate disabled without H5
- **WHEN** Radar Raw (H5) is not loaded
- **THEN** the system does not offer a usable Generate Peak Series action

#### Scenario: Generate disabled while H5 load is pending
- **WHEN** a Radar Raw (H5) load, replacement, waiting, or cancellation job is pending
- **THEN** the system does not offer a usable Generate Peak Series action and does not generate peaks from any previous H5 data

#### Scenario: Generate blocked from stale H5 object
- **WHEN** an old H5 object or peak series remains in memory but the active H5 slot no longer matches the current requested H5 identity
- **THEN** Generate Peak Series does not use that stale object and reports or presents H5 as unavailable for generation

#### Scenario: Refresh UI after generate
- **WHEN** peak generation completes successfully
- **THEN** the system updates the Signals plot, rendered-heatmap peak selector, rendered-heatmap marker, and Resources rows without requiring a separate import step

#### Scenario: Generate does not replace peak series
- **WHEN** the user invokes Generate Peak Series while peak series already exist
- **THEN** the system appends the newly generated peak series and preserves existing peak series
