
import json
import sys
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


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"MQTT connection failed: {reason_code}")
        return

    # Subscribing inside on_connect guarantees subscriptions are established
    # on initial connection and restored after every automatic reconnection.
    client.subscribe("camera/+/telemetry", qos=1)
    client.subscribe("camera/+/status", qos=1)
    client.subscribe("camera/+/response", qos=1)

    print(
        f"Connected to MQTT broker at {BROKER_HOST}:{BROKER_PORT} "
        f"(session present: {flags.session_present})."
    )
    print("Monitoring telemetry, status, and command responses.\n")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    if reason_code.is_failure:
        print(
            f"Disconnected from MQTT broker unexpectedly ({reason_code}). "
            "Paho will attempt automatic reconnection..."
        )
    else:
        print("Disconnected from MQTT broker cleanly.")



def on_message(client, userdata, message):
    try:
        data = json.loads(message.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        print("Invalid JSON on topic:", message.topic)
        return

    print("Topic:", message.topic)

    if message.topic.endswith("/telemetry"):
        print(
            f"  Device: {data.get('device_id')} | "
            f"Target FPS: {data.get('target_fps')} | "
            f"Actual FPS: {data.get('fps')} | "
            f"Temperature: {data.get('temperature_c')} °C"
        )

    elif message.topic.endswith("/status"):
        print(
            f"  Device: {data.get('device_id')} | "
            f"Status: {data.get('status')} | "
            f"Reason: {data.get('reason', 'reported')}"
        )

    elif message.topic.endswith("/response"):
        print(
            f"  Device: {data.get('device_id')} | "
            f"Command ID: {data.get('command_id')} | "
            f"Success: {data.get('success')} | "
            f"Message: {data.get('message')} | "
            f"Current FPS: {data.get('current_fps')}"
        )

    print("-" * 65)


client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id="camera-monitor",
)
client.username_pw_set(*get_role_credentials("monitor"))
configure_tls(client)
configure_reconnect(client)

client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message

print("Starting camera monitor...")
try:
    client.connect_async(BROKER_HOST, BROKER_PORT, keepalive=60)
except Exception as error:
    print(f"Initial connection setup error: {error}")

try:
    client.loop_forever(retry_first_connection=True)
except KeyboardInterrupt:
    print("\nMonitor stopped.")
finally:
    client.disconnect()
