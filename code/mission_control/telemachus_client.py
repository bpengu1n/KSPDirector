"""
mission_control/telemachus_client.py
-------------------------------------
Asynchronous Telemachus WebSocket client for Perseus 1 Mission Control.

Connects to the Telemachus KSP plugin's WebSocket data feed, subscribes to
the telemetry topics needed for ascent monitoring, and maintains a live
state dictionary that the mission control server can read at any time.

Telemachus WebSocket protocol:
    - Connect to: ws://[ksp-host]:8085/datalink
    - Subscribe:  send {"rate": N, "+": ["topic1", "topic2"]}
    - Receive:    JSON object {"topic": value, ...} at the requested rate (ms)
    - Unsubscribe: send {"-": ["topic1"]}

Common topic names (KSP 1, Telemachus 1.x):
    v.altitude            Altitude above sea level (m)
    v.velocity            Total velocity (m/s)
    v.verticalSpeed       Vertical component of velocity (m/s)
    v.surfaceVelocity     Horizontal surface velocity (m/s)
    o.ApA                 Apoapsis altitude (m)
    o.PeA                 Periapsis altitude (m)
    o.inclination         Orbital inclination (degrees)
    o.eccentricity        Orbital eccentricity
    p.heading             Vehicle heading (degrees)
    p.pitch               Vehicle pitch (-90 to +90, 0 = horizon)
    p.roll                Vehicle roll (degrees)
    t.universalTime       Universe time (s)
    t.missionTime         Mission elapsed time (s)
    f.throttle            Current throttle (0.0 to 1.0)
    r.resource[LiquidFuel]  Liquid fuel remaining (units)
    r.resource[SolidFuel]   Solid fuel remaining (units)
    v.atmosphericDensity  Atmospheric density (kg/m³)
    v.lat                 Latitude (degrees)
    v.long                Longitude (degrees)

NOTE: Topic names may vary by Telemachus version. Check your plugin's
topic list at http://[ksp-host]:8085/telemachus/datalink if subscriptions
do not produce data.
"""

import json
import logging
import math as _math
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Topics to subscribe to (adjust if your Telemachus version uses different names)
SUBSCRIBED_TOPICS = [
    "v.altitude",
    "v.velocity",
    "v.verticalSpeed",
    "v.surfaceVelocity",
    "o.ApA",
    "o.PeA",
    "o.inclination",
    "o.eccentricity",
    "p.heading",
    "p.pitch",
    "p.roll",
    "t.universalTime",
    "t.missionTime",
    "f.throttle",
    "r.resource[LiquidFuel]",
    "r.resource[SolidFuel]",
    "v.atmosphericDensity",
    "v.lat",
    "v.long",
]

# Human-readable field mapping: Telemachus topic -> internal key
FIELD_MAP = {
    "v.altitude":             "altitude",          # m
    "v.velocity":             "velocity",          # m/s
    "v.verticalSpeed":        "v_vert",            # m/s
    "v.surfaceVelocity":      "v_horiz",           # m/s (approx)
    "o.ApA":                  "apoapsis",          # m
    "o.PeA":                  "periapsis",         # m
    "o.inclination":          "inclination",       # deg
    "o.eccentricity":         "eccentricity",
    "p.heading":              "heading",           # deg
    "p.pitch":                "pitch",             # deg, +up/-down from horizon
    "p.roll":                 "roll",              # deg
    "t.universalTime":        "universal_time",    # s
    "t.missionTime":          "mission_time",      # s (MET)
    "f.throttle":             "throttle",          # 0-1
    "r.resource[LiquidFuel]": "liquid_fuel",
    "r.resource[SolidFuel]":  "solid_fuel",
    "v.atmosphericDensity":   "atm_density",       # kg/m³
    "v.lat":                  "latitude",          # deg
    "v.long":                 "longitude",         # deg
}

# Default / disconnected state (all zeros/None)
EMPTY_STATE = {v: None for v in FIELD_MAP.values()}

# ---------------------------------------------------------------------------
# Downrange computation (Fix P0-03)
# ---------------------------------------------------------------------------
_KM_PER_DEG_KERBIN = 600.0 * _math.pi / 180.0   # ~10.47 km/degree at equator
# Earth's value (111.12 km/deg) must NOT be used here.

def compute_downrange_km(lon_delta_deg: float, lat_deg: float) -> float:
    """
    Convert longitude delta (degrees east from launch longitude) to
    approximate downrange distance (km), accounting for Kerbin's geometry.

    Parameters
    ----------
    lon_delta_deg : float
        Longitude change from the launch site (degrees).
        Positive = eastward (direction of a 090° heading launch).
    lat_deg : float
        Current latitude (degrees). Used for the cos(lat) great-circle correction.

    Returns
    -------
    float
        Approximate downrange distance in km.

    Notes
    -----
    This is a flat-arc approximation valid for downrange distances << R_Kerbin.
    KSP KSC is at approximately latitude 0.06°, so the cos(lat) factor is
    negligibly close to 1.0 for a due-east launch from the stock launch site.

    Fix P0-03 (Engineering Review): previous formula used Earth's 111.12 km/degree
    scale and abs(lat) instead of cos(lat), overstating downrange by ~10.6×.
    """
    lat_rad = _math.radians(lat_deg)
    return abs(lon_delta_deg) * _KM_PER_DEG_KERBIN * _math.cos(lat_rad)


class TelematicusClient:
    """
    Runs a background thread that maintains a live telemetry state dict.

    Usage::

        client = TelematicusClient(host="192.168.1.100", rate_ms=100)
        client.start()

        # In your server code:
        state = client.get_state()
        print(state['altitude'], state['apoapsis'])

        # Register a callback for each update:
        client.on_update = lambda state: print(state['mission_time'])

        client.stop()
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8085,
                 rate_ms: int = 200):
        self.host = host
        self.port = port
        self.rate_ms = rate_ms
        self.url = f"ws://{host}:{port}/datalink"

        self._state: dict = dict(EMPTY_STATE)
        self._state["connected"] = False
        self._state["error"] = None
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.on_update: Optional[Callable[[dict], None]] = None

        # Accumulated trajectory for plotting (list of dicts)
        self._trajectory: list = []
        self._trajectory_lock = threading.Lock()
        # Launch longitude: captured at T+0 to compute delta-longitude for downrange
        self._launch_lon: Optional[float] = None

    def get_state(self) -> dict:
        """Return a snapshot of the current telemetry state (thread-safe)."""
        with self._lock:
            return dict(self._state)

    def get_trajectory(self) -> list:
        """Return the accumulated actual trajectory (thread-safe copy)."""
        with self._trajectory_lock:
            return list(self._trajectory)

    def clear_trajectory(self):
        with self._trajectory_lock:
            self._trajectory.clear()

    def start(self):
        """Start the background telemetry thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="telemachus-client")
        self._thread.start()
        logger.info("TelematicusClient started → %s", self.url)

    def stop(self):
        """Signal the background thread to stop and wait for it."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("TelematicusClient stopped")

    def _run(self):
        """Background loop: connect, subscribe, receive, reconnect on failure."""
        while not self._stop_event.is_set():
            try:
                self._connect_and_receive()
            except Exception as exc:
                logger.warning("Telemachus connection error: %s — retrying in 3s", exc)
                with self._lock:
                    self._state["connected"] = False
                    self._state["error"] = str(exc)
                time.sleep(3.0)

    def _connect_and_receive(self):
        try:
            import websocket
        except ImportError:
            raise ImportError(
                "websocket-client not installed. Run: pip install websocket-client"
            )

        ws = websocket.create_connection(self.url, timeout=5)
        try:
            # Subscribe to all topics
            sub_msg = json.dumps({"rate": self.rate_ms, "+": SUBSCRIBED_TOPICS})
            ws.send(sub_msg)
            with self._lock:
                self._state["connected"] = True
                self._state["error"] = None
            logger.info("Connected to Telemachus at %s", self.url)

            while not self._stop_event.is_set():
                raw = ws.recv()
                self._handle_message(raw)
        finally:
            ws.close()
            with self._lock:
                self._state["connected"] = False

    def _handle_message(self, raw: str):
        """Parse a Telemachus JSON message and update state."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

        with self._lock:
            for topic, value in data.items():
                key = FIELD_MAP.get(topic)
                if key:
                    self._state[key] = value

            # Build a trajectory point if we have position data
            alt = self._state.get("altitude")
            met = self._state.get("mission_time")
            if alt is not None and alt > 0 and met is not None and met > 0:
                lat = self._state.get("latitude", 0) or 0
                lon = self._state.get("longitude", 0) or 0

                # Capture launch longitude on first valid position fix
                if self._launch_lon is None and met < 3.0:
                    self._launch_lon = lon
                # Previous formula used Earth's 111.12 km/deg scale (10.6× error)
                # and abs(lat) instead of cos(lat).
                lon_delta = lon - (self._launch_lon if self._launch_lon is not None else lon)
                dr_km = compute_downrange_km(lon_delta, lat)

                point = {
                    "t": met,
                    "altitude_km": alt / 1000.0,
                    "downrange_km": dr_km,
                    "velocity": self._state.get("velocity", 0) or 0,
                    "apoapsis_km": (self._state.get("apoapsis") or 0) / 1000.0,
                    "periapsis_km": (self._state.get("periapsis") or 0) / 1000.0,
                    "pitch": self._state.get("pitch") or 0,
                }

        if alt is not None and alt > 0 and met is not None and met > 0:
            with self._trajectory_lock:
                # Fix P2-06: detect flight reset — MET drops below 5s after the
                # craft has been flying for over 30s — indicating a new launch.
                # Clear the trajectory and reset the launch longitude so the new
                # flight doesn't append onto the previous session's track.
                if (self._trajectory and
                        met < 5.0 and
                        self._trajectory[-1]["t"] > 30.0):
                    self._trajectory.clear()
                    self._launch_lon = None
                    logger.info("mission_time reset detected — trajectory cleared for new flight")

                # Downsample: only add a point if significant time has passed
                if not self._trajectory or (met - self._trajectory[-1]["t"]) > 0.5:
                    self._trajectory.append(point)

        if self.on_update:
            try:
                self.on_update(self.get_state())
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Simulation scenarios
# ---------------------------------------------------------------------------
# Each scenario is a list of keyframes: (t, state_dict_overrides).
# The sim interpolates between keyframes for smooth playback.
# Boost + Core phases reuse the actual sim trajectory; post-burnout
# phases are synthetic (the sim doesn't model Terrier).

import random as _random

# Kerbin constants (mirrored from sim.constants to avoid import dependency issues)
_MU = 3.5316e12
_R  = 600_000.0
_ATM_CEIL = 70_000.0
_G0 = 9.81


def _lerp(a, b, f):
    """Linear interpolation between a and b by fraction f."""
    return a + (b - a) * f


def _grav(h):
    r = _R + h
    return _MU / (r * r)


def _orbital_params(h, v, gamma):
    """Returns (apo_m, pe_m) above surface."""
    r = _R + h
    energy = 0.5 * v * v - _MU / r
    if energy >= 0:
        return float("inf"), float("-inf")
    a = -_MU / (2.0 * energy)
    h_mom = r * v * _math.cos(gamma)
    ecc_sq = 1.0 - (h_mom * h_mom) / (_MU * a)
    ecc = _math.sqrt(max(0.0, ecc_sq))
    apo = a * (1.0 + ecc) - _R
    per = a * (1.0 - ecc) - _R
    return apo, per


def _propagate_coast(h0, v0, gamma0, dr0, duration, dt=0.5, sample_dt=2.0):
    """Propagate a ballistic (no thrust) trajectory using 2D gravity-turn equations.

    Returns list of keyframe dicts at sample_dt intervals.
    """
    h, v, gamma, dr = h0, v0, gamma0, dr0
    t = 0.0
    last_sample = -sample_dt
    kf = []

    while t <= duration + dt * 0.5:
        if t - last_sample >= sample_dt - dt * 0.01 or t == 0.0:
            apo, per = _orbital_params(h, v, gamma)
            v_h = v * _math.cos(gamma)
            v_v = v * _math.sin(gamma)
            kf.append({
                "altitude": h, "velocity": v, "v_vert": v_v, "v_horiz": v_h,
                "apoapsis": apo, "periapsis": per,
                "pitch": _math.degrees(gamma), "heading": 90.0,
                "roll": 0.0, "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
                "phase": "COAST", "downrange": dr, "_dt": t,
            })
            last_sample = t

        g = _grav(h)
        r = _R + h
        dv = -g * _math.sin(gamma)
        dgamma = _math.cos(gamma) * (v / r - g / v) if v > 1.0 else 0.0
        dh = v * _math.sin(gamma)
        ddr = v * _math.cos(gamma)

        v += dv * dt
        gamma += dgamma * dt
        h += dh * dt
        dr += ddr * dt
        t += dt

        if h <= 0:
            h = 0
            break

    return kf


def _propagate_thrust(h0, v0, gamma0, dr0, mass0_kg, thrust_vac_n, isp_vac,
                      duration, prop_mass_kg=None,
                      target_apo_m=None, target_pe_m=None,
                      target_alt_m=None, dt=0.5, sample_dt=5.0,
                      phase="TERRIER", lf_start=360):
    """Propagate a powered trajectory with prograde-biased steering.

    When target_alt_m is set, adds a pitch-up bias to the gravity-turn that
    smoothly decreases as orbital velocity is approached — mimicking how a KSP
    player steers above prograde to climb from low suborbital to target orbit.
    Cuts thrust when propellant runs out.
    Returns list of keyframe dicts at sample_dt intervals.
    """
    h, v, gamma, dr = h0, v0, gamma0, dr0
    mass = mass0_kg
    mdot = thrust_vac_n / (isp_vac * _G0)
    if prop_mass_kg is not None:
        prop_total = prop_mass_kg
    else:
        prop_total = mass0_kg * 0.64
    prop_remaining = prop_total
    t = 0.0
    last_sample = -sample_dt
    kf = []

    v_target = _math.sqrt(_MU / (_R + (target_alt_m or 80_000)))

    while t <= duration + dt * 0.5:
        thrusting = prop_remaining > 0.1
        throttle = 1.0 if thrusting else 0.0

        if t - last_sample >= sample_dt - dt * 0.01 or t == 0.0:
            apo, per = _orbital_params(h, v, gamma)
            v_h = v * _math.cos(gamma)
            v_v = v * _math.sin(gamma)
            fuel_frac = max(0, prop_remaining / prop_total) if prop_total > 0 else 0
            kf.append({
                "altitude": h, "velocity": v, "v_vert": v_v, "v_horiz": v_h,
                "apoapsis": apo, "periapsis": per,
                "pitch": _math.degrees(gamma), "heading": 90.0,
                "roll": 0.0, "throttle": throttle,
                "liquid_fuel": max(0, lf_start * fuel_frac),
                "solid_fuel": 0,
                "phase": phase, "downrange": dr, "_dt": t,
            })
            last_sample = t

        if target_apo_m is not None and target_pe_m is not None:
            apo_now, pe_now = _orbital_params(h, v, gamma)
            if apo_now >= target_apo_m * 0.95 and pe_now >= target_pe_m:
                apo, per = _orbital_params(h, v, gamma)
                v_h = v * _math.cos(gamma)
                v_v = v * _math.sin(gamma)
                fuel_frac = max(0, prop_remaining / prop_total) if prop_total > 0 else 0
                kf.append({
                    "altitude": h, "velocity": v, "v_vert": v_v, "v_horiz": v_h,
                    "apoapsis": apo, "periapsis": per,
                    "pitch": _math.degrees(gamma), "heading": 90.0,
                    "roll": 0.0, "throttle": 0.0,
                    "liquid_fuel": max(0, lf_start * fuel_frac),
                    "solid_fuel": 0,
                    "phase": "ORBIT", "downrange": dr, "_dt": t,
                })
                break

        g = _grav(h)
        r = _R + h
        accel = (thrust_vac_n / mass) if thrusting else 0.0

        dgamma_gt = _math.cos(gamma) * (v / r - g / v) if v > 1.0 else 0.0

        if target_alt_m is not None and thrusting:
            apo_now, _ = _orbital_params(h, v, gamma)
            if apo_now < target_alt_m:
                climb_ang = min(20.0, max(5.0, (target_alt_m - h) / 4000.0))
                gamma_target = _math.radians(climb_ang)
            else:
                alt_err = target_alt_m - h
                gamma_target = _math.radians(max(-2.0, min(5.0, alt_err / 10000.0)))
            error = gamma_target - gamma
            steer_rate = max(-0.04, min(0.04, error * 1.0))
            dgamma = steer_rate
        else:
            dgamma = dgamma_gt

        dv = accel - g * _math.sin(gamma)
        dh = v * _math.sin(gamma)
        ddr = v * _math.cos(gamma)

        v += dv * dt
        gamma += dgamma * dt
        h += dh * dt
        dr += ddr * dt

        if thrusting:
            dm = mdot * dt
            mass -= dm
            prop_remaining -= dm
        t += dt

        if h <= 0:
            h = 0
            break

    return kf


def _build_ascent_keyframes(nom_pts, noise_pct=0.02, pitch_bias=0.0,
                            vel_scale=1.0):
    """Convert nominal sim TrajectoryPoints into keyframe dicts."""
    kf = []
    for p in nom_pts:
        n = lambda v: v * (1 + _random.uniform(-noise_pct, noise_pct))
        alt = n(p.altitude * vel_scale) if vel_scale != 1.0 else n(p.altitude)
        vel = n(p.velocity * vel_scale)
        apo = n(p.apoapsis * 1000) if p.apoapsis else 0
        per = p.periapsis * 1000 if p.periapsis else -600000
        kf.append({
            "t": p.t,
            "altitude": alt,
            "velocity": vel,
            "v_vert": n(p.v_vert * vel_scale),
            "v_horiz": n(p.v_horiz * vel_scale),
            "apoapsis": apo,
            "periapsis": per,
            "pitch": n(90.0 - p.pitch_from_v) + pitch_bias,
            "heading": 90.0,
            "roll": _random.uniform(-2, 2),
            "throttle": 1.0 if p.phase in ("BOOST", "CORE") else 0.0,
            "liquid_fuel": max(0, 360 - p.t * (360 / 60)),
            "solid_fuel": max(0, 160 - p.t * (160 / 25.3)) if p.t < 25.3 else 0,
            "phase": p.phase,
            "downrange": p.downrange,
        })
    return kf


def _interp_keyframes(keyframes, t):
    """Interpolate between two keyframes at time t. Returns a state dict."""
    if not keyframes:
        return None
    if t <= keyframes[0]["t"]:
        return dict(keyframes[0])
    if t >= keyframes[-1]["t"]:
        return dict(keyframes[-1])
    for i in range(len(keyframes) - 1):
        if keyframes[i]["t"] <= t <= keyframes[i + 1]["t"]:
            a, b = keyframes[i], keyframes[i + 1]
            dt = b["t"] - a["t"]
            f = (t - a["t"]) / dt if dt > 0 else 0
            result = {}
            for k in a:
                va, vb = a[k], b.get(k, a[k])
                if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                    result[k] = _lerp(va, vb, f)
                else:
                    result[k] = va if f < 0.5 else vb
            return result
    return dict(keyframes[-1])


def _burnout_state(kf_list):
    """Extract burnout state from the last ascent keyframe."""
    last = kf_list[-1]
    gamma = _math.radians(last["pitch"])
    return (last["altitude"], last["velocity"], gamma,
            last["downrange"], last["t"])


def _stamp_time(keyframes, t0):
    """Set absolute 't' on propagated keyframes using their relative '_dt'."""
    for k in keyframes:
        k["t"] = t0 + k.pop("_dt")
    return keyframes


def _coast_to_apoapsis(h0, v0, gamma0, dr0, margin_s=2.0):
    """Coast until near apoapsis (v_vert crosses zero), return keyframes."""
    kf = _propagate_coast(h0, v0, gamma0, dr0, duration=300.0,
                          dt=0.25, sample_dt=2.0)
    # Find apoapsis: where v_vert first goes negative
    for i, k in enumerate(kf):
        if k["v_vert"] < 0 and k["_dt"] > 5.0:
            # Back up by margin_s to catch just before apoapsis
            cut_dt = max(5.0, k["_dt"] - margin_s)
            return [x for x in kf if x["_dt"] <= cut_dt]
    return kf


def _scenario_nominal(nom_pts):
    """Nominal: full orbit insertion. Boost → Core → Coast → Terrier → Orbit."""
    kf = _build_ascent_keyframes(nom_pts)
    h0, v0, gamma0, dr0, t0 = _burnout_state(kf)

    coast_kf = _coast_to_apoapsis(h0, v0, gamma0, dr0)
    _stamp_time(coast_kf, t0)

    # Terrier ignition after coast (at/near apoapsis)
    c_last = coast_kf[-1]
    th0 = c_last["altitude"]
    tv0 = c_last["velocity"]
    tg0 = _math.radians(c_last["pitch"])
    tdr0 = c_last["downrange"]
    tt0 = c_last["t"]

    # Mission stage: 6.25t wet (2.25t dry + 4.0t FL-T800 propellant)
    mission_mass_kg = 6250.0
    terrier_thrust_n = 60_000.0
    terrier_isp = 345.0
    fl_t800_prop_kg = 4000.0

    terrier_kf = _propagate_thrust(
        th0, tv0, tg0, tdr0, mission_mass_kg, terrier_thrust_n, terrier_isp,
        duration=250.0, prop_mass_kg=fl_t800_prop_kg,
        target_apo_m=80_000, target_pe_m=50_000,
        target_alt_m=80_000, dt=0.25, sample_dt=5.0,
        phase="TERRIER", lf_start=360)
    _stamp_time(terrier_kf, tt0)

    # Orbit coast — propagate from Terrier cutoff state
    orb_last = terrier_kf[-1]
    orb_t0 = orb_last["t"]
    orb_h = orb_last["altitude"]
    orb_v = orb_last["velocity"]
    orb_gamma = _math.radians(orb_last["pitch"])
    orb_dr = orb_last["downrange"]
    orb_lf = orb_last.get("liquid_fuel", 28)

    orbit_coast = _propagate_coast(orb_h, orb_v, orb_gamma, orb_dr,
                                   duration=60.0, dt=0.5, sample_dt=10.0)
    _stamp_time(orbit_coast, orb_t0)
    for oc in orbit_coast:
        oc["phase"] = "ORBIT"
        oc["liquid_fuel"] = orb_lf
    orbit_kf = orbit_coast

    total_dur = orbit_kf[-1]["t"]
    return kf + coast_kf + terrier_kf + orbit_kf, total_dur


def _scenario_subnominal(nom_pts):
    """Sub-nominal: degraded performance, still achieves orbit but eccentric."""
    kf = _build_ascent_keyframes(nom_pts, noise_pct=0.03, pitch_bias=-3.0)
    h0, v0, gamma0, dr0, t0 = _burnout_state(kf)

    # Degrade burnout state: 7% less velocity, steeper gamma
    v0 *= 0.93
    gamma0 = _math.radians(45.0)

    coast_kf = _coast_to_apoapsis(h0, v0, gamma0, dr0)
    _stamp_time(coast_kf, t0)

    c_last = coast_kf[-1]
    th0, tv0 = c_last["altitude"], c_last["velocity"]
    tg0 = _math.radians(c_last["pitch"])
    tdr0, tt0 = c_last["downrange"], c_last["t"]

    mission_mass_kg = 6250.0
    terrier_kf = _propagate_thrust(
        th0, tv0, tg0, tdr0, mission_mass_kg, 60_000.0, 345.0,
        duration=280.0, prop_mass_kg=4000.0,
        target_apo_m=78_000, target_pe_m=35_000,
        target_alt_m=78_000, dt=0.25, sample_dt=5.0,
        phase="TERRIER", lf_start=360)
    _stamp_time(terrier_kf, tt0)

    orb_last = terrier_kf[-1]
    orb_t0 = orb_last["t"]
    orb_h = orb_last["altitude"]
    orb_v = orb_last["velocity"]
    orb_gamma = _math.radians(orb_last["pitch"])
    orb_dr = orb_last["downrange"]
    orb_lf = orb_last.get("liquid_fuel", 8)

    orbit_coast = _propagate_coast(orb_h, orb_v, orb_gamma, orb_dr,
                                   duration=60.0, dt=0.5, sample_dt=10.0)
    _stamp_time(orbit_coast, orb_t0)
    for oc in orbit_coast:
        oc["phase"] = "ORBIT"
        oc["liquid_fuel"] = orb_lf
    orbit_kf = orbit_coast

    total_dur = orbit_kf[-1]["t"]
    return kf + coast_kf + terrier_kf + orbit_kf, total_dur


def _scenario_abort(nom_pts):
    """Engine failure at T+42s, successful abort and capsule recovery."""
    kf = _build_ascent_keyframes(nom_pts)
    kf = [k for k in kf if k["t"] <= 42.0]
    last = kf[-1] if kf else kf[0]

    # Brief engine failure transition (hand-crafted, 4s event)
    abort_start = [
        {"t": 42.5, "altitude": last["altitude"], "velocity": last["velocity"] * 0.98,
         "v_vert": last["v_vert"] * 0.95, "v_horiz": last["v_horiz"],
         "apoapsis": last["apoapsis"], "periapsis": last["periapsis"],
         "pitch": last["pitch"] - 5, "heading": 88.0, "roll": 8.0,
         "throttle": 0.2, "liquid_fuel": 200, "solid_fuel": 0,
         "phase": "ABORT", "downrange": last["downrange"]},
        {"t": 44.0, "altitude": last["altitude"] + 300, "velocity": last["velocity"] * 0.9,
         "v_vert": last["v_vert"] * 0.7, "v_horiz": last["v_horiz"] * 0.85,
         "apoapsis": last["apoapsis"] * 0.9, "periapsis": -620000,
         "pitch": last["pitch"] - 15, "heading": 85.0, "roll": 25.0,
         "throttle": 0.0, "liquid_fuel": 195, "solid_fuel": 0,
         "phase": "ABORT", "downrange": last["downrange"] + 500},
    ]

    # Capsule separates at T+46 with reduced velocity
    sep_v = last["velocity"] * 0.55
    sep_gamma = _math.radians(36.0)
    sep_alt = last["altitude"] + 500
    sep_dr = last["downrange"] + 1000

    abort_start.append({
        "t": 46.0, "altitude": sep_alt, "velocity": sep_v,
        "v_vert": sep_v * _math.sin(sep_gamma),
        "v_horiz": sep_v * _math.cos(sep_gamma),
        "apoapsis": last["apoapsis"] * 0.6, "periapsis": -630000,
        "pitch": _math.degrees(sep_gamma), "heading": 88.0, "roll": 5.0,
        "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
        "phase": "ABORT", "downrange": sep_dr,
    })

    # Physics-propagated ballistic coast of the capsule
    coast_kf = _propagate_coast(sep_alt, sep_v, sep_gamma, sep_dr,
                                duration=120.0, dt=0.25, sample_dt=3.0)
    _stamp_time(coast_kf, 46.0)
    for ck in coast_kf:
        ck["phase"] = "ABORT"

    # Find where capsule drops below 5km for chute deploy
    chute_idx = len(coast_kf)
    for i, ck in enumerate(coast_kf):
        if ck["altitude"] <= 5000 and ck["v_vert"] < 0:
            chute_idx = i
            break

    abort_coast = coast_kf[:chute_idx]

    # Chute and landing from wherever we are
    if chute_idx < len(coast_kf):
        chute_pt = coast_kf[chute_idx]
    else:
        chute_pt = coast_kf[-1]

    chute_t = chute_pt["t"]
    chute_dr = chute_pt["downrange"]
    chute_kf = [
        {"t": chute_t, "altitude": chute_pt["altitude"],
         "velocity": chute_pt["velocity"],
         "v_vert": chute_pt["v_vert"], "v_horiz": chute_pt["v_horiz"],
         "apoapsis": 0, "periapsis": -640000,
         "pitch": _math.degrees(_math.atan2(chute_pt["v_vert"], max(1, chute_pt["v_horiz"]))),
         "heading": 89.5, "roll": 0.0,
         "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "CHUTE", "downrange": chute_dr},
        {"t": chute_t + 15, "altitude": 2500, "velocity": 12,
         "v_vert": -8, "v_horiz": 9,
         "apoapsis": 0, "periapsis": -640000,
         "pitch": -50.0, "heading": 90.0, "roll": 0.0,
         "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "CHUTE", "downrange": chute_dr + 200},
        {"t": chute_t + 40, "altitude": 200, "velocity": 8,
         "v_vert": -7, "v_horiz": 3,
         "apoapsis": 0, "periapsis": -640000,
         "pitch": -70.0, "heading": 90.0, "roll": 0.0,
         "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "CHUTE", "downrange": chute_dr + 300},
        {"t": chute_t + 50, "altitude": 0, "velocity": 6,
         "v_vert": -6, "v_horiz": 1,
         "apoapsis": 0, "periapsis": 0,
         "pitch": -85.0, "heading": 90.0, "roll": 0.0,
         "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "LANDED", "downrange": chute_dr + 320},
    ]

    total_dur = chute_kf[-1]["t"]
    return kf + abort_start + abort_coast + chute_kf, total_dur


def _scenario_catastrophic(nom_pts):
    """Structural failure at max-Q (~T+15s). Loss of vehicle."""
    kf = _build_ascent_keyframes(nom_pts)
    kf = [k for k in kf if k["t"] <= 15.0]
    last = kf[-1] if kf else kf[0]

    # Breakup event (hand-crafted 3s transition)
    fail_start = [
        {"t": 15.5, "altitude": last["altitude"], "velocity": last["velocity"] * 1.02,
         "v_vert": last["v_vert"], "v_horiz": last["v_horiz"],
         "apoapsis": last["apoapsis"], "periapsis": last["periapsis"],
         "pitch": last["pitch"] + 10, "heading": 85.0, "roll": 30.0,
         "throttle": 1.0, "liquid_fuel": 300, "solid_fuel": 80,
         "phase": "ABORT", "downrange": last["downrange"]},
        {"t": 16.5, "altitude": last["altitude"] + 100, "velocity": last["velocity"] * 0.8,
         "v_vert": last["v_vert"] * 0.5, "v_horiz": last["v_horiz"] * 0.6,
         "apoapsis": last["apoapsis"] * 0.5, "periapsis": -640000,
         "pitch": last["pitch"] + 45, "heading": 70.0, "roll": 120.0,
         "throttle": 0.0, "liquid_fuel": 280, "solid_fuel": 70,
         "phase": "ABORT", "downrange": last["downrange"] + 100},
    ]

    # Debris state after breakup: mostly vertical energy lost, some horiz remains
    debris_v = last["velocity"] * 0.4
    debris_gamma = _math.radians(-15.0)
    debris_alt = max(500, last["altitude"] - 200)
    debris_dr = last["downrange"] + 200

    # Physics-propagated debris ballistic fall
    debris_coast = _propagate_coast(debris_alt, debris_v, debris_gamma, debris_dr,
                                    duration=60.0, dt=0.25, sample_dt=2.0)
    _stamp_time(debris_coast, 18.0)
    for dk in debris_coast:
        dk["phase"] = "LOV"
        dk["liquid_fuel"] = 0
        dk["solid_fuel"] = 0
        dk["heading"] = max(15, 45 - (dk["t"] - 18.0))
        dk["roll"] = max(0, 45 - (dk["t"] - 18.0) * 2)

    # Truncate at ground impact
    lov_kf = []
    for dk in debris_coast:
        lov_kf.append(dk)
        if dk["altitude"] <= 0:
            dk["altitude"] = 0
            break

    # Ensure we end at ground level
    if lov_kf and lov_kf[-1]["altitude"] > 0:
        final = dict(lov_kf[-1])
        final["t"] = lov_kf[-1]["t"] + 2
        final["altitude"] = 0
        final["velocity"] = lov_kf[-1]["velocity"]
        final["v_vert"] = -lov_kf[-1]["velocity"]
        final["v_horiz"] = 10
        final["pitch"] = -89.0
        final["phase"] = "LOV"
        lov_kf.append(final)

    total_dur = lov_kf[-1]["t"] if lov_kf else 40.0
    return kf + fail_start + lov_kf, total_dur


SCENARIOS = {
    "nominal": {
        "label": "Nominal — Full Orbit",
        "builder": _scenario_nominal,
    },
    "subnominal": {
        "label": "Sub-nominal — Degraded Orbit",
        "builder": _scenario_subnominal,
    },
    "abort": {
        "label": "Engine Failure — Abort & Recovery",
        "builder": _scenario_abort,
    },
    "catastrophic": {
        "label": "Max-Q Breakup — Loss of Vehicle",
        "builder": _scenario_catastrophic,
    },
}


class SimulatedTelemetry:
    """
    Stand-in for TelematicusClient when no KSP game is running.
    Plays back scenario-driven telemetry with slight noise, allowing
    the mission control interface to be developed and tested offline.

    Supports multiple selectable scenarios, play/pause, and restart.

    Usage::

        client = SimulatedTelemetry()
        client.start()
        state = client.get_state()   # same interface as TelematicusClient
        client.set_scenario('abort')
        client.pause()
        client.resume()
        client.restart()
    """

    def __init__(self, rate_ms: int = 200, noise_pct: float = 0.02):
        self.rate_ms = rate_ms
        self.noise_pct = noise_pct
        self._state: dict = dict(EMPTY_STATE)
        self._state["connected"] = True
        self._state["simulated"] = True
        self._trajectory: list = []
        self._lock = threading.Lock()
        self._trajectory_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.on_update: Optional[Callable[[dict], None]] = None
        self._nom_pts = None
        self._start_time = None

        self._scenario_name = "nominal"
        self._keyframes = []
        self._scenario_duration = 300.0
        self._paused = False
        self._pause_elapsed = 0.0
        self._finished = False
        self._sim_status_callback: Optional[Callable[[dict], None]] = None

    def _load_nominal(self):
        """Load the nominal trajectory from the sim package."""
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from sim import run_ascent
        result = run_ascent()
        return result.points

    def _build_scenario(self, name):
        """Build keyframes for the named scenario."""
        if self._nom_pts is None:
            self._nom_pts = self._load_nominal()
        builder = SCENARIOS[name]["builder"]
        kf, duration = builder(self._nom_pts)
        return kf, duration

    def get_state(self) -> dict:
        with self._lock:
            return dict(self._state)

    def get_trajectory(self) -> list:
        with self._trajectory_lock:
            return list(self._trajectory)

    def clear_trajectory(self):
        with self._trajectory_lock:
            self._trajectory.clear()

    def get_sim_status(self) -> dict:
        return {
            "scenario": self._scenario_name,
            "paused": self._paused,
            "finished": self._finished,
            "scenarios": {k: v["label"] for k, v in SCENARIOS.items()},
        }

    def set_scenario(self, name: str):
        """Switch to a different scenario and restart."""
        if name not in SCENARIOS:
            return
        self._scenario_name = name
        self.restart()

    def pause(self):
        if not self._paused and not self._finished:
            self._paused = True
            self._pause_elapsed = time.time() - self._start_time if self._start_time else 0
            self._notify_status()

    def resume(self):
        if self._paused and not self._finished:
            self._paused = False
            self._start_time = time.time() - self._pause_elapsed
            self._notify_status()

    def restart(self):
        """Restart current scenario from T+0."""
        self._finished = False
        self._paused = False
        self._keyframes, self._scenario_duration = self._build_scenario(self._scenario_name)
        self._start_time = time.time()
        self._pause_elapsed = 0.0
        with self._trajectory_lock:
            self._trajectory.clear()
        self._notify_status()

    def _notify_status(self):
        if self._sim_status_callback:
            try:
                self._sim_status_callback(self.get_sim_status())
            except Exception:
                pass

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="sim-telemetry")
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)

    def _run(self):
        try:
            self._nom_pts = self._load_nominal()
        except Exception as e:
            logger.error("SimulatedTelemetry: could not load nominal: %s", e)
            return

        self._keyframes, self._scenario_duration = self._build_scenario(self._scenario_name)
        self._start_time = time.time()
        self._notify_status()

        while not self._stop_event.is_set():
            if self._paused or self._finished:
                time.sleep(self.rate_ms / 1000.0)
                continue

            elapsed = time.time() - self._start_time

            # Fix P2-06: detect trajectory reset
            with self._trajectory_lock:
                if (elapsed < 1.0 and self._trajectory and
                        self._trajectory[-1]["t"] > 30.0):
                    self._trajectory.clear()

            # Check for scenario completion
            if elapsed >= self._scenario_duration:
                elapsed = self._scenario_duration
                if not self._finished:
                    self._finished = True
                    self._notify_status()

            kf_state = _interp_keyframes(self._keyframes, elapsed)
            if kf_state is None:
                time.sleep(self.rate_ms / 1000.0)
                continue

            alt = kf_state.get("altitude", 0)
            apo = kf_state.get("apoapsis", 0)
            per = kf_state.get("periapsis", -600000)

            state = {
                "connected": True, "simulated": True,
                "altitude": alt,
                "velocity": kf_state.get("velocity", 0),
                "v_vert": kf_state.get("v_vert", 0),
                "v_horiz": kf_state.get("v_horiz", 0),
                "apoapsis": apo,
                "periapsis": per,
                "pitch": kf_state.get("pitch", 0),
                "heading": kf_state.get("heading", 90),
                "roll": kf_state.get("roll", 0),
                "mission_time": elapsed,
                "throttle": kf_state.get("throttle", 0),
                "liquid_fuel": kf_state.get("liquid_fuel", 0),
                "solid_fuel": kf_state.get("solid_fuel", 0),
                "atm_density": 1.225 * (2.718 ** (-alt / 5000)) if 0 < alt < 70000 else 0,
                "phase": kf_state.get("phase", "CORE"),
                "error": None,
            }

            with self._lock:
                self._state = state

            dr = kf_state.get("downrange", 0)
            traj_point = {
                "t": elapsed,
                "altitude_km": alt / 1000.0,
                "downrange_km": dr / 1000.0,
                "velocity": state["velocity"],
                "apoapsis_km": apo / 1000.0,
                "periapsis_km": per / 1000.0,
                "pitch": state["pitch"],
            }
            with self._trajectory_lock:
                if not self._trajectory or (elapsed - self._trajectory[-1]["t"]) > 0.5:
                    self._trajectory.append(traj_point)

            if self.on_update:
                try:
                    self.on_update(self.get_state())
                except Exception:
                    pass

            time.sleep(self.rate_ms / 1000.0)
