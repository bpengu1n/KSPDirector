"""Tests for sim.generic_vehicle and sim.trajectory.integrate_generic."""

import math

import pytest
from sim.parts_db import PartsDatabase
from sim.generic_vehicle import GenericVehicle, StageDefinition
from sim.vehicle import VehicleConfig
from sim.ascent_sim import run_generic
from sim.trajectory import integrate_generic, PITCH_PROGRAMS


@pytest.fixture(scope="module")
def db():
    return PartsDatabase.load_default()


# -----------------------------------------------------------------------
# GenericVehicle mass / performance
# -----------------------------------------------------------------------

class TestPerseus1Factory:
    def test_stage_count(self, db):
        v = GenericVehicle.from_perseus1()
        assert len(v.stages) == 3

    def test_stage_count_zero_boosters(self, db):
        cfg = VehicleConfig(n_boosters=0)
        v = GenericVehicle.from_perseus1(cfg)
        assert len(v.stages) == 2

    def test_liftoff_mass(self, db):
        v = GenericVehicle.from_perseus1()
        assert v.liftoff_mass(db) == pytest.approx(14.21, abs=0.5)

    def test_pad_twr(self, db):
        v = GenericVehicle.from_perseus1()
        assert v.pad_twr_asl(db) == pytest.approx(1.77, abs=0.1)

    def test_booster_parallel(self, db):
        v = GenericVehicle.from_perseus1()
        assert v.stages[0].parallel is True
        assert v.stages[1].parallel is False
        assert v.stages[2].parallel is False

    def test_validation_clean(self, db):
        v = GenericVehicle.from_perseus1()
        assert v.validate(db) == []

    def test_upper_stage_dv(self, db):
        v = GenericVehicle.from_perseus1()
        dv = v.stage_dv_vac(len(v.stages) - 1, db)
        assert dv > 2500
        assert dv < 4000


class TestCustomVehicle:
    def test_two_stage(self, db):
        v = GenericVehicle(
            name="2-Stage",
            stages=[
                StageDefinition(name="Core", engine_key="swivel", tank_key="flt800"),
                StageDefinition(name="Upper", engine_key="terrier", tank_key="flt400"),
            ],
            payload_keys=["mk1_pod"],
        )
        assert v.liftoff_mass(db) > 5.0
        assert v.pad_twr_asl(db) > 1.0
        assert v.total_dv_vac(db) > 3000

    def test_single_stage(self, db):
        v = GenericVehicle(
            name="SSTO-ish",
            stages=[
                StageDefinition(name="Main", engine_key="swivel", tank_key="flt800"),
            ],
            payload_keys=["mk1_pod"],
        )
        assert len(v.stages) == 1
        assert v.liftoff_mass(db) > 0
        assert v.total_dv_vac(db) > 1000

    def test_multi_engine(self, db):
        v = GenericVehicle(
            name="Twin Engine",
            stages=[
                StageDefinition(
                    name="Core", engine_key="swivel",
                    engine_count=2, tank_key="flt800", tank_count=2,
                ),
                StageDefinition(name="Upper", engine_key="terrier", tank_key="flt400"),
            ],
            payload_keys=["mk1_pod"],
        )
        single = GenericVehicle(
            name="Single Engine",
            stages=[
                StageDefinition(name="Core", engine_key="swivel", tank_key="flt800"),
                StageDefinition(name="Upper", engine_key="terrier", tank_key="flt400"),
            ],
            payload_keys=["mk1_pod"],
        )
        assert v.pad_twr_asl(db) > single.pad_twr_asl(db)


class TestSerialization:
    def test_roundtrip(self, db):
        v = GenericVehicle.from_perseus1()
        d = v.to_dict()
        v2 = GenericVehicle.from_dict(d)
        assert v2.liftoff_mass(db) == pytest.approx(v.liftoff_mass(db), abs=0.001)
        assert v2.name == v.name
        assert len(v2.stages) == len(v.stages)

    def test_dict_structure(self, db):
        v = GenericVehicle.from_perseus1()
        d = v.to_dict()
        assert "name" in d
        assert "stages" in d
        assert "payload_keys" in d
        assert len(d["stages"]) == 3


class TestValidation:
    def test_empty_stages(self, db):
        v = GenericVehicle(name="Empty", stages=[])
        errs = v.validate(db)
        assert any("at least one stage" in e for e in errs)

    def test_bad_engine_key(self, db):
        v = GenericVehicle(
            name="Bad",
            stages=[StageDefinition(name="S1", engine_key="nonexistent")],
        )
        errs = v.validate(db)
        assert any("engine not found" in e for e in errs)

    def test_bad_tank_key(self, db):
        v = GenericVehicle(
            name="Bad",
            stages=[
                StageDefinition(
                    name="S1", engine_key="swivel", tank_key="fake_tank",
                ),
            ],
        )
        errs = v.validate(db)
        assert any("tank not found" in e for e in errs)

    def test_bad_throttle(self, db):
        v = GenericVehicle(
            name="Bad",
            stages=[
                StageDefinition(
                    name="S1", engine_key="swivel",
                    tank_key="flt800", throttle_pct=0.0,
                ),
            ],
        )
        errs = v.validate(db)
        assert any("throttle_pct" in e for e in errs)


# -----------------------------------------------------------------------
# N-stage trajectory integration
# -----------------------------------------------------------------------

class TestGenericTrajectory:
    def test_perseus1_reaches_orbit(self, db):
        v = GenericVehicle.from_perseus1()
        result = run_generic(v, db)
        assert result.apoapsis_km > 70
        assert result.periapsis_km > 50

    def test_perseus1_staging_count(self, db):
        v = GenericVehicle.from_perseus1()
        result = run_generic(v, db)
        assert len(result.staging_events) == 2

    def test_perseus1_booster_sep_timing(self, db):
        v = GenericVehicle.from_perseus1()
        result = run_generic(v, db)
        sep = result.staging_events[0]
        assert sep.t == pytest.approx(25.3, abs=2.0)

    def test_two_stage_reaches_orbit(self, db):
        v = GenericVehicle(
            name="2-Stage",
            stages=[
                StageDefinition(name="Core", engine_key="swivel", tank_key="flt800"),
                StageDefinition(name="Upper", engine_key="terrier", tank_key="flt400"),
            ],
            payload_keys=["mk1_pod"],
        )
        result = run_generic(v, db)
        assert result.apoapsis_km > 70
        assert len(result.staging_events) == 1

    def test_single_stage(self, db):
        v = GenericVehicle(
            name="Single",
            stages=[
                StageDefinition(name="Main", engine_key="swivel", tank_key="flt800"),
            ],
            payload_keys=["mk1_pod"],
        )
        result = run_generic(v, db)
        assert len(result.staging_events) == 0
        assert len(result.points) > 0

    def test_zero_booster_perseus1(self, db):
        cfg = VehicleConfig(n_boosters=0)
        v = GenericVehicle.from_perseus1(cfg)
        result = run_generic(v, db)
        assert result.apoapsis_km > 70
        assert len(result.staging_events) == 1

    def test_phase_names(self, db):
        v = GenericVehicle.from_perseus1()
        result = run_generic(v, db)
        phases = {p.phase for p in result.points}
        assert "CORE" in phases
        assert "UPPER" in phases

    def test_orbit_phase_present(self, db):
        v = GenericVehicle.from_perseus1()
        result = run_generic(v, db)
        phases = {p.phase for p in result.points}
        assert "ORBIT" in phases

    def test_max_q_point(self, db):
        v = GenericVehicle.from_perseus1()
        result = run_generic(v, db)
        assert result.max_q_point is not None
        assert result.max_q_point.altitude > 0

    def test_drag_and_grav_losses(self, db):
        v = GenericVehicle.from_perseus1()
        result = run_generic(v, db)
        assert result.drag_loss_total > 0
        assert result.grav_loss_total > 0

    def test_different_pitch_program(self, db):
        v = GenericVehicle.from_perseus1()
        nominal = run_generic(v, db, pitch_program=PITCH_PROGRAMS["nominal"])
        steep = run_generic(v, db, pitch_program=PITCH_PROGRAMS["steep"])
        assert abs(nominal.grav_loss_total - steep.grav_loss_total) > 10

    def test_run_generic_default_db(self):
        v = GenericVehicle.from_perseus1()
        result = run_generic(v)
        assert result.apoapsis_km > 70


class TestOrbitInsertion:
    def test_perseus1_upper_is_oi(self, db):
        v = GenericVehicle.from_perseus1()
        assert v.stages[2].orbit_insertion is True
        assert v.orbit_insertion_idx() == 2

    def test_default_is_last_stage(self, db):
        v = GenericVehicle(
            name="No OI flag",
            stages=[
                StageDefinition(name="Core", engine_key="swivel", tank_key="flt800"),
                StageDefinition(name="Upper", engine_key="terrier", tank_key="flt400"),
            ],
            payload_keys=["mk1_pod"],
        )
        assert v.orbit_insertion_idx() == 1

    def test_post_orbit_stage_inert(self, db):
        v = GenericVehicle.from_perseus1()
        v.stages.append(
            StageDefinition(name="TMI", engine_key="terrier", tank_key="flt400"),
        )
        result = run_generic(v, db)
        # TMI stage should never activate or separate
        assert len(result.staging_events) == 2  # boosters + core only
        phases = {p.phase for p in result.points}
        assert "TMI" not in phases

    def test_post_orbit_mass_counted(self, db):
        base = GenericVehicle(
            name="No TMI",
            stages=[
                StageDefinition(name="Core", engine_key="swivel", tank_key="flt800"),
                StageDefinition(
                    name="Upper", engine_key="terrier", tank_key="flt400",
                    orbit_insertion=True,
                ),
            ],
            payload_keys=["mk1_pod"],
        )
        with_tmi = GenericVehicle(
            name="With TMI",
            stages=[
                StageDefinition(name="Core", engine_key="swivel", tank_key="flt800"),
                StageDefinition(
                    name="Upper", engine_key="terrier", tank_key="flt400",
                    orbit_insertion=True,
                ),
                StageDefinition(name="TMI", engine_key="terrier", tank_key="flt400"),
            ],
            payload_keys=["mk1_pod"],
        )
        assert with_tmi.liftoff_mass(db) > base.liftoff_mass(db)

    def test_serialization_roundtrip(self, db):
        v = GenericVehicle(
            name="OI test",
            stages=[
                StageDefinition(name="Core", engine_key="swivel", tank_key="flt800"),
                StageDefinition(
                    name="Upper", engine_key="terrier", tank_key="flt400",
                    orbit_insertion=True,
                ),
                StageDefinition(name="TMI", engine_key="terrier", tank_key="flt200"),
            ],
            payload_keys=["mk1_pod"],
        )
        d = v.to_dict()
        assert d["stages"][1]["orbit_insertion"] is True
        assert d["stages"][2]["orbit_insertion"] is False
        v2 = GenericVehicle.from_dict(d)
        assert v2.orbit_insertion_idx() == 1

    def test_validate_multiple_oi_flags(self, db):
        v = GenericVehicle(
            name="Bad",
            stages=[
                StageDefinition(
                    name="S1", engine_key="swivel", tank_key="flt800",
                    orbit_insertion=True,
                ),
                StageDefinition(
                    name="S2", engine_key="terrier", tank_key="flt400",
                    orbit_insertion=True,
                ),
            ],
            payload_keys=["mk1_pod"],
        )
        errs = v.validate(db)
        assert any("at most one" in e.lower() for e in errs)

    def test_validate_parallel_oi(self, db):
        v = GenericVehicle(
            name="Bad",
            stages=[
                StageDefinition(
                    name="Boosters", engine_key="hammer", parallel=True,
                    orbit_insertion=True,
                ),
                StageDefinition(name="Core", engine_key="swivel", tank_key="flt800"),
            ],
        )
        errs = v.validate(db)
        assert any("parallel" in e.lower() for e in errs)

    def test_orbit_insertion_is_used_for_circularize(self, db):
        v = GenericVehicle(
            name="OI middle stage",
            stages=[
                StageDefinition(name="Core", engine_key="swivel", tank_key="flt800"),
                StageDefinition(
                    name="Upper", engine_key="terrier", tank_key="flt800",
                    orbit_insertion=True,
                ),
                StageDefinition(name="TMI", engine_key="terrier", tank_key="flt400"),
            ],
            payload_keys=["mk1_pod"],
        )
        result = run_generic(v, db)
        phases = {p.phase for p in result.points}
        assert "ORBIT" in phases or "COAST_APO" in phases or "CIRCULARIZE" in phases


class TestPublicAPI:
    def test_imports(self):
        from sim import (
            PartsDatabase, Engine, FuelTank, StructuralPart,
            GenericVehicle, StageDefinition, run_generic,
        )
        assert PartsDatabase is not None
        assert GenericVehicle is not None
