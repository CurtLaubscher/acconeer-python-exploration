## ADDED Requirements

### Requirement: Resources menu
The system SHALL provide a top-level Resources menu for heatmap alignment datasource management.

#### Scenario: Show resource management entry
- **WHEN** the user opens the Resources menu
- **THEN** the menu provides an action to open the Resources window

#### Scenario: Load resources from menu
- **WHEN** the user opens the Resources menu
- **THEN** the menu provides load or replace actions for Camera Video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT resources

#### Scenario: Unload resources from menu
- **WHEN** the user opens the Resources menu
- **THEN** the menu provides unload or clear actions for unloadable Camera Video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT resources, enabling each action only when it can apply to the current session state

#### Scenario: Keep session actions in File menu
- **WHEN** the user opens the File menu
- **THEN** the menu remains the place for opening sessions, saving sessions, saving sessions as a new path, closing the current session, exporting synced video, and quitting the workbench

### Requirement: Resources window
The system SHALL provide a modeless Resources window that summarizes supported heatmap alignment resources and allows resource management without blocking the main alignment workflow.

#### Scenario: Open Resources window
- **WHEN** the user chooses the Resources window action
- **THEN** the system shows a modeless Resources window that can stay open while the main heatmap alignment window remains usable

#### Scenario: Reopen existing Resources window
- **WHEN** the Resources window is already open and the user chooses the Resources window action again
- **THEN** the system brings the existing Resources window to the foreground instead of creating a duplicate Resources window

#### Scenario: List supported resource slots
- **WHEN** the Resources window is visible
- **THEN** the window lists rows for Camera Video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT resource slots even when those resources are not loaded

#### Scenario: Refresh resource rows
- **WHEN** a resource is loaded, replaced, unloaded, cleared, reloaded, or fails to load while the Resources window is visible
- **THEN** the window updates the affected resource row without requiring the user to close and reopen the window

#### Scenario: Show current session context
- **WHEN** a session path is known
- **THEN** the Resources window shows the current session path as contextual information without treating the session as a datasource row

### Requirement: Resource row presentation
The system SHALL present each resource row with scan-friendly status, visual identity, path, and detail information.

#### Scenario: Show resource status
- **WHEN** the Resources window lists a resource row
- **THEN** the row indicates whether the resource is loaded, unloaded, missing, invalid, or loaded with warnings

#### Scenario: Show visual color marker
- **WHEN** a resource has a semantic timeline, signal, overlay, or warning color association
- **THEN** the row shows that association as a compact visual swatch or marker cell rather than as text labeled "Color"

#### Scenario: Show resource type and role
- **WHEN** the Resources window lists a resource row
- **THEN** the row identifies the resource type and current role, using user-facing names such as Camera Video, Radar Raw (H5), Radar Peak (JSON), or Leg2 MAT

#### Scenario: Show full path with filename preserved
- **WHEN** a resource row has a file path
- **THEN** the table displays the full path when it fits and uses middle elision when it does not fit, preserving the full filename at the end of the path when the available width allows it

#### Scenario: Show unelided path in details
- **WHEN** the user selects a resource row with a file path
- **THEN** the selected-row details provide access to the unelided full path

#### Scenario: Show resource details
- **WHEN** a resource row has loaded metadata
- **THEN** the row or selected-row details show useful resource-specific information such as camera duration and FPS, radar H5 frame count and duration, radar peak detection count, or Leg2 sample and reliable-segment counts

#### Scenario: Show stale remembered path
- **WHEN** a loaded session remembers a resource path that cannot be reloaded
- **THEN** the corresponding resource row remains visible with the remembered path and a missing or invalid status

### Requirement: Resources window actions
The system SHALL allow users to manage resources from the Resources window.

#### Scenario: Load empty resource slot
- **WHEN** the user selects an unloaded resource row and invokes its load action
- **THEN** the system opens the appropriate file picker and loads the selected resource type using the same validation behavior as the existing interactive load path

#### Scenario: Replace loaded resource
- **WHEN** the user selects a loaded resource row and invokes its load or replace action
- **THEN** the system opens the appropriate file picker and replaces that resource only after the new file validates successfully

#### Scenario: Unload selected resource
- **WHEN** the user selects a loaded optional resource row and invokes its unload or clear action
- **THEN** the system removes that resource from the current session without changing unrelated resources

#### Scenario: Unload primary resource
- **WHEN** the user selects a loaded Camera Video or Radar Raw (H5) row and invokes its unload action
- **THEN** the system clears the selected primary resource and also clears or disables only the preview, timeline, signal, or export state that directly depends on that primary resource

#### Scenario: Unload camera without clearing radar resources
- **WHEN** the user unloads Camera Video while Radar Raw (H5), Radar Peak (JSON), or Leg2 MAT resources are loaded
- **THEN** the system clears camera-dependent preview, timeline, viewport, and export state while preserving the loaded radar and Leg2 resources that remain valid

#### Scenario: Unload radar raw without clearing optional signal resources
- **WHEN** the user unloads Radar Raw (H5) while Radar Peak (JSON) or Leg2 MAT resources are loaded
- **THEN** the system clears radar-H5-dependent rendered heatmap and radar timeline state while preserving loaded Radar Peak (JSON) and Leg2 MAT resources as signal resources when their loaded data remains available

#### Scenario: Display optional signal resources without radar raw
- **WHEN** Radar Raw (H5) is not loaded and Radar Peak (JSON), Leg2 MAT, both, or neither are loaded
- **THEN** the Signals and Timeline areas display whichever optional signal resources are loaded against the shared absolute zero-time coordinate

#### Scenario: Reload remembered resource
- **WHEN** the user selects a resource row with a remembered path and invokes reload
- **THEN** the system attempts to load that remembered path using the same validation behavior as the corresponding resource load path

#### Scenario: Reveal resource path
- **WHEN** the user selects a resource row with an existing file path and invokes reveal path
- **THEN** the system opens the platform file browser at that path or its containing folder when supported

#### Scenario: Inspect resource warnings
- **WHEN** the user selects a resource row with warnings or load errors
- **THEN** the Resources window provides a way to inspect the warning or error details without relying only on the status bar

#### Scenario: Use row context menu actions
- **WHEN** the user opens a context menu on a resource row
- **THEN** the context menu offers the same applicable row-scoped actions as the Resources window selected-row controls, such as load or replace, unload or clear, reload, reveal path, and inspect warnings

#### Scenario: Omit double-click load behavior
- **WHEN** the user double-clicks a resource row
- **THEN** the system is not required to start a load or replace action

#### Scenario: Clear all resources
- **WHEN** the user invokes Clear All Resources from the Resources window and confirms the action
- **THEN** the system unloads Camera Video, Radar Raw (H5), Radar Peak (JSON), Leg2 MAT, and dependent preview, timeline, and signal state while preserving the current session path

#### Scenario: Confirm clear all resources
- **WHEN** the user invokes Clear All Resources
- **THEN** the confirmation message tells the user that loaded resources will be cleared and the current session path will be kept

### Requirement: Session identity and file actions
The system SHALL expose current session identity and expected session save/close actions while keeping session state separate from datasource rows.

#### Scenario: Show untitled session in title
- **WHEN** no current session path is known
- **THEN** the main heatmap alignment window title identifies the session as untitled

#### Scenario: Show current session name in title
- **WHEN** a current session path is known
- **THEN** the main heatmap alignment window title includes the current session filename

#### Scenario: Save existing session
- **WHEN** the user invokes Save Session and a current session path is known
- **THEN** the system saves the current alignment session to that path without prompting for a new path

#### Scenario: Save untitled session
- **WHEN** the user invokes Save Session and no current session path is known
- **THEN** the system behaves like Save Session As and asks the user for a session output path

#### Scenario: Save session as new path
- **WHEN** the user invokes Save Session As and successfully saves to a chosen path
- **THEN** the system updates the current session path to the chosen path and refreshes the main window title and Resources window session context

#### Scenario: Open session updates identity
- **WHEN** the user opens a saved session successfully
- **THEN** the system updates the current session path to the opened path and refreshes the main window title and Resources window session context

#### Scenario: Close current session
- **WHEN** the user invokes Close Session and confirms the action
- **THEN** the system clears loaded resources and session state, forgets the current session path, and returns the workbench to an untitled session without exiting the program

### Requirement: Main layout resource control cleanup
The system SHALL remove duplicated resource load and unload controls from the main heatmap alignment layout after equivalent Resources menu and Resources window actions exist.

#### Scenario: Launch with resource menu available
- **WHEN** the user launches the heatmap alignment workbench
- **THEN** the main layout does not show the previous top-row load buttons for Camera Video, Radar Raw (H5), and session loading

#### Scenario: Keep visualization controls near visualizations
- **WHEN** optional Radar Peak (JSON) or Leg2 MAT resources are loaded
- **THEN** visualization controls such as marker visibility, signal visibility, and selected Leg2 signal kind remain available near the relevant preview or signal controls

#### Scenario: Remove optional datasource load buttons from render panel
- **WHEN** the user views the render controls
- **THEN** the render panel does not show Radar Peak (JSON) or Leg2 MAT import and clear buttons that duplicate Resources menu or Resources window actions

#### Scenario: Keep alignment controls in main workflow
- **WHEN** the user views the Timeline and preview areas
- **THEN** playback, current-time, offset, nudge, viewport, render, and export-preview controls remain available in the main workflow where they directly affect alignment or visual review

### Requirement: Resource model extensibility
The system SHALL structure resource summaries so the Resources window can later represent multiple resource instances without changing the first-pass one-camera, one-H5 workflow.

#### Scenario: Represent current resources as summaries
- **WHEN** the Resources window builds its table rows
- **THEN** it derives rows from resource summary data that includes resource type, role, status, path, semantic color marker, details, warnings, and available actions

#### Scenario: Preserve current workflow constraints
- **WHEN** the Resources window is implemented for this change
- **THEN** it supports the current single Camera Video, single Radar Raw (H5), single Radar Peak (JSON), and single Leg2 MAT resource slots without requiring generic arbitrary resource loading
