# UX Survey Review — Team Assessment and Implementation Plan

**Review date:** 2026-06-26
**Survey reviewed:** `UX_SURVEY.md` v1.0 (2026-06-26)
**Review team:**
- Senior UX Engineer (accessibility, UI/layout, onboarding)
- Senior Software Engineer (architecture, performance, maintainability)
- Senior Test Engineer (test strategy, coverage, regression risk)
- Release Engineer (stability, branching, rollback)
- Senior Flight Controller Advisors (domain fidelity, operational accuracy)

---

## Review Methodology

Each survey recommendation (P0 through P3) and individual respondent suggestion
was evaluated against five criteria:

1. **Viability** — Can this be implemented within the current architecture?
2. **Stability risk** — Does this change touch core logic (flight director, sim)?
3. **Value/effort ratio** — How many users benefit relative to implementation cost?
4. **Domain fidelity** — Does this improve or degrade operational realism?
5. **Test coverage** — Can we write deterministic tests for this?

Decisions: **IMPLEMENT**, **DEFER**, or **DECLINE** with rationale.

---

## P0 — Critical (Survey Recommendations 1–3)

### P0-1: Vehicle Generalization

**Decision: DEFER**

| Criterion | Assessment |
|-----------|------------|
| Viability | Technically feasible — `VehicleConfig` already supports custom params, `ScriptedTelemetry` accepts arbitrary configs via `/api/scenario/load`. |
| Stability risk | **HIGH** — Gate thresholds in `assess_gates()` are tuned for Perseus 1 performance envelope. Scaling them generically risks false GO/NO-GO for dissimilar vehicles. |
| Value/effort | High value (5/7 players mentioned), but very high effort to do correctly. |
| Domain fidelity | FC advisors note: "Gate thresholds are well-chosen for the vehicle class." Generic gates would dilute this. |
| Test coverage | Would require parametric gate threshold testing for every supported vehicle class. |

**Rationale:** The scenario system already allows custom vehicles for trajectory
simulation. The real gap is gate threshold scaling, which is a flight-rules
problem, not a UI problem. Implementing naive threshold scaling would degrade
the flight controller fidelity that FC-01 and FC-02 praised. The correct
approach is a vehicle profile system with per-vehicle flight rules — this is a
major feature that should be its own design cycle, not a UX patch.

**What we do now:** No changes. The scenario panel already exposes custom vehicle
parameters. Document this capability more prominently in the UI.

---

### P0-2: Installation Simplification

**Decision: DEFER**

| Criterion | Assessment |
|-----------|------------|
| Viability | Docker image is straightforward; pip package requires packaging work; standalone binary requires PyInstaller/Nuitka. |
| Stability risk | Low for Docker; medium for packaging (dependency pinning, path resolution). |
| Value/effort | High value for beginners, but the 86% setup success rate indicates most users manage. |

**Rationale:** This is infrastructure/packaging work, not a code change. The
Flask server and sim have no external deps beyond `flask-socketio` and
`websocket-client`. A `Dockerfile` is the quickest win but KSP players typically
run Windows, where Docker is not common. A pip-installable package is the right
medium-term solution. Deferring to a dedicated packaging sprint.

---

### P0-3: Onboarding / First-Run Experience

**Decision: DEFER**

| Criterion | Assessment |
|-----------|------------|
| Viability | Feasible — add a dismissible overlay on first visit explaining panels. |
| Stability risk | Low — pure frontend, no backend changes. |
| Value/effort | Medium — helps 3/7 KSP players, but the tool's target audience (intermediate+) generally figures it out. |

**Rationale:** A welcome overlay is straightforward but needs UX design iteration
(what to show, how much, when to dismiss). The 100% gate comprehension rate
suggests the core UI is already intuitive for its intended audience. A glossary
tooltip system (hover-to-define "apoapsis", "periapsis") is higher value than a
one-time overlay. Deferring for design review.

---

## P1 — High Priority (Survey Recommendations 4–6)

### P1-4: Post-Ascent Phase Support

**Decision: DEFER**

| Criterion | Assessment |
|-----------|------------|
| Viability | The sim already models through ORBIT phase. Extending the flight director to TMI/coast/Mun approach is a major feature. |
| Stability risk | **HIGH** — Touching `detect_phase()` and `generate_advisory()` risks regression on the well-tested ascent path. |
| Domain fidelity | FC-02: "Not needed for the ascent tool — different consoles handle different mission phases." |

**Rationale:** The flight director is an ascent tool by design. Post-ascent
phases have fundamentally different advisory needs (burn timing, trajectory
correction maneuvers, approach guidance) that don't fit the current advisory
framework. This is a separate product feature, not an enhancement.

---

### P1-5: Mission Logging and Replay

**Decision: DEFER**

| Criterion | Assessment |
|-----------|------------|
| Viability | Feasible — persist trajectory + events to JSON/SQLite. |
| Stability risk | Medium — requires server-side file I/O, state management. |
| Value/effort | Medium — 3/7 players want it, useful for multiplayer debriefs. |

**Rationale:** Server-side persistence adds complexity (file paths, permissions,
cleanup, concurrent access). A simpler approach — client-side event log that
can be copy-pasted or downloaded — delivers much of the value. We implement the
**event log** (Task #9) as the foundation; full persistence comes later.

---

### P1-6: Audio/Visual Alert Escalation

**Decision: IMPLEMENT**

| Criterion | Assessment |
|-----------|------------|
| Viability | Existing P3-02 audio system is minimal (single beep, escalation-only). Can enhance significantly. |
| Stability risk | **LOW** — Pure frontend, no backend changes. |
| Value/effort | **HIGH** — 3/7 players + 1 FC mentioned. Directly improves second-screen use case. |
| Domain fidelity | FC-01: Real MCC has distinct audio tones for each alert level. |
| Test coverage | Audio is hard to unit-test, but visual flash can be CSS-tested via Playwright. |

**Implementation plan:**
- Distinct tone patterns: single beep (CAUTION), double beep (WARNING), continuous alarm (ABORT)
- Visual screen-edge flash on advisory level change (CSS animation)
- ABORT gets pulsing red border on the entire shell

**Branch:** `feature/ux-audio-visual-alerts`

---

## P2 — Medium Priority (Survey Recommendations 7–10)

### P2-7: Responsive / Mobile Layout

**Decision: DEFER**

| Criterion | Assessment |
|-----------|------------|
| Viability | Feasible with CSS media queries, but the three-canvas layout is inherently desktop-oriented. |
| Stability risk | Medium — CSS grid changes risk breaking the fixed layout. |
| Value/effort | Low — only 2/7 players mentioned; tablet use is niche. |

**Rationale:** The three-panel layout with real-time canvas rendering is not
well-suited for small screens. A responsive layout would need to stack panels
vertically, losing the simultaneous visibility that makes the tool useful. The
OBS overlay mode (P2-8) partially addresses tablet use by allowing single-panel views.

---

### P2-8: OBS Overlay Mode

**Decision: IMPLEMENT**

| Criterion | Assessment |
|-----------|------------|
| Viability | The `showPanel(name)` Houston API already exists. Add URL parameter routing + transparent background CSS. |
| Stability risk | **LOW** — Additive CSS + URL param parsing, no existing behavior changed. |
| Value/effort | **HIGH** — Enables streaming use case. KSP-07 (content creator, 900 hrs) is a high-value user archetype. |
| Test coverage | URL param parsing testable; CSS overlay mode verifiable via Playwright. |

**Implementation plan:**
- `?overlay=gates` / `?overlay=advisory` / `?overlay=telemetry` URL params
- Transparent background, no shell chrome, just the requested panel
- `?overlay=gates&fontscale=1.5` for presentation mode font scaling
- OBS can capture the browser source with transparent background

**Branch:** `feature/ux-obs-overlay`

---

### P2-9: Trajectory Prediction

**Decision: DEFER**

| Criterion | Assessment |
|-----------|------------|
| Viability | The ballistic projection engine already computes a forward arc from current state. This IS the trajectory predictor. |
| Stability risk | N/A — it already exists. |

**Rationale:** Both FC-01 and FC-02 requested this, but it already exists as the
amber dashed "ballistic projection" arc on the globe and trajectory plot. The
projection shows where the vehicle will end up if current rates continue with no
thrust. The gap is **discoverability** — label it "PREDICTOR" on the legend, add
a tooltip. No code change needed, just labeling.

---

### P2-10: Pre-Launch Countdown and Checklist

**Decision: IMPLEMENT**

| Criterion | Assessment |
|-----------|------------|
| Viability | Frontend-only feature — countdown timer + checklist UI before MET starts. |
| Stability risk | **LOW** — No backend changes. Runs before flight data arrives. |
| Value/effort | Medium — 2/7 players, but strong multiplayer/roleplay immersion value. |
| Domain fidelity | FC advisors confirm: pre-launch checklist is standard ops. |

**Implementation plan:**
- Collapsible pre-launch panel with default checklist items
- Items: TELEMETRY LINK, VEHICLE CONFIG, FLIGHT RULES, SAS ENABLE, THROTTLE SET
- Manual check-off (click to toggle)
- Countdown timer (T-10 to T-0) with visual/audio cues
- Auto-dismiss when MET > 0 (flight detected)

**Branch:** `feature/ux-prelaunch-checklist`

---

## P3 — Low Priority (Survey Recommendations 11–15)

### P3-11: Consumables Trending

**Decision: IMPLEMENT**

| Criterion | Assessment |
|-----------|------------|
| Viability | Straightforward — compute burn rate from consecutive fuel readings, extrapolate time-to-depletion. |
| Stability risk | **LOW** — Backend adds two computed fields to telemetry state; frontend displays them. |
| Value/effort | Medium — FC-01 specifically requested this as an early off-nominal indicator. |
| Domain fidelity | **HIGH** — "That's what PROP watches" (FC-01). |
| Test coverage | Pure arithmetic — fully testable. |

**Implementation plan:**
- Server-side: compute `lf_burn_rate` (units/s) and `lf_time_to_depletion` (s) from consecutive states
- Frontend: display burn rate + time-to-depletion below fuel bars
- Smooth with exponential moving average to avoid noise spikes

**Branch:** `feature/ux-consumables-trending`

---

### P3-12: Alternative Telemetry Backends (kRPC)

**Decision: DECLINE**

**Rationale:** kRPC/KRPC2 support requires a completely different protocol layer
(protobuf + RPC vs. WebSocket + JSON). The `TelematicusClient` interface is clean
and any new backend would implement the same `get_state()/get_trajectory()` API,
but the protocol work is substantial. The Telemachus topic name documentation
issue is addressed by the existing `telemachus_schema.json` reference. This is a
separate integration project, not a UX fix.

---

### P3-13: Customizable Mission Branding

**Decision: IMPLEMENT**

| Criterion | Assessment |
|-----------|------------|
| Viability | Simple — read mission name from URL param or server config, apply to title + topbar + MissionControl API. |
| Stability risk | **VERY LOW** — String substitution only. |
| Value/effort | Medium — specifically requested by content creator (KSP-07). |

**Implementation plan:**
- `?mission=NAME` URL parameter overrides "PERSEUS 1" in topbar
- `window.MissionControl.mission` reflects the custom name
- Server-side `--mission-name` CLI arg sets default for all clients

**Branch:** `feature/ux-custom-branding`

---

### P3-14: Flight Efficiency Scoring

**Decision: IMPLEMENT**

| Criterion | Assessment |
|-----------|------------|
| Viability | Post-flight summary comparing actual vs nominal: gravity loss ratio, fuel remaining, orbital accuracy. |
| Stability risk | **LOW** — Read-only computation from existing trajectory data. |
| Value/effort | Medium — gamification for intermediate players (KSP-03, KSP-04). |
| Test coverage | Pure arithmetic — fully testable. |

**Implementation plan:**
- Compute score when ORBIT phase detected: gravity loss efficiency, fuel margin, Ap/Pe accuracy
- Display as a scorecard overlay (0–100 rating)
- Accessible via `window.MissionControl.getFlightScore()`

**Branch:** `feature/ux-flight-scoring`

---

### P3-15: Text-to-Speech Callouts

**Decision: DEFER**

| Criterion | Assessment |
|-----------|------------|
| Viability | Browser `SpeechSynthesis` API is available but inconsistent across browsers/OS. |
| Stability risk | Low, but unreliable cross-platform behavior is worse than no feature. |
| Value/effort | Low — 1/7 players. Enhanced audio alerts (P1-6) cover most of the need. |

**Rationale:** The enhanced audio alert system (P1-6) with distinct tones per
level addresses the "I can't always see the advisory" problem. TTS adds
complexity and cross-browser fragility for marginal gain. Defer until audio
alerts are validated with users.

---

## Individual Respondent Suggestions — Additional Assessment

### FC-01: Booster SEP Confirmation Gate

**Decision: IMPLEMENT**

| Criterion | Assessment |
|-----------|------------|
| Domain fidelity | **HIGH** — "SRB separation is a major event with its own Go/No-Go." |
| Stability risk | **LOW** — Adds a gate before the existing CORE B/O gate, no existing gates change. |
| Test coverage | Deterministic — testable with the existing `telemetry_state` fixtures. |

**Implementation:** Add BOOSTER SEP gate to `assess_gates()` — GO if solid_fuel
dropped to 0 with altitude/velocity within bounds, MARGINAL if sep timing was
off-nominal.

**Branch:** `feature/ux-booster-sep-gate`

---

### FC-01: Nominal Pitch Reference in Advisory

**Decision: IMPLEMENT**

| Criterion | Assessment |
|-----------|------------|
| Domain fidelity | **HIGH** — "Steep relative to what? Add the nominal pitch." |
| Stability risk | **LOW** — Changes advisory text format only. |

**Implementation:** When generating pitch advisories in `generate_advisory()`,
include the nominal pitch value: `"PITCH TOWARD HORIZON (+22° STEEP, NOM 38°)"`.

**Branch:** `feature/ux-advisory-pitch-reference`

---

### FC-02: Consumables Trending

Covered by P3-11 above. **IMPLEMENT**.

---

### FC-02: Globe Hover Tooltips

**Decision: DEFER**

**Rationale:** Canvas hit-testing for trajectory points requires significant
implementation. The trajectory plot already shows altitude/downrange as axes.
Lower priority than other globe improvements.

---

### FC-02: Flight Rule Reference

**Decision: DEFER**

**Rationale:** Requires building a flight rules database. The advisory already
shows the triggering condition in the `reason` field. A formal flight rules
system is future work.

---

### FC-02: Fault Injection Scenarios

**Decision: DEFER**

**Rationale:** The scenario system partially addresses this (abort_steep preset),
but true fault injection (engine underperformance, early SRB sep) requires sim
modifications. Separate feature.

---

### KSP-06: Mission Event Log

**Decision: IMPLEMENT**

| Criterion | Assessment |
|-----------|------------|
| Value/effort | **HIGH** — Foundation for mission replay, multiplayer debrief, stream highlights. |
| Stability risk | **LOW** — Additive — log events without changing existing behavior. |

**Implementation:** Track phase transitions, gate status changes, and advisory
level changes with MET timestamps. Display in a scrollable panel. Exportable
as text.

**Branch:** `feature/ux-mission-event-log`

---

### KSP-07: OBS Overlay Mode

Covered by P2-8 above. **IMPLEMENT**.

---

### KSP-07: Event Log with Timestamps

Covered by KSP-06/Task #9 above. **IMPLEMENT**.

---

## Implementation Priority Order

Based on stability risk, value/effort, and dependency ordering:

| Order | Task | Branch | Risk | Rationale |
|-------|------|--------|------|-----------|
| 1 | Booster SEP Gate (FC-01) | `feature/ux-booster-sep-gate` | Low | Backend-only, high domain value, clean addition |
| 2 | Advisory Pitch Reference (FC-01) | `feature/ux-advisory-pitch-reference` | Low | Backend-only, improves advisory clarity |
| 3 | Consumables Trending (P3-11) | `feature/ux-consumables-trending` | Low | Backend compute + frontend display |
| 4 | Audio/Visual Alert Escalation (P1-6) | `feature/ux-audio-visual-alerts` | Low | Frontend-only, high user impact |
| 5 | Mission Event Log (KSP-06/07) | `feature/ux-mission-event-log` | Low | Frontend + server, foundation for replay |
| 6 | OBS Overlay Mode (P2-8) | `feature/ux-obs-overlay` | Low | Frontend-only, streaming enablement |
| 7 | Custom Branding (P3-13) | `feature/ux-custom-branding` | Very Low | String substitution |
| 8 | Pre-Launch Checklist (P2-10) | `feature/ux-prelaunch-checklist` | Low | Frontend-only, immersion |
| 9 | Flight Efficiency Scoring (P3-14) | `feature/ux-flight-scoring` | Low | Post-flight computation |

---

## Deferred Items Summary

| Item | Reason | Revisit When |
|------|--------|-------------|
| P0-1: Vehicle Generalization | Requires vehicle profile + flight rules system | Next design cycle |
| P0-2: Installation Simplification | Packaging/infra work, not code | Dedicated packaging sprint |
| P0-3: Onboarding Overlay | Needs UX design iteration | After core UX improvements ship |
| P1-4: Post-Ascent Phases | Major feature, different advisory framework | Separate product feature |
| P1-5: Mission Persistence | Server-side file I/O complexity | After event log validates the concept |
| P2-7: Mobile Layout | Desktop tool by design; overlay mode helps | If tablet adoption grows |
| P2-9: Trajectory Prediction | Already exists as ballistic projection | Label it "PREDICTOR" (doc fix) |
| P3-15: TTS Callouts | Cross-browser fragility | After audio alerts validated |

---

## Declined Items

| Item | Reason |
|------|--------|
| P3-12: kRPC Backend | Separate integration project, different protocol layer |

---

## Completed Implementations

*Updated as features are merged.*

| Item | Branch | Tests | Status |
|------|--------|-------|--------|
| — | — | — | Implementation starting |

---

*Review conducted 2026-06-26 by the UX Review Team. Next review cycle after
implementation round completes.*
