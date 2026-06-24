# Changelog

## [Unreleased]

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
- **52 new scenario tests**: Full coverage of LaunchScenario model, ScriptedTelemetry playback, scenario API routes, and FlightDirector integration.
- **34 ballistic projection tests**: Boundary-value, termination, drag, and numerical cross-validation tests.

### Changed
- Trajectory integrator `t_max` increased from 400s to 600s to accommodate full orbital insertion.
- Telemetry throttle mapping now includes TERRIER and CIRCULARIZE as powered phases.
- Liquid fuel telemetry models both core stage and mission stage FL-T800 tanks separately.
- `TrajectoryPoint.phase` field expanded: BOOST, CORE, TERRIER, COAST_APO, CIRCULARIZE, ORBIT, COAST.
- Server uses session context pattern instead of bare globals.
- Import structure cleaned up (no more `sys.path` manipulation).

### Fixed
- Suborbital trajectory no longer stops at core burnout (T+61s) — continues through Terrier burn to orbit.
- Gamma clamping bug that prevented descent during coast phases.
- Service bay double-count in fuel inspection test (source inspection updated for refactored method).

## [1.0.0] — 2026-06-24

### Initial Release
- Perseus 1 ascent trajectory simulator with 4 pitch programs.
- NASA-style mission control web UI with FlightDirector advisories and go/no-go gates.
- Telemachus integration for live KSP telemetry.
- SimulatedTelemetry for offline development.
- 4 SVG technical reference sheets (vehicle arrangement, staging, ascent program, abort criteria).
- 49-test regression suite covering all 30 engineering review findings.
