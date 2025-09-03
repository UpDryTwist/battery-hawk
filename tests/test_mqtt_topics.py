"""Tests for MQTT topics module."""

import pytest
from battery_hawk.mqtt.topics import MQTTTopics, TopicInfo


class TestMQTTTopics:
    """Test MQTT topics functionality."""

    @pytest.fixture
    def topics(self) -> MQTTTopics:
        """Create MQTTTopics instance with default prefix."""
        return MQTTTopics()

    @pytest.fixture
    def custom_topics(self) -> MQTTTopics:
        """Create MQTTTopics instance with custom prefix."""
        return MQTTTopics(prefix="custom_hawk")

    def test_default_prefix(self, topics: MQTTTopics) -> None:
        """Test default topic prefix."""
        assert topics.prefix == "battery_hawk"

    def test_custom_prefix(self, custom_topics: MQTTTopics) -> None:
        """Test custom topic prefix."""
        assert custom_topics.prefix == "custom_hawk"

    def test_device_reading_topic(self, topics: MQTTTopics) -> None:
        """Test device reading topic generation."""
        mac = "AA:BB:CC:DD:EE:FF"
        expected = "battery_hawk/device/AA:BB:CC:DD:EE:FF/reading"
        assert topics.device_reading(mac) == expected

    def test_device_status_topic(self, topics: MQTTTopics) -> None:
        """Test device status topic generation."""
        mac = "AA:BB:CC:DD:EE:FF"
        expected = "battery_hawk/device/AA:BB:CC:DD:EE:FF/status"
        assert topics.device_status(mac) == expected

    def test_vehicle_summary_topic(self, topics: MQTTTopics) -> None:
        """Test vehicle summary topic generation."""
        vehicle_id = "my_vehicle"
        expected = "battery_hawk/vehicle/my_vehicle/summary"
        assert topics.vehicle_summary(vehicle_id) == expected

    def test_system_status_topic(self, topics: MQTTTopics) -> None:
        """Test system status topic generation."""
        expected = "battery_hawk/system/status"
        assert topics.system_status() == expected

    def test_discovery_found_topic(self, topics: MQTTTopics) -> None:
        """Test discovery found topic generation."""
        expected = "battery_hawk/discovery/found"
        assert topics.discovery_found() == expected

    def test_device_wildcard_topics(self, topics: MQTTTopics) -> None:
        """Test device wildcard topic patterns."""
        # Specific device wildcard
        mac = "AA:BB:CC:DD:EE:FF"
        expected = "battery_hawk/device/AA:BB:CC:DD:EE:FF/+"
        assert topics.device_wildcard(mac) == expected
        
        # All devices wildcard
        expected = "battery_hawk/device/+/+"
        assert topics.device_wildcard() == expected

    def test_all_device_topics(self, topics: MQTTTopics) -> None:
        """Test all device topic patterns."""
        assert topics.all_device_readings() == "battery_hawk/device/+/reading"
        assert topics.all_device_status() == "battery_hawk/device/+/status"

    def test_all_vehicle_topics(self, topics: MQTTTopics) -> None:
        """Test all vehicle topic patterns."""
        assert topics.all_vehicle_summaries() == "battery_hawk/vehicle/+/summary"

    def test_global_wildcard_topics(self, topics: MQTTTopics) -> None:
        """Test global wildcard topic patterns."""
        assert topics.all_topics() == "battery_hawk/+"
        assert topics.all_topics_recursive() == "battery_hawk/#"

    def test_parse_device_reading_topic(self, topics: MQTTTopics) -> None:
        """Test parsing device reading topic."""
        topic = "battery_hawk/device/AA:BB:CC:DD:EE:FF/reading"
        parsed = topics.parse_topic(topic)
        
        assert parsed is not None
        assert parsed["category"] == "device"
        assert parsed["mac_address"] == "AA:BB:CC:DD:EE:FF"
        assert parsed["topic_type"] == "reading"
        assert parsed["full_topic"] == topic
        assert parsed["qos"] == 1
        assert parsed["retain"] is False

    def test_parse_device_status_topic(self, topics: MQTTTopics) -> None:
        """Test parsing device status topic."""
        topic = "battery_hawk/device/AA:BB:CC:DD:EE:FF/status"
        parsed = topics.parse_topic(topic)
        
        assert parsed is not None
        assert parsed["category"] == "device"
        assert parsed["mac_address"] == "AA:BB:CC:DD:EE:FF"
        assert parsed["topic_type"] == "status"
        assert parsed["retain"] is True

    def test_parse_vehicle_summary_topic(self, topics: MQTTTopics) -> None:
        """Test parsing vehicle summary topic."""
        topic = "battery_hawk/vehicle/my_vehicle/summary"
        parsed = topics.parse_topic(topic)
        
        assert parsed is not None
        assert parsed["category"] == "vehicle"
        assert parsed["vehicle_id"] == "my_vehicle"
        assert parsed["topic_type"] == "summary"
        assert parsed["retain"] is True

    def test_parse_system_status_topic(self, topics: MQTTTopics) -> None:
        """Test parsing system status topic."""
        topic = "battery_hawk/system/status"
        parsed = topics.parse_topic(topic)
        
        assert parsed is not None
        assert parsed["category"] == "system"
        assert parsed["topic_type"] == "status"
        assert parsed["qos"] == 2  # Critical
        assert parsed["retain"] is True

    def test_parse_discovery_topic(self, topics: MQTTTopics) -> None:
        """Test parsing discovery topic."""
        topic = "battery_hawk/discovery/found"
        parsed = topics.parse_topic(topic)
        
        assert parsed is not None
        assert parsed["category"] == "discovery"
        assert parsed["topic_type"] == "found"
        assert parsed["retain"] is False

    def test_parse_invalid_topic(self, topics: MQTTTopics) -> None:
        """Test parsing invalid topic."""
        # Wrong prefix
        assert topics.parse_topic("wrong_prefix/device/mac/reading") is None
        
        # No prefix
        assert topics.parse_topic("device/mac/reading") is None
        
        # Incomplete topic
        assert topics.parse_topic("battery_hawk/device") is None

    def test_mac_address_validation(self, topics: MQTTTopics) -> None:
        """Test MAC address validation."""
        # Valid formats
        assert topics.validate_mac_address("AA:BB:CC:DD:EE:FF") is True
        assert topics.validate_mac_address("aa:bb:cc:dd:ee:ff") is True
        assert topics.validate_mac_address("AA-BB-CC-DD-EE-FF") is True
        assert topics.validate_mac_address("aa-bb-cc-dd-ee-ff") is True
        assert topics.validate_mac_address("12:34:56:78:9A:BC") is True
        
        # Invalid formats
        assert topics.validate_mac_address("invalid_mac") is False
        assert topics.validate_mac_address("AA:BB:CC:DD:EE") is False  # Too short
        assert topics.validate_mac_address("AA:BB:CC:DD:EE:FF:GG") is False  # Too long
        assert topics.validate_mac_address("GG:BB:CC:DD:EE:FF") is False  # Invalid hex
        assert topics.validate_mac_address("AA.BB.CC.DD.EE.FF") is False  # Wrong separator

    def test_vehicle_id_validation(self, topics: MQTTTopics) -> None:
        """Test vehicle ID validation."""
        # Valid formats
        assert topics.validate_vehicle_id("my_vehicle") is True
        assert topics.validate_vehicle_id("vehicle-123") is True
        assert topics.validate_vehicle_id("Vehicle_1") is True
        assert topics.validate_vehicle_id("car1") is True
        assert topics.validate_vehicle_id("boat_2") is True
        assert topics.validate_vehicle_id("test-vehicle-123") is True
        
        # Invalid formats
        assert topics.validate_vehicle_id("invalid vehicle!") is False  # Space and special char
        assert topics.validate_vehicle_id("vehicle@home") is False  # Special character
        assert topics.validate_vehicle_id("vehicle.1") is False  # Dot not allowed
        assert topics.validate_vehicle_id("") is False  # Empty string

    def test_is_battery_hawk_topic(self, topics: MQTTTopics) -> None:
        """Test Battery Hawk topic identification."""
        # Valid Battery Hawk topics
        assert topics.is_battery_hawk_topic("battery_hawk/device/mac/reading") is True
        assert topics.is_battery_hawk_topic("battery_hawk/system/status") is True
        
        # Invalid topics
        assert topics.is_battery_hawk_topic("other_system/device/mac/reading") is False
        assert topics.is_battery_hawk_topic("device/mac/reading") is False

    def test_get_subscription_topics(self, topics: MQTTTopics) -> None:
        """Test subscription topic list."""
        subscription_topics = topics.get_subscription_topics()
        
        expected = [
            "battery_hawk/device/+/reading",
            "battery_hawk/device/+/status",
            "battery_hawk/vehicle/+/summary",
            "battery_hawk/system/status",
            "battery_hawk/discovery/found",
        ]
        
        assert set(subscription_topics) == set(expected)

    def test_topic_info_retrieval(self, topics: MQTTTopics) -> None:
        """Test topic information retrieval."""
        # Device reading info
        info = topics.get_topic_info("device_reading")
        assert info is not None
        assert isinstance(info, TopicInfo)
        assert info.qos == 1
        assert info.retain is False
        assert "reading" in info.description.lower()
        
        # System status info
        info = topics.get_topic_info("system_status")
        assert info is not None
        assert info.qos == 2  # Critical
        assert info.retain is True
        assert "system" in info.description.lower()
        
        # Non-existent topic
        assert topics.get_topic_info("non_existent") is None

    def test_list_all_patterns(self, topics: MQTTTopics) -> None:
        """Test listing all topic patterns."""
        patterns = topics.list_all_patterns()
        
        expected_keys = [
            "device_reading",
            "device_status", 
            "vehicle_summary",
            "system_status",
            "discovery_found"
        ]
        
        assert set(patterns.keys()) == set(expected_keys)
        
        # Verify all values are TopicInfo instances
        for pattern_info in patterns.values():
            assert isinstance(pattern_info, TopicInfo)
            assert hasattr(pattern_info, 'pattern')
            assert hasattr(pattern_info, 'description')
            assert hasattr(pattern_info, 'qos')
            assert hasattr(pattern_info, 'retain')
            assert hasattr(pattern_info, 'example')

    def test_custom_prefix_parsing(self, custom_topics: MQTTTopics) -> None:
        """Test topic parsing with custom prefix."""
        topic = "custom_hawk/device/AA:BB:CC:DD:EE:FF/reading"
        parsed = custom_topics.parse_topic(topic)
        
        assert parsed is not None
        assert parsed["category"] == "device"
        assert parsed["mac_address"] == "AA:BB:CC:DD:EE:FF"
        
        # Should not parse topics with wrong prefix
        wrong_topic = "battery_hawk/device/AA:BB:CC:DD:EE:FF/reading"
        assert custom_topics.parse_topic(wrong_topic) is None

    def test_topic_info_dataclass(self) -> None:
        """Test TopicInfo dataclass."""
        info = TopicInfo(
            pattern="test/{id}/data",
            description="Test topic",
            qos=1,
            retain=False,
            example="test/123/data"
        )
        
        assert info.pattern == "test/{id}/data"
        assert info.description == "Test topic"
        assert info.qos == 1
        assert info.retain is False
        assert info.example == "test/123/data"

    def test_convenience_functions(self) -> None:
        """Test convenience functions."""
        from battery_hawk.mqtt.topics import (
            device_reading_topic,
            device_status_topic,
            vehicle_summary_topic,
            system_status_topic,
            discovery_found_topic
        )
        
        mac = "AA:BB:CC:DD:EE:FF"
        vehicle_id = "test_vehicle"
        
        assert device_reading_topic(mac) == f"battery_hawk/device/{mac}/reading"
        assert device_status_topic(mac) == f"battery_hawk/device/{mac}/status"
        assert vehicle_summary_topic(vehicle_id) == f"battery_hawk/vehicle/{vehicle_id}/summary"
        assert system_status_topic() == "battery_hawk/system/status"
        assert discovery_found_topic() == "battery_hawk/discovery/found"
