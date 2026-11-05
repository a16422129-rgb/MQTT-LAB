"""Shared authenticated MQTT-over-TLS configuration for the camera lab."""

import os
import ssl
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


def _required_environment(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _environment_port():
    value = _required_environment("MQTT_BROKER_PORT")
    try:
        port = int(value)
    except ValueError as error:
        raise RuntimeError("MQTT_BROKER_PORT must be an integer.") from error

    if not 1 <= port <= 65535:
        raise RuntimeError("MQTT_BROKER_PORT must be between 1 and 65535.")

    return port


def _environment_boolean(name):
    value = _required_environment(name).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be true or false.")


def _environment_ca_certificate():
    configured_path = Path(_required_environment("MQTT_TLS_CA_CERT"))
    certificate_path = (
        configured_path
        if configured_path.is_absolute()
        else PROJECT_ROOT / configured_path
    ).resolve()

    if not certificate_path.is_file():
        raise RuntimeError(
            "MQTT_TLS_CA_CERT does not point to a readable CA certificate."
        )

    return certificate_path


BROKER_HOST = _required_environment("MQTT_BROKER_HOST")
BROKER_PORT = _environment_port()
USE_TLS = _environment_boolean("MQTT_USE_TLS")
TLS_CA_CERT = _environment_ca_certificate()

ROLE_CREDENTIAL_ENVIRONMENTS = {
    "camera01": ("MQTT_CAMERA01_USERNAME", "MQTT_CAMERA01_PASSWORD"),
    "camera02": ("MQTT_CAMERA02_USERNAME", "MQTT_CAMERA02_PASSWORD"),
    "dashboard": ("MQTT_DASHBOARD_USERNAME", "MQTT_DASHBOARD_PASSWORD"),
    "monitor": ("MQTT_MONITOR_USERNAME", "MQTT_MONITOR_PASSWORD"),
}


def get_role_credentials(role):
    """Return the configured username/password pair for one MQTT role."""
    try:
        username_key, password_key = ROLE_CREDENTIAL_ENVIRONMENTS[role]
    except KeyError as error:
        raise ValueError(f"Unknown MQTT role: {role}") from error

    username = _required_environment(username_key)
    password = _required_environment(password_key)
    return username, password


def configure_tls(client):
    """Require verified TLS before the client connects to the broker."""
    if not USE_TLS:
        raise RuntimeError(
            "MQTT_USE_TLS must be true; plaintext MQTT is not supported by this application."
        )

    # Paho's tls_set() uses a PROTOCOL_TLS_CLIENT context on supported Python
    # versions. CERT_REQUIRED and the default hostname checks remain enabled.
    client.tls_set(ca_certs=str(TLS_CA_CERT), cert_reqs=ssl.CERT_REQUIRED)
