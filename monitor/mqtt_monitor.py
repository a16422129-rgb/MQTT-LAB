import json

import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883
TELEMETRY_TOPIC = "camera/+/telemetry"


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print("MQTT connection failed:", reason_code)
        return

    print("Connected to MQTT broker.")
    client.subscribe(TELEMETRY_TOPIC, qos=0)
    print("Subscribed to:", TELEMETRY_TOPIC)
    print("Waiting for camera telemetry...\n")


def on_message(client, userdata, message):
    try:
        telemetry = json.loads(message.payload.decode("utf-8"))
        print(f"Topic: {message.topic}")
        print(f"Device: {telemetry['device_id']}")
        print(f"FPS: {telemetry['fps']}")
        print(f"Temperature: {telemetry['temperature_c']} °C")
        print(f"Status: {telemetry['status']}")
        print("-" * 40)

    except (UnicodeDecodeError, json.JSONDecodeError, KeyError) as error:
        print("Could not process message:", error)


client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id="camera-monitor",
)

client.on_connect = on_connect
client.on_message = on_message

print("Starting MQTT monitor...")
client.connect(BROKER, PORT, keepalive=60)

try:
    client.loop_forever()
except KeyboardInterrupt:
    print("\nStopping monitor...")
finally:
    client.disconnect()
