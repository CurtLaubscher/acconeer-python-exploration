from __future__ import annotations


"""Resources window and delegates for the heatmap alignment workbench."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from heatmap_alignment_reconcile import elide_path_middle
from heatmap_alignment_resource_summaries import ResourceAction, ResourceKind, ResourceSummary

from PySide6 import QtCore, QtGui, QtWidgets


RESOURCE_STATUS_LABELS = {
    "unloaded": "Unloaded",
    "loaded": "Loaded",
    "missing": "Missing",
    "invalid": "Invalid",
    "warning": "Warning",
}

RESOURCES_DETAILS_SECTION_SPACING_PX = 6
RESOURCES_DETAILS_PATH_BLOCK_TOP_MARGIN_PX = 6
# Initial column widths (Interactive; user can resize; not enforced on refresh).
RESOURCES_TABLE_RESOURCE_COLUMN_DEFAULT_WIDTH_PX = 140
RESOURCES_TABLE_STATUS_COLUMN_DEFAULT_WIDTH_PX = 150

RESOURCE_ACTION_LABELS: dict[ResourceAction, str] = {
    "load": "&Load...",
    "replace": "&Replace...",
    "unload": "&Unload",
    "reload": "&Reload",
    "reveal": "Show in &File Manager",
    "inspect": "Inspect &Warnings",
    "cancel": "&Cancel Load",
    "generate": "&Generate",
    "save": "&Save Peaks",
    "save_as": "Save Peaks &As...",
}

RESOURCE_JOB_STATUS_LABELS = {
    "idle": "Unloaded",
    "pending": "Loading",
    "loading": "Loading",
    "building": "Building",
    "waiting": "Waiting",
    "cancelling": "Cancelling",
    "failed": "Failed",
    "superseded": "Superseded",
}


@runtime_checkable
class _ResourcesWindowHost(Protocol):
    def clear_all_resources(self) -> None: ...
    def invoke_resource_action(
        self,
        kind: ResourceKind,
        action: ResourceAction,
        *,
        series_id: str = "",
    ) -> None: ...


class ResourceColorSwatchDelegate(QtWidgets.QStyledItemDelegate):
    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex,
    ) -> None:
        item_option = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(item_option, index)
        item_option.text = ""
        style = (
            option.widget.style() if option.widget is not None else QtWidgets.QApplication.style()
        )
        style.drawControl(
            QtWidgets.QStyle.ControlElement.CE_ItemViewItem,
            item_option,
            painter,
            option.widget,
        )

        color_hex = index.data(QtCore.Qt.ItemDataRole.UserRole)
        painter.save()
        try:
            rect = option.rect.adjusted(6, 8, -6, -8)
            if not color_hex:
                painter.setPen(QtGui.QPen(QtGui.QColor("#475569")))
                painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                painter.drawRect(rect)
                return
            color = QtGui.QColor(str(color_hex))
            if index.data(QtCore.Qt.ItemDataRole.UserRole + 1):
                color.setAlpha(96)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(rect, 3, 3)
        finally:
            painter.restore()


class ElidedPathItemDelegate(QtWidgets.QStyledItemDelegate):
    def initStyleOption(
        self,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex,
    ) -> None:
        super().initStyleOption(option, index)
        full_path = str(index.data(QtCore.Qt.ItemDataRole.UserRole) or "")
        if not full_path:
            option.text = ""
            return
        metrics = option.fontMetrics
        available_px = max(24, option.rect.width() - 12)
        avg_char_px = max(1, metrics.horizontalAdvance("n"))
        max_chars = max(12, available_px // avg_char_px)
        option.text = elide_path_middle(full_path, max_chars)


class ResourcesWindow(QtWidgets.QDialog):
    """Modeless resource manager owned by the alignment main window."""

    def __init__(self, main_window: _ResourcesWindowHost) -> None:
        super().__init__(main_window if isinstance(main_window, QtWidgets.QWidget) else None)
        self._main_window = main_window
        self.setWindowTitle("Resources")
        self.setModal(False)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.resize(920, 520)

        layout = QtWidgets.QVBoxLayout(self)

        self.session_label = QtWidgets.QLabel()
        self.session_label.setWordWrap(True)
        layout.addWidget(self.session_label)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["", "Resource", "Role", "Status", "Path"])
        table_header = self.table.horizontalHeader()
        table_header.setStretchLastSection(True)
        table_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        table_header.setSectionsClickable(False)
        table_header.setHighlightSections(False)
        self.table.setColumnWidth(0, 34)
        table_metrics = self.table.fontMetrics()
        resource_default_width = max(
            RESOURCES_TABLE_RESOURCE_COLUMN_DEFAULT_WIDTH_PX,
            table_metrics.horizontalAdvance("Radar Peak (JSON)") + 20,
        )
        status_default_width = max(
            RESOURCES_TABLE_STATUS_COLUMN_DEFAULT_WIDTH_PX,
            table_metrics.horizontalAdvance("Generated (unsaved)") + 20,
        )
        self.table.setColumnWidth(1, resource_default_width)
        self.table.setColumnWidth(3, status_default_width)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setCornerButtonEnabled(False)
        self.table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_row_context_menu)
        self.table.itemSelectionChanged.connect(self._update_details_for_selection)
        self.table.setItemDelegateForColumn(0, ResourceColorSwatchDelegate(self.table))
        self.table.setItemDelegateForColumn(4, ElidedPathItemDelegate(self.table))
        layout.addWidget(self.table, stretch=1)

        details_group = QtWidgets.QGroupBox("Selected Resource")
        details_layout = QtWidgets.QVBoxLayout(details_group)
        details_layout.setSpacing(0)
        self.details_identity_label = QtWidgets.QLabel()
        self.details_identity_label.setWordWrap(True)
        self.details_status_label = QtWidgets.QLabel()
        self.details_status_label.setWordWrap(True)
        self.details_messages_label = QtWidgets.QLabel()
        self.details_messages_label.setWordWrap(True)
        self.details_messages_label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.details_path_widget = QtWidgets.QWidget()
        path_block_layout = QtWidgets.QVBoxLayout(self.details_path_widget)
        path_block_layout.setContentsMargins(
            0,
            RESOURCES_DETAILS_PATH_BLOCK_TOP_MARGIN_PX,
            0,
            0,
        )
        path_block_layout.setSpacing(0)
        self.details_path_label = QtWidgets.QLabel()
        self.details_path_label.setWordWrap(True)
        self.details_path_label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        path_block_layout.addWidget(self.details_path_label)
        details_layout.addWidget(self.details_identity_label)
        details_layout.addSpacing(RESOURCES_DETAILS_SECTION_SPACING_PX)
        details_layout.addWidget(self.details_status_label)
        details_layout.addWidget(self.details_messages_label)
        details_layout.addWidget(self.details_path_widget)
        details_layout.addSpacing(RESOURCES_DETAILS_SECTION_SPACING_PX)

        action_row = QtWidgets.QHBoxLayout()
        self.load_button = QtWidgets.QPushButton(RESOURCE_ACTION_LABELS["load"])
        self.replace_button = QtWidgets.QPushButton(RESOURCE_ACTION_LABELS["replace"])
        self.unload_button = QtWidgets.QPushButton(RESOURCE_ACTION_LABELS["unload"])
        self.reload_button = QtWidgets.QPushButton(RESOURCE_ACTION_LABELS["reload"])
        self.reveal_button = QtWidgets.QPushButton(RESOURCE_ACTION_LABELS["reveal"])
        self.inspect_button = QtWidgets.QPushButton(RESOURCE_ACTION_LABELS["inspect"])
        self.cancel_button = QtWidgets.QPushButton(RESOURCE_ACTION_LABELS["cancel"])
        self.generate_button = QtWidgets.QPushButton(RESOURCE_ACTION_LABELS["generate"])
        self.save_peaks_button = QtWidgets.QPushButton(RESOURCE_ACTION_LABELS["save"])
        self.save_peaks_as_button = QtWidgets.QPushButton(RESOURCE_ACTION_LABELS["save_as"])
        for button in (
            self.load_button,
            self.replace_button,
            self.unload_button,
            self.reload_button,
            self.reveal_button,
            self.inspect_button,
            self.cancel_button,
            self.generate_button,
            self.save_peaks_button,
            self.save_peaks_as_button,
        ):
            action_row.addWidget(button)
        action_row.addStretch(1)
        details_layout.addLayout(action_row)
        layout.addWidget(details_group)

        self.load_button.clicked.connect(lambda: self._invoke_action("load"))
        self.replace_button.clicked.connect(lambda: self._invoke_action("replace"))
        self.unload_button.clicked.connect(lambda: self._invoke_action("unload"))
        self.reload_button.clicked.connect(lambda: self._invoke_action("reload"))
        self.reveal_button.clicked.connect(lambda: self._invoke_action("reveal"))
        self.inspect_button.clicked.connect(lambda: self._invoke_action("inspect"))
        self.cancel_button.clicked.connect(lambda: self._invoke_action("cancel"))
        self.generate_button.clicked.connect(lambda: self._invoke_action("generate"))
        self.save_peaks_button.clicked.connect(lambda: self._invoke_action("save"))
        self.save_peaks_as_button.clicked.connect(lambda: self._invoke_action("save_as"))

        bottom_row = QtWidgets.QHBoxLayout()
        self.clear_all_button = QtWidgets.QPushButton("Clear All Resources...")
        self.clear_all_button.clicked.connect(self._main_window.clear_all_resources)
        bottom_row.addWidget(self.clear_all_button)
        self.generate_peak_series_button = QtWidgets.QPushButton("&Generate Peak Series...")
        self.generate_peak_series_button.clicked.connect(
            lambda: self._main_window.invoke_resource_action("radar_peak", "generate")
        )
        bottom_row.addWidget(self.generate_peak_series_button)
        self.import_peak_series_button = QtWidgets.QPushButton("&Import Peak Series...")
        self.import_peak_series_button.clicked.connect(
            lambda: self._main_window.invoke_resource_action("radar_peak", "load")
        )
        bottom_row.addWidget(self.import_peak_series_button)
        bottom_row.addStretch(1)
        self.close_button = QtWidgets.QPushButton("&Close")
        self.close_button.clicked.connect(self._dismiss)
        bottom_row.addWidget(self.close_button)
        layout.addLayout(bottom_row)

        self._summaries: tuple[ResourceSummary, ...] = ()
        self._selected_series_id: str = ""  # Series id of the selected peak row (if any).

    def _dismiss(self) -> None:
        self.hide()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        event.accept()
        self.hide()

    @staticmethod
    def _configure_table_item(item: QtWidgets.QTableWidgetItem) -> None:
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)

    def _selected_table_row(self) -> int:
        selection_model = self.table.selectionModel()
        if selection_model is not None:
            selected_rows = selection_model.selectedRows()
            if selected_rows:
                return selected_rows[0].row()
        return self.table.currentRow()

    def _select_table_row(self, row: int) -> None:
        if row < 0 or row >= self.table.rowCount():
            return
        self.table.blockSignals(True)
        try:
            self.table.clearSelection()
            self.table.selectRow(row)
            self.table.setCurrentCell(row, 0)
        finally:
            self.table.blockSignals(False)

    def refresh(self, summaries: tuple[ResourceSummary, ...], session_path: Path | None) -> None:
        if session_path is None:
            self.session_label.setText("Session: Untitled Session")
        else:
            self.session_label.setText(f"Session: {session_path}")
        self._summaries = summaries
        selected_kind = self._selected_kind()
        prev_series_id = self._selected_series_id
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(summaries))
            for row_index, summary in enumerate(summaries):
                swatch_item = QtWidgets.QTableWidgetItem()
                swatch_item.setData(QtCore.Qt.ItemDataRole.UserRole, summary.color_hex)
                swatch_item.setData(QtCore.Qt.ItemDataRole.UserRole + 1, summary.color_muted)
                self._configure_table_item(swatch_item)
                self.table.setItem(row_index, 0, swatch_item)

                name_item = QtWidgets.QTableWidgetItem(summary.display_name)
                self._configure_table_item(name_item)
                self.table.setItem(row_index, 1, name_item)

                role_item = QtWidgets.QTableWidgetItem(summary.role)
                self._configure_table_item(role_item)
                self.table.setItem(row_index, 2, role_item)

                status_text = (
                    summary.status_label
                    if summary.status_label
                    else RESOURCE_STATUS_LABELS[summary.status]
                )
                if summary.job_phase not in ("idle", "superseded"):
                    status_text = RESOURCE_JOB_STATUS_LABELS[summary.job_phase]
                status_item = QtWidgets.QTableWidgetItem(status_text)
                self._configure_table_item(status_item)
                self.table.setItem(row_index, 3, status_item)

                path_item = QtWidgets.QTableWidgetItem()
                path_item.setData(QtCore.Qt.ItemDataRole.UserRole, summary.path)
                if summary.path:
                    path_item.setToolTip(summary.path)
                self._configure_table_item(path_item)
                self.table.setItem(row_index, 4, path_item)

            # Restore selection: prefer series_id match for peak rows; fall back to kind match.
            restored = False
            if prev_series_id:
                for row_index, summary in enumerate(summaries):
                    if summary.series_id == prev_series_id:
                        self._select_table_row(row_index)
                        restored = True
                        break
            if not restored and selected_kind is not None:
                for row_index, summary in enumerate(summaries):
                    if summary.kind == selected_kind and not summary.series_id:
                        self._select_table_row(row_index)
                        restored = True
                        break
            if not restored and summaries:
                self._select_table_row(0)
        finally:
            self.table.blockSignals(False)
        self._update_details_for_selection()

    def _selected_summary(self) -> ResourceSummary | None:
        row = self._selected_table_row()
        if row < 0 or row >= len(self._summaries):
            return None
        return self._summaries[row]

    def _selected_kind(self) -> ResourceKind | None:
        summary = self._selected_summary()
        return None if summary is None else summary.kind

    def _update_details_for_selection(self) -> None:
        summary = self._selected_summary()
        self._selected_series_id = summary.series_id if summary is not None else ""
        if summary is None:
            self.details_identity_label.setText("")
            self.details_status_label.setText("")
            self.details_messages_label.setText("")
            self.details_messages_label.setVisible(False)
            self.details_path_label.clear()
            self.details_path_widget.setVisible(False)
            for button in (
                self.load_button,
                self.replace_button,
                self.unload_button,
                self.reload_button,
                self.reveal_button,
                self.inspect_button,
                self.cancel_button,
                self.generate_button,
                self.save_peaks_button,
                self.save_peaks_as_button,
            ):
                button.setEnabled(False)
            return

        self.details_identity_label.setText(f"{summary.display_name} ({summary.role})")
        display_status = (
            summary.status_label
            if summary.status_label
            else RESOURCE_STATUS_LABELS[summary.status]
        )
        self.details_status_label.setText(f"{display_status}\n{summary.details}")
        if summary.messages:
            self.details_messages_label.setText("\n".join(summary.messages))
            self.details_messages_label.setVisible(True)
        else:
            self.details_messages_label.clear()
            self.details_messages_label.setVisible(False)

        if summary.path:
            self.details_path_label.setText(f"Path: {summary.path}")
            self.details_path_widget.setVisible(True)
        else:
            self.details_path_label.clear()
            self.details_path_widget.setVisible(False)

        action_set = set(summary.actions)
        is_peak_series_row = bool(summary.series_id)
        self.load_button.setEnabled("load" in action_set)
        # Replace is not supported for individual peak series rows; leave it disabled.
        self.replace_button.setEnabled("replace" in action_set and not is_peak_series_row)
        self.unload_button.setEnabled("unload" in action_set)
        self.reload_button.setEnabled("reload" in action_set)
        self.reveal_button.setEnabled("reveal" in action_set)
        self.inspect_button.setEnabled("inspect" in action_set)
        self.cancel_button.setEnabled("cancel" in action_set)
        # Generate is a global append action in the footer; disable it on individual series rows.
        self.generate_button.setEnabled("generate" in action_set and not is_peak_series_row)
        self.save_peaks_button.setEnabled("save" in action_set)
        self.save_peaks_as_button.setEnabled("save_as" in action_set)

    def _invoke_action(self, action: ResourceAction) -> None:
        summary = self._selected_summary()
        if summary is None:
            return
        self._main_window.invoke_resource_action(summary.kind, action, series_id=summary.series_id)

    def _show_row_context_menu(self, position: QtCore.QPoint) -> None:
        index = self.table.indexAt(position)
        if not index.isValid():
            return
        self._select_table_row(index.row())
        summary = self._selected_summary()
        if summary is None:
            return
        menu = QtWidgets.QMenu(self)
        for action in summary.actions:
            menu_action = menu.addAction(RESOURCE_ACTION_LABELS[action])
            menu_action.triggered.connect(
                lambda _checked=False, kind=summary.kind, chosen=action, sid=summary.series_id: (
                    self._main_window.invoke_resource_action(kind, chosen, series_id=sid)
                )
            )
        menu.exec(self.table.viewport().mapToGlobal(position))
