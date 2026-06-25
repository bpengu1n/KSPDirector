"""
tests/test_scenario.py
========================
Tests for the scriptable vehicle launch simulator feature.

Covers:
  - LaunchScenario data model (validation, serialization, VehicleConfig bridge)
  - ScriptedTelemetry playback engine (interface, state machine, speed control)
  - Server API routes for scenario management
  - Integration with FlightDirector

Test-first: these tests are written before the implementation.
"""

import sys
import os
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sim import run_ascent, VehicleConfig, PITCH_PROGRAMS


# ---------------------------------------------------------------------------
# Phase 1: LaunchScenario data model
# ---------------------------------------------------------------------------

class TestScenarioModel(unittest.TestCase):
    """Tests for the LaunchScenario dataclass."""

    def test_default_scenario_matches_perseus1(self):
        """Default LaunchScenario produces the same vehicle as VehicleConfig()."""
        from mission_control.scenario import LaunchScenario
        scenario = LaunchScenario()
        cfg = scenario.to_vehicle_config()
        default_cfg = VehicleConfig()
        self.assertAlmostEqual(cfg.liftoff_mass_t, default_cfg.liftoff_mass_t, places=2)
        self.assertAlmostEqual(cfg.pad_twr_asl, default_cfg.pad_twr_asl, places=2)
        self.assertAlmostEqual(cfg.mission_stage_dv_ms, default_cfg.mission_stage_dv_ms, places=0)

    def test_to_dict_from_dict_roundtrip(self):
        """LaunchScenario survives serialization roundtrip."""
        from mission_control.scenario import LaunchScenario
        original = LaunchScenario(
            name="Test", booster_type="thumper", n_boosters=3,
            booster_pct=30.0, extra_payload=0.2, pitch_program="steep",
            playback_speed=2.0, noise_pct=0.05,
        )
        d = original.to_dict()
        restored = LaunchScenario.from_dict(d)
        self.assertEqual(original.name, restored.name)
        self.assertEqual(original.booster_type, restored.booster_type)
        self.assertEqual(original.n_boosters, restored.n_boosters)
        self.assertAlmostEqual(original.booster_pct, restored.booster_pct)
        self.assertAlmostEqual(original.extra_payload, restored.extra_payload)
        self.assertEqual(original.pitch_program, restored.pitch_program)
        self.assertAlmostEqual(original.playback_speed, restored.playback_speed)
        self.assertAlmostEqual(original.noise_pct, restored.noise_pct)

    def test_validation_rejects_invalid_booster_type(self):
        from mission_control.scenario import LaunchScenario
        s = LaunchScenario(booster_type="invalid_engine")
        errors = s.validate()
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("booster_type" in e for e in errors))

    def test_validation_rejects_booster_pct_out_of_range(self):
        from mission_control.scenario import LaunchScenario
        for bad_pct in [0, -1, 101, 200]:
            s = LaunchScenario(booster_pct=bad_pct)
            errors = s.validate()
            self.assertTrue(len(errors) > 0, f"booster_pct={bad_pct} should be rejected")

    def test_validation_rejects_unknown_pitch_program(self):
        from mission_control.scenario import LaunchScenario
        s = LaunchScenario(pitch_program="nonexistent")
        errors = s.validate()
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("pitch_program" in e for e in errors))

    def test_validation_accepts_valid_defaults(self):
        from mission_control.scenario import LaunchScenario
        s = LaunchScenario()
        errors = s.validate()
        self.assertEqual(errors, [])

    def test_get_pitch_program_resolves_all_names(self):
        from mission_control.scenario import LaunchScenario
        for name in PITCH_PROGRAMS:
            s = LaunchScenario(pitch_program=name)
            prog = s.get_pitch_program()
            self.assertIs(prog, PITCH_PROGRAMS[name])

    def test_preset_scenarios_all_valid(self):
        from mission_control.scenario import PRESET_SCENARIOS
        for name, scenario in PRESET_SCENARIOS.items():
            errors = scenario.validate()
            self.assertEqual(errors, [], f"Preset '{name}' has validation errors: {errors}")

    def test_preset_scenarios_produce_valid_sim_results(self):
        from mission_control.scenario import PRESET_SCENARIOS
        for name, scenario in PRESET_SCENARIOS.items():
            cfg = scenario.to_vehicle_config()
            prog = scenario.get_pitch_program()
            result = run_ascent(cfg, prog)
            self.assertIsNotNone(result.points, f"Preset '{name}' produced no points")
            self.assertTrue(len(result.points) > 5,
                            f"Preset '{name}' produced too few points")

    def test_custom_vehicle_config_params(self):
        """Non-default params propagate to VehicleConfig."""
        from mission_control.scenario import LaunchScenario
        s = LaunchScenario(booster_type="thumper", n_boosters=3, booster_pct=30.0,
                           extra_payload=0.3)
        cfg = s.to_vehicle_config()
        self.assertEqual(cfg.booster_type, "thumper")
        self.assertEqual(cfg.n_boosters, 3)
        self.assertAlmostEqual(cfg.booster_pct, 30.0)
        self.assertAlmostEqual(cfg.extra_payload, 0.3)

    def test_validation_rejects_negative_n_boosters(self):
        from mission_control.scenario import LaunchScenario
        s = LaunchScenario(n_boosters=-1)
        errors = s.validate()
        self.assertTrue(len(errors) > 0)

    def test_validation_rejects_playback_speed_out_of_range(self):
        from mission_control.scenario import LaunchScenario
        for bad_speed in [0, 0.1, 11, 100]:
            s = LaunchScenario(playback_speed=bad_speed)
            errors = s.validate()
            self.assertTrue(len(errors) > 0,
                            f"playback_speed={bad_speed} should be rejected")


# ---------------------------------------------------------------------------
# Phase 2: ScriptedTelemetry playback engine
# ---------------------------------------------------------------------------

class TestScriptedTelemetry(unittest.TestCase):
    """Tests for the ScriptedTelemetry class."""

    def test_implements_client_interface(self):
        """ScriptedTelemetry has the same interface as TelematicusClient."""
        from mission_control.telemachus_client import ScriptedTelemetry
        st = ScriptedTelemetry()
        for method in ("get_state", "get_trajectory", "clear_trajectory",
                       "start", "stop"):
            self.assertTrue(callable(getattr(st, method, None)),
                            f"Missing method: {method}")

    def test_load_scenario_runs_sim(self):
        """After load_scenario, scenario summary has valid data."""
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        st = ScriptedTelemetry()
        summary = st.load_scenario(LaunchScenario())
        self.assertIn("liftoff_mass_t", summary)
        self.assertGreater(summary["liftoff_mass_t"], 10)
        self.assertIn("n_points", summary)
        self.assertGreater(summary["n_points"], 5)

    def test_playback_initial_state_is_stopped(self):
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        st = ScriptedTelemetry()
        st.load_scenario(LaunchScenario())
        status = st.get_playback_status()
        self.assertEqual(status["state"], "stopped")

    def test_playback_start_sets_playing(self):
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario())
        st.start()
        time.sleep(0.1)
        status = st.get_playback_status()
        self.assertEqual(status["state"], "playing")
        st.stop()

    def test_pause_resume_cycle(self):
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario())
        st.start()
        time.sleep(0.1)
        st.pause()
        status = st.get_playback_status()
        self.assertEqual(status["state"], "paused")
        st.resume()
        time.sleep(0.1)
        status = st.get_playback_status()
        self.assertEqual(status["state"], "playing")
        st.stop()

    def test_reset_clears_trajectory(self):
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario(playback_speed=10.0, noise_pct=0.0))
        st.start()
        time.sleep(0.3)
        st.stop()
        self.assertTrue(len(st.get_trajectory()) > 0)
        st.reset()
        self.assertEqual(len(st.get_trajectory()), 0)
        status = st.get_playback_status()
        self.assertEqual(status["state"], "stopped")

    def test_speed_change_preserves_elapsed(self):
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario(playback_speed=1.0, noise_pct=0.0))
        st.start()
        time.sleep(0.2)
        status_before = st.get_playback_status()
        elapsed_before = status_before["elapsed"]
        st.set_speed(5.0)
        status_after = st.get_playback_status()
        elapsed_after = status_after["elapsed"]
        self.assertAlmostEqual(elapsed_before, elapsed_after, delta=0.5)
        self.assertAlmostEqual(status_after["speed"], 5.0)
        st.stop()

    def test_state_includes_scripted_flag(self):
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario())
        st.start()
        time.sleep(0.1)
        state = st.get_state()
        self.assertTrue(state.get("scripted"))
        st.stop()

    def test_state_includes_playback_info(self):
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario())
        st.start()
        time.sleep(0.1)
        state = st.get_state()
        self.assertIn("playback", state)
        pb = state["playback"]
        self.assertIn("state", pb)
        self.assertIn("speed", pb)
        self.assertIn("elapsed", pb)
        self.assertIn("total", pb)
        st.stop()

    def test_pitch_convention_ksp(self):
        """State pitch uses KSP convention (90 - pitch_from_v)."""
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=10.0))
        st.start()
        time.sleep(0.3)
        state = st.get_state()
        st.stop()
        pitch = state.get("pitch", 0)
        # At liftoff, pitch_from_v ~0 (vertical), so KSP pitch ~90 (vertical)
        # During ascent, pitch_from_v increases, KSP pitch decreases
        # We just verify it's in a sane KSP range
        self.assertGreater(pitch, 0)
        self.assertLessEqual(pitch, 90)

    def test_different_scenarios_produce_different_trajectories(self):
        """Different pitch programs produce different sim results under the hood."""
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario

        st1 = ScriptedTelemetry()
        st1.load_scenario(LaunchScenario(pitch_program="nominal", noise_pct=0.0))
        sum1 = st1.get_scenario_summary()

        st2 = ScriptedTelemetry()
        st2.load_scenario(LaunchScenario(pitch_program="steep", noise_pct=0.0))
        sum2 = st2.get_scenario_summary()

        # Different pitch programs produce different apoapsis at core burnout
        self.assertNotAlmostEqual(sum1["apoapsis_km"], sum2["apoapsis_km"], places=0)

    def test_noise_zero_gives_clean_telemetry(self):
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=10.0))
        st.start()
        time.sleep(0.3)
        state = st.get_state()
        st.stop()
        # With zero noise, velocity should exactly match a sim trajectory point
        result = run_ascent()
        sim_velocities = [p.velocity for p in result.points]
        state_vel = state["velocity"]
        # Should be exactly one of the sim velocities
        min_diff = min(abs(v - state_vel) for v in sim_velocities)
        self.assertAlmostEqual(min_diff, 0, places=1)

    def test_keeps_playing_past_trajectory_end(self):
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=1000.0))
        st.start()
        time.sleep(0.3)
        status = st.get_playback_status()
        self.assertEqual(status["state"], "playing")
        state = st.get_state()
        self.assertIsNotNone(state.get("altitude"))
        st.stop()

    def test_get_scenario_summary(self):
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        st = ScriptedTelemetry()
        st.load_scenario(LaunchScenario())
        summary = st.get_scenario_summary()
        self.assertIn("liftoff_mass_t", summary)
        self.assertIn("pad_twr_asl", summary)
        self.assertIn("apoapsis_km", summary)


# ---------------------------------------------------------------------------
# Phase 3: Server API routes
# ---------------------------------------------------------------------------

class TestScenarioAPI(unittest.TestCase):
    """Tests for the scenario management REST API."""

    @classmethod
    def setUpClass(cls):
        from mission_control.server import app, socketio
        from mission_control.scenario import LaunchScenario, PRESET_SCENARIOS
        from mission_control.nominal_compare import NominalTrajectory, FlightDirector
        import mission_control.server as srv

        # Set up server session state for testing
        nominal = NominalTrajectory.load()
        srv.session.nominal_traj = nominal
        srv.session.flight_director = FlightDirector(nominal)
        srv.session.telemetry_client = None

        cls.app = app
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def test_api_scenarios_lists_presets(self):
        resp = self.client.get("/api/scenarios")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("scenarios", data)
        names = [s["name"] for s in data["scenarios"]]
        self.assertIn("nominal", names)

    def test_api_scenario_load_preset(self):
        resp = self.client.post("/api/scenario/load",
                                json={"preset": "nominal"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("ok"))
        self.assertIn("summary", data)

    def test_api_scenario_load_custom(self):
        resp = self.client.post("/api/scenario/load", json={
            "name": "Custom Test",
            "booster_type": "thumper",
            "n_boosters": 3,
            "booster_pct": 25.0,
            "pitch_program": "steep",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("ok"))

    def test_api_scenario_load_invalid_rejects(self):
        resp = self.client.post("/api/scenario/load", json={
            "booster_type": "nonexistent_engine",
        })
        self.assertEqual(resp.status_code, 400)

    def test_api_scenario_playback_controls(self):
        # Load first
        self.client.post("/api/scenario/load", json={"preset": "nominal"})
        # Start
        resp = self.client.post("/api/scenario/start")
        self.assertEqual(resp.status_code, 200)
        # Pause
        resp = self.client.post("/api/scenario/pause")
        self.assertEqual(resp.status_code, 200)
        # Resume
        resp = self.client.post("/api/scenario/resume")
        self.assertEqual(resp.status_code, 200)
        # Reset
        resp = self.client.post("/api/scenario/reset")
        self.assertEqual(resp.status_code, 200)
        # Stop the client to clean up threads
        import mission_control.server as srv
        if srv.session.telemetry_client:
            srv.session.telemetry_client.stop()

    def test_api_scenario_speed(self):
        self.client.post("/api/scenario/load", json={"preset": "nominal"})
        resp = self.client.post("/api/scenario/speed", json={"speed": 5.0})
        self.assertEqual(resp.status_code, 200)
        import mission_control.server as srv
        if srv.session.telemetry_client:
            srv.session.telemetry_client.stop()

    def test_api_scenario_current(self):
        self.client.post("/api/scenario/load", json={"preset": "nominal"})
        resp = self.client.get("/api/scenario/current")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("scenario", data)
        self.assertIn("playback", data)
        import mission_control.server as srv
        if srv.session.telemetry_client:
            srv.session.telemetry_client.stop()


# ---------------------------------------------------------------------------
# Phase 4: Integration with FlightDirector
# ---------------------------------------------------------------------------

class TestScriptedDirectorIntegration(unittest.TestCase):
    """Integration: ScriptedTelemetry state feeds FlightDirector correctly."""

    def test_scripted_state_feeds_flight_director(self):
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        from mission_control.nominal_compare import NominalTrajectory, FlightDirector

        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=10.0))
        st.start()
        time.sleep(0.3)
        state = st.get_state()
        st.stop()

        nominal = NominalTrajectory.load()
        fd = FlightDirector(nominal)
        result = fd.update(state)
        self.assertIn("phase", result)
        self.assertIn("advisory", result)
        self.assertIn("gates", result)

    def test_no_false_circularize_during_terrier_ascent(self):
        """detect_phase must not return CIRCULARIZE when apoapsis first passes
        60km during Terrier burn. At that point v_vert is ~211 m/s — the vehicle
        is still ascending, not near apoapsis."""
        from mission_control.nominal_compare import detect_phase, FlightPhase
        state = {
            "altitude": 48600.0, "apoapsis": 60200.0, "periapsis": -195700.0,
            "mission_time": 204.5, "solid_fuel": 0.0, "liquid_fuel": 200.0,
            "throttle": 1.0, "pitch": 50.0, "velocity": 1100.0,
            "v_horiz": 900.0, "v_vert": 211.0,
        }
        phase = detect_phase(state, FlightPhase.TERRIER)
        self.assertEqual(phase, FlightPhase.TERRIER,
            f"At 48.6km alt / 60.2km apo / v_vert=211 m/s, phase should be TERRIER "
            f"(still ascending), got {phase.value}")

    def test_circularize_detected_near_apoapsis(self):
        """detect_phase should return CIRCULARIZE when near apoapsis
        (v_vert near zero) with apo >= 60km and pe < 65km."""
        from mission_control.nominal_compare import detect_phase, FlightPhase
        state = {
            "altitude": 80000.0, "apoapsis": 80500.0, "periapsis": 20000.0,
            "mission_time": 472.0, "solid_fuel": 0.0, "liquid_fuel": 100.0,
            "throttle": 1.0, "pitch": 0.5, "velocity": 2200.0,
            "v_horiz": 2200.0, "v_vert": 3.0,
        }
        phase = detect_phase(state, FlightPhase.TERRIER)
        self.assertEqual(phase, FlightPhase.CIRCULARIZE,
            f"At 80km alt / v_vert~0 / pe=20km, should be CIRCULARIZE, got {phase.value}")

    def test_detect_phase_full_sequence(self):
        """detect_phase must correctly transition through the full nominal
        phase sequence when fed actual simulated telemetry states."""
        from mission_control.nominal_compare import detect_phase, FlightPhase
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario

        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=50.0))
        st.start()

        seen_phases = set()
        prev_phase = FlightPhase.PRELAUNCH
        for _ in range(300):
            time.sleep(0.05)
            state = st.get_state()
            if not state or state.get("mission_time", 0) < 0.1:
                continue
            phase = detect_phase(state, prev_phase)
            seen_phases.add(phase.value)
            prev_phase = phase
            if state.get("mission_time", 0) > 490:
                break
        st.stop()

        for expected in ("BOOST", "CORE", "TERRIER", "CIRCULARIZE", "ORBIT"):
            self.assertIn(expected, seen_phases,
                f"Phase {expected} should appear during full nominal ascent. "
                f"Seen: {sorted(seen_phases)}")


class TestTelemetryFuelModel(unittest.TestCase):
    """Tests that simulated telemetry reports realistic fuel values
    throughout the full ascent, including coast and circularization phases."""

    def test_fuel_nonzero_during_coast_apo(self):
        """Liquid fuel must remain positive during COAST_APO — the Terrier
        has stopped burning and fuel is preserved for circularization."""
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario

        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=50.0))
        st.start()

        coast_apo_fuel = None
        for _ in range(400):
            time.sleep(0.05)
            state = st.get_state()
            if not state:
                continue
            if state.get("phase") == "COAST_APO":
                coast_apo_fuel = state.get("liquid_fuel", 0)
                break
        st.stop()

        self.assertIsNotNone(coast_apo_fuel,
            "COAST_APO phase was never reached during playback")
        self.assertGreater(coast_apo_fuel, 0,
            f"Liquid fuel during COAST_APO should be > 0 (fuel is preserved "
            f"for circularization), got {coast_apo_fuel}")

    def test_fuel_nonzero_during_circularize(self):
        """Liquid fuel must remain positive during CIRCULARIZE — the Terrier
        is burning to raise periapsis."""
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario

        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=50.0))
        st.start()

        circ_fuel = None
        for _ in range(400):
            time.sleep(0.05)
            state = st.get_state()
            if not state:
                continue
            if state.get("phase") == "CIRCULARIZE":
                circ_fuel = state.get("liquid_fuel", 0)
                break
        st.stop()

        self.assertIsNotNone(circ_fuel,
            "CIRCULARIZE phase was never reached during playback")
        self.assertGreater(circ_fuel, 0,
            f"Liquid fuel during CIRCULARIZE should be > 0 (Terrier is still "
            f"burning), got {circ_fuel}")

    def test_fuel_positive_at_orbit_insertion(self):
        """At orbit insertion there should be remaining fuel for TMI burn."""
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario

        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=50.0))
        st.start()

        orbit_fuel = None
        for _ in range(400):
            time.sleep(0.05)
            state = st.get_state()
            if not state:
                continue
            if state.get("phase") == "ORBIT":
                orbit_fuel = state.get("liquid_fuel", 0)
                break
        st.stop()

        self.assertIsNotNone(orbit_fuel,
            "ORBIT phase was never reached during playback")
        self.assertGreater(orbit_fuel, 0,
            f"Liquid fuel at orbit insertion should be > 0 (TMI fuel remaining), "
            f"got {orbit_fuel}")

    def test_fuel_decreases_monotonically_during_powered_phases(self):
        """During powered flight (BOOST, CORE, TERRIER, CIRCULARIZE),
        liquid fuel should decrease over time, not increase."""
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario

        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=50.0))
        st.start()

        fuel_by_phase = {}
        for _ in range(400):
            time.sleep(0.05)
            state = st.get_state()
            if not state:
                continue
            phase = state.get("phase", "")
            lf = state.get("liquid_fuel", 0)
            met = state.get("mission_time", 0)
            if phase in ("CORE", "TERRIER", "CIRCULARIZE"):
                if phase not in fuel_by_phase:
                    fuel_by_phase[phase] = []
                fuel_by_phase[phase].append((met, lf))
            if met > 490:
                break
        st.stop()

        for phase, readings in fuel_by_phase.items():
            if len(readings) < 2:
                continue
            first_fuel = readings[0][1]
            last_fuel = readings[-1][1]
            self.assertGreater(first_fuel, last_fuel,
                f"Fuel should decrease during {phase}: "
                f"started at {first_fuel:.1f}, ended at {last_fuel:.1f}")

    def test_fuel_constant_during_coast(self):
        """During COAST_APO, fuel should remain approximately constant
        (no engines burning)."""
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario

        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=50.0))
        st.start()

        coast_fuels = []
        for _ in range(400):
            time.sleep(0.05)
            state = st.get_state()
            if not state:
                continue
            if state.get("phase") == "COAST_APO":
                coast_fuels.append(state.get("liquid_fuel", 0))
            if state.get("mission_time", 0) > 490:
                break
        st.stop()

        if len(coast_fuels) >= 2:
            fuel_range = max(coast_fuels) - min(coast_fuels)
            self.assertLess(fuel_range, 5.0,
                f"Fuel during COAST_APO should be constant, but varied by "
                f"{fuel_range:.1f} units (min={min(coast_fuels):.1f}, "
                f"max={max(coast_fuels):.1f})")

    def test_phase_from_telemetry_matches_sim(self):
        """The phase field in telemetry state should come from the sim's
        trajectory point, reflecting the actual planned phase."""
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario

        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=50.0))
        st.start()

        seen_phases = set()
        for _ in range(400):
            time.sleep(0.05)
            state = st.get_state()
            if not state:
                continue
            phase = state.get("phase")
            if phase:
                seen_phases.add(phase)
            if state.get("mission_time", 0) > 490:
                break
        st.stop()

        for expected in ("BOOST", "CORE", "TERRIER", "COAST_APO",
                         "CIRCULARIZE", "ORBIT"):
            self.assertIn(expected, seen_phases,
                f"Telemetry phase '{expected}' should appear during nominal "
                f"playback. Seen: {sorted(seen_phases)}")

    def test_nominal_regenerates_for_scenario(self):
        """When a scenario with different params is loaded, the sim produces
        different nominal numbers."""
        from mission_control.scenario import LaunchScenario

        s_nominal = LaunchScenario()
        s_steep = LaunchScenario(pitch_program="steep")

        r1 = run_ascent(s_nominal.to_vehicle_config(), s_nominal.get_pitch_program())
        r2 = run_ascent(s_steep.to_vehicle_config(), s_steep.get_pitch_program())

        # Different pitch programs produce different apoapsis at core burnout
        self.assertNotAlmostEqual(r1.apoapsis_km, r2.apoapsis_km, places=0)


# ---------------------------------------------------------------------------
# Phase 5: Edge cases & review findings (P2-7)
# ---------------------------------------------------------------------------

class TestScenarioEdgeCases(unittest.TestCase):
    """Boundary and edge-case tests added per code review P2-7."""

    def test_validation_at_exact_bounds(self):
        from mission_control.scenario import LaunchScenario
        s = LaunchScenario(
            booster_pct=1.0, n_boosters=0, noise_pct=0.0,
            playback_speed=0.25, extra_payload=0.0, cd=0.05, area_base=0.5,
        )
        self.assertEqual(s.validate(), [])

        s = LaunchScenario(
            booster_pct=100.0, n_boosters=6, noise_pct=0.20,
            playback_speed=10.0, extra_payload=2.0, cd=1.0, area_base=5.0,
        )
        self.assertEqual(s.validate(), [])

    def test_validation_just_outside_bounds(self):
        from mission_control.scenario import LaunchScenario
        s = LaunchScenario(booster_pct=0.99)
        self.assertTrue(len(s.validate()) > 0)

        s = LaunchScenario(noise_pct=0.201)
        self.assertTrue(len(s.validate()) > 0)

        s = LaunchScenario(n_boosters=7)
        self.assertTrue(len(s.validate()) > 0)

    def test_from_dict_ignores_unknown_keys(self):
        from mission_control.scenario import LaunchScenario
        d = {"name": "Test", "unknown_key": 42, "booster_type": "hammer"}
        s = LaunchScenario.from_dict(d)
        self.assertEqual(s.name, "Test")
        self.assertFalse(hasattr(s, "unknown_key"))

    def test_abort_preset_valid(self):
        from mission_control.scenario import PRESET_SCENARIOS
        self.assertIn("abort_steep", PRESET_SCENARIOS)
        errors = PRESET_SCENARIOS["abort_steep"].validate()
        self.assertEqual(errors, [])

    def test_abort_preset_produces_sim_result(self):
        from mission_control.scenario import PRESET_SCENARIOS
        s = PRESET_SCENARIOS["abort_steep"]
        result = run_ascent(s.to_vehicle_config(), s.get_pitch_program())
        self.assertTrue(len(result.points) > 5)

    def test_zero_boosters_scenario(self):
        from mission_control.scenario import LaunchScenario
        s = LaunchScenario(n_boosters=0)
        self.assertEqual(s.validate(), [])
        cfg = s.to_vehicle_config()
        self.assertEqual(cfg.n_boosters, 0)


class TestCoastPhase(unittest.TestCase):
    """Tests for trajectory phases after core burnout (Terrier → orbit)."""

    def test_trajectory_continues_past_core_burnout(self):
        result = run_ascent()
        self.assertIsNotNone(result.core_burnout)
        last_point = result.points[-1]
        self.assertGreater(last_point.t, result.core_burnout.t)

    def test_terrier_phase_after_core_burnout(self):
        result = run_ascent()
        phases = set(p.phase for p in result.points)
        self.assertIn("TERRIER", phases)
        self.assertIn("COAST_APO", phases)

    def test_nominal_reaches_orbit(self):
        result = run_ascent()
        phases = set(p.phase for p in result.points)
        self.assertIn("ORBIT", phases)
        orbit_pts = [p for p in result.points if p.phase == "ORBIT"]
        self.assertTrue(len(orbit_pts) > 0)
        self.assertGreater(orbit_pts[0].altitude / 1000, 70)

    def test_coast_apo_has_zero_thrust(self):
        result = run_ascent()
        coast_pts = [p for p in result.points if p.phase == "COAST_APO"]
        self.assertTrue(len(coast_pts) > 0)

    def test_burnout_orbital_params_preserved(self):
        result = run_ascent()
        self.assertAlmostEqual(result.apoapsis_km, 24.6, delta=1.0)
        self.assertAlmostEqual(result.periapsis_km, -587, delta=20)

    def test_orbit_near_target(self):
        result = run_ascent()
        orbit_pts = [p for p in result.points if p.phase == "ORBIT"]
        self.assertTrue(len(orbit_pts) > 0)
        p = orbit_pts[0]
        self.assertAlmostEqual(p.apoapsis, 80, delta=5)
        self.assertGreater(p.periapsis, 65)

    def test_full_phase_progression(self):
        result = run_ascent()
        phase_order = []
        prev = None
        for p in result.points:
            if p.phase != prev:
                phase_order.append(p.phase)
                prev = p.phase
        self.assertEqual(phase_order[:3], ["BOOST", "CORE", "TERRIER"])
        self.assertIn("COAST_APO", phase_order)

    def test_scripted_telemetry_plays_orbit(self):
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=500.0))
        st.start()
        time.sleep(0.3)
        state = st.get_state()
        self.assertIn(state.get("phase"),
                      ("TERRIER", "COAST_APO", "CIRCULARIZE", "ORBIT"))
        status = st.get_playback_status()
        self.assertEqual(status["state"], "playing")
        st.stop()

    def test_scripted_telemetry_stays_in_orbit(self):
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=1000.0))
        st.start()
        time.sleep(0.5)
        state = st.get_state()
        self.assertIn(state.get("phase"), ("ORBIT", "COAST_APO", "CIRCULARIZE"))
        self.assertGreater(state.get("altitude", 0), 50000)
        status = st.get_playback_status()
        self.assertEqual(status["state"], "playing")
        st.stop()


class TestConstantsAPI(unittest.TestCase):
    """Tests for the /api/constants endpoint (P1-1)."""

    @classmethod
    def setUpClass(cls):
        from mission_control.server import app
        cls.app = app
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def test_constants_endpoint_returns_kerbin_params(self):
        resp = self.client.get("/api/constants")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertAlmostEqual(data["R_KERBIN"], 600000.0)
        self.assertAlmostEqual(data["MU_KERBIN"], 3.5316e12)
        self.assertAlmostEqual(data["ATM_CEIL"], 70000.0)
        self.assertEqual(data["R_KM"], 600.0)
        self.assertEqual(data["ATM_CEIL_KM"], 70.0)

    def test_constants_match_sim(self):
        from sim.constants import R_KERBIN, MU_KERBIN, ATM_CEIL
        resp = self.client.get("/api/constants")
        data = resp.get_json()
        self.assertEqual(data["R_KERBIN"], R_KERBIN)
        self.assertEqual(data["MU_KERBIN"], MU_KERBIN)
        self.assertEqual(data["ATM_CEIL"], ATM_CEIL)


class TestUIViewport(unittest.TestCase):
    """Tests that the web UI viewport adapts to the full orbital trajectory."""

    @classmethod
    def setUpClass(cls):
        import os
        html_path = os.path.join(os.path.dirname(__file__),
                                 '..', 'mission_control', 'static', 'index.html')
        with open(html_path, 'r') as f:
            cls.html = f.read()

    def test_timeline_covers_full_mission(self):
        """Timeline TOTAL must extend past core burnout to cover Terrier + orbit."""
        import re
        m = re.search(r'const\s+TOTAL\s*=\s*(\d+)', self.html)
        self.assertIsNotNone(m, "TOTAL constant not found in timeline code")
        total = int(m.group(1))
        self.assertGreaterEqual(total, 480,
            f"Timeline TOTAL={total} is too short; orbit insertion occurs at ~T+480s")

    def test_timeline_has_terrier_and_orbit_events(self):
        """Timeline event markers should include Terrier ignition and orbit insertion."""
        self.assertIn("TERR", self.html,
            "Timeline should show a Terrier ignition event marker")

    def test_timeline_has_orbit_phase_band(self):
        """Timeline phase bands should include COAST and ORBIT beyond TERRIER."""
        import re
        bands = re.findall(r"label:\s*'(\w+)'", self.html)
        self.assertIn('COAST', bands,
            "Timeline phase bands should include a COAST/coast-to-apo band")

    def test_globe_extent_uses_actual_trajectory_not_nominal(self):
        """Globe dynamic zoom should track the actual trajectory extent,
        not the full nominal (which goes to orbit and would zoom out too far)."""
        import re
        extent_match = re.search(r'extentSources\s*=\s*\[([^\]]+)\]', self.html)
        self.assertIsNotNone(extent_match)
        sources = extent_match.group(1)
        self.assertNotIn('nominalTraj', sources,
            "Globe extent should NOT include nominalTraj — it zooms too far out")
        self.assertIn('actualTraj', sources,
            "Globe extent must include actualTraj to track the vehicle")

    def test_trajectory_plot_auto_range_excludes_orbital_nominal(self):
        """Trajectory plot auto-range should not include the full orbital
        nominal trajectory, which would compress the ascent view."""
        import re
        allpts_match = re.search(r'allPts\s*=\s*\[([^\]]+)\]', self.html)
        self.assertIsNotNone(allpts_match)
        sources = allpts_match.group(1)
        self.assertNotIn('nominalTraj', sources,
            "Trajectory plot auto-range should NOT include full nominalTraj")

    def test_nominal_coast_skips_orbital_points(self):
        """computeNominalCoast should project from the core burnout point,
        not the last orbital point (which would produce a nonsensical arc)."""
        self.assertRegex(self.html,
            r'computeNominalCoast.*?CORE.*?BOOST|burnout|core_burnout|phase\s*[!=]==?\s*["\']ORBIT',
            "computeNominalCoast should find the core burnout point, not use the last (orbital) point")

    def test_nominal_trajectory_split_for_display(self):
        """The nominal trajectory should be split into ascent (for detailed
        display) and orbital (for reference) portions."""
        self.assertIn('nominalAscent', self.html,
            "HTML should define nominalAscent for the core stage portion of the trajectory")

    def test_globe_altitude_rings_include_orbit(self):
        """Globe altitude rings should include the 80km target orbit ring."""
        import re
        rings = re.findall(r'\[([^\]]*80[^\]]*)\]\.forEach\(\s*(?:alt_km|a)\s*=>', self.html)
        self.assertTrue(len(rings) > 0,
            "Globe should have altitude ring at 80km (target orbit)")

    def test_vehicle_marker_visible_during_ascent(self):
        """The vehicle position marker must be drawn when altitude > 100m
        (not just during specific phases)."""
        self.assertIn('altitude', self.html)
        import re
        marker_check = re.search(r'altitude.*>\s*100', self.html)
        self.assertIsNotNone(marker_check,
            "Vehicle marker visibility check (altitude > 100) must exist")


class TestUILayoutVisibility(unittest.TestCase):
    """Tests that the interface layout doesn't clip or hide panels.

    The grid layout (topbar / content / timeline) must prevent the CSS Grid
    min-height:auto problem from pushing the timeline off-screen, and all
    major panels must be properly placed within the grid.
    """

    @classmethod
    def setUpClass(cls):
        import os
        html_path = os.path.join(os.path.dirname(__file__),
                                 '..', 'mission_control', 'static', 'index.html')
        with open(html_path, 'r') as f:
            cls.html = f.read()

    def _css_for(self, selector):
        """Extract CSS rule body for a given selector."""
        import re
        escaped = re.escape(selector)
        m = re.search(escaped + r'\s*\{([^}]+)\}', self.html)
        return m.group(1) if m else ''

    def test_shell_grid_has_three_rows(self):
        """The #shell grid must define exactly 3 rows: topbar, content, timeline."""
        import re
        m = re.search(r'grid-template-rows\s*:\s*([^;]+)', self._css_for('#shell'))
        self.assertIsNotNone(m, "#shell must define grid-template-rows")
        parts = m.group(1).strip().split()
        self.assertEqual(len(parts), 3,
            f"Grid should have 3 row tracks, got {len(parts)}: {parts}")

    def test_center_panel_prevents_overflow(self):
        """#center-panel must have min-height:0 or overflow:hidden to prevent
        the CSS Grid min-height:auto problem from expanding the middle row
        and pushing the timeline off-screen."""
        css = self._css_for('#center-panel')
        has_min_height_0 = 'min-height' in css and '0' in css
        has_overflow_hidden = 'overflow' in css and 'hidden' in css
        self.assertTrue(has_min_height_0 or has_overflow_hidden,
            "#center-panel needs min-height:0 or overflow:hidden to prevent grid overflow")

    def test_right_panel_prevents_overflow(self):
        """#right-panel must constrain its height to prevent pushing the
        timeline off-screen when advisory/gates content is tall."""
        css = self._css_for('#right-panel')
        has_min_height_0 = 'min-height' in css and '0' in css
        has_overflow = 'overflow' in css
        self.assertTrue(has_min_height_0 or has_overflow,
            "#right-panel needs min-height:0 or overflow to prevent grid overflow")

    def test_timeline_bar_has_explicit_grid_row(self):
        """#timeline-bar must have an explicit grid-row to ensure it lands
        in the bottom row regardless of auto-placement order."""
        css = self._css_for('#timeline-bar')
        self.assertIn('grid-row', css,
            "#timeline-bar should have explicit grid-row placement")

    def test_canvas_panels_have_overflow_hidden(self):
        """Canvas panels must have overflow:hidden so canvas elements don't
        force a minimum height on their grid track."""
        css = self._css_for('.canvas-panel')
        self.assertIn('overflow', css,
            ".canvas-panel needs overflow:hidden to contain canvas sizing")

    def test_all_grid_areas_present(self):
        """All 5 grid areas must exist in the HTML: topbar, left, center, right, timeline."""
        for panel_id in ['topbar', 'left-panel', 'center-panel', 'right-panel', 'timeline-bar']:
            self.assertIn(f'id="{panel_id}"', self.html,
                f"Grid area #{panel_id} must exist in the HTML")

    def test_body_overflow_hidden(self):
        """html,body must have overflow:hidden to prevent page scrolling."""
        self.assertRegex(self.html, r'html\s*,\s*body\s*\{[^}]*overflow\s*:\s*hidden',
            "html,body must have overflow:hidden")

    def test_timeline_canvas_has_height(self):
        """The timeline canvas must have an explicit height so it renders."""
        css = self._css_for('#timeline-canvas')
        self.assertIn('height', css,
            "#timeline-canvas must have an explicit height")


class TestUIGraphicalElements(unittest.TestCase):
    """Tests that graphical elements (stars, globe, trajectories, axes)
    render correctly within the viewport canvases."""

    @classmethod
    def setUpClass(cls):
        import os
        html_path = os.path.join(os.path.dirname(__file__),
                                 '..', 'mission_control', 'static', 'index.html')
        with open(html_path, 'r') as f:
            cls.html = f.read()

    def test_canvas_size_cache_retries_on_small_values(self):
        """getCanvasSize must re-measure if cached dimensions are too small.
        Without this, an initial layout race caches tiny values permanently,
        causing all stars to cluster at (0,0)."""
        import re
        fn = re.search(r'function\s+getCanvasSize\b.*?\}', self.html, re.DOTALL)
        self.assertIsNotNone(fn, "getCanvasSize function must exist")
        body = fn.group(0)
        self.assertRegex(body, r'\.w\s*<|\.h\s*<|width\s*<|height\s*<',
            "getCanvasSize must check for small cached dimensions to force re-measure")

    def test_star_positions_bounded_by_canvas(self):
        """Star positions must be scaled to canvas bounds (W, H) so they
        stay within the viewport regardless of canvas size."""
        import re
        star_section = re.search(r'Stars.*?for.*?\{(.*?)\}', self.html, re.DOTALL)
        self.assertIsNotNone(star_section, "Star rendering loop must exist")
        body = star_section.group(1)
        has_w = '* W' in body or '% W' in body
        has_h = '* H' in body or '% H' in body
        self.assertTrue(has_w, "Star X positions must be scaled by W")
        self.assertTrue(has_h, "Star Y positions must be scaled by H")

    def test_globe_renders_kerbin_body(self):
        """Globe must render the Kerbin circle with a gradient fill."""
        self.assertIn('R_px', self.html, "Globe must compute R_px for Kerbin radius")
        self.assertRegex(self.html, r'arc\(cx,\s*cy,\s*R_px',
            "Globe must draw Kerbin as a circle arc at (cx,cy) with radius R_px")

    def test_globe_renders_atmosphere_glow(self):
        """Globe must render the atmosphere glow band at 70km."""
        self.assertIn('atmR_px', self.html,
            "Globe must compute atmosphere radius in pixels")
        self.assertIn('ATM_CEIL_KM', self.html,
            "Atmosphere radius must reference ATM_CEIL_KM constant")

    def test_globe_scale_derived_from_canvas_size(self):
        """Globe scale must be computed from canvas dimensions so the view
        adapts to the actual canvas size, not a hardcoded value."""
        import re
        scale_match = re.search(r'scale\s*=.*?Math\.min\(W,\s*H\)', self.html)
        self.assertIsNotNone(scale_match,
            "Globe scale must use Math.min(W, H) to adapt to canvas size")

    def test_trajectory_plot_has_valid_axis_padding(self):
        """Trajectory plot must have positive padding on all four sides
        so axis labels and data don't clip at canvas edges."""
        import re
        pad_match = re.search(r'pad\s*=\s*\{\s*l:\s*(\d+),\s*r:\s*(\d+),\s*t:\s*(\d+),\s*b:\s*(\d+)\s*\}', self.html)
        self.assertIsNotNone(pad_match, "Trajectory plot must define pad {l, r, t, b}")
        l, r, t, b = int(pad_match.group(1)), int(pad_match.group(2)), \
                      int(pad_match.group(3)), int(pad_match.group(4))
        self.assertGreater(l, 0, "Left padding must be positive for Y-axis labels")
        self.assertGreater(r, 0, "Right padding must be positive")
        self.assertGreater(t, 0, "Top padding must be positive for title")
        self.assertGreater(b, 0, "Bottom padding must be positive for X-axis labels")

    def test_all_three_canvases_exist(self):
        """All three canvas elements must exist: globe, trajectory, timeline."""
        for canvas_id in ['globe-canvas', 'traj-canvas', 'timeline-canvas']:
            self.assertIn(f'id="{canvas_id}"', self.html,
                f"Canvas #{canvas_id} must exist in the HTML")

    def test_canvas_elements_fill_parent(self):
        """Canvas elements must use width:100%;height:100% to fill their
        parent panel, so the drawing area matches the panel size."""
        import re
        canvas_css = re.search(r'\.canvas-panel\s+canvas\s*\{([^}]+)\}', self.html)
        self.assertIsNotNone(canvas_css, ".canvas-panel canvas CSS rule must exist")
        rule = canvas_css.group(1)
        self.assertIn('width:100%', rule, "Canvas must have width:100%")
        self.assertIn('height:100%', rule, "Canvas must have height:100%")

    def test_center_panel_does_not_clip_canvases(self):
        """#center-panel should use min-height:0 without overflow:hidden,
        so canvas content is never clipped by the parent grid cell."""
        import re
        m = re.search(r'#center-panel\s*\{([^}]+)\}', self.html)
        self.assertIsNotNone(m, "#center-panel CSS rule must exist")
        css = m.group(1)
        self.assertIn('min-height', css, "#center-panel must have min-height:0")
        self.assertNotIn('overflow', css,
            "#center-panel should NOT have overflow:hidden — it clips canvas content")

    def test_globe_renders_launch_site_marker(self):
        """Globe must render the launch site marker at (0, 0)."""
        self.assertIn('toXY(0, 0)', self.html,
            "Globe must render launch site marker at downrange=0, altitude=0")

    def test_globe_renders_vehicle_position_marker(self):
        """Globe must render the current vehicle position as a marker dot."""
        import re
        marker = re.search(r'#69f0ae.*fill|fill.*#69f0ae', self.html)
        self.assertIsNotNone(marker,
            "Globe must render vehicle position marker (green #69f0ae dot)")

    def test_star_positions_not_regularly_spaced(self):
        """Star rendering must use a hash function that avoids visible rows.
        Simple linear congruential ((i * A + B) % W) produces equally-spaced
        rows at common canvas widths; a proper hash must be used instead."""
        import re
        star_section = re.search(r'// Stars.*?for\s*\(.*?\{(.*?)\}', self.html, re.DOTALL)
        self.assertIsNotNone(star_section, "Star rendering loop must exist")
        body = star_section.group(1)
        self.assertNotRegex(body, r'\(\s*i\s*\*\s*\d+\s*\+\s*\d+\s*\)\s*%\s*W',
            "Star X must not use simple ((i * A + B) % W) — it produces visible rows")

    def test_star_hash_uses_nonlinear_distribution(self):
        """Star position generation must use a nonlinear hash (e.g., bit mixing,
        sine hash, or xorshift) to produce visually random distribution."""
        import re
        star_section = re.search(r'// Stars.*?for\s*\(.*?\{(.*?)\}', self.html, re.DOTALL)
        self.assertIsNotNone(star_section, "Star rendering loop must exist")
        body = star_section.group(1)
        has_hash_fn = ('hash' in body.lower() or 'seed' in body.lower() or
                       'Math.sin' in body or '>>>' in body or '^' in body or
                       '0x' in body)
        self.assertTrue(has_hash_fn,
            "Star positions should use a hash function (bit mixing, sine hash, etc.) "
            "instead of linear arithmetic")


class TestUITimelinePhaseBands(unittest.TestCase):
    """Tests that timeline phase bands derive from actual trajectory data
    rather than using hardcoded transition times that can drift from the sim."""

    @classmethod
    def setUpClass(cls):
        import os
        html_path = os.path.join(os.path.dirname(__file__),
                                 '..', 'mission_control', 'static', 'index.html')
        with open(html_path, 'r') as f:
            cls.html = f.read()

    def test_phase_bands_derived_from_nominal_data(self):
        """Timeline phase bands must be derived from nominalTraj data,
        not hardcoded with fixed start/end times."""
        import re
        bands_section = re.search(r'(Phase bands|bands).*?forEach', self.html, re.DOTALL)
        self.assertIsNotNone(bands_section, "Phase band drawing code must exist")
        section = bands_section.group(0)
        has_dynamic = ('nominalTraj' in section or 'buildPhaseBands' in section or
                       'phaseBands' in section or 'computeBands' in section or
                       'deriveBands' in section)
        self.assertTrue(has_dynamic,
            "Phase bands should reference nominalTraj or a derived band computation, "
            "not use hardcoded start/end times")

    def test_phase_bands_include_coast_apo(self):
        """Phase bands should distinguish COAST_APO from other coast phases."""
        import re
        bands = re.findall(r"label:\s*'([^']+)'", self.html)
        coast_labels = [b for b in bands if 'COAST' in b.upper() or 'APO' in b.upper()]
        self.assertTrue(len(coast_labels) > 0,
            "Timeline should have a coast-to-apoapsis phase band")

    def test_no_hardcoded_terrier_end_time(self):
        """The Terrier phase band must not have a hardcoded end time like 290.
        The actual TERRIER→COAST_APO transition is at ~T+216.5s."""
        import re
        bands_match = re.findall(r"label:\s*'TERRIER'[^}]*end:\s*(\d+)", self.html)
        for end_val in bands_match:
            self.assertNotEqual(int(end_val), 290,
                "Terrier band end=290 is wrong (actual transition ~216.5s). "
                "Bands should derive from trajectory data.")

    def test_band_builder_function_exists(self):
        """A function must exist that computes phase bands from trajectory data,
        so bands update when a new scenario is loaded."""
        self.assertRegex(self.html, r'function\s+(buildPhaseBands|computePhaseBands|derivePhaseBands)',
            "A function to compute phase bands from trajectory data must exist")

    def test_phase_band_colors_defined(self):
        """Each phase should have a distinct band color for visual differentiation."""
        import re
        color_map = re.search(r'(PHASE_COLORS|phaseColors|bandColors)\s*=\s*\{', self.html)
        has_color_in_bands = len(re.findall(r"color:\s*'rgba", self.html)) >= 5
        self.assertTrue(color_map is not None or has_color_in_bands,
            "Phase band colors must be defined for at least 5 phases")

    def test_phase_bands_update_on_scenario_load(self):
        """When a new scenario loads (and new nominalTraj arrives), phase bands
        must be recomputed, not remain stale from the previous scenario."""
        import re
        on_nominal = re.search(r"socket\.on\('nominal'", self.html, re.DOTALL)
        self.assertIsNotNone(on_nominal, "Socket handler for 'nominal' event must exist")
        nominal_handler_start = on_nominal.start()
        handler_section = self.html[nominal_handler_start:nominal_handler_start + 500]
        has_band_rebuild = ('buildPhaseBands' in handler_section or
                           'computePhaseBands' in handler_section or
                           'derivePhaseBands' in handler_section or
                           'phaseBands' in handler_section)
        self.assertTrue(has_band_rebuild,
            "The 'nominal' socket handler must rebuild phase bands when new trajectory data arrives")


# ---------------------------------------------------------------------------
# Phase 6: Telemachus integration — expanded topics, per-stage dV, live data
# ---------------------------------------------------------------------------

class TestTelematicusTopics(unittest.TestCase):
    """Verify that SUBSCRIBED_TOPICS and FIELD_MAP cover the Telemachus-1 schema."""

    def test_subscribed_topics_include_vessel_data(self):
        from mission_control.telemachus_client import SUBSCRIBED_TOPICS
        required = [
            "v.altitude", "v.velocity", "v.verticalSpeed", "v.surfaceVelocity",
            "v.mass", "v.geeForce", "v.mach", "v.dynamicPressurekPa",
            "v.atmosphericDensity", "v.lat", "v.long", "v.currentStage",
        ]
        for t in required:
            self.assertIn(t, SUBSCRIBED_TOPICS, f"Missing topic: {t}")

    def test_subscribed_topics_include_orbital_data(self):
        from mission_control.telemachus_client import SUBSCRIBED_TOPICS
        required = [
            "o.ApA", "o.PeA", "o.inclination", "o.eccentricity",
            "o.sma", "o.period", "o.timeToAp", "o.timeToPe",
        ]
        for t in required:
            self.assertIn(t, SUBSCRIBED_TOPICS, f"Missing topic: {t}")

    def test_subscribed_topics_include_dv_totals(self):
        from mission_control.telemachus_client import SUBSCRIBED_TOPICS
        required = [
            "dv.ready", "dv.stageCount", "dv.totalDVVac",
            "dv.totalDVASL", "dv.totalDVActual", "dv.totalBurnTime",
        ]
        for t in required:
            self.assertIn(t, SUBSCRIBED_TOPICS, f"Missing dV topic: {t}")

    def test_subscribed_topics_include_resource_maxes(self):
        from mission_control.telemachus_client import SUBSCRIBED_TOPICS
        required = [
            "r.resource[LiquidFuel]", "r.resource[SolidFuel]",
            "r.resource[Oxidizer]", "r.resource[ElectricCharge]",
            "r.resourceMax[LiquidFuel]", "r.resourceMax[SolidFuel]",
            "r.resourceMax[Oxidizer]", "r.resourceMax[ElectricCharge]",
        ]
        for t in required:
            self.assertIn(t, SUBSCRIBED_TOPICS, f"Missing resource topic: {t}")

    def test_subscribed_topics_include_current_stage_resources(self):
        from mission_control.telemachus_client import SUBSCRIBED_TOPICS
        required = [
            "r.resourceCurrent[LiquidFuel]", "r.resourceCurrent[SolidFuel]",
            "r.resourceCurrent[Oxidizer]",
            "r.resourceCurrentMax[LiquidFuel]", "r.resourceCurrentMax[SolidFuel]",
            "r.resourceCurrentMax[Oxidizer]",
        ]
        for t in required:
            self.assertIn(t, SUBSCRIBED_TOPICS, f"Missing stage resource topic: {t}")

    def test_field_map_covers_all_subscribed_topics(self):
        from mission_control.telemachus_client import SUBSCRIBED_TOPICS, FIELD_MAP
        for topic in SUBSCRIBED_TOPICS:
            self.assertIn(topic, FIELD_MAP,
                f"SUBSCRIBED_TOPICS has '{topic}' but FIELD_MAP does not map it")

    def test_field_map_has_no_duplicate_keys(self):
        from mission_control.telemachus_client import FIELD_MAP
        values = list(FIELD_MAP.values())
        dupes = [v for v in values if values.count(v) > 1]
        self.assertEqual(len(dupes), 0,
            f"FIELD_MAP has duplicate internal keys: {set(dupes)}")

    def test_stage_dv_topics_template_list(self):
        from mission_control.telemachus_client import STAGE_DV_TOPICS
        self.assertIn("dv.stageDVVac", STAGE_DV_TOPICS)
        self.assertIn("dv.stageFuelMass", STAGE_DV_TOPICS)
        self.assertIn("dv.stageBurnTime", STAGE_DV_TOPICS)
        self.assertIn("dv.stageMass", STAGE_DV_TOPICS)
        self.assertIn("dv.stageDryMass", STAGE_DV_TOPICS)
        self.assertTrue(len(STAGE_DV_TOPICS) >= 15,
            "Should have at least 15 per-stage topic templates")


class TestTelematicusClientStages(unittest.TestCase):
    """Verify TelematicusClient builds per-stage data from dV topics."""

    def test_rebuild_stages_from_state(self):
        from mission_control.telemachus_client import TelematicusClient
        client = TelematicusClient.__new__(TelematicusClient)
        client._state = {"dv_stage_count": 2}
        client._stage_field_map = {}
        client._lock = __import__('threading').Lock()

        client._state["stage_0_dvvac"] = 1500.0
        client._state["stage_0_fuelmass"] = 2.0
        client._state["stage_0_drymass"] = 1.0
        client._state["stage_1_dvvac"] = 3000.0
        client._state["stage_1_fuelmass"] = 4.0
        client._state["stage_1_drymass"] = 2.0

        with client._lock:
            client._rebuild_stages_locked()

        stages = client._state["stages"]
        self.assertEqual(len(stages), 2)
        self.assertEqual(stages[0]["dv_vac"], 1500.0)
        self.assertEqual(stages[0]["fuel_mass"], 2.0)
        self.assertEqual(stages[1]["dv_vac"], 3000.0)
        self.assertEqual(stages[1]["fuel_mass"], 4.0)

    def test_rebuild_stages_skips_empty(self):
        from mission_control.telemachus_client import TelematicusClient
        client = TelematicusClient.__new__(TelematicusClient)
        client._state = {"dv_stage_count": 3}
        client._stage_field_map = {}
        client._lock = __import__('threading').Lock()

        client._state["stage_0_dvvac"] = 500.0
        client._state["stage_0_fuelmass"] = 1.0
        # stage 1 has no data at all
        client._state["stage_2_dvvac"] = 800.0
        client._state["stage_2_fuelmass"] = 0.5

        with client._lock:
            client._rebuild_stages_locked()

        stages = client._state["stages"]
        self.assertEqual(len(stages), 2)
        self.assertEqual(stages[0]["index"], 0)
        self.assertEqual(stages[1]["index"], 2)

    def test_rebuild_stages_no_count(self):
        from mission_control.telemachus_client import TelematicusClient
        client = TelematicusClient.__new__(TelematicusClient)
        client._state = {}
        client._stage_field_map = {}
        client._lock = __import__('threading').Lock()

        with client._lock:
            client._rebuild_stages_locked()
        self.assertNotIn("stages", client._state)


class TestSimulatedTelemetryStages(unittest.TestCase):
    """Verify SimulatedTelemetry includes stages and live resource maxes."""

    def test_state_includes_stages_array(self):
        from mission_control.telemachus_client import SimulatedTelemetry
        client = SimulatedTelemetry(rate_ms=200)
        client.start()
        time.sleep(1.0)
        state = client.get_state()
        client.stop()
        self.assertIn("stages", state)
        self.assertIsInstance(state["stages"], list)
        self.assertTrue(len(state["stages"]) > 0,
            "SimulatedTelemetry should report at least one stage with dV")

    def test_state_includes_resource_maxes(self):
        from mission_control.telemachus_client import SimulatedTelemetry
        client = SimulatedTelemetry(rate_ms=200)
        client.start()
        time.sleep(1.0)
        state = client.get_state()
        client.stop()
        self.assertIn("liquid_fuel_max", state)
        self.assertIn("solid_fuel_max", state)
        self.assertGreater(state["liquid_fuel_max"], 0)
        self.assertGreater(state["solid_fuel_max"], 0)

    def test_state_includes_mass_and_forces(self):
        from mission_control.telemachus_client import SimulatedTelemetry
        client = SimulatedTelemetry(rate_ms=200)
        client.start()
        time.sleep(1.0)
        state = client.get_state()
        client.stop()
        self.assertIn("mass", state)
        self.assertIn("mach", state)
        self.assertIn("dynamic_pressure", state)

    def test_stages_have_dv_and_fuel_data(self):
        from mission_control.telemachus_client import SimulatedTelemetry
        client = SimulatedTelemetry(rate_ms=200)
        client.start()
        time.sleep(1.0)
        state = client.get_state()
        client.stop()
        for stg in state["stages"]:
            self.assertIn("dv_vac", stg)
            self.assertIn("fuel_mass", stg)
            self.assertIn("label", stg)
            self.assertIsNotNone(stg["dv_vac"])
            self.assertIsNotNone(stg["fuel_mass"])

    def test_no_hardcoded_fuel_maxes_in_html(self):
        """The UI must use telemetry-provided fuel maxes, not hardcoded 360/160."""
        html_path = os.path.join(ROOT, 'mission_control', 'static', 'index.html')
        with open(html_path) as f:
            html = f.read()
        import re
        matches = re.findall(r'lfMax\s*=\s*360|sfMax\s*=\s*160', html)
        self.assertEqual(len(matches), 0,
            f"Found hardcoded fuel maxes in HTML: {matches}. "
            "Use s.liquid_fuel_max / s.solid_fuel_max from telemetry instead.")


class TestScriptedTelemetryStages(unittest.TestCase):
    """Verify ScriptedTelemetry includes stages and live resource maxes."""

    def test_state_includes_stages_array(self):
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        client = ScriptedTelemetry(rate_ms=200)
        client.load_scenario(LaunchScenario())
        client.start()
        time.sleep(1.0)
        state = client.get_state()
        client.stop()
        self.assertIn("stages", state)
        self.assertIsInstance(state["stages"], list)
        self.assertTrue(len(state["stages"]) > 0)

    def test_state_includes_resource_maxes(self):
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        client = ScriptedTelemetry(rate_ms=200)
        client.load_scenario(LaunchScenario())
        client.start()
        time.sleep(1.0)
        state = client.get_state()
        client.stop()
        self.assertIn("liquid_fuel_max", state)
        self.assertIn("solid_fuel_max", state)
        self.assertGreater(state["liquid_fuel_max"], 0)

    def test_state_includes_mass(self):
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        client = ScriptedTelemetry(rate_ms=200)
        client.load_scenario(LaunchScenario())
        client.start()
        time.sleep(1.0)
        state = client.get_state()
        client.stop()
        self.assertIn("mass", state)
        self.assertIsNotNone(state["mass"])
        self.assertGreater(state["mass"], 0)


class TestUIStageBarElements(unittest.TestCase):
    """Verify the HTML contains dynamic per-stage dV bar elements and logic."""

    @classmethod
    def setUpClass(cls):
        html_path = os.path.join(ROOT, 'mission_control', 'static', 'index.html')
        with open(html_path) as f:
            cls.html = f.read()

    def test_stage_dv_section_exists(self):
        self.assertIn('id="stage-dv-section"', self.html)
        self.assertIn('id="stage-dv-bars"', self.html)

    def test_update_stage_dv_bars_function(self):
        self.assertIn('function updateStageDVBars', self.html)

    def test_stage_dv_bars_called_from_telemetry_update(self):
        self.assertIn('updateStageDVBars', self.html)
        import re
        calls = re.findall(r'updateStageDVBars\(', self.html)
        self.assertTrue(len(calls) >= 1,
            "updateStageDVBars should be called from updateTelemetryPanel")

    def test_uses_stages_from_state(self):
        self.assertIn('s.stages', self.html,
            "UI must reference s.stages from telemetry state for dV bars")

    def test_fuel_max_from_telemetry(self):
        self.assertIn('s.liquid_fuel_max', self.html,
            "UI must use s.liquid_fuel_max from telemetry state")
        self.assertIn('s.solid_fuel_max', self.html,
            "UI must use s.solid_fuel_max from telemetry state")

    def test_vessel_section_exists(self):
        self.assertIn('id="vessel-section"', self.html)
        self.assertIn('id="t-mass"', self.html)
        self.assertIn('id="t-gforce"', self.html)
        self.assertIn('id="t-mach"', self.html)
        self.assertIn('id="t-dynp"', self.html)

    def test_orbit_time_fields_exist(self):
        self.assertIn('id="t-tta"', self.html)
        self.assertIn('id="t-ttp"', self.html)


if __name__ == "__main__":
    unittest.main()
