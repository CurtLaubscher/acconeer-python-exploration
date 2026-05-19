from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from PySide6 import QtCore
from PySide6.QtWidgets import QApplication


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

from heatmap_alignment_gui import CornerEditorWidget, build_argument_parser  # noqa: E402


@pytest.fixture(autouse=True, scope="module")
def qapplication() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication()


def test_build_argument_parser_accepts_peaks() -> None:
    parser = build_argument_parser()
    args = parser.parse_args(["--h5", "trial.h5", "--peaks", "peaks.json"])

    assert args.h5 == Path("trial.h5")
    assert args.peaks == Path("peaks.json")


def test_corner_editor_edge_drag_applies_delta_once() -> None:
    widget = CornerEditorWidget()
    widget.set_frame(np.zeros((100, 100, 3), dtype=np.uint8))
    widget.set_corners(
        np.array(
            [[10.0, 10.0], [90.0, 10.0], [90.0, 90.0], [10.0, 90.0]],
            dtype=np.float32,
        )
    )
    widget._drag_edge = 0
    widget._start_drag_image_pos = QtCore.QPointF(20.0, 20.0)
    widget._start_drag_corners = widget.current_corners()

    widget._translate_drag(QtCore.QPointF(30.0, 25.0))

    assert np.allclose(
        widget.current_corners(),
        np.array(
            [[19.0, 15.0], [99.0, 15.0], [90.0, 90.0], [10.0, 90.0]],
            dtype=np.float32,
        ),
    )


def test_corner_editor_center_drag_uses_bounded_drag_start_delta() -> None:
    widget = CornerEditorWidget()
    widget.set_frame(np.zeros((100, 100, 3), dtype=np.uint8))
    widget.set_corners(
        np.array(
            [[10.0, 10.0], [90.0, 10.0], [90.0, 90.0], [10.0, 90.0]],
            dtype=np.float32,
        )
    )
    widget._drag_center = True
    widget._start_drag_image_pos = QtCore.QPointF(50.0, 50.0)
    widget._start_drag_corners = widget.current_corners()

    widget._translate_drag(QtCore.QPointF(80.0, 70.0))

    assert np.allclose(
        widget.current_corners(),
        np.array(
            [[19.0, 19.0], [99.0, 19.0], [99.0, 99.0], [19.0, 99.0]],
            dtype=np.float32,
        ),
    )
