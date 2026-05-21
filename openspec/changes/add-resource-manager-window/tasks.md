## 1. Resource Summary Model

- [ ] 1.1 Add a small resource-summary model or helper for Camera Video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT rows
- [ ] 1.2 Include resource type, role/name, status, path, semantic color marker, details text, warnings/errors, and available actions in each summary
- [ ] 1.3 Preserve remembered paths and failed reload state for resources referenced by a loaded session
- [ ] 1.4 Add focused tests for unloaded, loaded, warning, missing, and invalid resource summary states

## 2. Resources Menu

- [ ] 2.1 Add a top-level Resources menu with a Manage Resources action
- [ ] 2.2 Move Camera Video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT load/replace actions into the Resources menu
- [ ] 2.3 Add Resources menu unload/clear actions with correct enabled state for each resource type
- [ ] 2.4 Keep session open, save, save as, close session, synced video export, and quit actions in the File menu
- [ ] 2.5 Add Save Session behavior that writes to the current session path and falls back to Save Session As for untitled sessions
- [ ] 2.6 Add Close Session behavior that confirms, clears loaded resources/session state, forgets the current session path, and leaves the program open
- [ ] 2.7 Add focused tests or smoke coverage for menu action availability and enabled-state updates

## 3. Resources Window UI

- [ ] 3.1 Implement a modeless Resources window owned by the heatmap alignment main window
- [ ] 3.2 Reopen the existing Resources window by raising/focusing it instead of creating duplicate windows
- [ ] 3.3 Add a resource table that lists the supported resource slots even when unloaded
- [ ] 3.4 Render semantic color associations as a compact swatch/marker cell without a visible "Color" column label
- [ ] 3.5 Show full file paths in the table using middle elision that preserves the full filename when width allows
- [ ] 3.6 Add a selected-row details area that shows the unelided full path, metadata, warnings, and available actions
- [ ] 3.7 Keep the window synchronized when resources are loaded, replaced, unloaded, cleared, reloaded, or fail validation
- [ ] 3.8 Show current session path context in the Resources window without listing the session as a datasource row

## 4. Resource Actions

- [ ] 4.1 Route Resources window load/replace actions through the existing Camera Video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT load paths
- [ ] 4.2 Route Resources window unload/clear actions through existing clear paths for optional datasources
- [ ] 4.3 Add explicit unload behavior for primary Camera Video and Radar Raw (H5) resources, clearing only directly dependent state
- [ ] 4.4 Add reload behavior for resources with remembered paths
- [ ] 4.5 Add reveal-path behavior using platform-supported file browser integration
- [ ] 4.6 Add warning/error inspection behavior that does not rely only on status-bar messages
- [ ] 4.7 Add row context menus that expose the same applicable row-scoped actions as selected-row buttons
- [ ] 4.8 Add confirmed Clear All Resources behavior that clears resources and dependent state while preserving the current session path
- [ ] 4.9 Avoid adding double-click load/replace behavior
- [ ] 4.10 Preserve loaded Radar Peak (JSON) and Leg2 MAT resources as displayable signal resources when Radar Raw (H5) is unloaded and their loaded data remains available

## 5. Main Layout Cleanup

- [ ] 5.1 Remove duplicated top-row load buttons after Resources menu/window actions are available
- [ ] 5.2 Remove Radar Peak (JSON) and Leg2 MAT import/clear buttons from the Render panel
- [ ] 5.3 Keep visualization controls near the relevant preview or signal controls, including peak marker visibility, Leg2 signal visibility, and Leg2 raw/filtered selection
- [ ] 5.4 Verify save/export/playback/timeline/viewport/render controls remain discoverable and enabled according to current resource state
- [ ] 5.5 Update the main window title when the session is untitled, opened, saved, saved as, or closed

## 6. Verification

- [ ] 6.1 Run focused GUI/resource tests with the repo-managed Hatch environment
- [ ] 6.2 Manually smoke-test opening the Resources window, loading/replacing/unloading each current resource type, and keeping the window open during alignment interaction
- [ ] 6.3 Manually smoke-test a session with a missing remembered resource path and confirm the row shows the remembered path with a missing or invalid status
- [ ] 6.4 Manually smoke-test Save Session, Save Session As, Close Session, Clear All Resources, and Resources window refocus behavior
- [ ] 6.5 Run `openspec validate add-resource-manager-window --strict`
