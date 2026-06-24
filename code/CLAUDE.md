# CLAUDE.md — Perseus 1 KSP Mission Pack

This file gives Claude Code the full context needed to continue development
without re-deriving things that are already settled. Read it fully before
touching any code. Key settled decisions are marked **DO NOT REOPEN** — they
have engineering rationale behind them and reopening them wastes iteration time.

---

## What this project is

A fan-made **Kerbal Space Program 1** mission pack for **Perseus 1**: a stock
1.25 m crewed Mun free-return flyby vehicle. Two parallel tracks:

1. **Physics-grounded simulation** — pure Python ascent trajectory simulator
   that produces verified numbers matching in-game behaviour.
2. **NASA-style documentation** — four SVG technical reference sheets in a
   consistent design system, plus a build plan / flight procedures document.
3. **Real-time Mission Control** — Flask + Socket.IO server that ingests
   Telemachus telemetry and serves a web-based flight director UI.

KSP version: **KSP 1 stock** (no mods affecting physics). The Telemachus plugin
is used for telemetry; it is NOT required to run the sim or mission control in
simulation mode.

---

## Directory layout

```
code/                          (root — was percy_project_fixed/ in outputs)
├── sim/                       Pure Python ascent sim — no external deps
│   ├── __init__.py            Public API: run_ascent, VehicleConfig, PITCH_PROGRAMS
│   ├── constants.py           Kerbin physics + verified KSP part stats + PERSEUS_1_DEFAULT
│   ├── atmosphere.py          Exponential atmosphere model
│   ├── vehicle.py             Mass accounting, pad TWR, ΔV, engine helpers
│   ├── trajectory.py          Euler integrator, pitch programs, orbital params
│   └── ascent_sim.py          CLI entry point + run_ascent() high-level API
│
├── mission_control/
│   ├── nominal_compare.py     Flight director: phase detection, go/no-go gates, advisories
│   ├── telemachus_client.py   Telemachus WS client + SimulatedTelemetry fallback
│   ├── server.py              Flask + Socket.IO backend
│   └── static/index.html      Complete mission control web UI (single file)
│
├── diagrams/                  SVG diagram source (nasa_dev/ working copies also exist)
│   ├── dsys.py                Design system: palette, primitives, title blocks
│   ├── parts.py               KSP part silhouettes (pod, tank, engines, fins)
│   ├── sheet1–4.py            Four reference sheets (build independently)
│   └── generate_diagrams.py   Consolidated single-file generator
│
├── tests/
│   ├── test_p0_regressions.py  17 tests — critical bug regressions
│   ├── test_p1_regressions.py  11 tests — high-priority issue regressions
│   └── test_p2_p3_regressions.py  21 tests — medium/low priority regressions
│
├── tools/
│   └── update_sheet3_trajectory.py   Regenerates TRAJECTORY constant in sheet3.py
│
├── docs/
│   ├── README.md              Quick-start guide
│   ├── SIM_API.md             Full simulation API reference
│   └── MISSION_CONTROL.md     Server setup, Telemachus, Houston UI integration
│
└── requirements.txt           flask, flask-socketio, eventlet, websocket-client
```

Also present at the package root (outside `code/`):
- `diagrams/*.svg` — four print-ready technical reference sheets
- `diagrams/generate_all.py` — consolidated SVG generator
- `perseus_1_build_plan.md` — full mission build plan and procedures
- `ENGINEERING_REVIEW.md` — 30-item engineering review, all resolved

---

## Running things

```bash
# Simulation (default: 2× Hammer @20%, nominal pitch program)
python -m sim.ascent_sim

# Compare pitch programs
python -m sim.ascent_sim --compare nominal steep shallow late_turn

# JSON output (pipe into other tools)
python -m sim.ascent_sim --json | python -m json.tool

# Mission control — simulation mode (no KSP needed)
python mission_control/server.py
# → open http://localhost:5000/

# Mission control — live KSP with Telemachus
python mission_control/server.py --ksp-host 192.168.1.X

# Full regression suite (must be green before committing any change)
python -m unittest tests.test_p0_regressions \
                   tests.test_p1_regressions \
                   tests.test_p2_p3_regressions -v

# Regenerate technical diagrams (run from nasa_dev/ or diagrams/)
python generate_diagrams.py   # or generate_all.py
# Validate SVG output
python -c "import xml.dom.minidom as m; m.parse('sheet3.svg'); print('valid')"

# Update sheet3 trajectory data from current sim
python tools/update_sheet3_trajectory.py
```

---

## Current verified numbers — DO NOT CHANGE WITHOUT RE-RUNNING SIM

These come from `python -m sim.ascent_sim` with the current codebase.
If you change any part mass or engine stat, re-run and update this table.

| Parameter | Value | Source |
|---|---|---|
| Liftoff mass | **14.21 t** | VehicleConfig() |
| Pad TWR (ASL) | **1.77** | VehicleConfig() |
| Mission stage ΔV (vac) | **3,458 m/s** | VehicleConfig() |
| SRB burn time @20% | **25.3 s** | VehicleConfig() |
| Booster sep | T+25s / 2.89 km / 253 m/s | sim |
| Core burnout | T+61s / 14.88 km / 8.31 km DR | sim |
| Velocity at burnout | 643 m/s (vH=492, vV=414) | sim |
| Pitch at burnout | 50° from vertical | sim |
| Apoapsis at burnout | 24.6 km (suborbital) | sim |
| Periapsis at burnout | −587 km (normal — Terrier finishes) | sim |
| Gravity losses | 531 m/s | sim |
| Drag losses | 33 m/s | sim |
| Target orbit | 80 × 80 km | design |
| Orbital speed @80km | 2,279 m/s | derived |
| TMI ΔV | ~856 m/s | design |
| Test suite | **163/163 green** | last run |

---

## Settled vehicle design — DO NOT REOPEN

These decisions have detailed engineering rationale. Treat them as fixed.

**SRB thrust limit: 20%**
Gives pad TWR 1.77, squarely inside the 1.4–1.8 target band. 45% (the
original incorrect value) produced dangerously high TWR ~2.5. Do not change.

**Core stage only gets partway — Terrier finishes by design**
The core (Swivel + FL-T800) reaches ~15 km / ~25 km apoapsis. The Terrier
then burns for the remaining ~1,800 m/s horizontal make-up to orbit. This
is intentional, not a contingency. The Terrier has 3,458 m/s total; needs
~1,800 for ascent completion + ~856 for TMI = ~2,656, leaving ~800 m/s margin.

**Hammer mounting: HIGH mount (nozzles at or above Swivel bell)**
Low mount causes plume impingement on the core. This is non-negotiable for
the physical model. The diagrams show the correct high-mount configuration.

**Service bay: centerline (inside the stack)**
A radially-mounted Telemachus antenna causes drag asymmetry and forward CoP
shift. Service bay on centreline eliminates this entirely. The bay mass (0.10 t)
is in `VehicleConfig.avionics_mass`, NOT in `extra_payload`.

**Fins: 4× Basic Fin on lower core tank, 45° off boosters**
Stay with the core after booster sep (unlike booster-mounted fins). The 45°
clocking is shown in the VIEW A-A plan inset on Sheet 1.

**`extra_payload = 0.0` (default)**
The service bay was previously double-counted here (P0-05 fix). Do not set
this back to 0.10. If you add genuine extra inert mass, use a non-zero value
explicitly but document what it represents.

---

## Critical constants — verified against KSP wiki

```python
# From sim/constants.py — do not change without re-verifying in-game

FULL_LF_FL_T800   = 360   # KSP units (1.8t at 0.005 t/unit, 9:11 LF:OX ratio)
                           # NOT 4000 — that was the P0-01 bug

SOLID_FUEL_2xHAMMER = 160 # KSP units (2 × 80 units; each Hammer 0.60t / 0.0075 t/unit)
                           # NOT 600 — that was the P0-02 bug

KM_PER_DEG_KERBIN = 10.47  # km per degree longitude at equator (R=600km)
                            # NOT 111.12 (Earth) — that was the P0-03 bug
```

---

## Pitch convention — important and confusing

Two different conventions are in use and must not be mixed:

| Convention | 0° | 90° | Used by |
|---|---|---|---|
| `pitch_from_v` (sim) | Straight up | Horizontal | `TrajectoryPoint.pitch_from_v` |
| KSP / Telemachus | Horizontal | Straight up | `p.pitch` in telemetry state |

Convert: `ksp_pitch = 90 - pitch_from_v`

`SimulatedTelemetry` outputs KSP convention (fixed in P0-04).
The advisory engine receives KSP convention and converts internally:
`actual_pitch_from_vertical = 90.0 - ksp_pitch`

---

## Simulation package API

```python
from sim import run_ascent, VehicleConfig, PITCH_PROGRAMS

# Baseline run
result = run_ascent()
print(result.apoapsis_km, result.periapsis_km)

# Custom vehicle
cfg = VehicleConfig(booster_pct=25, n_boosters=3)
result = run_ascent(cfg, pitch_program=PITCH_PROGRAMS['shallow'])

# Trajectory points
for pt in result.points:            # sampled every 0.5s
    print(pt.t, pt.altitude/1000,   # m → km
          pt.downrange/1000,        # m → km
          pt.velocity,
          pt.pitch_from_v,          # degrees from vertical
          pt.apoapsis,              # km (may be negative = suborbital)
          pt.phase)                 # 'BOOST' or 'CORE'

# Key events
result.booster_sep.t                # seconds from liftoff
result.core_burnout.v_horiz        # horizontal speed at burnout (m/s)
result.drag_loss_total              # m/s
result.grav_loss_total              # m/s

# JSON output
from sim.ascent_sim import result_to_dict
import json
print(json.dumps(result_to_dict(result, cfg), indent=2))

# CLI
python -m sim.ascent_sim --hammer-pct 20 --json
python -m sim.ascent_sim --compare nominal steep shallow late_turn
```

Available pitch programs: `nominal`, `steep`, `shallow`, `late_turn`.
Custom programs: callable `(altitude_m) -> Optional[float]` returning
flight-path angle from horizontal in degrees, or `None` for free gravity turn.

---

## Flight director / advisory system

```python
# nominal_compare.py public surface

from mission_control.nominal_compare import (
    NominalTrajectory, FlightDirector, FlightPhase,
    detect_phase, assess_gates, generate_advisory,
)

# Load nominal (runs the sim once at startup)
nominal = NominalTrajectory.load()
fd = FlightDirector(nominal)

# On each telemetry update (state is the dict from TelematicusClient.get_state())
result = fd.update(state)
# Returns:
# {
#   'phase': 'TERRIER',
#   'advisory': {'level': 'CAUTION', 'action': 'PITCH TOWARD HORIZON  (+22° STEEP)',
#                'reason': '...', 'urgent': False},
#   'gates': [{'phase': 'CORE B/O', 'status': 'GO', 'detail': '24.6 km Ap'}, ...],
#   'nominal_at_alt': {'altitude_km': 15.0, 'apoapsis_km': 24.1, ...},
# }
```

Advisory levels: `NOMINAL`, `CAUTION`, `WARNING`, `ABORT`.

Go/No-Go gate statuses: `GO`, `MARGINAL`, `NO-GO`, `NOT-YET`.

**Phase detection** uses altitude + apoapsis thresholds + prev_phase hysteresis
(NOT MET threshold — the MET-based split was P1-02, now fixed).

**ABORT gate** requires `met > 70s` guard (P1-05 fix) — cannot fire in the
first 7 seconds after Terrier ignition even if pe and apo are bad.

**Apoapsis stall detection** (P2-08): pass `prev_apo_km` to `generate_advisory()`
for rate-of-change alerting. `FlightDirector.update()` does this automatically.

---

## Telemachus / mission control

```python
# Live KSP
from mission_control.telemachus_client import TelematicusClient
client = TelematicusClient(host='192.168.1.X', port=8085, rate_ms=200)
client.start()
state = client.get_state()  # returns dict with: altitude, apoapsis, periapsis,
                             # velocity, v_vert, v_horiz, pitch, heading, roll,
                             # mission_time, throttle, liquid_fuel, solid_fuel, ...
traj  = client.get_trajectory()  # list of {t, altitude_km, downrange_km, ...}

# Simulation mode (no KSP)
from mission_control.telemachus_client import SimulatedTelemetry
client = SimulatedTelemetry(rate_ms=200)
client.start()
```

Telemachus WebSocket: `ws://[host]:8085/datalink`
Subscription format: `{"rate": 200, "+": ["v.altitude", "o.ApA", ...]}`
Topic list: see `SUBSCRIBED_TOPICS` in telemachus_client.py — adjust if your
plugin version uses different names.

**Downrange computation** uses `compute_downrange_km(lon_delta_deg, lat_deg)` —
Kerbin-correct (10.47 km/deg × cos(lat)), NOT Earth scale (P0-03 fix). Launch
longitude is captured automatically at MET < 3s.

**Trajectory auto-clear**: client detects MET reset (new flight) by watching for
`met < 5s` after the last trajectory point had `t > 30s`.

---

## Diagram system

Four SVG sheets, all valid XML (verified with `xml.dom.minidom`).
Design system lives in `diagrams/dsys.py`:

```python
from diagrams.dsys import (
    PANEL, INK, INK_SOFT, INK_FAINT,  # greys
    BLUEPRINT,                          # NASA blue (#1e3a5c-ish)
    SAFETY_RED,                         # red for abort/warning
    TEAL, VIOLET,                       # mission events
    FILL_BASE, FILL_BLUE,              # fill colours
    FONT_HEAD, FONT_MONO, FONT_BODY,   # typography
    rect, line, text, circle, path, poly, ellipse,
    hatch_defs, sheet_frame, mission_insignia,
    title_block, balloon, leader, stage_badge,
)
```

Sheet numbering: 1 of 4 through 4 of 4. If adding a Sheet 5, update all
title blocks. DWG numbers follow pattern `KSP-PRS1-XX-NN`.

**DO NOT add `fill="none"` in `extra=` parameter of `path()`** — `path()`
already emits `fill="none"` by default, producing a duplicate attribute
(this was the P0-XML bug caught by the strict SVG parser).

Regenerate + validate:
```bash
python diagrams/generate_diagrams.py
python -c "
import xml.dom.minidom as m
for f in ['sheet1','sheet2','sheet3','sheet4']:
    m.parse(f'{f}.svg'); print(f'{f}: valid')
"
```

---

## Engineering review status

All 30 findings from `ENGINEERING_REVIEW.md` are resolved.

```
tests/test_p0_regressions.py    17 tests  — P0 critical fixes validated
tests/test_p1_regressions.py    11 tests  — P1 high-priority fixes validated
tests/test_p2_p3_regressions.py 21 tests  — P2/P3 fixes validated
─────────────────────────────────────────────────────
Total                           49 tests  ALL PASSING
tests/test_scenario.py          88 tests  — scenario system + UI viewport + layout + graphical elements + timeline bands
tests/test_ballistic_projection.py 34 tests — ballistic projection + drag
─────────────────────────────────────────────────────
Total                          171 tests  ALL PASSING
```

**Before making any change**: run the full suite and confirm 171/171 green.
**When adding a feature or fixing a bug**: write the test first (red), then fix (green).

The engineering review describes _why_ each fix was made, not just what changed.
Read the relevant section before touching the associated code.

---

## Scriptable vehicle launch simulator

The scenario system enables rapid what-if analysis: load different vehicle
configs and pitch programs through the web UI or CLI, and replay results
through the full mission control pipeline (FlightDirector advisories,
go/no-go gates, web visualization).

### Architecture

```
LaunchScenario (scenario.py) → VehicleConfig + pitch program
  → run_ascent() → trajectory points
    → ScriptedTelemetry (telemachus_client.py) — drop-in replacement
      → broadcast_loop reads get_state() (unchanged)
        → FlightDirector.update() (unchanged)
          → Socket.IO → Web UI
```

### Key files

- `mission_control/scenario.py` — `LaunchScenario` dataclass + `PRESET_SCENARIOS`
- `mission_control/telemachus_client.py` — `ScriptedTelemetry` class (appended)
- `mission_control/server.py` — `/api/scenario/*` routes + `MissionSession`
- `mission_control/static/index.html` — scenario control panel + `/api/constants`
- `tests/test_scenario.py` — 88 tests covering model, playback, API, integration, UI viewport, layout, graphical elements, timeline bands

### Usage

```bash
# CLI: start with preset scenario
python mission_control/server.py --scenario nominal
python mission_control/server.py --scenario steep_ascent

# API: load preset
curl -X POST http://localhost:5000/api/scenario/load \
  -H 'Content-Type: application/json' -d '{"preset": "steep_ascent"}'

# API: load custom params
curl -X POST http://localhost:5000/api/scenario/load \
  -H 'Content-Type: application/json' \
  -d '{"booster_type":"thumper","n_boosters":3,"booster_pct":25,"pitch_program":"steep"}'

# Playback controls
curl -X POST http://localhost:5000/api/scenario/start
curl -X POST http://localhost:5000/api/scenario/speed -d '{"speed": 5}'
```

### Preset scenarios

| Key | Description | Purpose |
|---|---|---|
| `nominal` | Perseus 1 default | Baseline |
| `steep_ascent` | Steep pitch program | Higher apoapsis, more gravity loss |
| `shallow_ascent` | Shallow pitch program | Lower apoapsis, less gravity loss |
| `late_turn` | Late turn pitch program | Delayed gravity turn |
| `heavy_payload` | +0.5t extra payload | Performance margin testing |
| `thumper_variant` | Thumper boosters @15% | Alternative SRB |
| `high_twr` | Hammer @45% thrust | Over-powered launch |
| `abort_steep` | Steep + 45% + 10% noise | Abort training |

### Constants centralization

Kerbin physics constants (`R_KERBIN`, `MU_KERBIN`, `ATM_CEIL`, etc.) are
served from `/api/constants` so the JS ballistic projection engine stays
in sync with the Python sim. The frontend loads these on Socket.IO connect.

### Server state

All mutable server state lives in `MissionSession` (`server.py:session`).
Access via `session.telemetry_client`, `session.flight_director`, etc.
The module-level `__getattr__` provides backward-compatible reads.

### Test suite

```bash
# Full suite: 171 tests (49 regression + 88 scenario + 34 ballistic)
cd /home/user/KSPDirector/code
python -m unittest tests.test_p0_regressions tests.test_p1_regressions \
    tests.test_p2_p3_regressions tests.test_scenario \
    tests.test_ballistic_projection -v
```

---

## Known remaining rough edges (not bugs, just not polished)

These were evaluated and left intentionally — not worth the time vs the mission:

- **`generate_diagrams.py` consolidation** (P2-02): the AST-based import
  stripping is documented as the correct approach in the test but the generator
  currently uses a manual approach that works. If you regenerate and get an
  `IndentationError`, the regex patch in the build script is the fix.

- **Sheet 3 TRAJECTORY constant** (P3-07): provenance comment is present.
  Run `python tools/update_sheet3_trajectory.py` if sim params change to
  regenerate the trajectory data embedded in the diagram.

- **Houston UI integration** (P2/P3-08): the web interface has the hooks
  (`window.MissionControl`, CSS `--mc-*` vars, `data-panel` attrs, custom
  events) but has not been tested inside an actual Houston UI instance.

- **Telemachus topic names** vary between plugin versions. If subscriptions
  produce no data, check `http://[ksp-host]:8085/telemachus/datalink` and
  adjust `SUBSCRIBED_TOPICS` in telemachus_client.py.

---

## Conventions for new work

**Adding a new sim parameter**: add to `PERSEUS_1_DEFAULT` in `constants.py`
first, then wire in `VehicleConfig`. Never hardcode a vehicle parameter in two
places — one source of truth.

**Adding a new advisory condition**: add to `generate_advisory()` in
`nominal_compare.py`. Write the test scenario in `test_p2_p3_regressions.py`
first. Advisory levels in priority order: `ABORT` > `WARNING` > `CAUTION` > `NOMINAL`.

**Adding a new diagram sheet**: copy sheet4.py as a template. Update the sheet
count in ALL existing title blocks (`1 OF N` etc). Validate XML after generation.

**Changing the pitch program**: add to `PITCH_PROGRAMS` dict in `trajectory.py`.
Callable signature: `(altitude_m: float) -> Optional[float]` — returns
flight-path angle from horizontal in degrees, or `None` for free gravity turn.

**Test naming**: follow the `test_pNNN_description` pattern so the review
finding is traceable from the test name.
