"""Tests for Battery Hawk API system endpoints."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from src.battery_hawk.api import BatteryHawkAPI
from src.battery_hawk.config.config_manager import ConfigManager
from src.battery_hawk.core.engine import BatteryHawkCore


class MockDataStorage:
    """Mock data storage for testing."""

    def __init__(self) -> None:
        """Initialize mock data storage."""
        self.connected = True

    def is_connected(self):
        """Mock is connected."""
        return self.connected

    async def health_check(self):
        """Mock health check."""
        return self.connected

    def get_health_status(self):
        """Mock get health status."""
        return MagicMock(
            connected=self.connected, backend_name="MockDB", backend_version="1.0"
        )

    def get_metrics(self):
        """Mock get metrics."""
        return MagicMock(total_writes=100, successful_writes=95, failed_writes=5)


class MockDiscoveryService:
    """Mock discovery service for testing."""

    def __init__(self) -> None:
        """Initialize mock discovery service."""
        self.discovered_devices = {"AA:BB:CC:DD:EE:FF": {}}
        self.scanning = False


class MockDeviceRegistry:
    """Mock device registry for testing."""

    def __init__(self) -> None:
        """Initialize mock device registry."""
        self.devices = {
            "AA:BB:CC:DD:EE:FF": {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "device_type": "BM6",
                "status": "configured",
            }
        }

    def get_configured_devices(self):
        """Get configured devices."""
        return [
            device
            for device in self.devices.values()
            if device.get("status") == "configured"
        ]


class MockVehicleRegistry:
    """Mock vehicle registry for testing."""

    def __init__(self) -> None:
        """Initialize mock vehicle registry."""
        self.vehicles = {
            "vehicle_1": {
                "name": "Test Vehicle",
                "created_at": "2025-01-01T10:00:00Z",
            }
        }


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
def mock_config_manager():
    """Create a mock configuration manager."""
    return MockConfigManager()


@pytest.fixture
def mock_core_engine(mock_config_manager):
    """Create a mock core engine."""
    mock_engine = MagicMock(spec=BatteryHawkCore)
    mock_engine.running = True
    mock_engine.device_registry = MockDeviceRegistry()
    mock_engine.vehicle_registry = MockVehicleRegistry()
    mock_engine.discovery_service = MockDiscoveryService()
    mock_engine.data_storage = MockDataStorage()
    mock_engine.config = mock_config_manager  # Add config manager

    # Mock get_status method
    mock_engine.get_status.return_value = {
        "running": True,
        "active_tasks": 2,
        "active_devices": 1,
        "polling_tasks": 1,
        "storage_connected": True,
        "discovered_devices": 1,
        "configured_devices": 1,
        "vehicles": 1,
        "state_manager": {
            "total_devices": 1,
            "connected_devices": 1,
            "polling_devices": 1,
            "devices_with_errors": 0,
        },
    }

    return mock_engine


@pytest.fixture
def api_instance(mock_config_manager, mock_core_engine):
    """Create a BatteryHawkAPI instance for testing."""
    return BatteryHawkAPI(mock_config_manager, mock_core_engine)


@pytest.fixture
def client(api_instance):
    """Create a test client."""
    return api_instance.app.test_client()


class TestSystemEndpoints:
    """Test cases for system API endpoints."""

    def test_get_system_config(self, client) -> None:
        """Test GET /api/system/config endpoint."""
        response = client.get("/api/system/config")
        assert response.status_code == 200

        data = response.get_json()
        assert "data" in data
        assert data["data"]["type"] == "system-config"
        assert data["data"]["id"] == "current"
        assert "attributes" in data["data"]
        assert "logging" in data["data"]["attributes"]
        assert "bluetooth" in data["data"]["attributes"]

    def test_update_system_config_success(self, client) -> None:
        """Test PATCH /api/system/config endpoint with valid updates."""
        request_data = {
            "data": {
                "type": "system-config",
                "id": "current",
                "attributes": {
                    "logging": {"level": "DEBUG"},
                    "bluetooth": {"max_concurrent_connections": 5},
                },
            }
        }

        response = client.patch(
            "/api/system/config",
            data=json.dumps(request_data),
            content_type="application/json",
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["data"]["attributes"]["logging"]["level"] == "DEBUG"
        assert (
            data["data"]["attributes"]["bluetooth"]["max_concurrent_connections"] == 5
        )

    def test_update_system_config_invalid_section(self, client) -> None:
        """Test PATCH /api/system/config endpoint with invalid section."""
        request_data = {
            "data": {
                "type": "system-config",
                "id": "current",
                "attributes": {
                    "version": "2.0"  # Not allowed to modify
                },
            }
        }

        response = client.patch(
            "/api/system/config",
            data=json.dumps(request_data),
            content_type="application/json",
        )
        assert response.status_code == 400

        data = response.get_json()
        assert "errors" in data
        assert "cannot be modified" in data["errors"][0]["detail"]

    def test_update_system_config_invalid_logging_level(self, client) -> None:
        """Test PATCH /api/system/config endpoint with invalid logging level."""
        request_data = {
            "data": {
                "type": "system-config",
                "id": "current",
                "attributes": {"logging": {"level": "INVALID"}},
            }
        }

        response = client.patch(
            "/api/system/config",
            data=json.dumps(request_data),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_update_system_config_invalid_bluetooth_connections(self, client) -> None:
        """Test PATCH /api/system/config endpoint with invalid bluetooth connections."""
        request_data = {
            "data": {
                "type": "system-config",
                "id": "current",
                "attributes": {
                    "bluetooth": {
                        "max_concurrent_connections": 20  # Too high
                    }
                },
            }
        }

        response = client.patch(
            "/api/system/config",
            data=json.dumps(request_data),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_update_system_config_invalid_api_port(self, client) -> None:
        """Test PATCH /api/system/config endpoint with invalid API port."""
        request_data = {
            "data": {
                "type": "system-config",
                "id": "current",
                "attributes": {
                    "api": {
                        "port": 100  # Too low
                    }
                },
            }
        }

        response = client.patch(
            "/api/system/config",
            data=json.dumps(request_data),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_update_system_config_validation_error(self, client) -> None:
        """Test PATCH /api/system/config endpoint with validation errors."""
        # Missing required data structure
        request_data = {"type": "system-config", "attributes": {}}

        response = client.patch(
            "/api/system/config",
            data=json.dumps(request_data),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_get_system_status(self, client) -> None:
        """Test GET /api/system/status endpoint."""
        response = client.get("/api/system/status")
        assert response.status_code == 200

        data = response.get_json()
        assert "data" in data
        assert data["data"]["type"] == "system-status"
        assert data["data"]["id"] == "current"

        attributes = data["data"]["attributes"]
        assert "core" in attributes
        assert "storage" in attributes
        assert "components" in attributes
        assert "timestamp" in attributes

        # Check core status
        assert attributes["core"]["running"] is True
        assert attributes["core"]["active_tasks"] == 2

        # Check storage status
        assert attributes["storage"]["connected"] is True

        # Check components
        components = attributes["components"]
        assert "device_registry" in components
        assert "vehicle_registry" in components
        assert "discovery_service" in components
        assert "state_manager" in components

    def test_get_system_health_healthy(self, client) -> None:
        """Test GET /api/system/health endpoint when system is healthy."""
        response = client.get("/api/system/health")
        assert response.status_code == 200

        data = response.get_json()
        assert "data" in data
        assert data["data"]["type"] == "system-health"
        assert data["data"]["attributes"]["healthy"] is True
        assert data["data"]["attributes"]["components"]["core_engine"] is True
        assert data["data"]["attributes"]["components"]["data_storage"] is True

    def test_get_system_health_unhealthy(self, client, mock_core_engine) -> None:
        """Test GET /api/system/health endpoint when system is unhealthy."""
        # Make storage unhealthy
        mock_core_engine.data_storage.connected = False

        response = client.get("/api/system/health")
        assert response.status_code == 503  # Service Unavailable

        data = response.get_json()
        assert data["data"]["attributes"]["healthy"] is False
        assert data["data"]["attributes"]["components"]["data_storage"] is False

    def test_system_config_wrong_resource_id(self, client) -> None:
        """Test PATCH /api/system/config endpoint with wrong resource ID."""
        request_data = {
            "data": {
                "type": "system-config",
                "id": "wrong",
                "attributes": {"logging": {"level": "DEBUG"}},
            }
        }

        response = client.patch(
            "/api/system/config",
            data=json.dumps(request_data),
            content_type="application/json",
        )
        assert response.status_code == 409  # Conflict

    def test_system_config_wrong_resource_type(self, client) -> None:
        """Test PATCH /api/system/config endpoint with wrong resource type."""
        request_data = {
            "data": {"type": "wrong-type", "id": "current", "attributes": {}}
        }

        response = client.patch(
            "/api/system/config",
            data=json.dumps(request_data),
            content_type="application/json",
        )
        assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__])
