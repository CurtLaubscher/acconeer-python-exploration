## ADDED Requirements

### Requirement: Recent sessions are tracked for session JSON files
The Heatmap Alignment Workbench SHALL track recently used alignment session JSON files, not individual resource files referenced by a session.

#### Scenario: Session opened from file picker is tracked
- **WHEN** the user successfully opens an alignment session JSON file from the GUI file picker
- **THEN** the session file path is added to the recent sessions list as the most recent entry

#### Scenario: Session opened from CLI is tracked
- **WHEN** the workbench successfully opens an alignment session JSON file provided through the CLI `--session` option
- **THEN** the session file path is added to the recent sessions list as the most recent entry

#### Scenario: Session save is tracked
- **WHEN** the user successfully saves an alignment session JSON file
- **THEN** the session file path is added to the recent sessions list as the most recent entry

#### Scenario: Resource files are not tracked
- **WHEN** the user loads a camera video, HDF5 recording, MAT file, or peak-distance JSON resource
- **THEN** the resource file path is not added to the recent sessions list

### Requirement: Recent sessions use most-recent ordering
The workbench SHALL maintain a bounded most-recently-used list of at most 10 recent session file paths.

#### Scenario: Recently used session moves to top
- **WHEN** a session file already present in the recent sessions list is successfully opened or saved again
- **THEN** that existing session entry moves to the top of the list without creating a duplicate entry

#### Scenario: List is bounded
- **WHEN** adding a session file would make the recent sessions list contain more than 10 entries
- **THEN** the oldest entries are removed until only the 10 most recent entries remain

#### Scenario: Clear removes all entries
- **WHEN** the user activates Clear Recent Sessions
- **THEN** the recent sessions list becomes empty

### Requirement: Recent sessions are persisted as user preferences
The workbench SHALL persist recent sessions through Qt `QSettings` for the Heatmap Alignment Workbench application settings.

#### Scenario: Recent sessions survive restart
- **WHEN** the user opens or saves session files and then restarts the workbench
- **THEN** the File menu shows the previously recorded recent sessions in most-recent order

#### Scenario: Relative launch path becomes stable
- **WHEN** the workbench successfully opens a session from a relative CLI or dialog path
- **THEN** the recent sessions list stores a normalized absolute path for that session

### Requirement: Recent sessions are shown in the File menu
The workbench SHALL expose recent sessions under `File > Recent Sessions`.

#### Scenario: Recent sessions submenu shows entries
- **WHEN** recent session entries exist
- **THEN** the Recent Sessions submenu shows one action per recent session using the filename with extension as the action label

#### Scenario: Recent session action shows full path hint
- **WHEN** the user hovers a recent session action
- **THEN** the action exposes the full session file path as a tooltip or status tip

#### Scenario: Empty recent sessions submenu
- **WHEN** the recent sessions list is empty
- **THEN** the Recent Sessions submenu shows a disabled `No Recent Sessions` entry

#### Scenario: Clear action disabled when empty
- **WHEN** the recent sessions list is empty
- **THEN** the Clear Recent Sessions action is disabled

### Requirement: Missing recent sessions are handled on selection
The workbench SHALL handle missing recent session files only when the user selects that recent session entry.

#### Scenario: Missing selected recent session is removed
- **WHEN** the user selects a recent session entry and the session file no longer exists
- **THEN** the workbench shows a message that the session file no longer exists
- **AND** the missing file path is removed from the recent sessions list
- **AND** no session is opened from that entry

#### Scenario: Missing recent session does not prompt to discard work
- **WHEN** the user selects a recent session entry whose file no longer exists while the current session has unsaved changes
- **THEN** the workbench removes the missing entry and reports the missing file
- **AND** the workbench does not ask the user to save or discard the current session

#### Scenario: Missing recent sessions are not pruned at startup
- **WHEN** the workbench starts and a recent session path no longer exists
- **THEN** the path remains in the recent sessions list until the user selects it or clears the list

#### Scenario: Existing file that fails to load is retained
- **WHEN** the user selects a recent session entry whose file exists but cannot be loaded as a valid session
- **THEN** the workbench reports the load failure
- **AND** the path remains in the recent sessions list

### Requirement: Recent session opens protect unsaved work
The workbench SHALL use the same unsaved-change protection for existing recent session files as it uses when opening a session from the file picker.

#### Scenario: User cancels recent session open
- **WHEN** the current session has unsaved changes and the user selects an existing recent session entry
- **AND** the user cancels the save/discard/cancel prompt
- **THEN** the current session remains open
- **AND** the selected recent session is not opened

#### Scenario: User proceeds with recent session open
- **WHEN** the current session has unsaved changes and the user selects an existing recent session entry
- **AND** the user chooses to save or discard changes in a way that permits opening another session
- **THEN** the selected recent session is opened
