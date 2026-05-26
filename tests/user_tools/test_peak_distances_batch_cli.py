from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_TOOLS_PATH = REPO_ROOT / "user_tools"
if str(USER_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_PATH))

from export_sparse_iq_peak_distances import (  # noqa: E402
    PeakDistanceBatchPlanningError,
    _default_output_path,
    _plan_batch_exports,
    _resolve_inputs,
)


def _touch_h5(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def test_resolve_inputs_explicit_files_and_sorted_order(tmp_path: Path) -> None:
    a = tmp_path / "b.h5"
    b = tmp_path / "a.hdf5"
    _touch_h5(a)
    _touch_h5(b)

    resolved = _resolve_inputs([str(a), str(b)], recursive=False)
    assert [p.source_path for p in resolved] == [b.resolve(), a.resolve()]


def test_resolve_inputs_glob_pattern(tmp_path: Path) -> None:
    a = tmp_path / "a.h5"
    b = tmp_path / "b.h5"
    ignored = tmp_path / "not_peak.txt"
    _touch_h5(a)
    _touch_h5(b)
    ignored.write_text("x", encoding="utf-8")

    resolved = _resolve_inputs([str(tmp_path / "*.h5")], recursive=False)
    assert [p.source_path for p in resolved] == [a.resolve(), b.resolve()]


def test_resolve_inputs_directory_non_recursive(tmp_path: Path) -> None:
    d = tmp_path / "d"
    _touch_h5(d / "root.h5")
    _touch_h5(d / "sub" / "nested.h5")

    resolved = _resolve_inputs([str(d)], recursive=False)
    assert [p.source_path for p in resolved] == [d.joinpath("root.h5").resolve()]


def test_resolve_inputs_directory_recursive(tmp_path: Path) -> None:
    d = tmp_path / "d"
    _touch_h5(d / "root.h5")
    _touch_h5(d / "sub" / "nested.h5")

    resolved = _resolve_inputs([str(d)], recursive=True)
    assert [p.source_path for p in resolved] == [
        d.joinpath("root.h5").resolve(),
        (d / "sub" / "nested.h5").resolve(),
    ]


def test_resolve_inputs_directory_extension_is_case_insensitive(tmp_path: Path) -> None:
    d = tmp_path / "d"
    _touch_h5(d / "upper.H5")
    _touch_h5(d / "lower.hdf5")

    resolved = _resolve_inputs([str(d)], recursive=False)
    assert {p.source_path.name for p in resolved} == {"upper.H5", "lower.hdf5"}


def test_resolve_inputs_empty_total_set_errors(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    with pytest.raises(PeakDistanceBatchPlanningError, match="No H5 recordings were found"):
        _resolve_inputs([str(empty)], recursive=False)


def test_resolve_inputs_rejects_duplicate_resolved_inputs(tmp_path: Path) -> None:
    shared = tmp_path / "shared.h5"
    _touch_h5(shared)
    d = tmp_path / "dir"
    d.mkdir()
    shared2 = d / "shared.h5"
    _touch_h5(shared2)

    # Same source file resolved twice via explicit file and a glob/dir that resolves it again.
    with pytest.raises(PeakDistanceBatchPlanningError, match="Duplicate resolved input file"):
        _resolve_inputs([str(shared), str(shared)], recursive=False)

    with pytest.raises(PeakDistanceBatchPlanningError, match="Duplicate resolved input file"):
        _resolve_inputs([str(shared), str(tmp_path)], recursive=False)


def test_plan_batch_exports_default_output_paths(tmp_path: Path) -> None:
    src1 = tmp_path / "dir1" / "a.h5"
    src2 = tmp_path / "dir2" / "b.hdf5"
    _touch_h5(src1)
    _touch_h5(src2)

    resolved = _resolve_inputs([str(src1), str(src2)], recursive=False)
    planned = _plan_batch_exports(
        resolved_inputs=resolved,
        export_format="json",
        output=None,
        output_dir=None,
    )

    assert [p.output_path for p in planned] == [
        _default_output_path(src1.resolve(), "json").resolve(strict=False),
        _default_output_path(src2.resolve(), "json").resolve(strict=False),
    ]


def test_plan_batch_exports_output_dir_json_and_csv(tmp_path: Path) -> None:
    src1 = tmp_path / "a.h5"
    src2 = tmp_path / "b.hdf5"
    _touch_h5(src1)
    _touch_h5(src2)

    resolved = _resolve_inputs([str(src1), str(src2)], recursive=False)

    out = tmp_path / "out"
    planned_json = _plan_batch_exports(
        resolved_inputs=resolved,
        export_format="json",
        output=None,
        output_dir=out,
    )
    assert [p.output_path.name for p in planned_json] == [
        "a_peak_distances.json",
        "b_peak_distances.json",
    ]

    planned_csv = _plan_batch_exports(
        resolved_inputs=resolved,
        export_format="csv",
        output=None,
        output_dir=out,
    )
    assert [p.output_path.name for p in planned_csv] == [
        "a_peak_distances.csv",
        "b_peak_distances.csv",
    ]


def test_plan_batch_exports_rejects_output_with_multiple_inputs(tmp_path: Path) -> None:
    src1 = tmp_path / "a.h5"
    src2 = tmp_path / "b.h5"
    _touch_h5(src1)
    _touch_h5(src2)

    resolved = _resolve_inputs([str(src1), str(src2)], recursive=False)

    with pytest.raises(
        PeakDistanceBatchPlanningError, match="--output is only valid for exactly one"
    ):
        _plan_batch_exports(
            resolved_inputs=resolved,
            export_format="json",
            output=tmp_path / "out.json",
            output_dir=None,
        )


def test_plan_batch_exports_rejects_output_path_collisions(tmp_path: Path) -> None:
    # Two sources with the same stem collide under --output-dir.
    d1 = tmp_path / "d1"
    d2 = tmp_path / "d2"
    _touch_h5(d1 / "file.h5")
    _touch_h5(d2 / "file.h5")

    resolved = _resolve_inputs([str(d1), str(d2)], recursive=False)
    with pytest.raises(PeakDistanceBatchPlanningError, match="Output path collision"):
        _plan_batch_exports(
            resolved_inputs=resolved,
            export_format="json",
            output=None,
            output_dir=tmp_path / "out",
        )


def test_plan_batch_exports_rejects_output_dir_that_is_file(tmp_path: Path) -> None:
    src = tmp_path / "a.h5"
    _touch_h5(src)
    output_dir = tmp_path / "out"
    output_dir.write_text("not a directory", encoding="utf-8")

    resolved = _resolve_inputs([str(src)], recursive=False)
    with pytest.raises(PeakDistanceBatchPlanningError, match="not a directory"):
        _plan_batch_exports(
            resolved_inputs=resolved,
            export_format="json",
            output=None,
            output_dir=output_dir,
        )


def test_plan_batch_exports_rejects_existing_output_files(tmp_path: Path) -> None:
    src = tmp_path / "a.h5"
    _touch_h5(src)

    existing_output = _default_output_path(src.resolve(), "json")
    existing_output.write_text("already exists", encoding="utf-8")

    resolved = _resolve_inputs([str(src)], recursive=False)
    with pytest.raises(PeakDistanceBatchPlanningError, match="Output file already exists"):
        _plan_batch_exports(
            resolved_inputs=resolved,
            export_format="json",
            output=None,
            output_dir=None,
        )


def test_single_file_output_dir_naming_is_compatible(tmp_path: Path) -> None:
    src = tmp_path / "a.h5"
    _touch_h5(src)

    resolved = _resolve_inputs([str(src)], recursive=False)
    out = tmp_path / "out"
    planned = _plan_batch_exports(
        resolved_inputs=resolved,
        export_format="csv",
        output=None,
        output_dir=out,
    )

    assert planned[0].output_path == (out / "a_peak_distances.csv").resolve(strict=False)


def test_single_file_output_option_is_used_as_is(tmp_path: Path) -> None:
    src = tmp_path / "a.h5"
    _touch_h5(src)

    resolved = _resolve_inputs([str(src)], recursive=False)
    out_path = tmp_path / "custom_peaks.json"
    planned = _plan_batch_exports(
        resolved_inputs=resolved,
        export_format="json",
        output=out_path,
        output_dir=None,
    )

    assert planned[0].output_path == out_path.resolve(strict=False)


@dataclass(frozen=True)
class _FakeMeasurement:
    status: str


@dataclass(frozen=True)
class _FakeResult:
    measurements: tuple[_FakeMeasurement, ...]


def test_single_file_execution_keeps_legacy_success_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    src = tmp_path / "single.h5"
    _touch_h5(src)

    monkeypatch.setattr(
        "export_sparse_iq_peak_distances.resolve_selection_indices",
        lambda **_: (0, 0, 0, 0),
    )
    monkeypatch.setattr(
        "export_sparse_iq_peak_distances.export_peak_distances",
        lambda config: _FakeResult(measurements=(_FakeMeasurement(status="detected"),)),
    )

    def fake_write_peak_distance_json(result, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "export_sparse_iq_peak_distances.write_peak_distance_json",
        fake_write_peak_distance_json,
    )

    import export_sparse_iq_peak_distances as cli  # noqa: E402

    monkeypatch.setattr(sys, "argv", ["prog", str(src)])

    cli.main()

    captured = capsys.readouterr()
    assert (
        f"Wrote {_default_output_path(src.resolve(), 'json').resolve(strict=False)}"
        in captured.out
    )
    assert "source:" not in captured.out
    assert "Batch summary" not in captured.out


def test_batch_execution_continues_after_failure_and_summarizes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # This test exercises the batch loop without requiring real H5 files.
    src_ok = tmp_path / "ok.h5"
    src_fail = tmp_path / "fail.h5"
    _touch_h5(src_ok)
    _touch_h5(src_fail)

    # Prevent reading H5 structures.
    monkeypatch.setattr(
        "export_sparse_iq_peak_distances.resolve_selection_indices",
        lambda **_: (0, 0, 0, 0),
    )

    def fake_export_peak_distances(config) -> _FakeResult:
        if str(config.h5_path) == str(src_fail.resolve()):
            msg = "boom"
            raise ValueError(msg)
        return _FakeResult(
            measurements=(
                _FakeMeasurement(status="detected"),
                _FakeMeasurement(status="no_detection"),
            ),
        )

    monkeypatch.setattr(
        "export_sparse_iq_peak_distances.export_peak_distances",
        fake_export_peak_distances,
    )

    def fake_write_peak_distance_json(result, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "export_sparse_iq_peak_distances.write_peak_distance_json",
        fake_write_peak_distance_json,
    )

    # Run the CLI main entrypoint for both inputs; expect nonzero due to failure.
    import export_sparse_iq_peak_distances as cli  # noqa: E402

    argv = [
        "prog",
        str(src_fail),
        str(src_ok),
        "--format",
        "json",
        "--output-dir",
        str(tmp_path / "out"),
    ]
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1

    captured = capsys.readouterr()
    assert "Failed exporting peak distances" in captured.err
    assert "Wrote" in captured.out
    assert (tmp_path / "out" / "ok_peak_distances.json").exists()
