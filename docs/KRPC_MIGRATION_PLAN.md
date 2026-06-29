# COA C Implementation Plan: Migrate from Telemachus to kRPC

## Executive Summary

Replace the Telemachus WebSocket telemetry client with a kRPC-based client,
enabling arbitrary vehicle support, user-defined mission plans, richer
telemetry, and eliminating Telemachus topic-naming fragility. The Python sim,
flight director, web UI, scenario system, and test suite are preserved with
targeted modifications.

**Estimated total effort: 8–12 developer-days across 5 phases.**

---

## Phase 1: kRPC Client Drop-In Replacement ✓ COMPLETE

**Goal:** Replace `TelematicusClient` with a `KRPCClient` class that produces
the same `get_state()` / `get_trajectory()` dict format, so the rest of the
pipeline (FlightDirector, server.py broadcast loop, web UI) works unchanged.

### Tasks

| # | Task | Files | Status |
|---|------|-------|--------|
| 1.1 | Add `krpc` to requirements.txt | `requirements.txt` | Done |
| 1.2 | Create `KRPCClient` class | `mission_control/krpc_client.py` | Done (270 lines) |
| 1.3 | Wire into server.py as a third telemetry source | `mission_control/server.py` | Done (`--krpc-host` flag) |
| 1.4 | Write unit tests for KRPCClient | `tests/test_krpc_client.py` | Done (31 tests, all pass) |
| 1.5 | Integration test with live KSP | Manual | Pending (requires KSP + kRPC) |

### KRPCClient Design

```python
class KRPCClient:
    """Drop-in replacement for TelematicusClient using kRPC streams."""

    def __init__(self, host='127.0.0.1', rpc_port=50000, stream_port=50001,
                 rate_hz=5):
        ...

    def start(self):
        """Connect to kRPC, set up streams, start background update thread."""
        self._conn = krpc.connect(name='Perseus MC', address=self.host,
                                  rpc_port=self.rpc_port,
                                  stream_port=self.stream_port)
        self._vessel = self._conn.space_center.active_vessel
        self._setup_streams()

    def _setup_streams(self):
        """Create kRPC streams for all needed telemetry fields."""
        flight = self._vessel.flight(self._vessel.orbit.body.reference_frame)
        orbit = self._vessel.orbit
        control = self._vessel.control

        self._streams = {
            'altitude':     self._conn.add_stream(getattr, flight, 'mean_altitude'),
            'v_vert':       self._conn.add_stream(getattr, flight, 'vertical_speed'),
            'surface_speed':self._conn.add_stream(getattr, flight, 'speed'),
            'velocity':     self._conn.add_stream(getattr, orbit, 'speed'),
            'apoapsis':     self._conn.add_stream(getattr, orbit, 'apoapsis_altitude'),
            'periapsis':    self._conn.add_stream(getattr, orbit, 'periapsis_altitude'),
            'inclination':  self._conn.add_stream(getattr, orbit, 'inclination'),
            'eccentricity': self._conn.add_stream(getattr, orbit, 'eccentricity'),
            'time_to_ap':   self._conn.add_stream(getattr, orbit, 'time_to_apoapsis'),
            'time_to_pe':   self._conn.add_stream(getattr, orbit, 'time_to_periapsis'),
            'pitch':        self._conn.add_stream(getattr, flight, 'pitch'),
            'heading':      self._conn.add_stream(getattr, flight, 'heading'),
            'roll':         self._conn.add_stream(getattr, flight, 'roll'),
            'mission_time': self._conn.add_stream(getattr, self._vessel, 'met'),
            'throttle':     self._conn.add_stream(getattr, control, 'throttle'),
            'mass':         self._conn.add_stream(getattr, self._vessel, 'mass'),
            'g_force':      self._conn.add_stream(getattr, flight, 'g_force'),
            'latitude':     self._conn.add_stream(getattr, flight, 'latitude'),
            'longitude':    self._conn.add_stream(getattr, flight, 'longitude'),
            'dynamic_pressure': self._conn.add_stream(getattr, flight, 'dynamic_pressure'),
            'mach':         self._conn.add_stream(getattr, flight, 'mach'),
            'atm_density':  self._conn.add_stream(getattr, flight, 'atmosphere_density'),
        }

    def get_state(self) -> dict:
        """Read all streams and return state dict matching Telemachus format."""
        state = {}
        for key, stream in self._streams.items():
            state[key] = stream()
        # Derived fields
        state['v_horiz'] = math.sqrt(max(0, state['surface_speed']**2 - state['v_vert']**2))
        # Resources
        state['liquid_fuel'] = self._vessel.resources.amount('LiquidFuel')
        state['solid_fuel'] = self._vessel.resources.amount('SolidFuel')
        state['liquid_fuel_max'] = self._vessel.resources.max('LiquidFuel')
        state['solid_fuel_max'] = self._vessel.resources.max('SolidFuel')
        # ... remaining fields
        state['connected'] = True
        return state

    # get_trajectory(), clear_trajectory(), start(), stop() —
    # same interface as TelematicusClient
```

### Key Decisions

- **Streams vs polling:** Use kRPC streams for high-frequency data (position,
  velocity, attitude). Use direct RPC calls for low-frequency data (resources,
  part queries) — called once per update cycle, not streamed.
- **Reference frame:** Use `vessel.orbit.body.reference_frame` for `Flight`
  to get surface-relative attitude (matching Telemachus `n.pitch` convention).
  kRPC's `flight.pitch` is degrees from horizon (-90 to +90), same as
  Telemachus `n.pitch` — no convention conversion needed.
- **Thread model:** Single background thread polls streams at `rate_hz`,
  builds state dict, appends to trajectory — same pattern as TelematicusClient.

---

## Phase 2: Vehicle Detection + Mission Planning

**Goal:** Auto-detect the active vessel's configuration from kRPC, accept a
user-provided mission plan (target orbit, pitch preference), generate a
nominal trajectory from detected vehicle + plan, and feed that nominal into
the FlightDirector pipeline.

This phase bridges the gap between "raw kRPC telemetry" (Phase 1) and
"vehicle-aware flight direction" (Phase 3). The key insight is that the
nominal trajectory — not the vehicle spec — is what drives FlightDirector
thresholds.

### Tasks

| # | Task | Files | LOE | Notes |
|---|------|-------|-----|-------|
| 2.1 | Create `VehicleProfile` from kRPC part data | `mission_control/vehicle_detect.py` (new) | 6–8 hr | See design below |
| 2.2 | Compute per-stage ΔV from part data | Same file | 4–6 hr | Tsiolkovsky from parts |
| 2.3 | Create `MissionPlan` dataclass | `mission_control/mission_plan.py` (new) | 2–3 hr | Target orbit, pitch pref, staging overrides |
| 2.4 | `VehicleProfile.to_vehicle_config()` bridge | `mission_control/vehicle_detect.py` | 3–4 hr | Convert detected stages → sim-compatible config |
| 2.5 | Generalize `run_ascent()` for N stages | `sim/trajectory.py`, `sim/ascent_sim.py` | 10–14 hr | Currently assumes BOOST/CORE; needs N-stage |
| 2.6 | Nominal from detected vehicle + mission plan | `mission_control/nominal_compare.py` | 3–4 hr | `run_ascent(profile.to_vehicle_config(), plan)` |
| 2.7 | `/api/mission-plan` endpoint | `mission_control/server.py` | 2–3 hr | Accept/update target orbit from web UI |
| 2.8 | Tests for vehicle detection + mission plan | `tests/test_vehicle_detect.py` (new) | 4–6 hr | Mock kRPC vessel, N-stage sim runs |
| 2.9 | Integration test with Perseus 1 in KSP | Manual | 1–2 hr | Verify detected config matches known values |

**Subtotal: 4–5.5 days**

### MissionPlan Design

```python
@dataclass
class MissionPlan:
    """User-provided mission parameters that pair with a detected vehicle."""

    target_orbit_alt_km: float = 80.0
    target_inclination_deg: float = 0.0
    pitch_program: str = "auto"      # "auto", "steep", "shallow", or custom callable name
    staging_overrides: dict = field(default_factory=dict)  # manual corrections if auto-detect is wrong

    @classmethod
    def from_dict(cls, data: dict) -> 'MissionPlan':
        """Build from API request body."""
        ...

    def validate(self) -> list[str]:
        """Return list of validation errors (empty = valid)."""
        errors = []
        if not (10 <= self.target_orbit_alt_km <= 1000):
            errors.append("target_orbit_alt_km must be 10-1000")
        if not (-180 <= self.target_inclination_deg <= 180):
            errors.append("target_inclination_deg must be -180 to 180")
        return errors
```

The `MissionPlan` is persisted in `MissionSession` alongside the
`VehicleProfile` and the generated nominal trajectory.

### Vehicle Detection Design

```python
@dataclass
class StageProfile:
    """Per-stage breakdown from kRPC parts inspection."""
    index: int
    label: str                # auto-generated: "SRB", "Core", "Upper", or "Stage N"
    engines: list[str]        # engine part names
    fuel_types: list[str]     # "SolidFuel", "LiquidFuel+Oxidizer"
    dv_vac: float             # m/s
    dv_asl: float             # m/s
    thrust_vac: float         # kN
    thrust_asl: float         # kN
    isp_vac: float            # s
    isp_asl: float            # s
    burn_time: float          # s
    wet_mass: float           # tonnes
    dry_mass: float           # tonnes
    fuel_mass: float          # tonnes

@dataclass
class VehicleProfile:
    """Auto-detected vehicle configuration from kRPC part tree."""

    total_mass: float           # tonnes
    dry_mass: float             # tonnes
    stages: list[StageProfile]  # per-stage breakdown, firing order
    n_stages: int

    @classmethod
    def from_vessel(cls, vessel) -> 'VehicleProfile':
        """Inspect kRPC vessel object and build profile."""
        stages = []
        for stage_num in range(vessel.control.current_stage, -1, -1):
            engines = [p for p in vessel.parts.in_decouple_stage(stage_num)
                       if p.engine is not None]
            if not engines:
                continue
            fuel = vessel.resources_in_decouple_stage(stage_num, cumulative=False)
            # ... build StageProfile with engine ISP, thrust, fuel mass
            stages.append(StageProfile(...))
        return cls(stages=stages, total_mass=vessel.mass,
                   dry_mass=..., n_stages=len(stages))

    def to_vehicle_config(self) -> 'VehicleConfig':
        """Convert detected profile to a VehicleConfig the sim can run.

        For ≤3 stage vehicles (boosters + core + upper), maps directly to
        the existing VehicleConfig fields. For N>3 stages, produces a
        GeneralizedVehicleConfig (see Phase 2.5).
        """
        ...

    def stage_labels(self) -> list[str]:
        """Human-readable stage labels for the UI."""
        return [s.label for s in self.stages]
```

### Nominal Trajectory Generation

The critical pipeline for producing a nominal from detected vehicle + plan:

```
KRPCClient.get_vessel() → VehicleProfile.from_vessel()
                              ↓
                        MissionPlan (user-provided target orbit, pitch pref)
                              ↓
                        profile.to_vehicle_config()
                              ↓
                        run_ascent(config, pitch_program)
                              ↓
                        NominalTrajectory(result.points)
                              ↓
                        FlightDirector(nominal, config_from_nominal)
```

The FlightDirector config (Phase 3) is derived from the *nominal trajectory
run*, not from the vehicle profile directly. Stage burnout altitudes, expected
apoapsis at each stage transition, and fuel percentage thresholds all come
from where staging events occur in the nominal trajectory.

### Per-Stage ΔV Computation

kRPC does not expose KSP's built-in `DeltaVStageInfo`. We compute it:

```python
def compute_stage_dv(vessel, stage_num: int) -> float:
    """Compute vacuum ΔV for a single stage using the Tsiolkovsky equation."""
    engines = [p.engine for p in vessel.parts.in_decouple_stage(stage_num)
               if p.engine is not None]
    if not engines:
        return 0.0

    # Weighted average ISP (thrust-weighted harmonic mean)
    total_thrust = sum(e.max_vacuum_thrust for e in engines)
    if total_thrust == 0:
        return 0.0
    avg_isp = total_thrust / sum(e.max_vacuum_thrust / e.vacuum_specific_impulse
                                  for e in engines if e.vacuum_specific_impulse > 0)

    # Fuel mass in this stage
    resources = vessel.resources_in_decouple_stage(stage_num, cumulative=False)
    fuel_mass = (resources.amount('LiquidFuel') * 0.005 +
                 resources.amount('Oxidizer') * 0.005 +
                 resources.amount('SolidFuel') * 0.0075)

    # Start/end mass (cumulative includes upper stages)
    resources_cum = vessel.resources_in_decouple_stage(stage_num, cumulative=True)
    start_mass = vessel.mass  # simplified; proper impl uses cumulative stage masses
    end_mass = start_mass - fuel_mass

    if end_mass <= 0 or start_mass <= 0:
        return 0.0

    return avg_isp * 9.80665 * math.log(start_mass / end_mass)
```

**Edge cases to handle:**
- Fuel crossfeed (asparagus staging) — `cumulative=True` on `resources_in_decouple_stage`
- Multi-engine stages with different ISPs — thrust-weighted harmonic mean
- SRBs with thrust limiters — affect burn time but not ΔV
- Empty/separator stages (decouplers only, no fuel)

**Accuracy expectation:** Within ~5% of KSP's built-in readout for typical
vehicles. Crossfeed-heavy designs (asparagus) may diverge more. For Perseus 1
specifically, this should be exact since it has simple serial staging.

### Sim Generalization (Task 2.5)

The current sim assumes a two-phase ascent (BOOST → CORE). Generalizing to
N stages requires:

1. **`trajectory.py`**: The integrator loop currently switches from BOOST to
   CORE when SRB fuel depletes. Replace with a general staging model: iterate
   through `StageProfile` list, transition when each stage's fuel mass reaches
   zero, update thrust/ISP/mass accordingly. Phase labels become `STAGE_0`,
   `STAGE_1`, ... (or use `StageProfile.label` if available).

2. **`ascent_sim.py`**: `run_ascent()` currently takes a `VehicleConfig`
   designed around Perseus 1's 3-stage stack. Add a `GeneralizedVehicleConfig`
   that accepts an ordered list of stages, each with engine stats and fuel.
   The existing `VehicleConfig` becomes a factory that produces the
   generalized form for backward compatibility.

3. **Pitch program selection**: For arbitrary vehicles, the pitch program
   needs to adapt to TWR. High-TWR vehicles (>2.0) need steeper initial
   climbs; low-TWR vehicles (<1.3) need shallower turns. The "auto" option
   in `MissionPlan` selects from existing programs based on pad TWR:
   - TWR > 2.0: `steep`
   - 1.4 ≤ TWR ≤ 2.0: `nominal`
   - TWR < 1.4: `shallow`

   Custom pitch programs remain available for users who want precise control.

4. **Phase names**: The FlightDirector currently uses hardcoded phase names
   (`BOOST`, `CORE`, `TERRIER`, `CIRCULARIZE`, `ORBIT`). These become
   dynamic: `STAGE_0`, `STAGE_1`, ..., `CIRCULARIZE`, `ORBIT`. The UI
   displays `StageProfile.label` instead of hardcoded strings.

**This is the highest-risk task in the plan.** The sim's physics integrator is
general, but the staging logic and phase model are tightly coupled to
Perseus 1. Estimate 1.5–2 days for this task alone. The existing test suite
(325+ non-browser tests) must remain green throughout — backward compatibility
via the existing `VehicleConfig` producing the same results is the acceptance
criterion.

### Inclination Limitation

The current sim is 2D (vertical + downrange). It does not model orbital
inclination — all trajectories assume equatorial launch heading 090°.

For non-equatorial orbits, inclination affects launch heading (not 090°) and
increases the required ΔV slightly (cosine loss from non-equatorial Kerbin
rotation). This is a minor effect for low inclinations but significant for
polar orbits (~174 m/s penalty at Kerbin).

**For now, inclination is a display/advisory parameter only** — stored in
`MissionPlan`, shown in the UI, but not modeled in the sim. The nominal
trajectory assumes equatorial. This is acceptable because:
- The ascent *profile* (altitude vs. time, staging events) is nearly identical
  for any inclination — only heading differs
- The FlightDirector's go/no-go gates care about altitude/apoapsis/fuel, not
  heading
- Heading advisory ("TURN TO 045° FOR POLAR ORBIT") can be added as a simple
  advisory without changing the trajectory model

Full 3D trajectory modeling is future work.

---

## Phase 3: Derive FlightDirector Config from Nominal Trajectory

**Goal:** Remove Perseus 1-specific hardcoded thresholds from
`nominal_compare.py`. Derive all phase boundaries and go/no-go gates from
the nominal trajectory run (Phase 2.6), so the flight director works with
any vehicle + mission plan combination.

The key principle: **the nominal trajectory is the source of truth for
thresholds, not the vehicle spec.** You detect the vehicle, run the sim,
and the trajectory tells you where each stage burns out, what apoapsis to
expect at each transition, and when circularization should begin. Those
trajectory events become the FlightDirector's configuration.

### Tasks

| # | Task | Files | LOE | Notes |
|---|------|-------|-----|-------|
| 3.1 | Create `FlightDirectorConfig` dataclass | `mission_control/nominal_compare.py` | 2–3 hr | Extract all 20+ hardcoded thresholds |
| 3.2 | `FlightDirectorConfig.from_nominal()` | Same | 4–6 hr | Derive config from trajectory staging events |
| 3.3 | Accept config in `FlightDirector.__init__` | Same | 1–2 hr | Default = current Perseus 1 values |
| 3.4 | Dynamic phase names | Same | 2–3 hr | `STAGE_0`...`STAGE_N` + `CIRCULARIZE` + `ORBIT` |
| 3.5 | Update all existing tests | `tests/test_p*.py`, `tests/test_scenario.py` | 2–3 hr | Default config = backward compatible |
| 3.6 | New tests for non-Perseus configs | `tests/test_flight_director_config.py` (new) | 3–4 hr | 2-stage, 4-stage, no-booster vehicles |

**Subtotal: 2–3 days**

### Thresholds to Extract

```python
@dataclass
class FlightDirectorConfig:
    """All tunable thresholds for the flight director.

    Default values match current Perseus 1 hardcoded behavior for backward
    compatibility. For arbitrary vehicles, use from_nominal() to derive
    thresholds from a nominal trajectory run.
    """

    # Phase transitions — derived from nominal trajectory staging events
    stage_transitions: list[StageTransition] = field(default_factory=list)
    # Each StageTransition: {phase_name, alt_m, apo_km, met_s}
    # Example for Perseus 1:
    #   [("BOOST", 0, 0, 0), ("CORE", 2890, 5.2, 25.3), ("TERRIER", 17000, 32, 63)]

    # General thresholds
    target_orbit_alt_km: float = 80.0
    orbit_pe_km: float = 70                 # periapsis threshold for ORBIT phase
    circularize_apo_km: float = 60          # apoapsis threshold for CIRCULARIZE
    circularize_pe_km: float = 65           # periapsis ceiling for CIRCULARIZE
    circularize_vvert_ms: float = 50        # |v_vert| ceiling for CIRCULARIZE

    # Advisory generation
    abort_met_guard_s: float = 70.0         # MET before ABORT gate can fire
    pitch_deviation_threshold: float = 12.0 # degrees off nominal → CAUTION

    # Go/No-Go gates — derived from nominal staging events
    gate_configs: list[GateConfig] = field(default_factory=list)
    # Each GateConfig: {name, phase, metric, go_threshold, marginal_threshold}

    @classmethod
    def for_perseus_1(cls) -> 'FlightDirectorConfig':
        """Return the default Perseus 1 configuration (backward compatible)."""
        return cls(
            stage_transitions=[
                StageTransition("BOOST", 0, 0, 0),
                StageTransition("CORE", 2890, 5.2, 25.3),
                StageTransition("TERRIER", 17000, 32.0, 63.0),
            ],
            target_orbit_alt_km=80.0,
            abort_met_guard_s=70.0,
            # ... remaining Perseus 1 values
        )

    @classmethod
    def from_nominal(cls, trajectory_result, mission_plan) -> 'FlightDirectorConfig':
        """Derive all thresholds from a nominal trajectory run.

        Scans trajectory points for staging events (phase transitions),
        extracts altitude/apoapsis/MET at each transition, and builds
        phase boundaries + gate thresholds with appropriate margins.
        """
        transitions = []
        prev_phase = None
        for pt in trajectory_result.points:
            if pt.phase != prev_phase:
                transitions.append(StageTransition(
                    phase_name=pt.phase,
                    alt_m=pt.altitude,
                    apo_km=pt.apoapsis or 0,
                    met_s=pt.t,
                ))
            prev_phase = pt.phase

        # Gate thresholds: 80% of nominal altitude/apoapsis = MARGINAL,
        # 90% = GO. Derived from trajectory, not magic numbers.
        gates = []
        for i, trans in enumerate(transitions[1:], 1):
            gates.append(GateConfig(
                name=f"{transitions[i-1].phase_name} B/O",
                phase=transitions[i-1].phase_name,
                metric="apoapsis_km",
                go_threshold=trans.apo_km * 0.9,
                marginal_threshold=trans.apo_km * 0.5,
            ))

        return cls(
            stage_transitions=transitions,
            target_orbit_alt_km=mission_plan.target_orbit_alt_km,
            abort_met_guard_s=transitions[-1].met_s + 7.0,
            gate_configs=gates,
        )
```

### Dynamic Phase Names

Current hardcoded phases: `BOOST`, `CORE`, `TERRIER`, `CIRCULARIZE`, `ORBIT`.

For arbitrary vehicles, phase names during powered ascent become dynamic:
- `STAGE_0`, `STAGE_1`, `STAGE_2`, ... (or `StageProfile.label` from Phase 2)
- `CIRCULARIZE` — still a fixed concept (low v_vert + high pe)
- `ORBIT` — still a fixed concept (pe > threshold)

`detect_phase()` currently uses hardcoded altitude/apoapsis thresholds for
`BOOST→CORE` and `CORE→TERRIER` transitions. With `FlightDirectorConfig`,
it scans `stage_transitions` to find which phase boundary the current
altitude/apoapsis has crossed. The hysteresis logic (prev_phase) is preserved.

### Backward Compatibility Strategy

- `FlightDirectorConfig()` with no args produces exact current behavior
- `FlightDirector(nominal)` still works (uses default config internally)
- `FlightDirector(nominal, config=FlightDirectorConfig.for_perseus_1())` is explicit
- All existing tests pass without modification (default config matches)
- `from_nominal()` with Perseus 1 trajectory produces values within 5% of
  the hardcoded defaults — verified by test

---

## Phase 4: UI for Arbitrary Vehicles + Mission Planning

**Goal:** Remove Perseus 1-specific labels from the web UI, add mission plan
input fields, and enable re-computation of the nominal trajectory when the
user changes their plan.

### Tasks

| # | Task | Files | LOE | Notes |
|---|------|-------|-----|-------|
| 4.1 | Serve vehicle profile via `/api/vehicle` | `server.py` | 1 hr | Stage names, fuel caps, ΔV |
| 4.2 | Load vehicle profile in JS on connect | `static/index.html` | 2–3 hr | Replace hardcoded stage labels |
| 4.3 | Dynamic fuel bar max values | `static/index.html` | 1 hr | Use `liquid_fuel_max` from state |
| 4.4 | Dynamic stage labels | `static/index.html` | 1–2 hr | "SRB" / "Core" / "Terrier" → from profile |
| 4.5 | Mission plan input panel | `static/index.html` | 3–4 hr | Target orbit alt/inc, pitch selector |
| 4.6 | "Compute Nominal" action | `static/index.html`, `server.py` | 2–3 hr | Re-run sim + update FD on plan change |
| 4.7 | Vehicle detection trigger | `server.py`, `krpc_client.py` | 1–2 hr | Re-detect on staging event or user request |
| 4.8 | Update Playwright tests | `tests/test_ui_playwright.py` | 3–4 hr | Dynamic labels, mission plan panel |

**Subtotal: 2–2.5 days**

### Mission Plan Panel Design

The Scenario panel in the web UI gains a "Mission Plan" section (visible when
in kRPC mode, not simulation mode):

```
┌─ MISSION PLAN ──────────────────────────────┐
│  Target Orbit:  [  80 ] km    Inc: [ 0.0 ]° │
│  Pitch Program: [nominal ▾]                  │
│  [ Detect Vehicle ]  [ Compute Nominal ]     │
│                                              │
│  Vehicle: 3 stages, 14.21t, pad TWR 1.77    │
│  Nominal Ap: 24.6 km (core B/O)             │
│  Est. ΔV to orbit: 2,656 m/s                │
└──────────────────────────────────────────────┘
```

- **Detect Vehicle** queries `KRPCClient` for the current vessel's part tree
  and rebuilds the `VehicleProfile`
- **Compute Nominal** runs `run_ascent()` with the detected vehicle +
  current plan parameters, regenerates the `NominalTrajectory` and
  `FlightDirectorConfig`, and pushes the updated nominal to all clients
- Both actions available via API: `POST /api/vehicle/detect`,
  `POST /api/mission-plan/apply`

### Re-Nominal Workflow

When the user changes target orbit or pitch program:

```
User changes target orbit → POST /api/mission-plan/apply
  → server updates MissionPlan in MissionSession
  → server calls profile.to_vehicle_config()
  → server calls run_ascent(config, plan.pitch_program)
  → server rebuilds NominalTrajectory + FlightDirectorConfig.from_nominal()
  → server emits Socket.IO "nominal" event with new trajectory
  → web UI replaces nominal overlay on trajectory plot + globe
```

This is essentially the same flow as loading a scenario preset, but triggered
by mission plan edits instead of preset selection. The existing
`broadcast_loop` continues to compare actual telemetry against the
(now-updated) nominal.

---

## Phase 5: kRPC Upstream Contribution (Per-Stage ΔV)

**Goal:** Contribute a per-stage ΔV API to kRPC, closing the gap that
requires our manual Tsiolkovsky computation (Phase 2.2).

### Background

- **GitHub issue #336** (open since 2016): requests per-stage ΔV. Linked
  to issue #311 which asked for server-side stage predictions to avoid
  expensive client-side fuel-feeding logic. No implementation has been
  attempted by any contributor.
- **KSP 1.12** added a built-in `DeltaVStageInfo` class that the stock
  staging UI reads. This is the data source we'd wrap.
- **kRPC license:** LGPLv3 — accepts contributions under the same license.
- **Maintainer:** djungelorm. Active but part-time. Last release v0.5.4
  shipped June 2024.

### kRPC Architecture (Relevant to This Contribution)

```
krpc/
├── core/src/Service/Attributes/     # Annotation definitions
│   ├── KRPCClassAttribute.cs        #   [KRPCClass(Service = "SpaceCenter")]
│   ├── KRPCPropertyAttribute.cs     #   [KRPCProperty]
│   ├── KRPCMethodAttribute.cs       #   [KRPCMethod]
│   └── KRPCEnumAttribute.cs         #   [KRPCEnum]
│
├── service/SpaceCenter/src/Services/
│   ├── Vessel.cs                    # Main vessel class — we add Stages property here
│   ├── Flight.cs                    # Flight telemetry (reference for patterns)
│   ├── Orbit.cs                     # Orbital mechanics (reference)
│   ├── Resources.cs                 # Per-stage resource access (existing precedent)
│   ├── Parts/
│   │   ├── Engine.cs                # Engine wrapper — PRIMARY REFERENCE IMPL (628 lines)
│   │   ├── Part.cs                  # Individual part wrapper
│   │   └── Parts.cs                 # Part collection with InDecoupleStage()
│   └── BUILD.bazel
│
├── service/SpaceCenter/test/        # Python integration tests (unittest)
│   └── test_parts_engine.py         # Engine test pattern to follow
│
├── tools/ServiceDefinitions/        # Extracts annotations → JSON service defs
├── client/python/                   # Auto-generated Python stubs
└── protobuf/                        # Protocol buffer schemas (generic)
```

**Key insight:** kRPC already has `Vessel.ResourcesInDecoupleStage(stage, cumulative)`
and `Parts.InDecoupleStage(stage)` — the infrastructure for per-stage queries
exists. We're adding a wrapper around KSP's `DeltaVStageInfo` using the same
pattern as `Engine.cs` wrapping `ModuleEngines`.

### Build System

kRPC uses **Bazel**. Required tooling:

```bash
# Prerequisites
# - Bazelisk (manages Bazel versions)
# - Mono / .NET SDK (for C# compilation)
# - Python 3.12+
# - KSP game DLLs in lib/ksp/ (see kRPC build docs)

# Build SpaceCenter service
bazel build //service/SpaceCenter

# Run SpaceCenter tests (requires KSP running with kRPC loaded)
bazel test //service/SpaceCenter:test

# Build everything
bazel build //:krpc

# Docker alternative (avoids local toolchain setup)
docker pull ghcr.io/krpc/buildenv:latest
```

**First-time build pain:** Setting up `lib/ksp/` with the correct KSP
assemblies and getting Mono symlinked properly is the main friction point.
The Docker image sidesteps this.

### Implementation Plan

#### Task 5.1: Create `Stage.cs` Wrapper Class

**File:** `service/SpaceCenter/src/Services/Stage.cs` (new, ~180 lines)

**Pattern:** Follow `Engine.cs` — store a vessel ID + stage number, look up
`DeltaVStageInfo` on each property access.

```csharp
using System;
using KRPC.Service.Attributes;
using KRPC.SpaceCenter.ExtensionMethods;
using KRPC.Utils;

namespace KRPC.SpaceCenter.Services
{
    /// <summary>
    /// Represents a single stage in a vessel's staging sequence.
    /// Provides delta-v, mass, thrust, ISP, and burn time predictions
    /// from KSP's built-in stage calculator.
    /// </summary>
    /// <remarks>
    /// Obtained from <see cref="Vessel.Stages"/> or
    /// <see cref="Vessel.GetStageInfo"/>.
    /// </remarks>
    [KRPCClass(Service = "SpaceCenter", GameScene = GameScene.Flight)]
    public class Stage : Equatable<Stage>
    {
        readonly Guid vesselId;
        readonly int stageNumber;

        internal Stage(global::Vessel vessel, int stage)
        {
            if (ReferenceEquals(vessel, null))
                throw new ArgumentNullException(nameof(vessel));
            vesselId = vessel.id;
            stageNumber = stage;
        }

        public override bool Equals(Stage other)
        {
            return !ReferenceEquals(other, null) &&
                   vesselId == other.vesselId &&
                   stageNumber == other.stageNumber;
        }

        public override int GetHashCode()
        {
            return vesselId.GetHashCode() ^ stageNumber.GetHashCode();
        }

        internal global::Vessel InternalVessel
        {
            get { return FlightGlobalsExtensions.GetVesselById(vesselId); }
        }

        // Helper: get KSP's DeltaVStageInfo for this stage, or null
        DeltaVStageInfo GetStageInfo()
        {
            var vessel = InternalVessel;
            if (vessel == null || vessel.VesselDeltaV == null)
                return null;
            return vessel.VesselDeltaV.GetStage(stageNumber);
        }

        /// <summary>
        /// The stage number.
        /// </summary>
        [KRPCProperty]
        public int Number
        {
            get { return stageNumber; }
        }

        /// <summary>
        /// Delta-v of the stage in vacuum, in meters per second.
        /// </summary>
        [KRPCProperty]
        public double DeltaVVacuum
        {
            get
            {
                var info = GetStageInfo();
                return info != null ? info.deltaVinVac : 0.0;
            }
        }

        /// <summary>
        /// Delta-v of the stage at sea level on the current body,
        /// in meters per second.
        /// </summary>
        [KRPCProperty]
        public double DeltaVASL
        {
            get
            {
                var info = GetStageInfo();
                return info != null ? info.deltaVatASL : 0.0;
            }
        }

        /// <summary>
        /// Delta-v of the stage at the current atmospheric conditions,
        /// in meters per second.
        /// </summary>
        [KRPCProperty]
        public double DeltaVActual
        {
            get
            {
                var info = GetStageInfo();
                return info != null ? info.deltaVActual : 0.0;
            }
        }

        /// <summary>
        /// Thrust-to-weight ratio in vacuum.
        /// </summary>
        [KRPCProperty]
        public double TWRVacuum
        {
            get
            {
                var info = GetStageInfo();
                return info != null ? info.thrustToWeightVac : 0.0;
            }
        }

        /// <summary>
        /// Thrust-to-weight ratio at sea level on the current body.
        /// </summary>
        [KRPCProperty]
        public double TWRASL
        {
            get
            {
                var info = GetStageInfo();
                return info != null ? info.thrustToWeightASL : 0.0;
            }
        }

        /// <summary>
        /// Total thrust in vacuum, in Newtons.
        /// </summary>
        [KRPCProperty]
        public double ThrustVacuum
        {
            get
            {
                var info = GetStageInfo();
                return info != null ? (double)info.thrustVac * 1000.0 : 0.0;
            }
        }

        /// <summary>
        /// Total thrust at sea level, in Newtons.
        /// </summary>
        [KRPCProperty]
        public double ThrustASL
        {
            get
            {
                var info = GetStageInfo();
                return info != null ? (double)info.thrustASL * 1000.0 : 0.0;
            }
        }

        /// <summary>
        /// Specific impulse in vacuum, in seconds.
        /// </summary>
        [KRPCProperty]
        public double ISPVacuum
        {
            get
            {
                var info = GetStageInfo();
                return info != null ? info.ispVac : 0.0;
            }
        }

        /// <summary>
        /// Specific impulse at sea level, in seconds.
        /// </summary>
        [KRPCProperty]
        public double ISPASL
        {
            get
            {
                var info = GetStageInfo();
                return info != null ? info.ispASL : 0.0;
            }
        }

        /// <summary>
        /// Estimated burn time for this stage, in seconds.
        /// </summary>
        [KRPCProperty]
        public double BurnTime
        {
            get
            {
                var info = GetStageInfo();
                return info != null ? info.stageBurnTime : 0.0;
            }
        }

        /// <summary>
        /// Start mass of the stage (before burn), in kg.
        /// </summary>
        [KRPCProperty]
        public double StartMass
        {
            get
            {
                var info = GetStageInfo();
                return info != null ? (double)info.startMass * 1000.0 : 0.0;
            }
        }

        /// <summary>
        /// End mass of the stage (after burn), in kg.
        /// </summary>
        [KRPCProperty]
        public double EndMass
        {
            get
            {
                var info = GetStageInfo();
                return info != null ? (double)info.endMass * 1000.0 : 0.0;
            }
        }

        /// <summary>
        /// Fuel mass consumed by this stage, in kg.
        /// </summary>
        [KRPCProperty]
        public double FuelMass
        {
            get
            {
                var info = GetStageInfo();
                return info != null ? (double)info.fuelMass * 1000.0 : 0.0;
            }
        }

        /// <summary>
        /// Dry mass of the stage (without fuel), in kg.
        /// </summary>
        [KRPCProperty]
        public double DryMass
        {
            get
            {
                var info = GetStageInfo();
                return info != null ? (double)info.dryMass * 1000.0 : 0.0;
            }
        }
    }
}
```

**LOE:** 4–6 hours (including unit verification against KSP's readout)

**Key uncertainty:** The exact property names on `DeltaVStageInfo` need
verification against the KSP 1.12.5 assembly. The names above
(`deltaVinVac`, `deltaVatASL`, `thrustVac`, `ispVac`, `stageBurnTime`,
`startMass`, `endMass`, `fuelMass`, `dryMass`, `thrustToWeightVac`,
`thrustToWeightASL`, `deltaVActual`) are based on community documentation
and decompilation. Use dnSpy or ILSpy on `Assembly-CSharp.dll` from KSP
1.12.5 to confirm exact names before coding.

#### Task 5.2: Add `Vessel.Stages` Property and `Vessel.GetStageInfo()` Method

**File:** `service/SpaceCenter/src/Services/Vessel.cs` (modify)

```csharp
/// <summary>
/// A list of all stages for this vessel, ordered by stage number.
/// Each stage contains delta-v, mass, thrust, and burn time predictions
/// from KSP's built-in stage calculator.
/// </summary>
[KRPCProperty(GameScene = GameScene.Flight)]
public IList<Stage> Stages
{
    get
    {
        var vessel = InternalVessel;
        var stages = new List<Stage>();
        var dvInfo = vessel.VesselDeltaV;
        if (dvInfo == null)
            return stages;
        int count = dvInfo.OperatingStageInfo.Count;
        for (int i = 0; i < count; i++)
            stages.Add(new Stage(vessel, i));
        return stages;
    }
}

/// <summary>
/// Get stage information for a specific stage number.
/// </summary>
/// <param name="stage">The stage number.</param>
[KRPCMethod(GameScene = GameScene.Flight)]
public Stage GetStageInfo(int stage)
{
    return new Stage(InternalVessel, stage);
}
```

**LOE:** 1–2 hours

#### Task 5.3: Write Integration Tests

**File:** `service/SpaceCenter/test/test_stage.py` (new)

kRPC tests are Python `unittest.TestCase` subclasses that connect to a
running KSP instance with kRPC loaded and a known craft on the pad.

```python
import unittest
import krpctest

class TestStage(krpctest.TestCase):
    """Integration tests for per-stage delta-v information."""

    @classmethod
    def setUpClass(cls):
        super(TestStage, cls).setUpClass()
        cls.vessel = cls.conn.space_center.active_vessel

    def test_stages_list_not_empty(self):
        stages = self.vessel.stages
        self.assertGreater(len(stages), 0)

    def test_stage_number_sequential(self):
        stages = self.vessel.stages
        for i, stage in enumerate(stages):
            self.assertEqual(stage.number, i)

    def test_delta_v_vacuum_positive(self):
        for stage in self.vessel.stages:
            self.assertGreaterEqual(stage.delta_v_vacuum, 0)

    def test_delta_v_asl_le_vacuum(self):
        for stage in self.vessel.stages:
            self.assertLessEqual(stage.delta_v_asl, stage.delta_v_vacuum + 0.1)

    def test_mass_consistency(self):
        for stage in self.vessel.stages:
            if stage.fuel_mass > 0:
                self.assertGreater(stage.start_mass, stage.end_mass)
                self.assertAlmostEqual(
                    stage.fuel_mass,
                    stage.start_mass - stage.end_mass,
                    delta=0.1
                )

    def test_dry_mass_le_start_mass(self):
        for stage in self.vessel.stages:
            self.assertLessEqual(stage.dry_mass, stage.start_mass + 0.1)

    def test_burn_time_positive_when_fuel(self):
        for stage in self.vessel.stages:
            if stage.fuel_mass > 0 and stage.thrust_vacuum > 0:
                self.assertGreater(stage.burn_time, 0)

    def test_isp_positive_when_engines(self):
        for stage in self.vessel.stages:
            if stage.thrust_vacuum > 0:
                self.assertGreater(stage.isp_vacuum, 0)
                self.assertGreater(stage.isp_asl, 0)

    def test_twr_positive_when_engines(self):
        for stage in self.vessel.stages:
            if stage.thrust_vacuum > 0:
                self.assertGreater(stage.twr_vacuum, 0)

    def test_get_stage_info(self):
        stages = self.vessel.stages
        if len(stages) > 0:
            stage = self.vessel.get_stage_info(0)
            self.assertEqual(stage.number, 0)
            self.assertEqual(stage.delta_v_vacuum, stages[0].delta_v_vacuum)

    def test_get_stage_info_invalid(self):
        stage = self.vessel.get_stage_info(999)
        self.assertEqual(stage.delta_v_vacuum, 0)

if __name__ == '__main__':
    unittest.main()
```

**LOE:** 3–4 hours (including crafting a known test vessel in KSP)

#### Task 5.4: Update Changelog and Documentation

**File:** `service/SpaceCenter/CHANGES.txt` (modify)

```
v0.x.x
 * Add per-stage delta-v, mass, thrust, ISP, and burn time via new Stage class (#336)
 * Add Vessel.Stages property returning all stage information
 * Add Vessel.GetStageInfo(stage) method for individual stage lookup
```

**LOE:** 30 minutes

#### Task 5.5: Verify Client Auto-Generation

kRPC's build pipeline automatically generates client bindings from the
`[KRPCClass]`/`[KRPCProperty]` annotations:

1. `ServiceDefinitions` tool extracts annotations → JSON schema
2. `clientgen` tool generates Python/C++/Java/C# stubs
3. `docgen` tool generates API documentation pages

**No manual client code is needed.** After building, the Python client
will automatically expose:

```python
vessel = conn.space_center.active_vessel
for stage in vessel.stages:
    print(f"Stage {stage.number}: {stage.delta_v_vacuum:.0f} m/s ΔV, "
          f"{stage.start_mass:.0f}→{stage.end_mass:.0f} kg, "
          f"burn {stage.burn_time:.1f}s, "
          f"ISP {stage.isp_vacuum:.0f}s, TWR {stage.twr_vacuum:.2f}")
```

**LOE:** 1 hour (build, verify generated stubs, test manually)

### Task Summary

| # | Task | LOE | Dependency |
|---|------|-----|------------|
| 5.0 | Environment setup (Bazel, Mono, KSP DLLs, dnSpy verification) | 3–6 hr | None |
| 5.1 | Create `Stage.cs` wrapper class | 4–6 hr | 5.0 |
| 5.2 | Add `Vessel.Stages` + `Vessel.GetStageInfo()` | 1–2 hr | 5.1 |
| 5.3 | Write integration tests (`test_stage.py`) | 3–4 hr | 5.1 |
| 5.4 | Update CHANGES.txt | 30 min | 5.1 |
| 5.5 | Verify client auto-generation + manual smoke test | 1 hr | 5.2 |
| 5.6 | Open PR, write description, respond to review | 2–4 hr | 5.3 |
| | **Total** | **15–23 hr (2–3 dev-days)** | |

*Add 1–2 days for first-time build environment setup if not using Docker.*

### Contribution Workflow

1. **Comment on issue #336** before coding: propose the approach, reference
   `DeltaVStageInfo`, link to #311. Gauge maintainer interest and get
   design feedback before investing implementation time.
2. **Fork `krpc/krpc`**, create branch `yourname/per-stage-delta-v`.
3. **Verify KSP's `DeltaVStageInfo` API** with dnSpy/ILSpy on
   `KSP_Data/Managed/Assembly-CSharp.dll`. Confirm exact property names
   and types. Document findings in the PR description.
4. **Implement `Stage.cs`** following `Engine.cs` patterns (Equatable,
   null-safe, XML doc comments, GameScene = Flight).
5. **Add `Vessel.Stages` + `GetStageInfo()`** to `Vessel.cs`.
6. **Build:** `bazel build //service/SpaceCenter`.
7. **Create a test craft** in KSP with known staging (e.g., 3-stage rocket
   with documented ΔV). Save as a `.craft` file for the test suite.
8. **Run tests:** `bazel test //service/SpaceCenter:test`.
9. **Update `CHANGES.txt`**.
10. **Open PR** against `master`, referencing #336 and #311. Include:
    - Description of what `DeltaVStageInfo` exposes and how we wrap it
    - The dnSpy verification of property names
    - Test results
    - Python usage example

### Risks Specific to This Contribution

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `DeltaVStageInfo` property names wrong | Medium | Low | dnSpy verification before coding. If names are wrong, compile error — fast feedback. |
| `VesselDeltaV` is null in some flight states | Medium | Low | Null-check in `GetStageInfo()` helper; return 0.0 for all properties. Test with vessel on pad, in flight, and on suborbital trajectory. |
| Maintainer unresponsive or rejects approach | Medium | High | Comment on #336 first. If no response in 2 weeks, implement anyway — our manual computation (Phase 2.2) is the fallback. PR stays open for whenever they review. |
| Bazel build environment setup takes >1 day | Medium | Low | Use the Docker build image. Or build locally with `lib/ksp/` pointing to a real KSP install. |
| Stage numbering convention differs from Telemachus | Low | Medium | KSP uses `inverseStage` internally. kRPC's existing `Parts.InDecoupleStage()` already handles this convention — follow their pattern. |
| PR review requests significant redesign | Low | Medium | The design follows established kRPC patterns exactly (Engine.cs, Resources.cs). A redesign request would be unusual but we'd adapt. |

### Integration with Our Codebase (Post-Merge)

Once the PR is merged and released, our Phase 2.2 manual Tsiolkovsky
computation becomes optional. The integration path:

1. Update `krpc` package: `pip install --upgrade krpc`
2. In `KRPCClient`, replace manual ΔV computation with:
   ```python
   stages = []
   for stage in self._vessel.stages:
       stages.append({
           "index": stage.number,
           "dv_vac": stage.delta_v_vacuum,
           "dv_asl": stage.delta_v_asl,
           "dv_actual": stage.delta_v_actual,
           "twr_vac": stage.twr_vacuum,
           "twr_asl": stage.twr_asl,
           "isp_vac": stage.isp_vacuum,
           "isp_asl": stage.isp_asl,
           "thrust_vac": stage.thrust_vacuum,
           "thrust_asl": stage.thrust_asl,
           "burn_time": stage.burn_time,
           "mass": stage.start_mass,
           "dry_mass": stage.dry_mass,
           "fuel_mass": stage.fuel_mass,
       })
   state["stages"] = stages
   ```
3. Delete the manual `compute_stage_dv()` function from `vehicle_detect.py`.
4. Update tests to use the native API.

**LOE for integration:** 2–3 hours (after kRPC release with Stage class).

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| kRPC stream latency too high for real-time flight director | Low | High | Benchmark early in Phase 1. Fallback: reduce stream count, batch less-critical fields to polling. kRPC is protobuf over TCP — should be <10ms on localhost. |
| Per-stage ΔV manual computation inaccurate for complex vehicles | Medium | Medium | Validate against KSP's built-in readout for 3–5 vehicle types. Accept 5% tolerance. Crossfeed designs may diverge — document as known limitation. |
| kRPC stops being maintained | Low | High | KSP 1 is frozen — no new game updates to break compatibility. kRPC v0.5.4 (June 2024) is the likely final version needed. LGPLv3 allows forking. Worst case: pivot to COA B. |
| Vehicle auto-detection misidentifies stages | Medium | Medium | Perseus 1 is the primary test vehicle — verify exact match. Add heuristics for common patterns (serial staging, asparagus). Allow manual override via `MissionPlan.staging_overrides`. |
| Sim generalization (N-stage) regresses Perseus 1 numbers | Low | Critical | Physics integrator unchanged. Only staging model generalized. Acceptance: `VehicleConfig()` default path must produce identical results. 325+ existing tests enforce this. |
| FlightDirector threshold parameterization breaks existing tests | Low | Low | Default config exactly matches current hardcoded values. Run full suite after each change. |
| `from_nominal()` produces poor thresholds for unusual vehicles | Medium | Medium | Gate thresholds use percentage-of-nominal (90% GO, 50% MARGINAL). Test with at least 3 vehicle types: Perseus 1, single-stage, 4-stage. Allow user override via `MissionPlan`. |
| kRPC reference frame mismatch (pitch convention) | Low | High | Verify in Phase 1.5: compare kRPC `flight.pitch` to Telemachus `n.pitch` on the same vessel. Both should be degrees from horizon. Test explicitly. |
| Network connectivity between KSP machine and server | Low | Low | Same risk as Telemachus. kRPC defaults to localhost; LAN requires firewall config. Document in README. |

---

## Timeline

```
Phase 1: kRPC Client                    [1.5–2 days]  ✓ COMPLETE
Phase 2: Vehicle Detection + Mission    [4–5.5 days]  ← next
  2.1–2.2  VehicleProfile + ΔV calc              [1.5–2 days]
  2.3      MissionPlan dataclass                  [2–3 hr]
  2.4      VehicleProfile → VehicleConfig bridge  [3–4 hr]
  2.5      Generalize run_ascent() for N stages   [1.5–2 days]  ← highest risk
  2.6      Nominal from detected vehicle          [3–4 hr]
  2.7      /api/mission-plan endpoint             [2–3 hr]
  2.8–2.9  Tests + integration                    [5–8 hr]
Phase 3: FlightDirector from Nominal    [2–3 days]    ← can overlap with 2.5+
  3.1–3.3  Config dataclass + from_nominal()      [1–1.5 days]
  3.4      Dynamic phase names                    [2–3 hr]
  3.5–3.6  Test updates + new tests               [5–7 hr]
Phase 4: UI + Mission Plan Panel        [2–2.5 days]  ← after Phase 3
  4.1–4.4  Dynamic labels + fuel bars             [5–7 hr]
  4.5–4.6  Mission plan panel + compute nominal   [5–7 hr]
  4.7–4.8  Vehicle re-detect + test updates       [4–6 hr]
Phase 5: kRPC Upstream PR               [2–3 days]    ← independent, parallel
  5.0  Environment setup (Bazel/Mono/KSP DLLs)  [3–6 hr]  (+1–2 days if first time)
  5.1  Stage.cs wrapper class                    [4–6 hr]
  5.2  Vessel.Stages + GetStageInfo()            [1–2 hr]
  5.3  Integration tests (test_stage.py)         [3–4 hr]
  5.4  CHANGES.txt update                        [30 min]
  5.5  Client auto-gen verification              [1 hr]
  5.6  PR submission + review responses          [2–4 hr]

Total sequential: ~11–16 developer-days
With parallelism (Phases 2.5/3 overlap, Phase 5 in parallel): ~8–12 developer-days
```

### Milestones

| Milestone | Definition of Done | Target |
|-----------|-------------------|--------|
| M1: kRPC telemetry works | `KRPCClient.get_state()` returns valid data, FlightDirector processes it, web UI displays it. All existing tests pass. | ✓ DONE |
| M2: Vehicle auto-detected | Perseus 1 auto-detected correctly from kRPC parts. `VehicleProfile` converts to `VehicleConfig`. Detected values match known Perseus 1 stats within 5%. | End of Phase 2.4 |
| M3: Nominal from any vehicle | `run_ascent()` handles N-stage vehicles. Nominal trajectory generated from detected vehicle + user-provided `MissionPlan`. Perseus 1 results unchanged. | End of Phase 2.6 |
| M4: Flight director generalized | `FlightDirectorConfig.from_nominal()` produces correct phase boundaries for Perseus 1 and at least one non-Perseus vehicle (e.g., Kerbal X). No hardcoded Perseus thresholds remain. | End of Phase 3 |
| M5: UI works for any vehicle | Mission plan panel accepts target orbit. Stage labels, fuel bars, gate names reflect detected vehicle. "Compute Nominal" re-runs pipeline. No Perseus 1-specific text when flying another vehicle. | End of Phase 4 |
| M6: kRPC issue commented | Design proposal posted on issue #336 with DeltaVStageInfo approach. Maintainer feedback requested. | ✓ DONE |
| M7: kRPC PR submitted | PR opened against `krpc/krpc` with Stage.cs, Vessel.Stages, tests, CHANGES.txt. | End of Phase 5 |
| M8: kRPC PR merged + integrated | Native stage API available in released kRPC; manual Tsiolkovsky code removed from our codebase. | Post-Phase 5 (depends on maintainer) |

---

## What Stays Unchanged

- **Sim physics engine** (`sim/atmosphere.py`, `sim/trajectory.py` integrator): Kerbin atmosphere model, gravity, drag — all preserved. Only the staging model and entry points are generalized.
- **SVG diagram system** (`diagrams/`): no telemetry dependency
- **SimulatedTelemetry / ScriptedTelemetry**: still used for offline dev/demo
- **Web UI structure**: same HTML/CSS/JS, only label text and config loading change
- **Socket.IO protocol**: same events (`telemetry`, `director`, `nominal`)
- **Test infrastructure**: pytest, conftest.py, Playwright — all preserved
- **Scenario system**: `LaunchScenario` + `ScriptedTelemetry` still works for replay
- **Perseus 1 as default**: `VehicleConfig()` with no args still produces Perseus 1. All existing tests pass with no changes to expected values.

---

## Red Team Assessment

### Red Team Pass 1: "What breaks?"

**Finding RT-1: kRPC `flight.pitch` reference frame ambiguity.**
kRPC's `Flight` object takes a reference frame argument. Different frames
produce different pitch values. The default surface reference frame may not
match Telemachus `n.pitch` (navball frame).

*Resolution:* Phase 1 must include a reference frame verification step.
Create `KRPCClient` with `vessel.surface_reference_frame` and compare
output to Telemachus running simultaneously on the same vessel. Added as
Task 1.5 integration test. **Status: Mitigated.**

**Finding RT-2: Resource queries are RPC calls, not streams.**
`vessel.resources.amount('LiquidFuel')` is a synchronous RPC call. At 5 Hz
update rate, that's 10+ RPC calls per cycle (LF, SF, Ox, EC × current + max).
This could add latency.

*Resolution:* Batch resource queries. Alternatively, stream
`vessel.mass` (already planned) and derive fuel state from mass delta, only
querying resources at 1 Hz for the absolute values. **Status: Mitigated.**

**Finding RT-3: `vessel.parts.in_decouple_stage()` is expensive.**
Iterating the full part tree every update cycle is unnecessary. Vehicle
structure changes only at staging events.

*Resolution:* Cache the VehicleProfile. Rebuild only when
`vessel.control.current_stage` changes. Added as design constraint in
Phase 2. **Status: Mitigated.**

### Red Team Pass 2: "What's missing from the plan?"

**Finding RT-4: No rollback plan.**
If kRPC integration fails or is abandoned mid-implementation,
`TelematicusClient` must still work.

*Resolution:* The plan already preserves `TelematicusClient` — it is not
deleted, just supplemented. `server.py` selects the client based on CLI
flags: `--ksp-host` → Telemachus, `--krpc-host` → kRPC, neither → SimulatedTelemetry.
All three coexist. **Status: Mitigated.**

**Finding RT-5: No performance benchmarks defined.**
The plan says "benchmark early" but doesn't specify acceptance criteria.

*Resolution:* Add acceptance criteria:
- State update cycle (read streams + build dict) must complete in <50 ms
- End-to-end latency (KSP state change → web UI update) must be <500 ms
- KSP frame rate impact must be <5% (compare FPS with and without kRPC)

Added to Phase 1.5 integration test. **Status: Mitigated.**

**Finding RT-6: Maneuver node access is listed as a benefit but not planned.**
The comparison touted maneuver node access as a kRPC advantage, but no phase
uses it.

*Resolution:* Maneuver node access is a future enhancement, not a Phase 1–4
requirement. The `MissionPlan` dataclass (Phase 2.3) gives the user explicit
control over target orbit instead. Maneuver node integration deferred to
Future Work. **Status: Accepted.**

**Finding RT-6b: Sim generalization (Task 2.5) is high-risk.**
Generalizing `run_ascent()` from 2-stage to N-stage touches the core physics
integrator. A regression here invalidates all verified numbers (the entire
"Current verified numbers" table in CLAUDE.md).

*Resolution:* The physics integrator itself (Euler step, atmosphere model,
gravity, drag) is NOT modified — only the staging logic and phase labels
change. Acceptance criterion: `VehicleConfig()` with no args through the
generalized path must produce results identical to the current path (not
"within 5%" — identical). The existing 325+ non-browser tests enforce this.
**Status: Mitigated by test coverage.**

**Finding RT-7: `compute_downrange_km()` is shared between TelematicusClient
and KRPCClient.**
Both clients need this function for trajectory building. Currently it lives
in `telemachus_client.py`.

*Resolution:* Extract `compute_downrange_km()` to a shared utility during
Phase 1.2. Trivial refactor — function is already standalone with no
dependencies on the class. **Status: Mitigated.**

### Red Team Pass 3: "What about the user?"

**Finding RT-8: Installation is not simpler.**
COA C was partly motivated by installation simplicity, but the user still
needs Python + pip + kRPC mod. It's the same number of steps, just swapping
one mod for another.

*Resolution:* This is accurate. COA C's value is in richer telemetry and
arbitrary vehicle support, not in installation simplification. The plan
should not claim installation improvement. Updated Executive Summary to
remove that claim. **Status: Accepted — scope clarified.**

**Finding RT-9: No migration guide for existing users.**
Users currently running Telemachus need to know how to switch.

*Resolution:* Add a section to `docs/MISSION_CONTROL.md` documenting both
paths: Telemachus (legacy) and kRPC (recommended). Include kRPC installation
steps and `server.py --krpc-host` usage. Part of Phase 1 documentation. **Status: Mitigated.**

---

## Future Work (Post-COA C)

- **3D trajectory modeling:** Full inclination-aware sim with launch heading
  computation, cosine loss for non-equatorial orbits, and heading advisories.
  Required for accurate polar orbit mission plans.
- **Mission phases beyond ascent:** Extend `MissionPlan` to cover orbit
  operations — TMI burn, course corrections, Mun encounter. Each phase would
  have its own nominal and FlightDirector thresholds.
- **Maneuver node display:** Read planned burns from kRPC, show projected
  trajectory on the globe view and calculate remaining ΔV for TMI.
- **Autopilot hooks:** kRPC has full vessel control — could implement
  automated pitch programs or auto-circularization as an advanced feature.
- **Multi-vessel tracking:** kRPC can enumerate all vessels — potential for
  tracking debris, spent stages, or transfer vehicles.
- **Optimal ascent computation:** Given a vehicle's TWR profile, compute
  a near-optimal pitch program via numerical optimization rather than
  selecting from templates. Significant research problem.
- **kRPC WebSocket transport:** kRPC supports WebSocket connections, which
  could allow the browser to connect directly to KSP (eliminating the Python
  server for a read-only UI). This would be a separate COA evaluation.
