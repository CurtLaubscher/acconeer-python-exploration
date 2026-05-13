from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import shutil
from pathlib import Path

import h5py
import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.animation import FFMpegWriter
from PIL import Image

from acconeer.exptool import a121
from acconeer.exptool.a121 import algo


def _h5_str(dataset: h5py.Dataset) -> str:
    return bytes(dataset[()]).decode()


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


def _entry_group(session_group: h5py.Group, group_idx: int, entry_idx: int) -> h5py.Group:
    return session_group[f"group_{group_idx}"][f"entry_{entry_idx}"]


def _complex_frame(frame: np.ndarray) -> np.ndarray:
    return frame["real"].astype(np.float32) + 1j * frame["imag"].astype(np.float32)


def _distance_velocity_map(subframe: np.ndarray) -> np.ndarray:
    hanning_window = np.hanning(subframe.shape[0])[:, np.newaxis]
    z_ft = np.fft.fftshift(np.fft.fft(subframe * hanning_window, axis=0), axes=(0,))
    return np.abs(z_ft)


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


def _canvas_to_pil(fig: plt.Figure) -> Image.Image:
    fig.canvas.draw()
    width, height = fig.canvas.get_width_height()
    rgba = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8).reshape(height, width, 4)
    return Image.fromarray(rgba[:, :, :3])


def _load_plot_inputs(
    h5_path: Path, session_idx: int, group_idx: int, entry_idx: int, subsweep_idx: int
) -> tuple[
    h5py.File,
    h5py.Group,
    a121.SensorConfig,
    a121.Metadata,
    np.ndarray,
    int,
    float,
    int,
    str,
]:
    h5_file = h5py.File(h5_path, "r")
    session_group = h5_file["sessions"][f"session_{session_idx}"]
    entry = _entry_group(session_group, group_idx, entry_idx)

    session_config = a121.SessionConfig.from_json(_h5_str(session_group["session_config"]))
    sensor_id = int(entry["sensor_id"][()])
    sensor_config = session_config.groups[group_idx][sensor_id]
    metadata = a121.Metadata.from_json(_h5_str(entry["metadata"]))

    ticks = entry["result/tick"][()]
    server_info = json.loads(_h5_str(h5_file["server_info"]))
    ticks_per_second = int(server_info["ticks_per_second"])
    fps = _recording_fps(ticks, ticks_per_second)
    record_timestamp = _h5_str(h5_file["timestamp"])

    return h5_file, entry, sensor_config, metadata, ticks, ticks_per_second, fps, sensor_id, record_timestamp


def _find_ffmpeg(explicit_ffmpeg: Path | None) -> str | None:
    if explicit_ffmpeg is not None:
        if explicit_ffmpeg.is_dir():
            explicit_ffmpeg = explicit_ffmpeg / "ffmpeg.exe"
        return str(explicit_ffmpeg) if explicit_ffmpeg.exists() else None

    bundled_bin = Path(
        r"C:\Users\claub\Desktop\ffmpeg-master-latest-win64-gpl-shared\bin\ffmpeg.exe"
    )
    if bundled_bin.exists():
        return str(bundled_bin)

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
    (
        h5_file,
        entry,
        sensor_config,
        metadata,
        ticks,
        ticks_per_second,
        fps,
        sensor_id,
        record_timestamp,
    ) = _load_plot_inputs(
        h5_path, session_idx, group_idx, entry_idx, subsweep_idx
    )

    try:
        frame_dataset = entry["result/frame"]
        subsweep = sensor_config.subsweeps[subsweep_idx]
        offset = metadata.subsweep_data_offset[subsweep_idx]
        length = metadata.subsweep_data_length[subsweep_idx]
        frame_indices = list(range(0, len(frame_dataset), every_n))
        if max_frames is not None:
            frame_indices = frame_indices[:max_frames]

        distances_m = algo.get_distances_m(subsweep, metadata)
        velocities_m_s, velocity_resolution = algo.get_approx_fft_vels(metadata, sensor_config)

        def dvm_for_frame(frame_idx: int) -> np.ndarray:
            frame = _complex_frame(frame_dataset[frame_idx])
            subframe = frame[:, offset : offset + length]
            return _distance_velocity_map(subframe)

        first_dvm = dvm_for_frame(frame_indices[0])
        title = f"{h5_path.name} - sensor {sensor_id}, subsweep {subsweep_idx + 1}"
        fig, ax, image, timestamp_artist = _make_figure(
            first_dvm=first_dvm,
            distances_m=distances_m,
            velocities_m_s=velocities_m_s,
            velocity_resolution=velocity_resolution,
            title=title,
            color_min=color_min,
            color_max=color_max,
        )

        if fixed_levels:
            max_level = (
                color_max
                if color_max is not None
                else max(float(1.05 * max(np.max(dvm_for_frame(i)) for i in frame_indices)), 1e-12)
            )
            image.set_clim(color_min, max_level)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        effective_fps = fps / every_n

        if output_path.suffix.lower() == ".mp4":
            ffmpeg_path = _find_ffmpeg(ffmpeg)
            if ffmpeg_path is None:
                raise RuntimeError("MP4 output requires ffmpeg on PATH. Use .gif or install ffmpeg.")

            rcParams["animation.ffmpeg_path"] = ffmpeg_path
            writer = FFMpegWriter(fps=effective_fps, metadata={"title": title})
            with writer.saving(fig, str(output_path), dpi=120):
                for frame_no, frame_idx in enumerate(frame_indices, start=1):
                    dvm = dvm_for_frame(frame_idx)
                    image.set_data(dvm)
                    if not fixed_levels:
                        image.set_clim(color_min, max(float(1.05 * np.max(dvm)), 1e-12))
                    ax.set_title(f"{title} - frame {frame_idx + 1}/{len(frame_dataset)}")
                    timestamp_artist.set_text(
                        _timestamp_text(
                            timestamp_mode,
                            record_timestamp,
                            ticks,
                            ticks_per_second,
                            frame_idx,
                        )
                    )
                    writer.grab_frame()
        else:
            pil_frames: list[Image.Image] = []
            for frame_idx in frame_indices:
                dvm = dvm_for_frame(frame_idx)
                image.set_data(dvm)
                if not fixed_levels:
                    image.set_clim(color_min, max(float(1.05 * np.max(dvm)), 1e-12))
                ax.set_title(f"{title} - frame {frame_idx + 1}/{len(frame_dataset)}")
                timestamp_artist.set_text(
                    _timestamp_text(
                        timestamp_mode,
                        record_timestamp,
                        ticks,
                        ticks_per_second,
                        frame_idx,
                    )
                )
                pil_frames.append(_canvas_to_pil(fig))

            duration_ms = max(int(round(1000 / effective_fps)), 1)
            pil_frames[0].save(
                output_path,
                save_all=True,
                append_images=pil_frames[1:],
                duration=duration_ms,
                loop=0,
            )

        print(f"Wrote {output_path}")
        print(f"Source FPS: {fps:.3f}; output FPS: {effective_fps:.3f}; frames: {len(frame_indices)}")
    finally:
        plt.close("all")
        h5_file.close()


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
    parser.add_argument("--session", type=int, default=0, help="Session index")
    parser.add_argument("--group", type=int, default=0, help="Group index")
    parser.add_argument("--entry", type=int, default=0, help="Entry index")
    parser.add_argument("--subsweep", type=int, default=0, help="Zero-based subsweep index")
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
        help="Path to ffmpeg.exe or its bin directory. The known Desktop ffmpeg path is auto-detected.",
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
    export_heatmap_video(
        h5_path=args.input,
        output_path=output,
        session_idx=args.session,
        group_idx=args.group,
        entry_idx=args.entry,
        subsweep_idx=args.subsweep,
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
