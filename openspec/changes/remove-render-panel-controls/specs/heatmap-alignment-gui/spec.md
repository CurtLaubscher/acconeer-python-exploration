## MODIFIED Requirements

### Requirement: Alignment session persistence
The system SHALL save and load JSON alignment session files containing the state needed to reproduce a manual alignment session, including any optional imported distance-measurement datasource.

#### Scenario: Save alignment session
- **WHEN** the user saves an alignment session
- **THEN** the system writes alignment session version `2`, source paths, selected H5 session/group/entry/subsweep, render color limits, camera viewport corners, viewport output dimensions, export overlay settings, temporal offset in seconds, preprocessing settings, and optional imported distance-measurement datasource metadata to JSON

#### Scenario: Save datasource state without retired visibility fields
- **WHEN** the user saves an alignment session with Radar Peak (JSON) or Leg2 MAT resources loaded
- **THEN** the system does not write peak-distance datasource visibility or Leg2 ultrasonic datasource visibility as authoritative session state

#### Scenario: Load alignment session
- **WHEN** the user loads a saved alignment session
- **THEN** the system restores the session snapshot described by the JSON file using session load reconciliation so each resource slot is kept, loaded, or unloaded as needed, restores source selections, viewport geometry, render settings, temporal offset, preview state, and optional imported distance-measurement datasource metadata, and always applies remaining non-resource session fields after reconciliation

#### Scenario: Load version 1 alignment session
- **WHEN** the user loads an alignment session with version `1`
- **THEN** the system migrates the session payload to version `2`, ignores retired peak-distance and Leg2 datasource visibility fields, and loads the migrated session without warning if no other load error occurs

#### Scenario: Reject unsupported future alignment session
- **WHEN** the user loads an alignment session with a version newer than the workbench supports
- **THEN** the system rejects the file with a clear unsupported-version load error

### Requirement: Imported distance-measurement datasource
The system SHALL allow the heatmap alignment GUI to import a generated peak-distance JSON file as an optional datasource alongside the camera video and H5 heatmap recording.

#### Scenario: Import peak-distance JSON
- **WHEN** the user imports a peak-distance JSON file generated from a recorded H5 log
- **THEN** the system loads the distance measurements as an optional datasource without replacing the camera video or H5 heatmap track

#### Scenario: Load peak-distance JSON on startup
- **WHEN** the user launches the heatmap alignment GUI with a peak-distance JSON startup argument
- **THEN** the system loads that file as the optional distance-measurement datasource during startup

#### Scenario: Load H5 and peak-distance JSON on startup
- **WHEN** the user launches the heatmap alignment GUI with both H5 recording and peak-distance JSON startup arguments
- **THEN** the system loads the H5 recording and validates the peak-distance datasource against it using the same import rules as interactive import

#### Scenario: Load session and peak-distance JSON on startup
- **WHEN** the user launches the heatmap alignment GUI with both a saved alignment session and a peak-distance JSON startup argument
- **THEN** the explicitly provided peak-distance JSON replaces any peak-distance datasource stored in the loaded session after validation

#### Scenario: Validate imported datasource metadata
- **WHEN** the imported peak-distance JSON contains source-selection metadata
- **THEN** the system compares that metadata with the loaded H5 heatmap track when one is present and warns the user if the source selection appears incompatible

#### Scenario: Reject incompatible row count
- **WHEN** the imported peak-distance JSON has a different number of measurement objects than the loaded H5 heatmap recording has frames
- **THEN** the system rejects the import and leaves the current peak-distance datasource unchanged

#### Scenario: Validate real-time axis
- **WHEN** the imported peak-distance JSON contains elapsed real-time seconds
- **THEN** the system verifies that the imported time range is compatible with the loaded H5 heatmap recording duration when one is present

#### Scenario: Preserve timeline rows
- **WHEN** the imported peak-distance JSON contains frames with no detection
- **THEN** the system preserves those rows so the imported datasource remains aligned to the source recording timeline

#### Scenario: Reject reduced CSV as datasource
- **WHEN** the user attempts to import a reduced CSV peak-distance export as the heatmap alignment datasource
- **THEN** the system rejects it and asks for the canonical JSON peak-distance export

#### Scenario: Report invalid peak-distance JSON
- **WHEN** the user imports a JSON file that is not a canonical peak-distance JSON export
- **THEN** the system reports a user-oriented error message that identifies the file as an invalid peak-distance JSON file and presents technical parser details only as secondary context

#### Scenario: Display loaded peak visualization by default
- **WHEN** an imported or generated peak-distance datasource is loaded
- **THEN** the system makes its heatmap marker/export overlay and Signals plot visualization available without requiring a separate datasource visibility checkbox

#### Scenario: Unload peak datasource
- **WHEN** the user clears or unloads the imported peak-distance datasource
- **THEN** the system removes the imported peak measurements from the current session without changing the camera video or H5 heatmap track

#### Scenario: Load session without imported datasource
- **WHEN** the user loads an alignment session that does not contain an imported distance-measurement datasource
- **THEN** the system treats the datasource as absent and loads the existing camera and heatmap state normally

### Requirement: Peak-distance visualization
The system SHALL provide a lightweight visualization for an imported or generated peak-distance datasource in the heatmap alignment GUI.

#### Scenario: Render current peak on heatmap
- **WHEN** a peak-distance datasource is loaded and the current H5 frame has a detected peak
- **THEN** the system renders a marker for that peak at its measured distance on or alongside the current heatmap view

#### Scenario: Handle no-detection frame in visualization
- **WHEN** a peak-distance datasource is loaded and the current H5 frame has no detection
- **THEN** the system indicates the absence of a peak without drawing a misleading distance marker

#### Scenario: Export loaded peak marker
- **WHEN** a peak-distance datasource is loaded and the user exports a synced video with a heatmap overlay
- **THEN** the exported heatmap overlay includes the detected peak marker for each output frame that maps to a detected H5 peak row

### Requirement: Aligned signal plot
The system SHALL provide a separate Signals area above the Timeline area for reviewing imported time-series measurements against the shared physical timeline.

#### Scenario: Display signals area
- **WHEN** the user launches the alignment workbench
- **THEN** the system displays a boxed Signals area above the boxed Timeline area

#### Scenario: Plot H5 peak distance signal
- **WHEN** an imported or generated peak-distance datasource is loaded
- **THEN** the Signals area plots H5 peak distance over H5 elapsed time

#### Scenario: Use H5 track color for peak distance
- **WHEN** the Signals area plots H5-derived peak-distance data
- **THEN** the plotted H5 peak-distance signal uses a readable plot color derived from the same color family as the H5 timeline track

#### Scenario: Show detected and candidate distances
- **WHEN** the imported peak-distance datasource contains detected frames and no-detection frames with candidate distances
- **THEN** the Signals area plots `candidate_peak_distance_m` values segmented by detection status, rendering detected frames as the primary solid signal and no-detection frames as a lower-alpha signal

#### Scenario: Preserve missing-value gaps
- **WHEN** a peak-distance measurement has no plottable detected or candidate value
- **THEN** the Signals area leaves an actual gap rather than connecting a line through that measurement

#### Scenario: Show compact legend
- **WHEN** the Signals area contains one or more plotted signals
- **THEN** the system displays a compact legend identifying the plotted signal meanings

### Requirement: Leg2 ultrasonic signal display
The system SHALL display one selected Leg2 ultrasonic signal at a time in the existing Signals area using the Leg2 timeline color family.

#### Scenario: Plot selected raw ultrasonic signal
- **WHEN** the Leg2 ultrasonic datasource is loaded and raw ultrasonic display is selected
- **THEN** the Signals area plots raw ultrasonic distance over aligned shared timeline time in meters

#### Scenario: Plot selected filtered ultrasonic signal
- **WHEN** the Leg2 ultrasonic datasource is loaded and filtered ultrasonic display is selected
- **THEN** the Signals area plots filtered ultrasonic distance over aligned shared timeline time in meters

#### Scenario: Select raw or filtered ultrasonic display from Signals area
- **WHEN** a Leg2 ultrasonic datasource is loaded
- **THEN** the Signals area lets the user choose whether the plot displays the raw or filtered ultrasonic signal while keeping only one Leg2 ultrasonic signal plotted at a time

#### Scenario: Use Leg2 track color for ultrasonic signal
- **WHEN** the Signals area plots a Leg2 ultrasonic signal
- **THEN** the plotted signal uses a readable plot color derived from the same color family as the Leg2 timeline track

#### Scenario: Segment ultrasonic signal by ReliableFlag
- **WHEN** the selected Leg2 ultrasonic signal is plotted
- **THEN** the Signals area renders samples where `DataRecordCommon.ReliableFlag` is true as a slightly transparent primary signal and samples where `DataRecordCommon.ReliableFlag` is false as a lower-alpha signal

#### Scenario: Preserve ultrasonic missing-value gaps
- **WHEN** a selected Leg2 ultrasonic sample has no plottable distance value
- **THEN** the Signals area leaves an actual gap rather than connecting a line through that sample

#### Scenario: Align Leg2 signal with timeline geometry
- **WHEN** the Signals plot x-axis is in Timeline mode and a Leg2 ultrasonic signal is plotted
- **THEN** the Leg2 ultrasonic signal, Leg2 timeline bar, H5 peak-distance signal, and current-time indicators map the same shared time values to the same horizontal screen positions

#### Scenario: Show Leg2 signal legend entry
- **WHEN** the Signals area contains a plotted Leg2 ultrasonic signal
- **THEN** the compact legend identifies whether the plotted Leg2 signal is raw or filtered ultrasonic distance

### Requirement: Leg2 MAT session persistence
The system SHALL persist optional Leg2 `.mat` datasource state in alignment session files.

#### Scenario: Save Leg2 MAT session state
- **WHEN** the user saves an alignment session with a Leg2 ultrasonic datasource loaded
- **THEN** the session file includes the Leg2 `.mat` path, Leg2-to-H5 offset, and selected ultrasonic signal kind, without persisting a Leg2 datasource visibility field

#### Scenario: Restore Leg2 MAT session state
- **WHEN** the user loads an alignment session containing Leg2 ultrasonic datasource state
- **THEN** the system reloads the stored Leg2 `.mat` file and restores the Leg2-to-H5 offset, selected signal kind, timeline track, and Signals plot display

#### Scenario: Warn when stored Leg2 MAT cannot be reloaded
- **WHEN** the user loads an alignment session whose stored Leg2 `.mat` file is missing or invalid
- **THEN** the system reports the Leg2 `.mat` reload failure while keeping the rest of the alignment session usable

#### Scenario: Preserve older sessions without Leg2 fields
- **WHEN** the user loads an older alignment session that does not contain Leg2 ultrasonic datasource state
- **THEN** the system defaults to no loaded Leg2 ultrasonic datasource without requiring session migration

### Requirement: Session dirty state
The system SHALL use a single session-level dirty flag. Any **user-initiated** change to persisted `AlignmentSession` fields SHALL mark the session dirty, including viewport geometry, render and preprocess settings, timeline offset, export overlay settings and visibility, signal plot view settings, optional datasource paths and signal kind, and resource changes from explicit user load, unload, replace, import, or clear actions.

The system SHALL mark the session dirty when the user starts a resource load or replace from the UI (for example file dialogs or Resources window actions), not when background camera or H5 resource jobs complete.

The system SHALL NOT mark the session dirty when camera or H5 resource jobs complete after session open, session-load reconciliation, or `--session` startup, including updates inside `_apply_camera_job_result` and `_apply_h5_job_result`.

The system SHALL NOT mark the session dirty for ephemeral UI state that is not stored in the alignment session JSON, including timeline visible zoom or range.

The system SHALL NOT mark the session dirty when the user changes timeline playhead position (`current_time_s`) only.

The system SHALL suppress dirty marking during programmatic session load, control population from session, session reset after close, and reconcile-driven resource loads.

#### Scenario: Show dirty indicator in window title
- **WHEN** the session is dirty
- **THEN** the main heatmap alignment window title appends an asterisk (`*`) after the session name or untitled label

#### Scenario: Clear dirty indicator after save
- **WHEN** the user successfully saves the session to disk
- **THEN** the system clears the dirty flag and removes the asterisk from the window title

#### Scenario: Clear dirty indicator after open
- **WHEN** the user successfully opens a saved alignment session from disk
- **THEN** the system clears the dirty flag and removes the asterisk from the window title

#### Scenario: No dirty indicator after open when jobs complete
- **WHEN** the user opens a saved alignment session and background camera or H5 resource jobs complete without further user edits
- **THEN** the session remains not dirty and the window title does not show an asterisk

#### Scenario: Mark dirty on signal kind and export overlay controls
- **WHEN** the user changes Leg2 signal kind or toggles export overlay visibility, preview, or reset controls
- **THEN** the system marks the session dirty because those values are persisted in the alignment session JSON

### Requirement: Main layout resource control cleanup
The system SHALL remove duplicated or misplaced resource and render controls from the main heatmap alignment layout after equivalent Resources menu/window actions or visualization-owned controls exist.

#### Scenario: Launch with resource menu available
- **WHEN** the user launches the heatmap alignment workbench
- **THEN** the main layout does not show the previous top-row load buttons for Camera Video, Radar Raw (H5), and session loading

#### Scenario: Keep render controls near rendered heatmap
- **WHEN** the user views the Rendered Heatmap panel
- **THEN** rendered-heatmap color minimum and maximum controls are available in that panel rather than in a separate bottom Render panel

#### Scenario: Keep Signals controls near Signals plot
- **WHEN** optional Leg2 MAT resources are loaded
- **THEN** the selected Leg2 signal kind control is available in the Signals area near the plot it affects

#### Scenario: Remove datasource visibility checkboxes
- **WHEN** optional Radar Peak (JSON) or Leg2 MAT resources are loaded
- **THEN** the main layout does not show Show Peak Marker or Show Leg2 Signal checkboxes for datasource-level visibility

#### Scenario: Remove bottom Render panel
- **WHEN** the user views the main heatmap alignment workflow
- **THEN** the main layout does not show the previous bottom Render panel containing mixed render, preprocess, peak, and Leg2 controls

#### Scenario: Keep alignment controls in main workflow
- **WHEN** the user views the Timeline and preview areas
- **THEN** playback, current-time, offset, nudge, viewport, rendered-heatmap, Signals, and export-preview controls remain available in the main workflow where they directly affect alignment or visual review

### Requirement: Session load reconciliation
The system SHALL load a saved alignment session by reconciling the session JSON snapshot against the active workbench state rather than unconditionally tearing down every loaded resource on each open.

Reconciliation SHALL iterate a registered set of resource slots (camera video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT for the current workbench) and, for each slot, SHALL choose one of:

- **keep** - the desired resource identity from the session matches the active loaded resource or an in-flight resource job for that slot; the system does not close, unload, abandon, or restart load work for that slot solely because of the session open
- **load** - the session requests a non-empty resource identity that does not match the active or in-flight identity, or the slot is not loaded; the system loads or replaces that resource using the same behavior as an explicit resource load or reload, including pending replacement and restore-on-failure when a different resource was already loaded, without pre-clearing the active resource before starting the load
- **unload** - the session requests an empty path for that slot but the slot is still loaded; the system clears or unloads that resource so it does not remain active from a previous session

Resource identity SHALL be determined from session content, not from the session JSON file path on disk. Camera identity is the camera video path. H5 identity is the H5 file path plus session, group, entry, and subsweep indices. Radar Peak (JSON) identity is the peak-distance JSON path. Leg2 MAT identity is the Leg2 MAT path. An empty path means the slot is not requested.

After resource reconciliation, the system SHALL always apply non-resource session fields from the JSON snapshot, including viewport geometry, render settings, timeline state, export overlay, signal plot view, preview state, Leg2 offset, and selected Leg2 signal kind, even when one or more resource slots used **keep**.

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
- **THEN** the system still restores session fields from the JSON snapshot that are not satisfied by **keep** alone, such as viewport geometry, render settings, timeline state, preview state, export overlay settings, Leg2 offset, and selected Leg2 signal kind

#### Scenario: Keep GUI responsive when slots use keep
- **WHEN** the user opens a saved alignment session and all resource slots reconcile as **keep**
- **THEN** the system does not block the GUI thread on redundant camera proxy, H5, peak JSON, or Leg2 MAT reload work for those slots

#### Scenario: Keep GUI responsive during session open
- **WHEN** the user opens a saved alignment session that requires background camera or H5 resource work for slots reconciled as **load**
- **THEN** the system keeps the main window and Resources window responsive on the GUI thread while that work continues, using the same non-blocking resource job presentation as explicit resource loads
