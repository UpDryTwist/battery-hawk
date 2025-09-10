"""Tests for Battery Hawk API device endpoints."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.battery_hawk.api import BatteryHawkAPI
from src.battery_hawk.config.config_manager import ConfigManager
from src.battery_hawk.core.engine import BatteryHawkCore


class MockDeviceRegistry:
    """Mock device registry for testing."""

    def __init__(self) -> None:
        """Initialize mock device registry."""
        self.devices = {
            "AA:BB:CC:DD:EE:FF": {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "device_type": "BM6",
                "friendly_name": "Test Device",
                "vehicle_id": "vehicle_1",
                "status": "configured",
                "discovered_at": "2025-01-01T10:00:00Z",
                "configured_at": "2025-01-01T10:05:00Z",
                "polling_interval": 3600,
                "connection_config": {
                    "retry_attempts": 3,
                    "retry_interval": 60,
                    "reconnection_delay": 300,
                },
                # New persisted runtime fields
                "latest_reading": {
                    "voltage": 12.6,
                    "current": 1.2,
                    "temperature": 25.0,
                    "state_of_charge": 85.0,
                    "capacity": 50.0,
                    "cycles": 10,
                    "timestamp": 1234567890.0,
                    "extra": {"device_type": "BM6"},
                },
                "last_reading_time": "2025-01-01T10:30:00Z",
                "device_status": {
                    "connected": True,
                    "error_code": None,
                    "error_message": None,
                    "protocol_version": "1.0",
                    "last_command": "status",
                },
                "last_status_update": "2025-01-01T10:30:01Z",
            },
        }

    def get_device(self, mac_address: str) -> Any:
        """Get device by MAC address."""
        return self.devices.get(mac_address)

    async def configure_device(
        self,
        mac_address: str,
        device_type: str,
        friendly_name: str,
        vehicle_id: str | None = None,
        polling_interval: int = 3600,
    ) -> bool:
        """Mock configure device."""
        if mac_address in self.devices:
            self.devices[mac_address].update(
                {
                    "device_type": device_type,
                    "friendly_name": friendly_name,
                    "vehicle_id": vehicle_id,
                    "polling_interval": polling_interval,
                    "status": "configured",
                    "configured_at": "2025-01-01T10:05:00Z",
                },
            )
            return True
        return False

    async def remove_device(self, mac_address: str) -> bool:
        """Mock remove device."""
        if mac_address in self.devices:
            del self.devices[mac_address]
            return True
        return False


class MockStateManager:
    """Mock state manager for testing."""

    async def unregister_device(self, mac_address: str) -> bool:
        """Mock unregister device."""
        return True


class MockConfigManager(ConfigManager):
    """Mock configuration manager for testing."""

    def __init__(self, config_dir: str = "/data") -> None:
        """Initialize mock configuration manager with test data."""
        self.config_dir = config_dir
        self.configs = {
            "system": {
                "version": "1.0",
                "logging": {"level": "INFO"},
                "bluetooth": {"max_concurrent_connections": 3, "test_mode": False},
                "discovery": {"initial_scan": True, "scan_duration": 10},
                "influxdb": {"enabled": False},
                "mqtt": {"enabled": False, "topic_prefix": "batteryhawk"},
                "api": {
                    "enabled": True,
                    "host": "127.0.0.1",
                    "port": 5001,
                    "debug": False,
                },
            },
            "devices": {"version": "1.0", "devices": {}},
            "vehicles": {"version": "1.0", "vehicles": {}},
        }

    def get_config(self, key: str) -> dict:
        """Get a config by key."""
        return self.configs[key]

    def save_config(self, key: str) -> None:
        """Mock save config."""


@pytest.fixture
def mock_config_manager() -> MockConfigManager:
    """Create a mock configuration manager."""
    return MockConfigManager()


@pytest.fixture
def mock_core_engine() -> MagicMock:
    """Create a mock core engine."""
    mock_engine = MagicMock(spec=BatteryHawkCore)
    mock_engine.running = True
    mock_engine.device_registry = MockDeviceRegistry()
    mock_engine.state_manager = MockStateManager()
    return mock_engine


@pytest.fixture
def api_instance(
    mock_config_manager: MockConfigManager,
    mock_core_engine: MagicMock,
) -> BatteryHawkAPI:
    """Create a BatteryHawkAPI instance for testing."""
    return BatteryHawkAPI(mock_config_manager, mock_core_engine)


@pytest.fixture
def client(api_instance: BatteryHawkAPI) -> Any:
    """Create a test client."""
    return api_instance.app.test_client()


class TestDeviceEndpoints:
    """Test cases for device API endpoints."""

    def test_get_devices(self, client: Any) -> None:
        """Test GET /api/devices endpoint."""
        response = client.get("/api/devices")
        assert response.status_code == 200

        data = response.get_json()
        assert "data" in data
        assert "meta" in data
        assert "links" in data
        assert data["meta"]["total"] == 1
        assert len(data["data"]) == 1

        device = data["data"][0]
        assert device["type"] == "devices"
        assert device["id"] == "AA:BB:CC:DD:EE:FF"
        assert device["attributes"]["device_type"] == "BM6"
        assert device["attributes"]["friendly_name"] == "Test Device"
        # New: verify latest_reading and device_status in list response item
        attrs_list = device["attributes"]
        assert "latest_reading" in attrs_list
        assert attrs_list["latest_reading"]["voltage"] == 12.6
        assert attrs_list["device_status"]["connected"] is True

    def test_get_device_found(self, client: Any) -> None:
        """Test GET /api/devices/{mac} endpoint for existing device."""
        response = client.get("/api/devices/AA:BB:CC:DD:EE:FF")
        assert response.status_code == 200

        data = response.get_json()
        assert "data" in data

        device = data["data"]
        assert device["type"] == "devices"
        assert device["id"] == "AA:BB:CC:DD:EE:FF"
        assert device["attributes"]["device_type"] == "BM6"
        # New: verify latest_reading and device_status on single device response
        attrs = device["attributes"]
        assert "latest_reading" in attrs
        assert attrs["latest_reading"]["temperature"] == 25.0
        assert attrs["device_status"]["connected"] is True

    def test_get_device_not_found(self, client: Any) -> None:
        """Test GET /api/devices/{mac} endpoint for non-existing device."""
        response = client.get("/api/devices/XX:XX:XX:XX:XX:XX")
        assert response.status_code == 404

        data = response.get_json()
        assert "errors" in data
        assert data["errors"][0]["status"] == "404"

    def test_configure_device_success(self, client: Any) -> None:
        """Test POST /api/devices endpoint for device configuration."""
        request_data = {
            "data": {
                "type": "devices",
                "attributes": {
                    "mac_address": "AA:BB:CC:DD:EE:FF",
                    "device_type": "BM6",
                    "friendly_name": "Updated Test Device",
                    "vehicle_id": "vehicle_2",
                    "polling_interval": 1800,
                },
            },
        }

        response = client.post(
            "/api/devices",
            data=json.dumps(request_data),
            content_type="application/vnd.api+json",
        )
        assert response.status_code == 200

        data = response.get_json()
        assert "data" in data
        device = data["data"]
        assert device["attributes"]["friendly_name"] == "Updated Test Device"
        assert device["attributes"]["vehicle_id"] == "vehicle_2"

    def test_configure_device_not_found(self, client: Any) -> None:
        """Test POST /api/devices endpoint for non-existing device."""
        request_data = {
            "data": {
                "type": "devices",
                "attributes": {
                    "mac_address": "FF:FF:FF:FF:FF:FF",
                    "device_type": "BM6",
                    "friendly_name": "New Device",
                },
            },
        }

        response = client.post(
            "/api/devices",
            data=json.dumps(request_data),
            content_type="application/vnd.api+json",
        )
        assert response.status_code == 404

    def test_configure_device_validation_error(self, client: Any) -> None:
        """Test POST /api/devices endpoint with validation errors."""
        # Missing required fields
        request_data = {
            "data": {
                "type": "devices",
                "attributes": {
                    "mac_address": "AA:BB:CC:DD:EE:FF",
                    # Missing device_type and friendly_name
                },
            },
        }

        response = client.post(
            "/api/devices",
            data=json.dumps(request_data),
            content_type="application/vnd.api+json",
        )
        assert response.status_code == 400

        data = response.get_json()
        assert "errors" in data

    def test_update_device_success(self, client: Any) -> None:
        """Test PATCH /api/devices/{mac} endpoint."""
        request_data = {
            "data": {
                "type": "devices",
                "id": "AA:BB:CC:DD:EE:FF",
                "attributes": {
                    "friendly_name": "Updated Device Name",
                    "polling_interval": 7200,
                },
            },
        }

        response = client.patch(
            "/api/devices/AA:BB:CC:DD:EE:FF",
            data=json.dumps(request_data),
            content_type="application/json",
        )
        assert response.status_code == 200

        data = response.get_json()
        assert "data" in data
        device = data["data"]
        assert device["attributes"]["friendly_name"] == "Updated Device Name"

    def test_update_device_not_found(self, client: Any) -> None:
        """Test PATCH /api/devices/{mac} endpoint for non-existing device."""
        request_data = {
            "data": {
                "type": "devices",
                "id": "XX:XX:XX:XX:XX:XX",
                "attributes": {"friendly_name": "Updated Name"},
            },
        }

        response = client.patch(
            "/api/devices/XX:XX:XX:XX:XX:XX",
            data=json.dumps(request_data),
            content_type="application/json",
        )
        assert response.status_code == 404

    def test_delete_device_success(self, client: Any) -> None:
        """Test DELETE /api/devices/{mac} endpoint."""
        response = client.delete("/api/devices/AA:BB:CC:DD:EE:FF")
        assert response.status_code == 204

    def test_delete_device_not_found(self, client: Any) -> None:
        """Test DELETE /api/devices/{mac} endpoint for non-existing device."""
        response = client.delete("/api/devices/XX:XX:XX:XX:XX:XX")
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__])
