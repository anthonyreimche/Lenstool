"""Sequential ray tracing engine for rotationally symmetric systems."""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Tuple, List
from .surface import LensSystem, Surface
from .materials import refractive_index


@dataclass
class Ray:
    """A single ray defined by position and direction cosines."""
    y: float = 0.0  # height
    z: float = 0.0  # along optical axis
    u: float = 0.0  # direction cosine (angle tangent in paraxial, sin in real)
    wavelength: float = 0.5876  # microns
    vignetted: bool = False


@dataclass
class RayTraceResult:
    """Result of tracing a single ray through the system."""
    y_values: list = field(default_factory=list)  # y at each surface
    z_values: list = field(default_factory=list)  # z at each surface
    u_values: list = field(default_factory=list)  # u after each surface
    vignetted: bool = False
    error: str = ""


@dataclass
class RayFanResult:
    """Result of tracing a fan of rays."""
    pupil_coords: np.ndarray = None  # normalized pupil coordinates
    x_aberration: np.ndarray = None
    y_aberration: np.ndarray = None
    opd: np.ndarray = None  # optical path difference


def trace_paraxial_ray(system: LensSystem, y0: float, u0: float,
                        wavelength: float = 0.5876) -> RayTraceResult:
    """Trace a paraxial ray through the system (y-u trace)."""
    result = RayTraceResult()
    y = y0
    u = u0

    for i, surf in enumerate(system.surfaces):
        result.y_values.append(y)
        result.z_values.append(0.0)
        result.u_values.append(u)

        if i == len(system.surfaces) - 1:
            break  # last surface (image)

        c = surf.curvature
        n1 = _get_index_before(system, i, wavelength)
        n2 = _get_index_after(system, i, wavelength)

        # Refraction: n2*u2 = n1*u1 - y*c*(n2-n1)
        u_prime = (n1 * u - y * c * (n2 - n1)) / n2

        # Transfer: y_next = y + u_prime * t
        t = surf.thickness
        if abs(t) >= 1e10:
            t = 0.0

        y_next = y + u_prime * t
        u = u_prime
        y = y_next

    return result


def trace_real_ray_2d(system: LensSystem, y0: float, u0: float,
                       wavelength: float = 0.5876) -> RayTraceResult:
    """Trace a real (finite) ray in the y-z meridional plane using exact Snell's law."""
    result = RayTraceResult()

    y = y0
    z = 0.0
    sin_u = np.sin(np.arctan(u0)) if abs(u0) < 10 else u0 / np.sqrt(1 + u0 * u0)
    cos_u = np.sqrt(1.0 - sin_u ** 2)

    # Direction vector (dy, dz)
    L = sin_u
    M = cos_u

    z_global = 0.0  # running z position of each surface vertex

    for i, surf in enumerate(system.surfaces):
        # For object surface with infinite thickness, skip ahead to surface 1
        if i == 0 and abs(surf.thickness) > 1e9:
            result.y_values.append(y)
            result.z_values.append(0.0)
            result.u_values.append(np.arctan2(L, M))
            # No refraction at object surface (flat, air-air)
            z_global = 0.0
            continue

        if i == len(system.surfaces) - 1:
            # Intersect with image plane
            y_int, z_int = _intersect_surface_2d(y, z, L, M, z_global, surf)
            if y_int is not None:
                result.y_values.append(y_int)
                result.z_values.append(z_int)
            else:
                result.y_values.append(y)
                result.z_values.append(z)
            result.u_values.append(np.arctan2(L, M))
            break

        result.y_values.append(y)
        result.z_values.append(z)

        n1 = _get_index_before(system, i, wavelength)
        n2 = _get_index_after(system, i, wavelength)

        # Check for vignetting
        if abs(y) > surf.semi_diameter * 1.01 and surf.semi_diameter > 0:
            result.vignetted = True

        c = surf.curvature

        # Find intersection with surface using iterative method
        y_int, z_int = _intersect_surface_2d(y, z, L, M, z_global, surf)
        if y_int is None:
            result.vignetted = True
            result.error = f"Ray missed surface {i}"
            # Pad remaining
            for j in range(i + 1, len(system.surfaces)):
                result.y_values.append(y)
                result.z_values.append(z)
                result.u_values.append(0.0)
            return result

        y = y_int
        z = z_int

        # Check mirror
        is_mirror = surf.material.upper() == "MIRROR" if surf.material else False

        if is_mirror:
            # Reflection
            normal = _surface_normal_2d(surf, y, z_global)
            dot = L * normal[0] + M * normal[1]
            L = L - 2.0 * dot * normal[0]
            M = M - 2.0 * dot * normal[1]
            # Mirror reverses propagation direction sense
            n2 = -n1
        else:
            # Refraction via Snell's law (vector form)
            if abs(n2 - n1) > 1e-12:
                normal = _surface_normal_2d(surf, y, z_global)
                cos_i = L * normal[0] + M * normal[1]
                sin_i2 = 1.0 - cos_i ** 2
                ratio = n1 / n2
                sin_t2 = ratio ** 2 * sin_i2

                if sin_t2 > 1.0:
                    result.vignetted = True
                    result.error = f"Total internal reflection at surface {i}"
                    for j in range(i + 1, len(system.surfaces)):
                        result.y_values.append(y)
                        result.z_values.append(z)
                        result.u_values.append(0.0)
                    return result

                cos_t = np.sqrt(1.0 - sin_t2)
                if cos_i < 0:
                    cos_t = -cos_t

                # Normal points forward (same as ray), so use minus sign
                # d_t = ratio*d - (ratio*cos_i - cos_t)*n
                factor = ratio * cos_i - cos_t
                L = ratio * L - factor * normal[0]
                M = ratio * M - factor * normal[1]

                # Renormalize
                mag = np.sqrt(L ** 2 + M ** 2)
                L /= mag
                M /= mag

        result.u_values.append(np.arctan2(L, M))

        # Transfer to next surface
        t = surf.thickness
        if abs(t) >= 1e10:
            t = 0.0
        z_global += t

    return result


def _intersect_surface_2d(y: float, z: float, L: float, M: float,
                           z_vertex: float, surf: Surface) -> Tuple[Optional[float], Optional[float]]:
    """Find intersection of ray with surface in 2D."""
    c = surf.curvature
    k = surf.conic

    if abs(c) < 1e-18 and not surf.aspheric_coeffs:
        # Flat surface: find z = z_vertex
        if abs(M) < 1e-18:
            return None, None
        t = (z_vertex - z) / M
        y_int = y + t * L
        z_int = z + t * M
        return y_int, z_int

    # Iterative intersection for general conic + asphere
    # Initial guess: intersect with base sphere
    dz = z_vertex - z
    if abs(c) < 1e-18:
        # Nearly flat with aspheric terms
        if abs(M) < 1e-18:
            return None, None
        t = dz / M
    else:
        # Quadratic for sphere intersection
        # Ray: (y + L*t, z + M*t); surface at z_vertex + sag(y)
        # For sphere: c*y^2 - 2*(z-z_vertex) = 0 approximately
        A_coeff = c * (L ** 2) - 0  # simplified
        # Use proper sphere intersection
        A_coeff = c * L ** 2 + c * M ** 2
        B_coeff = 2.0 * c * (y * L + (z - z_vertex) * M) - 2.0 * M
        C_coeff = c * (y ** 2 + (z - z_vertex) ** 2) - 2.0 * (z - z_vertex)

        # Handle the case where A is very small
        if abs(A_coeff) < 1e-18:
            if abs(B_coeff) < 1e-18:
                return None, None
            t = -C_coeff / B_coeff
        else:
            disc = B_coeff ** 2 - 4.0 * A_coeff * C_coeff
            if disc < 0:
                return None, None
            sqrt_disc = np.sqrt(disc)
            t1 = (-B_coeff + sqrt_disc) / (2.0 * A_coeff)
            t2 = (-B_coeff - sqrt_disc) / (2.0 * A_coeff)
            # Choose the smaller positive t (or the one closest to expected)
            if t1 > 0 and t2 > 0:
                t = min(t1, t2)
            elif t1 > 0:
                t = t1
            elif t2 > 0:
                t = t2
            else:
                t = t1 if abs(t1) < abs(t2) else t2

    # Newton iteration for exact intersection (handles aspheres and conics)
    for _iteration in range(20):
        y_int = y + t * L
        z_int = z + t * M
        sag = surf.sag(y_int)
        z_surf = z_vertex + sag
        residual = z_int - z_surf

        if abs(residual) < 1e-12:
            return y_int, z_int

        # Derivative of residual w.r.t. t
        # d(z_int)/dt = M; d(z_surf)/dt = dsag/dy * dy/dt = dsag/dy * L
        c_val = surf.curvature
        k_val = surf.conic
        r2 = y_int ** 2

        if abs(c_val) < 1e-18:
            dsag_dy = 0.0
        else:
            denom = 1.0 - (1.0 + k_val) * c_val ** 2 * r2
            if denom < 1e-12:
                denom = 1e-12
            dsag_dy = c_val * y_int / np.sqrt(denom)

        # Aspheric contribution
        for j, coeff in enumerate(surf.aspheric_coeffs):
            power = 2 * (j + 2)
            dsag_dy += coeff * power * y_int ** (power - 1)

        dr_dt = M - dsag_dy * L
        if abs(dr_dt) < 1e-18:
            break
        t -= residual / dr_dt

    y_int = y + t * L
    z_int = z + t * M
    return y_int, z_int


def _surface_normal_2d(surf: Surface, y: float, z_vertex: float) -> np.ndarray:
    """Compute inward-pointing surface normal in y-z plane."""
    c = surf.curvature
    k = surf.conic
    r2 = y * y

    if abs(c) < 1e-18:
        dzdy = 0.0
    else:
        denom = 1.0 - (1.0 + k) * c * c * r2
        if denom < 1e-12:
            denom = 1e-12
        dzdy = c * y / np.sqrt(denom)

    for j, coeff in enumerate(surf.aspheric_coeffs):
        power = 2 * (j + 2)
        dzdy += coeff * power * y ** (power - 1)

    # Normal pointing towards incoming light: (-dzdy, 1) normalized
    # but we want it pointing into the surface (toward z+)
    normal = np.array([-dzdy, 1.0])
    normal /= np.linalg.norm(normal)
    return normal


def _get_index_before(system: LensSystem, surf_idx: int, wavelength: float) -> float:
    """Get refractive index of medium before surface surf_idx."""
    if surf_idx == 0:
        return 1.0  # Object space is air
    prev_mat = system.surfaces[surf_idx - 1].material
    return refractive_index(prev_mat, wavelength)


def _get_index_after(system: LensSystem, surf_idx: int, wavelength: float) -> float:
    """Get refractive index of medium after surface surf_idx."""
    mat = system.surfaces[surf_idx].material
    return refractive_index(mat, wavelength)


def trace_ray_fan(system: LensSystem, field_angle: float = 0.0,
                   wavelength: float = 0.5876, num_rays: int = 21,
                   direction: str = "Y") -> RayFanResult:
    """Trace a fan of rays across the pupil for a given field angle.

    Rays span the entrance pupil at the given field angle.
    Transverse aberration = ray intersection at image - chief ray intersection.
    """
    result = RayFanResult()
    pupil_coords = np.linspace(-1.0, 1.0, num_rays)
    result.pupil_coords = pupil_coords

    epd = system.entrance_pupil_diameter
    u_field = np.tan(np.radians(field_angle))

    # Chief ray: through center of pupil at field angle
    chief_result = trace_real_ray_2d(system, 0.0, u_field, wavelength)
    y_chief_ima = chief_result.y_values[-1] if not chief_result.vignetted else 0.0

    y_aberr = np.zeros(num_rays)
    x_aberr = np.zeros(num_rays)

    for i, py in enumerate(pupil_coords):
        # Ray enters at pupil height py * EPD/2, with field angle direction
        y_start = py * epd / 2.0
        ray_result = trace_real_ray_2d(system, y_start, u_field, wavelength)

        if ray_result.vignetted:
            y_aberr[i] = np.nan
            x_aberr[i] = np.nan
        else:
            y_aberr[i] = ray_result.y_values[-1] - y_chief_ima

    result.y_aberration = y_aberr
    result.x_aberration = x_aberr
    return result


def _trace_chief_ray(system: LensSystem, field_angle: float,
                      wavelength: float) -> RayTraceResult:
    """Trace the chief ray (through center of stop) for given field."""
    u_field = np.tan(np.radians(field_angle))
    return trace_real_ray_2d(system, 0.0, u_field, wavelength)


def trace_spot_diagram(system: LensSystem, field_angle: float = 0.0,
                        wavelength: float = 0.5876,
                        num_rings: int = 6, num_arms: int = 12) -> Tuple[np.ndarray, np.ndarray]:
    """Trace rays in a polar grid on the pupil for spot diagram.

    Since this is a 2D meridional tracer, the sagittal (x) displacement is
    approximated.  For each pupil point at radius r and angle theta:
      - Trace at the full pupil radius r to get the transverse aberration eps(r).
      - y-displacement: trace at the tangential pupil coord py for the exact
        meridional aberration (important off-axis where coma breaks symmetry).
      - x-displacement: eps(r) * sin(theta), distributing the radial aberration
        by the sagittal component of the pupil vector.
    """
    epd = system.entrance_pupil_diameter
    u_field = np.tan(np.radians(field_angle))

    # Chief ray for reference
    chief = trace_real_ray_2d(system, 0.0, u_field, wavelength)
    y_ref = chief.y_values[-1] if not chief.vignetted else 0.0

    x_spots = []
    y_spots = []

    # Cache aberration at each pupil radius to avoid redundant traces
    _eps_cache = {}

    def _get_eps(r_norm):
        """Get transverse aberration at normalized pupil radius r."""
        r_key = round(r_norm, 8)
        if r_key not in _eps_cache:
            res = trace_real_ray_2d(system, r_norm * epd / 2.0, u_field, wavelength)
            if not res.vignetted:
                _eps_cache[r_key] = res.y_values[-1] - y_ref
            else:
                _eps_cache[r_key] = None
        return _eps_cache[r_key]

    # Polar grid on entrance pupil. Use a uniform angular density per ring
    # (num_arms points per ring) rather than truncating inner rings — this
    # avoids structured-grid aliasing in DFT-based MTF calculations.
    for ring in range(num_rings + 1):
        r = ring / num_rings
        n_pts = num_arms if ring > 0 else 1
        # Half-step phase offset per ring breaks radial alignment between
        # rings, further reducing aliasing in the spot DFT.
        theta_offset = (np.pi / n_pts) * (ring % 2) if ring > 0 else 0.0
        for arm in range(n_pts):
            theta = 2.0 * np.pi * arm / n_pts + theta_offset
            py = r * np.cos(theta)
            px = r * np.sin(theta)

            # Tangential aberration: trace at the actual meridional pupil coord
            result = trace_real_ray_2d(system, py * epd / 2.0, u_field, wavelength)
            if result.vignetted:
                continue

            dy = result.y_values[-1] - y_ref

            # Sagittal aberration: use radial aberration * sin(theta)
            eps_r = _get_eps(r)
            if eps_r is not None and r > 1e-6:
                dx = eps_r * np.sin(theta)
            else:
                dx = 0.0

            x_spots.append(dx)
            y_spots.append(dy)

    return np.array(x_spots), np.array(y_spots)


def trace_chief_ray(system: LensSystem, field_angle: float,
                     wavelength: float = 0.5876) -> RayTraceResult:
    """Trace a paraxial chief ray that passes through the stop center.

    For infinite conjugate systems, the chief ray enters at slope = tan(field)
    and is aimed so y=0 at the stop surface.
    """
    u_field = np.tan(np.radians(field_angle))

    # Find stop surface index
    stop_idx = 0
    for i, s in enumerate(system.surfaces):
        if s.is_stop:
            stop_idx = i
            break

    if stop_idx == 0:
        # No stop defined or stop at surface 0, just trace at y=0
        return trace_paraxial_ray(system, 0.0, u_field, wavelength)

    # Trace two rays to find the starting y that gives y=0 at the stop
    # Ray a: (y=0, u=u_field)
    ray_a = trace_paraxial_ray(system, 0.0, u_field, wavelength)
    # Ray b: (y=1, u=0)
    ray_b = trace_paraxial_ray(system, 1.0, 0.0, wavelength)

    if stop_idx < len(ray_a.y_values) and stop_idx < len(ray_b.y_values):
        y_a = ray_a.y_values[stop_idx]
        y_b = ray_b.y_values[stop_idx]
        if abs(y_b) > 1e-15:
            y_start = -y_a / y_b
            return trace_paraxial_ray(system, y_start, u_field, wavelength)

    return trace_paraxial_ray(system, 0.0, u_field, wavelength)


def compute_efl(system: LensSystem, wavelength: float = None) -> float:
    """Compute effective focal length via paraxial marginal ray."""
    if wavelength is None:
        wavelength = system.primary_wavelength()

    y0 = system.entrance_pupil_diameter / 2.0
    result = trace_paraxial_ray(system, y0, 0.0, wavelength)

    if len(result.u_values) < 2:
        return float('inf')

    u_final = result.u_values[-1]
    if abs(u_final) < 1e-15:
        return float('inf')

    return -y0 / u_final


def compute_bfl(system: LensSystem, wavelength: float = None) -> float:
    """Compute back focal length."""
    if wavelength is None:
        wavelength = system.primary_wavelength()

    y0 = system.entrance_pupil_diameter / 2.0
    result = trace_paraxial_ray(system, y0, 0.0, wavelength)

    if not result.y_values:
        return 0.0

    y_last = result.y_values[-1]
    u_last = result.u_values[-1] if result.u_values else 0.0

    if abs(u_last) < 1e-15:
        return float('inf')

    return -y_last / u_last


def compute_image_position(system: LensSystem, wavelength: float = None) -> float:
    """Compute paraxial image distance from last surface."""
    return compute_bfl(system, wavelength)
