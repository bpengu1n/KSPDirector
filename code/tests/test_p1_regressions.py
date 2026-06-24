"""
tests/test_p1_regressions.py
==============================
Regression tests for P1 (High) findings from the Engineering Review.

P1 items addressed here:
  P1-02  Phase detection CORE/TERRIER uses hard MET threshold (fragile)
  P1-05  ABORT advisory can trigger at Terrier ignition edge cases
  P1-01  CLI extra-payload default mismatch (vehicle.py vs ascent_sim.py)

P1 items addressed by doc/diagram changes only (no code tests needed):
  P1-01  Mission stage dv stated as 3.6 km/s in build plan (text correction)
  P1-03  Sheet3 hardcoded milestones don't match current sim (diagram fix)
  P1-04  No trajectory history on browser reconnect (server test is integration-only)
  P1-06  Unused Literal import (fixed as part of P0 cycle — already green)

Authors: Dr. James Okafor (FC) — P1-02, P1-05 scenarios
         Sofia Chen (SWE) — P1-01, code-level validation
         Marcus Webb (UX) — annotated UI consequence notes
"""

import sys, os, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mission_control.nominal_compare import (
    FlightPhase, detect_phase, assess_gates, generate_advisory,
)
from sim.vehicle import VehicleConfig


# ---------------------------------------------------------------------------
# Shared state builders
# ---------------------------------------------------------------------------

def _state(alt=15000, apo=25000, pe=-587000, met=63, sf=0, lf=360,
           throttle=1.0, pitch=50.0, vel=631):
    """Build a minimal telemetry state dict for testing."""
    return {
        "altitude": float(alt), "apoapsis": float(apo), "periapsis": float(pe),
        "mission_time": float(met), "solid_fuel": float(sf),
        "liquid_fuel": float(lf), "throttle": float(throttle),
        "pitch": float(pitch), "velocity": float(vel),
        "v_horiz": 481.0, "v_vert": 408.0,
    }


# ---------------------------------------------------------------------------
# P1-02  Phase detection fragility
# ---------------------------------------------------------------------------

class TestP102PhaseDetection(unittest.TestCase):
    """
    The old detect_phase used `met < 70` to distinguish CORE from TERRIER.
    Core burnout is at ~63s MET; using met=70 gives only a 7-second window
    with no margin for off-nominal timing.

    Failure modes of the old approach:
    1. At met=71 with a full Terrier burn underway (apoapsis rising), the
       craft is classified as TERRIER — this is correct in the nominal case.
       But an early ignition or fast core burn could put us at met=71 while
       still on the core, giving a wrong TERRIER classification.
    2. After a KSP time-warp resumption, the MET can be inconsistent.
    3. There is no detection of the COAST phase (throttle=0 post-ignition).

    Fix: replace the MET-based split with altitude + apoapsis heuristics,
    use prev_phase hysteresis for the CORE→TERRIER transition, and return
    COAST when throttle < 0.05 and the craft is airborne.
    """

    # -- First order: COAST is never returned by old detect_phase --
    def test_p102_coast_phase_detected_on_zero_throttle(self):
        """
        When the Swivel is cut (throttle=0) mid-ascent, detect_phase must
        return COAST. Old code never returned COAST; a coasting craft would
        be classified as TERRIER or CORE, producing spurious guidance.
        """
        state = _state(alt=30000, apo=45000, pe=-400000,
                       met=80, sf=0, lf=300, throttle=0.0)
        phase = detect_phase(state, FlightPhase.TERRIER)
        self.assertEqual(phase, FlightPhase.COAST,
            f"Throttle=0 at 30km should be COAST, got {phase.value}. "
            f"Fix: add throttle<0.05 → COAST branch in detect_phase.")

    # -- Second order: wrong phase produces wrong gate assessment --
    def test_p102_core_phase_during_swivel_burn(self):
        """
        At the start of powered flight (alt=5km, Ap=4km, solid_fuel just gone),
        detect_phase should return CORE (Swivel burning before core burnout),
        not TERRIER. If it returns TERRIER, gate 2 (MID-TERR) activates with
        a low apoapsis and misclassifies the situation as off-nominal.
        """
        # This represents ~T+30s: boosters just dropped, swivel burning
        state = _state(alt=5000, apo=4000, pe=-600000,
                       met=30, sf=0, lf=355, throttle=1.0)
        phase = detect_phase(state, FlightPhase.BOOST)
        self.assertEqual(phase, FlightPhase.CORE,
            f"Just past booster sep (alt=5km, Ap=4km) should be CORE, "
            f"got {phase.value}. "
            f"Fix: use altitude + apoapsis heuristics instead of MET threshold.")

    # -- Second order: TERRIER correctly identified after burnout altitude --
    def test_p102_terrier_phase_after_core_burnout_altitude(self):
        """
        At alt>18km with Ap rising through 35km, the craft is clearly on
        the Terrier (past core burnout altitude of ~15km). detect_phase must
        return TERRIER regardless of MET value.
        """
        state = _state(alt=19000, apo=38000, pe=-560000,
                       met=72, sf=0, lf=330, throttle=1.0)
        phase = detect_phase(state, FlightPhase.CORE)
        self.assertEqual(phase, FlightPhase.TERRIER,
            f"At alt=19km, Ap=38km should be TERRIER, got {phase.value}. "
            f"Fix: alt>18km → TERRIER regardless of MET.")

    # -- Third order: hysteresis prevents TERRIER→CORE regression --
    def test_p102_terrier_phase_not_regressed_to_core(self):
        """
        JAMES OKAFOR (FC): Once the Terrier phase is established, a transient
        dip in apoapsis (e.g., measurement noise) must not revert classification
        to CORE. Phase transitions must be monotone: BOOST→CORE→TERRIER.
        """
        # Terrier was established (prev_phase=TERRIER)
        # Apoapsis momentarily reads 28km (noise) — below CORE threshold
        state = _state(alt=20000, apo=28000, pe=-550000,
                       met=75, sf=0, lf=310, throttle=1.0)
        phase = detect_phase(state, FlightPhase.TERRIER)
        self.assertEqual(phase, FlightPhase.TERRIER,
            f"Once TERRIER, must not regress to CORE on apoapsis noise. "
            f"Got {phase.value} with prev_phase=TERRIER. "
            f"Fix: use prev_phase hysteresis — if prev was TERRIER, stay TERRIER "
            f"while still burning liquid fuel.")

    # -- Third order: ORBIT detected correctly once Pe clears atmosphere --
    def test_p102_orbit_phase_when_periapsis_above_atmosphere(self):
        """
        When periapsis exceeds 70km, the craft is in a stable orbit.
        detect_phase must return ORBIT regardless of throttle state.
        """
        state = _state(alt=80000, apo=82000, pe=78000,
                       met=180, sf=0, lf=200, throttle=0.0)
        phase = detect_phase(state, FlightPhase.CIRCULARIZE)
        self.assertEqual(phase, FlightPhase.ORBIT,
            f"Pe=78km should be ORBIT, got {phase.value}. "
            f"Fix: pe > ATM_CEIL → ORBIT in detect_phase.")


# ---------------------------------------------------------------------------
# P1-05  ABORT advisory premature trigger
# ---------------------------------------------------------------------------

class TestP105AbortGuard(unittest.TestCase):
    """
    Even with P0-01 fixed (FULL_LF=360), there is a window at Terrier ignition
    where the abort criteria can be met:
    - Pe is deeply negative (~-587km) — normal at T+63s
    - Apoapsis is ~25km — normal at core burnout
    - If lf_pct somehow reads low (sensor glitch, or Terrier stage started
      with partial fuel for some reason), ABORT fires immediately

    Fix: add a guard that the Terrier has been burning for a minimum time
    (e.g., MET > 70s) before the abort gate goes live. This prevents a
    false abort in the first 7 seconds of Terrier operation.
    """

    def _terrier_state(self, lf=360.0, apo_km=25.0, pe_km=-587.0, met=63.0):
        return {
            "altitude":     15_000.0,
            "apoapsis":     apo_km * 1000,
            "periapsis":    pe_km  * 1000,
            "mission_time": met,
            "solid_fuel":    0.0,
            "liquid_fuel":  lf,
            "throttle":      1.0,
            "pitch":         50.0,
            "velocity":     631.0,
        }

    # -- First order: ABORT must not fire at T+63 with any reasonable fuel level --
    def test_p105_abort_not_at_ignition_nominal_fuel(self):
        """
        At Terrier ignition (MET=63s) with nominal fuel (360 units = 100%),
        Pe=-587km and Ap=25km — both completely normal.
        ABORT must not fire regardless of the apoapsis and periapsis readings.
        """
        state = self._terrier_state(lf=360.0, apo_km=25.0, pe_km=-587.0, met=63.0)
        adv = generate_advisory(state, FlightPhase.TERRIER)
        self.assertNotEqual(adv.level, "ABORT",
            f"ABORT fired at T+63s (Terrier ignition) with 100% fuel. "
            f"Got: '{adv.action}'. "
            f"Fix: guard abort with met > 70 or equivalent MET check.")

    # -- First order: ABORT must not fire at T+65 even with partial fuel --
    def test_p105_abort_not_at_t65_partial_fuel(self):
        """
        At T+65s (2s into Terrier burn), if fuel reads 270/360 (75%) — perhaps
        due to sensor lag — Pe is still -587km and Ap is still near 25km.
        ABORT must not fire: this is the normal state 2 seconds post-ignition.
        """
        state = self._terrier_state(lf=270.0, apo_km=26.0, pe_km=-580.0, met=65.0)
        adv = generate_advisory(state, FlightPhase.TERRIER)
        self.assertNotEqual(adv.level, "ABORT",
            f"ABORT fired at T+65s with 75% fuel. Got: '{adv.action}'. "
            f"Fix: ABORT gate must not activate in the first ~7s of Terrier burn.")

    # -- Second order: legitimate abort still fires when conditions truly warrant it --
    def test_p105_abort_fires_legitimately_at_low_fuel_late_burn(self):
        """
        At T+120s (well into the Terrier burn) with:
        - lf = 85 units (23.6% of 360 — genuinely low)
        - Apoapsis stalled at 32km (not rising)
        - Pe = -450km (hasn't improved)
        ABORT must fire — this represents a genuine no-orbit-achievable state.
        """
        state = self._terrier_state(lf=85.0, apo_km=32.0, pe_km=-450.0, met=120.0)
        adv = generate_advisory(state, FlightPhase.TERRIER)
        self.assertEqual(adv.level, "ABORT",
            f"ABORT did not fire at T+120s with 23.6% fuel and stalled trajectory. "
            f"Got: '{adv.level}' — '{adv.action}'. "
            f"Fix: ABORT gate must still fire when conditions genuinely warrant it.")

    # -- Third order: false abort followed by legitimate abort still works --
    def test_p105_abort_is_not_masked_after_guard_clears(self):
        """
        JAMES OKAFOR (FC): The guard preventing early ABORT must not prevent
        a legitimate ABORT once the guard window has expired. This tests that
        the fix doesn't over-suppress the abort.
        """
        # Early: should not abort
        early = self._terrier_state(lf=85.0, apo_km=24.0, pe_km=-587.0, met=65.0)
        early_adv = generate_advisory(early, FlightPhase.TERRIER)
        # Late: should abort
        late  = self._terrier_state(lf=85.0, apo_km=24.0, pe_km=-587.0, met=120.0)
        late_adv = generate_advisory(late, FlightPhase.TERRIER)
        self.assertNotEqual(early_adv.level, "ABORT",
            f"Early ABORT (T+65s) must be suppressed by guard. "
            f"Got: '{early_adv.action}'.")
        self.assertEqual(late_adv.level, "ABORT",
            f"Late ABORT (T+120s) must fire. Got: '{late_adv.level}'.")


# ---------------------------------------------------------------------------
# P1-01  CLI extra-payload default mismatch
# ---------------------------------------------------------------------------

class TestP101CLIDefaultConsistency(unittest.TestCase):
    """
    VehicleConfig.extra_payload now defaults to 0.0 (P0-05 fix).
    The CLI argparser in ascent_sim.py must use the same default,
    otherwise `python -m sim.ascent_sim` reports 14.31t while
    `VehicleConfig()` gives 14.21t — same codebase, different results.
    """

    def test_p101_cli_default_matches_vehicle_config_default(self):
        """
        The CLI --extra-payload default must equal VehicleConfig.extra_payload.
        """
        from sim.ascent_sim import build_argparser
        parser = build_argparser()
        args = parser.parse_args([])  # no args — all defaults
        cfg = VehicleConfig()
        self.assertAlmostEqual(args.extra_payload, cfg.extra_payload, delta=0.001,
            msg=f"CLI default extra_payload={args.extra_payload} != "
                f"VehicleConfig default={cfg.extra_payload}. "
                f"Fix: set argparse default to match VehicleConfig default (0.0).")

    def test_p101_cli_liftoff_mass_matches_vehicle_config(self):
        """
        With default arguments, the CLI must build a VehicleConfig whose
        liftoff_mass_t matches VehicleConfig() directly.
        """
        from sim.ascent_sim import build_argparser
        parser = build_argparser()
        args = parser.parse_args([])
        cfg_from_cli = VehicleConfig(
            booster_type=args.booster,
            n_boosters=args.n_boosters,
            booster_pct=args.booster_pct,
            extra_payload=args.extra_payload,
        )
        cfg_direct = VehicleConfig()
        self.assertAlmostEqual(cfg_from_cli.liftoff_mass_t,
                               cfg_direct.liftoff_mass_t, delta=0.001,
            msg=f"CLI-constructed mass={cfg_from_cli.liftoff_mass_t:.3f}t != "
                f"direct VehicleConfig mass={cfg_direct.liftoff_mass_t:.3f}t. "
                f"Ensure CLI defaults match VehicleConfig defaults.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
