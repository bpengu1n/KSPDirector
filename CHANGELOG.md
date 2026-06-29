# Changelog

## [Unreleased]

### Added
- **KSP parts database** (`sim/parts_db.py`): 341-part database parsed from KSP wiki CSV with typed frozen dataclasses (`Engine`, `FuelTank`, `StructuralPart`). Wiki-verified ISP supplements for all 29 stock engines and SRB mass corrections. Lookup by normalized key, display name, or legacy alias (`db.get_engine("swivel")`).
- **Generic N-stage vehicle model** (`sim/generic_vehicle.py`): `StageDefinition` and `GenericVehicle` dataclasses supporting arbitrary stage counts, parallel boosters, mixed engine types, and per-stage throttle limits. `orbit_insertion` flag on `StageDefinition` marks which stage performs orbit insertion; stages after it ride as inert mass. Computed properties: `liftoff_mass()`, `stage_dv_vac()`, `pad_twr_asl()`, `orbit_insertion_idx()`. Factory method `GenericVehicle.from_perseus1()` for backward-compatibility verification. JSON serialization via `to_dict()`/`from_dict()` and `validate()` against the parts database.
- **N-stage trajectory integrator** (`trajectory.py:integrate_generic()`): Data-driven staging engine alongside existing `integrate()`. Handles parallel boosters, sequential staging, and orbit insertion via the `orbit_insertion` flag (burn → coast-to-apoapsis → circularize). Stages after the orbit-insertion stage are treated as inert payload — never activated, never separated. New `engine_thrust_at_generic()` helper operates on `Engine` dataclass instead of constants dict keys.
- **`run_generic()` API** (`sim/ascent_sim.py`): High-level entry point for generic vehicle trajectories, parallel to existing `run_ascent()`.
- **`staging_events` field on `TrajectoryResult`**: List of `SeparationEvent` objects populated by `integrate_generic()` (backward-compatible default: empty list).
- **65 new tests**: 26 parts database tests (`test_parts_db.py`) and 39 generic vehicle + trajectory tests (`test_generic_vehicle.py`) covering mass accounting, dV calculations, staging events, orbit insertion, post-orbit inert stages, validation, serialization, and multiple vehicle configurations.
- **Booster SEP confirmation gate** (UX-FC01a): New go/no-go gate for SRB separation. GO when alt >1.5 km and vel >150 m/s at sep; MARGINAL for early sep; NOT-YET before burnout. Gate count now 5 (was 4).
- **Nominal pitch reference in advisories** (UX-FC01b): Pitch correction advisories now include the nominal pitch value (e.g., "PITCH TOWARD HORIZON (+22° STEEP, NOM 45°)") so operators can see the delta and target.
- **Consumables trending** (UX-P3-11): FlightDirector output includes `consumables.burn_rate` (units/s, EMA-smoothed) and `consumables.time_to_depletion` (seconds). Frontend displays burn rate and TTD below fuel bars when burning.
- **Flight efficiency scoring** (UX-P3-14): Post-flight scorecard (0–100) displayed when ORBIT phase reached. Components: orbital accuracy (Ap/Pe error vs 80 km target) and fuel efficiency. Accessible via `window.MissionControl.getFlightScore()`.
- **Enhanced audio/visual alerts** (UX-P1-6): Distinct tone patterns per level — single beep (CAUTION), double beep (WARNING), continuous alarm (ABORT). Visual screen-edge flash animation on advisory escalation. ABORT produces persistent red border pulse on shell.
- **OBS overlay mode** (UX-P2-8): `?overlay=gates|advisory|telemetry|director` URL parameter renders individual panels with transparent backgrounds for stream overlays. `?fontscale=1.5` for presentation-mode font scaling. Compatible with OBS browser source.
- **Pre-launch countdown and checklist** (UX-P2-10): Dismissible overlay with 5 default checklist items (TELEMETRY LINK, VEHICLE CONFIG, FLIGHT RULES, SAS ENABLE, THROTTLE SET). T-10 countdown timer with auto-dismiss when flight detected. Disable with `?checklist=0`.
- **Mission event log** (UX-KSP06/07): Scrollable log tracking phase transitions, gate status changes, and advisory level changes with MET timestamps. Export as downloadable text file. Accessible via `window.MissionControl.getEventLog()`.
- **Custom mission branding** (UX-P3-13): Persistent mission name setting via localStorage. Editable in the Scenario panel under "Mission Settings". Priority chain: URL param `?mission=NAME` (one-time override, auto-saves) → localStorage → server `--mission-name` CLI arg via `/api/config` → default "PERSEUS 1". Reflected in `window.MissionControl.mission`.
- **Server `/api/config` endpoint**: Serves server-side configuration (mission name).
- **44 new tests** (`test_ux_review.py`): Backend logic tests for booster SEP gate (7), advisory pitch reference (3), consumables trending (4), flight scoring (3), alert escalation (3); source-level verification for overlay mode (4), checklist (5), branding (8), event log (6), server config (1).
- **61 visual regression tests** (`test_visual_playwright.py`): Panel layout, CSS theming, advisory colors, mission branding, prelaunch overlay, canvas placement, telemetry layout, gate indicator colors, flight score overlay, scenario panel, and event log visual checks.
- `tests/test_isolation.py`: Meta-test that runs all 229 Playwright tests in natural, reversed, and random order via subprocesses, verifying 0 failures in each ordering.
- `pytest-randomly` and `pytest-reverse` test dependencies for order-independence verification.

### Added (documentation)
- **UX_REVIEW.md**: Comprehensive team assessment of all 15 UX survey recommendations. 9 items implemented, 7 deferred with rationale, 1 declined. Includes implementation priority order, stability risk assessment, and domain fidelity evaluation.

### Changed
- **Expanded Playwright UI tests from 54 to 229**: Covers telemetry panel updates, flight director advisory classes, stage dV bar rendering, scenario panel interactions, XSS escaping, globe zoom, ballistic projection, Houston UI integration, CSS custom properties, canvas drawing, and Socket.IO initialization.
- **Full test isolation via autouse `reset_ui` fixture**: Every Playwright test starts from an identical clean baseline — all mutable JS globals, DOM elements, and UI state reset before each test. Eliminates order-dependent failures.
- **CI workflow migrated from unittest to pytest**: `tests.yml` now installs `pytest`, `pytest-randomly`, and `pytest-reverse`, and runs `python -m pytest` instead of `python -m unittest`. Playwright and isolation tests excluded (no browser in CI).

### Fixed
- **CI workflow missing Playwright exclusion**: Added `--ignore=tests/test_visual_playwright.py` to CI workflow so headless-Chromium tests don't run on runners without a browser.
- **Blob download race**: `exportEventLog()` now defers `URL.revokeObjectURL` via `setTimeout` so the browser can initiate the download before the blob URL is revoked.
- **Duplicate Playwright test removed**: `test_invalidate_on_resize_direct` was identical to `test_invalidate_canvas_sizes`; removed the duplicate and cleaned dead variable in `test_resize_event_handler_exists`.
- **FlightDirector reset/init duplication**: `__init__` now calls `reset()` instead of duplicating all 7 field assignments, eliminating drift risk.
- **GainNode leak in `_playTone()`**: Oscillator `onended` callback now disconnects the GainNode to prevent accumulating orphaned audio nodes.
- **ABORT/WARNING setTimeout tracking**: All `setTimeout` IDs for alert tones are now tracked in `_abortAlarmTimeouts` and cleared by `_clearAbortAlarm()` helper, preventing orphaned timeouts across advisory transitions.
- **RESET_JS shared module**: Playwright test reset snippet extracted from both test files into `tests/playwright_helpers.py` to eliminate duplication and drift.
- **`test_visual_playwright.py` missing reset fixture**: Added autouse `reset_ui` fixture to prevent order-dependent failures in visual regression tests.

## [1.2.0] — 2026-06-26

### Changed
- **Migrated from eventlet to threading** for Socket.IO async mode. Removes the deprecated `eventlet` dependency; `broadcast_loop` now uses `time.sleep()` instead of `eventlet.sleep()`. No behavioral change — telemetry clients already used stdlib threads.
- **Test suite migrated from unittest to pytest**: All 6 test files converted from `unittest.TestCase` classes to plain pytest functions with shared fixtures in `conftest.py`. Uses `pytest.approx()`, `pytest.mark.parametrize`, and `pytest.mark.skipif`. Total: 324 collected (270 pass, 54 playwright skip without browser).
- Test redundancy reduced: consolidated duplicate state-builder helpers into `conftest.py` factory fixtures (`terrier_ignition_state`, `telemetry_state`), removed duplicate API error tests between test files, unified 7 HTML `setUpClass` patterns into single `html_source` fixture.
- `CLAUDE.md` updated with pytest commands, fixture documentation, and current test counts.

### Added
- `tests/conftest.py`: Shared pytest fixtures (`project_root`, `vehicle_config`, `terrier_ignition_state`, `telemetry_state`).
- `tests/COVERAGE_REPORT.md`: Coverage analysis (77% overall) with 10 prioritized recommendations for test augmentation (P-COV-01).
- `.coverage` added to `.gitignore`.

## [1.1.1] — 2026-06-25

### Fixed
- **Input validation hardening** (P-INPUT-01): `LaunchScenario.from_dict()` now coerces field types before construction; `validate()` catches `TypeError` on non-numeric inputs instead of crashing.
- **XSS prevention** (P-XSS-01): Added `esc()` helper to web UI; all `innerHTML` interpolations of user-controlled data (gate phases, stage labels, scenario summaries) are now escaped.
- **Pitch delta threshold floor** (P-UI-01): Nominal comparison threshold uses `Math.max(Math.abs(nominal), 5)` to avoid false warnings when nominal value is near zero.
- **Preset noise/speed override** (P-FUEL-02): Preset scenario loads now accept `noise_pct` and `playback_speed` overrides from request body.
- **`time_to_ap` placeholder** (P-TELEM-01): Offline telemetry modes set `time_to_ap` to `None` (UI shows "—") instead of omitting the field.
- **g-force model** (P-TELEM-02): g-force now returns 0.0 during coast (freefall) and uses `1.0 + velocity * 0.001` during powered flight, replacing the `velocity / elapsed` formula that produced nonsensical values.
- **Latitude/longitude fields** (P-TELEM-04): Both `SimulatedTelemetry` and `ScriptedTelemetry` now emit `latitude` and `longitude` in state dicts for ground-track display.
- **Periapsis noise** (P-TELEM-05): Periapsis value now gets `noise()` applied in both offline modes, matching all other telemetry fields.
- **Trajectory memory cap** (P-MEM-01): `TelematicusClient` trajectory list capped at 10,000 points with FIFO eviction to prevent unbounded memory growth.
- **Launch longitude lock safety** (P-THREAD-01): `_launch_lon` reset now uses `_lock` consistently, avoiding a potential race between trajectory clear and longitude capture.
- **Horizontal speed derivation** (P-TELEM-03): Live Telemachus client now derives `v_horiz = sqrt(surface_speed² - v_vert²)` instead of mapping `v.surfaceSpeed` directly. `v.surfaceSpeed` is total surface-relative speed (includes vertical component), not horizontal speed.

### Added
- 27 Playwright DOM tests (`test_ui_playwright.py`): Grid layout, computed CSS styles, element existence, JS function availability, XSS escaping, and constants loading — verified via headless Chromium instead of regex string matching.
- 5 new `TestVHorizDerivation` tests verifying FIELD_MAP mapping, v_horiz derivation math, and EMPTY_STATE keys.
- 31 new tests from prior round: `TestCircularizeBoundary` (5), `TestCLIScenarioFlag` (3), `TestAPIErrorPaths` (9), `TestInputValidation` (4), `TestPresetNoiseOverride` (3), `TestTelemetryFieldCompleteness` (3), `TestXSSEscaping` (4), `TestPitchDeltaThreshold` (1).
- `wait_for()` polling helper replacing `time.sleep()` in async test assertions.
- `playwright` added as test dependency for DOM-based UI tests.

## [1.1.0] — 2026-06-25

### Added
- **Scriptable Vehicle Launch Simulator**: `LaunchScenario` data model with 6 presets (nominal, steep_ascent, shallow_ascent, heavy_payload, thumper_variant, high_twr) and custom parameter support. `ScriptedTelemetry` playback engine with play/pause/reset/speed controls.
- **Full Terrier upper stage modeling**: Trajectory integrator now runs the complete ascent through orbit insertion (BOOST -> CORE -> TERRIER -> COAST_APO -> CIRCULARIZE -> ORBIT). Achieves 80x75 km orbit with 1500 m/s remaining dV.
- **Spherical gravity turn equation**: Centrifugal term added for post-core-burnout phases, giving accurate near-orbital flight path dynamics.
- **Terrier pitch guidance**: Altitude-dependent gamma floor during Terrier burn simulates KSP pilot behavior (gradual pitch-over toward horizon).
- **Web UI launch control panel**: Collapsible scenario panel with preset/custom selection, playback controls, vehicle summary readout, and real-time progress display.
- **Scenario REST + Socket.IO API**: `/api/scenarios`, `/api/scenario/load`, `/api/scenario/current`, playback control endpoints, `scenario_loaded` and `playback_status` events.
- **`--scenario` CLI argument**: Start mission control server with a preset scenario for headless or demo use.
- **Ballistic projection engine**: Physics-correct abort trajectory visualization with atmospheric drag, replacing the previous parabolic approximation.
- **Atmospheric drag model**: Exponential atmosphere with quadratic drag using scenario `cd`/`area_base` for both trajectory sim and ballistic projection.
- **Constants API endpoint**: `/api/constants` serves Kerbin physics constants to eliminate JS/Python duplication.
- **CI workflow**: GitHub Actions runs the full regression suite on every push and PR to `main` (Python 3.10/3.11/3.12).
- **69 new scenario tests**: Full coverage of LaunchScenario model, ScriptedTelemetry playback, scenario API routes, FlightDirector integration, and stage dV accuracy invariants.
- **34 ballistic projection tests**: Boundary-value, termination, drag, and numerical cross-validation tests.

### Changed
- Trajectory integrator `t_max` increased from 400s to 600s to accommodate full orbital insertion.
- Telemetry throttle mapping now includes TERRIER and CIRCULARIZE as powered phases.
- Stage dV bars now use time-based fuel depletion from trajectory phase transitions instead of mass-based estimation. Bar fill shows `dv_remaining / dv_initial` instead of `fuel_mass / total_mass`.
- All 3 stages (Stage 0, Stage 1, Stage 2) always visible with status indicators (active/pending/depleted). Depleted stages dimmed, pending stages subdued.
- Stage labels use sequential numbering (Stage 0/1/2) instead of engine names for consistency across vehicle configurations.
- `TrajectoryPoint.phase` field expanded: BOOST, CORE, TERRIER, COAST_APO, CIRCULARIZE, ORBIT, COAST.
- Server uses session context pattern instead of bare globals.
- Import structure cleaned up (no more `sys.path` manipulation).
- Telemachus topic list verified against TeaGuild/Telemachus-1 source; added `telemachus_schema.json` reference.

### Fixed
- **Stage dV accuracy**: Terrier dV no longer erroneously decreases during BOOST/CORE phases. Root cause was mass-based fuel estimation conflating two independent FL-T800 tanks (core vs mission stage).
- **Core stage dV**: Core (Swivel) dV now correctly decreases from liftoff through core burnout, matching the Swivel burning during both BOOST and CORE.
- Suborbital trajectory no longer stops at core burnout (T+61s) — continues through Terrier burn to orbit.
- Gamma clamping bug that prevented descent during coast phases.
- Timeline phase bands now derived dynamically from nominal trajectory data instead of hardcoded times that drifted from the sim (TERRIER ending at 290s instead of actual ~217s, CIRC starting at 420s instead of ~472s).
- Star rendering replaced linear congruential formula with sine hash to eliminate visible row patterns at common canvas sizes.
- Service bay double-count in fuel inspection test (source inspection updated for refactored method).

## [1.0.0] — 2026-06-24

### Initial Release
- Perseus 1 ascent trajectory simulator with 4 pitch programs.
- NASA-style mission control web UI with FlightDirector advisories and go/no-go gates.
- Telemachus integration for live KSP telemetry.
- SimulatedTelemetry for offline development.
- 4 SVG technical reference sheets (vehicle arrangement, staging, ascent program, abort criteria).
- 49-test regression suite covering all 30 engineering review findings.
