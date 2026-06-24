# Mission Control — Setup & Integration Guide

## Architecture

```
KSP + Telemachus plugin
        │
        │ WebSocket ws://[ksp-host]:8085/datalink
        │ JSON telemetry @ configurable rate
        ▼
mission_control/server.py  (Flask + Socket.IO)
        │
        ├── telemachus_client.py   WebSocket consumer + trajectory accumulator
        ├── nominal_compare.py     Flight director: phase, gates, advisories
        │
        │ Socket.IO events: telemetry / director / nominal
        ▼
mission_control/static/index.html  (browser)
        ├── Globe canvas (Kerbin + nominal / actual / abort arcs)
        ├── Trajectory canvas (altitude vs downrange)
        ├── Telemetry panel
        ├── Go/No-Go gates
        └── Advisory display + nominal comparison
```

---

## Starting the server

```bash
# Simulation mode (no KSP required)
python mission_control/server.py

# Live KSP (same machine)
python mission_control/server.py --ksp-host 127.0.0.1

# Live KSP (different machine on LAN)
python mission_control/server.py --ksp-host 192.168.1.42

# Options
python mission_control/server.py --help
  --ksp-host IP      KSP machine IP (omit for simulation mode)
  --ksp-port PORT    Telemachus port (default 8085)
  --rate MS          Telemetry polling rate ms (default 200)
  --port PORT        HTTP server port (default 5000)
  --emit-rate HZ     Browser push rate Hz (default 5)
```

Open http://localhost:5000/ in a browser (Chrome/Firefox recommended).

---

## Telemachus setup

1. Download [Telemachus](https://github.com/TeleIO/Telemachus-1) and
   extract into `KSP/GameData/`.

2. Launch KSP and load/create a vessel. Right-click the antenna and
   select **"Telemachus"** to enable the data feed. Note the IP:port
   shown (default: `ws://[your-ip]:8085/datalink`).

3. If KSP is on a different machine, ensure the WebSocket port (8085)
   is not blocked by the firewall.

4. Start the mission control server with `--ksp-host [ip]`.

### Topic names

Telemachus topic names vary slightly between versions. If telemetry
subscriptions produce no data, check your plugin version's topic list:

```
http://[ksp-host]:8085/telemachus/datalink
```

The topics subscribed by `telemachus_client.py` are defined in
`SUBSCRIBED_TOPICS` — edit that list to match your version.

---

## Socket.IO events (server → browser)

| Event | Payload | Description |
|---|---|---|
| `connected` | `{message}` | Server ready confirmation |
| `nominal` | `{trajectory: [...]}` | Full nominal trajectory (sent once on connect) |
| `telemetry` | `{state, trajectory}` | Telemetry snapshot + accumulated trajectory |
| `director` | `{phase, advisory, gates, nominal_at_alt, nominal_at_time}` | Flight director output |

### Telemetry state fields

```json
{
  "altitude":        12500.0,    // m above surface
  "velocity":         650.0,    // m/s total
  "v_vert":           430.0,    // m/s vertical
  "v_horiz":          480.0,    // m/s horizontal
  "apoapsis":       25000.0,    // m
  "periapsis":    -587000.0,    // m (negative = suborbital)
  "pitch":             45.0,    // degrees from horizon (KSP convention)
  "heading":           90.0,    // degrees
  "roll":               1.2,    // degrees
  "mission_time":      62.0,    // s (MET)
  "throttle":           1.0,    // 0–1
  "liquid_fuel":      3200.0,   // KSP units
  "solid_fuel":          0.0,   // KSP units (0 after booster sep)
  "atm_density":       0.001,   // kg/m³
  "connected":         true,
  "simulated":         false
}
```

### Director output fields

```json
{
  "phase": "TERRIER",
  "advisory": {
    "level":  "CAUTION",
    "action": "PITCH TOWARD HORIZON",
    "reason": "Apoapsis 28 km — build horizontal speed, lower the nose",
    "urgent": false
  },
  "gates": [
    { "phase": "CORE B/O",   "status": "GO",      "detail": "25.2 km Ap" },
    { "phase": "MID-TERR",   "status": "MARGINAL", "detail": "28.1 km Ap" },
    { "phase": "LATE-TERR",  "status": "NOT-YET",  "detail": "monitoring" },
    { "phase": "INSERTION",  "status": "NOT-YET",  "detail": "" }
  ],
  "nominal_at_alt":  { "altitude_km": 12.5, "apoapsis_km": 22.1, ... },
  "nominal_at_time": { "altitude_km": 14.8, "apoapsis_km": 24.1, ... }
}
```

---

## REST API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serve the mission control web interface |
| `GET` | `/api/nominal` | Full nominal trajectory as JSON |
| `GET` | `/api/state` | Current telemetry state (polling fallback) |
| `GET` | `/api/trajectory` | Accumulated actual trajectory |
| `POST` | `/api/clear-trajectory` | Reset actual trajectory accumulation |

---

## Houston UI integration

The web interface is designed for use both standalone and embedded
inside the [Telemachus Houston UI](https://github.com/KSP-TeleMachus/Telemachus-Houston)
or similar mission control frameworks.

### CSS theming

All colours use `--mc-*` CSS custom properties. Override them in the
host page to match Houston's palette:

```css
/* In your Houston theme or host stylesheet: */
:root {
  --mc-bg:           #0a0c10;
  --mc-panel:        #0f1520;
  --mc-accent:       #00b4d8;
  --mc-green-bright: #72efdd;
  /* etc. */
}
```

### Embedding panels

Individual panels can be embedded via URL parameter:

```html
<!-- Embed just the globe -->
<iframe src="http://localhost:5000/?panel=globe"></iframe>

<!-- Embed just the telemetry panel -->
<iframe src="http://localhost:5000/?panel=telemetry"></iframe>

<!-- Embed the trajectory plot -->
<iframe src="http://localhost:5000/?panel=trajectory"></iframe>
```

Each panel's root element has a `data-panel="[name]"` attribute and
hides non-matching panels when a `?panel=` URL parameter is present.

### JavaScript API

The interface exposes `window.MissionControl` for host frame integration:

```javascript
// In the host Houston UI:
const mc = document.getElementById('mc-frame').contentWindow.MissionControl;

// Get live state
const state = mc.getState();
const director = mc.getDirector();

// Subscribe to updates
mc.onUpdate((state, director) => {
  console.log('Altitude:', state.altitude, 'Apoapsis:', state.apoapsis);
});

// Access trajectory data
const nominal = mc.getNominalTrajectory();
const actual  = mc.getActualTrajectory();

// Clear accumulated flight path
mc.clearTrajectory();
```

### Custom events

The interface dispatches standard `CustomEvent` on `window` for any
Houston listener:

```javascript
// In Houston host frame:
window.addEventListener('mc:telemetry', e => {
  const { state, trajectory } = e.detail;
  // update Houston HUD elements
});
window.addEventListener('mc:director', e => {
  const { phase, advisory, gates } = e.detail;
  // update go/no-go display
});
```

### Extending the advisory system

The advisory logic lives entirely in `nominal_compare.py`. To add
mission-specific advisories (e.g. for TMI or Mun flyby phases),
extend `generate_advisory()` with additional `if phase == FlightPhase.TMI:` blocks.
The server picks up changes on restart — no client changes needed.

---

## Simulation mode

When started without `--ksp-host`, the server runs a `SimulatedTelemetry`
client that plays back the nominal trajectory with ±2% random noise.
This is useful for:
- Developing and testing the UI without a running KSP game
- Demonstrating the interface to others
- Verifying advisory logic against known trajectory events

The simulated session runs indefinitely, looping through the ~70 s
powered-flight window. To reset: `POST /api/clear-trajectory`.

---

## Flight director logic (`nominal_compare.py`)

### Phase detection

Phase is inferred from telemetry heuristics (no staging events from
Telemachus in all versions):

| Phase | Inference |
|---|---|
| `PRELAUNCH` | Altitude ≤ 10 m, MET < 5 s |
| `BOOST` | Solid fuel remaining > 1 unit |
| `CORE` | Liquid fuel > 0, throttle > 0, apoapsis < 60 km, MET < 70 s |
| `TERRIER` | Same but MET > 70 s or apoapsis ≥ 60 km |
| `CIRCULARIZE` | Liquid fuel > 0, throttle > 0, apoapsis ≥ 60 km, periapsis < 65 km |
| `ORBIT` | Periapsis > 70 km |

### Go/No-Go gate thresholds

| Gate | GO | MARGINAL | NO-GO |
|---|---|---|---|
| CORE B/O | Ap ≥ 20 km | 12–20 km | < 12 km |
| MID-TERR | Ap ≥ 40 km | 25–40 km | < 25 km + < 50% fuel |
| LATE-TERR | Ap ≥ 70 km | 50–70 km | < 25% fuel + Pe < −100 km |
| INSERTION | Pe > 70 km | 40–70 km | Cannot reach Pe > 70 km |

### Hard abort trigger

`ABORT` advisory when: fuel ≤ 25% AND periapsis < −100 km AND apoapsis < 40 km.
