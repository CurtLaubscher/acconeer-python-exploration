"""Rendered heatmap and detection-ratio presentation helpers."""

from __future__ import annotations

import numpy as np
from heatmap_alignment_core_models import OverlayPlotPresentation
from heatmap_alignment_sources import HeatmapTruthSource
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from sparse_iq_heatmap_common import axis_bin_edge_extent, finite_axis_bin_width


def _build_detection_ratio_lut() -> np.ndarray:
    """Build a 256-entry uint8 RGB LUT: Blues_r below ratio=1.0, YlOrRd above.

    Index 0 = ratio 0.0, index 128 = ratio 1.0 (threshold), index 255 = ratio ~2.0+.
    The warm half samples YlOrRd only up to 0.60 (yellow→orange) to avoid the dark-red tail.
    Returns shape (256, 3) uint8.
    """
    import matplotlib.pyplot as plt

    n = 256
    half = n // 2
    cool = plt.get_cmap("Blues_r")(np.linspace(0.15, 0.85, half))[:, :3]
    warm = plt.get_cmap("YlOrRd")(np.linspace(0.05, 0.45, n - half))[:, :3]
    colors = np.vstack((cool, warm))
    return (colors * 255).clip(0, 255).astype(np.uint8)


# Module-level LUT — built once on first use.
_DETECTION_RATIO_LUT: np.ndarray | None = None


def _get_detection_ratio_lut() -> np.ndarray:
    global _DETECTION_RATIO_LUT
    if _DETECTION_RATIO_LUT is None:
        _DETECTION_RATIO_LUT = _build_detection_ratio_lut()
    return _DETECTION_RATIO_LUT


def detection_ratio_to_rgb(
    detection_ratio: np.ndarray,
    *,
    ratio_max: float = 2.0,
) -> np.ndarray:
    """Map a 1-D detection ratio array to RGB uint8 pixels.

    Values at 0.0 → deep blue, at 1.0 → transition, at ratio_max+ → bright yellow.
    Returns shape (n, 3) uint8.
    """
    lut = _get_detection_ratio_lut()
    clipped = np.clip(detection_ratio / max(ratio_max, 1e-12), 0.0, 1.0)
    indices = (clipped * 255).astype(np.intp)
    return lut[indices]


def detection_ratio_strip_rgb(
    detection_ratio: np.ndarray,
    width: int,
) -> np.ndarray:
    """Return a (1, width, 3) uint8 row mapping detection_ratio bins across width pixels."""
    n_bins = len(detection_ratio)
    bin_colors = detection_ratio_to_rgb(detection_ratio)  # (n_bins, 3)
    col_indices = (np.arange(width) * n_bins / max(width, 1)).astype(np.intp)
    col_indices = np.clip(col_indices, 0, n_bins - 1)
    return bin_colors[col_indices][np.newaxis, :, :]  # (1, width, 3)


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

    _STRIP_HEIGHT_RATIO = 0.08  # fraction of total figure height for the detection strip

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
        x_min, x_max = axis_bin_edge_extent(axes.distances_m)
        y_min, y_max = axis_bin_edge_extent(
            axes.velocities_m_s,
            bin_width=axes.velocity_resolution,
            fallback_width=finite_axis_bin_width(axes.velocities_m_s),
        )
        self.extent = (
            x_min,
            x_max,
            y_min,
            y_max,
        )
        self._distances_m = axes.distances_m

        self._figure: Figure | None = None
        self._canvas: FigureCanvasAgg | None = None
        self._ax = None
        self._strip_ax = None
        self._image = None
        self._strip_mesh = None
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
        detection_ratio: np.ndarray | None = None,
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
        self._draw_detection_strip(detection_ratio)

        self._canvas.draw()
        width, height = self._canvas.get_width_height()
        rgba = np.frombuffer(self._canvas.buffer_rgba(), dtype=np.uint8).reshape(height, width, 4)
        return np.ascontiguousarray(rgba[:, :, :3].copy())

    def _rebuild_canvas(
        self,
        output_size: tuple[int, int],
        presentation: OverlayPlotPresentation | None = None,
    ) -> None:
        import matplotlib.gridspec as mgridspec

        if presentation is None:
            presentation = self.presentation_for(output_size=output_size)
        width, height = presentation.render_size
        self._output_size = presentation.render_size
        self._presentation = presentation
        dpi = 100.0
        figure = Figure(figsize=(width / dpi, height / dpi), dpi=dpi)
        canvas = FigureCanvasAgg(figure)

        strip_ratio = self._STRIP_HEIGHT_RATIO
        heatmap_ratio = 1.0 - strip_ratio
        gs = mgridspec.GridSpec(
            2, 1,
            figure=figure,
            height_ratios=[strip_ratio, heatmap_ratio],
            hspace=0.0,
        )
        strip_ax = figure.add_subplot(gs[0])
        ax = figure.add_subplot(gs[1], sharex=strip_ax)

        strip_ax.set_yticks([])
        strip_ax.set_xticks([])
        for spine in strip_ax.spines.values():
            spine.set_visible(False)
        strip_ax.set_facecolor("#1a1a2e")

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
            hspace=0.02,
        )

        self._figure = figure
        self._canvas = canvas
        self._ax = ax
        self._strip_ax = strip_ax
        self._image = image
        self._strip_mesh = None
        self._peak_artists = []

    @staticmethod
    def _detection_ratio_colormap():
        """Return the shared threshold-split colormap as a matplotlib ListedColormap."""
        import matplotlib.colors as mcolors

        lut = _get_detection_ratio_lut()  # (256, 3) uint8
        colors_f = lut.astype(np.float64) / 255.0
        # Append alpha=1 column so ListedColormap receives RGBA.
        rgba = np.hstack([colors_f, np.ones((len(colors_f), 1))])
        return mcolors.ListedColormap(rgba, name="detection_ratio_split")

    def _draw_detection_strip(self, detection_ratio: np.ndarray | None) -> None:
        if self._strip_ax is None:
            return
        if self._strip_mesh is not None:
            self._strip_mesh.remove()
            self._strip_mesh = None

        self._strip_ax.set_facecolor("#1a1a2e")
        if detection_ratio is None or len(detection_ratio) == 0:
            return

        distances = self._distances_m
        if len(distances) != len(detection_ratio):
            return

        dist_step = finite_axis_bin_width(distances)
        x_edges = np.concatenate([distances - 0.5 * dist_step, [distances[-1] + 0.5 * dist_step]])
        y_edges = np.array([0.0, 1.0])
        ratio_row = detection_ratio[np.newaxis, :]

        cmap = self._detection_ratio_colormap()
        import matplotlib.colors as mcolors
        norm = mcolors.TwoSlopeNorm(vcenter=1.0, vmin=min(0.0, float(ratio_row.min())), vmax=max(2.0, float(ratio_row.max())))
        mesh = self._strip_ax.pcolormesh(
            x_edges, y_edges, ratio_row,
            cmap=cmap,
            norm=norm,
            shading="flat",
        )
        self._strip_mesh = mesh
        self._strip_ax.set_xlim(self.extent[0], self.extent[1])
        self._strip_ax.set_ylim(0.0, 1.0)

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
        if self._ax is None or peak_distance_m is None:
            return
        # Draw downward triangle at peak x, at top of velocity axis
        y_top = self.extent[3]  # vel_max
        marker = self._ax.plot(
            peak_distance_m,
            y_top,
            marker="v",
            color="#ff4040",
            markersize=8,
            markeredgecolor="#ffffff",
            markeredgewidth=0.5,
            clip_on=False,
            zorder=10,
            transform=self._ax.transData,
        )[0]
        font_size = 7
        if self._presentation is not None:
            font_size = max(6, min(10, self._presentation.tick_label_size_pt))
        label = self._ax.annotate(
            "{:.3f} m".format(peak_distance_m),
            xy=(peak_distance_m, y_top),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=font_size,
            color="#ff4040",
            clip_on=True,
            zorder=10,
        )
        self._peak_artists = [marker, label]
