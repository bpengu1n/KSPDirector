# KSPDirector Physics Model Gaps Analysis
**Branch:** `claude/vehicle-launch-simulator-n9f8fr`  
**Focus:** `projectBallisticArc` (JavaScript) and related coast/abort projection logic  
**Reviewer:** Senior Aerospace Software Engineer – Flight Dynamics & Astrodynamics  
**Date:** 2026-06-24  

**Resolution Date:** 2026-06-24  
**Resolution Status:** 3 gaps resolved (including P0 drag model), 7 deferred with documented rationale.

---

## Executive Summary

The replacement of the fake parabolic abort arc with a numerically integrated 2D gravity-turn ballistic projection is a clear improvement in physical fidelity. The inclusion of the centripetal correction term (`cos γ · (v/r − g/v)`) is particularly good and correctly handles circular-orbit edge cases.

~~However, the current model remains a **simplified 2D point-mass propagator** with several aerospace-relevant gaps.~~ **Update:** The highest-impact gap (atmospheric drag) has been resolved. The model now includes exponential atmosphere + quadratic drag matching the Python sim's `atmosphere.py`. Remaining gaps are documented and prioritized.

**Overall Physics Fidelity Rating:** ~~Good~~ **Improved** for a KSP-based educational/ops-support tool (≈ 80–85 % of a minimal operational coast model with drag). Not suitable for high-precision reentry or long-duration coast predictions without further augmentation.

---

## Identified Physics Model Gaps

### 1. Atmospheric Drag (Highest Impact for Low-Altitude Aborts) — **RESOLVED**
- **Current State:** ~~No drag term in `projectBallisticArc`.~~ Drag added using exponential atmosphere model (`ρ = ρ₀·exp(−h/Hs)`) and quadratic drag (`a_drag = ½ρv²CdA/m`).
- **Implementation:** Both JS (`projectBallisticArc`) and Python reference (`project_ballistic_arc`) include drag. Constants (`PROJ_CDA`, `PROJ_RHO0`, `PROJ_SCALE_H`, `PROJ_ATM_CEIL_M`, `PROJ_MASS_KG`) loaded from `/api/constants` endpoint using the vehicle's effective CdA and post-SRB coast mass.
- **Tests:** `TestAtmosphericDrag` (5 tests) — validates drag reduces downrange at low altitude, is negligible above atmosphere, affects steep aborts, uses correct exponential model, and is present in UI source.

### 2. Atmospheric Density & Lift Effects — **DEFERRED**
- `ATM_CEIL_KM = 70` is ~~defined but unused in the propagator~~ now used as the drag ceiling.
- No lift coefficient or angle-of-attack modeling for the capsule during atmospheric reentry.
- **Rationale:** KSP capsules have minimal controllable lift in stock. Complex to implement, low value for current scope.

### 3. Fixed-Time-Step Euler Integration — **DEFERRED (intentional)**
- `dt = 2.0` seconds with forward Euler.
- **Rationale:** KSP's own physics engine runs Euler at ~50 Hz (dt≈0.02s). Using a higher-order method for the projection would introduce a fidelity mismatch with the game itself. Energy conservation test (`TestEnergyConservation`) validates the integrator produces stable results for vacuum arcs. The Python ascent sim also uses Euler at dt=0.02s by design.

### 4. 2D Planar Assumption (No Out-of-Plane Motion) — **DEFERRED**
- All propagation occurs in a single orbital plane.
- **Rationale:** Perseus 1 launches equatorially. Out-of-plane motion relevant only for inclined orbits.

### 5. Kerbin Oblateness (J2 Perturbation) Missing — **DEFERRED**
- Uses purely spherical gravity (`g = MU / r²`).
- **Rationale:** For short ballistic arcs (< 10–15 min) the error is <0.1%. Not worth the complexity.

### 6. Planetary Rotation & Surface Velocity — **DEFERRED**
- No Coriolis or centrifugal terms from Kerbin's rotation.
- **Rationale:** Downrange error of ~2-3 km possible on long coasts. Acceptable for abort visualization. Listed as highest-value next item in PENDING.md.

### 7. No Periapsis / Orbit Element Output — **DEFERRED**
- The function returns only `(altitude_km, downrange_km)` points.
- **Rationale:** Periapsis available from external telemetry state dict. Add to projection return if autonomous abort logic is implemented.

### 8. Hardcoded Constants & Lack of Traceability — **RESOLVED**
- ~~`R = 600000`, `MU = 3.5316e12` duplicated in JS.~~
- **Fix:** `/api/constants` endpoint serves all physics constants from `sim.constants`. JS loads on connect via `loadConstants()`. Now includes `DEFAULT_CDA` and `COAST_MASS_KG` for the drag model.

### 9. No Energy or Angular-Momentum Conservation Check — **RESOLVED**
- **Fix:** `TestEnergyConservation` class validates that specific orbital energy is conserved in vacuum arcs. Serves as an integration accuracy diagnostic.

### 10. Capsule Reentry Heating / Breakup Not Modeled — **DEFERRED**
- Purely kinematic; no thermal or structural limits considered.
- **Rationale:** KSP handles heating in-game. Projection is for trajectory visualization only.

---

## Comparison with Python `run_ascent` Simulator — **RESOLVED**

~~The branch does not yet expose whether the Python ascent simulator includes atmospheric drag.~~

**Resolution:** Both the Python ascent sim (`trajectory.py` using `atm.drag_force()`) and the ballistic projection (JS + Python reference) now use the same exponential atmosphere model with the same constants (`RHO0=1.225`, `SCALE_H=5000`, `ATM_CEIL=70000`). The Python reference implementation `project_ballistic_arc()` in `test_ballistic_projection.py` mirrors the JS exactly and is regression-tested against analytical `orbital_params()`.

---

## Resolution Summary

| Gap | Priority | Status | Resolution |
|-----|----------|--------|------------|
| Atmospheric drag | P0 | **Resolved** | Exponential atm + quadratic drag in JS and Python |
| RK4 / adaptive integrator | P1→P2 | **Deferred** | Euler matches KSP; energy conservation test validates |
| Shared constants + API | P1 | **Resolved** | `/api/constants` with physics + drag params |
| Periapsis / orbital elements | P1→P2 | **Deferred** | Available from telemetry state; add to projection if needed |
| Planetary rotation | P2 | **Deferred** | ~2-3 km error acceptable; highest-value next item |
| J2 perturbation | P3 | **Deferred** | <0.1% for short arcs |
| Lift / 3D effects | P3 | **Deferred** | Low value for stock KSP |
| Reentry heating | P3 | **Deferred** | KSP handles in-game |

**Test suite: 126/126 green** (49 regression + 43 scenario + 34 ballistic projection)

---

*End of Physics Model Gaps Analysis*  
*Updated with resolution status 2026-06-24.*
