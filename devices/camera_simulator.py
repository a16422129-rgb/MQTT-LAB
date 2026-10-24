import json
import random
import sys
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883

# Usage: python camera_simulator.py camera01
DEVICE_ID = sys.argv[1] if len(sys.argv) > 1 else "camera01"

TELEMETRY_TOPIC = f"camera/{DEVICE_ID}/telemetry"
STATUS_TOPIC = f"camera/{DEVICE_ID}/status"

fps = 30 if DEVICE_ID == "camera01" else 25
temperature_c = 42.0 if DEVICE_ID == "camera01" else 48.0


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print("Connection failed:", reason_code)
        return

    # Tell the broker to publish offline if this client disconnects
    # unexpectedly. The broker stores this as its Last Will.
    print(f"{DEVICE_ID} connected to broker.")


client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id=f"{DEVICE_ID}-simulator",
)

client.on_connect = on_connect

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
    # Publish online status after connecting.
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

    print(f"Publishing telemetry: {TELEMETRY_TOPIC}")
    print("Press Ctrl+C to stop this simulator.\n")

    while True:
        temperature_c += random.uniform(-0.5, 0.7)
        temperature_c = max(25.0, min(85.0, temperature_c))
        actual_fps = max(0, fps + random.randint(-2, 1))

        telemetry = {
            "device_id": DEVICE_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fps": actual_fps,
            "temperature_c": round(temperature_c, 1),
            "status": "online",
        }

        result = client.publish(
            TELEMETRY_TOPIC,
            json.dumps(telemetry),
            qos=0,
            retain=False,
        )

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print("Published:", json.dumps(telemetry))
        else:
            print("Publish failed:", result.rc)

        time.sleep(2)

except KeyboardInterrupt:
    print(f"\nStopping {DEVICE_ID}...")

    # A graceful shutdown should publish offline explicitly.
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
