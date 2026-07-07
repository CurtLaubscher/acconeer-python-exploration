"""Viewport rectification, visibility transforms, and xcorr diagnostics."""

from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np
from heatmap_alignment_core_models import (
    AlignmentSession,
    PreprocessSettings,
    ViewportVisibilitySettings,
)
from heatmap_alignment_sources import CameraVideoSource, HeatmapTruthSource


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


# ---------------------------------------------------------------------------
# Session load reconciliation helpers
#
# New resource types MUST register a reconcile slot in heatmap_alignment_gui.py
# _reconcile_session_load(). See OpenSpec change: session-load-responsiveness.
# ---------------------------------------------------------------------------
