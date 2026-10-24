
import json

import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883


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
