from __future__ import annotations

"""Shared lifecycle concepts for heatmap alignment background jobs."""

from enum import Enum


class JobResultStatus(Enum):
    """Whether a finished background job result should still be applied."""

    ACCEPTED = "accepted"
    CANCELLED = "cancelled"
    STALE = "stale"
