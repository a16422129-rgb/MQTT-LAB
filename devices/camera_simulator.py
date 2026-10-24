import json
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883
DEVICE_ID = "camera01"
TELEMETRY_TOPIC = f"camera/{DEVICE_ID}/telemetry"

# These values represent a simulated camera's current state.
fps = 30
temperature_c = 42.0

client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id=f"{DEVICE_ID}-simulator",
)

client.connect(BROKER, PORT, keepalive=60)
client.loop_start()

print(f"{DEVICE_ID} simulator started.")
print(f"Publishing to: {TELEMETRY_TOPIC}")
print("Press Ctrl+C to stop.\n")

try:
    while True:
        # Simulate small changes in camera temperature.
        temperature_c += random.uniform(-0.5, 0.7)
        temperature_c = max(25.0, min(85.0, temperature_c))

        # Simulate FPS fluctuating slightly around the target.
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
            print("Publish failed; MQTT error code:", result.rc)

        time.sleep(2)

except KeyboardInterrupt:
    print("\nStopping simulator...")

finally:
    client.loop_stop()
    client.disconnect()
