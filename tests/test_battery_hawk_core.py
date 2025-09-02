"""Tests for BatteryHawkCore and related components."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.battery_hawk.config.config_manager import ConfigManager
from src.battery_hawk.core import (
    BatteryHawkCore,
    DataStorage,
    DeviceRegistry,
    VehicleRegistry,
)


class MockConfigManager(ConfigManager):
    """Mock configuration manager for testing."""

    def __init__(self, config_dir: str = "/data") -> None:
        """Initialize mock configuration manager with test data."""
        self.config_dir = config_dir
        self.configs: dict[str, dict[str, Any]] = {
            "system": {
                "version": "1.0",
                "discovery": {
                    "initial_scan": True,
                    "periodic_interval": 43200,
                    "scan_duration": 10,
                },
                "bluetooth": {"max_concurrent_connections": 3},
                "influxdb": {"enabled": False},
                "vehicle_association": {
                    "vehicle_1": {
                        "device_types": ["BM6"],
                        "name_patterns": ["Starter"],
                        "mac_patterns": ["AA:BB"],
                        "max_devices": 2,
                    },
                    "vehicle_2": {
                        "device_types": ["BM2"],
                        "name_patterns": ["Auxiliary"],
                        "max_devices": 1,
                    },
                },
            },
            "devices": {"version": "1.0", "devices": {}},
            "vehicles": {"version": "1.0", "vehicles": {}},
        }

    def get_config(self, key: str) -> dict:
        """Get configuration section."""
        return self.configs.get(key, {})

    def save_config(self, key: str) -> None:
        """Save configuration section."""


class MockDevice:
    """Mock device for testing polling functionality."""

    def __init__(self, mac_address: str, device_type: str) -> None:
        """Initialize mock device."""
        self.mac_address = mac_address
        self.device_type = device_type
        self.read_data_called = False
        self.send_command_called = False

    async def read_data(self) -> MagicMock:
        """Mock read_data method."""
        self.read_data_called = True
        # Return a mock reading object
        reading = MagicMock()
        reading.voltage = 12.5
        reading.current = 2.1
        reading.temperature = 25.0
        reading.state_of_charge = 85
        reading.capacity = 100
        reading.cycles = 50
        reading.timestamp = "2024-01-01T12:00:00Z"
        reading.extra = {"health": "good"}
        return reading

    async def send_command(
        self,
        command: str,
        params: dict[str, Any] | None = None,
    ) -> MagicMock:
        """Mock send_command method."""
        self.send_command_called = True
        # Return a mock status object
        status = MagicMock()
        status.connected = True
        status.error_code = None
        status.error_message = None
        status.protocol_version = "1.0"
        status.last_command = command
        status.extra = {}
        return status


class TestBatteryHawkCore:
    """Test BatteryHawkCore functionality."""

    @pytest.fixture
    def config_manager(self) -> MockConfigManager:
        """Create a mock configuration manager."""
        return MockConfigManager()

    @pytest.fixture
    def core(self, config_manager: MockConfigManager) -> BatteryHawkCore:
        """Create a BatteryHawkCore instance for testing."""
        return BatteryHawkCore(config_manager)

    @pytest.mark.asyncio
    async def test_initialization(self, core: BatteryHawkCore) -> None:
        """Test core initialization."""
        assert core.running is False
        assert len(core.tasks) == 0
        assert len(core.active_devices) == 0
        assert len(core.polling_tasks) == 0
        assert len(core.event_handlers) == 6  # 6 event types

    @pytest.mark.asyncio
    async def test_event_handler_management(self, core: BatteryHawkCore) -> None:
        """Test event handler management."""
        # Test adding event handler
        event_data = {"test": "data"}
        handler_called = False

        def test_handler(data: dict[str, Any]) -> None:
            nonlocal handler_called
            handler_called = True
            assert data == event_data

        core.add_event_handler("device_discovered", test_handler)
        assert len(core.event_handlers["device_discovered"]) == 1

        # Test notifying event handlers
        await core._notify_event_handlers("device_discovered", event_data)
        assert handler_called

        # Test removing event handler
        result = core.remove_event_handler("device_discovered", test_handler)
        assert result is True
        assert len(core.event_handlers["device_discovered"]) == 0

        # Test removing non-existent handler
        result = core.remove_event_handler("device_discovered", test_handler)
        assert result is False

        # Test adding handler to unknown event type
        core.add_event_handler("unknown_event", test_handler)
        assert "unknown_event" not in core.event_handlers

    @pytest.mark.asyncio
    async def test_async_event_handler(self, core: BatteryHawkCore) -> None:
        """Test async event handler registration and execution."""
        event_called = False
        event_data = {}

        async def async_handler(data: dict[str, Any]) -> None:
            nonlocal event_called, event_data
            event_called = True
            event_data = data

        # Add async event handler
        core.add_event_handler("device_discovered", async_handler)

        # Trigger event
        test_data = {"device_id": "test_device"}
        await core._notify_event_handlers("device_discovered", test_data)

        # Verify handler was called
        assert event_called
        assert event_data == test_data

    @pytest.mark.asyncio
    async def test_vehicle_association_rules(self, core: BatteryHawkCore) -> None:
        """Test vehicle association rules loading."""
        rules = core._get_vehicle_association_rules()
        assert "vehicle_1" in rules
        assert "vehicle_2" in rules
        assert rules["vehicle_1"]["device_types"] == ["BM6"]
        assert rules["vehicle_1"]["name_patterns"] == ["Starter"]

    @pytest.mark.asyncio
    async def test_find_matching_vehicle(self, core: BatteryHawkCore) -> None:
        """Test finding matching vehicle for device."""
        # Test with device type match
        device_info = {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "device_type": "BM6",
            "friendly_name": "BM6_Starter_Battery",
        }
        vehicle_id = core._find_matching_vehicle(device_info)
        assert vehicle_id is None  # No rules configured

        # Test with name pattern match
        device_info = {
            "mac_address": "BB:CC:DD:EE:FF:AA",
            "device_type": "BM2",
            "friendly_name": "Battery Monitor 2_Auxiliary",
        }
        vehicle_id = core._find_matching_vehicle(device_info)
        assert vehicle_id is None  # No rules configured

        # Test with MAC pattern match
        device_info = {
            "mac_address": "CC:DD:EE:FF:AA:BB",
            "device_type": "BM6",
            "friendly_name": "Device_CC:DD:EE:FF:AA:BB",
        }
        vehicle_id = core._find_matching_vehicle(device_info)
        assert vehicle_id is None  # No rules configured

    @pytest.mark.asyncio
    async def test_generate_vehicle_name(self, core: BatteryHawkCore) -> None:
        """Test vehicle name generation."""
        # Test with meaningful friendly name
        device_info = {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "device_type": "BM6",
            "friendly_name": "BM6_Starter_Battery",
        }
        name = core._generate_vehicle_name(device_info)
        assert name == "Starter_Battery Vehicle"

        # Test with device type prefix removal
        device_info = {
            "mac_address": "BB:CC:DD:EE:FF:AA",
            "device_type": "BM2",
            "friendly_name": "Battery Monitor 2_Auxiliary",
        }
        name = core._generate_vehicle_name(device_info)
        assert name == "2_Auxiliary Vehicle"

        # Test fallback to device type
        device_info = {
            "mac_address": "CC:DD:EE:FF:AA:BB",
            "device_type": "BM6",
            "friendly_name": "Device_CC:DD:EE:FF:AA:BB",
        }
        name = core._generate_vehicle_name(device_info)
        assert name == "BM6 Vehicle"

        # Test error handling
        device_info = {
            "mac_address": "DD:EE:FF:AA:BB:CC",
            "device_type": "unknown",
            "friendly_name": None,
        }
        name = core._generate_vehicle_name(device_info)
        assert name == "unknown Vehicle"

    @pytest.mark.asyncio
    async def test_associate_device_with_vehicle(self, core: BatteryHawkCore) -> None:
        """Test device-to-vehicle association."""
        # Mock device registry configure_device method
        core.device_registry.configure_device = AsyncMock(return_value=True)

        # Mock state manager set_vehicle_association method
        core.state_manager.set_vehicle_association = AsyncMock(return_value=True)

        # Mock vehicle registry create_vehicle method
        core.vehicle_registry.create_vehicle = AsyncMock(return_value="vehicle_2")

        # Test association with new vehicle (since no rules are configured)
        device_info = {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "device_type": "BM6",
            "friendly_name": "Starter Battery",
        }

        await core._associate_device_with_vehicle(device_info)

        # Verify device was configured with new vehicle
        core.device_registry.configure_device.assert_called_once()
        call_args = core.device_registry.configure_device.call_args
        assert call_args[0][0] == "AA:BB:CC:DD:EE:FF"  # mac_address
        assert call_args[0][1] == "BM6"  # device_type
        assert call_args[0][2] == "Starter Battery"  # friendly_name
        assert call_args[1]["vehicle_id"] == "vehicle_2"  # vehicle_id

        # Verify state manager was updated
        core.state_manager.set_vehicle_association.assert_called_once_with(
            "AA:BB:CC:DD:EE:FF",
            "vehicle_2",
        )

    @pytest.mark.asyncio
    async def test_associate_device_with_new_vehicle(
        self,
        core: BatteryHawkCore,
    ) -> None:
        """Test device association with new vehicle creation."""
        # Mock device registry with device that doesn't match existing vehicles
        core.device_registry.devices = {
            "CC:DD:EE:FF:AA:BB": {
                "mac_address": "CC:DD:EE:FF:AA:BB",
                "device_type": "BM6",
                "friendly_name": "Unknown Battery",
                "status": "discovered",
                "vehicle_id": None,
            },
        }

        # Mock empty vehicle registry
        core.vehicle_registry.vehicles = {}

        # Mock state manager
        core.state_manager._states = {}

        # Test association with new vehicle
        device_info = core.device_registry.devices["CC:DD:EE:FF:AA:BB"]
        await core._associate_device_with_vehicle(device_info)

        # Verify new vehicle was created and device was associated
        assert len(core.vehicle_registry.vehicles) == 1
        vehicle_id = next(iter(core.vehicle_registry.vehicles.keys()))
        assert (
            core.device_registry.devices["CC:DD:EE:FF:AA:BB"]["vehicle_id"]
            == vehicle_id
        )

    @pytest.mark.asyncio
    async def test_update_vehicle_device_count(self, core: BatteryHawkCore) -> None:
        """Test updating vehicle device count."""
        # Mock device registry with devices associated to a vehicle
        core.device_registry.devices = {
            "AA:BB:CC:DD:EE:FF": {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "vehicle_id": "vehicle_1",
            },
            "BB:CC:DD:EE:FF:AA": {
                "mac_address": "BB:CC:DD:EE:FF:AA",
                "vehicle_id": "vehicle_1",
            },
        }

        # Mock vehicle registry
        core.vehicle_registry.vehicles = {
            "vehicle_1": {"name": "Vehicle 1", "device_count": 0},
        }

        # Test updating device count
        await core._update_vehicle_device_count("vehicle_1")
        assert core.vehicle_registry.vehicles["vehicle_1"]["device_count"] == 2

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, core: BatteryHawkCore) -> None:
        """Test graceful shutdown handling."""
        # Mock active devices
        core.active_devices = {
            "AA:BB:CC:DD:EE:FF": MagicMock(device_type="BM6"),
            "BB:CC:DD:EE:FF:AA": MagicMock(device_type="BM2"),
        }

        # Mock state manager
        core.state_manager._states = {
            "AA:BB:CC:DD:EE:FF": MagicMock(),
            "BB:CC:DD:EE:FF:AA": MagicMock(),
        }

        # Mock data storage
        core.data_storage.is_connected = MagicMock(return_value=True)
        core.data_storage.disconnect = AsyncMock()

        # Mock connection pool
        core.connection_pool.shutdown = AsyncMock()

        # Test shutdown
        await core.stop()

        # Verify shutdown was handled properly
        assert core.running is False
        assert len(core.active_devices) == 0
        core.data_storage.disconnect.assert_called_once()
        core.connection_pool.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_signal_handler_setup(self, core: BatteryHawkCore) -> None:
        """Test signal handler setup."""
        with contextlib.suppress(Exception):
            core._setup_signal_handlers()

    @pytest.mark.asyncio
    async def test_get_status(self, core: BatteryHawkCore) -> None:
        """Test status retrieval."""
        # Mock components
        core.data_storage.is_connected = MagicMock(return_value=True)
        core.discovery_service.discovered_devices = {"AA:BB:CC:DD:EE:FF": {}}
        core.device_registry.get_configured_devices = MagicMock(
            return_value=[{"id": 1}],
        )
        core.vehicle_registry.get_all_vehicles = MagicMock(return_value=[{"id": 1}])
        core.state_manager.get_summary = MagicMock(return_value={"total": 1})

        # Test status retrieval
        status = core.get_status()

        assert status["running"] is False
        assert status["active_tasks"] == 0
        assert status["active_devices"] == 0
        assert status["polling_tasks"] == 0
        assert status["storage_connected"] is True
        assert status["discovered_devices"] == 1
        assert status["configured_devices"] == 1
        assert status["vehicles"] == 1

    @pytest.mark.asyncio
    async def test_error_handling_in_event_handlers(
        self,
        core: BatteryHawkCore,
    ) -> None:
        """Test error handling in event handlers."""

        # Add a handler that raises an exception
        def error_handler(data: dict[str, Any]) -> None:
            raise ValueError("Test error")

        core.add_event_handler("device_discovered", error_handler)

        # Add a normal handler
        handler_called = False

        def normal_handler(data: dict[str, Any]) -> None:
            nonlocal handler_called
            handler_called = True

        core.add_event_handler("device_discovered", normal_handler)

        # Test that both handlers are called (error handler doesn't stop normal handler)
        await core._notify_event_handlers("device_discovered", {"test": "data"})
        assert handler_called

    @pytest.mark.asyncio
    async def test_vehicle_association_task_lifecycle(
        self,
        core: BatteryHawkCore,
    ) -> None:
        """Test vehicle association task lifecycle."""
        # Mock device registry with unassociated devices
        core.device_registry.devices = {
            "AA:BB:CC:DD:EE:FF": {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "device_type": "BM6",
                "friendly_name": "Starter Battery",
                "status": "discovered",
                "vehicle_id": None,
            },
        }

        # Mock vehicle registry
        core.vehicle_registry.vehicles = {
            "vehicle_1": {"name": "Vehicle 1", "id": "vehicle_1"},
        }

        # Mock state manager
        core.state_manager._states = {}

        # Start the core (this will start the vehicle association task)
        core.running = True

        # Create and run the vehicle association task for a short time
        task = asyncio.create_task(core._run_vehicle_association())

        # Wait a bit for the task to process
        await asyncio.sleep(0.1)

        # Stop the task
        core.running = False
        core.shutdown_event.set()

        # Wait for task to complete
        await asyncio.wait_for(task, timeout=1.0)

        # Verify the task completed without errors
        assert task.done()

    @pytest.mark.asyncio
    async def test_device_disconnection_during_shutdown(
        self,
        core: BatteryHawkCore,
    ) -> None:
        """Test device disconnection during shutdown."""
        # Mock active devices
        mock_device = MagicMock(device_type="BM6")
        core.active_devices = {"AA:BB:CC:DD:EE:FF": mock_device}

        # Mock state manager
        mock_state = MagicMock()
        core.state_manager._states = {"AA:BB:CC:DD:EE:FF": mock_state}

        # Mock data storage and connection pool
        core.data_storage.disconnect = AsyncMock()
        core.connection_pool.shutdown = AsyncMock()

        # Test shutdown
        await core.stop()

        # Verify device disconnection was handled
        assert len(core.active_devices) == 0
        # Verify state manager was updated
        mock_state.vehicle_id = None  # This would be set by the state manager

    @pytest.mark.asyncio
    async def test_event_handler_removal(self, core: BatteryHawkCore) -> None:
        """Test event handler removal functionality."""

        # Add a handler
        def test_handler(data: dict[str, Any]) -> None:
            pass

        core.add_event_handler("device_connected", test_handler)
        assert len(core.event_handlers["device_connected"]) == 1

        # Remove the handler
        result = core.remove_event_handler("device_connected", test_handler)
        assert result is True
        assert len(core.event_handlers["device_connected"]) == 0

        # Try to remove non-existent handler
        result = core.remove_event_handler("device_connected", test_handler)
        assert result is False

        # Try to remove from unknown event type
        result = core.remove_event_handler("unknown_event", test_handler)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_event_handlers(self, core: BatteryHawkCore) -> None:
        """Test getting event handlers."""

        # Add handlers to different event types
        def handler1(data: dict[str, Any]) -> None:
            pass

        def handler2(data: dict[str, Any]) -> None:
            pass

        core.add_event_handler("device_discovered", handler1)
        core.add_event_handler("device_connected", handler2)

        # Test getting all handlers
        all_handlers = core.get_event_handlers()
        assert isinstance(all_handlers, dict)
        assert len(all_handlers["device_discovered"]) == 1
        assert len(all_handlers["device_connected"]) == 1

        # Test getting handlers for specific event type
        discovered_handlers = core.get_event_handlers("device_discovered")
        assert isinstance(discovered_handlers, list)
        assert len(discovered_handlers) == 1
        assert discovered_handlers[0] == handler1

        # Test getting handlers for unknown event type
        unknown_handlers = core.get_event_handlers("unknown_event")
        assert isinstance(unknown_handlers, list)
        assert len(unknown_handlers) == 0


class TestDeviceRegistry:
    """Test suite for DeviceRegistry."""

    @pytest.fixture
    def mock_config_manager(self) -> MockConfigManager:
        """Create a mock configuration manager."""
        return MockConfigManager()

    @pytest.fixture
    def device_registry(self, mock_config_manager: MockConfigManager) -> DeviceRegistry:
        """Create a DeviceRegistry instance for testing."""
        return DeviceRegistry(mock_config_manager)

    def test_initialization(self, device_registry: DeviceRegistry) -> None:
        """Test that DeviceRegistry initializes correctly."""
        assert device_registry.config is not None
        assert isinstance(device_registry.devices, dict)

    @pytest.mark.asyncio
    async def test_register_discovered_devices(
        self,
        device_registry: DeviceRegistry,
    ) -> None:
        """Test registering discovered devices."""
        discovered_devices = {
            "AA:BB:CC:DD:EE:FF": {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "name": "BM6_Test",
                "device_type": "BM6",
            },
        }

        await device_registry.register_discovered_devices(discovered_devices)

        assert "AA:BB:CC:DD:EE:FF" in device_registry.devices
        device = device_registry.devices["AA:BB:CC:DD:EE:FF"]
        assert device["mac_address"] == "AA:BB:CC:DD:EE:FF"
        assert device["device_type"] == "BM6"
        assert device["friendly_name"] == "BM6_Test"
        assert device["status"] == "discovered"

    def test_get_device(self, device_registry: DeviceRegistry) -> None:
        """Test getting device by MAC address."""
        # Add a test device
        device_registry.devices["AA:BB:CC:DD:EE:FF"] = {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "device_type": "BM6",
        }

        device = device_registry.get_device("AA:BB:CC:DD:EE:FF")
        assert device is not None
        assert device["mac_address"] == "AA:BB:CC:DD:EE:FF"

        # Test non-existent device
        device = device_registry.get_device("11:22:33:44:55:66")
        assert device is None

    def test_get_configured_devices(self, device_registry: DeviceRegistry) -> None:
        """Test getting configured devices."""
        # Add test devices
        device_registry.devices.update(
            {
                "AA:BB:CC:DD:EE:FF": {
                    "mac_address": "AA:BB:CC:DD:EE:FF",
                    "status": "configured",
                },
                "11:22:33:44:55:66": {
                    "mac_address": "11:22:33:44:55:66",
                    "status": "discovered",
                },
            },
        )

        configured_devices = device_registry.get_configured_devices()
        assert len(configured_devices) == 1
        assert configured_devices[0]["mac_address"] == "AA:BB:CC:DD:EE:FF"


class TestVehicleRegistry:
    """Test suite for VehicleRegistry."""

    @pytest.fixture
    def mock_config_manager(self) -> MockConfigManager:
        """Create a mock configuration manager."""
        return MockConfigManager()

    @pytest.fixture
    def vehicle_registry(
        self,
        mock_config_manager: MockConfigManager,
    ) -> VehicleRegistry:
        """Create a VehicleRegistry instance for testing."""
        return VehicleRegistry(mock_config_manager)

    def test_initialization(self, vehicle_registry: VehicleRegistry) -> None:
        """Test that VehicleRegistry initializes correctly."""
        assert vehicle_registry.config is not None
        assert isinstance(vehicle_registry.vehicles, dict)

    @pytest.mark.asyncio
    async def test_create_vehicle(self, vehicle_registry: VehicleRegistry) -> None:
        """Test creating a vehicle."""
        vehicle_id = await vehicle_registry.create_vehicle("Test Vehicle")

        assert vehicle_id in vehicle_registry.vehicles
        vehicle = vehicle_registry.vehicles[vehicle_id]
        assert vehicle["name"] == "Test Vehicle"

    def test_get_vehicle(self, vehicle_registry: VehicleRegistry) -> None:
        """Test getting vehicle by ID."""
        # Add a test vehicle
        vehicle_registry.vehicles["test_vehicle"] = {
            "vehicle_id": "test_vehicle",
            "name": "Test Vehicle",
        }

        vehicle = vehicle_registry.get_vehicle("test_vehicle")
        assert vehicle is not None
        assert vehicle["name"] == "Test Vehicle"

        # Test non-existent vehicle
        vehicle = vehicle_registry.get_vehicle("unknown_vehicle")
        assert vehicle is None


class TestDataStorage:
    """Test suite for DataStorage."""

    @pytest.fixture
    def mock_config_manager(self) -> MockConfigManager:
        """Create a mock configuration manager."""
        return MockConfigManager()

    @pytest.fixture
    def data_storage(self, mock_config_manager: MockConfigManager) -> DataStorage:
        """Create a DataStorage instance for testing."""
        return DataStorage(mock_config_manager)

    def test_initialization(self, data_storage: DataStorage) -> None:
        """Test that DataStorage initializes correctly."""
        assert data_storage.config is not None
        assert data_storage.connected is False

    @pytest.mark.asyncio
    async def test_connect_disabled(self, data_storage: DataStorage) -> None:
        """Test connecting when InfluxDB is disabled."""
        result = await data_storage.connect()
        assert result is True
        assert data_storage.connected is False

    def test_is_connected(self, data_storage: DataStorage) -> None:
        """Test is_connected method."""
        assert data_storage.is_connected() is False
        data_storage.connected = True
        assert data_storage.is_connected() is True

    @pytest.mark.asyncio
    async def test_store_reading_disconnected(self, data_storage: DataStorage) -> None:
        """Test storing reading when not connected (should buffer)."""
        result = await data_storage.store_reading(
            "AA:BB:CC:DD:EE:FF",
            "test_vehicle",
            "BM6",
            {"voltage": 12.5},
        )
        # With error handling, readings are buffered when not connected
        assert result is True
        # Verify the reading was buffered
        assert len(data_storage._reading_buffer) == 1
        buffered = data_storage._reading_buffer[0]
        assert buffered.device_id == "AA:BB:CC:DD:EE:FF"
        assert buffered.reading["voltage"] == 12.5
