<div class="title-page">
  <div class="title-kicker">KERBAL SPACE PROGRAM MISSION PACKAGE</div>
  <h1>Perseus 1</h1>
  <h2>Mun Flyby Vehicle Build and Staging Plan</h2>
  <div class="doc-control-strip">
    <table>
      <tr>
        <td>REV A</td>
        <td>MISSION RULES</td>
        <td>KSC FLIGHT OPS</td>
      </tr>
    </table>
  </div>
  <img class="mission-patch" src="cache/images/openai_codex_gpt-image-2-medium_20260620_212534_6e4465cb.png" alt="Perseus 1 mission patch" />

  <table class="title-table">
    <thead>
      <tr>
        <th>Mission</th>
        <th>Profile</th>
        <th>Vehicle Type</th>
        <th>Recovery</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Perseus 1</td>
        <td>Stock KSP 1 Mun free-return flyby</td>
        <td>1.25 m crewed flyby stack</td>
        <td>Mk1 pod parachute splashdown / landing</td>
      </tr>
    </tbody>
  </table>

  <table class="title-table title-table-narrow">
    <thead>
      <tr>
        <th>Target</th>
        <th>Value</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>Parking orbit</td><td>80 km circular</td></tr>
      <tr><td>TMI burn</td><td>~856 m/s</td></tr>
      <tr><td>Mun periapsis</td><td>15-50 km</td></tr>
      <tr><td>Kerbin return periapsis</td><td>30-35 km</td></tr>
    </tbody>
  </table>

  <p class="title-note"><strong>Purpose:</strong> Baseline flight package for Perseus 1 covering vehicle configuration, staging, ascent and transfer targets, launch criteria, and CAPCOM references for a stock Kerbin-scale Mun free-return mission.</p>
</div>

<div class="page-break"></div>

# Perseus 1
## Mun Flyby Vehicle Build and Staging Plan

**Mission:** Stock KSP 1 Mun free-return flyby on Kerbin scale  
**Profile:** Launch -> 80 km parking orbit -> Trans-Mun Injection -> Mun flyby -> Kerbin return -> parachute recovery  
**Flight rule:** Favor control authority, staging clarity, and usable propellant margin over minimum-mass optimization.

---

## Mission targets

| Metric | Target | Caution band | Why it matters |
|---|---:|---:|---|
| Parking orbit | 75-90 km circular | Pe < 70 km | Gives a clean setup for TMI |
| Circular speed at 80 km | 2279 m/s | Much short of this means incomplete orbit | Quick orbit verification |
| TMI burn | 850-870 m/s | < 830 or > 890 m/s usually means a sloppy setup | Nominal target is about 856 m/s |
| Mun flyby periapsis | 15-50 km | < 10 km risky | Safe and practical flyby window |
| Kerbin return periapsis | 30-35 km | > 38 km shallow, < 25-28 km steep | Good stock reentry corridor |

---

## Vehicle concept

**Perseus 1** is a stock **1.25 m crewed Mun free-return vehicle** configured for disciplined ascent, straightforward staging, and sufficient propellant reserve to absorb ordinary piloting error without loss of mission.

| Design choice | Recommendation | Reason |
|---|---|---|
| Return capsule | Mk1 pod + heat shield + parachute | Light, proven, easy recovery |
| Mission stage | Terrier + FL-T800 | Enough delta-v to finish orbit, inject, and trim return |
| Launch core | Swivel + FL-T800 | Good control authority during ascent |
| Boost assist | 2x Hammer SRBs, thrust-limited | Simple lift-off without wild over-acceleration |
| Aerodynamics | Nose cone atop each Hammer | Cuts ascent drag on the exposed booster tops, helps the core stage reach target apoapsis |
| Stability | 4 fins on the lower core tank, mounted low | Helps keep ascent smooth; stays with the rocket after booster separation |

This is not a minimum-mass design. It is a mission-operations design: conservative enough to remain controllable in ascent, clear in stage management, and adequately margined through injection and return-trajectory trimming.

---

## Full stack, top to bottom

| Section | Order | Part |
|---|---:|---|
| Recovery | 1 | Mk16 Parachute |
| Recovery | 2 | Mk1 Command Pod |
| Avionics | 3 | Small reaction wheel + battery (inline, below pod) |
| Recovery | 4 | Heat Shield (1.25 m) |
| Mission stage | 5 | TR-18A Stack Decoupler |
| Mission stage | 6 | Service Bay (1.25 m) - houses antenna + fuel cells |
| Mission stage | 7 | FL-T800 Fuel Tank |
| Mission stage | 8 | LV-909 "Terrier" Liquid Fuel Engine |
| Launch core | 9 | TR-18A Stack Decoupler |
| Launch core | 10 | FL-T800 Fuel Tank |
| Launch core | 11 | LV-T45 "Swivel" Liquid Fuel Engine |
| Boosters | 12 | 2x TT-38K Radial Decoupler |
| Boosters | 13 | 2x RT-10 "Hammer" Solid Fuel Booster |
| Boosters | 14 | 2x Aerodynamic Nose Cone (1.25 m) |
| Stability | 15 | 4x Basic Fin (on lower core tank) |

---

## Rocket stack and staging overview

The full-page technical diagrams have been moved to **Appendix C** for cleaner presentation and easier print use at the console. The ascent pitch/roll program is in **Appendix D**.

| Stage event | Flight purpose |
|---|---|
| Boosters + Swivel | Clear pad, survive Max Q, raise apoapsis efficiently. |
| Terrier mission stage | Secure orbit, perform TMI, preserve free-return geometry. |
| Capsule-only return | Minimize mass for safe entry and parachute recovery. |

## Recommended editor tweaks

### Thrust and control tuning

| Setting | Recommendation | Acceptable range | Notes |
|---|---:|---:|---|
| Hammer thrust limit | 20% | 15-22% | Lands pad TWR ~1.8, inside the plan's own TWR target band |
| Swivel thrust | 100% | 100% | Leave full power available |
| Swivel gimbal | On | On | Helps with ascent correction |

### Staging checks

| Check | What to confirm |
|---|---|
| Parachute safety | Parachute is not grouped with engine or decoupler events |
| Mission stage safety | Terrier stage is not staged at liftoff |
| Booster release timing | Hammers separate only after burnout |
| Symmetry | Boosters and fins are mirrored correctly |

---

## Design rationale

### Mission-stage reserve
A **Terrier + FL-T800** under the Mk1 return capsule yields **3,458 m/s vacuum delta-v** (~3.46 km/s), calculated with the avionics module and service bay included in dry mass. That reserve covers the required trans-Mun injection (~856 m/s), routine Mun periapsis clean-up, and post-flyby Kerbin reentry targeting, with a margin of ~600 m/s for off-nominal corrections.

### Ascent control authority
The **Swivel** is carried in preference to a Reliant because gimbal authority materially reduces pilot workload during lower-atmosphere steering corrections and stage-transition recovery.

### Booster discipline
At full liftoff mass (~14.05 t with nose cones), the Swivel alone provides a pad TWR of about 1.22 - close to the sluggish floor - so the Hammers exist to carry that up into a controllable range, not to dominate it. **Thrust-limiting the Hammers to 20%** puts combined pad TWR at about **1.8**, right inside the plan's own 1.4-1.8 target band, versus roughly 2.5 if the Hammers were left near 45%. The lower setting also stretches the booster burn from about 5 s (full thrust) to roughly 25 s, which keeps the early climb gentler and pushes Max Q later and milder. Because thrust-limiting an SRB only spreads its fixed total impulse over more time rather than wasting propellant, the Hammers still deliver the same net delta-v to the stack at 20% as at any other setting - only the acceleration profile changes. A useful side effect: the longer burn lets the Swivel consume more core-tank propellant before booster separation, so TWR stays close to ~1.8 through that transition too, rather than dipping.

### Ascent drag
Each Hammer's top is exposed directly to the airstream for the whole boosted ascent, with nothing above to shield it. A small **Aerodynamic Nose Cone** on each booster cuts that drag at negligible mass cost (~0.03 t each) and helps the core stage carry more of its own weight toward the 70-85 km apoapsis target, rather than leaning as hard on the Terrier to finish the climb.

### Booster mounting and plume clearance
Mount the two Hammers so their **nozzle exits sit at or slightly above the Swivel's nozzle** - i.e. the booster bodies hang high against the core tank, not clustered low around the Swivel bell. If a Hammer is mounted low, with its nozzle hanging below the Swivel's, the Swivel's exhaust plume can wash across the booster body during ascent and cause heat damage or an unplanned booster failure. Keeping the tops high on the core tank routes both the Swivel's plume and the Hammers' own exhaust cleanly downward in parallel, with no impingement. Also keep a small radial offset between booster and tank so the boosters separate cleanly without clipping the core. A quick in-flight confirmation: right-click a Hammer during the first seconds of boost and watch its temperature - if it is not heating abnormally, the plume is clearing it.

### Fin placement
Mount the **4 fins on the lower core tank** (the Swivel's FL-T800), spaced symmetrically (every 90 degrees), and as **low as possible** on that tank - their bottom edges near the Swivel's mounting plane. Two specifics matter:

- **Mount them on the core, not on the boosters.** Core-mounted fins keep stabilizing the vehicle through the *entire* lower-atmosphere ascent, including the phase right after booster separation when the rocket is lighter and the center of mass has shifted but you are still moving fast through thick air. Fins mounted on the Hammers would depart at separation and take their stability with them at exactly the wrong moment.
- **As low as possible.** Fin authority comes from how far the fin sits behind the center of mass - the lower they are, the more leverage they have holding the center of pressure aft of the center of mass. This is also what counters the way the center of mass creeps downward as the core tank drains during the climb.

Use radial symmetry of 4 so the set is balanced; if ascent is still twitchy, the fix is bigger fins or fins mounted lower, not a reaction wheel (which contributes little in atmosphere).

### Avionics, power, and ascent handling
The craft carries a small **reaction wheel** and **battery** inline below the pod, a **6-cell fuel pack** for sustained power, and an extendable **Telemachus instrumentation antenna** for live telemetry. Placement of these matters more for handling than their mass does:

- **Keep draggy and asymmetric parts off the upper stack.** A single radially-mounted part high on the vehicle (especially on the capsule sidewall) pulls the center of pressure forward and creates a one-sided drag bias - a leading cause of the craft wandering or wanting to flip during ascent. The antenna and fuel cells are therefore housed in a **1.25 m service bay** on the mission stage, which puts them on the centerline (no drag asymmetry) and shields them during ascent. The bay costs only ~0.1 t - about 0.5 km of core-stage apoapsis, trivial against the Terrier's reserve - and tucking the parts inside removes their ascent drag, partially offsetting even that.
- **Service bay doors:** closed for launch and reentry, open for the mission phases (TMI, flyby). For uninterrupted reentry telemetry, a small **fixed** (non-extending) antenna on the capsule itself is preferable to relying on the stowed dish, since everything below the heat shield is gone by reentry.
- **Antenna stowed for launch.** The extendable dish is retracted on the pad and only deployed once out of the atmosphere; deployed extendable antennas carry large drag and can shear off near Max Q.
- **The reaction wheel earns its place in coast/TMI/flyby pointing, not in powered ascent.** During atmospheric ascent, the gimbaled Swivel and the fins dominate control authority; reaction-wheel torque is a minor contributor. If ascent handling is twitchy, the durable fixes are aerodynamic: mount the fins as low on the stack as possible (and size them up if needed) to hold the center of pressure behind the center of mass - which also counters the way the center of mass creeps downward as the core tank drains - keep the Swivel gimbal enabled, and fly a gentle gravity turn rather than over-steering with SAS in thick air.

---

## Build order checklist

### In the VAB

| Step | Action |
|---:|---|
| 1 | Place **Mk1 Command Pod** |
| 2 | Add **Mk16 Parachute** on top |
| 3 | Add **reaction wheel + battery** inline below the pod |
| 4 | Attach **1.25 m Heat Shield** below the avionics |
| 5 | Add **TR-18A Stack Decoupler** below the heat shield |
| 6 | Add **1.25 m Service Bay**; place **Telemachus antenna (retracted)** and **6-cell fuel pack** inside, on the centerline |
| 7 | Attach **FL-T800** below the bay |
| 8 | Attach **LV-909 Terrier** |
| 9 | Add second **TR-18A Stack Decoupler** below the Terrier |
| 10 | Attach second **FL-T800** |
| 11 | Attach **LV-T45 Swivel** |
| 12 | Add **2 radial decouplers** symmetrically to the lower tank |
| 13 | Attach **2 Hammer boosters**, nozzles **at or above the Swivel bell**, tops high on the core tank (plume clearance) |
| 14 | Add **Aerodynamic Nose Cone** atop each Hammer |
| 15 | Add **4 fins on the lower core tank**, symmetric (every 90°), as low as possible |
| 16 | Set Hammer thrust limit to **20%** |
| 17 | Confirm **Swivel gimbal enabled**; in the aero overlay, verify **center of mass sits above center of pressure** (check with tanks full and near-empty) |
| 18 | Verify centerline symmetry and staging order |

---

## Staging plan

| Firing sequence | Action | Hardware |
|---:|---|---|
| 5 | Liftoff ignition | Swivel + 2x Hammers |
| 4 | Booster separation | 2x Hammer via radial decouplers |
| 3 | Core stage separation | Empty lower FL-T800 + Swivel decouple away |
| 2 | Mission-stage ignition and orbital / transfer operations | Terrier + upper FL-T800 |
| 1 | Capsule recovery separation | Command Pod + Heat Shield from mission stage |
| 0 | Deploy parachute on landing | Mk16 Parachute |

> **Important:** KSP may display stage numbering in the opposite UI order. What matters is the firing sequence above.

---

## Ascent profile

### Liftoff and climb

| Phase | Guidance |
|---|---|
| Liftoff | SAS on if desired; Swivel at full throttle; Hammers ignite with the core |
| Initial climb | Hold near vertical at first and keep the vehicle smooth |
| Gravity turn | Begin a gentle eastward turn after clearing the pad and reaching safe speed |
| Mid ascent | Aim for roughly **45° pitch by 10-15 km**, depending on feel |
| Max-Q handling | Stay close to prograde; avoid abrupt steering below about **15 km** |

### Separation and orbit setup

| Event | Target |
|---|---|
| Booster separation | Drop Hammers after burnout; confirm core remains stable |
| Core stage goal | Push toward **70-85 km apoapsis** with good horizontal speed |
| Core stage sep | Decouple the empty core and light the Terrier stage |
| Out of atmosphere (~70 km+) | Open service bay and **deploy the Telemachus antenna**; safe to extend now that aero loads are gone |
| Parking orbit | Establish approximately **80 km x 80 km** |

---

## Ascent contingencies and abort windows

### Understanding periapsis during ascent

A **deeply negative periapsis at apoapsis is normal for most of the ascent — it is not an error by itself.** At core burnout the vehicle has roughly 485 m/s of horizontal speed against the ~2,279 m/s needed for orbit; periapsis stays far below the surface (hundreds of km negative) until the Terrier builds horizontal velocity toward orbital. Periapsis only climbs from deeply negative, through the surface, and up past 70 km in the **final portion of the Terrier burn**. So seeing periapsis at -400 km *partway through* the climb is expected. The failure case is periapsis still deeply negative — or apoapsis no longer rising — when the Terrier is **running low on fuel**.

### The real failure mode: flying too steep

The way this goes wrong is putting Terrier thrust into **climbing instead of building horizontal speed.** If the nose is held too high (toward vertical) during the Terrier burn, altitude increases but horizontal velocity stalls, apoapsis stops climbing, the vehicle arcs over, and it falls back before periapsis ever clears the atmosphere. A -400 km periapsis at the *end* of the burn, with apoapsis stuck low (~30 km), is the signature of this. **The correction is to pitch toward the horizon** (lower the nose, fly flatter, keep the prograde marker low) so thrust goes into horizontal speed.

### Go / No-Go gates

Judge the ascent by **apoapsis altitude and whether it is still rising**, not by the (normally negative) periapsis. Watch apoapsis as the primary health indicator through the Terrier burn:

| Gate | Nominal (GO) | Marginal (correct) | Abort / No-Go |
|---|---|---|---|
| Core burnout apoapsis | 20-30 km, rising | 15-20 km | < 12 km or already falling |
| Mid Terrier burn | Apoapsis climbing toward 70-80 km | Apoapsis rising slowly; pitch flatter | Apoapsis stalled < 40 km with > half Terrier fuel spent |
| Late Terrier burn | Apoapsis ~80 km, periapsis rising through 0 | Periapsis lagging; keep burning prograde | Terrier < 25% fuel and periapsis still < -100 km |
| Orbit insertion | Periapsis clears 70 km, ~80 km circular achievable | Periapsis 40-70 km; trim with remaining fuel | Cannot raise periapsis above 70 km with fuel remaining |

### Corrections (in priority order)

1. **Apoapsis rising too slowly / periapsis not climbing:** pitch **toward the horizon** immediately. The most common cause is too steep a climb; flying flatter converts thrust into the horizontal speed that raises periapsis. This is the single most effective fix.
2. **Apoapsis overshooting 85 km while periapsis still low:** you are climbing too much. Pitch further toward horizon; let apoapsis settle while horizontal speed catches up.
3. **Apoapsis stalled but fuel remains:** you are likely fighting gravity near-vertical. Lower the nose hard toward prograde/horizon and keep burning.
4. **Off-nominal but fuel-positive:** the Terrier carries ~3.4 km/s; the ascent needs roughly 1.8 km/s of horizontal make-up plus losses, so there is real margin to recover a sloppy climb **if caught early.**

### Hard abort window

**Abort the orbital insertion if, with 25% or less of the Terrier's fuel remaining, periapsis is still below -100 km (apoapsis stalled under ~40 km).** At that point there is not enough propellant to both raise apoapsis and build the horizontal speed for orbit, and continuing only deepens an unrecoverable suborbital arc. On abort: stop wasting fuel climbing, keep the capsule prograde and shallow for a survivable ballistic re-entry, retain enough propellant for a retrograde slow-down if available, ensure the **service bay is closed and heat shield is forward**, and ride it down as a suborbital recovery. A clean suborbital abort that recovers the crew is a far better outcome than burning the last fuel into a steeper crash.

---

## Orbit and transfer plan

### Parking orbit

| Item | Target |
|---|---:|
| Orbit shape | ~80 km x 80 km |
| Orbital speed | ~2279 m/s at 80 km |

**Circularization technique.** Target apoapsis near the **upper end of 70-85 km (aim ~80 km)** before circularizing; an 80 km apoapsis leaves a comfortable 10 km above the 70 km atmosphere edge, whereas circularizing from a marginal 71-72 km apoapsis tends to fail. The common mistake is starting the burn *at* apoapsis: the Terrier is a low-thrust engine, so the circularization burn takes appreciable time, and if you begin it exactly at apoapsis you coast past and begin falling before periapsis clears the atmosphere - which is why a too-late burn drops you back into the air. Instead, **lead apoapsis**: begin the prograde burn roughly half the burn duration *before* reaching apoapsis (for this light craft, a handful of seconds early), so periapsis is already rising while you are still climbing. Keep burning until **periapsis rises to meet apoapsis** at ~80 km. If apoapsis starts climbing well past 80 km you began too early/hard; if you sail past apoapsis with periapsis still low, you began too late.

### Trans-Mun Injection

| Item | Target | Note |
|---|---:|---|
| Burn magnitude | ~856 m/s | Practical live target: **850-870 m/s** |
| Burn direction | Prograde from parking orbit | Watch patched conics |
| Success cue | Mun encounter appears | Fine-tune if needed |

### Desired Mun flyby

| Flyby type | Mun periapsis |
|---|---:|
| Close dramatic pass | 15-25 km |
| Conservative pass | 25-50 km |
| Unsafe / risky | < 10 km |

### Kerbin return shaping

| Return condition | Action |
|---|---|
| Before atmospheric interface | Retract antenna and **close the service bay** before it separates with the mission stage; confirm a capsule-mounted fixed antenna (if fitted) for entry telemetry |
| 30-35 km Pe | Good reentry solution |
| > 38 km Pe | Lower periapsis |
| < 25-28 km Pe | Raise periapsis |

---

## Flight notes

| Situation | Recommendation |
|---|---|
| Core comes up short | Normal — Terrier finishes the climb; fly it flat (nose toward horizon) to build horizontal speed |
| Apoapsis won't rise on Terrier | You're too steep; pitch toward the horizon. Watch apoapsis, not periapsis |
| Launch feels too punchy | Lower Hammer thrust toward **15%** |
| Launch feels sluggish | Raise Hammer thrust toward **25%** |
| Vehicle starts to wobble | Reduce steering input and stay closer to prograde; if persistent, the cause is usually aero - check fins are low, gimbal is on, and nothing draggy is mounted asymmetrically high on the stack |
| Fuel margin matters | Fly a smooth ascent and avoid wasteful corrections |

---

## Summary recommendation

**Perseus 1** should be assembled as a **Mk1 pod + heat shield + Terrier + FL-T800 mission stage**, above a **Swivel + FL-T800 core**, with **two nose-coned, thrust-limited Hammer boosters** and **four fins**. In operational terms, this is a conservative one-crew Mun free-return vehicle with enough control authority and propellant margin to support a clean ascent, a nominal **~856 m/s** injection, and disciplined return-corridor trimming.

| Strength | Result |
|---|---|
| Simple to assemble | Easy VAB build |
| Clear stage logic | Easy to fly and recover |
| Stable ascent behavior | Less pilot workload |
| Large enough mission-stage margin | Forgiving orbit insertion and transfer |
| Good fit for stock KSP | Well suited to a Mun flyby |

<div class="page-break"></div>

# Appendix A
## One-Page Launch Checklist

### Pre-VAB build checks

| Check | Verify |
|---|---|
| Capsule stack | Mk16 chute, Mk1 pod, 1.25 m heat shield installed |
| Avionics | Reaction wheel + battery inline below pod |
| Mission stage | TR-18A, service bay (antenna + fuel cells inside, on centerline), FL-T800, Terrier installed |
| Launch core | TR-18A, FL-T800, Swivel installed |
| Boosters | 2x Hammers attached symmetrically, nose cone on each, nozzles level with or above the Swivel bell |
| Stability | 4 fins on lower core tank, mounted as low as possible and mirrored (every 90°) |
| Aero margin | Center of mass sits above center of pressure (check tanks full and near-empty) |
| Staging | Terrier not staged at liftoff; chute isolated from engine events |
| Tuning | Hammers at **20%** thrust limit; Swivel at **100%** |

### Pad checks

| Item | Go condition |
|---|---|
| SAS | On if desired |
| Throttle | Full |
| Service bay | Closed; Telemachus antenna retracted |
| Swivel gimbal | Enabled |
| Staging | Liftoff event shows Swivel + 2x Hammers |
| Heading plan | Eastward gravity turn |
| Mission target | 80 km parking orbit |

### Ascent callouts

| Event | Cue | Action |
|---|---|---|
| Liftoff | Clean rise, positive climb rate | Hold near vertical initially |
| Early turn | Clear of pad, safe speed | Start gentle eastward pitch |
| Mid ascent | ~10-15 km | Aim near **45°** pitch |
| Max-Q region | Below ~15 km | Keep steering smooth, stay near prograde |
| Booster burnout | Hammers empty | Separate boosters |
| Core finish | Apoapsis approaching **70-85 km** | Coast / finish shaping orbit |
| Core sep | Lower stage depleted | Decouple and ignite Terrier |

### Orbit and transfer checks

| Item | Target | Action |
|---|---:|---|
| Parking orbit | ~80 km x 80 km | Circularize |
| Orbital speed | ~2279 m/s at 80 km | Confirm orbit quality |
| TMI burn | **850-870 m/s** | Burn prograde |
| Mun periapsis | **15-50 km** | Correct if needed |
| Return periapsis | **30-35 km** | Trim after flyby |

### Abort / correction notes

| Condition | Response |
|---|---|
| Periapsis deeply negative mid-ascent | Normal — watch apoapsis instead; periapsis rises late in the Terrier burn |
| Apoapsis stalled, climbing too steep | Pitch toward the horizon to build horizontal speed |
| Apoapsis stalled < 40 km, Terrier < 25% fuel, Pe < -100 km | **Abort to suborbital recovery** (see Ascent contingencies) |
| Mun periapsis < 10 km | Raise periapsis immediately |
| Return periapsis > 38 km | Lower periapsis |
| Return periapsis < 25-28 km | Raise periapsis |
| Launch feels too aggressive | Lower Hammer thrust toward **15%** next attempt |
| Launch feels too sluggish | Raise Hammer thrust toward **25%** next attempt |


<div class="page-break"></div>

# Appendix B
## CAPCOM Pack

<div class="capcom-pack">
  <div class="capcom-banner">Flight Control Voice Package // Console Card Format</div>

  <h3>Mission profile</h3>
  <table>
    <thead>
      <tr><th>Item</th><th>Value</th></tr>
    </thead>
    <tbody>
      <tr><td>Mission type</td><td>Stock KSP 1 Mun free-return flyby</td></tr>
      <tr><td>Sequence</td><td>Launch -> 80 km parking orbit -> TMI -> Mun flyby -> Kerbin return</td></tr>
      <tr><td>Primary control standard</td><td>Short call, current value, recommendation</td></tr>
      <tr><td>Mission rule</td><td>No Mun orbit insertion; preserve return solution</td></tr>
    </tbody>
  </table>

  <h3>Key mission numbers</h3>
  <table>
    <thead>
      <tr><th>Item</th><th>Nominal</th><th>Caution</th></tr>
    </thead>
    <tbody>
      <tr><td>Pad TWR</td><td>1.4-1.8</td><td>&lt; 1.25 sluggish</td></tr>
      <tr><td>Parking orbit</td><td>75-90 km circular</td><td>Pe &lt; 70 km</td></tr>
      <tr><td>80 km circular speed</td><td>2279 m/s</td><td>materially short after circularization</td></tr>
      <tr><td>TMI burn from 80 km</td><td>850-870 m/s</td><td>&lt; 830 or &gt; 890 usually off-profile</td></tr>
      <tr><td>Time to Mun</td><td>~7.4 h</td><td>materially long / short indicates poor transfer</td></tr>
      <tr><td>Mun flyby periapsis</td><td>15-50 km</td><td>&lt; 10 km unsafe</td></tr>
      <tr><td>Mun periapsis speed</td><td>810-860 m/s</td><td>substantially outside band suggests poor geometry</td></tr>
      <tr><td>Kerbin return periapsis</td><td>30-35 km</td><td>&gt; 38 km shallow, &lt; 25-28 km steep</td></tr>
    </tbody>
  </table>

  <h3>Phase console cards</h3>

  <div class="phase-card">
    <div class="phase-header">
      <div class="phase-title">Pad / Launch</div>
      <div class="phase-subtitle">Terminal count through tower-clear confirmation</div>
    </div>
    <div class="phase-body">
      <div class="met-strip">MET target window: T-00:10 through T+00:30</div>
      <div class="status-box">
        <table>
          <tr><th>MET</th><th>ALT</th><th>VEL</th><th>STAGE</th></tr>
          <tr><td class="fill-line">__________</td><td class="fill-line">__________</td><td class="fill-line">__________</td><td class="fill-line">__________</td></tr>
        </table>
      </div>
      <table class="phase-band-table">
        <tr>
          <td><div class="phase-band go">GO band: comm good, staging verified, throttle set, SAS / guidance set</div></td>
          <td><div class="phase-band nogo">NO-GO band: staging error, control loss, TWR clearly below liftoff margin</div></td>
        </tr>
      </table>
      <div class="abort-box">
        <div class="abort-box-title">Abort / contingency</div>
        <table>
          <tr><th>Primary</th><td>Hold before commit for any staging discrepancy, throttle mis-set, or control-system fault. If thrust is not established cleanly at liftoff, shut down and remain on the pad.</td></tr>
          <tr><th>Mode I</th><td>If the stack departs controlled flight below safe separation conditions, cut thrust if possible, stage clear of failed boosters, and recover the capsule under chute at the first survivable opportunity.</td></tr>
          <tr><th>CAPCOM call</th><td>"No joy on launch commit. Hold, hold, hold. Safing the vehicle."</td></tr>
        </table>
      </div>
      <ul>
        <li>"Perseus 1, CAPCOM. Comm check good. Vehicle and weather are go."</li>
        <li>"Verify staging, throttle, guidance. You are go for terminal count."</li>
        <li>"T minus 10... 9... 8... ignition sequence start... 5... 4... 3... 2... 1... liftoff."</li>
        <li>"Liftoff confirmed. Roll program at pilot discretion."</li>
      </ul>
    </div>
  </div>

  <div class="phase-card">
    <div class="phase-header">
      <div class="phase-title">Ascent</div>
      <div class="phase-subtitle">Initial climb, Max Q, booster separation, apoapsis build</div>
    </div>
    <div class="phase-body">
      <div class="met-strip">MET target window: T+00:30 through orbit cutoff</div>
      <div class="status-box">
        <table>
          <tr><th>MET</th><th>ALT</th><th>VEL</th><th>Ap</th></tr>
          <tr><td class="fill-line">__________</td><td class="fill-line">__________</td><td class="fill-line">__________</td><td class="fill-line">__________</td></tr>
        </table>
      </div>
      <table class="phase-band-table">
        <tr>
          <td><div class="phase-band go">GO band: stable stack, clean pitch program, nominal staging, apoapsis rising toward 75 km</div></td>
          <td><div class="phase-band nogo">NO-GO band: severe wobble, staging transient with thrust loss, uncontrolled pitch excursion</div></td>
        </tr>
      </table>
      <div class="abort-box">
        <div class="abort-box-title">Abort / contingency</div>
        <table>
          <tr><th>Mode II</th><td>If ascent remains controllable but orbit is no longer achievable, pitch for survivable downrange arc, preserve capsule attitude, and prepare for ballistic recovery.</td></tr>
          <tr><th>Mode III</th><td>If upper-stage propulsion is lost after separation, secure the vehicle, protect attitude authority, and target immediate Kerbin return rather than orbit salvage.</td></tr>
          <tr><th>CAPCOM call</th><td>"Ascent no-go. Fly the recovery profile. Protect the capsule."</td></tr>
        </table>
      </div>
      <ul>
        <li>"Vehicle stable. Trajectory nominal."</li>
        <li>"Passing 5 kilometers. Velocity nominal. Continue pitch program."</li>
        <li>"Approaching Max Q. Keep it smooth."</li>
        <li>"Max Q. Vehicle looks good. You are go."</li>
        <li>"Stand by for staging."</li>
        <li>"Booster sep confirmed. Sustainer propulsion confirmed."</li>
        <li>"Passing 30 kilometers. Aero load decreasing. Continue building apoapsis."</li>
        <li>"Apoapsis 75 kilometers and rising. Prepare for cutoff."</li>
        <li>"Main engine cutoff. Cutoff confirmed. Apoapsis looks good."</li>
      </ul>
    </div>
  </div>

  <div class="phase-card">
    <div class="phase-header">
      <div class="phase-title">Circularization</div>
      <div class="phase-subtitle">Apoapsis burn to raise periapsis above atmosphere</div>
    </div>
    <div class="phase-body">
      <div class="met-strip">MET target window: apoapsis arrival through parking-orbit confirmation</div>
      <div class="status-box">
        <table>
          <tr><th>MET</th><th>Pe</th><th>Ap</th><th>dV rem</th></tr>
          <tr><td class="fill-line">__________</td><td class="fill-line">__________</td><td class="fill-line">__________</td><td class="fill-line">__________</td></tr>
        </table>
      </div>
      <table class="phase-band-table">
        <tr>
          <td><div class="phase-band go">GO band: prograde hold, periapsis climbing through 20 / 40 / 60 km, stable propellant margin</div></td>
          <td><div class="phase-band nogo">NO-GO band: periapsis fails to clear 70 km, major attitude divergence, fuel margin collapse</div></td>
        </tr>
      </table>
      <div class="abort-box">
        <div class="abort-box-title">Abort / contingency</div>
        <table>
          <tr><th>Primary</th><td>If periapsis cannot be raised above 70 km, do not chase a poor orbit. Preserve fuel, stabilize attitude, and plan immediate deorbit / recovery on the next pass.</td></tr>
          <tr><th>Secondary</th><td>If attitude control or power becomes marginal, terminate the burn early and accept suboptimal orbit only if reentry remains safely controlled.</td></tr>
          <tr><th>CAPCOM call</th><td>"Orbit not secure. Terminate burn. Set up for recovery."</td></tr>
        </table>
      </div>
      <ul>
        <li>"Recommend circularization at apoapsis. Burn prograde. Raise periapsis above 70 kilometers."</li>
        <li>"You are go for circularization burn."</li>
        <li>"Burn start."</li>
        <li>"Periapsis through 20... 40... 60..."</li>
        <li>"Orbit achieved. Current orbit stable."</li>
      </ul>
    </div>
  </div>

  <div class="phase-card">
    <div class="phase-header">
      <div class="phase-title">Trans-Mun Injection</div>
      <div class="phase-subtitle">Injection burn and encounter confirmation</div>
    </div>
    <div class="phase-body">
      <div class="met-strip">MET target window: transfer burn through encounter lock</div>
      <div class="status-box">
        <table>
          <tr><th>MET</th><th>dV used</th><th>Encounter</th><th>EC</th></tr>
          <tr><td class="fill-line">__________</td><td class="fill-line">__________</td><td class="fill-line">__________</td><td class="fill-line">__________</td></tr>
        </table>
      </div>
      <table class="phase-band-table">
        <tr>
          <td><div class="phase-band go">GO band: prograde aligned, target delta-v 850-870 m/s, Mun encounter appears on completion</div></td>
          <td><div class="phase-band nogo">NO-GO band: burn off-axis, encounter absent, excessive delta-v error, return geometry poor</div></td>
        </tr>
      </table>
      <div class="abort-box">
        <div class="abort-box-title">Abort / contingency</div>
        <table>
          <tr><th>Underburn</th><td>If Mun encounter is missed but parking orbit remains stable, stand down, re-evaluate delta-v, and either re-burn on the next node or wave off the flyby.</td></tr>
          <tr><th>Major miss</th><td>If burn geometry is bad or return corridor becomes unsafe, abort the translunar attempt, preserve remaining propellant, and restore a recoverable Kerbin orbit or direct return.</td></tr>
          <tr><th>CAPCOM call</th><td>"TMI no-go. Stand down from translunar profile. Recover to Kerbin plan."</td></tr>
        </table>
      </div>
      <ul>
        <li>"We are go for trans-Mun injection setup."</li>
        <li>"Target prograde burn: eight-five-six meters per second."</li>
        <li>"Burn in 10... 5... 4... 3... 2... 1... mark."</li>
        <li>"Burn start. Tracking nominal. Hold prograde."</li>
        <li>"Burn complete. Stand by for encounter solution."</li>
        <li>"We show a Mun encounter. Flyby profile is valid."</li>
      </ul>
    </div>
  </div>

  <div class="phase-card">
    <div class="phase-header">
      <div class="phase-title">Mun Approach / Flyby</div>
      <div class="phase-subtitle">SOI entry through closest approach and return-trajectory assessment</div>
    </div>
    <div class="phase-body">
      <div class="met-strip">MET target window: Mun SOI entry through closest approach</div>
      <div class="status-box">
        <table>
          <tr><th>MET</th><th>Mun Pe</th><th>Rel Vel</th><th>Return Pe</th></tr>
          <tr><td class="fill-line">__________</td><td class="fill-line">__________</td><td class="fill-line">__________</td><td class="fill-line">__________</td></tr>
        </table>
      </div>
      <table class="phase-band-table">
        <tr>
          <td><div class="phase-band go">GO band: periapsis remains 15-50 km, relative speed in family, free-return preserved</div></td>
          <td><div class="phase-band nogo">NO-GO band: periapsis below 10 km, impact threat, return periapsis driven outside recovery corridor</div></td>
        </tr>
      </table>
      <div class="abort-box">
        <div class="abort-box-title">Abort / contingency</div>
        <table>
          <tr><th>Low periapsis</th><td>If Mun periapsis trends below 10 km, execute immediate prograde / radial correction to remove impact risk before committing to the close approach.</td></tr>
          <tr><th>Return loss</th><td>If free-return geometry is lost, prioritize re-establishing a Kerbin return corridor over optimizing flyby altitude or photography.</td></tr>
          <tr><th>CAPCOM call</th><td>"Flyby no-go. Correct now for return corridor. Mission priority is safe return."</td></tr>
        </table>
      </div>
      <ul>
        <li>"Current Mun periapsis [value]. Target remains 15 to 50 kilometers."</li>
        <li>"Mun sphere-of-influence entry confirmed."</li>
        <li>"Current periapsis [value], relative speed [value]. Flyby remains nominal."</li>
        <li>"Passing 100 kilometers to periapsis."</li>
        <li>"Passing 50 kilometers to periapsis."</li>
        <li>"Closest approach. Flyby good. Stand by for return-trajectory assessment."</li>
      </ul>
    </div>
  </div>

  <div class="phase-card">
    <div class="phase-header">
      <div class="phase-title">Return</div>
      <div class="phase-subtitle">Kerbin corridor confirmation and long-coast monitoring</div>
    </div>
    <div class="phase-body">
      <div class="met-strip">MET target window: post-flyby coast through final reentry setup</div>
      <div class="status-box">
        <table>
          <tr><th>MET</th><th>Kerbin Pe</th><th>EC</th><th>Attitude</th></tr>
          <tr><td class="fill-line">__________</td><td class="fill-line">__________</td><td class="fill-line">__________</td><td class="fill-line">__________</td></tr>
        </table>
      </div>
      <table class="phase-band-table">
        <tr>
          <td><div class="phase-band go">GO band: Kerbin periapsis 30-35 km, power stable, attitude controlled, recovery corridor intact</div></td>
          <td><div class="phase-band nogo">NO-GO band: return periapsis &gt; 38 km or &lt; 25-28 km, power emergency, tumbling vehicle</div></td>
        </tr>
      </table>
      <div class="abort-box">
        <div class="abort-box-title">Abort / contingency</div>
        <table>
          <tr><th>Shallow return</th><td>If Kerbin periapsis is too high, lower it while propellant remains. Do not accept a skip-out trajectory unless power and life support margins clearly allow another circuit.</td></tr>
          <tr><th>Steep return</th><td>If periapsis is too low, raise it immediately to reduce heating and g-load risk. Protect power and attitude before fine-tuning corridor quality.</td></tr>
          <tr><th>CAPCOM call</th><td>"Return corridor no-go. Correct periapsis now. Keep the entry profile survivable."</td></tr>
        </table>
      </div>
      <ul>
        <li>"Current Kerbin periapsis [value]."</li>
        <li>"Reentry solution looks good. You are go."</li>
        <li>"Mun flyby complete. You are on return to Kerbin."</li>
        <li>"Primary watch items: power, attitude, final Kerbin periapsis."</li>
        <li>"Welcome home."</li>
      </ul>
    </div>
  </div>

  <div class="phase-card recovery-card">
    <div class="phase-header">
      <div class="phase-title">Recovery / Chute Ops</div>
      <div class="phase-subtitle">Final atmospheric entry, drogue / main deployment watch, and splashdown callouts</div>
    </div>
    <div class="phase-body">
      <div class="met-strip">MET target window: atmospheric interface through splashdown and crew safeing</div>
      <div class="status-box">
        <table>
          <tr><th>MET</th><th>G Load</th><th>ALT</th><th>Chute</th></tr>
          <tr><td class="fill-line">__________</td><td class="fill-line">__________</td><td class="fill-line">__________</td><td class="fill-line">__________</td></tr>
        </table>
      </div>
      <table class="phase-band-table">
        <tr>
          <td><div class="phase-band go">GO band: entry attitude stable, heat under control, chute deployment nominal, splashdown recovery assured</div></td>
          <td><div class="phase-band nogo">NO-GO band: heat spike, tumble, premature chute risk, unsafe impact trajectory</div></td>
        </tr>
      </table>
      <div class="abort-box">
        <div class="abort-box-title">Abort / contingency</div>
        <table>
          <tr><th>Attitude loss</th><td>If the capsule tumbles during entry, suspend nonessential actions and recover heat-shield-forward attitude before any chute concern.</td></tr>
          <tr><th>Chute issue</th><td>If chute deployment is delayed or unstable, hold for the next safe envelope and be prepared for contingency splashdown at higher vertical speed.</td></tr>
          <tr><th>CAPCOM call</th><td>"Recovery no-go. Stabilize attitude first. Chutes only in the safe envelope."</td></tr>
        </table>
      </div>
      <ul>
        <li>"Approaching entry interface. Verify capsule is heat-shield forward."</li>
        <li>"Entry loads building. Attitude remains your priority."</li>
        <li>"Heating nominal. Continue to monitor deceleration and control."</li>
        <li>"Below safe chute envelope. Stand by for deployment."</li>
        <li>"Chute deployment confirmed. Rate is coming down."</li>
        <li>"Splashdown expected. Recovery is go."</li>
        <li>"Splashdown confirmed. Perseus 1, welcome home."</li>
      </ul>
    </div>
  </div>


  <h3>Stage abort matrix</h3>
  <table class="console-notes">
    <thead><tr><th>Stage</th><th>Primary contingency action</th></tr></thead>
    <tbody>
      <tr><td>Pad / Launch</td><td>Hold on the pad for commit faults; if thrust/control is lost after commit, safe the vehicle and recover the capsule at first survivable opportunity.</td></tr>
      <tr><td>Ascent</td><td>Shift immediately to ballistic recovery if orbit is no longer achievable or ascent control degrades.</td></tr>
      <tr><td>Circularization</td><td>Terminate orbit insertion if periapsis cannot be secured; preserve fuel and set up direct recovery.</td></tr>
      <tr><td>Trans-Mun Injection</td><td>Wave off translunar profile on major underburn or bad geometry; restore recoverable Kerbin orbit or direct return.</td></tr>
      <tr><td>Mun Approach / Flyby</td><td>Correct low periapsis or lost free-return immediately; safe return takes priority over flyby quality.</td></tr>
      <tr><td>Return</td><td>Correct shallow/steep corridor while propellant and control remain available.</td></tr>
      <tr><td>Recovery / Chute Ops</td><td>Recover stable entry attitude first; deploy chutes only inside safe envelope.</td></tr>
    </tbody>
  </table>

  <h3>Correction / abort lines</h3>
  <table class="console-notes">
    <thead>
      <tr><th>Condition</th><th>CAPCOM call</th></tr>
    </thead>
    <tbody>
      <tr><td>Mun periapsis below 10 km</td><td>"Mun periapsis trending below 10 kilometers. Recommend correction burn now."</td></tr>
      <tr><td>Return periapsis 44 km</td><td>"Return periapsis 44 kilometers. That is shallow. Recommend lowering periapsis."</td></tr>
      <tr><td>Return periapsis 22 km</td><td>"Return periapsis 22 kilometers. That is steep. Recommend raising periapsis."</td></tr>
      <tr><td>Staging transient</td><td>"We saw a staging transient. Prioritize thrust and vehicle stability."</td></tr>
      <tr><td>Trajectory divergence</td><td>"Trajectory divergence observed. Correct now. Re-establish prograde."</td></tr>
          <tr><td>Chute not yet deployed in safe envelope</td><td>"Below safe chute envelope. Stand by for deployment."</td></tr>
      <tr><td>Launch commit fault</td><td>"Hold, hold, hold. Safing the vehicle."</td></tr>
      <tr><td>Ascent no longer supportable</td><td>"Ascent no-go. Fly the recovery profile."</td></tr>
      <tr><td>TMI miss / no encounter</td><td>"TMI no-go. Recover to Kerbin plan."</td></tr>
      <tr><td>Free-return lost at Mun</td><td>"Flyby no-go. Correct now for return corridor."</td></tr>
      <tr><td>Entry corridor unsafe</td><td>"Return corridor no-go. Correct periapsis now."</td></tr>
    </tbody>
  </table>

  <h3>Houston / Telemachus reference set</h3>
  <table>
    <thead>
      <tr><th>Mission need</th><th>Telemachus-style field</th><th>Use</th></tr>
    </thead>
    <tbody>
      <tr><td>Mission elapsed time</td><td><code>v.missionTime</code></td><td>event timing</td></tr>
      <tr><td>Altitude</td><td><code>v.altitude</code></td><td>ascent / orbit height</td></tr>
      <tr><td>Surface velocity</td><td><code>v.surfaceVelocity</code></td><td>ascent performance</td></tr>
      <tr><td>Vertical speed</td><td><code>v.verticalSpeed</code></td><td>climb / descent rate</td></tr>
      <tr><td>G force</td><td><code>v.geeForce</code></td><td>ascent and entry load</td></tr>
      <tr><td>Pitch / heading / roll</td><td><code>n.pitch2</code>, <code>n.heading2</code>, <code>n.roll2</code></td><td>attitude and guidance</td></tr>
      <tr><td>Throttle</td><td><code>f.throttle</code></td><td>commanded power</td></tr>
      <tr><td>Current stage</td><td><code>v.currentStage</code></td><td>stage-event confirmation</td></tr>
      <tr><td>Liquid fuel / oxidizer</td><td><code>r.resource[LiquidFuel]</code>, <code>r.resource[Oxidizer]</code></td><td>margin tracking</td></tr>
      <tr><td>Electric charge</td><td><code>r.resource[ElectricCharge]</code></td><td>control / comm margin</td></tr>
      <tr><td>Apoapsis / periapsis</td><td><code>o.ApA</code>, <code>o.PeA</code></td><td>orbit and return solution</td></tr>
      <tr><td>Time to apoapsis / periapsis</td><td><code>o.timeToAp</code>, <code>o.timeToPe</code></td><td>maneuver timing</td></tr>
      <tr><td>Body name</td><td><code>v.body</code></td><td>Kerbin / Mun confirmation</td></tr>
    </tbody>
  </table>

  <h3>Quick trigger library</h3>
  <table class="console-triggers">
    <thead>
      <tr><th>Trigger</th><th>Call</th></tr>
    </thead>
    <tbody>
      <tr><td><code>v.verticalSpeed &gt; 0</code> after release</td><td>"Liftoff confirmed."</td></tr>
      <tr><td><code>v.altitude ~ 5000</code></td><td>"Passing 5 kilometers. Velocity nominal."</td></tr>
      <tr><td><code>v.altitude 8000-15000</code> in hard climb</td><td>"Approaching Max Q. Keep it smooth."</td></tr>
      <tr><td><code>o.ApA ~ 75000</code></td><td>"Apoapsis 75 kilometers and rising. Prepare for cutoff."</td></tr>
      <tr><td><code>o.PeA &gt; 70000</code> after circularization</td><td>"Orbit achieved. Current orbit stable."</td></tr>
      <tr><td>Mun encounter appears</td><td>"We show a Mun encounter. Flyby profile is valid."</td></tr>
      <tr><td><code>v.body == Mun</code></td><td>"Mun sphere-of-influence entry confirmed."</td></tr>
      <tr><td><code>15000 &lt;= o.PeA &lt;= 50000</code> at Mun</td><td>"Mun periapsis [value]. Flyby remains acceptable."</td></tr>
      <tr><td><code>o.PeA &lt; 10000</code> at Mun</td><td>"Recommend correction burn now."</td></tr>
      <tr><td><code>30000 &lt;= o.PeA &lt;= 35000</code> on Kerbin return</td><td>"Return periapsis [value]. Reentry solution good."</td></tr>
      <tr><td><code>v.altitude &lt; 5000</code> under chute</td><td>"Chute deployment confirmed. Rate is coming down."</td></tr>
    </tbody>
  </table>
</div>

<div class="page-break"></div>

# Appendix C
## Technical Diagrams

### C1. Full Rocket Stack

<div class="technical-diagram-block">
  <img class="technical-diagram" src="perseus_rocket_stack_technical.svg" alt="Perseus 1 rocket stack technical diagram showing KSP parts, cut lines, and staging labels" />
  <div class="diagram-caption">Figure C1. Full Perseus 1 vehicle stack rendered in NASA technical-manual style, with KSP-authentic major parts, equal FL-T800 tank geometry, and explicit separation boundaries.</div>
</div>

<div class="page-break"></div>

### C2. Exploded Staging Decomposition

<div class="technical-diagram-block">
  <img class="technical-diagram technical-diagram-wide" src="perseus_staging_technical.svg" alt="Perseus 1 exploded staging visualization showing component groups by stage" />
  <div class="diagram-caption">Figure C2. Exploded stage-decomposition view showing booster jettison, core separation, Terrier mission-stage handoff, and capsule-only return configuration.</div>
</div>
<div class="page-break"></div>

# Appendix D
## Ascent Guidance Program

The full-page ascent guidance sheet (Figure D1) presents the powered-flight pitch and roll program in NASA reference-sheet style: a powered-flight sequence table, an altitude-vs-downrange trajectory plot with vehicle-attitude ticks, a roll/heading reference, and a stage timeline. All altitudes, velocities, and times are nominal values derived from the Perseus 1 ascent simulation (20% Hammer, Swivel 100%).

### D1. Powered Flight Sequence (text reference)

Pitch is given as degrees from vertical (0° = straight up). Values are nominal for a smooth, hand-flown gravity turn; treat as a reference, not a hard schedule.

| Event | MET | Alt | V (m/s) | Pitch | Roll | Action |
|---|---|---|---:|---:|---|---|
| Liftoff | T+00:00 | Pad | 0 | 0° | Hold | Swivel 100%, Hammers ignite. Hold vertical. SAS on. |
| Pitch program | T+00:08 | 250 m | 60 | 1° | Hold | Begin gentle pitch east. Initiate gravity turn. |
| Roll program | T+00:10 | 350 m | 70 | 2° | 090° E | Roll to flight heading 090. Establish downrange azimuth. |
| Throttle watch | T+00:16 | 1.0 km | 130 | 3° | Hold | Confirm prograde tracking. Keep nose near velocity vector. |
| Booster sep | T+00:25 | 2.6 km | 233 | 9° | Hold | Hammer burnout & jettison. Confirm core stable. |
| Max Q | T+00:30 | 3.5 km | 270 | 14° | Hold | Through max dynamic pressure. Steering smooth, near prograde. |
| Pitch 45 | T+00:50 | 10.0 km | 450 | 37° | Hold | Approx 45° from vertical. Hand off to gravity turn. |
| Core burnout | T+01:03 | 14.8 km | 633 | 50° | Hold | Lower FL-T800 dry. Stage: jettison core, ignite Terrier. |
| Terrier ascent | T+01:05 | 15+ km | 640 | Prograde | Hold | Terrier finishes climb. Track prograde to apoapsis target. |
| Apoapsis shaping | -- | 70-85 km | Var | Prograde | Hold | Coast/burn to set apoapsis ~80 km (upper end of band). |
| Circularize | -- | ~80 km Ap | ~2279 | Prograde | Hold | Begin burn ~½ burn-time BEFORE apoapsis. Burn until periapsis rises to ~80 km. |

**Program notes**

- Below ~15 km, keep the nose near the velocity vector; over-steering in thick air is the leading cause of departures.
- After booster separation the gravity turn is largely self-shaping — follow prograde rather than forcing pitch.
- The core stage nominally reaches only ~15 km at burnout (~25-30 km apoapsis if unpowered); the Terrier completes the climb to the 70-85 km target. This is by design, not a contingency.
- Times and altitudes are nominal simulation outputs; real hand-flown ascents will vary. Fly the profile by feel, using these as reference checkpoints.
- **Circularization:** aim for ~80 km apoapsis (not a marginal 71-72 km) and **lead apoapsis** — start the prograde burn a few seconds before reaching it, not at it. The Terrier's low thrust makes the burn long enough that starting at apoapsis lets you fall back into the atmosphere before periapsis clears 70 km. Burn until periapsis rises to meet apoapsis.
- **Watch apoapsis, not periapsis, during the climb.** A deeply negative periapsis (even -400 km) is normal until late in the Terrier burn; it only rises as horizontal speed approaches orbital. If apoapsis stalls or you arc over with periapsis still far negative, you are **flying too steep** — pitch toward the horizon to convert thrust into horizontal speed. Hard abort to suborbital recovery if apoapsis is stuck under ~40 km with ≤25% Terrier fuel and periapsis still below -100 km (see Ascent contingencies).

### D2. Ascent Guidance Sheet

<div class="technical-diagram-block">
  <img class="technical-diagram" src="perseus_ascent_program_technical.svg" alt="Perseus 1 ascent guidance program showing powered flight sequence, ascent trajectory plot, roll reference, and stage timeline" />
  <div class="diagram-caption">Figure D1. Ascent guidance program in NASA reference-sheet style: powered-flight sequence with pitch and roll commands by altitude, altitude-vs-downrange trajectory plot with vehicle-attitude ticks, launch-azimuth reference, and powered-flight stage timeline.</div>
</div>

### D3. Ascent Contingency & Abort Criteria Sheet

<div class="technical-diagram-block">
  <img class="technical-diagram" src="perseus_abort_criteria_technical.svg" alt="Perseus 1 ascent contingency and abort criteria showing go/no-go gates, corrections, and hard abort window" />
  <div class="diagram-caption">Figure D2. Ascent contingency and abort criteria: go/no-go gates by flight phase, prioritized corrections, and the hard abort window. Emphasizes judging the climb by apoapsis trend rather than the (normally negative) periapsis.</div>
</div>
