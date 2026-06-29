"""Tests for sim.parts_db — KSP parts database."""

import pytest
from sim.parts_db import PartsDatabase, Engine, FuelTank, StructuralPart, _normalize_key


@pytest.fixture(scope="module")
def db():
    return PartsDatabase.load_default()


class TestDatabaseLoading:
    def test_loads_engines(self, db):
        engines = db.list_engines()
        assert len(engines) >= 20

    def test_loads_tanks(self, db):
        tanks = db.list_tanks()
        assert len(tanks) >= 10

    def test_loads_parts(self, db):
        parts = db.list_parts()
        assert len(parts) >= 50

    def test_engine_types(self, db):
        liquid = db.list_engines(engine_type="liquid")
        solid = db.list_engines(engine_type="solid")
        assert len(liquid) >= 15
        assert len(solid) >= 5


class TestEngineLookup:
    def test_by_legacy_alias(self, db):
        e = db.get_engine("swivel")
        assert "Swivel" in e.name
        assert e.engine_type == "liquid"

    def test_by_display_name(self, db):
        e = db.get_engine('LV-T45 "Swivel" Liquid Fuel Engine')
        assert e.thrust_vac_kn > 0

    def test_by_normalized_key(self, db):
        e = db.get_engine("lv-t45_swivel_liquid_fuel_engine")
        assert "Swivel" in e.name

    def test_hammer_srb(self, db):
        e = db.get_engine("hammer")
        assert e.engine_type == "solid"
        assert e.mass_full_t == pytest.approx(0.75, abs=0.01)
        assert e.mass_dry_t == pytest.approx(0.15, abs=0.01)
        assert e.prop_mass_t == pytest.approx(0.60, abs=0.01)

    def test_thumper_srb(self, db):
        e = db.get_engine("thumper")
        assert e.mass_full_t == pytest.approx(1.50, abs=0.01)
        assert e.prop_mass_t == pytest.approx(1.20, abs=0.01)

    def test_terrier(self, db):
        e = db.get_engine("terrier")
        assert e.thrust_vac_kn == pytest.approx(60.0, abs=1.0)
        assert e.isp_vac == pytest.approx(345.0, abs=1.0)

    def test_unknown_engine_raises(self, db):
        with pytest.raises(KeyError):
            db.get_engine("nonexistent_engine")

    def test_all_engines_have_isp(self, db):
        for e in db.list_engines():
            assert e.isp_vac > 0, f"{e.name} missing isp_vac"
            assert e.isp_asl > 0, f"{e.name} missing isp_asl"

    def test_all_srbs_have_prop_mass(self, db):
        for e in db.list_engines(engine_type="solid"):
            assert e.prop_mass_t is not None and e.prop_mass_t > 0, (
                f"{e.name} missing prop_mass"
            )


class TestTankLookup:
    def test_by_legacy_alias(self, db):
        t = db.get_tank("flt800")
        assert "FL-T800" in t.name

    def test_flt800_masses(self, db):
        t = db.get_tank("flt800")
        assert t.mass_full_t == pytest.approx(4.50, abs=0.01)
        assert t.mass_dry_t == pytest.approx(0.50, abs=0.01)
        assert t.prop_mass_t == pytest.approx(4.00, abs=0.01)

    def test_flt400_masses(self, db):
        t = db.get_tank("flt400")
        assert t.mass_full_t == pytest.approx(2.25, abs=0.01)
        assert t.prop_mass_t == pytest.approx(2.00, abs=0.01)

    def test_fuel_type_filter(self, db):
        lf_ox = db.list_tanks(fuel_type="lf_ox")
        assert len(lf_ox) >= 5

    def test_unknown_tank_raises(self, db):
        with pytest.raises(KeyError):
            db.get_tank("nonexistent_tank")


class TestPartLookup:
    def test_by_legacy_alias(self, db):
        p = db.get_part("mk1_pod")
        assert "Mk1" in p.name
        assert p.category == "pod"

    def test_decoupler(self, db):
        p = db.get_part("tr18a_decoupler")
        assert p.category == "decoupler"

    def test_category_filter(self, db):
        pods = db.list_parts(category="pod")
        assert len(pods) >= 3

    def test_unknown_part_raises(self, db):
        with pytest.raises(KeyError):
            db.get_part("nonexistent_part")


class TestFrozenDataclasses:
    def test_engine_immutable(self, db):
        e = db.get_engine("swivel")
        with pytest.raises(AttributeError):
            e.thrust_vac_kn = 999

    def test_tank_immutable(self, db):
        t = db.get_tank("flt800")
        with pytest.raises(AttributeError):
            t.mass_full_t = 999

    def test_part_immutable(self, db):
        p = db.get_part("mk1_pod")
        with pytest.raises(AttributeError):
            p.mass_t = 999


class TestNormalizeKey:
    def test_simple(self):
        assert _normalize_key("Basic Fin") == "basic_fin"

    def test_quotes(self):
        assert _normalize_key('LV-T45 "Swivel" Liquid Fuel Engine') == "lv_t45_swivel_liquid_fuel_engine"

    def test_parens(self):
        assert _normalize_key("Heat Shield (1.25m)") == "heat_shield_1_25m"
