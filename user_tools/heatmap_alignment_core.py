from __future__ import annotations


"""Core models and services for the heatmap alignment GUI.

This module is intended to be used from the Hatch-managed `app` environment
because it depends on the same runtime surface as the GUI, including OpenCV.
"""

import json
import math
import os
import shutil
import tempfile
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from scipy.io import loadmat
from sparse_iq_peak_distance_core import (
    STATUS_DETECTED,
    FramePeakMeasurement,
    LoadedPeakDistanceDatasource,
    PeakDistanceDatasourceSettings,
    load_peak_distance_json,
    validate_peak_distance_import,
)


SESSION_VERSION = 1

H5_TIMELINE_TRACK_COLOR_HEX = "#22c55e"
CAMERA_TIMELINE_TRACK_COLOR_HEX = "#f97316"
LEG2_TIMELINE_TRACK_COLOR_HEX = "#6366f1"
SIGNAL_PLOT_BACKGROUND_HEX = "#0f1720"
SIGNAL_PLOT_NO_DETECTION_ALPHA = 72
# Primary-segment opacity for segmented Signals curves (e.g. Leg2 valid flag). Change here only.
SIGNAL_PLOT_PRIMARY_SEGMENT_OPACITY = 0.7
SIGNAL_PLOT_PRIMARY_SEGMENT_ALPHA = int(round(255 * SIGNAL_PLOT_PRIMARY_SEGMENT_OPACITY))
TIMELINE_PLAYHEAD_COLOR_HEX = "#f8fafc"
SIGNAL_PLAYHEAD_ALPHA = 96

SignalPlotRangeMode = Literal["auto", "manual"]
Leg2UltrasonicSignalKind = Literal["raw", "filtered"]


@dataclass
class CameraTrack:
    path: str = ""
    fps: float = 0.0
    duration_s: float = 0.0
    frame_count: int = 0


@dataclass
class HeatmapTrack:
    path: str = ""
    session_idx: int = 0
    group_idx: int = 0
    entry_idx: int = 0
    subsweep_idx: int = 0
    duration_s: float = 0.0
    fps: float = 0.0


@dataclass
class ViewportGeometry:
    corners: list[list[float]] = field(default_factory=list)
    output_width: int = 0
    output_height: int = 0


@dataclass
class RenderSettings:
    color_min: float = 0.0
    color_max: float | None = 3000.0
    fixed_levels: bool = True


@dataclass
class PreprocessSettings:
    blur_sigma: float = 0.0
    downscale_factor: float = 1.0
    lag_window_s: float = 2.0
    sample_count: int = 30


@dataclass
class TimelineState:
    current_time_s: float = 0.0
    offset_s: float = 0.0


@dataclass
class ExportOverlaySettings:
    visible: bool = True
    preview_enabled: bool = True
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0


@dataclass
class ViewportVisibilitySettings:
    enabled: bool = False
    map_to_viridis: bool = False
    low: float = 0.0
    high: float = 1.0
    gamma: float = 1.0


@dataclass
class SignalPlotViewSettings:
    x_range_mode: SignalPlotRangeMode = "auto"
    y_range_mode: SignalPlotRangeMode = "auto"
    manual_x_range: tuple[float, float] | None = None
    manual_y_range: tuple[float, float] | None = None


@dataclass
class Leg2UltrasonicDatasourceSettings:
    path: str = ""
    visible: bool = True
    signal_kind: Leg2UltrasonicSignalKind = "raw"
    offset_s: float = 0.0


@dataclass(frozen=True)
class LoadedLeg2UltrasonicDatasource:
    path: Path
    time_s: np.ndarray
    raw_distance_m: np.ndarray
    filtered_distance_m: np.ndarray
    reliable_flag_mask: np.ndarray
    stance_phase_mask: np.ndarray
    duration_s: float


@dataclass(frozen=True)
class PeakDistanceSignalSeries:
    detected_time_s: np.ndarray
    detected_distance_m: np.ndarray
    candidate_time_s: np.ndarray
    candidate_distance_m: np.ndarray


@dataclass(frozen=True)
class Leg2StanceIntervals:
    """Stance phase intervals from robustFC mask.

    Represents gait stance phases (foot in contact) as time intervals,
    with track offset already applied. Used to render filled patches on
    the Signals plot as a temporal context aid for manual alignment.
    """
    start_times_s: np.ndarray
    end_times_s: np.ndarray


@dataclass(frozen=True)
class Leg2UltrasonicSignalSeries:
    primary_time_s: np.ndarray
    primary_distance_m: np.ndarray
    faded_time_s: np.ndarray
    faded_distance_m: np.ndarray
    stance_intervals: Leg2StanceIntervals


class Leg2MatImportError(ValueError):
    """Raised when a Leg2 `.mat` file does not match the expected ultrasonic export."""

    def __init__(self, detail: str) -> None:
        self.detail = detail.strip()
        super().__init__(self.user_message())

    def user_message(self) -> str:
        if self.detail:
            return f"Could not load Leg2 MAT ultrasonic datasource.\n\n{self.detail}"
        return "Could not load Leg2 MAT ultrasonic datasource."


@dataclass(frozen=True)
class VideoProbe:
    path: Path
    fps: float
    frame_count: int
    duration_s: float
    width: int
    height: int


@dataclass(frozen=True)
class ProxyVideoResult:
    source_path: Path
    display_path: Path
    source_probe: VideoProbe
    proxy_path: Path | None
    state: Literal["original", "proxy_reused", "proxy_built", "proxy_unavailable"]


@dataclass(frozen=True)
class OverlayPlotPresentation:
    source_size: tuple[int, int]
    render_size: tuple[int, int]
    font_size_pt: float
    tick_label_size_pt: float
    tick_length_pt: float
    axis_line_width_pt: float
    left_margin: float
    right_margin: float
    bottom_margin: float
    top_margin: float


@dataclass
class AlignmentSession:
    """Serializable state for one alignment session."""

    version: int = SESSION_VERSION
    camera_track: CameraTrack = field(default_factory=CameraTrack)
    heatmap_track: HeatmapTrack = field(default_factory=HeatmapTrack)
    viewport: ViewportGeometry = field(default_factory=ViewportGeometry)
    render: RenderSettings = field(default_factory=RenderSettings)
    preprocess: PreprocessSettings = field(default_factory=PreprocessSettings)
    timeline: TimelineState = field(default_factory=TimelineState)
    export_overlay: ExportOverlaySettings = field(default_factory=ExportOverlaySettings)
    viewport_visibility: ViewportVisibilitySettings = field(
        default_factory=ViewportVisibilitySettings
    )
    peak_distance_datasource: PeakDistanceDatasourceSettings = field(
        default_factory=PeakDistanceDatasourceSettings
    )
    leg2_ultrasonic_datasource: Leg2UltrasonicDatasourceSettings = field(
        default_factory=Leg2UltrasonicDatasourceSettings
    )
    signal_plot_view: SignalPlotViewSettings = field(default_factory=SignalPlotViewSettings)

    def to_json_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        view = payload["signal_plot_view"]
        if view["manual_x_range"] is not None:
            view["manual_x_range"] = list(view["manual_x_range"])
        if view["manual_y_range"] is not None:
            view["manual_y_range"] = list(view["manual_y_range"])
        return payload

    @classmethod
    def from_json_dict(cls, payload: dict[str, Any]) -> AlignmentSession:
        version = payload.get("version")
        if version != SESSION_VERSION:
            raise ValueError(
                f"Unsupported alignment session version {version!r}; "
                f"expected {SESSION_VERSION}."
            )

        session = cls(
            version=version,
            camera_track=CameraTrack(**payload["camera_track"]),
            heatmap_track=HeatmapTrack(**payload["heatmap_track"]),
            viewport=ViewportGeometry(**payload["viewport"]),
            render=RenderSettings(**payload["render"]),
            preprocess=PreprocessSettings(**payload["preprocess"]),
            timeline=TimelineState(**payload["timeline"]),
            export_overlay=ExportOverlaySettings(**payload.get("export_overlay", {})),
            viewport_visibility=ViewportVisibilitySettings(
                **payload.get("viewport_visibility", {})
            ),
            peak_distance_datasource=PeakDistanceDatasourceSettings(
                **payload.get("peak_distance_datasource", {})
            ),
            leg2_ultrasonic_datasource=Leg2UltrasonicDatasourceSettings(
                **payload.get("leg2_ultrasonic_datasource", {})
            ),
            signal_plot_view=_signal_plot_view_settings_from_payload(
                payload.get("signal_plot_view")
            ),
        )
        validate_alignment_session(session)
        return session


def _signal_plot_view_settings_from_payload(
    payload: dict[str, Any] | None,
) -> SignalPlotViewSettings:
    if not payload:
        return SignalPlotViewSettings()

    x_range_mode = payload.get("x_range_mode", "auto")
    y_range_mode = payload.get("y_range_mode", "auto")
    if x_range_mode not in ("auto", "manual"):
        raise ValueError(f"Unsupported signal plot x_range_mode {x_range_mode!r}.")
    if y_range_mode not in ("auto", "manual"):
        raise ValueError(f"Unsupported signal plot y_range_mode {y_range_mode!r}.")

    manual_x_range = _optional_range_pair(payload.get("manual_x_range"))
    manual_y_range = _optional_range_pair(payload.get("manual_y_range"))
    return SignalPlotViewSettings(
        x_range_mode=x_range_mode,
        y_range_mode=y_range_mode,
        manual_x_range=manual_x_range,
        manual_y_range=manual_y_range,
    )


def _optional_range_pair(value: Any) -> tuple[float, float] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("Signal plot manual ranges must be two-number lists.")
    return float(value[0]), float(value[1])


def timeline_view_bounds_s(
    *,
    heatmap_duration_s: float,
    camera_duration_s: float,
    camera_offset_s: float,
    leg2_duration_s: float = 0.0,
    leg2_offset_s: float = 0.0,
    fit_padding_fraction: float = 0.12,
) -> tuple[float, float]:
    """Return padded shared timeline bounds used by the timeline and Signals plot."""
    heatmap_duration_s = max(0.0, heatmap_duration_s)
    camera_duration_s = max(0.0, camera_duration_s)
    leg2_duration_s = max(0.0, leg2_duration_s)
    camera_start_s = -camera_offset_s
    leg2_start_s = -leg2_offset_s
    track_starts = [0.0]
    track_ends = [heatmap_duration_s]
    if camera_duration_s > 0.0:
        track_starts.append(camera_start_s)
        track_ends.append(camera_start_s + camera_duration_s)
    if leg2_duration_s > 0.0:
        track_starts.append(leg2_start_s)
        track_ends.append(leg2_start_s + leg2_duration_s)

    range_start_s = min(track_starts)
    range_end_s = max(track_ends)
    span_s = range_end_s - range_start_s
    if span_s <= 0.0 or math.isclose(range_start_s, range_end_s):
        span_s = 1.0
    padding_s = span_s * fit_padding_fraction
    return range_start_s - padding_s, range_end_s + padding_s


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    normalized = hex_color.strip().lstrip("#")
    if len(normalized) != 6:
        raise ValueError(f"Expected #RRGGBB color, got {hex_color!r}.")
    return (
        int(normalized[0:2], 16),
        int(normalized[2:4], 16),
        int(normalized[4:6], 16),
    )


def _rgb_to_hex(red: int, green: int, blue: int) -> str:
    return f"#{red:02x}{green:02x}{blue:02x}"


def derive_signal_plot_color(
    track_color_hex: str,
    *,
    background_hex: str = SIGNAL_PLOT_BACKGROUND_HEX,
) -> str:
    """Derive a readable plot color from a timeline track color."""
    red, green, blue = _hex_to_rgb(track_color_hex)
    background_red, background_green, background_blue = _hex_to_rgb(background_hex)
    background_luminance = (
        0.299 * background_red + 0.587 * background_green + 0.114 * background_blue
    )
    if background_luminance < 128.0:
        scale = 1.35
    else:
        scale = 0.72
    adjusted = (
        int(np.clip(red * scale, 0, 255)),
        int(np.clip(green * scale, 0, 255)),
        int(np.clip(blue * scale, 0, 255)),
    )
    return _rgb_to_hex(*adjusted)


def derive_h5_signal_plot_color(
    track_color_hex: str = H5_TIMELINE_TRACK_COLOR_HEX,
    *,
    background_hex: str = SIGNAL_PLOT_BACKGROUND_HEX,
) -> str:
    """Derive a readable plot color from the H5 timeline track color."""
    return derive_signal_plot_color(track_color_hex, background_hex=background_hex)


def _leg2_mat_import_error(detail: str) -> Leg2MatImportError:
    return Leg2MatImportError(detail)


def _unwrap_mat_scalar(value: Any) -> Any:
    current = value
    while isinstance(current, np.ndarray) and current.ndim > 0 and current.size == 1:
        current = current.item()
    return current


def _mat_struct_field(container: Any, field_name: str) -> Any:
    if container is None:
        raise KeyError(field_name)
    if isinstance(container, dict):
        if field_name not in container:
            raise KeyError(field_name)
        return container[field_name]
    if hasattr(container, "_fieldnames"):
        if field_name not in getattr(container, "_fieldnames", ()):
            raise KeyError(field_name)
        return getattr(container, field_name)
    if isinstance(container, np.void):
        names = container.dtype.names or ()
        if field_name not in names:
            raise KeyError(field_name)
        return container[field_name]
    if isinstance(container, np.ndarray) and container.dtype.names:
        if field_name not in container.dtype.names:
            raise KeyError(field_name)
        if container.ndim == 0:
            return container[field_name]
        return container[field_name].reshape(-1)
    raise TypeError(f"Unsupported MATLAB struct container type: {type(container)!r}.")


def _mat_top_level_field(payload: dict[str, Any], struct_name: str, field_name: str) -> Any:
    if struct_name not in payload:
        raise KeyError(struct_name)
    try:
        return _mat_struct_field(payload[struct_name], field_name)
    except KeyError as exc:
        raise KeyError(f"{struct_name}.{field_name}") from exc


def _read_mat_1d_numeric_array(
    value: Any,
    *,
    field_label: str,
    require_finite: bool = True,
) -> np.ndarray:
    unwrapped = _unwrap_mat_scalar(value)
    try:
        array = np.asarray(unwrapped, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise Leg2MatImportError(
            f"{field_label} could not be interpreted as numeric samples."
        ) from exc
    array = np.squeeze(array)
    if array.ndim == 0:
        array = np.asarray([float(array)], dtype=np.float64)
    elif array.ndim != 1:
        array = array.reshape(-1)
    if array.size == 0:
        raise Leg2MatImportError(f"{field_label} is empty.")
    if require_finite and not np.all(np.isfinite(array)):
        raise Leg2MatImportError(f"{field_label} contains non-finite values.")
    return array.astype(np.float64, copy=False)


def _read_mat_1d_bool_array(value: Any, *, field_label: str) -> np.ndarray:
    numeric = _read_mat_1d_numeric_array(value, field_label=field_label)
    return numeric != 0.0


def _trim_trailing_zero_time_samples(
    time_s: np.ndarray,
    *companion_arrays: np.ndarray,
) -> tuple[np.ndarray, tuple[np.ndarray, ...]]:
    if time_s.size == 0:
        return time_s, companion_arrays
    valid_mask = time_s != 0.0
    if not np.any(valid_mask):
        return time_s[:0], tuple(array[:0] for array in companion_arrays)
    last_valid_idx = int(np.max(np.flatnonzero(valid_mask)))
    trimmed_time = time_s[: last_valid_idx + 1]
    trimmed_companions = tuple(array[: last_valid_idx + 1] for array in companion_arrays)
    return trimmed_time, trimmed_companions


def _validate_increasing_time_axis(time_s: np.ndarray) -> None:
    if time_s.size == 0:
        raise Leg2MatImportError("Leg2 time axis is empty after cleanup.")
    if not np.all(np.isfinite(time_s)):
        raise Leg2MatImportError("Leg2 time axis contains non-finite values.")
    if np.any(np.diff(time_s) <= 0.0):
        raise Leg2MatImportError("Leg2 time axis is not strictly increasing.")


def load_leg2_mat_ultrasonic(mat_path: Path) -> LoadedLeg2UltrasonicDatasource:
    """Load the known Leg2 ultrasonic export from a MATLAB v5 `.mat` file."""
    try:
        payload = loadmat(str(mat_path), squeeze_me=True, struct_as_record=False)
    except Exception as exc:
        raise _leg2_mat_import_error(f"Could not read MATLAB file: {exc}") from exc

    mat_fields = {key: value for key, value in payload.items() if not key.startswith("__")}
    required_paths = (
        ("DataRecordCommon", "timeOut"),
        ("Ultrasonic", "Distance"),
        ("DataRecordCommon", "ultrasonic_filtered"),
        ("DataRecordCommon", "ReliableFlag"),
        ("DataRecordCommon", "robustFC"),
    )
    extracted: dict[tuple[str, str], Any] = {}
    for struct_name, field_name in required_paths:
        label = f"{struct_name}.{field_name}"
        try:
            extracted[(struct_name, field_name)] = _mat_top_level_field(
                mat_fields,
                struct_name,
                field_name,
            )
        except KeyError:
            raise _leg2_mat_import_error(f"Missing required field: {label}") from None

    try:
        time_raw = _read_mat_1d_numeric_array(
            extracted[("DataRecordCommon", "timeOut")],
            field_label="DataRecordCommon.timeOut",
        )
        raw_distance_mm = _read_mat_1d_numeric_array(
            extracted[("Ultrasonic", "Distance")],
            field_label="Ultrasonic.Distance",
            require_finite=False,
        )
        filtered_distance_mm = _read_mat_1d_numeric_array(
            extracted[("DataRecordCommon", "ultrasonic_filtered")],
            field_label="DataRecordCommon.ultrasonic_filtered",
            require_finite=False,
        )
        reliable_flag_mask = _read_mat_1d_bool_array(
            extracted[("DataRecordCommon", "ReliableFlag")],
            field_label="DataRecordCommon.ReliableFlag",
        )
        robust_fc = _read_mat_1d_bool_array(
            extracted[("DataRecordCommon", "robustFC")],
            field_label="DataRecordCommon.robustFC",
        )
    except Leg2MatImportError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise _leg2_mat_import_error(str(exc)) from exc
    except Exception as exc:
        raise _leg2_mat_import_error(str(exc)) from exc

    lengths = {
        "DataRecordCommon.timeOut": time_raw.size,
        "Ultrasonic.Distance": raw_distance_mm.size,
        "DataRecordCommon.ultrasonic_filtered": filtered_distance_mm.size,
        "DataRecordCommon.ReliableFlag": reliable_flag_mask.size,
        "DataRecordCommon.robustFC": robust_fc.size,
    }
    unique_lengths = set(lengths.values())
    if len(unique_lengths) != 1:
        detail = ", ".join(f"{name}={count}" for name, count in lengths.items())
        raise _leg2_mat_import_error(f"Incompatible array lengths after cleanup: {detail}")

    time_s, (raw_distance_mm, filtered_distance_mm, reliable_flag_mask, robust_fc) = _trim_trailing_zero_time_samples(
        time_raw,
        raw_distance_mm,
        filtered_distance_mm,
        reliable_flag_mask,
        robust_fc,
    )
    _validate_increasing_time_axis(time_s)

    time_origin_s = float(time_s[0])
    elapsed_time_s = time_s - time_origin_s
    raw_distance_m = raw_distance_mm / 1000.0
    filtered_distance_m = filtered_distance_mm / 1000.0
    duration_s = float(elapsed_time_s[-1]) if elapsed_time_s.size else 0.0

    return LoadedLeg2UltrasonicDatasource(
        path=mat_path,
        time_s=elapsed_time_s.astype(np.float64, copy=False),
        raw_distance_m=raw_distance_m.astype(np.float64, copy=False),
        filtered_distance_m=filtered_distance_m.astype(np.float64, copy=False),
        reliable_flag_mask=reliable_flag_mask.astype(bool, copy=False),
        stance_phase_mask=robust_fc.astype(bool, copy=False),
        duration_s=duration_s,
    )


def import_leg2_mat_for_heatmap(mat_path: Path) -> LoadedLeg2UltrasonicDatasource:
    return load_leg2_mat_ultrasonic(mat_path)


def _plottable_leg2_distance_m(distance_m: float) -> float | None:
    if not math.isfinite(distance_m):
        return None
    return float(distance_m)


def _compute_leg2_stance_intervals(
    time_s: np.ndarray,
    stance_phase_mask: np.ndarray,
    offset_s: float,
) -> Leg2StanceIntervals:
    """Compute stance intervals from robustFC mask using rising/falling edge detection.

    Intervals span from time_s[i] where stance starts to time_s[i] where stance ends.
    Treat first time step as implicit rising edge if recording starts in stance (stance_phase_mask[0]==1),
    and last time step as implicit falling edge if recording ends in stance (stance_phase_mask[-1]==1).
    """
    if time_s.size == 0:
        return Leg2StanceIntervals(
            start_times_s=np.asarray([], dtype=np.float64),
            end_times_s=np.asarray([], dtype=np.float64),
        )

    track_start_s = -offset_s
    start_times: list[float] = []
    end_times: list[float] = []

    # Detect rising and falling edges in stance phase mask.
    # Track offset is applied to all time values so intervals move with the signal.
    for i in range(len(stance_phase_mask)):
        is_stance = stance_phase_mask[i]
        is_prev_stance = stance_phase_mask[i - 1] if i > 0 else False

        # Detect rising edge (0 -> 1 or implicit at start)
        if is_stance and not is_prev_stance:
            start_times.append(float(time_s[i]) + track_start_s)

        # Detect falling edge (1 -> 0 or implicit at end)
        if not is_stance and is_prev_stance:
            end_times.append(float(time_s[i - 1]) + track_start_s)
        elif is_stance and i == len(stance_phase_mask) - 1:
            # Implicit falling edge at end if recording ends in stance
            end_times.append(float(time_s[i]) + track_start_s)

    return Leg2StanceIntervals(
        start_times_s=np.asarray(start_times, dtype=np.float64),
        end_times_s=np.asarray(end_times, dtype=np.float64),
    )


def build_leg2_ultrasonic_signal_series(
    datasource: LoadedLeg2UltrasonicDatasource,
    *,
    signal_kind: Leg2UltrasonicSignalKind,
    offset_s: float,
) -> Leg2UltrasonicSignalSeries:
    if signal_kind == "raw":
        distance_values = datasource.raw_distance_m
    elif signal_kind == "filtered":
        distance_values = datasource.filtered_distance_m
    else:
        raise ValueError(f"Unsupported Leg2 ultrasonic signal kind {signal_kind!r}.")

    primary_time_s: list[float] = []
    primary_distance_m: list[float] = []
    faded_time_s: list[float] = []
    faded_distance_m: list[float] = []
    track_start_s = -offset_s

    def append_gap(time_values: list[float], distance_values_out: list[float]) -> None:
        if time_values and not math.isnan(time_values[-1]):
            time_values.append(float("nan"))
            distance_values_out.append(float("nan"))

    def append_bridge(
        source_time_s: list[float],
        source_distance_m: list[float],
        target_time_s: list[float],
        target_distance_m: list[float],
    ) -> None:
        if not source_time_s or math.isnan(source_time_s[-1]):
            return
        bridge_time_s = source_time_s[-1]
        bridge_distance_m = source_distance_m[-1]
        if target_time_s and target_time_s[-1] == bridge_time_s:
            return
        target_time_s.append(bridge_time_s)
        target_distance_m.append(bridge_distance_m)

    for source_time_s, distance_m, is_valid in zip(
        datasource.time_s,
        distance_values,
        datasource.reliable_flag_mask,
        strict=False,
    ):
        aligned_time_s = float(source_time_s) + track_start_s
        plottable_distance_m = _plottable_leg2_distance_m(float(distance_m))
        if plottable_distance_m is None:
            append_gap(primary_time_s, primary_distance_m)
            append_gap(faded_time_s, faded_distance_m)
            continue
        if is_valid:
            append_bridge(
                faded_time_s,
                faded_distance_m,
                primary_time_s,
                primary_distance_m,
            )
            append_gap(faded_time_s, faded_distance_m)
            primary_time_s.append(aligned_time_s)
            primary_distance_m.append(plottable_distance_m)
        else:
            append_bridge(
                primary_time_s,
                primary_distance_m,
                faded_time_s,
                faded_distance_m,
            )
            append_gap(primary_time_s, primary_distance_m)
            faded_time_s.append(aligned_time_s)
            faded_distance_m.append(plottable_distance_m)

    stance_intervals = _compute_leg2_stance_intervals(
        datasource.time_s,
        datasource.stance_phase_mask,
        offset_s,
    )

    return Leg2UltrasonicSignalSeries(
        primary_time_s=np.asarray(primary_time_s, dtype=np.float64),
        primary_distance_m=np.asarray(primary_distance_m, dtype=np.float64),
        faded_time_s=np.asarray(faded_time_s, dtype=np.float64),
        faded_distance_m=np.asarray(faded_distance_m, dtype=np.float64),
        stance_intervals=stance_intervals,
    )


def _plottable_candidate_distance_m(measurement: FramePeakMeasurement) -> float | None:
    value = measurement.candidate_peak_distance_m
    if not math.isfinite(value):
        return None
    return float(value)


def build_peak_distance_signal_series(
    measurements: tuple[FramePeakMeasurement, ...],
) -> PeakDistanceSignalSeries:
    detected_time_s: list[float] = []
    detected_distance_m: list[float] = []
    candidate_time_s: list[float] = []
    candidate_distance_m: list[float] = []

    def append_gap(time_values: list[float], distance_values: list[float]) -> None:
        if time_values and not math.isnan(time_values[-1]):
            time_values.append(float("nan"))
            distance_values.append(float("nan"))

    def append_bridge(
        source_time_s: list[float],
        source_distance_m: list[float],
        target_time_s: list[float],
        target_distance_m: list[float],
    ) -> None:
        if not source_time_s or math.isnan(source_time_s[-1]):
            return
        bridge_time_s = source_time_s[-1]
        bridge_distance_m = source_distance_m[-1]
        if target_time_s and target_time_s[-1] == bridge_time_s:
            return
        target_time_s.append(bridge_time_s)
        target_distance_m.append(bridge_distance_m)

    for measurement in measurements:
        distance_m = _plottable_candidate_distance_m(measurement)
        if distance_m is None:
            append_gap(detected_time_s, detected_distance_m)
            append_gap(candidate_time_s, candidate_distance_m)
            continue
        if measurement.status == STATUS_DETECTED:
            append_bridge(candidate_time_s, candidate_distance_m, detected_time_s, detected_distance_m)
            append_gap(candidate_time_s, candidate_distance_m)
            detected_time_s.append(measurement.time_s)
            detected_distance_m.append(distance_m)
        else:
            append_bridge(detected_time_s, detected_distance_m, candidate_time_s, candidate_distance_m)
            append_gap(detected_time_s, detected_distance_m)
            candidate_time_s.append(measurement.time_s)
            candidate_distance_m.append(distance_m)

    return PeakDistanceSignalSeries(
        detected_time_s=np.asarray(detected_time_s, dtype=np.float64),
        detected_distance_m=np.asarray(detected_distance_m, dtype=np.float64),
        candidate_time_s=np.asarray(candidate_time_s, dtype=np.float64),
        candidate_distance_m=np.asarray(candidate_distance_m, dtype=np.float64),
    )


def _visible_distance_values_in_x_range(
    time_distance_pairs: tuple[tuple[np.ndarray, np.ndarray], ...],
    *,
    x_min_s: float,
    x_max_s: float,
) -> list[float]:
    visible_values: list[float] = []
    for time_values, distance_values in time_distance_pairs:
        for time_s, distance_m in zip(time_values, distance_values, strict=False):
            if not math.isfinite(time_s) or not math.isfinite(distance_m):
                continue
            if x_min_s <= time_s <= x_max_s:
                visible_values.append(distance_m)
    return visible_values


def visible_signal_y_range(
    series: PeakDistanceSignalSeries,
    *,
    x_min_s: float,
    x_max_s: float,
    leg2_series: Leg2UltrasonicSignalSeries | None = None,
) -> tuple[float, float] | None:
    if x_max_s < x_min_s:
        x_min_s, x_max_s = x_max_s, x_min_s

    time_distance_pairs: tuple[tuple[np.ndarray, np.ndarray], ...] = (
        (series.detected_time_s, series.detected_distance_m),
        (series.candidate_time_s, series.candidate_distance_m),
    )
    if leg2_series is not None:
        time_distance_pairs = (
            *time_distance_pairs,
            (leg2_series.primary_time_s, leg2_series.primary_distance_m),
            (leg2_series.faded_time_s, leg2_series.faded_distance_m),
        )
    visible_values = _visible_distance_values_in_x_range(
        time_distance_pairs,
        x_min_s=x_min_s,
        x_max_s=x_max_s,
    )

    if not visible_values:
        return None
    y_min = min(0.0, min(visible_values))
    y_max = max(visible_values)
    if math.isclose(y_min, y_max):
        padding = max(abs(y_min) * 0.05, 0.05)
        return y_min - padding, y_max + padding
    padding = (y_max - y_min) * 0.05
    return y_min - padding, y_max + padding


def save_alignment_session(session: AlignmentSession, path: Path) -> None:
    validate_alignment_session(session, allow_missing_sources=True)
    path.write_text(json.dumps(session.to_json_dict(), indent=2), encoding="utf-8")


def load_alignment_session(path: Path) -> AlignmentSession:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed alignment session: {exc}") from exc

    return AlignmentSession.from_json_dict(payload)


def validate_alignment_session(
    session: AlignmentSession,
    *,
    allow_missing_sources: bool = False,
) -> None:
    if session.version != SESSION_VERSION:
        raise ValueError(f"Unsupported session version {session.version}.")

    if not allow_missing_sources:
        if session.camera_track.path and not Path(session.camera_track.path).exists():
            raise ValueError(f"Camera video does not exist: {session.camera_track.path}")
        if session.heatmap_track.path and not Path(session.heatmap_track.path).exists():
            raise ValueError(f"H5 recording does not exist: {session.heatmap_track.path}")

    corners = np.array(session.viewport.corners, dtype=np.float32)
    if corners.size != 0:
        if corners.shape != (4, 2):
            raise ValueError("Viewport corners must contain exactly four [x, y] points.")
        area = cv2.contourArea(corners)
        if abs(area) < 1.0:
            raise ValueError("Viewport quadrilateral is degenerate.")

    if session.viewport.output_width < 0 or session.viewport.output_height < 0:
        raise ValueError("Viewport output dimensions must be non-negative.")
    if session.preprocess.downscale_factor <= 0:
        raise ValueError("Downscale factor must be positive.")
    if session.preprocess.sample_count <= 0:
        raise ValueError("Sample count must be positive.")
    if session.export_overlay.width < 0 or session.export_overlay.height < 0:
        raise ValueError("Export overlay dimensions must be non-negative.")
    if not 0.0 <= session.viewport_visibility.low <= 1.0:
        raise ValueError("Viewport visibility low must be within [0, 1].")
    if not 0.0 <= session.viewport_visibility.high <= 1.0:
        raise ValueError("Viewport visibility high must be within [0, 1].")
    if session.viewport_visibility.low >= session.viewport_visibility.high:
        raise ValueError("Viewport visibility low must be less than high.")
    if session.viewport_visibility.gamma <= 0.0:
        raise ValueError("Viewport visibility gamma must be positive.")


def probe_video(path: Path) -> VideoProbe:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"Could not open camera video: {path}")
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    finally:
        capture.release()

    duration_s = frame_count / fps if fps > 0 and frame_count > 0 else 0.0
    return VideoProbe(
        path=path,
        fps=fps,
        frame_count=frame_count,
        duration_s=duration_s,
        width=width,
        height=height,
    )


def prepare_proxy_video(
    source_path: Path,
    *,
    max_dimension: int = 1280,
    cache_root: Path | None = None,
) -> ProxyVideoResult:
    """Prepare a preview proxy for large camera videos.

    Small sources at or below ``max_dimension`` are returned unchanged. Larger
    sources require ffmpeg; when ffmpeg is unavailable the call raises instead
    of falling back to full-resolution interactive preview.
    """
    source_probe = probe_video(source_path)
    if max(source_probe.width, source_probe.height) <= max_dimension:
        return ProxyVideoResult(
            source_path=source_path,
            display_path=source_path,
            source_probe=source_probe,
            proxy_path=None,
            state="original",
        )

    ffmpeg_path = _find_ffmpeg()
    if ffmpeg_path is None:
        raise RuntimeError("ffmpeg was not found; preview proxy generation is required.")

    proxy_path = _proxy_cache_path(
        source_path,
        source_probe=source_probe,
        max_dimension=max_dimension,
        cache_root=cache_root,
    )
    if proxy_path.exists():
        return ProxyVideoResult(
            source_path=source_path,
            display_path=proxy_path,
            source_probe=source_probe,
            proxy_path=proxy_path,
            state="proxy_reused",
        )

    from heatmap_alignment_resource_jobs import build_preview_proxy_video

    return build_preview_proxy_video(
        source_path,
        max_dimension=max_dimension,
        cache_root=cache_root,
    )


def _scaled_video_dimensions(width: int, height: int, max_dimension: int) -> tuple[int, int]:
    largest_dimension = max(width, height, 1)
    scale = min(1.0, max_dimension / largest_dimension)
    scaled_width = max(2, int(round(width * scale)))
    scaled_height = max(2, int(round(height * scale)))
    if scaled_width % 2 != 0:
        scaled_width -= 1
    if scaled_height % 2 != 0:
        scaled_height -= 1
    return max(2, scaled_width), max(2, scaled_height)


def _proxy_cache_path(
    source_path: Path,
    *,
    source_probe: VideoProbe,
    max_dimension: int,
    cache_root: Path | None,
) -> Path:
    source_stat = source_path.stat()
    payload = "|".join(
        [
            str(source_path.resolve()),
            str(source_stat.st_size),
            str(source_stat.st_mtime_ns),
            str(source_probe.width),
            str(source_probe.height),
            str(source_probe.frame_count),
            str(source_probe.fps),
            str(max_dimension),
            "proxy-v1",
        ]
    )
    digest = sha256(payload.encode("utf-8")).hexdigest()[:16]
    stem = source_path.stem
    root = cache_root or _default_proxy_cache_root()
    return root / f"{stem}_{digest}_proxy_{max_dimension}.mp4"


def _default_proxy_cache_root() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Acconeer" / "HeatmapAlignmentWorkbench" / "proxy-cache"
    return Path(tempfile.gettempdir()) / "Acconeer" / "HeatmapAlignmentWorkbench" / "proxy-cache"


def _resolve_ffmpeg_path(path: Path | None) -> str | None:
    if path is None:
        return None
    if path.is_dir():
        path = path / "ffmpeg.exe"
    return str(path) if path.exists() else None


def _find_ffmpeg() -> str | None:
    for candidate in (
        os.getenv("FFMPEG_PATH"),
        r"C:\Users\claub\Documents\Portable Programs\ffmpeg-master-latest-win64-gpl-shared\bin",
    ):
        if candidate:
            resolved = _resolve_ffmpeg_path(Path(candidate))
            if resolved is not None:
                return resolved
    return shutil.which("ffmpeg")


class CameraVideoSource:
    """OpenCV-backed camera video reader with sequential playback support."""

    _AccessHint = Literal["auto", "playback", "scrub", "random"]

    def __init__(self, path: Path, *, max_preview_dimension: int | None = 1280) -> None:
        self.path = path
        self._capture = cv2.VideoCapture(str(path))
        if not self._capture.isOpened():
            raise ValueError(f"Could not open camera video: {path}")

        self.fps = float(self._capture.get(cv2.CAP_PROP_FPS) or 0.0)
        self.frame_count = int(self._capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.original_width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        self.original_height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        self.duration_s = (
            self.frame_count / self.fps if self.fps > 0 and self.frame_count > 0 else 0.0
        )
        largest_dimension = max(self.original_width, self.original_height, 1)
        if max_preview_dimension is None or max_preview_dimension <= 0:
            self.preview_scale = 1.0
        else:
            self.preview_scale = min(1.0, max_preview_dimension / largest_dimension)
        self.preview_width = max(1, int(round(self.original_width * self.preview_scale)))
        self.preview_height = max(1, int(round(self.original_height * self.preview_scale)))
        self._frame_cache: OrderedDict[int, np.ndarray] = OrderedDict()
        self._cache_max_frames = 180
        self._sequential_frame_idx: int | None = None
        self._sequential_gap_limit = 90
        self._scrub_seek_threshold = 24

    def close(self) -> None:
        self._capture.release()

    @property
    def metadata(self) -> CameraTrack:
        return CameraTrack(
            path=str(self.path),
            fps=self.fps,
            duration_s=self.duration_s,
            frame_count=self.frame_count,
        )

    def frame_at_index(
        self,
        frame_idx: int,
        *,
        access_hint: _AccessHint = "auto",
    ) -> np.ndarray:
        if self.frame_count <= 0:
            raise ValueError("Camera video does not contain any frames.")

        clamped = int(np.clip(frame_idx, 0, self.frame_count - 1))
        cached = self._cache_get(clamped)
        if cached is not None:
            return cached

        if self._should_use_sequential_decode(clamped, access_hint):
            frame = self._read_forward_to_index(clamped)
        else:
            frame = self._read_with_seek(clamped)
        self._cache_put(clamped, frame)
        return frame

    def frame_at_seconds(
        self,
        time_s: float,
        *,
        access_hint: _AccessHint = "auto",
    ) -> tuple[int, np.ndarray]:
        if self.frame_count <= 0:
            raise ValueError("Camera video does not contain any frames.")
        clamped = float(np.clip(time_s, 0.0, self.duration_s if self.duration_s > 0 else 0.0))
        if self.fps > 0:
            frame_idx = int(round(clamped * self.fps))
        else:
            frame_idx = 0
        frame_idx = int(np.clip(frame_idx, 0, self.frame_count - 1))
        return frame_idx, self.frame_at_index(frame_idx, access_hint=access_hint)

    def clear_cache(self) -> None:
        self._frame_cache.clear()
        self._sequential_frame_idx = None

    def cache_info(self) -> dict[str, int | None]:
        return {
            "currsize": len(self._frame_cache),
            "maxsize": self._cache_max_frames,
            "sequential_frame_idx": self._sequential_frame_idx,
            "preview_width": self.preview_width,
            "preview_height": self.preview_height,
        }

    def _cache_get(self, frame_idx: int) -> np.ndarray | None:
        frame = self._frame_cache.get(frame_idx)
        if frame is None:
            return None
        self._frame_cache.move_to_end(frame_idx)
        return frame

    def _cache_put(self, frame_idx: int, frame_rgb: np.ndarray) -> None:
        self._frame_cache[frame_idx] = frame_rgb
        self._frame_cache.move_to_end(frame_idx)
        while len(self._frame_cache) > self._cache_max_frames:
            self._frame_cache.popitem(last=False)

    def _should_use_sequential_decode(self, target_idx: int, access_hint: _AccessHint) -> bool:
        if self._sequential_frame_idx is None:
            return False

        delta = target_idx - self._sequential_frame_idx
        if delta <= 0:
            return False

        if access_hint == "playback":
            return delta <= self._sequential_gap_limit
        if access_hint == "scrub":
            return delta <= self._scrub_seek_threshold
        if access_hint == "auto":
            return delta <= 4
        return False

    def _read_with_seek(self, frame_idx: int) -> np.ndarray:
        self._capture.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, frame = self._capture.read()
        if not ok or frame is None:
            raise ValueError(f"Could not read frame {frame_idx} from {self.path}")
        self._sequential_frame_idx = frame_idx
        return self._prepare_frame(frame)

    def _read_forward_to_index(self, target_idx: int) -> np.ndarray:
        if self._sequential_frame_idx is None or target_idx <= self._sequential_frame_idx:
            return self._read_with_seek(target_idx)

        next_idx = self._sequential_frame_idx + 1
        while next_idx < target_idx:
            ok = self._capture.grab()
            if not ok:
                raise ValueError(f"Could not skip frame {next_idx} from {self.path}")
            self._sequential_frame_idx = next_idx
            next_idx += 1

        ok, frame = self._capture.read()
        if not ok or frame is None:
            raise ValueError(f"Could not read frame {target_idx} from {self.path}")
        self._sequential_frame_idx = target_idx
        return self._prepare_frame(frame)

    def _prepare_frame(self, frame_bgr: np.ndarray) -> np.ndarray:
        if self.preview_scale < 1.0 and (
            frame_bgr.shape[1] != self.preview_width or frame_bgr.shape[0] != self.preview_height
        ):
            frame_bgr = cv2.resize(
                frame_bgr,
                (self.preview_width, self.preview_height),
                interpolation=cv2.INTER_AREA,
            )
        return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)


class HeatmapTruthSource:
    """H5-backed ground-truth heatmap renderer and time lookup service."""

    def __init__(
        self,
        path: Path,
        *,
        session_idx: int | None = None,
        group_idx: int | None = None,
        entry_idx: int | None = None,
        subsweep_idx: int | None = None,
        color_min: float = 0.0,
        color_max: float | None = 3000.0,
        fixed_levels: bool = True,
    ) -> None:
        from sparse_iq_heatmap_common import load_heatmap_record, resolve_selection_indices

        (
            resolved_session_idx,
            resolved_group_idx,
            resolved_entry_idx,
            resolved_subsweep_idx,
        ) = resolve_selection_indices(
            h5_path=path,
            session_idx=session_idx,
            group_idx=group_idx,
            entry_idx=entry_idx,
            subsweep_idx=subsweep_idx,
        )

        self.path = path
        self.record = load_heatmap_record(
            path,
            resolved_session_idx,
            resolved_group_idx,
            resolved_entry_idx,
        )
        self.subsweep_idx = resolved_subsweep_idx
        self.color_min = color_min
        self.color_max = color_max
        self.fixed_levels = fixed_levels
        self._fixed_color_level = self._resolve_fixed_color_level()

    @classmethod
    def from_loaded_record(
        cls,
        heatmap_record: object,
        *,
        path: Path,
        subsweep_idx: int,
        color_min: float = 0.0,
        color_max: float | None = 3000.0,
        fixed_levels: bool = True,
        resolved_fixed_color_level: float | None = None,
    ) -> HeatmapTruthSource:
        """Construct a truth source from a worker-loaded ``HeatmapRecord``."""

        instance = cls.__new__(cls)
        instance.path = path
        instance.record = heatmap_record
        instance.subsweep_idx = subsweep_idx
        instance.color_min = color_min
        instance.color_max = color_max
        instance.fixed_levels = fixed_levels
        if fixed_levels and resolved_fixed_color_level is not None:
            instance._fixed_color_level = resolved_fixed_color_level
        elif fixed_levels:
            instance._fixed_color_level = instance._resolve_fixed_color_level()
        else:
            instance._fixed_color_level = None
        return instance

    def close(self) -> None:
        self.record.close()

    def _resolve_fixed_color_level(self) -> float | None:
        from sparse_iq_heatmap_common import fixed_color_level

        if not self.fixed_levels:
            return None
        frame_indices = list(range(len(self.record.results)))
        return fixed_color_level(
            color_max=self.color_max,
            results=self.record.results,
            subsweep_idx=self.subsweep_idx,
            frame_indices=frame_indices,
        )

    @property
    def metadata(self) -> HeatmapTrack:
        return HeatmapTrack(
            path=str(self.path),
            session_idx=self.record.session_idx,
            group_idx=self.record.group_idx,
            entry_idx=self.record.entry_idx,
            subsweep_idx=self.subsweep_idx,
            duration_s=self.record.duration_s,
            fps=self.record.fps,
        )

    def update_render_settings(
        self, color_min: float, color_max: float | None, fixed_levels: bool
    ) -> None:
        self.color_min = color_min
        self.color_max = color_max
        self.fixed_levels = fixed_levels
        self._fixed_color_level = self._resolve_fixed_color_level()
        self.frame_at_index.cache_clear()

    @lru_cache(maxsize=256)
    def frame_at_index(self, frame_idx: int) -> np.ndarray:
        from sparse_iq_heatmap_common import heatmap_frame_rgb

        resolved_max = self._fixed_color_level if self.fixed_levels else self.color_max
        return heatmap_frame_rgb(
            self.record,
            subsweep_idx=self.subsweep_idx,
            frame_idx=frame_idx,
            color_min=self.color_min,
            color_max=resolved_max,
        )

    def frame_at_seconds(self, time_s: float) -> tuple[int, np.ndarray]:
        from sparse_iq_heatmap_common import frame_index_at_time

        frame_idx = frame_index_at_time(self.record, time_s)
        return frame_idx, self.frame_at_index(frame_idx)


class HeatmapPlotRenderer:
    """Reusable Matplotlib-backed heatmap plot renderer with axes."""

    _MIN_SOURCE_DIMENSION = 32
    _DEFAULT_SOURCE_FONT_SIZE_PT = 30.0
    _DEFAULT_SOURCE_TICK_LABEL_SIZE_PT = 22.0
    _DEFAULT_SOURCE_TICK_LENGTH_PT = 8.0
    _DEFAULT_SOURCE_AXIS_LINE_WIDTH_PT = 2.0
    _DEFAULT_SOURCE_LEFT_MARGIN_PX = 170.0
    _DEFAULT_SOURCE_RIGHT_MARGIN_PX = 35.0
    _DEFAULT_SOURCE_BOTTOM_MARGIN_PX = 115.0
    _DEFAULT_SOURCE_TOP_MARGIN_PX = 35.0
    _MIN_PLOT_BODY_SOURCE_WIDTH_PX = 32.0
    _MIN_PLOT_BODY_SOURCE_HEIGHT_PX = 32.0

    def __init__(
        self,
        heatmap_source: HeatmapTruthSource,
        *,
        output_size: tuple[int, int],
    ) -> None:
        from sparse_iq_heatmap_common import (
            color_max_for_dvm,
            distance_velocity_map,
            heatmap_axes,
            select_subsweep,
        )

        self.heatmap_source = heatmap_source
        self._distance_velocity_map = distance_velocity_map
        self._color_max_for_dvm = color_max_for_dvm

        subsweep = select_subsweep(heatmap_source.record, heatmap_source.subsweep_idx)
        axes = heatmap_axes(
            heatmap_source.record.metadata, heatmap_source.record.sensor_config, subsweep
        )
        distance_step = np.median(np.diff(axes.distances_m)) if len(axes.distances_m) > 1 else 1.0
        self.extent = (
            float(axes.distances_m[0] - 0.5 * distance_step),
            float(axes.distances_m[-1] + 0.5 * distance_step),
            float(axes.velocities_m_s[0] - 0.5 * axes.velocity_resolution),
            float(axes.velocities_m_s[-1] + 0.5 * axes.velocity_resolution),
        )

        self._figure: Figure | None = None
        self._canvas: FigureCanvasAgg | None = None
        self._ax = None
        self._image = None
        self._peak_artists: list[object] = []
        self._output_size = (0, 0)
        self._presentation: OverlayPlotPresentation | None = None
        self._rebuild_canvas(output_size)

    @classmethod
    def derive_presentation(
        cls,
        *,
        source_size: tuple[int, int],
        render_size: tuple[int, int],
    ) -> OverlayPlotPresentation:
        source_width = max(cls._MIN_SOURCE_DIMENSION, int(round(source_size[0])))
        source_height = max(cls._MIN_SOURCE_DIMENSION, int(round(source_size[1])))
        render_width = max(1, int(round(render_size[0])))
        render_height = max(1, int(round(render_size[1])))

        render_scale = max(
            0.01,
            min(
                render_width / source_width,
                render_height / source_height,
            ),
        )

        font_size_pt = max(0.1, cls._DEFAULT_SOURCE_FONT_SIZE_PT * render_scale)
        tick_label_size_pt = max(0.1, cls._DEFAULT_SOURCE_TICK_LABEL_SIZE_PT * render_scale)
        tick_length_pt = max(0.1, cls._DEFAULT_SOURCE_TICK_LENGTH_PT * render_scale)
        axis_line_width_pt = max(0.05, cls._DEFAULT_SOURCE_AXIS_LINE_WIDTH_PT * render_scale)
        left_margin_px, right_margin_px = cls._resolve_margin_pair(
            before_px=cls._DEFAULT_SOURCE_LEFT_MARGIN_PX * render_scale,
            after_px=cls._DEFAULT_SOURCE_RIGHT_MARGIN_PX * render_scale,
            size_px=render_width,
            min_body_px=min(
                render_width,
                max(1.0, cls._MIN_PLOT_BODY_SOURCE_WIDTH_PX * render_scale),
            ),
        )
        bottom_margin_px, top_margin_px = cls._resolve_margin_pair(
            before_px=cls._DEFAULT_SOURCE_BOTTOM_MARGIN_PX * render_scale,
            after_px=cls._DEFAULT_SOURCE_TOP_MARGIN_PX * render_scale,
            size_px=render_height,
            min_body_px=min(
                render_height,
                max(1.0, cls._MIN_PLOT_BODY_SOURCE_HEIGHT_PX * render_scale),
            ),
        )

        return OverlayPlotPresentation(
            source_size=(source_width, source_height),
            render_size=(render_width, render_height),
            font_size_pt=font_size_pt,
            tick_label_size_pt=tick_label_size_pt,
            tick_length_pt=tick_length_pt,
            axis_line_width_pt=axis_line_width_pt,
            left_margin=left_margin_px / render_width,
            right_margin=1.0 - (right_margin_px / render_width),
            bottom_margin=bottom_margin_px / render_height,
            top_margin=1.0 - (top_margin_px / render_height),
        )

    @staticmethod
    def _resolve_margin_pair(
        *,
        before_px: float,
        after_px: float,
        size_px: int,
        min_body_px: float,
    ) -> tuple[float, float]:
        if size_px <= 0:
            return 0.0, 0.0

        available_margin_px = max(0.0, float(size_px) - min_body_px)
        total_margin_px = max(0.0, before_px) + max(0.0, after_px)
        if total_margin_px <= 0.0 or available_margin_px <= 0.0:
            return 0.0, 0.0

        margin_scale = min(1.0, available_margin_px / total_margin_px)
        return before_px * margin_scale, after_px * margin_scale

    def presentation_for(
        self,
        *,
        output_size: tuple[int, int],
        source_size: tuple[int, int] | None = None,
    ) -> OverlayPlotPresentation:
        return self.derive_presentation(
            source_size=source_size or output_size,
            render_size=output_size,
        )

    def render_frame(
        self,
        frame_idx: int,
        *,
        output_size: tuple[int, int],
        source_size: tuple[int, int] | None = None,
        peak_distance_m: float | None = None,
        zero_velocity_m_s: float | None = None,
    ) -> np.ndarray:
        presentation = self.presentation_for(output_size=output_size, source_size=source_size)
        if output_size != self._output_size or presentation != self._presentation:
            self._rebuild_canvas(output_size, presentation)

        dvm = self._distance_velocity_map(
            self.heatmap_source.record.results[frame_idx].subframes[
                self.heatmap_source.subsweep_idx
            ]
        )
        self._image.set_data(dvm)
        if self.heatmap_source.fixed_levels:
            resolved_max = (
                self.heatmap_source._fixed_color_level
                if self.heatmap_source._fixed_color_level is not None
                else self.heatmap_source.color_max
            )
        else:
            resolved_max = (
                self.heatmap_source.color_max
                if self.heatmap_source.color_max is not None
                else self._color_max_for_dvm(dvm)
            )
        if resolved_max is None or resolved_max <= self.heatmap_source.color_min:
            resolved_max = self.heatmap_source.color_min + 1e-12
        self._image.set_clim(self.heatmap_source.color_min, resolved_max)
        self._draw_peak_marker(peak_distance_m, zero_velocity_m_s)

        self._canvas.draw()
        width, height = self._canvas.get_width_height()
        rgba = np.frombuffer(self._canvas.buffer_rgba(), dtype=np.uint8).reshape(height, width, 4)
        return np.ascontiguousarray(rgba[:, :, :3].copy())

    def _rebuild_canvas(
        self,
        output_size: tuple[int, int],
        presentation: OverlayPlotPresentation | None = None,
    ) -> None:
        if presentation is None:
            presentation = self.presentation_for(output_size=output_size)
        width, height = presentation.render_size
        self._output_size = presentation.render_size
        self._presentation = presentation
        dpi = 100.0
        figure = Figure(figsize=(width / dpi, height / dpi), dpi=dpi)
        canvas = FigureCanvasAgg(figure)
        ax = figure.add_subplot(111)
        initial = np.zeros((16, 16), dtype=np.float32)
        image = ax.imshow(
            initial,
            extent=self.extent,
            origin="lower",
            aspect="auto",
            interpolation="nearest",
            cmap="viridis",
            vmin=self.heatmap_source.color_min,
            vmax=max(
                self.heatmap_source.color_min + 1e-12, float(self.heatmap_source.color_max or 1.0)
            ),
        )
        ax.set_xlabel("Distance (m)")
        ax.set_ylabel("Velocity (m/s)")
        ax.xaxis.label.set_size(presentation.font_size_pt)
        ax.yaxis.label.set_size(presentation.font_size_pt)
        ax.tick_params(
            axis="both",
            which="both",
            labelsize=presentation.tick_label_size_pt,
            length=presentation.tick_length_pt,
            width=presentation.axis_line_width_pt,
            pad=max(1.0, presentation.tick_label_size_pt * 0.3),
        )
        for spine in ax.spines.values():
            spine.set_linewidth(presentation.axis_line_width_pt)
        figure.subplots_adjust(
            left=presentation.left_margin,
            right=presentation.right_margin,
            bottom=presentation.bottom_margin,
            top=presentation.top_margin,
        )

        self._figure = figure
        self._canvas = canvas
        self._ax = ax
        self._image = image
        self._peak_artists = []

    def _clear_peak_artists(self) -> None:
        if self._ax is None:
            self._peak_artists = []
            return
        for artist in self._peak_artists:
            artist.remove()
        self._peak_artists = []

    def _draw_peak_marker(
        self,
        peak_distance_m: float | None,
        zero_velocity_m_s: float | None,
    ) -> None:
        self._clear_peak_artists()
        if self._ax is None or peak_distance_m is None or zero_velocity_m_s is None:
            return
        line = self._ax.axvline(
            peak_distance_m,
            color="#ff4040",
            linewidth=1.5,
            alpha=0.9,
        )
        marker = self._ax.plot(
            peak_distance_m,
            zero_velocity_m_s,
            marker="o",
            color="#ffdc40",
            markersize=6,
            markeredgecolor="#202020",
            markeredgewidth=0.5,
        )[0]
        self._peak_artists = [line, marker]


def import_peak_distance_json_for_heatmap(
    json_path: Path,
    heatmap_source: HeatmapTruthSource | None = None,
) -> tuple[LoadedPeakDistanceDatasource, list[str]]:
    datasource = load_peak_distance_json(json_path)
    if heatmap_source is None:
        return datasource, []

    warnings = validate_peak_distance_import(
        datasource,
        heatmap_frame_count=len(heatmap_source.record.results),
        heatmap_duration_s=heatmap_source.record.duration_s,
        heatmap_path=heatmap_source.path,
        session_idx=heatmap_source.record.session_idx,
        group_idx=heatmap_source.record.group_idx,
        entry_idx=heatmap_source.record.entry_idx,
        subsweep_idx=heatmap_source.subsweep_idx,
        sensor_id=heatmap_source.record.sensor_id,
    )
    return datasource, warnings


def rectify_viewport(
    source_rgb: np.ndarray,
    corners: np.ndarray,
    output_size: tuple[int, int],
    *,
    interpolation: int = cv2.INTER_NEAREST,
) -> np.ndarray:
    width, height = output_size
    if width <= 0 or height <= 0:
        raise ValueError("Output viewport size must be positive.")

    src = np.asarray(corners, dtype=np.float32)
    if src.shape != (4, 2):
        raise ValueError("Viewport corners must have shape (4, 2).")

    dst = np.array(
        [
            [0.0, 0.0],
            [width - 1.0, 0.0],
            [width - 1.0, height - 1.0],
            [0.0, height - 1.0],
        ],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(source_rgb, transform, (width, height), flags=interpolation)


def scale_viewport_corners(
    corners: np.ndarray | list[list[float]],
    *,
    from_size: tuple[int, int],
    to_size: tuple[int, int],
) -> np.ndarray:
    src = np.asarray(corners, dtype=np.float32)
    if src.shape != (4, 2):
        raise ValueError("Viewport corners must have shape (4, 2).")

    from_width, from_height = from_size
    to_width, to_height = to_size
    if from_width <= 0 or from_height <= 0:
        raise ValueError("Source viewport size must be positive.")
    if to_width <= 0 or to_height <= 0:
        raise ValueError("Target viewport size must be positive.")

    scaled = src.copy()
    scaled[:, 0] *= to_width / from_width
    scaled[:, 1] *= to_height / from_height
    return scaled


@lru_cache(maxsize=1)
def _viridis_lookup_table_rgb() -> np.ndarray:
    values = np.arange(256, dtype=np.uint8).reshape(-1, 1)
    bgr = cv2.applyColorMap(values, cv2.COLORMAP_VIRIDIS)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).reshape(256, 3)


def _correct_viewport_rgb(
    frame_rgb: np.ndarray,
    settings: ViewportVisibilitySettings,
) -> np.ndarray:
    span = max(settings.high - settings.low, 1e-6)
    normalized = frame_rgb.astype(np.float32) / 255.0
    corrected = np.clip((normalized - settings.low) / span, 0.0, 1.0)
    return np.power(corrected, settings.gamma, dtype=np.float32)


def _viewport_luminance(corrected_rgb: np.ndarray) -> np.ndarray:
    return np.tensordot(
        corrected_rgb,
        np.array([0.2126, 0.7152, 0.0722], dtype=np.float32),
        axes=([-1], [0]),
    )


def apply_viewport_visibility(
    frame_rgb: np.ndarray,
    settings: ViewportVisibilitySettings,
) -> np.ndarray:
    if not settings.enabled:
        return frame_rgb

    corrected_rgb = _correct_viewport_rgb(frame_rgb, settings)
    if not settings.map_to_viridis:
        return np.ascontiguousarray(np.round(corrected_rgb * 255.0).astype(np.uint8))

    luminance = _viewport_luminance(corrected_rgb)
    mapped_idx = np.clip(np.round(luminance * 255.0), 0, 255).astype(np.uint8)
    return np.ascontiguousarray(_viridis_lookup_table_rgb()[mapped_idx])


def preprocess_frame(
    frame_rgb: np.ndarray,
    settings: PreprocessSettings,
) -> np.ndarray:
    processed = frame_rgb.astype(np.float32)
    if settings.blur_sigma > 0:
        processed = cv2.GaussianBlur(processed, (0, 0), settings.blur_sigma)
    if settings.downscale_factor != 1.0:
        new_width = max(1, int(round(processed.shape[1] * settings.downscale_factor)))
        new_height = max(1, int(round(processed.shape[0] * settings.downscale_factor)))
        processed = cv2.resize(processed, (new_width, new_height), interpolation=cv2.INTER_AREA)
    return processed


def normalize_frame_batch(batch: np.ndarray) -> np.ndarray:
    if batch.ndim != 4 or batch.shape[-1] != 3:
        raise ValueError("Expected frame batch with shape (N, H, W, 3).")
    mean = batch.mean(axis=(0, 1, 2), keepdims=True)
    std = batch.std(axis=(0, 1, 2), keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    return (batch - mean) / std


def correlation_for_lag(
    rectified_frames: np.ndarray,
    truth_frames: np.ndarray,
) -> float:
    rectified_normalized = normalize_frame_batch(rectified_frames)
    truth_normalized = normalize_frame_batch(truth_frames)
    rect_flat = rectified_normalized.reshape(rectified_normalized.shape[0], -1)
    truth_flat = truth_normalized.reshape(truth_normalized.shape[0], -1)
    numerators = np.sum(rect_flat * truth_flat, axis=1)
    denominators = np.linalg.norm(rect_flat, axis=1) * np.linalg.norm(truth_flat, axis=1)
    denominators = np.where(denominators < 1e-6, 1.0, denominators)
    return float(np.mean(numerators / denominators))


def compute_xcorr_diagnostics(
    camera_source: CameraVideoSource,
    heatmap_source: HeatmapTruthSource,
    session: AlignmentSession,
) -> tuple[np.ndarray, np.ndarray]:
    if not session.viewport.corners:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    lag_window_s = max(session.preprocess.lag_window_s, 0.0)
    if heatmap_source.record.fps <= 0:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    sample_count = session.preprocess.sample_count
    center_time_s = session.timeline.current_time_s
    base_truth_times = center_time_s + np.arange(sample_count) / max(
        heatmap_source.record.fps, 1.0
    )
    max_heatmap_time = heatmap_source.record.duration_s
    base_truth_times = base_truth_times[base_truth_times <= max_heatmap_time]
    if len(base_truth_times) == 0:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    step_s = 1.0 / max(camera_source.fps, heatmap_source.record.fps, 1.0)
    lag_values = np.arange(-lag_window_s, lag_window_s + 0.5 * step_s, step_s)
    corners = np.asarray(session.viewport.corners, dtype=np.float32)
    output_size = (session.viewport.output_width, session.viewport.output_height)

    truth_frames = np.stack(
        [
            preprocess_frame(
                heatmap_source.frame_at_seconds(float(truth_time))[1],
                session.preprocess,
            )
            for truth_time in base_truth_times
        ]
    )

    scores: list[float] = []
    for lag_s in lag_values:
        rectified_frames = []
        valid = True
        for truth_time in base_truth_times:
            camera_time = truth_time + session.timeline.offset_s + lag_s
            if camera_time < 0.0 or camera_time > camera_source.duration_s:
                valid = False
                break
            _, camera_frame = camera_source.frame_at_seconds(float(camera_time))
            rectified = rectify_viewport(camera_frame, corners, output_size)
            rectified_frames.append(preprocess_frame(rectified, session.preprocess))
        if not valid or not rectified_frames:
            scores.append(np.nan)
            continue
        score = correlation_for_lag(np.stack(rectified_frames), truth_frames)
        scores.append(score)

    return lag_values, np.array(scores, dtype=np.float64)


ResourceKind = Literal["camera", "radar_h5", "radar_peak", "leg2_mat"]
ResourceStatus = Literal["unloaded", "loaded", "missing", "invalid", "warning"]
ResourceAction = Literal[
    "load",
    "replace",
    "unload",
    "reload",
    "reveal",
    "inspect",
    "cancel",
]


@dataclass(frozen=True)
class ResourceSummary:
    """Scan-friendly summary for one heatmap alignment resource slot."""

    kind: ResourceKind
    display_name: str
    role: str
    status: ResourceStatus
    path: str
    color_hex: str | None
    color_muted: bool
    details: str
    messages: tuple[str, ...]
    actions: tuple[ResourceAction, ...]
    job_phase: ResourceJobPhase = "idle"
    job_target_filename: str = ""
    job_detail: str = ""
    job_cancellable: bool = False


ResourceJobPhase = Literal[
    "idle",
    "pending",
    "loading",
    "building",
    "waiting",
    "cancelling",
    "failed",
    "superseded",
]


@dataclass(frozen=True)
class ResourceJobPresentation:
    kind: ResourceKind
    phase: ResourceJobPhase = "idle"
    target_filename: str = ""
    detail: str = ""
    cancellable: bool = False


@dataclass(frozen=True)
class AlignmentResourceRuntime:
    """Runtime load state used when building resource summaries."""

    camera_loaded: bool = False
    radar_h5_loaded: bool = False
    radar_peak_loaded: bool = False
    leg2_loaded: bool = False
    peak_detected_count: int | None = None
    peak_measurement_count: int | None = None
    leg2_valid_segment_count: int | None = None
    leg2_sample_count: int | None = None
    reload_errors: tuple[tuple[ResourceKind, str], ...] = ()
    load_warnings: tuple[tuple[ResourceKind, str], ...] = ()
    resource_jobs: tuple[ResourceJobPresentation, ...] = ()


def elide_path_middle(path_text: str, max_chars: int) -> str:
    """Elide a path in the middle while preserving the filename when possible."""

    if max_chars < 4 or len(path_text) <= max_chars:
        return path_text

    path = Path(path_text)
    filename = path.name or path_text
    if not filename:
        return path_text[:max_chars]

    if path_text.endswith(filename):
        separator_index = len(path_text) - len(filename) - 1
        if separator_index >= 0 and path_text[separator_index] in "/\\":
            suffix = path_text[separator_index:]
        else:
            suffix = filename
    else:
        suffix = filename

    if len(suffix) >= max_chars:
        return f"...{suffix[-(max_chars - 3) :]}"

    ellipsis = "..."
    prefix_budget = max_chars - len(suffix) - len(ellipsis)
    if prefix_budget <= 0:
        return suffix[:max_chars]

    prefix = path_text[:prefix_budget]
    return f"{prefix}{ellipsis}{suffix}"


def _resource_job_presentation(
    kind: ResourceKind,
    runtime: AlignmentResourceRuntime,
) -> ResourceJobPresentation | None:
    for entry in runtime.resource_jobs:
        if entry.kind == kind:
            return entry
    return None


def _resource_messages(
    kind: ResourceKind,
    runtime: AlignmentResourceRuntime,
) -> tuple[str, ...]:
    messages = [text for key, text in runtime.reload_errors if key == kind]
    messages.extend(text for key, text in runtime.load_warnings if key == kind)
    job = _resource_job_presentation(kind, runtime)
    if job is not None and job.phase == "failed" and job.detail:
        messages = [job.detail, *messages]
    return tuple(messages)


def _resource_status(
    *,
    path_text: str,
    loaded: bool,
    messages: tuple[str, ...],
    job: ResourceJobPresentation | None = None,
) -> ResourceStatus:
    if job is not None and job.phase not in ("idle", "superseded"):
        if job.phase == "failed":
            return "invalid"
        if job.phase in ("pending", "loading", "building", "waiting", "cancelling"):
            return "warning" if loaded else "unloaded"
    if loaded:
        if messages:
            return "warning"
        return "loaded"
    if not path_text:
        return "unloaded"
    path = Path(path_text)
    if not path.exists():
        return "missing"
    if messages:
        return "invalid"
    return "unloaded"


def _resource_actions(
    *,
    status: ResourceStatus,
    path_text: str,
    can_unload: bool,
    messages: tuple[str, ...],
    job: ResourceJobPresentation | None = None,
) -> tuple[ResourceAction, ...]:
    actions: list[ResourceAction] = []
    if job is not None and job.phase in ("pending", "loading", "building", "waiting", "cancelling"):
        if job.cancellable:
            actions.append("cancel")
        if status in ("loaded", "warning"):
            actions.extend(("replace", "unload"))
        elif path_text:
            actions.append("reload")
        if path_text:
            actions.append("reveal")
        if messages:
            actions.append("inspect")
        deduped: list[ResourceAction] = []
        for action in actions:
            if action not in deduped:
                deduped.append(action)
        return tuple(deduped)

    if status in ("unloaded", "missing", "invalid"):
        actions.append("load")
    elif status in ("loaded", "warning"):
        actions.extend(("replace", "unload"))

    if path_text:
        if status in ("missing", "invalid", "unloaded") or status in ("loaded", "warning"):
            actions.append("reload")
        actions.append("reveal")

    if messages:
        actions.append("inspect")

    if can_unload and "unload" not in actions and status in ("loaded", "warning"):
        actions.append("unload")

    deduped = []
    for action in actions:
        if action not in deduped:
            deduped.append(action)
    return tuple(deduped)


def build_alignment_resource_summaries(
    session: AlignmentSession,
    runtime: AlignmentResourceRuntime,
) -> tuple[ResourceSummary, ...]:
    """Build fixed-slot resource summaries for the Resources window."""

    summaries: list[ResourceSummary] = []

    camera_path = session.camera_track.path
    camera_job = _resource_job_presentation("camera", runtime)
    camera_messages = _resource_messages("camera", runtime)
    camera_status = _resource_status(
        path_text=camera_path,
        loaded=runtime.camera_loaded,
        messages=camera_messages,
        job=camera_job,
    )
    camera_details = "No camera video loaded."
    if camera_job is not None and camera_job.phase not in ("idle", "superseded"):
        target = camera_job.target_filename or Path(camera_path).name
        if camera_job.phase == "building":
            camera_details = f"Building preview proxy for {target}..."
        elif camera_job.phase == "waiting":
            camera_details = camera_job.detail or f"Waiting for {target}..."
        elif camera_job.phase == "cancelling":
            camera_details = f"Cancelling load for {target}..."
        elif camera_job.phase == "failed":
            camera_details = camera_job.detail or f"Failed to load {target}."
        else:
            camera_details = camera_job.detail or f"Loading {target}..."
    elif runtime.camera_loaded:
        camera_details = (
            f"{session.camera_track.frame_count} frames, "
            f"{session.camera_track.fps:.3f} fps, "
            f"{session.camera_track.duration_s:.3f} s"
        )
    elif camera_path:
        camera_details = "Remembered camera path is not currently loaded."
    summaries.append(
        ResourceSummary(
            kind="camera",
            display_name="Camera Video",
            role="Primary",
            status=camera_status,
            path=camera_path,
            color_hex=CAMERA_TIMELINE_TRACK_COLOR_HEX,
            color_muted=not runtime.camera_loaded,
            details=camera_details,
            messages=camera_messages,
            actions=_resource_actions(
                status=camera_status,
                path_text=camera_path,
                can_unload=runtime.camera_loaded,
                messages=camera_messages,
                job=camera_job,
            ),
            job_phase=camera_job.phase if camera_job is not None else "idle",
            job_target_filename=camera_job.target_filename if camera_job is not None else "",
            job_detail=camera_job.detail if camera_job is not None else "",
            job_cancellable=camera_job.cancellable if camera_job is not None else False,
        )
    )

    h5_path = session.heatmap_track.path
    h5_job = _resource_job_presentation("radar_h5", runtime)
    h5_messages = _resource_messages("radar_h5", runtime)
    h5_status = _resource_status(
        path_text=h5_path,
        loaded=runtime.radar_h5_loaded,
        messages=h5_messages,
        job=h5_job,
    )
    h5_details = "No radar raw H5 recording loaded."
    if h5_job is not None and h5_job.phase not in ("idle", "superseded"):
        target = h5_job.target_filename or Path(h5_path).name
        if h5_job.phase == "cancelling":
            h5_details = f"Cancelling load for {target}..."
        elif h5_job.phase == "waiting":
            h5_details = h5_job.detail or f"Waiting for {target}..."
        elif h5_job.phase == "failed":
            h5_details = h5_job.detail or f"Failed to load {target}."
        else:
            h5_details = h5_job.detail or f"Loading {target}..."
    elif runtime.radar_h5_loaded:
        frame_count = max(
            1,
            int(round(session.heatmap_track.duration_s * max(session.heatmap_track.fps, 0.0))),
        )
        if session.heatmap_track.fps > 0:
            frame_count = int(round(session.heatmap_track.duration_s * session.heatmap_track.fps))
        h5_details = (
            f"{frame_count} frames, "
            f"{session.heatmap_track.fps:.3f} fps, "
            f"{session.heatmap_track.duration_s:.3f} s"
        )
    elif h5_path:
        h5_details = "Remembered H5 path is not currently loaded."
    summaries.append(
        ResourceSummary(
            kind="radar_h5",
            display_name="Radar Raw (H5)",
            role="Primary",
            status=h5_status,
            path=h5_path,
            color_hex=H5_TIMELINE_TRACK_COLOR_HEX,
            color_muted=not runtime.radar_h5_loaded,
            details=h5_details,
            messages=h5_messages,
            actions=_resource_actions(
                status=h5_status,
                path_text=h5_path,
                can_unload=runtime.radar_h5_loaded,
                messages=h5_messages,
                job=h5_job,
            ),
            job_phase=h5_job.phase if h5_job is not None else "idle",
            job_target_filename=h5_job.target_filename if h5_job is not None else "",
            job_detail=h5_job.detail if h5_job is not None else "",
            job_cancellable=h5_job.cancellable if h5_job is not None else False,
        )
    )

    peak_path = session.peak_distance_datasource.path
    peak_messages = _resource_messages("radar_peak", runtime)
    peak_status = _resource_status(
        path_text=peak_path,
        loaded=runtime.radar_peak_loaded,
        messages=peak_messages,
    )
    peak_details = "No radar peak JSON loaded."
    if runtime.radar_peak_loaded and runtime.peak_detected_count is not None:
        total = runtime.peak_measurement_count or 0
        peak_details = (
            f"{runtime.peak_detected_count}/{total} frames detected"
            if total
            else f"{runtime.peak_detected_count} detections"
        )
    elif peak_path:
        peak_details = "Remembered peak JSON path is not currently loaded."
    summaries.append(
        ResourceSummary(
            kind="radar_peak",
            display_name="Radar Peak (JSON)",
            role="Optional signal",
            status=peak_status,
            path=peak_path,
            color_hex=H5_TIMELINE_TRACK_COLOR_HEX,
            color_muted=not runtime.radar_peak_loaded,
            details=peak_details,
            messages=peak_messages,
            actions=_resource_actions(
                status=peak_status,
                path_text=peak_path,
                can_unload=runtime.radar_peak_loaded or bool(peak_path),
                messages=peak_messages,
            ),
        )
    )

    leg2_path = session.leg2_ultrasonic_datasource.path
    leg2_messages = _resource_messages("leg2_mat", runtime)
    leg2_status = _resource_status(
        path_text=leg2_path,
        loaded=runtime.leg2_loaded,
        messages=leg2_messages,
    )
    leg2_details = "No Leg2 MAT loaded."
    if runtime.leg2_loaded and runtime.leg2_sample_count is not None:
        valid = runtime.leg2_valid_segment_count or 0
        total = runtime.leg2_sample_count
        leg2_details = f"{total} samples, {valid}/{total} reliable segments"
    elif leg2_path:
        leg2_details = "Remembered Leg2 MAT path is not currently loaded."
    summaries.append(
        ResourceSummary(
            kind="leg2_mat",
            display_name="Leg2 MAT",
            role="Optional signal",
            status=leg2_status,
            path=leg2_path,
            color_hex=LEG2_TIMELINE_TRACK_COLOR_HEX,
            color_muted=not runtime.leg2_loaded,
            details=leg2_details,
            messages=leg2_messages,
            actions=_resource_actions(
                status=leg2_status,
                path_text=leg2_path,
                can_unload=runtime.leg2_loaded or bool(leg2_path),
                messages=leg2_messages,
            ),
        )
    )

    return tuple(summaries)
