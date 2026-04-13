"""Dialogs for system settings, wavelengths, fields, and optimization."""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                              QLabel, QLineEdit, QDoubleSpinBox, QSpinBox,
                              QPushButton, QListWidget, QGroupBox, QComboBox,
                              QTableWidget, QTableWidgetItem, QHeaderView,
                              QProgressBar, QTextEdit, QCheckBox, QMessageBox,
                              QAbstractItemView)
from PyQt6.QtCore import Qt, pyqtSignal, QThread

from ..engine.surface import LensSystem, SolveType
from ..engine.optimizer import Optimizer, OptimizationResult
from ..engine.materials import (available_glasses, GLASS_CATALOG, Glass,
                                 add_custom_glass, remove_custom_glass,
                                 is_custom_glass, save_glass_catalog,
                                 load_glass_catalog)


class SystemSettingsDialog(QDialog):
    """Dialog for editing system-level settings."""

    def __init__(self, system: LensSystem, parent=None):
        super().__init__(parent)
        self.system = system
        self.setWindowTitle("System Settings")
        self.setMinimumWidth(450)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.title_edit = QLineEdit(self.system.title)
        form.addRow("Title:", self.title_edit)

        self.epd_spin = QDoubleSpinBox()
        self.epd_spin.setRange(0.01, 10000)
        self.epd_spin.setDecimals(4)
        self.epd_spin.setValue(self.system.entrance_pupil_diameter)
        form.addRow("Entrance Pupil Diameter:", self.epd_spin)

        self.notes_edit = QTextEdit(self.system.notes)
        self.notes_edit.setMaximumHeight(80)
        form.addRow("Notes:", self.notes_edit)

        layout.addLayout(form)

        # Wavelengths
        wl_group = QGroupBox("Wavelengths (\u03bcm)")
        wl_layout = QVBoxLayout(wl_group)

        self.wl_list = QListWidget()
        for wl in self.system.wavelengths:
            self.wl_list.addItem(f"{wl:.4f}")
        wl_layout.addWidget(self.wl_list)

        wl_btns = QHBoxLayout()
        self.wl_edit = QDoubleSpinBox()
        self.wl_edit.setRange(0.1, 20.0)
        self.wl_edit.setDecimals(4)
        self.wl_edit.setValue(0.5876)
        wl_btns.addWidget(self.wl_edit)

        btn_add_wl = QPushButton("Add")
        btn_add_wl.clicked.connect(self._add_wavelength)
        wl_btns.addWidget(btn_add_wl)

        btn_del_wl = QPushButton("Remove")
        btn_del_wl.clicked.connect(self._remove_wavelength)
        wl_btns.addWidget(btn_del_wl)

        btn_preset = QPushButton("Visible (F,d,C)")
        btn_preset.clicked.connect(self._preset_fdc)
        wl_btns.addWidget(btn_preset)

        wl_layout.addLayout(wl_btns)

        self.primary_wl_spin = QSpinBox()
        self.primary_wl_spin.setMinimum(0)
        self.primary_wl_spin.setMaximum(max(0, len(self.system.wavelengths) - 1))
        self.primary_wl_spin.setValue(self.system.primary_wavelength_idx)
        wl_h = QHBoxLayout()
        wl_h.addWidget(QLabel("Primary wavelength index:"))
        wl_h.addWidget(self.primary_wl_spin)
        wl_layout.addLayout(wl_h)

        layout.addWidget(wl_group)

        # Fields
        field_group = QGroupBox("Field Angles (\u00b0)")
        field_layout = QVBoxLayout(field_group)

        self.field_list = QListWidget()
        for f in self.system.fields:
            self.field_list.addItem(f"{f:.2f}")
        field_layout.addWidget(self.field_list)

        field_btns = QHBoxLayout()
        self.field_edit = QDoubleSpinBox()
        self.field_edit.setRange(-90, 90)
        self.field_edit.setDecimals(2)
        self.field_edit.setValue(0.0)
        field_btns.addWidget(self.field_edit)

        btn_add_f = QPushButton("Add")
        btn_add_f.clicked.connect(self._add_field)
        field_btns.addWidget(btn_add_f)

        btn_del_f = QPushButton("Remove")
        btn_del_f.clicked.connect(self._remove_field)
        field_btns.addWidget(btn_del_f)

        field_layout.addLayout(field_btns)
        layout.addWidget(field_group)

        # Buttons
        btns = QHBoxLayout()
        btns.addStretch()
        btn_ok = QPushButton("OK")
        btn_ok.setObjectName("primaryButton")
        btn_ok.clicked.connect(self._accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

    def _add_wavelength(self):
        self.wl_list.addItem(f"{self.wl_edit.value():.4f}")

    def _remove_wavelength(self):
        row = self.wl_list.currentRow()
        if row >= 0 and self.wl_list.count() > 1:
            self.wl_list.takeItem(row)

    def _preset_fdc(self):
        self.wl_list.clear()
        for wl in [0.4861, 0.5876, 0.6563]:
            self.wl_list.addItem(f"{wl:.4f}")
        self.primary_wl_spin.setValue(1)

    def _add_field(self):
        self.field_list.addItem(f"{self.field_edit.value():.2f}")

    def _remove_field(self):
        row = self.field_list.currentRow()
        if row >= 0 and self.field_list.count() > 1:
            self.field_list.takeItem(row)

    def _accept(self):
        self.system.title = self.title_edit.text()
        self.system.entrance_pupil_diameter = self.epd_spin.value()
        self.system.notes = self.notes_edit.toPlainText()

        self.system.wavelengths = []
        for i in range(self.wl_list.count()):
            self.system.wavelengths.append(float(self.wl_list.item(i).text()))

        self.system.primary_wavelength_idx = min(
            self.primary_wl_spin.value(), len(self.system.wavelengths) - 1)

        self.system.fields = []
        for i in range(self.field_list.count()):
            self.system.fields.append(float(self.field_list.item(i).text()))

        self.accept()


class OptimizationThread(QThread):
    """Run optimization in background thread."""
    progress = pyqtSignal(int, float)
    finished_signal = pyqtSignal(object)

    def __init__(self, optimizer, max_iter):
        super().__init__()
        self.optimizer = optimizer
        self.max_iter = max_iter

    def run(self):
        def callback(iteration, merit):
            self.progress.emit(iteration, merit)

        result = self.optimizer.optimize(max_iterations=self.max_iter,
                                          callback=callback)
        self.finished_signal.emit(result)


# ---------------------------------------------------------------------------
# Optimization dialog help data
# ---------------------------------------------------------------------------

# Operand types: (code, label, description, default target, default weight)
OPERAND_TYPES = [
    ("SPOT", "SPOT — RMS spot size",
     "RMS spot size at the field/wavelength (mm). Target 0 to minimize blur.",
     0.0, 1.0),
    ("EFFL", "EFFL — Effective focal length",
     "Paraxial effective focal length (mm). Target your desired focal length.",
     100.0, 1.0),
    ("TRAY", "TRAY — Transverse ray",
     "Marginal ray transverse aberration at the image (mm). Target 0.",
     0.0, 1.0),
    ("AXCL", "AXCL — Axial color",
     "Focal-length difference between the first and last wavelengths (mm). "
     "Target 0 for achromatic correction.",
     0.0, 1.0),
    ("DIMX", "DIMX — Thickness / gap",
     "Thickness of a named surface (mm). Use this to keep an air gap above a "
     "minimum, or a glass thickness bounded.",
     5.0, 0.1),
]
OPERAND_DESC = {code: (label, desc, tgt, w) for code, label, desc, tgt, w in OPERAND_TYPES}

# Parameter types for variables
PARAMETER_TYPES = [
    ("radius", "Radius (R)",
     "Surface radius of curvature in mm. The primary optimization handle — "
     "controls surface power."),
    ("thickness", "Thickness (T)",
     "Axial gap following this surface in mm. Can move elements apart or "
     "adjust air spaces."),
    ("conic", "Conic (k)",
     "Conic constant (k). 0 = sphere, -1 = parabola, <-1 = hyperbola, "
     "between 0 and -1 = ellipse, >0 = oblate."),
]
PARAM_DESC = {code: (label, desc) for code, label, desc in PARAMETER_TYPES}


class _AddVariableDialog(QDialog):
    """Dialog for adding a variable with dropdowns for surface and parameter."""

    def __init__(self, system: LensSystem, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Variable")
        self.setMinimumWidth(360)
        self.system = system

        layout = QFormLayout(self)

        # Surface dropdown — skip OBJ and IMA
        self.surface_combo = QComboBox()
        self.surface_combo.setToolTip(
            "Pick which lens surface to vary. OBJ (object) and IMA (image) "
            "are excluded since they can't be optimization targets.")
        for i, surf in enumerate(system.surfaces):
            if i == 0 or i == len(system.surfaces) - 1:
                continue
            label = f"#{i}"
            if surf.comment:
                label += f"  {surf.comment}"
            if surf.is_stop:
                label += "  [STOP]"
            label += f"   R={surf.radius:.4g}  t={surf.thickness:.4g}"
            if surf.material:
                label += f"  {surf.material}"
            self.surface_combo.addItem(label, i)
        layout.addRow("Surface:", self.surface_combo)

        # Parameter dropdown
        self.param_combo = QComboBox()
        for code, label, desc in PARAMETER_TYPES:
            self.param_combo.addItem(label, code)
        self.param_combo.setToolTip(PARAMETER_TYPES[0][2])
        self.param_combo.currentIndexChanged.connect(self._update_param_tooltip)
        layout.addRow("Parameter:", self.param_combo)

        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(-1e9, 1e9)
        self.min_spin.setDecimals(4)
        self.min_spin.setValue(-1000.0)
        self.min_spin.setToolTip(
            "Lower bound the optimizer will clamp this variable to. Use this "
            "to prevent unphysical values (e.g. negative thicknesses).")
        layout.addRow("Minimum:", self.min_spin)

        self.max_spin = QDoubleSpinBox()
        self.max_spin.setRange(-1e9, 1e9)
        self.max_spin.setDecimals(4)
        self.max_spin.setValue(1000.0)
        self.max_spin.setToolTip("Upper bound for this variable.")
        layout.addRow("Maximum:", self.max_spin)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Add")
        btn_ok.setObjectName("primaryButton")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addRow(btns)

    def _update_param_tooltip(self, idx):
        if 0 <= idx < len(PARAMETER_TYPES):
            self.param_combo.setToolTip(PARAMETER_TYPES[idx][2])

    def get_result(self):
        return (self.surface_combo.currentData(),
                self.param_combo.currentData(),
                self.min_spin.value(),
                self.max_spin.value())


class OptimizationDialog(QDialog):
    """Optimization setup and execution dialog."""

    optimization_complete = pyqtSignal()

    def __init__(self, system: LensSystem, parent=None):
        super().__init__(parent)
        self.system = system
        self.optimizer = Optimizer(system)
        self.setWindowTitle("Optimization")
        self.setMinimumSize(760, 640)
        self._syncing = False
        self._setup_ui()
        self._refresh_tables()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Help banner ---
        help_box = QGroupBox("How to use the optimizer")
        help_layout = QVBoxLayout(help_box)
        help_text = QLabel(
            "<b>1. Variables</b> — parameters the optimizer will change "
            "(radii, thicknesses, conic). Click <i>Auto-Set</i> for all "
            "finite radii, or <i>Add</i> to pick specific ones.<br>"
            "<b>2. Operands</b> — the merit function goals. Each operand "
            "is a measurement that the optimizer drives toward its "
            "<i>Target</i>, weighted by <i>Weight</i>. Click <i>Default MF</i> "
            "for a spot-size merit function over all fields.<br>"
            "<b>3. Click Evaluate</b> to see the current merit, then "
            "<b>Optimize</b> to run damped least squares. Lower merit = better. "
            "Hover over any field for details."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #a6adc8;")
        help_layout.addWidget(help_text)
        layout.addWidget(help_box)

        # --- Variables table ---
        var_group = QGroupBox("Variables (parameters to change)")
        var_group.setToolTip(
            "Variables are the lens parameters the optimizer is free to "
            "modify. Typically the radii of curvature of each element.")
        var_layout = QVBoxLayout(var_group)

        self.var_table = QTableWidget()
        self.var_table.setColumnCount(4)
        self.var_table.setHorizontalHeaderLabels(
            ["Surface", "Parameter", "Min", "Max"])
        self.var_table.horizontalHeader().setStretchLastSection(True)
        self.var_table.verticalHeader().setVisible(False)
        self.var_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        # Column header tooltips
        hdr = self.var_table.horizontalHeader()
        hdr.setToolTip(
            "Surface: which lens surface to modify (OBJ/IMA excluded)\n"
            "Parameter: radius / thickness / conic\n"
            "Min/Max: clamp bounds for this variable")
        self.var_table.itemChanged.connect(self._on_var_item_changed)
        var_layout.addWidget(self.var_table)

        var_btns = QHBoxLayout()
        btn_auto_var = QPushButton("Auto-Set Variables")
        btn_auto_var.setToolTip(
            "Automatically mark every finite-radius surface as a variable. "
            "A good one-click starting point.")
        btn_auto_var.clicked.connect(self._auto_variables)

        btn_add_var = QPushButton("Add Variable…")
        btn_add_var.setToolTip(
            "Open a picker dialog to add one variable (choose surface, "
            "parameter, and bounds).")
        btn_add_var.clicked.connect(self._add_variable_dialog)

        btn_del_var = QPushButton("Remove")
        btn_del_var.setToolTip("Remove the currently selected variable row.")
        btn_del_var.clicked.connect(self._remove_variable)

        var_btns.addWidget(btn_auto_var)
        var_btns.addWidget(btn_add_var)
        var_btns.addWidget(btn_del_var)
        var_btns.addStretch()
        var_layout.addLayout(var_btns)

        layout.addWidget(var_group)

        # --- Operands table ---
        op_group = QGroupBox("Merit Function Operands (goals to minimize)")
        op_group.setToolTip(
            "The merit function is sqrt(mean((weight*(value-target))²)). "
            "Add operands that describe what 'good' looks like for your lens.")
        op_layout = QVBoxLayout(op_group)

        self.op_table = QTableWidget()
        self.op_table.setColumnCount(5)
        self.op_table.setHorizontalHeaderLabels(
            ["Type", "Target", "Weight", "Field", "Wave"])
        self.op_table.horizontalHeader().setStretchLastSection(True)
        self.op_table.verticalHeader().setVisible(False)
        self.op_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.op_table.horizontalHeader().setToolTip(
            "Type:   which measurement (SPOT, EFFL, TRAY, AXCL, DIMX)\n"
            "Target: desired value\n"
            "Weight: importance relative to other operands\n"
            "Field:  which field angle to measure at (index into system fields)\n"
            "Wave:   which wavelength to use (index into system wavelengths)")
        self.op_table.itemChanged.connect(self._on_op_item_changed)
        op_layout.addWidget(self.op_table)

        # Description label that updates when an operand row is selected
        self.op_desc_label = QLabel(
            "Select an operand row to see its description, "
            "or hover over column headers for help.")
        self.op_desc_label.setWordWrap(True)
        self.op_desc_label.setStyleSheet(
            "color: #a6adc8; padding: 4px; font-style: italic;")
        op_layout.addWidget(self.op_desc_label)
        self.op_table.currentCellChanged.connect(self._on_op_selection_changed)

        op_btns = QHBoxLayout()
        btn_auto_op = QPushButton("Default MF")
        btn_auto_op.setToolTip(
            "Replace the operand list with one SPOT operand per field, "
            "target 0. The standard starting point for most lenses.")
        btn_auto_op.clicked.connect(self._auto_operands)

        btn_add_op = QPushButton("Add Operand")
        btn_add_op.setToolTip(
            "Append a new SPOT operand. You can then change its type, "
            "target, and weight via the dropdowns in the table.")
        btn_add_op.clicked.connect(self._add_operand)

        btn_del_op = QPushButton("Remove")
        btn_del_op.setToolTip("Remove the currently selected operand row.")
        btn_del_op.clicked.connect(self._remove_operand)

        op_btns.addWidget(btn_auto_op)
        op_btns.addWidget(btn_add_op)
        op_btns.addWidget(btn_del_op)
        op_btns.addStretch()
        op_layout.addLayout(op_btns)

        layout.addWidget(op_group)

        # --- Settings row ---
        settings_box = QGroupBox("Optimizer settings")
        settings_layout = QHBoxLayout(settings_box)

        lbl_iter = QLabel("Max Iterations:")
        lbl_iter.setToolTip(
            "Maximum number of damped-least-squares steps. The optimizer "
            "will stop early if the merit converges.")
        settings_layout.addWidget(lbl_iter)
        self.iter_spin = QSpinBox()
        self.iter_spin.setRange(1, 1000)
        self.iter_spin.setValue(50)
        self.iter_spin.setToolTip(
            "Maximum DLS iterations. 20–100 is typical; increase for "
            "difficult designs. Each iteration computes a Jacobian by "
            "finite differences, so runtime scales with (variables × operands).")
        settings_layout.addWidget(self.iter_spin)

        settings_layout.addSpacing(16)
        lbl_damp = QLabel("Damping:")
        lbl_damp.setToolTip(
            "Initial Levenberg-Marquardt damping factor.\n"
            "  Small (0.001–0.01): closer to pure Gauss-Newton, fast but "
            "can diverge far from the optimum.\n"
            "  Large (1–10):        closer to gradient descent, robust but slow.\n"
            "  0.1 is a safe default.")
        settings_layout.addWidget(lbl_damp)
        self.damping_spin = QDoubleSpinBox()
        self.damping_spin.setRange(0.001, 100)
        self.damping_spin.setDecimals(3)
        self.damping_spin.setValue(0.1)
        self.damping_spin.setToolTip(lbl_damp.toolTip())
        settings_layout.addWidget(self.damping_spin)
        settings_layout.addStretch()
        layout.addWidget(settings_box)

        # --- Progress ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setToolTip(
            "Optimization progress — updates after each iteration.")
        layout.addWidget(self.progress_bar)

        self.merit_label = QLabel("Merit: --")
        self.merit_label.setToolTip(
            "Merit function value: lower is better. Zero would mean every "
            "operand is exactly at its target.")
        layout.addWidget(self.merit_label)

        # --- Buttons ---
        btns = QHBoxLayout()
        btns.addStretch()

        self.btn_evaluate = QPushButton("Evaluate")
        self.btn_evaluate.setToolTip(
            "Compute the current merit function without optimizing. Use "
            "this to sanity-check your operand setup.")
        self.btn_evaluate.clicked.connect(self._evaluate)
        btns.addWidget(self.btn_evaluate)

        self.btn_optimize = QPushButton("Optimize")
        self.btn_optimize.setObjectName("primaryButton")
        self.btn_optimize.setToolTip(
            "Run damped least squares to minimize the merit function. "
            "The lens system will be updated in-place.")
        self.btn_optimize.clicked.connect(self._run_optimization)
        btns.addWidget(self.btn_optimize)

        btn_close = QPushButton("Close")
        btn_close.setToolTip(
            "Close the dialog. Any optimization changes are kept — use "
            "File → Undo in the main window to revert if needed.")
        btn_close.clicked.connect(self.accept)
        btns.addWidget(btn_close)

        layout.addLayout(btns)

    # ------------------------------------------------------------------
    # Table population with combo-box cells
    # ------------------------------------------------------------------

    def _surface_choices(self):
        """List of (label, index) for surfaces that can be varied."""
        out = []
        for i, surf in enumerate(self.system.surfaces):
            if i == 0 or i == len(self.system.surfaces) - 1:
                continue
            tag = f"#{i}"
            if surf.is_stop:
                tag += " STO"
            if surf.comment:
                tag += f" {surf.comment[:10]}"
            out.append((tag, i))
        return out

    def _make_surface_combo(self, current_idx):
        combo = QComboBox()
        combo.setToolTip(
            "Lens surface to vary. Hover an entry for its current values.")
        for label, idx in self._surface_choices():
            combo.addItem(label, idx)
            try:
                surf = self.system.surfaces[idx]
                combo.setItemData(
                    combo.count() - 1,
                    f"Surface {idx}: R={surf.radius:.4g} "
                    f"t={surf.thickness:.4g} {surf.material or 'air'}",
                    Qt.ItemDataRole.ToolTipRole)
            except Exception:
                pass
        # Select current
        for i in range(combo.count()):
            if combo.itemData(i) == current_idx:
                combo.setCurrentIndex(i)
                break
        return combo

    def _make_parameter_combo(self, current_param):
        combo = QComboBox()
        for code, label, desc in PARAMETER_TYPES:
            combo.addItem(label, code)
            combo.setItemData(combo.count() - 1, desc,
                              Qt.ItemDataRole.ToolTipRole)
        for i in range(combo.count()):
            if combo.itemData(i) == current_param:
                combo.setCurrentIndex(i)
                combo.setToolTip(PARAM_DESC[current_param][1])
                break
        combo.currentIndexChanged.connect(
            lambda idx, c=combo: c.setToolTip(
                PARAM_DESC[c.currentData()][1] if c.currentData() in PARAM_DESC else ""))
        return combo

    def _make_operand_type_combo(self, current_type):
        combo = QComboBox()
        for code, label, desc, _tgt, _w in OPERAND_TYPES:
            combo.addItem(label, code)
            combo.setItemData(combo.count() - 1, desc,
                              Qt.ItemDataRole.ToolTipRole)
        for i in range(combo.count()):
            if combo.itemData(i) == current_type:
                combo.setCurrentIndex(i)
                combo.setToolTip(OPERAND_DESC[current_type][1])
                break
        return combo

    def _make_field_combo(self, current_idx):
        combo = QComboBox()
        combo.setToolTip(
            "Field angle index (into System → Fields). Use field 0 for "
            "on-axis, higher indices for off-axis angles.")
        if self.system.fields:
            for i, fa in enumerate(self.system.fields):
                combo.addItem(f"{i}: {fa:.2f}°", i)
        else:
            combo.addItem("0: 0.00°", 0)
        idx = min(current_idx, combo.count() - 1)
        combo.setCurrentIndex(max(0, idx))
        return combo

    def _make_wave_combo(self, current_idx):
        combo = QComboBox()
        combo.setToolTip(
            "Wavelength index (into System → Wavelengths). 0 is the primary "
            "wavelength by default.")
        if self.system.wavelengths:
            for i, wl in enumerate(self.system.wavelengths):
                combo.addItem(f"{i}: {wl:.4f} μm", i)
        else:
            combo.addItem("0: 0.5876 μm", 0)
        idx = min(current_idx, combo.count() - 1)
        combo.setCurrentIndex(max(0, idx))
        return combo

    def _refresh_tables(self):
        self._syncing = True
        try:
            # --- Variables ---
            self.var_table.setRowCount(len(self.optimizer.variables))
            for i, v in enumerate(self.optimizer.variables):
                surf_combo = self._make_surface_combo(v.surface_idx)
                surf_combo.currentIndexChanged.connect(
                    lambda idx, row=i, c=surf_combo: self._on_var_surface_changed(row, c))
                self.var_table.setCellWidget(i, 0, surf_combo)

                param_combo = self._make_parameter_combo(v.parameter)
                param_combo.currentIndexChanged.connect(
                    lambda idx, row=i, c=param_combo: self._on_var_param_changed(row, c))
                self.var_table.setCellWidget(i, 1, param_combo)

                item_min = QTableWidgetItem(f"{v.min_val:.4g}")
                item_min.setToolTip(
                    "Lower bound for this variable (clamped during optimization).")
                self.var_table.setItem(i, 2, item_min)
                item_max = QTableWidgetItem(f"{v.max_val:.4g}")
                item_max.setToolTip("Upper bound for this variable.")
                self.var_table.setItem(i, 3, item_max)

            self.var_table.resizeColumnsToContents()
            self.var_table.horizontalHeader().setStretchLastSection(True)

            # --- Operands ---
            self.op_table.setRowCount(len(self.optimizer.operands))
            for i, op in enumerate(self.optimizer.operands):
                type_combo = self._make_operand_type_combo(op.type)
                type_combo.currentIndexChanged.connect(
                    lambda idx, row=i, c=type_combo: self._on_op_type_changed(row, c))
                self.op_table.setCellWidget(i, 0, type_combo)

                item_tgt = QTableWidgetItem(f"{op.target:.4g}")
                item_tgt.setToolTip(
                    "Desired value for this operand. SPOT/TRAY/AXCL usually "
                    "target 0; EFFL targets your focal length; DIMX targets "
                    "a thickness.")
                self.op_table.setItem(i, 1, item_tgt)

                item_w = QTableWidgetItem(f"{op.weight:.4g}")
                item_w.setToolTip(
                    "Relative importance. Higher weight = optimizer cares "
                    "more about hitting this operand's target. Set to 0 to "
                    "disable a row without deleting it.")
                self.op_table.setItem(i, 2, item_w)

                fld_combo = self._make_field_combo(op.field_idx)
                fld_combo.currentIndexChanged.connect(
                    lambda idx, row=i, c=fld_combo: self._on_op_field_changed(row, c))
                self.op_table.setCellWidget(i, 3, fld_combo)

                wv_combo = self._make_wave_combo(op.wave_idx)
                wv_combo.currentIndexChanged.connect(
                    lambda idx, row=i, c=wv_combo: self._on_op_wave_changed(row, c))
                self.op_table.setCellWidget(i, 4, wv_combo)

            self.op_table.resizeColumnsToContents()
            self.op_table.horizontalHeader().setStretchLastSection(True)
        finally:
            self._syncing = False

    # ------------------------------------------------------------------
    # Table change handlers
    # ------------------------------------------------------------------

    def _on_var_surface_changed(self, row, combo):
        if self._syncing:
            return
        if 0 <= row < len(self.optimizer.variables):
            data = combo.currentData()
            if data is not None:
                self.optimizer.variables[row].surface_idx = int(data)

    def _on_var_param_changed(self, row, combo):
        if self._syncing:
            return
        if 0 <= row < len(self.optimizer.variables):
            data = combo.currentData()
            if data is not None:
                self.optimizer.variables[row].parameter = str(data)

    def _on_var_item_changed(self, item):
        if self._syncing:
            return
        row = item.row()
        col = item.column()
        if row >= len(self.optimizer.variables):
            return
        try:
            val = float(item.text())
        except ValueError:
            return
        v = self.optimizer.variables[row]
        if col == 2:
            v.min_val = val
        elif col == 3:
            v.max_val = val

    def _on_op_type_changed(self, row, combo):
        if self._syncing:
            return
        if 0 <= row < len(self.optimizer.operands):
            data = combo.currentData()
            if data is not None:
                self.optimizer.operands[row].type = str(data)
                # Update description label if this row is selected
                if self.op_table.currentRow() == row:
                    self._show_op_description(str(data))

    def _on_op_field_changed(self, row, combo):
        if self._syncing:
            return
        if 0 <= row < len(self.optimizer.operands):
            self.optimizer.operands[row].field_idx = int(combo.currentData() or 0)

    def _on_op_wave_changed(self, row, combo):
        if self._syncing:
            return
        if 0 <= row < len(self.optimizer.operands):
            self.optimizer.operands[row].wave_idx = int(combo.currentData() or 0)

    def _on_op_item_changed(self, item):
        if self._syncing:
            return
        row = item.row()
        col = item.column()
        if row >= len(self.optimizer.operands):
            return
        try:
            val = float(item.text())
        except ValueError:
            return
        op = self.optimizer.operands[row]
        if col == 1:
            op.target = val
        elif col == 2:
            op.weight = val

    def _on_op_selection_changed(self, row, col, prev_row, prev_col):
        if 0 <= row < len(self.optimizer.operands):
            self._show_op_description(self.optimizer.operands[row].type)

    def _show_op_description(self, op_type):
        info = OPERAND_DESC.get(op_type)
        if info:
            label, desc, _t, _w = info
            self.op_desc_label.setText(f"<b>{label}</b> — {desc}")
        else:
            self.op_desc_label.setText("")

    # ------------------------------------------------------------------
    # Button actions
    # ------------------------------------------------------------------

    def _auto_variables(self):
        self.optimizer.variables.clear()
        for i, surf in enumerate(self.system.surfaces):
            if i == 0 or i == len(self.system.surfaces) - 1:
                continue
            if abs(surf.radius) < 1e10:
                self.optimizer.add_variable(i, "radius")
        self._refresh_tables()

    def _add_variable_dialog(self):
        dlg = _AddVariableDialog(self.system, self)
        if dlg.exec():
            surf_idx, param, min_v, max_v = dlg.get_result()
            if surf_idx is not None:
                self.optimizer.add_variable(int(surf_idx), str(param), min_v, max_v)
                self._refresh_tables()

    def _remove_variable(self):
        row = self.var_table.currentRow()
        if row >= 0:
            self.optimizer.remove_variable(row)
            self._refresh_tables()

    def _auto_operands(self):
        self.optimizer.auto_set_operands()
        self._refresh_tables()

    def _add_operand(self):
        # Default to SPOT which is the most common operand
        _label, _desc, tgt, w = OPERAND_DESC["SPOT"]
        self.optimizer.add_operand("SPOT", tgt, w)
        self._refresh_tables()

    def _remove_operand(self):
        row = self.op_table.currentRow()
        if 0 <= row < len(self.optimizer.operands):
            self.optimizer.operands.pop(row)
            self._refresh_tables()

    def _evaluate(self):
        merit = self.optimizer.evaluate_merit()
        self.merit_label.setText(f"Merit: {merit:.6f}")

    def _run_optimization(self):
        if not self.optimizer.variables:
            QMessageBox.warning(self, "No Variables",
                "Add at least one variable before optimizing.\n\n"
                "Click 'Auto-Set Variables' for a quick start.")
            return
        if not self.optimizer.operands:
            QMessageBox.warning(self, "No Operands",
                "Add at least one operand to the merit function.\n\n"
                "Click 'Default MF' for a standard spot-size merit function.")
            return

        self.optimizer.damping = self.damping_spin.value()
        max_iter = self.iter_spin.value()

        self.btn_optimize.setEnabled(False)
        self.progress_bar.setMaximum(max_iter)

        self._thread = OptimizationThread(self.optimizer, max_iter)
        self._thread.progress.connect(self._on_progress)
        self._thread.finished_signal.connect(self._on_finished)
        self._thread.start()

    def _on_progress(self, iteration, merit):
        self.progress_bar.setValue(iteration)
        self.merit_label.setText(f"Iteration {iteration}: Merit = {merit:.6f}")

    def _on_finished(self, result: OptimizationResult):
        self.btn_optimize.setEnabled(True)
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.merit_label.setText(
            f"Done: {result.message} | Initial: {result.initial_merit:.6f} "
            f"| Final: {result.final_merit:.6f}")
        self._refresh_tables()
        self.optimization_complete.emit()


class AsphericEditDialog(QDialog):
    """Editor for conic constant and even-asphere polynomial coefficients."""

    # Coefficient labels following Zemax convention: A4, A6, A8, ... A16
    COEFF_LABELS = [
        ("A4",  "4th-order (primary spherical)"),
        ("A6",  "6th-order"),
        ("A8",  "8th-order"),
        ("A10", "10th-order"),
        ("A12", "12th-order"),
        ("A14", "14th-order"),
        ("A16", "16th-order"),
    ]

    def __init__(self, surface: 'Surface', surface_idx: int, parent=None):
        super().__init__(parent)
        from ..engine.surface import Surface  # avoid circular at module level
        self.surface = surface
        self.setWindowTitle(f"Aspheric Coefficients — Surface {surface_idx}")
        self.setMinimumWidth(460)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Help text
        help_lbl = QLabel(
            "Even-asphere sag:  z = <i>c r</i><sup>2</sup> / "
            "(1 + sqrt(1 - (1+k) <i>c</i><sup>2</sup> <i>r</i><sup>2</sup>)) "
            "+ A<sub>4</sub> r<sup>4</sup> + A<sub>6</sub> r<sup>6</sup> + ..."
        )
        help_lbl.setWordWrap(True)
        help_lbl.setStyleSheet("color: #a6adc8; padding: 4px;")
        layout.addWidget(help_lbl)

        form = QFormLayout()

        # Conic constant
        self.conic_edit = QLineEdit(self._fmt(self.surface.conic))
        self.conic_edit.setToolTip(
            "Conic constant k:\n"
            "  k = 0     sphere\n"
            "  k = -1    parabola\n"
            "  k < -1    hyperbola\n"
            "  -1 < k < 0  prolate ellipse\n"
            "  k > 0     oblate ellipse")
        form.addRow("Conic (k):", self.conic_edit)

        form.addRow(QLabel(""))  # spacer

        # Coefficient fields
        self.coeff_edits = []
        existing = self.surface.aspheric_coeffs
        for i, (label, desc) in enumerate(self.COEFF_LABELS):
            val = existing[i] if i < len(existing) else 0.0
            edit = QLineEdit(self._fmt(val))
            edit.setToolTip(f"{label}: {desc}\n"
                            f"Multiplied by r^{2*(i+2)}. "
                            "Use scientific notation, e.g. 1.5e-6")
            form.addRow(f"{label}:", edit)
            self.coeff_edits.append(edit)

        layout.addLayout(form)

        # Buttons
        btn_row = QHBoxLayout()

        btn_clear = QPushButton("Clear All")
        btn_clear.setToolTip("Set all coefficients to zero.")
        btn_clear.clicked.connect(self._clear_all)
        btn_row.addWidget(btn_clear)

        btn_row.addStretch()

        btn_ok = QPushButton("OK")
        btn_ok.setObjectName("primaryButton")
        btn_ok.clicked.connect(self._apply_and_accept)
        btn_row.addWidget(btn_ok)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        layout.addLayout(btn_row)

    @staticmethod
    def _fmt(val: float) -> str:
        if val == 0.0:
            return "0"
        if abs(val) < 1e-3 or abs(val) >= 1e6:
            return f"{val:.10e}"
        return f"{val:.10g}"

    def _clear_all(self):
        self.conic_edit.setText("0")
        for edit in self.coeff_edits:
            edit.setText("0")

    def _apply_and_accept(self):
        try:
            self.surface.conic = float(self.conic_edit.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid value",
                                "Conic constant must be a number.")
            return

        coeffs = []
        for i, edit in enumerate(self.coeff_edits):
            try:
                coeffs.append(float(edit.text()))
            except ValueError:
                label = self.COEFF_LABELS[i][0]
                QMessageBox.warning(self, "Invalid value",
                                    f"{label} must be a number (e.g. 1.5e-6).")
                return

        # Trim trailing zeros
        while coeffs and coeffs[-1] == 0.0:
            coeffs.pop()

        self.surface.aspheric_coeffs = coeffs
        self.accept()


class GlassCatalogDialog(QDialog):
    """Glass catalog browser with custom glass support."""

    def __init__(self, parent=None, select_mode=False):
        super().__init__(parent)
        self.setWindowTitle("Glass Catalog")
        self.setMinimumSize(600, 500)
        self.selected_glass = ""
        self._select_mode = select_mode
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter by name...")
        self.search_edit.textChanged.connect(self._filter)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Name", "nd", "vd", "Type", "Sellmeier B1"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 70)
        self.table.setColumnWidth(3, 70)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_double_click)
        self.table.currentCellChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)

        self._populate()

        # Detail panel for selected glass
        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("padding: 4px; font-family: monospace;")
        layout.addWidget(self.detail_label)

        # Buttons
        btns = QHBoxLayout()

        btn_add = QPushButton("Add Custom...")
        btn_add.clicked.connect(self._add_custom)
        btns.addWidget(btn_add)

        self.btn_edit = QPushButton("Edit...")
        self.btn_edit.clicked.connect(self._edit_custom)
        self.btn_edit.setEnabled(False)
        btns.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self._delete_custom)
        self.btn_delete.setEnabled(False)
        btns.addWidget(self.btn_delete)

        btns.addSpacing(10)

        btn_load = QPushButton("Load Catalog...")
        btn_load.clicked.connect(self._load_catalog)
        btns.addWidget(btn_load)

        btn_save = QPushButton("Save Custom...")
        btn_save.clicked.connect(self._save_catalog)
        btns.addWidget(btn_save)

        btns.addStretch()

        if self._select_mode:
            btn_ok = QPushButton("Select")
            btn_ok.clicked.connect(self._select_glass)
            btns.addWidget(btn_ok)

        btn_close = QPushButton("Cancel" if self._select_mode else "Close")
        btn_close.clicked.connect(self.reject)
        btns.addWidget(btn_close)

        layout.addLayout(btns)

    def _populate(self):
        glasses = sorted(GLASS_CATALOG.values(), key=lambda g: g.name)

        self.table.setRowCount(len(glasses))
        for i, glass in enumerate(glasses):
            name_item = QTableWidgetItem(glass.name)
            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, QTableWidgetItem(f"{glass.nd:.5f}"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{glass.vd:.2f}"))

            gtype = "Custom" if is_custom_glass(glass.name) else "Built-in"
            type_item = QTableWidgetItem(gtype)
            self.table.setItem(i, 3, type_item)

            has_sellmeier = glass.B1 != 0 or glass.B2 != 0
            b1_text = f"{glass.B1:.8f}" if has_sellmeier else "(Cauchy)"
            self.table.setItem(i, 4, QTableWidgetItem(b1_text))

            # Tint custom glass rows
            if gtype == "Custom":
                from PyQt6.QtGui import QColor
                for c in range(5):
                    item = self.table.item(i, c)
                    if item:
                        item.setForeground(QColor("#a6e3a1"))

    def _filter(self, text):
        for i in range(self.table.rowCount()):
            name = self.table.item(i, 0).text()
            self.table.setRowHidden(i, text.upper() not in name.upper())

    def _on_selection_changed(self, row, col, prev_row, prev_col):
        if row < 0:
            self.detail_label.setText("")
            self.btn_edit.setEnabled(False)
            self.btn_delete.setEnabled(False)
            return
        name = self.table.item(row, 0).text()
        glass = GLASS_CATALOG.get(name.upper())
        if not glass:
            return
        custom = is_custom_glass(name)
        self.btn_edit.setEnabled(custom)
        self.btn_delete.setEnabled(custom)

        has_s = glass.B1 != 0 or glass.B2 != 0
        model = "Sellmeier" if has_s else "Cauchy (nd/vd only)"
        detail = (f"{glass.name}  nd={glass.nd:.5f}  vd={glass.vd:.2f}  [{model}]")
        if has_s:
            detail += (f"\nB1={glass.B1:.10f}  B2={glass.B2:.10f}  B3={glass.B3:.10f}"
                       f"\nC1={glass.C1:.10f}  C2={glass.C2:.10f}  C3={glass.C3:.10f}")
        self.detail_label.setText(detail)

    def _on_double_click(self):
        if self._select_mode:
            self._select_glass()
        else:
            row = self.table.currentRow()
            if row >= 0:
                name = self.table.item(row, 0).text()
                if is_custom_glass(name):
                    self._edit_custom()

    def _select_glass(self):
        row = self.table.currentRow()
        if row >= 0:
            self.selected_glass = self.table.item(row, 0).text()
            self.accept()

    def _add_custom(self):
        dlg = _GlassEditDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            g = dlg.get_glass_data()
            add_custom_glass(**g)
            self._populate()

    def _edit_custom(self):
        row = self.table.currentRow()
        if row < 0:
            return
        name = self.table.item(row, 0).text()
        glass = GLASS_CATALOG.get(name.upper())
        if not glass or not is_custom_glass(name):
            return
        dlg = _GlassEditDialog(self, glass)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            g = dlg.get_glass_data()
            # Remove old name in case it was renamed
            remove_custom_glass(name)
            add_custom_glass(**g)
            self._populate()

    def _delete_custom(self):
        row = self.table.currentRow()
        if row < 0:
            return
        name = self.table.item(row, 0).text()
        if not is_custom_glass(name):
            return
        reply = QMessageBox.question(self, "Delete Glass",
                                      f"Delete custom glass '{name}'?",
                                      QMessageBox.StandardButton.Yes |
                                      QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            remove_custom_glass(name)
            self._populate()

    def _load_catalog(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Glass Catalog", "", "Glass Catalog (*.json);;All Files (*)")
        if path:
            try:
                count = load_glass_catalog(path)
                self._populate()
                QMessageBox.information(self, "Loaded",
                                         f"Loaded {count} glass(es) from catalog.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load catalog:\n{e}")

    def _save_catalog(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Custom Glasses", "custom_glasses.json",
            "Glass Catalog (*.json);;All Files (*)")
        if path:
            try:
                save_glass_catalog(path)
                QMessageBox.information(self, "Saved",
                                         f"Custom glasses saved to {path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save catalog:\n{e}")


class _GlassEditDialog(QDialog):
    """Dialog for adding/editing a custom glass."""

    def __init__(self, parent=None, glass: Glass = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Glass" if glass else "Add Custom Glass")
        self.setMinimumWidth(350)
        self._setup_ui(glass)

    def _setup_ui(self, glass):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(glass.name if glass else "")
        self.name_edit.setPlaceholderText("e.g. MY-GLASS-1")
        form.addRow("Name:", self.name_edit)

        self.nd_spin = QDoubleSpinBox()
        self.nd_spin.setRange(1.0, 3.0)
        self.nd_spin.setDecimals(5)
        self.nd_spin.setValue(glass.nd if glass else 1.52000)
        form.addRow("nd:", self.nd_spin)

        self.vd_spin = QDoubleSpinBox()
        self.vd_spin.setRange(0.0, 100.0)
        self.vd_spin.setDecimals(2)
        self.vd_spin.setValue(glass.vd if glass else 60.00)
        form.addRow("vd:", self.vd_spin)

        layout.addLayout(form)

        # Sellmeier group
        sellmeier_group = QGroupBox("Sellmeier Coefficients (optional)")
        sf = QFormLayout()

        self.b_spins = []
        self.c_spins = []
        for label, val in [("B1", glass.B1 if glass else 0.0),
                           ("B2", glass.B2 if glass else 0.0),
                           ("B3", glass.B3 if glass else 0.0)]:
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 10.0)
            spin.setDecimals(10)
            spin.setValue(val)
            sf.addRow(f"{label}:", spin)
            self.b_spins.append(spin)

        for label, val in [("C1", glass.C1 if glass else 0.0),
                           ("C2", glass.C2 if glass else 0.0),
                           ("C3", glass.C3 if glass else 0.0)]:
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 1000.0)
            spin.setDecimals(10)
            spin.setValue(val)
            sf.addRow(f"{label}:", spin)
            self.c_spins.append(spin)

        sellmeier_group.setLayout(sf)
        layout.addWidget(sellmeier_group)

        info = QLabel("Leave Sellmeier coefficients at 0 to use Cauchy approximation from nd/vd.")
        info.setWordWrap(True)
        info.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(info)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self._validate_and_accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

    def _validate_and_accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Glass name cannot be empty.")
            return
        self.accept()

    def get_glass_data(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "nd": self.nd_spin.value(),
            "vd": self.vd_spin.value(),
            "B1": self.b_spins[0].value(),
            "B2": self.b_spins[1].value(),
            "B3": self.b_spins[2].value(),
            "C1": self.c_spins[0].value(),
            "C2": self.c_spins[1].value(),
            "C3": self.c_spins[2].value(),
        }
