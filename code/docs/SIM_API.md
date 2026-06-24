# Simulation Package API Reference

## Overview

`sim/` is a self-contained pure-Python ascent simulation package. No external
dependencies. Import it, run it from the CLI, or use its output as input to
the mission control server.

---

## Quickstart

```python
from sim import run_ascent, VehicleConfig, PITCH_PROGRAMS

# Baseline run
result = run_ascent()
print(f"Apoapsis:  {result.apoapsis_km:.1f} km")
print(f"Periapsis: {result.periapsis_km:.0f} km")
print(f"Drag loss: {result.drag_loss_total:.0f} m/s")
print(f"Grav loss: {result.grav_loss_total:.0f} m/s")

# Custom vehicle
cfg = VehicleConfig(booster_pct=25, extra_payload=0.15)
result = run_ascent(cfg, pitch_program=PITCH_PROGRAMS['shallow'])

# Iterate trajectory points
for pt in result.points:
    print(f"t={pt.t:.1f}s  alt={pt.altitude/1000:.1f}km  "
          f"dr={pt.downrange/1000:.1f}km  v={pt.velocity:.0f}m/s  "
          f"Ap={pt.apoapsis:.1f}km")
```

---

## `sim.run_ascent(vehicle, pitch_program, dt)`

Main entry point. Runs the simulation and returns a `TrajectoryResult`.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `vehicle` | `VehicleConfig` | `VehicleConfig()` | Vehicle definition |
| `pitch_program` | callable | `PITCH_PROGRAMS['nominal']` | Pitch program function |
| `dt` | float | `0.02` | Integration timestep (s) |

Returns: `TrajectoryResult`

---

## `sim.VehicleConfig`

Dataclass describing the vehicle. All parameters have defaults matching
the current Perseus 1 flight plan.

```python
@dataclass
class VehicleConfig:
    booster_type:  str   = "hammer"   # "hammer" | "thumper"
    n_boosters:    int   = 2
    booster_pct:   float = 20.0       # SRB thrust limit (%)
    extra_payload: float = 0.10       # extra inert mass on core (t)
    cd:            float = 0.22       # drag coefficient
    area_base:     float = 1.80       # effective drag area (m²)
```

### Computed properties

```python
cfg = VehicleConfig()
cfg.liftoff_mass_t          # total wet mass at liftoff (t)
cfg.pad_twr_asl             # pad TWR at sea level
cfg.srb_burn_time_s         # SRB burn duration at configured throttle
cfg.mission_stage_dv_ms     # Terrier stage ΔV (vacuum, full tank, m/s)
cfg.effective_cda           # effective drag area (m²)
cfg.summary()               # formatted string summary
```

---

## `sim.PITCH_PROGRAMS`

Dict of pitch program callables. Each takes altitude (m) and returns
flight-path angle from horizontal (degrees), or `None` to hand off to
free gravity-turn physics.

| Key | Description |
|---|---|
| `"nominal"` | Hold vertical to 300 m, pitch to 45° by 12 km, then gravity turn |
| `"steep"` | Barely pitches — reaches only 75° by 12 km (too steep) |
| `"shallow"` | Pitches aggressively — reaches 35° by 8 km |
| `"late_turn"` | Holds vertical to 8 km, then pitches quickly |

### Defining a custom pitch program

```python
def my_pitch(h: float):
    if h <= 500:   return 90.0    # vertical
    if h >= 15000: return None    # free gravity turn
    frac = (h - 500) / (15000 - 500)
    return 90.0 - 40.0 * frac    # 90° → 50° over 0.5–15 km

result = run_ascent(pitch_program=my_pitch)
```

---

## `TrajectoryResult`

Returned by `run_ascent()`.

| Attribute | Type | Description |
|---|---|---|
| `points` | `list[TrajectoryPoint]` | Sampled trajectory (every 0.5 s by default) |
| `booster_sep` | `SeparationEvent \| None` | State at booster separation |
| `core_burnout` | `TrajectoryPoint \| None` | State at core engine cutoff |
| `max_q_point` | `TrajectoryPoint \| None` | State at max dynamic pressure |
| `apoapsis_km` | `float` | Apoapsis at cutoff (km) |
| `periapsis_km` | `float` | Periapsis at cutoff (km, normally negative) |
| `drag_loss_total` | `float` | Cumulative drag ΔV loss (m/s) |
| `grav_loss_total` | `float` | Cumulative gravity loss (m/s) |

### `TrajectoryPoint`

| Attribute | Type | Unit | Description |
|---|---|---|---|
| `t` | float | s | Time from liftoff |
| `altitude` | float | m | Altitude above surface |
| `downrange` | float | m | Horizontal distance east from launch |
| `velocity` | float | m/s | Total speed |
| `v_horiz` | float | m/s | Horizontal velocity component |
| `v_vert` | float | m/s | Vertical velocity component |
| `gamma` | float | rad | Flight-path angle from horizontal |
| `pitch_from_v` | float | deg | Pitch from vertical (0=up, 90=horizontal) |
| `mass` | float | t | Current vehicle mass |
| `apoapsis` | float | km | Instantaneous apoapsis |
| `periapsis` | float | km | Instantaneous periapsis (negative = suborbital) |
| `phase` | str | — | `'BOOST'` or `'CORE'` |
| `drag_loss_cum` | float | m/s | Cumulative drag loss to this point |
| `grav_loss_cum` | float | m/s | Cumulative gravity loss to this point |

---

## CLI Reference

```
python -m sim.ascent_sim [OPTIONS]

OPTIONS:
  --booster {hammer,thumper}    SRB type (default: hammer)
  --n-boosters N                Number of SRBs (default: 2)
  --hammer-pct / --booster-pct  SRB thrust limit % (default: 20)
  --extra-payload T             Extra inert core mass in tonnes (default: 0.10)
  --pitch PROGRAM               Pitch program (default: nominal)
                                Options: nominal, steep, shallow, late_turn
  --dt S                        Integration timestep in seconds (default: 0.02)
  --json                        Output full results as JSON
  --table                       Print trajectory table
  --compare P1 P2 ...           Compare multiple pitch programs side by side
```

### Examples

```bash
# Compare all pitch programs
python -m sim.ascent_sim --compare nominal steep shallow late_turn

# JSON output for piping
python -m sim.ascent_sim --json | python -c "
import json,sys
d = json.load(sys.stdin)
print('Apoapsis:', d['results']['apoapsis_km'], 'km')
print('Booster sep at:', d['results']['booster_sep']['t_s'], 's')
"

# Thumper variant at 20%
python -m sim.ascent_sim --booster thumper --booster-pct 20
```

---

## `sim/constants.py`

Contains all physics constants and part data. Key tables:

- `ENGINES` — verified KSP part stats for Swivel, Terrier, Hammer, Thumper
- `TANKS` — FL-T800, FL-T400, FL-T200 mass breakdowns
- `PARTS` — structural part masses (pod, chute, decoupler, fins, etc.)
- `PERSEUS_1_DEFAULT` — baseline vehicle parameter dict

All engine stats include a `"confidence"` field: `"verified"` means they
were cross-checked against the KSP wiki and self-consistency-tested
(thrust = mdot × Isp × g₀). `"best-effort"` means approximate.

---

## Physical model notes

- **Atmosphere**: exponential, ρ = 1.225·exp(−h/5000) kg/m³, ceiling 70 km.
- **Gravity**: μ/r² with μ = 3.5316×10¹² m³/s² (Kerbin), varying with altitude.
- **Isp interpolation**: linear with pressure fraction between ASL and vacuum values.
  This matches KSP's engine model.
- **Drag**: F = ½ρv²CdA with a fixed effective area. This is a simplification —
  KSP's drag model is part-based and more complex, but the drag loss is small
  (~30 m/s vs ~530 m/s gravity losses) so the approximation does not materially
  affect ascent planning.
- **Integration**: Euler, dt = 0.02 s. This is intentionally simple — KSP runs
  at ~50 Hz with Euler integration, so this gives good agreement with in-game
  behaviour without over-engineering.
- **Pitch program**: prescribed (commanded) through the thick lower atmosphere,
  handing off to natural gravity-turn physics above ~12 km altitude. The boundary
  is where aerodynamic steering forces and the prescribed pitch produce the same
  trajectory to within numerical noise.
