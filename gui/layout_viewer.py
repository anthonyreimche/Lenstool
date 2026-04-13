"""2D Lens Layout Viewer with ray tracing visualization."""

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QCheckBox
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor, QPainterPath,
                          QLinearGradient, QFont, QWheelEvent, QMouseEvent)

from ..engine.surface import LensSystem
from ..engine.raytrace import trace_real_ray_2d
from ..engine.materials import get_glass
from .theme import PLOT_COLORS, wavelength_to_color


class LayoutCanvas(QWidget):
    """Custom widget for drawing the lens layout."""

    surface_clicked = pyqtSignal(int)  # emits surface index when clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.system = None
        self.show_rays = True
        self.show_all_fields = True
        self.show_all_wavelengths = False
        self.num_rays = 7
        self.setMinimumSize(400, 200)

        # View transforms
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._last_mouse_pos = None
        self._drag_button = None

        # Selection highlighting
        self._highlighted_surface = -1
        self._surface_screen_rects = []  # (surf_index, z_center, z_left, z_right, y_top, y_bot)

        self.setMouseTracking(True)

    def set_system(self, system: LensSystem):
        self.system = system
        self._auto_fit()
        self.update()

    def _auto_fit(self):
        if not self.system:
            return
        total = self.system.total_track()
        if total < 1e-6:
            total = 100.0
        max_sd = max(s.semi_diameter for s in self.system.surfaces if s.semi_diameter > 0)
        if max_sd < 1e-6:
            max_sd = 20.0

        w = self.width() or 800
        h = self.height() or 400
        scale_x = w / (total * 1.4)
        scale_y = h / (max_sd * 3.0)
        self._zoom = min(scale_x, scale_y)
        self._pan_x = total * 0.1 * self._zoom
        self._pan_y = 0.0

    def paintEvent(self, event):
        if not self.system:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        bg = QColor(PLOT_COLORS["background"])
        painter.fillRect(self.rect(), bg)

        # Setup coordinate system: center vertically, z goes right, y goes up
        cx = 40 + self._pan_x
        cy = self.height() / 2 + self._pan_y

        # Draw optical axis
        axis_pen = QPen(QColor(PLOT_COLORS["grid"]), 1, Qt.PenStyle.DashLine)
        painter.setPen(axis_pen)
        painter.drawLine(0, int(cy), self.width(), int(cy))

        # Draw surfaces and lenses
        self._draw_surfaces(painter, cx, cy)

        # Draw rays
        if self.show_rays:
            self._draw_rays(painter, cx, cy)

        painter.end()

    def _draw_surfaces(self, painter: QPainter, cx: float, cy: float):
        z_pos = 0.0
        surfaces = self.system.surfaces
        self._surface_screen_rects = []

        for i, surf in enumerate(surfaces):
            if i == 0:  # Skip OBJ
                t = surf.thickness
                if abs(t) < 1e10:
                    z_pos += t
                continue

            sd = surf.semi_diameter
            if sd <= 0:
                sd = 10.0

            c = surf.curvature
            screen_z = cx + z_pos * self._zoom
            screen_sd = sd * self._zoom

            # Record screen position for hit-testing
            self._surface_screen_rects.append((i, screen_z, screen_sd, cy))

            # Check if this is part of a lens element (glass before or after)
            is_glass_after = bool(surf.material and surf.material.upper() not in ("", "AIR", "MIRROR"))
            is_glass_before = False
            if i > 0:
                prev_mat = surfaces[i - 1].material if i - 1 >= 0 else ""
                is_glass_before = bool(prev_mat and prev_mat.upper() not in ("", "AIR", "MIRROR"))

            # Draw highlight if this surface is selected
            is_highlighted = (i == self._highlighted_surface)
            # Also highlight if the selected surface is the front face of this element
            is_element_highlighted = False
            if is_glass_after and i < len(surfaces) - 1:
                if self._highlighted_surface == i or self._highlighted_surface == i + 1:
                    is_element_highlighted = True

            # Draw lens body if transitioning into glass
            if is_glass_after and i < len(surfaces) - 1:
                self._draw_lens_element(painter, cx, cy, z_pos, surf, surfaces, i,
                                         highlighted=is_element_highlighted)

            # Draw the surface curve
            if i == len(surfaces) - 1:
                # Image plane
                color = QColor("#fab387") if is_highlighted else QColor("#f9e2af")
                pen = QPen(color, 3 if is_highlighted else 2)
                painter.setPen(pen)
                painter.drawLine(int(screen_z), int(cy - screen_sd),
                               int(screen_z), int(cy + screen_sd))
            elif surf.is_stop:
                # Aperture stop
                color = QColor("#fab387") if is_highlighted else QColor("#f9e2af")
                pen = QPen(color, 3 if is_highlighted else 2)
                painter.setPen(pen)
                # Draw stop bars
                painter.drawLine(int(screen_z), int(cy - screen_sd - 5),
                               int(screen_z), int(cy - screen_sd * 0.0))
                painter.drawLine(int(screen_z), int(cy + screen_sd * 0.0),
                               int(screen_z), int(cy + screen_sd + 5))
            else:
                # Regular surface
                if is_highlighted:
                    self._draw_surface_curve(painter, cx, cy, z_pos, surf,
                                             QColor("#fab387"), width=3)
                else:
                    self._draw_surface_curve(painter, cx, cy, z_pos, surf,
                                             QColor(PLOT_COLORS["surface_edge"]))

            # Advance z
            t = surf.thickness
            if abs(t) < 1e10:
                z_pos += t

    def _draw_surface_curve(self, painter, cx, cy, z_pos, surf, color, width=2):
        """Draw a curved surface."""
        sd = surf.semi_diameter
        if sd <= 0:
            sd = 10.0

        pen = QPen(color, width)
        painter.setPen(pen)

        n_pts = 40
        path = QPainterPath()
        for j in range(n_pts + 1):
            y = -sd + 2.0 * sd * j / n_pts
            sag = surf.sag(y)
            screen_z = cx + (z_pos + sag) * self._zoom
            screen_y = cy - y * self._zoom
            if j == 0:
                path.moveTo(screen_z, screen_y)
            else:
                path.lineTo(screen_z, screen_y)

        painter.drawPath(path)

    def _draw_lens_element(self, painter, cx, cy, z_start, surf, surfaces, idx,
                           highlighted=False):
        """Draw a filled lens element between two surfaces."""
        sd = surf.semi_diameter
        if sd <= 0:
            sd = 10.0

        # Find the end surface of this element
        t = surf.thickness
        if abs(t) > 1e10:
            return

        end_idx = idx + 1
        if end_idx >= len(surfaces):
            return
        end_surf = surfaces[end_idx]

        z_end = z_start + t
        n_pts = 30

        # Build polygon path
        path = QPainterPath()

        # Front surface (top to bottom)
        for j in range(n_pts + 1):
            y = -sd + 2.0 * sd * j / n_pts
            sag = surf.sag(y)
            sz = cx + (z_start + sag) * self._zoom
            sy = cy - y * self._zoom
            if j == 0:
                path.moveTo(sz, sy)
            else:
                path.lineTo(sz, sy)

        # Back surface (bottom to top)
        end_sd = min(end_surf.semi_diameter, sd) if end_surf.semi_diameter > 0 else sd
        for j in range(n_pts, -1, -1):
            y = -end_sd + 2.0 * end_sd * j / n_pts
            sag = end_surf.sag(y)
            sz = cx + (z_end + sag) * self._zoom
            sy = cy - y * self._zoom
            path.lineTo(sz, sy)

        path.closeSubpath()

        # Fill with semi-transparent glass color
        if highlighted:
            fill_color = QColor(250, 179, 135, 70)  # orange tint when highlighted
        else:
            glass = get_glass(surf.material)
            if glass and glass.nd > 1.0:
                alpha = int(40 + (glass.nd - 1.0) * 120)
                alpha = min(alpha, 120)
                fill_color = QColor(137, 180, 250, alpha)  # blue tint
            else:
                fill_color = QColor(137, 180, 250, 40)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(fill_color))
        painter.drawPath(path)

        # Draw edges
        edge_color = QColor("#fab387") if highlighted else QColor(PLOT_COLORS["surface_edge"])
        edge_pen = QPen(edge_color, 2.5 if highlighted else 1.5)
        painter.setPen(edge_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def _draw_rays(self, painter, cx, cy):
        """Draw traced rays through the system."""
        if not self.system:
            return

        fields = self.system.fields if self.show_all_fields else [self.system.fields[0]]
        wavelengths = self.system.wavelengths if self.show_all_wavelengths else [self.system.primary_wavelength()]
        epd = self.system.entrance_pupil_diameter

        ray_positions = np.linspace(-1.0, 1.0, self.num_rays)

        for fi, field_angle in enumerate(fields):
            for wi, wavelength in enumerate(wavelengths):
                color = QColor(wavelength_to_color(wavelength))
                color.setAlpha(140)
                pen = QPen(color, 1.0)
                painter.setPen(pen)

                u_field = np.tan(np.radians(field_angle))

                for py in ray_positions:
                    y_start = py * epd / 2.0
                    result = trace_real_ray_2d(self.system, y_start, u_field, wavelength)

                    if result.vignetted and len(result.y_values) < 2:
                        continue

                    # Draw ray segments (skip OBJ at index 0, but add approach ray)
                    prev_screen = None

                    for j in range(1, len(result.y_values)):
                        sy = cy - result.y_values[j] * self._zoom
                        sz = cx + result.z_values[j] * self._zoom

                        if j == 1 and len(result.y_values) > 2:
                            # Draw incoming ray from the left edge
                            approach_z = result.z_values[j] - 15.0
                            approach_y = result.y_values[j] - u_field * 15.0
                            ay = cy - approach_y * self._zoom
                            az = cx + approach_z * self._zoom
                            painter.drawLine(int(az), int(ay), int(sz), int(sy))

                        if prev_screen is not None:
                            painter.drawLine(int(prev_screen[0]), int(prev_screen[1]),
                                           int(sz), int(sy))
                        prev_screen = (sz, sy)

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1.0 / 1.15
        self._zoom *= factor
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        self._last_mouse_pos = event.pos()
        self._drag_button = event.button()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._last_mouse_pos and self._drag_button == Qt.MouseButton.MiddleButton:
            dx = event.pos().x() - self._last_mouse_pos.x()
            dy = event.pos().y() - self._last_mouse_pos.y()
            self._pan_x += dx
            self._pan_y += dy
            self._last_mouse_pos = event.pos()
            self.update()
        elif self._last_mouse_pos and self._drag_button == Qt.MouseButton.RightButton:
            dy = event.pos().y() - self._last_mouse_pos.y()
            factor = 1.0 + dy * 0.005
            self._zoom *= factor
            self._last_mouse_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._drag_button == Qt.MouseButton.LeftButton and self._last_mouse_pos:
            # Check if it was a click (not a drag)
            dx = abs(event.pos().x() - self._last_mouse_pos.x())
            dy = abs(event.pos().y() - self._last_mouse_pos.y())
            if dx < 5 and dy < 5:
                self._handle_click(event.pos().x(), event.pos().y())
        self._last_mouse_pos = None
        self._drag_button = None

    def set_highlighted_surface(self, index: int):
        """Set the highlighted surface index (-1 to clear)."""
        if self._highlighted_surface != index:
            self._highlighted_surface = index
            self.update()

    def _handle_click(self, mx, my):
        """Find the nearest surface to the click position."""
        best_idx = -1
        best_dist = 25.0  # max pixel distance to register a click

        for (surf_idx, screen_z, screen_sd, cy) in self._surface_screen_rects:
            # Check if click is within vertical range of the surface
            if abs(my - cy) > screen_sd + 10:
                continue
            dist = abs(mx - screen_z)
            if dist < best_dist:
                best_dist = dist
                best_idx = surf_idx

        self._highlighted_surface = best_idx
        self.update()
        if best_idx >= 0:
            self.surface_clicked.emit(best_idx)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self._auto_fit()
        self.update()


class LayoutViewer(QWidget):
    """Lens layout viewer with controls."""

    surface_clicked = pyqtSignal(int)  # forwarded from canvas

    def __init__(self, system: LensSystem, parent=None):
        super().__init__(parent)
        self.system = system
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Controls bar
        controls = QHBoxLayout()
        title = QLabel("2D Layout")
        title.setObjectName("headerLabel")
        controls.addWidget(title)
        controls.addStretch()

        self.chk_rays = QCheckBox("Rays")
        self.chk_rays.setChecked(True)
        self.chk_rays.stateChanged.connect(self._update_options)
        controls.addWidget(self.chk_rays)

        self.chk_fields = QCheckBox("All Fields")
        self.chk_fields.setChecked(True)
        self.chk_fields.stateChanged.connect(self._update_options)
        controls.addWidget(self.chk_fields)

        self.chk_wavelengths = QCheckBox("Multi-\u03bb")
        self.chk_wavelengths.setChecked(False)
        self.chk_wavelengths.stateChanged.connect(self._update_options)
        controls.addWidget(self.chk_wavelengths)

        btn_fit = QPushButton("Fit")
        btn_fit.setFixedWidth(50)
        btn_fit.clicked.connect(self._fit_view)
        controls.addWidget(btn_fit)

        layout.addLayout(controls)

        # Canvas
        self.canvas = LayoutCanvas()
        self.canvas.set_system(self.system)
        self.canvas.surface_clicked.connect(self.surface_clicked)
        layout.addWidget(self.canvas)

    def set_system(self, system: LensSystem):
        self.system = system
        self.canvas.set_system(system)

    def refresh(self):
        """Repaint with current system data (no auto-fit)."""
        self.canvas.update()

    def set_highlighted_surface(self, index: int):
        self.canvas.set_highlighted_surface(index)

    def _update_options(self):
        self.canvas.show_rays = self.chk_rays.isChecked()
        self.canvas.show_all_fields = self.chk_fields.isChecked()
        self.canvas.show_all_wavelengths = self.chk_wavelengths.isChecked()
        self.canvas.update()

    def _fit_view(self):
        self.canvas._auto_fit()
        self.canvas.update()
