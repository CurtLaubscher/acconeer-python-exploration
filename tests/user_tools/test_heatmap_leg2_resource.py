from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

from heatmap_alignment_core import (  # noqa: E402
    Leg2UltrasonicDatasourceSettings,
    LoadedLeg2UltrasonicDatasource,
)
from heatmap_leg2_resource import Leg2ResourceAdapter  # noqa: E402


def _loaded_leg2() -> LoadedLeg2UltrasonicDatasource:
    return LoadedLeg2UltrasonicDatasource(
        path=Path("/tmp/leg2.mat"),
        time_s=np.array([0.0, 0.1, 0.2], dtype=np.float64),
        raw_distance_m=np.array([1.0, 1.1, 1.2], dtype=np.float64),
        filtered_distance_m=np.array([1.0, 1.05, 1.1], dtype=np.float64),
        reliable_flag_mask=np.array([True, False, True], dtype=np.bool_),
        stance_phase_mask=np.array([False, True, True], dtype=np.bool_),
        duration_s=0.2,
    )


def test_leg2_adapter_reports_fixed_slot_state() -> None:
    settings = Leg2UltrasonicDatasourceSettings(path="/tmp/leg2.mat")
    adapter = Leg2ResourceAdapter(settings, _loaded_leg2())

    assert adapter.is_loaded() is True
    assert adapter.has_path() is True
    assert adapter.can_unload() is True
    assert adapter.path_text() == "/tmp/leg2.mat"


def test_leg2_adapter_counts_loaded_samples_and_valid_segments() -> None:
    adapter = Leg2ResourceAdapter(Leg2UltrasonicDatasourceSettings(), _loaded_leg2())

    assert adapter.sample_count() == 3
    assert adapter.valid_segment_count() == 2


def test_leg2_adapter_handles_empty_slot() -> None:
    adapter = Leg2ResourceAdapter(Leg2UltrasonicDatasourceSettings(), None)

    assert adapter.is_loaded() is False
    assert adapter.has_path() is False
    assert adapter.can_unload() is False
    assert adapter.sample_count() is None
    assert adapter.valid_segment_count() is None


def test_leg2_adapter_can_unload_remembered_path_without_loaded_datasource() -> None:
    adapter = Leg2ResourceAdapter(
        Leg2UltrasonicDatasourceSettings(path="/tmp/missing.mat"),
        None,
    )

    assert adapter.is_loaded() is False
    assert adapter.has_path() is True
    assert adapter.can_unload() is True


def test_leg2_adapter_legend_name_follows_signal_kind() -> None:
    settings = Leg2UltrasonicDatasourceSettings(signal_kind="raw")
    assert Leg2ResourceAdapter(settings, None).legend_name() == "Leg2 raw ultrasonic"

    settings.signal_kind = "filtered"
    assert Leg2ResourceAdapter(settings, None).legend_name() == "Leg2 filtered ultrasonic"


def test_leg2_adapter_mutates_session_settings_for_load_and_clear() -> None:
    settings = Leg2UltrasonicDatasourceSettings(path="/tmp/old.mat", offset_s=1.25)
    adapter = Leg2ResourceAdapter(settings, None)

    adapter.remember_path(Path("/tmp/new.mat"))
    assert Path(settings.path) == Path("/tmp/new.mat")

    adapter.clear_settings()
    assert settings.path == ""
    assert settings.offset_s == 0.0
