## Why

Users repeatedly reopen the same session files while reviewing and iterating on radar data. A recent sessions menu reduces file-picker friction and makes command-line and GUI launch workflows feel consistent.

## What Changes

- Add a `File > Recent Sessions` menu that lists the 10 most recently opened or saved session JSON files.
- Record recent sessions when a session file is successfully opened from the GUI, successfully opened via the CLI `--session` launch path, or successfully saved.
- Store the recent sessions list as user preferences using `QSettings`.
- Show session filenames, including extensions, as menu labels and expose full paths as hover tooltips.
- Provide a disabled empty-state entry when no recent sessions exist.
- Provide a disabled `Clear Recent Sessions` action when the list is empty and an enabled action when entries exist.
- Remove a recent session automatically only when the user selects it and the file no longer exists.
- Do not scan or prune recent sessions at startup.
- Do not add individual resource files, such as HDF5 or media resources loaded by a session, to the recent sessions list.

## Capabilities

### New Capabilities
- `recent-sessions-menu`: Tracks and exposes recently used session JSON files through the GUI File menu.

### Modified Capabilities

## Impact

- Affects the session open/save and CLI `--session` launch paths.
- Affects the GUI File menu and status/message behavior for missing recent files.
- Adds persistent user preference storage through Qt `QSettings`.
- Adds focused tests for recent-session ordering, deduplication, bounding, persistence, and missing-file handling.
