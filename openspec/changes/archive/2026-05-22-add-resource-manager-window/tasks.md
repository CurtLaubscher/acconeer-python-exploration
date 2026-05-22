## 1. Resource Summary Model

- [x] 1.1 Add a small resource-summary model or helper for Camera Video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT rows
- [x] 1.2 Include resource type, role/name, status, path, semantic color marker, details text, warnings/errors, and available actions in each summary
- [x] 1.3 Preserve remembered paths and failed reload state for resources referenced by a loaded session
- [x] 1.4 Add focused tests for unloaded, loaded, warning, missing, and invalid resource summary states

## 2. Resources Menu

- [x] 2.1 Add a top-level Resources menu with a Manage Resources action
- [x] 2.2 Move Camera Video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT load/replace actions into the Resources menu
- [x] 2.3 Add Resources menu unload/clear actions with correct enabled state for each resource type
- [x] 2.4 Keep session open, save, save as, close session, synced video export, and quit actions in the File menu
- [x] 2.5 Add Save Session behavior that writes to the current session path and falls back to Save Session As for untitled sessions
- [x] 2.6 Add Close Session behavior that confirms, clears loaded resources/session state, forgets the current session path, and leaves the program open
- [x] 2.7 Add focused tests or smoke coverage for menu action availability and enabled-state updates

## 3. Resources Window UI

- [x] 3.1 Implement a modeless Resources window owned by the heatmap alignment main window
- [x] 3.2 Reopen the existing Resources window by raising/focusing it instead of creating duplicate windows
- [x] 3.3 Add a resource table that lists the supported resource slots even when unloaded
- [x] 3.4 Render semantic color associations as a compact swatch/marker cell without a visible "Color" column label
- [x] 3.5 Show full file paths in the table using middle elision that preserves the full filename when width allows
- [x] 3.6 Add a selected-row details area that shows the unelided full path, metadata, warnings, and available actions
- [x] 3.7 Keep the window synchronized when resources are loaded, replaced, unloaded, cleared, reloaded, or fail validation
- [x] 3.8 Show current session path context in the Resources window without listing the session as a datasource row

## 4. Resource Actions

- [x] 4.1 Route Resources window load/replace actions through the existing Camera Video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT load paths
- [x] 4.2 Route Resources window unload/clear actions through existing clear paths for optional datasources
- [x] 4.3 Add explicit unload behavior for primary Camera Video and Radar Raw (H5) resources, clearing only directly dependent state
- [x] 4.4 Add reload behavior for resources with remembered paths
- [x] 4.5 Add reveal-path behavior using platform-supported file browser integration
- [x] 4.6 Add warning/error inspection behavior that does not rely only on status-bar messages
- [x] 4.7 Add row context menus that expose the same applicable row-scoped actions as selected-row buttons
- [x] 4.8 Add confirmed Clear All Resources behavior that clears resources and dependent state while preserving the current session path
- [x] 4.9 Avoid adding double-click load/replace behavior
- [x] 4.10 Preserve loaded Radar Peak (JSON) and Leg2 MAT resources as displayable signal resources when Radar Raw (H5) is unloaded and their loaded data remains available

## 5. Main Layout Cleanup

- [x] 5.1 Remove duplicated top-row load buttons after Resources menu/window actions are available
- [x] 5.2 Remove Radar Peak (JSON) and Leg2 MAT import/clear buttons from the Render panel
- [x] 5.3 Keep visualization controls near the relevant preview or signal controls, including peak marker visibility, Leg2 signal visibility, and Leg2 raw/filtered selection
- [x] 5.4 Verify save/export/playback/timeline/viewport/render controls remain discoverable and enabled according to current resource state
- [x] 5.5 Update the main window title when the session is untitled, opened, saved, saved as, or closed

## 6. Verification

- [x] 6.1 Run focused GUI/resource tests with the repo-managed Hatch environment
- [x] 6.2 Manually smoke-test opening the Resources window, loading/replacing/unloading each current resource type, and keeping the window open during alignment interaction
- [x] 6.3 Manually smoke-test a session with a missing remembered resource path and confirm the row shows the remembered path with a missing or invalid status
- [x] 6.4 Manually smoke-test Save Session, Save Session As, Close Session, Clear All Resources, and Resources window refocus behavior
- [x] 6.5 Run `openspec validate add-resource-manager-window --strict`

## 7. Smoke-Test Polish Follow-Ups

- [x] 7.1 Rename resource reveal actions from "Reveal Path" to "Show in File Manager"
- [x] 7.2 Update path elision to preserve the separator immediately before the filename when width allows
- [x] 7.3 Refocus an already-open Resources window without moving it from the user's chosen position
- [x] 7.4 Reorder selected-resource details so resource identity appears first, and omit the path detail when no path exists
- [x] 7.5 Normalize Resources table selection so it uses one full selected row, preserves selection painting in custom delegates, and avoids mixed current-cell visuals
- [x] 7.6 Keep Resources table headers non-interactive unless sorting or column actions are intentionally implemented
- [x] 7.7 Add Qt mnemonics to Resources menu and common resource action labels without adding custom Escape-key behavior
- [x] 7.8 Add focused tests or smoke coverage for the Resources window polish changes

## 8. Resources Window Dismissal

- [x] 8.1 Add an obvious in-window dismissal action for the Resources window, preferably a bottom-row Close button unless a window-local menu is also justified
- [x] 8.2 Ensure dismissing the Resources window only closes or hides that utility window without unloading resources, closing the session, exiting the main workbench, or changing alignment state
- [x] 8.3 Add focused tests or smoke coverage for the Resources window dismissal action
