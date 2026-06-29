"""
sim/parts_db.py
---------------
KSP 1 stock parts database parsed from CSV wiki data.

Provides typed, immutable dataclasses for engines, fuel tanks, and structural
parts, with lookup by normalized key or display name.  ISP values missing from
the CSV are supplemented from wiki-verified constants.

Usage::

    from sim.parts_db import PartsDatabase
    db = PartsDatabase.load_default()
    engine = db.get_engine("swivel")
    tank = db.get_tank("fl-t800_fuel_tank")
    print(engine.thrust_vac_kn, engine.isp_vac)
"""

from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Engine:
    """A liquid-fuel engine or solid rocket booster."""
    name: str
    key: str
    engine_type: str        # "liquid" | "solid"
    mass_t: float           # dry mass for liquid, full mass for SRBs
    thrust_vac_kn: float
    thrust_asl_kn: float
    isp_vac: float
    isp_asl: float
    mass_full_t: Optional[float] = None   # SRB only
    mass_dry_t: Optional[float] = None    # SRB only
    prop_mass_t: Optional[float] = None   # SRB only


@dataclass(frozen=True)
class FuelTank:
    """A propellant tank (LF+OX, liquid-only, monopropellant, or xenon)."""
    name: str
    key: str
    mass_full_t: float
    mass_dry_t: float
    prop_mass_t: float
    liquid_fuel: float      # KSP units (0 for non-LF tanks)
    oxidizer: float         # KSP units (0 for non-LF+OX tanks)
    fuel_type: str          # "lf_ox" | "liquid_only" | "monoprop" | "xenon"


@dataclass(frozen=True)
class StructuralPart:
    """Any non-engine, non-tank part (pods, decouplers, nosecones, etc.)."""
    name: str
    key: str
    mass_t: float
    category: str


# ---------------------------------------------------------------------------
# ISP supplement — wiki-verified values for all stock liquid engines
# Keyed by CSV part name (exact match).
# ---------------------------------------------------------------------------

_ISP_SUPPLEMENT: dict[str, tuple[float, float]] = {
    # (isp_vac, isp_asl)
    'LV-1R "Spider" Liquid Fuel Engine':        (260.0, 235.0),
    '24-77 "Twitch" Liquid Fuel Engine':        (290.0, 250.0),
    'Mk-55 "Thud" Liquid Fuel Engine':          (305.0, 275.0),
    'O-10 "Puff" MonoPropellant Fuel Engine':   (250.0, 120.0),
    'LV-1 "Ant" Liquid Fuel Engine':            (315.0, 80.0),
    '48-7S "Spark" Liquid Fuel Engine':         (320.0, 265.0),
    'LV-909 "Terrier" Liquid Fuel Engine':      (345.0, 85.0),
    'LV-T30 "Reliant" Liquid Fuel Engine':      (310.0, 265.0),
    'LV-T45 "Swivel" Liquid Fuel Engine':       (320.0, 250.0),
    'S3 KS-25 "Vector" Liquid Fuel Engine':     (315.0, 295.0),
    'T-1 Toroidal Aerospike "Dart" Liquid Fuel Engine': (340.0, 290.0),
    'LV-N "Nerv" Atomic Rocket Motor':          (800.0, 185.0),
    'RE-L10 "Poodle" Liquid Fuel Engine':       (350.0, 90.0),
    'RE-I5 "Skipper" Liquid Fuel Engine':       (320.0, 280.0),
    'RE-M3 "Mainsail" Liquid Fuel Engine':      (310.0, 285.0),
    'LFB KR-1x2 "Twin-Boar" Liquid Fuel Engine': (300.0, 280.0),
    'Kerbodyne KR-2L+ "Rhino" Liquid Fuel Engine': (340.0, 205.0),
    'S3 KS-25x4 "Mammoth" Liquid Fuel Engine':  (315.0, 295.0),
    'CR-7 R.A.P.I.E.R. Engine':                 (305.0, 275.0),
    'IX-6315 "Dawn" Electric Propulsion System': (4200.0, 100.0),
}

# SRB ISP — also missing from CSV, supplement from wiki
_SRB_ISP_SUPPLEMENT: dict[str, tuple[float, float]] = {
    'RT-5 "Flea" Solid Fuel Booster':           (165.0, 140.0),
    'RT-10 "Hammer" Solid Fuel Booster':        (195.0, 170.0),
    'BACC "Thumper" Solid Fuel Booster':        (175.0, 165.0),
    'S1 SRB-KD25k "Kickback" Solid Fuel Booster': (195.0, 175.0),
    'Sepratron I':                               (154.0, 118.0),
    'FM1 "Mite" Solid Fuel Booster':            (185.0, 165.0),
    'F3S0 "Shrimp" Solid Fuel Booster':         (190.0, 168.0),
    'S2-17 "Thoroughbred" Solid Fuel Booster':  (210.0, 195.0),
    'S2-33 "Clydesdale" Solid Fuel Booster':    (210.0, 195.0),
}

# SRB mass corrections — CSV masses are systematically wrong for stock SRBs
# (the CSV's "mass_t_empty" column contains the actual full mass, and
# "mass_t_full" contains an inflated value from the PDF extraction).
# Values below are wiki-verified.  (mass_full_t, mass_dry_t)
_SRB_MASS_SUPPLEMENT: dict[str, tuple[float, float]] = {
    'RT-5 "Flea" Solid Fuel Booster':              (0.45,   0.09),
    'RT-10 "Hammer" Solid Fuel Booster':           (0.75,   0.15),
    'BACC "Thumper" Solid Fuel Booster':           (1.50,   0.30),
    'S1 SRB-KD25k "Kickback" Solid Fuel Booster':  (4.50,   0.90),
    'Sepratron I':                                  (0.0725, 0.0125),
}

# Legacy aliases mapping old short keys to CSV part names
_LEGACY_ENGINE_ALIASES: dict[str, str] = {
    "swivel":  'LV-T45 "Swivel" Liquid Fuel Engine',
    "terrier": 'LV-909 "Terrier" Liquid Fuel Engine',
    "hammer":  'RT-10 "Hammer" Solid Fuel Booster',
    "thumper": 'BACC "Thumper" Solid Fuel Booster',
}

_LEGACY_TANK_ALIASES: dict[str, str] = {
    "flt800": "FL-T800 Fuel Tank",
    "flt400": "FL-T400 Fuel Tank",
    "flt200": "FL-T200 Fuel Tank",
}

_LEGACY_PART_ALIASES: dict[str, str] = {
    "mk1_pod": "Mk1 Command Pod",
    "mk16_chute": "Mk16 Parachute",
    "heat_shield": "Heat Shield (1.25m)",
    "tr18a_decoupler": "TD-12 Decoupler",
    "tt38k_decoupler": "TT-38K Radial Decoupler",
    "basic_fin": "Basic Fin",
    "aero_nosecone": "Aerodynamic Nose Cone",
    "service_bay": "Service Bay (1.25m)",
    "reaction_wheel": "Small Inline Reaction Wheel",
    "battery": "Z-1k Rechargeable Battery Bank",
}

# Categories that map to structural parts (by CSV category/subcategory)
_STRUCTURAL_CATEGORIES: dict[str, str] = {
    "Pods": "pod",
    "SAS modules": "sas",
    "Reaction wheels": "reaction_wheel",
    "Decoupler and separator": "decoupler",
    "Docking": "docking",
    "Nose cones and tail connectors": "nosecone",
    "Winglets": "winglet",
    "Control surfaces": "control_surface",
    "Wings": "wing",
    "Modular wings": "wing",
    "Fairings": "fairing",
    "Cargo bays": "cargo_bay",
    "Service bays": "service_bay",
    "Batteries": "battery",
    "Generators": "generator",
    "Communications": "antenna",
    "Parachutes": "parachute",
    "Heat shields": "heat_shield",
    "Adapters, Couplers & Struts": "structural",
    "Beams, panels and radial elements": "structural",
    "Ground Support": "ground_support",
    "Landing gears": "landing_gear",
    "Landing legs": "landing_leg",
    "Rover wheels": "rover_wheel",
    "Containers": "container",
    "Deployables": "deployable",
    "Equipment": "equipment",
    "Experiment Storage": "science",
    "Labs": "science",
    "Resource scanners": "science",
    "Sensors": "science",
    "Telescopes": "science",
    "Radiators": "radiator",
    "Converters": "converter",
    "Escape systems": "escape_system",
    "Firework launchers": "misc",
    "Flags": "misc",
    "Habitation module": "habitation",
    "Ladders": "ladder",
    "Lights": "light",
    "Resource harvesters": "harvester",
    "RCS thrusters": "rcs_thruster",
    "Air intakes": "air_intake",
}


# ---------------------------------------------------------------------------
# Key normalization
# ---------------------------------------------------------------------------

def _normalize_key(name: str) -> str:
    """Deterministic key from a KSP part display name.

    Lowercase, strip inner quotes, replace non-alphanumeric runs with
    underscores, strip leading/trailing underscores.
    """
    s = name.lower()
    s = s.replace('"', '').replace("'", "")
    s = re.sub(r'[^a-z0-9]+', '_', s)
    return s.strip('_')


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _safe_float(val: str, default: float = 0.0) -> float:
    if not val or val == '-':
        return default
    val = val.strip()
    # Handle compound values like "1200 (800)" — take first number
    m = re.match(r'([0-9]*\.?[0-9]+)', val)
    if m:
        return float(m.group(1))
    return default


def _parse_engine(row: dict) -> Optional[Engine]:
    name = row.get('part', '').strip()
    if not name:
        return None

    subcat = row.get('subcategory', '')
    is_solid = subcat == 'Solid Fuel Boosters'
    is_ion = subcat == 'Ion Engines'
    engine_type = "solid" if is_solid else "liquid"

    thrust_vac = _safe_float(row.get('thrust_kn_vac', ''))
    thrust_asl = _safe_float(row.get('thrust_kn_atm', ''))
    if thrust_vac == 0.0 and thrust_asl == 0.0:
        return None

    # Mass
    if is_solid:
        if name in _SRB_MASS_SUPPLEMENT:
            mass_full, mass_dry = _SRB_MASS_SUPPLEMENT[name]
        else:
            mass_full = _safe_float(row.get('mass_t_full', ''))
            mass_dry = _safe_float(row.get('mass_t_empty', ''))
        prop_mass = mass_full - mass_dry if mass_full > mass_dry else 0.0
        mass_t = mass_full
    else:
        mass_t = _safe_float(row.get('mass_t', '') or row.get('mass_full_or_value', ''))
        # Twin-Boar has integrated fuel — use mass_t_empty if available
        me = row.get('mass_t_empty', '')
        if me and me.strip() and me.strip() != '-':
            mass_dry_val = _safe_float(me)
            mass_full_val = _safe_float(row.get('mass_t_full', ''))
            if mass_full_val > 0 and mass_dry_val > 0:
                mass_t = mass_dry_val
        mass_full = None
        mass_dry = None
        prop_mass = None

    # ISP — try flat columns, then parameters_json, then supplement
    isp_vac = _safe_float(row.get('isp_s_vac', ''))
    isp_asl = _safe_float(row.get('isp_s_atm', ''))

    if isp_vac == 0.0 or isp_asl == 0.0:
        pj_str = row.get('parameters_json', '')
        if pj_str:
            try:
                pj = json.loads(pj_str)
                if isp_vac == 0.0:
                    isp_vac = _safe_float(str(pj.get('isp_s_vac', '')))
                if isp_asl == 0.0:
                    isp_asl = _safe_float(str(pj.get('isp_s_atm', '')))
            except (json.JSONDecodeError, TypeError):
                pass

    if isp_vac == 0.0 or isp_asl == 0.0:
        supplement = _SRB_ISP_SUPPLEMENT if is_solid else _ISP_SUPPLEMENT
        if name in supplement:
            sv, sa = supplement[name]
            if isp_vac == 0.0:
                isp_vac = sv
            if isp_asl == 0.0:
                isp_asl = sa

    if isp_vac == 0.0 or isp_asl == 0.0:
        return None

    return Engine(
        name=name,
        key=_normalize_key(name),
        engine_type=engine_type,
        mass_t=mass_t,
        thrust_vac_kn=thrust_vac,
        thrust_asl_kn=thrust_asl,
        isp_vac=isp_vac,
        isp_asl=isp_asl,
        mass_full_t=mass_full,
        mass_dry_t=mass_dry,
        prop_mass_t=prop_mass,
    )


def _parse_tank(row: dict) -> Optional[FuelTank]:
    name = row.get('part', '').strip()
    if not name:
        return None

    mass_full = _safe_float(row.get('mass_t_full', ''))
    mass_dry = _safe_float(row.get('mass_t_empty', ''))
    if mass_full == 0.0 and mass_dry == 0.0:
        return None

    lf = _safe_float(row.get('liquid_fuel', ''))
    ox = _safe_float(row.get('oxidizer', ''))
    mp = _safe_float(row.get('monopropellant', ''))
    xe = _safe_float(row.get('xenon', ''))

    subcat = row.get('subcategory', '')
    if 'Xenon' in subcat:
        fuel_type = "xenon"
    elif 'RCS' in subcat or 'Monopropellant' in subcat or mp > 0:
        fuel_type = "monoprop"
    elif ox > 0 and lf > 0:
        fuel_type = "lf_ox"
    elif lf > 0:
        fuel_type = "liquid_only"
    else:
        fuel_type = "lf_ox"

    return FuelTank(
        name=name,
        key=_normalize_key(name),
        mass_full_t=mass_full,
        mass_dry_t=mass_dry,
        prop_mass_t=mass_full - mass_dry,
        liquid_fuel=lf,
        oxidizer=ox,
        fuel_type=fuel_type,
    )


def _parse_structural(row: dict, category_key: str) -> Optional[StructuralPart]:
    name = row.get('part', '').strip()
    if not name:
        return None

    mass_str = row.get('mass_t', '') or row.get('mass_full_or_value', '')
    mass = _safe_float(mass_str)
    if mass == 0.0:
        me = row.get('mass_t_empty', '')
        if me and me.strip():
            mass = _safe_float(me)

    return StructuralPart(
        name=name,
        key=_normalize_key(name),
        mass_t=mass,
        category=category_key,
    )


# ---------------------------------------------------------------------------
# PartsDatabase
# ---------------------------------------------------------------------------

class PartsDatabase:
    """Immutable database of KSP 1 stock parts.

    Load via ``PartsDatabase.load_default()`` for the bundled CSV, or
    ``PartsDatabase.load_csv(path)`` for a custom file.
    """

    def __init__(self):
        self._engines: dict[str, Engine] = {}
        self._tanks: dict[str, FuelTank] = {}
        self._parts: dict[str, StructuralPart] = {}
        self._name_to_engine_key: dict[str, str] = {}
        self._name_to_tank_key: dict[str, str] = {}
        self._name_to_part_key: dict[str, str] = {}

    # --- Loaders ---

    @classmethod
    def load_csv(cls, path: str | Path) -> PartsDatabase:
        db = cls()
        path = Path(path)
        with open(path, encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                subcat = row.get('subcategory', '')
                cat = row.get('category', '')

                if subcat in ('Liquid Fuel Engines', 'Solid Fuel Boosters', 'Ion Engines'):
                    engine = _parse_engine(row)
                    if engine:
                        db._engines[engine.key] = engine
                        db._name_to_engine_key[engine.name] = engine.key

                elif 'Fuel Tank' in cat or 'fuel tank' in subcat.lower():
                    # Skip fuel transfer parts
                    if subcat == 'Fuel transfer':
                        continue
                    tank = _parse_tank(row)
                    if tank:
                        db._tanks[tank.key] = tank
                        db._name_to_tank_key[tank.name] = tank.key

                else:
                    cat_key = _STRUCTURAL_CATEGORIES.get(subcat, 'misc')
                    part = _parse_structural(row, cat_key)
                    if part:
                        db._parts[part.key] = part
                        db._name_to_part_key[part.name] = part.key

        db._register_legacy_aliases()
        return db

    @classmethod
    def load_default(cls) -> PartsDatabase:
        csv_path = Path(__file__).parent / 'data' / 'ksp_parts.csv'
        return cls.load_csv(csv_path)

    def _register_legacy_aliases(self):
        for alias, display_name in _LEGACY_ENGINE_ALIASES.items():
            if display_name in self._name_to_engine_key:
                target_key = self._name_to_engine_key[display_name]
                if alias not in self._engines:
                    self._engines[alias] = self._engines[target_key]

        for alias, display_name in _LEGACY_TANK_ALIASES.items():
            if display_name in self._name_to_tank_key:
                target_key = self._name_to_tank_key[display_name]
                if alias not in self._tanks:
                    self._tanks[alias] = self._tanks[target_key]

        for alias, display_name in _LEGACY_PART_ALIASES.items():
            if display_name in self._name_to_part_key:
                target_key = self._name_to_part_key[display_name]
                if alias not in self._parts:
                    self._parts[alias] = self._parts[target_key]

    # --- Lookups ---

    def get_engine(self, key_or_name: str) -> Engine:
        if key_or_name in self._engines:
            return self._engines[key_or_name]
        if key_or_name in self._name_to_engine_key:
            return self._engines[self._name_to_engine_key[key_or_name]]
        normalized = _normalize_key(key_or_name)
        if normalized in self._engines:
            return self._engines[normalized]
        raise KeyError(f"Engine not found: {key_or_name!r}")

    def get_tank(self, key_or_name: str) -> FuelTank:
        if key_or_name in self._tanks:
            return self._tanks[key_or_name]
        if key_or_name in self._name_to_tank_key:
            return self._tanks[self._name_to_tank_key[key_or_name]]
        normalized = _normalize_key(key_or_name)
        if normalized in self._tanks:
            return self._tanks[normalized]
        raise KeyError(f"Tank not found: {key_or_name!r}")

    def get_part(self, key_or_name: str) -> StructuralPart:
        if key_or_name in self._parts:
            return self._parts[key_or_name]
        if key_or_name in self._name_to_part_key:
            return self._parts[self._name_to_part_key[key_or_name]]
        normalized = _normalize_key(key_or_name)
        if normalized in self._parts:
            return self._parts[normalized]
        raise KeyError(f"Part not found: {key_or_name!r}")

    # --- Listings ---

    def list_engines(self, engine_type: Optional[str] = None) -> list[Engine]:
        seen = set()
        result = []
        for e in self._engines.values():
            if id(e) not in seen:
                seen.add(id(e))
                if engine_type is None or e.engine_type == engine_type:
                    result.append(e)
        return sorted(result, key=lambda e: e.name)

    def list_tanks(self, fuel_type: Optional[str] = None) -> list[FuelTank]:
        seen = set()
        result = []
        for t in self._tanks.values():
            if id(t) not in seen:
                seen.add(id(t))
                if fuel_type is None or t.fuel_type == fuel_type:
                    result.append(t)
        return sorted(result, key=lambda t: t.name)

    def list_parts(self, category: Optional[str] = None) -> list[StructuralPart]:
        seen = set()
        result = []
        for p in self._parts.values():
            if id(p) not in seen:
                seen.add(id(p))
                if category is None or p.category == category:
                    result.append(p)
        return sorted(result, key=lambda p: p.name)

    @property
    def engine_count(self) -> int:
        return len({id(e) for e in self._engines.values()})

    @property
    def tank_count(self) -> int:
        return len({id(t) for t in self._tanks.values()})

    @property
    def part_count(self) -> int:
        return len({id(p) for p in self._parts.values()})
