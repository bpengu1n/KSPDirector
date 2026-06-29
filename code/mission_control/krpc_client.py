"""
mission_control/krpc_client.py
-------------------------------
kRPC-based telemetry client for Mission Control.

Drop-in replacement for TelematicusClient: produces the same get_state() /
get_trajectory() dict format so the FlightDirector, server broadcast loop,
and web UI work unchanged.

kRPC protocol:
    - RPC port default: 50000, stream port default: 50001
    - Uses protobuf-over-TCP (handled by the krpc Python package)
    - Push-based streams for high-frequency telemetry
    - Direct RPC for low-frequency queries (resources, parts)

Requires: pip install krpc
"""

import logging
import math
import threading
import time
from typing import Callable, Optional

from mission_control.telemachus_client import compute_downrange_km

logger = logging.getLogger(__name__)

TRAJECTORY_MAX_POINTS = 10000


class KRPCClient:
    """
    Telemetry client using kRPC streams for live KSP telemetry.

    Implements the same interface as TelematicusClient:
      get_state(), get_trajectory(), clear_trajectory(), start(), stop()

    Usage::

        client = KRPCClient(host="192.168.1.100")
        client.start()
        state = client.get_state()
        print(state['altitude'], state['apoapsis'])
        client.stop()
    """

    def __init__(self, host: str = "127.0.0.1", rpc_port: int = 50000,
                 stream_port: int = 50001, rate_hz: int = 5,
                 client_name: str = "Mission Control"):
        self.host = host
        self.rpc_port = rpc_port
        self.stream_port = stream_port
        self.rate_hz = rate_hz
        self.client_name = client_name

        self._conn = None
        self._vessel = None
        self._streams: dict = {}
        self._state: dict = {}
        self._lock = threading.Lock()
        self._trajectory: list = []
        self._trajectory_lock = threading.Lock()
        self._launch_lon: Optional[float] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.on_update: Optional[Callable[[dict], None]] = None

        self._init_state()

    def _init_state(self):
        with self._lock:
            self._state = {
                "connected": False,
                "error": None,
                "stages": [],
                "altitude": None,
                "velocity": None,
                "v_vert": None,
                "v_horiz": None,
                "surface_speed": None,
                "apoapsis": None,
                "periapsis": None,
                "inclination": None,
                "eccentricity": None,
                "time_to_ap": None,
                "time_to_pe": None,
                "pitch": None,
                "heading": None,
                "roll": None,
                "mission_time": None,
                "throttle": None,
                "mass": None,
                "g_force": None,
                "latitude": None,
                "longitude": None,
                "dynamic_pressure": None,
                "mach": None,
                "atm_density": None,
                "liquid_fuel": None,
                "solid_fuel": None,
                "oxidizer": None,
                "electric_charge": None,
                "liquid_fuel_max": None,
                "solid_fuel_max": None,
                "oxidizer_max": None,
                "electric_charge_max": None,
                "stage_liquid_fuel": None,
                "stage_solid_fuel": None,
                "stage_oxidizer": None,
                "stage_liquid_fuel_max": None,
                "stage_solid_fuel_max": None,
                "stage_oxidizer_max": None,
            }

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
                                        name="krpc-client")
        self._thread.start()
        logger.info("KRPCClient started → %s:%d", self.host, self.rpc_port)

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        self._close_streams()
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
        logger.info("KRPCClient stopped")

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self._connect_and_poll()
            except Exception as exc:
                logger.warning("kRPC connection error: %s — retrying in 3s", exc)
                with self._lock:
                    self._state["connected"] = False
                    self._state["error"] = str(exc)
                self._close_streams()
                time.sleep(3.0)

    def _connect_and_poll(self):
        try:
            import krpc
        except ImportError:
            raise ImportError(
                "krpc not installed. Run: pip install krpc"
            )

        self._conn = krpc.connect(
            name=self.client_name,
            address=self.host,
            rpc_port=self.rpc_port,
            stream_port=self.stream_port,
        )
        self._vessel = self._conn.space_center.active_vessel
        self._setup_streams()

        with self._lock:
            self._state["connected"] = True
            self._state["error"] = None
        logger.info("Connected to kRPC at %s:%d", self.host, self.rpc_port)

        interval = 1.0 / self.rate_hz
        while not self._stop_event.is_set():
            try:
                self._vessel = self._conn.space_center.active_vessel
            except Exception:
                raise ConnectionError("Lost connection to kRPC")

            self._read_streams()

            if self.on_update:
                try:
                    self.on_update(self.get_state())
                except Exception as exc:
                    logger.warning("on_update callback error: %s", exc)

            time.sleep(interval)

    def _setup_streams(self):
        vessel = self._vessel
        ref_frame = vessel.orbit.body.reference_frame
        flight = vessel.flight(ref_frame)
        orbit = vessel.orbit
        control = vessel.control

        conn = self._conn
        self._streams = {
            "altitude": conn.add_stream(getattr, flight, "mean_altitude"),
            "v_vert": conn.add_stream(getattr, flight, "vertical_speed"),
            "surface_speed": conn.add_stream(getattr, flight, "speed"),
            "velocity": conn.add_stream(getattr, orbit, "speed"),
            "apoapsis": conn.add_stream(getattr, orbit, "apoapsis_altitude"),
            "periapsis": conn.add_stream(getattr, orbit, "periapsis_altitude"),
            "inclination": conn.add_stream(getattr, orbit, "inclination"),
            "eccentricity": conn.add_stream(getattr, orbit, "eccentricity"),
            "time_to_ap": conn.add_stream(getattr, orbit, "time_to_apoapsis"),
            "time_to_pe": conn.add_stream(getattr, orbit, "time_to_periapsis"),
            "pitch": conn.add_stream(getattr, flight, "pitch"),
            "heading": conn.add_stream(getattr, flight, "heading"),
            "roll": conn.add_stream(getattr, flight, "roll"),
            "mission_time": conn.add_stream(getattr, vessel, "met"),
            "throttle": conn.add_stream(getattr, control, "throttle"),
            "mass": conn.add_stream(getattr, vessel, "mass"),
            "g_force": conn.add_stream(getattr, flight, "g_force"),
            "latitude": conn.add_stream(getattr, flight, "latitude"),
            "longitude": conn.add_stream(getattr, flight, "longitude"),
            "dynamic_pressure": conn.add_stream(getattr, flight, "dynamic_pressure"),
            "mach": conn.add_stream(getattr, flight, "mach"),
            "atm_density": conn.add_stream(getattr, flight, "atmosphere_density"),
        }

    def _close_streams(self):
        for stream in self._streams.values():
            try:
                stream.remove()
            except Exception:
                pass
        self._streams.clear()

    def _read_streams(self):
        state = {}
        for key, stream in self._streams.items():
            try:
                state[key] = stream()
            except Exception:
                state[key] = None

        surf = state.get("surface_speed")
        vv = state.get("v_vert")
        if surf is not None and vv is not None:
            state["v_horiz"] = math.sqrt(max(0.0, surf * surf - vv * vv))
        else:
            state["v_horiz"] = None

        self._read_resources(state)
        self._read_stage_resources(state)
        self._build_stages(state)

        state["connected"] = True
        state["error"] = None

        with self._lock:
            self._state.update(state)

        self._update_trajectory(state)

    def _read_resources(self, state: dict):
        vessel = self._vessel
        try:
            res = vessel.resources
            state["liquid_fuel"] = res.amount("LiquidFuel")
            state["solid_fuel"] = res.amount("SolidFuel")
            state["oxidizer"] = res.amount("Oxidizer")
            state["electric_charge"] = res.amount("ElectricCharge")
            state["liquid_fuel_max"] = res.max("LiquidFuel")
            state["solid_fuel_max"] = res.max("SolidFuel")
            state["oxidizer_max"] = res.max("Oxidizer")
            state["electric_charge_max"] = res.max("ElectricCharge")
        except Exception as exc:
            logger.debug("Resource query failed: %s", exc)

    def _read_stage_resources(self, state: dict):
        vessel = self._vessel
        try:
            stage_num = vessel.control.current_stage
            res = vessel.resources_in_decouple_stage(stage=stage_num, cumulative=False)
            state["stage_liquid_fuel"] = res.amount("LiquidFuel")
            state["stage_solid_fuel"] = res.amount("SolidFuel")
            state["stage_oxidizer"] = res.amount("Oxidizer")
            state["stage_liquid_fuel_max"] = res.max("LiquidFuel")
            state["stage_solid_fuel_max"] = res.max("SolidFuel")
            state["stage_oxidizer_max"] = res.max("Oxidizer")
            state["current_stage"] = stage_num
        except Exception as exc:
            logger.debug("Stage resource query failed: %s", exc)

    def _build_stages(self, state: dict):
        vessel = self._vessel
        try:
            dv_info = vessel.flight()  # noqa: not used, just probing connection
            parts = vessel.parts
            stages = []
            seen_stages = set()

            for part in parts.all:
                if part.decouple_stage not in seen_stages:
                    seen_stages.add(part.decouple_stage)

            for stage_num in sorted(seen_stages):
                engines = [p.engine for p in parts.in_decouple_stage(stage_num)
                           if p.engine is not None]
                if not engines:
                    continue

                res = vessel.resources_in_decouple_stage(stage=stage_num, cumulative=False)
                fuel_mass = (res.amount("LiquidFuel") * 0.005 +
                             res.amount("Oxidizer") * 0.005 +
                             res.amount("SolidFuel") * 0.0075)

                total_thrust_vac = sum(
                    e.max_vacuum_thrust for e in engines
                    if e.max_vacuum_thrust > 0
                )
                isp_denom = sum(
                    e.max_vacuum_thrust / e.vacuum_specific_impulse
                    for e in engines
                    if e.vacuum_specific_impulse > 0 and e.max_vacuum_thrust > 0
                )
                isp_vac = total_thrust_vac / isp_denom if isp_denom > 0 else 0

                total_thrust_asl = sum(
                    e.max_thrust for e in engines
                    if e.max_thrust > 0
                )
                isp_denom_asl = sum(
                    e.max_thrust / e.specific_impulse
                    for e in engines
                    if e.specific_impulse > 0 and e.max_thrust > 0
                )
                isp_asl = total_thrust_asl / isp_denom_asl if isp_denom_asl > 0 else 0

                dry_mass_parts = sum(p.mass - p.dry_mass for p in
                                     parts.in_decouple_stage(stage_num))
                start_mass = vessel.mass
                end_mass = start_mass - fuel_mass

                dv_vac = (isp_vac * 9.80665 * math.log(start_mass / end_mass)
                          if end_mass > 0 and start_mass > end_mass else 0)
                dv_asl = (isp_asl * 9.80665 * math.log(start_mass / end_mass)
                          if end_mass > 0 and start_mass > end_mass else 0)

                burn_time = (fuel_mass / (total_thrust_vac / (isp_vac * 9.80665))
                             if total_thrust_vac > 0 and isp_vac > 0 else 0)

                stages.append({
                    "index": stage_num,
                    "dv_vac": dv_vac,
                    "dv_asl": dv_asl,
                    "twr_vac": total_thrust_vac / (vessel.mass * 9.80665) if vessel.mass > 0 else 0,
                    "twr_asl": total_thrust_asl / (vessel.mass * 9.80665) if vessel.mass > 0 else 0,
                    "isp_vac": isp_vac,
                    "isp_asl": isp_asl,
                    "thrust_vac": total_thrust_vac,
                    "thrust_asl": total_thrust_asl,
                    "burn_time": burn_time,
                    "fuel_mass": fuel_mass,
                    "start_mass": start_mass,
                    "end_mass": end_mass,
                    "mass": fuel_mass + dry_mass_parts,
                })

            state["stages"] = stages
        except Exception as exc:
            logger.debug("Stage build failed: %s", exc)
            state["stages"] = []

    def _update_trajectory(self, state: dict):
        alt = state.get("altitude")
        met = state.get("mission_time")
        if alt is None or alt <= 0 or met is None or met <= 0:
            return

        lat = state.get("latitude", 0) or 0
        lon = state.get("longitude", 0) or 0

        with self._lock:
            if self._launch_lon is None and met < 3.0:
                self._launch_lon = lon
            launch_lon = self._launch_lon

        lon_delta = lon - (launch_lon if launch_lon is not None else lon)
        dr_km = compute_downrange_km(lon_delta, lat)

        point = {
            "t": met,
            "altitude_km": alt / 1000.0,
            "downrange_km": dr_km,
            "velocity": state.get("velocity", 0) or 0,
            "apoapsis_km": (state.get("apoapsis") or 0) / 1000.0,
            "periapsis_km": (state.get("periapsis") or 0) / 1000.0,
            "pitch": state.get("pitch") or 0,
        }

        with self._trajectory_lock:
            if (self._trajectory and met < 5.0 and
                    self._trajectory[-1]["t"] > 30.0):
                self._trajectory.clear()
                logger.info("MET reset detected — trajectory cleared for new flight")
                with self._lock:
                    self._launch_lon = None

            if not self._trajectory or (met - self._trajectory[-1]["t"]) > 0.5:
                self._trajectory.append(point)
                if len(self._trajectory) > TRAJECTORY_MAX_POINTS:
                    self._trajectory = self._trajectory[-TRAJECTORY_MAX_POINTS:]
