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

def _lerp(a, b, f):
    """Linear interpolation between a and b by fraction f."""
    return a + (b - a) * f


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


def _scenario_nominal(nom_pts):
    """Nominal: full orbit insertion. Boost → Core → Coast → Terrier → Orbit."""
    kf = _build_ascent_keyframes(nom_pts)
    last = kf[-1]
    t0 = last["t"]
    # Coast phase: T+61 to T+130 (coast to apoapsis ~24.6 km)
    coast_kf = [
        {"t": t0 + 1, "altitude": 15200, "velocity": 640, "v_vert": 380, "v_horiz": 510,
         "apoapsis": 24600, "periapsis": -587000, "pitch": 37.0, "heading": 90.0,
         "roll": 0.3, "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "COAST", "downrange": 9000},
        {"t": t0 + 30, "altitude": 22000, "velocity": 580, "v_vert": 120, "v_horiz": 565,
         "apoapsis": 24600, "periapsis": -587000, "pitch": 12.0, "heading": 90.0,
         "roll": 0.1, "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "COAST", "downrange": 24000},
        {"t": t0 + 55, "altitude": 24500, "velocity": 560, "v_vert": 10, "v_horiz": 560,
         "apoapsis": 24700, "periapsis": -587000, "pitch": 1.0, "heading": 90.0,
         "roll": 0.0, "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "COAST", "downrange": 40000},
    ]
    # Terrier ignition at apoapsis (~T+120), burn to orbit
    # Terrier Isp_vac=345s, thrust=60kN, mission stage ~6.3t
    # LF remaining: mission stage has FL-T800 = 360 units
    terrier_kf = [
        {"t": t0 + 60, "altitude": 24400, "velocity": 560, "v_vert": -5, "v_horiz": 560,
         "apoapsis": 24600, "periapsis": -587000, "pitch": 0.0, "heading": 90.0,
         "roll": 0.0, "throttle": 1.0, "liquid_fuel": 360, "solid_fuel": 0,
         "phase": "TERRIER", "downrange": 42000},
        {"t": t0 + 100, "altitude": 30000, "velocity": 900, "v_vert": 30, "v_horiz": 900,
         "apoapsis": 45000, "periapsis": -200000, "pitch": 2.0, "heading": 90.0,
         "roll": 0.1, "throttle": 1.0, "liquid_fuel": 280, "solid_fuel": 0,
         "phase": "TERRIER", "downrange": 70000},
        {"t": t0 + 150, "altitude": 55000, "velocity": 1400, "v_vert": 40, "v_horiz": 1400,
         "apoapsis": 68000, "periapsis": 10000, "pitch": 1.5, "heading": 90.0,
         "roll": 0.0, "throttle": 1.0, "liquid_fuel": 180, "solid_fuel": 0,
         "phase": "TERRIER", "downrange": 120000},
        {"t": t0 + 200, "altitude": 75000, "velocity": 1900, "v_vert": 15, "v_horiz": 1900,
         "apoapsis": 80000, "periapsis": 55000, "pitch": 0.5, "heading": 90.0,
         "roll": 0.0, "throttle": 1.0, "liquid_fuel": 90, "solid_fuel": 0,
         "phase": "TERRIER", "downrange": 200000},
        {"t": t0 + 240, "altitude": 79800, "velocity": 2270, "v_vert": 2, "v_horiz": 2270,
         "apoapsis": 80200, "periapsis": 79500, "pitch": 0.1, "heading": 90.0,
         "roll": 0.0, "throttle": 0.0, "liquid_fuel": 30, "solid_fuel": 0,
         "phase": "ORBIT", "downrange": 300000},
    ]
    # Stable orbit hold
    orbit_kf = [
        {"t": t0 + 260, "altitude": 80000, "velocity": 2279, "v_vert": 0, "v_horiz": 2279,
         "apoapsis": 80200, "periapsis": 79800, "pitch": 0.0, "heading": 90.0,
         "roll": 0.0, "throttle": 0.0, "liquid_fuel": 28, "solid_fuel": 0,
         "phase": "ORBIT", "downrange": 340000},
        {"t": t0 + 300, "altitude": 80000, "velocity": 2279, "v_vert": 0, "v_horiz": 2279,
         "apoapsis": 80100, "periapsis": 79900, "pitch": 0.0, "heading": 90.0,
         "roll": 0.0, "throttle": 0.0, "liquid_fuel": 28, "solid_fuel": 0,
         "phase": "ORBIT", "downrange": 400000},
    ]
    return kf + coast_kf + terrier_kf + orbit_kf, t0 + 300


def _scenario_subnominal(nom_pts):
    """Sub-nominal: degraded performance, still achieves orbit."""
    kf = _build_ascent_keyframes(nom_pts, noise_pct=0.03, pitch_bias=-3.0)
    last = kf[-1]
    t0 = last["t"]
    # Slightly worse burnout: lower apoapsis, needs more Terrier work
    ext_kf = [
        {"t": t0 + 1, "altitude": 14000, "velocity": 600, "v_vert": 340, "v_horiz": 480,
         "apoapsis": 20000, "periapsis": -600000, "pitch": 35.0, "heading": 90.0,
         "roll": 1.5, "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "COAST", "downrange": 8000},
        {"t": t0 + 40, "altitude": 19500, "velocity": 530, "v_vert": 60, "v_horiz": 527,
         "apoapsis": 20200, "periapsis": -600000, "pitch": 6.5, "heading": 90.0,
         "roll": 0.5, "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "COAST", "downrange": 28000},
        # Terrier ignition (earlier, lower)
        {"t": t0 + 50, "altitude": 19800, "velocity": 530, "v_vert": -10, "v_horiz": 530,
         "apoapsis": 20000, "periapsis": -600000, "pitch": -1.0, "heading": 90.0,
         "roll": 0.0, "throttle": 1.0, "liquid_fuel": 360, "solid_fuel": 0,
         "phase": "TERRIER", "downrange": 33000},
        {"t": t0 + 120, "altitude": 35000, "velocity": 1000, "v_vert": 50, "v_horiz": 1000,
         "apoapsis": 50000, "periapsis": -100000, "pitch": 3.0, "heading": 90.0,
         "roll": 0.2, "throttle": 1.0, "liquid_fuel": 230, "solid_fuel": 0,
         "phase": "TERRIER", "downrange": 80000},
        {"t": t0 + 200, "altitude": 65000, "velocity": 1700, "v_vert": 25, "v_horiz": 1700,
         "apoapsis": 75000, "periapsis": 30000, "pitch": 0.8, "heading": 90.0,
         "roll": 0.0, "throttle": 1.0, "liquid_fuel": 100, "solid_fuel": 0,
         "phase": "TERRIER", "downrange": 170000},
        # Achieves orbit but eccentric
        {"t": t0 + 260, "altitude": 76000, "velocity": 2250, "v_vert": 3, "v_horiz": 2250,
         "apoapsis": 78000, "periapsis": 72000, "pitch": 0.1, "heading": 90.0,
         "roll": 0.0, "throttle": 0.0, "liquid_fuel": 8, "solid_fuel": 0,
         "phase": "ORBIT", "downrange": 280000},
        {"t": t0 + 310, "altitude": 75500, "velocity": 2255, "v_vert": -1, "v_horiz": 2255,
         "apoapsis": 78000, "periapsis": 72000, "pitch": 0.0, "heading": 90.0,
         "roll": 0.0, "throttle": 0.0, "liquid_fuel": 8, "solid_fuel": 0,
         "phase": "ORBIT", "downrange": 350000},
    ]
    return kf + ext_kf, t0 + 310


def _scenario_abort(nom_pts):
    """Engine failure at T+42s, successful abort and capsule recovery."""
    kf = _build_ascent_keyframes(nom_pts)
    # Truncate at T+42s (core phase, Swivel failure)
    kf = [k for k in kf if k["t"] <= 42.0]
    last = kf[-1] if kf else kf[0]
    # Swivel fails — thrust drops, vehicle starts tumbling
    abort_kf = [
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
        # Abort separation — capsule separates, LES fires
        {"t": 46.0, "altitude": last["altitude"] + 500, "velocity": 350,
         "v_vert": 200, "v_horiz": 270,
         "apoapsis": last["apoapsis"] * 0.6, "periapsis": -630000,
         "pitch": 40.0, "heading": 88.0, "roll": 5.0,
         "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "ABORT", "downrange": last["downrange"] + 1000},
        # Ballistic arc — capsule coasting up then down
        {"t": 60.0, "altitude": last["altitude"] + 2000, "velocity": 280,
         "v_vert": 100, "v_horiz": 260,
         "apoapsis": last["apoapsis"] * 0.5, "periapsis": -640000,
         "pitch": 21.0, "heading": 89.0, "roll": 2.0,
         "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "ABORT", "downrange": last["downrange"] + 5000},
        {"t": 80.0, "altitude": last["altitude"], "velocity": 250,
         "v_vert": -30, "v_horiz": 245,
         "apoapsis": last["apoapsis"] * 0.4, "periapsis": -640000,
         "pitch": -7.0, "heading": 89.5, "roll": 1.0,
         "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "ABORT", "downrange": last["downrange"] + 12000},
        {"t": 110.0, "altitude": 6000, "velocity": 220,
         "v_vert": -120, "v_horiz": 180,
         "apoapsis": 0, "periapsis": -640000,
         "pitch": -33.0, "heading": 89.5, "roll": 0.5,
         "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "ABORT", "downrange": last["downrange"] + 22000},
        # Parachute deploy at ~5 km
        {"t": 120.0, "altitude": 4500, "velocity": 180,
         "v_vert": -100, "v_horiz": 150,
         "apoapsis": 0, "periapsis": -640000,
         "pitch": -33.0, "heading": 89.5, "roll": 0.0,
         "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "CHUTE", "downrange": last["downrange"] + 25000},
        # Under chute — slow descent
        {"t": 140.0, "altitude": 2500, "velocity": 12,
         "v_vert": -8, "v_horiz": 9,
         "apoapsis": 0, "periapsis": -640000,
         "pitch": -50.0, "heading": 90.0, "roll": 0.0,
         "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "CHUTE", "downrange": last["downrange"] + 26000},
        {"t": 170.0, "altitude": 200, "velocity": 8,
         "v_vert": -7, "v_horiz": 3,
         "apoapsis": 0, "periapsis": -640000,
         "pitch": -70.0, "heading": 90.0, "roll": 0.0,
         "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "CHUTE", "downrange": last["downrange"] + 26500},
        # Splashdown
        {"t": 180.0, "altitude": 0, "velocity": 6,
         "v_vert": -6, "v_horiz": 1,
         "apoapsis": 0, "periapsis": 0,
         "pitch": -85.0, "heading": 90.0, "roll": 0.0,
         "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "LANDED", "downrange": last["downrange"] + 26600},
    ]
    return kf + abort_kf, 180.0


def _scenario_catastrophic(nom_pts):
    """Structural failure at max-Q (~T+15s). Loss of vehicle."""
    kf = _build_ascent_keyframes(nom_pts)
    kf = [k for k in kf if k["t"] <= 15.0]
    last = kf[-1] if kf else kf[0]
    # Max-Q structural failure — rapid tumble, breakup
    fail_kf = [
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
        {"t": 18.0, "altitude": last["altitude"] - 200, "velocity": last["velocity"] * 0.5,
         "v_vert": -50, "v_horiz": last["v_horiz"] * 0.3,
         "apoapsis": 0, "periapsis": -640000,
         "pitch": -20.0, "heading": 45.0, "roll": -90.0,
         "throttle": 0.0, "liquid_fuel": 260, "solid_fuel": 60,
         "phase": "ABORT", "downrange": last["downrange"] + 200},
        # Debris falling
        {"t": 22.0, "altitude": last["altitude"] - 1500, "velocity": 180,
         "v_vert": -150, "v_horiz": 100,
         "apoapsis": 0, "periapsis": -640000,
         "pitch": -56.0, "heading": 30.0, "roll": 45.0,
         "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "LOV", "downrange": last["downrange"] + 500},
        {"t": 30.0, "altitude": max(100, last["altitude"] - 4000), "velocity": 200,
         "v_vert": -190, "v_horiz": 60,
         "apoapsis": 0, "periapsis": -640000,
         "pitch": -72.0, "heading": 20.0, "roll": 0.0,
         "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "LOV", "downrange": last["downrange"] + 800},
        {"t": 40.0, "altitude": 0, "velocity": 210,
         "v_vert": -210, "v_horiz": 10,
         "apoapsis": 0, "periapsis": 0,
         "pitch": -89.0, "heading": 15.0, "roll": 0.0,
         "throttle": 0.0, "liquid_fuel": 0, "solid_fuel": 0,
         "phase": "LOV", "downrange": last["downrange"] + 900},
    ]
    return kf + fail_kf, 40.0


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
