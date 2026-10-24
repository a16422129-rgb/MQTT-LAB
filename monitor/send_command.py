
import json
import sys
import uuid
import threading

import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883


def main():
    if len(sys.argv) != 3:
        print(
            "Usage: python send_command.py <device_id> <fps>\n"
            "Example: python send_command.py camera01 20"
        )
        raise SystemExit(1)

    device_id = sys.argv[1]

    try:
        requested_fps = int(sys.argv[2])
    except ValueError:
        print("FPS must be an integer.")
        raise SystemExit(1)

    command_id = str(uuid.uuid4())

    topic = f"camera/{device_id}/command"

    command = {
        "command_id": command_id,
        "action": "set_fps",
        "fps": requested_fps,
    }

    connected = threading.Event()

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print("MQTT connection failed:", reason_code)
        else:
            connected.set()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"command-sender-{uuid.uuid4().hex[:8]}",
    )
    client.on_connect = on_connect

    try:
        client.connect(BROKER, PORT, keepalive=60)
        client.loop_start()

        if not connected.wait(timeout=5):
            print("Could not connect to the MQTT broker.")
            return

        info = client.publish(
            topic,
            json.dumps(command),
            qos=1,
            retain=False,
        )

        info.wait_for_publish(timeout=5)

        if info.is_published():
            print("Command published successfully.")
            print("Topic:", topic)
            print("Command ID:", command_id)
            print("Payload:", json.dumps(command))
            print("Check the monitor for the device response.")
        else:
            print("Command publish timed out.")

    except OSError as error:
        print("MQTT error:", error)
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
