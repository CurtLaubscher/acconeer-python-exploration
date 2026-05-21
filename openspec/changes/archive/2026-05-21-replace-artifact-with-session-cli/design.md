## Context

The heatmap alignment GUI uses "Session" in the visible UI for saved alignment state, but the command-line startup option still uses the older `--artifact` name. The startup path already supports loading a saved session and then applying optional startup datasources such as peak-distance JSON or Leg2 MAT files. This change keeps that behavior but makes the CLI terminology match the user-facing model.

## Goals / Non-Goals

**Goals:**

- Make `--session` the only supported command-line option for loading a saved alignment session on startup.
- Remove the old `--artifact` startup option from parser configuration, help text, and startup flow.
- Rename saved-session implementation names that are directly involved in this flow, including load/save helper functions, GUI load/save methods, startup variables, settings keys, tests, and validation errors.
- Preserve the existing session-first startup precedence: a provided session file supplies saved state before explicit optional datasource overrides are applied.
- Update nearby user-facing wording so CLI help and startup errors consistently say "session".

**Non-Goals:**

- Rename the saved JSON schema or force a migration of existing session files.
- Rename unrelated historical OpenSpec archive content or unrelated uses of the generic word "artifact".
- Change interactive Load Session / Save Session behavior.
- Add compatibility aliases or deprecation warnings for `--artifact`.

## Decisions

- Use `--session` as a replacement, not an alias. The old term is actively confusing, and this tool does not need backwards compatibility for the startup flag.
- Keep the parser destination conceptually session-oriented. Implementation can use an `args.session` path and branch startup loading from that value.
- Rename persistence helpers such as `save_alignment_artifact` / `load_alignment_artifact` to session-oriented names in the same change. These helpers are part of the mental model for the startup option and are covered by focused tests.
- Rename the internal format version constant to session terminology while preserving the serialized JSON key as `version`. Existing saved files do not contain an `artifact` key, so the persisted schema does not need migration.
- Keep session startup precedence over individual camera/H5 arguments. A saved session is a complete alignment state; allowing camera/H5 arguments to partially override it would be a larger behavior change.
- Leave file format compatibility untouched. Existing saved session JSON files remain loadable through `--session` and the GUI picker.

## Risks / Trade-offs

- Users or scripts that still call `--artifact` will fail argument parsing. Mitigation: this is intentional for this change; CLI help will show the replacement `--session` option.
- Renaming helper functions can touch more tests than the parser-only change. Mitigation: keep the rename mechanical and limited to the heatmap alignment saved-session path.
- Tests may currently assert `args.artifact`. Mitigation: update those tests to assert `args.session` and add a negative parser test for the removed flag.
