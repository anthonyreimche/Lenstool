"""Main application window with docking panels, menus, and toolbars."""

import os
from PyQt6.QtWidgets import (QMainWindow, QDockWidget, QTabWidget, QMenuBar,
                              QToolBar, QStatusBar, QFileDialog, QMessageBox,
                              QApplication, QWidget, QVBoxLayout, QLabel,
                              QSplitter)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QAction, QFont, QIcon, QKeySequence

from ..engine.surface import LensSystem
from ..engine.fileio import (save_lens, load_lens, create_sample_doublet,
                              create_sample_cooke_triplet, create_sample_singlet,
                              create_sample_double_gauss, create_sample_petzval,
                              create_sample_telephoto, create_sample_landscape)
from ..engine.raytrace import compute_efl
from ..engine.analysis import system_summary

from .theme import DARK_STYLESHEET
from .lens_editor import LensDataEditor
from .layout_viewer import LayoutViewer
from .analysis_plots import (SpotDiagramWidget, MTFWidget, RayFanWidget,
                              FieldCurvatureWidget, SystemInfoWidget)
from .optimization_widget import OptimizationWidget
from .dialogs import (SystemSettingsDialog, GlassCatalogDialog)


class MainWindow(QMainWindow):
    """LensTool main application window."""

    def __init__(self):
        super().__init__()
        self.system = create_sample_doublet()
        self.current_file = None

        self.setWindowTitle("LensTool - Optical Lens Design")
        self.setMinimumSize(1200, 750)
        self.resize(1500, 900)

        self._setup_menus()
        self._setup_toolbar()
        self._setup_panels()
        self._setup_statusbar()
        self._update_title()
        self._refresh_all()

    def _setup_menus(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        new_action = QAction("&New System", self)
        new_action.setShortcut(QKeySequence("Ctrl+N"))
        new_action.triggered.connect(self._new_system)
        file_menu.addAction(new_action)

        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)

        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self._save_file)
        file_menu.addAction(save_action)

        saveas_action = QAction("Save &As...", self)
        saveas_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        saveas_action.triggered.connect(self._save_file_as)
        file_menu.addAction(saveas_action)

        file_menu.addSeparator()

        # Sample lenses submenu
        samples_menu = file_menu.addMenu("Sample Lenses")

        singlet = QAction("Plano-Convex Singlet", self)
        singlet.triggered.connect(lambda: self._load_sample(create_sample_singlet))
        samples_menu.addAction(singlet)

        doublet = QAction("Cemented Doublet", self)
        doublet.triggered.connect(lambda: self._load_sample(create_sample_doublet))
        samples_menu.addAction(doublet)

        triplet = QAction("Cooke Triplet", self)
        triplet.triggered.connect(lambda: self._load_sample(create_sample_cooke_triplet))
        samples_menu.addAction(triplet)

        dgauss = QAction("Double Gauss", self)
        dgauss.triggered.connect(lambda: self._load_sample(create_sample_double_gauss))
        samples_menu.addAction(dgauss)

        petzval = QAction("Petzval Lens", self)
        petzval.triggered.connect(lambda: self._load_sample(create_sample_petzval))
        samples_menu.addAction(petzval)

        telephoto = QAction("Telephoto", self)
        telephoto.triggered.connect(lambda: self._load_sample(create_sample_telephoto))
        samples_menu.addAction(telephoto)

        landscape = QAction("Landscape Meniscus", self)
        landscape.triggered.connect(lambda: self._load_sample(create_sample_landscape))
        samples_menu.addAction(landscape)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Alt+F4"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        insert_surf = QAction("Insert Surface", self)
        insert_surf.setShortcut(QKeySequence("Ctrl+Insert"))
        insert_surf.triggered.connect(lambda: self.editor._insert_surface())
        edit_menu.addAction(insert_surf)

        delete_surf = QAction("Delete Surface", self)
        delete_surf.setShortcut(QKeySequence("Ctrl+Delete"))
        delete_surf.triggered.connect(lambda: self.editor._delete_surface())
        edit_menu.addAction(delete_surf)

        edit_menu.addSeparator()

        sys_settings = QAction("System Settings...", self)
        sys_settings.setShortcut(QKeySequence("Ctrl+E"))
        sys_settings.triggered.connect(self._show_system_settings)
        edit_menu.addAction(sys_settings)

        glass_catalog = QAction("Glass Catalog...", self)
        glass_catalog.setShortcut(QKeySequence("Ctrl+G"))
        glass_catalog.triggered.connect(self._show_glass_catalog)
        edit_menu.addAction(glass_catalog)

        # Analysis menu
        analysis_menu = menubar.addMenu("&Analysis")

        spot_action = QAction("Spot Diagram", self)
        spot_action.setShortcut(QKeySequence("F3"))
        spot_action.triggered.connect(lambda: self._show_analysis_tab(0))
        analysis_menu.addAction(spot_action)

        mtf_action = QAction("MTF", self)
        mtf_action.setShortcut(QKeySequence("F4"))
        mtf_action.triggered.connect(lambda: self._show_analysis_tab(1))
        analysis_menu.addAction(mtf_action)

        fan_action = QAction("Ray Fan", self)
        fan_action.setShortcut(QKeySequence("F5"))
        fan_action.triggered.connect(lambda: self._show_analysis_tab(2))
        analysis_menu.addAction(fan_action)

        fc_action = QAction("Field Curvature / Distortion", self)
        fc_action.setShortcut(QKeySequence("F6"))
        fc_action.triggered.connect(lambda: self._show_analysis_tab(3))
        analysis_menu.addAction(fc_action)

        analysis_menu.addSeparator()

        refresh_action = QAction("Refresh All", self)
        refresh_action.setShortcut(QKeySequence("F2"))
        refresh_action.triggered.connect(self._refresh_all)
        analysis_menu.addAction(refresh_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        opt_action = QAction("Optimization...", self)
        opt_action.setShortcut(QKeySequence("Ctrl+M"))
        opt_action.triggered.connect(self._show_optimization)
        tools_menu.addAction(opt_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        self._dock_actions = {}
        # Populated after docks are created

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about = QAction("About LensTool", self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

    def _setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(toolbar)

        # Use text-based tool buttons
        actions = [
            ("New", self._new_system),
            ("Open", self._open_file),
            ("Save", self._save_file),
            None,  # separator
            ("Settings", self._show_system_settings),
            ("Glass", self._show_glass_catalog),
            None,
            ("Spot", lambda: self._show_analysis_tab(0)),
            ("MTF", lambda: self._show_analysis_tab(1)),
            ("Fans", lambda: self._show_analysis_tab(2)),
            ("F/C", lambda: self._show_analysis_tab(3)),
            None,
            ("Optimize", self._show_optimization),
            None,
            ("Refresh", self._refresh_all),
        ]

        for item in actions:
            if item is None:
                toolbar.addSeparator()
            else:
                name, callback = item
                action = QAction(name, self)
                action.triggered.connect(callback)
                toolbar.addAction(action)

    def _setup_panels(self):
        # Central: Splitter with Layout Viewer on top, Editor on bottom
        central = QSplitter(Qt.Orientation.Vertical)

        self.layout_viewer = LayoutViewer(self.system)
        self.layout_viewer.surface_clicked.connect(self._on_layout_surface_clicked)
        central.addWidget(self.layout_viewer)

        self.editor = LensDataEditor(self.system)
        self.editor.system_changed.connect(self._on_system_changed)
        self.editor.surface_selected.connect(self._on_editor_surface_selected)
        central.addWidget(self.editor)

        central.setSizes([450, 350])
        self.setCentralWidget(central)

        # Right dock: Analysis tabs
        analysis_dock = QDockWidget("Analysis", self)
        analysis_dock.setMinimumWidth(380)

        self.analysis_tabs = QTabWidget()

        self.spot_widget = SpotDiagramWidget(self.system)
        self.analysis_tabs.addTab(self.spot_widget, "Spot Diagram")

        self.mtf_widget = MTFWidget(self.system)
        self.analysis_tabs.addTab(self.mtf_widget, "MTF")

        self.rayfan_widget = RayFanWidget(self.system)
        self.analysis_tabs.addTab(self.rayfan_widget, "Ray Fans")

        self.fc_widget = FieldCurvatureWidget(self.system)
        self.analysis_tabs.addTab(self.fc_widget, "Field Curv.")

        self.info_widget = SystemInfoWidget(self.system)
        self.analysis_tabs.addTab(self.info_widget, "System Info")

        self.opt_widget = OptimizationWidget(self.system)
        self.opt_widget.optimization_complete.connect(self._on_optimization_complete)
        self.analysis_tabs.addTab(self.opt_widget, "Optimize")

        analysis_dock.setWidget(self.analysis_tabs)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, analysis_dock)

        # Add toggle actions to View menu
        view_menu = self.menuBar().actions()[3].menu()  # View menu
        if view_menu:
            view_menu.addAction(analysis_dock.toggleViewAction())

    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        self.status_efl = QLabel("EFL: --")
        self.status_fno = QLabel("F/#: --")
        self.status_track = QLabel("Track: --")
        self.status_surfs = QLabel("Surfaces: --")

        for label in [self.status_efl, self.status_fno, self.status_track, self.status_surfs]:
            label.setStyleSheet("padding: 0 12px;")
            self.statusbar.addPermanentWidget(label)

    def _update_title(self):
        fname = os.path.basename(self.current_file) if self.current_file else "Untitled"
        self.setWindowTitle(f"LensTool - {self.system.title} [{fname}]")

    def _update_status(self):
        try:
            summary = system_summary(self.system)
            self.status_efl.setText(f"EFL: {summary['efl']:.2f} mm")
            self.status_fno.setText(f"F/#: {summary['fno']:.2f}")
            self.status_track.setText(f"Track: {summary['total_track']:.1f} mm")
            self.status_surfs.setText(f"Surfaces: {summary['num_surfaces']}")
        except Exception:
            pass

    def _on_system_changed(self):
        self.layout_viewer.refresh()
        self._update_status()
        self._update_title()
        self.opt_widget.update_from_editor()

    def _on_editor_surface_selected(self, index: int):
        """Editor row selected -> highlight in layout."""
        self.layout_viewer.set_highlighted_surface(index)

    def _on_layout_surface_clicked(self, index: int):
        """Layout surface clicked -> select in editor."""
        self.editor.select_surface(index)

    def _refresh_all(self):
        """Refresh all views and analysis."""
        self.editor.refresh()
        self.layout_viewer.refresh()
        self._update_status()
        self._update_title()

        # Refresh active analysis tab
        idx = self.analysis_tabs.currentIndex()
        self._refresh_analysis_tab(idx)

    def _refresh_analysis_tab(self, idx):
        widgets = [self.spot_widget, self.mtf_widget, self.rayfan_widget,
                   self.fc_widget, self.info_widget, self.opt_widget]
        if 0 <= idx < len(widgets):
            widget = widgets[idx]
            if hasattr(widget, 'update_plot'):
                widget.update_plot()
            elif hasattr(widget, 'update_info'):
                widget.update_info()

    def _show_analysis_tab(self, idx):
        self.analysis_tabs.setCurrentIndex(idx)
        self._refresh_analysis_tab(idx)

    def _set_system(self, system: LensSystem):
        """Replace current system with a new one and refresh all."""
        self.system = system
        self.editor.set_system(system)
        self.layout_viewer.set_system(system)
        self.spot_widget.set_system(system)
        self.mtf_widget.set_system(system)
        self.rayfan_widget.set_system(system)
        self.fc_widget.set_system(system)
        self.info_widget.set_system(system)
        self.opt_widget.set_system(system)
        self._refresh_all()

    # === File Operations ===

    def _new_system(self):
        self.current_file = None
        self._set_system(LensSystem())

    def _open_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open Lens File", "",
            "Lens Files (*.lens *.json);;All Files (*)")
        if filepath:
            try:
                system = load_lens(filepath)
                self.current_file = filepath
                self._set_system(system)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open file:\n{e}")

    def _save_file(self):
        if self.current_file:
            try:
                save_lens(self.system, self.current_file)
                self.statusbar.showMessage("Saved.", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")
        else:
            self._save_file_as()

    def _save_file_as(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Lens File", f"{self.system.title}.lens",
            "Lens Files (*.lens);;JSON Files (*.json);;All Files (*)")
        if filepath:
            try:
                save_lens(self.system, filepath)
                self.current_file = filepath
                self._update_title()
                self.statusbar.showMessage("Saved.", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")

    def _load_sample(self, factory_func):
        self.current_file = None
        self._set_system(factory_func())

    # === Dialogs ===

    def _show_system_settings(self):
        dlg = SystemSettingsDialog(self.system, self)
        if dlg.exec():
            self._refresh_all()

    def _show_glass_catalog(self):
        dlg = GlassCatalogDialog(self, select_mode=False)
        dlg.exec()
        self.editor.refresh()

    def _show_optimization(self):
        """Switch to the Optimize tab in the analysis panel."""
        # Find the optimize tab index
        for i in range(self.analysis_tabs.count()):
            if self.analysis_tabs.tabText(i) == "Optimize":
                self.analysis_tabs.setCurrentIndex(i)
                break
        self.opt_widget.update_from_editor()

    def _on_optimization_complete(self):
        """Called after an optimization run finishes."""
        self.editor.refresh()
        self.layout_viewer.refresh()
        self._update_status()
        self._update_title()

    def _show_about(self):
        QMessageBox.about(self, "About LensTool",
                          "<h2 style='color: #89b4fa;'>LensTool v1.0</h2>"
                          "<p>Optical Lens Design Program</p>"
                          "<p style='color: #a6adc8;'>Features:</p>"
                          "<ul>"
                          "<li>Sequential ray tracing</li>"
                          "<li>Spot diagrams, MTF, ray fans</li>"
                          "<li>Field curvature & distortion</li>"
                          "<li>Seidel aberration analysis</li>"
                          "<li>DLS optimization</li>"
                          "<li>Glass catalog (Sellmeier)</li>"
                          "<li>Sample lens library</li>"
                          "</ul>")
