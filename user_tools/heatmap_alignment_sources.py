"""Camera and H5 source adapters for heatmap alignment."""

from __future__ import annotations

from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from heatmap_alignment_core_models import CameraTrack, HeatmapTrack
from heatmap_alignment_video_proxy import (
    ProxyVideoResult as ProxyVideoResult,
)
from heatmap_alignment_video_proxy import (
    VideoProbe as VideoProbe,
)
from heatmap_alignment_video_proxy import (
    default_proxy_cache_root,
    find_ffmpeg,
    proxy_cache_path,
    resolve_ffmpeg_path,
    scaled_video_dimensions,
)
from heatmap_alignment_video_proxy import (
    prepare_proxy_video as prepare_proxy_video,
)
from heatmap_alignment_video_proxy import (
    probe_video as probe_video,
)


_default_proxy_cache_root = default_proxy_cache_root
_find_ffmpeg = find_ffmpeg
_proxy_cache_path = proxy_cache_path
_resolve_ffmpeg_path = resolve_ffmpeg_path
_scaled_video_dimensions = scaled_video_dimensions


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
