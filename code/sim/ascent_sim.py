"""
sim/ascent_sim.py
-----------------
Main ascent simulation script for Perseus 1.

Usage (CLI)::

    # Run baseline and print summary
    python ascent_sim.py

    # Custom booster throttle
    python ascent_sim.py --hammer-pct 25

    # JSON output (for piping into mission control or other tools)
    python ascent_sim.py --json

    # Compare two pitch programs
    python ascent_sim.py --compare nominal steep

    # Print trajectory point table
    python ascent_sim.py --table

    # Thumper variant
    python ascent_sim.py --booster thumper --booster-pct 20

Usage (as module)::

    from sim.ascent_sim import run_ascent, VehicleConfig
    from sim.trajectory import PITCH_PROGRAMS

    cfg = VehicleConfig(booster_pct=20)
    result = run_ascent(cfg, pitch_program=PITCH_PROGRAMS['nominal'])
    print(result.apoapsis_km, result.periapsis_km)

    # Get full trajectory points (for plotting)
    for pt in result.points:
        print(pt.t, pt.altitude/1000, pt.downrange/1000, pt.apoapsis)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Optional

# Allow running as a script directly from this directory
if __name__ == "__main__":
    import os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sim.constants import G0, PERSEUS_1_DEFAULT
from sim.vehicle import VehicleConfig
from sim.trajectory import integrate, PITCH_PROGRAMS, TrajectoryResult


# ---------------------------------------------------------------------------
# High-level API
# ---------------------------------------------------------------------------

def run_ascent(
    vehicle: Optional[VehicleConfig] = None,
    pitch_program=None,
    dt: float = 0.02,
) -> TrajectoryResult:
    """
    Run the Perseus 1 ascent simulation and return the trajectory result.

    Parameters
    ----------
    vehicle : VehicleConfig, optional
        Vehicle configuration. Defaults to PERSEUS_1_DEFAULT if not specified.
    pitch_program : callable, optional
        Pitch program function. Defaults to the nominal gravity-turn program.
    dt : float
        Integration timestep in seconds (default 0.02 s).

    Returns
    -------
    TrajectoryResult
        Contains .points (sampled), .booster_sep, .core_burnout,
        .apoapsis_km, .periapsis_km, .drag_loss_total, .grav_loss_total.

    Examples
    --------
    ::

        from sim.ascent_sim import run_ascent
        from sim.vehicle import VehicleConfig
        from sim.trajectory import PITCH_PROGRAMS

        result = run_ascent(VehicleConfig(booster_pct=25),
                            pitch_program=PITCH_PROGRAMS['shallow'])
        print(f"Apoapsis: {result.apoapsis_km:.1f} km")
    """
    if vehicle is None:
        vehicle = VehicleConfig()
    if pitch_program is None:
        pitch_program = PITCH_PROGRAMS["nominal"]
    result = integrate(vehicle, pitch_program=pitch_program, dt=dt)
    result.config_summary = vehicle.summary()
    return result


def result_to_dict(result: TrajectoryResult, vehicle: VehicleConfig) -> dict:
    """Serialize a TrajectoryResult to a JSON-compatible dict."""
    def sep_dict(s):
        if s is None: return None
        return {"t_s": round(s.t, 1), "altitude_km": round(s.altitude/1000, 2),
                "velocity_ms": round(s.velocity, 1), "mass_t": round(s.mass, 3),
                "apoapsis_km": round(s.apoapsis, 1), "periapsis_km": round(s.periapsis, 1)}

    def bo_dict(p):
        if p is None: return None
        return {"t_s": round(p.t, 1), "altitude_km": round(p.altitude/1000, 2),
                "downrange_km": round(p.downrange/1000, 2),
                "velocity_ms": round(p.velocity, 1),
                "v_horiz_ms": round(p.v_horiz, 1), "v_vert_ms": round(p.v_vert, 1),
                "gamma_deg": round(math.degrees(p.gamma), 1),
                "pitch_from_vertical_deg": round(p.pitch_from_v, 1),
                "mass_t": round(p.mass, 3),
                "apoapsis_km": round(p.apoapsis, 1), "periapsis_km": round(p.periapsis, 1)}

    trajectory = [
        {"t_s": round(p.t, 2),
         "altitude_km": round(p.altitude/1000, 3),
         "downrange_km": round(p.downrange/1000, 3),
         "velocity_ms": round(p.velocity, 1),
         "v_horiz_ms": round(p.v_horiz, 1),
         "v_vert_ms": round(p.v_vert, 1),
         "pitch_from_vertical_deg": round(p.pitch_from_v, 1),
         "apoapsis_km": round(p.apoapsis, 2),
         "periapsis_km": round(p.periapsis, 2),
         "phase": p.phase}
        for p in result.points
    ]

    return {
        "vehicle": {
            "booster_type": vehicle.booster_type,
            "n_boosters": vehicle.n_boosters,
            "booster_pct": vehicle.booster_pct,
            "extra_payload_t": vehicle.extra_payload,
            "liftoff_mass_t": round(vehicle.liftoff_mass_t, 3),
            "pad_twr_asl": round(vehicle.pad_twr_asl, 3),
            "srb_burn_time_s": round(vehicle.srb_burn_time_s, 1),
            "mission_stage_dv_ms": round(vehicle.mission_stage_dv_ms, 0),
        },
        "results": {
            "booster_sep": sep_dict(result.booster_sep),
            "core_burnout": bo_dict(result.core_burnout),
            "apoapsis_km": round(result.apoapsis_km, 1),
            "periapsis_km": round(result.periapsis_km, 1),
            "drag_loss_ms": round(result.drag_loss_total, 1),
            "gravity_loss_ms": round(result.grav_loss_total, 1),
        },
        "trajectory": trajectory,
    }


def print_summary(result: TrajectoryResult, vehicle: VehicleConfig,
                  label: str = ""):
    prefix = f"[{label}] " if label else ""
    print(f"\n{'='*62}")
    print(f"{prefix}ASCENT SIMULATION RESULTS")
    print(f"{'='*62}")
    print(vehicle.summary())
    print()

    if result.booster_sep:
        s = result.booster_sep
        print(f"Booster separation:")
        print(f"  t = {s.t:.1f} s   h = {s.altitude/1000:.1f} km   "
              f"v = {s.velocity:.0f} m/s   mass = {s.mass:.2f} t")
        print(f"  Apoapsis at sep: {s.apoapsis:.1f} km   "
              f"Periapsis: {s.periapsis:.0f} km")

    if result.core_burnout:
        b = result.core_burnout
        print(f"\nCore burnout:")
        print(f"  t = {b.t:.1f} s   h = {b.altitude/1000:.1f} km   "
              f"DR = {b.downrange/1000:.1f} km")
        print(f"  v = {b.velocity:.0f} m/s  (horiz {b.v_horiz:.0f} / vert {b.v_vert:.0f})")
        print(f"  Pitch from vertical: {b.pitch_from_v:.0f}°")

    print(f"\nOrbital parameters at core burnout (if unpowered from here):")
    print(f"  Apoapsis:  {result.apoapsis_km:7.1f} km")
    print(f"  Periapsis: {result.periapsis_km:7.0f} km "
          f"({'suborbital' if result.periapsis_km < -70 else 'orbital' if result.periapsis_km > 70 else 'marginal'})")
    print(f"\nLoss budget:")
    print(f"  Gravity losses: {result.grav_loss_total:.0f} m/s")
    print(f"  Drag losses:    {result.drag_loss_total:.0f} m/s")


def print_table(result: TrajectoryResult):
    print(f"\n{'T+':>6}  {'Alt(km)':>8}  {'DR(km)':>7}  "
          f"{'v(m/s)':>7}  {'vH':>7}  {'vV':>7}  "
          f"{'Pitch°':>7}  {'Ap(km)':>8}  {'Pe(km)':>8}  Phase")
    for p in result.points:
        print(f"{p.t:>6.1f}  {p.altitude/1000:>8.2f}  {p.downrange/1000:>7.2f}  "
              f"{p.velocity:>7.0f}  {p.v_horiz:>7.0f}  {p.v_vert:>7.0f}  "
              f"{p.pitch_from_v:>7.1f}  {p.apoapsis:>8.1f}  {p.periapsis:>8.0f}  {p.phase}")


def compare_programs(vehicle: VehicleConfig, programs: list[str]):
    print(f"\nComparing pitch programs with: {vehicle.summary().split(chr(10))[0]}")
    print(f"\n{'Program':<16}  {'Ap(km)':>8}  {'Pe(km)':>8}  {'Sep-t(s)':>9}  "
          f"{'BO-h(km)':>9}  {'vH-bo':>7}  {'DragLoss':>9}  {'GravLoss':>9}")
    for name in programs:
        if name not in PITCH_PROGRAMS:
            print(f"  Unknown pitch program '{name}'. Options: {list(PITCH_PROGRAMS)}")
            continue
        r = run_ascent(vehicle, pitch_program=PITCH_PROGRAMS[name])
        sep_t = f"{r.booster_sep.t:.1f}" if r.booster_sep else "—"
        bo_h = f"{r.core_burnout.altitude/1000:.1f}" if r.core_burnout else "—"
        vh = f"{r.core_burnout.v_horiz:.0f}" if r.core_burnout else "—"
        print(f"{name:<16}  {r.apoapsis_km:>8.1f}  {r.periapsis_km:>8.0f}  "
              f"{sep_t:>9}  {bo_h:>9}  {vh:>7}  "
              f"{r.drag_loss_total:>9.0f}  {r.grav_loss_total:>9.0f}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ascent_sim.py",
        description="Perseus 1 ascent trajectory simulator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--booster", default="hammer",
                   choices=["hammer", "thumper"],
                   help="SRB type")
    p.add_argument("--n-boosters", type=int, default=2,
                   help="Number of SRBs")
    p.add_argument("--hammer-pct", "--booster-pct", type=float, default=20.0,
                   dest="booster_pct",
                   help="SRB thrust limit (%%). Alias --booster-pct also works.")
    p.add_argument("--extra-payload", type=float, default=0.0,
                   help="Extra inert mass on core stage (t) — default 0.0 since service bay is now modelled in avionics_mass")
    p.add_argument("--pitch", default="nominal",
                   choices=list(PITCH_PROGRAMS),
                   help="Pitch program to use")
    p.add_argument("--dt", type=float, default=0.02,
                   help="Integration timestep (s)")
    p.add_argument("--json", action="store_true",
                   help="Output full results as JSON (suitable for piping)")
    p.add_argument("--table", action="store_true",
                   help="Print trajectory table alongside summary")
    p.add_argument("--compare", nargs="+", metavar="PROGRAM",
                   help=f"Compare multiple pitch programs. Options: {list(PITCH_PROGRAMS)}")
    return p


def main(argv=None):
    parser = build_argparser()
    args = parser.parse_args(argv)

    vehicle = VehicleConfig(
        booster_type=args.booster,
        n_boosters=args.n_boosters,
        booster_pct=args.booster_pct,
        extra_payload=args.extra_payload,
    )

    if args.compare:
        compare_programs(vehicle, args.compare)
        return

    result = run_ascent(vehicle, pitch_program=PITCH_PROGRAMS[args.pitch], dt=args.dt)

    if args.json:
        print(json.dumps(result_to_dict(result, vehicle), indent=2))
        return

    print_summary(result, vehicle, label=f"{args.booster.upper()} @{args.booster_pct:.0f}%")
    if args.table:
        print_table(result)


if __name__ == "__main__":
    main()
