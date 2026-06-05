## Context

The Heatmap Alignment Workbench already has a `File` menu with open, save, save-as, close, export, and quit actions. It also already creates `QtCore.QSettings("Acconeer", "HeatmapAlignmentWorkbench")` and stores last-used paths there. Session files are alignment session JSON files handled by `load_alignment_session()` and `save_alignment_session()`.

Users often reopen the same alignment session files across repeated review sessions. The recent sessions feature should make those files easy to reopen without changing what a saved session contains or attempting to restore transient workspace state.

## Goals / Non-Goals

**Goals:**
- Track the 10 most recently opened or saved alignment session JSON files.
- Expose those files under `File > Recent Sessions`.
- Use the same recent-session recording logic for GUI open, GUI save, save-as/save-prompt saves, and CLI `--session` startup load.
- Persist the list as user preferences through the existing `QSettings` instance.
- Handle missing files only when selected by the user.

**Non-Goals:**
- Do not persist or restore playback position, selected resources, window state, viewport edits beyond what the session file already stores, or any other workspace state.
- Do not add individual resource files, such as HDF5 recordings, videos, MAT files, or peak-distance JSON resources, to the recent sessions list.
- Do not scan the file system at startup to prune unavailable recent sessions.
- Do not add a separate missing-entry review or cleanup dialog.

## Decisions

1. Store recent sessions in `QSettings`.

   Use the workbench's existing `QSettings("Acconeer", "HeatmapAlignmentWorkbench")` storage instead of introducing platform-specific path logic. This delegates Windows roaming/local details to Qt's settings backend and keeps recent sessions with the rest of the app's user preferences.

   Alternative considered: using a hand-managed JSON file in a platformdirs location. That would make the file location explicit but would duplicate settings infrastructure the GUI already uses.

2. Represent entries as normalized absolute path strings.

   The recent list should store session file paths independent of the process working directory. Path matching for deduplication should use normalized absolute paths so opening or saving the same file moves one existing entry to the top instead of creating duplicates.

   Alternative considered: storing relative paths from the CLI or dialog. That would make entries fragile when the app is launched from different directories.

3. Add a small recent-session helper instead of embedding list logic in menu callbacks.

   A helper should load, save, add, remove, clear, and list recent session paths. The GUI should use it to rebuild the `Recent Sessions` submenu and to record successful session opens/saves. This keeps ordering, deduplication, and list bounding testable without requiring full GUI tests for each edge case.

   Alternative considered: keeping the list directly in `HeatmapAlignmentWindow`. That is simpler initially but makes behavior easier to duplicate incorrectly between open/save/startup paths.

4. Record recents only after successful session operations.

   A path should be added after `load_alignment_session()` and the follow-on window state update succeeds, or after `save_alignment_session()` succeeds. Failed opens, cancelled dialogs, validation failures, and failed saves must not pollute the list. Recent-session selection should call a shared "open session from path" flow so file-picker opens, recent-menu opens, and CLI startup loads have one success point for recording recents.

   Alternative considered: recording selected paths before load. That would make broken or cancelled attempts appear as recent sessions.

5. Remove missing entries only on explicit selection.

   The app should not prune recents at startup, because network drives, removable media, and synced folders can be temporarily unavailable. If a user selects a recent session whose file no longer exists, the app should show a status/message-bar message and automatically remove that entry from the list.

   Alternative considered: disabling or hiding missing entries proactively. That would require startup or menu-open file checks and can make the menu change unexpectedly.

6. Check missing recent files before prompting to discard unsaved work.

   Selecting a missing recent session cannot replace the current session, so the app should report and remove the missing entry before showing any unsaved-changes prompt. Selecting an existing recent session should use the same save/discard/cancel protection as `Open Session...` before replacing the current session.

   Alternative considered: always prompting first. That can ask users to save or discard work for an action that is about to no-op because the target path is missing.

## Risks / Trade-offs

- Stale paths can remain visible until clicked -> Avoid startup pruning and remove entries only after an explicit failed selection.
- Duplicate basenames can make menu labels ambiguous -> Keep labels as filenames with extensions and use action tooltips/status tips for full paths.
- CLI startup load can raise before the window is fully settled -> Record the recent path from the same successful load path used by GUI opens, not from argument parsing.
- `QSettings` stores strings/lists with backend-specific typing -> Keep the serialized value simple, using a list of absolute path strings and defensive parsing when reading.
- Existing session files can fail to load because they are malformed or unsupported -> Report the load failure and retain the recent entry, because the file still exists and may be fixed or opened in a compatible version later.
