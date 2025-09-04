"""Integration tests for MQTT functionality."""

import json
import tempfile
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from battery_hawk.config.config_manager import ConfigManager
from battery_hawk.mqtt import MQTTEventHandler, MQTTInterface, MQTTPublisher, MQTTTopics
from battery_hawk_driver.base.protocol import BatteryInfo, DeviceStatus


class MockConfigManager(ConfigManager):
    """Mock configuration manager for testing."""

    def __init__(self) -> None:
        """Initialize mock configuration manager."""
        # Initialize parent with disabled watchers for testing
        super().__init__(config_dir=tempfile.mkdtemp(), enable_watchers=False)
        self.configs = {
            "system": {
                "mqtt": {
                    "enabled": True,
                    "broker": "localhost",
                    "port": 1883,
                    "username": "",
                    "password": "",
                    "topic_prefix": "test_batteryhawk",
                    "qos": 1,
                    "keepalive": 60,
                    "timeout": 10,
                    "retries": 3,
                    "tls": False,
                    "ca_cert": "",
                    "cert_file": "",
                    "key_file": "",
                    # Resilience configuration
                    "max_retries": 3,
                    "initial_retry_delay": 0.1,
                    "max_retry_delay": 1.0,
                    "backoff_multiplier": 2.0,
                    "jitter_factor": 0.1,
                    "connection_timeout": 5.0,
                    "health_check_interval": 1.0,
                    "message_queue_size": 10,
                    "message_retry_limit": 2,
                },
            },
        }
        self._change_handlers = []

    def get_config(self, key: str) -> dict:
        """Get configuration for section."""
        return self.configs.get(key, {})

    def register_change_handler(self, handler: Any) -> None:
        """Register configuration change handler."""
        self._change_handlers.append(handler)


class TestMQTTIntegration:
    """Integration tests for complete MQTT functionality."""

    @pytest.fixture
    def mock_config_manager(self) -> MockConfigManager:
        """Create a mock configuration manager."""
        return MockConfigManager()

    @pytest.fixture
    def mqtt_interface(self, mock_config_manager: MockConfigManager) -> MQTTInterface:
        """Create MQTT interface with mock configuration."""
        return MQTTInterface(mock_config_manager)

    @pytest.fixture
    def mqtt_publisher(self, mqtt_interface: MQTTInterface) -> MQTTPublisher:
        """Create MQTT publisher with mock interface."""
        return MQTTPublisher(mqtt_interface)

    @pytest.fixture
    def mqtt_event_handler(self, mqtt_publisher: MQTTPublisher) -> MQTTEventHandler:
        """Create MQTT event handler with mock publisher."""
        # Create a mock core engine
        mock_core_engine = MagicMock()
        return MQTTEventHandler(mock_core_engine, mqtt_publisher)

    def test_topic_structure_compliance(self, mqtt_interface: MQTTInterface) -> None:
        """Test that topic structure matches PRD specification."""
        topics = mqtt_interface.topics

        # Test device topics
        mac = "AA:BB:CC:DD:EE:FF"
        assert (
            topics.device_reading(mac)
            == "test_batteryhawk/device/AA:BB:CC:DD:EE:FF/reading"
        )
        assert (
            topics.device_status(mac)
            == "test_batteryhawk/device/AA:BB:CC:DD:EE:FF/status"
        )

        # Test vehicle topics
        vehicle_id = "my_vehicle"
        assert (
            topics.vehicle_summary(vehicle_id)
            == "test_batteryhawk/vehicle/my_vehicle/summary"
        )

        # Test system topics
        assert topics.system_status() == "test_batteryhawk/system/status"

        # Test discovery topics
        assert topics.discovery_found() == "test_batteryhawk/discovery/found"

    def test_topic_wildcards(self, mqtt_interface: MQTTInterface) -> None:
        """Test wildcard topic patterns for subscriptions."""
        topics = mqtt_interface.topics

        # Test wildcard patterns
        assert topics.all_device_readings() == "test_batteryhawk/device/+/reading"
        assert topics.all_device_status() == "test_batteryhawk/device/+/status"
        assert topics.all_vehicle_summaries() == "test_batteryhawk/vehicle/+/summary"
        assert topics.all_topics_recursive() == "test_batteryhawk/#"

    def test_topic_parsing(self, mqtt_interface: MQTTInterface) -> None:
        """Test topic parsing functionality."""
        topics = mqtt_interface.topics

        # Test device topic parsing
        device_reading_topic = "test_batteryhawk/device/AA:BB:CC:DD:EE:FF/reading"
        parsed = topics.parse_topic(device_reading_topic)
        assert parsed is not None
        assert parsed["category"] == "device"
        assert parsed["mac_address"] == "AA:BB:CC:DD:EE:FF"
        assert parsed["topic_type"] == "reading"

        # Test vehicle topic parsing
        vehicle_summary_topic = "test_batteryhawk/vehicle/my_vehicle/summary"
        parsed = topics.parse_topic(vehicle_summary_topic)
        assert parsed is not None
        assert parsed["category"] == "vehicle"
        assert parsed["vehicle_id"] == "my_vehicle"
        assert parsed["topic_type"] == "summary"

        # Test system topic parsing
        system_status_topic = "test_batteryhawk/system/status"
        parsed = topics.parse_topic(system_status_topic)
        assert parsed is not None
        assert parsed["category"] == "system"
        assert parsed["topic_type"] == "status"

    def test_topic_validation(self, mqtt_interface: MQTTInterface) -> None:
        """Test topic validation functions."""
        topics = mqtt_interface.topics

        # Test MAC address validation
        assert topics.validate_mac_address("AA:BB:CC:DD:EE:FF") is True
        assert topics.validate_mac_address("aa:bb:cc:dd:ee:ff") is True
        assert topics.validate_mac_address("AA-BB-CC-DD-EE-FF") is True
        assert topics.validate_mac_address("invalid_mac") is False

        # Test vehicle ID validation
        assert topics.validate_vehicle_id("my_vehicle") is True
        assert topics.validate_vehicle_id("vehicle-123") is True
        assert topics.validate_vehicle_id("Vehicle_1") is True
        assert topics.validate_vehicle_id("invalid vehicle!") is False

    @pytest.mark.asyncio
    async def test_complete_device_workflow(
        self,
        mqtt_interface: MQTTInterface,
        mqtt_publisher: MQTTPublisher,
    ) -> None:
        """Test complete device data publishing workflow."""
        # Mock the MQTT client
        with patch.object(mqtt_interface, "_client") as mock_client:
            mock_client.publish = AsyncMock()
            mqtt_interface._connection_state = (
                mqtt_interface._connection_state.CONNECTED
            )

            # Create test battery reading
            reading = BatteryInfo(
                voltage=12.6,
                current=2.5,
                temperature=25.0,
                state_of_charge=85.0,
                capacity=100.0,
                cycles=150,
            )

            # Publish device reading
            device_id = "AA:BB:CC:DD:EE:FF"
            await mqtt_publisher.publish_device_reading(
                device_id=device_id,
                reading=reading,
                vehicle_id="test_vehicle",
                device_type="BM6",
            )

            # Verify correct topic was used
            expected_topic = f"test_batteryhawk/device/{device_id}/reading"
            mock_client.publish.assert_called_once()
            call_args = mock_client.publish.call_args
            assert call_args[0][0] == expected_topic

            # Verify message structure
            message_data = json.loads(call_args[0][1])
            assert message_data["device_id"] == device_id
            assert message_data["voltage"] == 12.6
            assert message_data["current"] == 2.5
            assert message_data["vehicle_id"] == "test_vehicle"
            assert message_data["device_type"] == "BM6"
            assert "timestamp" in message_data
            assert "power" in message_data  # Should be calculated

    @pytest.mark.asyncio
    async def test_complete_status_workflow(
        self,
        mqtt_interface: MQTTInterface,
        mqtt_publisher: MQTTPublisher,
    ) -> None:
        """Test complete device status publishing workflow."""
        # Mock the MQTT client
        with patch.object(mqtt_interface, "_client") as mock_client:
            mock_client.publish = AsyncMock()
            mqtt_interface._connection_state = (
                mqtt_interface._connection_state.CONNECTED
            )

            # Create test device status
            status = DeviceStatus(
                connected=True,
                protocol_version="1.0",
                last_command="read_data",
            )

            # Publish device status
            device_id = "AA:BB:CC:DD:EE:FF"
            await mqtt_publisher.publish_device_status(
                device_id=device_id,
                status=status,
                device_type="BM6",
            )

            # Verify correct topic was used
            expected_topic = f"test_batteryhawk/device/{device_id}/status"
            mock_client.publish.assert_called_once()
            call_args = mock_client.publish.call_args
            assert call_args[0][0] == expected_topic

            # Verify retain flag for status messages
            assert call_args[1]["retain"] is True

    @pytest.mark.asyncio
    async def test_vehicle_summary_workflow(
        self,
        mqtt_interface: MQTTInterface,
        mqtt_publisher: MQTTPublisher,
    ) -> None:
        """Test vehicle summary publishing workflow."""
        # Mock the MQTT client
        with patch.object(mqtt_interface, "_client") as mock_client:
            mock_client.publish = AsyncMock()
            mqtt_interface._connection_state = (
                mqtt_interface._connection_state.CONNECTED
            )

            # Create test vehicle summary
            summary_data = {
                "total_devices": 2,
                "connected_devices": 1,
                "total_voltage": 25.2,
                "average_soc": 82.5,
                "devices": [
                    {"device_id": "AA:BB:CC:DD:EE:FF", "status": "connected"},
                    {"device_id": "BB:CC:DD:EE:FF:AA", "status": "disconnected"},
                ],
            }

            # Publish vehicle summary
            vehicle_id = "test_vehicle"
            await mqtt_publisher.publish_vehicle_summary(
                vehicle_id=vehicle_id,
                summary_data=summary_data,
            )

            # Verify correct topic was used
            expected_topic = f"test_batteryhawk/vehicle/{vehicle_id}/summary"
            mock_client.publish.assert_called_once()
            call_args = mock_client.publish.call_args
            assert call_args[0][0] == expected_topic

            # Verify retain flag for summary messages
            assert call_args[1]["retain"] is True

    @pytest.mark.asyncio
    async def test_system_status_workflow(
        self,
        mqtt_interface: MQTTInterface,
        mqtt_publisher: MQTTPublisher,
    ) -> None:
        """Test system status publishing workflow."""
        # Mock the MQTT client
        with patch.object(mqtt_interface, "_client") as mock_client:
            mock_client.publish = AsyncMock()
            mqtt_interface._connection_state = (
                mqtt_interface._connection_state.CONNECTED
            )

            # Create test system status
            status_data = {
                "status": "running",
                "uptime": 3600,
                "total_devices": 5,
                "connected_devices": 3,
                "storage_status": "healthy",
                "memory_usage": 45.2,
            }

            # Publish system status
            await mqtt_publisher.publish_system_status(status_data)

            # Verify correct topic was used
            expected_topic = "test_batteryhawk/system/status"
            mock_client.publish.assert_called_once()
            call_args = mock_client.publish.call_args
            assert call_args[0][0] == expected_topic

            # Verify retain flag for system status
            assert call_args[1]["retain"] is True

    @pytest.mark.asyncio
    async def test_event_handler_integration(
        self,
        mqtt_event_handler: MQTTEventHandler,
    ) -> None:
        """Test event handler integration with MQTT publishing."""
        # Mock the MQTT interface
        with patch.object(
            mqtt_event_handler.mqtt_publisher.mqtt_interface,
            "_client",
        ) as mock_client:
            mock_client.publish = AsyncMock()
            mqtt_event_handler.mqtt_publisher.mqtt_interface._connection_state = mqtt_event_handler.mqtt_publisher.mqtt_interface._connection_state.CONNECTED

            # Test device discovery event
            event_data = {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "device_type": "BM6",
                "rssi": -45,
                "advertisement_data": {"name": "BM6_Device"},
            }

            await mqtt_event_handler.on_device_discovered(event_data)

            # Verify discovery message was published
            expected_topic = "test_batteryhawk/discovery/found"
            mock_client.publish.assert_called()

            # Find the discovery call
            discovery_call = None
            for call in mock_client.publish.call_args_list:
                if call[0][0] == expected_topic:
                    discovery_call = call
                    break

            assert discovery_call is not None
            message_data = json.loads(discovery_call[0][1])
            assert message_data["device_id"] == "AA:BB:CC:DD:EE:FF"
            assert message_data["device_type"] == "BM6"

    def test_subscription_topics(self, mqtt_interface: MQTTInterface) -> None:
        """Test subscription topic patterns."""
        topics = mqtt_interface.topics
        subscription_topics = topics.get_subscription_topics()

        expected_topics = [
            "test_batteryhawk/device/+/reading",
            "test_batteryhawk/device/+/status",
            "test_batteryhawk/vehicle/+/summary",
            "test_batteryhawk/system/status",
            "test_batteryhawk/discovery/found",
        ]

        assert set(subscription_topics) == set(expected_topics)

    def test_topic_info_retrieval(self, mqtt_interface: MQTTInterface) -> None:
        """Test topic information retrieval."""
        topics = mqtt_interface.topics

        # Test device reading topic info
        device_reading_info = topics.get_topic_info("device_reading")
        assert device_reading_info is not None
        assert device_reading_info.qos == 1
        assert device_reading_info.retain is False

        # Test system status topic info
        system_status_info = topics.get_topic_info("system_status")
        assert system_status_info is not None
        assert system_status_info.qos == 2  # Critical
        assert system_status_info.retain is True

    def test_custom_topic_prefix(self) -> None:
        """Test custom topic prefix configuration."""
        custom_topics = MQTTTopics(prefix="custom_prefix")

        mac = "AA:BB:CC:DD:EE:FF"
        assert (
            custom_topics.device_reading(mac)
            == "custom_prefix/device/AA:BB:CC:DD:EE:FF/reading"
        )
        assert custom_topics.system_status() == "custom_prefix/system/status"
        assert custom_topics.discovery_found() == "custom_prefix/discovery/found"
