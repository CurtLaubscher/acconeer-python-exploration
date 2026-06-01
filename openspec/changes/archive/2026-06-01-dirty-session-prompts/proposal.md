## Why

The heatmap alignment GUI lets users change alignment session state (viewport, offsets, resources, render settings, export overlay, optional datasources, and more) but does not track whether those changes have been saved. After session-load reconciliation made Open Session fast, switching or closing sessions without saving is an easy way to lose work. Close Session also always asks for confirmation even on an empty, unchanged session.

## What Changes

- Add a single **session dirty** flag (explicit mark/clear) for any user-driven change to persisted `AlignmentSession` fields.
- Show a `*` suffix in the main window title when the session is dirty.
- Prompt **Save / Don't Save / Cancel** before **Open Session** (before the file dialog), **Close Session**, and **Quit** when dirty.
- **Quit** when clean: no prompt.
- **Close Session** when pristine and clean: no prompt; when clean but not pristine: single Yes/No confirm (unload resources); when dirty: tri-state.
- Mark dirty only at **user-initiated** entry points; **not** when async camera/H5 jobs complete after open/reconcile/startup.
- Align **Save Session** availability and validation with “save what we have”: do not require camera and H5 to be loaded in memory; use the same permissive source validation as core `save_alignment_session`.
- Mark the session dirty after **Clear All Resources** succeeds (existing Yes/No confirm unchanged).
- Do **not** add unsaved prompts on resource replace/load or on Clear All beyond the existing clear confirm.
- Preserve session-load **reconcile** behavior; dirty prompts only gate whether destructive navigation proceeds.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `heatmap-alignment-gui`: Session dirty tracking, title `*` indicator, unsaved-change prompts on open/close/quit, pristine close behavior, and Save Session policy without camera/H5-in-memory gate.

## Impact

- `user_tools/heatmap_alignment_gui.py` — dirty state, prompts, title, save enablement, guard points on open/close/quit.
- `tests/user_tools/test_heatmap_alignment_gui.py` — prompt and dirty/title behavior with mocked dialogs.
- `openspec/specs/heatmap-alignment-gui/spec.md` — updated via delta on archive.
- `openspec/specs/heatmap-alignment-gui/ideas.md` — follow-up ideas (timeline zoom persistence, validation-aware save, snapshot dirty, GUI refactor).
