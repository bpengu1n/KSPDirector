"""
sim/trajectory.py
-----------------
Numerical trajectory integration engine for KSP ascent simulation.

Integrates the 2D equations of motion (altitude + downrange) using Euler
stepping with small timesteps. Handles:
  - Altitude-varying gravity
  - Altitude-varying atmospheric density and Isp
  - Continuous propellant depletion for both boosters and core
  - Instantaneous mass/thrust drop at booster separation
  - Prescribed pitch program through dense atmosphere, then free gravity turn
  - Downrange distance integration

The integrator is intentionally simple (Euler, fixed dt) rather than using
higher-order methods, because KSP's own physics runs at ~50 Hz with Euler.
dt=0.02 s gives good agreement with in-game results.

Exports:
    TrajectoryPoint  -- dataclass for a single trajectory state
    TrajectoryResult -- dataclass collecting full results
    integrate        -- run the integration and return a TrajectoryResult
"""

import math
from dataclasses import dataclass, field
from typing import Callable, Optional

from .constants import G0, MU_KERBIN, R_KERBIN, ATM_CEIL, ENGINES, TANKS
from . import atmosphere as atm
from .vehicle import engine_thrust_at  # Fix P3-06: was imported inside integrate()

# Deferred imports for generic integrator (to avoid circular imports at module load)
# GenericVehicle and PartsDatabase are imported inside integrate_generic().


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TrajectoryPoint:
    """State at a single integration timestep."""
    t:             float    # s, time from liftoff
    altitude:      float    # m
    downrange:     float    # m, horizontal distance from launch site
    velocity:      float    # m/s, total speed
    v_horiz:       float    # m/s, horizontal component
    v_vert:        float    # m/s, vertical component
    gamma:         float    # rad, flight-path angle from horizontal
    pitch_from_v:  float    # deg, pitch from vertical (0=up, 90=horizontal)
    mass:          float    # t, current vehicle mass
    apoapsis:      float    # km, apoapsis altitude (from instantaneous orbit)
    periapsis:     float    # km, periapsis altitude (from instantaneous orbit)
    phase:         str      # 'BOOST', 'CORE', 'TERRIER', 'COAST_APO', 'CIRCULARIZE', 'ORBIT', 'COAST'
    drag_loss_cum: float    # m/s, cumulative drag velocity loss
    grav_loss_cum: float    # m/s, cumulative gravity loss


@dataclass
class SeparationEvent:
    t:         float
    altitude:  float     # m
    velocity:  float     # m/s
    gamma:     float     # rad
    mass:      float     # t (post-sep)
    apoapsis:  float     # km
    periapsis: float     # km


@dataclass
class TrajectoryResult:
    """Full results from a trajectory integration."""
    points:           list    # list of TrajectoryPoint (sampled, not every step)
    all_points:       list    # list of TrajectoryPoint (every step — for internal use)
    booster_sep:      Optional[SeparationEvent]
    core_burnout:     Optional[TrajectoryPoint]
    max_q_point:      Optional[TrajectoryPoint]    # point of maximum dynamic pressure
    drag_loss_total:  float   # m/s
    grav_loss_total:  float   # m/s
    # Orbital parameters at core burnout
    apoapsis_km:      float
    periapsis_km:     float
    # Generic staging events (populated by integrate_generic)
    staging_events:   list = field(default_factory=list)
    # Config echo
    config_summary:   str = ""


# ---------------------------------------------------------------------------
# Orbital mechanics helpers
# ---------------------------------------------------------------------------

def gravity(h: float) -> float:
    """Local gravitational acceleration (m/s²) at altitude h (m)."""
    r = R_KERBIN + h
    return MU_KERBIN / (r * r)


def orbital_params(h: float, v: float, gamma: float) -> tuple[float, float]:
    """
    Returns (apoapsis_km, periapsis_km) for an instantaneous orbital state.
    gamma: flight-path angle from horizontal (rad). 0 = horizontal, pi/2 = straight up.
    Returns km. Suborbital cases give negative periapsis.
    """
    r = R_KERBIN + h
    energy = 0.5 * v * v - MU_KERBIN / r
    if energy >= 0:
        return float("inf"), float("-inf")   # escape trajectory
    a = -MU_KERBIN / (2.0 * energy)
    h_mom = r * v * math.cos(gamma)
    ecc_sq = 1.0 - (h_mom * h_mom) / (MU_KERBIN * a)
    ecc = math.sqrt(max(0.0, ecc_sq))
    apo = (a * (1.0 + ecc) - R_KERBIN) / 1000.0    # km
    per = (a * (1.0 - ecc) - R_KERBIN) / 1000.0    # km
    return apo, per


# ---------------------------------------------------------------------------
# Pitch programs
# ---------------------------------------------------------------------------

# A pitch program is a callable: (altitude_m) -> Optional[float]
# Returns target gamma (flight-path angle from horizontal, DEGREES) if still
# in the prescribed phase, or None to hand off to free gravity-turn physics.

def pitch_nominal(h: float) -> Optional[float]:
    """
    Nominal Perseus 1 pitch program.
    Hold vertical (90° from horizontal = 0° from vertical) below 300 m,
    then pitch to ~45° from horizontal by 12 km, then free gravity turn.
    """
    if h <= 300.0:
        return 89.999        # essentially vertical
    if h >= 12_000.0:
        return None          # hand off to gravity turn
    # linear interpolation: 90° -> 45°
    frac = (h - 300.0) / (12_000.0 - 300.0)
    return 90.0 - 45.0 * frac


def pitch_steep(h: float) -> Optional[float]:
    """Steep ascent profile — holds near-vertical too long."""
    if h <= 300.0:
        return 89.999
    if h >= 12_000.0:
        return None
    frac = (h - 300.0) / (12_000.0 - 300.0)
    return 90.0 - 15.0 * frac   # only reaches 75°, not 45°


def pitch_shallow(h: float) -> Optional[float]:
    """Shallow ascent — pitches over more aggressively."""
    if h <= 300.0:
        return 89.999
    if h >= 8_000.0:
        return None
    frac = (h - 300.0) / (8_000.0 - 300.0)
    return 90.0 - 55.0 * frac


def pitch_late_turn(h: float) -> Optional[float]:
    """Holds vertical to 8 km then pitches."""
    if h <= 8_000.0:
        return 89.999
    if h >= 20_000.0:
        return None
    frac = (h - 8_000.0) / (20_000.0 - 8_000.0)
    return 90.0 - 45.0 * frac


PITCH_PROGRAMS = {
    "nominal":   pitch_nominal,
    "steep":     pitch_steep,
    "shallow":   pitch_shallow,
    "late_turn": pitch_late_turn,
}


# ---------------------------------------------------------------------------
# Main integrator
# ---------------------------------------------------------------------------

def integrate(
    vehicle,                           # VehicleConfig
    pitch_program: Callable = pitch_nominal,
    dt: float = 0.02,                  # s, timestep
    t_max: float = 600.0,              # s, max integration time
    sample_every_n: int = 25,          # save a point every N steps
    target_orbit_km: float = 80.0,     # target orbit altitude (km)
) -> TrajectoryResult:
    """
    Run the full ascent trajectory simulation: boosters → core → Terrier → orbit.

    Phases modelled:
      BOOST        SRBs + Swivel burning
      CORE         Swivel only, post booster sep
      TERRIER      Terrier burns prograde after core sep
      COAST_APO    Unpowered coast to apoapsis
      CIRCULARIZE  Terrier burns at apoapsis to raise periapsis
      ORBIT        Stable orbit, coasting
      COAST        Unpowered suborbital coast (if Terrier fuel exhausted)

    Parameters
    ----------
    vehicle : VehicleConfig
        Vehicle configuration (masses, engine settings, drag).
    pitch_program : callable
        Receives altitude (m), returns target flight-path angle (deg from horizontal)
        or None for free gravity turn.
    dt : float
        Integration timestep (seconds). 0.02 s recommended.
    t_max : float
        Maximum simulation time before forced termination.
    sample_every_n : int
        Save a full TrajectoryPoint every this many steps (to limit memory).
    target_orbit_km : float
        Target circular orbit altitude in km.

    Returns
    -------
    TrajectoryResult
    """
    b = ENGINES[vehicle.booster_type]
    b_mdot_full = b["thrust_vac"] * 1000 / (b["isp_vac"] * G0)
    throttle = vehicle.booster_pct / 100.0
    cda = vehicle.effective_cda

    target_apo_m = target_orbit_km * 1000.0
    target_pe_m = (target_orbit_km - 5.0) * 1000.0

    # Build initial state
    t = 0.0
    h = 0.0          # altitude, m
    dr = 0.0         # downrange, m
    v = 0.1          # velocity, m/s (small nonzero to avoid div/0)
    gamma = math.radians(89.999)   # flight-path angle from horizontal (rad)

    boost_prop = vehicle.booster_set_prop * 1000   # kg
    core_prop  = vehicle.core_stage_prop * 1000    # kg
    terrier_prop = TANKS["flt800"]["prop_mass"] * 1000  # kg, mission stage
    mass = vehicle.liftoff_mass_t * 1000           # kg

    boosters_attached = True
    core_burned_out = False
    terrier_phase = None   # None → "TERRIER" → "COAST_APO" → "CIRCULARIZE" → "ORBIT"
    free_turn = False
    step = 0
    drag_loss = 0.0
    grav_loss = 0.0
    prev_v_vert = None

    booster_sep_event: Optional[SeparationEvent] = None
    core_sep_event: Optional[SeparationEvent] = None
    core_burnout_pt: Optional[TrajectoryPoint] = None
    ap_at_burnout: Optional[float] = None
    pe_at_burnout: Optional[float] = None
    max_q_pt: Optional[TrajectoryPoint] = None
    max_q_val = 0.0

    all_pts = []
    sampled_pts = []

    def make_point(phase):
        v_h = v * math.cos(gamma)
        v_v = v * math.sin(gamma)
        ap, pe = orbital_params(h, v, gamma)
        return TrajectoryPoint(
            t=t, altitude=h, downrange=dr, velocity=v,
            v_horiz=v_h, v_vert=v_v, gamma=gamma,
            pitch_from_v=90.0 - math.degrees(gamma),
            mass=mass / 1000.0,
            apoapsis=ap, periapsis=pe,
            phase=phase,
            drag_loss_cum=drag_loss,
            grav_loss_cum=grav_loss,
        )

    while t < t_max:
        g = gravity(h)

        # --- Engine thrust based on flight phase ---
        T_total_N = 0.0
        mdot_terrier = 0.0

        if terrier_phase in ("TERRIER", "CIRCULARIZE") and terrier_prop > 0:
            T_kN, mdot_terrier = engine_thrust_at(h, "terrier", 1.0)
            T_total_N = T_kN * 1000.0
        elif not core_burned_out:
            T_sw_kN, mdot_sw_kgs = engine_thrust_at(h, "swivel", 1.0)
            T_sw_N = T_sw_kN * 1000.0

            T_b_N = 0.0; mdot_b_kgs = 0.0
            if boosters_attached and boost_prop > 0.01:
                T_b_kN, mdot_b_each = engine_thrust_at(h, vehicle.booster_type, throttle)
                T_b_N = vehicle.n_boosters * T_b_kN * 1000.0
                mdot_b_kgs = vehicle.n_boosters * mdot_b_each

            T_total_N = T_sw_N + T_b_N

        D_N = atm.drag_force(h, v, cda)

        # --- Dynamic pressure ---
        q = 0.5 * atm.density(h) * v * v
        if q > max_q_val:
            max_q_val = q
            max_q_pt = make_point("BOOST" if boosters_attached else "CORE")

        # --- Pitch / gravity turn ---
        if not core_burned_out:
            pg_deg = pitch_program(h)
        else:
            pg_deg = None

        if pg_deg is not None and not free_turn:
            gamma = math.radians(pg_deg)
            dv  = (T_total_N - D_N) / mass - g * math.sin(gamma)
            dh  = v * math.sin(gamma)
            dgamma = 0.0
        else:
            free_turn = True
            dv  = (T_total_N - D_N) / mass - g * math.sin(gamma)
            if core_burned_out and v > 0.5:
                r = R_KERBIN + h
                dgamma = math.cos(gamma) * (v / r - g / v)
            elif v > 0.5:
                dgamma = -g * math.cos(gamma) / v
            else:
                dgamma = 0.0
            dh  = v * math.sin(gamma)

        # Downrange: horizontal displacement
        ddr = v * math.cos(gamma)

        # Loss bookkeeping during any powered phase
        if T_total_N > 0:
            drag_loss += (D_N / mass) * dt
            grav_loss += g * math.sin(gamma) * dt

        # --- Integrate ---
        v     += dv * dt
        h     += dh * dt
        dr    += ddr * dt
        if terrier_phase == "TERRIER":
            frac = min(1.0, h / target_apo_m)
            gamma_floor = math.radians(15.0) * (1.0 - frac)
            gamma = max(gamma + dgamma * dt, gamma_floor)
        elif terrier_phase == "CIRCULARIZE":
            gamma = max(gamma + dgamma * dt, 0.0)
        elif core_burned_out:
            gamma = gamma + dgamma * dt
        else:
            gamma = max(gamma + dgamma * dt, 0.0)

        # --- Propellant consumption & staging ---
        if terrier_phase in ("TERRIER", "CIRCULARIZE") and terrier_prop > 0:
            dm = mdot_terrier * dt
            terrier_prop -= dm
            mass -= dm
            if terrier_prop <= 0:
                terrier_prop = 0.0
                if terrier_phase == "TERRIER":
                    terrier_phase = "COAST_APO"
                else:
                    terrier_phase = "ORBIT" if orbital_params(h, v, gamma)[1] > target_pe_m / 1000.0 else "COAST"

        elif not core_burned_out:
            dm_sw = mdot_sw_kgs * dt
            dm_b  = mdot_b_kgs * dt if boosters_attached else 0.0

            boost_prop -= dm_b
            core_prop  -= dm_sw

            # Booster burnout → separation
            if boosters_attached and boost_prop <= 0.0:
                boost_prop = 0.0
                boosters_attached = False
                mass -= dm_b
                sep_inert_kg = vehicle.booster_set_dry * 1000
                mass -= sep_inert_kg
                ap, pe = orbital_params(h, v, gamma)
                booster_sep_event = SeparationEvent(
                    t=t, altitude=h, velocity=v, gamma=gamma,
                    mass=mass / 1000.0, apoapsis=ap, periapsis=pe,
                )
            else:
                mass -= dm_b

            mass -= dm_sw

            # Core burnout → core separation → Terrier ignition
            if core_prop <= 0.0:
                core_prop = 0.0
                core_burned_out = True
                core_burnout_pt = make_point("CORE")
                ap_at_burnout, pe_at_burnout = orbital_params(h, v, gamma)
                # Jettison core stage dry mass (tank, Swivel, decoupler, fins, extra payload)
                core_sep_kg = (vehicle.core_stage_dry + vehicle.fin_mass +
                               vehicle.extra_payload) * 1000
                mass -= core_sep_kg
                ap, pe = orbital_params(h, v, gamma)
                core_sep_event = SeparationEvent(
                    t=t, altitude=h, velocity=v, gamma=gamma,
                    mass=mass / 1000.0, apoapsis=ap, periapsis=pe,
                )
                terrier_phase = "TERRIER"

        # --- Terrier phase transitions ---
        if terrier_phase == "TERRIER" and terrier_prop > 0:
            ap_now = orbital_params(h, v, gamma)[0]
            if ap_now >= target_orbit_km:
                terrier_phase = "COAST_APO"

        if terrier_phase == "COAST_APO":
            v_v = v * math.sin(gamma)
            if prev_v_vert is not None and prev_v_vert > 0 and v_v <= 0:
                terrier_phase = "CIRCULARIZE" if terrier_prop > 0 else "COAST"
            prev_v_vert = v_v

        if terrier_phase == "CIRCULARIZE" and terrier_prop > 0:
            pe_now = orbital_params(h, v, gamma)[1]
            if pe_now >= target_orbit_km - 5.0:
                terrier_phase = "ORBIT"

        t += dt
        step += 1

        # --- Phase label ---
        if terrier_phase:
            phase = terrier_phase
        elif boosters_attached:
            phase = "BOOST"
        elif not core_burned_out:
            phase = "CORE"
        else:
            phase = "COAST"

        if step % sample_every_n == 0:
            sampled_pts.append(make_point(phase))

        if h < -100.0:
            if not core_burned_out:
                core_burnout_pt = make_point("CORE")
                ap_at_burnout, pe_at_burnout = orbital_params(h, v, gamma)
            break

    # Orbital params at core burnout (not end of flight)
    if ap_at_burnout is not None:
        ap_final, pe_final = ap_at_burnout, pe_at_burnout
    else:
        ap_final, pe_final = orbital_params(h, v, gamma)

    return TrajectoryResult(
        points=sampled_pts,
        all_points=sampled_pts,
        booster_sep=booster_sep_event,
        core_burnout=core_burnout_pt,
        max_q_point=max_q_pt,
        drag_loss_total=drag_loss,
        grav_loss_total=grav_loss,
        apoapsis_km=ap_final,
        periapsis_km=pe_final,
    )


# ---------------------------------------------------------------------------
# Generic N-stage integrator
# ---------------------------------------------------------------------------

def engine_thrust_at_generic(h, engine, throttle):
    """Like engine_thrust_at() but takes an Engine dataclass instead of a key."""
    pf = atm.pressure_fraction(h)
    thrust_100pct_kN = engine.thrust_vac_kn - (engine.thrust_vac_kn - engine.thrust_asl_kn) * pf
    thrust_kN = thrust_100pct_kN * throttle
    isp = atm.effective_isp(h, engine.isp_vac, engine.isp_asl)
    mdot = thrust_kN * 1000 / (isp * G0)
    return thrust_kN, mdot


def integrate_generic(
    vehicle,                                # GenericVehicle
    db,                                     # PartsDatabase
    pitch_program: Callable = pitch_nominal,
    dt: float = 0.02,
    t_max: float = 600.0,
    sample_every_n: int = 25,
    target_orbit_km: float = 80.0,
) -> TrajectoryResult:
    """Run an N-stage ascent trajectory simulation.

    Works with any GenericVehicle definition.  Parallel stages fire alongside
    the first sequential stage.  The stage marked ``orbit_insertion=True``
    (or the last stage if none is marked) gets the burn-coast-circularize
    state machine.  Stages after the orbit-insertion stage are inert mass.
    """
    cda = vehicle.cd * vehicle.area_base
    target_apo_m = target_orbit_km * 1000.0
    target_pe_m = (target_orbit_km - 5.0) * 1000.0
    n_stages = len(vehicle.stages)
    oi_idx = vehicle.orbit_insertion_idx()

    # Build per-stage runtime state
    stage_dry_kg = [vehicle.stage_dry_mass(i, db) * 1000 for i in range(n_stages)]
    stage_engines = [db.get_engine(s.engine_key) for s in vehicle.stages]

    stage_states = []
    for i in range(n_stages):
        prop_kg = vehicle.stage_prop_mass(i, db) * 1000
        stage_states.append({
            "prop": prop_kg,
            "active": False,
            "separated": False,
        })

    # Activate initial stages: all leading parallel stages + first non-parallel
    # Never activate stages beyond the orbit-insertion stage
    for i, stage in enumerate(vehicle.stages):
        if i > oi_idx:
            break
        stage_states[i]["active"] = True
        if not stage.parallel:
            break

    # Initial kinematic state
    t = 0.0
    h = 0.0
    dr = 0.0
    v = 0.1
    gamma = math.radians(89.999)
    mass = vehicle.liftoff_mass(db) * 1000  # kg

    # Final-stage orbit insertion state machine
    # None until the last stage activates, then BURN → COAST_APO → CIRCULARIZE → ORBIT
    final_mode = "BURN" if stage_states[oi_idx]["active"] else None

    free_turn = False
    step = 0
    drag_loss = 0.0
    grav_loss = 0.0
    prev_v_vert = None

    staging_events: list[SeparationEvent] = []
    max_q_pt: Optional[TrajectoryPoint] = None
    max_q_val = 0.0
    sampled_pts: list[TrajectoryPoint] = []

    def _phase_label():
        if final_mode is not None:
            if final_mode == "BURN":
                return vehicle.stages[oi_idx].name.upper()
            return final_mode
        for i in reversed(range(n_stages)):
            if stage_states[i]["active"] and not stage_states[i]["separated"]:
                return vehicle.stages[i].name.upper()
        return "COAST"

    def make_point(phase):
        v_h = v * math.cos(gamma)
        v_v = v * math.sin(gamma)
        ap, pe = orbital_params(h, v, gamma)
        return TrajectoryPoint(
            t=t, altitude=h, downrange=dr, velocity=v,
            v_horiz=v_h, v_vert=v_v, gamma=gamma,
            pitch_from_v=90.0 - math.degrees(gamma),
            mass=mass / 1000.0,
            apoapsis=ap, periapsis=pe,
            phase=phase,
            drag_loss_cum=drag_loss,
            grav_loss_cum=grav_loss,
        )

    while t < t_max:
        g = gravity(h)

        # --- Engine thrust from all active stages ---
        T_total_N = 0.0
        per_stage_mdot: dict[int, float] = {}

        if final_mode not in ("COAST_APO", "ORBIT", "COAST"):
            for i in range(oi_idx + 1):
                st = stage_states[i]
                if st["active"] and not st["separated"] and st["prop"] > 0:
                    eng = stage_engines[i]
                    throttle = vehicle.stages[i].throttle_pct / 100.0
                    T_kN, mdot_each = engine_thrust_at_generic(h, eng, throttle)
                    T_total_N += vehicle.stages[i].engine_count * T_kN * 1000
                    per_stage_mdot[i] = vehicle.stages[i].engine_count * mdot_each

        D_N = atm.drag_force(h, v, cda)

        # --- Dynamic pressure tracking ---
        q = 0.5 * atm.density(h) * v * v
        if q > max_q_val:
            max_q_val = q
            max_q_pt = make_point(_phase_label())

        # --- Pitch / gravity turn ---
        if not free_turn:
            pg_deg = pitch_program(h)
            if pg_deg is None:
                free_turn = True
        else:
            pg_deg = None

        if pg_deg is not None:
            gamma = math.radians(pg_deg)
            dv = (T_total_N - D_N) / mass - g * math.sin(gamma)
            dh = v * math.sin(gamma)
            dgamma = 0.0
        else:
            free_turn = True
            dv = (T_total_N - D_N) / mass - g * math.sin(gamma)
            dh = v * math.sin(gamma)
            if final_mode is not None and v > 0.5:
                r = R_KERBIN + h
                dgamma = math.cos(gamma) * (v / r - g / v)
            elif v > 0.5:
                dgamma = -g * math.cos(gamma) / v
            else:
                dgamma = 0.0

        ddr = v * math.cos(gamma)

        if T_total_N > 0:
            drag_loss += (D_N / mass) * dt
            grav_loss += g * math.sin(gamma) * dt

        # --- Integrate ---
        v += dv * dt
        h += dh * dt
        dr += ddr * dt

        if final_mode == "BURN":
            frac = min(1.0, h / target_apo_m) if target_apo_m > 0 else 1.0
            gamma_floor = math.radians(15.0) * (1.0 - frac)
            gamma = max(gamma + dgamma * dt, gamma_floor)
        elif final_mode == "CIRCULARIZE":
            gamma = max(gamma + dgamma * dt, 0.0)
        elif final_mode is not None:
            gamma = gamma + dgamma * dt
        else:
            gamma = max(gamma + dgamma * dt, 0.0)

        # --- Propellant consumption ---
        for i, mdot_kgs in per_stage_mdot.items():
            dm = mdot_kgs * dt
            stage_states[i]["prop"] -= dm
            mass -= dm

        # --- Staging: check for burnout (ascent stages only) ---
        for i in range(oi_idx + 1):
            st = stage_states[i]
            stage = vehicle.stages[i]
            if not st["active"] or st["separated"] or st["prop"] > 0:
                continue

            st["prop"] = 0.0

            if i == oi_idx:
                # Last stage: mode transition, no separation
                if final_mode == "BURN":
                    final_mode = "COAST_APO"
                elif final_mode == "CIRCULARIZE":
                    ap, pe = orbital_params(h, v, gamma)
                    final_mode = "ORBIT" if pe >= target_orbit_km - 5.0 else "COAST"
                continue

            # Non-final stage: separate
            st["separated"] = True
            st["active"] = False
            mass -= stage_dry_kg[i]

            ap, pe = orbital_params(h, v, gamma)
            staging_events.append(SeparationEvent(
                t=t, altitude=h, velocity=v, gamma=gamma,
                mass=mass / 1000.0, apoapsis=ap, periapsis=pe,
            ))

            if not stage.parallel:
                for j in range(i + 1, oi_idx + 1):
                    if not stage_states[j]["separated"]:
                        stage_states[j]["active"] = True
                        if j == oi_idx:
                            final_mode = "BURN"
                        if not vehicle.stages[j].parallel:
                            break

        # --- Final-stage phase transitions ---
        if final_mode == "BURN" and stage_states[oi_idx]["prop"] > 0:
            ap_now = orbital_params(h, v, gamma)[0]
            if ap_now >= target_orbit_km:
                final_mode = "COAST_APO"

        if final_mode == "COAST_APO":
            v_v = v * math.sin(gamma)
            if prev_v_vert is not None and prev_v_vert > 0 and v_v <= 0:
                final_mode = ("CIRCULARIZE"
                              if stage_states[oi_idx]["prop"] > 0
                              else "COAST")
            prev_v_vert = v_v

        if final_mode == "CIRCULARIZE" and stage_states[oi_idx]["prop"] > 0:
            pe_now = orbital_params(h, v, gamma)[1]
            if pe_now >= target_orbit_km - 5.0:
                final_mode = "ORBIT"

        t += dt
        step += 1

        if step % sample_every_n == 0:
            sampled_pts.append(make_point(_phase_label()))

        if h < -100.0:
            break

    ap_final, pe_final = orbital_params(h, v, gamma)

    return TrajectoryResult(
        points=sampled_pts,
        all_points=sampled_pts,
        booster_sep=staging_events[0] if staging_events else None,
        core_burnout=None,
        max_q_point=max_q_pt,
        drag_loss_total=drag_loss,
        grav_loss_total=grav_loss,
        apoapsis_km=ap_final,
        periapsis_km=pe_final,
        staging_events=staging_events,
    )
