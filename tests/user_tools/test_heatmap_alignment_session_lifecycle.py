from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

from heatmap_alignment_core import AlignmentSession, CameraTrack, PeakSeriesSessionEntry  # noqa: E402
import heatmap_alignment_session_lifecycle as lifecycle_module  # noqa: E402
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
