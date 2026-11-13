import json
import random
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mqtt_config import (
    BROKER_HOST,
    BROKER_PORT,
    configure_reconnect,
    configure_tls,
    get_role_credentials,
)

DEVICE_ID = sys.argv[1] if len(sys.argv) > 1 else "camera01"


def get_camera_credentials(device_id):
    if device_id not in {"camera01", "camera02"}:
        raise ValueError(
            "Device ID must be camera01 or camera02 when authentication is enabled."
        )

    return get_role_credentials(device_id)

TELEMETRY_TOPIC = f"camera/{DEVICE_ID}/telemetry"
STATUS_TOPIC = f"camera/{DEVICE_ID}/status"
COMMAND_TOPIC = f"camera/{DEVICE_ID}/command"
RESPONSE_TOPIC = f"camera/{DEVICE_ID}/response"

# Simulated camera state
fps = 30 if DEVICE_ID == "camera01" else 25
temperature_c = 42.0 if DEVICE_ID == "camera01" else 48.0


def publish_response(client, command_id, success, message):
    response = {
        "device_id": DEVICE_ID,
        "command_id": command_id,
        "success": success,
        "message": message,
        "current_fps": fps,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    info = client.publish(
        RESPONSE_TOPIC,
        json.dumps(response),
        qos=1,
        retain=False,
    )
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        print(
            f"[{DEVICE_ID}] Warning: Failed to publish command response: "
            f"{mqtt.error_string(info.rc)}"
        )


def publish_status(client, status, reason=None):
    """Publish camera online/offline status with QoS 1 and retain flag."""
    payload = {
        "device_id": DEVICE_ID,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if reason:
        payload["reason"] = reason

    info = client.publish(
        STATUS_TOPIC,
        json.dumps(payload),
        qos=1,
        retain=True,
    )
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        print(
            f"[{DEVICE_ID}] Warning: Failed to publish {status} status: "
            f"{mqtt.error_string(info.rc)}"
        )
    else:
        print(f"[{DEVICE_ID}] Status published: {status}")
    return info


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"[{DEVICE_ID}] MQTT connection failed: {reason_code}")
        return

    print(
        f"[{DEVICE_ID}] Connected to MQTT broker at {BROKER_HOST}:{BROKER_PORT} "
        f"(session present: {flags.session_present})."
    )
    client.subscribe(COMMAND_TOPIC, qos=1)
    print(f"[{DEVICE_ID}] Listening for commands on: {COMMAND_TOPIC}")

    # Ensure the camera publishes its online status only after a successful connection.
    # When reconnecting after a broker restart or network blip, this re-announces online state.
    publish_status(client, "online")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    if reason_code.is_failure:
        print(
            f"[{DEVICE_ID}] Disconnected from MQTT broker unexpectedly ({reason_code}). "
            "Paho will attempt automatic reconnection..."
        )
    else:
        print(f"[{DEVICE_ID}] Disconnected from MQTT broker cleanly.")


def on_message(client, userdata, message):
    global fps

    try:
        command = json.loads(message.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        print("Received invalid JSON command.")
        publish_response(client, "unknown", False, "Invalid JSON")
        return

    command_id = str(command.get("command_id", "unknown"))
    action = command.get("action")

    if action != "set_fps":
        publish_response(
            client, command_id, False, "Unsupported action"
        )
        return

    requested_fps = command.get("fps")

    # Reject booleans, strings, and values outside the allowed range.
    if type(requested_fps) is not int or not 1 <= requested_fps <= 60:
        publish_response(
            client,
            command_id,
            False,
            "FPS must be an integer between 1 and 60",
        )
        return

    fps = requested_fps
    print(f"Command applied: FPS target changed to {fps}")

    publish_response(
        client,
        command_id,
        True,
        f"Target FPS set to {fps}",
    )


client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id=f"{DEVICE_ID}-simulator",
)
client.username_pw_set(*get_camera_credentials(DEVICE_ID))
configure_tls(client)
configure_reconnect(client)

client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message

client.will_set(
    STATUS_TOPIC,
    payload=json.dumps({
        "device_id": DEVICE_ID,
        "status": "offline",
        "reason": "unexpected_disconnect",
    }),
    qos=1,
    retain=True,
)

try:
    client.connect_async(BROKER_HOST, BROKER_PORT, keepalive=10)
except Exception as error:
    print(f"[{DEVICE_ID}] Initial connection attempt error: {error}")

client.loop_start()

try:
    print(f"\n{DEVICE_ID} simulator is running.")
    print("Press Ctrl+C to stop.\n")

    while True:
        temperature_c += random.uniform(-0.5, 0.7)
        temperature_c = max(25.0, min(85.0, temperature_c))

        actual_fps = max(0, fps + random.randint(-2, 1))

        telemetry = {
            "device_id": DEVICE_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fps": actual_fps,
            "target_fps": fps,
            "temperature_c": round(temperature_c, 1),
            "status": "online",
        }

        if client.is_connected():
            info = client.publish(
                TELEMETRY_TOPIC,
                json.dumps(telemetry),
                qos=1,
                retain=False,
            )
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                print(
                    f"[{DEVICE_ID}] Failed to publish telemetry: "
                    f"{mqtt.error_string(info.rc)}"
                )
            else:
                print(
                    f"Telemetry: target FPS={fps}, "
                    f"actual FPS={actual_fps}, "
                    f"temperature={temperature_c:.1f} C"
                )
        else:
            print(f"[{DEVICE_ID}] Waiting for MQTT connection before publishing telemetry...")

        time.sleep(2)

except KeyboardInterrupt:
    print(f"\nStopping {DEVICE_ID}...")

    if client.is_connected():
        try:
            info = publish_status(client, "offline", reason="graceful_shutdown")
            info.wait_for_publish(timeout=3)
            print(f"[{DEVICE_ID}] Graceful offline status delivered.")
        except Exception as error:
            print(f"[{DEVICE_ID}] Failed to deliver graceful offline status: {error}")
    else:
        print(f"[{DEVICE_ID}] Client not connected; skipping offline status publish.")

finally:
    client.disconnect()
    client.loop_stop()
