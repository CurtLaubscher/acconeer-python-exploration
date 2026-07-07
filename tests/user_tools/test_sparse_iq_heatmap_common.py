from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

from sparse_iq_heatmap_common import frame_index_at_time  # noqa: E402


class _FakeHeatmapRecord:
    def __init__(self, ticks: list[int], ticks_per_second: int) -> None:
        self.ticks = np.array(ticks, dtype=np.int64)
        self.ticks_per_second = ticks_per_second
        self.results = [object() for _ in ticks]

    @property
    def duration_s(self) -> float:
        if len(self.ticks) < 2:
            return 0.0
        return float((self.ticks[-1] - self.ticks[0]) / self.ticks_per_second)


def test_frame_index_at_time_selects_current_frame_before_midpoint() -> None:
    record = _FakeHeatmapRecord([100, 200, 300], ticks_per_second=100)

    assert frame_index_at_time(record, 0.49) == 0


def test_frame_index_at_time_selects_next_frame_after_midpoint() -> None:
    record = _FakeHeatmapRecord([100, 200, 300], ticks_per_second=100)

    assert frame_index_at_time(record, 0.51) == 1


def test_frame_index_at_time_chooses_earlier_frame_at_exact_midpoint() -> None:
    record = _FakeHeatmapRecord([100, 200, 300], ticks_per_second=100)

    assert frame_index_at_time(record, 0.5) == 0


def test_frame_index_at_time_selects_exact_frame_timestamp() -> None:
    record = _FakeHeatmapRecord([100, 200, 300], ticks_per_second=100)

    assert frame_index_at_time(record, 1.0) == 1


def test_frame_index_at_time_clamps_before_first_frame() -> None:
    record = _FakeHeatmapRecord([100, 200, 300], ticks_per_second=100)

    assert frame_index_at_time(record, -1.0) == 0


def test_frame_index_at_time_clamps_after_last_frame() -> None:
    record = _FakeHeatmapRecord([100, 200, 300], ticks_per_second=100)

    assert frame_index_at_time(record, 99.0) == 2


def test_frame_index_at_time_rejects_empty_record() -> None:
    record = _FakeHeatmapRecord([], ticks_per_second=100)

    with pytest.raises(ValueError, match="does not contain any frames"):
        frame_index_at_time(record, 0.0)
