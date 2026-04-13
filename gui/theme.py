"""Dark theme stylesheet for LensTool GUI."""

DARK_STYLESHEET = """
/* === Global === */
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", "Consolas", monospace;
    font-size: 13px;
}

/* === Main Window === */
QMainWindow {
    background-color: #1e1e2e;
}

QMainWindow::separator {
    background-color: #313244;
    width: 2px;
    height: 2px;
}

/* === Menu Bar === */
QMenuBar {
    background-color: #181825;
    color: #cdd6f4;
    border-bottom: 1px solid #313244;
    padding: 2px;
}

QMenuBar::item {
    padding: 4px 10px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #45475a;
}

QMenu {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 30px 6px 20px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #45475a;
}

QMenu::separator {
    height: 1px;
    background-color: #313244;
    margin: 4px 8px;
}

/* === Tool Bar === */
QToolBar {
    background-color: #181825;
    border-bottom: 1px solid #313244;
    padding: 2px;
    spacing: 2px;
}

QToolBar::separator {
    width: 1px;
    background-color: #313244;
    margin: 4px 4px;
}

QToolButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 8px;
    color: #cdd6f4;
    min-width: 60px;
}

QToolButton:hover {
    background-color: #313244;
    border: 1px solid #45475a;
}

QToolButton:pressed {
    background-color: #45475a;
}

/* === Dock Widgets === */
QDockWidget {
    titlebar-close-icon: none;
    color: #cdd6f4;
    font-weight: bold;
}

QDockWidget::title {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 4px 4px 0 0;
    padding: 6px 10px;
    text-align: left;
}

QDockWidget::close-button, QDockWidget::float-button {
    background-color: transparent;
    border: none;
    padding: 2px;
}

QDockWidget::close-button:hover, QDockWidget::float-button:hover {
    background-color: #45475a;
    border-radius: 3px;
}

/* === Tab Widget === */
QTabWidget::pane {
    border: 1px solid #313244;
    border-radius: 0 0 6px 6px;
    background-color: #1e1e2e;
}

QTabBar::tab {
    background-color: #181825;
    color: #a6adc8;
    border: 1px solid #313244;
    border-bottom: none;
    padding: 6px 16px;
    margin-right: 2px;
    border-radius: 6px 6px 0 0;
}

QTabBar::tab:selected {
    background-color: #1e1e2e;
    color: #89b4fa;
    border-bottom: 2px solid #89b4fa;
}

QTabBar::tab:hover:!selected {
    background-color: #313244;
    color: #cdd6f4;
}

/* === Table Widget === */
QTableWidget, QTableView {
    background-color: #11111b;
    alternate-background-color: #181825;
    gridline-color: #313244;
    border: 1px solid #313244;
    border-radius: 4px;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
}

QTableWidget::item, QTableView::item {
    padding: 4px 8px;
    border: none;
}

QTableWidget::item:selected, QTableView::item:selected {
    background-color: #45475a;
}

QHeaderView::section {
    background-color: #181825;
    color: #a6adc8;
    border: 1px solid #313244;
    padding: 4px 8px;
    font-weight: bold;
}

QHeaderView::section:hover {
    background-color: #313244;
}

/* === Scroll Bars === */
QScrollBar:vertical {
    background-color: #11111b;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 5px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #585b70;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #11111b;
    height: 10px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background-color: #45475a;
    border-radius: 5px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #585b70;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* === Buttons === */
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #45475a;
    border: 1px solid #585b70;
}

QPushButton:pressed {
    background-color: #585b70;
}

QPushButton:disabled {
    background-color: #1e1e2e;
    color: #585b70;
    border: 1px solid #313244;
}

QPushButton#primaryButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
}

QPushButton#primaryButton:hover {
    background-color: #74c7ec;
}

QPushButton#dangerButton {
    background-color: #f38ba8;
    color: #1e1e2e;
    border: none;
}

/* === Line Edit / Spin Box === */
QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #11111b;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 4px;
    padding: 4px 8px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #89b4fa;
}

/* === Combo Box === */
QComboBox {
    background-color: #11111b;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 4px;
    padding: 4px 8px;
}

QComboBox:hover {
    border: 1px solid #45475a;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    selection-background-color: #45475a;
}

/* === Group Box === */
QGroupBox {
    border: 1px solid #313244;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #89b4fa;
}

/* === Status Bar === */
QStatusBar {
    background-color: #181825;
    border-top: 1px solid #313244;
    color: #a6adc8;
}

QStatusBar::item {
    border: none;
}

/* === Splitter === */
QSplitter::handle {
    background-color: #313244;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

/* === Progress Bar === */
QProgressBar {
    background-color: #11111b;
    border: 1px solid #313244;
    border-radius: 4px;
    text-align: center;
    color: #cdd6f4;
}

QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 3px;
}

/* === Label Styles === */
QLabel#headerLabel {
    font-size: 16px;
    font-weight: bold;
    color: #89b4fa;
}

QLabel#subtitleLabel {
    color: #a6adc8;
    font-size: 11px;
}

/* === Tool Tips === */
QToolTip {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
}

/* === Dialog === */
QDialog {
    background-color: #1e1e2e;
}

/* === Text Edit === */
QTextEdit, QPlainTextEdit {
    background-color: #11111b;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 4px;
}
"""

# Color palette for plots
PLOT_COLORS = {
    "background": "#11111b",
    "foreground": "#cdd6f4",
    "grid": "#313244",
    "grid_minor": "#1e1e2e",
    "axis": "#a6adc8",
    "ray_colors": ["#89b4fa", "#a6e3a1", "#f38ba8", "#fab387", "#f9e2af",
                    "#cba6f7", "#94e2d5", "#eba0ac", "#89dceb", "#b4befe"],
    "wavelength_colors": {
        0.4861: "#89b4fa",   # F-line (blue)
        0.5461: "#a6e3a1",   # e-line (green)
        0.5876: "#f9e2af",   # d-line (yellow)
        0.6563: "#f38ba8",   # C-line (red)
    },
    "spot_color": "#89b4fa",
    "airy_disk": "#45475a",
    "mtf_tangential": "#89b4fa",
    "mtf_sagittal": "#f38ba8",
    "mtf_diffraction": "#45475a",
    "accent": "#89b4fa",
    "accent2": "#cba6f7",
    "surface_fill": "#313244",
    "surface_edge": "#89b4fa",
    "lens_fill": "#1e3a5f",
}


def wavelength_to_color(wavelength_um: float) -> str:
    """Map a wavelength to a display color."""
    colors = PLOT_COLORS["wavelength_colors"]
    # Find closest
    if wavelength_um in colors:
        return colors[wavelength_um]

    closest = min(colors.keys(), key=lambda w: abs(w - wavelength_um))
    return colors[closest]
