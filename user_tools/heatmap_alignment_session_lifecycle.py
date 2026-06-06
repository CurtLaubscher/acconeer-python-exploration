from __future__ import annotations

"""Session lifecycle state helpers for the heatmap alignment workbench."""

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from heatmap_alignment_core import AlignmentSession, session_equivalent_for_pristine


@dataclass
class SessionLifecycleState:
    """Current session path and dirty/pristine state, independent of Qt widgets."""

    current_path: Path | None = None
    dirty: bool = False
    dirty_guard_depth: int = 0

    def mark_dirty(self) -> bool:
        """Mark dirty unless guarded; return whether the visible dirty state changed."""
        if self.dirty_guard_depth > 0:
            return False
        if self.dirty:
            return False
        self.dirty = True
        return True

    def clear_dirty(self) -> bool:
        """Clear dirty state; return whether the visible dirty state changed."""
        if not self.dirty:
            return False
        self.dirty = False
        return True

    @contextmanager
    def dirty_guard(self) -> Iterator[None]:
        self.dirty_guard_depth += 1
        try:
            yield
        finally:
            self.dirty_guard_depth -= 1

    def is_pristine(
        self,
        session: AlignmentSession,
        *,
        has_camera: bool,
        has_h5: bool,
        has_peaks: bool,
        has_leg2: bool,
    ) -> bool:
        if self.current_path is not None:
            return False
        if has_camera or has_h5 or has_peaks or has_leg2:
            return False
        return session_equivalent_for_pristine(session, AlignmentSession())
