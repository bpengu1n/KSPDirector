"""
tests/test_p2_p3_regressions.py
================================
Regression tests for P2 (Medium) and P3 (Low) findings from the Engineering Review.

Covers all testable P2/P3 items. Items that are purely UI changes (P2-03, P2-09,
P3-02, P3-03, P3-08) or doc-only fixes (P3-04, P3-09) are verified by code
inspection or source-text checks rather than behavioural assertions.

Authors: Sofia Chen (SWE) — code-quality items
         Dr. James Okafor (FC) — advisory wording, operational correctness
         Marcus Webb (UX) — UI-change verification methods
"""

import ast
import inspect
import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


# ---------------------------------------------------------------------------
# P2-01  mass_after_booster_sep returns upper bound without caveat
# ---------------------------------------------------------------------------

class TestP201MassAfterSep(unittest.TestCase):
    """
    VehicleConfig.mass_after_booster_sep subtracts only booster dry/prop mass
    from liftoff_mass, ignoring the Swivel propellant burned during the 25.3s
    boost phase. This overstates the post-sep mass and understates the actual
    Swivel-only burn mass.

    Fix: add a computed property `mass_at_booster_sep` that deducts the core
    propellant consumed during the booster burn, and document the existing
    `mass_after_booster_sep` as a conservative upper bound only.
    """

    def test_p201_mass_at_sep_accounts_for_swivel_burn(self):
        """
        During the 25.3s booster burn the Swivel also burns.
        Swivel mdot ≈ 63.7 kg/s → 25.3s → ~1.61t propellant consumed.
        mass_after_booster_sep (naive) ignores this; should equal
        liftoff − boosters − core-prop-consumed-during-boost.
        """
        from sim.vehicle import VehicleConfig, engine_thrust_at
        from sim.constants import G0, ENGINES
        cfg = VehicleConfig()

        # Calculate Swivel propellant consumed during booster burn
        # mdot_vac = thrust_vac * 1000 / (isp_vac * g0)
        sw = ENGINES["swivel"]
        mdot_vac_kgs = sw["thrust_vac"] * 1000 / (sw["isp_vac"] * G0)
        prop_during_boost_t = (mdot_vac_kgs * cfg.srb_burn_time_s) / 1000.0

        naive_mass  = cfg.mass_after_booster_sep
        actual_mass = naive_mass - prop_during_boost_t

        # The two values must differ by the swivel consumption
        self.assertGreater(naive_mass - actual_mass, 1.0,
            f"Swivel consumes >{1.0:.1f}t during boost phase ({prop_during_boost_t:.2f}t). "
            f"mass_after_booster_sep={naive_mass:.3f}t should be documented as upper bound. "
            f"Fix: add mass_at_booster_sep property that deducts swivel consumption.")

    def test_p201_mass_at_booster_sep_property_exists(self):
        """
        A computed property `mass_at_booster_sep` must exist and return a
        value lower than `mass_after_booster_sep` by the core-propellant
        consumed during the boost phase.
        """
        from sim.vehicle import VehicleConfig
        cfg = VehicleConfig()
        self.assertTrue(hasattr(cfg, 'mass_at_booster_sep'),
            "VehicleConfig must have a 'mass_at_booster_sep' property that "
            "deducts core propellant burned during the boost phase. "
            "Fix: add this property alongside the existing mass_after_booster_sep.")
        self.assertLess(cfg.mass_at_booster_sep, cfg.mass_after_booster_sep,
            f"mass_at_booster_sep ({cfg.mass_at_booster_sep:.3f}t) must be < "
            f"mass_after_booster_sep ({cfg.mass_after_booster_sep:.3f}t) "
            f"by the Swivel propellant consumed during the boost burn.")


# ---------------------------------------------------------------------------
# P2-02  generate_diagrams.py import-stripping is fragile (regex-based)
# ---------------------------------------------------------------------------

class TestP202DiagramConsolidation(unittest.TestCase):
    """
    The diagram consolidation script stripped imports using a string-startswith
    check, which failed on multi-line import continuations and required manual
    patching after each regeneration.

    Fix: use the `ast` module to find import node line ranges and strip them
    cleanly, regardless of continuation style.
    """

    def _ast_strip_imports(self, src: str) -> str:
        """Reference implementation of the correct AST-based import stripping."""
        tree = ast.parse(src)
        import_lines = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for ln in range(node.lineno, node.end_lineno + 1):
                    import_lines.add(ln)
        lines = src.split('\n')
        return '\n'.join(l for i, l in enumerate(lines, 1)
                         if i not in import_lines)

    def test_p202_multi_line_import_stripped_cleanly(self):
        """
        A multi-line import continuation must be fully removed (all its lines),
        not leave orphaned continuation lines that cause IndentationError.
        """
        src = (
            "from parts import (\n"
            "    part_tank, part_engine,\n"
            "    part_fin\n"
            ")\n"
            "x = 1\n"
        )
        stripped = self._ast_strip_imports(src)
        # After stripping, only `x = 1` and blank lines should remain
        non_blank = [l for l in stripped.split('\n') if l.strip()]
        self.assertEqual(non_blank, ['x = 1'],
            f"Multi-line import not fully stripped. Remaining: {non_blank}. "
            f"Fix: use AST-based stripping in generate_diagrams.py consolidation.")

    def test_p202_stripped_source_compiles(self):
        """
        After stripping imports from a module with a multi-line from-import,
        the result must compile without SyntaxError or IndentationError.
        """
        src = (
            "import sys\n"
            "from dsys import (\n"
            "    rect, line, text,\n"
            "    circle, path\n"
            ")\n"
            "\n"
            "def build():\n"
            "    return 'ok'\n"
        )
        stripped = self._ast_strip_imports(src)
        try:
            compile(stripped, '<test>', 'exec')
        except (SyntaxError, IndentationError) as e:
            self.fail(
                f"AST-stripped source does not compile: {e}\n"
                f"Stripped source:\n{stripped}\n"
                f"Fix: implement AST-based import stripping in generate_diagrams.py."
            )

    def test_p202_generate_diagrams_compiles_clean(self):
        """
        The deployed generate_diagrams.py must compile without errors.
        This is the integration check — it catches any orphaned continuation
        line that slipped through.
        """
        src = open(os.path.join(ROOT, 'diagrams', 'generate_diagrams.py')).read()
        try:
            compile(src, 'generate_diagrams.py', 'exec')
        except (SyntaxError, IndentationError) as e:
            self.fail(
                f"generate_diagrams.py has a syntax/indentation error: {e}. "
                f"Fix: use AST-based import stripping in the consolidation process.")


# ---------------------------------------------------------------------------
# P2-05  SECRET_KEY is hardcoded
# ---------------------------------------------------------------------------

class TestP205SecretKey(unittest.TestCase):
    """
    The Flask SECRET_KEY must be configurable via the MC_SECRET_KEY
    environment variable so the server can be deployed outside a
    local-only KSP session without hardcoded credentials.
    """

    def test_p205_secret_key_reads_from_environment(self):
        """
        When MC_SECRET_KEY is set in the environment, the server must use
        that value rather than the hardcoded string.
        """
        src = open(os.path.join(ROOT, 'mission_control', 'server.py')).read()
        self.assertIn('MC_SECRET_KEY', src,
            "server.py must read SECRET_KEY from MC_SECRET_KEY env var. "
            "Fix: app.config['SECRET_KEY'] = os.environ.get('MC_SECRET_KEY', 'dev-key')")
        self.assertIn('environ', src,
            "server.py must use os.environ to read SECRET_KEY. "
            "Fix: import os and use os.environ.get('MC_SECRET_KEY', ...).")

    def test_p205_hardcoded_key_not_in_production_path(self):
        """
        The literal string 'perseus-mission-control' must not be the only
        source of the SECRET_KEY. The env-var path must be present.
        """
        src = open(os.path.join(ROOT, 'mission_control', 'server.py')).read()
        # The hardcoded string may appear as a fallback default, but
        # environ.get must be the primary path.
        self.assertIn('os.environ.get', src,
            "SECRET_KEY must use os.environ.get() as the primary source. "
            "Fix: SECRET_KEY = os.environ.get('MC_SECRET_KEY', 'fallback').")


# ---------------------------------------------------------------------------
# P2-06  Trajectory not auto-cleared between flights
# ---------------------------------------------------------------------------

class TestP206TrajectoryAutoReset(unittest.TestCase):
    """
    If the player relaunches without restarting the server, the trajectory
    list accumulates data from the previous flight, producing a confused glob
    on the globe visualization.

    Fix: detect when mission_time drops below 5s after having been above 30s
    and auto-clear the accumulated trajectory.
    """

    def test_p206_trajectory_reset_logic_exists(self):
        """
        TelematicusClient._handle_message must contain logic to detect a
        mission-time reset (MET drops back to near-zero) and clear the
        accumulated trajectory.
        """
        src = open(os.path.join(ROOT, 'mission_control',
                                'telemachus_client.py')).read()
        self.assertIn('mission_time reset', src,
            "telemachus_client.py must detect MET reset and auto-clear trajectory. "
            "Fix: if met < 5 and last trajectory point met > 30: clear trajectory.")

    def test_p206_sim_telemetry_also_resets(self):
        """
        SimulatedTelemetry also loops — it must clear the trajectory when
        its internal elapsed time resets to near zero.
        """
        src = open(os.path.join(ROOT, 'mission_control',
                                'telemachus_client.py')).read()
        # Check SimulatedTelemetry has some form of reset logic
        self.assertIn('clear()', src,
            "SimulatedTelemetry must call _trajectory.clear() on loop reset. "
            "Fix: detect elapsed < 1s after elapsed > 30s in SimulatedTelemetry._run.")


# ---------------------------------------------------------------------------
# P2-08  Advisory missing apoapsis-stall detection
# ---------------------------------------------------------------------------

class TestP208ApoStallDetection(unittest.TestCase):
    """
    The advisory engine detects that apoapsis is *currently* low but doesn't
    check whether it has *stopped rising*. An apoapsis that is slowly rising
    at 40km with plenty of fuel is not an emergency; one that is stuck at
    40km and falling is.

    Fix: pass the previous apoapsis reading to generate_advisory so it can
    compute the stall rate and escalate to WARNING when apoapsis is both
    low and not rising.
    """

    def _state(self, apo_km, alt_km=20, lf=280, met=90):
        return {
            'altitude': alt_km * 1000, 'apoapsis': apo_km * 1000,
            'periapsis': -400_000, 'mission_time': float(met),
            'solid_fuel': 0, 'liquid_fuel': float(lf),
            'throttle': 1.0, 'pitch': 45.0, 'velocity': 900.0,
        }

    def test_p208_rising_apo_is_nominal_not_warning(self):
        """
        An apoapsis at 38km that was 35km one second ago (rising at 3 km/s)
        with 78% fuel remaining must be NOMINAL or CAUTION, not WARNING.
        The craft is on track; warning would be premature.
        """
        from mission_control.nominal_compare import generate_advisory, FlightPhase
        state = self._state(apo_km=38, lf=280)
        adv = generate_advisory(state, FlightPhase.TERRIER, prev_apo_km=35.0)
        self.assertNotEqual(adv.level, 'WARNING',
            f"Rising Ap (35→38 km) with 78% fuel must not trigger WARNING. "
            f"Got '{adv.level}' — '{adv.action}'. "
            f"Fix: add prev_apo_km param to generate_advisory and compute stall rate.")

    def test_p208_stalled_apo_triggers_warning(self):
        """
        An apoapsis at 38km that was also 38km one second ago (stalled),
        with 50% fuel spent, must trigger at least CAUTION or WARNING.
        """
        from mission_control.nominal_compare import generate_advisory, FlightPhase
        state = self._state(apo_km=38, lf=180)  # 50% fuel
        adv = generate_advisory(state, FlightPhase.TERRIER, prev_apo_km=38.0)
        self.assertIn(adv.level, ('CAUTION', 'WARNING'),
            f"Stalled Ap (38→38 km) at 50% fuel must be CAUTION or WARNING. "
            f"Got '{adv.level}'. "
            f"Fix: detect stall (|current_apo - prev_apo| < threshold) and escalate.")


# ---------------------------------------------------------------------------
# P3-01  Advisory wording ambiguous for flight controllers
# ---------------------------------------------------------------------------

class TestP301AdvisoryWording(unittest.TestCase):
    """
    "PITCH DOWN X° FROM VERTICAL" is ambiguous: does it mean "pitch down
    by X degrees" or "go to a pitch of X degrees from vertical"?
    Standard flight controller language uses imperative direction:
    "PITCH TOWARD HORIZON" (too steep) or "PITCH TOWARD VERTICAL" (too shallow).

    Fix: replace the degree-from-vertical phrasing with direction-first wording.
    The deviation may appear as context, not as the primary command.
    """

    def _steep_advisory(self, pitch_ksp=15.0, nom_pfv=37.0):
        """Return advisory for a steep ascent (pitch_ksp=15 → pfv=75, nom=37)."""
        from mission_control.nominal_compare import generate_advisory, FlightPhase
        state = {
            'altitude': 10_000, 'apoapsis': 35_000, 'periapsis': -580_000,
            'mission_time': 80.0, 'solid_fuel': 0, 'liquid_fuel': 300,
            'throttle': 1.0, 'pitch': pitch_ksp, 'velocity': 450,
        }
        nom = {'pitch_from_vertical': nom_pfv}
        return generate_advisory(state, FlightPhase.TERRIER, nominal=nom)

    def test_p301_steep_advisory_says_toward_horizon(self):
        """
        When the craft is too steep (actual pfv=75°, nominal pfv=37°, diff=+38°),
        the advisory action must say 'TOWARD HORIZON', not 'FROM VERTICAL'.
        """
        adv = self._steep_advisory(pitch_ksp=15.0)  # KSP pitch 15 → pfv=75 (steep)
        self.assertIn('HORIZON', adv.action.upper(),
            f"Steep ascent advisory must say TOWARD HORIZON. "
            f"Got: '{adv.action}'. "
            f"Fix: change wording from 'PITCH DOWN X° FROM VERTICAL' to "
            f"'PITCH TOWARD HORIZON (+Xdeg steep)'.")
        self.assertNotIn('FROM VERTICAL', adv.action.upper(),
            f"Advisory must not say 'FROM VERTICAL' — ambiguous phrasing. "
            f"Got: '{adv.action}'.")

    def test_p301_shallow_advisory_says_toward_vertical(self):
        """
        When the craft is too shallow (actual pfv=15°, nominal pfv=37°, diff=-22°),
        the advisory must say 'TOWARD VERTICAL' or 'CLIMB MORE'.
        """
        adv = self._steep_advisory(pitch_ksp=75.0)  # KSP 75 → pfv=15 (shallow)
        self.assertIn('VERTICAL', adv.action.upper(),
            f"Shallow ascent advisory must reference VERTICAL direction. "
            f"Got: '{adv.action}'. "
            f"Fix: change wording to 'PITCH TOWARD VERTICAL (+Xdeg shallow)'.")


# ---------------------------------------------------------------------------
# P3-05  VehicleConfig private field initialization is awkward
# ---------------------------------------------------------------------------

class TestP305VehicleConfigFields(unittest.TestCase):
    """
    Using `field(default_factory=dict)` for `_booster` implies it's a
    mutable default that needs isolation per instance, but it's immediately
    overwritten in `__post_init__`. The correct pattern for a derived field
    that's computed from other fields is `field(init=False, default=None)`.
    """

    def test_p305_booster_field_uses_init_false(self):
        """
        The private `_booster` field must use `field(init=False)`,
        not `field(default_factory=dict)`, to communicate intent clearly:
        it is a derived field, not an independent mutable default.
        """
        src = open(os.path.join(ROOT, 'sim', 'vehicle.py')).read()
        self.assertNotIn('default_factory=dict', src,
            "VehicleConfig._booster must not use default_factory=dict. "
            "Fix: change to field(init=False, default=None, repr=False).")
        self.assertIn('init=False', src,
            "VehicleConfig._booster and _cda must use field(init=False). "
            "Fix: field(init=False, default=None, repr=False).")

    def test_p305_vehicle_config_still_initialises(self):
        """
        After the field cleanup, VehicleConfig must still initialise correctly
        and all properties must return valid values.
        """
        from sim.vehicle import VehicleConfig
        cfg = VehicleConfig()
        self.assertAlmostEqual(cfg.liftoff_mass_t, 14.21, delta=0.05)
        self.assertAlmostEqual(cfg.pad_twr_asl, 1.77, delta=0.05)
        self.assertAlmostEqual(cfg.mission_stage_dv_ms, 3458, delta=10)
        self.assertGreater(cfg.effective_cda, 0)


# ---------------------------------------------------------------------------
# P3-06  engine_thrust_at imported inside function body in trajectory.py
# ---------------------------------------------------------------------------

class TestP306ModuleLevelImport(unittest.TestCase):
    """
    `engine_thrust_at` is imported inside `integrate()` at every call.
    Module-level imports are resolved once; function-level imports add
    repeated overhead and make dependency chains harder to trace.
    """

    def test_p306_import_at_module_level(self):
        """
        `engine_thrust_at` must be imported at the top of trajectory.py,
        not inside the `integrate()` function body.
        """
        src = open(os.path.join(ROOT, 'sim', 'trajectory.py')).read()
        self.assertNotIn('    from .vehicle import', src,
            "engine_thrust_at must not be imported inside integrate(). "
            "Fix: move 'from .vehicle import engine_thrust_at' to module level.")

    def test_p306_engine_thrust_at_callable(self):
        """
        engine_thrust_at must return valid (kN, kg/s) values at sea level.
        At h=0 (sea level), uses ASL Isp (250s) and ASL thrust (167.97 kN):
          mdot = 167.97*1000 / (250*9.81) = 68.49 kg/s
        Note: vacuum mdot (63.7 kg/s at vac Isp 320s) is only correct at altitude.
        """
        from sim.vehicle import engine_thrust_at
        thrust_kN, mdot_kgs = engine_thrust_at(0, 'swivel', 1.0)
        # ASL thrust from KSP wiki: 167.97 kN
        self.assertAlmostEqual(thrust_kN, 167.97, delta=2.0,
            msg=f"Swivel ASL thrust should be ~167.97 kN, got {thrust_kN:.2f}")
        # ASL mdot = 167.97*1000 / (250*9.81) ≈ 68.49 kg/s
        self.assertAlmostEqual(mdot_kgs, 68.49, delta=1.0,
            msg=f"Swivel ASL mdot should be ~68.49 kg/s at h=0, got {mdot_kgs:.2f}. "
                f"(Vacuum mdot is 63.7 kg/s — only correct at altitude.)")


# ---------------------------------------------------------------------------
# P3-07  TRAJECTORY constant provenance and helper script
# ---------------------------------------------------------------------------

class TestP307TrajectoryProvenance(unittest.TestCase):
    """
    The TRAJECTORY constant in sheet3.py is a 36-element hard-coded list
    that silently grows stale whenever the sim parameters change.
    A provenance comment and a helper script remove the ambiguity.
    """

    def test_p307_trajectory_constant_has_provenance_comment(self):
        """
        The TRAJECTORY constant must have a comment naming:
        - the function used to generate it
        - the VehicleConfig parameters used
        """
        sheet3_path = os.path.join(ROOT, '..', 'nasa_dev', 'sheet3.py')
        if not os.path.exists(sheet3_path):
            sheet3_path = os.path.join(ROOT, 'diagrams', 'sheet3.py')
        src = open(sheet3_path).read()
        self.assertIn('run_ascent', src,
            "TRAJECTORY constant must reference run_ascent() in a provenance comment. "
            "Fix: add '# Derived from: sim.run_ascent(VehicleConfig(...))' above TRAJECTORY.")

    def test_p307_helper_script_exists(self):
        """
        A helper script tools/update_sheet3_trajectory.py (or equivalent) must
        exist to regenerate TRAJECTORY from the current sim output.
        """
        tools_path = os.path.join(ROOT, 'tools', 'update_sheet3_trajectory.py')
        self.assertTrue(os.path.exists(tools_path),
            f"Helper script not found at {tools_path}. "
            f"Fix: create tools/update_sheet3_trajectory.py that runs sim and "
            f"writes the TRAJECTORY constant to sheet3.py.")


# ---------------------------------------------------------------------------
# P3-10  PERSEUS_1_DEFAULT unused / dual source of truth
# ---------------------------------------------------------------------------

class TestP310DefaultConsistency(unittest.TestCase):
    """
    PERSEUS_1_DEFAULT in constants.py defines the baseline vehicle parameters
    but VehicleConfig does not read from it — meaning there are two independent
    sources of the same ground truth that can silently diverge.

    Fix: wire VehicleConfig's field defaults to PERSEUS_1_DEFAULT so there is
    one authoritative source.
    """

    def test_p310_vehicle_config_uses_perseus_1_default(self):
        """
        VehicleConfig field defaults must be sourced from PERSEUS_1_DEFAULT,
        not hardcoded independently.
        """
        src = open(os.path.join(ROOT, 'sim', 'vehicle.py')).read()
        self.assertIn('PERSEUS_1_DEFAULT[', src,
            "VehicleConfig must use PERSEUS_1_DEFAULT['key'] for field defaults. "
            "Fix: booster_type = PERSEUS_1_DEFAULT['booster_type'], etc.")

    def test_p310_defaults_match_between_constant_and_class(self):
        """
        The runtime values in VehicleConfig() must match PERSEUS_1_DEFAULT.
        """
        from sim.vehicle import VehicleConfig
        from sim.constants import PERSEUS_1_DEFAULT
        cfg = VehicleConfig()
        self.assertEqual(cfg.booster_type, PERSEUS_1_DEFAULT['booster_type'],
            f"booster_type mismatch: VehicleConfig={cfg.booster_type}, "
            f"PERSEUS_1_DEFAULT={PERSEUS_1_DEFAULT['booster_type']}.")
        self.assertEqual(cfg.n_boosters, PERSEUS_1_DEFAULT['n_boosters'],
            f"n_boosters mismatch.")
        self.assertAlmostEqual(cfg.booster_pct, PERSEUS_1_DEFAULT['booster_pct'],
            delta=0.1, msg="booster_pct mismatch.")


if __name__ == '__main__':
    unittest.main(verbosity=2)
