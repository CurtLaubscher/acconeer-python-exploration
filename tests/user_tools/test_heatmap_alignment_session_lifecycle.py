from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

from heatmap_alignment_core import AlignmentSession, CameraTrack  # noqa: E402
from heatmap_alignment_session_lifecycle import SessionLifecycleState  # noqa: E402


def test_lifecycle_mark_dirty_reports_visible_state_change() -> None:
    lifecycle = SessionLifecycleState()

    assert lifecycle.mark_dirty() is True
    assert lifecycle.dirty is True
    assert lifecycle.mark_dirty() is False


def test_lifecycle_dirty_guard_suppresses_dirty_mark() -> None:
    lifecycle = SessionLifecycleState()

    with lifecycle.dirty_guard():
        assert lifecycle.mark_dirty() is False

    assert lifecycle.dirty is False


def test_lifecycle_dirty_guard_supports_nesting() -> None:
    lifecycle = SessionLifecycleState()

    with lifecycle.dirty_guard():
        with lifecycle.dirty_guard():
            assert lifecycle.mark_dirty() is False
        assert lifecycle.mark_dirty() is False

    assert lifecycle.mark_dirty() is True


def test_lifecycle_clear_dirty_reports_visible_state_change() -> None:
    lifecycle = SessionLifecycleState(dirty=True)

    assert lifecycle.clear_dirty() is True
    assert lifecycle.dirty is False
    assert lifecycle.clear_dirty() is False


def test_lifecycle_pristine_requires_untitled_empty_default_session() -> None:
    lifecycle = SessionLifecycleState()

    assert lifecycle.is_pristine(
        AlignmentSession(),
        has_camera=False,
        has_h5=False,
        has_peaks=False,
        has_leg2=False,
    )

    lifecycle.current_path = Path("/tmp/session.json")
    assert not lifecycle.is_pristine(
        AlignmentSession(),
        has_camera=False,
        has_h5=False,
        has_peaks=False,
        has_leg2=False,
    )


def test_lifecycle_pristine_rejects_loaded_resources_or_nondefault_session() -> None:
    lifecycle = SessionLifecycleState()

    assert not lifecycle.is_pristine(
        AlignmentSession(camera_track=CameraTrack(path="/tmp/camera.mp4")),
        has_camera=False,
        has_h5=False,
        has_peaks=False,
        has_leg2=False,
    )
    assert not lifecycle.is_pristine(
        AlignmentSession(),
        has_camera=True,
        has_h5=False,
        has_peaks=False,
        has_leg2=False,
    )
    assert not lifecycle.is_pristine(
        AlignmentSession(),
        has_camera=False,
        has_h5=True,
        has_peaks=False,
        has_leg2=False,
    )
    assert not lifecycle.is_pristine(
        AlignmentSession(),
        has_camera=False,
        has_h5=False,
        has_peaks=True,
        has_leg2=False,
    )
    assert not lifecycle.is_pristine(
        AlignmentSession(),
        has_camera=False,
        has_h5=False,
        has_peaks=False,
        has_leg2=True,
    )
