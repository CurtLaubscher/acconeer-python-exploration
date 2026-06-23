"""Plot peak strength and full distance profiles from a Sparse IQ H5 recording."""

from __future__ import annotations

import argparse
from pathlib import Path

import h5py
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm
from matplotlib.ticker import ScalarFormatter

from acconeer.exptool import a121
from acconeer.exptool.a121 import algo


DEFAULT_H5_PATH = Path(r"L:\Member Folders\Curt Laubscher\Data\260616 radar\cha_cha_slide.h5")
DEFAULT_START_S = 442.0
DEFAULT_STOP_S = 483.4
DEFAULT_STRENGTH_MIN = 200.0
DEFAULT_STRENGTH_MAX = 2000.0
DEFAULT_THRESHOLD = 650.0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot peak and time-distance strength views from a Sparse IQ recording."
    )
    parser.add_argument("h5_path", nargs="?", type=Path, default=DEFAULT_H5_PATH)
    parser.add_argument(
        "--start", type=float, default=DEFAULT_START_S, help="Start time in seconds."
    )
    parser.add_argument("--stop", type=float, default=DEFAULT_STOP_S, help="Stop time in seconds.")
    parser.add_argument("--session", type=int, default=0)
    parser.add_argument("--group", type=int, default=0)
    parser.add_argument("--entry", type=int, default=0)
    parser.add_argument("--subsweep", type=int, default=0)
    parser.add_argument("--strength-min", type=float, default=DEFAULT_STRENGTH_MIN)
    parser.add_argument("--strength-max", type=float, default=DEFAULT_STRENGTH_MAX)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument(
        "--output",
        type=Path,
        help="Output PNG path. Defaults to <recording-stem>_strength_analysis.png.",
    )
    parser.add_argument("--show", action="store_true", help="Show the figure after saving it.")
    return parser.parse_args()


def _load_profile_slice(
    h5_path: Path,
    *,
    session_idx: int,
    group_idx: int,
    entry_idx: int,
    subsweep_idx: int,
    start_s: float,
    stop_s: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return times, distances, and sum-over-velocity profiles for one time slice."""
    record = a121.open_record(h5_path)
    try:
        session = record.session(session_idx)
        sensor_items = list(session.session_config.groups[group_idx].items())
        sensor_id, sensor_config = sensor_items[entry_idx]
        metadata = session.extended_metadata[group_idx][sensor_id]
        subsweep = sensor_config.subsweeps[subsweep_idx]
        ticks_per_second = record.server_info.ticks_per_second
    finally:
        record.close()

    result_path = f"sessions/session_{session_idx}/group_{group_idx}/entry_{entry_idx}/result"
    with h5py.File(h5_path, "r") as h5_file:
        result_group = h5_file[result_path]
        ticks = result_group["tick"][:]
        elapsed_s = (ticks - ticks[0]) / ticks_per_second
        first_frame = int(np.searchsorted(elapsed_s, start_s, side="right"))
        stop_frame = int(np.searchsorted(elapsed_s, stop_s, side="right"))
        if first_frame >= stop_frame:
            msg = f"No frames found in the interval {start_s} < time <= {stop_s}."
            raise ValueError(msg)

        offset = int(metadata.subsweep_data_offset[subsweep_idx])
        length = int(metadata.subsweep_data_length[subsweep_idx])
        raw_frames = result_group["frame"][
            first_frame:stop_frame,
            :,
            offset : offset + length,
        ]

    frames = raw_frames["real"].astype(np.float64) + 1j * raw_frames["imag"].astype(np.float64)
    sweep_window = np.hanning(frames.shape[1])[np.newaxis, :, np.newaxis]
    velocity_spectrum = np.fft.fftshift(
        np.fft.fft(frames * sweep_window, axis=1),
        axes=(1,),
    )
    profiles = np.sum(np.abs(velocity_spectrum), axis=1)
    distances_m = algo.get_distances_m(subsweep, metadata)
    return elapsed_s[first_frame:stop_frame], distances_m, profiles


def _format_plain_log_colorbar(colorbar: object, ticks: list[float]) -> None:
    colorbar.set_ticks(ticks)  # type: ignore[attr-defined]
    colorbar.ax.yaxis.set_major_formatter(ScalarFormatter())  # type: ignore[attr-defined]
    colorbar.ax.minorticks_off()  # type: ignore[attr-defined]


def create_figure(
    time_s: np.ndarray,
    distances_m: np.ndarray,
    profiles: np.ndarray,
    *,
    start_s: float,
    stop_s: float,
    threshold: float,
    strength_min: float,
    strength_max: float,
    recording_name: str,
) -> plt.Figure:
    peak_bin = np.argmax(profiles, axis=1)
    peak_strength = profiles[np.arange(len(profiles)), peak_bin]
    peak_distance_m = distances_m[peak_bin]

    shared_norm = LogNorm(vmin=strength_min, vmax=strength_max, clip=True)
    candidate_ticks = [200, 300, 400, 500, 650, 800, 1000, 1500, 2000, 2500]
    strength_ticks = [tick for tick in candidate_ticks if strength_min <= tick <= strength_max]

    figure = plt.figure(figsize=(12, 13), constrained_layout=True)
    grid = figure.add_gridspec(4, 1, height_ratios=[1.05, 1, 1, 1.15])

    strength_distance_ax = figure.add_subplot(grid[0])
    strength_distance_points = strength_distance_ax.scatter(
        peak_distance_m,
        peak_strength,
        c=time_s,
        s=5,
        alpha=0.5,
        cmap="viridis",
        linewidths=0,
        rasterized=True,
    )
    strength_distance_ax.axhline(
        threshold,
        color="tab:red",
        linestyle="--",
        linewidth=1,
        alpha=0.75,
        label=f"Peak threshold ({threshold:g})",
    )
    strength_distance_ax.set(
        xlabel="Peak distance (m)",
        ylabel="Peak strength",
        title="Peak strength vs. peak distance",
    )
    strength_distance_ax.grid(alpha=0.2)
    strength_distance_ax.legend(loc="upper right", fontsize=8)
    time_colorbar = figure.colorbar(strength_distance_points, ax=strength_distance_ax, pad=0.01)
    time_colorbar.set_label("Elapsed time (s)")

    distance_time_ax = figure.add_subplot(grid[1])
    distance_time_points = distance_time_ax.scatter(
        time_s,
        peak_distance_m,
        c=peak_strength,
        norm=shared_norm,
        s=5,
        alpha=0.65,
        cmap="plasma",
        linewidths=0,
        rasterized=True,
    )
    distance_time_ax.set(
        xlabel="Elapsed time (s)",
        ylabel="Peak distance (m)",
        title="Maximum-distance-bin time series",
    )
    distance_time_ax.grid(alpha=0.2)
    peak_colorbar = figure.colorbar(
        distance_time_points,
        ax=distance_time_ax,
        pad=0.01,
        extend="both",
    )
    peak_colorbar.set_label("Peak strength (log color scale)")
    _format_plain_log_colorbar(peak_colorbar, strength_ticks)

    strength_time_ax = figure.add_subplot(grid[2], sharex=distance_time_ax)
    strength_time_points = strength_time_ax.scatter(
        time_s,
        peak_strength,
        c=peak_distance_m,
        s=5,
        alpha=0.6,
        cmap="viridis",
        linewidths=0,
        rasterized=True,
    )
    strength_time_ax.axhline(
        threshold,
        color="tab:red",
        linestyle="--",
        linewidth=1,
        alpha=0.75,
    )
    strength_time_ax.set(
        xlabel="Elapsed time (s)",
        ylabel="Peak strength",
        title="Maximum strength time series",
    )
    strength_time_ax.grid(alpha=0.2)
    distance_colorbar = figure.colorbar(strength_time_points, ax=strength_time_ax, pad=0.01)
    distance_colorbar.set_label("Peak distance (m)")

    heatmap_ax = figure.add_subplot(grid[3], sharex=distance_time_ax)
    heatmap = heatmap_ax.pcolormesh(
        time_s,
        distances_m,
        profiles.T,
        shading="auto",
        cmap="plasma",
        norm=shared_norm,
        rasterized=True,
    )
    heatmap_ax.set(
        xlabel="Elapsed time (s)",
        ylabel="Distance (m)",
        title="Full distance profile over time",
    )
    heatmap_colorbar = figure.colorbar(heatmap, ax=heatmap_ax, pad=0.01, extend="both")
    heatmap_colorbar.set_label("Strength (log color scale)")
    _format_plain_log_colorbar(heatmap_colorbar, strength_ticks)

    figure.suptitle(
        f"{recording_name} — raw sum-v strength, {start_s:g} < t <= {stop_s:g} s",
        fontsize=14,
    )
    return figure


def main() -> None:
    args = _parse_args()
    if args.start >= args.stop:
        msg = "--start must be less than --stop."
        raise ValueError(msg)
    if args.strength_min <= 0 or args.strength_min >= args.strength_max:
        msg = "Strength limits must satisfy 0 < --strength-min < --strength-max."
        raise ValueError(msg)

    time_s, distances_m, profiles = _load_profile_slice(
        args.h5_path,
        session_idx=args.session,
        group_idx=args.group,
        entry_idx=args.entry,
        subsweep_idx=args.subsweep,
        start_s=args.start,
        stop_s=args.stop,
    )
    figure = create_figure(
        time_s,
        distances_m,
        profiles,
        start_s=args.start,
        stop_s=args.stop,
        threshold=args.threshold,
        strength_min=args.strength_min,
        strength_max=args.strength_max,
        recording_name=args.h5_path.name,
    )

    output_path = args.output or Path(f"{args.h5_path.stem}_strength_analysis.png")
    figure.savefig(output_path, dpi=180)
    print(f"Saved {output_path.resolve()}")
    if args.show:
        plt.show()
    else:
        plt.close(figure)


if __name__ == "__main__":
    main()
