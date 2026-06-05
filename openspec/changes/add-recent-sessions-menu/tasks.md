## 1. Recent Sessions Storage

- [x] 1.1 Add a small recent-session storage helper around `QSettings` that loads, saves, clears, removes, and returns recent session paths.
- [x] 1.2 Normalize entries to absolute path strings and deduplicate by normalized path.
- [x] 1.3 Enforce a maximum of 10 entries with most-recent-first ordering.
- [x] 1.4 Defensively handle missing, empty, or malformed settings values as an empty recent sessions list.

## 2. File Menu UI

- [x] 2.1 Add `File > Recent Sessions` below the open/save session actions and before close/export actions.
- [x] 2.2 Populate one action per recent session using the filename with extension as the menu label.
- [x] 2.3 Set each recent session action tooltip or status tip to the full session path.
- [x] 2.4 Show a disabled `No Recent Sessions` entry when the recent sessions list is empty.
- [x] 2.5 Add `Clear Recent Sessions` and disable it when the list is empty.
- [x] 2.6 Refresh the submenu after adding, removing, or clearing recent session entries.

## 3. Open And Save Integration

- [x] 3.1 Add a shared open-session-from-path flow that can be used by file-picker opens, recent-menu opens, and CLI `--session` startup loads.
- [x] 3.2 Record a session path after a GUI file-picker session open succeeds.
- [x] 3.3 Record a session path after a CLI `--session` startup load succeeds through the same successful-load path.
- [x] 3.4 Record a session path after `Save Session`, `Save Session As`, or prompt-driven session save succeeds.
- [x] 3.5 Ensure cancelled opens/saves, failed opens, validation failures, and failed saves do not add recent session entries.
- [x] 3.6 Ensure loading videos, HDF5 recordings, MAT files, and peak-distance JSON resources does not add recent session entries.
- [x] 3.7 Ensure recent-menu opens for existing files use the same save/discard/cancel prompt behavior as file-picker session opens.

## 4. Missing And Failed Recent Opens

- [x] 4.1 When a selected recent session path no longer exists, show a message that the file no longer exists.
- [x] 4.2 Remove a missing selected recent session from the list and refresh the submenu.
- [x] 4.3 Check missing recent-session paths before prompting users to save or discard unsaved current work.
- [x] 4.4 Catch and report load failures for existing recent session files without removing their recent entries.
- [x] 4.5 Do not scan or prune missing recent session paths at startup.

## 5. Verification

- [x] 5.1 Add unit tests for ordering, deduplication, bounding, clearing, removing, persistence parsing, and malformed settings handling.
- [x] 5.2 Add focused tests or manual verification for File menu labels, disabled empty state, clear action state, and full-path tooltip/status hints.
- [x] 5.3 Verify GUI open, CLI `--session`, save, save-as, and prompt-save paths add recent sessions only after success.
- [x] 5.4 Verify recent-menu open cancel/proceed behavior when the current session has unsaved changes.
- [x] 5.5 Run the relevant repo-defined Hatch test or tooling command for the changed code.
