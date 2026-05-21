## 1. CLI Argument Rename

- [x] 1.1 Replace the heatmap alignment startup parser option `--artifact` with `--session`.
- [x] 1.2 Update startup loading code to read `args.session` and load the saved alignment session before applying optional datasource overrides.
- [x] 1.3 Update CLI help, examples, and nearby user-facing startup wording to use "session" instead of "artifact" for the saved alignment file argument.
- [x] 1.4 Rename saved-session helper functions, GUI methods, variables, settings keys, and validation errors from artifact terminology to session terminology where they are part of the heatmap alignment save/load path.
- [x] 1.5 Preserve the saved JSON schema, including the existing `version` key and session state fields, so existing saved session files remain loadable.

## 2. Tests

- [x] 2.1 Update parser tests to assert `--session` populates the saved-session startup path.
- [x] 2.2 Add or update a parser test that verifies legacy `--artifact` is rejected.
- [x] 2.3 Update startup precedence tests so session loading remains authoritative over camera/H5 startup arguments while explicit optional datasource startup arguments still override session datasources where specified.
- [x] 2.4 Rename saved-session roundtrip tests from artifact terminology to session terminology and keep coverage for loading existing JSON payloads.

## 3. Validation

- [x] 3.1 Run the focused heatmap alignment GUI tests through the repo-managed Hatch test environment.
- [x] 3.2 Run OpenSpec validation/status for `replace-artifact-with-session-cli` and confirm the change is apply-ready.
