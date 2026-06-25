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
import sys
import threading
import time
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

CHROMIUM_PATH = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(port):
    from mission_control.server import app, socketio
    socketio.run(app, host="127.0.0.1", port=port,
                 allow_unsafe_werkzeug=True, log_output=False)


@unittest.skipUnless(HAS_PLAYWRIGHT, "playwright not installed")
@unittest.skipUnless(os.path.exists(CHROMIUM_PATH), "Chromium not found")
class TestUIPlaywright(unittest.TestCase):
    """P-TEST-06: DOM-based tests replacing regex HTML inspection."""

    @classmethod
    def setUpClass(cls):
        cls._port = _free_port()
        cls._server_thread = threading.Thread(
            target=_start_server, args=(cls._port,), daemon=True)
        cls._server_thread.start()

        for _ in range(40):
            try:
                with socket.create_connection(("127.0.0.1", cls._port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.25)

        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(
            executable_path=CHROMIUM_PATH, headless=True)
        cls._page = cls._browser.new_page()
        cls._page.goto(f"http://127.0.0.1:{cls._port}/", wait_until="networkidle")

    @classmethod
    def tearDownClass(cls):
        cls._page.close()
        cls._browser.close()
        cls._pw.stop()

    # --- Grid layout ---

    def test_shell_exists_with_grid_display(self):
        shell = self._page.query_selector("#shell")
        self.assertIsNotNone(shell, "#shell element must exist")
        display = self._page.evaluate(
            "getComputedStyle(document.getElementById('shell')).display")
        self.assertEqual(display, "grid")

    def test_shell_has_three_grid_rows(self):
        rows = self._page.evaluate(
            "getComputedStyle(document.getElementById('shell')).gridTemplateRows")
        parts = rows.strip().split()
        self.assertEqual(len(parts), 3,
                         f"#shell should have 3 grid rows, got {len(parts)}: {rows}")

    def test_all_grid_panels_exist(self):
        for panel_id in ["topbar", "left-panel", "center-panel",
                         "right-panel", "timeline-bar"]:
            el = self._page.query_selector(f"#{panel_id}")
            self.assertIsNotNone(el, f"#{panel_id} must exist")

    def test_center_panel_has_min_height_zero(self):
        mh = self._page.evaluate(
            "getComputedStyle(document.getElementById('center-panel')).minHeight")
        self.assertEqual(mh, "0px",
                         f"#center-panel min-height should be 0px, got {mh}")

    def test_right_panel_has_min_height_zero(self):
        mh = self._page.evaluate(
            "getComputedStyle(document.getElementById('right-panel')).minHeight")
        self.assertEqual(mh, "0px",
                         f"#right-panel min-height should be 0px, got {mh}")

    def test_body_overflow_hidden(self):
        overflow = self._page.evaluate(
            "getComputedStyle(document.body).overflow")
        self.assertEqual(overflow, "hidden")

    def test_timeline_bar_grid_row_placement(self):
        row = self._page.evaluate(
            "getComputedStyle(document.getElementById('timeline-bar')).gridRow")
        self.assertIn("3", row,
                      f"#timeline-bar should be in grid row 3, got {row}")

    # --- Canvas elements ---

    def test_all_canvases_exist(self):
        for canvas_id in ["globe-canvas", "traj-canvas", "timeline-canvas"]:
            el = self._page.query_selector(f"#{canvas_id}")
            self.assertIsNotNone(el, f"#{canvas_id} must exist")

    def test_canvases_have_nonzero_dimensions(self):
        for canvas_id in ["globe-canvas", "traj-canvas", "timeline-canvas"]:
            box = self._page.evaluate(f"""(() => {{
                const c = document.getElementById('{canvas_id}');
                const r = c.getBoundingClientRect();
                return {{w: r.width, h: r.height}};
            }})()""")
            self.assertGreater(box["w"], 0,
                               f"#{canvas_id} width should be > 0")
            self.assertGreater(box["h"], 0,
                               f"#{canvas_id} height should be > 0")

    def test_timeline_canvas_has_explicit_height(self):
        h = self._page.evaluate(
            "getComputedStyle(document.getElementById('timeline-canvas')).height")
        self.assertNotEqual(h, "0px",
                            f"#timeline-canvas computed height should not be 0px")

    # --- Telemetry panel elements ---

    def test_telemetry_value_elements_exist(self):
        required_ids = ["t-alt", "t-vel", "t-vvert", "t-vhoriz",
                        "t-apo", "t-pe", "met-display",
                        "t-mass", "t-gforce", "t-mach", "t-dynp",
                        "t-tta", "t-ttp"]
        for eid in required_ids:
            el = self._page.query_selector(f"#{eid}")
            self.assertIsNotNone(el, f"Telemetry field #{eid} must exist")

    def test_stage_dv_section_exists(self):
        self.assertIsNotNone(self._page.query_selector("#stage-dv-section"))
        self.assertIsNotNone(self._page.query_selector("#stage-dv-bars"))

    def test_vessel_section_exists(self):
        self.assertIsNotNone(self._page.query_selector("#vessel-section"))

    # --- JavaScript functions ---

    def test_esc_function_exists(self):
        result = self._page.evaluate("typeof esc")
        self.assertEqual(result, "function", "esc() must be defined")

    def test_esc_escapes_html(self):
        result = self._page.evaluate("esc('<script>alert(1)</script>')")
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;", result)

    def test_update_stage_dv_bars_exists(self):
        result = self._page.evaluate("typeof updateStageDVBars")
        self.assertEqual(result, "function")

    def test_get_canvas_size_exists(self):
        result = self._page.evaluate("typeof getCanvasSize")
        self.assertEqual(result, "function")

    def test_project_ballistic_arc_exists(self):
        result = self._page.evaluate("typeof projectBallisticArc")
        self.assertEqual(result, "function")

    def test_build_phase_bands_exists(self):
        result = self._page.evaluate("typeof buildPhaseBands")
        self.assertEqual(result, "function")

    def test_mission_control_api_object(self):
        result = self._page.evaluate("typeof window.MissionControl")
        self.assertEqual(result, "object",
                         "window.MissionControl API object must exist")
        methods = self._page.evaluate("""
            Object.keys(window.MissionControl).filter(
                k => typeof window.MissionControl[k] === 'function')
        """)
        self.assertIn("loadScenario", methods)
        self.assertIn("controlPlayback", methods)

    # --- Scenario panel ---

    def test_scenario_panel_exists(self):
        panel = self._page.query_selector("#scenario-panel")
        self.assertIsNotNone(panel, "Scenario control panel must exist")

    def test_scenario_preset_dropdown(self):
        select = self._page.query_selector("#sc-preset")
        self.assertIsNotNone(select, "Preset scenario dropdown must exist")
        self._page.evaluate("fetchPresets()")
        self._page.wait_for_timeout(500)
        options = self._page.evaluate("""
            Array.from(document.getElementById('sc-preset').options)
                 .map(o => o.value)
        """)
        self.assertIn("nominal", options)
        self.assertIn("steep_ascent", options)

    def test_playback_controls_exist(self):
        for btn_id in ["sc-play-btn", "sc-pause-btn", "sc-reset-btn"]:
            el = self._page.query_selector(f"#{btn_id}")
            self.assertIsNotNone(el, f"Playback button #{btn_id} must exist")

    # --- Advisory / Gates ---

    def test_advisory_panel_exists(self):
        el = self._page.query_selector("#advisory-action")
        self.assertIsNotNone(el, "Advisory action element must exist")

    def test_gates_container_exists(self):
        el = self._page.query_selector("#gates-list")
        self.assertIsNotNone(el, "Gates container must exist")

    # --- Constants loaded ---

    def test_kerbin_constants_loaded(self):
        r_km = self._page.evaluate("typeof R_KM !== 'undefined' ? R_KM : null")
        self.assertIsNotNone(r_km, "R_KM (Kerbin radius) must be defined")
        self.assertAlmostEqual(r_km, 600.0, places=0)

    # --- CSS custom properties ---

    def test_css_custom_properties_defined(self):
        props = ["--mc-bg", "--mc-panel", "--mc-accent", "--mc-text",
                 "--mc-green", "--mc-red"]
        for prop in props:
            val = self._page.evaluate(
                f"getComputedStyle(document.documentElement).getPropertyValue('{prop}').trim()")
            self.assertTrue(len(val) > 0,
                            f"CSS custom property {prop} must be defined")


if __name__ == "__main__":
    unittest.main()
