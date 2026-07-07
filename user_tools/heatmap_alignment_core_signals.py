"""Signal datasource import and plot-series helpers for heatmap alignment."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
from heatmap_alignment_core_models import (
    DetectionSignalSeries,
    Leg2MatImportError,
    Leg2StanceIntervals,
    Leg2UltrasonicSignalKind,
    Leg2UltrasonicSignalSeries,
    LoadedLeg2UltrasonicDatasource,
)
from scipy.io import loadmat
from sparse_iq_peak_distance_core import STATUS_DETECTED, FrameDetectionMeasurement


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


def _plottable_candidate_distance_m(measurement: FrameDetectionMeasurement) -> float | None:
    value = measurement.candidate_distance_m
    if not math.isfinite(value):
        return None
    return float(value)


def build_peak_distance_signal_series(
    measurements: tuple[FrameDetectionMeasurement, ...],
) -> DetectionSignalSeries:
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

    return DetectionSignalSeries(
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
    series: DetectionSignalSeries,
    *,
    x_min_s: float,
    x_max_s: float,
    leg2_series: Leg2UltrasonicSignalSeries | None = None,
) -> tuple[float, float] | None:
    return visible_signal_y_range_for_series(
        (series,),
        x_min_s=x_min_s,
        x_max_s=x_max_s,
        leg2_series=leg2_series,
    )


def visible_signal_y_range_for_series(
    series_list: tuple[DetectionSignalSeries, ...],
    *,
    x_min_s: float,
    x_max_s: float,
    leg2_series: Leg2UltrasonicSignalSeries | None = None,
) -> tuple[float, float] | None:
    if x_max_s < x_min_s:
        x_min_s, x_max_s = x_max_s, x_min_s

    time_distance_pairs: list[tuple[np.ndarray, np.ndarray]] = []
    for series in series_list:
        time_distance_pairs.extend(
            (
                (series.detected_time_s, series.detected_distance_m),
                (series.candidate_time_s, series.candidate_distance_m),
            )
        )
    if leg2_series is not None:
        time_distance_pairs.extend(
            (
                (leg2_series.primary_time_s, leg2_series.primary_distance_m),
                (leg2_series.faded_time_s, leg2_series.faded_distance_m),
            )
        )

    visible_values = _visible_distance_values_in_x_range(
        tuple(time_distance_pairs),
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
