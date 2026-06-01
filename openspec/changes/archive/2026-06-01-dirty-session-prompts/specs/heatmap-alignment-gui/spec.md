## ADDED Requirements

### Requirement: Session dirty state
The system SHALL track whether the current alignment session has unsaved changes relative to the last successful save, successful open, or reset to a pristine untitled session.

The system SHALL use a single session-level dirty flag. Any **user-initiated** change to persisted `AlignmentSession` fields SHALL mark the session dirty, including viewport geometry, render and preprocess settings, timeline offset, export overlay settings and visibility, signal plot view settings, optional datasource paths visibility and signal kind, and resource changes from explicit user load, unload, replace, import, or clear actions.

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

#### Scenario: Mark dirty on datasource visibility and export overlay controls
- **WHEN** the user toggles peak-distance marker visibility, Leg2 signal visibility or signal kind, or export overlay visibility, preview, or reset controls
- **THEN** the system marks the session dirty because those values are persisted in the alignment session JSON

#### Scenario: Mark dirty after clear all resources
- **WHEN** the user confirms Clear All Resources and the system unloads all resources while keeping the current session path
- **THEN** the system marks the session dirty

#### Scenario: Mark dirty on resource replace without extra prompt
- **WHEN** the user loads or replaces any resource from the UI and the session JSON changes
- **THEN** the system marks the session dirty at the user-initiated entry point and does not show an additional unsaved-changes dialog for that action alone

### Requirement: Unsaved changes before destructive session navigation
When the session is dirty, the system SHALL prompt the user with **Save**, **Don't Save**, and **Cancel** before actions that would discard in-memory session state.

The prompt SHALL use conventional desktop wording: state that there are unsaved changes and ask whether to save them before quitting, closing the current session, or opening another session. The system SHALL NOT use internal terms such as “workbench” in the prompt text.

For **Open Session**, the system SHALL show the unsaved-changes prompt before the open file dialog when the current session is dirty.

For **Save** in the prompt, the system SHALL save to the current session path when known, or behave like Save Session As when the session is untitled. If save fails or the user cancels Save As, the system SHALL cancel the guarded action and leave the current session unchanged and dirty.

For **Don't Save**, the system SHALL proceed with the requested action without writing the current session to disk.

For **Cancel**, the system SHALL abort the requested action and leave the current session unchanged.

The system SHALL NOT show the unsaved-changes prompt when loading a session from `--session` on startup or when tests call session load helpers directly without the menu guard.

When the session is not dirty, the system SHALL NOT show the unsaved-changes prompt on quit or close.

#### Scenario: Prompt before quit when dirty
- **WHEN** the user quits the application while the session is dirty
- **THEN** the system shows an unsaved-changes prompt with Save, Don't Save, and Cancel before exiting

#### Scenario: No prompt before quit when clean
- **WHEN** the user quits the application while the session is not dirty
- **THEN** the system exits without an unsaved-changes or save prompt

#### Scenario: Prompt before close session when dirty
- **WHEN** the user invokes Close Session while the session is dirty
- **THEN** the system shows an unsaved-changes prompt with Save, Don't Save, and Cancel before clearing session state

#### Scenario: Confirm close session when clean but not pristine
- **WHEN** the user invokes Close Session, the session is not dirty, and the workbench is not pristine (for example a known session path and/or loaded resources)
- **THEN** the system shows a single Yes/No confirmation that the session will be closed and resources unloaded, and does not show the Save / Don't Save / Cancel prompt

#### Scenario: Prompt before open session when dirty
- **WHEN** the user invokes Open Session while the session is dirty
- **THEN** the system shows an unsaved-changes prompt with Save, Don't Save, and Cancel before showing the open file dialog

#### Scenario: Don't save then open loads from disk
- **WHEN** the user chooses Don't Save in the Open Session unsaved-changes prompt and then selects a session file
- **THEN** the system loads that file using session load reconciliation and discards unsaved in-memory changes

#### Scenario: Don't save then cancel open file dialog
- **WHEN** the user chooses Don't Save in the Open Session unsaved-changes prompt and then cancels the open file dialog without selecting a file
- **THEN** the system does not load a new session, leaves the current session unchanged, and keeps the session dirty

#### Scenario: Save then open when path known
- **WHEN** the user chooses Save in the Open Session unsaved-changes prompt and the current session path is known and save succeeds
- **THEN** the system saves to the current path and then continues to the open file dialog

#### Scenario: Save then open when untitled
- **WHEN** the user chooses Save in the Open Session unsaved-changes prompt and no current session path is known
- **THEN** the system prompts for a save path as in Save Session As and continues to open only if save succeeds

#### Scenario: Abort guarded action when save validation fails
- **WHEN** the user chooses Save in an unsaved-changes prompt and session save fails validation
- **THEN** the system shows the validation error, keeps the session dirty, and does not quit, close the session, or open another session

#### Scenario: No prompt on startup session load
- **WHEN** the user launches the heatmap alignment GUI with `--session` and a valid session path
- **THEN** the system loads that session without an unsaved-changes prompt

#### Scenario: Close pristine session without dialog
- **WHEN** the user invokes Close Session, the session is not dirty, and the workbench is pristine (untitled, default session state, no loaded resources)
- **THEN** the system closes the session without a confirmation or unsaved-changes dialog

## MODIFIED Requirements

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
- **THEN** the system updates the current session path to the chosen path, clears the dirty flag, and refreshes the main window title and Resources window session context

#### Scenario: Save session without requiring loaded camera and H5
- **WHEN** the user invokes Save Session or Save from an unsaved-changes prompt
- **THEN** the system allows save based on the current alignment session JSON and does not require camera video and H5 recording to be loaded in memory, using validation that permits missing or absent source files on disk when paths are recorded

#### Scenario: Open session updates identity
- **WHEN** the user opens a saved session successfully
- **THEN** the system updates the current session path to the opened path, clears the dirty flag, and refreshes the main window title and Resources window session context

#### Scenario: Close current session after dirty discard or clean confirmation
- **WHEN** the user invokes Close Session and proceeds after the unsaved-changes prompt (including Don't Save), or confirms close when the session is clean but not pristine, or closes a pristine clean session without a prompt
- **THEN** the system clears loaded resources and session state, forgets the current session path, clears the dirty flag, and returns to an untitled session without exiting the program
