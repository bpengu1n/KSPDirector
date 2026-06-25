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

Common topic names (verified against TeaGuild/Telemachus-1 source):
    v.altitude            Altitude above sea level (m)
    v.speed               Total speed (m/s) — NOT v.velocity (doesn't exist)
    v.verticalSpeed       Vertical component of velocity (m/s)
    v.surfaceSpeed        Surface speed (m/s) — NOT v.surfaceVelocity
    o.ApA                 Apoapsis altitude (m)
    o.PeA                 Periapsis altitude (m)
    o.inclination         Orbital inclination (degrees)
    o.eccentricity        Orbital eccentricity
    n.heading             Vehicle heading (degrees) — NOT p.heading
    n.pitch               Vehicle pitch (-90 to +90, 0 = horizon) — NOT p.pitch
    n.roll                Vehicle roll (degrees) — NOT p.roll
    t.universalTime       Universe time (s)
    v.missionTime         Mission elapsed time (s) — NOT t.missionTime
    f.throttle            Current throttle (0.0 to 1.0)
    r.resource[LiquidFuel]  Liquid fuel remaining (units)
    r.resource[SolidFuel]   Solid fuel remaining (units)
    r.resourceMax[Name]     Max resource capacity (units)
    v.mass                Vessel mass (tonnes)
    v.geeForce            G-force experienced
    v.mach                Mach number
    v.dynamicPressurekPa  Dynamic pressure (kPa)
    v.atmosphericDensity  Atmospheric density (kg/m³)
    v.lat                 Latitude (degrees)
    v.long                Longitude (degrees)
    dv.stageCount         Number of stages with delta-V
    dv.stageDVVac[n]      Per-stage delta-V vacuum (m/s)

Full schema: see code/telemachus_schema.json

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

# Topics to subscribe to — verified against TeaGuild/Telemachus-1 source.
# This is the base set; per-stage topics (dv.stageDVVac[0], etc.) are added
# dynamically after dv.stageCount is known.
SUBSCRIBED_TOPICS = [
    # Position / altitude
    "v.altitude",
    "v.heightFromTerrain",
    # Velocity — NOTE: v.velocity does NOT exist in Telemachus-1;
    # v.speed is total speed, v.surfaceSpeed is surface speed
    "v.verticalSpeed",
    "v.surfaceSpeed",
    "v.speed",
    # Orbital
    "o.ApA",
    "o.PeA",
    "o.inclination",
    "o.eccentricity",
    "o.sma",
    "o.period",
    "o.timeToAp",
    "o.timeToPe",
    "o.trueAnomaly",
    "o.lan",
    "o.argumentOfPeriapsis",
    # Attitude — NOTE: p.heading/p.pitch/p.roll do NOT exist;
    # Telemachus-1 uses n.heading/n.pitch/n.roll (navball frame)
    "n.heading",
    "n.pitch",
    "n.roll",
    # Time — NOTE: t.missionTime does NOT exist;
    # Telemachus-1 uses v.missionTime
    "t.universalTime",
    "v.missionTime",
    # Flight control
    "f.throttle",
    # Vessel-wide resources
    "r.resource[LiquidFuel]",
    "r.resource[SolidFuel]",
    "r.resource[Oxidizer]",
    "r.resource[ElectricCharge]",
    "r.resourceMax[LiquidFuel]",
    "r.resourceMax[SolidFuel]",
    "r.resourceMax[Oxidizer]",
    "r.resourceMax[ElectricCharge]",
    # Current-stage resources
    "r.resourceCurrent[LiquidFuel]",
    "r.resourceCurrent[SolidFuel]",
    "r.resourceCurrent[Oxidizer]",
    "r.resourceCurrentMax[LiquidFuel]",
    "r.resourceCurrentMax[SolidFuel]",
    "r.resourceCurrentMax[Oxidizer]",
    # Vessel mass / forces / atmosphere
    "v.mass",
    "v.geeForce",
    "v.mach",
    "v.dynamicPressurekPa",
    "v.atmosphericDensity",
    "v.lat",
    "v.long",
    # Stage info
    "v.currentStage",
    # Delta-V totals
    "dv.ready",
    "dv.stageCount",
    "dv.totalDVVac",
    "dv.totalDVASL",
    "dv.totalDVActual",
    "dv.totalBurnTime",
]

# Human-readable field mapping: Telemachus topic -> internal key
# Verified against TeaGuild/Telemachus-1 source (VesselDataHandlers.cs,
# FlightControlHandlers.cs, ResourceHandlers.cs, DeltaVHandlers.cs,
# SystemHandlers.cs).
FIELD_MAP = {
    "v.altitude":             "altitude",          # m ASL
    "v.heightFromTerrain":    "height_terrain",    # m AGL
    "v.verticalSpeed":        "v_vert",            # m/s
    "v.surfaceSpeed":         "v_horiz",           # m/s surface frame
    "v.speed":                "velocity",          # m/s total (orbital frame)
    "o.ApA":                  "apoapsis",          # m
    "o.PeA":                  "periapsis",         # m
    "o.inclination":          "inclination",       # deg
    "o.eccentricity":         "eccentricity",
    "o.sma":                  "sma",               # m
    "o.period":               "period",            # s
    "o.timeToAp":             "time_to_ap",        # s
    "o.timeToPe":             "time_to_pe",        # s
    "o.trueAnomaly":          "true_anomaly",      # deg
    "o.lan":                  "lan",               # deg
    "o.argumentOfPeriapsis":  "arg_pe",            # deg
    "n.heading":              "heading",           # deg (navball)
    "n.pitch":                "pitch",             # deg, +up/-down from horizon
    "n.roll":                 "roll",              # deg
    "t.universalTime":        "universal_time",    # s
    "v.missionTime":          "mission_time",      # s (MET)
    "f.throttle":             "throttle",          # 0-1
    "r.resource[LiquidFuel]": "liquid_fuel",
    "r.resource[SolidFuel]":  "solid_fuel",
    "r.resource[Oxidizer]":   "oxidizer",
    "r.resource[ElectricCharge]": "electric_charge",
    "r.resourceMax[LiquidFuel]": "liquid_fuel_max",
    "r.resourceMax[SolidFuel]":  "solid_fuel_max",
    "r.resourceMax[Oxidizer]":   "oxidizer_max",
    "r.resourceMax[ElectricCharge]": "electric_charge_max",
    "r.resourceCurrent[LiquidFuel]":  "stage_liquid_fuel",
    "r.resourceCurrent[SolidFuel]":   "stage_solid_fuel",
    "r.resourceCurrent[Oxidizer]":    "stage_oxidizer",
    "r.resourceCurrentMax[LiquidFuel]":  "stage_liquid_fuel_max",
    "r.resourceCurrentMax[SolidFuel]":   "stage_solid_fuel_max",
    "r.resourceCurrentMax[Oxidizer]":    "stage_oxidizer_max",
    "v.mass":                 "mass",              # tonnes
    "v.geeForce":             "g_force",
    "v.mach":                 "mach",
    "v.dynamicPressurekPa":   "dynamic_pressure",  # kPa
    "v.atmosphericDensity":   "atm_density",       # kg/m³
    "v.lat":                  "latitude",          # deg
    "v.long":                 "longitude",         # deg
    "v.currentStage":         "current_stage",
    "dv.ready":               "dv_ready",
    "dv.stageCount":          "dv_stage_count",
    "dv.totalDVVac":          "dv_total_vac",      # m/s
    "dv.totalDVASL":          "dv_total_asl",      # m/s
    "dv.totalDVActual":       "dv_total_actual",   # m/s
    "dv.totalBurnTime":       "dv_total_burn_time", # s
}

# Per-stage dV topic templates — expanded with actual stage indices at runtime
STAGE_DV_TOPICS = [
    "dv.stageDVVac", "dv.stageDVASL", "dv.stageDVActual",
    "dv.stageTWRVac", "dv.stageTWRASL", "dv.stageTWRActual",
    "dv.stageISPVac", "dv.stageISPASL", "dv.stageISPActual",
    "dv.stageThrustVac", "dv.stageThrustASL", "dv.stageThrustActual",
    "dv.stageBurnTime",
    "dv.stageMass", "dv.stageDryMass", "dv.stageFuelMass",
    "dv.stageStartMass", "dv.stageEndMass",
]

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
        self._state["stages"] = []
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.on_update: Optional[Callable[[dict], None]] = None

        # Accumulated trajectory for plotting (list of dicts)
        self._trajectory: list = []
        self._trajectory_lock = threading.Lock()
        # Launch longitude: captured at T+0 to compute delta-longitude for downrange
        self._launch_lon: Optional[float] = None
        # Per-stage dV subscriptions — expanded once dv.stageCount is known
        self._stage_topics_subscribed: int = 0
        self._stage_field_map: dict = {}

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
            sub_msg = json.dumps({"rate": self.rate_ms, "+": SUBSCRIBED_TOPICS})
            ws.send(sub_msg)
            with self._lock:
                self._state["connected"] = True
                self._state["error"] = None
                self._stage_topics_subscribed = 0
            logger.info("Connected to Telemachus at %s", self.url)

            while not self._stop_event.is_set():
                raw = ws.recv()
                self._handle_message(raw)
                self._maybe_subscribe_stage_topics(ws)
        finally:
            ws.close()
            with self._lock:
                self._state["connected"] = False

    def _maybe_subscribe_stage_topics(self, ws):
        with self._lock:
            stage_count = self._state.get("dv_stage_count")
            if not stage_count or not isinstance(stage_count, (int, float)):
                return
            stage_count = int(stage_count)
            if stage_count <= 0 or stage_count == self._stage_topics_subscribed:
                return

        topics = []
        field_map = {}
        for i in range(stage_count):
            for base in STAGE_DV_TOPICS:
                topic = f"{base}[{i}]"
                short = base.replace("dv.stage", "").lower()
                key = f"stage_{i}_{short}"
                topics.append(topic)
                field_map[topic] = key

        sub_msg = json.dumps({"+": topics})
        ws.send(sub_msg)
        with self._lock:
            self._stage_field_map.update(field_map)
            self._stage_topics_subscribed = stage_count
        logger.info("Subscribed to per-stage dV topics for %d stages", stage_count)

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
                else:
                    key = self._stage_field_map.get(topic)
                    if key:
                        self._state[key] = value

            self._rebuild_stages_locked()

            # Build a trajectory point if we have position data
            alt = self._state.get("altitude")
            met = self._state.get("mission_time")
            if alt is not None and alt > 0 and met is not None and met > 0:
                lat = self._state.get("latitude", 0) or 0
                lon = self._state.get("longitude", 0) or 0

                if self._launch_lon is None and met < 3.0:
                    self._launch_lon = lon
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
                if (self._trajectory and
                        met < 5.0 and
                        self._trajectory[-1]["t"] > 30.0):
                    self._trajectory.clear()
                    self._launch_lon = None
                    logger.info("mission_time reset detected — trajectory cleared for new flight")

                if not self._trajectory or (met - self._trajectory[-1]["t"]) > 0.5:
                    self._trajectory.append(point)

        if self.on_update:
            try:
                self.on_update(self.get_state())
            except Exception as exc:
                logger.warning("on_update callback error: %s", exc)

    def _rebuild_stages_locked(self):
        """Build the stages list from per-stage dV data in self._state. Caller holds _lock."""
        count = self._state.get("dv_stage_count")
        if not count or not isinstance(count, (int, float)):
            return
        count = int(count)
        stages = []
        for i in range(count):
            def _get(short):
                return self._state.get(f"stage_{i}_{short}")
            dv_vac = _get("dvvac")
            fuel_mass = _get("fuelmass")
            if dv_vac is None and fuel_mass is None:
                continue
            stages.append({
                "index": i,
                "dv_vac": _get("dvvac"),
                "dv_asl": _get("dvasl"),
                "dv_actual": _get("dvactual"),
                "twr_vac": _get("twrvac"),
                "twr_asl": _get("twrasl"),
                "twr_actual": _get("twractual"),
                "isp_vac": _get("ispvac"),
                "isp_asl": _get("ispasl"),
                "isp_actual": _get("ispactual"),
                "thrust_vac": _get("thrustvac"),
                "thrust_asl": _get("thrustasl"),
                "thrust_actual": _get("thrustactual"),
                "burn_time": _get("burntime"),
                "mass": _get("mass"),
                "dry_mass": _get("drymass"),
                "fuel_mass": _get("fuelmass"),
                "start_mass": _get("startmass"),
                "end_mass": _get("endmass"),
            })
        self._state["stages"] = stages


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

    def _compute_liquid_fuel_from_mass(self, mass, phase):
        mission_wet = 6.250
        mission_dry = 2.250
        core_dry_with_mission = 8.102
        if phase in ("BOOST", "CORE"):
            fuel_frac = max(0, (mass - core_dry_with_mission) /
                           (14.21 - core_dry_with_mission))
            return 360.0 * fuel_frac
        prop_remaining = max(0, mass - mission_dry)
        prop_total = mission_wet - mission_dry
        return 360.0 * min(1.0, prop_remaining / prop_total)

    @staticmethod
    def _extract_stage_timing(points):
        """Extract phase transition times from trajectory points."""
        srb_end = 25.3
        core_end = 61.0
        terrier_end = 61.0
        prev_phase = None
        for p in points:
            if prev_phase == "BOOST" and p.phase != "BOOST":
                srb_end = p.t
            if prev_phase == "CORE" and p.phase not in ("BOOST", "CORE"):
                core_end = p.t
            if prev_phase == "TERRIER" and p.phase != "TERRIER":
                terrier_end = p.t
            prev_phase = p.phase
        return {"srb_end": srb_end, "core_end": core_end,
                "terrier_start": core_end, "terrier_end": terrier_end}

    def _build_sim_stages(self, elapsed, timing):
        """Build stage list using time-based fuel depletion.

        All stages are always present. Each stage's dV depletes only
        during its active burn window. Status indicates whether the
        stage is pending, active, or depleted.
        """
        srb_end = timing["srb_end"]
        core_end = timing["core_end"]
        terrier_start = timing["terrier_start"]
        terrier_end = timing["terrier_end"]

        srb_initial_dv = 222.0
        core_initial_dv = 1100.0
        terrier_initial_dv = 3458.0

        if elapsed < srb_end:
            srb_frac = max(0, 1.0 - elapsed / srb_end)
            srb_status = "active"
        else:
            srb_frac = 0.0
            srb_status = "depleted"

        if elapsed < core_end:
            core_frac = max(0, 1.0 - elapsed / core_end)
            core_status = "active"
        else:
            core_frac = 0.0
            core_status = "depleted"

        if elapsed < terrier_start:
            terrier_frac = 1.0
            terrier_status = "pending"
        elif elapsed < terrier_end:
            terrier_frac = max(0, 1.0 - (elapsed - terrier_start) / (terrier_end - terrier_start))
            terrier_status = "active"
        else:
            terrier_frac = (terrier_end - terrier_start) / (terrier_end - terrier_start)
            burn_duration = terrier_end - terrier_start
            remaining_prop = 1.0 - burn_duration / max(0.01, burn_duration)
            terrier_frac = max(0, remaining_prop) if terrier_end < timing.get("total", 9999) else 0.0
            terrier_status = "depleted"

        # After terrier burn, maintain the remaining dV (coast with fuel left)
        if elapsed >= terrier_end:
            terrier_burn_frac = min(1.0, (terrier_end - terrier_start) / 225.0)
            terrier_frac = max(0, 1.0 - terrier_burn_frac)
            terrier_status = "depleted"

        return [
            {
                "index": 0, "label": "Stage 0",
                "dv_vac": srb_frac * srb_initial_dv,
                "dv_asl": srb_frac * 170.0,
                "dv_initial": srb_initial_dv,
                "fuel_mass": srb_frac * 1.200,
                "dry_mass": 0.908,
                "mass": srb_frac * 1.200 + 0.908,
                "burn_time": max(0, srb_end - elapsed) if srb_status == "active" else 0,
                "status": srb_status,
            },
            {
                "index": 1, "label": "Stage 1",
                "dv_vac": core_frac * core_initial_dv,
                "dv_asl": core_frac * 900.0,
                "dv_initial": core_initial_dv,
                "fuel_mass": core_frac * 4.0,
                "dry_mass": 1.8525,
                "mass": core_frac * 4.0 + 1.8525,
                "burn_time": max(0, core_end - elapsed) if core_status == "active" else 0,
                "status": core_status,
            },
            {
                "index": 2, "label": "Stage 2",
                "dv_vac": terrier_frac * terrier_initial_dv,
                "dv_asl": terrier_frac * 800.0,
                "dv_initial": terrier_initial_dv,
                "fuel_mass": terrier_frac * 4.0,
                "dry_mass": 2.250,
                "mass": terrier_frac * 4.0 + 2.250,
                "burn_time": max(0, terrier_end - elapsed) if terrier_status == "active" else 0,
                "status": terrier_status,
            },
        ]

    def _run(self):
        import random
        try:
            pts = self._load_nominal()
        except Exception as e:
            logger.error("SimulatedTelemetry: could not load nominal: %s", e)
            return

        self._start_time = time.time()
        pt_idx = 0
        timing = self._extract_stage_timing(pts)

        while not self._stop_event.is_set():
            elapsed = time.time() - self._start_time
            with self._trajectory_lock:
                if (elapsed < 1.0 and self._trajectory and
                        self._trajectory[-1]["t"] > 30.0):
                    self._trajectory.clear()
            while pt_idx + 1 < len(pts) and pts[pt_idx + 1].t <= elapsed:
                pt_idx += 1

            if pt_idx >= len(pts):
                pt_idx = len(pts) - 1

            p = pts[pt_idx]
            landed = (pt_idx >= len(pts) - 1 and elapsed > p.t and
                      p.altitude < 1000)

            noise = lambda v: v * (1 + random.uniform(-self.noise_pct, self.noise_pct))

            if landed:
                alt = 0.0
                vel = 0.0
                v_v = 0.0
                v_h = 0.0
                pitch = 0.0
                phase = "LANDED"
            else:
                alt = noise(p.altitude)
                vel = noise(p.velocity)
                v_v = noise(p.v_vert)
                v_h = noise(p.v_horiz)
                pitch = noise(90.0 - p.pitch_from_v)
                phase = p.phase

            apoapsis = noise(p.apoapsis * 1000) if p.apoapsis and not landed else 0
            periapsis = p.periapsis * 1000 if p.periapsis and not landed else 0

            lf = self._compute_liquid_fuel_from_mass(p.mass, p.phase)
            sf = max(0, 160 - elapsed * (160 / 25.3)) if elapsed < 25.3 else 0
            lf_max = 360.0
            sf_max = 160.0

            sim_stages = self._build_sim_stages(elapsed, timing)

            state = {
                "connected": True, "simulated": True,
                "altitude": alt,
                "velocity": vel,
                "v_vert": v_v,
                "v_horiz": v_h,
                "apoapsis": apoapsis,
                "periapsis": periapsis,
                "inclination": 0.0,
                "time_to_ap": max(0, 61 - elapsed) if not landed else None,
                "time_to_pe": None,
                "pitch": pitch,
                "heading": 90.0,
                "roll": random.uniform(-2, 2) if not landed else 0.0,
                "mission_time": elapsed,
                "throttle": 0.0 if landed else (1.0 if p.phase in ("BOOST", "CORE", "TERRIER", "CIRCULARIZE") else 0.0),
                "liquid_fuel": lf,
                "solid_fuel": sf,
                "liquid_fuel_max": lf_max,
                "solid_fuel_max": sf_max,
                "oxidizer": lf * (11.0 / 9.0),
                "oxidizer_max": lf_max * (11.0 / 9.0),
                "mass": p.mass,
                "g_force": noise(p.velocity / max(1, elapsed)) * 0.1 if not landed else 1.0,
                "mach": vel / 343.0 if alt < 70000 and not landed else 0.0,
                "dynamic_pressure": 0.5 * (1.225 * (2.718 ** (-alt / 5000))) * vel * vel / 1000.0 if alt < 70000 and not landed else 0.0,
                "atm_density": 1.225 if landed else (1.225 * (2.718 ** (-alt / 5000)) if alt < 70000 else 0),
                "phase": phase,
                "error": None,
                "stages": sim_stages,
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
                except Exception as exc:
                    logger.warning("SimulatedTelemetry on_update error: %s", exc)

            time.sleep(self.rate_ms / 1000.0)


class ScriptedTelemetry:
    """
    Telemetry source that runs the sim with a user-defined LaunchScenario
    and plays back with controllable speed, pause, and reset.

    Implements the same interface as TelematicusClient/SimulatedTelemetry:
      get_state(), get_trajectory(), clear_trajectory(), start(), stop()
    Plus playback controls:
      load_scenario(), pause(), resume(), reset(), set_speed()
    """

    def __init__(self, rate_ms: int = 200):
        self.rate_ms = rate_ms
        self._state: dict = dict(EMPTY_STATE)
        self._state["connected"] = True
        self._state["scripted"] = True
        self._trajectory: list = []
        self._lock = threading.Lock()
        self._trajectory_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.on_update: Optional[Callable[[dict], None]] = None

        self._points: list = []
        self._scenario = None
        self._sim_result = None
        self._vehicle_cfg = None

        self._playback_state = "stopped"
        self._speed = 1.0
        self._start_time: Optional[float] = None
        self._pause_time: Optional[float] = None
        self._pause_accumulated = 0.0

    def load_scenario(self, scenario) -> dict:
        from mission_control.scenario import LaunchScenario
        from sim import run_ascent

        self.stop()
        self._scenario = scenario
        self._speed = scenario.playback_speed

        self._vehicle_cfg = scenario.to_vehicle_config()
        pitch_prog = scenario.get_pitch_program()
        self._sim_result = run_ascent(self._vehicle_cfg, pitch_prog)
        self._points = list(self._sim_result.points)

        with self._lock:
            self._playback_state = "stopped"
            self._start_time = None
            self._pause_time = None
            self._pause_accumulated = 0.0
            self._state = dict(EMPTY_STATE)
            self._state["connected"] = True
            self._state["scripted"] = True

        with self._trajectory_lock:
            self._trajectory.clear()

        return self.get_scenario_summary()

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
        if not self._points:
            return
        if self._thread and self._thread.is_alive():
            self.stop()
        self._stop_event.clear()
        with self._lock:
            self._playback_state = "playing"
            self._start_time = time.time()
            self._pause_time = None
            self._pause_accumulated = 0.0
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="scripted-telemetry")
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

    def pause(self):
        with self._lock:
            if self._playback_state == "playing":
                self._playback_state = "paused"
                self._pause_time = time.time()

    def resume(self):
        with self._lock:
            if self._playback_state == "paused" and self._pause_time is not None:
                self._pause_accumulated += time.time() - self._pause_time
                self._pause_time = None
                self._playback_state = "playing"

    def reset(self):
        self.stop()
        with self._lock:
            self._playback_state = "stopped"
            self._start_time = None
            self._pause_time = None
            self._pause_accumulated = 0.0
            self._state = dict(EMPTY_STATE)
            self._state["connected"] = True
            self._state["scripted"] = True
        with self._trajectory_lock:
            self._trajectory.clear()

    def set_speed(self, speed: float):
        with self._lock:
            if self._start_time is not None and self._playback_state == "playing":
                current_elapsed = self._get_sim_elapsed_locked()
                self._speed = speed
                self._start_time = time.time() - (current_elapsed / self._speed)
                self._pause_accumulated = 0.0
            else:
                self._speed = speed

    def _get_sim_elapsed_locked(self) -> float:
        if self._start_time is None:
            return 0.0
        wall = time.time() - self._start_time - self._pause_accumulated
        return wall * self._speed

    def get_playback_status(self) -> dict:
        with self._lock:
            elapsed = self._get_sim_elapsed_locked()
            total = self._points[-1].t if self._points else 0.0
            return {
                "state": self._playback_state,
                "speed": self._speed,
                "elapsed": round(elapsed, 2),
                "total": round(total, 2),
            }

    def get_scenario_summary(self) -> dict:
        if not self._vehicle_cfg or not self._sim_result:
            return {}
        cfg = self._vehicle_cfg
        r = self._sim_result
        return {
            "liftoff_mass_t": round(cfg.liftoff_mass_t, 2),
            "pad_twr_asl": round(cfg.pad_twr_asl, 2),
            "mission_stage_dv_ms": round(cfg.mission_stage_dv_ms, 0),
            "srb_burn_time_s": round(cfg.srb_burn_time_s, 1),
            "apoapsis_km": round(r.apoapsis_km, 1),
            "periapsis_km": round(r.periapsis_km, 1),
            "n_points": len(self._points),
        }

    def _compute_liquid_fuel_from_mass(self, mass, phase):
        cfg = self._vehicle_cfg
        mission_wet = cfg.mission_stage_wet if cfg else 6.250
        mission_dry = cfg.mission_stage_dry if cfg else 2.250
        if phase in ("BOOST", "CORE"):
            liftoff = cfg.liftoff_mass_t if cfg else 14.21
            core_prop = cfg.core_stage_prop if cfg else 4.0
            booster_dry = cfg.booster_set_dry if cfg else 0.908
            booster_prop = cfg.booster_set_prop if cfg else 1.200
            core_dry_with_mission = liftoff - core_prop - booster_dry - booster_prop
            fuel_frac = max(0, (mass - core_dry_with_mission) /
                           max(0.01, liftoff - core_dry_with_mission))
            return 360.0 * fuel_frac
        prop_remaining = max(0, mass - mission_dry)
        prop_total = max(0.01, mission_wet - mission_dry)
        return 360.0 * min(1.0, prop_remaining / prop_total)

    def _build_scripted_stages(self, elapsed, timing):
        """Build stage list using time-based fuel depletion (same as SimulatedTelemetry)."""
        cfg = self._vehicle_cfg
        srb_end = timing["srb_end"]
        core_end = timing["core_end"]
        terrier_start = timing["terrier_start"]
        terrier_end = timing["terrier_end"]

        srb_initial_dv = 222.0
        core_initial_dv = 1100.0
        terrier_initial_dv = cfg.mission_stage_dv_ms if cfg else 3458.0

        if elapsed < srb_end:
            srb_frac = max(0, 1.0 - elapsed / srb_end)
            srb_status = "active"
        else:
            srb_frac = 0.0
            srb_status = "depleted"

        if elapsed < core_end:
            core_frac = max(0, 1.0 - elapsed / core_end)
            core_status = "active"
        else:
            core_frac = 0.0
            core_status = "depleted"

        if elapsed < terrier_start:
            terrier_frac = 1.0
            terrier_status = "pending"
        elif elapsed < terrier_end:
            terrier_frac = max(0, 1.0 - (elapsed - terrier_start) / (terrier_end - terrier_start))
            terrier_status = "active"
        else:
            terrier_burn_frac = min(1.0, (terrier_end - terrier_start) / 225.0)
            terrier_frac = max(0, 1.0 - terrier_burn_frac)
            terrier_status = "depleted"

        booster_prop = cfg.booster_set_prop if cfg else 1.200
        booster_dry = cfg.booster_set_dry if cfg else 0.908
        core_prop = cfg.core_stage_prop if cfg else 4.0
        mission_wet = cfg.mission_stage_wet if cfg else 6.250
        mission_dry = cfg.mission_stage_dry if cfg else 2.250
        mission_prop = mission_wet - mission_dry

        return [
            {
                "index": 0, "label": "Stage 0",
                "dv_vac": srb_frac * srb_initial_dv,
                "dv_asl": srb_frac * 170.0,
                "dv_initial": srb_initial_dv,
                "fuel_mass": srb_frac * booster_prop,
                "dry_mass": booster_dry,
                "mass": srb_frac * booster_prop + booster_dry,
                "burn_time": max(0, srb_end - elapsed) if srb_status == "active" else 0,
                "status": srb_status,
            },
            {
                "index": 1, "label": "Stage 1",
                "dv_vac": core_frac * core_initial_dv,
                "dv_asl": core_frac * 900.0,
                "dv_initial": core_initial_dv,
                "fuel_mass": core_frac * core_prop,
                "dry_mass": 1.8525,
                "mass": core_frac * core_prop + 1.8525,
                "burn_time": max(0, core_end - elapsed) if core_status == "active" else 0,
                "status": core_status,
            },
            {
                "index": 2, "label": "Stage 2",
                "dv_vac": terrier_frac * terrier_initial_dv,
                "dv_asl": terrier_frac * 800.0,
                "dv_initial": terrier_initial_dv,
                "fuel_mass": terrier_frac * mission_prop,
                "dry_mass": mission_dry,
                "mass": terrier_frac * mission_prop + mission_dry,
                "burn_time": max(0, terrier_end - elapsed) if terrier_status == "active" else 0,
                "status": terrier_status,
            },
        ]

    def _run(self):
        import random

        pts = self._points
        if not pts:
            return

        pt_idx = 0
        noise_pct = self._scenario.noise_pct if self._scenario else 0.02
        timing = SimulatedTelemetry._extract_stage_timing(pts)

        while not self._stop_event.is_set():
            with self._lock:
                if self._playback_state != "playing":
                    pass  # will sleep below, outside the lock
                else:
                    elapsed = self._get_sim_elapsed_locked()

            if self._playback_state != "playing":
                time.sleep(self.rate_ms / 1000.0)
                continue

            while pt_idx + 1 < len(pts) and pts[pt_idx + 1].t <= elapsed:
                pt_idx += 1

            if pt_idx >= len(pts) - 1:
                pt_idx = len(pts) - 1

            p = pts[pt_idx]
            landed = (pt_idx >= len(pts) - 1 and elapsed > p.t and
                      p.altitude < 1000)

            if noise_pct > 0:
                noise = lambda v: v * (1 + random.uniform(-noise_pct, noise_pct))
            else:
                noise = lambda v: v

            if landed:
                alt = 0.0
                vel = 0.0
                v_v = 0.0
                v_h = 0.0
                pitch = 0.0
                phase = "LANDED"
            else:
                alt = noise(p.altitude)
                vel = noise(p.velocity)
                v_v = noise(p.v_vert)
                v_h = noise(p.v_horiz)
                pitch = noise(90.0 - p.pitch_from_v)
                phase = p.phase

            apoapsis = noise(p.apoapsis * 1000) if p.apoapsis and not landed else 0
            periapsis = p.periapsis * 1000 if p.periapsis and not landed else 0

            cfg = self._vehicle_cfg
            srb_burn_time = cfg.srb_burn_time_s if cfg else 25.3
            lf_total = 360.0
            sf_total = (cfg.booster_set_prop / 0.0075) if (cfg and cfg.n_boosters > 0) else 0

            lf = self._compute_liquid_fuel_from_mass(p.mass, p.phase)
            sf = max(0, sf_total - elapsed * (sf_total / srb_burn_time)) if elapsed < srb_burn_time else 0

            sim_stages = self._build_scripted_stages(elapsed, timing)

            total_sim_time = pts[-1].t if pts else 61
            state = {
                "connected": True, "simulated": True, "scripted": True,
                "altitude": alt,
                "velocity": vel,
                "v_vert": v_v,
                "v_horiz": v_h,
                "apoapsis": apoapsis,
                "periapsis": periapsis,
                "inclination": 0.0,
                "time_to_ap": max(0, total_sim_time - elapsed) if not landed else None,
                "time_to_pe": None,
                "pitch": pitch,
                "heading": 90.0,
                "roll": (random.uniform(-2, 2) if noise_pct > 0 else 0.0) if not landed else 0.0,
                "mission_time": elapsed,
                "throttle": 0.0 if landed else (1.0 if p.phase in ("BOOST", "CORE", "TERRIER", "CIRCULARIZE") else 0.0),
                "liquid_fuel": lf,
                "solid_fuel": sf,
                "liquid_fuel_max": lf_total,
                "solid_fuel_max": sf_total,
                "oxidizer": lf * (11.0 / 9.0),
                "oxidizer_max": lf_total * (11.0 / 9.0),
                "mass": p.mass,
                "g_force": 1.0,
                "mach": vel / 343.0 if alt < 70000 and not landed else 0.0,
                "dynamic_pressure": 0.5 * (1.225 * (2.718 ** (-alt / 5000))) * vel * vel / 1000.0 if alt < 70000 and not landed else 0.0,
                "atm_density": 1.225 if landed else (1.225 * (2.718 ** (-alt / 5000)) if alt < 70000 else 0),
                "phase": phase,
                "error": None,
                "playback": self.get_playback_status(),
                "stages": sim_stages,
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
                except Exception as exc:
                    logger.warning("ScriptedTelemetry on_update error: %s", exc)

            time.sleep(self.rate_ms / 1000.0)
