# MQTT Camera Monitoring Lab

A local IoT lab built with Python, Mosquitto, MQTT, FastAPI, and WebSockets. Simulates two cameras and monitors them through a live browser dashboard.

## Architecture

`Camera simulators ↔ MQTT (Mosquitto) ↔ FastAPI ↔ Web dashboard`

- Live FPS and temperature telemetry
- Online/offline status, Last Will and Testament (LWT), and stale-device detection
- Remote target-FPS commands with device responses
- MQTT QoS 1 and retained status messages

## Requirements

- Python 3.10+
- Mosquitto running locally on `127.0.0.1:1883`

## Setup

From PowerShell in the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install paho-mqtt fastapi "uvicorn[standard]"
```

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

## Notes

- This is a local learning project, not a production-secured deployment.
- Camera state is kept in memory and resets when the web backend restarts.
- QoS 1 may deliver duplicate messages; consumers should be designed accordingly.
