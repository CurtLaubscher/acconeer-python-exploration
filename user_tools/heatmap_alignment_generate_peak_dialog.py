from __future__ import annotations


"""Peak-series generation dialog for the heatmap alignment workbench."""

from heatmap_peak_distance_resource import default_generated_name
from sparse_iq_peak_distance_core import (
    ALGORITHM_LABEL_DISTANCE_NORMALIZED,
    ALGORITHM_LABEL_SUM_VELOCITY,
    ALGORITHM_LABEL_ZERO_VELOCITY_SLICE,
    DEFAULT_DIST_NORM_REFERENCE_DISTANCE_M,
    DEFAULT_DIST_NORM_THRESHOLD_MAX,
    DEFAULT_DIST_NORM_THRESHOLD_MIN,
    DEFAULT_PEAK_THRESHOLD,
    PEAK_EXTRACTION_METHOD_DISTANCE_NORMALIZED,
    PEAK_EXTRACTION_METHOD_SUM_VELOCITY,
    PEAK_EXTRACTION_METHOD_ZERO_VELOCITY_SLICE,
    PEAK_SELECTION_METHOD_NEAREST_ISLAND,
    PEAK_SELECTION_METHOD_STRONGEST_PEAK,
    SELECTION_LABEL_NEAREST_ISLAND,
    SELECTION_LABEL_STRONGEST_PEAK,
)

from PySide6 import QtWidgets


class GenerateDetectionSeriesDialog(QtWidgets.QDialog):
    """Dialog for configuring a new generated detection series."""

    def __init__(
        self,
        parent=None,
        *,
        default_threshold: float = DEFAULT_PEAK_THRESHOLD,
        distance_bin_width_m: float = 0.0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Generate Detection Series")
        self._distance_bin_width_m = max(distance_bin_width_m, 0.0)
        layout = QtWidgets.QFormLayout(self)
        self._algo_combo = QtWidgets.QComboBox()
        self._algo_combo.addItem(ALGORITHM_LABEL_SUM_VELOCITY, PEAK_EXTRACTION_METHOD_SUM_VELOCITY)
        self._algo_combo.addItem(
            ALGORITHM_LABEL_ZERO_VELOCITY_SLICE, PEAK_EXTRACTION_METHOD_ZERO_VELOCITY_SLICE
        )
        self._algo_combo.addItem(
            ALGORITHM_LABEL_DISTANCE_NORMALIZED, PEAK_EXTRACTION_METHOD_DISTANCE_NORMALIZED
        )
        layout.addRow("Algorithm:", self._algo_combo)

        self._selection_combo = QtWidgets.QComboBox()
        self._selection_combo.addItem(
            SELECTION_LABEL_STRONGEST_PEAK, PEAK_SELECTION_METHOD_STRONGEST_PEAK
        )
        self._selection_combo.addItem(
            SELECTION_LABEL_NEAREST_ISLAND, PEAK_SELECTION_METHOD_NEAREST_ISLAND
        )
        layout.addRow("Selection:", self._selection_combo)

        self._threshold_spin = QtWidgets.QDoubleSpinBox()
        self._threshold_spin.setRange(0.0, 1_000_000.0)
        self._threshold_spin.setDecimals(1)
        self._threshold_spin.setValue(default_threshold)
        self._threshold_label = QtWidgets.QLabel("Threshold:")
        layout.addRow(self._threshold_label, self._threshold_spin)

        self._threshold_max_spin = QtWidgets.QDoubleSpinBox()
        self._threshold_max_spin.setRange(1.0, 1_000_000.0)
        self._threshold_max_spin.setDecimals(1)
        self._threshold_max_spin.setValue(DEFAULT_DIST_NORM_THRESHOLD_MAX)
        self._threshold_max_label = QtWidgets.QLabel("Threshold max:")
        layout.addRow(self._threshold_max_label, self._threshold_max_spin)

        self._threshold_min_spin = QtWidgets.QDoubleSpinBox()
        self._threshold_min_spin.setRange(1.0, 1_000_000.0)
        self._threshold_min_spin.setDecimals(1)
        self._threshold_min_spin.setValue(DEFAULT_DIST_NORM_THRESHOLD_MIN)
        self._threshold_min_label = QtWidgets.QLabel("Threshold min:")
        layout.addRow(self._threshold_min_label, self._threshold_min_spin)

        self._reference_distance_spin = QtWidgets.QDoubleSpinBox()
        self._reference_distance_spin.setRange(0.01, 100.0)
        self._reference_distance_spin.setDecimals(3)
        self._reference_distance_spin.setSingleStep(0.05)
        self._reference_distance_spin.setValue(DEFAULT_DIST_NORM_REFERENCE_DISTANCE_M)
        self._reference_distance_label = QtWidgets.QLabel("Reference distance (m):")
        layout.addRow(self._reference_distance_label, self._reference_distance_spin)

        bridge_step_m = self._distance_bin_width_m if self._distance_bin_width_m > 0 else 0.001
        self._bridge_gap_spin = QtWidgets.QDoubleSpinBox()
        self._bridge_gap_spin.setRange(0.0, 100.0)
        self._bridge_gap_spin.setDecimals(6)
        self._bridge_gap_spin.setSingleStep(bridge_step_m)
        self._bridge_gap_spin.setValue(bridge_step_m)
        self._bridge_gap_label = QtWidgets.QLabel("Bridge gap (m):")
        layout.addRow(self._bridge_gap_label, self._bridge_gap_spin)

        self._name_edit = QtWidgets.QLineEdit()
        layout.addRow("Name:", self._name_edit)

        self._algo_combo.currentIndexChanged.connect(self._on_algo_changed)
        self._selection_combo.currentIndexChanged.connect(self._on_selection_changed)
        self._threshold_spin.valueChanged.connect(self._update_default_name)
        self._threshold_max_spin.valueChanged.connect(self._update_default_name)
        self._threshold_min_spin.valueChanged.connect(self._update_default_name)
        self._reference_distance_spin.valueChanged.connect(self._update_default_name)
        self._bridge_gap_spin.valueChanged.connect(self._update_default_name)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self._on_algo_changed()
        self._on_selection_changed()

    def _on_algo_changed(self) -> None:
        is_dist_norm = self._algo_combo.currentData() == PEAK_EXTRACTION_METHOD_DISTANCE_NORMALIZED
        self._threshold_label.setVisible(not is_dist_norm)
        self._threshold_spin.setVisible(not is_dist_norm)
        self._threshold_max_label.setVisible(is_dist_norm)
        self._threshold_max_spin.setVisible(is_dist_norm)
        self._threshold_min_label.setVisible(is_dist_norm)
        self._threshold_min_spin.setVisible(is_dist_norm)
        self._reference_distance_label.setVisible(is_dist_norm)
        self._reference_distance_spin.setVisible(is_dist_norm)
        self._update_default_name()

    def _on_selection_changed(self) -> None:
        is_nearest_island = (
            self._selection_combo.currentData() == PEAK_SELECTION_METHOD_NEAREST_ISLAND
        )
        self._bridge_gap_label.setVisible(is_nearest_island)
        self._bridge_gap_spin.setVisible(is_nearest_island)
        self._update_default_name()

    def _update_default_name(self) -> None:
        algo_id = self._algo_combo.currentData()
        thresh = self._threshold_spin.value()
        ref = self._reference_distance_spin.value()
        selection_method = self._selection_combo.currentData()
        self._name_edit.setPlaceholderText(
            default_generated_name(
                algo_id,
                thresh,
                reference_distance_m=ref,
                selection_method=selection_method,
            )
        )

    @property
    def algorithm_id(self) -> str:
        return self._algo_combo.currentData()

    @property
    def selection_method(self) -> str:
        return self._selection_combo.currentData()

    @property
    def threshold(self) -> float:
        return self._threshold_spin.value()

    @property
    def threshold_max(self) -> float:
        return self._threshold_max_spin.value()

    @property
    def threshold_min(self) -> float:
        return self._threshold_min_spin.value()

    @property
    def reference_distance_m(self) -> float:
        return self._reference_distance_spin.value()

    @property
    def bridge_gap_m(self) -> float:
        if self.selection_method != PEAK_SELECTION_METHOD_NEAREST_ISLAND:
            return 0.0
        return self._bridge_gap_spin.value()

    @property
    def display_name(self) -> str:
        text = self._name_edit.text().strip()
        if text:
            return text
        return default_generated_name(
            self.algorithm_id,
            self.threshold,
            reference_distance_m=self.reference_distance_m,
            selection_method=self.selection_method,
        )
