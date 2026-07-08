from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

import heatmap_alignment_session_lifecycle as lifecycle_module  # noqa: E402
from heatmap_alignment_core_models import (  # noqa: E402
    AlignmentSession,
    CameraTrack,
    PeakSeriesSessionEntry,
)
from heatmap_alignment_session_lifecycle import (  # noqa: E402
    SessionLifecycleState,
    SessionTransitionGuard,
)


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


def test_lifecycle_prepare_session_for_save_syncs_peak_entries() -> None:
    lifecycle = SessionLifecycleState()
    session = AlignmentSession()
    peak_entries = [
        PeakSeriesSessionEntry(
            path="/tmp/peaks.json",
            display_name="peaks",
            color="#3b82f6",
        )
    ]

    prepared = lifecycle.prepare_session_for_save(session, peak_entries=peak_entries)

    assert prepared is session
    assert session.peak_series == peak_entries


def test_lifecycle_prepare_session_for_save_validates_payload() -> None:
    lifecycle = SessionLifecycleState()
    session = AlignmentSession()
    session.viewport.output_width = -1

    try:
        lifecycle.prepare_session_for_save(session, peak_entries=[])
    except ValueError as exc:
        assert "Viewport output dimensions" in str(exc)
    else:
        raise AssertionError("Expected invalid session payload to fail validation")


def test_lifecycle_save_to_path_writes_session_and_updates_path(tmp_path: Path) -> None:
    lifecycle = SessionLifecycleState()
    session_path = tmp_path / "alignment.json"
    session = AlignmentSession(camera_track=CameraTrack(path="/tmp/camera.mp4"))

    lifecycle.save_to_path(session, session_path)

    assert session_path.exists()
    assert lifecycle.current_path == session_path


def test_lifecycle_save_to_path_does_not_update_path_on_failure(
    monkeypatch, tmp_path: Path
) -> None:
    existing_path = tmp_path / "existing.json"
    lifecycle = SessionLifecycleState(current_path=existing_path)
    session_path = tmp_path / "alignment.json"
    session = AlignmentSession(camera_track=CameraTrack(path="/tmp/camera.mp4"))

    def fail_save(_session: AlignmentSession, _path: Path) -> None:
        raise OSError("save failed")

    monkeypatch.setattr(lifecycle_module, "save_alignment_session", fail_save)

    try:
        lifecycle.save_to_path(session, session_path)
    except OSError:
        pass
    else:
        raise AssertionError("Expected session save to fail")

    assert lifecycle.current_path == existing_path


def test_lifecycle_load_from_path_reads_session_and_updates_path(tmp_path: Path) -> None:
    lifecycle = SessionLifecycleState()
    session_path = tmp_path / "alignment.json"
    camera_path = tmp_path / "camera.mp4"
    camera_path.touch()
    original = AlignmentSession(camera_track=CameraTrack(path=str(camera_path)))
    SessionLifecycleState().save_to_path(original, session_path)

    loaded = lifecycle.load_from_path(session_path)

    assert loaded.camera_track.path == str(camera_path)
    assert lifecycle.current_path == session_path


def test_lifecycle_load_from_path_does_not_update_path_on_failure(tmp_path: Path) -> None:
    lifecycle = SessionLifecycleState(current_path=tmp_path / "existing.json")
    missing_path = tmp_path / "missing.json"

    try:
        lifecycle.load_from_path(missing_path)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Expected missing session load to fail")

    assert lifecycle.current_path == tmp_path / "existing.json"


def test_lifecycle_prompt_for_dirty_session_without_unsaved_peaks() -> None:
    lifecycle = SessionLifecycleState(dirty=True)

    prompt = lifecycle.save_discard_cancel_prompt("quit", peaks_unsaved=False)

    assert prompt.title == "Quit Heatmap Alignment?"
    assert prompt.text == "There are unsaved changes. Do you want to save them before quitting?"


def test_lifecycle_prompt_for_unsaved_peaks_without_dirty_session() -> None:
    lifecycle = SessionLifecycleState(dirty=False)

    prompt = lifecycle.save_discard_cancel_prompt("close", peaks_unsaved=True)

    assert prompt.title == "Close Session?"
    assert "Unsaved peak-distance data will be lost if you close this session." in prompt.text
    assert "Saving the alignment session does not write peak JSON." in prompt.text
    assert prompt.text.endswith("Proceed?")


def test_lifecycle_prompt_for_dirty_session_with_unsaved_peaks() -> None:
    lifecycle = SessionLifecycleState(dirty=True)

    prompt = lifecycle.save_discard_cancel_prompt("open", peaks_unsaved=True)

    assert prompt.title == "Open Another Session?"
    assert "There are unsaved changes." in prompt.text
    assert "opening another session" in prompt.text
    assert "Unsaved peak-distance data will also be lost." in prompt.text
    assert "Saving the alignment session does not write peak JSON." in prompt.text


def test_lifecycle_clean_close_session_prompt() -> None:
    lifecycle = SessionLifecycleState()

    prompt = lifecycle.clean_close_session_prompt()

    assert prompt.title == "Close Session?"
    assert prompt.text == "Close this session and unload all resources?"


def test_lifecycle_clear_current_path_reports_change(tmp_path: Path) -> None:
    lifecycle = SessionLifecycleState(current_path=tmp_path / "session.json")

    assert lifecycle.clear_current_path() is True
    assert lifecycle.current_path is None
    assert lifecycle.clear_current_path() is False


def test_reset_after_close_clears_path_and_returns_fresh_session(tmp_path: Path) -> None:
    lifecycle = SessionLifecycleState(current_path=tmp_path / "session.json")

    reset = lifecycle.reset_after_close()

    assert lifecycle.current_path is None
    assert reset.path_cleared is True
    assert reset.session == AlignmentSession()


def test_reset_after_close_without_path_reports_path_not_cleared() -> None:
    lifecycle = SessionLifecycleState()

    reset = lifecycle.reset_after_close()

    assert lifecycle.current_path is None
    assert reset.path_cleared is False
    assert reset.session == AlignmentSession()


def test_session_transition_guard_prompt_values() -> None:
    assert SessionTransitionGuard(prompt="none").prompt == "none"
    assert SessionTransitionGuard(prompt="save_discard_cancel").prompt == "save_discard_cancel"
    assert SessionTransitionGuard(prompt="clean_close_confirm").prompt == "clean_close_confirm"


def _empty_loaded_flags() -> dict[str, bool]:
    return {
        "has_camera": False,
        "has_h5": False,
        "has_peaks": False,
        "has_leg2": False,
    }


def test_transition_guard_dirty_session_requests_save_discard_cancel() -> None:
    lifecycle = SessionLifecycleState(dirty=True)

    guard = lifecycle.transition_guard(
        "open",
        AlignmentSession(),
        peaks_unsaved=False,
        **_empty_loaded_flags(),
    )

    assert guard.prompt == "save_discard_cancel"


def test_transition_guard_unsaved_peaks_requests_save_discard_cancel() -> None:
    lifecycle = SessionLifecycleState()

    guard = lifecycle.transition_guard(
        "quit",
        AlignmentSession(),
        peaks_unsaved=True,
        **_empty_loaded_flags(),
    )

    assert guard.prompt == "save_discard_cancel"


def test_transition_guard_clean_non_pristine_close_requests_confirm() -> None:
    lifecycle = SessionLifecycleState()

    guard = lifecycle.transition_guard(
        "close",
        AlignmentSession(camera_track=CameraTrack(path="/tmp/camera.mp4")),
        peaks_unsaved=False,
        **_empty_loaded_flags(),
    )

    assert guard.prompt == "clean_close_confirm"


def test_transition_guard_clean_non_pristine_open_proceeds_without_confirm() -> None:
    lifecycle = SessionLifecycleState()

    guard = lifecycle.transition_guard(
        "open",
        AlignmentSession(camera_track=CameraTrack(path="/tmp/camera.mp4")),
        peaks_unsaved=False,
        **_empty_loaded_flags(),
    )

    assert guard.prompt == "none"


def test_transition_guard_pristine_close_proceeds_silently() -> None:
    lifecycle = SessionLifecycleState()

    guard = lifecycle.transition_guard(
        "close",
        AlignmentSession(),
        peaks_unsaved=False,
        **_empty_loaded_flags(),
    )

    assert guard.prompt == "none"


def test_transition_guard_loaded_camera_close_requests_confirm() -> None:
    lifecycle = SessionLifecycleState()
    flags = _empty_loaded_flags()
    flags["has_camera"] = True

    guard = lifecycle.transition_guard(
        "close",
        AlignmentSession(),
        peaks_unsaved=False,
        **flags,
    )

    assert guard.prompt == "clean_close_confirm"


def test_transition_guard_dirty_close_prefers_save_discard_cancel() -> None:
    lifecycle = SessionLifecycleState(dirty=True)
    flags = _empty_loaded_flags()
    flags["has_camera"] = True

    guard = lifecycle.transition_guard(
        "close",
        AlignmentSession(),
        peaks_unsaved=False,
        **flags,
    )

    assert guard.prompt == "save_discard_cancel"


def test_lifecycle_window_title_untitled_and_named(tmp_path: Path) -> None:
    lifecycle = SessionLifecycleState()

    assert lifecycle.window_title() == "Heatmap Alignment Workbench — Untitled Session"

    lifecycle.mark_dirty()
    assert lifecycle.window_title() == "Heatmap Alignment Workbench — Untitled Session*"

    lifecycle.current_path = tmp_path / "trial.json"
    lifecycle.clear_dirty()
    assert lifecycle.window_title() == "Heatmap Alignment Workbench — trial.json"

    lifecycle.mark_dirty()
    assert lifecycle.window_title() == "Heatmap Alignment Workbench — trial.json*"
