"""Optimization tab widget — embeds directly into the analysis panel."""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QTableWidget, QTableWidgetItem,
                              QHeaderView, QComboBox, QDoubleSpinBox, QSpinBox,
                              QProgressBar, QGroupBox, QMessageBox,
                              QAbstractItemView, QSplitter)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QColor

from ..engine.surface import LensSystem, SolveType
from ..engine.optimizer import Optimizer, OptimizationResult


# ---- Operand definitions ----
OPERAND_INFO = {
    "SPOT":  ("RMS spot size (mm) — target 0 to minimise blur", 0.0, 1.0),
    "EFFL":  ("Effective focal length (mm) — target your desired EFL", 100.0, 1.0),
    "TRAY":  ("Transverse ray aberration (mm) — target 0", 0.0, 1.0),
    "AXCL":  ("Axial chromatic aberration (mm) — target 0", 0.0, 1.0),
    "DIMX":  ("Surface thickness (mm) — constrain a gap", 5.0, 0.1),
}
OPERAND_CODES = list(OPERAND_INFO.keys())


class _OptThread(QThread):
    """Run DLS optimization in a background thread."""
    progress = pyqtSignal(int, float)
    finished_signal = pyqtSignal(object)

    def __init__(self, optimizer, max_iter):
        super().__init__()
        self.optimizer = optimizer
        self.max_iter = max_iter

    def run(self):
        result = self.optimizer.optimize(
            max_iterations=self.max_iter,
            callback=lambda it, m: self.progress.emit(it, m))
        self.finished_signal.emit(result)


class OptimizationWidget(QWidget):
    """Inline optimization panel that reads V-marked variables from the editor."""

    optimization_complete = pyqtSignal()

    def __init__(self, system: LensSystem, parent=None):
        super().__init__(parent)
        self.system = system
        self.optimizer = Optimizer(system)
        self._syncing = False
        self._thread = None
        self._setup_ui()

    def set_system(self, system: LensSystem):
        self.system = system
        self.optimizer = Optimizer(system)
        self._sync_variables()
        self._refresh_operand_table()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        # ---- Variables summary ----
        var_box = QGroupBox("Variables  (mark V in Radius/Thickness columns)")
        var_box.setToolTip(
            "Variables are auto-collected from the lens editor. Type a value "
            "followed by 'V' in any Radius or Thickness cell (e.g. '61.47 V') "
            "or right-click → Make Radius/Thickness Variable.")
        var_lay = QVBoxLayout(var_box)

        self.var_label = QLabel("No variables. Mark parameters with V in the editor.")
        self.var_label.setWordWrap(True)
        self.var_label.setStyleSheet("color: #a6adc8;")
        var_lay.addWidget(self.var_label)

        root.addWidget(var_box)

        # ---- Operands table ----
        op_box = QGroupBox("Merit Function Operands")
        op_box.setToolTip(
            "Define what 'good' means. The optimiser drives each operand "
            "toward its Target, weighted by Weight. Lower merit = better.")
        op_lay = QVBoxLayout(op_box)

        self.op_table = QTableWidget()
        self.op_table.setColumnCount(5)
        self.op_table.setHorizontalHeaderLabels(
            ["Type", "Target", "Weight", "Field", "Wave"])
        self.op_table.horizontalHeader().setStretchLastSection(True)
        self.op_table.verticalHeader().setVisible(False)
        self.op_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.op_table.setMaximumHeight(180)
        self.op_table.itemChanged.connect(self._on_op_item_changed)
        op_lay.addWidget(self.op_table)

        # Description label
        self.op_desc = QLabel("Add operands with the buttons below.")
        self.op_desc.setWordWrap(True)
        self.op_desc.setStyleSheet("color: #a6adc8; font-style: italic;")
        op_lay.addWidget(self.op_desc)
        self.op_table.currentCellChanged.connect(self._on_op_row_selected)

        op_btns = QHBoxLayout()
        btn_default = QPushButton("Default MF")
        btn_default.setToolTip(
            "One SPOT operand per field (target 0). A good starting point.")
        btn_default.clicked.connect(self._default_operands)

        btn_add = QPushButton("Add")
        btn_add.setToolTip("Add a SPOT operand (then change via the Type dropdown).")
        btn_add.clicked.connect(self._add_operand)

        btn_del = QPushButton("Remove")
        btn_del.setToolTip("Remove the selected operand row.")
        btn_del.clicked.connect(self._remove_operand)

        op_btns.addWidget(btn_default)
        op_btns.addWidget(btn_add)
        op_btns.addWidget(btn_del)
        op_btns.addStretch()
        op_lay.addLayout(op_btns)

        root.addWidget(op_box)

        # ---- Settings row ----
        settings = QHBoxLayout()

        settings.addWidget(QLabel("Iterations:"))
        self.iter_spin = QSpinBox()
        self.iter_spin.setRange(1, 1000)
        self.iter_spin.setValue(50)
        self.iter_spin.setToolTip("Max DLS iterations (20-100 typical).")
        settings.addWidget(self.iter_spin)

        settings.addSpacing(8)
        settings.addWidget(QLabel("Damping:"))
        self.damp_spin = QDoubleSpinBox()
        self.damp_spin.setRange(0.001, 100)
        self.damp_spin.setDecimals(3)
        self.damp_spin.setValue(0.1)
        self.damp_spin.setToolTip("LM damping factor (0.1 is a safe default).")
        settings.addWidget(self.damp_spin)

        settings.addStretch()
        root.addLayout(settings)

        # ---- Progress + buttons ----
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        root.addWidget(self.progress_bar)

        self.merit_label = QLabel("Merit: --")
        self.merit_label.setToolTip(
            "Current merit function value. Lower = better. Zero = perfect.")
        root.addWidget(self.merit_label)

        action_btns = QHBoxLayout()
        action_btns.addStretch()

        self.btn_evaluate = QPushButton("Evaluate")
        self.btn_evaluate.setToolTip("Compute the merit without changing anything.")
        self.btn_evaluate.clicked.connect(self._evaluate)
        action_btns.addWidget(self.btn_evaluate)

        self.btn_optimize = QPushButton("Optimize")
        self.btn_optimize.setObjectName("primaryButton")
        self.btn_optimize.setToolTip(
            "Run DLS to minimize the merit function. The lens is updated in-place.")
        self.btn_optimize.clicked.connect(self._run)
        action_btns.addWidget(self.btn_optimize)

        root.addLayout(action_btns)
        root.addStretch()

    # ------------------------------------------------------------------
    # Variable sync  (reads V-marked params from the system)
    # ------------------------------------------------------------------
    def _sync_variables(self):
        """Rebuild the optimizer variable list from V-marked surfaces."""
        self.optimizer.variables.clear()
        lines = []
        for i, surf in enumerate(self.system.surfaces):
            if i == 0 or i == len(self.system.surfaces) - 1:
                continue
            if surf.radius_solve == SolveType.VARIABLE:
                self.optimizer.add_variable(i, "radius")
                lines.append(f"  Surf {i} Radius = {surf.radius:.4g}")
            if surf.thickness_solve == SolveType.VARIABLE:
                self.optimizer.add_variable(i, "thickness", 0.1, 500.0)
                lines.append(f"  Surf {i} Thickness = {surf.thickness:.4g}")

        if lines:
            self.var_label.setText(
                f"<b>{len(self.optimizer.variables)} variable(s)</b> "
                f"detected from editor:<br>" + "<br>".join(lines))
            self.var_label.setStyleSheet("color: #a6e3a1;")  # green
        else:
            self.var_label.setText(
                "No variables. Mark parameters with <b>V</b> in the editor "
                "(e.g. type <code>61.47 V</code> in a Radius cell, or right-click "
                "→ Make Radius Variable).")
            self.var_label.setStyleSheet("color: #f38ba8;")  # red hint

    def update_from_editor(self):
        """Called by main window when the system changes."""
        self.optimizer.system = self.system
        self._sync_variables()

    # ------------------------------------------------------------------
    # Operand table
    # ------------------------------------------------------------------
    def _refresh_operand_table(self):
        self._syncing = True
        try:
            self.op_table.setRowCount(len(self.optimizer.operands))
            for i, op in enumerate(self.optimizer.operands):
                # Type combo
                combo = QComboBox()
                for code in OPERAND_CODES:
                    combo.addItem(code, code)
                    combo.setItemData(combo.count() - 1,
                                      OPERAND_INFO[code][0],
                                      Qt.ItemDataRole.ToolTipRole)
                idx = OPERAND_CODES.index(op.type) if op.type in OPERAND_CODES else 0
                combo.setCurrentIndex(idx)
                combo.currentIndexChanged.connect(
                    lambda _idx, row=i, c=combo: self._op_type_changed(row, c))
                self.op_table.setCellWidget(i, 0, combo)

                # Target
                item_t = QTableWidgetItem(f"{op.target:.4g}")
                item_t.setToolTip("Desired value for this operand.")
                self.op_table.setItem(i, 1, item_t)

                # Weight
                item_w = QTableWidgetItem(f"{op.weight:.4g}")
                item_w.setToolTip("Relative importance (0 = disabled).")
                self.op_table.setItem(i, 2, item_w)

                # Field combo
                fc = QComboBox()
                if self.system.fields:
                    for fi, fa in enumerate(self.system.fields):
                        fc.addItem(f"{fi}: {fa:.1f}\u00b0", fi)
                else:
                    fc.addItem("0: 0.0\u00b0", 0)
                fc.setCurrentIndex(min(op.field_idx, fc.count() - 1))
                fc.currentIndexChanged.connect(
                    lambda _idx, row=i, c=fc: self._op_field_changed(row, c))
                self.op_table.setCellWidget(i, 3, fc)

                # Wave combo
                wc = QComboBox()
                if self.system.wavelengths:
                    for wi, wl in enumerate(self.system.wavelengths):
                        wc.addItem(f"{wi}: {wl:.4f}\u00b5m", wi)
                else:
                    wc.addItem("0: 0.5876\u00b5m", 0)
                wc.setCurrentIndex(min(op.wave_idx, wc.count() - 1))
                wc.currentIndexChanged.connect(
                    lambda _idx, row=i, c=wc: self._op_wave_changed(row, c))
                self.op_table.setCellWidget(i, 4, wc)

            self.op_table.resizeColumnsToContents()
            self.op_table.horizontalHeader().setStretchLastSection(True)
        finally:
            self._syncing = False

    def _op_type_changed(self, row, combo):
        if self._syncing or row >= len(self.optimizer.operands):
            return
        self.optimizer.operands[row].type = combo.currentData()

    def _op_field_changed(self, row, combo):
        if self._syncing or row >= len(self.optimizer.operands):
            return
        self.optimizer.operands[row].field_idx = int(combo.currentData() or 0)

    def _op_wave_changed(self, row, combo):
        if self._syncing or row >= len(self.optimizer.operands):
            return
        self.optimizer.operands[row].wave_idx = int(combo.currentData() or 0)

    def _on_op_item_changed(self, item):
        if self._syncing:
            return
        row, col = item.row(), item.column()
        if row >= len(self.optimizer.operands):
            return
        try:
            val = float(item.text())
        except ValueError:
            return
        if col == 1:
            self.optimizer.operands[row].target = val
        elif col == 2:
            self.optimizer.operands[row].weight = val

    def _on_op_row_selected(self, row, col, prev_row, prev_col):
        if 0 <= row < len(self.optimizer.operands):
            code = self.optimizer.operands[row].type
            info = OPERAND_INFO.get(code)
            if info:
                self.op_desc.setText(f"<b>{code}</b> — {info[0]}")

    def _default_operands(self):
        self.optimizer.auto_set_operands()
        self._refresh_operand_table()

    def _add_operand(self):
        self.optimizer.add_operand("SPOT", 0.0, 1.0)
        self._refresh_operand_table()

    def _remove_operand(self):
        row = self.op_table.currentRow()
        if 0 <= row < len(self.optimizer.operands):
            self.optimizer.operands.pop(row)
            self._refresh_operand_table()

    # ------------------------------------------------------------------
    # Evaluate / Optimize
    # ------------------------------------------------------------------
    def _evaluate(self):
        self._sync_variables()
        if not self.optimizer.variables:
            QMessageBox.information(self, "No Variables",
                "Mark parameters with V in the editor first.\n\n"
                "e.g. type '61.47 V' in a Radius cell.")
            return
        if not self.optimizer.operands:
            QMessageBox.information(self, "No Operands",
                "Add operands with 'Default MF' or 'Add'.")
            return
        merit = self.optimizer.evaluate_merit()
        self.merit_label.setText(f"Merit: {merit:.6f}")

    def _run(self):
        self._sync_variables()
        if not self.optimizer.variables:
            QMessageBox.information(self, "No Variables",
                "Mark parameters with V in the editor first.\n\n"
                "e.g. type '61.47 V' in a Radius cell, or right-click "
                "→ Make Radius Variable.")
            return
        if not self.optimizer.operands:
            QMessageBox.information(self, "No Operands",
                "Click 'Default MF' for a spot-size merit function, "
                "or add operands manually.")
            return

        self.optimizer.damping = self.damp_spin.value()
        max_iter = self.iter_spin.value()

        self.btn_optimize.setEnabled(False)
        self.btn_evaluate.setEnabled(False)
        self.progress_bar.setMaximum(max_iter)

        self._thread = _OptThread(self.optimizer, max_iter)
        self._thread.progress.connect(self._on_progress)
        self._thread.finished_signal.connect(self._on_finished)
        self._thread.start()

    def _on_progress(self, iteration, merit):
        self.progress_bar.setValue(iteration)
        self.merit_label.setText(f"Iteration {iteration}: Merit = {merit:.6f}")

    def _on_finished(self, result: OptimizationResult):
        self.btn_optimize.setEnabled(True)
        self.btn_evaluate.setEnabled(True)
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.merit_label.setText(
            f"Done: {result.message} | Initial: {result.initial_merit:.6f} "
            f"→ Final: {result.final_merit:.6f}")
        self._sync_variables()
        self.optimization_complete.emit()
