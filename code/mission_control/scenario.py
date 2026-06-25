"""
mission_control/scenario.py
-----------------------------
Scriptable launch scenario definition for the Perseus 1 mission control.

A LaunchScenario bridges user input (JSON from the web UI or CLI) to the
sim package's VehicleConfig and pitch program selection, plus playback
options for the scripted telemetry engine.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from sim.vehicle import VehicleConfig
from sim.constants import ENGINES
from sim.trajectory import PITCH_PROGRAMS


@dataclass
class LaunchScenario:
    """Launch scenario parameters bridging UI/CLI input to the sim.

    Units: extra_payload in tonnes, cd dimensionless, area_base in m²,
    booster_pct as percentage 1-100, noise_pct as fraction 0.0-0.20,
    playback_speed as multiplier (1.0 = real-time).
    """
    name: str = "Custom Scenario"
    booster_type: str = "hammer"          # key into sim.constants.ENGINES
    n_boosters: int = 2                   # count, 0-6
    booster_pct: float = 20.0             # thrust limiter, % (1-100)
    extra_payload: float = 0.0            # tonnes
    cd: float = 0.22                      # drag coefficient, dimensionless
    area_base: float = 1.80               # cross-section, m²
    pitch_program: str = "nominal"        # key into sim.trajectory.PITCH_PROGRAMS
    playback_speed: float = 1.0           # multiplier (0.25-10.0)
    noise_pct: float = 0.02              # telemetry noise fraction (0.0-0.20)

    def to_vehicle_config(self) -> VehicleConfig:
        return VehicleConfig(
            booster_type=self.booster_type,
            n_boosters=self.n_boosters,
            booster_pct=self.booster_pct,
            extra_payload=self.extra_payload,
            cd=self.cd,
            area_base=self.area_base,
        )

    def get_pitch_program(self):
        return PITCH_PROGRAMS[self.pitch_program]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "booster_type": self.booster_type,
            "n_boosters": self.n_boosters,
            "booster_pct": self.booster_pct,
            "extra_payload": self.extra_payload,
            "cd": self.cd,
            "area_base": self.area_base,
            "pitch_program": self.pitch_program,
            "playback_speed": self.playback_speed,
            "noise_pct": self.noise_pct,
        }

    @classmethod
    def from_dict(cls, d: dict) -> LaunchScenario:
        _COERCE = {
            "name": str,
            "booster_type": str,
            "n_boosters": int,
            "booster_pct": float,
            "extra_payload": float,
            "cd": float,
            "area_base": float,
            "pitch_program": str,
            "playback_speed": float,
            "noise_pct": float,
        }
        filtered = {}
        for k, v in d.items():
            if k in _COERCE:
                try:
                    filtered[k] = _COERCE[k](v)
                except (TypeError, ValueError):
                    filtered[k] = v
        return cls(**filtered)

    def validate(self) -> list[str]:
        errors = []
        if self.booster_type not in ENGINES:
            errors.append(
                f"booster_type '{self.booster_type}' not in {list(ENGINES.keys())}"
            )
        def _check_range(name, val, lo, hi):
            try:
                if not (lo <= val <= hi):
                    errors.append(f"{name} must be {lo}-{hi}, got {val}")
            except TypeError:
                errors.append(f"{name} must be numeric, got {type(val).__name__}")
        _check_range("n_boosters", self.n_boosters, 0, 6)
        _check_range("booster_pct", self.booster_pct, 1, 100)
        if self.pitch_program not in PITCH_PROGRAMS:
            errors.append(
                f"pitch_program '{self.pitch_program}' not in {list(PITCH_PROGRAMS.keys())}"
            )
        _check_range("playback_speed", self.playback_speed, 0.25, 10.0)
        _check_range("noise_pct", self.noise_pct, 0.0, 0.20)
        _check_range("extra_payload", self.extra_payload, 0.0, 2.0)
        _check_range("cd", self.cd, 0.05, 1.0)
        _check_range("area_base", self.area_base, 0.5, 5.0)
        return errors


PRESET_SCENARIOS = {
    "nominal": LaunchScenario(name="Perseus 1 Nominal"),
    "steep_ascent": LaunchScenario(name="Steep Ascent", pitch_program="steep"),
    "shallow_ascent": LaunchScenario(name="Shallow Ascent", pitch_program="shallow"),
    "late_turn": LaunchScenario(name="Late Turn", pitch_program="late_turn"),
    "heavy_payload": LaunchScenario(name="Heavy Payload", extra_payload=0.5),
    "thumper_variant": LaunchScenario(
        name="Thumper Variant", booster_type="thumper", booster_pct=15,
    ),
    "high_twr": LaunchScenario(name="High TWR", booster_pct=45),
    "abort_steep": LaunchScenario(
        name="Abort Training (Steep)", pitch_program="steep",
        booster_pct=45, noise_pct=0.10,
    ),
}
