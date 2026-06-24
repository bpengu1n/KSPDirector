"""
sim/atmosphere.py
-----------------
Kerbin standard atmosphere model (exponential, stock KSP 1).

Exports:
    density(h)            -> kg/m³
    pressure_fraction(h)  -> 0.0 to 1.0 (1.0 = sea level)
    effective_isp(h, isp_vac, isp_asl) -> s
    drag_force(h, v, cda) -> N
"""

import math
from .constants import ATM_CEIL, RHO0, SCALE_H


def density(h: float) -> float:
    """Air density at altitude h (m). Returns kg/m³. Zero above ATM_CEIL."""
    if h >= ATM_CEIL:
        return 0.0
    return RHO0 * math.exp(-h / SCALE_H)


def pressure_fraction(h: float) -> float:
    """
    Atmospheric pressure as a fraction of sea-level pressure.
    Used for Isp interpolation: 1.0 = sea level, 0.0 = vacuum.
    """
    if h >= ATM_CEIL:
        return 0.0
    return math.exp(-h / SCALE_H)


def effective_isp(h: float, isp_vac: float, isp_asl: float) -> float:
    """
    Interpolate between vacuum and sea-level Isp based on local pressure.
    KSP models this linearly with pressure fraction.
    """
    pf = pressure_fraction(h)
    return isp_vac - (isp_vac - isp_asl) * pf


def drag_force(h: float, v: float, cda: float) -> float:
    """
    Aerodynamic drag force (N).
    Uses a simple quadratic drag model: F = 0.5 * rho * v² * CdA
    cda: effective drag area (Cd * A, m²)
    """
    return 0.5 * density(h) * v * v * cda
