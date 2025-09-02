"""
Tests for storage backend abstraction and implementations.

This module tests the abstract base class, factory, and concrete implementations
of storage backends for Battery Hawk.
"""

from __future__ import annotations

import shutil
import tempfile
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

from battery_hawk.config.config_manager import ConfigManager
from battery_hawk.core.storage import InfluxDBStorageBackend, StorageBackendFactory
from battery_hawk.core.storage_backends import (
    BaseStorageBackend,
    StorageHealth,
    StorageMetrics,
)
from battery_hawk.core.storage_backends_examples import (
    JSONFileStorageBackend,
    NullStorageBackend,
)


class MockConfigManager(ConfigManager):
    """Mock configuration manager for testing."""

    def __init__(self, backend_config: dict | None = None) -> None:
        """Initialize mock configuration manager."""
        self.config_dir = "/data"
        self.configs = {
            "system": {
                "version": "1.0",
                "influxdb": backend_config
                or {
                    "enabled": True,
                    "host": "localhost",
                    "port": 8086,
                    "database": "test_battery_hawk",
                    "username": "test_user",
                    "password": "test_pass",
                    "timeout": 5000,
                    "retries": 2,
                },
                "json_storage": {
                    "path": tempfile.gettempdir() + "/test_battery_hawk_storage",
                },
            },
            "devices": {
                "version": "1.0",
                "devices": {
                    "AA:BB:CC:DD:EE:FF": {
                        "name": "Test Device",
                        "type": "BM6",
                    },
                },
            },
            "vehicles": {
                "version": "1.0",
                "vehicles": {
                    "vehicle_1": {
                        "name": "Test Vehicle",
                    },
                },
            },
        }

    def get_config(self, key: str) -> dict:
        """Get configuration section."""
        return self.configs.get(key, {})


class TestStorageBackend(BaseStorageBackend):
    """Test implementation of BaseStorageBackend for testing."""

    @property
    def backend_name(self) -> str:
        """Return backend name."""
        return "Test"

    @property
    def backend_version(self) -> str:
        """Return backend version."""
        return "1.0.0"

    @property
    def capabilities(self) -> set[str]:
        """Return backend capabilities."""
        return {"test_capability"}

    async def connect(self) -> bool:
        """Connect to storage."""
        self.connected = True
        return True

    async def disconnect(self) -> None:
        """Disconnect from storage."""
        self.connected = False

    async def store_reading(
        self,
        device_id: str,
        vehicle_id: str,
        device_type: str,
        reading: dict,
    ) -> bool:
        """Store a reading."""
        return True

    async def get_recent_readings(self, device_id: str, limit: int = 100) -> list[dict]:
        """Get recent readings."""
        return []

    async def get_vehicle_summary(self, vehicle_id: str, hours: int = 24) -> dict:
        """Get vehicle summary."""
        return {}

    async def health_check(self) -> bool:
        """Check health."""
        return True


@pytest.fixture
def mock_config_manager() -> MockConfigManager:
    """Fixture for mock configuration manager."""
    return MockConfigManager()


@pytest.fixture
def temp_storage_dir() -> Generator[str]:
    """Fixture for temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
class TestBaseStorageBackend:
    """Test cases for BaseStorageBackend abstract class."""

    async def test_initialization(self, mock_config_manager: MockConfigManager) -> None:
        """Test BaseStorageBackend initialization."""
        backend = TestStorageBackend(mock_config_manager)

        assert backend.config == mock_config_manager
        assert backend.backend_name == "Test"
        assert backend.backend_version == "1.0.0"
        assert backend.capabilities == {"test_capability"}
        assert not backend.connected
        assert isinstance(backend.metrics, StorageMetrics)

    async def test_connection_lifecycle(
        self,
        mock_config_manager: MockConfigManager,
    ) -> None:
        """Test connection and disconnection."""
        backend = TestStorageBackend(mock_config_manager)

        # Test connection
        result = await backend.connect()
        assert result is True
        assert backend.is_connected() is True

        # Test disconnection
        await backend.disconnect()
        assert backend.is_connected() is False

    async def test_capabilities(self, mock_config_manager: MockConfigManager) -> None:
        """Test capability checking."""
        backend = TestStorageBackend(mock_config_manager)

        assert backend.has_capability("test_capability") is True
        assert backend.has_capability("nonexistent_capability") is False

    async def test_health_status(self, mock_config_manager: MockConfigManager) -> None:
        """Test health status reporting."""
        backend = TestStorageBackend(mock_config_manager)
        await backend.connect()

        health = backend.get_health_status()
        assert isinstance(health, StorageHealth)
        assert health.connected is True
        assert health.backend_name == "Test"
        assert health.backend_version == "1.0.0"

    async def test_storage_info(self, mock_config_manager: MockConfigManager) -> None:
        """Test storage information reporting."""
        backend = TestStorageBackend(mock_config_manager)
        await backend.connect()

        info = await backend.get_storage_info()
        assert info["backend_name"] == "Test"
        assert info["backend_version"] == "1.0.0"
        assert info["capabilities"] == ["test_capability"]
        assert info["connected"] is True
        assert "health" in info
        assert "metrics" in info


@pytest.mark.asyncio
class TestStorageBackendFactory:
    """Test cases for StorageBackendFactory."""

    def test_get_available_backends(self) -> None:
        """Test getting available backend types."""
        backends = StorageBackendFactory.get_available_backends()
        assert "influxdb" in backends
        assert "json" in backends
        assert "null" in backends

    def test_create_influxdb_backend(
        self,
        mock_config_manager: MockConfigManager,
    ) -> None:
        """Test creating InfluxDB backend."""
        backend = StorageBackendFactory.create_backend("influxdb", mock_config_manager)
        assert isinstance(backend, InfluxDBStorageBackend)
        assert backend.backend_name == "InfluxDB"

    def test_create_json_backend(self, mock_config_manager: MockConfigManager) -> None:
        """Test creating JSON file backend."""
        backend = StorageBackendFactory.create_backend("json", mock_config_manager)
        assert isinstance(backend, JSONFileStorageBackend)
        assert backend.backend_name == "JSONFile"

    def test_create_null_backend(self, mock_config_manager: MockConfigManager) -> None:
        """Test creating null backend."""
        backend = StorageBackendFactory.create_backend("null", mock_config_manager)
        assert isinstance(backend, NullStorageBackend)
        assert backend.backend_name == "Null"

    def test_create_invalid_backend(
        self,
        mock_config_manager: MockConfigManager,
    ) -> None:
        """Test creating invalid backend type."""
        with pytest.raises(ValueError, match="Unsupported backend type"):
            StorageBackendFactory.create_backend("invalid", mock_config_manager)

    def test_register_custom_backend(
        self,
        mock_config_manager: MockConfigManager,
    ) -> None:
        """Test registering custom backend."""
        StorageBackendFactory.register_backend("test", TestStorageBackend)

        backend = StorageBackendFactory.create_backend("test", mock_config_manager)
        assert isinstance(backend, TestStorageBackend)

    def test_register_invalid_backend(self) -> None:
        """Test registering invalid backend class."""

        class InvalidBackend:
            pass

        with pytest.raises(TypeError, match="must inherit from BaseStorageBackend"):
            StorageBackendFactory.register_backend("invalid", InvalidBackend)


@pytest.mark.asyncio
class TestJSONFileStorageBackend:
    """Test cases for JSONFileStorageBackend."""

    async def test_initialization(
        self,
        mock_config_manager: MockConfigManager,
        temp_storage_dir: str,
    ) -> None:
        """Test JSON file backend initialization."""
        # Update config to use temp directory
        mock_config_manager.configs["system"]["json_storage"]["path"] = temp_storage_dir

        backend = JSONFileStorageBackend(mock_config_manager)
        assert backend.backend_name == "JSONFile"
        assert backend.capabilities == {"time_series", "backup"}

    async def test_connection(
        self,
        mock_config_manager: MockConfigManager,
        temp_storage_dir: str,
    ) -> None:
        """Test JSON file backend connection."""
        mock_config_manager.configs["system"]["json_storage"]["path"] = temp_storage_dir

        backend = JSONFileStorageBackend(mock_config_manager)
        result = await backend.connect()

        assert result is True
        assert backend.is_connected() is True

    async def test_store_and_retrieve_readings(
        self,
        mock_config_manager: MockConfigManager,
        temp_storage_dir: str,
    ) -> None:
        """Test storing and retrieving readings."""
        mock_config_manager.configs["system"]["json_storage"]["path"] = temp_storage_dir

        backend = JSONFileStorageBackend(mock_config_manager)
        await backend.connect()

        # Store a reading
        reading = {"voltage": 12.5, "current": 2.3, "temperature": 25.0}
        result = await backend.store_reading(
            "AA:BB:CC:DD:EE:FF",
            "vehicle_1",
            "BM6",
            reading,
        )
        assert result is True

        # Retrieve readings
        readings = await backend.get_recent_readings("AA:BB:CC:DD:EE:FF", limit=10)
        assert len(readings) == 1
        assert readings[0]["voltage"] == 12.5
        assert readings[0]["device_id"] == "AA:BB:CC:DD:EE:FF"

    async def test_vehicle_summary(
        self,
        mock_config_manager: MockConfigManager,
        temp_storage_dir: str,
    ) -> None:
        """Test vehicle summary calculation."""
        mock_config_manager.configs["system"]["json_storage"]["path"] = temp_storage_dir

        backend = JSONFileStorageBackend(mock_config_manager)
        await backend.connect()

        # Store multiple readings
        readings = [
            {"voltage": 12.5, "current": 2.3, "temperature": 25.0},
            {"voltage": 12.4, "current": 2.1, "temperature": 24.0},
        ]

        for reading in readings:
            await backend.store_reading(
                "AA:BB:CC:DD:EE:FF",
                "vehicle_1",
                "BM6",
                reading,
            )

        # Get summary
        summary = await backend.get_vehicle_summary("vehicle_1", hours=24)
        assert summary["vehicle_id"] == "vehicle_1"
        assert summary["reading_count"] == 2
        assert summary["avg_voltage"] == 12.45  # (12.5 + 12.4) / 2

    async def test_health_check(
        self,
        mock_config_manager: MockConfigManager,
        temp_storage_dir: str,
    ) -> None:
        """Test health check."""
        mock_config_manager.configs["system"]["json_storage"]["path"] = temp_storage_dir

        backend = JSONFileStorageBackend(mock_config_manager)
        await backend.connect()

        result = await backend.health_check()
        assert result is True


@pytest.mark.asyncio
class TestNullStorageBackend:
    """Test cases for NullStorageBackend."""

    async def test_null_backend_operations(
        self,
        mock_config_manager: MockConfigManager,
    ) -> None:
        """Test null backend operations."""
        backend = NullStorageBackend(mock_config_manager)

        # Test connection
        result = await backend.connect()
        assert result is True
        assert backend.is_connected() is True

        # Test storing (should succeed but discard data)
        result = await backend.store_reading(
            "device",
            "vehicle",
            "BM6",
            {"voltage": 12.5},
        )
        assert result is True

        # Test retrieving (should return empty)
        readings = await backend.get_recent_readings("device")
        assert readings == []

        # Test summary (should return empty summary)
        summary = await backend.get_vehicle_summary("vehicle")
        assert summary["reading_count"] == 0

        # Test health check
        result = await backend.health_check()
        assert result is True
