"""Shared Playwright test helpers — imported by test_ui_playwright.py and
test_visual_playwright.py to ensure identical test isolation."""

RESET_JS = """(() => {
    // Global mutable state
    latestState = {};
    latestDirector = {};
    actualTraj = [];
    _globeZoomMul = 1.0;
    _lastStageCount = -1;
    _prevAdvisoryLevel = 'NOMINAL';

    // UX review globals
    _eventLog.length = 0;
    _prevPhase = null;
    _prevGateStatuses = {};
    _prevLoggedAdvisoryLevel = 'NOMINAL';
    _scoreShown = false;
    _prelaunchDismissed = false;
    if (_abortAlarmInterval) { clearInterval(_abortAlarmInterval); _abortAlarmInterval = null; }
    if (_countdownInterval) { clearInterval(_countdownInterval); _countdownInterval = null; }
    if (typeof _abortAlarmTimeouts !== 'undefined') {
        _abortAlarmTimeouts.forEach(id => clearTimeout(id));
        _abortAlarmTimeouts.length = 0;
    }

    // Canvas size cache (const object — clear keys, don't reassign)
    for (const k of Object.keys(_canvasSizes)) delete _canvasSizes[k];

    // Telemetry value cells
    for (const id of ['t-alt','t-vel','t-vvert','t-vhoriz','t-apo','t-pe',
                       't-mass','t-gforce','t-mach','t-dynp','t-tta','t-ttp',
                       't-inc','t-pitch','t-hdg','t-roll','t-thr','t-lf',
                       't-sf','t-atm','t-met2']) {
        const el = document.getElementById(id);
        if (el) el.textContent = '\\u2014';
    }
    document.getElementById('met-display').textContent = 'T+ 00:00:00';

    // Fuel bars
    document.getElementById('lf-bar').style.width = '0%';
    document.getElementById('sf-bar').style.width = '0%';

    // Stage dV bars
    document.getElementById('stage-dv-bars').innerHTML = '';
    document.getElementById('stage-dv-section').style.display = 'none';

    // Advisory panel
    const abox = document.getElementById('advisory-box');
    if (abox) abox.className = 'NOMINAL';
    const alevel = document.getElementById('advisory-level');
    if (alevel) { alevel.textContent = 'NOMINAL'; alevel.className = 'NOMINAL'; }
    const aaction = document.getElementById('advisory-action');
    if (aaction) aaction.textContent = 'STANDING BY';
    const areason = document.getElementById('advisory-reason');
    if (areason) areason.textContent = 'Awaiting launch';

    // Gates
    document.getElementById('gates-list').innerHTML = '';

    // Phase badge + connection badge
    document.getElementById('phase-badge').textContent = 'PRELAUNCH';
    const cb = document.getElementById('conn-badge');
    if (cb) { cb.textContent = 'DISCONNECTED'; cb.className = 'off'; }

    // Scenario panel
    document.getElementById('scenario-panel').classList.remove('open');
    document.getElementById('scenario-btn').classList.remove('active');
    document.getElementById('sc-pb-state').textContent = '\\u2014';
    document.getElementById('sc-pb-elapsed').textContent = 'T+ 0.0s';
    document.getElementById('sc-summary').innerHTML = '';
    const cf = document.getElementById('sc-custom-fields');
    if (cf) cf.style.opacity = '';

    // data-panel display reset
    document.querySelectorAll('[data-panel]').forEach(
        el => el.style.display = '');

    // Playback progress bar
    const bar = document.getElementById('sc-pb-bar');
    if (bar) bar.style.width = '0%';

    // UX review DOM elements
    const shell = document.getElementById('shell');
    if (shell) shell.classList.remove('alert-flash-CAUTION', 'alert-flash-WARNING', 'alert-flash-ABORT');
    const eventLog = document.getElementById('event-log');
    if (eventLog) eventLog.innerHTML = '';
    const scoreOverlay = document.getElementById('flight-score-overlay');
    if (scoreOverlay) scoreOverlay.style.display = 'none';
})()"""
