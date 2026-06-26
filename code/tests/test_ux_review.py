"""Tests for UX survey review implementations.

Test naming follows the project convention: test_uxNN_description where NN
traces to the UX_REVIEW.md item.
"""

import re

import pytest

from mission_control.nominal_compare import (
    FlightPhase, assess_gates, generate_advisory, FlightDirector,
    NominalTrajectory,
)


# ---------------------------------------------------------------------------
# UX-FC01a: Booster SEP confirmation gate
# ---------------------------------------------------------------------------

class TestBoosterSepGate:
    """FC-01 requested an explicit BOOSTER SEP go/no-go gate."""

    def test_ux_fc01a_gate_present_in_output(self, telemetry_state):
        """assess_gates returns a BOOSTER SEP gate."""
        state = telemetry_state(sf=0, alt=3000, met=26, apo=5000)
        gates = assess_gates(state, FlightPhase.CORE)
        gate_names = [g.phase for g in gates]
        assert "BOOSTER SEP" in gate_names

    def test_ux_fc01a_not_yet_during_boost(self, telemetry_state):
        """BOOSTER SEP gate is NOT-YET while SRBs still burning."""
        state = telemetry_state(sf=80, alt=1500, met=10, apo=3000)
        gates = assess_gates(state, FlightPhase.BOOST)
        sep_gate = [g for g in gates if g.phase == "BOOSTER SEP"][0]
        assert sep_gate.status == "NOT-YET"

    def test_ux_fc01a_go_nominal_sep(self, telemetry_state):
        """BOOSTER SEP gate is GO after nominal separation (~T+25s, ~2.9 km, ~253 m/s)."""
        state = telemetry_state(sf=0, alt=2890, met=26, apo=5000, vel=253)
        gates = assess_gates(state, FlightPhase.CORE)
        sep_gate = [g for g in gates if g.phase == "BOOSTER SEP"][0]
        assert sep_gate.status == "GO"

    def test_ux_fc01a_marginal_early_sep(self, telemetry_state):
        """BOOSTER SEP gate is MARGINAL if sep happened very early (low alt/vel)."""
        state = telemetry_state(sf=0, alt=800, met=12, apo=1500, vel=80)
        gates = assess_gates(state, FlightPhase.CORE)
        sep_gate = [g for g in gates if g.phase == "BOOSTER SEP"][0]
        assert sep_gate.status == "MARGINAL"

    def test_ux_fc01a_go_in_terrier_phase(self, telemetry_state):
        """BOOSTER SEP gate remains GO in later phases."""
        state = telemetry_state(sf=0, alt=18000, met=80, apo=50000, vel=500)
        gates = assess_gates(state, FlightPhase.TERRIER)
        sep_gate = [g for g in gates if g.phase == "BOOSTER SEP"][0]
        assert sep_gate.status == "GO"

    def test_ux_fc01a_five_gates_total(self, telemetry_state):
        """Gate count is now 5 (BOOSTER SEP + original 4)."""
        state = telemetry_state(sf=0, alt=3000, met=26, apo=5000)
        gates = assess_gates(state, FlightPhase.CORE)
        assert len(gates) == 5

    def test_ux_fc01a_prelaunch_not_yet(self, telemetry_state):
        """BOOSTER SEP gate is NOT-YET during PRELAUNCH."""
        state = telemetry_state(sf=160, alt=5, met=0, apo=0)
        gates = assess_gates(state, FlightPhase.PRELAUNCH)
        sep_gate = [g for g in gates if g.phase == "BOOSTER SEP"][0]
        assert sep_gate.status == "NOT-YET"


# ---------------------------------------------------------------------------
# UX-FC01b: Nominal pitch reference in advisory text
# ---------------------------------------------------------------------------

class TestAdvisoryPitchReference:
    """FC-01 requested nominal pitch value in advisory text."""

    def test_ux_fc01b_steep_advisory_shows_nominal(self, telemetry_state):
        """When flying steep, advisory includes nominal pitch reference."""
        state = telemetry_state(alt=18000, apo=35000, pe=-200000, met=80,
                                lf=300, pitch=30)  # 30 deg KSP = very steep
        nominal = {
            "pitch_from_vertical": 45.0,  # nominal 45 deg from vert
            "altitude_km": 18.0,
            "apoapsis_km": 35.0,
        }
        adv = generate_advisory(state, FlightPhase.TERRIER, nominal=nominal)
        assert "NOM" in adv.action or "nom" in adv.action.lower(), \
            f"Advisory should reference nominal pitch, got: {adv.action}"

    def test_ux_fc01b_shallow_advisory_shows_nominal(self, telemetry_state):
        """When flying shallow, advisory includes nominal pitch reference."""
        state = telemetry_state(alt=18000, apo=35000, pe=-200000, met=80,
                                lf=300, pitch=80)  # 80 deg KSP = very shallow
        nominal = {
            "pitch_from_vertical": 45.0,
            "altitude_km": 18.0,
            "apoapsis_km": 35.0,
        }
        adv = generate_advisory(state, FlightPhase.TERRIER, nominal=nominal)
        assert "NOM" in adv.action or "nom" in adv.action.lower(), \
            f"Advisory should reference nominal pitch, got: {adv.action}"

    def test_ux_fc01b_nominal_flight_no_pitch_ref(self, telemetry_state):
        """When flying on-nominal, no pitch correction reference needed."""
        state = telemetry_state(alt=25000, apo=75000, pe=55000, met=120,
                                lf=200, pitch=45)
        nominal = {
            "pitch_from_vertical": 45.0,
            "altitude_km": 25.0,
            "apoapsis_km": 75.0,
        }
        adv = generate_advisory(state, FlightPhase.TERRIER, nominal=nominal)
        assert adv.level == "NOMINAL"


# ---------------------------------------------------------------------------
# UX-P3-11: Consumables trending (burn rate + time-to-depletion)
# ---------------------------------------------------------------------------

class TestConsumablesTrending:
    """FC-01 requested burn rate and time-to-depletion display."""

    def test_ux_p311_flight_director_tracks_burn_rate(self):
        """FlightDirector output includes fuel_burn_rate field."""
        nominal = NominalTrajectory.load()
        fd = FlightDirector(nominal)
        state1 = {
            "altitude": 15000, "apoapsis": 25000, "periapsis": -587000,
            "mission_time": 63, "solid_fuel": 0, "liquid_fuel": 360,
            "throttle": 1.0, "pitch": 50, "velocity": 631,
            "v_horiz": 481, "v_vert": 408,
        }
        fd.update(state1)

        state2 = dict(state1)
        state2["mission_time"] = 64
        state2["liquid_fuel"] = 355
        state2["altitude"] = 15500
        state2["apoapsis"] = 26000
        result = fd.update(state2)

        assert "consumables" in result
        assert "burn_rate" in result["consumables"]
        assert result["consumables"]["burn_rate"] > 0

    def test_ux_p311_time_to_depletion_computed(self):
        """FlightDirector output includes time_to_depletion."""
        nominal = NominalTrajectory.load()
        fd = FlightDirector(nominal)
        state1 = {
            "altitude": 15000, "apoapsis": 25000, "periapsis": -587000,
            "mission_time": 63, "solid_fuel": 0, "liquid_fuel": 360,
            "throttle": 1.0, "pitch": 50, "velocity": 631,
            "v_horiz": 481, "v_vert": 408,
        }
        fd.update(state1)

        state2 = dict(state1)
        state2["mission_time"] = 64
        state2["liquid_fuel"] = 355
        state2["altitude"] = 15500
        state2["apoapsis"] = 26000
        result = fd.update(state2)

        ttd = result["consumables"]["time_to_depletion"]
        assert ttd is not None
        assert ttd > 0
        # EMA-smoothed burn rate after one sample: alpha=0.3, raw=5.0 u/s
        # smoothed = 0.3 * 5.0 + 0.7 * 0.0 = 1.5 u/s
        # TTD = 355 / 1.5 ≈ 236.7s
        assert ttd == pytest.approx(355 / 1.5, rel=0.05)

    def test_ux_p311_zero_burn_rate_when_coasting(self):
        """Burn rate is 0 and time_to_depletion is None when not burning."""
        nominal = NominalTrajectory.load()
        fd = FlightDirector(nominal)
        state1 = {
            "altitude": 80000, "apoapsis": 80000, "periapsis": 75000,
            "mission_time": 300, "solid_fuel": 0, "liquid_fuel": 200,
            "throttle": 0.0, "pitch": 0, "velocity": 2200,
            "v_horiz": 2200, "v_vert": 0,
        }
        fd.update(state1)

        state2 = dict(state1)
        state2["mission_time"] = 301
        result = fd.update(state2)

        assert result["consumables"]["burn_rate"] == pytest.approx(0, abs=0.01)
        assert result["consumables"]["time_to_depletion"] is None

    def test_ux_p311_no_consumables_on_first_update(self):
        """First update has no previous state — consumables should use defaults."""
        nominal = NominalTrajectory.load()
        fd = FlightDirector(nominal)
        state = {
            "altitude": 100, "apoapsis": 0, "periapsis": 0,
            "mission_time": 1, "solid_fuel": 160, "liquid_fuel": 360,
            "throttle": 1.0, "pitch": 90, "velocity": 50,
            "v_horiz": 0, "v_vert": 50,
        }
        result = fd.update(state)
        assert "consumables" in result
        assert result["consumables"]["burn_rate"] == pytest.approx(0, abs=0.01)


# ---------------------------------------------------------------------------
# UX-P3-14: Flight efficiency scoring
# ---------------------------------------------------------------------------

class TestFlightEfficiencyScoring:
    """Post-flight scoring comparing actual vs nominal performance."""

    def test_ux_p314_score_available_in_orbit(self):
        """FlightDirector provides flight_score when ORBIT phase reached."""
        nominal = NominalTrajectory.load()
        fd = FlightDirector(nominal)

        # Simulate progression to orbit
        states = [
            {"altitude": 100, "apoapsis": 0, "periapsis": 0,
             "mission_time": 1, "solid_fuel": 160, "liquid_fuel": 360,
             "throttle": 1.0, "pitch": 88, "velocity": 50,
             "v_horiz": 0, "v_vert": 50},
            {"altitude": 80000, "apoapsis": 80000, "periapsis": 78000,
             "mission_time": 300, "solid_fuel": 0, "liquid_fuel": 150,
             "throttle": 0.0, "pitch": 0, "velocity": 2250,
             "v_horiz": 2250, "v_vert": 5},
        ]
        for s in states:
            result = fd.update(s)

        assert "flight_score" in result
        score = result["flight_score"]
        assert "overall" in score
        assert 0 <= score["overall"] <= 100

    def test_ux_p314_score_components(self):
        """Flight score includes fuel_efficiency, orbital_accuracy, gravity_loss components."""
        nominal = NominalTrajectory.load()
        fd = FlightDirector(nominal)

        state = {
            "altitude": 80000, "apoapsis": 80000, "periapsis": 78000,
            "mission_time": 300, "solid_fuel": 0, "liquid_fuel": 150,
            "throttle": 0.0, "pitch": 0, "velocity": 2250,
            "v_horiz": 2250, "v_vert": 5,
        }
        result = fd.update(state)
        score = result["flight_score"]

        assert "fuel_efficiency" in score
        assert "orbital_accuracy" in score

    def test_ux_p314_no_score_before_orbit(self):
        """No flight score during ascent phases."""
        nominal = NominalTrajectory.load()
        fd = FlightDirector(nominal)

        state = {
            "altitude": 15000, "apoapsis": 25000, "periapsis": -587000,
            "mission_time": 63, "solid_fuel": 0, "liquid_fuel": 360,
            "throttle": 1.0, "pitch": 50, "velocity": 631,
            "v_horiz": 481, "v_vert": 408,
        }
        result = fd.update(state)
        assert result.get("flight_score") is None


# ---------------------------------------------------------------------------
# UX-P1-6: Audio/visual alert escalation (test alert level transitions)
# ---------------------------------------------------------------------------

class TestAlertEscalation:
    """Verify advisory level transitions that drive audio/visual alerts."""

    def test_ux_p16_nominal_to_caution_transition(self, telemetry_state):
        """Advisory escalates from NOMINAL to CAUTION when pitch deviates."""
        state = telemetry_state(alt=18000, apo=35000, pe=-200000, met=80,
                                lf=300, pitch=30)
        nominal = {"pitch_from_vertical": 45.0}
        adv = generate_advisory(state, FlightPhase.TERRIER, nominal=nominal)
        assert adv.level == "CAUTION"

    def test_ux_p16_warning_on_low_apo(self, telemetry_state):
        """Advisory escalates to WARNING when apoapsis dangerously low."""
        state = telemetry_state(alt=16000, apo=28000, pe=-300000, met=80,
                                lf=200, pitch=50)
        adv = generate_advisory(state, FlightPhase.TERRIER)
        assert adv.level == "WARNING"

    def test_ux_p16_abort_fires_when_criteria_met(self, telemetry_state):
        """ABORT fires when fuel critical + apoapsis stalled + pe deeply negative."""
        state = telemetry_state(alt=20000, apo=35000, pe=-150000, met=120,
                                lf=80, pitch=30)
        adv = generate_advisory(state, FlightPhase.TERRIER)
        assert adv.level == "ABORT"


# ---------------------------------------------------------------------------
# UX-P2-8: OBS Overlay mode (CSS + URL param tests via source inspection)
# ---------------------------------------------------------------------------

class TestOverlayMode:
    """Verify overlay mode CSS and URL param support are present in index.html."""

    @pytest.fixture
    def html_source(self):
        import os
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "mission_control", "static", "index.html"
        )
        with open(html_path) as f:
            return f.read()

    def test_ux_p28_overlay_css_exists(self, html_source):
        """Overlay mode CSS class is defined."""
        assert "body.overlay-mode" in html_source

    def test_ux_p28_overlay_url_param_parsed(self, html_source):
        """URL param 'overlay' is parsed in JavaScript."""
        assert "overlay" in html_source
        assert "_overlayPanel" in html_source

    def test_ux_p28_fontscale_param_parsed(self, html_source):
        """URL param 'fontscale' is parsed for presentation mode."""
        assert "_fontScale" in html_source

    def test_ux_p28_overlay_visible_class(self, html_source):
        """overlay-visible class is applied to target panel."""
        assert "overlay-visible" in html_source


# ---------------------------------------------------------------------------
# UX-P2-10: Pre-launch checklist (source inspection)
# ---------------------------------------------------------------------------

class TestPrelaunchChecklist:
    """Verify pre-launch checklist elements exist in index.html."""

    @pytest.fixture
    def html_source(self):
        import os
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "mission_control", "static", "index.html"
        )
        with open(html_path) as f:
            return f.read()

    def test_ux_p210_checklist_overlay_exists(self, html_source):
        """Pre-launch overlay div exists."""
        assert 'id="prelaunch-overlay"' in html_source

    def test_ux_p210_checklist_items(self, html_source):
        """Default checklist items are present."""
        for item in ["TELEMETRY LINK", "VEHICLE CONFIG", "FLIGHT RULES",
                      "SAS ENABLE", "THROTTLE SET"]:
            assert item in html_source

    def test_ux_p210_countdown_display(self, html_source):
        """Countdown display element exists."""
        assert 'id="prelaunch-countdown"' in html_source

    def test_ux_p210_dismiss_function(self, html_source):
        """dismissPrelaunch function is defined."""
        assert "function dismissPrelaunch" in html_source

    def test_ux_p210_auto_dismiss_on_launch(self, html_source):
        """Auto-dismiss triggered when flight detected."""
        assert "checkAutoLaunch" in html_source


# ---------------------------------------------------------------------------
# UX-P3-13: Custom branding (source inspection)
# ---------------------------------------------------------------------------

class TestCustomBranding:
    """Verify custom branding support — persistent setting via localStorage."""

    @pytest.fixture
    def html_source(self):
        import os
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "mission_control", "static", "index.html"
        )
        with open(html_path) as f:
            return f.read()

    def test_ux_p313_localstorage_persistence(self, html_source):
        """Mission name is stored in localStorage for persistence."""
        assert "localStorage.getItem" in html_source
        assert "localStorage.setItem" in html_source
        assert "mc_mission_name" in html_source

    def test_ux_p313_mission_name_applied(self, html_source):
        """Mission name is applied to topbar element."""
        assert "mission-name" in html_source
        assert "MISSION CONTROL" in html_source

    def test_ux_p313_settings_input_exists(self, html_source):
        """Scenario panel has a mission name input field."""
        assert "sc-mission-name" in html_source
        assert "setMissionName" in html_source

    def test_ux_p313_apply_mission_name_function(self, html_source):
        """applyMissionName function updates UI elements."""
        assert "function applyMissionName" in html_source
        assert "function setMissionName" in html_source

    def test_ux_p313_url_param_override(self, html_source):
        """URL param still works as a one-time override that saves to localStorage."""
        assert "_missionUrlParam" in html_source

    def test_ux_p313_server_config_fallback(self, html_source):
        """Falls back to server /api/config for mission name."""
        assert "/api/config" in html_source

    def test_ux_p313_server_mission_name_arg(self):
        """Server accepts --mission-name CLI argument."""
        from mission_control.server import build_argparser
        parser = build_argparser()
        args = parser.parse_args(["--mission-name", "APOLLO 11"])
        assert args.mission_name == "APOLLO 11"

    def test_ux_p313_houston_api_exposes_mission(self, html_source):
        """Houston API exposes mission name."""
        assert "mission:" in html_source
        assert "_missionName" in html_source


# ---------------------------------------------------------------------------
# UX-KSP-06/07: Mission event log (source inspection)
# ---------------------------------------------------------------------------

class TestMissionEventLog:
    """Verify mission event log elements exist."""

    @pytest.fixture
    def html_source(self):
        import os
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "mission_control", "static", "index.html"
        )
        with open(html_path) as f:
            return f.read()

    def test_ux_ksp06_event_log_section(self, html_source):
        """Event log section exists in HTML."""
        assert 'id="event-log-section"' in html_source
        assert 'id="event-log"' in html_source

    def test_ux_ksp06_log_event_function(self, html_source):
        """logEvent function is defined."""
        assert "function logEvent" in html_source

    def test_ux_ksp06_track_events_function(self, html_source):
        """trackEvents function tracks phase, gate, and advisory changes."""
        assert "function trackEvents" in html_source

    def test_ux_ksp07_export_function(self, html_source):
        """exportEventLog function creates downloadable text."""
        assert "function exportEventLog" in html_source
        assert "mission_event_log.txt" in html_source

    def test_ux_ksp06_houston_api_exposes_log(self, html_source):
        """Houston API exposes getEventLog."""
        assert "getEventLog" in html_source

    def test_ux_ksp06_houston_api_exposes_score(self, html_source):
        """Houston API exposes getFlightScore."""
        assert "getFlightScore" in html_source


# ---------------------------------------------------------------------------
# Server-side: /api/config endpoint
# ---------------------------------------------------------------------------

class TestServerConfig:
    """Verify /api/config endpoint exists."""

    def test_ux_config_route_exists(self):
        """Server has /api/config route."""
        from mission_control.server import app
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert "/api/config" in rules
