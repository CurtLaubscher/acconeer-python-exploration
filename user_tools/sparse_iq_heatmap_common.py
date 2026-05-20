from __future__ import annotations


"""Shared Sparse IQ heatmap helpers used by exporter and alignment tooling.

Keep this module compatible with the repo's Hatch-managed environments so the
CLI exporter and the GUI truth renderer stay on the same code path.
"""

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
import numpy as np

from acconeer.exptool import a121
from acconeer.exptool.a121 import algo


@dataclass
class HeatmapRecord:
    record: a121.Record
    sensor_config: a121.SensorConfig
    metadata: a121.Metadata
    results: list[a121.Result]
    ticks: np.ndarray
    ticks_per_second: int
    fps: float
    sensor_id: int
    record_timestamp: str
    session_idx: int
    group_idx: int
    entry_idx: int

    @property
    def duration_s(self) -> float:
        if len(self.ticks) < 2:
            return 0.0

        return float((self.ticks[-1] - self.ticks[0]) / self.ticks_per_second)

    def close(self) -> None:
        self.record.close()


@dataclass(frozen=True)
class HeatmapAxes:
    distances_m: np.ndarray
    velocities_m_s: np.ndarray
    velocity_resolution: float


def recording_fps(ticks: np.ndarray, ticks_per_second: int) -> float:
    if len(ticks) < 2:
        return 1.0

    intervals_s = np.diff(ticks) / ticks_per_second
    return float(1.0 / np.mean(intervals_s))


def timestamp_text(
    timestamp_mode: str,
    record_timestamp: str,
    ticks: np.ndarray,
    ticks_per_second: int,
    frame_idx: int,
) -> str:
    elapsed_s = elapsed_time_seconds(ticks, ticks_per_second, frame_idx)

    if timestamp_mode == "none":
        return ""
    if timestamp_mode == "absolute":
        try:
            absolute_time = datetime.fromisoformat(record_timestamp) + timedelta(seconds=elapsed_s)
            return absolute_time.isoformat(timespec="milliseconds")
        except ValueError:
            return f"{record_timestamp} + {elapsed_s:.3f} s"

    return f"t = {elapsed_s:.3f} s"


def distance_velocity_map(subframe: np.ndarray) -> np.ndarray:
    hanning_window = np.hanning(subframe.shape[0])[:, np.newaxis]
    z_ft = np.fft.fftshift(np.fft.fft(subframe * hanning_window, axis=0), axes=(0,))
    return np.abs(z_ft)


def color_max_for_dvm(dvm: np.ndarray) -> float:
    return max(float(1.05 * np.max(dvm)), 1e-12)


def heatmap_axes(
    metadata: a121.Metadata, sensor_config: a121.SensorConfig, subsweep: a121.SubsweepConfig
) -> HeatmapAxes:
    distances_m = algo.get_distances_m(subsweep, metadata)
    velocities_m_s, velocity_resolution = algo.get_approx_fft_vels(metadata, sensor_config)
    return HeatmapAxes(
        distances_m=distances_m,
        velocities_m_s=velocities_m_s,
        velocity_resolution=velocity_resolution,
    )


def render_dvm_to_rgb(
    dvm: np.ndarray,
    *,
    color_min: float,
    color_max: float | None,
    cmap_name: str = "viridis",
) -> np.ndarray:
    resolved_max = color_max if color_max is not None else color_max_for_dvm(dvm)
    if resolved_max <= color_min:
        resolved_max = color_min + 1e-12

    normalized = np.clip((dvm - color_min) / (resolved_max - color_min), 0.0, 1.0)
    rgba = matplotlib.colormaps[cmap_name](normalized)
    return np.ascontiguousarray((rgba[:, :, :3] * 255).astype(np.uint8))


def heatmap_frame_rgb(
    heatmap_record: HeatmapRecord,
    *,
    subsweep_idx: int,
    frame_idx: int,
    color_min: float,
    color_max: float | None,
    cmap_name: str = "viridis",
) -> np.ndarray:
    dvm = distance_velocity_map(heatmap_record.results[frame_idx].subframes[subsweep_idx])
    return render_dvm_to_rgb(
        dvm,
        color_min=color_min,
        color_max=color_max,
        cmap_name=cmap_name,
    )


def load_heatmap_record(
    h5_path: Path, session_idx: int, group_idx: int, entry_idx: int
) -> HeatmapRecord:
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
    fps = recording_fps(ticks, ticks_per_second)
    record_timestamp = record.timestamp

    return HeatmapRecord(
        record=record,
        sensor_config=sensor_config,
        metadata=metadata,
        results=results,
        ticks=ticks,
        ticks_per_second=ticks_per_second,
        fps=fps,
        sensor_id=sensor_id,
        record_timestamp=record_timestamp,
        session_idx=session_idx,
        group_idx=group_idx,
        entry_idx=entry_idx,
    )


def resolve_index(
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


def resolve_selection_indices(
    *,
    h5_path: Path,
    session_idx: int | None,
    group_idx: int | None,
    entry_idx: int | None,
    subsweep_idx: int | None,
) -> tuple[int, int, int, int]:
    record = a121.open_record(h5_path)

    try:
        resolved_session_idx = resolve_index(
            requested_idx=session_idx,
            count=record.num_sessions,
            option_name="session",
            item_name="session",
            parent_description="recording",
        )

        session = record.session(resolved_session_idx)
        resolved_group_idx = resolve_index(
            requested_idx=group_idx,
            count=len(session.session_config.groups),
            option_name="group",
            item_name="group",
            parent_description=f"session {resolved_session_idx}",
        )

        sensor_items = list(session.session_config.groups[resolved_group_idx].items())
        resolved_entry_idx = resolve_index(
            requested_idx=entry_idx,
            count=len(sensor_items),
            option_name="entry",
            item_name="entry",
            parent_description=f"group {resolved_group_idx} in session {resolved_session_idx}",
        )

        sensor_id, sensor_config = sensor_items[resolved_entry_idx]
        resolved_subsweep_idx = resolve_index(
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


def select_subsweep(heatmap_record: HeatmapRecord, subsweep_idx: int) -> a121.SubsweepConfig:
    if len(heatmap_record.results) == 0:
        raise ValueError("The selected sensor entry does not contain any frames to export.")

    try:
        return heatmap_record.sensor_config.subsweeps[subsweep_idx]
    except IndexError as exc:
        msg = f"Could not find subsweep {subsweep_idx} for sensor {heatmap_record.sensor_id}."
        raise ValueError(msg) from exc


def select_frame_indices(
    results: list[a121.Result], every_n: int, max_frames: int | None
) -> list[int]:
    if max_frames is not None and max_frames < 0:
        raise ValueError(f"--max-frames must be non-negative, got {max_frames}.")

    frame_indices = list(range(0, len(results), every_n))
    if max_frames is not None:
        frame_indices = frame_indices[:max_frames]

    if len(frame_indices) == 0:
        raise ValueError(
            "No frames were selected for export. Adjust --max-frames or choose a recording "
            "with available frames."
        )

    return frame_indices


def fixed_color_level(
    *, color_max: float | None, results: list[a121.Result], subsweep_idx: int, frame_indices: list[int]
) -> float:
    if color_max is not None:
        return color_max

    return max(
        color_max_for_dvm(distance_velocity_map(results[i].subframes[subsweep_idx]))
        for i in frame_indices
    )


def elapsed_time_seconds(ticks: np.ndarray, ticks_per_second: int, frame_idx: int) -> float:
    if len(ticks) == 0:
        return 0.0
    return float((ticks[frame_idx] - ticks[0]) / ticks_per_second)


def frame_index_at_time(
    heatmap_record: HeatmapRecord,
    time_s: float,
) -> int:
    if len(heatmap_record.results) == 0:
        raise ValueError("The selected sensor entry does not contain any frames.")

    clamped = min(max(time_s, 0.0), heatmap_record.duration_s)
    target_tick = heatmap_record.ticks[0] + int(round(clamped * heatmap_record.ticks_per_second))
    return int(np.searchsorted(heatmap_record.ticks, target_tick, side="left").clip(0, len(heatmap_record.ticks) - 1))
