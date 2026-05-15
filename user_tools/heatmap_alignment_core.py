from __future__ import annotations

"""Core models and services for the heatmap alignment GUI.

This module is intended to be used from the Hatch-managed `app` environment
because it depends on the same runtime surface as the GUI, including OpenCV.
"""

import json
import os
import shutil
import subprocess
import tempfile
from hashlib import sha256
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any
from typing import Literal

import cv2
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np


ARTIFACT_VERSION = 1


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


@dataclass
class AlignmentSession:
    """Serializable state for one alignment session."""

    version: int = ARTIFACT_VERSION
    camera_track: CameraTrack = field(default_factory=CameraTrack)
    heatmap_track: HeatmapTrack = field(default_factory=HeatmapTrack)
    viewport: ViewportGeometry = field(default_factory=ViewportGeometry)
    render: RenderSettings = field(default_factory=RenderSettings)
    preprocess: PreprocessSettings = field(default_factory=PreprocessSettings)
    timeline: TimelineState = field(default_factory=TimelineState)
    export_overlay: ExportOverlaySettings = field(default_factory=ExportOverlaySettings)
    viewport_visibility: ViewportVisibilitySettings = field(default_factory=ViewportVisibilitySettings)

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json_dict(cls, payload: dict[str, Any]) -> AlignmentSession:
        version = payload.get("version")
        if version != ARTIFACT_VERSION:
            raise ValueError(
                f"Unsupported alignment artifact version {version!r}; "
                f"expected {ARTIFACT_VERSION}."
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
            viewport_visibility=ViewportVisibilitySettings(**payload.get("viewport_visibility", {})),
        )
        validate_alignment_session(session)
        return session


def save_alignment_artifact(session: AlignmentSession, path: Path) -> None:
    validate_alignment_session(session, allow_missing_sources=True)
    path.write_text(json.dumps(session.to_json_dict(), indent=2), encoding="utf-8")


def load_alignment_artifact(path: Path) -> AlignmentSession:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed alignment artifact: {exc}") from exc

    return AlignmentSession.from_json_dict(payload)


def validate_alignment_session(
    session: AlignmentSession,
    *,
    allow_missing_sources: bool = False,
) -> None:
    if session.version != ARTIFACT_VERSION:
        raise ValueError(f"Unsupported artifact version {session.version}.")

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
        return ProxyVideoResult(
            source_path=source_path,
            display_path=source_path,
            source_probe=source_probe,
            proxy_path=None,
            state="proxy_unavailable",
        )

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

    proxy_path.parent.mkdir(parents=True, exist_ok=True)
    scaled_width, scaled_height = _scaled_video_dimensions(
        source_probe.width,
        source_probe.height,
        max_dimension,
    )
    try:
        subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(source_path),
                "-vf",
                f"scale={scaled_width}:{scaled_height}",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                str(proxy_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return ProxyVideoResult(
            source_path=source_path,
            display_path=source_path,
            source_probe=source_probe,
            proxy_path=None,
            state="proxy_unavailable",
        )
    return ProxyVideoResult(
        source_path=source_path,
        display_path=proxy_path,
        source_probe=source_probe,
        proxy_path=proxy_path,
        state="proxy_built",
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
        if (
            self.preview_scale < 1.0
            and (
                frame_bgr.shape[1] != self.preview_width
                or frame_bgr.shape[0] != self.preview_height
            )
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

    def update_render_settings(self, color_min: float, color_max: float | None, fixed_levels: bool) -> None:
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

    def __init__(
        self,
        heatmap_source: HeatmapTruthSource,
        *,
        output_size: tuple[int, int],
    ) -> None:
        from sparse_iq_heatmap_common import color_max_for_dvm
        from sparse_iq_heatmap_common import distance_velocity_map
        from sparse_iq_heatmap_common import heatmap_axes
        from sparse_iq_heatmap_common import select_subsweep

        self.heatmap_source = heatmap_source
        self._distance_velocity_map = distance_velocity_map
        self._color_max_for_dvm = color_max_for_dvm

        subsweep = select_subsweep(heatmap_source.record, heatmap_source.subsweep_idx)
        axes = heatmap_axes(heatmap_source.record.metadata, heatmap_source.record.sensor_config, subsweep)
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
        self._output_size = (0, 0)
        self._rebuild_canvas(output_size)

    def render_frame(self, frame_idx: int, *, output_size: tuple[int, int]) -> np.ndarray:
        if output_size != self._output_size:
            self._rebuild_canvas(output_size)

        dvm = self._distance_velocity_map(
            self.heatmap_source.record.results[frame_idx].subframes[self.heatmap_source.subsweep_idx]
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

        self._canvas.draw()
        width, height = self._canvas.get_width_height()
        rgba = np.frombuffer(self._canvas.buffer_rgba(), dtype=np.uint8).reshape(height, width, 4)
        return np.ascontiguousarray(rgba[:, :, :3].copy())

    def _rebuild_canvas(self, output_size: tuple[int, int]) -> None:
        width, height = output_size
        width = max(32, int(width))
        height = max(32, int(height))
        self._output_size = (width, height)
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
            vmax=max(self.heatmap_source.color_min + 1e-12, float(self.heatmap_source.color_max or 1.0)),
        )
        ax.set_xlabel("Distance (m)")
        ax.set_ylabel("Velocity (m/s)")
        ax.tick_params(labelsize=8)
        figure.subplots_adjust(left=0.20, right=0.98, bottom=0.22, top=0.98)

        self._figure = figure
        self._canvas = canvas
        self._ax = ax
        self._image = image


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
    base_truth_times = center_time_s + np.arange(sample_count) / max(heatmap_source.record.fps, 1.0)
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
