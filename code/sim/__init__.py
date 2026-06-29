"""
sim — Perseus 1 Ascent Simulation Package
==========================================

Quick start::

    from sim import run_ascent, VehicleConfig, PITCH_PROGRAMS

    # Baseline run (20% Hammer, nominal pitch program)
    result = run_ascent()
    print(f"Apoapsis:  {result.apoapsis_km:.1f} km")
    print(f"Periapsis: {result.periapsis_km:.0f} km")

    # Custom vehicle
    cfg = VehicleConfig(booster_pct=25, extra_payload=0.15)
    result = run_ascent(cfg, pitch_program=PITCH_PROGRAMS['shallow'])

    # Iterate over trajectory points (t, altitude_km, downrange_km, ...)
    for pt in result.points:
        print(pt.t, pt.altitude / 1000, pt.downrange / 1000)

Modules
-------
constants   Kerbin physics, verified KSP part stats, Perseus 1 default config
atmosphere  Exponential atmosphere model (density, pressure, drag)
vehicle     Mass accounting, pad TWR, delta-v calculations
trajectory  Numerical integrator (Euler, dt=0.02s), pitch programs
ascent_sim  High-level run_ascent() API + CLI entry point
"""

from .ascent_sim import run_ascent, run_generic, result_to_dict, compare_programs
from .vehicle import VehicleConfig
from .trajectory import PITCH_PROGRAMS, TrajectoryResult, TrajectoryPoint
from .parts_db import PartsDatabase, Engine, FuelTank, StructuralPart
from .generic_vehicle import GenericVehicle, StageDefinition

__all__ = [
    "run_ascent",
    "run_generic",
    "result_to_dict",
    "compare_programs",
    "VehicleConfig",
    "PITCH_PROGRAMS",
    "TrajectoryResult",
    "TrajectoryPoint",
    "PartsDatabase",
    "Engine",
    "FuelTank",
    "StructuralPart",
    "GenericVehicle",
    "StageDefinition",
]
