## ADDED Requirements

### Requirement: Multi-instance peak series resources
The system SHALL represent peak-distance outputs as zero or more peak series resources in the heatmap alignment workbench.

Each peak series resource SHALL have an in-session identity, display name, visible state for Signals plotting, assigned plot color, provenance, optional JSON path, measurements, and row-specific status or warning details. Peak series resources MAY be generated from the loaded H5 or imported from canonical peak-distance JSON.

The system SHALL allow multiple generated and imported peak series to coexist in the same session. Generating or importing a peak series SHALL append a new peak series row rather than replacing existing peak series.

The system SHALL keep Camera Video and Radar Raw (H5) as single primary loaded resources in this change. The system SHALL keep Leg2 MAT as a single optional resource in this change.

#### Scenario: Generate appends peak series
- **WHEN** Radar Raw (H5) is loaded and the user generates a peak series
- **THEN** the system appends a new unsaved peak series resource row without removing existing peak series rows

#### Scenario: Import appends peak series
- **WHEN** the user imports a canonical peak-distance JSON file
- **THEN** the system appends a new imported peak series resource row without removing existing peak series rows

#### Scenario: Multiple peak series coexist
- **WHEN** the user has generated or imported more than one peak series
- **THEN** the Resources window shows each peak series as a separate manageable resource row

#### Scenario: Preserve fixed primary resources
- **WHEN** this change is implemented
- **THEN** Camera Video and Radar Raw (H5) remain single primary resources and Leg2 MAT remains a single optional resource

### Requirement: Shared peak algorithm engine
The system SHALL provide a non-GUI peak algorithm engine used by both the heatmap alignment GUI and the `peak-distances` CLI.

The engine SHALL expose at least two algorithms: `zero_velocity_slice` with a concise user label such as `v0 slice`, and `sum_velocity` with a concise user label such as `sum v`. Each algorithm SHALL support the peak threshold parameter and SHALL use `DEFAULT_PEAK_THRESHOLD` as its default threshold unless the user supplies another value.

The GUI SHALL NOT implement peak algorithm selection or peak extraction directly in Qt plotting code.

#### Scenario: GUI and CLI share algorithms
- **WHEN** the GUI generates peaks and the CLI exports peaks for the same algorithm id and threshold
- **THEN** both paths use the same non-GUI algorithm implementation

#### Scenario: Generate with v0 slice
- **WHEN** the user selects the `v0 slice` algorithm and generates a peak series
- **THEN** the system computes peaks from the distance profile at the velocity bin nearest `0 m/s`

#### Scenario: Generate with sum v
- **WHEN** the user selects the `sum v` algorithm and generates a peak series
- **THEN** the system computes peaks from the profile formed by summing the distance/velocity map across velocity bins

### Requirement: Peak generation dialog
The system SHALL show a small Generate Peak Series dialog before generating peaks.

The dialog SHALL let the user choose the algorithm before generation, show the selected algorithm label, let the user edit the algorithm parameters supported in v1, and let the user edit the new peak series display name. The v1 parameter controls SHALL include threshold for both supported algorithms.

Generated default names SHALL be concise enough for Signals legends, for example `v0 slice, thresh 650` or `sum v, thresh 650`.

#### Scenario: Configure generated peak series
- **WHEN** the user invokes Generate Peak Series
- **THEN** the system presents a dialog for algorithm choice, threshold, and peak series name before running generation

#### Scenario: Generate uses entered params
- **WHEN** the user changes the threshold in the Generate Peak Series dialog and confirms generation
- **THEN** the new peak series is computed with the entered threshold and records that threshold in its metadata

#### Scenario: Cancel generation dialog
- **WHEN** the user cancels the Generate Peak Series dialog
- **THEN** the system does not compute peaks and does not append a peak series row

### Requirement: Rendered heatmap peak selector
The system SHALL provide a rendered-heatmap control that selects which peak series, if any, supplies the current-frame peak marker.

The selector SHALL include `None` and every loaded/generated peak series. The selector SHALL allow exactly one selected peak series at a time. The selector SHALL be independent of Signals plot visibility.

After successful Generate, the system SHALL select the newly generated peak series for the rendered heatmap marker by default.

#### Scenario: Select no heatmap peak marker
- **WHEN** the user chooses `None` in the rendered heatmap peak selector
- **THEN** the rendered heatmap view does not show a peak marker from any peak series

#### Scenario: Select one peak series marker
- **WHEN** multiple peak series exist and the user selects one of them in the rendered heatmap peak selector
- **THEN** the rendered heatmap view uses only that selected peak series for the current-frame peak marker

#### Scenario: Newly generated series becomes marker source
- **WHEN** peak generation completes successfully
- **THEN** the rendered heatmap peak selector selects the newly generated peak series

#### Scenario: Marker selection independent of signal visibility
- **WHEN** a peak series is hidden from the Signals plot but selected in the rendered heatmap peak selector
- **THEN** the rendered heatmap marker still uses that selected peak series

#### Scenario: Selected marker series unloaded
- **WHEN** the user unloads the peak series currently selected in the rendered heatmap peak selector
- **THEN** the selector falls back to `None` and the rendered heatmap stops using that series for peak markers

## MODIFIED Requirements

### Requirement: Alignment session persistence
The system SHALL save and load JSON alignment session files containing the state needed to reproduce a manual alignment session, including optional imported or saved peak series resource references.

The system SHALL NOT embed generated peak measurement arrays in alignment session JSON. Unsaved generated peak series without a saved JSON path SHALL NOT be restored when the session is saved and later reloaded.

The system SHALL write alignment session version `3` after this change. Version `3` session JSON SHALL store peak series references in a `peak_series` list and SHALL NOT write the retired single `peak_distance_datasource` field.

#### Scenario: Save alignment session
- **WHEN** the user saves an alignment session
- **THEN** the system writes alignment session version `3`, source paths, selected H5 session/group/entry/subsweep, render color limits, camera viewport corners, viewport output dimensions, export overlay settings, temporal offset in seconds, preprocessing settings, optional imported or saved peak series metadata in `peak_series`, and optional imported Leg2 datasource metadata to JSON

#### Scenario: Save datasource state without retired visibility fields
- **WHEN** the user saves an alignment session with peak series or Leg2 MAT resources loaded
- **THEN** the system does not write retired single peak-distance datasource visibility or Leg2 ultrasonic datasource visibility fields as authoritative session state

#### Scenario: Load alignment session
- **WHEN** the user loads a saved alignment session
- **THEN** the system restores the session snapshot described by the JSON file using session load reconciliation so each primary resource slot and persisted optional resource reference is kept, loaded, or unloaded as needed, restores source selections, viewport geometry, render settings, temporal offset, preview state, persisted peak series references, and optional imported Leg2 datasource metadata, and always applies remaining non-resource session fields after reconciliation

#### Scenario: Load version 1 alignment session
- **WHEN** the user loads an alignment session with version `1`
- **THEN** the system migrates the session payload through all intermediate versions to version `3`, ignores retired peak-distance and Leg2 datasource visibility fields, converts any migrated single peak datasource path into `peak_series`, and loads the migrated session without warning if no other load error occurs

#### Scenario: Migrate single peak datasource session
- **WHEN** the user loads a version `2` session that stores one `peak_distance_datasource` path
- **THEN** the system migrates that path into one imported peak series resource row in the version `3` `peak_series` list

#### Scenario: Do not restore unsaved generated peaks
- **WHEN** the user saves an alignment session while unsaved generated peak series exist and later reloads that session
- **THEN** the system restores only peak series with saved/imported JSON paths and does not restore generated peak measurements that were never saved as JSON

#### Scenario: Reject unsupported future alignment session
- **WHEN** the user loads an alignment session with a version newer than the workbench supports
- **THEN** the system rejects the file with a clear unsupported-version load error

### Requirement: Resources window
The system SHALL provide a modeless Resources window that summarizes supported heatmap alignment resources and allows resource management without blocking the main alignment workflow.

The Resources window SHALL list single rows for Camera Video, Radar Raw (H5), and Leg2 MAT resource slots. The Resources window SHALL list zero or more peak series rows, one per generated or imported peak series resource, rather than one fixed Radar Peak (JSON) row.

#### Scenario: Open Resources window
- **WHEN** the user chooses the Resources window action
- **THEN** the system shows a modeless Resources window that can stay open while the main heatmap alignment window remains usable

#### Scenario: Reopen existing Resources window
- **WHEN** the Resources window is already open and the user chooses the Resources window action again
- **THEN** the system brings the existing Resources window to the foreground instead of creating a duplicate Resources window or moving the existing window from its user-chosen position

#### Scenario: List supported resource rows
- **WHEN** the Resources window is visible
- **THEN** the window lists rows for Camera Video, Radar Raw (H5), Leg2 MAT, and each current peak series resource

#### Scenario: No fixed peak row when no peak series exist
- **WHEN** no peak series resources exist
- **THEN** the Resources window does not need to show a fixed empty Radar Peak (JSON) slot row

#### Scenario: Refresh resource rows
- **WHEN** a resource is loaded, replaced, imported, generated, unloaded, reloaded, saved, or fails to load while the Resources window is visible
- **THEN** the window updates the affected resource rows without requiring the user to close and reopen the window

#### Scenario: Show current session context
- **WHEN** a session path is known
- **THEN** the Resources window shows the current session path as contextual information without treating the session as a datasource row

#### Scenario: Show obvious window dismissal action
- **WHEN** the Resources window is visible
- **THEN** the window provides an obvious in-window dismissal action such as a Close button or window-local close menu item

#### Scenario: Dismiss Resources window without changing state
- **WHEN** the user invokes the Resources window dismissal action
- **THEN** the system closes or hides only the Resources window without unloading resources, closing the current session, exiting the main workbench, or changing alignment state

### Requirement: Resource row presentation
The system SHALL present each resource row with scan-friendly status, visual identity, path, and detail information.

#### Scenario: Show resource status
- **WHEN** the Resources window lists a resource row
- **THEN** the row indicates whether the resource is loaded, unloaded, missing, invalid, loaded with warnings, generated unsaved, or another applicable concise state

#### Scenario: Show visual color marker
- **WHEN** a resource has a semantic timeline, signal, overlay, or warning color association
- **THEN** the row shows that association as a compact visual swatch or marker cell rather than as text labeled "Color"

#### Scenario: Show resource type and role
- **WHEN** the Resources window lists a resource row
- **THEN** the row identifies the resource type and current role, using user-facing names such as Camera Video, Radar Raw (H5), Peak Series, or Leg2 MAT

#### Scenario: Show peak series display name
- **WHEN** the Resources window lists a peak series row
- **THEN** the row shows the peak series display name so multiple generated or imported peak series can be distinguished

#### Scenario: Show full path with filename preserved
- **WHEN** a resource row has a file path
- **THEN** the table displays the full path when it fits and uses middle elision when it does not fit, preserving the full filename at the end of the path when the available width allows it

#### Scenario: Preserve separator before elided filename
- **WHEN** a resource path is middle-elided and the available width allows preserving the filename
- **THEN** the elided path includes the path separator immediately before the filename in the preserved suffix

#### Scenario: Show unelided path in details
- **WHEN** the user selects a resource row with a file path
- **THEN** the selected-row details provide access to the unelided full path

#### Scenario: Show selected resource identity first
- **WHEN** the user selects a resource row
- **THEN** the selected-resource details area presents the resource type or name before status, metadata, warnings, or path details

#### Scenario: Omit empty path details
- **WHEN** the user selects an unloaded resource row without a remembered path
- **THEN** the selected-resource details area omits the path detail instead of showing a placeholder path value

#### Scenario: Show resource details
- **WHEN** a resource row has loaded metadata
- **THEN** the row or selected-row details show useful resource-specific information such as camera duration and FPS, radar H5 frame count and duration, peak detection count and algorithm, or Leg2 sample and reliable-segment counts

#### Scenario: Show stale remembered path
- **WHEN** a loaded session remembers a resource path that cannot be reloaded
- **THEN** the corresponding resource row remains visible with the remembered path and a missing or invalid status

### Requirement: Imported distance-measurement datasource
The system SHALL allow the heatmap alignment GUI to import one or more canonical peak-distance JSON files as optional peak series resources.

Each imported peak series SHALL append a resource row instead of replacing existing peak series. Imported peak series SHALL use the same canonical JSON validation behavior as the existing interactive peak-distance import path. When Radar Raw (H5) is loaded, imported peak series SHALL be validated against the loaded H5 where possible using frame count, real-time seconds, source selection metadata, and recording metadata.

#### Scenario: Import peak-distance JSON
- **WHEN** the user imports a canonical peak-distance JSON file
- **THEN** the system loads it as a new peak series resource without replacing camera video, H5 heatmap, Leg2 MAT, or existing peak series resources

#### Scenario: Import multiple peak-distance JSON files
- **WHEN** the user imports more than one canonical peak-distance JSON file
- **THEN** the system keeps each accepted file as a separate peak series resource row

#### Scenario: Load H5 and peak-distance JSON on startup
- **WHEN** the user launches the heatmap alignment GUI with both H5 recording and peak-distance JSON startup arguments
- **THEN** the system loads the H5 recording and imports the peak-distance JSON as a peak series using the same validation rules as interactive import

#### Scenario: Load session and peak-distance JSON on startup
- **WHEN** the user launches the heatmap alignment GUI with both a saved alignment session and a peak-distance JSON startup argument
- **THEN** the explicitly provided peak-distance JSON is imported as an additional peak series after the session load using the same validation rules as interactive import, unless that path is already present and the implementation chooses to avoid duplicate imported rows

#### Scenario: Validate imported datasource metadata
- **WHEN** an imported peak-distance JSON contains source-selection metadata
- **THEN** the system compares that metadata with the loaded H5 heatmap track when one is present and attaches a row-specific warning if the source selection appears incompatible

#### Scenario: Reject incompatible row count
- **WHEN** an imported peak-distance JSON has a different number of measurement objects than the loaded H5 heatmap recording has frames
- **THEN** the system rejects that import and leaves existing peak series resources unchanged

#### Scenario: Validate real-time axis
- **WHEN** an imported peak-distance JSON contains elapsed real-time seconds
- **THEN** the system verifies that the imported time range is compatible with the loaded H5 heatmap recording duration when one is present

#### Scenario: Preserve timeline rows
- **WHEN** an imported peak-distance JSON contains frames with no detection
- **THEN** the system preserves those rows so the imported peak series remains aligned to the source recording timeline

#### Scenario: Reject reduced CSV as datasource
- **WHEN** the user attempts to import a reduced CSV peak-distance export as a peak series
- **THEN** the system rejects it and asks for the canonical JSON peak-distance export

#### Scenario: Report invalid peak-distance JSON
- **WHEN** the user imports a JSON file that is not a canonical peak-distance JSON export
- **THEN** the system reports a user-oriented error message that identifies the file as an invalid peak-distance JSON file and presents technical parser details only as secondary context

#### Scenario: Display imported peak visualization by default
- **WHEN** a peak-distance JSON is imported as a peak series
- **THEN** the system makes that series available for Signals plot visualization and rendered-heatmap marker selection without requiring a separate datasource visibility checkbox

#### Scenario: Unload imported peak series
- **WHEN** the user unloads an imported peak series resource row
- **THEN** the system removes that peak series from the current session without changing the camera video, H5 heatmap track, Leg2 MAT resource, or other peak series

#### Scenario: Load session without imported datasource
- **WHEN** the user loads an alignment session that does not contain any imported or saved peak series references
- **THEN** the system treats peak series resources as absent and loads the existing camera and heatmap state normally

### Requirement: Peak-distance visualization
The system SHALL provide lightweight visualization for peak series resources in the heatmap alignment GUI.

The rendered heatmap marker and exported heatmap overlay marker SHALL use only the peak series selected by the rendered-heatmap peak selector. The system SHALL NOT draw all available peak series as heatmap markers at the same time.

#### Scenario: Render current peak on heatmap
- **WHEN** a peak series is selected in the rendered-heatmap peak selector and the current H5 frame has a detected peak for that series
- **THEN** the system renders a marker for that peak at its measured distance on or alongside the current heatmap view

#### Scenario: Handle no-detection frame in visualization
- **WHEN** a peak series is selected in the rendered-heatmap peak selector and the current H5 frame has no detection for that series
- **THEN** the system indicates the absence of a peak without drawing a misleading distance marker

#### Scenario: Export selected peak marker
- **WHEN** a peak series is selected in the rendered-heatmap peak selector and the user exports a synced video with a heatmap overlay
- **THEN** the exported heatmap overlay includes the detected peak marker from the selected peak series for each output frame that maps to a detected H5 peak row

#### Scenario: Do not render unselected peak markers
- **WHEN** multiple peak series exist and only one is selected in the rendered-heatmap peak selector
- **THEN** the rendered heatmap and exported overlay omit markers from the unselected peak series

### Requirement: Aligned signal plot
The system SHALL provide a separate Signals area above the Timeline area for reviewing imported time-series measurements against the shared physical timeline.

#### Scenario: Display signals area
- **WHEN** the user launches the alignment workbench
- **THEN** the system displays a boxed Signals area above the boxed Timeline area

#### Scenario: Plot multiple H5 peak distance signals
- **WHEN** one or more visible peak series resources exist
- **THEN** the Signals area plots each visible peak series over H5 elapsed time

#### Scenario: Use assigned peak series colors
- **WHEN** the Signals area plots multiple peak series
- **THEN** each peak series uses its assigned readable comparison color rather than all peak series using the H5 track color

#### Scenario: Show concise peak legend labels
- **WHEN** the Signals area legend identifies plotted peak series
- **THEN** each peak series legend text uses its concise display name, including enough algorithm or import context to distinguish it from other peak series

#### Scenario: Show detected and candidate distances
- **WHEN** a peak series contains detected frames and no-detection frames with candidate distances
- **THEN** the Signals area plots `candidate_peak_distance_m` values segmented by detection status, rendering detected frames as the primary signal and no-detection frames as a lower-alpha signal for that peak series

#### Scenario: Preserve missing-value gaps
- **WHEN** a peak-distance measurement has no plottable detected or candidate value
- **THEN** the Signals area leaves an actual gap rather than connecting a line through that measurement

#### Scenario: Show compact legend
- **WHEN** the Signals area contains one or more plotted signals
- **THEN** the system displays a compact legend identifying the plotted signal meanings

### Requirement: Resources menu
The system SHALL provide a top-level Resources menu for heatmap alignment resource management.

The system SHALL keep Load terminology for primary Camera Video and Radar Raw (H5) actions. The system SHALL use Import terminology for optional external peak series files where those actions are touched by this change. The system SHALL prefer Unload terminology over Clear for resource removal where those actions are touched by this change.

#### Scenario: Show resource management entry
- **WHEN** the user chooses the menu action to manage resources
- **THEN** the system opens or focuses the Resources window

#### Scenario: Load resources from menu
- **WHEN** the user opens the Resources menu
- **THEN** the menu provides load or replace actions for Camera Video, Radar Raw (H5), and Leg2 MAT resources, and MAY provide append actions for Import Peak Series or Generate Peak Series

#### Scenario: Unload resources from menu
- **WHEN** the user opens the Resources menu
- **THEN** the menu provides unload actions for unloadable Camera Video, Radar Raw (H5), and Leg2 MAT resources, enabling each action only when it can apply to the current session state

#### Scenario: Peak row actions stay row-scoped
- **WHEN** the user wants to save, save as, reload, or unload a specific peak series
- **THEN** the system provides those actions from the corresponding peak series row in the Resources window rather than as ambiguous global peak actions

#### Scenario: Keep session actions in File menu
- **WHEN** the user opens the File menu
- **THEN** the menu remains the place for opening sessions, saving sessions, saving sessions as a new path, closing the current session, exporting synced video, and quitting the workbench

### Requirement: Resources window actions
The system SHALL allow users to manage resources from the Resources window.

#### Scenario: Load empty resource slot
- **WHEN** the user selects an unloaded primary resource row and invokes its load action
- **THEN** the system opens the appropriate file picker and loads the selected resource type using the same validation behavior as the existing interactive load path

#### Scenario: Replace loaded resource
- **WHEN** the user selects a loaded primary resource row and invokes its load or replace action
- **THEN** the system opens the appropriate file picker and replaces that resource only after the new file validates successfully

#### Scenario: Import peak series from Resources window
- **WHEN** the user invokes Import Peak Series from the Resources window
- **THEN** the system opens a peak-distance JSON file picker and appends each accepted import as a new peak series resource

#### Scenario: Generate peak series from Resources window
- **WHEN** Radar Raw (H5) is loaded and the user invokes Generate Peak Series from the Resources window
- **THEN** the system opens the Generate Peak Series dialog and appends a new generated peak series when the dialog is confirmed

#### Scenario: Unload selected resource
- **WHEN** the user selects a loaded optional resource row and invokes its unload action
- **THEN** the system removes that resource from the current session without changing unrelated resources

#### Scenario: Unload selected peak series
- **WHEN** the user unloads a peak series resource row
- **THEN** the system removes only that peak series and updates Signals plotting and rendered-heatmap marker selection as needed

#### Scenario: Unload primary resource
- **WHEN** the user selects a loaded Camera Video or Radar Raw (H5) row and invokes its unload action
- **THEN** the system clears the selected primary resource and also clears or disables only the preview, timeline, signal, or export state that directly depends on that primary resource

#### Scenario: Unload camera without clearing radar resources
- **WHEN** the user unloads Camera Video while Radar Raw (H5), peak series resources, or Leg2 MAT resources are loaded
- **THEN** the system clears camera-dependent preview, timeline, viewport, and export state while preserving the loaded radar and Leg2 resources that remain valid

#### Scenario: Unload radar raw without clearing optional signal resources
- **WHEN** the user unloads Radar Raw (H5) while peak series resources or Leg2 MAT resources are loaded
- **THEN** the system clears radar-H5-dependent rendered heatmap and radar timeline state while preserving loaded peak series and Leg2 MAT resources as signal resources when their loaded data remains available

#### Scenario: Display optional signal resources without radar raw
- **WHEN** Radar Raw (H5) is not loaded and peak series resources, Leg2 MAT, both, or neither are loaded
- **THEN** the Signals and Timeline areas display whichever optional signal resources are loaded against the shared absolute zero-time coordinate

#### Scenario: Reload remembered resource
- **WHEN** the user selects a resource row with a remembered path and invokes reload
- **THEN** the system attempts to load that remembered path using the same validation behavior as the corresponding resource load path

#### Scenario: Reveal resource path
- **WHEN** the user selects a resource row with an existing file path and invokes reveal path
- **THEN** the system opens the platform file browser at that path or its containing folder when supported

#### Scenario: Label file manager action clearly
- **WHEN** the Resources window or resource row context menu shows the action that opens the platform file browser
- **THEN** the action is labeled "Show in File Manager"

#### Scenario: Inspect resource warnings
- **WHEN** the user selects a resource row with warnings or load errors
- **THEN** the system provides a way to inspect the warning or error details without relying only on the status bar

#### Scenario: Use row context menu actions
- **WHEN** the user opens a context menu on a resource row
- **THEN** the context menu offers the same applicable row-scoped actions as the Resources window selected-row controls, including save, save as, reload, and unload for peak series rows when applicable

#### Scenario: Omit double-click load behavior
- **WHEN** the user double-clicks a resource row
- **THEN** the system is not required to start a load or replace action

#### Scenario: Clear all resources
- **WHEN** the user invokes Clear All Resources from the Resources window and confirms the action
- **THEN** the system unloads Camera Video, Radar Raw (H5), all peak series resources, Leg2 MAT, and dependent preview, timeline, and signal state while preserving the current session path

#### Scenario: Confirm clear all resources
- **WHEN** the user invokes Clear All Resources
- **THEN** the confirmation message tells the user that loaded resources will be cleared and the current session path will be kept

#### Scenario: Confirm clear all with unsaved generated peaks
- **WHEN** unsaved generated peak series exist and the user invokes Clear All Resources
- **THEN** the confirmation message also states that unsaved generated peak data will be lost

#### Scenario: Save peak series from Resources window
- **WHEN** the user selects a peak series row and invokes Save while it is unsaved, or Save As while peak data is in memory
- **THEN** the system writes canonical peak-distance JSON according to the save-peaks requirements for that selected row

### Requirement: In-app peak generation from loaded H5
The system SHALL allow the user to generate peak series measurements from the currently loaded Radar Raw (H5) recording without leaving the heatmap alignment workbench.

Generation SHALL use the loaded H5 session, group, entry, and subsweep indices from the current heatmap track. Generation SHALL process all frames. Generation SHALL use the selected algorithm and threshold from the Generate Peak Series dialog.

The system SHALL enable Generate Peak Series only when Radar Raw (H5) is loaded. The system SHALL disable or omit Generate Peak Series when H5 is not loaded.

Generation SHALL run synchronously on the GUI thread for v1 unless implementation measurements show that background execution is necessary, and SHALL reuse the in-memory H5 record rather than re-opening the file through `export_peak_distances()`.

#### Scenario: Generate peaks from loaded H5
- **WHEN** Radar Raw (H5) is loaded and the user confirms the Generate Peak Series dialog
- **THEN** the system computes peak-distance measurements from the loaded H5 and appends them as a new unsaved peak series resource without writing JSON to disk

#### Scenario: Generate disabled without H5
- **WHEN** Radar Raw (H5) is not loaded
- **THEN** the system does not offer a usable Generate Peak Series action

#### Scenario: Refresh UI after generate
- **WHEN** peak generation completes successfully
- **THEN** the system updates the Signals plot, rendered-heatmap peak selector, rendered-heatmap marker, and Resources rows without requiring a separate import step

#### Scenario: Generate does not replace peak series
- **WHEN** the user invokes Generate Peak Series while peak series already exist
- **THEN** the system appends the newly generated peak series and preserves existing peak series

### Requirement: Peaks dirty state and Resources status
The system SHALL track unsaved state per peak series resource.

The system SHALL NOT add peak-series unsaved state to the main window title asterisk.

The system SHALL show generated unsaved state in the corresponding peak series Resources table Status column as **Generated (unsaved)** or an equivalent concise label. The system SHALL NOT add new table columns for this state.

#### Scenario: Show generated unsaved in Status column
- **WHEN** a peak series was generated and has not been saved to disk
- **THEN** that peak series resource row Status column shows **Generated (unsaved)** or an equivalent concise unsaved label

#### Scenario: Clear peak series unsaved state after save
- **WHEN** the user successfully saves a peak series to a JSON path
- **THEN** the system clears that peak series unsaved state and shows a normal loaded or saved status for that row

#### Scenario: Keep other peak unsaved states
- **WHEN** the user saves one unsaved peak series while another generated peak series remains unsaved
- **THEN** the system clears unsaved state only for the saved row

### Requirement: Save peaks from Resources
The system SHALL allow saving one selected peak series resource to canonical peak-distance JSON from the Resources window.

The system SHALL write JSON using the same format as `peak-distances` (`write_peak_distance_json` / `acconeer_peak_distances`).

Save SHALL be row-specific. Save SHALL write to the selected peak series path when one exists. If no path exists, Save SHALL behave like Save As and prompt for an output path. Save As SHALL always prompt for an output path. The default suggested filename SHALL be based on the loaded H5 stem, algorithm label, and `.json` extension when practical.

The system SHALL set or update the selected peak series path only after a successful save. The system SHALL mark the alignment session dirty when saved peak series path or persisted display metadata changes.

The system SHALL NOT write peak JSON automatically as part of Generate.

#### Scenario: Save generated peak series first save
- **WHEN** a generated peak series is unsaved, no JSON path is set for that row, and the user invokes Save on that row
- **THEN** the system prompts for an output path and writes canonical JSON on confirmation

#### Scenario: Save peak series to existing path
- **WHEN** a peak series has a JSON path and the user invokes Save on that row
- **THEN** the system confirms overwrite if the file exists and writes canonical JSON to that path

#### Scenario: Save As peak series
- **WHEN** peak-distance data exists for a selected peak series row and the user invokes Save As
- **THEN** the system prompts for an output path and writes canonical JSON to the selected path on confirmation

#### Scenario: Save disabled when selected row has no peak data
- **WHEN** no peak series row with in-memory measurements is selected
- **THEN** row-specific Save and Save As are disabled or omitted

#### Scenario: Save does not affect other peak series
- **WHEN** the user saves one peak series
- **THEN** the system does not write, unload, or change unsaved state for other peak series

### Requirement: H5 replacement clears peak datasource
The system SHALL preserve peak series resources as optional signal resources when a different Radar Raw (H5) resource successfully replaces the current H5 recording.

The system SHALL NOT automatically unload all peak series solely because H5 changed. Imported peak series validation warnings SHALL remain row-specific. Generated peak series that remain after H5 replacement SHALL continue to behave as signal resources until the user unloads them, clears all resources, or opens another session.

#### Scenario: Preserve peak series after different H5 replacement
- **WHEN** a new H5 recording successfully replaces a different active H5 recording while peak series resources exist
- **THEN** the system preserves the existing peak series resources and updates H5-dependent rendered heatmap state for the new H5

#### Scenario: Preserve peaks after failed H5 replacement
- **WHEN** a pending H5 replacement fails before becoming active
- **THEN** the system preserves the previously active H5 recording and all peak series resources

### Requirement: Unsaved peaks in session navigation prompts
When any generated peak series is unsaved, the system SHALL include peak-loss warning text in the same unsaved-changes prompt used for a dirty alignment session on quit, close session, and open session, without showing a second modal solely for peaks.

The warning SHALL state that unsaved peak-distance data will be lost. The warning SHALL state that saving the alignment session does not write peak JSON. The warning SHALL NOT imply that choosing **Save** in that dialog writes peak JSON. The **Save** control SHALL retain its existing behavior (save alignment session only).

#### Scenario: Peaks-only unsaved still prompts
- **WHEN** one or more generated peak series are unsaved, the alignment session is not dirty, and the user quits, closes the session, or opens another session
- **THEN** the system shows the unsaved-changes prompt before proceeding

#### Scenario: Warn on quit with unsaved peaks
- **WHEN** the user quits while one or more generated peak series are unsaved
- **THEN** the unsaved-changes prompt includes text that unsaved peak-distance data will be lost and that saving the session does not save peak JSON

#### Scenario: Warn on open session with unsaved peaks
- **WHEN** the user opens another session while one or more generated peak series are unsaved
- **THEN** the same combined unsaved-changes prompt behavior applies as for quit

### Requirement: Confirmations for peak resource actions
The system SHALL confirm before unloading a peak series row when that row contains unsaved generated peak data.

The system SHALL confirm before Reload on a peak series row when that row contains unsaved generated peak data, because reload reads from disk and discards unsaved generated data.

The system SHALL prompt when the user saves the alignment session while any generated peak series is unsaved, warning that peak JSON is not saved with the session and that the user should save peak series from Resources first.

#### Scenario: Confirm unload with unsaved generated peaks
- **WHEN** a peak series row contains unsaved generated peak data and the user unloads that row
- **THEN** the system confirms that unsaved generated peak data for that row will be lost

#### Scenario: Confirm reload with unsaved generated peaks
- **WHEN** a peak series row contains unsaved generated peak data and the user invokes Reload on that row
- **THEN** the system shows a blocking confirmation that reload discards unsaved generated data and proceeds only if the user confirms

#### Scenario: Confirm save session with unsaved peaks
- **WHEN** one or more generated peak series are unsaved and the user invokes Save Session
- **THEN** the system warns that peak JSON is not included in the session save before continuing

#### Scenario: Session save does not persist generated peaks
- **WHEN** the user saves the alignment session while unsaved generated peak series exist and later reopens that session
- **THEN** the system loads saved/imported peak series from stored JSON paths, omits unsaved generated peak series that had no path, and does not restore unsaved generated peak measurements from the prior session

### Requirement: Unsaved changes before destructive session navigation
When the session is dirty, or when any generated peak series is unsaved, the system SHALL prompt the user with **Save**, **Don't Save**, and **Cancel** before actions that would discard in-memory session state or unsaved peak series.

The prompt SHALL use conventional desktop wording: state that there are unsaved changes and ask whether to save them before quitting, closing the current session, or opening another session. The system SHALL NOT use internal terms such as "workbench" in the prompt text.

When generated peak series are unsaved, the prompt body SHALL additionally warn that unsaved peak-distance data will be lost and that saving the alignment session does not write peak JSON. The prompt SHALL NOT imply that choosing **Save** in that dialog saves peak JSON.

For **Open Session**, the system SHALL show the unsaved-changes prompt before the open file dialog when the current session is dirty or any generated peak series is unsaved.

For **Save** in the prompt, the system SHALL save to the current session path when known, or behave like Save Session As when the session is untitled. If save fails or the user cancels Save As, the system SHALL cancel the guarded action and leave the current session unchanged and dirty.

For **Don't Save**, the system SHALL proceed with the requested action without writing the current session to disk or unsaved generated peak series to JSON.

For **Cancel**, the system SHALL abort the requested action and leave the current session unchanged.

The system SHALL NOT show the unsaved-changes prompt when loading a session from `--session` on startup or when tests call session load helpers directly without the menu guard.

#### Scenario: Prompt before quit when dirty
- **WHEN** the user chooses Quit and the session is dirty or any generated peak series is unsaved
- **THEN** the system shows the unsaved-changes prompt before exiting

#### Scenario: Prompt before close session when dirty
- **WHEN** the user closes the current session and the session is dirty or any generated peak series is unsaved
- **THEN** the system shows the unsaved-changes prompt before clearing the session

#### Scenario: Prompt before open session when dirty
- **WHEN** the user chooses Open Session and the session is dirty or any generated peak series is unsaved
- **THEN** the system shows the unsaved-changes prompt before the open file dialog

#### Scenario: No prompt when clean
- **WHEN** the user quits, closes the session, or opens another session and neither the session nor any peak series is unsaved
- **THEN** the system does not show the unsaved-changes prompt for that action
