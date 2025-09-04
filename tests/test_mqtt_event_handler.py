"""Tests for MQTT event handler functionality."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from battery_hawk.core.engine import BatteryHawkCore
from battery_hawk.core.state import DeviceState
from battery_hawk.mqtt import MQTTEventHandler, MQTTInterface, MQTTPublisher
from battery_hawk_driver.base.protocol import BatteryInfo, DeviceStatus


class TestMQTTEventHandler:
    """Test MQTT event handler functionality."""

    @pytest.fixture
    def mock_core_engine(self) -> Any:
        """Create a mock core engine."""
        mock_engine = MagicMock(spec=BatteryHawkCore)
        mock_engine.add_event_handler = MagicMock()
        mock_engine.remove_event_handler = MagicMock()

        # Mock state manager
        mock_state_manager = MagicMock()
        mock_state_manager.subscribe_to_changes = MagicMock()
        mock_state_manager.unsubscribe_from_changes = MagicMock()
        mock_state_manager.get_all_devices = MagicMock(return_value=[])
        mock_engine.state_manager = mock_state_manager

        # Mock registries
        mock_device_registry = MagicMock()
        mock_device_registry.get_device = MagicMock(return_value=None)
        mock_engine.device_registry = mock_device_registry

        mock_vehicle_registry = MagicMock()
        mock_vehicle_registry.get_vehicle = MagicMock(
            return_value={"name": "Test Vehicle"},
        )
        mock_engine.vehicle_registry = mock_vehicle_registry

        return mock_engine

    @pytest.fixture
    def mock_mqtt_publisher(self) -> Any:
        """Create a mock MQTT publisher."""
        mock_interface = MagicMock(spec=MQTTInterface)
        mock_interface.publish = AsyncMock()

        mock_publisher = MagicMock(spec=MQTTPublisher)
        mock_publisher.mqtt_interface = mock_interface
        mock_publisher.publish_device_reading = AsyncMock()
        mock_publisher.publish_device_status = AsyncMock()
        mock_publisher.publish_vehicle_summary = AsyncMock()
        mock_publisher.publish_system_status = AsyncMock()

        return mock_publisher

    @pytest.fixture
    def event_handler(
        self,
        mock_core_engine: Any,
        mock_mqtt_publisher: Any,
    ) -> MQTTEventHandler:
        """Create MQTT event handler with mocked dependencies."""
        return MQTTEventHandler(mock_core_engine, mock_mqtt_publisher)

    def test_init(
        self,
        event_handler: MQTTEventHandler,
        mock_core_engine: BatteryHawkCore,
        mock_mqtt_publisher: MQTTPublisher,
    ) -> None:
        """Test event handler initialization."""
        assert event_handler.core_engine is mock_core_engine
        assert event_handler.mqtt_publisher is mock_mqtt_publisher
        assert event_handler._registered_handlers == {}
        assert event_handler._vehicle_summary_cache == {}

    def test_register_all_handlers(
        self,
        event_handler: MQTTEventHandler,
        mock_core_engine: BatteryHawkCore,
    ) -> None:
        """Test registering all event handlers."""
        event_handler.register_all_handlers()

        # Verify core engine handlers were registered
        assert mock_core_engine.add_event_handler.call_count == 3
        mock_core_engine.add_event_handler.assert_any_call(
            "device_discovered",
            event_handler._registered_handlers["core_device_discovered"],
        )
        mock_core_engine.add_event_handler.assert_any_call(
            "vehicle_associated",
            event_handler._registered_handlers["core_vehicle_associated"],
        )
        mock_core_engine.add_event_handler.assert_any_call(
            "system_shutdown",
            event_handler._registered_handlers["core_system_shutdown"],
        )

        # Verify state manager handlers were registered
        assert mock_core_engine.state_manager.subscribe_to_changes.call_count == 4
        mock_core_engine.state_manager.subscribe_to_changes.assert_any_call(
            "reading",
            event_handler._registered_handlers["state_reading"],
        )
        mock_core_engine.state_manager.subscribe_to_changes.assert_any_call(
            "status",
            event_handler._registered_handlers["state_status"],
        )
        mock_core_engine.state_manager.subscribe_to_changes.assert_any_call(
            "connection",
            event_handler._registered_handlers["state_connection"],
        )
        mock_core_engine.state_manager.subscribe_to_changes.assert_any_call(
            "vehicle",
            event_handler._registered_handlers["state_vehicle"],
        )

    def test_unregister_all_handlers(
        self,
        event_handler: MQTTEventHandler,
        mock_core_engine: BatteryHawkCore,
    ) -> None:
        """Test unregistering all event handlers."""
        # First register handlers
        event_handler.register_all_handlers()

        # Then unregister them
        event_handler.unregister_all_handlers()

        # Verify handlers were unregistered
        assert mock_core_engine.remove_event_handler.call_count == 3
        assert mock_core_engine.state_manager.unsubscribe_from_changes.call_count == 4
        assert event_handler._registered_handlers == {}

    @pytest.mark.asyncio
    async def test_on_device_discovered(
        self,
        event_handler: MQTTEventHandler,
        mock_mqtt_publisher: MQTTPublisher,
    ) -> None:
        """Test device discovered event handler."""
        event_data = {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "device_type": "BM2",
            "name": "Test Device",
            "rssi": -45,
            "advertisement_data": {"manufacturer": "test"},
        }

        await event_handler.on_device_discovered(event_data)

        # Verify discovery message was published
        mock_mqtt_publisher.mqtt_interface.publish.assert_called_once()
        args, kwargs = mock_mqtt_publisher.mqtt_interface.publish.call_args

        assert args[0] == "discovery/found"
        assert kwargs["retain"] is False

        payload = args[1]
        assert payload["device_id"] == "AA:BB:CC:DD:EE:FF"
        assert payload["device_type"] == "BM2"
        assert payload["name"] == "Test Device"
        assert payload["rssi"] == -45

    @pytest.mark.asyncio
    async def test_on_device_reading(
        self,
        event_handler: MQTTEventHandler,
        mock_mqtt_publisher: MQTTPublisher,
        mock_core_engine: BatteryHawkCore,
    ) -> None:
        """Test device reading event handler."""
        mac_address = "AA:BB:CC:DD:EE:FF"

        # Create device state with reading
        reading = BatteryInfo(
            voltage=12.6,
            current=2.5,
            temperature=25.0,
            state_of_charge=85.0,
        )

        new_state = DeviceState(mac_address, "BM2")
        new_state.update_reading(reading)
        new_state.vehicle_id = "vehicle_123"

        # Mock device registry response
        mock_core_engine.device_registry.get_device.return_value = {
            "vehicle_id": "vehicle_123",
        }

        await event_handler.on_device_reading(mac_address, new_state, None)

        # Verify device reading was published
        mock_mqtt_publisher.publish_device_reading.assert_called_once_with(
            device_id=mac_address,
            reading=reading,
            vehicle_id="vehicle_123",
            device_type="BM2",
        )

    @pytest.mark.asyncio
    async def test_on_device_status_change(
        self,
        event_handler: MQTTEventHandler,
        mock_mqtt_publisher: MQTTPublisher,
    ) -> None:
        """Test device status change event handler."""
        mac_address = "AA:BB:CC:DD:EE:FF"

        # Create device state with status
        status = DeviceStatus(
            connected=True,
            protocol_version="1.0",
        )

        new_state = DeviceState(mac_address, "BM2")
        new_state.update_status(status)

        await event_handler.on_device_status_change(mac_address, new_state, None)

        # Verify device status was published
        mock_mqtt_publisher.publish_device_status.assert_called_once_with(
            device_id=mac_address,
            status=status,
            device_type="BM2",
        )

    @pytest.mark.asyncio
    async def test_on_device_connection_change(
        self,
        event_handler: MQTTEventHandler,
        mock_mqtt_publisher: MQTTPublisher,
    ) -> None:
        """Test device connection change event handler."""
        mac_address = "AA:BB:CC:DD:EE:FF"

        # Create old and new states with different connection status
        old_state = DeviceState(mac_address, "BM2")
        old_state.connected = False

        new_state = DeviceState(mac_address, "BM2")
        new_state.connected = True

        await event_handler.on_device_connection_change(
            mac_address,
            new_state,
            old_state,
        )

        # Verify connection status was published
        mock_mqtt_publisher.publish_device_status.assert_called_once()

        # Get the call arguments using call_args_list
        call_list = mock_mqtt_publisher.publish_device_status.call_args_list
        assert len(call_list) == 1

        call = call_list[0]

        # Check if it's a call object or tuple
        if hasattr(call, "args") and hasattr(call, "kwargs"):
            # It's a call object
            args = call.args
            kwargs = call.kwargs
        else:
            # It's a tuple
            args, kwargs = call

        # The method is called with keyword arguments only
        device_id_arg = kwargs.get("device_id")
        status_arg = kwargs.get("status")
        device_type_kwarg = kwargs.get("device_type")

        assert device_id_arg == mac_address
        assert status_arg.connected is True
        assert device_type_kwarg == "BM2"

    @pytest.mark.asyncio
    async def test_on_vehicle_associated(
        self,
        event_handler: MQTTEventHandler,
        mock_mqtt_publisher: MQTTPublisher,
    ) -> None:
        """Test vehicle association event handler."""
        event_data = {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "vehicle_id": "vehicle_123",
            "device_type": "BM2",
            "new_vehicle": True,
        }

        await event_handler.on_vehicle_associated(event_data)

        # Verify association message was published
        mock_mqtt_publisher.mqtt_interface.publish.assert_called()
        args, kwargs = mock_mqtt_publisher.mqtt_interface.publish.call_args

        assert args[0] == "vehicle/vehicle_123/device_associated"
        assert kwargs["retain"] is False

        payload = args[1]
        assert payload["device_id"] == "AA:BB:CC:DD:EE:FF"
        assert payload["vehicle_id"] == "vehicle_123"
        assert payload["new_vehicle"] is True

    @pytest.mark.asyncio
    async def test_on_system_shutdown(
        self,
        event_handler: MQTTEventHandler,
        mock_mqtt_publisher: MQTTPublisher,
    ) -> None:
        """Test system shutdown event handler."""
        event_data = {"reason": "user_requested"}

        await event_handler.on_system_shutdown(event_data)

        # Verify shutdown message was published
        mock_mqtt_publisher.mqtt_interface.publish.assert_called_once()
        args, kwargs = mock_mqtt_publisher.mqtt_interface.publish.call_args

        assert args[0] == "system/shutdown"
        assert kwargs["retain"] is True

        payload = args[1]
        assert payload["status"] == "shutting_down"
        assert payload["reason"] == "user_requested"

    @pytest.mark.asyncio
    async def test_on_system_status_change(
        self,
        event_handler: MQTTEventHandler,
        mock_mqtt_publisher: MQTTPublisher,
    ) -> None:
        """Test system status change handler."""
        status_data = {
            "core": {"running": True},
            "storage": {"connected": True},
        }

        await event_handler.on_system_status_change(status_data)

        # Verify system status was published
        mock_mqtt_publisher.publish_system_status.assert_called_once_with(status_data)

    @pytest.mark.asyncio
    async def test_update_vehicle_summary(
        self,
        event_handler: MQTTEventHandler,
        mock_mqtt_publisher: MQTTPublisher,
        mock_core_engine: BatteryHawkCore,
    ) -> None:
        """Test vehicle summary update."""
        vehicle_id = "vehicle_123"

        # Mock vehicle registry
        mock_core_engine.vehicle_registry.get_vehicle.return_value = {
            "name": "Test Vehicle",
        }

        # Mock device states
        device_state = DeviceState("AA:BB:CC:DD:EE:FF", "BM2")
        device_state.vehicle_id = vehicle_id
        device_state.connected = True

        reading = BatteryInfo(
            voltage=12.6,
            current=2.5,
            temperature=25.0,
            state_of_charge=85.0,
            capacity=100.0,
        )
        device_state.update_reading(reading)

        mock_core_engine.state_manager.get_all_devices.return_value = [device_state]

        await event_handler._update_vehicle_summary(vehicle_id)

        # Verify vehicle summary was published
        mock_mqtt_publisher.publish_vehicle_summary.assert_called_once()
        args, kwargs = mock_mqtt_publisher.publish_vehicle_summary.call_args

        assert args[0] == vehicle_id
        summary_data = args[1]
        assert summary_data["name"] == "Test Vehicle"
        assert summary_data["total_devices"] == 1
        assert summary_data["connected_devices"] == 1
        assert summary_data["average_voltage"] == 12.6
        assert summary_data["overall_health"] == "excellent"

    @pytest.mark.asyncio
    async def test_vehicle_summary_caching(
        self,
        event_handler: MQTTEventHandler,
        mock_mqtt_publisher: MQTTPublisher,
        mock_core_engine: BatteryHawkCore,
    ) -> None:
        """Test that vehicle summary is cached to avoid redundant updates."""
        vehicle_id = "vehicle_123"

        # Mock vehicle registry
        mock_core_engine.vehicle_registry.get_vehicle.return_value = {
            "name": "Test Vehicle",
        }

        # Mock device states - use the same device state object for both calls
        device_state = DeviceState("AA:BB:CC:DD:EE:FF", "BM2")
        device_state.vehicle_id = vehicle_id
        device_state.connected = True

        # Create a reading with fixed timestamp to ensure consistent data
        reading = BatteryInfo(
            voltage=12.6,
            current=2.5,
            temperature=25.0,
            state_of_charge=85.0,
            capacity=100.0,
            timestamp=1234567890.0,  # Fixed timestamp
        )
        device_state.update_reading(reading)

        mock_core_engine.state_manager.get_all_devices.return_value = [device_state]

        # Call twice with same data
        await event_handler._update_vehicle_summary(vehicle_id)
        await event_handler._update_vehicle_summary(vehicle_id)

        # Should only publish once due to caching
        assert mock_mqtt_publisher.publish_vehicle_summary.call_count == 1
