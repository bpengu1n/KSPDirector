"""
sim/generic_vehicle.py
----------------------
Generic N-stage vehicle model backed by the parts database.

Supports arbitrary stage configurations: serial stages, parallel boosters,
mixed engine types.  Computes mass breakdowns, per-stage delta-v, and pad TWR
from database lookups.

Usage::

    from sim.parts_db import PartsDatabase
    from sim.generic_vehicle import GenericVehicle, StageDefinition

    db = PartsDatabase.load_default()
    v = GenericVehicle(
        name="My Rocket",
        stages=[
            StageDefinition(name="Core", engine_key="swivel", tank_key="flt800"),
            StageDefinition(name="Upper", engine_key="terrier", tank_key="flt400"),
        ],
        payload_keys=["mk1_pod", "mk16_chute", "heat_shield"],
    )
    print(f"Liftoff: {v.liftoff_mass(db):.2f}t, TWR: {v.pad_twr_asl(db):.2f}")
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from .constants import G0
from .parts_db import PartsDatabase


@dataclass
class StageDefinition:
    """One stage of a generic vehicle.

    For solid rocket boosters, ``tank_key`` is ``None`` — propellant mass
    comes from the engine's ``prop_mass_t``.  For liquid engines, ``tank_key``
    names the propellant tank.

    Parallel stages (``parallel=True``) fire simultaneously with the first
    sequential (non-parallel) stage.  When they burn out they separate without
    advancing the staging sequence.
    """
    name: str
    engine_key: str
    engine_count: int = 1
    throttle_pct: float = 100.0
    tank_key: Optional[str] = None
    tank_count: int = 1
    parallel: bool = False
    jettison_keys: list[str] = field(default_factory=list)
    passive_keys: list[str] = field(default_factory=list)
    extra_mass_t: float = 0.0


@dataclass
class GenericVehicle:
    """An N-stage vehicle assembled from database parts."""
    name: str
    stages: list[StageDefinition]
    payload_keys: list[str] = field(default_factory=list)
    cd: float = 0.22
    area_base: float = 1.80

    # --- Mass properties ---

    def payload_mass(self, db: PartsDatabase) -> float:
        return sum(db.get_part(k).mass_t for k in self.payload_keys)

    def stage_dry_mass(self, idx: int, db: PartsDatabase) -> float:
        stage = self.stages[idx]
        engine = db.get_engine(stage.engine_key)

        if engine.engine_type == "solid":
            engine_dry = (engine.mass_dry_t or 0.0) * stage.engine_count
        else:
            engine_dry = engine.mass_t * stage.engine_count

        tank_dry = 0.0
        if stage.tank_key is not None:
            tank = db.get_tank(stage.tank_key)
            tank_dry = tank.mass_dry_t * stage.tank_count

        jettison = sum(db.get_part(k).mass_t for k in stage.jettison_keys)
        passive = sum(db.get_part(k).mass_t for k in stage.passive_keys)

        return engine_dry + tank_dry + jettison + passive + stage.extra_mass_t

    def stage_prop_mass(self, idx: int, db: PartsDatabase) -> float:
        stage = self.stages[idx]
        engine = db.get_engine(stage.engine_key)

        if engine.engine_type == "solid":
            return (engine.prop_mass_t or 0.0) * stage.engine_count
        if stage.tank_key is not None:
            tank = db.get_tank(stage.tank_key)
            return tank.prop_mass_t * stage.tank_count
        return 0.0

    def stage_wet_mass(self, idx: int, db: PartsDatabase) -> float:
        return self.stage_dry_mass(idx, db) + self.stage_prop_mass(idx, db)

    def liftoff_mass(self, db: PartsDatabase) -> float:
        total = self.payload_mass(db)
        for i in range(len(self.stages)):
            total += self.stage_wet_mass(i, db)
        return total

    # --- Performance ---

    def stage_dv_vac(self, idx: int, db: PartsDatabase) -> float:
        stage = self.stages[idx]
        engine = db.get_engine(stage.engine_key)
        prop = self.stage_prop_mass(idx, db)
        if prop <= 0:
            return 0.0

        mass_above = self.payload_mass(db)
        for j in range(idx + 1, len(self.stages)):
            mass_above += self.stage_wet_mass(j, db)

        m0 = mass_above + self.stage_wet_mass(idx, db)
        m1 = mass_above + self.stage_dry_mass(idx, db)
        if m1 <= 0:
            return 0.0
        return G0 * engine.isp_vac * math.log(m0 / m1)

    def total_dv_vac(self, db: PartsDatabase) -> float:
        return sum(self.stage_dv_vac(i, db) for i in range(len(self.stages)))

    def pad_twr_asl(self, db: PartsDatabase) -> float:
        thrust_kn = 0.0
        for i, stage in enumerate(self.stages):
            engine = db.get_engine(stage.engine_key)
            thrust_kn += (engine.thrust_asl_kn * stage.engine_count
                          * (stage.throttle_pct / 100.0))
            if not stage.parallel:
                break
        weight_kn = self.liftoff_mass(db) * G0
        if weight_kn <= 0:
            return 0.0
        return thrust_kn / weight_kn

    # --- Factory ---

    @classmethod
    def from_perseus1(cls, cfg=None) -> GenericVehicle:
        if cfg is None:
            from .vehicle import VehicleConfig
            cfg = VehicleConfig()

        stages = []

        if cfg.n_boosters > 0:
            stages.append(StageDefinition(
                name="Boosters",
                engine_key=cfg.booster_type,
                engine_count=cfg.n_boosters,
                throttle_pct=cfg.booster_pct,
                parallel=True,
                jettison_keys=(
                    ["tt38k_decoupler"] * cfg.n_boosters
                    + ["aero_nosecone"] * cfg.n_boosters
                ),
            ))

        stages.append(StageDefinition(
            name="Core",
            engine_key="swivel",
            engine_count=1,
            throttle_pct=100.0,
            tank_key="flt800",
            tank_count=1,
            jettison_keys=["tr18a_decoupler"],
            passive_keys=["basic_fin"] * 4,
            extra_mass_t=cfg.extra_payload,
        ))

        stages.append(StageDefinition(
            name="Upper",
            engine_key="terrier",
            engine_count=1,
            throttle_pct=100.0,
            tank_key="flt800",
            tank_count=1,
            jettison_keys=["tr18a_decoupler"],
        ))

        return cls(
            name=f"Perseus 1 ({cfg.n_boosters}x {cfg.booster_type} @{cfg.booster_pct:.0f}%)",
            stages=stages,
            payload_keys=[
                "mk1_pod", "mk16_chute", "heat_shield",
                "service_bay", "reaction_wheel", "battery",
            ],
            cd=cfg.cd,
            area_base=cfg.area_base,
        )

    # --- Serialization ---

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "stages": [
                {
                    "name": s.name,
                    "engine_key": s.engine_key,
                    "engine_count": s.engine_count,
                    "throttle_pct": s.throttle_pct,
                    "tank_key": s.tank_key,
                    "tank_count": s.tank_count,
                    "parallel": s.parallel,
                    "jettison_keys": list(s.jettison_keys),
                    "passive_keys": list(s.passive_keys),
                    "extra_mass_t": s.extra_mass_t,
                }
                for s in self.stages
            ],
            "payload_keys": list(self.payload_keys),
            "cd": self.cd,
            "area_base": self.area_base,
        }

    @classmethod
    def from_dict(cls, d: dict) -> GenericVehicle:
        stages = []
        for sd in d.get("stages", []):
            stages.append(StageDefinition(
                name=sd["name"],
                engine_key=sd["engine_key"],
                engine_count=sd.get("engine_count", 1),
                throttle_pct=sd.get("throttle_pct", 100.0),
                tank_key=sd.get("tank_key"),
                tank_count=sd.get("tank_count", 1),
                parallel=sd.get("parallel", False),
                jettison_keys=sd.get("jettison_keys", []),
                passive_keys=sd.get("passive_keys", []),
                extra_mass_t=sd.get("extra_mass_t", 0.0),
            ))
        return cls(
            name=d.get("name", "Unnamed"),
            stages=stages,
            payload_keys=d.get("payload_keys", []),
            cd=d.get("cd", 0.22),
            area_base=d.get("area_base", 1.80),
        )

    # --- Validation ---

    def validate(self, db: PartsDatabase) -> list[str]:
        errors = []
        if not self.stages:
            errors.append("Vehicle must have at least one stage")
            return errors

        for key in self.payload_keys:
            try:
                db.get_part(key)
            except KeyError:
                errors.append(f"Payload part not found: {key!r}")

        for i, stage in enumerate(self.stages):
            prefix = f"Stage {i} ({stage.name})"
            try:
                db.get_engine(stage.engine_key)
            except KeyError:
                errors.append(f"{prefix}: engine not found: {stage.engine_key!r}")

            if stage.tank_key is not None:
                try:
                    db.get_tank(stage.tank_key)
                except KeyError:
                    errors.append(f"{prefix}: tank not found: {stage.tank_key!r}")

            if stage.engine_count < 1:
                errors.append(f"{prefix}: engine_count must be >= 1")
            if stage.tank_count < 1 and stage.tank_key is not None:
                errors.append(f"{prefix}: tank_count must be >= 1")
            if not (1.0 <= stage.throttle_pct <= 100.0):
                errors.append(
                    f"{prefix}: throttle_pct must be 1-100, got {stage.throttle_pct}"
                )

            for key in stage.jettison_keys:
                try:
                    db.get_part(key)
                except KeyError:
                    errors.append(f"{prefix}: jettison part not found: {key!r}")

            for key in stage.passive_keys:
                try:
                    db.get_part(key)
                except KeyError:
                    errors.append(f"{prefix}: passive part not found: {key!r}")

        return errors
