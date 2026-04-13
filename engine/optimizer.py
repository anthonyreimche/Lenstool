"""Lens optimization engine using damped least squares (DLS)."""

import numpy as np
from typing import List, Tuple, Callable, Optional
from dataclasses import dataclass, field
from .surface import LensSystem, SolveType
from .raytrace import trace_real_ray_2d, trace_paraxial_ray, compute_efl
from .analysis import rms_spot_size


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


class Optimizer:
    """Damped least squares optimizer for lens systems."""

    def __init__(self, system: LensSystem):
        self.system = system
        self.variables: List[Variable] = []
        self.operands: List[Operand] = []
        self.damping = 0.1

    def add_variable(self, surface_idx: int, parameter: str,
                     min_val: float = -1e10, max_val: float = 1e10):
        self.variables.append(Variable(surface_idx, parameter, min_val, max_val))

    def remove_variable(self, index: int):
        if 0 <= index < len(self.variables):
            self.variables.pop(index)

    def add_operand(self, op_type: str, target: float = 0.0, weight: float = 1.0,
                    surface: int = -1, field_idx: int = 0, wave_idx: int = 0):
        self.operands.append(Operand(op_type, target, weight, surface, field_idx, wave_idx))

    def clear_operands(self):
        self.operands.clear()

    def clear_variables(self):
        self.variables.clear()

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

    def optimize(self, max_iterations: int = 50, tolerance: float = 1e-8,
                  callback: Optional[Callable] = None) -> OptimizationResult:
        """Run damped least squares optimization."""
        result = OptimizationResult()

        if not self.variables or not self.operands:
            result.message = "No variables or operands defined"
            return result

        n_vars = len(self.variables)
        n_ops = len(self.operands)

        result.initial_merit = self.evaluate_merit()
        damping = self.damping

        for iteration in range(max_iterations):
            # Get current parameter vector
            x = np.array([v.get_value(self.system) for v in self.variables])

            # Compute residuals
            r = self._compute_residuals()
            merit = np.sqrt(np.mean(r ** 2))

            if callback:
                callback(iteration, merit)

            # Compute Jacobian by finite differences
            J = np.zeros((n_ops, n_vars))
            delta = 1e-6

            for j in range(n_vars):
                x_save = self.variables[j].get_value(self.system)

                # Forward perturbation
                step = max(abs(x_save) * delta, delta)
                self.variables[j].set_value(self.system, x_save + step)
                r_plus = self._compute_residuals()

                # Restore
                self.variables[j].set_value(self.system, x_save)

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
                for j, var in enumerate(self.variables):
                    var.set_value(self.system, x_new[j])

                new_merit = self.evaluate_merit()

                if new_merit < merit:
                    damping *= 0.5
                    damping = max(damping, 1e-10)
                    break
                else:
                    # Revert
                    for j, var in enumerate(self.variables):
                        var.set_value(self.system, x[j])
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

        result.final_merit = self.evaluate_merit()
        if not result.message:
            result.message = f"Completed {result.iterations} iterations"

        return result
