"""
tests/test_ballistic_projection.py
====================================
Regression tests for the ballistic trajectory projection engine added to the
mission control visualization (index.html).

The projection uses 2D gravity-turn equations over spherical Kerbin with a
centripetal correction term to predict unpowered coast arcs from any given
state vector. These tests validate a Python reference implementation of the
same equations against the sim's analytical orbital_params() and known
KSP orbital mechanics.

Test categories:
  - Physics accuracy: projection apoapsis matches orbital_params analytical solution
  - Centripetal term: without it, circular orbits incorrectly dive
  - Velocity dependence: projection must use actual velocity, not ignore it
  - Ground impact: suborbital arcs terminate at altitude = 0
  - Nominal coast extension: post-burnout coast reaches expected apoapsis
  - Edge cases: near-zero velocity, vertical ascent, escape trajectories

Authors: Flight Dynamics (FIDO) validation — orbital mechanics assertions
         SWE — integration fidelity, edge cases
"""

import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sim.constants import MU_KERBIN, R_KERBIN
from sim.trajectory import orbital_params, gravity


# ---------------------------------------------------------------------------
# Python reference implementation of the JS ballistic projection
# ---------------------------------------------------------------------------
# Mirrors projectBallisticArc() from index.html exactly — same integration
# order, same equations, same constants. If the JS diverges from this, the
# test documents the intended behavior.

def project_ballistic_arc(alt_m, v_horiz, v_vert, dr_km=0.0,
                          dt=2.0, max_steps=300,
                          include_centripetal=True):
    """
    Propagate a ballistic (unpowered) arc from a given state vector.

    Returns list of dicts: [{altitude_km, downrange_km}, ...].
    Matches the JS implementation in index.html.
    """
    R = R_KERBIN
    MU = MU_KERBIN

    h = alt_m
    dr = dr_km * 1000.0
    v = math.sqrt(v_horiz**2 + v_vert**2)
    gamma = math.atan2(v_vert, v_horiz)

    if v < 1 or h < 50:
        return []

    pts = [{"altitude_km": h / 1000.0, "downrange_km": dr / 1000.0}]

    for _ in range(max_steps):
        r = R + h
        g = MU / (r * r)
        sinG = math.sin(gamma)
        cosG = math.cos(gamma)

        # Position update first (current v, gamma)
        h += v * sinG * dt
        dr += v * cosG * dt

        # Velocity update
        v += (-g * sinG) * dt
        if include_centripetal:
            gamma += (cosG * (v / r - g / v)) * dt
        else:
            gamma += (-g * cosG / v) * dt

        if v < 0.5:
            break

        if h <= 0:
            pts.append({"altitude_km": 0, "downrange_km": dr / 1000.0})
            break

        pts.append({"altitude_km": h / 1000.0, "downrange_km": dr / 1000.0})
        if h > 200000:
            break

    return pts


def arc_max_altitude(pts):
    """Return peak altitude (km) from a projection arc."""
    return max(p["altitude_km"] for p in pts) if pts else 0


def arc_endpoint(pts):
    """Return the last point of a projection arc."""
    return pts[-1] if pts else None


# ---------------------------------------------------------------------------
# Core burnout state (from CLAUDE.md verified numbers)
# ---------------------------------------------------------------------------

BURNOUT_ALT_M = 14880.0
BURNOUT_VEL = 643.0
BURNOUT_PFV_DEG = 50.0      # pitch from vertical
BURNOUT_GAMMA_RAD = math.radians(90.0 - BURNOUT_PFV_DEG)  # 40° from horiz
BURNOUT_VH = BURNOUT_VEL * math.cos(BURNOUT_GAMMA_RAD)    # ~492 m/s
BURNOUT_VV = BURNOUT_VEL * math.sin(BURNOUT_GAMMA_RAD)    # ~413 m/s
BURNOUT_DR_KM = 8.31


# ---------------------------------------------------------------------------
# Test: projection apoapsis matches analytical orbital_params
# ---------------------------------------------------------------------------

class TestProjectionApoapsis(unittest.TestCase):
    """
    The ballistic projection's peak altitude must agree with the analytical
    apoapsis from orbital_params() to within integration tolerance.
    This is the primary accuracy check.
    """

    def test_burnout_apoapsis_matches_orbital_params(self):
        """
        From core burnout state (14.88km, 643 m/s, 40° gamma):
        orbital_params gives ~24.6 km apoapsis.
        The projection must reach within 1 km of this.
        """
        apo_analytical, _ = orbital_params(
            BURNOUT_ALT_M, BURNOUT_VEL, BURNOUT_GAMMA_RAD
        )
        pts = project_ballistic_arc(
            BURNOUT_ALT_M, BURNOUT_VH, BURNOUT_VV, BURNOUT_DR_KM
        )
        apo_projected = arc_max_altitude(pts)

        self.assertAlmostEqual(apo_projected, apo_analytical, delta=1.0,
            msg=f"Projection apoapsis ({apo_projected:.1f} km) must match "
            f"orbital_params ({apo_analytical:.1f} km) within 1 km. "
            f"This validates the gravity-turn integrator against the "
            f"analytical vis-viva solution.")

    def test_higher_velocity_gives_higher_apoapsis(self):
        """
        Increasing velocity at the same altitude and angle must raise apoapsis.
        Validates that the projection responds to velocity magnitude.
        """
        v_low = 500.0
        v_high = 800.0
        gamma = math.radians(40.0)

        pts_low = project_ballistic_arc(
            15000, v_low * math.cos(gamma), v_low * math.sin(gamma)
        )
        pts_high = project_ballistic_arc(
            15000, v_high * math.cos(gamma), v_high * math.sin(gamma)
        )

        apo_low = arc_max_altitude(pts_low)
        apo_high = arc_max_altitude(pts_high)

        self.assertGreater(apo_high, apo_low + 5.0,
            f"Higher velocity ({v_high} m/s) must produce higher apoapsis "
            f"({apo_high:.1f} km) than lower velocity ({v_low} m/s, "
            f"{apo_low:.1f} km). Projection must use actual velocity.")

    def test_shallow_angle_gives_more_downrange(self):
        """
        A shallower flight path angle (more horizontal) at the same speed
        should produce more downrange distance before impact.
        """
        v = 643.0
        gamma_steep = math.radians(60.0)
        gamma_shallow = math.radians(20.0)

        pts_steep = project_ballistic_arc(
            15000,
            v * math.cos(gamma_steep), v * math.sin(gamma_steep)
        )
        pts_shallow = project_ballistic_arc(
            15000,
            v * math.cos(gamma_shallow), v * math.sin(gamma_shallow)
        )

        ep_steep = arc_endpoint(pts_steep)
        ep_shallow = arc_endpoint(pts_shallow)

        self.assertGreater(
            ep_shallow["downrange_km"], ep_steep["downrange_km"] + 5.0,
            f"Shallow angle (20°) must reach further downrange "
            f"({ep_shallow['downrange_km']:.1f} km) than steep angle (60°, "
            f"{ep_steep['downrange_km']:.1f} km).")


# ---------------------------------------------------------------------------
# Test: centripetal correction term is essential
# ---------------------------------------------------------------------------

class TestCentripetalCorrection(unittest.TestCase):
    """
    The centripetal term (v·cos γ / r) in dγ/dt accounts for the changing
    direction of "down" as the craft moves around the planet. Without it:
    - A circular orbit incorrectly shows gamma decreasing (dive)
    - Coast arcs are systematically too steep
    - Projected apoapsis is underestimated

    This was the root cause of the old projection "dropping off."
    """

    def test_circular_orbit_stays_level(self):
        """
        At circular orbital velocity (gamma=0, v=v_circ), the flight-path
        angle must remain near zero. Without the centripetal term, gamma
        would go negative at ~0.004 rad/s, showing a nonexistent dive.
        """
        h = 80000.0
        r = R_KERBIN + h
        v_circ = math.sqrt(MU_KERBIN / r)

        pts = project_ballistic_arc(h, v_circ, 0.0, dt=2.0, max_steps=150)

        min_alt = min(p["altitude_km"] for p in pts)
        max_alt = max(p["altitude_km"] for p in pts)

        self.assertGreater(min_alt, 75.0,
            f"Circular orbit at 80 km must not descend below 75 km. "
            f"Got min altitude {min_alt:.1f} km. "
            f"This indicates the centripetal term is missing or wrong — "
            f"without it, gamma drifts negative and the orbit appears to dive.")
        self.assertLess(max_alt, 85.0,
            f"Circular orbit at 80 km must not rise above 85 km. "
            f"Got max altitude {max_alt:.1f} km.")

    def test_without_centripetal_orbit_dives(self):
        """
        Confirms that removing the centripetal term causes a circular orbit
        to incorrectly dive. This is the bug the projection fix addresses.
        """
        h = 80000.0
        r = R_KERBIN + h
        v_circ = math.sqrt(MU_KERBIN / r)

        pts_bad = project_ballistic_arc(
            h, v_circ, 0.0, dt=2.0, max_steps=150,
            include_centripetal=False
        )

        min_alt_bad = min(p["altitude_km"] for p in pts_bad)

        self.assertLess(min_alt_bad, 50.0,
            f"WITHOUT centripetal term, circular orbit must incorrectly dive. "
            f"Got min altitude {min_alt_bad:.1f} km (expected < 50 km). "
            f"If this passes, the test validates that the centripetal term "
            f"is the fix for the 'projection drops off' bug.")

    def test_centripetal_improves_high_arc_accuracy(self):
        """
        For a high, near-orbital coast arc, the centripetal term must
        improve the apoapsis estimate. At suborbital velocities the term
        is only ~7% of the gravity term and Euler noise dominates; at
        near-orbital velocities (v/r comparable to g/v) it is essential.
        """
        h = 50000.0
        v = 1800.0
        gamma = math.radians(10.0)
        v_h = v * math.cos(gamma)
        v_v = v * math.sin(gamma)

        apo_analytical, _ = orbital_params(h, v, gamma)

        pts_with = project_ballistic_arc(
            h, v_h, v_v, include_centripetal=True
        )
        pts_without = project_ballistic_arc(
            h, v_h, v_v, include_centripetal=False
        )

        apo_with = arc_max_altitude(pts_with)
        apo_without = arc_max_altitude(pts_without)

        err_with = abs(apo_with - apo_analytical)
        err_without = abs(apo_without - apo_analytical)

        self.assertLess(err_with, err_without,
            f"Centripetal term must improve apoapsis accuracy for near-orbital arcs. "
            f"With: {apo_with:.1f} km (err {err_with:.1f}), "
            f"without: {apo_without:.1f} km (err {err_without:.1f}), "
            f"analytical: {apo_analytical:.1f} km.")


# ---------------------------------------------------------------------------
# Test: velocity dependence (old projection ignored velocity entirely)
# ---------------------------------------------------------------------------

class TestVelocityDependence(unittest.TestCase):
    """
    The old parabolic projection used alt = h0*(1-f²) which completely
    ignored the velocity vector. These tests confirm the new projection
    produces different arcs for different velocities at the same position.
    """

    def test_zero_horizontal_velocity_falls_straight_down(self):
        """
        A craft at 15 km with zero horizontal velocity and zero vertical
        velocity should produce no projection (below threshold).
        One with only vertical velocity should land near directly below.
        """
        pts_zero = project_ballistic_arc(15000, 0.0, 0.0)
        self.assertEqual(len(pts_zero), 0,
            "Zero velocity must produce empty projection.")

        pts_falling = project_ballistic_arc(15000, 0.0, -50.0)
        if pts_falling:
            ep = arc_endpoint(pts_falling)
            self.assertLess(ep["downrange_km"], 1.0,
                f"Purely vertical descent must land near launch site. "
                f"Got {ep['downrange_km']:.1f} km downrange.")

    def test_same_position_different_velocities_differ(self):
        """
        Two states at the same position but with different velocity vectors
        must produce visibly different arcs. The old parabolic projection
        would have produced identical arcs.
        """
        pts_a = project_ballistic_arc(15000, 400.0, 300.0)
        pts_b = project_ballistic_arc(15000, 200.0, 500.0)

        apo_a = arc_max_altitude(pts_a)
        apo_b = arc_max_altitude(pts_b)

        self.assertNotAlmostEqual(apo_a, apo_b, delta=2.0,
            msg=f"Different velocity vectors at same altitude must produce "
            f"different apoapsis. Got {apo_a:.1f} vs {apo_b:.1f} km. "
            f"A velocity-independent projection would give identical results.")


# ---------------------------------------------------------------------------
# Test: suborbital arc ground impact
# ---------------------------------------------------------------------------

class TestGroundImpact(unittest.TestCase):
    """
    Suborbital ballistic arcs must terminate at or below altitude = 0.
    The projection must show the complete arc from current position to impact.
    """

    def test_suborbital_arc_reaches_ground(self):
        """
        From core burnout (suborbital, Pe = -587 km), the projection
        must eventually reach altitude 0 (ground impact).
        """
        pts = project_ballistic_arc(
            BURNOUT_ALT_M, BURNOUT_VH, BURNOUT_VV, BURNOUT_DR_KM
        )

        ep = arc_endpoint(pts)
        self.assertIsNotNone(ep,
            "Suborbital arc must produce at least one point.")
        self.assertLessEqual(ep["altitude_km"], 0.05,
            f"Suborbital arc must reach ground (altitude ≤ 0). "
            f"Last point altitude: {ep['altitude_km']:.2f} km.")

    def test_impact_downrange_is_realistic(self):
        """
        From burnout at 8.31 km DR, 15 km alt, 643 m/s at 40° gamma,
        impact should be in the 50-100 km downrange range (suborbital hop).
        """
        pts = project_ballistic_arc(
            BURNOUT_ALT_M, BURNOUT_VH, BURNOUT_VV, BURNOUT_DR_KM
        )

        ep = arc_endpoint(pts)
        self.assertGreater(ep["downrange_km"], 40.0,
            f"Impact downrange ({ep['downrange_km']:.1f} km) is too short "
            f"for a 643 m/s suborbital arc from 15 km altitude.")
        self.assertLess(ep["downrange_km"], 120.0,
            f"Impact downrange ({ep['downrange_km']:.1f} km) is too far "
            f"for a suborbital arc with only 643 m/s.")


# ---------------------------------------------------------------------------
# Test: nominal coast extension
# ---------------------------------------------------------------------------

class TestNominalCoastExtension(unittest.TestCase):
    """
    The nominal trajectory from the sim ends at core burnout. The coast
    extension should continue the trajectory ballistically to show where
    the craft coasts after the Swivel burns out.
    """

    def test_coast_reaches_sim_apoapsis(self):
        """
        The coast extension from core burnout must reach an apoapsis
        close to the sim's reported 24.6 km. This validates that the
        coast extension correctly uses the burnout state vector.
        """
        pts = project_ballistic_arc(
            BURNOUT_ALT_M, BURNOUT_VH, BURNOUT_VV, BURNOUT_DR_KM
        )

        apo = arc_max_altitude(pts)
        self.assertAlmostEqual(apo, 24.6, delta=1.5,
            msg=f"Nominal coast apoapsis ({apo:.1f} km) must be close to "
            f"sim's reported 24.6 km.")

    def test_coast_starts_at_burnout_position(self):
        """
        The first point of the coast arc must be at the burnout position.
        """
        pts = project_ballistic_arc(
            BURNOUT_ALT_M, BURNOUT_VH, BURNOUT_VV, BURNOUT_DR_KM
        )

        self.assertGreater(len(pts), 2,
            "Coast extension must produce more than 2 points.")
        self.assertAlmostEqual(
            pts[0]["altitude_km"], BURNOUT_ALT_M / 1000.0, delta=0.1,
            msg="Coast must start at burnout altitude.")
        self.assertAlmostEqual(
            pts[0]["downrange_km"], BURNOUT_DR_KM, delta=0.1,
            msg="Coast must start at burnout downrange.")

    def test_coast_rises_then_falls(self):
        """
        With positive vertical velocity at burnout, the coast arc must
        first rise to apoapsis, then descend back to ground.
        """
        pts = project_ballistic_arc(
            BURNOUT_ALT_M, BURNOUT_VH, BURNOUT_VV, BURNOUT_DR_KM
        )

        alts = [p["altitude_km"] for p in pts]
        peak_idx = alts.index(max(alts))

        self.assertGreater(peak_idx, 0,
            "Arc must rise before reaching peak (peak should not be first point).")
        self.assertLess(peak_idx, len(alts) - 1,
            "Arc must descend after peak (peak should not be last point).")


# ---------------------------------------------------------------------------
# Test: gravity model consistency
# ---------------------------------------------------------------------------

class TestGravityConsistency(unittest.TestCase):
    """
    The projection must use the same gravity model as the sim:
    g(h) = μ / (R + h)². At sea level this gives 9.81 m/s², and at
    80 km it gives ~7.64 m/s².
    """

    def test_surface_gravity(self):
        """
        At h=0, g must equal μ/R² ≈ 9.81 m/s² (Kerbin standard).
        """
        g0 = MU_KERBIN / (R_KERBIN ** 2)
        self.assertAlmostEqual(g0, 9.81, delta=0.01,
            msg=f"Kerbin surface gravity must be ~9.81 m/s², got {g0:.3f}.")

    def test_gravity_decreases_with_altitude(self):
        """
        Gravity at 80 km must be measurably less than at the surface.
        g(80km) = μ / (680km)² ≈ 7.64 m/s².
        """
        g_surface = gravity(0)
        g_80km = gravity(80000)

        self.assertLess(g_80km, g_surface,
            f"Gravity must decrease with altitude: "
            f"g(0)={g_surface:.2f}, g(80km)={g_80km:.2f}.")
        self.assertAlmostEqual(g_80km, 7.64, delta=0.05,
            msg=f"g at 80 km should be ~7.64 m/s², got {g_80km:.2f}.")

    def test_circular_velocity_at_80km(self):
        """
        v_circ at 80 km = sqrt(μ/r) ≈ 2279 m/s (the CIRC_SPEED_80KM
        constant used in the UI).
        """
        r = R_KERBIN + 80000
        v_circ = math.sqrt(MU_KERBIN / r)
        self.assertAlmostEqual(v_circ, 2279, delta=2,
            msg=f"Circular velocity at 80 km should be ~2279 m/s, got {v_circ:.1f}.")


# ---------------------------------------------------------------------------
# Test: UI source code contains projection engine
# ---------------------------------------------------------------------------

class TestUIProjectionPresence(unittest.TestCase):
    """
    The mission control index.html must contain the ballistic projection
    engine and draw it on both the globe and trajectory plot canvases.
    """

    def _read_ui(self):
        with open(os.path.join(
            ROOT, 'mission_control', 'static', 'index.html'
        )) as f:
            return f.read()

    def test_projection_function_exists(self):
        """
        index.html must define projectBallisticArc() with proper
        gravity-turn equations.
        """
        src = self._read_ui()
        self.assertIn('projectBallisticArc', src,
            "index.html must contain the projectBallisticArc function.")
        self.assertIn('MU_KERBIN_PROJ', src,
            "index.html must use MU_KERBIN_PROJ (3.5316e12) for Kerbin's "
            "gravitational parameter.")

    def test_centripetal_term_present(self):
        """
        The projection must include the centripetal correction term
        (v/r in the gamma update). Without it, orbits incorrectly dive.
        """
        src = self._read_ui()
        self.assertIn('v / r', src,
            "index.html projection must include centripetal term (v/r) "
            "in the gamma update equation. Without this term, even a "
            "circular orbit would appear to dive toward the surface.")

    def test_nominal_coast_computed(self):
        """
        index.html must compute and draw a nominal coast extension
        after the powered trajectory ends at core burnout.
        """
        src = self._read_ui()
        self.assertIn('nominalCoast', src,
            "index.html must compute a nominalCoast extension to show "
            "the ballistic arc after core burnout.")
        self.assertIn('computeNominalCoast', src,
            "index.html must define computeNominalCoast() to extend "
            "the nominal trajectory past core burnout.")

    def test_old_parabolic_projection_removed(self):
        """
        The old fake parabolic projection (h0*(1-f²)) must be replaced
        by the physics-correct ballistic arc.
        """
        src = self._read_ui()
        self.assertNotIn('1 - f * f', src,
            "Old parabolic projection formula (1-f*f) must be removed. "
            "It ignored velocity entirely and produced unrealistic arcs.")
        self.assertNotIn('parabolic descent', src,
            "Old 'parabolic descent' comment must be removed — projection "
            "now uses proper gravity-turn equations.")

    def test_projection_drawn_on_globe(self):
        """
        The ballistic projection must be drawn on the Kerbin globe canvas.
        """
        src = self._read_ui()
        self.assertIn('projectionArc', src,
            "Globe view must draw projectionArc (ballistic projection).")

    def test_projection_drawn_on_trajectory_plot(self):
        """
        The ballistic projection must also appear on the trajectory plot.
        """
        src = self._read_ui()
        self.assertIn('trajProjPts', src,
            "Trajectory plot must draw trajProjPts (ballistic projection).")


if __name__ == '__main__':
    unittest.main(verbosity=2)
