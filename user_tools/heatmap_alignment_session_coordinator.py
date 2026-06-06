from __future__ import annotations

"""UI-neutral session flow plans and outcomes for the alignment workbench.

Orchestration boundary (refactor track):
- ``SessionLifecycleState`` owns mutable path/dirty state and pure prompt/guard helpers.
- This module owns multi-step flow inputs and results without Qt dependencies.
- ``HeatmapAlignmentWindow`` owns widgets, dialogs, resource teardown, and preview refresh.

A future coordinator can compose lifecycle helpers into load/close/open sequences while
returning objects from this module. Do not import PySide6 or GUI modules here.
"""

from dataclasses import dataclass
from pathlib import Path

from heatmap_alignment_core import AlignmentSession


@dataclass(frozen=True)
class ClosedSessionReset:
    """Default session document produced by closing the current workbench session."""

    session: AlignmentSession
    path_cleared: bool


@dataclass(frozen=True)
class LoadSessionPlan:
    """Inputs for opening a saved session file in the workbench."""

    session_path: Path
    prompt_for_unsaved: bool = True
