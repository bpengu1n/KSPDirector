# Coverage Report

Generated: 2026-06-25

Test suite: `test_p0_regressions`, `test_p1_regressions`, `test_p2_p3_regressions`,
`test_ballistic_projection`, `test_scenario` (264 tests, all passing).

Playwright tests (`test_ui_playwright`, 27 logical tests) excluded from coverage
because they require a headless Chromium browser.

## Current Coverage Summary

| Module | Stmts | Miss | Cover |
|--------|------:|-----:|------:|
| `sim/__init__.py` | 4 | 0 | 100% |
| `sim/constants.py` | 10 | 0 | 100% |
| `sim/atmosphere.py` | 15 | 0 | 100% |
| `sim/vehicle.py` | 98 | 0 | 100% |
| `sim/trajectory.py` | 246 | 13 | 95% |
| `sim/ascent_sim.py` | 122 | 85 | 30% |
| `mission_control/__init__.py` | 0 | 0 | 100% |
| `mission_control/scenario.py` | 55 | 0 | 100% |
| `mission_control/nominal_compare.py` | 197 | 21 | 89% |
| `mission_control/server.py` | 273 | 98 | 64% |
| `mission_control/telemachus_client.py` | 550 | 148 | 73% |
| **TOTAL** | **1570** | **365** | **77%** |

## Uncovered Areas

### sim/ascent_sim.py (30% coverage)

The entire CLI layer is untested:

- **`result_to_dict()`** (lines 107-138) -- JSON serialization of TrajectoryResult. Only called by `--json` CLI flag.
- **`print_summary()`** (lines 163-204) -- Console summary output. Includes orbit insertion reporting and remaining dV calculation.
- **`print_table()`** (lines 208-214) -- Trajectory table printing (`--table` flag).
- **`compare_programs()`** (lines 218-229) -- Multi-program comparison (`--compare` flag).
- **`main()`** (lines 272-311) -- CLI entry point with argparse dispatch. Includes `--scenario` flag handling.

### sim/trajectory.py (95% coverage)

- **`orbital_params()` escape trajectory branch** (line 104) -- `energy >= 0` returns `(inf, -inf)`. Requires extremely high velocity input.
- **`pitch_late_turn()` early return** (line 162) -- The `h <= 8000` branch of the late-turn pitch program.
- **`integrate()` crash branch** (lines 436-440) -- `h < -100` impact detection with fallback core burnout recording. Only hit when the vehicle crashes before staging.
- **`integrate()` free-turn dgamma branch** (line 324) -- Core-burned-out free gravity turn with `v > 0.5` guard.
- **Terrier phase detection** (lines 356-360) -- Terrier ignition logic within the integrator.

### mission_control/nominal_compare.py (89% coverage)

- **`NominalTrajectory.at_altitude()` empty-pts guard** (line 103) -- `if not pts: return None`.
- **`NominalTrajectory.at_altitude()` small altitude delta guard** (line 108) -- `abs(a1 - a0) < 1.0` interpolation skip.
- **`detect_phase()` ORBIT from fuel check** (line 216) -- `apo_km >= 60 and pe_km >= 65` powered-orbit branch.
- **`generate_advisory()` TERRIER low-apoapsis warning** (line 366) -- `apo_km < 30 and alt_km > 15 and lf_pct < 60`.
- **`generate_advisory()` high-apoapsis caution** (lines 379, 385) -- `apo_km > 90 and pe_km < 60` and `apo_km >= 70 and pe_km > 50`.
- **`generate_advisory()` circularize branch** (lines 433-439) -- CIRCULARIZE phase advisories.
- **`generate_advisory()` BOOST/CORE fallback** (lines 443-446) -- Nominal advisory for boost/core phases.
- **`FlightDirector.update()` nominal lookup** (line 484) -- `nominal_at_alt` population.

### mission_control/server.py (64% coverage)

- **Route handlers**: `index()`, `api_nominal()`, `api_state()`, `api_trajectory()`, `api_clear_trajectory()` (lines 95-142) -- All HTTP routes untested outside of scenario API tests.
- **Socket.IO event handlers**: `on_connect()`, `on_disconnect()`, `on_request_nominal()`, `on_clear_trajectory()`, `on_playback_control()` (lines 297-349) -- WebSocket event handlers.
- **`broadcast_loop()`** (lines 360-388) -- Background telemetry broadcasting greenlet. Includes error handling and `director_error` emission.
- **`main()`** (lines 420-475) -- CLI entry point with Telemachus/simulation/scenario mode setup. Includes `--ksp-host` live mode.

### mission_control/telemachus_client.py (73% coverage)

- **`TelematicusClient` class** (lines 258-446) -- The entire live WebSocket client is untested:
  - `__init__()`, `start()`, `stop()` -- lifecycle
  - `_run()`, `_connect_and_receive()` -- WebSocket reconnection loop
  - `_maybe_subscribe_stage_topics()` -- Dynamic per-stage dV subscription
  - `_handle_message()` -- JSON parsing, field mapping, trajectory accumulation, MET reset detection, `v_horiz` derivation from `surface_speed`
  - `_rebuild_stages_locked()` -- Stage list reconstruction from per-stage dV data
- **`SimulatedTelemetry._run()`** (lines 664-770) -- The main simulation loop: trajectory point interpolation, noise injection, phase detection, g-force calculation, landed state, trajectory auto-clear on MET reset.
- **`ScriptedTelemetry._run()`** (lines 1034-1155) -- Scripted playback loop: similar to SimulatedTelemetry but with pause/speed controls.
- **`SimulatedTelemetry.stop()`** (line 553) -- Stop method.
- **Error callbacks**: `on_update` exception handling in both SimulatedTelemetry (line 770) and ScriptedTelemetry (line 1155).

## Recommended Test Additions (Top 10, Prioritized)

### 1. `result_to_dict()` serialization (sim/ascent_sim.py)

Test that `result_to_dict()` returns a well-formed dict with expected keys and
correct rounding. Run a default `run_ascent()`, serialize, and verify the
structure matches the documented JSON schema (vehicle, results, trajectory
arrays). This covers 30+ lines and is pure-function testing with no I/O.

### 2. TelematicusClient `_handle_message()` parsing (telemachus_client.py)

Unit-test `_handle_message()` directly by constructing a `TelematicusClient`
(without calling `start()`) and feeding it raw JSON strings. Verify:
- Known topics map to correct state keys via `FIELD_MAP`
- `v_horiz` is derived from `surface_speed` and `v_vert`
- Trajectory points accumulate with correct downrange computation
- MET reset clears trajectory (met < 5 after last point t > 30)
- Invalid JSON is silently ignored
- Trajectory FIFO eviction at 10,000 points

### 3. `broadcast_loop()` error handling (server.py)

Test the broadcast loop's exception path: mock `session.telemetry_client` to
raise on `get_state()`, verify `director_error` is emitted via socketio and
the loop continues (does not crash). Also test the happy path: mock a
telemetry client returning valid state, verify `telemetry` and `director`
events are emitted.

### 4. `orbital_params()` edge cases (sim/trajectory.py)

Test the escape trajectory branch (`energy >= 0`) by providing velocity above
escape velocity at Kerbin surface (~3,431 m/s). Verify `(inf, -inf)` is
returned. Also test edge cases: zero velocity, horizontal flight at various
altitudes, and the `ecc_sq` clamping when numerical noise makes it negative.

### 5. Server route handlers (server.py)

Test `api_nominal()`, `api_state()`, `api_trajectory()`, and
`api_clear_trajectory()` using Flask's test client. Cover the 503 error paths
(no client/no nominal loaded) and the success paths (with mocked session
state). The `/api/constants` route should verify all Kerbin constants are
present and match `sim.constants`.

### 6. `generate_advisory()` TERRIER edge cases (nominal_compare.py)

Test the three uncovered TERRIER advisory branches:
- Low apoapsis WARNING: `apo_km < 30, alt_km > 15, lf_pct < 60`
- High apoapsis CAUTION: `apo_km > 90, pe_km < 60`
- On-track NOMINAL: `apo_km >= 70, pe_km > 50`
Also test the CIRCULARIZE phase advisories and BOOST/CORE fallback.

### 7. Socket.IO event handlers (server.py)

Test `on_connect()` (emits nominal trajectory + connection message),
`on_playback_control()` (start/pause/resume/reset/speed actions), and
`on_clear_trajectory()` using `flask_socketio.SocketIOTestClient`. Verify
correct events are emitted and playback state changes are applied.

### 8. CLI `main()` functions (ascent_sim.py, server.py)

Test `ascent_sim.main()` with various argv combinations:
- `["--json"]` -- verify JSON output to stdout
- `["--compare", "nominal", "steep"]` -- verify comparison runs
- `["--table"]` -- verify table output
- `["--scenario", "nominal"]` -- verify scenario mode
- `["--scenario", "nonexistent"]` -- verify error exit
Use `capsys` or `io.StringIO` to capture output.

### 9. `SimulatedTelemetry._run()` loop behavior (telemachus_client.py)

Test the simulation loop by starting `SimulatedTelemetry` with a short rate,
sleeping briefly, then stopping. Verify:
- State contains non-zero altitude after a few ticks
- Trajectory accumulates points
- Phase transitions occur (BOOST -> CORE)
- g_force is populated
- Landed state detection works at end of trajectory

### 10. `_maybe_subscribe_stage_topics()` dynamic subscription (telemachus_client.py)

Test stage topic subscription logic by constructing a `TelematicusClient`,
setting `dv_stage_count` in its state, and calling
`_maybe_subscribe_stage_topics()` with a mock WebSocket. Verify:
- Correct topics are generated for N stages
- Subscription message is sent via `ws.send()`
- `_stage_field_map` is populated
- Duplicate calls with same count are no-ops
