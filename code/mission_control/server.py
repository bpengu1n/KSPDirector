"""
mission_control/server.py
--------------------------
Perseus 1 Mission Control backend server.

Connects to Telemachus (or runs in simulation mode), runs the flight director
on each telemetry update, and pushes results to connected browser clients via
Socket.IO.

Usage::

    # Simulation mode (no KSP required):
    python server.py

    # Connect to live KSP/Telemachus:
    python server.py --ksp-host 192.168.1.100

    # Custom port:
    python server.py --port 5001

    # Custom Telemachus rate:
    python server.py --ksp-host 192.168.1.100 --rate 100

The server serves the static web interface at http://localhost:5000/
and relays telemetry via Socket.IO.

Socket.IO events emitted to clients:
    telemetry   Full telemetry state snapshot
    director    Flight director output (phase, advisory, gates, nominal)
    nominal     Nominal trajectory (sent once on connection)
    connected   Server → client connection confirmation
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

# Add project root to path so we can import sim and mission_control
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from flask import Flask, render_template_string, jsonify, send_from_directory, request
from flask_socketio import SocketIO, emit

from mission_control.telemachus_client import TelematicusClient, SimulatedTelemetry, ScriptedTelemetry
from mission_control.nominal_compare import NominalTrajectory, FlightDirector
from mission_control.scenario import LaunchScenario, PRESET_SCENARIOS

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flask + SocketIO app
# ---------------------------------------------------------------------------

import os

app = Flask(__name__, static_folder=str(Path(__file__).parent / "static"))
# Fix P2-05: SECRET_KEY must be configurable for non-local deployments.
# Set MC_SECRET_KEY in the environment; falls back to a dev-only string.
app.config["SECRET_KEY"] = os.environ.get("MC_SECRET_KEY", "perseus-dev-only-key")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet",
                    logger=False, engineio_logger=False)

# Global state (set in main())
telemetry_client = None
flight_director: Optional[FlightDirector] = None
nominal_traj: Optional[NominalTrajectory] = None
current_scenario: Optional[LaunchScenario] = None
EMIT_RATE_HZ = 5    # how often to push to browser (independent of telemetry rate)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the mission control web interface."""
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return "<h2>Mission control UI not found at static/index.html</h2>", 404


@app.route("/api/nominal")
def api_nominal():
    """Return the full nominal trajectory as JSON (for offline reference)."""
    if nominal_traj is None:
        return jsonify({"error": "nominal not loaded"}), 503
    return jsonify({
        "trajectory": nominal_traj.trajectory_for_plot(),
    })


@app.route("/api/state")
def api_state():
    """Return current telemetry state as JSON (polling fallback)."""
    if telemetry_client is None:
        return jsonify({"error": "not connected"}), 503
    return jsonify(telemetry_client.get_state())


@app.route("/api/trajectory")
def api_trajectory():
    """Return actual (accumulated) trajectory from telemetry."""
    if telemetry_client is None:
        return jsonify({"trajectory": []})
    return jsonify({"trajectory": telemetry_client.get_trajectory()})


@app.route("/api/clear-trajectory", methods=["POST"])
def api_clear_trajectory():
    if telemetry_client:
        telemetry_client.clear_trajectory()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Scenario management routes
# ---------------------------------------------------------------------------

@app.route("/api/scenarios")
def api_scenarios():
    scenarios = []
    for key, s in PRESET_SCENARIOS.items():
        scenarios.append({
            "name": key,
            "label": s.name,
            "booster_type": s.booster_type,
            "n_boosters": s.n_boosters,
            "booster_pct": s.booster_pct,
            "pitch_program": s.pitch_program,
        })
    return jsonify({"scenarios": scenarios})


@app.route("/api/scenario/load", methods=["POST"])
def api_scenario_load():
    global telemetry_client, flight_director, nominal_traj, current_scenario

    data = request.get_json(force=True)

    if "preset" in data:
        scenario = PRESET_SCENARIOS.get(data["preset"])
        if not scenario:
            return jsonify({"error": f"Unknown preset: {data['preset']}"}), 400
    else:
        scenario = LaunchScenario.from_dict(data)
        errors = scenario.validate()
        if errors:
            return jsonify({"error": "Validation failed", "details": errors}), 400

    if telemetry_client:
        telemetry_client.stop()

    from sim import run_ascent
    vehicle_cfg = scenario.to_vehicle_config()
    pitch_prog = scenario.get_pitch_program()
    result = run_ascent(vehicle_cfg, pitch_prog)
    nominal_traj = NominalTrajectory(result.points)
    flight_director = FlightDirector(nominal_traj)

    scripted = ScriptedTelemetry(rate_ms=200)
    scripted.load_scenario(scenario)
    telemetry_client = scripted
    current_scenario = scenario

    summary = scripted.get_scenario_summary()

    try:
        socketio.emit("nominal", {"trajectory": nominal_traj.trajectory_for_plot()})
        socketio.emit("scenario_loaded", {
            "scenario": scenario.to_dict(),
            "summary": summary,
        })
    except Exception:
        pass

    return jsonify({"ok": True, "summary": summary})


@app.route("/api/scenario/current")
def api_scenario_current():
    result = {"scenario": None, "playback": None}
    if current_scenario:
        result["scenario"] = current_scenario.to_dict()
    if isinstance(telemetry_client, ScriptedTelemetry):
        result["playback"] = telemetry_client.get_playback_status()
    return jsonify(result)


@app.route("/api/scenario/start", methods=["POST"])
def api_scenario_start():
    if not isinstance(telemetry_client, ScriptedTelemetry):
        return jsonify({"error": "No scripted scenario loaded"}), 400
    telemetry_client.start()
    return jsonify({"ok": True})


@app.route("/api/scenario/pause", methods=["POST"])
def api_scenario_pause():
    if not isinstance(telemetry_client, ScriptedTelemetry):
        return jsonify({"error": "No scripted scenario loaded"}), 400
    telemetry_client.pause()
    return jsonify({"ok": True})


@app.route("/api/scenario/resume", methods=["POST"])
def api_scenario_resume():
    if not isinstance(telemetry_client, ScriptedTelemetry):
        return jsonify({"error": "No scripted scenario loaded"}), 400
    telemetry_client.resume()
    return jsonify({"ok": True})


@app.route("/api/scenario/reset", methods=["POST"])
def api_scenario_reset():
    if not isinstance(telemetry_client, ScriptedTelemetry):
        return jsonify({"error": "No scripted scenario loaded"}), 400
    telemetry_client.reset()
    return jsonify({"ok": True})


@app.route("/api/scenario/speed", methods=["POST"])
def api_scenario_speed():
    if not isinstance(telemetry_client, ScriptedTelemetry):
        return jsonify({"error": "No scripted scenario loaded"}), 400
    data = request.get_json(force=True)
    speed = data.get("speed", 1.0)
    if not (0.25 <= speed <= 10.0):
        return jsonify({"error": "speed must be 0.25-10.0"}), 400
    telemetry_client.set_speed(speed)
    return jsonify({"ok": True, "speed": speed})


# ---------------------------------------------------------------------------
# Socket.IO events
# ---------------------------------------------------------------------------

@socketio.on("connect")
def on_connect():
    logger.info("Browser connected: %s", request_sid())
    # Send nominal trajectory once on connect
    if nominal_traj:
        emit("nominal", {"trajectory": nominal_traj.trajectory_for_plot()})
    # Fix P1-04: send full accumulated trajectory so reconnecting browsers
    # see the complete flight path, not just the last 50 points from the
    # broadcast loop.
    if telemetry_client:
        full_traj = telemetry_client.get_trajectory()
        if full_traj:
            emit("trajectory_history", {"trajectory": full_traj})
    emit("connected", {"message": "Perseus 1 Mission Control — connected"})


def request_sid():
    from flask import request
    return getattr(request, "sid", "?")


@socketio.on("disconnect")
def on_disconnect():
    logger.info("Browser disconnected")


@socketio.on("request_nominal")
def on_request_nominal():
    if nominal_traj:
        emit("nominal", {"trajectory": nominal_traj.trajectory_for_plot()})


@socketio.on("clear_trajectory")
def on_clear_trajectory():
    if telemetry_client:
        telemetry_client.clear_trajectory()


@socketio.on("playback_control")
def on_playback_control(data):
    if not isinstance(telemetry_client, ScriptedTelemetry):
        return
    action = data.get("action")
    if action == "start":
        telemetry_client.start()
    elif action == "pause":
        telemetry_client.pause()
    elif action == "resume":
        telemetry_client.resume()
    elif action == "reset":
        telemetry_client.reset()
    elif action == "speed":
        speed = data.get("speed", 1.0)
        telemetry_client.set_speed(speed)


# ---------------------------------------------------------------------------
# Background emit loop
# ---------------------------------------------------------------------------

def broadcast_loop():
    """
    Background greenlet: reads latest telemetry + director output and
    broadcasts to all connected Socket.IO clients at EMIT_RATE_HZ.
    """
    import eventlet
    interval = 1.0 / EMIT_RATE_HZ
    while True:
        try:
            if telemetry_client:
                state = telemetry_client.get_state()
                trajectory = telemetry_client.get_trajectory()
                director_out = flight_director.update(state) if flight_director else {}

                socketio.emit("telemetry", {
                    "state": state,
                    "trajectory": trajectory[-50:] if trajectory else [],
                })
                socketio.emit("director", director_out)

                if isinstance(telemetry_client, ScriptedTelemetry):
                    socketio.emit("playback_status",
                                  telemetry_client.get_playback_status())
        except Exception as exc:
            logger.error("Broadcast error: %s", exc, exc_info=True)
            try:
                socketio.emit("director_error", {
                    "message": str(exc),
                    "type": type(exc).__name__,
                })
            except Exception:
                pass  # don't let the error-reporting itself crash the loop
        eventlet.sleep(interval)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="server.py",
        description="Perseus 1 Mission Control server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--ksp-host", default=None, metavar="IP",
                   help="KSP machine IP. If not set, runs in simulation mode.")
    p.add_argument("--ksp-port", type=int, default=8085,
                   help="Telemachus WebSocket port")
    p.add_argument("--rate", type=int, default=200,
                   help="Telemetry update rate (ms)")
    p.add_argument("--port", type=int, default=5000,
                   help="HTTP/WebSocket server port")
    p.add_argument("--emit-rate", type=int, default=5,
                   help="Browser push rate (Hz)")
    p.add_argument("--debug", action="store_true",
                   help="Enable Flask debug output")
    p.add_argument("--scenario", default=None, metavar="NAME",
                   help="Start with a preset scenario (e.g., 'nominal', 'steep_ascent'). "
                        "Implies simulation mode.")
    return p


def main(argv=None):
    global telemetry_client, flight_director, nominal_traj, current_scenario, EMIT_RATE_HZ

    parser = build_argparser()
    args = parser.parse_args(argv)
    EMIT_RATE_HZ = args.emit_rate

    # Load nominal trajectory
    logger.info("Computing nominal trajectory…")
    try:
        nominal_traj = NominalTrajectory.load()
        logger.info("Nominal trajectory loaded (%d points)", len(nominal_traj._pts))
    except Exception as exc:
        logger.error("Could not load nominal trajectory: %s", exc)
        nominal_traj = None

    # Initialise flight director
    if nominal_traj:
        flight_director = FlightDirector(nominal_traj)

    # Start telemetry client
    if args.scenario:
        scenario = PRESET_SCENARIOS.get(args.scenario)
        if not scenario:
            logger.error("Unknown scenario '%s'. Available: %s",
                         args.scenario, list(PRESET_SCENARIOS.keys()))
            sys.exit(1)
        logger.info("Starting in SCRIPTED mode with scenario '%s'", args.scenario)
        from sim import run_ascent
        cfg = scenario.to_vehicle_config()
        result = run_ascent(cfg, scenario.get_pitch_program())
        nominal_traj = NominalTrajectory(result.points)
        flight_director = FlightDirector(nominal_traj)
        scripted = ScriptedTelemetry(rate_ms=args.rate)
        scripted.load_scenario(scenario)
        telemetry_client = scripted
        current_scenario = scenario
        telemetry_client.start()
    elif args.ksp_host:
        logger.info("Connecting to KSP/Telemachus at %s:%d …", args.ksp_host, args.ksp_port)
        telemetry_client = TelematicusClient(
            host=args.ksp_host, port=args.ksp_port, rate_ms=args.rate
        )
    else:
        logger.info("No --ksp-host given — starting in SIMULATION mode")
        telemetry_client = SimulatedTelemetry(rate_ms=args.rate)

    telemetry_client.start()

    # Start broadcast greenlet
    import eventlet
    socketio.start_background_task(broadcast_loop)

    mode = "SIMULATION" if args.ksp_host is None else f"LIVE ({args.ksp_host})"
    logger.info("Perseus 1 Mission Control — %s — http://localhost:%d/", mode, args.port)

    socketio.run(app, host="0.0.0.0", port=args.port, debug=args.debug,
                 use_reloader=False)


if __name__ == "__main__":
    main()
