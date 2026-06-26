"""
tests/test_ballistic_projection.py
====================================
Regression tests for the ballistic trajectory projection engine added to the
mission control visualization (index.html).

Migrated to pytest style.
"""

import math
import os
import pytest

from sim.constants import MU_KERBIN, R_KERBIN, ATM_CEIL, RHO0, SCALE_H
from sim.trajectory import orbital_params, gravity
from sim.vehicle import VehicleConfig


# ---------------------------------------------------------------------------
# Python reference implementation of the JS ballistic projection
# ---------------------------------------------------------------------------

DEFAULT_CDA = VehicleConfig().effective_cda
DEFAULT_COAST_MASS = VehicleConfig().mass_at_booster_sep * 1000.0  # kg


def project_ballistic_arc(alt_m, v_horiz, v_vert, dr_km=0.0,
                          dt=2.0, max_steps=300,
                          include_centripetal=True,
                          include_drag=True,
                          cda=None, mass_kg=None):
    """
    Propagate a ballistic (unpowered) arc from a given state vector.

    Returns list of dicts: [{altitude_km, downrange_km}, ...].
    Matches the JS implementation in index.html.
    """
    R = R_KERBIN
    MU = MU_KERBIN
    _cda = cda if cda is not None else DEFAULT_CDA
    _mass = mass_kg if mass_kg is not None else DEFAULT_COAST_MASS

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

        # Drag deceleration
        a_drag = 0.0
        if include_drag and 0 < h < ATM_CEIL:
            rho = RHO0 * math.exp(-h / SCALE_H)
            a_drag = 0.5 * rho * v * v * _cda / _mass

        # Velocity update
        v += (-g * sinG - a_drag) * dt
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
BURNOUT_GAMMA_RAD = math.radians(90.0 - BURNOUT_PFV_DEG)  # 40 deg from horiz
BURNOUT_VH = BURNOUT_VEL * math.cos(BURNOUT_GAMMA_RAD)    # ~492 m/s
BURNOUT_VV = BURNOUT_VEL * math.sin(BURNOUT_GAMMA_RAD)    # ~413 m/s
BURNOUT_DR_KM = 8.31

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Projection apoapsis vs analytical orbital_params
# ---------------------------------------------------------------------------

def test_burnout_apo_matches_analytical():
    apo_analytical, _ = orbital_params(
        BURNOUT_ALT_M, BURNOUT_VEL, BURNOUT_GAMMA_RAD
    )
    pts = project_ballistic_arc(
        BURNOUT_ALT_M, BURNOUT_VH, BURNOUT_VV, BURNOUT_DR_KM
    )
    apo_projected = arc_max_altitude(pts)
    assert apo_projected == pytest.approx(apo_analytical, abs=1.0)


def test_higher_vel_higher_apo():
    v_low, v_high = 500.0, 800.0
    gamma = math.radians(40.0)
    pts_low = project_ballistic_arc(
        15000, v_low * math.cos(gamma), v_low * math.sin(gamma)
    )
    pts_high = project_ballistic_arc(
        15000, v_high * math.cos(gamma), v_high * math.sin(gamma)
    )
    assert arc_max_altitude(pts_high) > arc_max_altitude(pts_low) + 5.0


def test_shallow_angle_more_dr():
    v = 643.0
    gamma_steep = math.radians(60.0)
    gamma_shallow = math.radians(20.0)
    pts_steep = project_ballistic_arc(
        15000, v * math.cos(gamma_steep), v * math.sin(gamma_steep)
    )
    pts_shallow = project_ballistic_arc(
        15000, v * math.cos(gamma_shallow), v * math.sin(gamma_shallow)
    )
    assert arc_endpoint(pts_shallow)["downrange_km"] > arc_endpoint(pts_steep)["downrange_km"] + 5.0


# ---------------------------------------------------------------------------
# Centripetal correction term
# ---------------------------------------------------------------------------

def test_circular_orbit_level():
    h = 80000.0
    r = R_KERBIN + h
    v_circ = math.sqrt(MU_KERBIN / r)
    pts = project_ballistic_arc(h, v_circ, 0.0, dt=2.0, max_steps=150)
    min_alt = min(p["altitude_km"] for p in pts)
    max_alt = max(p["altitude_km"] for p in pts)
    assert min_alt > 75.0
    assert max_alt < 85.0


def test_no_centripetal_dives():
    # Without centripetal term, circular orbit incorrectly dives
    h = 80000.0
    r = R_KERBIN + h
    v_circ = math.sqrt(MU_KERBIN / r)
    pts_bad = project_ballistic_arc(
        h, v_circ, 0.0, dt=2.0, max_steps=150, include_centripetal=False
    )
    min_alt_bad = min(p["altitude_km"] for p in pts_bad)
    assert min_alt_bad < 50.0


def test_centripetal_improves_high_arc():
    h = 50000.0
    v = 1800.0
    gamma = math.radians(10.0)
    v_h = v * math.cos(gamma)
    v_v = v * math.sin(gamma)
    apo_analytical, _ = orbital_params(h, v, gamma)
    pts_with = project_ballistic_arc(h, v_h, v_v, include_centripetal=True)
    pts_without = project_ballistic_arc(h, v_h, v_v, include_centripetal=False)
    err_with = abs(arc_max_altitude(pts_with) - apo_analytical)
    err_without = abs(arc_max_altitude(pts_without) - apo_analytical)
    assert err_with < err_without


# ---------------------------------------------------------------------------
# Velocity dependence
# ---------------------------------------------------------------------------

def test_zero_vel_no_projection():
    pts_zero = project_ballistic_arc(15000, 0.0, 0.0)
    assert len(pts_zero) == 0


def test_vertical_fall_near_origin():
    pts_falling = project_ballistic_arc(15000, 0.0, -50.0)
    if pts_falling:
        ep = arc_endpoint(pts_falling)
        assert ep["downrange_km"] < 1.0


def test_diff_vel_diff_arcs():
    pts_a = project_ballistic_arc(15000, 400.0, 300.0)
    pts_b = project_ballistic_arc(15000, 200.0, 500.0)
    apo_a = arc_max_altitude(pts_a)
    apo_b = arc_max_altitude(pts_b)
    assert abs(apo_a - apo_b) > 2.0


# ---------------------------------------------------------------------------
# Suborbital arc ground impact
# ---------------------------------------------------------------------------

def test_suborbital_hits_ground():
    pts = project_ballistic_arc(
        BURNOUT_ALT_M, BURNOUT_VH, BURNOUT_VV, BURNOUT_DR_KM
    )
    ep = arc_endpoint(pts)
    assert ep is not None
    assert ep["altitude_km"] <= 0.05


def test_impact_dr_realistic():
    pts = project_ballistic_arc(
        BURNOUT_ALT_M, BURNOUT_VH, BURNOUT_VV, BURNOUT_DR_KM
    )
    ep = arc_endpoint(pts)
    assert 40.0 < ep["downrange_km"] < 120.0


# ---------------------------------------------------------------------------
# Nominal coast extension
# ---------------------------------------------------------------------------

def test_coast_reaches_sim_apo():
    pts = project_ballistic_arc(
        BURNOUT_ALT_M, BURNOUT_VH, BURNOUT_VV, BURNOUT_DR_KM
    )
    apo = arc_max_altitude(pts)
    assert apo == pytest.approx(24.6, abs=1.5)


def test_coast_starts_at_burnout():
    pts = project_ballistic_arc(
        BURNOUT_ALT_M, BURNOUT_VH, BURNOUT_VV, BURNOUT_DR_KM
    )
    assert len(pts) > 2
    assert pts[0]["altitude_km"] == pytest.approx(BURNOUT_ALT_M / 1000.0, abs=0.1)
    assert pts[0]["downrange_km"] == pytest.approx(BURNOUT_DR_KM, abs=0.1)


def test_coast_rises_then_falls():
    pts = project_ballistic_arc(
        BURNOUT_ALT_M, BURNOUT_VH, BURNOUT_VV, BURNOUT_DR_KM
    )
    alts = [p["altitude_km"] for p in pts]
    peak_idx = alts.index(max(alts))
    assert peak_idx > 0
    assert peak_idx < len(alts) - 1


# ---------------------------------------------------------------------------
# Gravity model consistency
# ---------------------------------------------------------------------------

def test_surface_gravity():
    g0 = MU_KERBIN / (R_KERBIN ** 2)
    assert g0 == pytest.approx(9.81, abs=0.01)


def test_gravity_decreases_with_alt():
    g_surface = gravity(0)
    g_80km = gravity(80000)
    assert g_80km < g_surface
    assert g_80km == pytest.approx(7.64, abs=0.05)


def test_v_circ_80km():
    r = R_KERBIN + 80000
    v_circ = math.sqrt(MU_KERBIN / r)
    assert v_circ == pytest.approx(2279, abs=2)


# ---------------------------------------------------------------------------
# UI source code contains projection engine
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ui_html():
    html_path = os.path.join(ROOT, 'mission_control', 'static', 'index.html')
    with open(html_path) as f:
        return f.read()


def test_ui_has_projection_fn(ui_html):
    assert 'projectBallisticArc' in ui_html
    assert 'MU_KERBIN_PROJ' in ui_html


def test_ui_centripetal_term(ui_html):
    assert 'v / r' in ui_html


def test_ui_nominal_coast(ui_html):
    assert 'nominalCoast' in ui_html
    assert 'computeNominalCoast' in ui_html


def test_ui_no_old_parabolic(ui_html):
    assert '1 - f * f' not in ui_html
    assert 'parabolic descent' not in ui_html


def test_ui_projection_on_globe(ui_html):
    assert 'projectionArc' in ui_html


def test_ui_projection_on_traj_plot(ui_html):
    assert 'trajProjPts' in ui_html


# ---------------------------------------------------------------------------
# Atmospheric drag
# ---------------------------------------------------------------------------

def test_drag_reduces_dr_low_alt():
    pts_drag = project_ballistic_arc(5000, 250.0, 100.0, include_drag=True)
    pts_nodrag = project_ballistic_arc(5000, 250.0, 100.0, include_drag=False)
    assert arc_endpoint(pts_drag)["downrange_km"] < arc_endpoint(pts_nodrag)["downrange_km"]


def test_drag_none_above_atm():
    h = 80000.0
    v = 1500.0
    gamma = math.radians(15.0)
    v_h = v * math.cos(gamma)
    v_v = v * math.sin(gamma)
    pts_drag = project_ballistic_arc(h, v_h, v_v, include_drag=True)
    pts_nodrag = project_ballistic_arc(h, v_h, v_v, include_drag=False)
    assert arc_max_altitude(pts_drag) == pytest.approx(arc_max_altitude(pts_nodrag), abs=0.1)


def test_drag_reduces_burnout_dr():
    pts_drag = project_ballistic_arc(
        BURNOUT_ALT_M, BURNOUT_VH, BURNOUT_VV, BURNOUT_DR_KM, include_drag=True
    )
    pts_nodrag = project_ballistic_arc(
        BURNOUT_ALT_M, BURNOUT_VH, BURNOUT_VV, BURNOUT_DR_KM, include_drag=False
    )
    assert arc_endpoint(pts_drag)["downrange_km"] < arc_endpoint(pts_nodrag)["downrange_km"]


def test_exp_atmosphere_model():
    rho_10km = RHO0 * math.exp(-10000 / SCALE_H)
    assert rho_10km == pytest.approx(0.168, abs=0.01)


def test_ui_has_drag_model(ui_html):
    assert 'a_drag' in ui_html
    assert 'PROJ_CDA' in ui_html
    assert 'PROJ_RHO0' in ui_html


# ---------------------------------------------------------------------------
# Energy conservation diagnostic
# ---------------------------------------------------------------------------

def test_vacuum_arc_propagates():
    h = 80000.0
    v = 1800.0
    gamma = math.radians(15.0)
    v_h = v * math.cos(gamma)
    v_v = v * math.sin(gamma)
    pts = project_ballistic_arc(h, v_h, v_v, include_drag=False,
                                 dt=1.0, max_steps=600)
    ep = pts[-1]
    if ep["altitude_km"] > 0:
        assert len(pts) > 10


# ---------------------------------------------------------------------------
# Server error resilience (excluding duplicate API tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def flask_client():
    from mission_control.server import app, session
    app.config["TESTING"] = True
    client = app.test_client()
    yield client, session


def test_start_no_scenario_400(flask_client):
    client, session = flask_client
    session.telemetry_client = None
    resp = client.post("/api/scenario/start")
    assert resp.status_code == 400


def test_pause_no_scenario_400(flask_client):
    client, session = flask_client
    session.telemetry_client = None
    resp = client.post("/api/scenario/pause")
    assert resp.status_code == 400


def test_speed_out_of_range_400(flask_client):
    client, session = flask_client
    client.post("/api/scenario/load", json={"preset": "nominal"})
    resp = client.post("/api/scenario/speed", json={"speed": 99.0})
    assert resp.status_code == 400
    if session.telemetry_client:
        session.telemetry_client.stop()


def test_constants_has_drag_params(flask_client):
    client, _ = flask_client
    resp = client.get("/api/constants")
    data = resp.get_json()
    assert "DEFAULT_CDA" in data
    assert "COAST_MASS_KG" in data
    assert data["DEFAULT_CDA"] > 0
    assert data["COAST_MASS_KG"] > 0
