import sqlite3
import asyncio
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


# ---------------- Configuration ----------------

BROKER = "127.0.0.1"
PORT = 1883
TELEMETRY_TIMEOUT_SECONDS = 6

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "camera_history.db"
load_dotenv(PROJECT_DIR / ".env")
db = None
# Internal state is held in memory; no database is required for this lab.
cameras = {
    "camera01": {
        "device_id": "camera01",
        "connection": "offline",
        "fps": None,
        "target_fps": None,
        "temperature_c": None,
        "last_seen": None,
        "last_seen_monotonic": None,
        "last_response": None,
    },
    "camera02": {
        "device_id": "camera02",
        "connection": "offline",
        "fps": None,
        "target_fps": None,
        "temperature_c": None,
        "last_seen": None,
        "last_seen_monotonic": None,
        "last_response": None,
    },
}

websocket_clients: set[WebSocket] = set()
event_loop = None
mqtt_client = None


def get_dashboard_credentials():
    username = os.getenv("MQTT_DASHBOARD_USERNAME")
    password = os.getenv("MQTT_DASHBOARD_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "Missing dashboard MQTT credentials. Set MQTT_DASHBOARD_USERNAME and "
            "MQTT_DASHBOARD_PASSWORD in the root .env file."
        )

    return username, password


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def public_camera_state():
    """Return JSON-safe state without internal timing fields."""
    result = {}

    for device_id, camera in cameras.items():
        result[device_id] = {
            key: value
            for key, value in camera.items()
            if key != "last_seen_monotonic"
        }

    return result


async def broadcast_state():
    """Send the latest camera state to every connected browser."""
    if not websocket_clients:
        return

    message = json.dumps({
        "type": "camera_state",
        "cameras": public_camera_state(),
    })

    disconnected = []

    for websocket in list(websocket_clients):
        try:
            await websocket.send_text(message)
        except Exception:
            disconnected.append(websocket)

    for websocket in disconnected:
        websocket_clients.discard(websocket)

def initialize_database():
    global db

    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            received_at TEXT NOT NULL,
            received_at_epoch REAL NOT NULL,
            fps REAL,
            target_fps INTEGER,
            temperature_c REAL
        )
    """)

    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_device_time
        ON telemetry (device_id, received_at_epoch)
    """)

    db.commit()
    print(f"Telemetry database ready: {DB_PATH}")

async def process_mqtt_message(topic, raw_payload):
    """Run MQTT message processing on FastAPI's asyncio event loop."""
    try:
        payload = json.loads(raw_payload)
    except (json.JSONDecodeError, TypeError):
        print(f"Ignoring invalid JSON on {topic}")
        return

    parts = topic.split("/")
    if len(parts) != 3 or parts[0] != "camera":
        return

    device_id = parts[1]
    message_type = parts[2]

    # Discover cameras dynamically, not just the two original simulators.
    if device_id not in cameras:
        cameras[device_id] = {
            "device_id": device_id,
            "connection": "offline",
            "fps": None,
            "target_fps": None,
            "temperature_c": None,
            "last_seen": None,
            "last_seen_monotonic": None,
            "last_response": None,
        }

    camera = cameras[device_id]

    if message_type == "telemetry":
        camera["fps"] = payload.get("fps")
        camera["target_fps"] = payload.get("target_fps")
        camera["temperature_c"] = payload.get("temperature_c")
        camera["last_seen"] = utc_now()
        camera["last_seen_monotonic"] = time.monotonic()
        camera["connection"] = "online"
        if db is not None:
            received_at = utc_now()
            db.execute(
                """
                INSERT INTO telemetry (
                    device_id, received_at, received_at_epoch,
                    fps, target_fps, temperature_c
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    device_id,
                    received_at,
                    time.time(),
                    payload.get("fps"),
                    payload.get("target_fps"),
                    payload.get("temperature_c"),
                ),
            )
            db.commit()

    elif message_type == "status":
        status = payload.get("status", "unknown")

        if status == "offline":
            camera["connection"] = "offline"
        elif status == "online":
            # The telemetry timeout below will catch a device that stops
            # publishing even if its retained status still says "online".
            camera["connection"] = "waiting_for_telemetry"

    elif message_type == "response":
        camera["last_response"] = {
            "command_id": payload.get("command_id"),
            "success": payload.get("success", False),
            "message": payload.get("message", ""),
            "current_fps": payload.get("current_fps"),
            "timestamp": payload.get("timestamp"),
        }

        if payload.get("success") and payload.get("current_fps") is not None:
            camera["target_fps"] = payload["current_fps"]

    await broadcast_state()


def on_mqtt_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"MQTT connection failed: {reason_code}")
        return

    print(f"Connected to MQTT broker at {BROKER}:{PORT}")
    client.subscribe("camera/+/telemetry", qos=1)
    client.subscribe("camera/+/status", qos=1)
    client.subscribe("camera/+/response", qos=1)


def on_mqtt_message(client, userdata, message):
    # Paho calls this callback on its network thread. Schedule all state
    # updates on the FastAPI event loop instead of modifying state here.
    if event_loop is not None and not event_loop.is_closed():
        event_loop.call_soon_threadsafe(
            lambda: asyncio.create_task(
                process_mqtt_message(message.topic, message.payload.decode("utf-8"))
            )
        )


async def check_stale_cameras():
    """Mark a camera stale when telemetry stops arriving."""
    while True:
        now = time.monotonic()
        changed = False

        for camera in cameras.values():
            last_seen = camera["last_seen_monotonic"]

            if last_seen is not None and now - last_seen > TELEMETRY_TIMEOUT_SECONDS:
                if camera["connection"] != "stale":
                    camera["connection"] = "stale"
                    changed = True

        if changed:
            await broadcast_state()

        await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global event_loop, mqtt_client

    event_loop = asyncio.get_running_loop()
    initialize_database()

    mqtt_client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"camera-web-dashboard-{uuid.uuid4().hex[:8]}",
    )
    mqtt_client.username_pw_set(*get_dashboard_credentials())
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message

    mqtt_client.connect(BROKER, PORT, keepalive=30)
    mqtt_client.loop_start()

    stale_task = asyncio.create_task(check_stale_cameras())

    print("Camera dashboard backend started.")

    try:
        yield
    finally:
        stale_task.cancel()

        if mqtt_client is not None:
            mqtt_client.disconnect()
            mqtt_client.loop_stop()
            if db is not None:
                db.close()
                db = None

        event_loop = None
        print("Camera dashboard backend stopped.")


app = FastAPI(title="MQTT Camera Dashboard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class FPSCommand(BaseModel):
    fps: int = Field(ge=1, le=60)


@app.get("/")
async def homepage():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/cameras")
async def get_cameras():
    return {"cameras": public_camera_state()}

@app.get("/api/history")
async def get_history(device_id: str = "camera01", minutes: int = 60):
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Telemetry database is not ready",
        )

    if not device_id or len(device_id) > 100:
        raise HTTPException(status_code=400, detail="Invalid device ID")

    if not 1 <= minutes <= 10080:
        raise HTTPException(
            status_code=400,
            detail="Minutes must be between 1 and 10080",
        )

    cutoff = time.time() - minutes * 60

    rows = db.execute(
        """
        SELECT received_at, fps, target_fps, temperature_c
        FROM telemetry
        WHERE device_id = ? AND received_at_epoch >= ?
        ORDER BY received_at_epoch ASC
        LIMIT 10000
        """,
        (device_id, cutoff),
    ).fetchall()

    return {
        "device_id": device_id,
        "minutes": minutes,
        "count": len(rows),
        "readings": [
            {
                "timestamp": row[0],
                "fps": row[1],
                "target_fps": row[2],
                "temperature_c": row[3],
            }
            for row in rows
        ],
    }


@app.post("/api/cameras/{device_id}/fps")
async def set_camera_fps(device_id: str, command: FPSCommand):
    if device_id not in cameras:
        raise HTTPException(status_code=404, detail="Unknown camera")

    if mqtt_client is None or not mqtt_client.is_connected():
        raise HTTPException(status_code=503, detail="MQTT broker is not connected")

    command_id = str(uuid.uuid4())
    topic = f"camera/{device_id}/command"

    payload = {
        "command_id": command_id,
        "action": "set_fps",
        "fps": command.fps,
    }

    result = mqtt_client.publish(
        topic,
        json.dumps(payload),
        qos=1,
        retain=False,
    )

    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        raise HTTPException(status_code=503, detail="Could not publish MQTT command")

    return {
        "published": True,
        "device_id": device_id,
        "command_id": command_id,
        "requested_fps": command.fps,
        "message": "Command sent. Waiting for the camera response.",
    }


@app.websocket("/ws")
async def camera_websocket(websocket: WebSocket):
    await websocket.accept()
    websocket_clients.add(websocket)

    try:
        await websocket.send_text(json.dumps({
            "type": "camera_state",
            "cameras": public_camera_state(),
        }))

        while True:
            # Keep the connection alive and detect disconnected browsers.
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass
    finally:
        websocket_clients.discard(websocket)
