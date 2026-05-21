## Why

The heatmap alignment workbench still exposes the saved-session startup option as `--artifact`, an older and non-specific term that no longer matches the user-facing "Session" language. This makes command-line session resume harder to discover and easier to misunderstand.

## What Changes

- **BREAKING**: Replace the `--artifact` startup argument with `--session` for loading a saved alignment session.
- Remove `--artifact` from user-facing CLI help and startup parsing for the heatmap alignment workbench.
- Rename nearby saved-session helpers, GUI methods, settings keys, tests, and error wording from artifact terminology to session terminology where this can be done without changing the saved JSON format.
- Keep startup precedence behavior conceptually the same: when a session file is provided, it defines the saved alignment state and takes precedence over individual camera/H5 startup source arguments.
- Update user-facing help/error wording to refer to saved alignment sessions rather than artifacts.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `heatmap-alignment-gui`: Replace the saved-session startup CLI argument and user-facing wording from artifact terminology to session terminology.

## Impact

- Affected code: `user_tools/heatmap_alignment_gui.py` startup argument parsing and launch path.
- Affected code: `user_tools/heatmap_alignment_core.py` saved-session load/save helper names and validation errors.
- Affected tests: heatmap alignment core and GUI/startup tests that cover saved-session roundtrips, command-line arguments, and session-loading precedence.
- Affected docs/help: CLI help text for `hatch run app:heatmap-align` and any nearby comments or user-facing messages that mention `artifact`.
- Dependencies: none.
