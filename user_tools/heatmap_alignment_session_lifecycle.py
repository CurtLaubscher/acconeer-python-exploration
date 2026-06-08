from __future__ import annotations

"""Session lifecycle state helpers for the heatmap alignment workbench."""

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Literal

from heatmap_alignment_core import (
    AlignmentSession,
    PeakSeriesSessionEntry,
    load_alignment_session,
    save_alignment_session,
    session_equivalent_for_pristine,
    validate_alignment_session,
)


@dataclass(frozen=True)
class ClosedSessionReset:
    """Default session document produced by closing the current workbench session."""

    session: AlignmentSession
    path_cleared: bool


SessionPromptAction = Literal["open", "close", "quit"]
SessionGuardPrompt = Literal["none", "save_discard_cancel", "clean_close_confirm"]

_CLOSE_SESSION_TITLE = "Close Session?"
_WINDOW_TITLE_PREFIX = "Heatmap Alignment Workbench — "


@dataclass(frozen=True)
class SaveDiscardCancelPrompt:
    title: str
    text: str


@dataclass(frozen=True)
class SessionTransitionGuard:
    """UI-neutral decision for whether a session transition needs a prompt."""

    prompt: SessionGuardPrompt


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

    def prepare_session_for_save(
        self,
        session: AlignmentSession,
        *,
        peak_entries: list[PeakSeriesSessionEntry],
    ) -> AlignmentSession:
        """Apply live save-only fields and validate before writing a session file."""
        session.peak_series = list(peak_entries)
        validate_alignment_session(session, allow_missing_sources=True)
        return session

    def save_to_path(self, session: AlignmentSession, path: Path) -> None:
        save_alignment_session(session, path)
        self.current_path = path

    def load_from_path(self, path: Path) -> AlignmentSession:
        session = load_alignment_session(path)
        self.current_path = path
        return session

    def clear_current_path(self) -> bool:
        """Clear the remembered session file path; return whether it changed."""
        if self.current_path is None:
            return False
        self.current_path = None
        return True

    def reset_after_close(self) -> ClosedSessionReset:
        """Produce a fresh session document and clear the remembered file path."""
        return ClosedSessionReset(
            session=AlignmentSession(),
            path_cleared=self.clear_current_path(),
        )

    def window_title(self) -> str:
        """Return the main window title from current path and dirty state."""
        dirty_suffix = "*" if self.dirty else ""
        if self.current_path is None:
            return f"{_WINDOW_TITLE_PREFIX}Untitled Session{dirty_suffix}"
        return f"{_WINDOW_TITLE_PREFIX}{self.current_path.name}{dirty_suffix}"

    def save_discard_cancel_prompt(
        self,
        action: SessionPromptAction,
        *,
        peaks_unsaved: bool,
    ) -> SaveDiscardCancelPrompt:
        titles: dict[SessionPromptAction, str] = {
            "open": "Open Another Session?",
            "close": _CLOSE_SESSION_TITLE,
            "quit": "Quit Heatmap Alignment?",
        }
        peaks_note = "Saving the alignment session does not write peak JSON."
        if self.dirty and peaks_unsaved:
            texts: dict[SessionPromptAction, str] = {
                "open": (
                    "There are unsaved changes. Do you want to save them before "
                    "opening another session?\n\nUnsaved peak-distance data will also be lost. "
                    f"{peaks_note}"
                ),
                "close": (
                    "There are unsaved changes. Do you want to save them before "
                    "closing this session?\n\nUnsaved peak-distance data will also be lost. "
                    f"{peaks_note}"
                ),
                "quit": (
                    "There are unsaved changes. Do you want to save them before quitting?"
                    f"\n\nUnsaved peak-distance data will also be lost. {peaks_note}"
                ),
            }
        elif peaks_unsaved:
            texts = {
                "open": (
                    "Unsaved peak-distance data will be lost if you open another session. "
                    f"{peaks_note}\n\nProceed?"
                ),
                "close": (
                    "Unsaved peak-distance data will be lost if you close this session. "
                    f"{peaks_note}\n\nProceed?"
                ),
                "quit": (
                    "Unsaved peak-distance data will be lost if you quit. "
                    f"{peaks_note}\n\nProceed?"
                ),
            }
        else:
            texts = {
                "open": (
                    "There are unsaved changes. Do you want to save them before "
                    "opening another session?"
                ),
                "close": (
                    "There are unsaved changes. Do you want to save them before "
                    "closing this session?"
                ),
                "quit": "There are unsaved changes. Do you want to save them before quitting?",
            }
        return SaveDiscardCancelPrompt(title=titles[action], text=texts[action])

    def clean_close_session_prompt(self) -> SaveDiscardCancelPrompt:
        """Return title/text for closing a clean but non-pristine session."""
        return SaveDiscardCancelPrompt(
            title=_CLOSE_SESSION_TITLE,
            text="Close this session and unload all resources?",
        )

    def transition_guard(
        self,
        action: SessionPromptAction,
        session: AlignmentSession,
        *,
        peaks_unsaved: bool,
        has_camera: bool,
        has_h5: bool,
        has_peaks: bool,
        has_leg2: bool,
    ) -> SessionTransitionGuard:
        """Return which prompt, if any, is required before a session transition."""
        if self.dirty or peaks_unsaved:
            return SessionTransitionGuard(prompt="save_discard_cancel")
        if action == "close" and not self.is_pristine(
            session,
            has_camera=has_camera,
            has_h5=has_h5,
            has_peaks=has_peaks,
            has_leg2=has_leg2,
        ):
            return SessionTransitionGuard(prompt="clean_close_confirm")
        return SessionTransitionGuard(prompt="none")
