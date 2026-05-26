"""Export zero-velocity peak-distance measurements from an Acconeer H5 log.

Launch through the repo-managed Hatch app environment:

    hatch run app:peak-distances INPUT.h5
    hatch run app:peak-distances INPUT.h5 --format csv -o peaks.csv
    hatch run app:peak-distances INPUT1.h5 INPUT2.h5
    hatch run app:peak-distances --output-dir out --format json ./recordings/
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from glob import glob as glob_matches
from pathlib import Path
from typing import Literal

from sparse_iq_heatmap_common import resolve_selection_indices
from sparse_iq_peak_distance_core import (
    DEFAULT_PEAK_THRESHOLD,
    PeakDistanceExportConfig,
    export_peak_distances,
    write_peak_distance_csv,
    write_peak_distance_json,
)


def _default_output_path(input_path: Path, export_format: str) -> Path:
    suffix = ".json" if export_format == "json" else ".csv"
    return input_path.with_name(f"{input_path.stem}_peak_distances{suffix}")


H5_EXTENSIONS = {".h5", ".hdf5"}


def _is_h5_file(path: Path) -> bool:
    return path.suffix.lower() in H5_EXTENSIONS


@dataclass(frozen=True)
class ResolvedPeakDistanceInput:
    source_path: Path  # resolved absolute path


@dataclass(frozen=True)
class PlannedPeakDistanceExport:
    source_path: Path  # resolved absolute path
    output_path: Path  # absolute path


class PeakDistanceBatchPlanningError(ValueError):
    pass


def _discover_h5_files_in_directory(dir_path: Path, *, recursive: bool) -> list[Path]:
    if recursive:
        candidates = (p for p in dir_path.rglob("*") if p.is_file())
    else:
        candidates = (p for p in dir_path.iterdir() if p.is_file())

    return sorted(
        (p for p in candidates if _is_h5_file(p)),
        key=lambda p: str(p.resolve()),
    )


def _expand_glob_pattern(pattern: str) -> list[Path]:
    # Keep glob expansion predictable by sorting by resolved absolute path.
    # We still filter to H5 extensions case-insensitively.
    matches = (Path(p) for p in glob_matches(pattern, recursive=True))
    h5_matches = [p for p in matches if p.exists() and p.is_file() and _is_h5_file(p)]
    return sorted(h5_matches, key=lambda p: str(p.resolve()))


def _looks_like_glob(pattern: str) -> bool:
    return any(ch in pattern for ch in ("*", "?", "[")) or ("**" in pattern)


def _resolve_inputs(
    raw_inputs: list[str],
    *,
    recursive: bool,
) -> list[ResolvedPeakDistanceInput]:
    resolved_paths: list[Path] = []
    for raw in raw_inputs:
        if _looks_like_glob(raw):
            expanded = _expand_glob_pattern(raw)
            resolved_paths.extend(expanded)
            continue

        path = Path(raw)
        if path.is_dir():
            discovered = _discover_h5_files_in_directory(path, recursive=recursive)
            resolved_paths.extend(discovered)
            continue

        if path.is_file():
            if not _is_h5_file(path):
                msg = f"Input file is not a supported H5 recording: {path}"
                raise PeakDistanceBatchPlanningError(msg)
            resolved_paths.append(path.resolve())
            continue

        msg = f"Input path does not exist: {path}"
        raise PeakDistanceBatchPlanningError(msg)

    # Normalize order for deterministic batch execution.
    resolved_paths = sorted((p.resolve() for p in resolved_paths), key=lambda p: str(p))

    # Reject duplicates based on resolved absolute path.
    unique: list[Path] = []
    seen: set[Path] = set()
    for p in resolved_paths:
        if p in seen:
            msg = f"Duplicate resolved input file: {p}"
            raise PeakDistanceBatchPlanningError(msg)
        seen.add(p)
        unique.append(p)

    if not unique:
        msg = "No H5 recordings were found for the provided inputs."
        raise PeakDistanceBatchPlanningError(msg)

    return [ResolvedPeakDistanceInput(source_path=p) for p in unique]


def _plan_batch_exports(
    *,
    resolved_inputs: list[ResolvedPeakDistanceInput],
    export_format: Literal["json", "csv"],
    output: Path | None,
    output_dir: Path | None,
) -> list[PlannedPeakDistanceExport]:
    if output is not None and output_dir is not None:
        msg = "Use only one of --output and --output-dir."
        raise PeakDistanceBatchPlanningError(msg)

    # `--output` stays valid only for a single resolved input.
    if output is not None and len(resolved_inputs) != 1:
        msg = "--output is only valid for exactly one input."
        raise PeakDistanceBatchPlanningError(msg)

    if output_dir is not None and output_dir.exists() and not output_dir.is_dir():
        msg = f"Output directory path exists and is not a directory: {output_dir}"
        raise PeakDistanceBatchPlanningError(msg)

    suffix = "json" if export_format == "json" else "csv"
    planned: list[PlannedPeakDistanceExport] = []
    output_paths_by_abs: dict[Path, list[Path]] = {}

    def add_job(source: Path, planned_output: Path) -> None:
        abs_output = planned_output.resolve(strict=False)
        output_paths_by_abs.setdefault(abs_output, []).append(source)
        planned.append(PlannedPeakDistanceExport(source_path=source, output_path=abs_output))

    for item in resolved_inputs:
        source = item.source_path
        if output is not None:
            add_job(source, output)
            continue

        if output_dir is not None:
            planned_output = output_dir / f"{source.stem}_peak_distances.{suffix}"
            add_job(source, planned_output)
        else:
            add_job(source, _default_output_path(source, export_format))

    collisions = {out: srcs for out, srcs in output_paths_by_abs.items() if len(srcs) > 1}
    if collisions:
        out_path = next(iter(collisions.keys()))
        srcs = collisions[out_path]
        srcs_str = ", ".join(str(p) for p in srcs)
        msg = f"Output path collision: {out_path} (from sources: {srcs_str})"
        raise PeakDistanceBatchPlanningError(msg)

    for job in planned:
        if job.output_path.exists():
            msg = f"Output file already exists: {job.output_path}"
            raise PeakDistanceBatchPlanningError(msg)

    return planned


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export thresholded zero-velocity peak-distance measurements from Sparse IQ H5 logs."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=str,
        help="One or more input recordings: explicit H5 files, glob patterns, or directories.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output path for a single resolved input. Defaults to INPUT_STEM_peak_distances.json or .csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Write batch outputs to a directory using <input_stem>_peak_distances.<format> naming.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Enable recursive discovery of .h5 and .hdf5 files for directory inputs.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "csv"),
        default="json",
        help="Export format. Defaults to canonical JSON.",
    )
    parser.add_argument(
        "--session",
        type=int,
        default=None,
        help="Session index. Defaults to 0, with a warning if multiple sessions exist.",
    )
    parser.add_argument(
        "--group",
        type=int,
        default=None,
        help="Group index within the selected session. Defaults to 0 if omitted.",
    )
    parser.add_argument(
        "--entry",
        type=int,
        default=None,
        help="Entry index within the selected group. Defaults to 0 if omitted.",
    )
    parser.add_argument(
        "--subsweep",
        type=int,
        default=None,
        help="Zero-based subsweep index. Defaults to 0 if omitted.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_PEAK_THRESHOLD,
        help=f"Peak strength threshold. Defaults to {DEFAULT_PEAK_THRESHOLD:g}.",
    )
    parser.add_argument("--max-frames", type=int, default=None, help="Limit exported frames")
    parser.add_argument("--every-n", type=int, default=1, help="Export every Nth frame")
    args = parser.parse_args()

    try:
        export_format: Literal["json", "csv"] = args.format
        resolved_inputs = _resolve_inputs(args.inputs, recursive=args.recursive)
        planned_jobs = _plan_batch_exports(
            resolved_inputs=resolved_inputs,
            export_format=export_format,
            output=args.output,
            output_dir=args.output_dir,
        )
    except PeakDistanceBatchPlanningError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    is_batch = len(planned_jobs) > 1
    succeeded = 0
    failed = 0
    for job in planned_jobs:
        try:
            session_idx, group_idx, entry_idx, subsweep_idx = resolve_selection_indices(
                h5_path=job.source_path,
                session_idx=args.session,
                group_idx=args.group,
                entry_idx=args.entry,
                subsweep_idx=args.subsweep,
            )
            config = PeakDistanceExportConfig(
                h5_path=job.source_path,
                session_idx=session_idx,
                group_idx=group_idx,
                entry_idx=entry_idx,
                subsweep_idx=subsweep_idx,
                threshold=args.threshold,
                every_n=max(args.every_n, 1),
                max_frames=args.max_frames,
            )
            result = export_peak_distances(config)
            if export_format == "json":
                write_peak_distance_json(result, job.output_path)
            else:
                write_peak_distance_csv(result, job.output_path)

            detected = sum(1 for row in result.measurements if row.status == "detected")
            succeeded += 1
            if is_batch:
                print(f"Wrote {job.output_path} (source: {job.source_path})")
            else:
                print(f"Wrote {job.output_path}")
            print(
                f"Format: {export_format}; frames: {len(result.measurements)}; "
                f"detected peaks: {detected}; threshold: {args.threshold:g}"
            )
        except (OSError, ValueError) as exc:
            failed += 1
            if is_batch:
                print(
                    f"Failed exporting peak distances for {job.source_path} "
                    f"-> {job.output_path}: {exc}",
                    file=sys.stderr,
                )
            else:
                print(str(exc), file=sys.stderr)

    if is_batch:
        print(f"Batch summary: {succeeded} succeeded; {failed} failed")
    if failed > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
