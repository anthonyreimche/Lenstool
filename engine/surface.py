"""Optical surface definitions for sequential ray tracing."""

import numpy as np
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class SurfaceType(Enum):
    STANDARD = "Standard"
    EVEN_ASPHERE = "Even Asphere"
    PARAXIAL = "Paraxial"
    COORDINATE_BREAK = "Coordinate Break"


class ApertureType(Enum):
    NONE = "None"
    CIRCULAR = "Circular Aperture"
    RECTANGULAR = "Rectangular Aperture"


class SolveType(Enum):
    FIXED = "Fixed"
    MARGINAL_RAY_HEIGHT = "Marginal Ray Height"
    CHIEF_RAY_HEIGHT = "Chief Ray Height"
    PICKUP = "Pickup"
    VARIABLE = "Variable"


@dataclass
class Surface:
    """A single optical surface in a sequential system."""

    comment: str = ""
    surface_type: SurfaceType = SurfaceType.STANDARD
    radius: float = float('inf')  # radius of curvature (inf = flat)
    thickness: float = 0.0  # distance to next surface
    material: str = ""  # glass name or empty for air
    semi_diameter: float = 10.0
    conic: float = 0.0  # conic constant (0=sphere, -1=paraboloid)
    aspheric_coeffs: list = field(default_factory=list)  # A4, A6, A8, A10, A12, A14, A16

    # Aperture
    aperture_type: ApertureType = ApertureType.NONE
    aperture_value: float = 0.0

    # Solve
    radius_solve: SolveType = SolveType.FIXED
    thickness_solve: SolveType = SolveType.FIXED
    material_solve: SolveType = SolveType.FIXED

    # Flags
    is_stop: bool = False

    @property
    def curvature(self) -> float:
        if abs(self.radius) > 1e18:
            return 0.0
        return 1.0 / self.radius

    @curvature.setter
    def curvature(self, c: float):
        if abs(c) < 1e-18:
            self.radius = float('inf')
        else:
            self.radius = 1.0 / c

    def sag(self, y: float) -> float:
        """Compute sag of surface at radial height y."""
        c = self.curvature
        k = self.conic
        r2 = y * y

        if abs(c) < 1e-18:
            z = 0.0
        else:
            denom = 1.0 - (1.0 + k) * c * c * r2
            if denom < 0:
                # Beyond surface extent
                denom = 1e-12
            z = c * r2 / (1.0 + np.sqrt(denom))

        # Add aspheric terms
        rp = r2
        for coeff in self.aspheric_coeffs:
            rp *= r2  # r^4, r^6, ...
            z += coeff * rp

        return z

    def normal_at(self, y: float, z_surface: float) -> np.ndarray:
        """Compute outward normal at height y (in y-z plane for 2D)."""
        c = self.curvature
        k = self.conic
        r2 = y * y

        # dz/dy for standard conic
        if abs(c) < 1e-18:
            dzdy = 0.0
        else:
            denom = 1.0 - (1.0 + k) * c * c * r2
            if denom < 1e-12:
                denom = 1e-12
            dzdy = c * y / np.sqrt(denom)

        # Aspheric contribution to slope
        rp = 1.0
        for i, coeff in enumerate(self.aspheric_coeffs):
            power = 2 * (i + 2)  # 4, 6, 8, ...
            rp = y ** (power - 1)
            dzdy += coeff * power * rp

        # Normal is (-dz/dy, 1) normalized (pointing back toward incoming light)
        norm = np.array([-dzdy, 1.0])
        norm /= np.linalg.norm(norm)
        return norm


@dataclass
class LensSystem:
    """A sequential optical system defined by surfaces."""

    surfaces: list = field(default_factory=list)
    wavelengths: list = field(default_factory=lambda: [0.5876])  # d-line in microns
    primary_wavelength_idx: int = 0
    fields: list = field(default_factory=lambda: [0.0])  # field angles in degrees
    field_type: str = "angle"  # "angle", "object_height", "image_height"
    entrance_pupil_diameter: float = 20.0
    title: str = "New Lens"
    notes: str = ""

    def __post_init__(self):
        if not self.surfaces:
            # Create default: OBJ, STO, IMA
            obj = Surface(comment="OBJ", thickness=float('inf'))
            stop = Surface(comment="STO", is_stop=True, thickness=50.0, semi_diameter=10.0)
            ima = Surface(comment="IMA", semi_diameter=10.0)
            self.surfaces = [obj, stop, ima]

    @property
    def num_surfaces(self) -> int:
        return len(self.surfaces)

    @property
    def stop_surface(self) -> int:
        for i, s in enumerate(self.surfaces):
            if s.is_stop:
                return i
        return 1

    @stop_surface.setter
    def stop_surface(self, idx: int):
        for s in self.surfaces:
            s.is_stop = False
        if 0 <= idx < len(self.surfaces):
            self.surfaces[idx].is_stop = True

    def total_track(self) -> float:
        """Total length from first surface to image."""
        return sum(s.thickness for s in self.surfaces[:-1]
                   if abs(s.thickness) < 1e10)

    def insert_surface(self, idx: int):
        """Insert a new surface before idx."""
        new_surf = Surface(thickness=0.0, semi_diameter=10.0)
        self.surfaces.insert(idx, new_surf)

    def delete_surface(self, idx: int):
        """Delete surface at idx (cannot delete OBJ or IMA)."""
        if idx <= 0 or idx >= len(self.surfaces) - 1:
            return
        self.surfaces.pop(idx)

    def primary_wavelength(self) -> float:
        return self.wavelengths[self.primary_wavelength_idx]
