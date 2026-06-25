"""Regression tests for P1 (High) findings from the Engineering Review."""

import pytest

from mission_control.nominal_compare import FlightPhase, detect_phase, generate_advisory
from sim.vehicle import VehicleConfig


# ---------------------------------------------------------------------------
# P1-02  Phase detection fragility
# ---------------------------------------------------------------------------

def test_p102_coast_detected(telemetry_state):
    state = telemetry_state(alt=30000, apo=45000, pe=-400000,
                            met=80, sf=0, lf=300, throttle=0.0)
    phase = detect_phase(state, FlightPhase.TERRIER)
    assert phase == FlightPhase.COAST, f"Throttle=0 at 30km should be COAST, got {phase.value}"


def test_p102_core_during_swivel(telemetry_state):
    state = telemetry_state(alt=5000, apo=4000, pe=-600000,
                            met=30, sf=0, lf=355, throttle=1.0)
    phase = detect_phase(state, FlightPhase.BOOST)
    assert phase == FlightPhase.CORE, f"Post booster-sep at 5km should be CORE, got {phase.value}"


def test_p102_terrier_after_burnout(telemetry_state):
    state = telemetry_state(alt=19000, apo=38000, pe=-560000,
                            met=72, sf=0, lf=330, throttle=1.0)
    phase = detect_phase(state, FlightPhase.CORE)
    assert phase == FlightPhase.TERRIER, f"At 19km/38km Ap should be TERRIER, got {phase.value}"


def test_p102_no_terrier_regression(telemetry_state):
    # Once TERRIER, must not regress to CORE on noise
    state = telemetry_state(alt=20000, apo=28000, pe=-550000,
                            met=75, sf=0, lf=310, throttle=1.0)
    phase = detect_phase(state, FlightPhase.TERRIER)
    assert phase == FlightPhase.TERRIER, (
        f"Must not regress from TERRIER on Ap noise, got {phase.value}")


def test_p102_orbit_detected(telemetry_state):
    state = telemetry_state(alt=80000, apo=82000, pe=78000,
                            met=180, sf=0, lf=200, throttle=0.0)
    phase = detect_phase(state, FlightPhase.CIRCULARIZE)
    assert phase == FlightPhase.ORBIT, f"Pe=78km should be ORBIT, got {phase.value}"


# ---------------------------------------------------------------------------
# P1-05  ABORT advisory premature trigger
# ---------------------------------------------------------------------------

def _terrier_state(lf=360.0, apo_km=25.0, pe_km=-587.0, met=63.0):
    return {
        "altitude":     15_000.0,
        "apoapsis":     apo_km * 1000,
        "periapsis":    pe_km * 1000,
        "mission_time": met,
        "solid_fuel":    0.0,
        "liquid_fuel":  lf,
        "throttle":      1.0,
        "pitch":         50.0,
        "velocity":     631.0,
    }


def test_p105_no_abort_at_ignition():
    state = _terrier_state(lf=360.0, apo_km=25.0, pe_km=-587.0, met=63.0)
    adv = generate_advisory(state, FlightPhase.TERRIER)
    assert adv.level != "ABORT", f"ABORT fired at T+63s with full fuel: '{adv.action}'"


def test_p105_no_abort_at_t65():
    state = _terrier_state(lf=270.0, apo_km=26.0, pe_km=-580.0, met=65.0)
    adv = generate_advisory(state, FlightPhase.TERRIER)
    assert adv.level != "ABORT", f"ABORT fired at T+65s with 75% fuel: '{adv.action}'"


def test_p105_abort_fires_late():
    # Genuine abort at T+120s with low fuel and stalled trajectory
    state = _terrier_state(lf=85.0, apo_km=32.0, pe_km=-450.0, met=120.0)
    adv = generate_advisory(state, FlightPhase.TERRIER)
    assert adv.level == "ABORT", (
        f"ABORT should fire at T+120s with 23.6% fuel, got '{adv.level}'")


def test_p105_guard_then_abort():
    # Early: suppressed; late: fires
    early = _terrier_state(lf=85.0, apo_km=24.0, pe_km=-587.0, met=65.0)
    early_adv = generate_advisory(early, FlightPhase.TERRIER)
    late = _terrier_state(lf=85.0, apo_km=24.0, pe_km=-587.0, met=120.0)
    late_adv = generate_advisory(late, FlightPhase.TERRIER)
    assert early_adv.level != "ABORT", f"Early ABORT must be suppressed: '{early_adv.action}'"
    assert late_adv.level == "ABORT", f"Late ABORT must fire, got '{late_adv.level}'"


# ---------------------------------------------------------------------------
# P1-01  CLI extra-payload default mismatch
# ---------------------------------------------------------------------------

def test_p101_cli_default_match():
    from sim.ascent_sim import build_argparser
    args = build_argparser().parse_args([])
    cfg = VehicleConfig()
    assert args.extra_payload == pytest.approx(cfg.extra_payload, abs=0.001), (
        f"CLI default extra_payload={args.extra_payload} != VehicleConfig={cfg.extra_payload}")


def test_p101_cli_mass_match():
    from sim.ascent_sim import build_argparser
    args = build_argparser().parse_args([])
    cfg_from_cli = VehicleConfig(
        booster_type=args.booster,
        n_boosters=args.n_boosters,
        booster_pct=args.booster_pct,
        extra_payload=args.extra_payload,
    )
    cfg_direct = VehicleConfig()
    assert cfg_from_cli.liftoff_mass_t == pytest.approx(
        cfg_direct.liftoff_mass_t, abs=0.001), (
        f"CLI mass={cfg_from_cli.liftoff_mass_t:.3f}t != "
        f"direct={cfg_direct.liftoff_mass_t:.3f}t")
