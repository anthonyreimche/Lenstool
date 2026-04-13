"""Glass material catalog with Sellmeier dispersion models."""

import json
import numpy as np
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Glass:
    """Glass material with Sellmeier dispersion coefficients."""
    name: str
    nd: float  # refractive index at d-line
    vd: float  # Abbe number
    # Sellmeier coefficients
    B1: float = 0.0
    B2: float = 0.0
    B3: float = 0.0
    C1: float = 0.0
    C2: float = 0.0
    C3: float = 0.0

    def refractive_index(self, wavelength_um: float) -> float:
        """Compute refractive index using Sellmeier equation.
        wavelength_um: wavelength in micrometers.
        """
        if self.B1 == 0 and self.B2 == 0 and self.B3 == 0:
            # Use simplified Cauchy approximation from nd and vd
            return self._cauchy_index(wavelength_um)

        lam2 = wavelength_um ** 2
        n2 = 1.0 + (self.B1 * lam2 / (lam2 - self.C1) +
                     self.B2 * lam2 / (lam2 - self.C2) +
                     self.B3 * lam2 / (lam2 - self.C3))
        return np.sqrt(n2)

    def _cauchy_index(self, wavelength_um: float) -> float:
        """Approximate index from nd, vd using Cauchy-like model."""
        # Standard wavelengths
        lam_d = 0.5876  # d-line
        lam_F = 0.4861  # F-line
        lam_C = 0.6563  # C-line

        nF_nC = (self.nd - 1.0) / self.vd if self.vd > 0 else 0.0
        # Linear dispersion model
        # n(lam) ≈ nd + (nF-nC) * (lam_d^2 - lam^2) / (lam_d^2 - lam_F*lam_C) approximately
        A = self.nd
        B = nF_nC * lam_F * lam_C  # simplified Cauchy B
        return A + B / (wavelength_um ** 2) - B / (lam_d ** 2)


# Built-in glass catalog (Schott glasses with Sellmeier coefficients)
GLASS_CATALOG = {}


def _add_glass(name, nd, vd, B1, B2, B3, C1, C2, C3):
    GLASS_CATALOG[name.upper()] = Glass(name, nd, vd, B1, B2, B3, C1, C2, C3)


# Schott catalog - common glasses
_add_glass("BK7", 1.5168, 64.17,
           1.03961212, 0.231792344, 1.01046945,
           0.00600069867, 0.0200179144, 103.560653)

_add_glass("SF11", 1.78472, 25.68,
           1.73759695, 0.313747346, 1.89878101,
           0.013188707, 0.0623068142, 155.23629)

_add_glass("SF2", 1.64769, 33.82,
           1.40301821, 0.231767504, 0.939056586,
           0.0105795466, 0.0493226978, 112.405955)

_add_glass("SK16", 1.62041, 60.32,
           1.34317774, 0.241144399, 0.994317969,
           0.00704687339, 0.0229005, 92.7508526)

_add_glass("F2", 1.62004, 36.37,
           1.34533359, 0.209073176, 0.937357162,
           0.00997743871, 0.0470450767, 111.886764)

_add_glass("F5", 1.60342, 38.03,
           1.3104464, 0.19603426, 0.96612977,
           0.00958633048, 0.0457627627, 115.011883)

_add_glass("BAF10", 1.67003, 47.11,
           1.5851495, 0.143559385, 1.08521269,
           0.00926681282, 0.0424489805, 105.613573)

_add_glass("BAK1", 1.5725, 57.55,
           1.12365662, 0.309276848, 0.881511957,
           0.00644742752, 0.0222284402, 107.297751)

_add_glass("BAK4", 1.56883, 55.98,
           1.28834642, 0.132817724, 0.945395373,
           0.00779980626, 0.0315631177, 105.965875)

_add_glass("SK4", 1.61272, 58.63,
           1.32993741, 0.228542996, 0.988465211,
           0.00716874107, 0.0246455892, 100.886364)

_add_glass("LAK9", 1.6910, 54.71,
           1.46231905, 0.344399589, 1.15508372,
           0.00724270156, 0.0243353131, 85.4686868)

_add_glass("LASF9", 1.85025, 32.17,
           2.00029547, 0.298926886, 1.80691843,
           0.0121426017, 0.0538736236, 156.530829)

_add_glass("SSK4", 1.61772, 55.12,
           1.32993741, 0.228542996, 0.988465211,
           0.00716874107, 0.0246455892, 100.886364)

_add_glass("N-BK7", 1.5168, 64.17,
           1.03961212, 0.231792344, 1.01046945,
           0.00600069867, 0.0200179144, 103.560653)

_add_glass("N-SF11", 1.78472, 25.76,
           1.73759695, 0.313747346, 1.89878101,
           0.013188707, 0.0623068142, 155.23629)

_add_glass("N-LAK22", 1.65113, 55.89,
           1.14229781, 0.535138441, 1.04088385,
           0.00585778594, 0.0198546147, 100.834017)

_add_glass("N-SF6", 1.80518, 25.36,
           1.77931763, 0.338149866, 2.08734474,
           0.0133714182, 0.0617533621, 174.01759)

_add_glass("N-SF5", 1.67271, 32.25,
           1.52481889, 0.187085527, 1.42729015,
           0.011254756, 0.0588995392, 129.141675)

_add_glass("N-FK51A", 1.48656, 84.47,
           0.971247817, 0.216901417, 0.904651666,
           0.00472301995, 0.0153575612, 168.68133)

_add_glass("N-LAF2", 1.7440, 44.85,
           1.80984227, 0.156571813, 1.0917464,
           0.0101711622, 0.0442431765, 100.687748)

# Mirror (dummy entry)
GLASS_CATALOG["MIRROR"] = Glass("MIRROR", 1.0, 0.0)


def get_glass(name: str) -> Optional[Glass]:
    """Look up a glass by name."""
    if not name or name.upper() in ("", "AIR"):
        return None
    return GLASS_CATALOG.get(name.upper())


def refractive_index(material_name: str, wavelength_um: float) -> float:
    """Get refractive index for a named material at a given wavelength."""
    glass = get_glass(material_name)
    if glass is None:
        return 1.0  # Air
    return glass.refractive_index(wavelength_um)


def available_glasses() -> list:
    """Return sorted list of available glass names."""
    return sorted(GLASS_CATALOG.keys())


# Track which glasses are user-added (not built-in)
_BUILTIN_GLASSES = set(GLASS_CATALOG.keys())


def is_custom_glass(name: str) -> bool:
    """Check if a glass is user-added (not built-in)."""
    return name.upper() in GLASS_CATALOG and name.upper() not in _BUILTIN_GLASSES


def add_custom_glass(name: str, nd: float, vd: float,
                     B1=0.0, B2=0.0, B3=0.0, C1=0.0, C2=0.0, C3=0.0):
    """Add a custom glass to the catalog."""
    key = name.upper()
    GLASS_CATALOG[key] = Glass(name, nd, vd, B1, B2, B3, C1, C2, C3)


def remove_custom_glass(name: str) -> bool:
    """Remove a custom glass. Returns False if it's a built-in glass."""
    key = name.upper()
    if key in _BUILTIN_GLASSES:
        return False
    if key in GLASS_CATALOG:
        del GLASS_CATALOG[key]
        return True
    return False


def save_glass_catalog(filepath: str):
    """Save all custom glasses to a JSON catalog file."""
    customs = []
    for key, glass in GLASS_CATALOG.items():
        if key not in _BUILTIN_GLASSES:
            customs.append(asdict(glass))
    with open(filepath, 'w') as f:
        json.dump({"format": "LensTool Glass Catalog", "version": "1.0",
                    "glasses": customs}, f, indent=2)


def load_glass_catalog(filepath: str) -> int:
    """Load custom glasses from a JSON catalog file. Returns count loaded."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    count = 0
    for g in data.get("glasses", []):
        name = g.get("name", "")
        if not name:
            continue
        key = name.upper()
        GLASS_CATALOG[key] = Glass(
            name=name, nd=g.get("nd", 1.5), vd=g.get("vd", 50.0),
            B1=g.get("B1", 0.0), B2=g.get("B2", 0.0), B3=g.get("B3", 0.0),
            C1=g.get("C1", 0.0), C2=g.get("C2", 0.0), C3=g.get("C3", 0.0))
        count += 1
    return count
