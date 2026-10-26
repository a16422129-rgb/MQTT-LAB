
import json
import os
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

BROKER = "127.0.0.1"
PORT = 1883

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def get_monitor_credentials():
    username = os.getenv("MQTT_MONITOR_USERNAME")
    password = os.getenv("MQTT_MONITOR_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "Missing monitor MQTT credentials. Set MQTT_MONITOR_USERNAME and "
            "MQTT_MONITOR_PASSWORD in the root .env file."
        )

    return username, password


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print("MQTT connection failed:", reason_code)
        return

    client.subscribe("camera/+/telemetry", qos=1)
    client.subscribe("camera/+/status", qos=1)
    client.subscribe("camera/+/response", qos=1)

    print("Connected to Mosquitto.")
    print("Monitoring telemetry, status, and command responses.\n")


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
client.username_pw_set(*get_monitor_credentials())

client.on_connect = on_connect
client.on_message = on_message

print("Starting camera monitor...")
client.connect(BROKER, PORT, keepalive=60)

try:
    client.loop_forever()
except KeyboardInterrupt:
    print("\nMonitor stopped.")
finally:
    client.disconnect()
