## Context

The heatmap alignment GUI currently exposes resource actions in multiple places:

- The File menu includes camera/radar load actions, optional datasource import/clear actions, session open/save actions, export, and quit.
- The main top row duplicates camera/radar/session/export actions.
- The Render panel contains optional datasource import/clear controls and loaded-state labels for Radar Peak (JSON) and Leg2 MAT.

That layout worked when the app had only Camera Video and Radar Raw (H5) sources, but it is becoming unclear as optional Radar Peak (JSON) and Leg2 MAT datasources join the same workflow. Users need a single place to answer "what is loaded?", inspect file paths, see resource colors, and load or unload each resource.

## Goals / Non-Goals

**Goals:**

- Add a top-level Resources menu for resource-oriented commands.
- Add a modeless Resources window that can remain open while the user aligns data.
- Give modeless utility windows an obvious in-window dismissal affordance, such as a Close button and/or a window-local close menu item, rather than relying only on the title-bar close control.
- List known resource slots even when unloaded, so the user can see what the workbench supports.
- Use a small unlabeled color swatch/marker cell rather than a text-labeled "Color" column.
- Show full resource paths where space allows, with middle elision that tries to preserve the full filename.
- Provide load/replace and unload/clear actions from the Resources window.
- Provide selected-row action buttons and matching row context-menu actions in the Resources window.
- Use clear user-facing action labels, including `Show in File Manager` for the action that reveals a resource path in the platform file browser.
- Keep Resources table selection simple and native-feeling: one selected row, no cell-like secondary selection state, no custom selection visuals that obscure the selected row, and no interactive header behavior unless sorting is intentionally added later.
- Provide a confirmed "Clear All Resources" action that clears loaded resources without forgetting the current session path.
- Show the current session identity in the main window title and support both `Save Session` and `Save Session As...`.
- Provide a File-menu action to close the current session without exiting the workbench.
- Surface stale, missing, invalid, or warning states when a session remembers a path that cannot currently be loaded.
- Remove or reduce duplicated top-level load buttons and optional datasource controls after equivalent resource actions are available.
- Keep the design compatible with future multiple resource instances without implementing arbitrary multi-resource loading now.

**Non-Goals:**

- Generic arbitrary resource adapters.
- Loading multiple Camera Video resources, multiple Radar Raw (H5) recordings, or multiple MAT files in this change.
- MAT variable browsing or arbitrary signal selection.
- Track linking, selected-track offset controls, or multi-track group actions.
- Exporting Signals or Leg2 data into synced videos.
- Changing session file semantics except as needed to display remembered resource status.
- Dirty-session tracking, unsaved-change markers, and save prompts before exit or session replacement.

## Decisions

### Add A Resources Menu Separate From File

Create a top-level `Resources` menu for data-source actions:

- `Manage Resources...`
- Load/replace actions for Camera Video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT.
- Unload/clear actions for the same resource types, disabled when the relevant resource cannot be unloaded.
- Reload actions when a stored path exists or a resource has a failed reload state.

Keep session open/save and synced video export under `File`. A session references resources and restores state, but it is not itself a datasource. The Resources window can display the current session path as contextual information without moving session persistence into the Resources menu.

The File menu should support:

- `Open Session...`
- `Save Session`
- `Save Session As...`
- `Close Session`
- `Export Synced Video...`
- `Quit`

`Save Session` should write to the current session path when one is known. For an untitled session, it should fall back to `Save Session As...`. `Save Session As...` should update the current session path after a successful save.

`Close Session` should reset the workbench to an untitled empty session and clear loaded resources. This is intentionally different from `Clear All Resources`, which clears resources but keeps the current session path. Because dirty-session tracking is out of scope, `Close Session` may use a simple confirmation rather than a save/discard/cancel prompt.

The main window title should include the current session identity, such as the session filename when a path is known or `Untitled Session` otherwise. The Resources window should show the same session path context.

Alternative considered: put session open/save in Resources too. That would group all file-related operations, but it blurs the difference between "load data into this session" and "open/save the session state itself."

### Use A Modeless Resource Manager Window

Use a modeless `QDialog` or secondary `QWidget` owned by the main window. It should stay synchronized with the main window state and allow users to keep it open while loading, unloading, dragging tracks, and saving sessions. Reopening Resources while the window already exists should raise/focus the existing window instead of creating duplicates, without moving a window that the user has already positioned. If the existing window is minimized, restoring it is appropriate.

The window should contain:

- A compact toolbar or top action row with context-aware commands.
- A resource table for scanning.
- A details/action area for the selected row.

The table is the overview; the details area is where longer paths, warnings, and precise actions live. This avoids forcing every action into tiny table cells.

Alternative considered: a modal load/unload dialog. That would be simpler, but it would not work as well as a persistent "what is loaded?" reference while aligning data.

### Provide An Obvious Dismiss Action

Modeless utility windows should provide a visible way to dismiss the window from within the window itself. For the Resources window, a bottom-row `Close` button is sufficient and avoids adding a full menu bar solely for one action. If more window-local actions are added later, a small window-local menu such as `File > Close` can be considered.

Closing the Resources window should only hide or close the manager window. It should not unload resources, close the session, change alignment state, or exit the main workbench.

Alternative considered: rely only on the operating-system title-bar close button. That works technically, but smoke testing showed users can look for an in-window `Close` action in a utility window.

### Show Fixed Resource Slots First

For this change, the resource table should list the known slots with user-facing resource names:

- Camera Video
- Radar Raw (H5)
- Radar Peak (JSON)
- Leg2 MAT

Rows should exist even when unloaded. This makes supported resource types discoverable and answers "what can I load here?" without relying on menu exploration.

If a saved session references a resource path that fails to reload, the corresponding row should remain visible with a failed/missing/warning status and the remembered path. That is the useful "not found" case: it is not a newly discovered file, but a resource the session expected and could not load.

Future multiple-resource support can evolve the table from fixed slots to resource instances with `type`, `role`, and `display name` fields, such as `Camera Video / Primary / cam_A.mp4`, `Radar Raw (H5) / Reference / trial.h5`, and `MAT Signal / Leg2 Ultrasonic / leg2.mat`.

Alternative considered: list only loaded resources. That keeps the table shorter, but it hides available resource types and makes missing session resources harder to diagnose.

### Use A Swatch Marker Instead Of A "Color" Column

Represent resource color with a narrow swatch/marker column that has no visible "Color" text label. The visual marker should match the semantic color family used for timeline bars, signal plots, legends, and related warnings.

For unloaded resources, the swatch may show the reserved semantic color in a muted style. For resources without a visual association, the swatch can be empty or neutral.

Alternative considered: a normal column labeled `Color`. That is explicit, but it adds UI text for something that is better understood visually and would make the table feel more like a raw data grid.

### Preserve Filenames In Elided Full Paths

The resource table should show full paths, not only filenames, because files from different trial folders may share names. When the path does not fit, use middle elision so the drive/root and filename remain visible and the filename is preserved when the available width allows it. The preserved suffix should try to include the path separator immediately before the filename, such as `\trial.h5` on Windows or `/trial.h5` on Linux, so the filename does not read like a standalone token. At extremely narrow widths the UI should still prefer middle elision, but the details area and tooltip should be the authoritative place for the unelided full path.

The details area should show the selected resource type/name first, then status/details/warnings, then the unelided full path when one exists. For unloaded resources without a remembered path, omit the path row instead of showing a dash or placeholder. The details area should offer reveal/copy actions where available.

Alternative considered: table shows filename only and details show path. That scans well, but it does not solve the common ambiguity where multiple resources have identical exported names.

### Provide Load And Unload In The Window

The Resources window should allow users to load/replace and unload/clear resources. Menu actions are useful shortcuts, but the window should be a complete resource management surface rather than a read-only status table.

Row selection should update visible action buttons in the details area or toolbar. Direct row context menus should provide the same row-scoped actions for convenience, but they should not be the only way to access resource commands. The reveal action should be labeled `Show in File Manager` rather than `Reveal Path`, because it describes the user-visible behavior. Do not add double-click load behavior in this change; explicit buttons and context menus are clearer and easier to test.

The Resources window should also provide `Clear All Resources...`. This action should ask for confirmation using wording that makes it clear the current session path is preserved. It should unload Camera Video, Radar Raw (H5), Radar Peak (JSON), Leg2 MAT, and dependent previews/signals/timeline state. It should not clear the current session path or turn the session into a new untitled session.

Unloading a primary resource should only clear state that directly depends on that resource:

- Unloading Camera Video clears the camera source, viewport preview, camera timeline row, export overlay preview, and camera-dependent export state. Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT resources can remain loaded.
- Unloading Radar Raw (H5) clears the radar recording, rendered heatmap, radar timeline row, radar heatmap preview, and Radar Peak (JSON) validation relationship to that H5. Radar Peak (JSON) and Leg2 MAT resources can remain loaded and visible as signal/timeline resources when their own loaded data is available.
- Optional signal resources use the shared timeline's absolute zero-time coordinate even when Radar Raw (H5) is not loaded. If both Radar Peak (JSON) and Leg2 MAT are loaded, both can display; if one is loaded, only that one displays; if neither is loaded, no optional signal resource displays.

Alternative considered: window is read-only and all actions live in menus. That preserves a simple implementation but splits status and action across two places, which is the problem this change is trying to fix.

### Keep The Resources Table Predictable

The Resources table should use single-row selection and avoid custom row/cell styling that makes a focused cell look selected independently from the selected row. If custom delegates are used for swatches or elided paths, they should preserve normal selected-row background behavior. The selected resource should be derived from the selected row rather than an unrelated current cell when possible.

The header should not appear to offer sortable or clickable column behavior unless sorting is intentionally implemented. If header press feedback causes visual confusion without adding behavior, disable clickable headers.

Alternative considered: allow default cell focus and header press behavior. That is less code, but smoke testing showed it can look like multiple selection states or transient header style changes in a manager that is intended to be simple.

### Add Basic Keyboard Mnemonics Without Special Escape Handling

Menu actions and resource action buttons should use Qt mnemonics where natural, such as `&Resources`, `&Manage Resources...`, `&Load`, `&Unload`, and `Show in &File Manager`. This improves keyboard navigation without requiring a new shortcut system.

Do not add custom `Esc` behavior for the Resources window in this change. Native menu dismissal is enough; the modeless Resources window should not gain extra close-on-Esc behavior as part of this polish pass.

### Move Duplicated Controls Out Of The Main Layout

Once equivalent Resource menu/window actions exist:

- Remove the top-row `Load Camera`, `Load H5`, and `Load Session` buttons.
- Keep `Save Session` and `Export Synced Video` either under `File` only or as a smaller command area if a strong workflow reason remains.
- Remove Radar Peak (JSON) and Leg2 MAT load/clear buttons from the Render panel.
- Keep resource-specific visualization controls near the relevant visualization area when they directly affect display, such as show/hide peak marker, show/hide Leg2 signal, and raw/filtered Leg2 selection.

This keeps the main view focused on alignment, preview, timeline, and signal interpretation.

Alternative considered: duplicate all resource actions in both the main layout and Resources window. That maximizes discoverability but increases clutter and state drift.

## Risks / Trade-offs

- [Window becomes a second source of truth] -> Drive it from a single resource-summary builder that reads current session and loaded-resource state.
- [Table overfits today's four resource types] -> Model rows as resource summaries with type/role/action metadata, even though the first UI uses fixed slots.
- [Unavailable or missing resources confuse users] -> Distinguish `Unloaded`, `Loaded`, `Missing`, `Invalid`, and `Warning` states with explicit status text and details.
- [Path text becomes unreadable] -> Use middle elision in the table and full unelided text in the details area.
- [Removing top buttons hurts first-run discoverability] -> Keep direct load actions in the Resources menu and make the Resources window easy to open from the menu.
- [Session close and clear-all feel similar] -> Keep the commands separate: `Close Session` forgets the current session path and resets to untitled, while `Clear All Resources` keeps the current session identity.
- [Optional signal resources without Radar Raw feel unanchored] -> Keep a shared absolute zero-time coordinate in the timeline and allow loaded optional signal resources to display relative to that coordinate.
- [No dirty tracking can lose edits] -> Use explicit confirmations for destructive reset-style actions and leave proper dirty tracking plus save/discard prompts as a follow-up idea.
- [Qt table tests are brittle] -> Keep resource summary generation testable without rendering and add focused GUI smoke tests for the table/window.
