from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

from heatmap_alignment_core import AlignmentSession  # noqa: E402
from heatmap_alignment_session_coordinator import (  # noqa: E402
    ClosedSessionReset,
    LoadSessionPlan,
)


def test_closed_session_reset_fields() -> None:
    session = AlignmentSession()
    reset = ClosedSessionReset(session=session, path_cleared=True)

    assert reset.session is session
    assert reset.path_cleared is True


def test_load_session_plan_defaults(tmp_path: Path) -> None:
    session_path = tmp_path / "session.json"
    plan = LoadSessionPlan(session_path=session_path)

    assert plan.session_path == session_path
    assert plan.prompt_for_unsaved is True


def test_load_session_plan_custom_prompt_flag(tmp_path: Path) -> None:
    session_path = tmp_path / "session.json"
    plan = LoadSessionPlan(session_path=session_path, prompt_for_unsaved=False)

    assert plan.prompt_for_unsaved is False
