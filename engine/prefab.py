"""Prefab element catalog — stock lens elements the company manufactures.

Each PrefabElement describes a single physical lens element (one or more
glass surfaces) with fixed geometry.  Designers can search the catalog
to find elements close to what the optimizer produced, or constrain the
design to use only prefab parts.
"""

import json
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class PrefabElement:
    """A manufactured lens element in the company inventory."""
    part_number: str = ""
    description: str = ""
    # Geometry (single-element: 2 surfaces)
    r1: float = float('inf')       # front radius of curvature (mm)
    r2: float = float('inf')       # back radius of curvature (mm)
    thickness: float = 5.0         # center thickness (mm)
    material: str = "BK7"          # glass name
    diameter: float = 25.0         # clear aperture / outer diameter (mm)
    # Optional second cemented element (doublet)
    r3: float = 0.0                # 0 = not a doublet
    thickness2: float = 0.0
    material2: str = ""
    # Metadata
    category: str = ""             # e.g. "plano-convex", "doublet", "meniscus"
    efl_nominal: float = 0.0       # nominal EFL if known (mm)
    coating: str = ""              # e.g. "MgF2", "BBAR"
    notes: str = ""

    @property
    def is_doublet(self) -> bool:
        return self.r3 != 0.0 and self.material2 != ""

    @property
    def num_surfaces(self) -> int:
        return 4 if self.is_doublet else 2


# ---------------------------------------------------------------------------
# Built-in prefab catalog (common stock optics)
# ---------------------------------------------------------------------------

PREFAB_CATALOG: List[PrefabElement] = []


def _add(part, desc, r1, r2, t, mat, dia, cat, efl=0.0, **kw):
    PREFAB_CATALOG.append(PrefabElement(
        part_number=part, description=desc,
        r1=r1, r2=r2, thickness=t, material=mat, diameter=dia,
        category=cat, efl_nominal=efl, **kw))


# --- Plano-convex singlets ---
_add("PCX-25-50", "Plano-convex f=50mm", 25.84, float('inf'), 5.3, "BK7", 25.0,
     "plano-convex", 50.0)
_add("PCX-25-75", "Plano-convex f=75mm", 38.76, float('inf'), 4.1, "BK7", 25.0,
     "plano-convex", 75.0)
_add("PCX-25-100", "Plano-convex f=100mm", 51.68, float('inf'), 3.5, "BK7", 25.0,
     "plano-convex", 100.0)
_add("PCX-25-150", "Plano-convex f=150mm", 77.52, float('inf'), 2.9, "BK7", 25.0,
     "plano-convex", 150.0)
_add("PCX-25-200", "Plano-convex f=200mm", 103.36, float('inf'), 2.6, "BK7", 25.0,
     "plano-convex", 200.0)
_add("PCX-50-100", "Plano-convex f=100mm D=50", 51.68, float('inf'), 7.1, "BK7", 50.0,
     "plano-convex", 100.0)
_add("PCX-50-200", "Plano-convex f=200mm D=50", 103.36, float('inf'), 4.8, "BK7", 50.0,
     "plano-convex", 200.0)

# --- Bi-convex ---
_add("BCX-25-50", "Bi-convex f=50mm", 46.1, -46.1, 5.8, "BK7", 25.0,
     "bi-convex", 50.0)
_add("BCX-25-100", "Bi-convex f=100mm", 92.2, -92.2, 3.6, "BK7", 25.0,
     "bi-convex", 100.0)
_add("BCX-25-200", "Bi-convex f=200mm", 184.4, -184.4, 2.8, "BK7", 25.0,
     "bi-convex", 200.0)

# --- Plano-concave ---
_add("PCV-25-N50", "Plano-concave f=-50mm", float('inf'), 25.84, 2.0, "BK7", 25.0,
     "plano-concave", -50.0)
_add("PCV-25-N100", "Plano-concave f=-100mm", float('inf'), 51.68, 2.0, "BK7", 25.0,
     "plano-concave", -100.0)

# --- Meniscus ---
_add("MEN-25-100", "Pos. meniscus f=100mm", 38.6, 71.8, 3.5, "BK7", 25.0,
     "meniscus", 100.0)
_add("MEN-25-200", "Pos. meniscus f=200mm", 69.1, 125.0, 2.8, "BK7", 25.0,
     "meniscus", 200.0)

# --- Achromatic doublets ---
_add("ACH-25-50", "Achromat f=50mm", 31.2, -23.4, 6.0, "N-BK7", 25.0,
     "achromat", 50.0,
     r3=-23.4, thickness2=2.5, material2="N-SF5")
_add("ACH-25-75", "Achromat f=75mm", 46.1, -34.5, 5.0, "N-BK7", 25.0,
     "achromat", 75.0,
     r3=-34.5, thickness2=2.0, material2="N-SF5")
_add("ACH-25-100", "Achromat f=100mm", 61.47, -44.64, 6.0, "N-BK7", 25.0,
     "achromat", 100.0,
     r3=-44.64, thickness2=2.5, material2="N-SF5")
_add("ACH-25-150", "Achromat f=150mm", 91.2, -67.3, 4.5, "N-BK7", 25.0,
     "achromat", 150.0,
     r3=-67.3, thickness2=2.0, material2="N-SF5")
_add("ACH-25-200", "Achromat f=200mm", 119.7, -88.6, 4.0, "N-BK7", 25.0,
     "achromat", 200.0,
     r3=-88.6, thickness2=1.8, material2="N-SF5")
_add("ACH-50-100", "Achromat f=100mm D=50", 61.47, -44.64, 10.0, "N-BK7", 50.0,
     "achromat", 100.0,
     r3=-44.64, thickness2=4.0, material2="N-SF5")
_add("ACH-50-200", "Achromat f=200mm D=50", 119.7, -88.6, 7.0, "N-BK7", 50.0,
     "achromat", 200.0,
     r3=-88.6, thickness2=3.0, material2="N-SF5")


# ---------------------------------------------------------------------------
# Search & matching
# ---------------------------------------------------------------------------

def search_prefab(query: str = "", category: str = "",
                  efl_min: float = -1e10, efl_max: float = 1e10,
                  dia_min: float = 0, dia_max: float = 1e10) -> List[PrefabElement]:
    """Search the prefab catalog with filters."""
    results = []
    q = query.upper()
    for elem in PREFAB_CATALOG:
        if q and q not in elem.part_number.upper() and q not in elem.description.upper():
            continue
        if category and category.lower() != elem.category.lower():
            continue
        if elem.efl_nominal != 0:
            if not (efl_min <= elem.efl_nominal <= efl_max):
                continue
        if not (dia_min <= elem.diameter <= dia_max):
            continue
        results.append(elem)
    return results


def match_prefab(r1: float, r2: float, thickness: float,
                 material: str, diameter: float,
                 max_results: int = 5) -> List[tuple]:
    """Find prefab elements closest to the given parameters.

    Returns list of (PrefabElement, distance_score) sorted by distance.
    Distance is a weighted Euclidean metric over normalized parameters.
    """
    results = []
    for elem in PREFAB_CATALOG:
        # Normalize radii comparison (use curvature to handle infinity)
        c1_a = 0.0 if abs(r1) > 1e10 else 1.0 / r1
        c1_b = 0.0 if abs(elem.r1) > 1e10 else 1.0 / elem.r1
        c2_a = 0.0 if abs(r2) > 1e10 else 1.0 / r2
        c2_b = 0.0 if abs(elem.r2) > 1e10 else 1.0 / elem.r2

        d_curv = (c1_a - c1_b) ** 2 + (c2_a - c2_b) ** 2
        d_thick = ((thickness - elem.thickness) / max(thickness, 1.0)) ** 2
        d_dia = ((diameter - elem.diameter) / max(diameter, 1.0)) ** 2

        # Material match bonus
        mat_penalty = 0.0 if material.upper() == elem.material.upper() else 0.1

        score = np.sqrt(d_curv * 1000 + d_thick + d_dia + mat_penalty)
        results.append((elem, score))

    results.sort(key=lambda x: x[1])
    return results[:max_results]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_prefab_catalog(filepath: str, elements: List[PrefabElement] = None):
    """Save prefab catalog to JSON."""
    elems = elements or PREFAB_CATALOG
    data = {
        "format": "LensTool Prefab Catalog",
        "version": "1.0",
        "elements": [asdict(e) for e in elems],
    }
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=_json_default)


def load_prefab_catalog(filepath: str, replace: bool = False) -> int:
    """Load prefab elements from JSON. Returns count loaded."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    if replace:
        PREFAB_CATALOG.clear()
    count = 0
    for d in data.get("elements", []):
        elem = PrefabElement(
            part_number=d.get("part_number", ""),
            description=d.get("description", ""),
            r1=_float_or_inf(d.get("r1", float('inf'))),
            r2=_float_or_inf(d.get("r2", float('inf'))),
            thickness=d.get("thickness", 5.0),
            material=d.get("material", "BK7"),
            diameter=d.get("diameter", 25.0),
            r3=d.get("r3", 0.0),
            thickness2=d.get("thickness2", 0.0),
            material2=d.get("material2", ""),
            category=d.get("category", ""),
            efl_nominal=d.get("efl_nominal", 0.0),
            coating=d.get("coating", ""),
            notes=d.get("notes", ""),
        )
        PREFAB_CATALOG.append(elem)
        count += 1
    return count


def add_prefab_element(elem: PrefabElement):
    """Add an element to the catalog."""
    PREFAB_CATALOG.append(elem)


def remove_prefab_element(index: int) -> bool:
    """Remove an element by index."""
    if 0 <= index < len(PREFAB_CATALOG):
        PREFAB_CATALOG.pop(index)
        return True
    return False


def prefab_categories() -> List[str]:
    """Return sorted unique categories in the catalog."""
    cats = set(e.category for e in PREFAB_CATALOG if e.category)
    return sorted(cats)


def _float_or_inf(val):
    """Handle JSON null/string infinity."""
    if val is None or val == "Infinity" or val == "inf":
        return float('inf')
    if val == "-Infinity" or val == "-inf":
        return float('-inf')
    return float(val)


def _json_default(obj):
    """Handle infinity for JSON serialization."""
    if isinstance(obj, float):
        if np.isinf(obj):
            return "Infinity" if obj > 0 else "-Infinity"
    return obj
