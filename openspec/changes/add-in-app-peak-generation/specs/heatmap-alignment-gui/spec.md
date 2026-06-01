## ADDED Requirements

### Requirement: In-app peak generation from loaded H5
The system SHALL allow the user to generate Radar Peak (JSON) measurements from the currently loaded Radar Raw (H5) recording without leaving the heatmap alignment workbench.

Generation SHALL use the same zero-velocity-slice peak algorithm and default threshold as the `peak-distances` CLI (`650` until a future change adds UI). Generation SHALL use the loaded H5 session, group, entry, and subsweep indices from the current heatmap track. Generation SHALL process all frames (no `every_n` or `max_frames` in the GUI).

The system SHALL enable Generate only when Radar Raw (H5) is loaded. The system SHALL disable or omit Generate when H5 is not loaded.

Generation SHALL run synchronously on the GUI thread for v1, with a clear busy indication, and SHALL reuse the in-memory H5 record rather than re-opening the file through `export_peak_distances()`.

#### Scenario: Generate peaks from loaded H5
- **WHEN** Radar Raw (H5) is loaded and the user invokes Generate on the Radar Peak (JSON) resource row
- **THEN** the system computes peak-distance measurements from the loaded H5 and holds them in memory as the active peak-distance data without writing JSON to disk

#### Scenario: Generate disabled without H5
- **WHEN** Radar Raw (H5) is not loaded
- **THEN** the system does not offer a usable Generate action for Radar Peak (JSON)

#### Scenario: Refresh UI after generate
- **WHEN** peak generation completes successfully
- **THEN** the system updates the Signals plot, heatmap peak overlay, and Resources row details the same way as after a successful peak-distance JSON import, without requiring a separate import step

#### Scenario: Confirm replace in-memory peaks
- **WHEN** the user invokes Generate while peak-distance data is already present in memory (loaded or previously generated)
- **THEN** the system confirms that generation replaces in-memory peak data and that files on disk are unchanged until the user saves peaks

### Requirement: Peaks dirty state and Resources status
The system SHALL track whether the in-memory peak-distance datasource differs from the last successful save to disk.

The system SHALL NOT add a peaks-dirty indicator to the main window title asterisk.

The system SHALL show peaks unsaved state in the Radar Peak (JSON) Resources table **Status** column as **Generated (unsaved)** when peaks were generated and not yet saved. The system SHALL NOT add new table columns for this state.

#### Scenario: Show generated unsaved in Status column
- **WHEN** the user generated peaks and has not saved them to disk
- **THEN** the Radar Peak (JSON) resource row Status column shows **Generated (unsaved)**

#### Scenario: Clear peaks dirty after save
- **WHEN** the user successfully saves peaks to a JSON path
- **THEN** the system clears peaks dirty, loads or reflects the saved file as the active peak-distance datasource, and shows a normal loaded status in the Status column

### Requirement: Save peaks from Resources
The system SHALL allow saving in-memory peak-distance data to canonical peak-distance JSON from the Resources window.

The system SHALL write JSON using the same format as `peak-distances` (`write_peak_distance_json` / `acconeer_peak_distances`).

The system SHALL set `session.peak_distance_datasource.path` only after a successful save. The system SHALL mark the alignment session dirty when the saved peak path changes from what was previously stored in the session.

**Save peaks** SHALL be enabled when peaks are dirty and peak data is in memory. When no output path is set, **Save peaks** SHALL open a file dialog (same default naming as Save peaks as…). When a path is shown in the resource row, **Save peaks** SHALL write to that path after overwrite confirmation.

**Save peaks as…** SHALL be enabled whenever peak data is in memory, including when peaks are not dirty. **Save peaks as…** SHALL always prompt for an output path. The default suggested filename SHALL be `{h5_stem}_peak_distances.json` beside the loaded H5 when practical.

The system SHALL NOT write peak JSON automatically as part of Generate.

#### Scenario: Save peaks as first save
- **WHEN** peaks are dirty, no peak JSON path is set, and the user invokes Save peaks
- **THEN** the system prompts for an output path and writes canonical JSON on confirmation

#### Scenario: Save peaks to existing path
- **WHEN** peaks are dirty, a peak JSON path is shown in the resource row, and the user invokes Save peaks
- **THEN** the system confirms overwrite if the file exists and writes canonical JSON to that path

#### Scenario: Save peaks disabled when not dirty
- **WHEN** peaks are in memory but not dirty
- **THEN** Save peaks is disabled or omitted

#### Scenario: Save peaks as enabled when peaks in memory
- **WHEN** peak-distance data is in memory, including after a successful save when peaks are not dirty
- **THEN** Save peaks as… is available

#### Scenario: Save peaks as disabled without peaks
- **WHEN** no peak-distance data is in memory
- **THEN** Save peaks as… is disabled or omitted

### Requirement: Unsaved peaks in session navigation prompts
When peaks are dirty, the system SHALL include peak-loss warning text in the same unsaved-changes prompt used for a dirty alignment session on quit, close session, and open session, without showing a second modal solely for peaks.

The warning SHALL state that unsaved peak-distance data will be lost. The warning SHALL state that saving the alignment session does not write peak JSON. The warning SHALL NOT imply that choosing **Save** in that dialog writes peak JSON. The **Save** control SHALL retain its existing behavior (save alignment session only).

#### Scenario: Peaks-only dirty still prompts
- **WHEN** peaks are dirty and the alignment session is not dirty, and the user quits, closes the session, or opens another session
- **THEN** the system shows the unsaved-changes prompt before proceeding

#### Scenario: Warn on quit with unsaved peaks
- **WHEN** the user quits while peaks are dirty
- **THEN** the unsaved-changes prompt includes text that unsaved peak-distance data will be lost and that saving the session does not save peak JSON

#### Scenario: Warn on open session with unsaved peaks
- **WHEN** the user opens another session while peaks are dirty
- **THEN** the same combined unsaved-changes prompt behavior applies as for quit

### Requirement: Confirmations for peak resource actions
The system SHALL confirm before clearing or unloading Radar Peak (JSON) when peaks are dirty.

The system SHALL confirm before Reload on Radar Peak (JSON) when peaks are dirty, because reload reads from disk and discards unsaved generated data.

The system SHALL prompt when the user saves the alignment session while peaks are dirty, warning that peak JSON is not saved with the session and that the user should save peaks from Resources first.

#### Scenario: Confirm unload with unsaved generated peaks
- **WHEN** peaks are dirty and the user unloads or clears Radar Peak (JSON)
- **THEN** the system confirms that unsaved generated peak data will be lost

#### Scenario: Confirm reload with unsaved generated peaks
- **WHEN** peaks are dirty and the user invokes Reload on Radar Peak (JSON)
- **THEN** the system shows a blocking confirmation that reload discards unsaved generated data and proceeds only if the user confirms

#### Scenario: Confirm save session with unsaved peaks
- **WHEN** peaks are dirty and the user invokes Save Session
- **THEN** the system warns that peak JSON is not included in the session save before continuing

#### Scenario: Session save does not persist generated peaks
- **WHEN** the user saves the alignment session while peaks are dirty and later reopens that session
- **THEN** the system loads peak-distance data from the peak JSON path stored in the session, or omits peaks if no path was saved, and does not restore unsaved generated peaks from the prior session

## MODIFIED Requirements

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

#### Scenario: Label file manager action clearly
- **WHEN** the Resources window or resource row context menu shows the action that opens the platform file browser
- **THEN** the action is labeled "Show in File Manager"

#### Scenario: Inspect resource warnings
- **WHEN** the user selects a resource row with warnings or load errors
- **THEN** the system provides a way to inspect the warning or error details without relying only on the status bar

#### Scenario: Use row context menu actions
- **WHEN** the user opens a context menu on a resource row
- **THEN** the context menu offers the same applicable row-scoped actions as the Resources window selected-row controls, including generate and save peaks for Radar Peak (JSON) when applicable

#### Scenario: Omit double-click load behavior
- **WHEN** the user double-clicks a resource row
- **THEN** the system is not required to start a load or replace action

#### Scenario: Clear all resources
- **WHEN** the user invokes Clear All Resources from the Resources window and confirms the action
- **THEN** the system unloads Camera Video, Radar Raw (H5), Radar Peak (JSON), Leg2 MAT, and dependent preview, timeline, and signal state while preserving the current session path

#### Scenario: Confirm clear all resources
- **WHEN** the user invokes Clear All Resources
- **THEN** the confirmation message tells the user that loaded resources will be cleared and the current session path will be kept

#### Scenario: Confirm clear all with unsaved generated peaks
- **WHEN** peaks are dirty and the user invokes Clear All Resources
- **THEN** the confirmation message also states that unsaved generated peak data will be lost

#### Scenario: Generate peaks from Resources window
- **WHEN** the user selects the Radar Peak (JSON) row, Radar Raw (H5) is loaded, and the user invokes Generate
- **THEN** the system generates peak-distance data from the loaded H5 and updates the workbench without writing JSON until the user saves peaks

#### Scenario: Save peaks from Resources window
- **WHEN** the user selects the Radar Peak (JSON) row and invokes Save peaks while peaks are dirty, or Save peaks as… while peak data is in memory
- **THEN** the system writes canonical peak-distance JSON according to the save-peaks requirements

### Requirement: Unsaved changes before destructive session navigation
When the session is dirty, the system SHALL prompt the user with **Save**, **Don't Save**, and **Cancel** before actions that would discard in-memory session state.

The prompt SHALL use conventional desktop wording: state that there are unsaved changes and ask whether to save them before quitting, closing the current session, or opening another session. The system SHALL NOT use internal terms such as “workbench” in the prompt text.

When peaks are dirty, the prompt body SHALL additionally warn that unsaved peak-distance data will be lost and that saving the alignment session does not write peak JSON. The prompt SHALL NOT imply that choosing **Save** in that dialog saves peak JSON.

For **Open Session**, the system SHALL show the unsaved-changes prompt before the open file dialog when the current session is dirty or peaks are dirty.

For **Save** in the prompt, the system SHALL save to the current session path when known, or behave like Save Session As when the session is untitled. If save fails or the user cancels Save As, the system SHALL cancel the guarded action and leave the current session unchanged and dirty.

For **Don't Save**, the system SHALL proceed with the requested action without writing the current session to disk.

For **Cancel**, the system SHALL abort the requested action and leave the current session unchanged.

The system SHALL NOT show the unsaved-changes prompt when loading a session from `--session` on startup or when tests call session load helpers directly without the menu guard.

#### Scenario: Prompt before quit when dirty
- **WHEN** the user chooses Quit and the session is dirty or peaks are dirty
- **THEN** the system shows the unsaved-changes prompt before exiting

#### Scenario: Prompt before close session when dirty
- **WHEN** the user closes the current session and the session is dirty or peaks are dirty
- **THEN** the system shows the unsaved-changes prompt before clearing the session

#### Scenario: Prompt before open session when dirty
- **WHEN** the user chooses Open Session and the session is dirty or peaks are dirty
- **THEN** the system shows the unsaved-changes prompt before the open file dialog

#### Scenario: No prompt when clean
- **WHEN** the user quits, closes the session, or opens another session and neither the session nor peaks are dirty
- **THEN** the system does not show the unsaved-changes prompt for that action
