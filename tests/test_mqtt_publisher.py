"""Tests for MQTT publisher functionality."""

import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from battery_hawk.mqtt import MQTTInterface, MQTTPublisher, MQTTConnectionError
from battery_hawk_driver.base.protocol import BatteryInfo, DeviceStatus


class TestMQTTPublisher:
    """Test MQTT publisher functionality."""

    @pytest.fixture
    def mock_mqtt_interface(self) -> MQTTInterface:
        """Create a mock MQTT interface."""
        mock_interface = MagicMock(spec=MQTTInterface)
        mock_interface.publish = AsyncMock()
        mock_interface._mqtt_config = {"qos": 1}
        return mock_interface

    @pytest.fixture
    def publisher(self, mock_mqtt_interface: MQTTInterface) -> MQTTPublisher:
        """Create MQTT publisher with mock interface."""
        return MQTTPublisher(mock_mqtt_interface)

    @pytest.fixture
    def sample_battery_info(self) -> BatteryInfo:
        """Create sample battery info for testing."""
        return BatteryInfo(
            voltage=12.6,
            current=1.5,
            temperature=25.0,
            state_of_charge=85.0,
            capacity=100.0,
            cycles=150,
            timestamp=1234567890.0,
            extra={"device_type": "BM2", "raw_data": {"test": "value"}},
        )

    @pytest.fixture
    def sample_device_status(self) -> DeviceStatus:
        """Create sample device status for testing."""
        return DeviceStatus(
            connected=True,
            error_code=None,
            error_message=None,
            protocol_version="1.0",
            last_command="read_data",
            extra={"signal_strength": -45},
        )

    @pytest.mark.asyncio
    async def test_publish_device_reading_basic(
        self,
        publisher: MQTTPublisher,
        mock_mqtt_interface: MQTTInterface,
        sample_battery_info: BatteryInfo,
    ) -> None:
        """Test basic device reading publication."""
        device_id = "AA:BB:CC:DD:EE:FF"
        
        await publisher.publish_device_reading(device_id, sample_battery_info)
        
        # Verify publish was called with correct parameters
        mock_mqtt_interface.publish.assert_called_once()
        args, kwargs = mock_mqtt_interface.publish.call_args
        
        assert args[0] == f"device/{device_id}/reading"
        assert kwargs["retain"] is False
        
        # Verify payload structure
        payload = args[1]
        assert payload["device_id"] == device_id
        assert payload["voltage"] == 12.6
        assert payload["current"] == 1.5
        assert payload["temperature"] == 25.0
        assert payload["state_of_charge"] == 85.0
        assert payload["capacity"] == 100.0
        assert payload["cycles"] == 150
        assert payload["power"] == 12.6 * 1.5  # voltage * current
        assert "timestamp" in payload
        assert payload["extra"] == sample_battery_info.extra

    @pytest.mark.asyncio
    async def test_publish_device_reading_with_vehicle(
        self,
        publisher: MQTTPublisher,
        mock_mqtt_interface: MQTTInterface,
        sample_battery_info: BatteryInfo,
    ) -> None:
        """Test device reading publication with vehicle ID."""
        device_id = "AA:BB:CC:DD:EE:FF"
        vehicle_id = "vehicle_123"
        device_type = "BM2"
        
        await publisher.publish_device_reading(
            device_id,
            sample_battery_info,
            vehicle_id=vehicle_id,
            device_type=device_type,
        )
        
        # Verify payload includes vehicle and device type
        args, _ = mock_mqtt_interface.publish.call_args
        payload = args[1]
        assert payload["vehicle_id"] == vehicle_id
        assert payload["device_type"] == device_type

    @pytest.mark.asyncio
    async def test_publish_device_reading_minimal_data(
        self,
        publisher: MQTTPublisher,
        mock_mqtt_interface: MQTTInterface,
    ) -> None:
        """Test device reading publication with minimal data."""
        device_id = "AA:BB:CC:DD:EE:FF"
        minimal_reading = BatteryInfo(
            voltage=12.0,
            current=0.0,
            temperature=20.0,
            state_of_charge=50.0,
        )
        
        await publisher.publish_device_reading(device_id, minimal_reading)
        
        # Verify payload structure with minimal data
        args, _ = mock_mqtt_interface.publish.call_args
        payload = args[1]
        assert payload["device_id"] == device_id
        assert payload["voltage"] == 12.0
        assert payload["current"] == 0.0
        assert payload["temperature"] == 20.0
        assert payload["state_of_charge"] == 50.0
        assert payload["power"] == 0.0  # 12.0 * 0.0
        assert "capacity" not in payload  # Should not include None values
        assert "cycles" not in payload

    @pytest.mark.asyncio
    async def test_publish_device_status_connected(
        self,
        publisher: MQTTPublisher,
        mock_mqtt_interface: MQTTInterface,
        sample_device_status: DeviceStatus,
    ) -> None:
        """Test device status publication for connected device."""
        device_id = "AA:BB:CC:DD:EE:FF"
        device_type = "BM6"
        
        await publisher.publish_device_status(
            device_id,
            sample_device_status,
            device_type=device_type,
        )
        
        # Verify publish was called with correct parameters
        mock_mqtt_interface.publish.assert_called_once()
        args, kwargs = mock_mqtt_interface.publish.call_args
        
        assert args[0] == f"device/{device_id}/status"
        assert kwargs["retain"] is True  # Status should be retained
        
        # Verify payload structure
        payload = args[1]
        assert payload["device_id"] == device_id
        assert payload["connected"] is True
        assert payload["protocol_version"] == "1.0"
        assert payload["last_command"] == "read_data"
        assert payload["device_type"] == device_type
        assert payload["extra"] == sample_device_status.extra
        assert "timestamp" in payload

    @pytest.mark.asyncio
    async def test_publish_device_status_disconnected_with_error(
        self,
        publisher: MQTTPublisher,
        mock_mqtt_interface: MQTTInterface,
    ) -> None:
        """Test device status publication for disconnected device with error."""
        device_id = "AA:BB:CC:DD:EE:FF"
        error_status = DeviceStatus(
            connected=False,
            error_code=1001,
            error_message="Connection timeout",
        )
        
        await publisher.publish_device_status(device_id, error_status)
        
        # Verify payload includes error information
        args, _ = mock_mqtt_interface.publish.call_args
        payload = args[1]
        assert payload["connected"] is False
        assert payload["error_code"] == 1001
        assert payload["error_message"] == "Connection timeout"

    @pytest.mark.asyncio
    async def test_publish_vehicle_summary(
        self,
        publisher: MQTTPublisher,
        mock_mqtt_interface: MQTTInterface,
    ) -> None:
        """Test vehicle summary publication."""
        vehicle_id = "vehicle_123"
        summary_data = {
            "total_devices": 3,
            "connected_devices": 2,
            "average_voltage": 12.4,
            "total_capacity": 300.0,
            "overall_health": "good",
            "devices": [
                {"id": "device1", "status": "connected"},
                {"id": "device2", "status": "connected"},
                {"id": "device3", "status": "disconnected"},
            ],
        }
        
        await publisher.publish_vehicle_summary(vehicle_id, summary_data)
        
        # Verify publish was called with correct parameters
        mock_mqtt_interface.publish.assert_called_once()
        args, kwargs = mock_mqtt_interface.publish.call_args
        
        assert args[0] == f"vehicle/{vehicle_id}/summary"
        assert kwargs["retain"] is True  # Vehicle summaries should be retained
        
        # Verify payload structure
        payload = args[1]
        assert payload["vehicle_id"] == vehicle_id
        assert payload["total_devices"] == 3
        assert payload["connected_devices"] == 2
        assert payload["average_voltage"] == 12.4
        assert "timestamp" in payload

    @pytest.mark.asyncio
    async def test_publish_system_status(
        self,
        publisher: MQTTPublisher,
        mock_mqtt_interface: MQTTInterface,
    ) -> None:
        """Test system status publication."""
        status_data = {
            "core": {
                "running": True,
                "uptime": 3600,
                "version": "1.0.0",
            },
            "storage": {
                "influxdb_connected": True,
                "disk_usage": 45.2,
            },
            "components": {
                "mqtt": "connected",
                "bluetooth": "active",
                "api": "running",
            },
        }
        
        await publisher.publish_system_status(status_data)
        
        # Verify publish was called with correct parameters
        mock_mqtt_interface.publish.assert_called_once()
        args, kwargs = mock_mqtt_interface.publish.call_args
        
        assert args[0] == "system/status"
        assert kwargs["retain"] is True  # System status should be retained
        
        # Verify payload structure
        payload = args[1]
        assert payload["core"]["running"] is True
        assert payload["storage"]["influxdb_connected"] is True
        assert payload["components"]["mqtt"] == "connected"
        assert "timestamp" in payload
        
        # Verify QoS was temporarily set to 2 for system status
        assert mock_mqtt_interface._mqtt_config["qos"] == 1  # Should be restored

    @pytest.mark.asyncio
    async def test_publish_error_handling(
        self,
        publisher: MQTTPublisher,
        mock_mqtt_interface: MQTTInterface,
        sample_battery_info: BatteryInfo,
    ) -> None:
        """Test error handling in publish methods."""
        device_id = "AA:BB:CC:DD:EE:FF"
        
        # Mock publish to raise an exception
        mock_mqtt_interface.publish.side_effect = MQTTConnectionError("Connection lost")
        
        with pytest.raises(MQTTConnectionError):
            await publisher.publish_device_reading(device_id, sample_battery_info)

    @pytest.mark.asyncio
    async def test_timestamp_handling(
        self,
        publisher: MQTTPublisher,
        mock_mqtt_interface: MQTTInterface,
    ) -> None:
        """Test timestamp handling in readings."""
        device_id = "AA:BB:CC:DD:EE:FF"
        
        # Test with explicit timestamp
        reading_with_timestamp = BatteryInfo(
            voltage=12.0,
            current=1.0,
            temperature=25.0,
            state_of_charge=80.0,
            timestamp=1234567890.0,
        )
        
        await publisher.publish_device_reading(device_id, reading_with_timestamp)
        
        args, _ = mock_mqtt_interface.publish.call_args
        payload = args[1]
        assert payload["timestamp"] == 1234567890.0
        
        # Reset mock
        mock_mqtt_interface.publish.reset_mock()
        
        # Test without timestamp (should use current time)
        reading_without_timestamp = BatteryInfo(
            voltage=12.0,
            current=1.0,
            temperature=25.0,
            state_of_charge=80.0,
        )
        
        await publisher.publish_device_reading(device_id, reading_without_timestamp)
        
        args, _ = mock_mqtt_interface.publish.call_args
        payload = args[1]
        # Should have a timestamp that's a valid ISO format string
        assert "timestamp" in payload
        assert isinstance(payload["timestamp"], str)
        # Should be able to parse as datetime
        datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))
