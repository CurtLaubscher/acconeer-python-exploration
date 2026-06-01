## ADDED Requirements

### Requirement: Session load reconciliation
The system SHALL load a saved alignment session by reconciling the session JSON snapshot against the active workbench state rather than unconditionally tearing down every loaded resource on each open.

Reconciliation SHALL iterate a registered set of resource slots (camera video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT for the current workbench) and, for each slot, SHALL choose one of:

- **keep** — the desired resource identity from the session matches the active loaded resource or an in-flight resource job for that slot; the system does not close, unload, abandon, or restart load work for that slot solely because of the session open
- **load** — the session requests a non-empty resource identity that does not match the active or in-flight identity, or the slot is not loaded; the system loads or replaces that resource using the same behavior as an explicit resource load or reload, including pending replacement and restore-on-failure when a different resource was already loaded, without pre-clearing the active resource before starting the load
- **unload** — the session requests an empty path for that slot but the slot is still loaded; the system clears or unloads that resource so it does not remain active from a previous session

Resource identity SHALL be determined from session content, not from the session JSON file path on disk. Camera identity is the camera video path. H5 identity is the H5 file path plus session, group, entry, and subsweep indices. Radar Peak (JSON) identity is the peak-distance JSON path. Leg2 MAT identity is the Leg2 MAT path. An empty path means the slot is not requested.

After resource reconciliation, the system SHALL always apply non-resource session fields from the JSON snapshot, including viewport geometry, render settings, timeline state, export overlay, signal plot view, preview state, and optional datasource visibility or offset settings, even when one or more resource slots used **keep**.

Before starting H5 **load** actions, the system SHALL assign the desired session snapshot to the active workbench session object so H5 selection indices read during `load_h5_from_path` match the session being opened.

#### Scenario: Keep camera slot when identity matches
- **WHEN** the user loads a saved alignment session whose camera video path matches the active camera resource or matches the target of an in-flight camera resource job
- **THEN** the system reconciles the camera slot as **keep** and does not close the active camera source or abandon the in-flight camera job solely because of the session open

#### Scenario: Keep H5 slot when identity matches
- **WHEN** the user loads a saved alignment session whose H5 path and selection indices match the active H5 resource or match the target of an in-flight H5 resource job
- **THEN** the system reconciles the H5 slot as **keep** and does not close the active H5 source or abandon the in-flight H5 job solely because of the session open

#### Scenario: Load camera when session requests different identity
- **WHEN** the user loads a saved alignment session whose camera video path differs from the active camera resource and in-flight camera job target
- **THEN** the system reconciles the camera slot as **load** and starts camera loading using the same background camera resource job behavior as an explicit camera load or reload

#### Scenario: Load H5 when session requests different identity
- **WHEN** the user loads a saved alignment session whose H5 path or selection indices differ from the active H5 resource and in-flight H5 job target
- **THEN** the system reconciles the H5 slot as **load** and starts H5 loading using the same background H5 resource job behavior as an explicit H5 load or reload

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
- **THEN** the system still restores session fields from the JSON snapshot that are not satisfied by **keep** alone, such as viewport geometry, render settings, timeline state, preview state, and export overlay settings

#### Scenario: Keep GUI responsive when slots use keep
- **WHEN** the user opens a saved alignment session and all resource slots reconcile as **keep**
- **THEN** the system does not block the GUI thread on redundant camera proxy, H5, peak JSON, or Leg2 MAT reload work for those slots

#### Scenario: Keep GUI responsive during session open
- **WHEN** the user opens a saved alignment session that requires background camera or H5 resource work for slots reconciled as **load**
- **THEN** the system keeps the main window and Resources window responsive on the GUI thread while that work continues, using the same non-blocking resource job presentation as explicit resource loads

#### Scenario: No modal session loading dialog
- **WHEN** the user opens a saved alignment session
- **THEN** the system does not show a dedicated modal loading dialog for the session; loading state appears through existing Resources rows and affected preview loading presentation

## MODIFIED Requirements

### Requirement: Alignment session persistence
The system SHALL save and load JSON alignment session files containing the state needed to reproduce a manual alignment session, including any optional imported distance-measurement datasource.

#### Scenario: Save alignment session
- **WHEN** the user saves an alignment session
- **THEN** the system writes source paths, selected H5 session/group/entry/subsweep, render color limits, camera viewport corners, viewport output dimensions, export overlay settings, temporal offset in seconds, preprocessing settings, and optional imported distance-measurement datasource metadata to JSON

#### Scenario: Load alignment session
- **WHEN** the user loads a saved alignment session
- **THEN** the system restores the session snapshot described by the JSON file using session load reconciliation so each resource slot is kept, loaded, or unloaded as needed, restores source selections, viewport geometry, render settings, temporal offset, preview state, and optional imported distance-measurement datasource metadata, and always applies remaining non-resource session fields after reconciliation

### Requirement: Session startup CLI
The system SHALL allow the heatmap alignment GUI to load a saved alignment session on startup using a session-specific command-line argument.

#### Scenario: Load session on startup
- **WHEN** the user launches the heatmap alignment GUI with a saved alignment session path passed to `--session`
- **THEN** the system loads that saved alignment session after the main window is shown, scheduled on the GUI event loop so startup can paint the workbench before resource loading begins

#### Scenario: Session startup takes precedence over source startup arguments
- **WHEN** the user launches the heatmap alignment GUI with `--session` and individual camera or H5 startup arguments
- **THEN** the system loads the saved alignment session as the source of camera, H5, viewport, render, and alignment state rather than partially overriding it with the individual camera or H5 arguments

#### Scenario: Optional datasource startup arguments may override session datasources
- **WHEN** the user launches the heatmap alignment GUI with `--session` and an explicit optional datasource startup argument such as peak-distance JSON or Leg2 MAT
- **THEN** the system loads the saved alignment session first and then applies the explicit optional datasource startup argument using the same override behavior as the corresponding datasource requirement

#### Scenario: Reject legacy artifact startup argument
- **WHEN** the user launches the heatmap alignment GUI with the legacy `--artifact` startup argument
- **THEN** the command-line parser rejects the argument and presents help that lists `--session` as the saved alignment session startup argument

### Requirement: Workbench lifecycle during resource jobs
The system SHALL cancel or abandon active camera and H5 resource jobs safely when the workbench is closed or reset to an empty session so late completions cannot mutate a closed session, and SHALL reconcile resource slots on saved session open so unchanged identities use **keep** without abandoning matching in-flight jobs.

#### Scenario: Abandon jobs on window close
- **WHEN** the main workbench window closes while a camera or H5 resource job is pending
- **THEN** the system cancels or abandons those jobs, clears pending job state and replacement backups, and does not apply their completions to a later workbench instance

#### Scenario: Ignore worker completion after manager deletion
- **WHEN** a background resource worker completes after the workbench has been closed and its job manager QObject is no longer alive
- **THEN** the worker completion path exits without raising a traceback and without attempting to update deleted GUI objects

#### Scenario: Abandoned manager skips worker dispatch
- **WHEN** resource jobs are abandoned during window close, session close, or workbench reset to an empty session
- **THEN** late worker runnables observe the abandoned state before dispatch, release any completed payload without applying it, and do not raise a traceback

#### Scenario: Abandon jobs on session close
- **WHEN** the user closes the current session and returns to an empty workbench while a camera or H5 resource job is pending
- **THEN** the system cancels or abandons those jobs, clears pending job state and replacement backups, and does not apply their completions to the reset session

#### Scenario: Discard stale pending job payloads
- **WHEN** a superseded or otherwise ignored camera or H5 job completion would leave a pending result payload unused
- **THEN** the system discards that payload promptly so stale results cannot retain HDF5-backed records or other resources in manager state

#### Scenario: Do not abandon matching jobs on session open
- **WHEN** the user opens a saved alignment session and reconciliation selects **keep** for a camera or H5 slot with an in-flight job for the same resource identity
- **THEN** the system does not abandon that in-flight job solely because of the session open
