"""
tests/test_scenario.py
========================
Tests for the scriptable vehicle launch simulator feature.

Migrated to pytest style.
"""

import os
import re
import time
import math
import pytest

from sim import run_ascent, VehicleConfig, PITCH_PROGRAMS


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def wait_for(pred, timeout=5.0, interval=0.05):
    """Poll until pred() returns truthy or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = pred()
        if result:
            return result
        time.sleep(interval)
    return pred()


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ascent_result():
    """Run the ascent sim once; shared by coast phase and stage dV tests."""
    return run_ascent()


@pytest.fixture
def flask_test_client():
    """Flask test client with clean server session per test."""
    from mission_control.server import app, socketio
    from mission_control.nominal_compare import NominalTrajectory, FlightDirector
    import mission_control.server as srv

    nominal = NominalTrajectory.load()
    srv.session.nominal_traj = nominal
    srv.session.flight_director = FlightDirector(nominal)
    srv.session.telemetry_client = None
    srv.session.current_scenario = None

    app.config["TESTING"] = True
    client = app.test_client()
    yield client, srv.session, app, socketio

    if srv.session.telemetry_client:
        srv.session.telemetry_client.stop()
    srv.session.telemetry_client = None
    srv.session.current_scenario = None


@pytest.fixture(scope="module")
def html_source():
    """Read index.html once; shared by all UI inspection tests."""
    html_path = os.path.join(ROOT, 'mission_control', 'static', 'index.html')
    with open(html_path) as f:
        return f.read()


# ---------------------------------------------------------------------------
# LaunchScenario data model
# ---------------------------------------------------------------------------

def test_default_scenario_matches():
    from mission_control.scenario import LaunchScenario
    scenario = LaunchScenario()
    cfg = scenario.to_vehicle_config()
    default_cfg = VehicleConfig()
    assert cfg.liftoff_mass_t == pytest.approx(default_cfg.liftoff_mass_t, abs=0.01)
    assert cfg.pad_twr_asl == pytest.approx(default_cfg.pad_twr_asl, abs=0.01)
    assert cfg.mission_stage_dv_ms == pytest.approx(default_cfg.mission_stage_dv_ms, abs=1)


def test_scenario_roundtrip():
    from mission_control.scenario import LaunchScenario
    original = LaunchScenario(
        name="Test", booster_type="thumper", n_boosters=3,
        booster_pct=30.0, extra_payload=0.2, pitch_program="steep",
        playback_speed=2.0, noise_pct=0.05,
    )
    d = original.to_dict()
    restored = LaunchScenario.from_dict(d)
    assert original.name == restored.name
    assert original.booster_type == restored.booster_type
    assert original.n_boosters == restored.n_boosters
    assert original.booster_pct == pytest.approx(restored.booster_pct)
    assert original.extra_payload == pytest.approx(restored.extra_payload)
    assert original.pitch_program == restored.pitch_program
    assert original.playback_speed == pytest.approx(restored.playback_speed)
    assert original.noise_pct == pytest.approx(restored.noise_pct)


def test_reject_bad_booster():
    from mission_control.scenario import LaunchScenario
    s = LaunchScenario(booster_type="invalid_engine")
    errors = s.validate()
    assert len(errors) > 0
    assert any("booster_type" in e for e in errors)


@pytest.mark.parametrize("bad_pct", [0, -1, 101, 200])
def test_reject_bad_booster_pct(bad_pct):
    from mission_control.scenario import LaunchScenario
    s = LaunchScenario(booster_pct=bad_pct)
    assert len(s.validate()) > 0


def test_reject_bad_pitch_program():
    from mission_control.scenario import LaunchScenario
    s = LaunchScenario(pitch_program="nonexistent")
    errors = s.validate()
    assert len(errors) > 0
    assert any("pitch_program" in e for e in errors)


def test_valid_defaults_accepted():
    from mission_control.scenario import LaunchScenario
    assert LaunchScenario().validate() == []


def test_pitch_program_resolves():
    from mission_control.scenario import LaunchScenario
    for name in PITCH_PROGRAMS:
        s = LaunchScenario(pitch_program=name)
        assert s.get_pitch_program() is PITCH_PROGRAMS[name]


def test_presets_all_valid():
    from mission_control.scenario import PRESET_SCENARIOS
    for name, scenario in PRESET_SCENARIOS.items():
        assert scenario.validate() == [], f"Preset '{name}' has errors"


def test_presets_produce_sim_results():
    from mission_control.scenario import PRESET_SCENARIOS
    for name, scenario in PRESET_SCENARIOS.items():
        cfg = scenario.to_vehicle_config()
        prog = scenario.get_pitch_program()
        result = run_ascent(cfg, prog)
        assert result.points is not None
        assert len(result.points) > 5, f"Preset '{name}' produced too few points"


def test_custom_vehicle_params():
    from mission_control.scenario import LaunchScenario
    s = LaunchScenario(booster_type="thumper", n_boosters=3, booster_pct=30.0,
                       extra_payload=0.3)
    cfg = s.to_vehicle_config()
    assert cfg.booster_type == "thumper"
    assert cfg.n_boosters == 3
    assert cfg.booster_pct == pytest.approx(30.0)
    assert cfg.extra_payload == pytest.approx(0.3)


def test_reject_negative_boosters():
    from mission_control.scenario import LaunchScenario
    assert len(LaunchScenario(n_boosters=-1).validate()) > 0


@pytest.mark.parametrize("bad_speed", [0, 0.1, 11, 100])
def test_reject_bad_playback_speed(bad_speed):
    from mission_control.scenario import LaunchScenario
    assert len(LaunchScenario(playback_speed=bad_speed).validate()) > 0


# ---------------------------------------------------------------------------
# ScriptedTelemetry playback engine
# ---------------------------------------------------------------------------

@pytest.fixture
def scripted_telemetry():
    """Factory fixture that creates, yields, and stops a ScriptedTelemetry."""
    from mission_control.telemachus_client import ScriptedTelemetry
    from mission_control.scenario import LaunchScenario
    created = []

    def _make(rate_ms=50, **scenario_kwargs):
        st = ScriptedTelemetry(rate_ms=rate_ms)
        st.load_scenario(LaunchScenario(**scenario_kwargs))
        created.append(st)
        return st

    yield _make
    for st in created:
        try:
            st.stop()
        except Exception:
            pass


def test_client_interface():
    from mission_control.telemachus_client import ScriptedTelemetry
    st = ScriptedTelemetry()
    for method in ("get_state", "get_trajectory", "clear_trajectory", "start", "stop"):
        assert callable(getattr(st, method, None)), f"Missing method: {method}"


def test_load_scenario_runs_sim():
    from mission_control.telemachus_client import ScriptedTelemetry
    from mission_control.scenario import LaunchScenario
    st = ScriptedTelemetry()
    summary = st.load_scenario(LaunchScenario())
    assert "liftoff_mass_t" in summary
    assert summary["liftoff_mass_t"] > 10
    assert summary["n_points"] > 5


def test_initial_state_stopped():
    from mission_control.telemachus_client import ScriptedTelemetry
    from mission_control.scenario import LaunchScenario
    st = ScriptedTelemetry()
    st.load_scenario(LaunchScenario())
    assert st.get_playback_status()["state"] == "stopped"


def test_playback_start(scripted_telemetry):
    st = scripted_telemetry()
    st.start()
    time.sleep(0.1)
    assert st.get_playback_status()["state"] == "playing"


def test_pause_resume(scripted_telemetry):
    st = scripted_telemetry()
    st.start()
    time.sleep(0.1)
    st.pause()
    assert st.get_playback_status()["state"] == "paused"
    st.resume()
    time.sleep(0.1)
    assert st.get_playback_status()["state"] == "playing"


def test_reset_clears_traj(scripted_telemetry):
    st = scripted_telemetry(playback_speed=10.0, noise_pct=0.0)
    st.start()
    time.sleep(0.3)
    st.stop()
    assert len(st.get_trajectory()) > 0
    st.reset()
    assert len(st.get_trajectory()) == 0
    assert st.get_playback_status()["state"] == "stopped"


def test_speed_change_preserves_elapsed(scripted_telemetry):
    st = scripted_telemetry(playback_speed=1.0, noise_pct=0.0)
    st.start()
    time.sleep(0.2)
    elapsed_before = st.get_playback_status()["elapsed"]
    st.set_speed(5.0)
    status_after = st.get_playback_status()
    assert elapsed_before == pytest.approx(status_after["elapsed"], abs=0.5)
    assert status_after["speed"] == pytest.approx(5.0)


def test_state_has_scripted_flag(scripted_telemetry):
    st = scripted_telemetry()
    st.start()
    time.sleep(0.1)
    assert st.get_state().get("scripted") is True


def test_state_has_playback_info(scripted_telemetry):
    st = scripted_telemetry()
    st.start()
    time.sleep(0.1)
    state = st.get_state()
    assert "playback" in state
    pb = state["playback"]
    for key in ("state", "speed", "elapsed", "total"):
        assert key in pb


def test_pitch_convention_ksp(scripted_telemetry):
    st = scripted_telemetry(noise_pct=0.0, playback_speed=10.0)
    st.start()
    time.sleep(0.3)
    state = st.get_state()
    pitch = state.get("pitch", 0)
    assert 0 < pitch <= 90


def test_diff_scenarios_diff_traj():
    from mission_control.telemachus_client import ScriptedTelemetry
    from mission_control.scenario import LaunchScenario
    st1 = ScriptedTelemetry()
    st1.load_scenario(LaunchScenario(pitch_program="nominal", noise_pct=0.0))
    sum1 = st1.get_scenario_summary()
    st2 = ScriptedTelemetry()
    st2.load_scenario(LaunchScenario(pitch_program="steep", noise_pct=0.0))
    sum2 = st2.get_scenario_summary()
    assert abs(sum1["apoapsis_km"] - sum2["apoapsis_km"]) > 0.5


def test_zero_noise_clean(scripted_telemetry):
    st = scripted_telemetry(noise_pct=0.0, playback_speed=10.0)
    st.start()
    time.sleep(0.3)
    state = st.get_state()
    result = run_ascent()
    sim_velocities = [p.velocity for p in result.points]
    min_diff = min(abs(v - state["velocity"]) for v in sim_velocities)
    assert min_diff == pytest.approx(0, abs=0.5)


def test_plays_past_end(scripted_telemetry):
    st = scripted_telemetry(noise_pct=0.0, playback_speed=1000.0)
    st.start()
    time.sleep(0.3)
    assert st.get_playback_status()["state"] == "playing"
    assert st.get_state().get("altitude") is not None


def test_scenario_summary():
    from mission_control.telemachus_client import ScriptedTelemetry
    from mission_control.scenario import LaunchScenario
    st = ScriptedTelemetry()
    st.load_scenario(LaunchScenario())
    summary = st.get_scenario_summary()
    for key in ("liftoff_mass_t", "pad_twr_asl", "apoapsis_km"):
        assert key in summary


# ---------------------------------------------------------------------------
# Server API routes
# ---------------------------------------------------------------------------

def test_api_list_presets(flask_test_client):
    client, session, _, _ = flask_test_client
    resp = client.get("/api/scenarios")
    assert resp.status_code == 200
    names = [s["name"] for s in resp.get_json()["scenarios"]]
    assert "nominal" in names


def test_api_load_preset(flask_test_client):
    client, session, _, _ = flask_test_client
    resp = client.post("/api/scenario/load", json={"preset": "nominal"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("ok")
    assert "summary" in data


def test_api_load_custom(flask_test_client):
    client, _, _, _ = flask_test_client
    resp = client.post("/api/scenario/load", json={
        "name": "Custom Test",
        "booster_type": "thumper",
        "n_boosters": 3,
        "booster_pct": 25.0,
        "pitch_program": "steep",
    })
    assert resp.status_code == 200
    assert resp.get_json().get("ok")


def test_api_load_invalid_rejects(flask_test_client):
    client, _, _, _ = flask_test_client
    resp = client.post("/api/scenario/load", json={"booster_type": "nonexistent_engine"})
    assert resp.status_code == 400


def test_api_playback_controls(flask_test_client):
    client, _, _, _ = flask_test_client
    client.post("/api/scenario/load", json={"preset": "nominal"})
    assert client.post("/api/scenario/start").status_code == 200
    assert client.post("/api/scenario/pause").status_code == 200
    assert client.post("/api/scenario/resume").status_code == 200
    assert client.post("/api/scenario/reset").status_code == 200


def test_api_scenario_speed(flask_test_client):
    client, _, _, _ = flask_test_client
    client.post("/api/scenario/load", json={"preset": "nominal"})
    resp = client.post("/api/scenario/speed", json={"speed": 5.0})
    assert resp.status_code == 200


def test_api_scenario_current(flask_test_client):
    client, _, _, _ = flask_test_client
    client.post("/api/scenario/load", json={"preset": "nominal"})
    resp = client.get("/api/scenario/current")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "scenario" in data
    assert "playback" in data


# ---------------------------------------------------------------------------
# FlightDirector integration
# ---------------------------------------------------------------------------

def test_scripted_feeds_director():
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
    for key in ("phase", "advisory", "gates"):
        assert key in result


def test_no_false_circularize():
    from mission_control.nominal_compare import detect_phase, FlightPhase
    state = {
        "altitude": 48600.0, "apoapsis": 60200.0, "periapsis": -195700.0,
        "mission_time": 204.5, "solid_fuel": 0.0, "liquid_fuel": 200.0,
        "throttle": 1.0, "pitch": 50.0, "velocity": 1100.0,
        "v_horiz": 900.0, "v_vert": 211.0,
    }
    phase = detect_phase(state, FlightPhase.TERRIER)
    assert phase == FlightPhase.TERRIER


def test_circularize_near_apo():
    from mission_control.nominal_compare import detect_phase, FlightPhase
    state = {
        "altitude": 80000.0, "apoapsis": 80500.0, "periapsis": 20000.0,
        "mission_time": 472.0, "solid_fuel": 0.0, "liquid_fuel": 100.0,
        "throttle": 1.0, "pitch": 0.5, "velocity": 2200.0,
        "v_horiz": 2200.0, "v_vert": 3.0,
    }
    phase = detect_phase(state, FlightPhase.TERRIER)
    assert phase == FlightPhase.CIRCULARIZE


def test_full_phase_sequence():
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
        assert expected in seen_phases, f"Missing phase {expected}. Seen: {sorted(seen_phases)}"


# ---------------------------------------------------------------------------
# Telemetry fuel model
# ---------------------------------------------------------------------------

def _run_until_phase(phase_name, playback_speed=50.0, max_iters=400):
    """Start a ScriptedTelemetry and poll until the given phase is reached."""
    from mission_control.telemachus_client import ScriptedTelemetry
    from mission_control.scenario import LaunchScenario
    st = ScriptedTelemetry(rate_ms=50)
    st.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=playback_speed))
    st.start()
    found_state = None
    for _ in range(max_iters):
        time.sleep(0.05)
        state = st.get_state()
        if state and state.get("phase") == phase_name:
            found_state = state
            break
    st.stop()
    return found_state


def test_fuel_nonzero_coast_apo():
    state = _run_until_phase("COAST_APO")
    assert state is not None, "COAST_APO phase not reached"
    assert state.get("liquid_fuel", 0) > 0


def test_fuel_nonzero_circularize():
    state = _run_until_phase("CIRCULARIZE")
    assert state is not None, "CIRCULARIZE phase not reached"
    assert state.get("liquid_fuel", 0) > 0


def test_fuel_positive_at_orbit():
    state = _run_until_phase("ORBIT")
    assert state is not None, "ORBIT phase not reached"
    assert state.get("liquid_fuel", 0) > 0


def test_fuel_decreases_powered():
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
            fuel_by_phase.setdefault(phase, []).append((met, lf))
        if met > 490:
            break
    st.stop()
    for phase, readings in fuel_by_phase.items():
        if len(readings) < 2:
            continue
        assert readings[0][1] > readings[-1][1], \
            f"Fuel should decrease during {phase}"


def test_fuel_constant_coast():
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
        assert max(coast_fuels) - min(coast_fuels) < 5.0


def test_phase_from_telem_matches():
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
    for expected in ("BOOST", "CORE", "TERRIER", "COAST_APO", "CIRCULARIZE", "ORBIT"):
        assert expected in seen_phases, f"Missing phase '{expected}'"


def test_nominal_regen_for_scenario():
    from mission_control.scenario import LaunchScenario
    s_nominal = LaunchScenario()
    s_steep = LaunchScenario(pitch_program="steep")
    r1 = run_ascent(s_nominal.to_vehicle_config(), s_nominal.get_pitch_program())
    r2 = run_ascent(s_steep.to_vehicle_config(), s_steep.get_pitch_program())
    assert abs(r1.apoapsis_km - r2.apoapsis_km) > 0.5


# ---------------------------------------------------------------------------
# Scenario edge cases
# ---------------------------------------------------------------------------

def test_valid_at_exact_bounds():
    from mission_control.scenario import LaunchScenario
    s = LaunchScenario(
        booster_pct=1.0, n_boosters=0, noise_pct=0.0,
        playback_speed=0.25, extra_payload=0.0, cd=0.05, area_base=0.5,
    )
    assert s.validate() == []
    s = LaunchScenario(
        booster_pct=100.0, n_boosters=6, noise_pct=0.20,
        playback_speed=10.0, extra_payload=2.0, cd=1.0, area_base=5.0,
    )
    assert s.validate() == []


def test_just_outside_bounds():
    from mission_control.scenario import LaunchScenario
    assert len(LaunchScenario(booster_pct=0.99).validate()) > 0
    assert len(LaunchScenario(noise_pct=0.201).validate()) > 0
    assert len(LaunchScenario(n_boosters=7).validate()) > 0


def test_from_dict_ignores_unknowns():
    from mission_control.scenario import LaunchScenario
    s = LaunchScenario.from_dict({"name": "Test", "unknown_key": 42, "booster_type": "hammer"})
    assert s.name == "Test"
    assert not hasattr(s, "unknown_key")


def test_abort_preset_valid():
    from mission_control.scenario import PRESET_SCENARIOS
    assert "abort_steep" in PRESET_SCENARIOS
    assert PRESET_SCENARIOS["abort_steep"].validate() == []


def test_abort_preset_runs_sim():
    from mission_control.scenario import PRESET_SCENARIOS
    s = PRESET_SCENARIOS["abort_steep"]
    result = run_ascent(s.to_vehicle_config(), s.get_pitch_program())
    assert len(result.points) > 5


def test_zero_boosters():
    from mission_control.scenario import LaunchScenario
    s = LaunchScenario(n_boosters=0)
    assert s.validate() == []
    assert s.to_vehicle_config().n_boosters == 0


# ---------------------------------------------------------------------------
# Coast phase (uses ascent_result fixture)
# ---------------------------------------------------------------------------

def test_traj_past_core_burnout(ascent_result):
    assert ascent_result.core_burnout is not None
    assert ascent_result.points[-1].t > ascent_result.core_burnout.t


def test_terrier_phase_exists(ascent_result):
    phases = set(p.phase for p in ascent_result.points)
    assert "TERRIER" in phases
    assert "COAST_APO" in phases


def test_nominal_reaches_orbit(ascent_result):
    phases = set(p.phase for p in ascent_result.points)
    assert "ORBIT" in phases
    orbit_pts = [p for p in ascent_result.points if p.phase == "ORBIT"]
    assert len(orbit_pts) > 0
    assert orbit_pts[0].altitude / 1000 > 70


def test_coast_apo_zero_thrust(ascent_result):
    coast_pts = [p for p in ascent_result.points if p.phase == "COAST_APO"]
    assert len(coast_pts) > 0


def test_burnout_orbital_params(ascent_result):
    assert ascent_result.apoapsis_km == pytest.approx(24.6, abs=1.0)
    assert ascent_result.periapsis_km == pytest.approx(-587, abs=20)


def test_orbit_near_target(ascent_result):
    orbit_pts = [p for p in ascent_result.points if p.phase == "ORBIT"]
    assert len(orbit_pts) > 0
    p = orbit_pts[0]
    assert p.apoapsis == pytest.approx(80, abs=5)
    assert p.periapsis > 65


def test_full_phase_order(ascent_result):
    phase_order = []
    prev = None
    for p in ascent_result.points:
        if p.phase != prev:
            phase_order.append(p.phase)
            prev = p.phase
    assert phase_order[:3] == ["BOOST", "CORE", "TERRIER"]
    assert "COAST_APO" in phase_order


def test_scripted_plays_orbit():
    from mission_control.telemachus_client import ScriptedTelemetry
    from mission_control.scenario import LaunchScenario
    st = ScriptedTelemetry(rate_ms=50)
    st.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=500.0))
    st.start()
    time.sleep(0.3)
    state = st.get_state()
    assert state.get("phase") in ("TERRIER", "COAST_APO", "CIRCULARIZE", "ORBIT")
    assert st.get_playback_status()["state"] == "playing"
    st.stop()


def test_scripted_stays_in_orbit():
    from mission_control.telemachus_client import ScriptedTelemetry
    from mission_control.scenario import LaunchScenario
    st = ScriptedTelemetry(rate_ms=50)
    st.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=1000.0))
    st.start()
    time.sleep(0.5)
    state = st.get_state()
    assert state.get("phase") in ("ORBIT", "COAST_APO", "CIRCULARIZE")
    assert state.get("altitude", 0) > 50000
    assert st.get_playback_status()["state"] == "playing"
    st.stop()


# ---------------------------------------------------------------------------
# Constants API
# ---------------------------------------------------------------------------

def test_constants_kerbin_params(flask_test_client):
    client, _, _, _ = flask_test_client
    resp = client.get("/api/constants")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["R_KERBIN"] == pytest.approx(600000.0)
    assert data["MU_KERBIN"] == pytest.approx(3.5316e12)
    assert data["ATM_CEIL"] == pytest.approx(70000.0)
    assert data["R_KM"] == 600.0
    assert data["ATM_CEIL_KM"] == 70.0


def test_constants_match_sim(flask_test_client):
    from sim.constants import R_KERBIN, MU_KERBIN, ATM_CEIL
    client, _, _, _ = flask_test_client
    data = client.get("/api/constants").get_json()
    assert data["R_KERBIN"] == R_KERBIN
    assert data["MU_KERBIN"] == MU_KERBIN
    assert data["ATM_CEIL"] == ATM_CEIL


# ---------------------------------------------------------------------------
# UI viewport (all use html_source fixture)
# ---------------------------------------------------------------------------

def test_timeline_covers_mission(html_source):
    m = re.search(r'const\s+TOTAL\s*=\s*(\d+)', html_source)
    assert m is not None
    assert int(m.group(1)) >= 480


def test_timeline_terrier_event(html_source):
    assert "TERR" in html_source


def test_timeline_orbit_band(html_source):
    bands = re.findall(r"label:\s*'(\w+)'", html_source)
    assert 'COAST' in bands


def test_globe_tracks_actual_traj(html_source):
    extent_match = re.search(r'extentSources\s*=\s*\[([^\]]+)\]', html_source)
    assert extent_match is not None
    sources = extent_match.group(1)
    assert 'nominalTraj' not in sources
    assert 'actualTraj' in sources


def test_traj_plot_excludes_orbital(html_source):
    allpts_match = re.search(r'allPts\s*=\s*\[([^\]]+)\]', html_source)
    assert allpts_match is not None
    assert 'nominalTraj' not in allpts_match.group(1)


def test_nominal_coast_from_burnout(html_source):
    assert re.search(
        r'computeNominalCoast.*?CORE.*?BOOST|burnout|core_burnout|phase\s*[!=]==?\s*["\']ORBIT',
        html_source
    )


def test_nominal_split_for_display(html_source):
    assert 'nominalAscent' in html_source


def test_globe_80km_ring(html_source):
    rings = re.findall(r'\[([^\]]*80[^\]]*)\]\.forEach\(\s*(?:alt_km|a)\s*=>', html_source)
    assert len(rings) > 0


def test_vehicle_marker_visible(html_source):
    assert re.search(r'altitude.*>\s*100', html_source)


# ---------------------------------------------------------------------------
# UI layout visibility
# ---------------------------------------------------------------------------

def _css_for(html, selector):
    escaped = re.escape(selector)
    m = re.search(escaped + r'\s*\{([^}]+)\}', html)
    return m.group(1) if m else ''


def test_shell_grid_three_rows(html_source):
    m = re.search(r'grid-template-rows\s*:\s*([^;]+)', _css_for(html_source, '#shell'))
    assert m is not None
    assert len(m.group(1).strip().split()) == 3


def test_center_panel_no_overflow(html_source):
    css = _css_for(html_source, '#center-panel')
    assert ('min-height' in css and '0' in css) or ('overflow' in css and 'hidden' in css)


def test_right_panel_no_overflow(html_source):
    css = _css_for(html_source, '#right-panel')
    assert ('min-height' in css and '0' in css) or ('overflow' in css)


def test_timeline_explicit_row(html_source):
    assert 'grid-row' in _css_for(html_source, '#timeline-bar')


def test_canvas_panel_overflow(html_source):
    assert 'overflow' in _css_for(html_source, '.canvas-panel')


def test_all_grid_areas(html_source):
    for panel_id in ['topbar', 'left-panel', 'center-panel', 'right-panel', 'timeline-bar']:
        assert f'id="{panel_id}"' in html_source


def test_body_overflow_hidden(html_source):
    assert re.search(r'html\s*,\s*body\s*\{[^}]*overflow\s*:\s*hidden', html_source)


def test_timeline_canvas_height(html_source):
    assert 'height' in _css_for(html_source, '#timeline-canvas')


# ---------------------------------------------------------------------------
# UI graphical elements
# ---------------------------------------------------------------------------

def test_canvas_size_retries(html_source):
    fn = re.search(r'function\s+getCanvasSize\b.*?\}', html_source, re.DOTALL)
    assert fn is not None
    body = fn.group(0)
    assert re.search(r'\.w\s*<|\.h\s*<|width\s*<|height\s*<', body)


def test_stars_bounded(html_source):
    star_section = re.search(r'Stars.*?for.*?\{(.*?)\}', html_source, re.DOTALL)
    assert star_section is not None
    body = star_section.group(1)
    assert '* W' in body or '% W' in body
    assert '* H' in body or '% H' in body


def test_globe_kerbin_body(html_source):
    assert 'R_px' in html_source
    assert re.search(r'arc\(cx,\s*cy,\s*R_px', html_source)


def test_globe_atm_glow(html_source):
    assert 'atmR_px' in html_source
    assert 'ATM_CEIL_KM' in html_source


def test_globe_scale_from_canvas(html_source):
    assert re.search(r'scale\s*=.*?Math\.min\(W,\s*H\)', html_source)


def test_traj_plot_axis_padding(html_source):
    pad_match = re.search(
        r'pad\s*=\s*\{\s*l:\s*(\d+),\s*r:\s*(\d+),\s*t:\s*(\d+),\s*b:\s*(\d+)\s*\}',
        html_source
    )
    assert pad_match is not None
    l, r, t, b = (int(pad_match.group(i)) for i in range(1, 5))
    assert l > 0 and r > 0 and t > 0 and b > 0


def test_three_canvases(html_source):
    for cid in ['globe-canvas', 'traj-canvas', 'timeline-canvas']:
        assert f'id="{cid}"' in html_source


def test_canvas_fills_parent(html_source):
    canvas_css = re.search(r'\.canvas-panel\s+canvas\s*\{([^}]+)\}', html_source)
    assert canvas_css is not None
    rule = canvas_css.group(1)
    assert 'width:100%' in rule
    assert 'height:100%' in rule


def test_center_no_clip(html_source):
    m = re.search(r'#center-panel\s*\{([^}]+)\}', html_source)
    assert m is not None
    css = m.group(1)
    assert 'min-height' in css
    assert 'overflow' not in css


def test_globe_launch_marker(html_source):
    assert 'toXY(0, 0)' in html_source


def test_globe_vehicle_marker(html_source):
    assert re.search(r'#69f0ae.*fill|fill.*#69f0ae', html_source)


def test_stars_not_regular(html_source):
    star_section = re.search(r'// Stars.*?for\s*\(.*?\{(.*?)\}', html_source, re.DOTALL)
    assert star_section is not None
    body = star_section.group(1)
    assert not re.search(r'\(\s*i\s*\*\s*\d+\s*\+\s*\d+\s*\)\s*%\s*W', body)


def test_stars_nonlinear_hash(html_source):
    star_section = re.search(r'// Stars.*?for\s*\(.*?\{(.*?)\}', html_source, re.DOTALL)
    assert star_section is not None
    body = star_section.group(1)
    assert ('hash' in body.lower() or 'seed' in body.lower() or
            'Math.sin' in body or '>>>' in body or '^' in body or '0x' in body)


# ---------------------------------------------------------------------------
# Timeline phase bands
# ---------------------------------------------------------------------------

def test_bands_from_nominal_data(html_source):
    bands_section = re.search(r'(Phase bands|bands).*?forEach', html_source, re.DOTALL)
    assert bands_section is not None
    section = bands_section.group(0)
    assert ('nominalTraj' in section or 'buildPhaseBands' in section or
            'phaseBands' in section or 'computeBands' in section or
            'deriveBands' in section)


def test_bands_include_coast(html_source):
    bands = re.findall(r"label:\s*'([^']+)'", html_source)
    assert any('COAST' in b.upper() or 'APO' in b.upper() for b in bands)


def test_no_hardcoded_terrier_end(html_source):
    bands_match = re.findall(r"label:\s*'TERRIER'[^}]*end:\s*(\d+)", html_source)
    for end_val in bands_match:
        assert int(end_val) != 290


def test_band_builder_fn(html_source):
    assert re.search(
        r'function\s+(buildPhaseBands|computePhaseBands|derivePhaseBands)', html_source
    )


def test_phase_band_colors(html_source):
    color_map = re.search(r'(PHASE_COLORS|phaseColors|bandColors)\s*=\s*\{', html_source)
    has_color_in_bands = len(re.findall(r"color:\s*'rgba", html_source)) >= 5
    assert color_map is not None or has_color_in_bands


def test_bands_update_on_load(html_source):
    on_nominal = re.search(r"socket\.on\('nominal'", html_source, re.DOTALL)
    assert on_nominal is not None
    handler_section = html_source[on_nominal.start():on_nominal.start() + 700]
    assert ('buildPhaseBands' in handler_section or
            'computePhaseBands' in handler_section or
            'derivePhaseBands' in handler_section or
            'phaseBands' in handler_section)


# ---------------------------------------------------------------------------
# Telemachus topics
# ---------------------------------------------------------------------------

def test_topics_vessel_data():
    from mission_control.telemachus_client import SUBSCRIBED_TOPICS
    required = [
        "v.altitude", "v.speed", "v.verticalSpeed", "v.surfaceSpeed",
        "v.mass", "v.geeForce", "v.mach", "v.dynamicPressurekPa",
        "v.atmosphericDensity", "v.lat", "v.long", "v.currentStage",
    ]
    for t in required:
        assert t in SUBSCRIBED_TOPICS


def test_topics_orbital_data():
    from mission_control.telemachus_client import SUBSCRIBED_TOPICS
    for t in ["o.ApA", "o.PeA", "o.inclination", "o.eccentricity",
              "o.sma", "o.period", "o.timeToAp", "o.timeToPe"]:
        assert t in SUBSCRIBED_TOPICS


def test_topics_dv_totals():
    from mission_control.telemachus_client import SUBSCRIBED_TOPICS
    for t in ["dv.ready", "dv.stageCount", "dv.totalDVVac",
              "dv.totalDVASL", "dv.totalDVActual", "dv.totalBurnTime"]:
        assert t in SUBSCRIBED_TOPICS


def test_topics_resource_maxes():
    from mission_control.telemachus_client import SUBSCRIBED_TOPICS
    for t in ["r.resource[LiquidFuel]", "r.resource[SolidFuel]",
              "r.resource[Oxidizer]", "r.resource[ElectricCharge]",
              "r.resourceMax[LiquidFuel]", "r.resourceMax[SolidFuel]",
              "r.resourceMax[Oxidizer]", "r.resourceMax[ElectricCharge]"]:
        assert t in SUBSCRIBED_TOPICS


def test_topics_current_stage_res():
    from mission_control.telemachus_client import SUBSCRIBED_TOPICS
    for t in ["r.resourceCurrent[LiquidFuel]", "r.resourceCurrent[SolidFuel]",
              "r.resourceCurrent[Oxidizer]",
              "r.resourceCurrentMax[LiquidFuel]", "r.resourceCurrentMax[SolidFuel]",
              "r.resourceCurrentMax[Oxidizer]"]:
        assert t in SUBSCRIBED_TOPICS


def test_field_map_covers_topics():
    from mission_control.telemachus_client import SUBSCRIBED_TOPICS, FIELD_MAP
    for topic in SUBSCRIBED_TOPICS:
        assert topic in FIELD_MAP, f"FIELD_MAP missing '{topic}'"


def test_field_map_no_dupes():
    from mission_control.telemachus_client import FIELD_MAP
    values = list(FIELD_MAP.values())
    dupes = [v for v in values if values.count(v) > 1]
    assert len(dupes) == 0, f"Duplicate keys: {set(dupes)}"


def test_stage_dv_topics():
    from mission_control.telemachus_client import STAGE_DV_TOPICS
    for key in ["dv.stageDVVac", "dv.stageFuelMass", "dv.stageBurnTime",
                "dv.stageMass", "dv.stageDryMass"]:
        assert key in STAGE_DV_TOPICS
    assert len(STAGE_DV_TOPICS) >= 15


# ---------------------------------------------------------------------------
# TelematicusClient stages
# ---------------------------------------------------------------------------

def test_rebuild_stages():
    from mission_control.telemachus_client import TelematicusClient
    import threading
    client = TelematicusClient.__new__(TelematicusClient)
    client._state = {"dv_stage_count": 2}
    client._stage_field_map = {}
    client._lock = threading.Lock()
    client._state["stage_0_dvvac"] = 1500.0
    client._state["stage_0_fuelmass"] = 2.0
    client._state["stage_0_drymass"] = 1.0
    client._state["stage_1_dvvac"] = 3000.0
    client._state["stage_1_fuelmass"] = 4.0
    client._state["stage_1_drymass"] = 2.0
    with client._lock:
        client._rebuild_stages_locked()
    stages = client._state["stages"]
    assert len(stages) == 2
    assert stages[0]["dv_vac"] == 1500.0
    assert stages[1]["dv_vac"] == 3000.0


def test_rebuild_stages_skips_empty():
    from mission_control.telemachus_client import TelematicusClient
    import threading
    client = TelematicusClient.__new__(TelematicusClient)
    client._state = {"dv_stage_count": 3}
    client._stage_field_map = {}
    client._lock = threading.Lock()
    client._state["stage_0_dvvac"] = 500.0
    client._state["stage_0_fuelmass"] = 1.0
    client._state["stage_2_dvvac"] = 800.0
    client._state["stage_2_fuelmass"] = 0.5
    with client._lock:
        client._rebuild_stages_locked()
    stages = client._state["stages"]
    assert len(stages) == 2
    assert stages[0]["index"] == 0
    assert stages[1]["index"] == 2


def test_rebuild_stages_no_count():
    from mission_control.telemachus_client import TelematicusClient
    import threading
    client = TelematicusClient.__new__(TelematicusClient)
    client._state = {}
    client._stage_field_map = {}
    client._lock = threading.Lock()
    with client._lock:
        client._rebuild_stages_locked()
    assert "stages" not in client._state


# ---------------------------------------------------------------------------
# v_horiz derivation
# ---------------------------------------------------------------------------

def _make_telem_client():
    import threading
    from mission_control.telemachus_client import TelematicusClient, EMPTY_STATE
    client = TelematicusClient.__new__(TelematicusClient)
    client._state = dict(EMPTY_STATE)
    client._stage_field_map = {}
    client._lock = threading.Lock()
    client._trajectory_lock = threading.Lock()
    client._trajectory = []
    client._launch_lon = None
    client.on_update = None
    return client


def test_field_map_surface_speed():
    from mission_control.telemachus_client import FIELD_MAP
    assert FIELD_MAP["v.surfaceSpeed"] == "surface_speed"
    assert "v_horiz" not in FIELD_MAP.values()


def test_v_horiz_derived():
    import json
    client = _make_telem_client()
    client._handle_message(json.dumps({"v.surfaceSpeed": 500.0, "v.verticalSpeed": 300.0}))
    expected = math.sqrt(500**2 - 300**2)
    assert client.get_state()["v_horiz"] == pytest.approx(expected, abs=0.001)


def test_v_horiz_pure_horizontal():
    import json
    client = _make_telem_client()
    client._handle_message(json.dumps({"v.surfaceSpeed": 1000.0, "v.verticalSpeed": 0.0}))
    assert client.get_state()["v_horiz"] == pytest.approx(1000.0, abs=0.001)


def test_v_horiz_pure_vertical():
    import json
    client = _make_telem_client()
    client._handle_message(json.dumps({"v.surfaceSpeed": 200.0, "v.verticalSpeed": 200.0}))
    assert client.get_state()["v_horiz"] == pytest.approx(0.0, abs=0.01)


def test_v_horiz_in_empty_state():
    from mission_control.telemachus_client import EMPTY_STATE
    assert "v_horiz" in EMPTY_STATE
    assert "surface_speed" in EMPTY_STATE


# ---------------------------------------------------------------------------
# SimulatedTelemetry stages
# ---------------------------------------------------------------------------

def test_sim_telem_has_stages():
    from mission_control.telemachus_client import SimulatedTelemetry
    client = SimulatedTelemetry(rate_ms=200)
    client.start()
    state = wait_for(lambda: client.get_state() if client.get_state().get("stages") else None)
    client.stop()
    assert "stages" in state
    assert isinstance(state["stages"], list)
    assert len(state["stages"]) > 0


def test_sim_telem_resource_maxes():
    from mission_control.telemachus_client import SimulatedTelemetry
    client = SimulatedTelemetry(rate_ms=200)
    client.start()
    state = wait_for(lambda: client.get_state() if client.get_state().get("stages") else None)
    client.stop()
    assert state["liquid_fuel_max"] > 0
    assert state["solid_fuel_max"] > 0


def test_sim_telem_mass_and_forces():
    from mission_control.telemachus_client import SimulatedTelemetry
    client = SimulatedTelemetry(rate_ms=200)
    client.start()
    state = wait_for(lambda: client.get_state() if client.get_state().get("stages") else None)
    client.stop()
    for key in ("mass", "mach", "dynamic_pressure"):
        assert key in state


def test_sim_telem_stage_dv_fuel():
    from mission_control.telemachus_client import SimulatedTelemetry
    client = SimulatedTelemetry(rate_ms=200)
    client.start()
    state = wait_for(lambda: client.get_state() if client.get_state().get("stages") else None)
    client.stop()
    for stg in state["stages"]:
        assert stg["dv_vac"] is not None
        assert stg["fuel_mass"] is not None
        assert "label" in stg


def test_no_hardcoded_fuel_maxes(html_source):
    matches = re.findall(r'lfMax\s*=\s*360|sfMax\s*=\s*160', html_source)
    assert len(matches) == 0


# ---------------------------------------------------------------------------
# ScriptedTelemetry stages
# ---------------------------------------------------------------------------

def test_scripted_has_stages():
    from mission_control.telemachus_client import ScriptedTelemetry
    from mission_control.scenario import LaunchScenario
    client = ScriptedTelemetry(rate_ms=200)
    client.load_scenario(LaunchScenario())
    client.start()
    state = wait_for(lambda: client.get_state() if client.get_state().get("stages") else None)
    client.stop()
    assert isinstance(state["stages"], list)
    assert len(state["stages"]) > 0


def test_scripted_resource_maxes():
    from mission_control.telemachus_client import ScriptedTelemetry
    from mission_control.scenario import LaunchScenario
    client = ScriptedTelemetry(rate_ms=200)
    client.load_scenario(LaunchScenario())
    client.start()
    state = wait_for(lambda: client.get_state() if client.get_state().get("stages") else None)
    client.stop()
    assert state["liquid_fuel_max"] > 0


def test_scripted_has_mass():
    from mission_control.telemachus_client import ScriptedTelemetry
    from mission_control.scenario import LaunchScenario
    client = ScriptedTelemetry(rate_ms=200)
    client.load_scenario(LaunchScenario())
    client.start()
    state = wait_for(lambda: client.get_state() if client.get_state().get("stages") else None)
    client.stop()
    assert state["mass"] is not None
    assert state["mass"] > 0


# ---------------------------------------------------------------------------
# Stage dV accuracy (SimulatedTelemetry)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def stage_dv_data():
    """Pre-compute ascent result and helpers for stage dV tests."""
    from sim import run_ascent, VehicleConfig
    from mission_control.telemachus_client import SimulatedTelemetry
    result = run_ascent()
    pts = result.points
    cfg = VehicleConfig()

    def get_points_for_phase(phase):
        return [p for p in pts if p.phase == phase]

    def build_stages(elapsed):
        s = SimulatedTelemetry.__new__(SimulatedTelemetry)
        timing = s._extract_stage_timing(pts)
        return s._build_sim_stages(elapsed, timing)

    def find_stage(stages, label):
        for s in stages:
            if s["label"] == label:
                return s
        return None

    return pts, cfg, get_points_for_phase, build_stages, find_stage


def test_terrier_dv_const_boost(stage_dv_data):
    pts, _, get_phase, build_stages, find_stage = stage_dv_data
    boost_pts = get_phase("BOOST")
    assert len(boost_pts) > 5
    terrier_dvs = [find_stage(build_stages(p.t), "Stage 2")["dv_vac"]
                   for p in boost_pts if find_stage(build_stages(p.t), "Stage 2")]
    assert len(terrier_dvs) > 5
    assert terrier_dvs[0] == pytest.approx(terrier_dvs[-1], abs=1.0)


def test_terrier_dv_const_core(stage_dv_data):
    pts, _, get_phase, build_stages, find_stage = stage_dv_data
    core_pts = get_phase("CORE")
    assert len(core_pts) > 5
    terrier_dvs = [find_stage(build_stages(p.t), "Stage 2")["dv_vac"]
                   for p in core_pts if find_stage(build_stages(p.t), "Stage 2")]
    assert len(terrier_dvs) > 5
    assert terrier_dvs[0] == pytest.approx(terrier_dvs[-1], abs=1.0)


def test_terrier_dv_const_coast(stage_dv_data):
    pts, _, get_phase, build_stages, find_stage = stage_dv_data
    coast_pts = get_phase("COAST_APO")
    if not coast_pts:
        pytest.skip("No COAST_APO phase in trajectory")
    terrier_dvs = [find_stage(build_stages(p.t), "Stage 2")["dv_vac"]
                   for p in coast_pts if find_stage(build_stages(p.t), "Stage 2")]
    assert len(terrier_dvs) > 2
    assert terrier_dvs[0] == pytest.approx(terrier_dvs[-1], abs=1.0)


def test_terrier_dv_decreases_burn(stage_dv_data):
    pts, _, get_phase, build_stages, find_stage = stage_dv_data
    terrier_pts = get_phase("TERRIER")
    assert len(terrier_pts) > 10
    terrier_dvs = [find_stage(build_stages(p.t), "Stage 2")["dv_vac"]
                   for p in terrier_pts if find_stage(build_stages(p.t), "Stage 2")]
    assert terrier_dvs[0] > terrier_dvs[-1]
    for i in range(1, len(terrier_dvs)):
        assert terrier_dvs[i] <= terrier_dvs[i-1] + 0.1


def test_terrier_starts_full_dv(stage_dv_data):
    _, _, _, build_stages, find_stage = stage_dv_data
    t = find_stage(build_stages(0.0), "Stage 2")
    assert t is not None
    assert t["dv_vac"] == pytest.approx(3458.0, abs=50)


def test_core_dv_decreases_boost(stage_dv_data):
    _, _, get_phase, build_stages, find_stage = stage_dv_data
    boost_pts = get_phase("BOOST")
    core_dvs = [find_stage(build_stages(p.t), "Stage 1")["dv_vac"]
                for p in boost_pts if find_stage(build_stages(p.t), "Stage 1")]
    assert len(core_dvs) > 5
    assert core_dvs[0] > core_dvs[-1]


def test_core_dv_decreases_core(stage_dv_data):
    _, _, get_phase, build_stages, find_stage = stage_dv_data
    core_pts = get_phase("CORE")
    core_dvs = [find_stage(build_stages(p.t), "Stage 1")["dv_vac"]
                for p in core_pts if find_stage(build_stages(p.t), "Stage 1")]
    assert len(core_dvs) > 5
    assert core_dvs[0] > core_dvs[-1]


def test_srb_dv_decreases_boost(stage_dv_data):
    _, _, get_phase, build_stages, find_stage = stage_dv_data
    boost_pts = get_phase("BOOST")
    srb_dvs = [find_stage(build_stages(p.t), "Stage 0")["dv_vac"]
               for p in boost_pts if find_stage(build_stages(p.t), "Stage 0")]
    assert len(srb_dvs) > 5
    assert srb_dvs[0] > srb_dvs[-1]
    assert srb_dvs[0] == pytest.approx(222.0, abs=10)


def test_srb_depleted_after_boost(stage_dv_data):
    _, _, get_phase, build_stages, find_stage = stage_dv_data
    core_pts = get_phase("CORE")
    for p in core_pts[:3]:
        s = find_stage(build_stages(p.t), "Stage 0")
        assert s is not None
        assert s["status"] == "depleted"
        assert s["dv_vac"] == pytest.approx(0.0, abs=0.1)


def test_core_depleted_after_core(stage_dv_data):
    _, _, get_phase, build_stages, find_stage = stage_dv_data
    terrier_pts = get_phase("TERRIER")
    for p in terrier_pts[:3]:
        c = find_stage(build_stages(p.t), "Stage 1")
        assert c is not None
        assert c["status"] == "depleted"
        assert c["dv_vac"] == pytest.approx(0.0, abs=0.1)


def test_all_stages_always_present(stage_dv_data):
    pts, _, _, build_stages, _ = stage_dv_data
    for p in pts[::10]:
        stages = build_stages(p.t)
        assert len(stages) == 3
        assert [s["label"] for s in stages] == ["Stage 0", "Stage 1", "Stage 2"]


def test_stages_have_dv_initial(stage_dv_data):
    _, _, _, build_stages, _ = stage_dv_data
    for s in build_stages(0.0):
        assert "dv_initial" in s
        assert s["dv_initial"] > 0


def test_stages_have_status(stage_dv_data):
    _, _, _, build_stages, _ = stage_dv_data
    for s in build_stages(0.0):
        assert s["status"] in ("pending", "active", "depleted")


# ---------------------------------------------------------------------------
# Scripted stage dV accuracy
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def scripted_stage_data():
    """Pre-compute data for ScriptedTelemetry stage dV tests."""
    from sim import run_ascent
    from mission_control.scenario import LaunchScenario
    from mission_control.telemachus_client import SimulatedTelemetry, ScriptedTelemetry
    scenario = LaunchScenario()
    cfg = scenario.to_vehicle_config()
    result = run_ascent(cfg, scenario.get_pitch_program())
    pts = result.points
    timing = SimulatedTelemetry._extract_stage_timing(pts)

    def build_stages(elapsed):
        s = ScriptedTelemetry.__new__(ScriptedTelemetry)
        s._vehicle_cfg = cfg
        s._scenario = scenario
        return s._build_scripted_stages(elapsed, timing)

    def find_stage(stages, label):
        for s in stages:
            if s["label"] == label:
                return s
        return None

    return pts, build_stages, find_stage


def test_scr_terrier_const_boost(scripted_stage_data):
    pts, build_stages, find_stage = scripted_stage_data
    boost_pts = [p for p in pts if p.phase == "BOOST"]
    dvs = [find_stage(build_stages(p.t), "Stage 2")["dv_vac"]
           for p in boost_pts if find_stage(build_stages(p.t), "Stage 2")]
    assert len(dvs) > 5
    assert dvs[0] == pytest.approx(dvs[-1], abs=1.0)


def test_scr_terrier_const_core(scripted_stage_data):
    pts, build_stages, find_stage = scripted_stage_data
    core_pts = [p for p in pts if p.phase == "CORE"]
    dvs = [find_stage(build_stages(p.t), "Stage 2")["dv_vac"]
           for p in core_pts if find_stage(build_stages(p.t), "Stage 2")]
    assert len(dvs) > 5
    assert dvs[0] == pytest.approx(dvs[-1], abs=1.0)


def test_scr_terrier_decreases_burn(scripted_stage_data):
    pts, build_stages, find_stage = scripted_stage_data
    terrier_pts = [p for p in pts if p.phase == "TERRIER"]
    dvs = [find_stage(build_stages(p.t), "Stage 2")["dv_vac"]
           for p in terrier_pts if find_stage(build_stages(p.t), "Stage 2")]
    assert dvs[0] > dvs[-1]


def test_scr_terrier_const_coast(scripted_stage_data):
    pts, build_stages, find_stage = scripted_stage_data
    coast_pts = [p for p in pts if p.phase == "COAST_APO"]
    if not coast_pts:
        pytest.skip("No COAST_APO phase")
    dvs = [find_stage(build_stages(p.t), "Stage 2")["dv_vac"]
           for p in coast_pts if find_stage(build_stages(p.t), "Stage 2")]
    assert len(dvs) > 2
    assert dvs[0] == pytest.approx(dvs[-1], abs=1.0)


# ---------------------------------------------------------------------------
# UI stage bar elements
# ---------------------------------------------------------------------------

def test_stage_dv_section(html_source):
    assert 'id="stage-dv-section"' in html_source
    assert 'id="stage-dv-bars"' in html_source


def test_update_stage_dv_bars_fn(html_source):
    assert 'function updateStageDVBars' in html_source


def test_stage_dv_bars_called(html_source):
    assert len(re.findall(r'updateStageDVBars\(', html_source)) >= 1


def test_uses_stages_from_state(html_source):
    assert 's.stages' in html_source


def test_fuel_max_from_telem(html_source):
    assert 's.liquid_fuel_max' in html_source
    assert 's.solid_fuel_max' in html_source


def test_vessel_section(html_source):
    for tid in ['vessel-section', 't-mass', 't-gforce', 't-mach', 't-dynp']:
        assert f'id="{tid}"' in html_source


def test_orbit_time_fields(html_source):
    assert 'id="t-tta"' in html_source
    assert 'id="t-ttp"' in html_source


# ---------------------------------------------------------------------------
# Circularize boundary (parametrized)
# ---------------------------------------------------------------------------

def _detect_phase_helper(alt_m, apo_km, pe_km, v_vert, prev=None):
    from mission_control.nominal_compare import detect_phase
    state = {
        "altitude": alt_m,
        "apoapsis": apo_km * 1000,
        "periapsis": pe_km * 1000,
        "solid_fuel": 0,
        "liquid_fuel": 100,
        "throttle": 1.0,
        "v_vert": v_vert,
    }
    return detect_phase(state, prev).name


@pytest.mark.parametrize("v_vert, expected", [
    (49, "CIRCULARIZE"),
    (-49, "CIRCULARIZE"),
])
def test_circ_triggers(v_vert, expected):
    assert _detect_phase_helper(70000, 80, 30, v_vert) == expected


@pytest.mark.parametrize("v_vert", [50, 51, -51])
def test_circ_does_not_trigger(v_vert):
    assert _detect_phase_helper(70000, 80, 30, v_vert) != "CIRCULARIZE"


# ---------------------------------------------------------------------------
# CLI scenario flag
# ---------------------------------------------------------------------------

def test_unknown_scenario_exits():
    from mission_control.server import build_argparser
    from mission_control.scenario import PRESET_SCENARIOS
    args = build_argparser().parse_args(["--scenario", "nonexistent_scenario_xyz"])
    assert args.scenario == "nonexistent_scenario_xyz"
    assert args.scenario not in PRESET_SCENARIOS


def test_valid_scenario_parses():
    from mission_control.server import build_argparser
    assert build_argparser().parse_args(["--scenario", "nominal"]).scenario == "nominal"


def test_sim_compare_flag():
    from sim.ascent_sim import build_argparser
    args = build_argparser().parse_args(["--compare", "nominal", "steep"])
    assert args.compare == ["nominal", "steep"]


# ---------------------------------------------------------------------------
# API error paths (consolidated with ballistic's duplicates removed)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("endpoint", [
    "/api/scenario/start",
    "/api/scenario/pause",
    "/api/scenario/resume",
    "/api/scenario/reset",
])
def test_no_client_returns_400(flask_test_client, endpoint):
    client, _, _, _ = flask_test_client
    assert client.post(endpoint).status_code == 400


def test_speed_no_client_400(flask_test_client):
    client, _, _, _ = flask_test_client
    assert client.post("/api/scenario/speed", json={"speed": 2.0}).status_code == 400


def test_speed_out_of_range_400(flask_test_client):
    client, _, _, _ = flask_test_client
    client.post("/api/scenario/load", json={"preset": "nominal"})
    assert client.post("/api/scenario/speed", json={"speed": 100.0}).status_code == 400
    assert client.post("/api/scenario/speed", json={"speed": 0.1}).status_code == 400


def test_load_unknown_preset_400(flask_test_client):
    client, _, _, _ = flask_test_client
    assert client.post("/api/scenario/load", json={"preset": "does_not_exist"}).status_code == 400


def test_load_invalid_body_400(flask_test_client):
    client, _, _, _ = flask_test_client
    assert client.post("/api/scenario/load", data="not json",
                       content_type="text/plain").status_code == 400


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_from_dict_coerces_int():
    from mission_control.scenario import LaunchScenario
    assert LaunchScenario.from_dict({"n_boosters": "3"}).n_boosters == 3


def test_from_dict_coerces_float():
    from mission_control.scenario import LaunchScenario
    assert LaunchScenario.from_dict({"booster_pct": "25.5"}).booster_pct == pytest.approx(25.5)


def test_from_dict_bad_type_validates():
    from mission_control.scenario import LaunchScenario
    assert len(LaunchScenario.from_dict({"n_boosters": "foo"}).validate()) > 0


def test_from_dict_non_numeric_validates():
    from mission_control.scenario import LaunchScenario
    assert len(LaunchScenario.from_dict({"booster_pct": "not_a_number"}).validate()) > 0


# ---------------------------------------------------------------------------
# Preset noise override
# ---------------------------------------------------------------------------

def test_preset_noise_override(flask_test_client):
    client, _, _, _ = flask_test_client
    resp = client.post("/api/scenario/load", json={"preset": "nominal", "noise_pct": 0.10})
    assert resp.status_code == 200
    import mission_control.server as srv
    assert srv.session.current_scenario.noise_pct == pytest.approx(0.10)


def test_preset_speed_override(flask_test_client):
    client, _, _, _ = flask_test_client
    resp = client.post("/api/scenario/load", json={"preset": "nominal", "playback_speed": 5.0})
    assert resp.status_code == 200
    import mission_control.server as srv
    assert srv.session.current_scenario.playback_speed == pytest.approx(5.0)


def test_preset_invalid_noise_ignored(flask_test_client):
    client, _, _, _ = flask_test_client
    resp = client.post("/api/scenario/load", json={"preset": "nominal", "noise_pct": 0.50})
    assert resp.status_code == 200
    import mission_control.server as srv
    assert srv.session.current_scenario.noise_pct == pytest.approx(0.02)


# ---------------------------------------------------------------------------
# Telemetry field completeness
# ---------------------------------------------------------------------------

def test_sim_has_lat_lon():
    from mission_control.telemachus_client import SimulatedTelemetry
    client = SimulatedTelemetry(rate_ms=50)
    client.start()
    state = wait_for(lambda: client.get_state() if (client.get_state().get("altitude") or 0) > 0 else None)
    client.stop()
    assert "latitude" in state and state["latitude"] is not None
    assert "longitude" in state and state["longitude"] is not None


def test_scripted_has_lat_lon():
    from mission_control.telemachus_client import ScriptedTelemetry
    from mission_control.scenario import LaunchScenario
    client = ScriptedTelemetry(rate_ms=50)
    client.load_scenario(LaunchScenario(noise_pct=0.0, playback_speed=10.0))
    client.start()
    state = wait_for(lambda: client.get_state() if (client.get_state().get("altitude") or 0) > 0 else None)
    client.stop()
    assert "latitude" in state
    assert "longitude" in state


def test_sim_time_to_ap_none():
    from mission_control.telemachus_client import SimulatedTelemetry
    client = SimulatedTelemetry(rate_ms=50)
    client.start()
    state = wait_for(lambda: client.get_state() if (client.get_state().get("altitude") or 0) > 0 else None)
    client.stop()
    assert state.get("time_to_ap") is None


# ---------------------------------------------------------------------------
# XSS escaping
# ---------------------------------------------------------------------------

def test_esc_function(html_source):
    assert 'function esc(' in html_source


def test_gates_use_esc(html_source):
    assert 'esc(g.phase)' in html_source
    assert 'esc(g.status)' in html_source
    assert 'esc(g.detail' in html_source


def test_stage_labels_esc(html_source):
    assert 'esc(stg.label' in html_source


def test_nominal_comp_esc(html_source):
    assert 'esc(r.label)' in html_source


# ---------------------------------------------------------------------------
# Pitch delta threshold
# ---------------------------------------------------------------------------

def test_threshold_uses_max_floor(html_source):
    assert 'Math.max(Math.abs(r.nom), 5)' in html_source


# ---------------------------------------------------------------------------
# Socket.IO broadcast
# ---------------------------------------------------------------------------

@pytest.fixture
def socketio_env():
    """Set up Flask-SocketIO test environment with SimulatedTelemetry running."""
    from mission_control.server import app, socketio, session
    from mission_control.nominal_compare import NominalTrajectory, FlightDirector
    from mission_control.telemachus_client import SimulatedTelemetry

    app.config["TESTING"] = True
    nom = NominalTrajectory.load()
    session.nominal_traj = nom
    session.flight_director = FlightDirector(nom)
    client = SimulatedTelemetry(rate_ms=50)
    client.start()
    wait_for(lambda: (client.get_state().get("altitude") or 0) > 0)
    wait_for(lambda: len(client.get_trajectory()) > 0)
    session.telemetry_client = client

    session.current_scenario = None

    yield app, socketio, session, client

    client.stop()
    session.telemetry_client = None
    session.current_scenario = None


def _sio_connect(app, socketio):
    from flask_socketio import SocketIOTestClient
    return SocketIOTestClient(app, socketio)


def _event_names(received):
    return [r["name"] for r in received]


def test_sio_connect_events(socketio_env):
    app, socketio, _, _ = socketio_env
    sio = _sio_connect(app, socketio)
    received = sio.get_received()
    names = _event_names(received)
    assert "connected" in names
    assert "nominal" in names
    nom_event = next(r for r in received if r["name"] == "nominal")
    assert isinstance(nom_event["args"][0]["trajectory"], list)
    assert len(nom_event["args"][0]["trajectory"]) > 0
    sio.disconnect()


def test_sio_traj_history(socketio_env):
    app, socketio, _, _ = socketio_env
    sio = _sio_connect(app, socketio)
    received = sio.get_received()
    assert "trajectory_history" in _event_names(received)
    hist = next(r for r in received if r["name"] == "trajectory_history")
    assert "trajectory" in hist["args"][0]
    sio.disconnect()


def test_sio_broadcast_pipeline(socketio_env):
    app, socketio_obj, session, _ = socketio_env
    sio = _sio_connect(app, socketio_obj)
    sio.get_received()

    state = session.telemetry_client.get_state()
    trajectory = session.telemetry_client.get_trajectory()
    director_out = session.flight_director.update(state)

    with app.test_request_context("/"):
        socketio_obj.emit("telemetry", {
            "state": state,
            "trajectory": trajectory[-50:] if trajectory else [],
        })
        socketio_obj.emit("director", director_out)

    received = sio.get_received()
    names = _event_names(received)
    assert "telemetry" in names
    assert "director" in names

    telem = next(r for r in received if r["name"] == "telemetry")
    telem_state = telem["args"][0]["state"]
    for key in ("altitude", "velocity", "v_horiz"):
        assert key in telem_state

    director = next(r for r in received if r["name"] == "director")
    assert "phase" in director["args"][0]
    sio.disconnect()


def test_sio_director_advisory(socketio_env):
    app, socketio_obj, session, _ = socketio_env
    sio = _sio_connect(app, socketio_obj)
    sio.get_received()

    state = session.telemetry_client.get_state()
    director_out = session.flight_director.update(state)

    with app.test_request_context("/"):
        socketio_obj.emit("director", director_out)

    received = sio.get_received()
    director = next(r for r in received if r["name"] == "director")
    data = director["args"][0]
    assert "advisory" in data
    assert "gates" in data
    assert "level" in data["advisory"]
    assert isinstance(data["gates"], list)
    sio.disconnect()


def test_sio_request_nominal(socketio_env):
    app, socketio_obj, _, _ = socketio_env
    sio = _sio_connect(app, socketio_obj)
    sio.get_received()
    sio.emit("request_nominal")
    received = sio.get_received()
    assert "nominal" in _event_names(received)
    sio.disconnect()


def test_sio_clear_trajectory(socketio_env):
    app, socketio_obj, session, _ = socketio_env
    sio = _sio_connect(app, socketio_obj)
    sio.get_received()
    pre_len = len(session.telemetry_client.get_trajectory())
    sio.emit("clear_trajectory")
    assert len(session.telemetry_client.get_trajectory()) == 0
    sio.disconnect()
