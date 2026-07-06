from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

from heatmap_alignment_core import AlignmentSession, CameraTrack, HeatmapTrack  # noqa: E402
from heatmap_alignment_resource_summaries import (  # noqa: E402
    AlignmentResourceRuntime,
    ResourceJobPresentation,
    _resource_messages,
    build_alignment_resource_summaries,
)


def test_build_alignment_resource_summaries_cover_fixed_slots() -> None:
    summaries = build_alignment_resource_summaries(
        AlignmentSession(),
        AlignmentResourceRuntime(),
    )

    assert [summary.kind for summary in summaries] == [
        "camera",
        "radar_h5",
        "radar_peak",
        "leg2_mat",
    ]
    assert all(summary.status == "unloaded" for summary in summaries)


def test_build_alignment_resource_summaries_mark_missing_remembered_paths() -> None:
    missing = Path("/tmp/does-not-exist-camera.mp4")
    session = AlignmentSession(
        camera_track=CameraTrack(path=str(missing)),
        heatmap_track=HeatmapTrack(path=""),
    )
    summaries = build_alignment_resource_summaries(
        session,
        AlignmentResourceRuntime(
            reload_errors=(("camera", f"File not found: {missing}"),),
        ),
    )

    camera_summary = summaries[0]
    assert camera_summary.status == "missing"
    assert camera_summary.path == str(missing)
    assert "reload" in camera_summary.actions


def test_build_alignment_resource_summaries_mark_invalid_remembered_paths() -> None:
    existing = Path(__file__).resolve()
    session = AlignmentSession(
        camera_track=CameraTrack(path=str(existing)),
        heatmap_track=HeatmapTrack(path=""),
    )
    summaries = build_alignment_resource_summaries(
        session,
        AlignmentResourceRuntime(
            reload_errors=(("camera", "Could not reload camera video."),),
        ),
    )

    assert summaries[0].status == "invalid"
    assert "inspect" in summaries[0].actions


def test_build_alignment_resource_summaries_mark_loaded_state() -> None:
    session = AlignmentSession(
        camera_track=CameraTrack(path="/tmp/cam.mp4", duration_s=2.0, fps=30.0, frame_count=60),
        heatmap_track=HeatmapTrack(path=""),
    )
    summaries = build_alignment_resource_summaries(
        session,
        AlignmentResourceRuntime(camera_loaded=True),
    )

    assert summaries[0].status == "loaded"
    assert "unload" in summaries[0].actions


def test_build_alignment_resource_summaries_includes_h5_bin_widths() -> None:
    session = AlignmentSession(
        heatmap_track=HeatmapTrack(path="/tmp/radar.h5", duration_s=2.0, fps=10.0),
    )
    summaries = build_alignment_resource_summaries(
        session,
        AlignmentResourceRuntime(
            radar_h5_loaded=True,
            radar_distance_bin_width_m=0.0025,
            radar_velocity_bin_width_m_s=0.04,
        ),
    )

    h5_summary = summaries[1]
    assert h5_summary.status == "loaded"
    assert "distance bin 0.0025 m" in h5_summary.details
    assert "velocity bin 0.04 m/s" in h5_summary.details


def test_build_alignment_resource_summaries_mark_loaded_warning_state() -> None:
    session = AlignmentSession(
        camera_track=CameraTrack(path="/tmp/cam.mp4", duration_s=2.0, fps=30.0, frame_count=60),
        heatmap_track=HeatmapTrack(path=""),
    )
    summaries = build_alignment_resource_summaries(
        session,
        AlignmentResourceRuntime(
            camera_loaded=True,
            load_warnings=(("camera", "Proxy preview unavailable."),),
        ),
    )

    assert summaries[0].status == "warning"
    assert "inspect" in summaries[0].actions
    assert "Proxy preview unavailable." in summaries[0].messages


def test_resource_messages_dedupes_job_detail_already_in_reload_errors() -> None:
    failure_text = "Preview proxy generation failed.\n\nffmpeg error detail"
    runtime = AlignmentResourceRuntime(
        reload_errors=(("camera", failure_text),),
        resource_jobs=(
            ResourceJobPresentation(
                kind="camera",
                phase="failed",
                detail=failure_text,
            ),
        ),
    )

    messages = _resource_messages("camera", runtime)

    assert messages == (failure_text,)


def test_resource_messages_prepends_job_detail_when_not_in_reload_errors() -> None:
    runtime = AlignmentResourceRuntime(
        reload_errors=(),
        resource_jobs=(
            ResourceJobPresentation(
                kind="camera",
                phase="failed",
                detail="Proxy build failed.",
            ),
        ),
    )

    messages = _resource_messages("camera", runtime)

    assert messages == ("Proxy build failed.",)
