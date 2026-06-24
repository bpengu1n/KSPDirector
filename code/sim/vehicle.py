"""
sim/vehicle.py
--------------
Vehicle mass accounting and engine performance calculations for Perseus 1
and variants. Computes mass breakdowns, effective drag area, pad TWR,
and mission-stage delta-v.

Usage::

    from sim.vehicle import VehicleConfig
    cfg = VehicleConfig(booster_pct=20)
    print(cfg.liftoff_mass_t)
    print(cfg.pad_twr_asl)
    print(cfg.mission_stage_dv_ms)
"""

import math
from dataclasses import dataclass, field

from .constants import G0, ENGINES, TANKS, PARTS, PERSEUS_1_DEFAULT


# ---------------------------------------------------------------------------
# Engine helpers
# ---------------------------------------------------------------------------

def engine_mdot_full(engine_key: str) -> float:
    """Mass flow rate (kg/s) at 100% throttle in vacuum."""
    e = ENGINES[engine_key]
    return e["thrust_vac"] * 1000 / (e["isp_vac"] * G0)


def engine_thrust_at(h: float, engine_key: str, throttle: float,
                     atmosphere_module=None) -> tuple[float, float]:
    """
    Returns (thrust_kN, mdot_kg_s) for a given engine at altitude h and throttle.

    KSP interpolates thrust (and Isp) linearly with atmospheric pressure fraction.
    thrust_kN is in kN; mdot is in kg/s.
    The caller must convert thrust to N for force calculations (* 1000).
    """
    if atmosphere_module is None:
        from . import atmosphere as atm
        atmosphere_module = atm
    e = ENGINES[engine_key]
    pf = atmosphere_module.pressure_fraction(h)
    # Interpolate thrust directly (matches KSP engine card values)
    thrust_100pct_kN = e["thrust_vac"] - (e["thrust_vac"] - e["thrust_asl"]) * pf
    thrust_kN = thrust_100pct_kN * throttle
    # mdot from interpolated Isp
    isp = atmosphere_module.effective_isp(h, e["isp_vac"], e["isp_asl"])
    mdot = thrust_kN * 1000 / (isp * G0)   # kg/s
    return thrust_kN, mdot


# ---------------------------------------------------------------------------
# VehicleConfig
# ---------------------------------------------------------------------------

@dataclass
class VehicleConfig:
    """
    Fully describes a Perseus 1 vehicle variant.
    Default values match the current flight plan (2x Hammer @ 20%, 1x service bay).

    All masses in tonnes, thrusts in kN, Isp in seconds.
    """

    # Fix P3-10: defaults sourced from PERSEUS_1_DEFAULT — single authoritative source
    booster_type:    str   = PERSEUS_1_DEFAULT["booster_type"]
    n_boosters:      int   = PERSEUS_1_DEFAULT["n_boosters"]
    booster_pct:     float = PERSEUS_1_DEFAULT["booster_pct"]

    # --- Extra inert payload on the core stage (below upper decoupler).
    # Fix P0-05: was 0.10t (the service bay) but the service bay is now
    # correctly modelled in avionics_mass / mission_stage_dry. Defaulting
    # to 0.10 caused the bay to be counted twice in liftoff_mass_t.
    # Set to 0.0 — use a non-zero value only for genuine extra core-stage mass.
    extra_payload:   float = 0.0            # t

    # Drag model (from PERSEUS_1_DEFAULT)
    cd:              float = PERSEUS_1_DEFAULT["cd"]
    area_base:       float = PERSEUS_1_DEFAULT["area_base"]

    # Fix P3-05: private derived fields use init=False to communicate they
    # are computed in __post_init__, not user-supplied at construction time.
    _booster: dict  = field(init=False, default=None, repr=False)
    _cda:     float = field(init=False, default=0.0,  repr=False)

    def __post_init__(self):
        self._booster = ENGINES[self.booster_type]
        extra_boosters = max(0, self.n_boosters - 2)
        area_extra = extra_boosters * 0.35
        self._cda = self.cd * (self.area_base + area_extra)

    # -----------------------------------------------------------------------
    # Mass breakdown
    # -----------------------------------------------------------------------

    @property
    def capsule_mass(self) -> float:
        return PARTS["mk1_pod"] + PARTS["mk16_chute"] + PARTS["heat_shield"]

    @property
    def avionics_mass(self) -> float:
        return PARTS["reaction_wheel"] + PARTS["battery"] + PARTS.get("service_bay", 0.10)

    @property
    def mission_stage_dry(self) -> float:
        """Dry mass of mission stage (above upper decoupler)."""
        return (self.capsule_mass + self.avionics_mass +
                PARTS["tr18a_decoupler"] + TANKS["flt800"]["mass_dry"] +
                ENGINES["terrier"]["mass"])

    @property
    def mission_stage_wet(self) -> float:
        return self.mission_stage_dry + TANKS["flt800"]["prop_mass"]

    @property
    def core_stage_dry(self) -> float:
        """Dry mass of launch-core stage (Swivel + lower FL-T800 + lower decoupler)."""
        return (PARTS["tr18a_decoupler"] + TANKS["flt800"]["mass_dry"] +
                ENGINES["swivel"]["mass"])

    @property
    def core_stage_prop(self) -> float:
        return TANKS["flt800"]["prop_mass"]

    @property
    def booster_set_dry(self) -> float:
        return self.n_boosters * (self._booster["mass_dry"] + PARTS["tt38k_decoupler"])

    @property
    def booster_set_prop(self) -> float:
        return self.n_boosters * self._booster["prop_mass"]

    @property
    def booster_nosecone_mass(self) -> float:
        return self.n_boosters * PARTS["aero_nosecone"]

    @property
    def fin_mass(self) -> float:
        return 4 * PARTS["basic_fin"]

    @property
    def liftoff_mass_t(self) -> float:
        return (self.mission_stage_wet +
                self.core_stage_dry + self.core_stage_prop +
                self.booster_set_dry + self.booster_set_prop +
                self.booster_nosecone_mass + self.fin_mass +
                self.extra_payload)

    @property
    def mass_after_booster_sep(self) -> float:
        """
        Vehicle mass immediately after booster jettison, assuming NO core
        propellant has been consumed yet.  This is a **conservative upper bound**
        — the actual mass is lower by the Swivel propellant burned during the
        booster phase.  Use :attr:`mass_at_booster_sep` for the accurate value.
        """
        return self.liftoff_mass_t - self.booster_set_dry - self.booster_set_prop

    @property
    def mass_at_booster_sep(self) -> float:
        """
        Estimated vehicle mass at the moment of booster separation, accounting
        for core-stage (Swivel) propellant consumed during the booster burn.

        Uses the vacuum Swivel mdot as a conservative estimate (actual sea-level
        mdot is slightly lower, so this slightly under-predicts mass).
        """
        from .constants import G0, ENGINES
        sw = ENGINES["swivel"]
        mdot_vac_kgs = sw["thrust_vac"] * 1000 / (sw["isp_vac"] * G0)
        core_prop_burned_t = (mdot_vac_kgs * self.srb_burn_time_s) / 1000.0
        return self.mass_after_booster_sep - core_prop_burned_t

    # -----------------------------------------------------------------------
    # Performance
    # -----------------------------------------------------------------------

    @property
    def effective_cda(self) -> float:
        return self._cda

    @property
    def pad_twr_asl(self) -> float:
        """Liftoff TWR (all engines at their settings, sea level)."""
        swivel_thrust = ENGINES["swivel"]["thrust_asl"]
        srb_thrust = self.n_boosters * self._booster["thrust_asl"] * (self.booster_pct / 100.0)
        total_kN = swivel_thrust + srb_thrust
        weight_kN = self.liftoff_mass_t * G0
        return total_kN / weight_kN

    @property
    def srb_burn_time_s(self) -> float:
        """Time to booster burnout at the configured throttle setting."""
        mdot_full = engine_mdot_full(self.booster_type)
        mdot = mdot_full * (self.booster_pct / 100.0)
        return (self._booster["prop_mass"] * 1000) / mdot  # s

    @property
    def mission_stage_dv_ms(self) -> float:
        """Vacuum delta-v of the Terrier mission stage (full tank)."""
        m0 = self.mission_stage_wet
        m1 = self.mission_stage_dry
        return G0 * ENGINES["terrier"]["isp_vac"] * math.log(m0 / m1)

    def summary(self) -> str:
        lines = [
            f"VehicleConfig — Perseus 1 variant",
            f"  Booster: {self.n_boosters}x {self.booster_type.upper()} @ {self.booster_pct:.0f}%",
            f"  Liftoff mass:          {self.liftoff_mass_t:.2f} t",
            f"  Pad TWR (ASL):         {self.pad_twr_asl:.2f}",
            f"  SRB burn time:         {self.srb_burn_time_s:.1f} s",
            f"  Mission stage dv:      {self.mission_stage_dv_ms:.0f} m/s (vacuum, full tank)",
            f"  Effective CdA:         {self.effective_cda:.3f} m²",
        ]
        return "\n".join(lines)
