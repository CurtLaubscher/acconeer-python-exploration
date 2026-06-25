"""Plot peak strength and full distance profiles from a Sparse IQ H5 recording."""

# The h5py and Matplotlib packages expose incomplete typing at their dynamic API boundaries.
# Keep strict checks on this script's typed arrays and functions without reporting stub noise.
# pyright: reportAny=false, reportMissingTypeStubs=false, reportPrivateImportUsage=false
# pyright: reportPrivateLocalImportUsage=false
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnusedCallResult=false

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import h5py
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from matplotlib.colorbar import Colorbar
from matplotlib.colors import ListedColormap, LogNorm
from matplotlib.figure import Figure
from matplotlib.ticker import ScalarFormatter

from acconeer.exptool import a121
from acconeer.exptool.a121 import algo


DEFAULT_H5_PATH = Path(r"L:\Member Folders\Curt Laubscher\Data\260616 radar\cha_cha_slide.h5")
DEFAULT_START_S = 442.0
DEFAULT_STOP_S = 483.4

# Set this to False to plot the original, unnormalized strength values.
PLOT_NORMALIZED_VALUES = True

RAW_STRENGTH_MIN = 10.0
RAW_STRENGTH_MAX = 2400.0
RAW_THRESHOLD = 750.0
NORMALIZED_STRENGTH_MIN = 0.1
NORMALIZED_STRENGTH_MAX = 3.0
NORMALIZED_THRESHOLD = 1.0

DEFAULT_STRENGTH_MIN = NORMALIZED_STRENGTH_MIN if PLOT_NORMALIZED_VALUES else RAW_STRENGTH_MIN
DEFAULT_STRENGTH_MAX = NORMALIZED_STRENGTH_MAX if PLOT_NORMALIZED_VALUES else RAW_STRENGTH_MAX
DEFAULT_THRESHOLD = NORMALIZED_THRESHOLD if PLOT_NORMALIZED_VALUES else RAW_THRESHOLD

NORMALIZATION_THRESHOLD_MAX = 1250.0
NORMALIZATION_THRESHOLD_MIN = 300.0
NORMALIZATION_THRESHOLD_DISTANCE_M = 0.700

BELOW_THRESHOLD_COLORMAP = "managua"
ABOVE_THRESHOLD_COLORMAP = "YlOrRd_r"
MINIMUM_LIGHTNESS = 15.0
BELOW_THRESHOLD_LIGHTNESS = 65.0
ABOVE_THRESHOLD_LIGHTNESS = 75.0
MAXIMUM_LIGHTNESS = 95.0

FloatArray = npt.NDArray[np.float64]


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
) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray]:
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
        if not isinstance(result_group, h5py.Group):
            msg = f"Expected {result_path} to be an HDF5 group."
            raise TypeError(msg)

        tick_dataset = result_group["tick"]
        frame_dataset = result_group["frame"]
        if not isinstance(tick_dataset, h5py.Dataset) or not isinstance(
            frame_dataset, h5py.Dataset
        ):
            msg = f"Expected tick and frame datasets under {result_path}."
            raise TypeError(msg)

        ticks = np.asarray(tick_dataset[:], dtype=np.int64)
        elapsed_s = (ticks - ticks[0]) / ticks_per_second
        first_frame = int(np.searchsorted(elapsed_s, start_s, side="right"))
        stop_frame = int(np.searchsorted(elapsed_s, stop_s, side="right"))
        if first_frame >= stop_frame:
            msg = f"No frames found in the interval {start_s} < time <= {stop_s}."
            raise ValueError(msg)

        offset = int(metadata.subsweep_data_offset[subsweep_idx])
        length = int(metadata.subsweep_data_length[subsweep_idx])
        raw_frames = np.asarray(
            frame_dataset[
                first_frame:stop_frame,
                :,
                offset : offset + length,
            ]
        )

    real_frames = np.asarray(raw_frames["real"], dtype=np.float64)
    imaginary_frames = np.asarray(raw_frames["imag"], dtype=np.float64)
    frames = real_frames + 1j * imaginary_frames
    sweep_window = np.hanning(frames.shape[1])[np.newaxis, :, np.newaxis]
    velocity_spectrum = np.fft.fftshift(
        np.fft.fft(frames * sweep_window, axis=1),
        axes=(1,),
    )
    profiles = np.asarray(np.sum(np.abs(velocity_spectrum), axis=1), dtype=np.float64)
    distances_m = np.asarray(algo.get_distances_m(subsweep, metadata), dtype=np.float64)
    normalization_threshold = np.maximum(
        NORMALIZATION_THRESHOLD_MAX * (1.0 - distances_m / NORMALIZATION_THRESHOLD_DISTANCE_M),
        NORMALIZATION_THRESHOLD_MIN,
    )
    profiles_normalized = profiles / normalization_threshold
    selected_times = np.asarray(elapsed_s[first_frame:stop_frame], dtype=np.float64)
    return selected_times, distances_m, profiles, profiles_normalized


def _format_plain_log_colorbar(colorbar: Colorbar, ticks: Sequence[float]) -> None:
    colorbar.set_ticks(ticks)
    colorbar.ax.yaxis.set_major_formatter(ScalarFormatter())
    colorbar.ax.minorticks_off()


def _cie_lightness(rgb: FloatArray) -> FloatArray:
    """Return perceptual CIE L* for sRGB colors in the range 0 to 1."""
    linear_rgb = np.where(
        rgb <= 0.04045,
        rgb / 12.92,
        ((rgb + 0.055) / 1.055) ** 2.4,
    )
    relative_luminance = linear_rgb @ np.array([0.2126, 0.7152, 0.0722])
    delta = 6.0 / 29.0
    lightness = (
        116.0
        * np.where(
            relative_luminance > delta**3,
            np.cbrt(relative_luminance),
            relative_luminance / (3.0 * delta**2) + 4.0 / 29.0,
        )
        - 16.0
    )
    return np.asarray(lightness, dtype=np.float64)


def _sample_colormap_by_lightness(
    colormap_name: str,
    *,
    start: float,
    stop: float,
    color_count: int,
    lightness_min: float,
    lightness_max: float,
) -> FloatArray:
    """Sample a monotonic colormap at evenly spaced CIE L* values."""
    colormap = plt.get_cmap(colormap_name)
    source_positions = np.linspace(start, stop, 4096)
    source_colors = np.asarray(colormap(source_positions), dtype=np.float64)
    source_lightness = _cie_lightness(source_colors[:, :3])
    monotonic_lightness = np.maximum.accumulate(source_lightness)
    target_lightness = np.linspace(lightness_min, lightness_max, color_count)
    target_positions = np.interp(
        target_lightness,
        monotonic_lightness,
        source_positions,
    )
    return np.asarray(colormap(target_positions), dtype=np.float64)


def _threshold_split_colormap(
    strength_min: float,
    strength_max: float,
    threshold: float,
) -> ListedColormap:
    """Create cool and warm ramps with rising L* and a threshold jump."""
    norm = LogNorm(vmin=strength_min, vmax=strength_max)
    threshold_position = float(norm(threshold))
    color_count = 512
    lower_count = int(np.clip(round(color_count * threshold_position), 2, color_count - 2))
    upper_count = color_count - lower_count

    below_threshold = _sample_colormap_by_lightness(
        BELOW_THRESHOLD_COLORMAP,
        start=0.5,
        stop=1.0,
        color_count=lower_count,
        lightness_min=MINIMUM_LIGHTNESS,
        lightness_max=BELOW_THRESHOLD_LIGHTNESS,
    )
    above_threshold = _sample_colormap_by_lightness(
        ABOVE_THRESHOLD_COLORMAP,
        start=0.0,
        stop=1.0,
        color_count=upper_count,
        lightness_min=ABOVE_THRESHOLD_LIGHTNESS,
        lightness_max=MAXIMUM_LIGHTNESS,
    )
    colors = np.vstack((below_threshold, above_threshold))
    return ListedColormap(colors, name="threshold_split_perceptual")


def create_figure(
    time_s: FloatArray,
    distances_m: FloatArray,
    profiles: FloatArray,
    *,
    start_s: float,
    stop_s: float,
    threshold: float,
    strength_min: float,
    strength_max: float,
    recording_name: str,
    normalized: bool,
) -> Figure:
    peak_bin = np.argmax(profiles, axis=1)
    peak_strength = profiles[np.arange(len(profiles)), peak_bin]
    peak_distance_m = distances_m[peak_bin]

    shared_norm = LogNorm(vmin=strength_min, vmax=strength_max, clip=True)
    strength_colormap = (
        _threshold_split_colormap(strength_min, strength_max, threshold)
        if normalized
        else "plasma"
    )
    candidate_ticks = (
        [0.1, 0.2, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0]
        if normalized
        else [20.0, 50.0, 100.0, 200.0, 400.0, 750.0, 2000.0, 2500.0]
    )
    strength_ticks = [tick for tick in candidate_ticks if strength_min <= tick <= strength_max]
    strength_label = "Normalized strength" if normalized else "Strength"
    peak_strength_label = f"Peak {strength_label.lower()}"

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
        label=f"{strength_label} threshold ({threshold:g})",
    )
    strength_distance_ax.set(
        xlabel="Peak distance (m)",
        ylabel=peak_strength_label,
        title=f"{peak_strength_label} vs. peak distance",
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
        # vmin=strength_min,
        # vmax=strength_max,
        s=5,
        alpha=0.65,
        cmap=strength_colormap,
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
    peak_colorbar.set_label(peak_strength_label)
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
        ylabel=peak_strength_label,
        title=f"Maximum {strength_label.lower()} time series",
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
        cmap=strength_colormap,
        norm=shared_norm,
        rasterized=True,
    )
    heatmap_ax.set(
        xlabel="Elapsed time (s)",
        ylabel="Distance (m)",
        title="Full distance profile over time",
    )
    heatmap_colorbar = figure.colorbar(heatmap, ax=heatmap_ax, pad=0.01, extend="both")
    heatmap_colorbar.set_label(f"{strength_label} (log color scale)")
    _format_plain_log_colorbar(heatmap_colorbar, strength_ticks)

    figure.suptitle(
        f"{recording_name} — {strength_label.lower()}, {start_s:g} < t <= {stop_s:g} s",
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

    time_s, distances_m, profiles, profiles_normalized = _load_profile_slice(
        args.h5_path,
        session_idx=args.session,
        group_idx=args.group,
        entry_idx=args.entry,
        subsweep_idx=args.subsweep,
        start_s=args.start,
        stop_s=args.stop,
    )
    plotted_profiles = profiles_normalized if PLOT_NORMALIZED_VALUES else profiles
    figure = create_figure(
        time_s,
        distances_m,
        plotted_profiles,
        start_s=args.start,
        stop_s=args.stop,
        threshold=args.threshold,
        strength_min=args.strength_min,
        strength_max=args.strength_max,
        recording_name=args.h5_path.name,
        normalized=PLOT_NORMALIZED_VALUES,
    )

    mode = "normalized_strength" if PLOT_NORMALIZED_VALUES else "strength"
    output_path = args.output or Path(f"{args.h5_path.stem}_{mode}_analysis.png")
    figure.savefig(output_path, dpi=180)
    print(f"Saved {output_path.resolve()}")
    if args.show:
        plt.show()
    else:
        plt.close(figure)


if __name__ == "__main__":
    main()
