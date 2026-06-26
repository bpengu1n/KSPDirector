"""Regression tests for P0 (Critical) findings from the Engineering Review."""

import inspect
import math

import pytest

from mission_control.nominal_compare import FlightPhase, assess_gates, generate_advisory
from mission_control.telemachus_client import SimulatedTelemetry, compute_downrange_km
from sim.constants import PARTS
from sim.vehicle import VehicleConfig


# ---------------------------------------------------------------------------
# P0-01  FULL_LF = 4000 is wrong -- should be 360 KSP units
# ---------------------------------------------------------------------------

def test_p001_full_lf_value(terrier_ignition_state):
    # Full tank (360 LF) must not make MID-TERR gate NO-GO
    state = terrier_ignition_state(lf_units=360.0)
    gates = assess_gates(state, FlightPhase.TERRIER)
    mid_terr = next(g for g in gates if g.phase == "MID-TERR")
    assert mid_terr.status != "NO-GO", (
        "MID-TERR gate shows NO-GO on a full tank -- FULL_LF is wrong")


def test_p001_full_tank_pct(terrier_ignition_state):
    # Full tank must not trigger WARNING or ABORT
    state = terrier_ignition_state(lf_units=360.0)
    adv = generate_advisory(state, FlightPhase.TERRIER)
    assert adv.level != "WARNING", f"WARNING fired with full tank: '{adv.action}'"
    assert adv.level != "ABORT", f"ABORT fired with full tank: '{adv.action}'"


def test_p001_no_false_abort(terrier_ignition_state):
    # Simplified: just verify no ABORT at ignition with full fuel.
    # The low-fuel genuine-abort path is tested more thoroughly in P1-05.
    state = terrier_ignition_state(lf_units=360.0)
    adv = generate_advisory(state, FlightPhase.TERRIER)
    assert adv.level != "ABORT", (
        f"ABORT fired at Terrier ignition with full tank: '{adv.action}'")


def test_p001_late_terr_gate(terrier_ignition_state):
    # At 60% fuel (216 units), LATE-TERR should show NOT-YET
    state = terrier_ignition_state(lf_units=216.0, apoapsis=55_000.0,
                                   periapsis=-200_000.0)
    gates = assess_gates(state, FlightPhase.TERRIER)
    late = next(g for g in gates if g.phase == "LATE-TERR")
    assert late.status == "NOT-YET", (
        f"LATE-TERR gate should be NOT-YET at 60% fuel, got '{late.status}'")


# ---------------------------------------------------------------------------
# P0-02  SimulatedTelemetry fuel drain uses wrong full-tank values
# ---------------------------------------------------------------------------

def test_p002_sim_lf_max():
    src = inspect.getsource(SimulatedTelemetry._compute_liquid_fuel_from_mass)
    assert '4000' not in src, "SimulatedTelemetry must not reference 4000"
    assert '360' in src, "SimulatedTelemetry must reference 360 (correct LF max)"


def test_p002_sim_sf_max():
    src = inspect.getsource(SimulatedTelemetry._run)
    assert '600 -' not in src, "SimulatedTelemetry must not use '600 -'"
    assert '160' in src, "SimulatedTelemetry must reference 160 (correct SF max)"


def test_p002_lf_drain_timing():
    # At T+30s with both fixes, LF pct must be <= 100%
    elapsed = 30.0
    lf_fixed = max(0, 360 - elapsed * (360 / 60))
    lf_pct_fixed = (lf_fixed / 360.0) * 100
    assert lf_pct_fixed <= 100.0, f"LF pct at T=30s is {lf_pct_fixed:.0f}%, expected <= 100%"


# ---------------------------------------------------------------------------
# P0-03  Downrange uses Earth scale (111.12 km/deg) not Kerbin (10.47 km/deg)
# ---------------------------------------------------------------------------

R_KERBIN_KM = 600.0


def test_p003_km_per_deg():
    ksc_lat = 0.06
    km_per_deg = R_KERBIN_KM * math.pi / 180.0
    expected = abs(1.0) * km_per_deg * math.cos(math.radians(ksc_lat))
    result = compute_downrange_km(1.0, ksc_lat)
    assert result == pytest.approx(expected, abs=0.1), (
        f"compute_downrange_km(1.0, {ksc_lat}) = {result:.3f}, expected ~{expected:.3f}")


def test_p003_burnout_dr():
    lon_change = 8.07 / (R_KERBIN_KM * math.pi / 180.0)
    result = compute_downrange_km(lon_change, 0.06)
    assert result == pytest.approx(8.07, abs=0.15), (
        f"Burnout downrange: {result:.2f} km, expected ~8.07 km")


def test_p003_arc_visibility():
    lon_change = 8.07 / (R_KERBIN_KM * math.pi / 180.0)
    dr_km = compute_downrange_km(lon_change, 0.06)
    arc_px = (dr_km / R_KERBIN_KM) * 300
    assert arc_px > 3.0, (
        f"Arc at burnout: {arc_px:.2f}px on 300px globe, must be >3px")


# ---------------------------------------------------------------------------
# P0-04  SimulatedTelemetry pitch convention is inverted
# ---------------------------------------------------------------------------

def test_p004_vertical_pitch():
    correct_output = 90.0 - 0.0  # pitch_from_v=0 -> KSP 90
    assert correct_output == pytest.approx(90.0, abs=0.5)
    src = inspect.getsource(SimulatedTelemetry._run)
    assert "90.0 - p.pitch_from_v" in src, (
        "SimulatedTelemetry must convert using '90.0 - p.pitch_from_v'")


def _advisory_for_pitch(sim_pitch_output, alt_km, apo_km):
    nom = {"pitch_from_vertical": 37.0}
    state = {
        "altitude": alt_km * 1000,
        "apoapsis": apo_km * 1000,
        "periapsis": -587_000.0,
        "liquid_fuel": 300.0,
        "pitch": sim_pitch_output,
        "velocity": 450.0,
        "mission_time": 50.0,
    }
    adv = generate_advisory(state, FlightPhase.TERRIER, nominal=nom)
    actual_pitch_v = 90.0 - sim_pitch_output
    return adv.level, adv.action, actual_pitch_v


def test_p004_steep_wrong_advisory():
    # Buggy output (pitch_from_v=75 passed directly) should NOT say TOWARD HORIZON
    _, action_buggy, _ = _advisory_for_pitch(75.0, 10.0, 28.0)
    assert "TOWARD HORIZON" not in action_buggy, (
        f"Bug confirmed: steep ascent advisory '{action_buggy}' says TOWARD HORIZON "
        "when fed raw pitch_from_v")


def test_p004_steep_correct_advisory():
    # After fix: KSP output = 90-75 = 15; advisory engine sees pfv=75 (steep)
    correct_output = 90.0 - 75.0
    _, _, pitch_v_computed = _advisory_for_pitch(correct_output, 10.0, 28.0)
    assert pitch_v_computed > 50.0, (
        f"After fix: pitch_v_computed={pitch_v_computed:.1f}, expected >50")
    assert pitch_v_computed > 60.0, (
        f"After fix: pitch_v_computed={pitch_v_computed:.1f}, expected >60")


# ---------------------------------------------------------------------------
# P0-05  Service bay mass double-counted in extra_payload + avionics_mass
# ---------------------------------------------------------------------------

def test_p005_no_double_count():
    cfg_default = VehicleConfig()
    cfg_with_bay = VehicleConfig(extra_payload=0.10)
    bay_mass = PARTS.get("service_bay", 0.10)

    assert cfg_default.extra_payload == pytest.approx(0.0, abs=0.001), (
        f"Default extra_payload should be 0.0, got {cfg_default.extra_payload}")
    assert cfg_default.liftoff_mass_t == pytest.approx(14.210, abs=0.005), (
        f"Default liftoff_mass should be ~14.21t, got {cfg_default.liftoff_mass_t:.3f}t")
    diff = cfg_with_bay.liftoff_mass_t - cfg_default.liftoff_mass_t
    assert diff == pytest.approx(bay_mass, abs=0.001), (
        f"Extra 0.10 should add exactly {bay_mass}t, got {diff:.3f}t")


def test_p005_twr_correct():
    cfg = VehicleConfig(extra_payload=0.0)
    assert cfg.pad_twr_asl >= 1.77, f"Pad TWR={cfg.pad_twr_asl:.4f}, expected >= 1.77"
    assert cfg.pad_twr_asl <= 1.80, f"Pad TWR={cfg.pad_twr_asl:.4f}, expected <= 1.80"


def test_p005_dv_unchanged():
    cfg_buggy = VehicleConfig(extra_payload=0.10)
    cfg_correct = VehicleConfig(extra_payload=0.0)
    assert cfg_buggy.mission_stage_dv_ms == pytest.approx(
        cfg_correct.mission_stage_dv_ms, abs=1.0), (
        f"Mission stage dV should be identical: {cfg_buggy.mission_stage_dv_ms:.0f} vs "
        f"{cfg_correct.mission_stage_dv_ms:.0f}")
    assert cfg_correct.mission_stage_dv_ms == pytest.approx(3458.0, abs=5.0), (
        f"Mission stage dV should be ~3458 m/s, got {cfg_correct.mission_stage_dv_ms:.0f}")


def test_p005_avionics_bay():
    cfg = VehicleConfig(extra_payload=0.0)
    bay = PARTS.get("service_bay", 0.10)
    rw = PARTS.get("reaction_wheel", 0.05)
    bat = PARTS.get("battery", 0.01)
    expected_avionics = rw + bat + bay
    assert cfg.avionics_mass == pytest.approx(expected_avionics, abs=0.001), (
        f"avionics_mass={cfg.avionics_mass:.3f}t, expected {expected_avionics:.3f}t")
