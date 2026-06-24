#!/usr/bin/env python3
"""
tools/update_sheet3_trajectory.py
-----------------------------------
Regenerates the TRAJECTORY constant in diagrams/sheet3.py (and the nasa_dev
working copy) from the current sim output, keeping the diagram data
in sync with the simulation physics.

Usage::

    python tools/update_sheet3_trajectory.py [--sheet PATH]

Run this after any change to:
  - sim/constants.py (part masses, engine stats)
  - sim/vehicle.py   (VehicleConfig defaults)
  - sim/trajectory.py (pitch programs, integrator)

The script writes the new TRAJECTORY and updated PROGRAM milestones
directly into the target sheet3.py file.
"""
import sys, os, math, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sim import run_ascent, VehicleConfig
from sim.trajectory import PITCH_PROGRAMS


def build_trajectory_constant(result) -> str:
    """Format the trajectory points as a Python list literal."""
    pts = result.points
    # Downsample to ~40 points
    step = max(1, len(pts) // 40)
    sampled = pts[::step]
    if sampled[-1] is not pts[-1]:
        sampled.append(pts[-1])
    lines = ["# Derived from: sim.run_ascent(VehicleConfig(booster_pct=20))"]
    lines.append("# Regenerate: python tools/update_sheet3_trajectory.py")
    lines.append(f"# VehicleConfig: booster_pct=20, extra_payload=0.0")
    lines.append("TRAJECTORY = [")
    for p in sampled:
        dr = round(p.downrange / 1000, 2)
        alt = round(p.altitude / 1000, 2)
        pitch = round(p.pitch_from_v, 0)
        lines.append(f"    ({dr:.2f}, {alt:.2f}, {int(pitch)}),")
    lines.append("]")
    lines.append(f"SEP_PT = ({result.booster_sep.altitude/1000:.2f}, "
                 f"{result.booster_sep.altitude/1000:.2f})  # (downrange_km, alt_km) -- update if needed")
    lines.append(f"BURNOUT_PT = ({result.core_burnout.downrange/1000:.2f}, "
                 f"{result.core_burnout.altitude/1000:.2f})")
    return "\n".join(lines)


def update_sheet(path: str, new_traj: str, result) -> None:
    src = open(path).read()
    # Find and replace the TRAJECTORY block
    import re
    pattern = r'# Derived from:.*?^(?=\w)'
    match = re.search(pattern, src, re.DOTALL | re.MULTILINE)
    if match:
        src = src[:match.start()] + new_traj + "\n\n" + src[match.end():]
    else:
        # Try to find old TRAJECTORY = [...] and replace
        old = re.search(r'TRAJECTORY = \[.*?\]', src, re.DOTALL)
        if old:
            src = src[:old.start()] + new_traj + src[old.end():]
        else:
            print(f"WARNING: Could not find TRAJECTORY in {path}. No changes made.")
            return
    open(path, 'w').write(src)
    print(f"Updated: {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet", default=None,
                        help="Path to sheet3.py (default: auto-detect)")
    args = parser.parse_args()

    print("Running ascent simulation...")
    result = run_ascent()
    b = result.booster_sep
    bo = result.core_burnout
    print(f"  Booster sep:  T+{b.t:.0f}s  {b.altitude/1000:.2f}km  {b.velocity:.0f}m/s")
    print(f"  Core burnout: T+{bo.t:.0f}s  {bo.altitude/1000:.2f}km  {bo.velocity:.0f}m/s")
    print(f"  Points: {len(result.points)}")

    traj_code = build_trajectory_constant(result)

    # Try both locations
    candidates = [
        args.sheet,
        os.path.join(ROOT, 'diagrams', 'sheet3.py'),
        os.path.join(ROOT, '..', 'nasa_dev', 'sheet3.py'),
    ]
    updated = 0
    for path in candidates:
        if path and os.path.exists(path):
            update_sheet(path, traj_code, result)
            updated += 1

    if updated == 0:
        print("No sheet3.py found. Generated code:\n")
        print(traj_code)
    else:
        print(f"\nDone. Updated {updated} file(s). Remember to regenerate the SVG.")


if __name__ == "__main__":
    main()
