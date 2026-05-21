## Why

The heatmap alignment workbench now has several independently loadable resources, but their load, clear, status, and visibility controls are scattered across the File menu, the main top row, and the render controls. A dedicated resource management surface will make it clear what is loaded, what is missing or empty, where each file points, and how each resource relates to timeline and signal colors.

## What Changes

- Add a top-level `Resources` menu that groups load, unload, reload, and manage actions by resource type.
- Add a modeless Resources window that lists supported resource slots, including loaded and unloaded resources.
- Show each resource's status, semantic color swatch, resource type/role, full file path with middle elision, and useful resource-specific details.
- Provide load/replace, unload/clear, reload, reveal path, and warning-inspection actions from the Resources window.
- Add row context menus in the Resources window for the same row-scoped resource actions exposed by selected-row buttons.
- Add a confirmed "Clear All Resources" action that clears loaded resources without forgetting the current session path.
- Add current-session identity to the main window title and support both `Save Session` and `Save Session As...`.
- Add a File-menu action to close the current session without exiting the workbench.
- Move Camera Video, Radar Raw (H5), Radar Peak (JSON), and Leg2 MAT load/unload controls out of the main control row and render panel once they are available from the Resources menu/window.
- Keep session open/save actions under `File`, while allowing the Resources window to show the current session path as context.
- Preserve the existing one-camera/one-radar-recording workflow while structuring the UI so future multiple videos, Radar Raw (H5) recordings, `.mat` files, and derived datasources can be represented as resource instances.
- Do not introduce generic arbitrary datasource loading, `.mat` variable browsing, new timeline linking, or automatic alignment suggestions in this change.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `heatmap-alignment-gui`: Add resource management menu/window behavior and relocate existing resource load/unload controls without changing the core alignment workflow.

## Impact

- Affected GUI code:
  - `user_tools/heatmap_alignment_gui.py`
- Potentially affected core/session code:
  - `user_tools/heatmap_alignment_core.py` if reusable resource summary models are useful.
- Affected UX:
  - Top-row load buttons and optional datasource load/clear controls in the render panel are removed or reduced after equivalent resource actions exist in the menu/window.
  - Session open/save remains a File-level workflow rather than being treated as a datasource.
- Dependencies:
  - No new runtime dependency is expected; use existing PySide6/Qt functionality.
- Tests:
  - Add focused GUI/unit tests for resource summaries, menu action enablement, Resources window table contents, load/unload action routing, path elision behavior, and preservation of existing resource state.
