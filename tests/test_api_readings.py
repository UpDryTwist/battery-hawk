"""Tests for Battery Hawk API readings endpoints."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from src.battery_hawk.api import BatteryHawkAPI
from src.battery_hawk.config.config_manager import ConfigManager
from src.battery_hawk.core.engine import BatteryHawkCore
from src.battery_hawk.core.state import DeviceState
from src.battery_hawk_driver.base.protocol import BatteryInfo


class MockDataStorage:
    """Mock data storage for testing."""

    def __init__(self) -> None:
        """Initialize mock data storage."""
        self.readings = [
            {
                "time": "2025-01-01T12:00:00Z",
                "voltage": 12.5,
                "current": 2.1,
                "temperature": 25.0,
                "state_of_charge": 85.0,
                "power": 26.25,
                "device_type": "BM6",
                "vehicle_id": "vehicle_1",
            },
            {
                "time": "2025-01-01T11:00:00Z",
                "voltage": 12.3,
                "current": 1.8,
                "temperature": 24.5,
                "state_of_charge": 82.0,
                "power": 22.14,
                "device_type": "BM6",
                "vehicle_id": "vehicle_1",
            },
        ]

    async def get_recent_readings(self, device_id: str, limit: int = 100) -> list[Any]:
        """Mock get recent readings."""
        return self.readings[:limit]

    def is_connected(self) -> bool:
        """Mock is connected."""
        return True


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
            },
        }

    def get_device(self, mac_address: str) -> Any:
        """Get device by MAC address."""
        return self.devices.get(mac_address)


class MockStateManager:
    """Mock state manager for testing."""

    def __init__(self) -> None:
        """Initialize mock state manager."""
        # Create a mock device state with latest reading
        self.device_state = DeviceState(
            mac_address="AA:BB:CC:DD:EE:FF",
            device_type="BM6",
            friendly_name="Test Device",
        )

        # Set up latest reading
        battery_info = BatteryInfo(
            voltage=12.5,
            current=2.1,
            temperature=25.0,
            state_of_charge=85.0,
        )
        self.device_state.update_reading(battery_info)

    def get_device_state(self, mac_address: str) -> Any:
        """Get device state by MAC address."""
        if mac_address == "AA:BB:CC:DD:EE:FF":
            return self.device_state
        return None


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
    mock_engine.data_storage = MockDataStorage()
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


class TestReadingsEndpoints:
    """Test cases for readings API endpoints."""

    def test_get_device_readings(self, client: Any) -> None:
        """Test GET /api/readings/{mac} endpoint."""
        response = client.get("/api/readings/AA:BB:CC:DD:EE:FF")
        assert response.status_code == 200

        data = response.get_json()
        assert "data" in data
        assert "meta" in data
        assert "links" in data
        assert data["meta"]["total"] == 2
        assert len(data["data"]) == 2

        reading = data["data"][0]
        assert reading["type"] == "readings"
        assert reading["attributes"]["device_id"] == "AA:BB:CC:DD:EE:FF"
        assert reading["attributes"]["voltage"] == 12.5
        assert reading["attributes"]["current"] == 2.1

    def test_get_device_readings_with_pagination(self, client: Any) -> None:
        """Test GET /api/readings/{mac} endpoint with pagination."""
        response = client.get("/api/readings/AA:BB:CC:DD:EE:FF?limit=1&offset=0")
        assert response.status_code == 200

        data = response.get_json()
        assert data["meta"]["limit"] == 1
        assert data["meta"]["offset"] == 0
        assert len(data["data"]) == 1
        # Should have next link since we have 2 readings total and limit is 1
        assert "next" in data["links"]

    def test_get_device_readings_invalid_params(self, client: Any) -> None:
        """Test GET /api/readings/{mac} endpoint with invalid parameters."""
        response = client.get("/api/readings/AA:BB:CC:DD:EE:FF?limit=invalid")
        assert response.status_code == 400

        data = response.get_json()
        assert "errors" in data

    def test_get_device_readings_not_found(self, client: Any) -> None:
        """Test GET /api/readings/{mac} endpoint for non-existing device."""
        response = client.get("/api/readings/XX:XX:XX:XX:XX:XX")
        assert response.status_code == 404

        data = response.get_json()
        assert "errors" in data
        assert data["errors"][0]["status"] == "404"

    def test_get_latest_reading(self, client: Any) -> None:
        """Test GET /api/readings/{mac}/latest endpoint."""
        response = client.get("/api/readings/AA:BB:CC:DD:EE:FF/latest")
        assert response.status_code == 200

        data = response.get_json()
        assert "data" in data

        reading = data["data"]
        assert reading["type"] == "readings"
        assert reading["attributes"]["device_id"] == "AA:BB:CC:DD:EE:FF"
        assert reading["attributes"]["voltage"] == 12.5

    def test_get_latest_reading_not_found(self, client: Any) -> None:
        """Test GET /api/readings/{mac}/latest endpoint for non-existing device."""
        response = client.get("/api/readings/XX:XX:XX:XX:XX:XX/latest")
        assert response.status_code == 404

    def test_get_latest_reading_no_data(
        self,
        client: Any,
        mock_core_engine: MagicMock,
    ) -> None:
        """Test GET /api/readings/{mac}/latest endpoint when no readings available."""
        # Mock state manager to return device state with no readings
        mock_state = MagicMock()
        mock_state.latest_reading = None
        mock_core_engine.state_manager.get_device_state = MagicMock(
            return_value=mock_state,
        )

        response = client.get("/api/readings/AA:BB:CC:DD:EE:FF/latest")
        assert response.status_code == 404

    def test_readings_sorting(self, client: Any) -> None:
        """Test readings sorting functionality."""
        # Test ascending timestamp sort
        response = client.get("/api/readings/AA:BB:CC:DD:EE:FF?sort=timestamp")
        assert response.status_code == 200

        data = response.get_json()
        # Should be sorted in ascending order (oldest first)
        timestamps = [reading["attributes"]["timestamp"] for reading in data["data"]]
        assert timestamps == sorted(timestamps)

    def test_readings_invalid_sort(self, client: Any) -> None:
        """Test readings with invalid sort parameter."""
        response = client.get("/api/readings/AA:BB:CC:DD:EE:FF?sort=invalid")
        assert response.status_code == 400

        data = response.get_json()
        assert "errors" in data
        assert "Invalid sort parameter" in data["errors"][0]["detail"]

    def test_readings_limit_validation(self, client: Any) -> None:
        """Test readings limit parameter validation."""
        # Test limit too high
        response = client.get("/api/readings/AA:BB:CC:DD:EE:FF?limit=2000")
        assert response.status_code == 400

        # Test negative limit
        response = client.get("/api/readings/AA:BB:CC:DD:EE:FF?limit=-1")
        assert response.status_code == 400

    def test_readings_offset_validation(self, client: Any) -> None:
        """Test readings offset parameter validation."""
        # Test negative offset
        response = client.get("/api/readings/AA:BB:CC:DD:EE:FF?offset=-1")
        assert response.status_code == 400

        data = response.get_json()
        assert "errors" in data


if __name__ == "__main__":
    pytest.main([__file__])
