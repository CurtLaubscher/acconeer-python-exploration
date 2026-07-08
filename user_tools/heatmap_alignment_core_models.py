"""Session models and shared constants for the heatmap alignment workbench."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np


SESSION_VERSION = 3

H5_TIMELINE_TRACK_COLOR_HEX = "#22c55e"
CAMERA_TIMELINE_TRACK_COLOR_HEX = "#f97316"
LEG2_TIMELINE_TRACK_COLOR_HEX = "#6366f1"
SIGNAL_PLOT_BACKGROUND_HEX = "#0f1720"
SIGNAL_PLOT_NO_DETECTION_ALPHA = 72
# Primary-segment opacity for segmented Signals curves (e.g. Leg2 valid flag). Change here only.
SIGNAL_PLOT_PRIMARY_SEGMENT_OPACITY = 0.7
SIGNAL_PLOT_PRIMARY_SEGMENT_ALPHA = int(round(255 * SIGNAL_PLOT_PRIMARY_SEGMENT_OPACITY))
TIMELINE_PLAYHEAD_COLOR_HEX = "#f8fafc"
# Shared styling for both Timeline and Signals playheads. Tune here only.
PLAYHEAD_ALPHA = int(round(255 * 0.87))  # ~13% transparency
PLAYHEAD_PEN_WIDTH = 2.5

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


@dataclass(frozen=True)
class TimelineH5DragSnapshot:
    range_start_s: float
    range_end_s: float
    current_time_s: float
    camera_offset_s: float
    leg2_offset_s: float


def timeline_h5_drag_affects_alignment(
    *,
    camera_duration_s: float,
    leg2_duration_s: float,
) -> bool:
    """Return whether dragging H5 can shift non-H5 offset-bearing tracks."""
    return camera_duration_s > 0.0 or leg2_duration_s > 0.0


def apply_timeline_h5_alignment_drag(
    snapshot: TimelineH5DragSnapshot,
    *,
    h5_desired_start_s: float,
) -> TimelineH5DragSnapshot:
    """Apply a coordinate-frame shift so the H5 bar appears at ``h5_desired_start_s``."""
    delta_s = h5_desired_start_s
    return TimelineH5DragSnapshot(
        range_start_s=snapshot.range_start_s - delta_s,
        range_end_s=snapshot.range_end_s - delta_s,
        current_time_s=snapshot.current_time_s - delta_s,
        camera_offset_s=snapshot.camera_offset_s + delta_s,
        leg2_offset_s=snapshot.leg2_offset_s + delta_s,
    )


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
class DetectionSignalSeries:
    detected_time_s: np.ndarray
    detected_distance_m: np.ndarray
    candidate_time_s: np.ndarray
    candidate_distance_m: np.ndarray


PeakDistanceSignalSeries = DetectionSignalSeries


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


def _filter_dataclass_fields(dc_type: type, raw: dict) -> dict:
    """Return only the keys from *raw* that are valid fields of *dc_type*."""
    import dataclasses
    valid = {f.name for f in dataclasses.fields(dc_type)}
    return {k: v for k, v in raw.items() if k in valid}


def _normalize_heatmap_track_keys(raw: dict) -> dict:
    """Rename legacy HeatmapTrack JSON keys to their current names."""
    renames = {
        "session_index": "session_idx",
        "group_index": "group_idx",
        "entry_index": "entry_idx",
        "subsweep_index": "subsweep_idx",
    }
    result = {}
    for k, v in raw.items():
        result[renames.get(k, k)] = v
    return result


@dataclass
class PeakSeriesSessionEntry:
    """Persisted peak-series metadata stored in alignment session JSON."""

    path: str = ""
    display_name: str = ""
    color: str = "#3b82f6"
    visible: bool = True
    heatmap_selected: bool = False


def _peak_series_entry_from_payload(raw: Any) -> PeakSeriesSessionEntry | None:
    if isinstance(raw, PeakSeriesSessionEntry):
        return raw
    if not isinstance(raw, dict):
        return None
    data = _filter_dataclass_fields(PeakSeriesSessionEntry, raw)
    entry = PeakSeriesSessionEntry(**data)
    if not entry.display_name and entry.path:
        entry.display_name = Path(entry.path).stem
    return entry


def _peak_series_entries_from_payload(raw_entries: Any) -> list[PeakSeriesSessionEntry]:
    if not isinstance(raw_entries, list):
        return []
    entries = []
    for raw_entry in raw_entries:
        entry = _peak_series_entry_from_payload(raw_entry)
        if entry is not None:
            entries.append(entry)
    return entries


def _peak_series_entries_to_json(
    entries: list[PeakSeriesSessionEntry | dict[str, Any]],
) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for raw_entry in entries:
        entry = _peak_series_entry_from_payload(raw_entry)
        if entry is None or not entry.path:
            continue
        payload.append(asdict(entry))
    return payload


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
    peak_series: list[PeakSeriesSessionEntry] = field(default_factory=list)
    leg2_ultrasonic_datasource: Leg2UltrasonicDatasourceSettings = field(
        default_factory=Leg2UltrasonicDatasourceSettings
    )
    signal_plot_view: SignalPlotViewSettings = field(default_factory=SignalPlotViewSettings)

    def to_json_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        view = payload["signal_plot_view"]
        view.pop("x_range_mode", None)
        view.pop("manual_x_range", None)
        if view["manual_y_range"] is not None:
            view["manual_y_range"] = list(view["manual_y_range"])
        payload["peak_series"] = _peak_series_entries_to_json(self.peak_series)
        return payload

    @classmethod
    def from_json_dict(cls, payload: dict[str, Any]) -> AlignmentSession:
        version = payload.get("version")

        if version == 1:
            # v1 -> v2: strip "visible" from datasource settings blocks.
            payload = dict(payload)
            if "peak_distance_datasource" in payload:
                peak_block = dict(payload["peak_distance_datasource"])
                peak_block.pop("visible", None)
                payload["peak_distance_datasource"] = peak_block
            if "leg2_ultrasonic_datasource" in payload:
                leg2_block = dict(payload["leg2_ultrasonic_datasource"])
                leg2_block.pop("visible", None)
                payload["leg2_ultrasonic_datasource"] = leg2_block
            payload["version"] = 2
            version = 2

        if version == 2:
            payload = dict(payload)
            old_peak = payload.pop("peak_distance_datasource", {})
            old_path = old_peak.get("path", "") if isinstance(old_peak, dict) else ""
            if old_path:
                from pathlib import Path
                payload["peak_series"] = [
                    PeakSeriesSessionEntry(
                        path=old_path,
                        display_name=Path(old_path).stem,
                        color="#3b82f6",
                        visible=True,
                        heatmap_selected=False,
                    )
                ]
            else:
                payload["peak_series"] = []
            payload["version"] = 3
            version = 3

        if version != SESSION_VERSION:
            raise ValueError(
                f"Unsupported alignment session version {version!r}; "
                f"expected {SESSION_VERSION}."
            )

        camera_track_raw = _filter_dataclass_fields(CameraTrack, payload.get("camera_track", {}))
        heatmap_track_raw = _filter_dataclass_fields(
            HeatmapTrack, _normalize_heatmap_track_keys(payload.get("heatmap_track", {}))
        )

        session = cls(
            version=version,
            camera_track=CameraTrack(**camera_track_raw),
            heatmap_track=HeatmapTrack(**heatmap_track_raw),
            viewport=ViewportGeometry(**payload.get("viewport", {})),
            render=RenderSettings(**payload.get("render", {})),
            preprocess=PreprocessSettings(**payload.get("preprocess", {})),
            timeline=TimelineState(**payload.get("timeline", {})),
            export_overlay=ExportOverlaySettings(**payload.get("export_overlay", {})),
            viewport_visibility=ViewportVisibilitySettings(
                **payload.get("viewport_visibility", {})
            ),
            peak_series=_peak_series_entries_from_payload(payload.get("peak_series", [])),
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

    y_range_mode = payload.get("y_range_mode", "auto")
    if y_range_mode not in ("auto", "manual"):
        raise ValueError(f"Unsupported signal plot y_range_mode {y_range_mode!r}.")

    manual_y_range = _optional_range_pair(payload.get("manual_y_range"))
    return SignalPlotViewSettings(
        x_range_mode="auto",
        y_range_mode=y_range_mode,
        manual_x_range=None,
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
    if heatmap_duration_s <= 0.0 and camera_duration_s <= 0.0 and leg2_duration_s <= 0.0:
        return 0.0, 60.0
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


def session_equivalent_for_pristine(
    left: AlignmentSession,
    right: AlignmentSession,
) -> bool:
    """Return whether two sessions match for pristine-workbench comparison."""

    return _json_values_equivalent_for_pristine(
        left.to_json_dict(),
        right.to_json_dict(),
    )


def _json_values_equivalent_for_pristine(left: object, right: object) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        if set(left.keys()) != set(right.keys()):
            return False
        return all(
            _json_values_equivalent_for_pristine(left[key], right[key]) for key in left
        )

    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return False
        return all(
            _json_values_equivalent_for_pristine(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )

    if isinstance(left, bool) or isinstance(right, bool):
        return left is right

    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-9)

    return left == right
