from __future__ import annotations


"""Camera/proxy resource job execution for heatmap alignment."""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
from heatmap_alignment_core_models import CameraTrack
from heatmap_alignment_resource_job_state import ProxyBuildError, ResourceJobError
from heatmap_alignment_video_proxy import (
    ProxyVideoResult,
    find_ffmpeg,
    probe_video,
    proxy_cache_path,
    scaled_video_dimensions,
)
from heatmap_alignment_viewport_processing import scale_viewport_corners


_PROXY_TEMP_SUFFIX = ".partial"


@dataclass(frozen=True)
class CameraResourceJobResult:
    source_path: Path
    proxy_result: ProxyVideoResult
    camera_track: CameraTrack


def _proxy_temp_path(proxy_path: Path) -> Path:
    return proxy_path.with_name(proxy_path.name + _PROXY_TEMP_SUFFIX)


def _cleanup_proxy_temp(proxy_path: Path) -> None:
    temp_path = _proxy_temp_path(proxy_path)
    if temp_path.exists():
        temp_path.unlink()


def _promote_proxy_temp(proxy_path: Path) -> None:
    temp_path = _proxy_temp_path(proxy_path)
    if not temp_path.exists():
        raise ProxyBuildError("Preview proxy output is missing.")
    proxy_path.parent.mkdir(parents=True, exist_ok=True)
    if proxy_path.exists():
        proxy_path.unlink()
    os.replace(temp_path, proxy_path)


def build_preview_proxy_video(
    source_path: Path,
    *,
    max_dimension: int = 1280,
    cache_root: Path | None = None,
    cancel_check: Callable[[], bool] | None = None,
    process_hook: Callable[[subprocess.Popen[str]], None] | None = None,
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

    ffmpeg_path = find_ffmpeg()
    if ffmpeg_path is None:
        raise ProxyBuildError("ffmpeg was not found; preview proxy generation is required.")

    proxy_path = proxy_cache_path(
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

    if cancel_check and cancel_check():
        raise ProxyBuildError("Preview proxy generation cancelled.")

    scaled_width, scaled_height = scaled_video_dimensions(
        source_probe.width,
        source_probe.height,
        max_dimension,
    )
    temp_path = _proxy_temp_path(proxy_path)
    _cleanup_proxy_temp(proxy_path)
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
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
        "-f",
        "mp4",
        str(temp_path),
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if process_hook is not None:
        process_hook(process)
    try:
        stdout, stderr = process.communicate()
    except Exception:
        process.kill()
        process.communicate()
        _cleanup_proxy_temp(proxy_path)
        raise
    if cancel_check and cancel_check():
        if process.poll() is None:
            process.kill()
            process.communicate()
        _cleanup_proxy_temp(proxy_path)
        raise ProxyBuildError("Preview proxy generation cancelled.")
    if process.returncode != 0:
        _cleanup_proxy_temp(proxy_path)
        detail = (stderr or stdout or "").strip()
        message = "Preview proxy generation failed."
        if detail:
            message = f"{message}\n\n{detail}"
        raise ProxyBuildError(message)
    try:
        _promote_proxy_temp(proxy_path)
    except OSError as exc:
        _cleanup_proxy_temp(proxy_path)
        raise ProxyBuildError(f"Could not finalize preview proxy: {exc}") from exc
    return ProxyVideoResult(
        source_path=source_path,
        display_path=proxy_path,
        source_probe=source_probe,
        proxy_path=proxy_path,
        state="proxy_built",
    )


def run_camera_resource_job(
    camera_path: Path,
    *,
    cache_root: Path | None = None,
    cancel_check: Callable[[], bool] | None = None,
    process_hook: Callable[[subprocess.Popen[str]], None] | None = None,
) -> CameraResourceJobResult:
    if cancel_check and cancel_check():
        raise ResourceJobError("Camera load cancelled.")
    proxy_result = build_preview_proxy_video(
        camera_path,
        cache_root=cache_root,
        cancel_check=cancel_check,
        process_hook=process_hook,
    )
    if proxy_result.state not in ("original", "proxy_reused", "proxy_built"):
        raise ProxyBuildError("Preview proxy is required for this camera video.")
    return CameraResourceJobResult(
        source_path=camera_path,
        proxy_result=proxy_result,
        camera_track=CameraTrack(
            path=str(camera_path),
            fps=proxy_result.source_probe.fps,
            duration_s=proxy_result.source_probe.duration_s,
            frame_count=proxy_result.source_probe.frame_count,
        ),
    )


def _corners_within_bounds(
    corners: np.ndarray,
    width: int,
    height: int,
) -> bool:
    if corners.shape != (4, 2):
        return False
    xs = corners[:, 0]
    ys = corners[:, 1]
    if np.any(xs < 0.0) or np.any(ys < 0.0):
        return False
    if np.any(xs > width - 1) or np.any(ys > height - 1):
        return False
    min_x = float(np.min(xs))
    max_x = float(np.max(xs))
    min_y = float(np.min(ys))
    max_y = float(np.max(ys))
    return (max_x - min_x) >= 8.0 and (max_y - min_y) >= 8.0


def _aspect_ratio(size: tuple[int, int]) -> float:
    width, height = size
    if width <= 0 or height <= 0:
        return 0.0
    return width / height


def resolve_replacement_viewport_corners(
    *,
    existing_corners: list[list[float]] | None,
    previous_native_size: tuple[int, int],
    replacement_native_size: tuple[int, int],
    aspect_ratio_tolerance: float = 0.02,
) -> list[list[float]] | None:
    """Preserve, scale, or reset viewport corners for a camera replacement."""

    if not existing_corners:
        return None

    corners = np.asarray(existing_corners, dtype=np.float32)
    prev_w, prev_h = previous_native_size
    new_w, new_h = replacement_native_size
    if prev_w <= 0 or prev_h <= 0 or new_w <= 0 or new_h <= 0:
        return None

    if (prev_w, prev_h) == (new_w, new_h):
        if _corners_within_bounds(corners, new_w, new_h):
            return corners.tolist()
        return None

    prev_ratio = _aspect_ratio((prev_w, prev_h))
    new_ratio = _aspect_ratio((new_w, new_h))
    if prev_ratio <= 0.0 or new_ratio <= 0.0:
        return None
    if abs(prev_ratio - new_ratio) > aspect_ratio_tolerance:
        return None

    scaled = scale_viewport_corners(
        corners,
        from_size=(prev_w, prev_h),
        to_size=(new_w, new_h),
    )
    if _corners_within_bounds(scaled, new_w, new_h):
        return scaled.tolist()
    return None


def replacement_viewport_needs_default_reset(
    *,
    previous_corners: list[list[float]] | None,
    previous_native_size: tuple[int, int],
    replacement_native_size: tuple[int, int],
) -> bool:
    """Return True when a replacement should reset viewport corners to defaults."""

    if not previous_corners or previous_native_size == (0, 0):
        return False
    return (
        resolve_replacement_viewport_corners(
            existing_corners=previous_corners,
            previous_native_size=previous_native_size,
            replacement_native_size=replacement_native_size,
        )
        is None
    )
