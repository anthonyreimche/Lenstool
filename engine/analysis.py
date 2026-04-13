"""Optical analysis functions: spot diagrams, MTF, ray fans, Seidel aberrations."""

import numpy as np
from typing import Tuple, List, Dict
from .surface import LensSystem
from .raytrace import (trace_real_ray_2d, trace_paraxial_ray, compute_efl,
                        trace_spot_diagram, trace_ray_fan, trace_chief_ray)
from .materials import refractive_index


def spot_diagram(system: LensSystem, field_angle: float = 0.0,
                  wavelength: float = None, num_rings: int = 8,
                  num_arms: int = 18) -> Tuple[np.ndarray, np.ndarray]:
    """Generate spot diagram data for a given field and wavelength."""
    if wavelength is None:
        wavelength = system.primary_wavelength()
    return trace_spot_diagram(system, field_angle, wavelength, num_rings, num_arms)


def spot_diagram_multi_wave(system: LensSystem, field_angle: float = 0.0,
                             num_rings: int = 8, num_arms: int = 18) -> Dict:
    """Generate spot diagrams for all wavelengths."""
    results = {}
    for wl in system.wavelengths:
        x, y = spot_diagram(system, field_angle, wl, num_rings, num_arms)
        results[wl] = (x, y)
    return results


def ray_fan(system: LensSystem, field_angle: float = 0.0,
            wavelength: float = None, num_rays: int = 51) -> Tuple[np.ndarray, np.ndarray]:
    """Compute transverse ray aberration fan."""
    if wavelength is None:
        wavelength = system.primary_wavelength()

    result = trace_ray_fan(system, field_angle, wavelength, num_rays)
    return result.pupil_coords, result.y_aberration


def ray_fan_multi_wave(system: LensSystem, field_angle: float = 0.0,
                        num_rays: int = 51) -> Dict:
    """Ray fan for all wavelengths."""
    results = {}
    for wl in system.wavelengths:
        py, ey = ray_fan(system, field_angle, wl, num_rays)
        results[wl] = (py, ey)
    return results


def geometric_mtf(system: LensSystem, field_angle: float = 0.0,
                   wavelength: float = None,
                   max_frequency: float = 200.0,
                   num_freq: int = 100,
                   num_rings: int = 24, num_arms: int = 48) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute geometric (ray-based) MTF via spot diagram DFT.

    Returns: (frequencies, tangential_mtf, sagittal_mtf)
    """
    if wavelength is None:
        wavelength = system.primary_wavelength()

    x_spots, y_spots = spot_diagram(system, field_angle, wavelength, num_rings, num_arms)

    if len(x_spots) < 3:
        freqs = np.linspace(0, max_frequency, num_freq)
        return freqs, np.ones(num_freq), np.ones(num_freq)

    # Center spots so the LSF is centered on zero.
    y_centered = y_spots - np.mean(y_spots)
    x_centered = x_spots - np.mean(x_spots)

    frequencies = np.linspace(0, max_frequency, num_freq)

    def _mtf_from_samples(samples):
        """Build a kernel-smoothed LSF from spot samples and FFT it.

        Pure histogramming is noisy when spot count is small. We approximate
        a kernel-density LSF by binning into a fine grid then convolving with
        a Gaussian whose width is set to the average inter-sample spacing.
        """
        if len(samples) < 3:
            return np.ones_like(frequencies)
        std = np.std(samples)
        if std < 1e-8:
            return np.ones_like(frequencies)

        n = len(samples)
        # Inter-sample spacing in the LSF (Silverman's rule, simplified).
        h = 1.06 * std / (n ** 0.2)

        half_width = max(6.0 * std, np.max(np.abs(samples))) * 1.2
        n_bins = 2048
        bin_width = 2.0 * half_width / n_bins

        hist, _ = np.histogram(samples, bins=n_bins,
                               range=(-half_width, half_width))
        lsf = hist.astype(float)
        if lsf.sum() < 1e-12:
            return np.ones_like(frequencies)
        lsf /= lsf.sum()

        # Convolve LSF with Gaussian kernel of width h (samples → density).
        sigma_bins = h / bin_width
        if sigma_bins > 0.5:
            radius = int(np.ceil(4.0 * sigma_bins))
            kx = np.arange(-radius, radius + 1)
            kernel = np.exp(-0.5 * (kx / sigma_bins) ** 2)
            kernel /= kernel.sum()
            lsf = np.convolve(lsf, kernel, mode='same')

        spectrum = np.abs(np.fft.fft(lsf))
        bin_freqs = np.fft.fftfreq(n_bins, d=bin_width)
        mask = bin_freqs >= 0
        bf = bin_freqs[mask]
        sp = spectrum[mask]
        order = np.argsort(bf)
        bf = bf[order]
        sp = sp[order]
        if sp[0] > 0:
            sp /= sp[0]
        return np.interp(frequencies, bf, sp, left=1.0, right=0.0)

    tang_mtf = _mtf_from_samples(y_centered)
    sag_mtf = _mtf_from_samples(x_centered)

    # Final 5-point boxcar smoothing to clean residual noise-floor ripple
    # in severely aberrated cases. The kernel is small enough not to alter
    # well-resolved MTF curves visibly.
    def _smooth5(arr):
        if len(arr) < 5:
            return arr
        kern = np.array([0.1, 0.2, 0.4, 0.2, 0.1])
        padded = np.concatenate([[arr[0]] * 2, arr, [arr[-1]] * 2])
        return np.convolve(padded, kern, mode='valid')

    tang_mtf = _smooth5(tang_mtf)
    sag_mtf = _smooth5(sag_mtf)
    tang_mtf = np.clip(tang_mtf, 0.0, 1.0)
    sag_mtf = np.clip(sag_mtf, 0.0, 1.0)

    # Normalize
    if tang_mtf[0] > 0:
        tang_mtf /= tang_mtf[0]
    if sag_mtf[0] > 0:
        sag_mtf /= sag_mtf[0]

    return frequencies, tang_mtf, sag_mtf


def diffraction_limit_mtf(system: LensSystem, wavelength: float = None,
                            num_freq: int = 100, max_frequency: float = 200.0) -> Tuple[np.ndarray, np.ndarray]:
    """Compute diffraction-limited MTF cutoff."""
    if wavelength is None:
        wavelength = system.primary_wavelength()

    efl = compute_efl(system, wavelength)
    if abs(efl) < 1e-6:
        efl = 100.0

    f_number = efl / system.entrance_pupil_diameter if system.entrance_pupil_diameter > 0 else 10.0
    cutoff = 1.0 / (wavelength * 1e-3 * f_number)  # cycles/mm

    frequencies = np.linspace(0, max_frequency, num_freq)
    mtf = np.zeros(num_freq)

    for i, f in enumerate(frequencies):
        if f >= cutoff:
            mtf[i] = 0.0
        else:
            v = f / cutoff
            mtf[i] = (2.0 / np.pi) * (np.arccos(v) - v * np.sqrt(1.0 - v * v))

    return frequencies, mtf


def field_curvature(system: LensSystem, wavelength: float = None,
                     num_fields: int = 21) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute field curvature (tangential and sagittal).

    Returns: (field_angles, tangential_focus, sagittal_focus)
    """
    if wavelength is None:
        wavelength = system.primary_wavelength()

    max_field = max(abs(f) for f in system.fields) if system.fields else 0.0
    if max_field == 0:
        max_field = 10.0

    field_angles = np.linspace(0, max_field, num_fields)
    t_focus = np.full(num_fields, np.nan)
    s_focus = np.full(num_fields, np.nan)

    import math
    epd = system.entrance_pupil_diameter

    def _focus_at_zone(u_field, zone):
        """Find longitudinal crossing of paired rays at +/- zone*EPD/2."""
        y_p = zone * epd / 2.0
        r_p = trace_real_ray_2d(system, y_p, u_field, wavelength)
        r_n = trace_real_ray_2d(system, -y_p, u_field, wavelength)
        if r_p.vignetted or r_n.vignetted:
            return None
        y_a = r_p.y_values[-1]
        y_b = r_n.y_values[-1]
        u_a = r_p.u_values[-1]
        u_b = r_n.u_values[-1]
        sl_a = math.tan(u_a) if abs(u_a) < 1.5 else 0.0
        sl_b = math.tan(u_b) if abs(u_b) < 1.5 else 0.0
        d = sl_a - sl_b
        if abs(d) < 1e-12:
            return None
        return (y_b - y_a) / d

    for i, fa in enumerate(field_angles):
        u_field = np.tan(np.radians(fa))

        # Tangential focus: full marginal pair, falling back to smaller zones
        # if vignetting cuts off the upper/lower marginal at this field.
        for zone in (1.0, 0.85, 0.7, 0.5):
            dz = _focus_at_zone(u_field, zone)
            if dz is not None:
                t_focus[i] = dz
                break

        # Sagittal focus: in this 2D meridional tracer we approximate
        # using a 0.7-zone marginal pair.
        for zone in (0.7, 0.5, 0.3):
            dz_s = _focus_at_zone(u_field, zone)
            if dz_s is not None:
                s_focus[i] = dz_s
                break

    return field_angles, t_focus, s_focus


def distortion(system: LensSystem, wavelength: float = None,
               num_fields: int = 21) -> Tuple[np.ndarray, np.ndarray]:
    """Compute distortion as percentage vs field angle."""
    if wavelength is None:
        wavelength = system.primary_wavelength()

    efl = compute_efl(system, wavelength)
    max_field = max(abs(f) for f in system.fields) if system.fields else 0.0
    if max_field == 0:
        max_field = 10.0

    field_angles = np.linspace(0, max_field, num_fields)
    dist_pct = np.full(num_fields, np.nan)
    dist_pct[0] = 0.0  # 0% distortion on-axis by definition

    from .raytrace import trace_chief_ray as _para_chief

    for i, fa in enumerate(field_angles):
        if fa < 1e-6:
            continue
        u_field = np.tan(np.radians(fa))
        # Prefer the paraxial-chief starting height (passes through stop center).
        # For systems with a rear stop, that y can be far outside the front
        # element — fall back to y=0 at OBJ if the real ray vignettes.
        para = _para_chief(system, fa, wavelength)
        y_obj_chief = para.y_values[0]
        result = trace_real_ray_2d(system, y_obj_chief, u_field, wavelength)
        if result.vignetted:
            result = trace_real_ray_2d(system, 0.0, u_field, wavelength)
        if not result.vignetted:
            y_actual = result.y_values[-1]
            y_ideal = abs(efl) * np.tan(np.radians(fa))
            if abs(y_ideal) > 1e-10:
                dist_pct[i] = 100.0 * (y_actual - y_ideal) / y_ideal

    return field_angles, dist_pct


def seidel_aberrations(system: LensSystem, wavelength: float = None) -> Dict:
    """Compute third-order (Seidel) aberration coefficients.

    Uses the Welford/Hopkins formulation:
        S_I   = Σ A² y Δ(u/n)           (Spherical)
        S_II  = Σ A Ā y Δ(u/n)          (Coma)
        S_III = Σ Ā² y Δ(u/n)           (Astigmatism)
        S_IV  = Σ H² c (1/n' - 1/n)     (Petzval)
        S_V   = Σ (Ā/A) Ā² y Δ(u/n)    (Distortion, approx)

    where A = n(u + yc), Δ(u/n) = u'/n' - u/n, H = Lagrange invariant.
    """
    if wavelength is None:
        wavelength = system.primary_wavelength()

    epd = system.entrance_pupil_diameter
    y_m0 = epd / 2.0

    max_field = max(abs(f) for f in system.fields) if system.fields else 0.0
    u_c0 = np.tan(np.radians(max_field))

    marginal = trace_paraxial_ray(system, y_m0, 0.0, wavelength)
    chief = trace_chief_ray(system, max_field, wavelength)

    # Lagrange invariant H = n * (u_m * y_c - u_c * y_m), constant through system
    # Compute at surface 1 (first real surface)
    H = 0.0
    if len(marginal.y_values) > 1 and len(chief.y_values) > 1:
        n1 = _get_n_after(system, 0, wavelength)  # index after OBJ surface
        # Use values at surface 1 (after refraction at OBJ = after transfer from OBJ)
        H = n1 * (marginal.u_values[1] * chief.y_values[1] -
                   chief.u_values[1] * marginal.y_values[1])

    S1 = 0.0  # Spherical
    S2 = 0.0  # Coma
    S3 = 0.0  # Astigmatism
    S4 = 0.0  # Petzval
    S5 = 0.0  # Distortion

    n_surfs = len(system.surfaces)
    for i in range(n_surfs - 1):
        surf = system.surfaces[i]
        c = surf.curvature

        n = _get_n_before(system, i, wavelength)
        n_prime = _get_n_after(system, i, wavelength)

        if abs(n_prime - n) < 1e-12:
            continue  # air-air or same medium

        if i >= len(marginal.y_values) - 1 or i >= len(chief.y_values) - 1:
            continue

        # Ray data at surface i (before refraction)
        y_m = marginal.y_values[i]
        u_m = marginal.u_values[i]     # slope arriving at i
        u_m_prime = marginal.u_values[i + 1]  # slope after refraction at i

        y_c = chief.y_values[i]
        u_c = chief.u_values[i]
        u_c_prime = chief.u_values[i + 1]

        # Δ(u/n) for marginal ray at this surface
        delta_un = u_m_prime / n_prime - u_m / n

        if abs(delta_un) < 1e-18 and abs(c) < 1e-18:
            continue

        # Abbe invariants (paraxial angle of incidence * n)
        A = n * (u_m + y_m * c)
        A_bar = n * (u_c + y_c * c)

        # Seidel contributions
        S1 += A * A * y_m * delta_un
        S2 += A * A_bar * y_m * delta_un
        S3 += A_bar * A_bar * y_m * delta_un
        S4 += H * H * c * (1.0 / n_prime - 1.0 / n)
        if abs(A) > 1e-12:
            S5 += (A_bar / A) * A_bar * A_bar * y_m * delta_un

    return {
        "S1_spherical": S1,
        "S2_coma": S2,
        "S3_astigmatism": S3,
        "S4_petzval": S4,
        "S5_distortion": S5,
    }


def _get_n_before(system, idx, wavelength):
    if idx == 0:
        return 1.0
    mat = system.surfaces[idx - 1].material
    return refractive_index(mat, wavelength)


def _get_n_after(system, idx, wavelength):
    mat = system.surfaces[idx].material
    return refractive_index(mat, wavelength)


def rms_spot_size(system: LensSystem, field_angle: float = 0.0,
                   wavelength: float = None) -> float:
    """Compute RMS spot radius."""
    if wavelength is None:
        wavelength = system.primary_wavelength()

    x, y = spot_diagram(system, field_angle, wavelength)
    if len(x) < 2:
        return 0.0

    x_mean = np.nanmean(x)
    y_mean = np.nanmean(y)
    r2 = (x - x_mean) ** 2 + (y - y_mean) ** 2
    return np.sqrt(np.nanmean(r2))


def system_summary(system: LensSystem) -> Dict:
    """Compute summary of system properties."""
    wl = system.primary_wavelength()
    efl = compute_efl(system, wl)

    epd = system.entrance_pupil_diameter
    fno = abs(efl / epd) if epd > 0 else float('inf')
    na = np.sin(np.arctan(epd / (2.0 * efl))) if abs(efl) > 1e-6 else 0.0

    total_track = system.total_track()

    return {
        "title": system.title,
        "efl": efl,
        "fno": fno,
        "na": na,
        "epd": epd,
        "total_track": total_track,
        "num_surfaces": system.num_surfaces,
        "num_elements": sum(1 for s in system.surfaces if s.material and s.material.upper() not in ("", "AIR", "MIRROR")) // 1,
        "wavelengths": system.wavelengths,
        "fields": system.fields,
    }
