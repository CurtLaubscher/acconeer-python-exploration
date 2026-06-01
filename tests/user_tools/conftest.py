"""Shared fixtures for heatmap alignment user_tools tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6 import QtWidgets
from PySide6.QtWidgets import QApplication

REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

from heatmap_alignment_gui import HeatmapAlignmentWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapplication() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication()


@pytest.fixture(autouse=True)
def _no_modal_gui_dialogs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent QMessageBox/QFileDialog from blocking automated GUI tests."""
    monkeypatch.setattr(
        HeatmapAlignmentWindow,
        "_prompt_save_discard_cancel",
        lambda self, action: "discard",
    )
    monkeypatch.setattr(
        HeatmapAlignmentWindow,
        "_confirm_close_session_clean",
        lambda self: True,
    )
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: ("", ""),
    )
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: ("", ""),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "question",
        lambda *args, **kwargs: QtWidgets.QMessageBox.StandardButton.No,
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "warning",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "information",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "exec",
        lambda self: int(QtWidgets.QMessageBox.StandardButton.Cancel),
    )
