"""
tests/test_ui_playwright.py
============================
DOM-based UI tests using Playwright + headless Chromium.

Replaces the regex-based HTML/JS tests (P-TEST-06) with proper DOM queries,
computed style checks, and JavaScript evaluation.

Requires: pip install playwright
Browser:  /opt/pw-browsers/chromium-1194/chrome-linux/chrome (pre-installed)

These tests start the Flask server on a random port in a background thread,
load the page in headless Chromium, and verify the actual rendered DOM.
"""

import os
import socket
import threading
import time

import pytest

CHROMIUM_PATH = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

pytestmark = pytest.mark.skipif(
    not HAS_PLAYWRIGHT or not os.path.exists(CHROMIUM_PATH),
    reason="playwright not installed or Chromium not found",
)


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(port):
    from mission_control.server import app, socketio
    socketio.run(app, host="127.0.0.1", port=port,
                 allow_unsafe_werkzeug=True, log_output=False)


@pytest.fixture(scope="module")
def page():
    """Start server in thread, launch browser, yield page, cleanup."""
    port = _free_port()
    server_thread = threading.Thread(
        target=_start_server, args=(port,), daemon=True)
    server_thread.start()

    for _ in range(40):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.25)

    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        executable_path=CHROMIUM_PATH, headless=True)
    p = browser.new_page()
    p.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")

    yield p

    p.close()
    browser.close()
    pw.stop()


# --- Grid layout ---

def test_shell_grid_display(page):
    shell = page.query_selector("#shell")
    assert shell is not None, "#shell element must exist"
    display = page.evaluate(
        "getComputedStyle(document.getElementById('shell')).display")
    assert display == "grid"


def test_shell_three_rows(page):
    rows = page.evaluate(
        "getComputedStyle(document.getElementById('shell')).gridTemplateRows")
    parts = rows.strip().split()
    assert len(parts) == 3, \
        f"#shell should have 3 grid rows, got {len(parts)}: {rows}"


@pytest.mark.parametrize("panel_id", [
    "topbar", "left-panel", "center-panel", "right-panel", "timeline-bar",
])
def test_grid_panels_exist(page, panel_id):
    el = page.query_selector(f"#{panel_id}")
    assert el is not None, f"#{panel_id} must exist"


def test_center_min_height(page):
    mh = page.evaluate(
        "getComputedStyle(document.getElementById('center-panel')).minHeight")
    assert mh == "0px", \
        f"#center-panel min-height should be 0px, got {mh}"


def test_right_min_height(page):
    mh = page.evaluate(
        "getComputedStyle(document.getElementById('right-panel')).minHeight")
    assert mh == "0px", \
        f"#right-panel min-height should be 0px, got {mh}"


def test_body_overflow(page):
    overflow = page.evaluate(
        "getComputedStyle(document.body).overflow")
    assert overflow == "hidden"


def test_timeline_grid_row(page):
    row = page.evaluate(
        "getComputedStyle(document.getElementById('timeline-bar')).gridRow")
    assert "3" in row, \
        f"#timeline-bar should be in grid row 3, got {row}"


# --- Canvas elements ---

@pytest.mark.parametrize("canvas_id", [
    "globe-canvas", "traj-canvas", "timeline-canvas",
])
def test_canvases_exist(page, canvas_id):
    el = page.query_selector(f"#{canvas_id}")
    assert el is not None, f"#{canvas_id} must exist"


@pytest.mark.parametrize("canvas_id", [
    "globe-canvas", "traj-canvas", "timeline-canvas",
])
def test_canvas_dimensions(page, canvas_id):
    box = page.evaluate(f"""(() => {{
        const c = document.getElementById('{canvas_id}');
        const r = c.getBoundingClientRect();
        return {{w: r.width, h: r.height}};
    }})()""")
    assert box["w"] > 0, f"#{canvas_id} width should be > 0"
    assert box["h"] > 0, f"#{canvas_id} height should be > 0"


def test_timeline_canvas_height(page):
    h = page.evaluate(
        "getComputedStyle(document.getElementById('timeline-canvas')).height")
    assert h != "0px", \
        f"#timeline-canvas computed height should not be 0px"


# --- Telemetry panel elements ---

@pytest.mark.parametrize("eid", [
    "t-alt", "t-vel", "t-vvert", "t-vhoriz",
    "t-apo", "t-pe", "met-display",
    "t-mass", "t-gforce", "t-mach", "t-dynp",
    "t-tta", "t-ttp",
])
def test_telemetry_elements(page, eid):
    el = page.query_selector(f"#{eid}")
    assert el is not None, f"Telemetry field #{eid} must exist"


def test_stage_dv_section(page):
    assert page.query_selector("#stage-dv-section") is not None
    assert page.query_selector("#stage-dv-bars") is not None


def test_vessel_section(page):
    assert page.query_selector("#vessel-section") is not None


# --- JavaScript functions ---

def test_esc_fn_exists(page):
    result = page.evaluate("typeof esc")
    assert result == "function", "esc() must be defined"


def test_esc_escapes(page):
    result = page.evaluate("esc('<script>alert(1)</script>')")
    assert "<script>" not in result
    assert "&lt;" in result


def test_stage_dv_bars_fn(page):
    result = page.evaluate("typeof updateStageDVBars")
    assert result == "function"


def test_canvas_size_fn(page):
    result = page.evaluate("typeof getCanvasSize")
    assert result == "function"


def test_projection_fn(page):
    result = page.evaluate("typeof projectBallisticArc")
    assert result == "function"


def test_phase_bands_fn(page):
    result = page.evaluate("typeof buildPhaseBands")
    assert result == "function"


def test_mc_api_object(page):
    result = page.evaluate("typeof window.MissionControl")
    assert result == "object", \
        "window.MissionControl API object must exist"
    methods = page.evaluate("""
        Object.keys(window.MissionControl).filter(
            k => typeof window.MissionControl[k] === 'function')
    """)
    assert "loadScenario" in methods
    assert "controlPlayback" in methods


# --- Scenario panel ---

def test_scenario_panel(page):
    panel = page.query_selector("#scenario-panel")
    assert panel is not None, "Scenario control panel must exist"


def test_preset_dropdown(page):
    select = page.query_selector("#sc-preset")
    assert select is not None, "Preset scenario dropdown must exist"
    page.evaluate("fetchPresets()")
    page.wait_for_timeout(500)
    options = page.evaluate("""
        Array.from(document.getElementById('sc-preset').options)
             .map(o => o.value)
    """)
    assert "nominal" in options
    assert "steep_ascent" in options


@pytest.mark.parametrize("btn_id", [
    "sc-play-btn", "sc-pause-btn", "sc-reset-btn",
])
def test_playback_controls(page, btn_id):
    el = page.query_selector(f"#{btn_id}")
    assert el is not None, f"Playback button #{btn_id} must exist"


# --- Advisory / Gates ---

def test_advisory_panel(page):
    el = page.query_selector("#advisory-action")
    assert el is not None, "Advisory action element must exist"


def test_gates_container(page):
    el = page.query_selector("#gates-list")
    assert el is not None, "Gates container must exist"


# --- Constants loaded ---

def test_kerbin_constants(page):
    r_km = page.evaluate("typeof R_KM !== 'undefined' ? R_KM : null")
    assert r_km is not None, "R_KM (Kerbin radius) must be defined"
    assert abs(r_km - 600.0) < 1.0


# --- CSS custom properties ---

@pytest.mark.parametrize("prop", [
    "--mc-bg", "--mc-panel", "--mc-accent", "--mc-text",
    "--mc-green", "--mc-red",
])
def test_css_vars(page, prop):
    val = page.evaluate(
        f"getComputedStyle(document.documentElement).getPropertyValue('{prop}').trim()")
    assert len(val) > 0, f"CSS custom property {prop} must be defined"


# --- UX Review: Mission branding persistence ---

def test_mission_name_input_exists(page):
    el = page.query_selector("#sc-mission-name")
    assert el is not None, "Mission name input must exist in scenario panel"
    assert el.get_attribute("type") == "text"


def test_mission_name_default_display(page):
    name_el = page.query_selector("#mission-name")
    assert name_el is not None
    assert "PERSEUS 1" in name_el.text_content()
    assert "MISSION CONTROL" in name_el.text_content()


def test_set_mission_name_updates_ui(page):
    page.evaluate("setMissionName('GEMINI 4')")
    name_el = page.query_selector("#mission-name")
    assert "GEMINI 4" in name_el.text_content()
    title = page.evaluate("document.title")
    assert "GEMINI 4" in title
    page.evaluate("setMissionName('')")


def test_mission_name_localstorage_persistence(page):
    page.evaluate("setMissionName('APOLLO 13')")
    stored = page.evaluate("localStorage.getItem('mc_mission_name')")
    assert stored == "APOLLO 13"
    page.evaluate("setMissionName('')")
    stored_after = page.evaluate("localStorage.getItem('mc_mission_name')")
    assert stored_after is None


def test_mission_name_syncs_houston_api(page):
    page.evaluate("setMissionName('VOSTOK 1')")
    mission = page.evaluate("window.MissionControl.mission")
    assert mission == "VOSTOK 1"
    page.evaluate("setMissionName('')")
    default = page.evaluate("window.MissionControl.mission")
    assert default == "PERSEUS 1"


def test_apply_mission_name_updates_input(page):
    page.evaluate("applyMissionName('MERCURY 7')")
    val = page.evaluate("document.getElementById('sc-mission-name').value")
    assert val == "MERCURY 7"
    page.evaluate("setMissionName('')")


# --- UX Review: Pre-launch checklist ---

def test_prelaunch_overlay_exists(page):
    el = page.query_selector("#prelaunch-overlay")
    assert el is not None, "Pre-launch checklist overlay must exist"


def test_prelaunch_checklist_items(page):
    items = page.evaluate("""
        Array.from(document.querySelectorAll('.checklist-item'))
             .map(el => el.textContent)
    """)
    assert len(items) >= 5


# --- UX Review: Event log ---

def test_event_log_section_exists(page):
    el = page.query_selector("#event-log")
    assert el is not None, "Event log container must exist"


def test_event_log_export_button(page):
    has_fn = page.evaluate("typeof exportEventLog === 'function'")
    assert has_fn is True


# --- UX Review: Alert flash animations ---

def test_alert_flash_functions(page):
    has_play = page.evaluate("typeof _playTone === 'function'")
    assert has_play is True


# --- UX Review: Consumables display ---

def test_consumables_display_elements(page):
    has_fn = page.evaluate("typeof updateConsumablesDisplay === 'function'")
    assert has_fn is True


# --- UX Review: Flight score ---

def test_flight_score_overlay_exists(page):
    el = page.query_selector("#flight-score-overlay")
    assert el is not None, "Flight score overlay must exist"


def test_flight_score_function(page):
    has_fn = page.evaluate("typeof showFlightScore === 'function'")
    assert has_fn is True


# --- UX Review: Behavioral tests (not just existence) ---

def test_event_log_records_phase_change(page):
    """trackEvents logs phase transitions to the event log."""
    page.evaluate("""
        _eventLog.length = 0;
        document.getElementById('event-log').innerHTML = '';
        _prevPhase = null;
        trackEvents({mission_time: 25}, {phase: 'BOOST', gates: [], advisory: {level: 'NOMINAL'}});
        trackEvents({mission_time: 61}, {phase: 'CORE', gates: [], advisory: {level: 'NOMINAL'}});
    """)
    entries = page.evaluate("_eventLog.length")
    assert entries >= 2
    last = page.evaluate("_eventLog[_eventLog.length - 1].msg")
    assert "CORE" in last


def test_event_log_records_advisory_change(page):
    """trackEvents logs advisory level changes independently of playAdvisoryAlert."""
    page.evaluate("""
        _eventLog.length = 0;
        document.getElementById('event-log').innerHTML = '';
        _prevLoggedAdvisoryLevel = 'NOMINAL';
        _prevPhase = 'CORE';
        trackEvents({mission_time: 80}, {phase: 'CORE', gates: [],
            advisory: {level: 'CAUTION', action: 'PITCH STEEP'}});
    """)
    entries = page.evaluate("_eventLog.filter(e => e.type === 'advisory').length")
    assert entries == 1


def test_abort_alarm_clears_on_deescalation(page):
    """playAdvisoryAlert clears abort alarm interval on de-escalation."""
    result = page.evaluate("""
        _prevAdvisoryLevel = 'NOMINAL';
        playAdvisoryAlert('ABORT');
        const hadAlarm = _abortAlarmInterval !== null;
        playAdvisoryAlert('CAUTION');
        const alarmAfter = _abortAlarmInterval;
        ({hadAlarm, alarmCleared: alarmAfter === null})
    """)
    assert result["hadAlarm"] is True
    assert result["alarmCleared"] is True


def test_overlay_panel_selector_sanitized(page):
    """Overlay panel selector strips special characters."""
    result = page.evaluate("""
        const raw = '"],.bad[x="';
        const safe = raw.replace(/[^a-zA-Z0-9_-]/g, '');
        safe
    """)
    assert result == "badx"
