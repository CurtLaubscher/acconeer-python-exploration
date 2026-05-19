"""Export zero-velocity peak-distance measurements from an Acconeer H5 log.

Launch through the repo-managed Hatch app environment:

    hatch run app:peak-distances INPUT.h5
    hatch run app:peak-distances INPUT.h5 --format csv -o peaks.csv
"""

from __future__ import annotations

import argparse
import sys
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export thresholded zero-velocity peak-distance measurements from a Sparse IQ H5 log."
        )
    )
    parser.add_argument("input", type=Path, help="Input .h5 recording")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output path. Defaults to INPUT_STEM_peak_distances.json or .csv",
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

    export_format: Literal["json", "csv"] = args.format
    output = args.output or _default_output_path(args.input, export_format)
    session_idx, group_idx, entry_idx, subsweep_idx = resolve_selection_indices(
        h5_path=args.input,
        session_idx=args.session,
        group_idx=args.group,
        entry_idx=args.entry,
        subsweep_idx=args.subsweep,
    )

    try:
        result = export_peak_distances(
            PeakDistanceExportConfig(
                h5_path=args.input,
                session_idx=session_idx,
                group_idx=group_idx,
                entry_idx=entry_idx,
                subsweep_idx=subsweep_idx,
                threshold=args.threshold,
                every_n=max(args.every_n, 1),
                max_frames=args.max_frames,
            )
        )
        if export_format == "json":
            write_peak_distance_json(result, output)
        else:
            write_peak_distance_csv(result, output)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    detected = sum(1 for row in result.measurements if row.status == "detected")
    print(f"Wrote {output}")
    print(
        f"Format: {export_format}; frames: {len(result.measurements)}; "
        f"detected peaks: {detected}; threshold: {args.threshold:g}"
    )


if __name__ == "__main__":
    main()
