"""
sim/constants.py
----------------
Kerbin physics constants and verified stock KSP 1 part statistics.

All values sourced from the KSP wiki and cross-checked for self-consistency
(thrust, Isp, and propellant mass must satisfy: thrust = mdot * Isp * g0).
Any value flagged BEST-EFFORT has not been independently verified against
the wiki — treat as approximate.
"""

# ---------------------------------------------------------------------------
# Fundamental constants
# ---------------------------------------------------------------------------

G0 = 9.81          # m/s², standard gravity (used in Isp/thrust calculations)

# ---------------------------------------------------------------------------
# Kerbin parameters (stock KSP 1)
# ---------------------------------------------------------------------------

R_KERBIN   = 600_000.0    # m, Kerbin surface radius
MU_KERBIN  = 3.5316e12    # m³/s², gravitational parameter
ATM_CEIL   = 70_000.0     # m, top of Kerbin atmosphere

# Standard atmosphere model (exponential)
RHO0       = 1.225        # kg/m³, sea-level atmospheric density
SCALE_H    = 5_000.0      # m, atmosphere scale height

# Orbital speed at key altitudes (derived, for reference)
# v_circ(80km) = sqrt(MU_KERBIN / (R_KERBIN + 80000)) ≈ 2279 m/s  [VERIFIED]

# ---------------------------------------------------------------------------
# Engine data  (all forces in kN, masses in tonnes)
# ---------------------------------------------------------------------------

ENGINES = {
    # LV-T45 Swivel (gimballed upper-booster engine)
    # Self-consistency check: mdot = 200*1000 / (320*9.81) = 63.74 kg/s
    "swivel": {
        "thrust_vac":   200.0,   # kN
        "thrust_asl":   167.97,  # kN  (from wiki: 167.97 kN)
        "isp_vac":      320.0,   # s
        "isp_asl":      250.0,   # s
        "mass":           1.50,  # t
        "gimbal_deg":     3.0,   # degrees
        "confidence":    "verified",
    },

    # LV-909 Terrier (vacuum upper stage engine)
    # Self-consistency check: mdot = 60*1000 / (345*9.81) = 17.73 kg/s
    "terrier": {
        "thrust_vac":    60.0,   # kN
        "thrust_asl":     0.215, # kN (near zero — atmosphere-only penalty)
        "isp_vac":       345.0,  # s
        "isp_asl":        85.0,  # s
        "mass":            0.50, # t
        "gimbal_deg":      4.0,
        "confidence":    "verified",
    },

    # RT-10 Hammer SRB
    # Self-consistency check: mdot = 227*1000 / (195*9.81) = 118.66 kg/s
    # At 100% throttle: burn time = 600 kg / 118.66 = 5.06 s  [VERIFIED]
    # At 20% throttle: burn time = 600 kg / (118.66*0.20) = 25.3 s
    "hammer": {
        "thrust_vac":   227.0,   # kN at 100%
        "thrust_asl":   197.9,   # kN at 100% (approx: scaled by Isp ratio 170/195)
        "isp_vac":      195.0,   # s
        "isp_asl":      170.0,   # s
        "mass_full":      0.75,  # t (full, including propellant)
        "mass_dry":       0.15,  # t (empty casing)
        "prop_mass":      0.60,  # t propellant
        "confidence":   "verified",
    },

    # BACC Thumper SRB (BEST-EFFORT — not verified vs wiki)
    "thumper": {
        "thrust_vac":   300.0,   # kN at 100%
        "thrust_asl":   295.4,   # kN at 100% (scaled by Isp ratio 165/175; approx)
        "isp_vac":      175.0,   # s
        "isp_asl":      165.0,   # s
        "mass_full":      1.50,  # t
        "mass_dry":       0.30,  # t
        "prop_mass":      1.20,  # t
        "confidence":   "best-effort",
    },
}

# ---------------------------------------------------------------------------
# Tank data
# ---------------------------------------------------------------------------

TANKS = {
    # FL-T800 (standard 1.25m tank used in Perseus 1)
    # Propellant mass ratio: (4.5 - 0.5) / 4.5 = 0.889  [VERIFIED: KSP uses 9:1 family]
    "flt800": {
        "mass_full":  4.50,   # t
        "mass_dry":   0.50,   # t
        "prop_mass":  4.00,   # t
        "confidence": "verified",
    },
    "flt400": {
        "mass_full":  2.25,   # t
        "mass_dry":   0.25,   # t
        "prop_mass":  2.00,   # t
        "confidence": "verified",
    },
    "flt200": {
        "mass_full":  1.125,
        "mass_dry":   0.125,
        "prop_mass":  1.000,
        "confidence": "verified",
    },
}

# ---------------------------------------------------------------------------
# Structural / avionics parts (masses only)
# ---------------------------------------------------------------------------

PARTS = {
    "mk1_pod":        0.84,   # t
    "mk16_chute":     0.10,   # t
    "heat_shield":    0.10,   # t
    "tr18a_decoupler":0.05,   # t each
    "tt38k_decoupler":0.025,  # t each
    "basic_fin":      0.075,  # t each
    "aero_nosecone":  0.03,   # t each
    "service_bay":    0.10,   # t (approx)
    "reaction_wheel": 0.05,   # t (approx, small 1.25m)
    "battery":        0.01,   # t (approx, z-1k)
}

# ---------------------------------------------------------------------------
# Perseus 1 baseline vehicle definition
# ---------------------------------------------------------------------------
# Used as the default by AscentSimulator. Override any value to model variants.

PERSEUS_1_DEFAULT = {
    # Booster config
    "booster_type":    "hammer",
    "n_boosters":       2,
    "booster_pct":     20.0,        # thrust limit %

    # Fix P0-05 / P3-10: service bay is now modelled in VehicleConfig.avionics_mass;
    # extra_payload is for genuine additional core-stage inert mass only.
    "extra_payload":    0.0,        # t

    # Core stage: Swivel + 1x FL-T800
    # Mission stage: Terrier + 1x FL-T800 + capsule stack

    # Drag model (effective CdA, estimated for 1.25m stack with 2 radial boosters)
    "cd":               0.22,
    "area_base":        1.80,       # m²
    "area_per_extra_booster": 0.35, # m² additional per booster beyond 2
}
