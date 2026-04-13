"""File I/O for lens prescriptions (JSON-based .lens format)."""

import json
import os
from typing import Optional
from .surface import LensSystem, Surface, SurfaceType


def _auto_bfl(system: LensSystem):
    """Auto-compute back focal length for the last air space before IMA."""
    from .raytrace import trace_paraxial_ray
    last = len(system.surfaces) - 2  # last surface before IMA
    par = trace_paraxial_ray(system, system.entrance_pupil_diameter / 2.0,
                              0.0, system.primary_wavelength())
    # Use IMA surface values: y is at last surface (t=0 so no transfer),
    # u is the post-refraction slope from the last refracting surface
    y_ima = par.y_values[-1]
    u_ima = par.u_values[-1]
    if abs(u_ima) > 1e-15:
        system.surfaces[last].thickness = -y_ima / u_ima


def save_lens(system: LensSystem, filepath: str):
    """Save lens system to JSON file."""
    data = {
        "format": "LensTool",
        "version": "1.0",
        "title": system.title,
        "notes": system.notes,
        "wavelengths": system.wavelengths,
        "primary_wavelength_idx": system.primary_wavelength_idx,
        "fields": system.fields,
        "field_type": system.field_type,
        "entrance_pupil_diameter": system.entrance_pupil_diameter,
        "surfaces": []
    }

    for surf in system.surfaces:
        s = {
            "comment": surf.comment,
            "type": surf.surface_type.value,
            "radius": surf.radius,
            "thickness": surf.thickness,
            "material": surf.material,
            "semi_diameter": surf.semi_diameter,
            "conic": surf.conic,
            "is_stop": surf.is_stop,
        }
        if surf.aspheric_coeffs:
            s["aspheric_coeffs"] = surf.aspheric_coeffs
        data["surfaces"].append(s)

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def load_lens(filepath: str) -> LensSystem:
    """Load lens system from JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    system = LensSystem.__new__(LensSystem)
    system.title = data.get("title", "Untitled")
    system.notes = data.get("notes", "")
    system.wavelengths = data.get("wavelengths", [0.5876])
    system.primary_wavelength_idx = data.get("primary_wavelength_idx", 0)
    system.fields = data.get("fields", [0.0])
    system.field_type = data.get("field_type", "angle")
    system.entrance_pupil_diameter = data.get("entrance_pupil_diameter", 20.0)
    system.surfaces = []

    for s in data.get("surfaces", []):
        surf = Surface(
            comment=s.get("comment", ""),
            surface_type=SurfaceType(s.get("type", "Standard")),
            radius=s.get("radius", float('inf')),
            thickness=s.get("thickness", 0.0),
            material=s.get("material", ""),
            semi_diameter=s.get("semi_diameter", 10.0),
            conic=s.get("conic", 0.0),
            is_stop=s.get("is_stop", False),
            aspheric_coeffs=s.get("aspheric_coeffs", []),
        )
        system.surfaces.append(surf)

    if not system.surfaces:
        system.__post_init__()

    return system


def create_sample_doublet() -> LensSystem:
    """Create a sample cemented doublet lens."""
    system = LensSystem.__new__(LensSystem)
    system.title = "Cemented Doublet f/4"
    system.notes = "Classic crown-flint achromatic doublet"
    system.wavelengths = [0.4861, 0.5876, 0.6563]  # F, d, C lines
    system.primary_wavelength_idx = 1
    system.fields = [0.0, 3.5, 5.0]
    system.field_type = "angle"
    system.entrance_pupil_diameter = 25.0

    system.surfaces = [
        Surface(comment="OBJ", thickness=1e10, semi_diameter=0.0),
        Surface(comment="", radius=61.47, thickness=6.0, material="N-BK7",
                semi_diameter=14.0),
        Surface(comment="", radius=-43.28, thickness=2.5, material="N-SF5",
                semi_diameter=14.0),
        Surface(comment="", radius=-124.6, thickness=90.0, material="",
                semi_diameter=14.0),
        Surface(comment="STO", is_stop=True, thickness=5.0, semi_diameter=12.5),
        Surface(comment="IMA", semi_diameter=15.0),
    ]

    return system


def create_sample_cooke_triplet() -> LensSystem:
    """Create a Cooke triplet (positive-negative-positive) lens."""
    system = LensSystem.__new__(LensSystem)
    system.title = "Cooke Triplet f/7"
    system.notes = "Classic three-element anastigmat"
    system.wavelengths = [0.4861, 0.5876, 0.6563]
    system.primary_wavelength_idx = 1
    system.fields = [0.0, 10.0, 20.0]
    system.field_type = "angle"
    system.entrance_pupil_diameter = 10.0

    system.surfaces = [
        Surface(comment="OBJ", thickness=1e10),
        Surface(comment="L1", radius=26.10, thickness=3.50, material="SK16",
                semi_diameter=7.5),
        Surface(comment="", radius=146.50, thickness=6.00, material="",
                semi_diameter=7.5),
        Surface(comment="L2 STO", radius=-44.40, thickness=1.20, material="F2",
                semi_diameter=4.5, is_stop=True),
        Surface(comment="", radius=26.10, thickness=5.50, material="",
                semi_diameter=4.5),
        Surface(comment="L3", radius=81.50, thickness=3.50, material="SK16",
                semi_diameter=7.5),
        Surface(comment="", radius=-30.20, thickness=0.0, material="",
                semi_diameter=7.5),
        Surface(comment="IMA", semi_diameter=20.0),
    ]

    _auto_bfl(system)
    return system


def create_sample_petzval() -> LensSystem:
    """Create a Petzval-type lens (two separated doublets)."""
    system = LensSystem.__new__(LensSystem)
    system.title = "Petzval Lens f/3.5"
    system.notes = "Two separated positive groups"
    system.wavelengths = [0.4861, 0.5876, 0.6563]
    system.primary_wavelength_idx = 1
    system.fields = [0.0, 5.0, 10.0]
    system.field_type = "angle"
    system.entrance_pupil_diameter = 14.0

    system.surfaces = [
        Surface(comment="OBJ", thickness=1e10),
        Surface(comment="STO", radius=45.0, thickness=4.50, material="SK16",
                semi_diameter=9.0, is_stop=True),
        Surface(comment="", radius=-45.0, thickness=1.50, material="F2",
                semi_diameter=9.0),
        Surface(comment="", radius=-175.0, thickness=20.00, material="",
                semi_diameter=9.0),
        Surface(comment="", radius=30.0, thickness=4.00, material="SK16",
                semi_diameter=8.0),
        Surface(comment="", radius=-60.0, thickness=1.50, material="F2",
                semi_diameter=8.0),
        Surface(comment="", radius=-200.0, thickness=0.0, material="",
                semi_diameter=8.0),
        Surface(comment="IMA", semi_diameter=18.0),
    ]

    _auto_bfl(system)
    return system


def create_sample_telephoto() -> LensSystem:
    """Create a telephoto lens (positive front, negative rear)."""
    system = LensSystem.__new__(LensSystem)
    system.title = "Telephoto"
    system.notes = "Two-group telephoto with short total track"
    system.wavelengths = [0.4861, 0.5876, 0.6563]
    system.primary_wavelength_idx = 1
    system.fields = [0.0, 2.0, 4.0]
    system.field_type = "angle"
    system.entrance_pupil_diameter = 20.0

    system.surfaces = [
        Surface(comment="OBJ", thickness=1e10),
        Surface(comment="STO L1a", radius=38.0, thickness=6.0, material="N-BK7",
                semi_diameter=14.0, is_stop=True),
        Surface(comment="L1b", radius=-28.0, thickness=2.0, material="N-SF5",
                semi_diameter=14.0),
        Surface(comment="", radius=-80.0, thickness=45.0, material="",
                semi_diameter=14.0),
        Surface(comment="L2", radius=-100.0, thickness=2.0, material="N-BK7",
                semi_diameter=8.0),
        Surface(comment="", radius=300.0, thickness=0.0, material="",
                semi_diameter=8.0),
        Surface(comment="IMA", semi_diameter=15.0),
    ]

    _auto_bfl(system)
    return system


def create_sample_landscape() -> LensSystem:
    """Create a landscape (meniscus) lens with front stop."""
    system = LensSystem.__new__(LensSystem)
    system.title = "Landscape Lens"
    system.notes = "Single meniscus with remote stop for field correction"
    system.wavelengths = [0.4861, 0.5876, 0.6563]
    system.primary_wavelength_idx = 1
    system.fields = [0.0, 10.0, 20.0]
    system.field_type = "angle"
    system.entrance_pupil_diameter = 5.0

    system.surfaces = [
        Surface(comment="OBJ", thickness=1e10),
        Surface(comment="STO", is_stop=True, thickness=10.0, semi_diameter=4.0),
        Surface(comment="L1", radius=-80.0, thickness=3.0, material="N-BK7",
                semi_diameter=8.0),
        Surface(comment="", radius=-25.0, thickness=0.0, material="",
                semi_diameter=8.0),
        Surface(comment="IMA", semi_diameter=25.0),
    ]

    _auto_bfl(system)
    return system


def create_sample_singlet() -> LensSystem:
    """Create a simple plano-convex singlet."""
    system = LensSystem.__new__(LensSystem)
    system.title = "Plano-Convex Singlet f/5"
    system.notes = "Simple singlet lens"
    system.wavelengths = [0.4861, 0.5876, 0.6563]
    system.primary_wavelength_idx = 1
    system.fields = [0.0, 5.0, 10.0]
    system.field_type = "angle"
    system.entrance_pupil_diameter = 20.0

    system.surfaces = [
        Surface(comment="OBJ", thickness=1e10),
        Surface(comment="STO", radius=51.68, thickness=5.0, material="BK7",
                semi_diameter=12.0, is_stop=True),
        Surface(comment="", radius=float('inf'), thickness=96.70, material="",
                semi_diameter=12.0),
        Surface(comment="IMA", semi_diameter=20.0),
    ]

    return system


def create_sample_double_gauss() -> LensSystem:
    """Create a simplified Double Gauss (Biotar-type) lens."""
    system = LensSystem.__new__(LensSystem)
    system.title = "Double Gauss f/2.8"
    system.notes = "4-element symmetric Double Gauss"
    system.wavelengths = [0.4861, 0.5876, 0.6563]
    system.primary_wavelength_idx = 1
    system.fields = [0.0, 7.0, 14.0]
    system.field_type = "angle"
    system.entrance_pupil_diameter = 18.0

    system.surfaces = [
        Surface(comment="OBJ", thickness=1e10),
        Surface(comment="L1", radius=56.20, thickness=5.40, material="LAK9",
                semi_diameter=14.0),
        Surface(comment="", radius=152.0, thickness=0.50, material="",
                semi_diameter=14.0),
        Surface(comment="L2", radius=37.80, thickness=6.50, material="LAK9",
                semi_diameter=13.0),
        Surface(comment="L2b", radius=137.0, thickness=2.00, material="SF2",
                semi_diameter=12.0),
        Surface(comment="", radius=24.20, thickness=8.00, material="",
                semi_diameter=9.5),
        Surface(comment="STO", thickness=8.00, semi_diameter=9.0, is_stop=True),
        Surface(comment="L3", radius=-23.50, thickness=2.00, material="SF2",
                semi_diameter=9.5),
        Surface(comment="L3b", radius=-131.0, thickness=6.00, material="LAK9",
                semi_diameter=12.0),
        Surface(comment="", radius=-36.26, thickness=0.50, material="",
                semi_diameter=13.0),
        Surface(comment="L4", radius=530.0, thickness=4.50, material="LAK9",
                semi_diameter=13.5),
        Surface(comment="", radius=-54.60, thickness=0.0, material="",
                semi_diameter=13.5),
        Surface(comment="IMA", semi_diameter=22.0),
    ]

    _auto_bfl(system)
    return system
