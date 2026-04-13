"""Analysis plot windows: Spot Diagram, MTF, Ray Fans, Field Curvature, Distortion."""

import numpy as np
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QComboBox, QPushButton, QTabWidget, QGridLayout,
                              QSizePolicy)
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QPainterPath, QFont

from ..engine.surface import LensSystem
from ..engine.analysis import (spot_diagram, spot_diagram_multi_wave,
                                ray_fan, ray_fan_multi_wave,
                                geometric_mtf, diffraction_limit_mtf,
                                field_curvature, distortion, seidel_aberrations,
                                rms_spot_size, system_summary)
from .theme import PLOT_COLORS, wavelength_to_color


class PlotWidget(QWidget):
    """Base widget for drawing analysis plots."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(350, 280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._title = ""
        self._x_label = ""
        self._y_label = ""
        self._x_range = (0.0, 1.0)
        self._y_range = (-1.0, 1.0)
        self._datasets = []  # list of (x_array, y_array, color, label, line_style)
        self._scatter_datasets = []  # (x_arr, y_arr, color, size)
        self._show_grid = True
        self._auto_range = True
        self._square_aspect = False  # force equal x/y scaling

    def set_title(self, title: str):
        self._title = title
        self.update()

    def set_axes(self, x_label: str, y_label: str):
        self._x_label = x_label
        self._y_label = y_label

    def set_range(self, x_range, y_range):
        self._x_range = x_range
        self._y_range = y_range
        self._auto_range = False

    def add_line(self, x, y, color="#89b4fa", label="", dashed=False):
        self._datasets.append((np.array(x), np.array(y), color, label, dashed))
        if self._auto_range:
            self._compute_auto_range()
        self.update()

    def add_scatter(self, x, y, color="#89b4fa", size=3):
        self._scatter_datasets.append((np.array(x), np.array(y), color, size))
        if self._auto_range:
            self._compute_auto_range()
        self.update()

    def clear(self):
        self._datasets.clear()
        self._scatter_datasets.clear()
        self._auto_range = True
        self.update()

    def _compute_auto_range(self):
        all_x = []
        all_y = []
        for x, y, *_ in self._datasets:
            mask = np.isfinite(x) & np.isfinite(y)
            all_x.extend(x[mask])
            all_y.extend(y[mask])
        for x, y, *_ in self._scatter_datasets:
            mask = np.isfinite(x) & np.isfinite(y)
            all_x.extend(x[mask])
            all_y.extend(y[mask])

        if all_x:
            xmin, xmax = min(all_x), max(all_x)
            dx = xmax - xmin
            if dx < 1e-12:
                dx = 1.0
            self._x_range = (xmin - dx * 0.05, xmax + dx * 0.05)
        if all_y:
            ymin, ymax = min(all_y), max(all_y)
            dy = ymax - ymin
            if dy < 1e-12:
                dy = 1.0
            self._y_range = (ymin - dy * 0.1, ymax + dy * 0.1)

        # For square aspect, equalize the data ranges so 1 unit = 1 unit
        if self._square_aspect and all_x and all_y:
            x_span = self._x_range[1] - self._x_range[0]
            y_span = self._y_range[1] - self._y_range[0]
            max_span = max(x_span, y_span)
            x_mid = (self._x_range[0] + self._x_range[1]) / 2
            y_mid = (self._y_range[0] + self._y_range[1]) / 2
            self._x_range = (x_mid - max_span / 2, x_mid + max_span / 2)
            self._y_range = (y_mid - max_span / 2, y_mid + max_span / 2)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg = QColor(PLOT_COLORS["background"])
        painter.fillRect(self.rect(), bg)

        # Margins
        ml, mr, mt, mb = 60, 20, 35, 40
        w = self.width() - ml - mr
        h = self.height() - mt - mb

        if w < 10 or h < 10:
            painter.end()
            return

        # Force square plot area if requested
        if self._square_aspect:
            side = min(w, h)
            ml = ml + (w - side) // 2
            mt = mt + (h - side) // 2
            w = side
            h = side

        # Plot area background
        plot_rect = QRectF(ml, mt, w, h)
        painter.fillRect(plot_rect, QColor("#181825"))

        # Grid
        if self._show_grid:
            self._draw_grid(painter, ml, mt, w, h)

        # Axes
        self._draw_axes(painter, ml, mt, w, h)

        # Data
        for x, y, color, label, dashed in self._datasets:
            self._draw_line(painter, x, y, color, dashed, ml, mt, w, h)

        for x, y, color, size in self._scatter_datasets:
            self._draw_scatter(painter, x, y, color, size, ml, mt, w, h)

        # Title
        if self._title:
            painter.setPen(QColor(PLOT_COLORS["foreground"]))
            font = QFont("Segoe UI", 11, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(QRectF(ml, 2, w, 30), Qt.AlignmentFlag.AlignCenter, self._title)

        # Axis labels
        font = QFont("Segoe UI", 9)
        painter.setFont(font)
        painter.setPen(QColor(PLOT_COLORS["axis"]))
        if self._x_label:
            painter.drawText(QRectF(ml, mt + h + 18, w, 20),
                           Qt.AlignmentFlag.AlignCenter, self._x_label)
        if self._y_label:
            painter.save()
            painter.translate(14, mt + h / 2)
            painter.rotate(-90)
            painter.drawText(QRectF(-50, 0, 100, 20),
                           Qt.AlignmentFlag.AlignCenter, self._y_label)
            painter.restore()

        # Legend
        if any(label for _, _, _, label, _ in self._datasets):
            self._draw_legend(painter, ml + 10, mt + 10)

        painter.end()

    def _draw_grid(self, painter, ml, mt, w, h):
        pen = QPen(QColor(PLOT_COLORS["grid"]), 0.5, Qt.PenStyle.DotLine)
        painter.setPen(pen)

        n_grid = 5
        for i in range(1, n_grid):
            x = ml + w * i / n_grid
            painter.drawLine(int(x), mt, int(x), mt + h)
            y = mt + h * i / n_grid
            painter.drawLine(ml, int(y), ml + w, int(y))

    def _draw_axes(self, painter, ml, mt, w, h):
        pen = QPen(QColor(PLOT_COLORS["axis"]), 1)
        painter.setPen(pen)
        font = QFont("Segoe UI", 8)
        painter.setFont(font)

        # X tick labels
        xmin, xmax = self._x_range
        n_ticks = 5
        for i in range(n_ticks + 1):
            val = xmin + (xmax - xmin) * i / n_ticks
            x = ml + w * i / n_ticks
            painter.drawLine(int(x), mt + h, int(x), mt + h + 4)
            text = f"{val:.3g}"
            painter.drawText(QRectF(x - 25, mt + h + 5, 50, 15),
                           Qt.AlignmentFlag.AlignCenter, text)

        # Y tick labels
        ymin, ymax = self._y_range
        for i in range(n_ticks + 1):
            val = ymin + (ymax - ymin) * i / n_ticks
            y = mt + h - h * i / n_ticks
            painter.drawLine(ml - 4, int(y), ml, int(y))
            text = f"{val:.3g}"
            painter.drawText(QRectF(ml - 55, y - 8, 50, 16),
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, text)

        # Border
        painter.drawRect(QRectF(ml, mt, w, h))

    def _to_screen(self, x_val, y_val, ml, mt, w, h):
        xmin, xmax = self._x_range
        ymin, ymax = self._y_range
        sx = ml + (x_val - xmin) / (xmax - xmin) * w if xmax != xmin else ml + w / 2
        sy = mt + h - (y_val - ymin) / (ymax - ymin) * h if ymax != ymin else mt + h / 2
        return sx, sy

    def _draw_line(self, painter, x, y, color, dashed, ml, mt, w, h):
        pen = QPen(QColor(color), 1.5)
        if dashed:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)

        path = QPainterPath()
        first = True
        for xi, yi in zip(x, y):
            if not np.isfinite(xi) or not np.isfinite(yi):
                first = True
                continue
            sx, sy = self._to_screen(xi, yi, ml, mt, w, h)
            if first:
                path.moveTo(sx, sy)
                first = False
            else:
                path.lineTo(sx, sy)
        painter.drawPath(path)

    def _draw_scatter(self, painter, x, y, color, size, ml, mt, w, h):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(color)))

        for xi, yi in zip(x, y):
            if not np.isfinite(xi) or not np.isfinite(yi):
                continue
            sx, sy = self._to_screen(xi, yi, ml, mt, w, h)
            if ml <= sx <= ml + w and mt <= sy <= mt + h:
                painter.drawEllipse(QRectF(sx - size / 2, sy - size / 2, size, size))

    def _draw_legend(self, painter, x, y):
        font = QFont("Segoe UI", 8)
        painter.setFont(font)
        dy = 0
        for _, _, color, label, dashed in self._datasets:
            if not label:
                continue
            pen = QPen(QColor(color), 2)
            if dashed:
                pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(int(x), int(y + dy + 6), int(x + 20), int(y + dy + 6))
            painter.setPen(QColor(PLOT_COLORS["foreground"]))
            painter.drawText(int(x + 25), int(y + dy + 10), label)
            dy += 16


class SpotDiagramWidget(QWidget):
    """Spot diagram analysis window."""

    def __init__(self, system: LensSystem, parent=None):
        super().__init__(parent)
        self.system = system
        self._setup_ui()
        self.update_plot()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Controls
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Field:"))
        self.field_combo = QComboBox()
        self.field_combo.currentIndexChanged.connect(self.update_plot)
        ctrl.addWidget(self.field_combo)
        ctrl.addStretch()

        btn = QPushButton("Refresh")
        btn.clicked.connect(self.update_plot)
        ctrl.addWidget(btn)
        layout.addLayout(ctrl)

        # Plots - one per field
        self.plot_area = QGridLayout()
        layout.addLayout(self.plot_area)

        self._plots = []
        self._refresh_fields()

    def _refresh_fields(self):
        self.field_combo.clear()
        self.field_combo.addItem("All Fields")
        for f in self.system.fields:
            self.field_combo.addItem(f"{f:.1f}\u00b0")

    def set_system(self, system: LensSystem):
        self.system = system
        self._refresh_fields()
        self.update_plot()

    def update_plot(self):
        # Clear old plots
        for p in self._plots:
            p.setParent(None)
        self._plots.clear()

        fields = self.system.fields
        idx = self.field_combo.currentIndex()
        if idx > 0 and idx - 1 < len(fields):
            fields = [fields[idx - 1]]

        n_cols = min(len(fields), 3)
        for i, field_angle in enumerate(fields):
            plot = PlotWidget()
            plot._square_aspect = True
            plot.set_title(f"Spot Diagram  {field_angle:.1f}\u00b0")
            plot.set_axes("X (\u03bcm)", "Y (\u03bcm)")

            for wl in self.system.wavelengths:
                x, y = spot_diagram(self.system, field_angle, wl)
                color = wavelength_to_color(wl)
                # Convert mm to microns
                plot.add_scatter(x * 1000, y * 1000, color, 3)

            # Airy disk circle using actual EFL
            from ..engine.raytrace import compute_efl
            efl = compute_efl(self.system)
            if abs(efl) < 1e-6:
                efl = 100.0
            fno = abs(efl / self.system.entrance_pupil_diameter) if self.system.entrance_pupil_diameter > 0 else 5.0
            airy_radius = 1.22 * self.system.primary_wavelength() * fno  # in microns
            theta = np.linspace(0, 2 * np.pi, 60)
            plot.add_line(airy_radius * np.cos(theta), airy_radius * np.sin(theta),
                         PLOT_COLORS["airy_disk"], "Airy disk", True)

            rms = rms_spot_size(self.system, field_angle) * 1000
            plot.set_title(f"Spot  {field_angle:.1f}\u00b0  RMS={rms:.1f}\u03bcm")

            row, col = divmod(i, n_cols)
            self.plot_area.addWidget(plot, row, col)
            self._plots.append(plot)


class MTFWidget(QWidget):
    """MTF analysis window."""

    def __init__(self, system: LensSystem, parent=None):
        super().__init__(parent)
        self.system = system
        self._setup_ui()
        self.update_plot()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Max Freq (cy/mm):"))
        self.freq_combo = QComboBox()
        self.freq_combo.setEditable(True)
        self.freq_combo.addItems(["50", "100", "200", "400", "600"])
        self.freq_combo.setCurrentIndex(2)
        self.freq_combo.setFixedWidth(80)
        self.freq_combo.currentIndexChanged.connect(self.update_plot)
        self.freq_combo.lineEdit().returnPressed.connect(self.update_plot)
        ctrl.addWidget(self.freq_combo)
        ctrl.addStretch()

        btn = QPushButton("Refresh")
        btn.clicked.connect(self.update_plot)
        ctrl.addWidget(btn)
        layout.addLayout(ctrl)

        self.plot = PlotWidget()
        layout.addWidget(self.plot)

    def set_system(self, system: LensSystem):
        self.system = system
        self.update_plot()

    def update_plot(self):
        self.plot.clear()
        max_freq = float(self.freq_combo.currentText())

        self.plot.set_title("Geometric MTF")
        self.plot.set_axes("Spatial Frequency (cy/mm)", "Modulation")
        self.plot.set_range((0, max_freq), (0, 1.05))

        # Diffraction limit
        freq, dl_mtf = diffraction_limit_mtf(self.system, max_frequency=max_freq)
        self.plot.add_line(freq, dl_mtf, PLOT_COLORS["mtf_diffraction"], "Diffraction Limit", True)

        # MTF per field
        colors = PLOT_COLORS["ray_colors"]
        for i, field_angle in enumerate(self.system.fields):
            freq, t_mtf, s_mtf = geometric_mtf(self.system, field_angle,
                                                 max_frequency=max_freq)
            c = colors[i % len(colors)]
            self.plot.add_line(freq, t_mtf, c, f"T {field_angle:.1f}\u00b0")
            # Sagittal in same color but dashed
            self.plot.add_line(freq, s_mtf, c, f"S {field_angle:.1f}\u00b0", True)

        self.plot.update()


class RayFanWidget(QWidget):
    """Ray aberration fan plot."""

    def __init__(self, system: LensSystem, parent=None):
        super().__init__(parent)
        self.system = system
        self._setup_ui()
        self.update_plot()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        ctrl = QHBoxLayout()
        ctrl.addStretch()
        btn = QPushButton("Refresh")
        btn.clicked.connect(self.update_plot)
        ctrl.addWidget(btn)
        layout.addLayout(ctrl)

        self.plot_area = QGridLayout()
        layout.addLayout(self.plot_area)
        self._plots = []

    def set_system(self, system: LensSystem):
        self.system = system
        self.update_plot()

    def update_plot(self):
        for p in self._plots:
            p.setParent(None)
        self._plots.clear()

        fields = self.system.fields
        n_cols = min(len(fields), 3)

        for i, field_angle in enumerate(fields):
            plot = PlotWidget()
            plot.set_title(f"Ray Fan  {field_angle:.1f}\u00b0")
            plot.set_axes("Pupil (Py)", "\u0394y (mm)")

            for wl in self.system.wavelengths:
                py, ey = ray_fan(self.system, field_angle, wl)
                color = wavelength_to_color(wl)
                plot.add_line(py, ey, color, f"{wl:.4f}\u03bcm")

            row, col = divmod(i, n_cols)
            self.plot_area.addWidget(plot, row, col)
            self._plots.append(plot)


class FieldCurvatureWidget(QWidget):
    """Field curvature and distortion plots."""

    def __init__(self, system: LensSystem, parent=None):
        super().__init__(parent)
        self.system = system
        self._setup_ui()
        self.update_plot()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        ctrl = QHBoxLayout()
        ctrl.addStretch()
        btn = QPushButton("Refresh")
        btn.clicked.connect(self.update_plot)
        ctrl.addWidget(btn)
        layout.addLayout(ctrl)

        h_layout = QHBoxLayout()
        self.fc_plot = PlotWidget()
        self.dist_plot = PlotWidget()
        h_layout.addWidget(self.fc_plot)
        h_layout.addWidget(self.dist_plot)
        layout.addLayout(h_layout)

    def set_system(self, system: LensSystem):
        self.system = system
        self.update_plot()

    def update_plot(self):
        self.fc_plot.clear()
        self.dist_plot.clear()

        # Field curvature
        fa, t_focus, s_focus = field_curvature(self.system)
        self.fc_plot.set_title("Field Curvature")
        self.fc_plot.set_axes("Focus Shift (mm)", "Field Angle (\u00b0)")
        self.fc_plot.add_line(t_focus, fa, PLOT_COLORS["mtf_tangential"], "Tangential")
        self.fc_plot.add_line(s_focus, fa, PLOT_COLORS["mtf_sagittal"], "Sagittal")

        # Distortion
        fa2, dist_pct = distortion(self.system)
        self.dist_plot.set_title("Distortion")
        self.dist_plot.set_axes("Distortion (%)", "Field Angle (\u00b0)")
        self.dist_plot.add_line(dist_pct, fa2, PLOT_COLORS["accent"])


class SystemInfoWidget(QWidget):
    """System summary and Seidel aberrations display."""

    def __init__(self, system: LensSystem, parent=None):
        super().__init__(parent)
        self.system = system
        self._setup_ui()
        self.update_info()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setTextFormat(Qt.TextFormat.RichText)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.info_label)

        btn = QPushButton("Refresh")
        btn.clicked.connect(self.update_info)
        layout.addWidget(btn)
        layout.addStretch()

    def set_system(self, system: LensSystem):
        self.system = system
        self.update_info()

    def update_info(self):
        summary = system_summary(self.system)
        seidel = seidel_aberrations(self.system)

        html = f"""
        <div style="color: #cdd6f4; font-family: Consolas, monospace;">
        <h3 style="color: #89b4fa;">{summary['title']}</h3>
        <table style="font-size: 13px;">
        <tr><td style="color: #a6adc8; padding-right:12px;">EFL:</td>
            <td><b>{summary['efl']:.4f} mm</b></td></tr>
        <tr><td style="color: #a6adc8;">F/#:</td>
            <td><b>{summary['fno']:.2f}</b></td></tr>
        <tr><td style="color: #a6adc8;">NA:</td>
            <td><b>{summary['na']:.4f}</b></td></tr>
        <tr><td style="color: #a6adc8;">EPD:</td>
            <td><b>{summary['epd']:.2f} mm</b></td></tr>
        <tr><td style="color: #a6adc8;">Total Track:</td>
            <td><b>{summary['total_track']:.2f} mm</b></td></tr>
        <tr><td style="color: #a6adc8;">Surfaces:</td>
            <td><b>{summary['num_surfaces']}</b></td></tr>
        </table>

        <h3 style="color: #cba6f7; margin-top:16px;">Seidel Aberrations</h3>
        <table style="font-size: 13px;">
        <tr><td style="color: #a6adc8; padding-right:12px;">S1 (Spherical):</td>
            <td><b>{seidel['S1_spherical']:.6f}</b></td></tr>
        <tr><td style="color: #a6adc8;">S2 (Coma):</td>
            <td><b>{seidel['S2_coma']:.6f}</b></td></tr>
        <tr><td style="color: #a6adc8;">S3 (Astigmatism):</td>
            <td><b>{seidel['S3_astigmatism']:.6f}</b></td></tr>
        <tr><td style="color: #a6adc8;">S4 (Petzval):</td>
            <td><b>{seidel['S4_petzval']:.6f}</b></td></tr>
        <tr><td style="color: #a6adc8;">S5 (Distortion):</td>
            <td><b>{seidel['S5_distortion']:.6f}</b></td></tr>
        </table>

        <h3 style="color: #a6e3a1; margin-top:16px;">RMS Spot Sizes</h3>
        <table style="font-size: 13px;">
        """

        for field_angle in self.system.fields:
            rms = rms_spot_size(self.system, field_angle) * 1000  # to microns
            html += f"""<tr><td style="color: #a6adc8; padding-right:12px;">{field_angle:.1f}\u00b0:</td>
                       <td><b>{rms:.2f} \u03bcm</b></td></tr>"""

        html += "</table></div>"
        self.info_label.setText(html)
