"""Lens Data Editor - spreadsheet-like surface table."""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
                              QTableWidgetItem, QHeaderView, QPushButton,
                              QMenu, QAbstractItemView, QLabel, QComboBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont

from ..engine.surface import LensSystem, Surface, SurfaceType, SolveType
from ..engine.materials import get_glass, available_glasses


class LensDataEditor(QWidget):
    """Spreadsheet-style lens data editor similar to Zemax LDE."""

    system_changed = pyqtSignal()
    surface_selected = pyqtSignal(int)  # emits surface index when row is selected

    COLUMNS = ["Surf", "Comment", "Radius", "Thickness", "Material",
               "Semi-Diameter", "Conic"]

    def __init__(self, system: LensSystem, parent=None):
        super().__init__(parent)
        self.system = system
        self._updating = False
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel("Lens Data Editor")
        title_label.setObjectName("headerLabel")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        btn_insert = QPushButton("+ Insert")
        btn_insert.clicked.connect(self._insert_surface)
        btn_delete = QPushButton("- Delete")
        btn_delete.clicked.connect(self._delete_surface)
        btn_insert.setFixedWidth(80)
        btn_delete.setFixedWidth(80)

        btn_up = QPushButton("\u25b2")  # ▲
        btn_up.setToolTip("Move element up (swaps with previous element group)")
        btn_up.setFixedWidth(30)
        btn_up.clicked.connect(lambda: self._move_element(-1))

        btn_down = QPushButton("\u25bc")  # ▼
        btn_down.setToolTip("Move element down (swaps with next element group)")
        btn_down.setFixedWidth(30)
        btn_down.clicked.connect(lambda: self._move_element(1))

        header_layout.addWidget(btn_insert)
        header_layout.addWidget(btn_delete)
        header_layout.addWidget(btn_up)
        header_layout.addWidget(btn_down)
        layout.addLayout(header_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.verticalHeader().setVisible(False)

        # Column widths
        widths = [55, 90, 100, 100, 85, 100, 80]
        for i, w in enumerate(widths):
            self.table.setColumnWidth(i, w)

        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.currentCellChanged.connect(self._on_row_changed)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.table)

    def set_system(self, system: LensSystem):
        self.system = system
        self.refresh()

    def refresh(self):
        """Rebuild table from system data."""
        self._updating = True
        self.table.setRowCount(len(self.system.surfaces))

        for i, surf in enumerate(self.system.surfaces):
            # Surface number (with stop indicator)
            if i == 0:
                label = "OBJ"
            elif i == len(self.system.surfaces) - 1:
                label = "IMA"
            elif surf.is_stop:
                label = f"{i} STO"
            else:
                label = str(i)
            self._set_item(i, 0, label, editable=False)

            # Comment
            self._set_item(i, 1, surf.comment)

            # Radius (append V if variable)
            r_suffix = "  V" if surf.radius_solve == SolveType.VARIABLE else ""
            if abs(surf.radius) > 1e10:
                self._set_item(i, 2, "Infinity" + r_suffix)
            else:
                self._set_item(i, 2, f"{surf.radius:.6f}{r_suffix}")

            # Thickness (append V if variable)
            t_suffix = "  V" if surf.thickness_solve == SolveType.VARIABLE else ""
            if abs(surf.thickness) > 1e10:
                self._set_item(i, 3, "Infinity" + t_suffix)
            else:
                self._set_item(i, 3, f"{surf.thickness:.6f}{t_suffix}")

            # Material
            self._set_item(i, 4, surf.material)

            # Semi-Diameter
            self._set_item(i, 5, f"{surf.semi_diameter:.4f}")

            # Conic (show [A] indicator if aspheric coefficients are present)
            conic_text = f"{surf.conic:.6f}"
            if surf.aspheric_coeffs and any(c != 0 for c in surf.aspheric_coeffs):
                conic_text += "  [A]"
            self._set_item(i, 6, conic_text)

            # Color coding
            if surf.material and surf.material.upper() not in ("", "AIR"):
                for c in range(len(self.COLUMNS)):
                    item = self.table.item(i, c)
                    if item:
                        item.setBackground(QColor("#1e3a5f"))
            if surf.is_stop:
                for c in range(len(self.COLUMNS)):
                    item = self.table.item(i, c)
                    if item:
                        item.setForeground(QColor("#f9e2af"))
            # Highlight variable cells with a tint
            if surf.radius_solve == SolveType.VARIABLE:
                item = self.table.item(i, 2)
                if item:
                    item.setForeground(QColor("#a6e3a1"))  # green for variable
            if surf.thickness_solve == SolveType.VARIABLE:
                item = self.table.item(i, 3)
                if item:
                    item.setForeground(QColor("#a6e3a1"))

        self._updating = False

    def _set_item(self, row, col, text, editable=True):
        item = QTableWidgetItem(str(text))
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, col, item)

    def _on_row_changed(self, current_row, current_col, prev_row, prev_col):
        if not self._updating and current_row >= 0:
            self.surface_selected.emit(current_row)

    def _on_cell_double_clicked(self, row, col):
        """Handle double-click: Material col → glass picker, Conic col → aspheric editor."""
        if row < 0 or row >= len(self.system.surfaces):
            return
        if col == 4:  # Material column
            from .dialogs import GlassCatalogDialog
            dlg = GlassCatalogDialog(self, select_mode=True)
            if dlg.exec():
                glass_name = dlg.selected_glass
                self.system.surfaces[row].material = glass_name
                self._updating = True
                self.table.item(row, 4).setText(glass_name)
                self._updating = False
                self.refresh()
                self.system_changed.emit()
        elif col == 6:  # Conic column → open aspheric editor
            self._open_aspheric_editor(row)

    def select_surface(self, index: int):
        """Select a row in the table programmatically."""
        if 0 <= index < self.table.rowCount():
            self._updating = True
            self.table.setCurrentCell(index, 0)
            self._updating = False

    def _on_cell_changed(self, row, col):
        if self._updating:
            return
        if row < 0 or row >= len(self.system.surfaces):
            return

        surf = self.system.surfaces[row]
        item = self.table.item(row, col)
        if not item:
            return
        text = item.text().strip()

        try:
            if col == 1:  # Comment
                surf.comment = text
            elif col == 2:  # Radius
                # Detect V suffix to toggle variable solve
                has_v = text.rstrip().upper().endswith("V")
                val_text = text.upper().replace("V", "").strip()
                if val_text.lower() in ("inf", "infinity", ""):
                    surf.radius = float('inf')
                else:
                    surf.radius = float(val_text)
                surf.radius_solve = SolveType.VARIABLE if has_v else SolveType.FIXED
            elif col == 3:  # Thickness
                has_v = text.rstrip().upper().endswith("V")
                val_text = text.upper().replace("V", "").strip()
                if val_text.lower() in ("inf", "infinity"):
                    surf.thickness = float('inf')
                else:
                    surf.thickness = float(val_text)
                surf.thickness_solve = SolveType.VARIABLE if has_v else SolveType.FIXED
            elif col == 4:  # Material
                surf.material = text.upper()
            elif col == 5:  # Semi-Diameter
                surf.semi_diameter = float(text)
            elif col == 6:  # Conic (strip "[A]" indicator if present)
                surf.conic = float(text.replace("[A]", "").strip())
        except ValueError:
            pass

        self.system_changed.emit()

    def _insert_surface(self):
        row = self.table.currentRow()
        if row < 1:
            row = len(self.system.surfaces) - 1
        self.system.insert_surface(row)
        self.refresh()
        self.system_changed.emit()

    def _delete_surface(self):
        row = self.table.currentRow()
        if row > 0 and row < len(self.system.surfaces) - 1:
            self.system.delete_surface(row)
            self.refresh()
            self.system_changed.emit()

    def _open_aspheric_editor(self, row):
        """Open the aspheric coefficient editor for the given surface."""
        if row < 0 or row >= len(self.system.surfaces):
            return
        from .dialogs import AsphericEditDialog
        surf = self.system.surfaces[row]
        dlg = AsphericEditDialog(surf, row, self)
        if dlg.exec():
            self.refresh()
            self.system_changed.emit()

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        row = self.table.rowAt(pos.y())

        insert_before = QAction("Insert Surface Before", self)
        insert_before.triggered.connect(lambda: self._insert_at(row))
        menu.addAction(insert_before)

        insert_after = QAction("Insert Surface After", self)
        insert_after.triggered.connect(lambda: self._insert_at(row + 1))
        menu.addAction(insert_after)

        menu.addSeparator()

        delete_action = QAction("Delete Surface", self)
        delete_action.triggered.connect(lambda: self._delete_at(row))
        delete_action.setEnabled(0 < row < len(self.system.surfaces) - 1)
        menu.addAction(delete_action)

        menu.addSeparator()

        set_stop = QAction("Set as Stop", self)
        set_stop.triggered.connect(lambda: self._set_stop(row))
        set_stop.setEnabled(0 < row < len(self.system.surfaces) - 1)
        menu.addAction(set_stop)

        aspheric_action = QAction("Edit Aspheric Coefficients...", self)
        aspheric_action.triggered.connect(lambda: self._open_aspheric_editor(row))
        aspheric_action.setEnabled(0 <= row < len(self.system.surfaces))
        menu.addAction(aspheric_action)

        menu.addSeparator()

        move_up = QAction("Move Element Up", self)
        move_up.triggered.connect(lambda: self._move_element(-1))
        elem = self._element_for_surface(row) if 0 < row < len(self.system.surfaces) - 1 else None
        elements = self._detect_elements()
        if elem and elements:
            ei = elements.index(elem) if elem in elements else -1
            move_up.setEnabled(ei > 0)
        else:
            move_up.setEnabled(False)
        menu.addAction(move_up)

        move_down = QAction("Move Element Down", self)
        move_down.triggered.connect(lambda: self._move_element(1))
        if elem and elements:
            ei = elements.index(elem) if elem in elements else -1
            move_down.setEnabled(0 <= ei < len(elements) - 1)
        else:
            move_down.setEnabled(False)
        menu.addAction(move_down)

        menu.addSeparator()

        make_variable_r = QAction("Make Radius Variable", self)
        make_variable_r.triggered.connect(lambda: self._toggle_variable(row, "radius"))
        menu.addAction(make_variable_r)

        make_variable_t = QAction("Make Thickness Variable", self)
        make_variable_t.triggered.connect(lambda: self._toggle_variable(row, "thickness"))
        menu.addAction(make_variable_t)

        menu.exec(self.table.mapToGlobal(pos))

    def _insert_at(self, idx):
        if idx < 1:
            idx = 1
        if idx >= len(self.system.surfaces):
            idx = len(self.system.surfaces) - 1
        self.system.insert_surface(idx)
        self.refresh()
        self.system_changed.emit()

    def _delete_at(self, idx):
        if 0 < idx < len(self.system.surfaces) - 1:
            self.system.delete_surface(idx)
            self.refresh()
            self.system_changed.emit()

    def _set_stop(self, idx):
        self.system.stop_surface = idx
        self.refresh()
        self.system_changed.emit()

    def _toggle_variable(self, row, param):
        if row < 0 or row >= len(self.system.surfaces):
            return
        surf = self.system.surfaces[row]
        if param == "radius":
            if surf.radius_solve == SolveType.VARIABLE:
                surf.radius_solve = SolveType.FIXED
            else:
                surf.radius_solve = SolveType.VARIABLE
        elif param == "thickness":
            if surf.thickness_solve == SolveType.VARIABLE:
                surf.thickness_solve = SolveType.FIXED
            else:
                surf.thickness_solve = SolveType.VARIABLE
        self.refresh()

    # ------------------------------------------------------------------
    # Element detection and reordering
    # ------------------------------------------------------------------

    def _detect_elements(self):
        """Identify element groups: contiguous glass runs + their back surface.

        Returns a list of (start, end) index tuples.  Each tuple covers
        surfaces ``start`` through ``end`` *inclusive*; ``surfaces[end]``
        is the back face of the element (its thickness is the air gap
        following the element).

        OBJ (index 0) and IMA (last index) are never included.
        Air-only surfaces between elements are standalone (start == end).
        """
        surfs = self.system.surfaces
        n = len(surfs)
        elements = []
        i = 1                       # skip OBJ
        last = n - 1               # skip IMA
        while i < last:
            mat = surfs[i].material
            if mat and mat.upper() not in ("", "AIR", "MIRROR"):
                # Start of a glass run
                start = i
                while (i < last and surfs[i].material
                       and surfs[i].material.upper() not in ("", "AIR", "MIRROR")):
                    i += 1
                # i is now the back surface (air/empty material)
                elements.append((start, i))
                i += 1
            else:
                # Standalone air surface (e.g. a remote stop)
                elements.append((i, i))
                i += 1
        return elements

    def _element_for_surface(self, surf_idx):
        """Return the element (start, end) that contains *surf_idx*, or None."""
        for elem in self._detect_elements():
            if elem[0] <= surf_idx <= elem[1]:
                return elem
        return None

    def _move_element(self, direction: int):
        """Move the element containing the selected row up (-1) or down (+1).

        Air gaps stay at their positional slot: only the glass surfaces
        are swapped, then the gap thicknesses are restored to their
        original positions so the surrounding spacing is preserved.
        """
        row = self.table.currentRow()
        if row <= 0 or row >= len(self.system.surfaces) - 1:
            return

        elements = self._detect_elements()
        if len(elements) < 2:
            return

        # Find which element index owns this row
        elem_idx = None
        for ei, (s, e) in enumerate(elements):
            if s <= row <= e:
                elem_idx = ei
                break
        if elem_idx is None:
            return

        # Determine the neighbour to swap with
        swap_idx = elem_idx + direction
        if swap_idx < 0 or swap_idx >= len(elements):
            return

        # Always order so that A is before B
        if direction < 0:
            idx_a, idx_b = swap_idx, elem_idx
        else:
            idx_a, idx_b = elem_idx, swap_idx

        start_a, end_a = elements[idx_a]
        start_b, end_b = elements[idx_b]

        surfs = self.system.surfaces

        # Save the air-gap thicknesses at each positional slot
        gap_a = surfs[end_a].thickness
        gap_b = surfs[end_b].thickness

        # Extract surface groups (references)
        group_a = surfs[start_a:end_a + 1]
        group_b = surfs[start_b:end_b + 1]

        # Rebuild the surface list with groups swapped
        before = surfs[:start_a]
        after = surfs[end_b + 1:]
        between = surfs[end_a + 1:start_b]  # surfaces between the groups (usually none)

        new_surfs = before + group_b + between + group_a + after

        # Restore positional air gaps.  After the swap, group_b occupies
        # the first slot and group_a occupies the second slot.
        len_b = len(group_b)
        len_between = len(between)
        # Back surface of group_b (now in first position)
        new_surfs[start_a + len_b - 1].thickness = gap_a
        # Back surface of group_a (now in second position)
        new_surfs[start_a + len_b + len_between + len(group_a) - 1].thickness = gap_b

        self.system.surfaces = new_surfs

        # Select the moved element so the user can keep pressing the key
        if direction < 0:
            new_start = start_a
        else:
            new_start = start_a + len_b + len_between

        self.refresh()
        self.select_surface(new_start)
        self.system_changed.emit()
