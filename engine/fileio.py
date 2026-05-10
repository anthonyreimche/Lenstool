"""File I/O for lens prescriptions (JSON-based .lens format)."""

import json
import os
from typing import Optional
from .surface import LensSystem, Surface, SurfaceType, SolveType


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
        # Save solve types (only non-default to keep files clean)
        if surf.radius_solve != SolveType.FIXED:
            s["radius_solve"] = surf.radius_solve.value
        if surf.thickness_solve != SolveType.FIXED:
            s["thickness_solve"] = surf.thickness_solve.value
        if surf.material_solve != SolveType.FIXED:
            s["material_solve"] = surf.material_solve.value
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
        # Load solve types
        if "radius_solve" in s:
            surf.radius_solve = SolveType(s["radius_solve"])
        if "thickness_solve" in s:
            surf.thickness_solve = SolveType(s["thickness_solve"])
        if "material_solve" in s:
            surf.material_solve = SolveType(s["material_solve"])
        system.surfaces.append(surf)

    if not system.surfaces:
        system.__post_init__()

    return system


def load_lens_library(folder: str) -> list:
    """Scan *folder* for .lens files and return a list of (title, filepath).

    Used by the Sample Lenses menu to discover user-created designs.
    Returns an empty list if the folder does not exist.
    """
    import glob
    if not os.path.isdir(folder):
        return []
    files = sorted(glob.glob(os.path.join(folder, "*.lens")))
    results = []
    for fp in files:
        try:
            with open(fp, "r") as f:
                import json as _json
                data = _json.load(f)
            title = data.get("title", os.path.splitext(os.path.basename(fp))[0])
            results.append((title, fp))
        except Exception:
            results.append((os.path.basename(fp), fp))
    return results


