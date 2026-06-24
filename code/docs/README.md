# Perseus 1 — KSP Mission Pack · Technical Package

A fan-made Kerbal Space Program 1 mission pack for **Perseus 1**, a stock
1.25 m crewed Mun free-return flyby vehicle. This repository contains:

- **`sim/`** — Physics-grounded ascent trajectory simulator (pure Python)
- **`mission_control/`** — Real-time Mission Control: Telemachus integration + web interface
- **`diagrams/`** — NASA-style SVG technical reference sheets + generator
- **`docs/`** — This documentation

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the ascent simulator

```bash
# Summary (default: 2x Hammer @20%, nominal pitch program)
python -m sim.ascent_sim

# Custom throttle
python -m sim.ascent_sim --hammer-pct 25

# JSON output (pipe into other tools)
python -m sim.ascent_sim --json > results.json

# Compare pitch programs
python -m sim.ascent_sim --compare nominal steep shallow late_turn

# Full trajectory table
python -m sim.ascent_sim --table
```

### 3. Start Mission Control (simulation mode)

```bash
# No KSP game required — plays back the nominal trajectory with noise
python mission_control/server.py
# Open http://localhost:5000/ in a browser
```

### 4. Start Mission Control (live KSP)

```bash
# With Telemachus installed and KSP running on the same machine:
python mission_control/server.py --ksp-host 127.0.0.1

# KSP on another machine:
python mission_control/server.py --ksp-host 192.168.1.42
```

### 5. Regenerate technical diagrams

```bash
# Outputs 4 SVG files to ./out/
python diagrams/generate_diagrams.py
```

---

## Project Structure

```
perseus-mission/
├── sim/
│   ├── __init__.py          Importable API (run_ascent, VehicleConfig, …)
│   ├── constants.py         Kerbin physics + verified KSP part stats
│   ├── atmosphere.py        Exponential atmosphere model
│   ├── vehicle.py           Mass accounting, pad TWR, delta-v
│   ├── trajectory.py        Numerical integrator + pitch programs
│   └── ascent_sim.py        CLI entry point + high-level run_ascent()
│
├── mission_control/
│   ├── __init__.py
│   ├── telemachus_client.py  WebSocket client for Telemachus KSP plugin
│   ├── nominal_compare.py    Flight director: phase detection, go/no-go, advisories
│   ├── server.py             Flask + Socket.IO backend server
│   └── static/
│       └── index.html        Full mission control web interface
│
├── diagrams/
│   ├── dsys.py              SVG design system (palette, primitives, title blocks)
│   ├── parts.py             KSP part silhouettes (pod, tank, engines, fins…)
│   ├── sheet1.py            Sheet 1: Vehicle General Arrangement
│   ├── sheet2.py            Sheet 2: Stage Separation Sequence
│   ├── sheet3.py            Sheet 3: Ascent Guidance Program
│   ├── sheet4.py            Sheet 4: Ascent Contingency & Abort Criteria
│   └── generate_diagrams.py Consolidated single-file generator
│
├── docs/
│   ├── README.md            This file
│   ├── SIM_API.md           Simulation package API reference
│   └── MISSION_CONTROL.md   Mission control setup and Houston integration
│
└── requirements.txt
```

---

## Vehicle: Perseus 1

| Parameter | Value |
|---|---|
| Crew | 1 (Mk1 pod) |
| Mission | Mun free-return flyby |
| Liftoff mass | ~14.3 t |
| Pad TWR | ~1.76 (20% Hammer) |
| Booster burnout | T+25 s / 2.6 km |
| Mission stage ΔV | ~3,460 m/s vacuum |
| Target orbit | 80 × 80 km |
| TMI ΔV | ~856 m/s |

### Key design decisions (see build plan for full rationale)

- **Hammers at 20%** thrust limit → pad TWR 1.76, booster burn 25 s, landing
  squarely inside the 1.4–1.8 target band.
- **Terrier finishes the climb** — the core stage reaches ~25 km apoapsis at
  burnout; the Terrier has 3,460 m/s and uses roughly 1.8–2.0 km/s to finish
  the ascent plus TMI, leaving substantial reserve.
- **Service bay** on the mission stage houses the Telemachus antenna and fuel
  cells on the centreline — eliminates the drag asymmetry that caused ascent
  instability with a single radially-mounted antenna.
- **Fins on the lower core tank** (not the boosters) — stays with the vehicle
  after booster separation. Mount as low as possible, clocked 45° off the SRBs.

---

## Simulation accuracy

The simulator uses:
- Exponential Kerbin atmosphere (ρ₀ = 1.225 kg/m³, H = 5 km scale height)
- Altitude-varying gravity (μ/r²)
- Thrust and Isp interpolated between ASL and vacuum by pressure fraction
- Euler integration at dt = 0.02 s
- Self-consistent Hammer burn time (thrust/Isp → mdot → burn duration)

Results are consistent with the in-game experience: ~25 km apoapsis at core
burnout, booster sep at ~25 s, gravity losses ~530 m/s dominating drag losses
~30 m/s by more than an order of magnitude.

---

## Telemachus Setup (for live mission control)

1. Install the [Telemachus](https://github.com/TeleIO/Telemachus-1) plugin
   into your KSP `GameData` folder.
2. In-game, right-click the antenna on your vessel to open Telemachus and
   note the displayed IP/port (default: port 8085).
3. Start the mission control server with `--ksp-host [IP]`.

See `docs/MISSION_CONTROL.md` for full details including network setup,
topic customisation, and Houston UI integration.


> **Circularization burn time:** ~2–5 s at 80 km with ~3.7t mission stage; lead apoapsis by ~1–2.5 s.
