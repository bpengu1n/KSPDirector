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
Phase 5: kRPC Upstream PR               [2–3 days]    ← independent, parallel
  5.0  Environment setup (Bazel/Mono/KSP DLLs)  [3–6 hr]  (+1–2 days if first time)
  5.1  Stage.cs wrapper class                    [4–6 hr]
  5.2  Vessel.Stages + GetStageInfo()            [1–2 hr]
  5.3  Integration tests (test_stage.py)         [3–4 hr]
  5.4  CHANGES.txt update                        [30 min]
  5.5  Client auto-gen verification              [1 hr]
  5.6  PR submission + review responses          [2–4 hr]

Total sequential: ~7–11 developer-days
With parallelism (Phases 2/3 overlap, Phase 5 in parallel): ~5–8 developer-days
```

### Milestones

| Milestone | Definition of Done | Target |
|-----------|-------------------|--------|
| M1: kRPC telemetry works | `KRPCClient.get_state()` returns valid data, FlightDirector processes it, web UI displays it. All existing tests pass. | End of Phase 1 |
| M2: Arbitrary vehicle support | Perseus 1 auto-detected correctly. Non-Perseus vehicle (e.g., stock Kerbal X) produces reasonable FlightDirector output. | End of Phase 3 |
| M3: UI generalized | No Perseus 1-specific text visible when flying a non-Perseus vehicle. Stage labels, fuel bars, and gate thresholds reflect detected vehicle. | End of Phase 4 |
| M4: kRPC issue commented | Design proposal posted on issue #336 with DeltaVStageInfo approach. Maintainer feedback requested before full implementation. | Phase 5 start |
| M5: kRPC PR submitted | PR opened against `krpc/krpc` with Stage.cs, Vessel.Stages, tests, CHANGES.txt. | End of Phase 5 |
| M6: kRPC PR merged + integrated | Native stage API available in released kRPC; manual Tsiolkovsky code removed from our codebase. | Post-Phase 5 (depends on maintainer) |

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
