"""Automated Test Suite for Full-Duplex WebSocket Telemetry Streaming Endpoint."""
import pytest
from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_websocket_telemetry_streaming(sample_telemetry):
    """Verify full-duplex WebSocket connection, handshake, and bidirectional telemetry exchange."""
    with client.websocket_connect("/ws/telemetry") as websocket:
        # 1. Verify Handshake
        handshake = websocket.receive_json()
        assert handshake["event"] == "CONNECTED"
        assert handshake["status"] == "OPERATIONAL"

        # 2. Transmit Telemetry Payload
        payload = sample_telemetry.model_dump()
        websocket.send_json(payload)

        # 3. Receive Real-Time Telemetry & SOP Update
        response = websocket.receive_json()
        assert response["event"] == "TELEMETRY_UPDATE"
        assert "telemetry" in response
        assert response["telemetry"]["central_pressure_hpa"] == 940.0
        assert response["telemetry"]["twse_m"] > 0.0

        assert "incident_command_sop" in response
        sop = response["incident_command_sop"]
        assert sop["threat_posture"] in ["RED", "ORANGE", "YELLOW"]
        assert len(sop["asset_breaches"]) > 0

        assert "parametric_status" in response
