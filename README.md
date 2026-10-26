# MQTT Camera Monitoring Lab

A local IoT lab built with Python, Mosquitto, MQTT, FastAPI, and WebSockets. Simulates two cameras and monitors them through a live browser dashboard.

## Architecture

`Camera simulators ↔ MQTT (Mosquitto) ↔ FastAPI ↔ Web dashboard`

- Live FPS and temperature telemetry
- Online/offline status, Last Will and Testament (LWT), and stale-device detection
- Remote target-FPS commands with device responses
- MQTT QoS 1 and retained status messages
- Per-client MQTT username/password authentication (no TLS in this stage)

## Requirements

- Python 3.10+
- Mosquitto running locally on `127.0.0.1:1883`
- A Mosquitto configuration that disables anonymous connections and uses the
  password and ACL files described below

## Setup

From PowerShell in the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install paho-mqtt python-dotenv fastapi "uvicorn[standard]"
```

### MQTT credential configuration

Copy `.env.example` to `.env`, then replace every password placeholder with the
password for its matching Mosquitto account. `.env` is ignored by Git and must
never be committed or logged. The clients fail before connecting when their
required credentials are absent.

```powershell
Copy-Item .env.example .env
```

The four accounts are `camera01`, `camera02`, `dashboard`, and `monitor`.
Each simulator uses its matching camera account; the web dashboard uses
`dashboard`; and the read-only console monitor uses `monitor`. The
`send_command.py` utility intentionally uses the `dashboard` account because it
publishes command messages, which the read-only `monitor` account is not
allowed to do.

### Mosquitto password and ACL setup (manual)

`security/aclfile` documents the intended least-privilege permissions:

| Account | Read | Write |
| --- | --- | --- |
| `camera01` | `camera/camera01/command` | `camera/camera01/telemetry`, `camera/camera01/status`, `camera/camera01/response` |
| `camera02` | `camera/camera02/command` | `camera/camera02/telemetry`, `camera/camera02/status`, `camera/camera02/response` |
| `dashboard` | `camera/+/telemetry`, `camera/+/status`, `camera/+/response` | `camera/+/command` |
| `monitor` | `camera/+/telemetry`, `camera/+/status`, `camera/+/response` | none |

Create a Mosquitto password file outside source control, one account at a time.
Use `-c` only for the first account so the later commands preserve the file:

```powershell
mosquitto_passwd -c .\security\passwordfile camera01
mosquitto_passwd .\security\passwordfile camera02
mosquitto_passwd .\security\passwordfile dashboard
mosquitto_passwd .\security\passwordfile monitor
```

An administrator must then configure the Mosquitto Windows service to use the
absolute paths to `security/passwordfile` and `security/aclfile`, and set
`allow_anonymous false`. This change and the required service restart are
deliberately not performed by this project. Keep the password file private and
out of source control.

## Run

Open separate PowerShell windows. Run each command from the project root.

1. Start Mosquitto (if it is not already running).
2. Start the MQTT monitor:

   ```powershell
   .\.venv\Scripts\python.exe .\monitor\mqtt_monitor.py
   ```

3. Start camera 1:

   ```powershell
   .\.venv\Scripts\python.exe .\devices\camera_simulator.py camera01
   ```

4. Start camera 2:

   ```powershell
   .\.venv\Scripts\python.exe .\devices\camera_simulator.py camera02
   ```

5. Start the web dashboard backend:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn web.app:app --host 127.0.0.1 --port 8000
   ```

6. Open http://127.0.0.1:8000 in your browser.

## Send a command from the terminal

```powershell
.\.venv\Scripts\python.exe .\monitor\send_command.py camera01 20
```

The dashboard can also send FPS commands. Valid target FPS values are 1–60.

## Verification checklist

After an administrator has enabled the Mosquitto configuration above and each
`.env` value matches its password-file account:

1. Run the monitor, both cameras, and the dashboard as shown above. Each should
   print its normal connection message. A missing `.env` value instead produces
   a local configuration error without revealing a password; a wrong password
   produces the client's MQTT connection-failed message.
2. Check that both camera telemetry streams appear in the monitor and browser.
   Attempting to publish to a camera topic owned by the other camera with that
   camera's credentials must be denied by Mosquitto.
3. Use the dashboard's FPS control (or `send_command.py`) for `camera01` and
   `camera02`. The dashboard should receive each response and display the new
   target FPS. `send_command.py` uses `dashboard` credentials for this reason.
4. Run `mqtt_monitor.py` with the `monitor` account and confirm it receives
   telemetry, retained status, and responses. Attempting to publish a command
   with `monitor` credentials must be denied by Mosquitto.
5. Leave the dashboard running for several telemetry intervals, refresh it, and
   inspect its historical chart. Live WebSocket updates and SQLite history
   should continue to populate as before.

For ACL-denial checks, use a separate test client or `mosquitto_pub` with the
account under test. Do not use the `monitor` program itself to publish: it is
intentionally read-only.

## Notes

- This is a local learning project, not a production-secured deployment.
- TLS is intentionally not configured in this stage.
- Camera state is kept in memory and resets when the web backend restarts.
- QoS 1 may deliver duplicate messages; consumers should be designed accordingly.
