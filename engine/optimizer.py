"""Lens optimization engine using damped least squares (DLS)."""

import numpy as np
from typing import List, Tuple, Callable, Optional
from dataclasses import dataclass, field
from .surface import LensSystem, SolveType
from .raytrace import trace_real_ray_2d, trace_paraxial_ray, compute_efl
from .analysis import rms_spot_size
from .materials import (GLASS_CATALOG, get_glass, find_nearest_glass,
                        glass_nd_vd, available_glasses)


@dataclass
class Variable:
    """An optimization variable."""
    surface_idx: int
    parameter: str  # "radius", "thickness", "conic"
    min_val: float = -1e10
    max_val: float = 1e10

    def get_value(self, system: LensSystem) -> float:
        surf = system.surfaces[self.surface_idx]
        if self.parameter == "radius":
            return surf.radius
        elif self.parameter == "thickness":
            return surf.thickness
        elif self.parameter == "conic":
            return surf.conic
        return 0.0

    def set_value(self, system: LensSystem, value: float):
        value = np.clip(value, self.min_val, self.max_val)
        surf = system.surfaces[self.surface_idx]
        if self.parameter == "radius":
            surf.radius = value
        elif self.parameter == "thickness":
            surf.thickness = value
        elif self.parameter == "conic":
            surf.conic = value


@dataclass
class MaterialVariable:
    """A material optimization variable — represents glass as (nd, vd).

    During DLS, nd and vd are treated as two continuous variables.
    After optimization, the nearest real catalog glass is selected.
    *glass_pool* restricts the search to a subset of the catalog.
    """
    surface_idx: int
    glass_pool: List[str] = field(default_factory=list)  # empty = all catalog

    # Internal continuous representation
    _nd: float = 0.0
    _vd: float = 0.0

    def sync_from_system(self, system: LensSystem):
        """Read current glass nd/vd from the surface."""
        mat = system.surfaces[self.surface_idx].material
        self._nd, self._vd = glass_nd_vd(mat)

    def get_values(self) -> Tuple[float, float]:
        return self._nd, self._vd

    def set_values(self, nd: float, vd: float):
        self._nd = np.clip(nd, 1.3, 2.5)
        self._vd = np.clip(vd, 15.0, 95.0)

    def apply_nearest_glass(self, system: LensSystem) -> str:
        """Snap to the nearest real catalog glass and apply it."""
        pool = self.glass_pool or None
        matches = find_nearest_glass(self._nd, self._vd, pool, max_results=1)
        if matches:
            name = matches[0][0]
            system.surfaces[self.surface_idx].material = name
            # Update internal values to match the snapped glass
            g = get_glass(name)
            if g:
                self._nd, self._vd = g.nd, g.vd
            return name
        return system.surfaces[self.surface_idx].material

    def best_glass_name(self) -> str:
        """Return the name of the nearest glass without applying."""
        pool = self.glass_pool or None
        matches = find_nearest_glass(self._nd, self._vd, pool, max_results=1)
        return matches[0][0] if matches else "?"


@dataclass
class Operand:
    """An optimization target/operand."""
    type: str  # "EFFL", "SPOT", "TRAY", "AXCL", "DIMX"
    target: float = 0.0
    weight: float = 1.0
    surface: int = -1
    field_idx: int = 0
    wave_idx: int = 0


@dataclass
class OptimizationResult:
    """Result of an optimization run."""
    initial_merit: float = 0.0
    final_merit: float = 0.0
    iterations: int = 0
    converged: bool = False
    message: str = ""
    glass_changes: List[str] = field(default_factory=list)


class Optimizer:
    """Damped least squares optimizer for lens systems."""

    def __init__(self, system: LensSystem):
        self.system = system
        self.variables: List[Variable] = []
        self.material_variables: List[MaterialVariable] = []
        self.operands: List[Operand] = []
        self.damping = 0.1

    def add_variable(self, surface_idx: int, parameter: str,
                     min_val: float = -1e10, max_val: float = 1e10):
        self.variables.append(Variable(surface_idx, parameter, min_val, max_val))

    def remove_variable(self, index: int):
        if 0 <= index < len(self.variables):
            self.variables.pop(index)

    def add_material_variable(self, surface_idx: int,
                              glass_pool: List[str] = None):
        """Add a material variable for the given surface."""
        mv = MaterialVariable(surface_idx, glass_pool or [])
        mv.sync_from_system(self.system)
        self.material_variables.append(mv)

    def remove_material_variable(self, index: int):
        if 0 <= index < len(self.material_variables):
            self.material_variables.pop(index)

    def add_operand(self, op_type: str, target: float = 0.0, weight: float = 1.0,
                    surface: int = -1, field_idx: int = 0, wave_idx: int = 0):
        self.operands.append(Operand(op_type, target, weight, surface, field_idx, wave_idx))

    def clear_operands(self):
        self.operands.clear()

    def clear_variables(self):
        self.variables.clear()
        self.material_variables.clear()

    def auto_set_variables(self):
        """Automatically set all radii and thicknesses as variables."""
        self.variables.clear()
        for i, surf in enumerate(self.system.surfaces):
            if i == 0 or i == len(self.system.surfaces) - 1:
                continue
            if abs(surf.radius) < 1e10:
                self.add_variable(i, "radius")
            if surf.thickness_solve == SolveType.VARIABLE:
                self.add_variable(i, "thickness", 0.1, 200.0)

    def auto_set_operands(self):
        """Set default optimization operands (minimize spot size at all fields)."""
        self.operands.clear()
        for fi in range(len(self.system.fields)):
            self.add_operand("SPOT", 0.0, 1.0, field_idx=fi)

    def evaluate_merit(self) -> float:
        """Evaluate the merit function (RMS of weighted operands)."""
        residuals = self._compute_residuals()
        if len(residuals) == 0:
            return 0.0
        return np.sqrt(np.mean(residuals ** 2))

    def _compute_residuals(self) -> np.ndarray:
        """Compute weighted residual vector."""
        residuals = []
        for op in self.operands:
            val = self._evaluate_operand(op)
            residuals.append(op.weight * (val - op.target))
        return np.array(residuals)

    def _evaluate_operand(self, op: Operand) -> float:
        """Evaluate a single operand."""
        wl_idx = min(op.wave_idx, len(self.system.wavelengths) - 1)
        wavelength = self.system.wavelengths[wl_idx]
        field_idx = min(op.field_idx, len(self.system.fields) - 1)
        field_angle = self.system.fields[field_idx]

        if op.type == "EFFL":
            return compute_efl(self.system, wavelength)
        elif op.type == "SPOT":
            return rms_spot_size(self.system, field_angle, wavelength)
        elif op.type == "TRAY":
            # Transverse ray aberration at marginal ray
            epd = self.system.entrance_pupil_diameter
            u_field = np.tan(np.radians(field_angle))
            result = trace_real_ray_2d(self.system, epd / 2.0, u_field, wavelength)
            chief = trace_real_ray_2d(self.system, 0.0, u_field, wavelength)
            if not result.vignetted and not chief.vignetted:
                return result.y_values[-1] - chief.y_values[-1]
            return 1e3
        elif op.type == "DIMX":
            # Distance (thickness) of surface
            if 0 <= op.surface < len(self.system.surfaces):
                return self.system.surfaces[op.surface].thickness
            return 0.0
        elif op.type == "AXCL":
            # Axial chromatic (focus shift between wavelengths)
            if len(self.system.wavelengths) < 2:
                return 0.0
            efl1 = compute_efl(self.system, self.system.wavelengths[0])
            efl2 = compute_efl(self.system, self.system.wavelengths[-1])
            return efl2 - efl1
        return 0.0

    # ------------------------------------------------------------------
    # Build combined variable vector (continuous + material nd/vd)
    # ------------------------------------------------------------------

    def _get_full_vector(self) -> np.ndarray:
        """Get combined parameter vector: [continuous vars..., nd1, vd1, nd2, vd2, ...]."""
        vals = [v.get_value(self.system) for v in self.variables]
        for mv in self.material_variables:
            nd, vd = mv.get_values()
            vals.extend([nd, vd])
        return np.array(vals)

    def _set_full_vector(self, x: np.ndarray):
        """Apply combined parameter vector back to system."""
        n_cont = len(self.variables)
        for j, var in enumerate(self.variables):
            var.set_value(self.system, x[j])
        idx = n_cont
        for mv in self.material_variables:
            mv.set_values(x[idx], x[idx + 1])
            # Apply the fictional nd/vd to the system via a temporary glass
            self._apply_material_continuous(mv)
            idx += 2

    def _apply_material_continuous(self, mv: MaterialVariable):
        """During optimization, approximate the glass at (nd, vd).

        We modify the surface's material to the nearest catalog glass,
        which gives us real Sellmeier dispersion for accurate ray tracing.
        """
        mv.apply_nearest_glass(self.system)

    def _total_var_count(self) -> int:
        return len(self.variables) + 2 * len(self.material_variables)

    # ------------------------------------------------------------------
    # Optimization
    # ------------------------------------------------------------------

    def optimize(self, max_iterations: int = 50, tolerance: float = 1e-8,
                  callback: Optional[Callable] = None) -> OptimizationResult:
        """Run damped least squares optimization."""
        result = OptimizationResult()

        n_total = self._total_var_count()
        if n_total == 0 or not self.operands:
            result.message = "No variables or operands defined"
            return result

        # Sync material variables from current system state
        for mv in self.material_variables:
            mv.sync_from_system(self.system)

        n_ops = len(self.operands)

        result.initial_merit = self.evaluate_merit()
        damping = self.damping

        for iteration in range(max_iterations):
            # Get current parameter vector
            x = self._get_full_vector()

            # Compute residuals
            r = self._compute_residuals()
            merit = np.sqrt(np.mean(r ** 2))

            if callback:
                callback(iteration, merit)

            # Compute Jacobian by finite differences
            J = np.zeros((n_ops, n_total))
            delta = 1e-6

            for j in range(n_total):
                x_save = x[j]

                # Choose appropriate step size
                if j >= len(self.variables):
                    # Material variable — use larger step for nd/vd
                    step = max(abs(x_save) * 1e-4, 1e-4)
                else:
                    step = max(abs(x_save) * delta, delta)

                x_pert = x.copy()
                x_pert[j] = x_save + step
                self._set_full_vector(x_pert)
                r_plus = self._compute_residuals()

                # Restore
                self._set_full_vector(x)

                J[:, j] = (r_plus - r) / step

            # DLS update: dx = -(J^T J + lambda*I)^-1 J^T r
            JtJ = J.T @ J
            Jtr = J.T @ r

            # Damping
            diag = np.diag(JtJ).copy()
            diag[diag < 1e-12] = 1e-12

            for attempt in range(5):
                A = JtJ + damping * np.diag(diag)
                try:
                    dx = np.linalg.solve(A, -Jtr)
                except np.linalg.LinAlgError:
                    damping *= 10
                    continue

                # Apply update
                x_new = x + dx
                self._set_full_vector(x_new)

                new_merit = self.evaluate_merit()

                if new_merit < merit:
                    damping *= 0.5
                    damping = max(damping, 1e-10)
                    break
                else:
                    # Revert
                    self._set_full_vector(x)
                    damping *= 10
            else:
                result.message = "Failed to find descent direction"
                break

            # Check convergence
            if abs(merit - new_merit) < tolerance and iteration > 0:
                result.converged = True
                result.message = "Converged"
                break

            result.iterations = iteration + 1

        # Final snap: apply nearest real glasses for all material variables
        for mv in self.material_variables:
            name = mv.apply_nearest_glass(self.system)
            nd, vd = mv.get_values()
            result.glass_changes.append(
                f"Surf {mv.surface_idx}: {name} (nd={nd:.4f}, vd={vd:.1f})")

        result.final_merit = self.evaluate_merit()
        if not result.message:
            result.message = f"Completed {result.iterations} iterations"

        return result

    # ------------------------------------------------------------------
    # Glass substitution (brute-force discrete search)
    # ------------------------------------------------------------------

    def glass_substitution(self, callback: Optional[Callable] = None
                           ) -> OptimizationResult:
        """Try every glass in each material variable's pool.

        For each material variable, test all candidate glasses and keep
        the one that gives the lowest merit.  This is a discrete search
        that complements the continuous DLS optimization.
        """
        result = OptimizationResult()
        result.initial_merit = self.evaluate_merit()

        if not self.material_variables:
            result.message = "No material variables"
            return result

        total_evals = sum(
            len(mv.glass_pool) if mv.glass_pool else len(GLASS_CATALOG)
            for mv in self.material_variables)
        eval_count = 0

        for mv in self.material_variables:
            pool = mv.glass_pool if mv.glass_pool else list(GLASS_CATALOG.keys())
            pool = [n for n in pool if n.upper() != "MIRROR"]

            surf = self.system.surfaces[mv.surface_idx]
            best_glass = surf.material
            best_merit = self.evaluate_merit()

            for glass_name in pool:
                surf.material = glass_name
                try:
                    m = self.evaluate_merit()
                except Exception:
                    m = 1e10
                if m < best_merit:
                    best_merit = m
                    best_glass = glass_name

                eval_count += 1
                if callback:
                    callback(eval_count, best_merit)

            surf.material = best_glass
            mv.sync_from_system(self.system)
            g = get_glass(best_glass)
            if g:
                result.glass_changes.append(
                    f"Surf {mv.surface_idx}: {best_glass} "
                    f"(nd={g.nd:.4f}, vd={g.vd:.1f})")

        result.final_merit = self.evaluate_merit()
        result.message = f"Tested {eval_count} glass combinations"
        return result
