from __future__ import annotations


"""Compatibility facade for heatmap alignment dialogs and resource widgets.

New code should import from focused modules: `heatmap_alignment_resources_window`,
`heatmap_alignment_generate_peak_dialog`, and `heatmap_alignment_heatmap_header`.
"""

from heatmap_alignment_generate_peak_dialog import *  # noqa: F403
from heatmap_alignment_heatmap_header import *  # noqa: F403
from heatmap_alignment_resources_window import *  # noqa: F403
