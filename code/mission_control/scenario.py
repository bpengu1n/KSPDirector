"""
mission_control/scenario.py
-----------------------------
Scriptable launch scenario definition for the Perseus 1 mission control.

A LaunchScenario bridges user input (JSON from the web UI or CLI) to the
sim package's VehicleConfig and pitch program selection, plus playback
options for the scripted telemetry engine.
"""

from __future__ import annotations

import sys
import os
from dataclasses import dataclass, asdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sim.vehicle import VehicleConfig
from sim.constants import ENGINES
from sim.trajectory import PITCH_PROGRAMS


@dataclass
class LaunchScenario:
    name: str = "Custom Scenario"
    booster_type: str = "hammer"
    n_boosters: int = 2
    booster_pct: float = 20.0
    extra_payload: float = 0.0
    cd: float = 0.22
    area_base: float = 1.80
    pitch_program: str = "nominal"
    playback_speed: float = 1.0
    noise_pct: float = 0.02

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
        known_fields = {
            "name", "booster_type", "n_boosters", "booster_pct",
            "extra_payload", "cd", "area_base", "pitch_program",
            "playback_speed", "noise_pct",
        }
        filtered = {k: v for k, v in d.items() if k in known_fields}
        return cls(**filtered)

    def validate(self) -> list[str]:
        errors = []
        if self.booster_type not in ENGINES:
            errors.append(
                f"booster_type '{self.booster_type}' not in {list(ENGINES.keys())}"
            )
        if not (0 <= self.n_boosters <= 6):
            errors.append(f"n_boosters must be 0-6, got {self.n_boosters}")
        if not (1 <= self.booster_pct <= 100):
            errors.append(f"booster_pct must be 1-100, got {self.booster_pct}")
        if self.pitch_program not in PITCH_PROGRAMS:
            errors.append(
                f"pitch_program '{self.pitch_program}' not in {list(PITCH_PROGRAMS.keys())}"
            )
        if not (0.25 <= self.playback_speed <= 10.0):
            errors.append(f"playback_speed must be 0.25-10.0, got {self.playback_speed}")
        if not (0.0 <= self.noise_pct <= 0.20):
            errors.append(f"noise_pct must be 0.0-0.20, got {self.noise_pct}")
        if not (0.0 <= self.extra_payload <= 2.0):
            errors.append(f"extra_payload must be 0.0-2.0, got {self.extra_payload}")
        if not (0.05 <= self.cd <= 1.0):
            errors.append(f"cd must be 0.05-1.0, got {self.cd}")
        if not (0.5 <= self.area_base <= 5.0):
            errors.append(f"area_base must be 0.5-5.0, got {self.area_base}")
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
}
