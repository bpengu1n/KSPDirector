# COA C Implementation Plan: Migrate from Telemachus to kRPC

## Executive Summary

Replace the Telemachus WebSocket telemetry client with a kRPC-based client,
enabling arbitrary vehicle support, richer telemetry, and eliminating
Telemachus topic-naming fragility. The Python sim, flight director, web UI,
scenario system, and test suite are preserved with targeted modifications.

**Estimated total effort: 6–9 developer-days across 5 phases.**

---

## Phase 1: kRPC Client Drop-In Replacement

**Goal:** Replace `TelematicusClient` with a `KRPCClient` class that produces
the same `get_state()` / `get_trajectory()` dict format, so the rest of the
pipeline (FlightDirector, server.py broadcast loop, web UI) works unchanged.

### Tasks

| # | Task | Files | LOE | Notes |
|---|------|-------|-----|-------|
| 1.1 | Add `krpc` to requirements.txt | `requirements.txt` | 15 min | `pip install krpc` |
| 1.2 | Create `KRPCClient` class | `mission_control/krpc_client.py` (new) | 4–6 hr | See design below |
| 1.3 | Wire into server.py as a third telemetry source | `mission_control/server.py` | 1–2 hr | `--krpc-host` flag |
| 1.4 | Write unit tests for KRPCClient | `tests/test_krpc_client.py` (new) | 3–4 hr | Mock `krpc.connect()` |
| 1.5 | Integration test with live KSP | Manual | 2–3 hr | Requires KSP + kRPC running |

**Subtotal: 1.5–2 days**

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

## Phase 2: Vehicle Auto-Detection from kRPC Parts API

**Goal:** Automatically build a `VehicleConfig`-equivalent from the active
vessel's part tree, eliminating manual vehicle configuration.

### Tasks

| # | Task | Files | LOE | Notes |
|---|------|-------|-----|-------|
| 2.1 | Create `VehicleProfile` from kRPC part data | `mission_control/vehicle_detect.py` (new) | 6–8 hr | See design below |
| 2.2 | Compute per-stage ΔV from part data | Same file | 4–6 hr | Tsiolkovsky from parts |
| 2.3 | Pass vehicle profile to FlightDirector | `mission_control/nominal_compare.py` | 2–3 hr | Parameterize thresholds |
| 2.4 | Tests for vehicle detection | `tests/test_vehicle_detect.py` (new) | 3–4 hr | Mock kRPC vessel objects |
| 2.5 | Integration test with Perseus 1 in KSP | Manual | 1–2 hr | Verify detected config matches known values |

**Subtotal: 2–3 days**

### Vehicle Detection Design

```python
class VehicleProfile:
    """Auto-detected vehicle configuration from kRPC part tree."""

    # Detected properties
    total_mass: float           # tonnes
    dry_mass: float             # tonnes
    stages: list[StageProfile]  # per-stage breakdown
    has_boosters: bool
    booster_type: str           # 'hammer', 'thumper', etc.
    n_boosters: int

    # Derived thresholds for FlightDirector
    booster_burnout_alt_km: float   # estimated from booster burn time + trajectory
    core_burnout_alt_km: float      # estimated from core ΔV + trajectory
    target_orbit_km: float          # from maneuver node if available, else 80 km default

    @classmethod
    def from_vessel(cls, vessel) -> 'VehicleProfile':
        """Inspect kRPC vessel object and build profile."""
        stages = []
        for stage_num in range(vessel.control.current_stage, -1, -1):
            engines = [p for p in vessel.parts.in_decouple_stage(stage_num)
                       if p.engine is not None and p.engine.active]
            fuel = vessel.resources_in_decouple_stage(stage_num, cumulative=False)
            # ... build StageProfile with engine ISP, thrust, fuel mass
        return cls(stages=stages, ...)

    def to_flight_director_config(self) -> dict:
        """Generate threshold config for FlightDirector parameterization."""
        return {
            'core_burnout_alt_threshold': self.core_burnout_alt_km * 1000 * 1.1,
            'core_burnout_apo_threshold': ...,
            'met_terrier_established': ...,
            'full_lf': self.stages[-1].fuel_capacity,
            'target_orbit_alt': self.target_orbit_km,
        }
```

### Per-Stage ΔV Computation

kRPC does not expose KSP's built-in `DeltaVStageInfo`. We compute it:

```python
def compute_stage_dv(vessel, stage_num: int) -> float:
    """Compute vacuum ΔV for a single stage using the Tsiolkovsky equation."""
    engines = [p.engine for p in vessel.parts.in_decouple_stage(stage_num)
               if p.engine is not None]
    if not engines:
        return 0.0

    # Weighted average ISP
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

---

## Phase 3: Parameterize Flight Director Thresholds

**Goal:** Remove Perseus 1-specific hardcoded thresholds from
`nominal_compare.py` so the flight director works with any vehicle.

### Tasks

| # | Task | Files | LOE | Notes |
|---|------|-------|-----|-------|
| 3.1 | Create `FlightDirectorConfig` dataclass | `mission_control/nominal_compare.py` | 2–3 hr | Extract all hardcoded thresholds |
| 3.2 | Accept config in FlightDirector.__init__ | Same | 1–2 hr | Default = current Perseus 1 values |
| 3.3 | Generate config from VehicleProfile | `mission_control/vehicle_detect.py` | 2–3 hr | Map detected vehicle → thresholds |
| 3.4 | Update all existing tests to pass config | `tests/test_p*.py`, `tests/test_scenario.py` | 2–3 hr | Default config = backward compatible |
| 3.5 | New tests for non-Perseus vehicles | `tests/test_vehicle_detect.py` | 2–3 hr | Thumper variant, no-booster, etc. |

**Subtotal: 1.5–2 days**

### Thresholds to Extract

```python
@dataclass
class FlightDirectorConfig:
    """All tunable thresholds for the flight director, extracted from
    what was previously hardcoded for Perseus 1."""

    # Phase detection (detect_phase)
    core_burnout_alt_m: float = 17_000      # altitude above which → TERRIER
    core_burnout_apo_km: float = 32         # apoapsis above which → TERRIER
    orbit_pe_km: float = 70                 # periapsis threshold for ORBIT
    circularize_apo_km: float = 60          # apoapsis threshold for CIRCULARIZE
    circularize_pe_km: float = 65           # periapsis ceiling for CIRCULARIZE
    circularize_vvert_ms: float = 50        # |v_vert| ceiling for CIRCULARIZE

    # Advisory generation (generate_advisory)
    target_orbit_alt_km: float = 80.0       # nominal target orbit
    met_terrier_established_s: float = 70.0 # MET before ABORT can fire
    full_lf_units: float = 360.0            # full liquid fuel for % calculations
    pitch_deviation_threshold: float = 12.0 # degrees off nominal → CAUTION

    # Gate assessment (assess_gates)
    booster_sep_alt_km: float = 1.5         # GO threshold
    booster_sep_vel_ms: float = 150         # GO threshold
    core_bo_apo_go_km: float = 20           # GO threshold
    core_bo_apo_marginal_km: float = 12     # MARGINAL threshold
    mid_terr_apo_go_km: float = 40          # GO threshold
    late_terr_apo_go_km: float = 70         # GO threshold

    @classmethod
    def for_perseus_1(cls) -> 'FlightDirectorConfig':
        """Return the default Perseus 1 configuration (backward compatible)."""
        return cls()
```

### Backward Compatibility Strategy

- `FlightDirectorConfig()` with no args produces exact current behavior
- `FlightDirector(nominal)` still works (uses default config)
- `FlightDirector(nominal, config=FlightDirectorConfig.for_perseus_1())` is explicit
- All existing tests pass without modification (default config matches)

---

## Phase 4: UI Updates for Arbitrary Vehicles

**Goal:** Remove Perseus 1-specific labels and hardcoded values from the web UI.

### Tasks

| # | Task | Files | LOE | Notes |
|---|------|-------|-----|-------|
| 4.1 | Serve vehicle profile via `/api/vehicle` | `server.py` | 1 hr | Stage names, fuel caps, etc. |
| 4.2 | Load vehicle profile in JS on connect | `static/index.html` | 2–3 hr | Replace hardcoded stage labels |
| 4.3 | Dynamic fuel bar max values | `static/index.html` | 1 hr | Use `liquid_fuel_max` from state |
| 4.4 | Dynamic stage labels | `static/index.html` | 1–2 hr | "SRB" / "Core" / "Terrier" → from profile |
| 4.5 | Update Playwright tests for dynamic labels | `tests/test_ui_playwright.py` | 2–3 hr | Parameterize expected text |

**Subtotal: 1–1.5 days**

---

## Phase 5: kRPC Upstream Contribution (Per-Stage ΔV)

**Goal:** Contribute a per-stage ΔV API to kRPC, closing the gap that
requires our manual Tsiolkovsky computation.

### Feasibility Assessment

**Repository:** `github.com/krpc/krpc` — LGPLv3, accepts PRs.

**What exists:** GitHub issue #336 requests this feature. It has been open
for several years, indicating interest but no implementation.

**What KSP exposes internally:** Since KSP 1.12, the game has a built-in
`DeltaVStageInfo` class that computes per-stage ΔV, TWR, ISP, burn time,
and mass breakdown. This is what the stock staging UI reads.

**Implementation approach for a kRPC PR:**

The kRPC service definition lives in `service/SpaceCenter/src/Services/`.
Adding per-stage ΔV would involve:

1. Create a new `StageDeltaV` class wrapping KSP's `DeltaVStageInfo`:
   ```csharp
   [KRPCClass(Service = "SpaceCenter")]
   public class StageDeltaV {
       [KRPCProperty] public double DVVacuum { get; }
       [KRPCProperty] public double DVASL { get; }
       [KRPCProperty] public double DVActual { get; }
       [KRPCProperty] public double TWRVacuum { get; }
       [KRPCProperty] public double TWRASL { get; }
       [KRPCProperty] public double ISPVacuum { get; }
       [KRPCProperty] public double ISPASL { get; }
       [KRPCProperty] public double BurnTime { get; }
       [KRPCProperty] public double StartMass { get; }
       [KRPCProperty] public double EndMass { get; }
       [KRPCProperty] public double FuelMass { get; }
   }
   ```

2. Add a `Vessel.DeltaVPerStage` property returning `IList<StageDeltaV>`.

3. Write tests in kRPC's existing test harness.

**Effort estimate:** 2–4 days for a contributor familiar with kRPC internals;
4–8 days for a first-time contributor (learning build system, test framework,
C# conventions, review cycles).

**Risk factors:**
- kRPC's build system is complex (Bazel-based, cross-platform, multi-language
  client generation). First build can take significant setup time.
- PR review turnaround is unpredictable — maintainer is active but part-time.
  Could be days or months. v0.5.4 shipped June 2024, so 12+ months between
  the last release and now.
- KSP's `DeltaVStageInfo` has edge cases with asparagus staging and fuel
  crossfeed that may complicate the wrapper.

**Recommendation:** Submit the PR but don't block on it. Our manual computation
(Phase 2.2) is the fallback and will be needed regardless during the review
period. If merged, we remove our manual computation and use the native API.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| kRPC stream latency too high for real-time flight director | Low | High | Benchmark early in Phase 1. Fallback: reduce stream count, batch less-critical fields to polling. kRPC is protobuf over TCP — should be <10ms on localhost. |
| Per-stage ΔV manual computation inaccurate for complex vehicles | Medium | Medium | Validate against KSP's built-in readout for 3–5 vehicle types. Accept 5% tolerance. Crossfeed designs may diverge — document as known limitation. |
| kRPC stops being maintained | Low | High | KSP 1 is frozen — no new game updates to break compatibility. kRPC v0.5.4 (June 2024) is the likely final version needed. LGPLv3 allows forking. Worst case: pivot to COA B. |
| Vehicle auto-detection misidentifies stages | Medium | Medium | Perseus 1 is the primary test vehicle — verify exact match. Add heuristics for common patterns (serial staging, asparagus). Allow manual override in UI. |
| FlightDirector threshold parameterization breaks existing tests | Low | Low | Default config exactly matches current hardcoded values. Run full suite after each change. |
| kRPC reference frame mismatch (pitch convention) | Low | High | Verify in Phase 1.5: compare kRPC `flight.pitch` to Telemachus `n.pitch` on the same vessel. Both should be degrees from horizon. Test explicitly. |
| Network connectivity between KSP machine and server | Low | Low | Same risk as Telemachus. kRPC defaults to localhost; LAN requires firewall config. Document in README. |

---

## Timeline

```
Phase 1: kRPC Client                    [1.5–2 days]  ← start here
Phase 2: Vehicle Auto-Detection         [2–3 days]
Phase 3: Parameterize FlightDirector    [1.5–2 days]  ← can overlap with Phase 2
Phase 4: UI Updates                     [1–1.5 days]  ← after Phase 3
Phase 5: kRPC Upstream PR               [2–4 days]    ← independent, can run in parallel

Total sequential: ~6–9 developer-days
With parallelism (Phases 2/3 overlap, Phase 5 in parallel): ~5–7 developer-days
```

### Milestones

| Milestone | Definition of Done | Target |
|-----------|-------------------|--------|
| M1: kRPC telemetry works | `KRPCClient.get_state()` returns valid data, FlightDirector processes it, web UI displays it. All existing tests pass. | End of Phase 1 |
| M2: Arbitrary vehicle support | Perseus 1 auto-detected correctly. Non-Perseus vehicle (e.g., stock Kerbal X) produces reasonable FlightDirector output. | End of Phase 3 |
| M3: UI generalized | No Perseus 1-specific text visible when flying a non-Perseus vehicle. Stage labels, fuel bars, and gate thresholds reflect detected vehicle. | End of Phase 4 |
| M4: kRPC PR submitted | PR opened against `krpc/krpc` with per-stage ΔV wrapper, tests, docs. | End of Phase 5 |

---

## What Stays Unchanged

- **Python simulation package** (`sim/`): entirely independent of telemetry source
- **SVG diagram system** (`diagrams/`): no telemetry dependency
- **SimulatedTelemetry / ScriptedTelemetry**: still used for offline dev/demo
- **Web UI structure**: same HTML/CSS/JS, only label text and config loading change
- **Socket.IO protocol**: same events (`telemetry`, `director`, `nominal`)
- **Test infrastructure**: pytest, conftest.py, Playwright — all preserved
- **Scenario system**: `LaunchScenario` + `ScriptedTelemetry` still works for replay

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
requirement. Add to "Future Work" section. Not blocking. **Status: Accepted.**

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

- **Maneuver node display:** Read planned burns from kRPC, show projected
  trajectory on the globe view and calculate remaining ΔV for TMI.
- **Autopilot hooks:** kRPC has full vessel control — could implement
  automated pitch programs or auto-circularization as an advanced feature.
- **Multi-vessel tracking:** kRPC can enumerate all vessels — potential for
  tracking debris, spent stages, or transfer vehicles.
- **kRPC WebSocket transport:** kRPC supports WebSocket connections, which
  could allow the browser to connect directly to KSP (eliminating the Python
  server for a read-only UI). This would be a separate COA evaluation.
