"""Small resource-action helpers for the heatmap alignment workbench."""

from __future__ import annotations

from pathlib import Path


def containing_directory(path: Path) -> Path:
    return path if path.is_dir() else path.parent
