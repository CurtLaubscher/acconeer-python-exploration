from __future__ import annotations


"""Qt-free helper for the fixed Leg2 MAT resource slot."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from heatmap_alignment_core_models import (
    Leg2UltrasonicDatasourceSettings,
    LoadedLeg2UltrasonicDatasource,
)


@dataclass
class Leg2ResourceAdapter:
    """Adapter for the single fixed Leg2 MAT datasource slot."""

    settings: Leg2UltrasonicDatasourceSettings
    datasource: LoadedLeg2UltrasonicDatasource | None

    def is_loaded(self) -> bool:
        return self.datasource is not None

    def path_text(self) -> str:
        return self.settings.path

    def has_path(self) -> bool:
        return bool(self.settings.path)

    def can_unload(self) -> bool:
        return self.is_loaded() or self.has_path()

    def legend_name(self) -> str:
        if self.settings.signal_kind == "filtered":
            return "Leg2 filtered ultrasonic"
        return "Leg2 raw ultrasonic"

    def sample_count(self) -> int | None:
        if self.datasource is None:
            return None
        return int(self.datasource.time_s.size)

    def valid_segment_count(self) -> int | None:
        if self.datasource is None:
            return None
        return int(np.count_nonzero(self.datasource.reliable_flag_mask))

    def clear_settings(self) -> None:
        self.settings.path = ""
        self.settings.offset_s = 0.0

    def remember_path(self, path: Path) -> None:
        self.settings.path = str(path)
