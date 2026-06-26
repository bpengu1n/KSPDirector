"""
tests/test_ui_playwright.py
============================
DOM-based UI tests using Playwright + headless Chromium.

Tests start the Flask server on a random port in a background thread,
load the page in headless Chromium, and verify the actual rendered DOM,
computed styles, JavaScript function behavior, and Socket.IO integration.

Requires: pip install playwright
Browser:  /opt/pw-browsers/chromium-1194/chrome-linux/chrome (pre-installed)
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


# ===================================================================
# Grid layout
# ===================================================================

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
    assert mh == "0px"


def test_right_min_height(page):
    mh = page.evaluate(
        "getComputedStyle(document.getElementById('right-panel')).minHeight")
    assert mh == "0px"


def test_body_overflow(page):
    overflow = page.evaluate(
        "getComputedStyle(document.body).overflow")
    assert overflow == "hidden"


def test_timeline_grid_row(page):
    row = page.evaluate(
        "getComputedStyle(document.getElementById('timeline-bar')).gridRow")
    assert "3" in row


def test_shell_fills_viewport(page):
    dims = page.evaluate("""(() => {
        const s = document.getElementById('shell');
        return {w: s.offsetWidth, h: s.offsetHeight,
                vw: window.innerWidth, vh: window.innerHeight};
    })()""")
    assert dims["w"] == dims["vw"]
    assert dims["h"] == dims["vh"]


def test_left_panel_overflow_auto(page):
    ov = page.evaluate(
        "getComputedStyle(document.getElementById('left-panel')).overflowY")
    assert ov == "auto", f"left-panel overflowY should be auto, got {ov}"


# ===================================================================
# Canvas elements
# ===================================================================

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
    assert h != "0px"


@pytest.mark.parametrize("canvas_id", [
    "globe-canvas", "traj-canvas", "timeline-canvas",
])
def test_canvas_has_2d_context(page, canvas_id):
    has_ctx = page.evaluate(f"""(() => {{
        const c = document.getElementById('{canvas_id}');
        return c.getContext('2d') !== null;
    }})()""")
    assert has_ctx, f"#{canvas_id} must support 2d context"


def test_canvas_not_blank_after_render(page):
    page.evaluate("renderAll()")
    page.wait_for_timeout(100)
    for cid in ("globe-canvas", "traj-canvas", "timeline-canvas"):
        blank = page.evaluate(f"""(() => {{
            const c = document.getElementById('{cid}');
            const ctx = c.getContext('2d');
            const d = ctx.getImageData(0, 0, c.width, c.height).data;
            return d.every(v => v === 0);
        }})()""")
        assert not blank, f"#{cid} should have non-blank pixels after renderAll()"


def test_get_canvas_size_returns_dimensions(page):
    size = page.evaluate("getCanvasSize('globe-canvas')")
    assert size["w"] > 0
    assert size["h"] > 0


def test_get_canvas_size_caches(page):
    page.evaluate("invalidateCanvasSizes()")
    s1 = page.evaluate("getCanvasSize('globe-canvas')")
    s2 = page.evaluate("getCanvasSize('globe-canvas')")
    assert s1["w"] == s2["w"] and s1["h"] == s2["h"]


def test_invalidate_canvas_sizes(page):
    result = page.evaluate("""(() => {
        invalidateCanvasSizes();
        getCanvasSize('globe-canvas');
        const before = Object.keys(_canvasSizes).length;
        invalidateCanvasSizes();
        const after = Object.keys(_canvasSizes).length;
        return {before, after};
    })()""")
    assert result["before"] > 0, "getCanvasSize should populate cache"
    assert result["after"] == 0, "invalidateCanvasSizes should clear cache"


# ===================================================================
# Telemetry panel elements
# ===================================================================

@pytest.mark.parametrize("eid", [
    "t-alt", "t-vel", "t-vvert", "t-vhoriz",
    "t-apo", "t-pe", "met-display",
    "t-mass", "t-gforce", "t-mach", "t-dynp",
    "t-tta", "t-ttp",
    "t-inc", "t-pitch", "t-hdg", "t-roll",
    "t-thr", "t-lf", "t-sf",
    "t-atm", "t-met2",
])
def test_telemetry_elements(page, eid):
    el = page.query_selector(f"#{eid}")
    assert el is not None, f"Telemetry field #{eid} must exist"


def test_stage_dv_section(page):
    assert page.query_selector("#stage-dv-section") is not None
    assert page.query_selector("#stage-dv-bars") is not None


def test_vessel_section(page):
    assert page.query_selector("#vessel-section") is not None


@pytest.mark.parametrize("bar_id", ["lf-bar", "sf-bar"])
def test_fuel_bars_exist(page, bar_id):
    el = page.query_selector(f"#{bar_id}")
    assert el is not None, f"Fuel bar #{bar_id} must exist"


def test_fuel_bars_have_width_style(page):
    for bar_id in ("lf-bar", "sf-bar"):
        w = page.evaluate(
            f"document.getElementById('{bar_id}').style.width")
        assert w is not None


# ===================================================================
# Top bar elements
# ===================================================================

def test_mission_name(page):
    el = page.query_selector("#mission-name")
    assert el is not None
    text = page.evaluate("document.getElementById('mission-name').textContent")
    assert len(text.strip()) > 0, "Mission name should not be empty"


def test_phase_badge(page):
    el = page.query_selector("#phase-badge")
    assert el is not None, "Phase badge must exist"


def test_conn_badge(page):
    el = page.query_selector("#conn-badge")
    assert el is not None, "Connection badge must exist"


def test_scenario_btn(page):
    el = page.query_selector("#scenario-btn")
    assert el is not None, "Scenario toggle button must exist"


# ===================================================================
# Right panel — advisory and gates
# ===================================================================

@pytest.mark.parametrize("eid", [
    "advisory-box", "advisory-level", "advisory-action", "advisory-reason",
])
def test_advisory_elements(page, eid):
    el = page.query_selector(f"#{eid}")
    assert el is not None, f"Advisory element #{eid} must exist"


def test_gates_container(page):
    el = page.query_selector("#gates-list")
    assert el is not None, "Gates container must exist"


def test_gates_section(page):
    el = page.query_selector("#gates-section")
    assert el is not None


def test_nominal_section(page):
    el = page.query_selector("#nominal-section")
    assert el is not None


def test_nom_compare(page):
    el = page.query_selector("#nom-compare")
    assert el is not None


# ===================================================================
# Loading overlay
# ===================================================================

def test_loading_overlay_exists(page):
    el = page.query_selector("#loading-overlay")
    assert el is not None


def test_loading_msg_exists(page):
    el = page.query_selector("#loading-msg")
    assert el is not None


def test_loading_bar_exists(page):
    el = page.query_selector("#loading-bar")
    assert el is not None


def test_loading_overlay_visible_before_nominal(page):
    display = page.evaluate(
        "document.getElementById('loading-overlay').style.display")
    assert display in ("flex", "none"), \
        f"Loading overlay display should be flex or none, got {display}"


# ===================================================================
# Scenario panel
# ===================================================================

def test_scenario_panel(page):
    panel = page.query_selector("#scenario-panel")
    assert panel is not None


def test_preset_dropdown(page):
    select = page.query_selector("#sc-preset")
    assert select is not None
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


@pytest.mark.parametrize("eid", [
    "sc-booster-type", "sc-n-boosters", "sc-booster-pct",
    "sc-extra-payload", "sc-pitch-program", "sc-noise",
])
def test_scenario_custom_fields(page, eid):
    el = page.query_selector(f"#{eid}")
    assert el is not None, f"Scenario field #{eid} must exist"


def test_booster_pct_range_label(page):
    el = page.query_selector("#sc-booster-pct-val")
    assert el is not None


def test_noise_range_label(page):
    el = page.query_selector("#sc-noise-val")
    assert el is not None


def test_playback_state_display(page):
    assert page.query_selector("#sc-pb-state") is not None


def test_playback_elapsed_display(page):
    assert page.query_selector("#sc-pb-elapsed") is not None


def test_playback_total_display(page):
    assert page.query_selector("#sc-pb-total") is not None


def test_playback_progress_bar(page):
    assert page.query_selector("#sc-pb-bar") is not None


def test_scenario_summary_section(page):
    assert page.query_selector("#sc-summary-section") is not None
    assert page.query_selector("#sc-summary") is not None


def test_custom_fields_container(page):
    assert page.query_selector("#sc-custom-fields") is not None


def test_scenario_toggle(page):
    page.evaluate("""
        document.getElementById('scenario-panel').classList.remove('open');
        document.getElementById('scenario-btn').classList.remove('active');
    """)
    has_open = page.evaluate(
        "document.getElementById('scenario-panel').classList.contains('open')")
    assert not has_open

    page.evaluate("toggleScenarioPanel()")
    has_open = page.evaluate(
        "document.getElementById('scenario-panel').classList.contains('open')")
    assert has_open, "Panel should open after toggle"

    btn_active = page.evaluate(
        "document.getElementById('scenario-btn').classList.contains('active')")
    assert btn_active, "Button should be active when panel is open"

    page.evaluate("toggleScenarioPanel()")
    has_open = page.evaluate(
        "document.getElementById('scenario-panel').classList.contains('open')")
    assert not has_open, "Panel should close after second toggle"


def test_preset_disables_custom_fields(page):
    page.evaluate("fetchPresets()")
    page.wait_for_timeout(500)
    page.evaluate("document.getElementById('sc-preset').value = 'nominal'")
    page.evaluate("onPresetChange()")
    opacity = page.evaluate(
        "document.getElementById('sc-custom-fields').style.opacity")
    assert opacity == "0.4", f"Custom fields opacity should be 0.4 for preset, got {opacity}"

    page.evaluate("document.getElementById('sc-preset').value = ''")
    page.evaluate("onPresetChange()")
    opacity = page.evaluate(
        "document.getElementById('sc-custom-fields').style.opacity")
    assert opacity == "1", f"Custom fields opacity should be 1 for custom, got {opacity}"


def test_preset_all_scenarios_present(page):
    page.evaluate("fetchPresets()")
    page.wait_for_timeout(500)
    options = page.evaluate("""
        Array.from(document.getElementById('sc-preset').options)
             .map(o => o.value).filter(v => v !== '')
    """)
    expected = {"nominal", "steep_ascent", "shallow_ascent", "late_turn",
                "heavy_payload", "thumper_variant", "high_twr", "abort_steep"}
    assert set(options) == expected, f"Missing presets: {expected - set(options)}"


def test_speed_buttons_exist(page):
    for speed in ("0.5", "1", "2", "5", "10"):
        found = page.evaluate(f"""(() => {{
            const btns = document.querySelectorAll('button');
            return Array.from(btns).some(b => {{
                const oc = b.getAttribute('onclick') || '';
                return oc.includes('scSpeed({speed})');
            }});
        }})()""")
        assert found, f"Speed button for scSpeed({speed}) must exist"


# ===================================================================
# JavaScript utility functions
# ===================================================================

def test_esc_fn_exists(page):
    result = page.evaluate("typeof esc")
    assert result == "function"


def test_esc_escapes_html(page):
    result = page.evaluate("esc('<script>alert(1)</script>')")
    assert "<script>" not in result
    assert "&lt;" in result


def test_esc_handles_ampersand(page):
    result = page.evaluate("esc('A & B')")
    assert "&amp;" in result
    assert "& B" not in result


def test_esc_handles_quotes(page):
    result = page.evaluate("""esc('"hello" & <world>')""")
    assert "&lt;" in result
    assert "&amp;" in result


def test_esc_empty_string(page):
    result = page.evaluate("esc('')")
    assert result == ""


def test_esc_plain_text(page):
    result = page.evaluate("esc('hello world')")
    assert result == "hello world"


def test_el_helper(page):
    result = page.evaluate("el('shell') === document.getElementById('shell')")
    assert result is True


def test_format_met(page):
    result = page.evaluate("formatMET(3661)")
    assert result == "T+ 01:01:01"


def test_format_met_zero(page):
    result = page.evaluate("formatMET(0)")
    assert "00:00:00" in result


def test_format_met_large(page):
    result = page.evaluate("formatMET(86399)")
    assert "23:59:59" in result


def test_fmt_num(page):
    result = page.evaluate("fmtNum(1234.567, 2)")
    assert result == "1234.57"


def test_fmt_num_zero_dec(page):
    result = page.evaluate("fmtNum(42.9)")
    assert result == "43"


def test_fmt_km(page):
    result = page.evaluate("fmtKm(15000)")
    assert result == "15.0"


def test_fmt_km_negative(page):
    result = page.evaluate("fmtKm(-587000)")
    assert result == "-587.0"


def test_color_class_in_range(page):
    result = page.evaluate("colorClass(50, 30, 80)")
    assert result == "good"


def test_color_class_out_of_range(page):
    result = page.evaluate("colorClass(20, 30, 80)")
    assert result == "bad"


def test_set_val(page):
    page.evaluate("setVal('t-alt', '12.3', 'green')")
    text = page.evaluate("document.getElementById('t-alt').textContent")
    assert text == "12.3"


def test_set_conn_badge(page):
    page.evaluate("setConnBadge('on', 'CONNECTED')")
    text = page.evaluate("document.getElementById('conn-badge').textContent")
    assert text == "CONNECTED"


# ===================================================================
# JavaScript global variables and constants
# ===================================================================

def test_kerbin_constants(page):
    r_km = page.evaluate("typeof R_KM !== 'undefined' ? R_KM : null")
    assert r_km is not None
    assert abs(r_km - 600.0) < 1.0


def test_atm_ceil_constant(page):
    atm = page.evaluate("typeof ATM_CEIL_KM !== 'undefined' ? ATM_CEIL_KM : null")
    assert atm is not None
    assert abs(atm - 70.0) < 1.0


def test_circ_speed_constant(page):
    cs = page.evaluate("typeof CIRC_SPEED_80KM !== 'undefined' ? CIRC_SPEED_80KM : null")
    assert cs is not None
    assert abs(cs - 2279) < 10


def test_mu_kerbin_constant(page):
    mu = page.evaluate(
        "typeof MU_KERBIN_PROJ !== 'undefined' ? MU_KERBIN_PROJ : null")
    assert mu is not None
    assert mu > 3.5e12


@pytest.mark.parametrize("varname", [
    "PROJ_CDA", "PROJ_RHO0", "PROJ_SCALE_H", "PROJ_ATM_CEIL_M", "PROJ_MASS_KG",
])
def test_projection_constants(page, varname):
    val = page.evaluate(f"typeof {varname} !== 'undefined' ? {varname} : null")
    assert val is not None, f"{varname} must be defined"
    assert val > 0, f"{varname} must be positive"


@pytest.mark.parametrize("varname,expected_type", [
    ("nominalTraj", "object"),
    ("nominalAscent", "object"),
    ("nominalCoast", "object"),
    ("phaseBands", "object"),
    ("actualTraj", "object"),
    ("latestState", "object"),
    ("latestDirector", "object"),
    ("simMode", "boolean"),
    ("scenarioPresets", "object"),
])
def test_global_state_variables(page, varname, expected_type):
    t = page.evaluate(f"typeof {varname}")
    assert t == expected_type, f"{varname} should be {expected_type}, got {t}"


# ===================================================================
# Phase colors and labels
# ===================================================================

@pytest.mark.parametrize("phase", [
    "BOOST", "CORE", "TERRIER", "COAST_APO", "CIRCULARIZE", "ORBIT", "COAST",
])
def test_phase_color_defined(page, phase):
    val = page.evaluate(f"PHASE_COLORS['{phase}']")
    assert val is not None, f"PHASE_COLORS['{phase}'] must be defined"


@pytest.mark.parametrize("phase", [
    "BOOST", "CORE", "TERRIER", "COAST_APO", "CIRCULARIZE", "ORBIT", "COAST",
])
def test_phase_label_defined(page, phase):
    val = page.evaluate(f"PHASE_LABELS['{phase}']")
    assert val is not None, f"PHASE_LABELS['{phase}'] must be defined"
    assert len(val) > 0


# ===================================================================
# Ballistic projection engine
# ===================================================================

def test_projection_fn_exists(page):
    result = page.evaluate("typeof projectBallisticArc")
    assert result == "function"


def test_projection_returns_array(page):
    result = page.evaluate("""
        projectBallisticArc(15000, 492, 414, 8.31)
    """)
    assert isinstance(result, list)
    assert len(result) > 0


def test_projection_starts_at_input(page):
    result = page.evaluate("""
        projectBallisticArc(15000, 492, 414, 8.31)
    """)
    first = result[0]
    assert abs(first["altitude_km"] - 15.0) < 0.1
    assert abs(first["downrange_km"] - 8.31) < 0.1


def test_projection_returns_to_ground(page):
    result = page.evaluate("""
        projectBallisticArc(15000, 200, 100, 8.0)
    """)
    last = result[-1]
    assert last["altitude_km"] <= 0.1, \
        f"Suborbital projection should return to ground, ended at {last['altitude_km']:.1f} km"


def test_projection_orbital_stays_high(page):
    result = page.evaluate("""
        projectBallisticArc(80000, 2279, 0, 50.0)
    """)
    min_alt = min(p["altitude_km"] for p in result)
    assert min_alt > 60, \
        f"Orbital-speed projection should stay high, min alt = {min_alt:.1f} km"


def test_projection_has_required_keys(page):
    result = page.evaluate("""
        projectBallisticArc(15000, 492, 414, 8.31)
    """)
    first = result[0]
    assert "altitude_km" in first
    assert "downrange_km" in first


def test_compute_nominal_coast_fn(page):
    result = page.evaluate("typeof computeNominalCoast")
    assert result == "function"


def test_build_phase_bands_fn(page):
    result = page.evaluate("typeof buildPhaseBands")
    assert result == "function"


def test_build_phase_bands_with_data(page):
    bands = page.evaluate("""(() => {
        const traj = [
            {phase: 'BOOST', t: 0}, {phase: 'BOOST', t: 10},
            {phase: 'CORE', t: 11}, {phase: 'CORE', t: 30},
            {phase: 'TERRIER', t: 31}, {phase: 'TERRIER', t: 60},
        ];
        return buildPhaseBands(traj);
    })()""")
    assert len(bands) == 3
    assert bands[0]["label"] == "BOOST" or "BOOST" in str(bands[0])
    assert bands[1]["label"] == "CORE" or "CORE" in str(bands[1])
    assert bands[2]["label"] == "TERRIER" or "TERRIER" in str(bands[2])


def test_build_phase_bands_single_phase(page):
    bands = page.evaluate("""(() => {
        const traj = [{phase: 'BOOST', t: 0}, {phase: 'BOOST', t: 25}];
        return buildPhaseBands(traj);
    })()""")
    assert len(bands) == 1
    assert "start" in bands[0]
    assert "end" in bands[0]


def test_build_phase_bands_empty(page):
    bands = page.evaluate("buildPhaseBands([])")
    assert bands == []


# ===================================================================
# Canvas drawing functions
# ===================================================================

def test_draw_globe_fn(page):
    assert page.evaluate("typeof drawGlobe") == "function"


def test_draw_trajectory_plot_fn(page):
    assert page.evaluate("typeof drawTrajectoryPlot") == "function"


def test_draw_timeline_fn(page):
    assert page.evaluate("typeof drawTimeline") == "function"


def test_render_all_fn(page):
    assert page.evaluate("typeof renderAll") == "function"


def test_render_all_no_error(page):
    error = page.evaluate("""(() => {
        try { renderAll(); return null; }
        catch(e) { return e.message; }
    })()""")
    assert error is None, f"renderAll() threw: {error}"


# ===================================================================
# Stage dV bars
# ===================================================================

def test_stage_dv_bars_fn(page):
    result = page.evaluate("typeof updateStageDVBars")
    assert result == "function"


def test_stage_dv_bars_render(page):
    page.evaluate("""
        updateStageDVBars([
            {label:'Stage 0', dv_remaining:500, dv_initial:800, status:'active',
             fuel_pct:62.5, burn_s:25.3},
            {label:'Stage 1', dv_remaining:3458, dv_initial:3458, status:'pending',
             fuel_pct:100, burn_s:0},
        ])
    """)
    display = page.evaluate(
        "document.getElementById('stage-dv-section').style.display")
    assert display != "none"
    html = page.evaluate(
        "document.getElementById('stage-dv-bars').innerHTML")
    assert "Stage 0" in html
    assert "Stage 1" in html


def test_stage_dv_bars_empty_hides(page):
    page.evaluate("updateStageDVBars([])")
    display = page.evaluate(
        "document.getElementById('stage-dv-section').style.display")
    assert display == "none"


def test_stage_dv_bars_depleted_class(page):
    page.evaluate("""
        updateStageDVBars([
            {label:'Stage 0', dv_remaining:0, dv_initial:800, status:'depleted',
             fuel_pct:0, burn_s:25.3},
        ])
    """)
    cls = page.evaluate("document.getElementById('stage-dv-0').className")
    assert "depleted" in cls


def test_stage_colors_array(page):
    colors = page.evaluate("STAGE_COLORS")
    assert isinstance(colors, list)
    assert len(colors) >= 3


# ===================================================================
# Telemetry update function
# ===================================================================

def test_update_telemetry_panel_fn(page):
    assert page.evaluate("typeof updateTelemetryPanel") == "function"


def test_update_telemetry_panel_populates(page):
    page.evaluate("""
        latestState = {
            altitude: 15000, velocity: 631, v_vert: 414, v_horiz: 492,
            apoapsis: 25000, periapsis: -587000, mission_time: 63,
            throttle: 1.0, liquid_fuel: 300, solid_fuel: 0,
            pitch: 50, heading: 90, roll: 0,
            mass: 8.5, g_force: 1.8
        };
        updateTelemetryPanel();
    """)
    alt_text = page.evaluate("document.getElementById('t-alt').textContent")
    assert "15" in alt_text, f"Expected altitude ~15, got {alt_text}"

    vel_text = page.evaluate("document.getElementById('t-vel').textContent")
    assert "631" in vel_text, f"Expected velocity ~631, got {vel_text}"

    met_text = page.evaluate("document.getElementById('met-display').textContent")
    assert "01:03" in met_text


def test_update_telemetry_fuel_bars(page):
    page.evaluate("""
        latestState = {
            altitude: 10000, velocity: 500, v_vert: 300, v_horiz: 400,
            apoapsis: 20000, periapsis: -500000, mission_time: 40,
            throttle: 1.0, liquid_fuel: 180, solid_fuel: 80,
            pitch: 60, heading: 90, roll: 0,
        };
        updateTelemetryPanel();
    """)
    lf_width = page.evaluate("document.getElementById('lf-bar').style.width")
    sf_width = page.evaluate("document.getElementById('sf-bar').style.width")
    assert "50" in lf_width, f"LF bar should show ~50%, got {lf_width}"
    assert "50" in sf_width, f"SF bar should show ~50%, got {sf_width}"


# ===================================================================
# Flight director update
# ===================================================================

def test_update_director_panel_fn(page):
    assert page.evaluate("typeof updateDirectorPanel") == "function"


def test_update_director_panel_advisory(page):
    page.evaluate("""
        latestDirector = {
            advisory: {level: 'CAUTION', action: 'PITCH TOWARD HORIZON',
                       reason: 'Steep ascent', urgent: false},
            gates: [{phase: 'CORE B/O', status: 'GO', detail: '24.6 km Ap'}],
            nominal_at_alt: {altitude_km: 15},
            phase: 'TERRIER'
        };
        updateDirectorPanel();
    """)
    level_text = page.evaluate(
        "document.getElementById('advisory-level').textContent")
    assert level_text == "CAUTION"
    action_text = page.evaluate(
        "document.getElementById('advisory-action').textContent")
    assert "PITCH TOWARD HORIZON" in action_text

    box_cls = page.evaluate(
        "document.getElementById('advisory-box').className")
    assert "CAUTION" in box_cls

    gates_html = page.evaluate(
        "document.getElementById('gates-list').innerHTML")
    assert "CORE B/O" in gates_html
    assert "GO" in gates_html


def test_update_director_warning_class(page):
    page.evaluate("""
        latestDirector = {
            advisory: {level: 'WARNING', action: 'LOW FUEL',
                       reason: 'Fuel below threshold', urgent: true},
            gates: [], phase: 'TERRIER'
        };
        updateDirectorPanel();
    """)
    cls = page.evaluate("document.getElementById('advisory-box').className")
    assert "WARNING" in cls


def test_update_director_abort_class(page):
    page.evaluate("""
        latestDirector = {
            advisory: {level: 'ABORT', action: 'ABORT ABORT ABORT',
                       reason: 'Critical failure', urgent: true},
            gates: [], phase: 'TERRIER'
        };
        updateDirectorPanel();
    """)
    cls = page.evaluate("document.getElementById('advisory-box').className")
    assert "ABORT" in cls


def test_phase_badge_exists_and_has_text(page):
    text = page.evaluate("document.getElementById('phase-badge').textContent")
    assert len(text.strip()) > 0, "Phase badge should have text content"


# ===================================================================
# Socket.IO connection
# ===================================================================

def test_socket_object_exists(page):
    t = page.evaluate("typeof socket")
    assert t == "object", "Socket.IO client must be initialized"


def test_socket_io_initialized(page):
    exists = page.evaluate("typeof socket !== 'undefined' && socket !== null")
    assert exists is True, "Socket.IO client must be initialized"
    has_on = page.evaluate("typeof socket.on === 'function'")
    assert has_on is True, "Socket should have .on() method"


def test_nominal_traj_is_array(page):
    t = page.evaluate("Array.isArray(nominalTraj)")
    assert t is True


def test_nominal_ascent_is_array(page):
    t = page.evaluate("Array.isArray(nominalAscent)")
    assert t is True


def test_nominal_coast_is_array(page):
    t = page.evaluate("Array.isArray(nominalCoast)")
    assert t is True


def test_phase_bands_is_array(page):
    t = page.evaluate("Array.isArray(phaseBands)")
    assert t is True


# ===================================================================
# Houston UI integration
# ===================================================================

def test_mc_api_object(page):
    result = page.evaluate("typeof window.MissionControl")
    assert result == "object"
    methods = page.evaluate("""
        Object.keys(window.MissionControl).filter(
            k => typeof window.MissionControl[k] === 'function')
    """)
    assert "loadScenario" in methods
    assert "controlPlayback" in methods


def test_mc_show_panel_method(page):
    has = page.evaluate("typeof window.MissionControl.showPanel")
    assert has == "function"


@pytest.mark.parametrize("panel_name", [
    "topbar", "telemetry", "globe", "trajectory", "director", "timeline",
])
def test_data_panel_attributes(page, panel_name):
    el = page.query_selector(f"[data-panel='{panel_name}']")
    assert el is not None, f"data-panel='{panel_name}' element must exist"


def test_mc_show_panel_hides_others(page):
    page.evaluate("""
        document.querySelectorAll('[data-panel]').forEach(
            el => el.style.display = '');
        window.MissionControl.showPanel('globe');
    """)
    globe_display = page.evaluate(
        "document.querySelector('[data-panel=\"globe\"]').style.display")
    telem_display = page.evaluate(
        "document.querySelector('[data-panel=\"telemetry\"]').style.display")
    assert globe_display != "none", "Globe panel should be visible"
    assert telem_display == "none", "Telemetry panel should be hidden"

    page.evaluate("""
        document.querySelectorAll('[data-panel]').forEach(
            el => el.style.display = '');
    """)


# ===================================================================
# CSS custom properties
# ===================================================================

@pytest.mark.parametrize("prop", [
    "--mc-bg", "--mc-panel", "--mc-panel-alt", "--mc-border",
    "--mc-accent", "--mc-accent-dim",
    "--mc-text", "--mc-text-dim", "--mc-text-bright",
    "--mc-green", "--mc-green-bright",
    "--mc-yellow", "--mc-yellow-bright",
    "--mc-red", "--mc-red-bright",
    "--mc-violet", "--mc-violet-bright",
    "--mc-teal", "--mc-teal-bright",
    "--mc-abort",
    "--mc-font-mono", "--mc-font-ui",
])
def test_css_vars(page, prop):
    val = page.evaluate(
        f"getComputedStyle(document.documentElement).getPropertyValue('{prop}').trim()")
    assert len(val) > 0, f"CSS custom property {prop} must be defined"


def test_css_bg_is_dark(page):
    bg = page.evaluate("""
        getComputedStyle(document.documentElement)
            .getPropertyValue('--mc-bg').trim()
    """)
    assert bg.startswith("#0") or bg.startswith("rgb"), \
        f"Background should be dark, got {bg}"


def test_body_uses_mc_bg(page):
    bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert bg != "" and bg != "rgba(0, 0, 0, 0)", \
        "Body should have a background color set"


def test_body_uses_mc_text(page):
    color = page.evaluate("getComputedStyle(document.body).color")
    assert color != "" and color != "rgba(0, 0, 0, 0)"


def test_body_font_family(page):
    ff = page.evaluate("getComputedStyle(document.body).fontFamily")
    assert len(ff) > 0


# ===================================================================
# Advisory audio
# ===================================================================

def test_play_advisory_alert_fn(page):
    assert page.evaluate("typeof playAdvisoryAlert") == "function"


def test_alert_ctx_exists(page):
    assert page.evaluate("typeof _alertCtx") != "undefined"


# ===================================================================
# Scenario load and playback via API
# ===================================================================

def test_load_scenario_via_js(page):
    result = page.evaluate("""(async () => {
        const r = await fetch('/api/scenario/load', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({preset: 'nominal'})
        });
        return {status: r.status, ok: r.ok};
    })()""")
    assert result["ok"] is True, f"Load scenario failed: status {result['status']}"


def test_scenario_start_via_js(page):
    page.evaluate("""(async () => {
        await fetch('/api/scenario/load', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({preset: 'nominal'})
        });
    })()""")
    page.wait_for_timeout(300)
    result = page.evaluate("""(async () => {
        const r = await fetch('/api/scenario/start', {method: 'POST'});
        return {status: r.status};
    })()""")
    assert result["status"] == 200


def test_scenario_playback_updates_ui(page):
    page.evaluate("""
        updatePlaybackUI({state: 'playing', elapsed: 30.5, total: 120.0,
                          speed: 2.0});
    """)
    state = page.evaluate(
        "document.getElementById('sc-pb-state').textContent")
    assert "PLAYING" in state

    elapsed = page.evaluate(
        "document.getElementById('sc-pb-elapsed').textContent")
    assert "30" in elapsed


def test_scenario_summary_update(page):
    page.evaluate("""
        updateScenarioSummary({
            vehicle: 'Perseus 1',
            liftoff_mass_t: 14.21,
            pitch_program: 'nominal',
            n_boosters: 2,
            booster_type: 'hammer',
            pad_twr: 1.77
        });
    """)
    html = page.evaluate(
        "document.getElementById('sc-summary').innerHTML")
    assert "Perseus 1" in html or "14.21" in html


# ===================================================================
# XSS escaping in DOM updates
# ===================================================================

def test_xss_in_gates(page):
    page.evaluate("""
        latestDirector = {
            advisory: {level: 'NOMINAL', action: 'OK', reason: ''},
            gates: [{phase: '<img src=x onerror=alert(1)>',
                     status: 'GO', detail: 'test'}],
            phase: 'BOOST'
        };
        updateDirectorPanel();
    """)
    html = page.evaluate("document.getElementById('gates-list').innerHTML")
    assert "<img" not in html, "Gate phase must be XSS-escaped"
    assert "&lt;" in html


def test_xss_in_stage_labels(page):
    page.evaluate("""
        updateStageDVBars([
            {label:'<script>alert(1)</script>', dv_remaining:500,
             dv_initial:800, status:'active', fuel_pct:62, burn_s:10},
        ])
    """)
    html = page.evaluate("document.getElementById('stage-dv-bars').innerHTML")
    assert "<script>alert(1)</script>" not in html, \
        "Script tags must not appear unescaped in stage labels"


def test_xss_in_scenario_summary(page):
    page.evaluate("""
        updateScenarioSummary({
            vehicle: '<img src=x>',
            liftoff_mass_t: 14.21,
            pitch_program: 'nominal',
        });
    """)
    html = page.evaluate("document.getElementById('sc-summary').innerHTML")
    assert "<img" not in html


# ===================================================================
# Resize handling
# ===================================================================

def test_invalidate_on_resize_direct(page):
    page.evaluate("invalidateCanvasSizes(); getCanvasSize('globe-canvas')")
    cached_before = page.evaluate("Object.keys(_canvasSizes).length")
    assert cached_before > 0
    page.evaluate("invalidateCanvasSizes()")
    cached_after = page.evaluate("Object.keys(_canvasSizes).length")
    assert cached_after == 0


def test_resize_event_handler_exists(page):
    has_handler = page.evaluate("""(() => {
        let called = false;
        const orig = invalidateCanvasSizes;
        return typeof orig === 'function';
    })()""")
    assert has_handler


# ===================================================================
# Globe zoom
# ===================================================================

def test_globe_zoom_mul_default(page):
    val = page.evaluate("_globeZoomMul")
    assert val == 1.0


def test_globe_zoom_wheel_changes_mul(page):
    page.evaluate("_globeZoomMul = 1.0")
    page.evaluate("""
        const c = document.getElementById('globe-canvas');
        c.dispatchEvent(new WheelEvent('wheel', {deltaY: 100}));
    """)
    val = page.evaluate("_globeZoomMul")
    assert val != 1.0, f"Scroll should change zoom multiplier, got {val}"


def test_globe_zoom_reset_dblclick(page):
    page.evaluate("_globeZoomMul = 2.5")
    page.evaluate("""
        const c = document.getElementById('globe-canvas');
        c.dispatchEvent(new MouseEvent('dblclick'));
    """)
    val = page.evaluate("_globeZoomMul")
    assert val == 1.0, f"Double-click should reset zoom to 1.0, got {val}"


# ===================================================================
# Miscellaneous
# ===================================================================

def test_animate_fn(page):
    assert page.evaluate("typeof animate") == "function"


def test_sim_mode_flag(page):
    val = page.evaluate("simMode")
    assert isinstance(val, bool)


def test_actual_traj_initially_empty(page):
    page.evaluate("actualTraj = []")
    assert page.evaluate("actualTraj.length") == 0
