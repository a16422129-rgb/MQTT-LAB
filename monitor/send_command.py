
import json
import sys
import uuid
import threading
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
    connection_error = None

    def on_connect(client, userdata, flags, reason_code, properties):
        nonlocal connection_error
        if reason_code.is_failure:
            connection_error = str(reason_code)
            print(f"MQTT connection failed: {reason_code}")
        else:
            connected.set()

    def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"Disconnected from MQTT broker: {reason_code}")

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"command-sender-{uuid.uuid4().hex[:8]}",
    )
    client.username_pw_set(*get_role_credentials("dashboard"))
    configure_tls(client)
    configure_reconnect(client, min_delay=1, max_delay=5)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=10)
        client.loop_start()

        if not connected.wait(timeout=5):
            if connection_error:
                print(f"Could not connect to the MQTT broker: {connection_error}")
            else:
                print("Could not connect to the MQTT broker (connection timed out after 5 seconds).")
            return

        info = client.publish(
            topic,
            json.dumps(command),
            qos=1,
            retain=False,
        )

        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"Failed to publish command: {mqtt.error_string(info.rc)}")
            return

        try:
            info.wait_for_publish(timeout=5)
        except (RuntimeError, ValueError) as error:
            print(f"Command publish error: {error}")
            return

        if info.is_published():
            print("Command published successfully.")
            print("Topic:", topic)
            print("Command ID:", command_id)
            print("Payload:", json.dumps(command))
            print("Check the monitor for the device response.")
        else:
            print("Command publish timed out after 5 seconds.")

    except OSError as error:
        print("MQTT connection error:", error)
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
