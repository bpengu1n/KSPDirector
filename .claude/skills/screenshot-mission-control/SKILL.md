description: Launch mission control in sim mode, drive all scenarios with Playwright, and capture screenshots

# Screenshot Mission Control

Captures screenshots of the Perseus 1 Mission Control web UI running in simulation mode, cycling through all available scenarios.

## Prerequisites

```bash
pip install flask flask-socketio eventlet
cd /tmp && npm init -y > /dev/null 2>&1 && npm install playwright-core 2>&1 | tail -1
```

Chromium is pre-installed at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`.

## Run

### 1. Start the server (simulation mode)

```bash
kill $(lsof -ti:5000) 2>/dev/null
cd /home/user/KSPDirector/code
nohup python mission_control/server.py > /tmp/mc-server.log 2>&1 &
for i in {1..20}; do curl -sf http://localhost:5000/ > /dev/null && break; sleep 1; done
```

### 2. Drive with Playwright and screenshot

Write a Node ESM script (`.mjs`) using `playwright-core` with the pre-installed Chromium:

```javascript
import { chromium } from 'playwright-core';
const browser = await chromium.launch({
  executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
  args: ['--no-sandbox', '--disable-gpu'],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto('http://localhost:5000/', { waitUntil: 'networkidle' });
```

### 3. Scenario cycling

Available scenarios (via the `#sim-scenario` dropdown):
- `nominal` — Nominal: full orbit insertion (~300s)
- `subnominal` — Sub-nominal: degraded orbit (~310s)
- `abort` — Engine failure + abort & recovery (~180s)
- `catastrophic` — Max-Q breakup, loss of vehicle (~40s)

Switch scenario: `await page.selectOption('#sim-scenario', 'catastrophic');`

Sim controls:
- Pause: `await page.click('#sim-play-pause');`
- Restart: `await page.click('#sim-restart');`

Wait for the scenario to build enough trajectory before screenshotting (15-20s for boost+core, full duration for completion).

### 4. Stop

```bash
kill $(lsof -ti:5000) 2>/dev/null
```

## Gotchas

- The server uses eventlet + Socket.IO WebSockets. Use `waitUntil: 'networkidle'` then additional `waitForTimeout` to let the sim advance — `waitForSelector` won't help since telemetry updates come over WebSocket, not DOM mutations.
- `playwright-core` (not `playwright`) is needed to use the pre-installed Chromium binary directly. Install it in a temp dir if not available globally.
- The sim controls bar only appears after the first `sim_status` WebSocket event fires (~2-3s after page load). Wait at least 3s before interacting with controls.
- Each scenario auto-pauses on completion. The status label changes to "COMPLETE" (green text).
