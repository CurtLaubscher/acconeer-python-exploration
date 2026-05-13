from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
import numpy as np


matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.animation import FFMpegWriter
from PIL import Image

from acconeer.exptool import a121
from acconeer.exptool.a121 import algo


@dataclass
class _PlotInputs:
    record: a121.Record
    sensor_config: a121.SensorConfig
    metadata: a121.Metadata
    results: list[a121.Result]
    ticks: np.ndarray
    ticks_per_second: int
    fps: float
    sensor_id: int
    record_timestamp: str


@dataclass
class _PreparedPlot:
    title: str
    fig: plt.Figure
    ax: plt.Axes
    image: matplotlib.image.AxesImage
    timestamp_artist: matplotlib.text.Text


def _recording_fps(ticks: np.ndarray, ticks_per_second: int) -> float:
    if len(ticks) < 2:
        return 1.0

    intervals_s = np.diff(ticks) / ticks_per_second
    return float(1.0 / np.mean(intervals_s))


def _timestamp_text(
    timestamp_mode: str,
    record_timestamp: str,
    ticks: np.ndarray,
    ticks_per_second: int,
    frame_idx: int,
) -> str:
    elapsed_s = float((ticks[frame_idx] - ticks[0]) / ticks_per_second)

    if timestamp_mode == "none":
        return ""
    if timestamp_mode == "absolute":
        try:
            absolute_time = datetime.fromisoformat(record_timestamp) + timedelta(seconds=elapsed_s)
            return absolute_time.isoformat(timespec="milliseconds")
        except ValueError:
            return f"{record_timestamp} + {elapsed_s:.3f} s"

    return f"t = {elapsed_s:.3f} s"


def _distance_velocity_map(subframe: np.ndarray) -> np.ndarray:
    hanning_window = np.hanning(subframe.shape[0])[:, np.newaxis]
    z_ft = np.fft.fftshift(np.fft.fft(subframe * hanning_window, axis=0), axes=(0,))
    return np.abs(z_ft)


def _color_max_for_dvm(dvm: np.ndarray) -> float:
    return max(float(1.05 * np.max(dvm)), 1e-12)


def _make_figure(
    first_dvm: np.ndarray,
    distances_m: np.ndarray,
    velocities_m_s: np.ndarray,
    velocity_resolution: float,
    title: str,
    color_min: float,
    color_max: float | None,
) -> tuple[plt.Figure, plt.Axes, matplotlib.image.AxesImage, matplotlib.text.Text]:
    distance_step = np.median(np.diff(distances_m)) if len(distances_m) > 1 else 1.0
    extent = (
        float(distances_m[0] - 0.5 * distance_step),
        float(distances_m[-1] + 0.5 * distance_step),
        float(velocities_m_s[0] - 0.5 * velocity_resolution),
        float(velocities_m_s[-1] + 0.5 * velocity_resolution),
    )

    fig, ax = plt.subplots(figsize=(9, 5), dpi=120)
    image = ax.imshow(
        first_dvm,
        extent=extent,
        origin="lower",
        aspect="auto",
        interpolation="nearest",
        cmap="viridis",
        vmin=color_min,
        vmax=color_max if color_max is not None else max(float(1.05 * np.max(first_dvm)), 1e-12),
    )
    fig.colorbar(image, ax=ax, label="Magnitude")
    ax.set_xlabel("Distance (m)")
    ax.set_ylabel("Velocity (m/s)")
    ax.set_title(title)
    timestamp_artist = ax.text(
        0.02,
        0.96,
        "",
        transform=ax.transAxes,
        va="top",
        ha="left",
        color="white",
        bbox={"facecolor": "black", "alpha": 0.65, "edgecolor": "none", "pad": 4},
    )
    fig.tight_layout()
    return fig, ax, image, timestamp_artist


def _update_frame_plot(
    *,
    frame_idx: int,
    subsweep_idx: int,
    fixed_levels: bool,
    color_min: float,
    title: str,
    results: list[a121.Result],
    image: matplotlib.image.AxesImage,
    ax: plt.Axes,
    timestamp_artist: matplotlib.text.Text,
    timestamp_mode: str,
    record_timestamp: str,
    ticks: np.ndarray,
    ticks_per_second: int,
) -> None:
    dvm = _distance_velocity_map(results[frame_idx].subframes[subsweep_idx])
    image.set_data(dvm)
    if not fixed_levels:
        image.set_clim(color_min, _color_max_for_dvm(dvm))

    ax.set_title(f"{title} - frame {frame_idx + 1}/{len(results)}")
    timestamp_artist.set_text(
        _timestamp_text(
            timestamp_mode,
            record_timestamp,
            ticks,
            ticks_per_second,
            frame_idx,
        )
    )


def _canvas_to_pil(fig: plt.Figure) -> Image.Image:
    fig.canvas.draw()
    width, height = fig.canvas.get_width_height()
    rgba = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8).reshape(height, width, 4)
    return Image.fromarray(rgba[:, :, :3])


def _load_plot_inputs(
    h5_path: Path, session_idx: int, group_idx: int, entry_idx: int
) -> _PlotInputs:
    record = a121.open_record(h5_path)

    try:
        session = record.session(session_idx)
        session_config = session.session_config
        sensor_items = list(session_config.groups[group_idx].items())
        sensor_id, sensor_config = sensor_items[entry_idx]
    except IndexError as exc:
        record.close()
        msg = f"Could not find group {group_idx}, entry {entry_idx} in session {session_idx}."
        raise ValueError(msg) from exc
    except Exception:
        record.close()
        raise

    metadata = session.extended_metadata[group_idx][sensor_id]
    results = [extended_result[group_idx][sensor_id] for extended_result in session.extended_results]
    ticks = np.array([result.tick for result in results], dtype=np.int64)
    ticks_per_second = record.server_info.ticks_per_second
    fps = _recording_fps(ticks, ticks_per_second)
    record_timestamp = record.timestamp

    return _PlotInputs(
        record=record,
        sensor_config=sensor_config,
        metadata=metadata,
        results=results,
        ticks=ticks,
        ticks_per_second=ticks_per_second,
        fps=fps,
        sensor_id=sensor_id,
        record_timestamp=record_timestamp,
    )


def _resolve_index(
    *,
    requested_idx: int | None,
    count: int,
    option_name: str,
    item_name: str,
    parent_description: str,
) -> int:
    if count == 0:
        msg = f"{parent_description} does not contain any {item_name}s."
        raise ValueError(msg)

    if requested_idx is None:
        if count > 1:
            print(
                f"Warning: {parent_description} contains {count} {item_name}s; "
                f"defaulting to --{option_name} 0.",
                file=sys.stderr,
            )
        return 0

    if 0 <= requested_idx < count:
        return requested_idx

    msg = (
        f"{parent_description} does not contain {item_name} {requested_idx}. "
        f"Valid indices are 0 to {count - 1}."
    )
    raise ValueError(msg)


def _resolve_selection_indices(
    *,
    h5_path: Path,
    session_idx: int | None,
    group_idx: int | None,
    entry_idx: int | None,
    subsweep_idx: int | None,
) -> tuple[int, int, int, int]:
    record = a121.open_record(h5_path)

    try:
        resolved_session_idx = _resolve_index(
            requested_idx=session_idx,
            count=record.num_sessions,
            option_name="session",
            item_name="session",
            parent_description="recording",
        )

        session = record.session(resolved_session_idx)
        resolved_group_idx = _resolve_index(
            requested_idx=group_idx,
            count=len(session.session_config.groups),
            option_name="group",
            item_name="group",
            parent_description=f"session {resolved_session_idx}",
        )

        sensor_items = list(session.session_config.groups[resolved_group_idx].items())
        resolved_entry_idx = _resolve_index(
            requested_idx=entry_idx,
            count=len(sensor_items),
            option_name="entry",
            item_name="entry",
            parent_description=f"group {resolved_group_idx} in session {resolved_session_idx}",
        )

        sensor_id, sensor_config = sensor_items[resolved_entry_idx]
        resolved_subsweep_idx = _resolve_index(
            requested_idx=subsweep_idx,
            count=len(sensor_config.subsweeps),
            option_name="subsweep",
            item_name="subsweep",
            parent_description=f"sensor {sensor_id} in group {resolved_group_idx}",
        )
    finally:
        record.close()

    return (
        resolved_session_idx,
        resolved_group_idx,
        resolved_entry_idx,
        resolved_subsweep_idx,
    )


def _select_subsweep(plot_inputs: _PlotInputs, subsweep_idx: int) -> a121.SubsweepConfig:
    if len(plot_inputs.results) == 0:
        msg = "The selected sensor entry does not contain any frames to export."
        raise ValueError(msg)

    try:
        return plot_inputs.sensor_config.subsweeps[subsweep_idx]
    except IndexError as exc:
        msg = f"Could not find subsweep {subsweep_idx} for sensor {plot_inputs.sensor_id}."
        raise ValueError(msg) from exc


def _select_frame_indices(
    results: list[a121.Result], every_n: int, max_frames: int | None
) -> list[int]:
    if max_frames is not None and max_frames < 0:
        msg = f"--max-frames must be non-negative, got {max_frames}."
        raise ValueError(msg)

    frame_indices = list(range(0, len(results), every_n))
    if max_frames is not None:
        frame_indices = frame_indices[:max_frames]

    if len(frame_indices) == 0:
        msg = (
            "No frames were selected for export. Adjust --max-frames or choose a recording "
            "with available frames."
        )
        raise ValueError(msg)

    return frame_indices


def _fixed_color_level(
    *, color_max: float | None, results: list[a121.Result], subsweep_idx: int, frame_indices: list[int]
) -> float:
    if color_max is not None:
        return color_max

    return max(
        _color_max_for_dvm(_distance_velocity_map(results[i].subframes[subsweep_idx]))
        for i in frame_indices
    )


def _prepare_plot(
    *,
    h5_path: Path,
    plot_inputs: _PlotInputs,
    subsweep_idx: int,
    subsweep: a121.SubsweepConfig,
    color_min: float,
    color_max: float | None,
    frame_indices: list[int],
) -> _PreparedPlot:
    distances_m = algo.get_distances_m(subsweep, plot_inputs.metadata)
    velocities_m_s, velocity_resolution = algo.get_approx_fft_vels(
        plot_inputs.metadata, plot_inputs.sensor_config
    )
    first_dvm = _distance_velocity_map(plot_inputs.results[frame_indices[0]].subframes[subsweep_idx])
    title = f"{h5_path.name} - sensor {plot_inputs.sensor_id}, subsweep {subsweep_idx + 1}"
    fig, ax, image, timestamp_artist = _make_figure(
        first_dvm=first_dvm,
        distances_m=distances_m,
        velocities_m_s=velocities_m_s,
        velocity_resolution=velocity_resolution,
        title=title,
        color_min=color_min,
        color_max=color_max,
    )
    return _PreparedPlot(
        title=title,
        fig=fig,
        ax=ax,
        image=image,
        timestamp_artist=timestamp_artist,
    )


def _write_mp4(
    *,
    output_path: Path,
    ffmpeg: Path | None,
    effective_fps: float,
    prepared_plot: _PreparedPlot,
    plot_inputs: _PlotInputs,
    subsweep_idx: int,
    frame_indices: list[int],
    fixed_levels: bool,
    color_min: float,
    timestamp_mode: str,
) -> None:
    ffmpeg_path = _find_ffmpeg(ffmpeg)
    if ffmpeg_path is None:
        msg = "MP4 output requires ffmpeg on PATH. Use .gif or install ffmpeg."
        raise RuntimeError(msg)

    rcParams["animation.ffmpeg_path"] = ffmpeg_path
    writer = FFMpegWriter(fps=effective_fps, metadata={"title": prepared_plot.title})
    with writer.saving(prepared_plot.fig, str(output_path), dpi=120):
        for frame_idx in frame_indices:
            _update_frame_plot(
                frame_idx=frame_idx,
                subsweep_idx=subsweep_idx,
                fixed_levels=fixed_levels,
                color_min=color_min,
                title=prepared_plot.title,
                results=plot_inputs.results,
                image=prepared_plot.image,
                ax=prepared_plot.ax,
                timestamp_artist=prepared_plot.timestamp_artist,
                timestamp_mode=timestamp_mode,
                record_timestamp=plot_inputs.record_timestamp,
                ticks=plot_inputs.ticks,
                ticks_per_second=plot_inputs.ticks_per_second,
            )
            writer.grab_frame()


def _write_gif(
    *,
    output_path: Path,
    effective_fps: float,
    prepared_plot: _PreparedPlot,
    plot_inputs: _PlotInputs,
    subsweep_idx: int,
    frame_indices: list[int],
    fixed_levels: bool,
    color_min: float,
    timestamp_mode: str,
) -> None:
    pil_frames: list[Image.Image] = []
    for frame_idx in frame_indices:
        _update_frame_plot(
            frame_idx=frame_idx,
            subsweep_idx=subsweep_idx,
            fixed_levels=fixed_levels,
            color_min=color_min,
            title=prepared_plot.title,
            results=plot_inputs.results,
            image=prepared_plot.image,
            ax=prepared_plot.ax,
            timestamp_artist=prepared_plot.timestamp_artist,
            timestamp_mode=timestamp_mode,
            record_timestamp=plot_inputs.record_timestamp,
            ticks=plot_inputs.ticks,
            ticks_per_second=plot_inputs.ticks_per_second,
        )
        pil_frames.append(_canvas_to_pil(prepared_plot.fig))

    duration_ms = max(round(1000 / effective_fps), 1)
    pil_frames[0].save(
        output_path,
        save_all=True,
        append_images=pil_frames[1:],
        duration=duration_ms,
        loop=0,
    )


def _resolve_ffmpeg_path(path: Path | None) -> str | None:
    if path is None:
        return None

    if path.is_dir():
        path = path / "ffmpeg.exe"

    return str(path) if path.exists() else None


def _find_ffmpeg(explicit_ffmpeg: Path | None) -> str | None:
    ffmpeg_path = _resolve_ffmpeg_path(explicit_ffmpeg)
    if ffmpeg_path is not None:
        return ffmpeg_path

    env_ffmpeg = os.getenv("FFMPEG_PATH")
    if env_ffmpeg:
        ffmpeg_path = _resolve_ffmpeg_path(Path(env_ffmpeg))
        if ffmpeg_path is not None:
            return ffmpeg_path

    return shutil.which("ffmpeg")


def _apply_theme(theme: str) -> None:
    if theme == "dark":
        plt.style.use("dark_background")
    else:
        plt.style.use("default")


def export_heatmap_video(
    h5_path: Path,
    output_path: Path,
    session_idx: int,
    group_idx: int,
    entry_idx: int,
    subsweep_idx: int,
    max_frames: int | None,
    every_n: int,
    fixed_levels: bool,
    ffmpeg: Path | None,
    color_min: float,
    color_max: float | None,
    timestamp_mode: str,
    theme: str,
) -> None:
    _apply_theme(theme)
    plot_inputs = _load_plot_inputs(h5_path, session_idx, group_idx, entry_idx)

    try:
        subsweep = _select_subsweep(plot_inputs, subsweep_idx)
        frame_indices = _select_frame_indices(plot_inputs.results, every_n, max_frames)
        prepared_plot = _prepare_plot(
            h5_path=h5_path,
            plot_inputs=plot_inputs,
            subsweep_idx=subsweep_idx,
            subsweep=subsweep,
            color_min=color_min,
            color_max=color_max,
            frame_indices=frame_indices,
        )

        if fixed_levels:
            max_level = _fixed_color_level(
                color_max=color_max,
                results=plot_inputs.results,
                subsweep_idx=subsweep_idx,
                frame_indices=frame_indices,
            )
            prepared_plot.image.set_clim(color_min, max_level)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        effective_fps = plot_inputs.fps / every_n

        if output_path.suffix.lower() == ".mp4":
            _write_mp4(
                output_path=output_path,
                ffmpeg=ffmpeg,
                effective_fps=effective_fps,
                prepared_plot=prepared_plot,
                plot_inputs=plot_inputs,
                subsweep_idx=subsweep_idx,
                frame_indices=frame_indices,
                fixed_levels=fixed_levels,
                color_min=color_min,
                timestamp_mode=timestamp_mode,
            )
        else:
            _write_gif(
                output_path=output_path,
                effective_fps=effective_fps,
                prepared_plot=prepared_plot,
                plot_inputs=plot_inputs,
                subsweep_idx=subsweep_idx,
                frame_indices=frame_indices,
                fixed_levels=fixed_levels,
                color_min=color_min,
                timestamp_mode=timestamp_mode,
            )

        print(f"Wrote {output_path}")
        print(
            f"Source FPS: {plot_inputs.fps:.3f}; output FPS: {effective_fps:.3f}; "
            f"frames: {len(frame_indices)}"
        )
    finally:
        plt.close("all")
        plot_inputs.record.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the Sparse IQ velocity-vs-distance heatmap from an Acconeer A121 H5 file."
    )
    parser.add_argument("input", type=Path, help="Input .h5 recording")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output .gif or .mp4. Defaults to INPUT_STEM_velocity_distance.gif",
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
    parser.add_argument("--max-frames", type=int, default=None, help="Limit exported frames")
    parser.add_argument("--every-n", type=int, default=1, help="Export every Nth frame")
    parser.add_argument(
        "--dynamic-levels",
        action="store_true",
        help="Match the app's per-frame color scaling. By default, one fixed color scale is used.",
    )
    parser.add_argument(
        "--ffmpeg",
        type=Path,
        default=None,
        help="Path to ffmpeg.exe or its bin directory. Falls back to FFMPEG_PATH, then PATH.",
    )
    parser.add_argument(
        "--color-max",
        type=float,
        default=3000.0,
        help="Fixed magnitude color maximum. Defaults to 3000. Use 0 with --dynamic-levels to ignore.",
    )
    parser.add_argument(
        "--color-min",
        type=float,
        default=0.0,
        help="Magnitude color minimum. Defaults to 0.",
    )
    parser.add_argument(
        "--timestamp",
        choices=("relative", "absolute", "none"),
        default="relative",
        help="Timestamp display mode. Defaults to elapsed recording time.",
    )
    parser.add_argument(
        "--theme",
        choices=("light", "dark"),
        default="light",
        help="Plot theme. Defaults to light.",
    )
    args = parser.parse_args()

    output = args.output or args.input.with_name(f"{args.input.stem}_velocity_distance.gif")
    session_idx, group_idx, entry_idx, subsweep_idx = _resolve_selection_indices(
        h5_path=args.input,
        session_idx=args.session,
        group_idx=args.group,
        entry_idx=args.entry,
        subsweep_idx=args.subsweep,
    )
    export_heatmap_video(
        h5_path=args.input,
        output_path=output,
        session_idx=session_idx,
        group_idx=group_idx,
        entry_idx=entry_idx,
        subsweep_idx=subsweep_idx,
        max_frames=args.max_frames,
        every_n=max(args.every_n, 1),
        fixed_levels=not args.dynamic_levels,
        ffmpeg=args.ffmpeg,
        color_min=args.color_min,
        color_max=None if args.color_max <= 0 else args.color_max,
        timestamp_mode=args.timestamp,
        theme=args.theme,
    )


if __name__ == "__main__":
    main()
