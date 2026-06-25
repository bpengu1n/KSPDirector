"""Shared pytest fixtures for the Perseus 1 regression test suite."""

import os
import pytest

from sim.vehicle import VehicleConfig


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def project_root():
    """Return the project root directory path."""
    return ROOT


@pytest.fixture
def vehicle_config():
    """Return a fresh default VehicleConfig instance."""
    return VehicleConfig()


@pytest.fixture
def terrier_ignition_state():
    """Factory fixture: build a telemetry state for just after Terrier ignition.

    Returns a callable that accepts lf_units and optional overrides.
    """
    def _build(lf_units, **overrides):
        state = {
            "altitude":     15_000.0,
            "velocity":     631.0,
            "v_vert":       408.0,
            "v_horiz":      481.0,
            "apoapsis":     25_000.0,
            "periapsis":   -587_000.0,
            "pitch":        50.0,
            "heading":      90.0,
            "roll":          0.0,
            "mission_time": 63.0,
            "throttle":      1.0,
            "liquid_fuel":  float(lf_units),
            "solid_fuel":    0.0,
            "atm_density":   0.002,
        }
        state.update(overrides)
        return state
    return _build


@pytest.fixture
def telemetry_state():
    """Factory fixture: build a minimal telemetry state dict for testing.

    Accepts keyword overrides for any field.
    """
    def _build(alt=15000, apo=25000, pe=-587000, met=63, sf=0, lf=360,
               throttle=1.0, pitch=50.0, vel=631, **extra):
        state = {
            "altitude": float(alt),
            "apoapsis": float(apo),
            "periapsis": float(pe),
            "mission_time": float(met),
            "solid_fuel": float(sf),
            "liquid_fuel": float(lf),
            "throttle": float(throttle),
            "pitch": float(pitch),
            "velocity": float(vel),
            "v_horiz": 481.0,
            "v_vert": 408.0,
        }
        state.update(extra)
        return state
    return _build
