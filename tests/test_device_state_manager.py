"""
Tests for DeviceStateManager.

This module contains comprehensive tests for the DeviceStateManager class,
including state updates, thread safety, and observer notifications.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from src.battery_hawk.core.state import DeviceState, DeviceStateManager
from src.battery_hawk_driver.base.protocol import BatteryInfo, DeviceStatus


class TestDeviceState:
    """Test cases for DeviceState class."""

    def test_device_state_initialization(self) -> None:
        """Test DeviceState initialization."""
        state = DeviceState("AA:BB:CC:DD:EE:FF", "BM6", "Test Device")

        assert state.mac_address == "AA:BB:CC:DD:EE:FF"
        assert state.device_type == "BM6"
        assert state.friendly_name == "Test Device"
        assert not state.connected
        assert state.connection_error_count == 0
        assert state.reading_count == 0
        assert not state.polling_active
        assert state.polling_error_count == 0
        assert state.vehicle_id is None

    def test_update_reading(self) -> None:
        """Test updating device reading."""
        state = DeviceState("AA:BB:CC:DD:EE:FF", "BM6", "Test Device")

        # Set initial error counts
        state.connection_error_count = 5
        state.polling_error_count = 3
        state.last_connection_error = "Test error"
        state.last_polling_error = "Test polling error"

        reading = BatteryInfo(
            voltage=12.6,
            current=1.2,
            temperature=25.0,
            state_of_charge=90.0,
            capacity=100.0,
            cycles=10,
            timestamp=1234567890.0,
        )

        state.update_reading(reading)

        assert state.latest_reading == reading
        assert state.reading_count == 1
        assert state.connection_error_count == 0  # Reset on successful reading
        assert state.polling_error_count == 0  # Reset on successful reading
        assert state.last_connection_error is None
        assert state.last_polling_error is None

    def test_update_status(self) -> None:
        """Test updating device status."""
        state = DeviceState("AA:BB:CC:DD:EE:FF", "BM6", "Test Device")

        status = DeviceStatus(
            connected=True,
            error_code=None,
            error_message=None,
            protocol_version="1.0",
            last_command="status",
        )

        state.update_status(status)

        assert state.device_status == status
        assert state.connected is True

    def test_update_connection_state(self) -> None:
        """Test updating connection state."""
        state = DeviceState("AA:BB:CC:DD:EE:FF", "BM6", "Test Device")

        # Test successful connection
        state.update_connection_state(True)
        assert state.connected is True
        assert state.connection_error_count == 0
        assert state.last_connection_error is None

        # Test failed connection
        state.update_connection_state(False, "Connection timeout")
        assert state.connected is False
        assert state.connection_error_count == 1
        assert state.last_connection_error == "Connection timeout"

    def test_update_polling_state(self) -> None:
        """Test updating polling state."""
        state = DeviceState("AA:BB:CC:DD:EE:FF", "BM6", "Test Device")

        # Test active polling
        state.update_polling_state(True)
        assert state.polling_active is True
        assert state.polling_error_count == 0
        assert state.last_polling_error is None

        # Test polling with error
        state.update_polling_state(False, "Read timeout")
        assert state.polling_active is False
        assert state.polling_error_count == 1
        assert state.last_polling_error == "Read timeout"

    def test_to_dict(self) -> None:
        """Test converting device state to dictionary."""
        state = DeviceState("AA:BB:CC:DD:EE:FF", "BM6", "Test Device")

        reading = BatteryInfo(
            voltage=12.6,
            current=1.2,
            temperature=25.0,
            state_of_charge=90.0,
            capacity=100.0,
            cycles=10,
            timestamp=1234567890.0,
        )
        state.update_reading(reading)

        status = DeviceStatus(
            connected=True,
            protocol_version="1.0",
            last_command="status",
        )
        state.update_status(status)

        state_dict = state.to_dict()

        assert state_dict["mac_address"] == "AA:BB:CC:DD:EE:FF"
        assert state_dict["device_type"] == "BM6"
        assert state_dict["friendly_name"] == "Test Device"
        assert state_dict["connected"] is True
        assert state_dict["latest_reading"]["voltage"] == 12.6
        assert state_dict["latest_reading"]["current"] == 1.2
        assert state_dict["latest_reading"]["temperature"] == 25.0
        assert state_dict["latest_reading"]["state_of_charge"] == 90.0
        assert state_dict["device_status"]["connected"] is True
        assert state_dict["device_status"]["protocol_version"] == "1.0"


class TestDeviceStateManager:
    """Test cases for DeviceStateManager class."""

    @pytest.fixture
    def state_manager(self) -> DeviceStateManager:
        """Create a DeviceStateManager instance for testing."""
        return DeviceStateManager()

    @pytest.fixture
    def sample_reading(self) -> BatteryInfo:
        """Create a sample battery reading."""
        return BatteryInfo(
            voltage=12.6,
            current=1.2,
            temperature=25.0,
            state_of_charge=90.0,
            capacity=100.0,
            cycles=10,
            timestamp=1234567890.0,
        )

    @pytest.fixture
    def sample_status(self) -> DeviceStatus:
        """Create a sample device status."""
        return DeviceStatus(
            connected=True,
            error_code=None,
            error_message=None,
            protocol_version="1.0",
            last_command="status",
        )

    @pytest.mark.asyncio
    async def test_register_device(self, state_manager: DeviceStateManager) -> None:
        """Test registering a new device."""
        result = await state_manager.register_device("AA:BB:CC:DD:EE:FF", "BM6")
        assert result is True

        # Verify device is in the manager
        retrieved_state = state_manager.get_device_state("AA:BB:CC:DD:EE:FF")
        assert retrieved_state is not None
        assert retrieved_state.mac_address == "AA:BB:CC:DD:EE:FF"
        assert retrieved_state.device_type == "BM6"

    @pytest.mark.asyncio
    async def test_register_duplicate_device(
        self,
        state_manager: DeviceStateManager,
    ) -> None:
        """Test registering a device that already exists."""
        result1 = await state_manager.register_device("AA:BB:CC:DD:EE:FF", "BM6")
        assert result1 is True

        result2 = await state_manager.register_device("AA:BB:CC:DD:EE:FF", "BM6")
        assert result2 is False

    @pytest.mark.asyncio
    async def test_unregister_device(self, state_manager: DeviceStateManager) -> None:
        """Test unregistering a device."""
        await state_manager.register_device("AA:BB:CC:DD:EE:FF", "BM6")

        # Verify device exists
        assert state_manager.get_device_state("AA:BB:CC:DD:EE:FF") is not None

        # Unregister device
        result = await state_manager.unregister_device("AA:BB:CC:DD:EE:FF")
        assert result is True

        # Verify device is removed
        assert state_manager.get_device_state("AA:BB:CC:DD:EE:FF") is None

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_device(
        self,
        state_manager: DeviceStateManager,
    ) -> None:
        """Test unregistering a device that doesn't exist."""
        result = await state_manager.unregister_device("AA:BB:CC:DD:EE:FF")
        assert result is False

    @pytest.mark.asyncio
    async def test_update_device_reading(
        self,
        state_manager: DeviceStateManager,
        sample_reading: BatteryInfo,
    ) -> None:
        """Test updating device reading."""
        await state_manager.register_device("AA:BB:CC:DD:EE:FF", "BM6")

        result = await state_manager.update_device_reading(
            "AA:BB:CC:DD:EE:FF",
            sample_reading,
        )
        assert result is True

        state = state_manager.get_device_state("AA:BB:CC:DD:EE:FF")
        assert state is not None
        assert state.latest_reading == sample_reading
        assert state.reading_count == 1

    @pytest.mark.asyncio
    async def test_update_device_reading_nonexistent(
        self,
        state_manager: DeviceStateManager,
        sample_reading: BatteryInfo,
    ) -> None:
        """Test updating reading for nonexistent device."""
        result = await state_manager.update_device_reading(
            "AA:BB:CC:DD:EE:FF",
            sample_reading,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_update_device_status(
        self,
        state_manager: DeviceStateManager,
        sample_status: DeviceStatus,
    ) -> None:
        """Test updating device status."""
        await state_manager.register_device("AA:BB:CC:DD:EE:FF", "BM6")

        result = await state_manager.update_device_status(
            "AA:BB:CC:DD:EE:FF",
            sample_status,
        )
        assert result is True

        state = state_manager.get_device_state("AA:BB:CC:DD:EE:FF")
        assert state is not None
        assert state.device_status == sample_status
        assert state.connected is True

    @pytest.mark.asyncio
    async def test_update_connection_state(
        self,
        state_manager: DeviceStateManager,
    ) -> None:
        """Test updating connection state."""
        await state_manager.register_device("AA:BB:CC:DD:EE:FF", "BM6")

        # Test successful connection
        result = await state_manager.update_connection_state("AA:BB:CC:DD:EE:FF", True)
        assert result is True

        state = state_manager.get_device_state("AA:BB:CC:DD:EE:FF")
        assert state is not None
        assert state.connected is True
        assert state.connection_error_count == 0

        # Test failed connection
        result = await state_manager.update_connection_state(
            "AA:BB:CC:DD:EE:FF",
            False,
            "Timeout",
        )
        assert result is True

        state = state_manager.get_device_state("AA:BB:CC:DD:EE:FF")
        assert state is not None
        assert state.connected is False
        assert state.connection_error_count == 1
        assert state.last_connection_error == "Timeout"

    @pytest.mark.asyncio
    async def test_update_polling_state(
        self,
        state_manager: DeviceStateManager,
    ) -> None:
        """Test updating polling state."""
        await state_manager.register_device("AA:BB:CC:DD:EE:FF", "BM6")

        # Test active polling
        result = await state_manager.update_polling_state("AA:BB:CC:DD:EE:FF", True)
        assert result is True

        state = state_manager.get_device_state("AA:BB:CC:DD:EE:FF")
        assert state is not None
        assert state.polling_active is True
        assert state.polling_error_count == 0

        # Test polling with error
        result = await state_manager.update_polling_state(
            "AA:BB:CC:DD:EE:FF",
            False,
            "Read failed",
        )
        assert result is True

        state = state_manager.get_device_state("AA:BB:CC:DD:EE:FF")
        assert state is not None
        assert state.polling_active is False
        assert state.polling_error_count == 1
        assert state.last_polling_error == "Read failed"

    @pytest.mark.asyncio
    async def test_set_vehicle_association(
        self,
        state_manager: DeviceStateManager,
    ) -> None:
        """Test setting vehicle association."""
        await state_manager.register_device("AA:BB:CC:DD:EE:FF", "BM6")

        # Set vehicle association
        result = await state_manager.set_vehicle_association(
            "AA:BB:CC:DD:EE:FF",
            "vehicle_1",
        )
        assert result is True

        state = state_manager.get_device_state("AA:BB:CC:DD:EE:FF")
        assert state is not None
        assert state.vehicle_id == "vehicle_1"

        # Remove vehicle association
        result = await state_manager.set_vehicle_association("AA:BB:CC:DD:EE:FF", None)
        assert result is True

        state = state_manager.get_device_state("AA:BB:CC:DD:EE:FF")
        assert state is not None
        assert state.vehicle_id is None

    @pytest.mark.asyncio
    async def test_set_vehicle_association_nonexistent(
        self,
        state_manager: DeviceStateManager,
    ) -> None:
        """Test setting vehicle association for nonexistent device."""
        result = await state_manager.set_vehicle_association(
            "AA:BB:CC:DD:EE:FF",
            "vehicle_1",
        )
        assert result is False

    def test_get_all_devices(self, state_manager: DeviceStateManager) -> None:
        """Test getting all devices."""
        # Register devices
        asyncio.run(state_manager.register_device("AA:BB:CC:DD:EE:FF", "BM6"))
        asyncio.run(state_manager.register_device("BB:CC:DD:EE:FF:AA", "BM2"))
        asyncio.run(state_manager.register_device("CC:DD:EE:FF:AA:BB", "BM6"))

        # Test getting all devices
        devices = state_manager.get_all_devices()
        assert len(devices) == 3

    def test_get_devices_by_type(self, state_manager: DeviceStateManager) -> None:
        """Test getting devices by type."""
        # Register devices
        asyncio.run(state_manager.register_device("AA:BB:CC:DD:EE:FF", "BM6"))
        asyncio.run(state_manager.register_device("BB:CC:DD:EE:FF:AA", "BM2"))
        asyncio.run(state_manager.register_device("CC:DD:EE:FF:AA:BB", "BM6"))

        # Test getting devices by type
        bm6_devices = state_manager.get_devices_by_type("BM6")
        assert len(bm6_devices) == 2

        bm2_devices = state_manager.get_devices_by_type("BM2")
        assert len(bm2_devices) == 1

    def test_get_devices_by_vehicle(self, state_manager: DeviceStateManager) -> None:
        """Test getting devices by vehicle."""
        # Register devices
        asyncio.run(state_manager.register_device("AA:BB:CC:DD:EE:FF", "BM6"))
        asyncio.run(state_manager.register_device("BB:CC:DD:EE:FF:AA", "BM2"))
        asyncio.run(state_manager.register_device("CC:DD:EE:FF:AA:BB", "BM6"))

        # Set vehicle associations
        asyncio.run(
            state_manager.set_vehicle_association("AA:BB:CC:DD:EE:FF", "vehicle_1"),
        )
        asyncio.run(
            state_manager.set_vehicle_association("BB:CC:DD:EE:FF:AA", "vehicle_1"),
        )
        asyncio.run(
            state_manager.set_vehicle_association("CC:DD:EE:FF:AA:BB", "vehicle_2"),
        )

        # Test getting devices by vehicle
        vehicle_1_devices = state_manager.get_devices_by_vehicle("vehicle_1")
        assert len(vehicle_1_devices) == 2

        vehicle_2_devices = state_manager.get_devices_by_vehicle("vehicle_2")
        assert len(vehicle_2_devices) == 1

    def test_get_connected_devices(self, state_manager: DeviceStateManager) -> None:
        """Test getting connected devices."""
        # Register devices
        asyncio.run(state_manager.register_device("AA:BB:CC:DD:EE:FF", "BM6"))
        asyncio.run(state_manager.register_device("BB:CC:DD:EE:FF:AA", "BM2"))
        asyncio.run(state_manager.register_device("CC:DD:EE:FF:AA:BB", "BM6"))

        # Set connection states
        asyncio.run(state_manager.update_connection_state("AA:BB:CC:DD:EE:FF", True))
        asyncio.run(state_manager.update_connection_state("BB:CC:DD:EE:FF:AA", False))
        asyncio.run(state_manager.update_connection_state("CC:DD:EE:FF:AA:BB", True))

        # Test getting connected devices
        connected_devices = state_manager.get_connected_devices()
        assert len(connected_devices) == 2

    def test_get_polling_devices(self, state_manager: DeviceStateManager) -> None:
        """Test getting polling devices."""
        # Register devices
        asyncio.run(state_manager.register_device("AA:BB:CC:DD:EE:FF", "BM6"))
        asyncio.run(state_manager.register_device("BB:CC:DD:EE:FF:AA", "BM2"))
        asyncio.run(state_manager.register_device("CC:DD:EE:FF:AA:BB", "BM6"))

        # Set polling states
        asyncio.run(state_manager.update_polling_state("AA:BB:CC:DD:EE:FF", True))
        asyncio.run(state_manager.update_polling_state("BB:CC:DD:EE:FF:AA", False))
        asyncio.run(state_manager.update_polling_state("CC:DD:EE:FF:AA:BB", True))

        # Test getting polling devices
        polling_devices = state_manager.get_polling_devices()
        assert len(polling_devices) == 2

    def test_get_devices_with_errors(self, state_manager: DeviceStateManager) -> None:
        """Test getting devices with errors."""
        # Register devices
        asyncio.run(state_manager.register_device("AA:BB:CC:DD:EE:FF", "BM6"))
        asyncio.run(state_manager.register_device("BB:CC:DD:EE:FF:AA", "BM2"))
        asyncio.run(state_manager.register_device("CC:DD:EE:FF:AA:BB", "BM6"))

        # Set error states
        asyncio.run(
            state_manager.update_connection_state(
                "AA:BB:CC:DD:EE:FF",
                False,
                "Connection failed",
            ),
        )
        asyncio.run(
            state_manager.update_polling_state(
                "BB:CC:DD:EE:FF:AA",
                False,
                "Polling failed",
            ),
        )
        asyncio.run(state_manager.update_connection_state("CC:DD:EE:FF:AA:BB", True))

        # Test getting devices with errors
        error_devices = state_manager.get_devices_with_errors()
        assert len(error_devices) == 2

    def test_subscribe_and_unsubscribe(self, state_manager: DeviceStateManager) -> None:
        """Test subscribing and unsubscribing to changes."""
        # Register a device
        asyncio.run(state_manager.register_device("AA:BB:CC:DD:EE:FF", "BM6"))

        # Subscribe to changes
        callback_called = False
        callback_mac = ""
        callback_new_state = None
        callback_old_state = None

        def test_callback(
            mac_address: str,
            new_state: DeviceState | None,
            old_state: DeviceState | None,
        ) -> None:
            nonlocal \
                callback_called, \
                callback_mac, \
                callback_new_state, \
                callback_old_state
            callback_called = True
            callback_mac = mac_address
            callback_new_state = new_state
            callback_old_state = old_state

        state_manager.subscribe_to_changes("reading", test_callback)

        # Update device reading
        reading = MagicMock()
        asyncio.run(state_manager.update_device_reading("AA:BB:CC:DD:EE:FF", reading))

        # Verify callback was called
        assert callback_called
        assert callback_mac == "AA:BB:CC:DD:EE:FF"
        assert callback_new_state is not None
        assert callback_old_state is not None

        # Unsubscribe
        result = state_manager.unsubscribe_from_changes("reading", test_callback)
        assert result is True

        # Reset callback flag
        callback_called = False

        # Update device reading again
        asyncio.run(state_manager.update_device_reading("AA:BB:CC:DD:EE:FF", reading))

        # Verify callback was not called
        assert not callback_called

    def test_invalid_event_type(self, state_manager: DeviceStateManager) -> None:
        """Test subscribing to invalid event type."""

        def test_callback(
            mac_address: str,
            new_state: DeviceState | None,
            old_state: DeviceState | None,
        ) -> None:
            pass

        state_manager.subscribe_to_changes("invalid_event", test_callback)
        # Should not raise an exception, just log a warning

    def test_get_summary(self, state_manager: DeviceStateManager) -> None:
        """Test getting summary information."""
        # Register devices
        asyncio.run(state_manager.register_device("AA:BB:CC:DD:EE:FF", "BM6"))
        asyncio.run(state_manager.register_device("BB:CC:DD:EE:FF:AA", "BM2"))

        # Set some states
        asyncio.run(state_manager.update_connection_state("AA:BB:CC:DD:EE:FF", True))
        asyncio.run(state_manager.update_polling_state("BB:CC:DD:EE:FF:AA", True))

        # Get summary
        summary = state_manager.get_summary()
        assert summary["total_devices"] == 2
        assert summary["connected_devices"] == 1
        assert summary["polling_devices"] == 1
        assert summary["devices_with_errors"] == 0

    @pytest.mark.asyncio
    async def test_concurrent_access(self, state_manager: DeviceStateManager) -> None:
        """Test concurrent access to state manager."""
        # Register a device
        await state_manager.register_device("AA:BB:CC:DD:EE:FF", "BM6")

        # Create multiple tasks that update the device concurrently
        async def update_reading(task_id: int) -> None:
            reading = MagicMock()
            await state_manager.update_device_reading("AA:BB:CC:DD:EE:FF", reading)

        async def update_status(task_id: int) -> None:
            status = MagicMock()
            await state_manager.update_device_status("AA:BB:CC:DD:EE:FF", status)

        # Run concurrent updates
        tasks = []
        for i in range(10):
            tasks.append(asyncio.create_task(update_reading(i)))
            tasks.append(asyncio.create_task(update_status(i)))

        await asyncio.gather(*tasks)

        # Verify device state is consistent
        state = state_manager.get_device_state("AA:BB:CC:DD:EE:FF")
        assert state is not None
        assert state.reading_count == 10
