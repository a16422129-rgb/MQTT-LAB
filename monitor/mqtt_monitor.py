
import json

import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print("Connection failed:", reason_code)
        return

    client.subscribe("camera/+/telemetry", qos=0)
    client.subscribe("camera/+/status", qos=1)

    print("Connected to Mosquitto.")
    print("Monitoring all camera devices...\n")


def on_message(client, userdata, message):
    try:
        data = json.loads(message.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        print("Invalid JSON received on", message.topic)
        return

    print(f"Topic: {message.topic}")

    if message.topic.endswith("/telemetry"):
        print(
            f"  {data.get('device_id')} | "
            f"FPS: {data.get('fps')} | "
            f"Temperature: {data.get('temperature_c')} °C"
        )
    elif message.topic.endswith("/status"):
        print(
            f"  {data.get('device_id')} | "
            f"Status: {data.get('status')} | "
            f"Reason: {data.get('reason', 'reported')}"
        )

    print("-" * 45)


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
