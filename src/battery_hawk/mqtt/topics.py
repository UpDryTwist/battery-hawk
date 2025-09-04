"""
MQTT topic structure and helper functions for Battery Hawk.

This module defines the complete MQTT topic structure according to the PRD
and provides helper functions for topic construction and pattern matching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class TopicInfo:
    """Information about an MQTT topic."""

    pattern: str
    description: str
    qos: int
    retain: bool
    example: str


class MQTTTopics:
    """
    MQTT topic structure and helper methods for Battery Hawk.

    Implements the topic structure defined in the PRD:
    - battery_hawk/device/{mac}/reading     # Device reading updates
    - battery_hawk/device/{mac}/status      # Device connection status
    - battery_hawk/vehicle/{id}/summary     # Vehicle summary data
    - battery_hawk/system/status            # System status updates
    - battery_hawk/discovery/found          # New device discovered
    """

    def __init__(self, prefix: str = "battery_hawk") -> None:
        """
        Initialize topic helper with configurable prefix.

        Args:
            prefix: Topic prefix (default: "battery_hawk")
        """
        self.prefix = prefix
        self._topic_patterns = self._build_topic_patterns()

    def _build_topic_patterns(self) -> dict[str, TopicInfo]:
        """Build topic pattern definitions."""
        return {
            "device_reading": TopicInfo(
                pattern=f"{self.prefix}/device/{{mac}}/reading",
                description="Device reading updates with battery sensor data",
                qos=1,  # Important but not critical
                retain=False,  # Time-series data, don't retain
                example=f"{self.prefix}/device/AA:BB:CC:DD:EE:FF/reading",
            ),
            "device_status": TopicInfo(
                pattern=f"{self.prefix}/device/{{mac}}/status",
                description="Device connection and operational status",
                qos=1,  # Important for monitoring
                retain=True,  # Retain last known status
                example=f"{self.prefix}/device/AA:BB:CC:DD:EE:FF/status",
            ),
            "vehicle_summary": TopicInfo(
                pattern=f"{self.prefix}/vehicle/{{id}}/summary",
                description="Vehicle summary data with aggregated metrics",
                qos=1,  # Important for dashboards
                retain=True,  # Retain last known summary
                example=f"{self.prefix}/vehicle/my_vehicle/summary",
            ),
            "system_status": TopicInfo(
                pattern=f"{self.prefix}/system/status",
                description="System status and health information",
                qos=2,  # Critical system information
                retain=True,  # Retain last known system state
                example=f"{self.prefix}/system/status",
            ),
            "discovery_found": TopicInfo(
                pattern=f"{self.prefix}/discovery/found",
                description="New device discovery notifications",
                qos=1,  # Important for device management
                retain=False,  # Event-based, don't retain
                example=f"{self.prefix}/discovery/found",
            ),
        }

    # Device Topics
    def device_reading(self, mac_address: str) -> str:
        """Get device reading topic for specific MAC address."""
        return f"{self.prefix}/device/{mac_address}/reading"

    def device_status(self, mac_address: str) -> str:
        """Get device status topic for specific MAC address."""
        return f"{self.prefix}/device/{mac_address}/status"

    def device_wildcard(self, mac_address: str = "+") -> str:
        """Get device wildcard topic for subscription."""
        return f"{self.prefix}/device/{mac_address}/+"

    def all_device_readings(self) -> str:
        """Get wildcard topic for all device readings."""
        return f"{self.prefix}/device/+/reading"

    def all_device_status(self) -> str:
        """Get wildcard topic for all device status updates."""
        return f"{self.prefix}/device/+/status"

    # Vehicle Topics
    def vehicle_summary(self, vehicle_id: str) -> str:
        """Get vehicle summary topic for specific vehicle ID."""
        return f"{self.prefix}/vehicle/{vehicle_id}/summary"

    def all_vehicle_summaries(self) -> str:
        """Get wildcard topic for all vehicle summaries."""
        return f"{self.prefix}/vehicle/+/summary"

    # System Topics
    def system_status(self) -> str:
        """Get system status topic."""
        return f"{self.prefix}/system/status"

    # Discovery Topics
    def discovery_found(self) -> str:
        """Get discovery found topic."""
        return f"{self.prefix}/discovery/found"

    # Subscription Patterns
    def all_topics(self) -> str:
        """Get wildcard topic for all Battery Hawk topics."""
        return f"{self.prefix}/+"

    def all_topics_recursive(self) -> str:
        """Get recursive wildcard topic for all Battery Hawk topics."""
        return f"{self.prefix}/#"

    # Topic Analysis
    def parse_topic(self, topic: str) -> dict[str, Any] | None:
        """
        Parse a topic and extract information.

        Args:
            topic: Full topic string to parse

        Returns:
            Dictionary with topic information or None if not recognized
        """
        # Remove prefix if present
        if topic.startswith(f"{self.prefix}/"):
            topic_path = topic[len(f"{self.prefix}/") :]
        else:
            return None

        # Parse different topic types
        parts = topic_path.split("/")

        # Constants for topic parsing
        min_device_parts = 3
        min_vehicle_parts = 3
        min_system_parts = 2
        min_discovery_parts = 2

        if len(parts) >= min_device_parts and parts[0] == "device":
            mac_address = parts[1]
            topic_type = parts[2]
            return {
                "category": "device",
                "mac_address": mac_address,
                "topic_type": topic_type,
                "full_topic": topic,
                "qos": self._get_qos_for_topic_type(f"device_{topic_type}"),
                "retain": self._get_retain_for_topic_type(f"device_{topic_type}"),
            }

        if len(parts) >= min_vehicle_parts and parts[0] == "vehicle":
            vehicle_id = parts[1]
            topic_type = parts[2]
            return {
                "category": "vehicle",
                "vehicle_id": vehicle_id,
                "topic_type": topic_type,
                "full_topic": topic,
                "qos": self._get_qos_for_topic_type(f"vehicle_{topic_type}"),
                "retain": self._get_retain_for_topic_type(f"vehicle_{topic_type}"),
            }

        if len(parts) >= min_system_parts and parts[0] == "system":
            topic_type = parts[1]
            return {
                "category": "system",
                "topic_type": topic_type,
                "full_topic": topic,
                "qos": self._get_qos_for_topic_type(f"system_{topic_type}"),
                "retain": self._get_retain_for_topic_type(f"system_{topic_type}"),
            }

        if len(parts) >= min_discovery_parts and parts[0] == "discovery":
            topic_type = parts[1]
            return {
                "category": "discovery",
                "topic_type": topic_type,
                "full_topic": topic,
                "qos": self._get_qos_for_topic_type(f"discovery_{topic_type}"),
                "retain": self._get_retain_for_topic_type(f"discovery_{topic_type}"),
            }

        return None

    def _get_qos_for_topic_type(self, topic_type: str) -> int:
        """Get QoS level for topic type."""
        topic_info = self._topic_patterns.get(topic_type)
        return topic_info.qos if topic_info else 1

    def _get_retain_for_topic_type(self, topic_type: str) -> bool:
        """Get retain flag for topic type."""
        topic_info = self._topic_patterns.get(topic_type)
        return topic_info.retain if topic_info else False

    def get_topic_info(self, topic_type: str) -> TopicInfo | None:
        """Get topic information for a specific topic type."""
        return self._topic_patterns.get(topic_type)

    def list_all_patterns(self) -> dict[str, TopicInfo]:
        """Get all topic patterns and their information."""
        return self._topic_patterns.copy()

    def validate_mac_address(self, mac_address: str) -> bool:
        """Validate MAC address format."""
        mac_pattern = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")
        return bool(mac_pattern.match(mac_address))

    def validate_vehicle_id(self, vehicle_id: str) -> bool:
        """Validate vehicle ID format."""
        # Vehicle IDs should be alphanumeric with underscores/hyphens
        return bool(re.match(r"^[a-zA-Z0-9_-]+$", vehicle_id))

    def is_battery_hawk_topic(self, topic: str) -> bool:
        """Check if topic belongs to Battery Hawk."""
        return topic.startswith(f"{self.prefix}/")

    def get_subscription_topics(self) -> list[str]:
        """Get list of topics for subscribing to all Battery Hawk messages."""
        return [
            self.all_device_readings(),
            self.all_device_status(),
            self.all_vehicle_summaries(),
            self.system_status(),
            self.discovery_found(),
        ]


# Default instance with standard prefix
default_topics = MQTTTopics()


# Convenience functions using default instance
def device_reading_topic(mac_address: str) -> str:
    """Get device reading topic."""
    return default_topics.device_reading(mac_address)


def device_status_topic(mac_address: str) -> str:
    """Get device status topic."""
    return default_topics.device_status(mac_address)


def vehicle_summary_topic(vehicle_id: str) -> str:
    """Get vehicle summary topic."""
    return default_topics.vehicle_summary(vehicle_id)


def system_status_topic() -> str:
    """Get system status topic."""
    return default_topics.system_status()


def discovery_found_topic() -> str:
    """Get discovery found topic."""
    return default_topics.discovery_found()
