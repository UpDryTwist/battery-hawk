"""Tests for Battery Hawk API vehicle endpoints."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.battery_hawk.api import BatteryHawkAPI
from src.battery_hawk.config.config_manager import ConfigManager
from src.battery_hawk.core.engine import BatteryHawkCore


class MockVehicleRegistry:
    """Mock vehicle registry for testing."""

    def __init__(self) -> None:
        """Initialize mock vehicle registry."""
        self.vehicles = {
            "vehicle_1": {
                "name": "Test Vehicle",
                "created_at": "2025-01-01T10:00:00Z",
                "device_count": 2,
            },
        }

    def get_vehicle(self, vehicle_id: str) -> Any:
        """Get vehicle by ID."""
        return self.vehicles.get(vehicle_id)

    def get_all_vehicles(self) -> list[Any]:
        """Get all vehicles."""
        return list(self.vehicles.values())

    async def create_vehicle(self, name: str, vehicle_id: str | None = None) -> Any:
        """Mock create vehicle."""
        if vehicle_id is None:
            vehicle_id = f"vehicle_{len(self.vehicles) + 1}"

        if vehicle_id not in self.vehicles:
            self.vehicles[vehicle_id] = {
                "name": name,
                "created_at": "2025-01-01T10:00:00Z",
                "device_count": 0,
            }
        return vehicle_id

    async def update_vehicle_name(self, vehicle_id: str, name: str) -> bool:
        """Mock update vehicle name."""
        if vehicle_id in self.vehicles:
            self.vehicles[vehicle_id]["name"] = name
            return True
        return False

    async def delete_vehicle(self, vehicle_id: str) -> bool:
        """Mock delete vehicle."""
        if vehicle_id in self.vehicles:
            del self.vehicles[vehicle_id]
            return True
        return False


class MockDeviceRegistry:
    """Mock device registry for testing."""

    def __init__(self) -> None:
        """Initialize mock device registry."""
        self.devices = {
            "AA:BB:CC:DD:EE:FF": {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "device_type": "BM6",
                "friendly_name": "Test Device 1",
                "vehicle_id": "vehicle_1",
                "status": "configured",
            },
            "BB:CC:DD:EE:FF:AA": {
                "mac_address": "BB:CC:DD:EE:FF:AA",
                "device_type": "BM2",
                "friendly_name": "Test Device 2",
                "vehicle_id": "vehicle_1",
                "status": "configured",
            },
        }

    def get_devices_by_vehicle(self, vehicle_id: str) -> list[Any]:
        """Get devices by vehicle ID."""
        return [
            device
            for device in self.devices.values()
            if device.get("vehicle_id") == vehicle_id
        ]


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
    mock_engine.vehicle_registry = MockVehicleRegistry()
    mock_engine.device_registry = MockDeviceRegistry()
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


class TestVehicleEndpoints:
    """Test cases for vehicle API endpoints."""

    def test_get_vehicles(self, client: Any) -> None:
        """Test GET /api/vehicles endpoint."""
        response = client.get("/api/vehicles")
        assert response.status_code == 200

        data = response.get_json()
        assert "data" in data
        assert "meta" in data
        assert "links" in data
        assert data["meta"]["total"] == 1
        assert len(data["data"]) == 1

        vehicle = data["data"][0]
        assert vehicle["type"] == "vehicles"
        assert vehicle["id"] == "vehicle_1"
        assert vehicle["attributes"]["name"] == "Test Vehicle"
        assert vehicle["attributes"]["device_count"] == 2

    def test_get_vehicle_found(self, client: Any) -> None:
        """Test GET /api/vehicles/{id} endpoint for existing vehicle."""
        response = client.get("/api/vehicles/vehicle_1")
        assert response.status_code == 200

        data = response.get_json()
        assert "data" in data

        vehicle = data["data"]
        assert vehicle["type"] == "vehicles"
        assert vehicle["id"] == "vehicle_1"
        assert vehicle["attributes"]["name"] == "Test Vehicle"

    def test_get_vehicle_not_found(self, client: Any) -> None:
        """Test GET /api/vehicles/{id} endpoint for non-existing vehicle."""
        response = client.get("/api/vehicles/nonexistent")
        assert response.status_code == 404

        data = response.get_json()
        assert "errors" in data
        assert data["errors"][0]["status"] == "404"

    def test_create_vehicle_success(self, client: Any) -> None:
        """Test POST /api/vehicles endpoint for vehicle creation."""
        request_data = {
            "data": {"type": "vehicles", "attributes": {"name": "New Test Vehicle"}},
        }

        response = client.post(
            "/api/vehicles",
            data=json.dumps(request_data),
            content_type="application/json",
        )
        assert response.status_code == 201

        data = response.get_json()
        assert "data" in data
        vehicle = data["data"]
        assert vehicle["attributes"]["name"] == "New Test Vehicle"
        assert vehicle["attributes"]["device_count"] == 0

    def test_create_vehicle_with_custom_id(self, client: Any) -> None:
        """Test POST /api/vehicles endpoint with custom ID."""
        request_data = {
            "data": {
                "type": "vehicles",
                "attributes": {"name": "Custom ID Vehicle", "id": "custom_vehicle_id"},
            },
        }

        response = client.post(
            "/api/vehicles",
            data=json.dumps(request_data),
            content_type="application/json",
        )
        assert response.status_code == 201

        data = response.get_json()
        assert "data" in data
        vehicle = data["data"]
        assert vehicle["id"] == "custom_vehicle_id"

    def test_create_vehicle_validation_error(self, client: Any) -> None:
        """Test POST /api/vehicles endpoint with validation errors."""
        # Missing required name field
        request_data = {"data": {"type": "vehicles", "attributes": {}}}

        response = client.post(
            "/api/vehicles",
            data=json.dumps(request_data),
            content_type="application/json",
        )
        assert response.status_code == 400

        data = response.get_json()
        assert "errors" in data

    def test_update_vehicle_success(self, client: Any) -> None:
        """Test PATCH /api/vehicles/{id} endpoint."""
        request_data = {
            "data": {
                "type": "vehicles",
                "id": "vehicle_1",
                "attributes": {"name": "Updated Vehicle Name"},
            },
        }

        response = client.patch(
            "/api/vehicles/vehicle_1",
            data=json.dumps(request_data),
            content_type="application/json",
        )
        assert response.status_code == 200

        data = response.get_json()
        assert "data" in data
        vehicle = data["data"]
        assert vehicle["attributes"]["name"] == "Updated Vehicle Name"

    def test_update_vehicle_not_found(self, client: Any) -> None:
        """Test PATCH /api/vehicles/{id} endpoint for non-existing vehicle."""
        request_data = {
            "data": {
                "type": "vehicles",
                "id": "nonexistent",
                "attributes": {"name": "Updated Name"},
            },
        }

        response = client.patch(
            "/api/vehicles/nonexistent",
            data=json.dumps(request_data),
            content_type="application/json",
        )
        assert response.status_code == 404

    def test_delete_vehicle_with_devices_fails(self, client: Any) -> None:
        """Test DELETE /api/vehicles/{id} endpoint fails when vehicle has devices."""
        response = client.delete("/api/vehicles/vehicle_1")
        assert response.status_code == 409  # Conflict - has associated devices

        data = response.get_json()
        assert "errors" in data
        assert "associated devices" in data["errors"][0]["detail"]

    def test_delete_vehicle_not_found(self, client: Any) -> None:
        """Test DELETE /api/vehicles/{id} endpoint for non-existing vehicle."""
        response = client.delete("/api/vehicles/nonexistent")
        assert response.status_code == 404

    def test_delete_vehicle_success(
        self,
        client: Any,
        mock_core_engine: MagicMock,
    ) -> None:
        """Test DELETE /api/vehicles/{id} endpoint succeeds when vehicle has no devices."""
        # Create a vehicle with no devices
        mock_core_engine.vehicle_registry.vehicles["empty_vehicle"] = {
            "name": "Empty Vehicle",
            "created_at": "2025-01-01T10:00:00Z",
            "device_count": 0,
        }

        # Mock get_devices_by_vehicle to return empty list for this vehicle
        original_method = mock_core_engine.device_registry.get_devices_by_vehicle

        def mock_get_devices_by_vehicle(vehicle_id: str) -> list[Any]:
            if vehicle_id == "empty_vehicle":
                return []
            return original_method(vehicle_id)

        mock_core_engine.device_registry.get_devices_by_vehicle = (
            mock_get_devices_by_vehicle
        )

        response = client.delete("/api/vehicles/empty_vehicle")
        assert response.status_code == 204

    def test_get_vehicle_devices(self, client: Any) -> None:
        """Test GET /api/vehicles/{id}/devices endpoint."""
        response = client.get("/api/vehicles/vehicle_1/devices")
        assert response.status_code == 200

        data = response.get_json()
        assert "data" in data
        assert "meta" in data
        assert data["meta"]["total"] == 2
        assert data["meta"]["vehicle_id"] == "vehicle_1"
        assert len(data["data"]) == 2

        # Check that devices are properly formatted
        device = data["data"][0]
        assert device["type"] == "devices"
        assert "mac_address" in device["attributes"]

    def test_get_vehicle_devices_not_found(self, client: Any) -> None:
        """Test GET /api/vehicles/{id}/devices endpoint for non-existing vehicle."""
        response = client.get("/api/vehicles/nonexistent/devices")
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__])
