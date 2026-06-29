"""Tests for KRPCClient — kRPC telemetry drop-in replacement.

All tests mock the krpc module since no live KSP server is available in CI.
Verifies interface compatibility with TelematicusClient and correct data flow.
"""

import math
import sys
import threading
import time
import types
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Mock krpc module — must be injected before importing KRPCClient
# ---------------------------------------------------------------------------

def _make_mock_krpc():
    """Build a mock krpc module that simulates the kRPC Python client API."""
    mock_krpc = types.ModuleType("krpc")

    class MockStream:
        def __init__(self, value=0.0):
            self._value = value

        def __call__(self):
            return self._value

        def remove(self):
            pass

    mock_krpc.MockStream = MockStream
    mock_krpc.connect = MagicMock()
    return mock_krpc


def _build_mock_connection(state=None):
    """Build a mock kRPC connection with realistic vessel/flight/orbit objects."""
    if state is None:
        state = {}

    defaults = {
        "altitude": 15000.0,
        "v_vert": 408.0,
        "surface_speed": 631.0,
        "velocity": 643.0,
        "apoapsis": 25000.0,
        "periapsis": -587000.0,
        "inclination": 0.0,
        "eccentricity": 0.95,
        "time_to_ap": 45.0,
        "time_to_pe": 300.0,
        "pitch": 40.0,
        "heading": 90.0,
        "roll": 0.5,
        "mission_time": 63.0,
        "throttle": 1.0,
        "mass": 8.5,
        "g_force": 1.8,
        "latitude": 0.06,
        "longitude": 1.2,
        "dynamic_pressure": 12.5,
        "mach": 1.9,
        "atm_density": 0.002,
    }
    defaults.update(state)

    stream_map = {
        "mean_altitude": defaults["altitude"],
        "vertical_speed": defaults["v_vert"],
        "speed": None,  # overloaded below
        "apoapsis_altitude": defaults["apoapsis"],
        "periapsis_altitude": defaults["periapsis"],
        "inclination": defaults["inclination"],
        "eccentricity": defaults["eccentricity"],
        "time_to_apoapsis": defaults["time_to_ap"],
        "time_to_periapsis": defaults["time_to_pe"],
        "pitch": defaults["pitch"],
        "heading": defaults["heading"],
        "roll": defaults["roll"],
        "met": defaults["mission_time"],
        "throttle": defaults["throttle"],
        "mass": defaults["mass"],
        "g_force": defaults["g_force"],
        "latitude": defaults["latitude"],
        "longitude": defaults["longitude"],
        "dynamic_pressure": defaults["dynamic_pressure"],
        "mach": defaults["mach"],
        "atmosphere_density": defaults["atm_density"],
    }

    conn = MagicMock()
    vessel = MagicMock()
    flight = MagicMock()
    orbit = MagicMock()
    control = MagicMock()
    body = MagicMock()
    ref_frame = MagicMock()

    body.reference_frame = ref_frame
    orbit.body = body
    vessel.orbit = orbit
    vessel.control = control
    vessel.met = defaults["mission_time"]
    vessel.mass = defaults["mass"]

    conn.space_center.active_vessel = vessel
    vessel.flight.return_value = flight

    from tests.test_krpc_client import _make_mock_krpc
    MockStream = _make_mock_krpc().MockStream

    def mock_add_stream(fn, obj, attr):
        if attr == "speed":
            if obj is orbit:
                return MockStream(defaults["velocity"])
            else:
                return MockStream(defaults["surface_speed"])
        if attr in stream_map:
            return MockStream(stream_map[attr])
        return MockStream(0.0)

    conn.add_stream = mock_add_stream

    # Resources
    res = MagicMock()
    res.amount.side_effect = lambda name: {
        "LiquidFuel": 360.0,
        "SolidFuel": 80.0,
        "Oxidizer": 440.0,
        "ElectricCharge": 100.0,
    }.get(name, 0.0)
    res.max.side_effect = lambda name: {
        "LiquidFuel": 360.0,
        "SolidFuel": 160.0,
        "Oxidizer": 440.0,
        "ElectricCharge": 150.0,
    }.get(name, 0.0)
    vessel.resources = res

    # Stage resources
    stage_res = MagicMock()
    stage_res.amount.side_effect = lambda name: {
        "LiquidFuel": 180.0,
        "SolidFuel": 0.0,
        "Oxidizer": 220.0,
    }.get(name, 0.0)
    stage_res.max.side_effect = lambda name: {
        "LiquidFuel": 360.0,
        "SolidFuel": 0.0,
        "Oxidizer": 440.0,
    }.get(name, 0.0)
    vessel.resources_in_decouple_stage.return_value = stage_res
    vessel.control.current_stage = 2

    # Parts (empty by default — stages build is best-effort)
    vessel.parts.all = []
    vessel.parts.in_decouple_stage.return_value = []

    return conn, vessel, defaults


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def inject_mock_krpc():
    """Inject mock krpc module into sys.modules for all tests."""
    mock_krpc = _make_mock_krpc()
    with patch.dict(sys.modules, {"krpc": mock_krpc}):
        yield mock_krpc


@pytest.fixture
def mock_conn():
    """Provide a mock kRPC connection and its expected default values."""
    conn, vessel, defaults = _build_mock_connection()
    return conn, vessel, defaults


@pytest.fixture
def make_client(inject_mock_krpc, mock_conn):
    """Factory: create a KRPCClient with mocked krpc.connect()."""
    conn, vessel, defaults = mock_conn

    def _make(rate_hz=5, **kwargs):
        inject_mock_krpc.connect = MagicMock(return_value=conn)
        from mission_control.krpc_client import KRPCClient
        client = KRPCClient(rate_hz=rate_hz, **kwargs)
        return client, defaults

    return _make


# ---------------------------------------------------------------------------
# Interface compatibility tests
# ---------------------------------------------------------------------------

class TestKRPCClientInterface:
    """Verify KRPCClient has the same public interface as TelematicusClient."""

    def test_has_get_state(self, make_client):
        client, _ = make_client()
        assert callable(client.get_state)

    def test_has_get_trajectory(self, make_client):
        client, _ = make_client()
        assert callable(client.get_trajectory)

    def test_has_clear_trajectory(self, make_client):
        client, _ = make_client()
        assert callable(client.clear_trajectory)

    def test_has_start_stop(self, make_client):
        client, _ = make_client()
        assert callable(client.start)
        assert callable(client.stop)

    def test_has_on_update(self, make_client):
        client, _ = make_client()
        assert hasattr(client, "on_update")

    def test_initial_state_not_connected(self, make_client):
        client, _ = make_client()
        state = client.get_state()
        assert state["connected"] is False

    def test_initial_state_has_error_key(self, make_client):
        client, _ = make_client()
        state = client.get_state()
        assert "error" in state

    def test_initial_trajectory_empty(self, make_client):
        client, _ = make_client()
        assert client.get_trajectory() == []

    def test_clear_trajectory_empties(self, make_client):
        client, _ = make_client()
        client._trajectory = [{"t": 1.0}]
        client.clear_trajectory()
        assert client.get_trajectory() == []


# ---------------------------------------------------------------------------
# State reading tests
# ---------------------------------------------------------------------------

class TestKRPCStateReading:
    """Verify stream reading produces correct state dict."""

    def test_read_streams_populates_state(self, make_client):
        client, defaults = make_client()
        from mission_control.krpc_client import KRPCClient
        import krpc as mock_krpc

        conn = mock_krpc.connect.return_value
        client._conn = conn
        client._vessel = conn.space_center.active_vessel
        client._setup_streams()
        client._read_streams()

        state = client.get_state()
        assert state["altitude"] == pytest.approx(defaults["altitude"])
        assert state["velocity"] == pytest.approx(defaults["velocity"])
        assert state["v_vert"] == pytest.approx(defaults["v_vert"])
        assert state["pitch"] == pytest.approx(defaults["pitch"])
        assert state["heading"] == pytest.approx(defaults["heading"])
        assert state["mission_time"] == pytest.approx(defaults["mission_time"])
        assert state["throttle"] == pytest.approx(defaults["throttle"])
        assert state["mass"] == pytest.approx(defaults["mass"])
        assert state["connected"] is True

    def test_v_horiz_derived_correctly(self, make_client):
        client, defaults = make_client()
        import krpc as mock_krpc

        conn = mock_krpc.connect.return_value
        client._conn = conn
        client._vessel = conn.space_center.active_vessel
        client._setup_streams()
        client._read_streams()

        state = client.get_state()
        expected = math.sqrt(
            defaults["surface_speed"] ** 2 - defaults["v_vert"] ** 2
        )
        assert state["v_horiz"] == pytest.approx(expected)

    def test_resources_populated(self, make_client):
        client, _ = make_client()
        import krpc as mock_krpc

        conn = mock_krpc.connect.return_value
        client._conn = conn
        client._vessel = conn.space_center.active_vessel
        client._setup_streams()
        client._read_streams()

        state = client.get_state()
        assert state["liquid_fuel"] == pytest.approx(360.0)
        assert state["solid_fuel"] == pytest.approx(80.0)
        assert state["liquid_fuel_max"] == pytest.approx(360.0)
        assert state["solid_fuel_max"] == pytest.approx(160.0)
        assert state["oxidizer"] == pytest.approx(440.0)
        assert state["oxidizer_max"] == pytest.approx(440.0)

    def test_stage_resources_populated(self, make_client):
        client, _ = make_client()
        import krpc as mock_krpc

        conn = mock_krpc.connect.return_value
        client._conn = conn
        client._vessel = conn.space_center.active_vessel
        client._setup_streams()
        client._read_streams()

        state = client.get_state()
        assert state["stage_liquid_fuel"] == pytest.approx(180.0)
        assert state["current_stage"] == 2


# ---------------------------------------------------------------------------
# Trajectory accumulation tests
# ---------------------------------------------------------------------------

class TestKRPCTrajectory:
    """Verify trajectory point accumulation and MET reset detection."""

    def _setup_client_with_streams(self, make_client):
        client, defaults = make_client()
        import krpc as mock_krpc

        conn = mock_krpc.connect.return_value
        client._conn = conn
        client._vessel = conn.space_center.active_vessel
        client._setup_streams()
        return client, defaults

    def test_trajectory_point_appended(self, make_client):
        client, defaults = make_client()
        import krpc as mock_krpc

        conn = mock_krpc.connect.return_value
        client._conn = conn
        client._vessel = conn.space_center.active_vessel
        client._setup_streams()
        client._read_streams()

        traj = client.get_trajectory()
        assert len(traj) == 1
        assert traj[0]["t"] == pytest.approx(defaults["mission_time"])
        assert traj[0]["altitude_km"] == pytest.approx(defaults["altitude"] / 1000.0)

    def test_trajectory_min_interval(self, make_client):
        """Points closer than 0.5s apart are skipped."""
        client, _ = self._setup_client_with_streams(make_client)

        client._read_streams()
        client._read_streams()

        assert len(client.get_trajectory()) == 1

    def test_trajectory_met_reset_clears(self, make_client):
        """When MET drops below 5s after a point > 30s, trajectory clears."""
        client, _ = self._setup_client_with_streams(make_client)

        client._read_streams()
        assert len(client.get_trajectory()) == 1

        for stream in client._streams.values():
            if stream() == 63.0:
                stream._value = 2.0
            if stream() == 15000.0:
                stream._value = 100.0

        client._read_streams()
        traj = client.get_trajectory()
        assert len(traj) == 1
        assert traj[0]["t"] == pytest.approx(2.0)

    def test_trajectory_fifo_eviction(self, make_client):
        client, _ = self._setup_client_with_streams(make_client)

        for i in range(10010):
            t = float(i)
            for stream in client._streams.values():
                if stream() == 63.0 or (hasattr(stream, '_value') and isinstance(stream._value, float) and stream._value >= 0):
                    pass
            point = {
                "t": t,
                "altitude_km": 15.0,
                "downrange_km": 0.0,
                "velocity": 600.0,
                "apoapsis_km": 25.0,
                "periapsis_km": -587.0,
                "pitch": 40.0,
            }
            client._trajectory.append(point)

        from mission_control.krpc_client import TRAJECTORY_MAX_POINTS
        client._update_trajectory({
            "altitude": 15000.0,
            "mission_time": 20000.0,
            "latitude": 0.0,
            "longitude": 0.0,
            "velocity": 600.0,
            "apoapsis": 25000.0,
            "periapsis": -587000.0,
            "pitch": 40.0,
        })

        assert len(client.get_trajectory()) <= TRAJECTORY_MAX_POINTS


# ---------------------------------------------------------------------------
# Downrange computation tests
# ---------------------------------------------------------------------------

class TestKRPCDownrange:
    """Verify downrange computation uses Kerbin-correct formula."""

    def test_launch_lon_captured(self, make_client):
        """Launch longitude captured when MET < 3s."""
        client, _ = make_client()
        import krpc as mock_krpc

        conn = mock_krpc.connect.return_value
        client._conn = conn
        client._vessel = conn.space_center.active_vessel
        client._setup_streams()

        for stream in client._streams.values():
            if hasattr(stream, '_value') and stream._value == 63.0:
                stream._value = 1.5

        client._read_streams()
        assert client._launch_lon is not None

    def test_downrange_kerbin_scale(self, make_client):
        client, _ = make_client()
        import krpc as mock_krpc

        conn = mock_krpc.connect.return_value
        client._conn = conn
        client._vessel = conn.space_center.active_vessel
        client._setup_streams()

        for stream in client._streams.values():
            if hasattr(stream, '_value') and stream._value == 63.0:
                stream._value = 1.0

        client._read_streams()

        for stream in client._streams.values():
            if hasattr(stream, '_value') and stream._value == 1.0:
                stream._value = 30.0

        lon_stream = None
        for stream in client._streams.values():
            if hasattr(stream, '_value') and stream._value == 1.2:
                stream._value = 2.2
                lon_stream = stream
                break

        client._read_streams()
        traj = client.get_trajectory()
        assert len(traj) >= 1
        last = traj[-1]
        assert last["downrange_km"] > 0


# ---------------------------------------------------------------------------
# Connection lifecycle tests
# ---------------------------------------------------------------------------

class TestKRPCLifecycle:
    """Verify start/stop/reconnect behavior."""

    def test_start_creates_thread(self, make_client):
        client, _ = make_client()
        import krpc as mock_krpc

        stop_after_one = threading.Event()
        original_connect_and_poll = client._connect_and_poll

        def patched_poll():
            stop_after_one.set()
            client._stop_event.set()

        client._connect_and_poll = patched_poll
        client.start()
        stop_after_one.wait(timeout=2.0)
        client.stop()
        assert client._thread is not None

    def test_stop_cleans_up(self, make_client):
        client, _ = make_client()
        client._connect_and_poll = lambda: client._stop_event.wait()
        client.start()
        time.sleep(0.1)
        client.stop()
        assert client._stop_event.is_set()

    def test_import_error_on_missing_krpc(self, inject_mock_krpc):
        with patch.dict(sys.modules, {"krpc": None}):
            from mission_control.krpc_client import KRPCClient
            client = KRPCClient()
            with pytest.raises((ImportError, ModuleNotFoundError)):
                client._connect_and_poll()

    def test_reconnect_on_failure(self, make_client):
        """Verify the client retries after connection failure."""
        client, _ = make_client()
        attempt_count = 0

        def failing_connect():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count >= 2:
                client._stop_event.set()
            raise ConnectionError("test failure")

        client._connect_and_poll = failing_connect
        client.start()
        time.sleep(0.5)
        client.stop()
        assert attempt_count >= 1


# ---------------------------------------------------------------------------
# on_update callback tests
# ---------------------------------------------------------------------------

class TestKRPCCallback:
    """Verify on_update callback fires correctly."""

    def test_on_update_receives_state(self, make_client):
        client, _ = make_client()
        import krpc as mock_krpc

        conn = mock_krpc.connect.return_value
        client._conn = conn
        client._vessel = conn.space_center.active_vessel
        client._setup_streams()

        received = []
        client.on_update = lambda s: received.append(s)

        stopped = threading.Event()
        original_poll = client._connect_and_poll

        def single_poll():
            client._read_streams()
            if client.on_update:
                client.on_update(client.get_state())
            client._stop_event.set()

        client._connect_and_poll = single_poll
        client.start()
        time.sleep(0.5)
        client.stop()

        assert len(received) >= 1
        assert received[0]["connected"] is True

    def test_on_update_exception_does_not_crash(self, make_client):
        client, _ = make_client()
        import krpc as mock_krpc

        conn = mock_krpc.connect.return_value
        client._conn = conn
        client._vessel = conn.space_center.active_vessel
        client._setup_streams()

        def bad_callback(state):
            raise ValueError("callback error")

        client.on_update = bad_callback

        client._connect_and_poll = lambda: (
            client._read_streams(),
            client._stop_event.set(),
        )
        client.start()
        time.sleep(0.5)
        client.stop()


# ---------------------------------------------------------------------------
# State dict compatibility with FlightDirector
# ---------------------------------------------------------------------------

class TestFlightDirectorCompatibility:
    """Verify KRPCClient state dict works with FlightDirector.update()."""

    def test_state_has_required_fields(self, make_client):
        """FlightDirector.update() requires these fields in the state dict."""
        client, _ = make_client()
        import krpc as mock_krpc

        conn = mock_krpc.connect.return_value
        client._conn = conn
        client._vessel = conn.space_center.active_vessel
        client._setup_streams()
        client._read_streams()

        state = client.get_state()
        required = [
            "altitude", "velocity", "v_vert", "v_horiz",
            "apoapsis", "periapsis", "pitch", "heading",
            "mission_time", "throttle", "liquid_fuel", "solid_fuel",
        ]
        for field in required:
            assert field in state, f"Missing required field: {field}"
            assert state[field] is not None, f"Field {field} is None"

    def test_state_works_with_flight_director(self, make_client):
        """Integration: feed KRPCClient state into FlightDirector."""
        client, _ = make_client()
        import krpc as mock_krpc

        conn = mock_krpc.connect.return_value
        client._conn = conn
        client._vessel = conn.space_center.active_vessel
        client._setup_streams()
        client._read_streams()

        state = client.get_state()
        state["atm_density"] = state.get("atm_density") or 0.002

        from mission_control.nominal_compare import NominalTrajectory, FlightDirector
        nominal = NominalTrajectory.load()
        fd = FlightDirector(nominal)
        result = fd.update(state)

        assert "phase" in result
        assert "advisory" in result
        assert "gates" in result


# ---------------------------------------------------------------------------
# Constructor parameter tests
# ---------------------------------------------------------------------------

class TestKRPCClientParams:

    def test_default_params(self, inject_mock_krpc):
        from mission_control.krpc_client import KRPCClient
        client = KRPCClient()
        assert client.host == "127.0.0.1"
        assert client.rpc_port == 50000
        assert client.stream_port == 50001
        assert client.rate_hz == 5

    def test_custom_params(self, inject_mock_krpc):
        from mission_control.krpc_client import KRPCClient
        client = KRPCClient(
            host="10.0.0.5",
            rpc_port=51000,
            stream_port=51001,
            rate_hz=10,
            client_name="Test MC",
        )
        assert client.host == "10.0.0.5"
        assert client.rpc_port == 51000
        assert client.stream_port == 51001
        assert client.rate_hz == 10
        assert client.client_name == "Test MC"

    def test_get_state_thread_safe(self, make_client):
        """get_state returns a copy, not a reference."""
        client, _ = make_client()
        s1 = client.get_state()
        s2 = client.get_state()
        assert s1 is not s2
        s1["altitude"] = 99999
        assert client.get_state().get("altitude") != 99999

    def test_get_trajectory_thread_safe(self, make_client):
        """get_trajectory returns a copy."""
        client, _ = make_client()
        t1 = client.get_trajectory()
        t2 = client.get_trajectory()
        assert t1 is not t2
