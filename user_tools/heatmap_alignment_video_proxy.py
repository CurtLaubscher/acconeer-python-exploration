from __future__ import annotations


"""Video probing and preview proxy helpers for heatmap alignment."""

import os
import shutil
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal

import cv2


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

    ffmpeg_path = find_ffmpeg()
    if ffmpeg_path is None:
        raise RuntimeError("ffmpeg was not found; preview proxy generation is required.")

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

    from heatmap_alignment_camera_resource_job import build_preview_proxy_video

    return build_preview_proxy_video(
        source_path,
        max_dimension=max_dimension,
        cache_root=cache_root,
    )


def scaled_video_dimensions(width: int, height: int, max_dimension: int) -> tuple[int, int]:
    largest_dimension = max(width, height, 1)
    scale = min(1.0, max_dimension / largest_dimension)
    scaled_width = max(2, int(round(width * scale)))
    scaled_height = max(2, int(round(height * scale)))
    if scaled_width % 2 != 0:
        scaled_width -= 1
    if scaled_height % 2 != 0:
        scaled_height -= 1
    return max(2, scaled_width), max(2, scaled_height)


def proxy_cache_path(
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
    root = default_proxy_cache_root() if cache_root is None else cache_root
    return root / f"{stem}_{digest}_proxy_{max_dimension}.mp4"


def default_proxy_cache_root() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Acconeer" / "HeatmapAlignmentWorkbench" / "proxy-cache"
    return Path(tempfile.gettempdir()) / "Acconeer" / "HeatmapAlignmentWorkbench" / "proxy-cache"


def resolve_ffmpeg_path(path: Path | None) -> str | None:
    if path is None:
        return None
    if path.is_dir():
        path = path / "ffmpeg.exe"
    return str(path) if path.exists() else None


def find_ffmpeg() -> str | None:
    for candidate in (
        os.getenv("FFMPEG_PATH"),
        r"C:\Users\claub\Documents\Portable Programs\ffmpeg-master-latest-win64-gpl-shared\bin",
    ):
        if candidate:
            resolved = resolve_ffmpeg_path(Path(candidate))
            if resolved is not None:
                return resolved
    return shutil.which("ffmpeg")
