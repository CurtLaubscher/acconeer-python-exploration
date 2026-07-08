"""Compatibility facade for heatmap alignment core models and services.

New code should import from focused modules such as `heatmap_alignment_core_models`,
`heatmap_alignment_sources`, `heatmap_alignment_core_signals`,
`heatmap_alignment_rendering`, `heatmap_alignment_peak_import`,
`heatmap_alignment_viewport_processing`, and `heatmap_alignment_reconcile`.
"""

from __future__ import annotations

import heatmap_alignment_peak_import as _peak_import
from heatmap_alignment_core_models import *  # noqa: F403
from heatmap_alignment_core_signals import *  # noqa: F403
from heatmap_alignment_core_signals import _compute_leg2_stance_intervals  # noqa: F401
from heatmap_alignment_peak_import import *  # noqa: F403
from heatmap_alignment_reconcile import *  # noqa: F403
from heatmap_alignment_rendering import *  # noqa: F403
from heatmap_alignment_sources import *  # noqa: F403
from heatmap_alignment_sources import (  # noqa: F401
    _default_proxy_cache_root,
    _find_ffmpeg,
    _proxy_cache_path,
    _resolve_ffmpeg_path,
    _scaled_video_dimensions,
)
from heatmap_alignment_viewport_processing import *  # noqa: F403
from heatmap_alignment_viewport_processing import _viridis_lookup_table_rgb  # noqa: F401


def import_peak_distance_json_for_heatmap(json_path, heatmap_source=None):
    """Compatibility wrapper preserving monkeypatch behavior on this facade."""
    original_validate = _peak_import.validate_peak_distance_import
    original_analyze = _peak_import.analyze_heatmap_record
    _peak_import.validate_peak_distance_import = validate_peak_distance_import  # noqa: F405
    _peak_import.analyze_heatmap_record = analyze_heatmap_record  # noqa: F405
    try:
        return _peak_import.import_peak_distance_json_for_heatmap(
            json_path,
            heatmap_source,
        )
    finally:
        _peak_import.validate_peak_distance_import = original_validate
        _peak_import.analyze_heatmap_record = original_analyze
