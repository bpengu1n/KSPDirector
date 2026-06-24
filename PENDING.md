# PENDING — Deferred & Future Items

Issues remaining after the vehicle launch simulator MR. Organized by source
document so a follow-up session can pick up where this left off.

**Branch:** `claude/vehicle-launch-simulator-n9f8fr`  
**Last updated:** 2026-06-24  
**Test suite:** 126/126 green (49 regression + 43 scenario + 34 ballistic)

---

## From: Code Review (KSPDirector_Vehicle_Launch_Simulator_Code_Review.md)

| ID | Item | Priority | Status | Notes |
|----|------|----------|--------|-------|
| CR-P1-3 | MissionSession class — consider Flask app context or DI for multi-session | P2 | **Deferred** | Current `MissionSession` container is sufficient for single-user. Revisit if multi-session needed. |
| CR-P2-8 | Frontend render throttling | P3 | **Deferred** | Single-vehicle 5 Hz is fine. Throttle or use offscreen canvas if multi-vehicle. |
| CR-P3-11 | CLI headless scenario runner (`python -m mission_control.scenario --run`) | P3 | **Deferred** | `--scenario NAME` flag on server.py covers basic headless use. Standalone runner is nice-to-have. |

---

## From: Physics Model Gaps (KSPDirector_Physics_Model_Gaps.md)

| ID | Gap | Priority | Status | Notes |
|----|-----|----------|--------|-------|
| PG-1 | Atmospheric drag in ballistic projection | P0 | **Resolved** | Exponential atmosphere + quadratic drag added to both JS and Python reference. Uses CdA from VehicleConfig, coast mass from booster sep. |
| PG-2 | Lift / angle-of-attack modeling | P3 | **Deferred** | Complex; KSP capsules have minimal controllable lift. Low value for current scope. |
| PG-3 | RK4 / adaptive integrator | P2 | **Deferred** | Euler at dt=2s matches KSP's own physics model (Euler at ~50 Hz). Higher-order method is academic improvement only. Energy conservation test validates current accuracy. |
| PG-4 | 3D / out-of-plane motion | P3 | **Deferred** | All Perseus 1 ops are equatorial launch, single plane. 3D needed only for inclined launches. |
| PG-5 | J2 perturbation | P3 | **Deferred** | Effect is <0.1% for arcs under 15 min. Not worth complexity. |
| PG-6 | Planetary rotation / Coriolis | P2 | **Deferred** | Downrange error ~2-3 km on long coasts. Acceptable for abort visualization. Add if doing landing footprint prediction. |
| PG-7 | Periapsis / orbital elements output | P2 | **Deferred** | Projection returns (alt_km, dr_km) points. Periapsis available from external state dict. Add if needed for autonomous abort logic. |
| PG-8 | Hardcoded constants | P1 | **Resolved** | `/api/constants` endpoint, `loadConstants()` on connect. Includes CdA and coast mass for drag model. |
| PG-9 | Energy conservation check | P1 | **Resolved** | `TestEnergyConservation` validates specific orbital energy is conserved in vacuum arcs. |
| PG-10 | Reentry heating / breakup | P3 | **Deferred** | Purely kinematic model. KSP handles heating in-game; projection is for trajectory visualization only. |
| PG-Python | Python reference implementation of `projectBallisticArc` | P1 | **Resolved** | `project_ballistic_arc()` in `test_ballistic_projection.py` with drag support, regression-tested against analytical orbital_params. |

---

## From: Test Coverage Recommendations (KSPDirector_Test_Coverage_Recommendations.md)

| ID | Recommendation | Priority | Status | Notes |
|----|---------------|----------|--------|-------|
| TC-P0-1 | Validation boundary tests | P0 | **Resolved** | `TestScenarioEdgeCases` — exact bounds, just-outside-bounds, unknown keys. |
| TC-P0-2 | Ballistic projection termination & edge cases | P0 | **Resolved** | Existing tests cover: zero velocity, surface impact, circular orbit, high-altitude escape, periapsis abort. New: drag effects at low/high altitude, steep abort. |
| TC-P0-3 | Scenario load + ScriptedTelemetry integration | P0 | **Resolved** | `TestScriptedDirectorIntegration` + `TestScenarioAPI` cover full pipeline. |
| TC-P1-4 | Round-trip serialization for all presets | P1 | **Resolved** | `test_to_dict_from_dict_roundtrip` + `test_preset_scenarios_all_valid`. |
| TC-P1-5 | Python/JS numerical consistency | P1 | **Resolved** | Python reference `project_ballistic_arc()` mirrors JS exactly, tested against analytical orbital_params. Both now include drag. |
| TC-P1-6 | Server error resilience | P1 | **Resolved** | `TestServerErrorResilience` — invalid preset, invalid params, controls without scenario, speed out of range. |
| TC-P1-7 | Noise injection & playback speed | P1 | **Partially resolved** | Speed change tested (`test_speed_change_preserves_elapsed`). Noise boundary tested (`test_noise_zero_gives_clean_telemetry`). Mock-based timing tests deferred. |
| TC-P2-8 | Preset coverage | P2 | **Resolved** | `test_preset_scenarios_all_valid` + `test_preset_scenarios_produce_valid_sim_results` iterate all presets. |
| TC-P2-9 | Abort projection visualization path | P2 | **Deferred** | JS canvas rendering not covered by Python test harness. Consider Playwright/Puppeteer for future UI testing. |
| TC-P2-10 | Dynamic zoom extent calculation | P2 | **Deferred** | Same — requires browser-based testing. |
| TC-P3-11 | Property-based / fuzz testing (hypothesis) | P3 | **Deferred** | Would add `hypothesis` dependency. Good for long-term robustness. |
| TC-P3-12 | Performance regression test | P3 | **Deferred** | Projection runs in <1ms for 300 steps. No regression observed. |
| TC-Harness-1 | Shared constants module + API | N/A | **Resolved** | `/api/constants` endpoint with full physics + drag constants. |
| TC-Harness-2 | Test utilities / fixtures | P3 | **Deferred** | Tests work fine with inline setup. Add conftest.py if test count grows. |
| TC-Harness-3 | Coverage tooling | P2 | **Deferred** | Add `coverage` to requirements.txt and CI. |
| TC-Harness-4 | CI / GitHub Action | P2 | **Deferred** | No CI pipeline exists yet. Add when repo matures. |
| TC-Harness-5 | Frontend test strategy (Playwright) | P3 | **Deferred** | Canvas rendering tests need browser automation. |

---

## Quick Start for Next Session

```bash
# Verify current state
cd /home/user/KSPDirector/code
python -m unittest tests.test_p0_regressions tests.test_p1_regressions \
    tests.test_p2_p3_regressions tests.test_scenario \
    tests.test_ballistic_projection -v

# Highest-value next items (in order):
# 1. PG-6:  Add Kerbin rotation to ballistic projection (downrange correction)
# 2. TC-Harness-3: Add coverage tooling + CI gate
# 3. PG-7:  Return periapsis/apoapsis from projection for autonomous abort
# 4. CR-P3-11: Standalone scenario CLI runner
```

---

*End of pending items list.*
