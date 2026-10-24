import json
import random
import sys
import time
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883

DEVICE_ID = sys.argv[1] if len(sys.argv) > 1 else "camera01"

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

    client.publish(
        RESPONSE_TOPIC,
        json.dumps(response),
        qos=1,
        retain=False,
    )


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print("MQTT connection failed:", reason_code)
        return

    print(f"{DEVICE_ID} connected to broker.")
    client.subscribe(COMMAND_TOPIC, qos=1)
    print(f"Listening for commands on: {COMMAND_TOPIC}")


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

client.on_connect = on_connect
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

client.connect(BROKER, PORT, keepalive=10)
client.loop_start()

try:
    # Wait for the MQTT connection and command subscription to settle.
    time.sleep(1)

    client.publish(
        STATUS_TOPIC,
        json.dumps({
            "device_id": DEVICE_ID,
            "status": "online",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }),
        qos=1,
        retain=True,
    )

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

        client.publish(
            TELEMETRY_TOPIC,
            json.dumps(telemetry),
            qos=1,
            retain=False,
        )

        print(
            f"Telemetry: target FPS={fps}, "
            f"actual FPS={actual_fps}, "
            f"temperature={temperature_c:.1f} C"
        )

        time.sleep(2)

except KeyboardInterrupt:
    print(f"\nStopping {DEVICE_ID}...")

    info = client.publish(
        STATUS_TOPIC,
        json.dumps({
            "device_id": DEVICE_ID,
            "status": "offline",
            "reason": "graceful_shutdown",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }),
        qos=1,
        retain=True,
    )
    info.wait_for_publish(timeout=3)

finally:
    client.disconnect()
    client.loop_stop()
