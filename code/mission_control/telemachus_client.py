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


class SimulatedTelemetry:
    """
    Stand-in for TelematicusClient when no KSP game is running.
    Plays back the nominal trajectory with slight noise, allowing
    the mission control interface to be developed and tested offline.

    Usage::

        client = SimulatedTelemetry()
        client.start()
        state = client.get_state()   # same interface as TelematicusClient
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
        self._nom_traj = None
        self._start_time = None

    def _load_nominal(self):
        """Load the nominal trajectory from the sim package."""
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from sim import run_ascent
        result = run_ascent()
        return result.points

    def get_state(self) -> dict:
        with self._lock:
            return dict(self._state)

    def get_trajectory(self) -> list:
        with self._trajectory_lock:
            return list(self._trajectory)

    def clear_trajectory(self):
        with self._trajectory_lock:
            self._trajectory.clear()

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
        import random
        try:
            pts = self._load_nominal()
        except Exception as e:
            logger.error("SimulatedTelemetry: could not load nominal: %s", e)
            return

        self._start_time = time.time()
        pt_idx = 0

        while not self._stop_event.is_set():
            elapsed = time.time() - self._start_time
            # Fix P2-06: if elapsed resets (e.g., start_time was reset externally),
            # clear the trajectory so the new simulated flight starts clean.
            with self._trajectory_lock:
                if (elapsed < 1.0 and self._trajectory and
                        self._trajectory[-1]["t"] > 30.0):
                    self._trajectory.clear()
            # Advance through nominal points up to current elapsed time
            while pt_idx + 1 < len(pts) and pts[pt_idx + 1].t <= elapsed:
                pt_idx += 1

            if pt_idx >= len(pts):
                pt_idx = len(pts) - 1

            p = pts[pt_idx]
            noise = lambda v: v * (1 + random.uniform(-self.noise_pct, self.noise_pct))

            alt = noise(p.altitude)
            apoapsis = noise(p.apoapsis * 1000) if p.apoapsis else 0
            periapsis = p.periapsis * 1000 if p.periapsis else -600000

            state = {
                "connected": True, "simulated": True,
                "altitude": alt,
                "velocity": noise(p.velocity),
                "v_vert": noise(p.v_vert),
                "v_horiz": noise(p.v_horiz),
                "apoapsis": apoapsis,
                "periapsis": periapsis,
                # Fix P0-04: convert to KSP / Telemachus pitch convention
                # KSP convention: +90° = straight up, 0° = horizontal
                # sim stores pitch_from_v: 0° = straight up, 90° = horizontal
                # These are complementary: ksp_pitch = 90 - pitch_from_v
                "pitch": noise(90.0 - p.pitch_from_v),
                "heading": 90.0,
                "roll": random.uniform(-2, 2),
                "mission_time": elapsed,
                "throttle": 1.0 if p.phase in ("BOOST", "CORE") else 0.0,
                # Fix P0-02: correct KSP unit values
                # LiquidFuel: FL-T800 = 360 units (1.8t at 0.005 t/unit, 9:11 LF:OX)
                # SolidFuel:  2x Hammer = 160 units (2 × 80; each 0.60t at 0.0075 t/unit)
                "liquid_fuel": max(0, 360 - elapsed * (360 / 60)),
                "solid_fuel":  max(0, 160 - elapsed * (160 / 25.3)) if elapsed < 25.3 else 0,
                "atm_density": 1.225 * (2.718 ** (-alt / 5000)) if alt < 70000 else 0,
                "phase": p.phase,
                "error": None,
            }

            with self._lock:
                self._state = state

            traj_point = {
                "t": elapsed,
                "altitude_km": alt / 1000.0,
                "downrange_km": p.downrange / 1000.0,
                "velocity": state["velocity"],
                "apoapsis_km": apoapsis / 1000.0,
                "periapsis_km": periapsis / 1000.0,
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
