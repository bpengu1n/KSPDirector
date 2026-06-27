"""
tests/test_visual_playwright.py
================================
Visual regression tests using Playwright screenshots + bounding-box assertions.

These tests verify the rendered appearance and element placement of the Mission
Control UI — not just DOM existence. They check:
  - Panel layout at 1280×720 (positions, sizes, non-overlap)
  - CSS color theming (dark background, accent colors)
  - Advisory box color states (NOMINAL/CAUTION/WARNING/ABORT)
  - Prelaunch overlay positioning and visibility
  - Mission branding display styling
  - Screenshot-based full-page and per-panel golden image capture
  - Gate indicator colors match status
  - Telemetry panel typography and alignment

Requires: pip install playwright
Browser:  /opt/pw-browsers/chromium-1194/chrome-linux/chrome (pre-installed)
"""

import os
import socket
import threading
import time

import pytest

CHROMIUM_PATH = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")

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


from tests.playwright_helpers import RESET_JS as _RESET_JS


@pytest.fixture(autouse=True)
def reset_ui(page):
    """Reset all mutable UI state before each test."""
    page.evaluate(_RESET_JS)
    page.evaluate("dismissPrelaunch()")
    page.wait_for_timeout(100)


@pytest.fixture(scope="module")
def page():
    """Start server, launch browser at 1280×720, dismiss prelaunch, yield page."""
    port = _free_port()
    t = threading.Thread(target=_start_server, args=(port,), daemon=True)
    t.start()

    for _ in range(40):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.25)

    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        executable_path=CHROMIUM_PATH, headless=True)
    p = browser.new_page(viewport={"width": 1280, "height": 720})
    p.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
    p.evaluate("dismissPrelaunch()")
    p.wait_for_timeout(300)

    yield p

    p.close()
    browser.close()
    pw.stop()


def _bbox(page, selector):
    return page.evaluate(f"""(() => {{
        const el = document.querySelector('{selector}');
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return {{x: r.x, y: r.y, w: r.width, h: r.height,
                 right: r.right, bottom: r.bottom}};
    }})()""")


def _computed(page, selector, prop):
    return page.evaluate(
        f"getComputedStyle(document.querySelector('{selector}')).{prop}")


def _css_var(page, prop):
    return page.evaluate(
        f"getComputedStyle(document.documentElement)"
        f".getPropertyValue('{prop}').trim()")


# ============================================================
#  Panel layout at 1280×720
# ============================================================

class TestPanelLayout:
    """Verify the 5 panels fill the viewport correctly at 1280×720."""

    def test_topbar_spans_full_width(self, page):
        b = _bbox(page, "#topbar")
        assert b is not None
        assert b["w"] == pytest.approx(1280, abs=2)
        assert b["x"] == pytest.approx(0, abs=1)

    def test_topbar_height(self, page):
        b = _bbox(page, "#topbar")
        assert b["h"] == pytest.approx(56, abs=2)

    def test_left_panel_position(self, page):
        b = _bbox(page, "#left-panel")
        assert b is not None
        assert b["x"] == pytest.approx(0, abs=1)
        assert b["y"] == pytest.approx(57, abs=2)
        assert b["w"] == pytest.approx(280, abs=2)

    def test_center_panel_position(self, page):
        b = _bbox(page, "#center-panel")
        assert b is not None
        assert b["x"] == pytest.approx(281, abs=2)
        assert b["y"] == pytest.approx(57, abs=2)
        assert b["w"] == pytest.approx(708, abs=5)

    def test_right_panel_position(self, page):
        b = _bbox(page, "#right-panel")
        assert b is not None
        assert b["x"] == pytest.approx(990, abs=5)
        assert b["y"] == pytest.approx(57, abs=2)
        assert b["w"] == pytest.approx(290, abs=5)

    def test_timeline_spans_full_width(self, page):
        b = _bbox(page, "#timeline-bar")
        assert b is not None
        assert b["w"] == pytest.approx(1280, abs=2)
        assert b["h"] == pytest.approx(44, abs=2)

    def test_timeline_at_bottom(self, page):
        b = _bbox(page, "#timeline-bar")
        assert b["bottom"] == pytest.approx(720, abs=2)

    def test_panels_fill_viewport_height(self, page):
        top = _bbox(page, "#topbar")
        mid = _bbox(page, "#center-panel")
        bot = _bbox(page, "#timeline-bar")
        total = top["h"] + mid["h"] + bot["h"]
        assert total == pytest.approx(720, abs=5), \
            f"Panels should fill 720px, got {total}"

    def test_no_horizontal_overlap_left_center(self, page):
        left = _bbox(page, "#left-panel")
        center = _bbox(page, "#center-panel")
        assert left["right"] <= center["x"] + 2

    def test_no_horizontal_overlap_center_right(self, page):
        center = _bbox(page, "#center-panel")
        right = _bbox(page, "#right-panel")
        assert center["right"] <= right["x"] + 2

    def test_right_panel_reaches_edge(self, page):
        right = _bbox(page, "#right-panel")
        assert right["right"] == pytest.approx(1280, abs=2)

    def test_middle_row_panels_same_height(self, page):
        left = _bbox(page, "#left-panel")
        center = _bbox(page, "#center-panel")
        right = _bbox(page, "#right-panel")
        assert left["h"] == pytest.approx(center["h"], abs=2)
        assert center["h"] == pytest.approx(right["h"], abs=2)


# ============================================================
#  CSS theming (dark mode colors)
# ============================================================

class TestCSSTheming:
    """Verify the dark theme CSS custom properties and computed colors."""

    def test_background_is_dark(self, page):
        bg = _computed(page, "body", "backgroundColor")
        r, g, b = _parse_rgb(bg)
        assert r < 30 and g < 30 and b < 30, \
            f"Body background should be very dark, got {bg}"

    def test_panel_background_darker_than_body(self, page):
        body_bg = _computed(page, "body", "backgroundColor")
        panel_bg = _computed(page, "#topbar", "backgroundColor")
        br, bg_, bb = _parse_rgb(body_bg)
        pr, pg, pb = _parse_rgb(panel_bg)
        assert (pr + pg + pb) > (br + bg_ + bb), \
            "Panel bg should be slightly lighter than body bg"

    def test_accent_color_is_blue(self, page):
        accent = _css_var(page, "--mc-accent")
        assert accent == "#1e88e5"

    def test_text_color_is_light(self, page):
        color = _computed(page, "body", "color")
        r, g, b = _parse_rgb(color)
        assert r > 180 and g > 180 and b > 180, \
            f"Text should be light on dark bg, got {color}"

    def test_green_var_defined(self, page):
        assert _css_var(page, "--mc-green") == "#2e7d32"

    def test_red_var_defined(self, page):
        assert _css_var(page, "--mc-red") == "#b71c1c"

    def test_yellow_var_defined(self, page):
        assert _css_var(page, "--mc-yellow") == "#e65100"


# ============================================================
#  Advisory box color states
# ============================================================

class TestAdvisoryColors:
    """Verify advisory box changes color based on alert level."""

    def test_nominal_green_border(self, page):
        border = _computed(page, "#advisory-box.NOMINAL", "borderColor")
        if border:
            r, g, b = _parse_rgb(border)
            assert g > r and g > b, \
                f"NOMINAL border should be green, got {border}"

    def test_caution_changes_border(self, page):
        page.evaluate("""
            document.getElementById('advisory-box').className = 'CAUTION';
        """)
        page.wait_for_timeout(400)
        border = _computed(page, "#advisory-box", "borderTopColor")
        r, g, b = _parse_rgb(border)
        assert r > b, f"CAUTION border should be orange/amber, got {border}"
        page.evaluate("""
            document.getElementById('advisory-box').className = 'NOMINAL';
        """)
        page.wait_for_timeout(400)

    def test_warning_red_border(self, page):
        page.evaluate("""
            document.getElementById('advisory-box').className = 'WARNING';
        """)
        page.wait_for_timeout(400)
        border = _computed(page, "#advisory-box", "borderTopColor")
        r, g, b = _parse_rgb(border)
        assert r > g and r > b, \
            f"WARNING border should be red, got {border}"
        page.evaluate("""
            document.getElementById('advisory-box').className = 'NOMINAL';
        """)
        page.wait_for_timeout(400)

    def test_abort_red_background_stronger(self, page):
        page.evaluate("""
            document.getElementById('advisory-box').className = 'ABORT';
        """)
        page.wait_for_timeout(400)
        bg = _computed(page, "#advisory-box", "backgroundColor")
        r, g, b, a = _parse_rgba(bg)
        assert r > g and r > b, \
            f"ABORT background should be red-tinted, got {bg}"
        assert a > 0.2, f"ABORT background alpha should be >0.2, got {a}"
        page.evaluate("""
            document.getElementById('advisory-box').className = 'NOMINAL';
        """)
        page.wait_for_timeout(400)

    def test_advisory_level_text_color_nominal(self, page):
        page.evaluate("""
            const el = document.getElementById('advisory-level');
            el.className = 'NOMINAL';
            el.textContent = 'NOMINAL';
        """)
        color = _computed(page, "#advisory-level", "color")
        r, g, b = _parse_rgb(color)
        assert g > r and g > b, \
            f"NOMINAL level text should be green, got {color}"

    def test_advisory_level_text_color_caution(self, page):
        page.evaluate("""
            const el = document.getElementById('advisory-level');
            el.className = 'CAUTION';
        """)
        color = _computed(page, "#advisory-level", "color")
        r, g, b = _parse_rgb(color)
        assert r > b, f"CAUTION level text should be amber, got {color}"
        page.evaluate("""
            const el = document.getElementById('advisory-level');
            el.className = 'NOMINAL';
        """)


# ============================================================
#  Mission branding display
# ============================================================

class TestMissionBranding:
    """Verify mission name display styling and placement."""

    def test_mission_name_in_topbar(self, page):
        name_box = _bbox(page, "#mission-name")
        topbar_box = _bbox(page, "#topbar")
        assert name_box is not None
        assert name_box["y"] >= topbar_box["y"]
        assert name_box["bottom"] <= topbar_box["bottom"]

    def test_mission_name_accent_color(self, page):
        color = _computed(page, "#mission-name", "color")
        r, g, b = _parse_rgb(color)
        assert b > r, f"Mission name should be blue/accent, got {color}"

    def test_mission_name_font_size(self, page):
        fs = _computed(page, "#mission-name", "fontSize")
        size = float(fs.replace("px", ""))
        assert 11 <= size <= 16, \
            f"Mission name font size should be 11-16px, got {fs}"

    def test_custom_name_updates_display(self, page):
        page.evaluate("setMissionName('ATLAS V')")
        text = page.evaluate(
            "document.getElementById('mission-name').textContent")
        assert "ATLAS V" in text
        color = _computed(page, "#mission-name", "color")
        r, g, b = _parse_rgb(color)
        assert b > r, "Custom name should keep accent color"
        page.evaluate("setMissionName('')")

    def test_met_display_in_topbar(self, page):
        met_box = _bbox(page, "#met-display")
        topbar_box = _bbox(page, "#topbar")
        assert met_box is not None
        assert met_box["y"] >= topbar_box["y"]
        assert met_box["bottom"] <= topbar_box["bottom"]

    def test_met_display_font_is_monospace(self, page):
        ff = _computed(page, "#met-display", "fontFamily")
        assert any(mono in ff.lower() for mono in
                   ["mono", "courier", "consolas", "ibm plex"]), \
            f"MET display should use monospace font, got {ff}"


# ============================================================
#  Prelaunch overlay
# ============================================================

class TestPrelaunchOverlay:
    """Verify prelaunch overlay appearance and dismissal."""

    def test_prelaunch_overlay_covers_viewport(self, page):
        page.evaluate("""
            document.getElementById('prelaunch-overlay').classList
                .remove('hidden');
        """)
        page.wait_for_timeout(100)
        b = _bbox(page, "#prelaunch-overlay")
        assert b["w"] >= 1280
        assert b["h"] >= 720
        page.evaluate("dismissPrelaunch()")
        page.wait_for_timeout(300)

    def test_prelaunch_overlay_centered_content(self, page):
        page.evaluate("""
            document.getElementById('prelaunch-overlay').classList
                .remove('hidden');
        """)
        page.wait_for_timeout(100)
        display = _computed(page, "#prelaunch-overlay", "display")
        assert display == "flex"
        justify = _computed(page, "#prelaunch-overlay", "justifyContent")
        align = _computed(page, "#prelaunch-overlay", "alignItems")
        assert justify == "center"
        assert align == "center"
        page.evaluate("dismissPrelaunch()")
        page.wait_for_timeout(300)

    def test_checklist_items_visible(self, page):
        page.evaluate("""
            document.getElementById('prelaunch-overlay').classList
                .remove('hidden');
        """)
        page.wait_for_timeout(100)
        items = page.evaluate("""
            Array.from(document.querySelectorAll('.checklist-item'))
                .map(el => {
                    const r = el.getBoundingClientRect();
                    return {w: r.width, h: r.height, visible: r.width > 0};
                })
        """)
        assert len(items) >= 5
        for item in items:
            assert item["visible"], "Checklist items should be visible"
            assert item["h"] > 20, "Checklist items should have readable height"
        page.evaluate("dismissPrelaunch()")
        page.wait_for_timeout(300)


# ============================================================
#  Canvas placement
# ============================================================

class TestCanvasPlacement:
    """Verify canvases are positioned within their parent panels."""

    def test_globe_canvas_inside_center(self, page):
        globe = _bbox(page, "#globe-canvas")
        center = _bbox(page, "#center-panel")
        assert globe["x"] >= center["x"]
        assert globe["right"] <= center["right"] + 1
        assert globe["y"] >= center["y"]

    def test_traj_canvas_inside_center(self, page):
        traj = _bbox(page, "#traj-canvas")
        center = _bbox(page, "#center-panel")
        assert traj["x"] >= center["x"]
        assert traj["right"] <= center["right"] + 1

    def test_timeline_canvas_inside_timeline_bar(self, page):
        tc = _bbox(page, "#timeline-canvas")
        tb = _bbox(page, "#timeline-bar")
        assert tc is not None
        assert tc["x"] >= tb["x"]
        assert tc["right"] <= tb["right"] + 1
        assert tc["y"] >= tb["y"]
        assert tc["bottom"] <= tb["bottom"] + 1

    def test_globe_and_traj_both_visible(self, page):
        globe = _bbox(page, "#globe-canvas")
        traj = _bbox(page, "#traj-canvas")
        assert globe["w"] > 50
        assert globe["h"] > 50
        assert traj["w"] > 50
        assert traj["h"] > 50


# ============================================================
#  Telemetry panel visual structure
# ============================================================

class TestTelemetryLayout:
    """Verify telemetry values are inside the left panel with correct styling."""

    def test_telemetry_fields_inside_left_panel(self, page):
        left = _bbox(page, "#left-panel")
        for eid in ["t-alt", "t-vel", "t-apo", "t-pe"]:
            b = _bbox(page, f"#{eid}")
            assert b is not None, f"#{eid} must exist"
            assert b["x"] >= left["x"], \
                f"#{eid} should be inside left panel"
            assert b["right"] <= left["right"] + 2, \
                f"#{eid} should not extend past left panel"

    def test_telemetry_values_monospace(self, page):
        ff = _computed(page, "#t-alt", "fontFamily")
        assert any(mono in ff.lower() for mono in
                   ["mono", "courier", "consolas", "ibm plex"]), \
            f"Telemetry values should use monospace font, got {ff}"

    def test_telemetry_values_right_positioned(self, page):
        result = page.evaluate("""(() => {
            const row = document.getElementById('t-alt').closest('.telem-row');
            if (!row) return null;
            const s = getComputedStyle(row);
            return {display: s.display, justify: s.justifyContent};
        })()""")
        assert result is not None
        assert result["display"] == "flex"
        assert result["justify"] == "space-between"

    def test_section_headers_exist_and_styled(self, page):
        headers = page.evaluate("""
            Array.from(document.querySelectorAll('.telem-section-title'))
                .filter(el => getComputedStyle(el.parentElement).display !== 'none')
                .map(el => ({
                    text: el.textContent,
                    color: getComputedStyle(el).color,
                    height: el.getBoundingClientRect().height,
                }))
        """)
        assert len(headers) >= 3, "Should have >=3 visible telemetry sections"
        for h in headers:
            assert h["height"] > 0, \
                f"Section header '{h['text']}' should have height"


# ============================================================
#  Gate indicators visual state
# ============================================================

class TestGateIndicatorColors:
    """Verify gate indicators change color based on status."""

    def test_go_indicator_green(self, page):
        page.evaluate("""
            const container = document.getElementById('gates-list');
            container.innerHTML = '<div class="gate-row">' +
                '<span class="gate-indicator GO"></span>' +
                '<span class="gate-status-text GO">GO</span></div>';
        """)
        color = _computed(page, ".gate-indicator.GO", "backgroundColor")
        r, g, b = _parse_rgb(color)
        assert g > r and g > b, \
            f"GO indicator should be green, got {color}"

    def test_nogo_indicator_red(self, page):
        page.evaluate("""
            const container = document.getElementById('gates-list');
            container.innerHTML = '<div class="gate-row">' +
                '<span class="gate-indicator NO-GO"></span>' +
                '<span class="gate-status-text NO-GO">NO-GO</span></div>';
        """)
        color = _computed(page, ".gate-indicator.NO-GO", "backgroundColor")
        r, g, b = _parse_rgb(color)
        assert r > g and r > b, \
            f"NO-GO indicator should be red, got {color}"

    def test_marginal_indicator_amber(self, page):
        page.evaluate("""
            const container = document.getElementById('gates-list');
            container.innerHTML = '<div class="gate-row">' +
                '<span class="gate-indicator MARGINAL"></span>' +
                '<span class="gate-status-text MARGINAL">MARGINAL</span></div>';
        """)
        color = _computed(page, ".gate-indicator.MARGINAL", "backgroundColor")
        r, g, b = _parse_rgb(color)
        assert r > b, \
            f"MARGINAL indicator should be amber, got {color}"

    def test_gate_text_matches_indicator_color(self, page):
        page.evaluate("""
            const container = document.getElementById('gates-list');
            container.innerHTML = '<div class="gate-row">' +
                '<span class="gate-indicator GO"></span>' +
                '<span class="gate-status-text GO">GO</span></div>';
        """)
        ind_color = _computed(page, ".gate-indicator.GO", "backgroundColor")
        txt_color = _computed(page, ".gate-status-text.GO", "color")
        ir, ig, ib = _parse_rgb(ind_color)
        tr, tg, tb = _parse_rgb(txt_color)
        assert ig > ir and tg > tr, \
            "GO indicator and text should both be green"


# ============================================================
#  Flight score overlay
# ============================================================

class TestFlightScoreOverlay:
    """Verify flight score overlay appearance."""

    def test_flight_score_hidden_by_default(self, page):
        display = _computed(page, "#flight-score-overlay", "display")
        assert display == "none"

    def test_flight_score_visible_when_shown(self, page):
        page.evaluate("""
            _scoreShown = false;
            showFlightScore({
                orbital_accuracy: 85, fuel_efficiency: 72,
                overall: 80, lf_remaining: 258,
                target_alt: 80, actual_apo: 81, actual_pe: 79
            });
        """)
        page.wait_for_timeout(200)
        display = _computed(page, "#flight-score-overlay", "display")
        assert display != "none", "Score overlay should be visible"
        b = _bbox(page, "#flight-score-overlay")
        assert b["w"] > 200 and b["h"] > 100
        page.evaluate("""
            document.getElementById('flight-score-overlay').style.display='none';
            _scoreShown = false;
        """)

    def test_flight_score_grade_displayed(self, page):
        page.evaluate("""
            _scoreShown = false;
            showFlightScore({
                orbital_accuracy: 95, fuel_efficiency: 90,
                overall: 93, lf_remaining: 300,
                target_alt: 80, actual_apo: 80.2, actual_pe: 79.8
            });
        """)
        page.wait_for_timeout(200)
        text = page.evaluate(
            "document.getElementById('flight-score-overlay').textContent")
        assert "EXCELLENT" in text
        assert "93" in text
        page.evaluate("""
            document.getElementById('flight-score-overlay').style.display='none';
            _scoreShown = false;
        """)


# ============================================================
#  Screenshot capture (golden baselines)
# ============================================================

class TestScreenshotBaselines:
    """Capture reference screenshots for visual regression tracking."""

    def test_capture_full_page(self, page):
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        path = os.path.join(SCREENSHOT_DIR, "full_page_1280x720.png")
        page.screenshot(path=path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 10000, \
            "Screenshot should be a non-trivial image"

    def test_capture_topbar(self, page):
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        el = page.query_selector("#topbar")
        path = os.path.join(SCREENSHOT_DIR, "topbar.png")
        el.screenshot(path=path)
        assert os.path.exists(path)

    def test_capture_left_panel(self, page):
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        el = page.query_selector("#left-panel")
        path = os.path.join(SCREENSHOT_DIR, "left_panel.png")
        el.screenshot(path=path)
        assert os.path.exists(path)

    def test_capture_right_panel(self, page):
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        el = page.query_selector("#right-panel")
        path = os.path.join(SCREENSHOT_DIR, "right_panel.png")
        el.screenshot(path=path)
        assert os.path.exists(path)

    def test_capture_advisory_states(self, page):
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        for state in ["NOMINAL", "CAUTION", "WARNING", "ABORT"]:
            page.evaluate(f"""
                document.getElementById('advisory-box').className = '{state}';
                document.getElementById('advisory-level').className = '{state}';
                document.getElementById('advisory-level').textContent = '{state}';
            """)
            page.wait_for_timeout(100)
            el = page.query_selector("#advisory-box")
            path = os.path.join(SCREENSHOT_DIR, f"advisory_{state.lower()}.png")
            el.screenshot(path=path)
            assert os.path.exists(path)
        page.evaluate("""
            document.getElementById('advisory-box').className = 'NOMINAL';
            document.getElementById('advisory-level').className = 'NOMINAL';
            document.getElementById('advisory-level').textContent = 'NOMINAL';
        """)


# ============================================================
#  Scenario panel visual
# ============================================================

class TestScenarioPanelVisual:
    """Verify scenario panel placement and element styling."""

    def test_scenario_panel_inside_left_panel(self, page):
        sc = _bbox(page, "#scenario-panel")
        left = _bbox(page, "#left-panel")
        if sc and left:
            assert sc["x"] >= left["x"]
            assert sc["right"] <= left["right"] + 2

    def test_playback_buttons_visible(self, page):
        page.evaluate(
            "document.getElementById('scenario-panel').classList.add('open')")
        page.wait_for_timeout(400)
        for btn_id in ["sc-play-btn", "sc-pause-btn", "sc-reset-btn"]:
            b = _bbox(page, f"#{btn_id}")
            assert b is not None, f"#{btn_id} must exist"
            assert b["w"] > 20, f"#{btn_id} should have reasonable width"
            assert b["h"] > 15, f"#{btn_id} should have reasonable height"
        page.evaluate(
            "document.getElementById('scenario-panel').classList.remove('open')")

    def test_play_button_green_border(self, page):
        border = page.evaluate(
            "getComputedStyle(document.getElementById('sc-play-btn'))"
            ".borderColor")
        r, g, b = _parse_rgb(border)
        assert g > r and g > b, \
            f"Play button border should be green, got {border}"

    def test_reset_button_red_border(self, page):
        border = page.evaluate(
            "getComputedStyle(document.getElementById('sc-reset-btn'))"
            ".borderColor")
        r, g, b = _parse_rgb(border)
        assert r > g and r > b, \
            f"Reset button border should be red, got {border}"

    def test_mission_name_input_visible(self, page):
        page.evaluate(
            "document.getElementById('scenario-panel').classList.add('open')")
        page.wait_for_timeout(400)
        b = _bbox(page, "#sc-mission-name")
        assert b is not None
        assert b["w"] > 80
        assert b["h"] > 15
        page.evaluate(
            "document.getElementById('scenario-panel').classList.remove('open')")


# ============================================================
#  Event log visual structure
# ============================================================

class TestEventLogVisual:
    """Verify event log area is positioned and styled correctly."""

    def test_event_log_inside_right_panel(self, page):
        log = _bbox(page, "#event-log")
        right = _bbox(page, "#right-panel")
        if log and right:
            assert log["x"] >= right["x"]
            assert log["right"] <= right["right"] + 2

    def test_event_log_section_has_scroll(self, page):
        overflow = _computed(page, "#event-log-section", "overflowY")
        assert overflow in ("auto", "scroll"), \
            f"Event log section should scroll, got overflow-y: {overflow}"


# ============================================================
#  Helpers
# ============================================================

def _parse_rgb(css_color):
    """Parse 'rgb(r, g, b)' or 'rgba(r, g, b, a)' into (r, g, b) ints."""
    css_color = css_color.strip()
    if css_color.startswith("rgba"):
        inner = css_color[5:-1]
    elif css_color.startswith("rgb"):
        inner = css_color[4:-1]
    else:
        raise ValueError(f"Cannot parse color: {css_color}")
    parts = [p.strip() for p in inner.split(",")]
    return int(parts[0]), int(parts[1]), int(parts[2])


def _parse_rgba(css_color):
    """Parse 'rgba(r, g, b, a)' into (r, g, b, a)."""
    css_color = css_color.strip()
    if css_color.startswith("rgba"):
        inner = css_color[5:-1]
    elif css_color.startswith("rgb"):
        inner = css_color[4:-1]
        return int(inner.split(",")[0]), int(inner.split(",")[1]), \
            int(inner.split(",")[2]), 1.0
    else:
        raise ValueError(f"Cannot parse color: {css_color}")
    parts = [p.strip() for p in inner.split(",")]
    return int(parts[0]), int(parts[1]), int(parts[2]), float(parts[3])
