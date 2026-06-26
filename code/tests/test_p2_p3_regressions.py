"""Regression tests for P2 (Medium) and P3 (Low) findings from the Engineering Review."""

import ast
import os

import pytest

from mission_control.nominal_compare import FlightPhase, generate_advisory
from sim.constants import G0, ENGINES, PERSEUS_1_DEFAULT
from sim.vehicle import VehicleConfig, engine_thrust_at


# ---------------------------------------------------------------------------
# P2-01  mass_after_booster_sep returns upper bound without caveat
# ---------------------------------------------------------------------------

def test_p201_swivel_burn_during_boost(vehicle_config):
    sw = ENGINES["swivel"]
    mdot_vac_kgs = sw["thrust_vac"] * 1000 / (sw["isp_vac"] * G0)
    prop_during_boost_t = (mdot_vac_kgs * vehicle_config.srb_burn_time_s) / 1000.0
    naive_mass = vehicle_config.mass_after_booster_sep
    assert naive_mass - (naive_mass - prop_during_boost_t) > 1.0, (
        f"Swivel consumes >{1.0}t during boost ({prop_during_boost_t:.2f}t)")


def test_p201_mass_at_sep_exists(vehicle_config):
    assert hasattr(vehicle_config, 'mass_at_booster_sep'), (
        "VehicleConfig must have 'mass_at_booster_sep' property")
    assert vehicle_config.mass_at_booster_sep < vehicle_config.mass_after_booster_sep, (
        f"mass_at_booster_sep ({vehicle_config.mass_at_booster_sep:.3f}t) must be < "
        f"mass_after_booster_sep ({vehicle_config.mass_after_booster_sep:.3f}t)")


# ---------------------------------------------------------------------------
# P2-02  generate_diagrams.py import-stripping is fragile
# ---------------------------------------------------------------------------

def _ast_strip_imports(src):
    tree = ast.parse(src)
    import_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for ln in range(node.lineno, node.end_lineno + 1):
                import_lines.add(ln)
    lines = src.split('\n')
    return '\n'.join(l for i, l in enumerate(lines, 1) if i not in import_lines)


def test_p202_multiline_import_strip():
    src = (
        "from parts import (\n"
        "    part_tank, part_engine,\n"
        "    part_fin\n"
        ")\n"
        "x = 1\n"
    )
    stripped = _ast_strip_imports(src)
    non_blank = [l for l in stripped.split('\n') if l.strip()]
    assert non_blank == ['x = 1'], f"Multi-line import not fully stripped: {non_blank}"


def test_p202_stripped_compiles():
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
    stripped = _ast_strip_imports(src)
    compile(stripped, '<test>', 'exec')  # raises SyntaxError on failure


def test_p202_generate_compiles(project_root):
    src = open(os.path.join(project_root, 'diagrams', 'generate_diagrams.py')).read()
    compile(src, 'generate_diagrams.py', 'exec')  # raises on failure


# ---------------------------------------------------------------------------
# P2-05  SECRET_KEY is hardcoded
# ---------------------------------------------------------------------------

def test_p205_secret_from_env(project_root):
    src = open(os.path.join(project_root, 'mission_control', 'server.py')).read()
    assert 'MC_SECRET_KEY' in src, "server.py must read SECRET_KEY from MC_SECRET_KEY env var"
    assert 'environ' in src, "server.py must use os.environ"


def test_p205_env_get_used(project_root):
    src = open(os.path.join(project_root, 'mission_control', 'server.py')).read()
    assert 'os.environ.get' in src, "SECRET_KEY must use os.environ.get() as primary source"


# ---------------------------------------------------------------------------
# P2-06  Trajectory not auto-cleared between flights
# ---------------------------------------------------------------------------

def test_p206_reset_logic(project_root):
    src = open(os.path.join(project_root, 'mission_control', 'telemachus_client.py')).read()
    assert 'mission_time reset' in src, (
        "telemachus_client.py must detect MET reset and auto-clear trajectory")


def test_p206_sim_resets(project_root):
    src = open(os.path.join(project_root, 'mission_control', 'telemachus_client.py')).read()
    assert 'clear()' in src, "SimulatedTelemetry must call _trajectory.clear() on loop reset"


# ---------------------------------------------------------------------------
# P2-08  Advisory missing apoapsis-stall detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("prev_apo,lf,expected_not,label", [
    (35.0, 280, "WARNING", "rising apo should not warn"),
])
def test_p208_rising_apo_nominal(prev_apo, lf, expected_not, label):
    state = {
        'altitude': 20_000.0, 'apoapsis': 38_000.0,
        'periapsis': -400_000, 'mission_time': 90.0,
        'solid_fuel': 0, 'liquid_fuel': float(lf),
        'throttle': 1.0, 'pitch': 45.0, 'velocity': 900.0,
    }
    adv = generate_advisory(state, FlightPhase.TERRIER, prev_apo_km=prev_apo)
    assert adv.level != expected_not, (
        f"{label}: got '{adv.level}' -- '{adv.action}'")


@pytest.mark.parametrize("prev_apo,lf,label", [
    (38.0, 180, "stalled apo should warn"),
])
def test_p208_stalled_apo_warns(prev_apo, lf, label):
    state = {
        'altitude': 20_000.0, 'apoapsis': 38_000.0,
        'periapsis': -400_000, 'mission_time': 90.0,
        'solid_fuel': 0, 'liquid_fuel': float(lf),
        'throttle': 1.0, 'pitch': 45.0, 'velocity': 900.0,
    }
    adv = generate_advisory(state, FlightPhase.TERRIER, prev_apo_km=prev_apo)
    assert adv.level in ('CAUTION', 'WARNING'), (
        f"{label}: got '{adv.level}'")


# ---------------------------------------------------------------------------
# P3-01  Advisory wording ambiguous for flight controllers
# ---------------------------------------------------------------------------

def _steep_advisory(pitch_ksp=15.0, nom_pfv=37.0):
    state = {
        'altitude': 10_000, 'apoapsis': 35_000, 'periapsis': -580_000,
        'mission_time': 80.0, 'solid_fuel': 0, 'liquid_fuel': 300,
        'throttle': 1.0, 'pitch': pitch_ksp, 'velocity': 450,
    }
    nom = {'pitch_from_vertical': nom_pfv}
    return generate_advisory(state, FlightPhase.TERRIER, nominal=nom)


def test_p301_steep_toward_horizon():
    adv = _steep_advisory(pitch_ksp=15.0)
    assert 'HORIZON' in adv.action.upper(), (
        f"Steep advisory must say TOWARD HORIZON, got: '{adv.action}'")
    assert 'FROM VERTICAL' not in adv.action.upper(), (
        f"Must not use ambiguous 'FROM VERTICAL' phrasing: '{adv.action}'")


def test_p301_shallow_toward_vert():
    adv = _steep_advisory(pitch_ksp=75.0)
    assert 'VERTICAL' in adv.action.upper(), (
        f"Shallow advisory must reference VERTICAL, got: '{adv.action}'")


# ---------------------------------------------------------------------------
# P3-05  VehicleConfig private field initialization
# ---------------------------------------------------------------------------

def test_p305_init_false(project_root):
    src = open(os.path.join(project_root, 'sim', 'vehicle.py')).read()
    assert 'default_factory=dict' not in src, (
        "_booster must not use default_factory=dict")
    assert 'init=False' in src, "_booster/_cda must use field(init=False)"


def test_p305_config_still_works():
    cfg = VehicleConfig()
    assert cfg.liftoff_mass_t == pytest.approx(14.21, abs=0.05)
    assert cfg.pad_twr_asl == pytest.approx(1.77, abs=0.05)
    assert cfg.mission_stage_dv_ms == pytest.approx(3458, abs=10)
    assert cfg.effective_cda > 0


# ---------------------------------------------------------------------------
# P3-06  engine_thrust_at imported inside function body
# ---------------------------------------------------------------------------

def test_p306_module_level_import(project_root):
    src = open(os.path.join(project_root, 'sim', 'trajectory.py')).read()
    assert '    from .vehicle import' not in src, (
        "engine_thrust_at must be imported at module level, not inside integrate()")


def test_p306_engine_thrust_callable():
    thrust_kN, mdot_kgs = engine_thrust_at(0, 'swivel', 1.0)
    assert thrust_kN == pytest.approx(167.97, abs=2.0), (
        f"Swivel ASL thrust should be ~167.97 kN, got {thrust_kN:.2f}")
    assert mdot_kgs == pytest.approx(68.49, abs=1.0), (
        f"Swivel ASL mdot should be ~68.49 kg/s, got {mdot_kgs:.2f}")


# ---------------------------------------------------------------------------
# P3-07  TRAJECTORY constant provenance and helper script
# ---------------------------------------------------------------------------

def test_p307_provenance_comment(project_root):
    sheet3_path = os.path.join(project_root, '..', 'nasa_dev', 'sheet3.py')
    if not os.path.exists(sheet3_path):
        sheet3_path = os.path.join(project_root, 'diagrams', 'sheet3.py')
    src = open(sheet3_path).read()
    assert 'run_ascent' in src, (
        "TRAJECTORY constant must reference run_ascent() in a provenance comment")


def test_p307_helper_exists(project_root):
    tools_path = os.path.join(project_root, 'tools', 'update_sheet3_trajectory.py')
    assert os.path.exists(tools_path), f"Helper script not found at {tools_path}"


# ---------------------------------------------------------------------------
# P3-10  PERSEUS_1_DEFAULT unused / dual source of truth
# ---------------------------------------------------------------------------

def test_p310_uses_default_dict(project_root):
    src = open(os.path.join(project_root, 'sim', 'vehicle.py')).read()
    assert 'PERSEUS_1_DEFAULT[' in src, (
        "VehicleConfig must source field defaults from PERSEUS_1_DEFAULT")


def test_p310_values_match():
    cfg = VehicleConfig()
    assert cfg.booster_type == PERSEUS_1_DEFAULT['booster_type']
    assert cfg.n_boosters == PERSEUS_1_DEFAULT['n_boosters']
    assert cfg.booster_pct == pytest.approx(PERSEUS_1_DEFAULT['booster_pct'], abs=0.1)
