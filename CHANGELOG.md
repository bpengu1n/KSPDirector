# Changelog

## [Unreleased]

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
