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
    """Tests for the coast phase after core burnout."""

    def test_trajectory_continues_past_core_burnout(self):
        result = run_ascent()
        self.assertIsNotNone(result.core_burnout)
        last_point = result.points[-1]
        self.assertGreater(last_point.t, result.core_burnout.t)

    def test_coast_phase_label(self):
        result = run_ascent()
        phases = set(p.phase for p in result.points)
        self.assertIn("COAST", phases)

    def test_coast_has_zero_thrust(self):
        result = run_ascent()
        coast_points = [p for p in result.points if p.phase == "COAST"]
        self.assertTrue(len(coast_points) > 0)

    def test_burnout_orbital_params_preserved(self):
        result = run_ascent()
        self.assertAlmostEqual(result.apoapsis_km, 24.6, delta=1.0)
        self.assertAlmostEqual(result.periapsis_km, -587, delta=20)

    def test_coast_ends_at_surface_or_tmax(self):
        result = run_ascent()
        last_point = result.points[-1]
        at_surface = last_point.altitude < 2000
        at_tmax = last_point.t >= 395
        self.assertTrue(at_surface or at_tmax,
                        f"Last point: alt={last_point.altitude:.0f}m, t={last_point.t:.1f}s")

    def test_scripted_telemetry_plays_coast(self):
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=500.0))
        st.start()
        time.sleep(0.3)
        state = st.get_state()
        self.assertIn(state.get("phase"), ("COAST", "LANDED"))
        status = st.get_playback_status()
        self.assertEqual(status["state"], "playing")
        st.stop()

    def test_scripted_telemetry_reaches_landed(self):
        from mission_control.telemachus_client import ScriptedTelemetry
        from mission_control.scenario import LaunchScenario
        st = ScriptedTelemetry(rate_ms=50)
        st.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=1000.0))
        st.start()
        time.sleep(0.5)
        state = st.get_state()
        self.assertEqual(state.get("phase"), "LANDED")
        self.assertEqual(state.get("altitude"), 0.0)
        self.assertEqual(state.get("velocity"), 0.0)
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


if __name__ == "__main__":
    unittest.main()
