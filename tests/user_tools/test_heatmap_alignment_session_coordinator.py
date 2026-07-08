from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

from heatmap_alignment_core_models import (  # noqa: E402
    AlignmentSession,
    CameraTrack,
    HeatmapTrack,
    Leg2UltrasonicDatasourceSettings,
    PeakSeriesSessionEntry,
)
from heatmap_alignment_reconcile import H5SlotIdentity  # noqa: E402
from heatmap_alignment_session_coordinator import (  # noqa: E402
    ClosedSessionReset,
    LoadedResourceState,
    LoadSessionPlan,
    SessionReconcilePlan,
    plan_session_reconcile,
)


def test_closed_session_reset_fields() -> None:
    session = AlignmentSession()
    reset = ClosedSessionReset(session=session, path_cleared=True)

    assert reset.session is session
    assert reset.path_cleared is True


def test_load_session_plan_defaults(tmp_path: Path) -> None:
    session_path = tmp_path / "session.json"
    plan = LoadSessionPlan(session_path=session_path)

    assert plan.session_path == session_path
    assert plan.prompt_for_unsaved is True


def test_load_session_plan_custom_prompt_flag(tmp_path: Path) -> None:
    session_path = tmp_path / "session.json"
    plan = LoadSessionPlan(session_path=session_path, prompt_for_unsaved=False)

    assert plan.prompt_for_unsaved is False


# ---------------------------------------------------------------------------
# LoadedResourceState and SessionReconcilePlan
# ---------------------------------------------------------------------------


def _empty_loaded() -> LoadedResourceState:
    return LoadedResourceState(
        camera_loaded_path=None,
        camera_inflight_path=None,
        h5_loaded_identity=None,
        h5_inflight_identity=None,
        loaded_peak_paths=frozenset(),
        leg2_loaded_path=None,
    )


# --- camera slot ---


def test_plan_reconcile_camera_keep_when_paths_match() -> None:
    session = AlignmentSession(camera_track=CameraTrack(path="/tmp/video.mp4"))
    loaded = LoadedResourceState(
        camera_loaded_path="/tmp/video.mp4",
        camera_inflight_path=None,
        h5_loaded_identity=None,
        h5_inflight_identity=None,
        loaded_peak_paths=frozenset(),
        leg2_loaded_path=None,
    )

    plan = plan_session_reconcile(session, loaded)

    assert plan.camera_action == "keep"


def test_plan_reconcile_camera_keep_when_inflight_matches() -> None:
    session = AlignmentSession(camera_track=CameraTrack(path="/tmp/video.mp4"))
    loaded = LoadedResourceState(
        camera_loaded_path=None,
        camera_inflight_path="/tmp/video.mp4",
        h5_loaded_identity=None,
        h5_inflight_identity=None,
        loaded_peak_paths=frozenset(),
        leg2_loaded_path=None,
    )

    plan = plan_session_reconcile(session, loaded)

    assert plan.camera_action == "keep"


def test_plan_reconcile_camera_load_when_path_differs() -> None:
    session = AlignmentSession(camera_track=CameraTrack(path="/tmp/new.mp4"))
    loaded = LoadedResourceState(
        camera_loaded_path="/tmp/old.mp4",
        camera_inflight_path=None,
        h5_loaded_identity=None,
        h5_inflight_identity=None,
        loaded_peak_paths=frozenset(),
        leg2_loaded_path=None,
    )

    plan = plan_session_reconcile(session, loaded)

    assert plan.camera_action == "load"


def test_plan_reconcile_camera_load_when_nothing_loaded() -> None:
    session = AlignmentSession(camera_track=CameraTrack(path="/tmp/video.mp4"))

    plan = plan_session_reconcile(session, _empty_loaded())

    assert plan.camera_action == "load"


def test_plan_reconcile_camera_unload_when_session_has_no_path() -> None:
    session = AlignmentSession()  # empty camera path
    loaded = LoadedResourceState(
        camera_loaded_path="/tmp/old.mp4",
        camera_inflight_path=None,
        h5_loaded_identity=None,
        h5_inflight_identity=None,
        loaded_peak_paths=frozenset(),
        leg2_loaded_path=None,
    )

    plan = plan_session_reconcile(session, loaded)

    assert plan.camera_action == "unload"


def test_plan_reconcile_camera_keep_when_both_empty() -> None:
    session = AlignmentSession()  # no camera

    plan = plan_session_reconcile(session, _empty_loaded())

    assert plan.camera_action == "keep"


# --- H5 slot ---


def _h5_identity(path: str) -> H5SlotIdentity:
    return H5SlotIdentity(path=path, session_idx=0, group_idx=0, entry_idx=0, subsweep_idx=0)


def test_plan_reconcile_h5_keep_when_identity_matches() -> None:
    session = AlignmentSession(heatmap_track=HeatmapTrack(path="/tmp/record.h5"))
    loaded = LoadedResourceState(
        camera_loaded_path=None,
        camera_inflight_path=None,
        h5_loaded_identity=_h5_identity("/tmp/record.h5"),
        h5_inflight_identity=None,
        loaded_peak_paths=frozenset(),
        leg2_loaded_path=None,
    )

    plan = plan_session_reconcile(session, loaded)

    assert plan.h5_action == "keep"


def test_plan_reconcile_h5_keep_when_inflight_matches() -> None:
    session = AlignmentSession(heatmap_track=HeatmapTrack(path="/tmp/record.h5"))
    loaded = LoadedResourceState(
        camera_loaded_path=None,
        camera_inflight_path=None,
        h5_loaded_identity=None,
        h5_inflight_identity=_h5_identity("/tmp/record.h5"),
        loaded_peak_paths=frozenset(),
        leg2_loaded_path=None,
    )

    plan = plan_session_reconcile(session, loaded)

    assert plan.h5_action == "keep"


def test_plan_reconcile_h5_load_when_identity_differs() -> None:
    session = AlignmentSession(heatmap_track=HeatmapTrack(path="/tmp/new.h5"))
    loaded = LoadedResourceState(
        camera_loaded_path=None,
        camera_inflight_path=None,
        h5_loaded_identity=_h5_identity("/tmp/old.h5"),
        h5_inflight_identity=None,
        loaded_peak_paths=frozenset(),
        leg2_loaded_path=None,
    )

    plan = plan_session_reconcile(session, loaded)

    assert plan.h5_action == "load"


def test_plan_reconcile_h5_unload_when_session_has_no_path() -> None:
    session = AlignmentSession()  # empty H5 path
    loaded = LoadedResourceState(
        camera_loaded_path=None,
        camera_inflight_path=None,
        h5_loaded_identity=_h5_identity("/tmp/old.h5"),
        h5_inflight_identity=None,
        loaded_peak_paths=frozenset(),
        leg2_loaded_path=None,
    )

    plan = plan_session_reconcile(session, loaded)

    assert plan.h5_action == "unload"


# --- peak set diff ---


def test_plan_reconcile_peak_paths_to_load_and_unload() -> None:
    session = AlignmentSession(
        peak_series=[
            PeakSeriesSessionEntry(path="/tmp/new_peaks.json"),
            PeakSeriesSessionEntry(path="/tmp/shared_peaks.json"),
        ]
    )
    loaded = LoadedResourceState(
        camera_loaded_path=None,
        camera_inflight_path=None,
        h5_loaded_identity=None,
        h5_inflight_identity=None,
        loaded_peak_paths=frozenset({"/tmp/old_peaks.json", "/tmp/shared_peaks.json"}),
        leg2_loaded_path=None,
    )

    plan = plan_session_reconcile(session, loaded)

    assert plan.peak_paths_to_load == frozenset({"/tmp/new_peaks.json"})
    assert plan.peak_paths_to_unload == frozenset({"/tmp/old_peaks.json"})


def test_plan_reconcile_peak_no_change_when_paths_match() -> None:
    session = AlignmentSession(
        peak_series=[PeakSeriesSessionEntry(path="/tmp/peaks.json")]
    )
    loaded = LoadedResourceState(
        camera_loaded_path=None,
        camera_inflight_path=None,
        h5_loaded_identity=None,
        h5_inflight_identity=None,
        loaded_peak_paths=frozenset({"/tmp/peaks.json"}),
        leg2_loaded_path=None,
    )

    plan = plan_session_reconcile(session, loaded)

    assert plan.peak_paths_to_load == frozenset()
    assert plan.peak_paths_to_unload == frozenset()


def test_plan_reconcile_peak_all_unloaded_when_session_empty() -> None:
    session = AlignmentSession()
    loaded = LoadedResourceState(
        camera_loaded_path=None,
        camera_inflight_path=None,
        h5_loaded_identity=None,
        h5_inflight_identity=None,
        loaded_peak_paths=frozenset({"/tmp/peaks.json"}),
        leg2_loaded_path=None,
    )

    plan = plan_session_reconcile(session, loaded)

    assert plan.peak_paths_to_load == frozenset()
    assert plan.peak_paths_to_unload == frozenset({"/tmp/peaks.json"})


# --- Leg2 slot ---


def test_plan_reconcile_leg2_keep_when_path_matches() -> None:
    session = AlignmentSession(
        leg2_ultrasonic_datasource=Leg2UltrasonicDatasourceSettings(path="/tmp/leg2.mat")
    )
    loaded = LoadedResourceState(
        camera_loaded_path=None,
        camera_inflight_path=None,
        h5_loaded_identity=None,
        h5_inflight_identity=None,
        loaded_peak_paths=frozenset(),
        leg2_loaded_path="/tmp/leg2.mat",
    )

    plan = plan_session_reconcile(session, loaded)

    assert plan.leg2_action == "keep"


def test_plan_reconcile_leg2_load_when_path_differs() -> None:
    session = AlignmentSession(
        leg2_ultrasonic_datasource=Leg2UltrasonicDatasourceSettings(path="/tmp/new.mat")
    )
    loaded = LoadedResourceState(
        camera_loaded_path=None,
        camera_inflight_path=None,
        h5_loaded_identity=None,
        h5_inflight_identity=None,
        loaded_peak_paths=frozenset(),
        leg2_loaded_path="/tmp/old.mat",
    )

    plan = plan_session_reconcile(session, loaded)

    assert plan.leg2_action == "load"


def test_plan_reconcile_leg2_unload_when_session_has_no_path() -> None:
    session = AlignmentSession()  # empty leg2 path
    loaded = LoadedResourceState(
        camera_loaded_path=None,
        camera_inflight_path=None,
        h5_loaded_identity=None,
        h5_inflight_identity=None,
        loaded_peak_paths=frozenset(),
        leg2_loaded_path="/tmp/old.mat",
    )

    plan = plan_session_reconcile(session, loaded)

    assert plan.leg2_action == "unload"


def test_plan_reconcile_leg2_load_when_nothing_loaded() -> None:
    session = AlignmentSession(
        leg2_ultrasonic_datasource=Leg2UltrasonicDatasourceSettings(path="/tmp/leg2.mat")
    )

    plan = plan_session_reconcile(session, _empty_loaded())

    assert plan.leg2_action == "load"
