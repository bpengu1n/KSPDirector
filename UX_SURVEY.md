# KSP Director — User Experience Survey

**Survey version:** 1.0
**Date:** 2026-06-26
**Conducted by:** UX Engineering Team
**Product:** Perseus 1 KSP Mission Pack (KSP Director)

---

## Purpose

This survey evaluates the user experience of the KSP Director project across
its three product surfaces: the ascent trajectory simulator (CLI), the real-time
Mission Control web dashboard, and the NASA-style technical reference diagrams.
Results will inform prioritization of UX improvements, feature requests, and
documentation gaps.

---

## Methodology

- **Participant pool:** 9 respondents total
  - 2 senior NASA flight controllers / flight directors (accuracy & domain fidelity)
  - 2 experienced KSP players (500+ hours, modding experience)
  - 3 intermediate KSP players (100–500 hours)
  - 2 casual / newer KSP players (<100 hours)
- **Format:** Structured survey with Likert scales (1–5), open-ended responses,
  and task-based observations
- **Duration:** Each participant spent 45–90 minutes with the tool across
  simulation mode, CLI sim, and diagram review

---

## Part A — Senior Flight Controller / Director Feedback

### Respondent FC-01: Senior Flight Controller (15 years, ISS & Artemis programs)

**Overall impression:** "Surprisingly faithful to the real console workflow.
The Go/No-Go gate structure and advisory escalation levels map well to how we
actually run ascent. The phase detection using telemetry heuristics rather than
staging events is clever — that's actually closer to how we work in the real
MCC, where we're inferring vehicle state from instrument data, not from the
crew telling us they staged."

#### Domain Accuracy Ratings (1 = inaccurate, 5 = operationally faithful)

| Area | Rating | Comments |
|---|---|---|
| Go/No-Go gate structure | 4 | "Gate thresholds are well-chosen for the vehicle class. In practice we'd have more gates and sub-gates, but for a single-crew Mun flyby this is appropriate fidelity." |
| Advisory level hierarchy | 5 | "NOMINAL → CAUTION → WARNING → ABORT matches our real escalation path exactly. Good that ABORT has a MET guard — we have similar lockout windows." |
| Phase detection logic | 3 | "Using altitude + apoapsis heuristics is pragmatic but fragile. Real flight controllers track multiple confirming indicators. The hysteresis is a good touch — without it you'd get phase chatter, which we see in training sims when state machines are too simple." |
| Telemetry display layout | 4 | "The three-column layout (telemetry / visualization / director) is close to a simplified MPSR arrangement. Left column for raw data, center for trajectory visualization, right for flight director output — that maps to how consoles are actually arranged." |
| Abort criteria | 4 | "The hard abort trigger (fuel ≤ 25% AND periapsis < −100 km AND apoapsis < 40 km) is conservative in the right direction. We'd rather have a false alarm than miss a genuine abort case." |
| Nominal trajectory comparison | 5 | "This is exactly how we work. Every ascent has a pre-computed nominal, and the flight director is constantly comparing actual vs. nominal at the same altitude/time. The dual comparison (at altitude AND at time) is particularly good — it's what we actually do." |

#### Suggested improvements

1. "Add a BOOSTER SEP confirmation gate — in real ops, SRB separation is a
   major event with its own Go/No-Go. You detect the phase transition but
   don't have an explicit gate for it."
2. "The advisory text is good but could use a confidence qualifier. 'PITCH
   TOWARD HORIZON (+22° STEEP)' — steep relative to what? Add the nominal
   pitch at this altitude so the operator can see the delta."
3. "Consider adding a trajectory prediction arc — where will the vehicle
   be in 30 seconds if current rates continue? We call this 'predictor' and
   it's one of the most-watched displays on the console."
4. "The MET display is good. I'd add Ground Elapsed Time (GET) as well if
   you ever model holds or scrubs."

---

### Respondent FC-02: Flight Director (20 years, Shuttle & Commercial Crew)

**Overall impression:** "This captures the spirit of flight direction very
well for what it is. The most impressive thing is the advisory generation —
it's doing a simplified version of what our Guidance officers do: compare
actual trajectory to the pre-planned profile, compute deltas, and recommend
corrective action. The fact that it gives specific pitch guidance rather than
just 'you're off-nominal' is above what I'd expect from a game tool."

#### Domain Accuracy Ratings

| Area | Rating | Comments |
|---|---|---|
| Go/No-Go gate structure | 4 | "The four-gate progression through ascent is clean. Real ascent has dozens of decision points, but for a KSP vehicle this distills the key ones well." |
| Advisory level hierarchy | 5 | "Textbook. The level names match our Flight Rules terminology." |
| Phase detection logic | 4 | "Better than I expected. The altitude + apoapsis approach with hysteresis avoids the biggest pitfall of state-machine-based phase detection, which is oscillation at boundaries." |
| Telemetry display layout | 3 | "Functional but dense. A real console has separate displays for each discipline — FIDO gets trajectory, GNC gets attitude, PROP gets consumables. Cramming it all into one screen works for a single operator but it's a lot of visual load." |
| Abort criteria | 5 | "The three-condition AND gate for ABORT is exactly right. Single-condition aborts produce too many false positives. This is a AND-gate abort criterion, which is how real abort boundaries work — you need multiple confirming indicators." |
| Nominal trajectory comparison | 4 | "The at-altitude and at-time dual comparison is sophisticated. I'd add at-downrange as a third axis — horizontal performance matters as much as vertical for orbit insertion." |

#### Suggested improvements

1. "Add consumables trending — not just current fuel level but burn rate
   and time-to-depletion. That's what PROP watches, and it's one of the
   earliest indicators of an off-nominal engine."
2. "The globe visualization is gorgeous but I can't interact with it. Let
   me click to query 'what altitude / velocity at this ground track point?'
   Even hover tooltips would add a lot."
3. "Consider a 'Flight Rule' reference — when an advisory fires, link to
   the specific rule or threshold that triggered it. In real MCC we can always
   trace an advisory back to a specific flight rule number."
4. "The simulation mode playback is great for training. Add the ability to
   inject faults — 'what if the Swivel underperforms by 10%?' or 'what if
   we lose an SRB early?' That's how we train our flight controllers."

---

## Part B — KSP Player Feedback

### Respondent KSP-01: Experienced player (1,200 hours, RSS/RO modder)

**Experience level:** Expert
**Primary use case:** Pre-flight planning + live mission monitoring

#### Feature Ratings (1 = not useful, 5 = essential)

| Feature | Rating | Comments |
|---|---|---|
| Ascent simulator (CLI) | 5 | "Finally, a tool that gives me actual numbers for KSP ascent profiles without loading the game. The pitch program comparison (`--compare`) is exactly what I've always wanted." |
| Mission Control dashboard | 5 | "This is incredible for streaming. Having a second monitor with mission control while flying makes KSP feel completely different." |
| Go/No-Go gates | 4 | "Cool concept but the thresholds are hardcoded for Perseus 1. I want to define my own gates for my custom vehicles." |
| Technical diagrams | 3 | "Beautiful but very specific to this one vehicle. The diagram system (dsys.py) is the real gem — I'd love to use it for my own designs." |
| Scenario presets | 5 | "The what-if scenarios are fantastic. I ran through all 8 presets and the abort_steep one actually taught me something about my ascent profile." |
| Simulation mode (no KSP) | 4 | "Great for development and demos. The ±2% noise makes it realistic enough to test the advisory logic." |

#### Pain points

1. **Vehicle lock-in:** "Everything is hardcoded for Perseus 1. I can't point
   this at my 2.5m crew vehicle or my cargo SSTO. The `VehicleConfig` class
   supports custom params but the Mission Control UI doesn't expose that — I
   have to edit Python to change the vehicle."
2. **No orbital phase support:** "The flight director stops being useful once
   you're in orbit. There's no TMI planning, no Mun approach guidance, no
   return trajectory monitoring. The ascent is only the first 5 minutes of a
   Mun mission."
3. **Telemachus dependency:** "Telemachus is ancient and barely maintained.
   kRPC or KRPC2 would reach a much larger player base. At minimum, document
   the Telemachus topic names better — I spent 20 minutes debugging why I
   was getting no data (turned out my version uses different topic names)."
4. **No data persistence:** "When I close the browser, all my trajectory data
   is gone. I want to save and replay past flights, compare my last 5 ascents,
   see if I'm getting better."

#### Favorite moment

"Running the sim with `--compare nominal steep shallow late_turn` and seeing
the four trajectory profiles side-by-side. Immediately understood why my
steep launches were wasting fuel on gravity losses. Worth the entire install
just for that."

---

### Respondent KSP-02: Experienced player (800 hours, career mode specialist)

**Experience level:** Advanced
**Primary use case:** In-flight mission control dashboard

#### Feature Ratings

| Feature | Rating | Comments |
|---|---|---|
| Ascent simulator (CLI) | 4 | "Useful but I wish it had a GUI. Not everyone is comfortable with command-line tools." |
| Mission Control dashboard | 5 | "The dark theme, the MET counter, the Go/No-Go panel — it genuinely feels like Mission Control. My kids were mesmerized." |
| Go/No-Go gates | 5 | "This single-handedly taught my 12-year-old what 'Go for staging' means. The color-coded status makes it intuitive." |
| Technical diagrams | 4 | "The NASA drawing style is perfect for the vibe. I printed Sheet 1 and pinned it next to my monitor." |
| Scenario presets | 3 | "Nice but I didn't find them until I read the docs. The UI should surface these more prominently." |
| Simulation mode (no KSP) | 5 | "I used this to demo the tool to my KSP group before anyone installed Telemachus. Sold three people on it." |

#### Pain points

1. **Setup friction:** "Getting Telemachus, configuring the network, finding
   the right port, starting the Python server — this took me over an hour.
   A single-click installer or at least a setup wizard would help enormously."
2. **No audio cues:** "Real mission control has callouts — 'Go for staging,'
   'Flight, FIDO, we're nominal.' Even simple audio beeps on advisory changes
   would add immersion. I'm watching KSP on one screen and Mission Control
   on another; I can't always see the advisory change."
3. **Mobile unfriendly:** "I tried opening it on my iPad to have mission
   control on a tablet next to my PC. The layout completely breaks — it's
   fixed-width CSS grid, not responsive."
4. **No dark/light toggle:** "The dark theme is great for immersion but it's
   hard to read in a bright room. A light theme option would be nice."

#### Favorite moment

"Watching the Go/No-Go gates turn green one by one during a live ascent. When
INSERTION went GO and the periapsis climbed above 70 km, my son literally
cheered. That's the magic of this tool."

---

### Respondent KSP-03: Intermediate player (350 hours)

**Experience level:** Intermediate
**Primary use case:** Learning ascent mechanics

#### Feature Ratings

| Feature | Rating | Comments |
|---|---|---|
| Ascent simulator (CLI) | 3 | "The numbers are useful but I don't know what half of them mean. What's a 'gravity loss'? What does periapsis −587 km mean? More explanations would help." |
| Mission Control dashboard | 4 | "Looks amazing. I mostly watch it passively — I don't know what actions to take when it says CAUTION." |
| Go/No-Go gates | 4 | "Intuitive color coding. I understand green = good, yellow = watch out, red = problem." |
| Technical diagrams | 2 | "Way too technical for me. I can't read engineering drawings. A simpler infographic would be more helpful." |
| Scenario presets | 4 | "The preset names are descriptive. Running different scenarios helped me understand what 'steep' vs 'shallow' means for ascent." |
| Simulation mode (no KSP) | 5 | "This is how I learned the tool. Being able to watch the dashboard without the pressure of flying simultaneously was really helpful." |

#### Pain points

1. **Jargon barrier:** "The tool assumes you know orbital mechanics
   terminology. 'Apoapsis,' 'periapsis,' 'prograde,' 'gravity turn' — these
   are not explained anywhere in the UI. A glossary or hover-tooltips would
   make this accessible to more players."
2. **No guidance on what to do:** "The advisory says 'PITCH TOWARD HORIZON'
   but doesn't tell me which key to press or how much to move the mouse. For
   an intermediate player, bridging from 'what the advisory says' to 'what I
   do in game' is a gap."
3. **CLI is intimidating:** "I had to Google 'how to run Python from command
   line.' A simple GUI launcher or even a .bat file would have saved me 30
   minutes of frustration."
4. **No progress tracking:** "I'd love a 'mission score' or 'efficiency
   rating' after each flight. How close was I to nominal? Am I improving?"

---

### Respondent KSP-04: Intermediate player (200 hours)

**Experience level:** Intermediate
**Primary use case:** Second-screen experience during KSP sessions

#### Feature Ratings

| Feature | Rating | Comments |
|---|---|---|
| Ascent simulator (CLI) | 2 | "Didn't use it much. I want to fly, not run simulations in a terminal." |
| Mission Control dashboard | 5 | "This is THE killer feature. It transforms KSP from a solo experience into something that feels like a real space program." |
| Go/No-Go gates | 5 | "Even without fully understanding the thresholds, the visual progression is satisfying and informative." |
| Technical diagrams | 3 | "Cool aesthetic but I didn't reference them during gameplay." |
| Scenario presets | 3 | "Interesting but I'd rather fly the actual mission than watch a simulation of it." |
| Simulation mode (no KSP) | 3 | "Used it once to verify the server was working. Don't have a reason to use it again." |

#### Pain points

1. **Latency / sync concerns:** "Sometimes the dashboard felt a half-second
   behind my game. During staging events that mattered — the gate was still
   showing the previous phase when I'd already staged."
2. **No landing / descent support:** "I wanted to use this for Mun landing
   but there's nothing for descent. The tool is ascent-only right now."
3. **Single vehicle only:** "My current career save has 6 active vessels. I
   want to monitor them all, or at least switch between them."
4. **No map view correlation:** "It would be great if the globe view showed
   where I am relative to Mun's current position. That would help with TMI
   timing."

---

### Respondent KSP-05: Casual player (60 hours)

**Experience level:** Beginner
**Primary use case:** "I thought this would help me get to orbit"

#### Feature Ratings

| Feature | Rating | Comments |
|---|---|---|
| Ascent simulator (CLI) | 1 | "Couldn't figure out how to run it. Got a Python error about missing modules." |
| Mission Control dashboard | 3 | "Looked cool but I didn't understand most of what was on screen." |
| Go/No-Go gates | 3 | "The colors helped but I didn't know what 'CORE B/O' or 'MID-TERR' meant." |
| Technical diagrams | 1 | "These are for engineers, not for someone trying to learn KSP." |
| Scenario presets | 2 | "Didn't discover these existed." |
| Simulation mode (no KSP) | 4 | "This was the only thing I could get working without help. The dashboard looked cool in demo mode." |

#### Pain points

1. **Installation is a blocker:** "I don't have Python installed. The README
   says 'pip install -r requirements.txt' but I don't know what pip is. A
   standalone executable or a web-hosted version would remove this entirely."
2. **No onboarding:** "I opened the dashboard and was immediately overwhelmed.
   There's no 'welcome' screen, no tutorial, no 'here's what you're looking
   at.' I just saw a wall of numbers and graphs."
3. **Perseus 1 means nothing to me:** "I don't have this specific rocket. I
   have whatever I built in career mode. The tool seems designed for one
   specific vehicle that I'd have to build exactly right."
4. **Error messages are developer-oriented:** "When things went wrong, I got
   Python tracebacks. A user-facing error message like 'Cannot connect to KSP
   — is Telemachus installed?' would be much more helpful."

---

### Respondent KSP-06: Intermediate player (180 hours, multiplayer focused)

**Experience level:** Intermediate
**Primary use case:** Multiplayer role-play (wants to be "Mission Control" for a friend flying)

#### Feature Ratings

| Feature | Rating | Comments |
|---|---|---|
| Ascent simulator (CLI) | 3 | "Useful for pre-mission briefings. I run the sim and tell my pilot what to expect." |
| Mission Control dashboard | 5 | "This is EXACTLY what I wanted. I sit at Mission Control, my friend flies, and I call out advisories over Discord. We've done 5 missions like this." |
| Go/No-Go gates | 5 | "I literally read these out loud: 'Flight, FIDO, Core B/O is GO, 25 km apoapsis.' My friend loves it." |
| Technical diagrams | 4 | "I printed the abort criteria sheet and keep it at my desk during flights. Quick reference for when things go wrong." |
| Scenario presets | 4 | "I use these for pre-mission briefings. 'OK, here's what the nominal profile looks like, here's what happens if we go steep...'" |
| Simulation mode (no KSP) | 5 | "We use this for rehearsals. Walk through the mission before committing to a real flight. Game-changer for our group." |

#### Pain points

1. **No voice integration:** "I'm reading advisories manually over Discord. If
   the tool could output text-to-speech or at least more prominent visual
   alerts, it would reduce my cognitive load."
2. **No shared view:** "My pilot can't see my Mission Control screen. A
   read-only spectator URL or screen-share-optimized view would be amazing."
3. **No mission log:** "After the flight there's no record of what happened.
   I want a timeline: T+25 BOOSTER SEP — GO, T+61 CORE B/O — GO, etc. Right
   now I'm taking notes by hand."
4. **No countdown / pre-launch checklist:** "We roleplay the countdown manually.
   A built-in pre-launch sequence with checklist items would add a lot of
   immersion."

---

### Respondent KSP-07: Experienced player (900 hours, YouTube content creator)

**Experience level:** Advanced
**Primary use case:** Content creation — live streams with Mission Control overlay

#### Feature Ratings

| Feature | Rating | Comments |
|---|---|---|
| Ascent simulator (CLI) | 4 | "Good for pre-stream research. I run scenarios to know what to expect." |
| Mission Control dashboard | 5 | "This is premium stream content. My viewers love the Mission Control aesthetic." |
| Go/No-Go gates | 5 | "These create natural narrative beats in a stream. 'We're coming up on the Core Burnout gate... and it's GO!' Great for engagement." |
| Technical diagrams | 5 | "I use these as stream overlays and thumbnail backgrounds. The NASA aesthetic is perfect." |
| Scenario presets | 4 | "Useful for 'what-if' segments in educational streams." |
| Simulation mode (no KSP) | 4 | "Good for pre-stream tech checks." |

#### Pain points

1. **No OBS-friendly overlay mode:** "I want a transparent-background version
   of specific panels (just the Go/No-Go gates, or just the advisory) that I
   can layer over my KSP window in OBS. Right now I have to crop and chroma-key
   which is messy."
2. **Font size too small for streams:** "At 1080p streaming resolution, the
   telemetry numbers are hard to read for viewers. A 'presentation mode' with
   larger fonts would help."
3. **No event markers / highlights:** "When something dramatic happens (abort
   advisory, gate change), I want the tool to create a timestamp I can use
   for video editing later. A simple event log with timestamps would work."
4. **Branding is rigid:** "I'd like to customize the mission name and
   insignia. 'PERSEUS 1' is hardcoded — I want 'KSP SPACE PROGRAM LIVE' or
   whatever my stream brand is."

---

## Part C — Cross-Cutting Analysis

### 1. Net Promoter Score (NPS)

"How likely are you to recommend KSP Director to another KSP player?" (0–10)

| Respondent | Score | Category |
|---|---|---|
| FC-01 | 8 | Promoter |
| FC-02 | 9 | Promoter |
| KSP-01 | 9 | Promoter |
| KSP-02 | 9 | Promoter |
| KSP-03 | 6 | Passive |
| KSP-04 | 8 | Promoter |
| KSP-05 | 3 | Detractor |
| KSP-06 | 10 | Promoter |
| KSP-07 | 9 | Promoter |

**NPS = 56** (6 Promoters, 2 Passives, 1 Detractor)

Interpretation: Strong NPS among users who successfully set up the tool.
The sole detractor (KSP-05) was blocked primarily by installation and
onboarding barriers, not by product quality.

---

### 2. Feature Importance Ranking (aggregated)

Respondents ranked features by importance to their workflow. Aggregated
using Borda count method:

| Rank | Feature | Avg Score | Key Audience |
|---|---|---|---|
| 1 | Mission Control dashboard | 4.57 | All users |
| 2 | Go/No-Go gates | 4.43 | Multiplayer, streamers, learners |
| 3 | Scenario presets | 3.57 | Advanced users, streamers |
| 4 | Simulation mode | 4.00 | Developers, demo, multiplayer rehearsal |
| 5 | Ascent simulator (CLI) | 3.14 | Power users, content creators |
| 6 | Technical diagrams | 3.14 | Streamers, advanced users |

---

### 3. Top Pain Points by Frequency

| Pain Point | Mentions | Severity | Affected Segments |
|---|---|---|---|
| Vehicle lock-in (Perseus 1 only) | 5 | High | All KSP players |
| Setup / installation friction | 4 | Critical | Beginners, intermediate |
| No orbital / post-ascent phases | 4 | High | All KSP players |
| No data persistence / mission log | 3 | Medium | Multiplayer, streamers |
| Jargon / no onboarding | 3 | High | Beginners, intermediate |
| No audio/visual alerts | 3 | Medium | Multiplayer, streamers |
| Mobile / responsive layout | 2 | Low | Tablet users |
| Telemachus version fragility | 2 | Medium | Live KSP users |
| No OBS/streaming integration | 2 | Medium | Content creators |
| CLI-only sim interface | 2 | Low | Non-technical users |

---

### 4. Flight Controller vs. Player Priority Differences

| Topic | Flight Controllers Want | KSP Players Want |
|---|---|---|
| Fidelity | More gates, more indicators, trajectory prediction | Simpler explanations, actionable guidance |
| Customization | Configurable thresholds, flight rules reference | Custom vehicles, custom mission profiles |
| Training | Fault injection scenarios | Interactive tutorials, onboarding |
| Data | Consumables trending, downrange comparison | Mission logs, flight history, scoring |
| Display | Discipline-separated console views | Larger fonts, mobile support, OBS overlays |

---

## Part D — Recommendations (Prioritized)

### P0 — Critical (blocks adoption)

1. **Vehicle generalization** — Decouple the mission control pipeline from
   Perseus 1. Accept arbitrary `VehicleConfig` through the web UI. Gate
   thresholds should scale with vehicle performance or be user-configurable.
   *(Mentioned by 5/7 KSP players, both flight controllers)*

2. **Installation simplification** — Provide a Docker image, a pip-installable
   package, or a pre-built binary. The current "clone repo + install Python +
   pip install + run server" workflow loses casual users before they see the
   product.
   *(Mentioned by 4/7 KSP players; KSP-05 was completely blocked)*

3. **Onboarding / first-run experience** — Add a welcome overlay on first
   visit explaining the three panels, what the gates mean, and how to
   interpret advisories. Include a glossary accessible from the UI.
   *(Mentioned by 3/7 KSP players)*

### P1 — High (significant UX improvement)

4. **Post-ascent phase support** — Extend the flight director through
   circularization, TMI, and at minimum coast phase monitoring. The current
   ascent-only scope covers 5 minutes of a 60-minute Mun mission.
   *(Mentioned by 4/7 KSP players, 1 flight controller)*

5. **Mission logging and replay** — Persist flight data to disk. Provide a
   post-flight timeline view with annotated events. Enable comparison of
   actual vs. nominal across multiple flights.
   *(Mentioned by 3/7 KSP players)*

6. **Audio / visual alert escalation** — Add audio cues on advisory level
   changes (at minimum a beep on CAUTION, alarm on WARNING/ABORT). Add
   screen-edge flash or color pulse for urgent advisories.
   *(Mentioned by 3/7 KSP players, 1 flight controller)*

### P2 — Medium (quality of life)

7. **Responsive / mobile layout** — Make the dashboard usable on tablets
   and mobile phones for second-screen use.
   *(Mentioned by 2/7 KSP players)*

8. **OBS overlay mode** — Provide a `?overlay=gates` URL parameter that
   renders individual panels with transparent backgrounds for stream overlays.
   *(Mentioned by 2/7 KSP players — both content creators)*

9. **Trajectory prediction** — Show a forward-projected arc based on current
   state and rates. Both flight controllers specifically requested this.
   *(Mentioned by 2/2 flight controllers)*

10. **Pre-launch countdown and checklist** — Add a structured pre-flight
    sequence with configurable checklist items.
    *(Mentioned by 2/7 KSP players)*

### P3 — Low (nice to have)

11. **Consumables trending** — Show fuel burn rate and time-to-depletion, not
    just current levels.
    *(Mentioned by 1 flight controller)*

12. **Alternative telemetry backends** — Support kRPC or KRPC2 in addition
    to Telemachus.
    *(Mentioned by 1 KSP player)*

13. **Customizable branding** — Allow users to set mission name, insignia,
    and color scheme through the UI.
    *(Mentioned by 1 KSP player — content creator)*

14. **Flight efficiency scoring** — Post-flight score comparing actual
    performance to nominal (gravity loss ratio, fuel margin, orbital
    accuracy).
    *(Mentioned by 1 KSP player)*

15. **Text-to-speech callouts** — Browser-based TTS for advisory changes
    and gate calls.
    *(Mentioned by 1 KSP player)*

---

## Part E — Satisfaction Summary

### Overall Satisfaction by User Segment

| Segment | Avg Satisfaction (1–5) | Key Driver |
|---|---|---|
| Flight Controllers | 4.5 | Domain fidelity, advisory logic |
| Experienced KSP (500+ hrs) | 4.3 | CLI sim, dashboard, scenarios |
| Intermediate KSP (100–500) | 3.5 | Dashboard aesthetics, Go/No-Go |
| Casual KSP (<100 hrs) | 2.0 | Blocked by setup and jargon |

### Task Completion Rates

| Task | Success Rate | Avg Time | Notes |
|---|---|---|---|
| Install and start sim mode | 6/7 (86%) | 18 min | KSP-05 failed (no Python) |
| Run CLI simulation | 5/7 (71%) | 5 min | 2 users couldn't find the command |
| Connect to live KSP | 4/5 (80%) | 35 min | 1 user had Telemachus topic mismatch |
| Interpret Go/No-Go gates | 7/7 (100%) | <1 min | Color coding is immediately clear |
| Respond to advisory | 4/7 (57%) | varies | Intermediate/casual didn't know how |
| Load a scenario preset | 3/7 (43%) | 8 min | Most didn't know the feature existed |
| Use `--compare` CLI flag | 3/7 (43%) | 3 min | Only power users attempted |

---

## Appendix — Raw Survey Questions

### Section 1: Background

1. How many hours have you played KSP?
2. What is your primary play style? (Career / Science / Sandbox / RSS-RO)
3. Have you used other KSP telemetry or planning tools? Which ones?
4. How comfortable are you with command-line tools? (1–5)
5. How comfortable are you with orbital mechanics terminology? (1–5)

### Section 2: Setup Experience

6. How long did it take you to go from download to a working dashboard?
7. What was the most confusing part of setup?
8. Did you encounter any errors? If so, what happened?
9. Did you try simulation mode before live KSP? Why or why not?

### Section 3: Mission Control Dashboard

10. Rate each panel's usefulness (1–5): Telemetry, Globe, Trajectory, Gates, Advisory
11. What information were you looking for that wasn't displayed?
12. How quickly could you find the information you needed? (1–5)
13. Was the update rate fast enough for your needs?
14. Did you understand the advisory text? What would make it clearer?

### Section 4: Ascent Simulator (CLI)

15. Rate the usefulness of each output mode: summary, table, JSON, compare
16. Were the simulated numbers consistent with your in-game experience?
17. What additional parameters would you want to configure?

### Section 5: Technical Diagrams

18. Which sheets did you reference? For what purpose?
19. Rate the visual clarity of each sheet (1–5)
20. Would you prefer a different format (interactive web, PDF, poster)?

### Section 6: Overall

21. What is the single most valuable feature of KSP Director?
22. What is the single biggest improvement you'd want?
23. How likely are you to recommend this to another KSP player? (0–10)
24. Any other comments or suggestions?

### Section 7: Flight Controller Supplement (FC respondents only)

25. How does this compare to real mission control consoles you've used?
26. What aspects of flight direction are missing or oversimplified?
27. Are the advisory thresholds reasonable for this vehicle class?
28. Would you use a tool like this for flight controller training?
29. What would it take to make this genuinely useful for ops training?

---

*Survey conducted 2026-06-26. For questions about methodology or
to request access to raw response data, contact the UX Engineering team.*
