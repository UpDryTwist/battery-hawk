"""Tests for MQTT interface."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from battery_hawk.config.config_manager import ConfigManager
from battery_hawk.mqtt import MQTTConnectionError, MQTTInterface


class MockConfigManager(ConfigManager):
    """Mock configuration manager for testing."""

    def __init__(self, config_dir: str = "/data") -> None:
        """Initialize mock configuration manager with test data."""
        self.config_dir = config_dir
        self._listeners: list = []
        self.logger = logging.getLogger("battery_hawk.config")
        self._enable_watchers = False
        self.configs = {
            "system": {
                "version": "1.0",
                "logging": {"level": "INFO"},
                "bluetooth": {"max_concurrent_connections": 3, "test_mode": False},
                "discovery": {"initial_scan": True, "scan_duration": 10},
                "influxdb": {"enabled": False},
                "mqtt": {
                    "enabled": True,
                    "broker": "localhost",
                    "port": 1883,
                    "username": "test_user",
                    "password": "test_pass",
                    "topic_prefix": "test_batteryhawk",
                    "qos": 1,
                    "keepalive": 60,
                    "timeout": 10,
                    "retries": 3,
                    "tls": False,
                    # Retry configuration for fast tests
                    "max_retries": 0,  # No retries for tests
                    "initial_retry_delay": 0.01,
                    "max_retry_delay": 0.01,
                    "backoff_multiplier": 1.0,
                    "jitter_factor": 0.0,
                    "connection_timeout": 1.0,
                    "health_check_interval": 1.0,
                    "message_queue_size": 100,
                    "message_retry_limit": 1,
                },
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
        self._listeners = []

    def add_listener(self, listener: Callable[[str, dict[str, Any]], None]) -> None:
        """Add configuration change listener."""
        self._listeners.append(listener)

    def _notify_listeners(self, section: str, config: dict[str, Any]) -> None:
        """Notify listeners of configuration changes."""
        for listener in self._listeners:
            listener(section, config)


@pytest.fixture
def mock_config_manager() -> MockConfigManager:
    """Create mock configuration manager."""
    return MockConfigManager()


@pytest.fixture
def mqtt_interface(mock_config_manager: MockConfigManager) -> MQTTInterface:
    """Create MQTT interface with mock config."""
    return MQTTInterface(mock_config_manager)


@pytest.fixture
def disabled_mqtt_config_manager() -> MockConfigManager:
    """Create mock configuration manager with MQTT disabled."""
    config_manager = MockConfigManager()
    config_manager.configs["system"]["mqtt"]["enabled"] = False
    return config_manager


@pytest.fixture
def retry_mqtt_config_manager() -> MockConfigManager:
    """Create mock configuration manager with retry enabled for testing."""
    config_manager = MockConfigManager()
    # Enable retries for retry tests
    config_manager.configs["system"]["mqtt"]["max_retries"] = 2
    config_manager.configs["system"]["mqtt"]["initial_retry_delay"] = 0.01
    return config_manager


class TestMQTTInterface:
    """Test MQTT interface functionality."""

    def test_init(self, mqtt_interface: MQTTInterface) -> None:
        """Test MQTT interface initialization."""
        assert mqtt_interface.config_manager is not None
        assert mqtt_interface.logger is not None
        assert not mqtt_interface.connected
        assert mqtt_interface._client is None

    def test_get_mqtt_config_valid(self, mqtt_interface: MQTTInterface) -> None:
        """Test getting valid MQTT configuration."""
        config = mqtt_interface._get_mqtt_config()
        assert config["enabled"] is True
        assert config["broker"] == "localhost"
        assert config["port"] == 1883
        assert config["topic_prefix"] == "test_batteryhawk"

    def test_get_mqtt_config_disabled(self, disabled_mqtt_config_manager: MockConfigManager) -> None:
        """Test getting MQTT configuration when disabled."""
        mqtt_interface = MQTTInterface(disabled_mqtt_config_manager)
        config = mqtt_interface._get_mqtt_config()
        assert config["enabled"] is False

    def test_get_mqtt_config_missing_fields(self, mock_config_manager: MockConfigManager) -> None:
        """Test configuration validation with missing fields."""
        # Remove required field
        del mock_config_manager.configs["system"]["mqtt"]["broker"]

        with pytest.raises(ValueError, match="Missing required MQTT configuration fields"):
            MQTTInterface(mock_config_manager)

    def test_get_mqtt_config_invalid_port(self, mock_config_manager: MockConfigManager) -> None:
        """Test configuration validation with invalid port."""
        mock_config_manager.configs["system"]["mqtt"]["port"] = 70000

        with pytest.raises(ValueError, match="Invalid MQTT port"):
            MQTTInterface(mock_config_manager)

    def test_get_mqtt_config_invalid_qos(self, mock_config_manager: MockConfigManager) -> None:
        """Test configuration validation with invalid QoS."""
        mock_config_manager.configs["system"]["mqtt"]["qos"] = 5

        with pytest.raises(ValueError, match="Invalid MQTT QoS level"):
            MQTTInterface(mock_config_manager)

    def test_get_topic(self, mqtt_interface: MQTTInterface) -> None:
        """Test topic prefix functionality."""
        topic = mqtt_interface._get_topic("devices/status")
        assert topic == "test_batteryhawk/devices/status"

    @pytest.mark.asyncio
    async def test_connect_disabled(self, disabled_mqtt_config_manager: MockConfigManager) -> None:
        """Test connection when MQTT is disabled."""
        mqtt_interface = MQTTInterface(disabled_mqtt_config_manager)
        await mqtt_interface.connect()
        assert not mqtt_interface.connected

    @pytest.mark.asyncio
    @patch("battery_hawk.mqtt.client.Client")
    async def test_connect_success(self, mock_client_class: MagicMock, mqtt_interface: MQTTInterface) -> None:
        """Test successful MQTT connection."""
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        await mqtt_interface.connect()

        assert mqtt_interface.connected
        mock_client.__aenter__.assert_called_once()

    @pytest.mark.asyncio
    @patch("battery_hawk.mqtt.client.Client")
    async def test_connect_failure(self, mock_client_class: MagicMock, mqtt_interface: MQTTInterface) -> None:
        """Test MQTT connection failure."""
        mock_client = AsyncMock()
        mock_client.__aenter__.side_effect = OSError("Connection failed")
        mock_client_class.return_value = mock_client

        with pytest.raises(MQTTConnectionError, match="Failed to connect to MQTT broker"):
            await mqtt_interface.connect()

        assert not mqtt_interface.connected

    @pytest.mark.asyncio
    @patch("battery_hawk.mqtt.client.Client")
    async def test_connect_retry(self, mock_client_class: MagicMock, retry_mqtt_config_manager: MockConfigManager) -> None:
        """Test MQTT connection with retry."""
        mqtt_interface = MQTTInterface(retry_mqtt_config_manager)
        mock_client = AsyncMock()
        # Fail first attempt, succeed second
        mock_client.__aenter__.side_effect = [OSError("Connection failed"), None]
        mock_client_class.return_value = mock_client

        await mqtt_interface.connect()

        assert mqtt_interface.connected
        assert mock_client.__aenter__.call_count == 2

    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self, mqtt_interface: MQTTInterface) -> None:
        """Test disconnect when not connected."""
        await mqtt_interface.disconnect()
        assert not mqtt_interface.connected

    @pytest.mark.asyncio
    @patch("battery_hawk.mqtt.client.Client")
    async def test_disconnect_success(self, mock_client_class: MagicMock, mqtt_interface: MQTTInterface) -> None:
        """Test successful disconnect."""
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        # Connect first
        await mqtt_interface.connect()
        assert mqtt_interface.connected

        # Then disconnect
        await mqtt_interface.disconnect()

        assert not mqtt_interface.connected
        mock_client.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_not_connected(self, mqtt_interface: MQTTInterface) -> None:
        """Test publish when not connected - should queue message."""
        # Publish should not raise exception but queue the message
        await mqtt_interface.publish("test/topic", {"message": "test"})

        # Message should be queued
        assert len(mqtt_interface._message_queue) == 1
        queued_msg = mqtt_interface._message_queue[0]
        assert queued_msg.topic == "test/topic"
        assert queued_msg.payload == {"message": "test"}

    @pytest.mark.asyncio
    @patch("battery_hawk.mqtt.client.Client")
    async def test_publish_success(self, mock_client_class: MagicMock, mqtt_interface: MQTTInterface) -> None:
        """Test successful message publish."""
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        # Connect first
        await mqtt_interface.connect()

        # Publish message
        payload = {"device": "test", "status": "online"}
        await mqtt_interface.publish("devices/status", payload)

        mock_client.publish.assert_called_once()
        args, kwargs = mock_client.publish.call_args
        assert args[0] == "test_batteryhawk/devices/status"
        assert json.loads(args[1]) == payload
        assert kwargs["qos"] == 1

    @pytest.mark.asyncio
    async def test_subscribe_not_connected(self, mqtt_interface: MQTTInterface) -> None:
        """Test subscribe when not connected."""
        handler = MagicMock()

        with pytest.raises(MQTTConnectionError, match="Not connected to MQTT broker"):
            await mqtt_interface.subscribe("test/topic", handler)

    @pytest.mark.asyncio
    @patch("battery_hawk.mqtt.client.Client")
    async def test_subscribe_success(self, mock_client_class: MagicMock, mqtt_interface: MQTTInterface) -> None:
        """Test successful topic subscription."""
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        handler = MagicMock()

        # Connect first
        await mqtt_interface.connect()

        # Subscribe to topic
        await mqtt_interface.subscribe("devices/status", handler)

        mock_client.subscribe.assert_called_once_with("test_batteryhawk/devices/status", qos=1)
        assert "test_batteryhawk/devices/status" in mqtt_interface._message_handlers

    def test_config_change_handler(self, mqtt_interface: MQTTInterface) -> None:
        """Test configuration change handling."""
        # Simulate config change
        new_config = mqtt_interface.config_manager.configs["system"].copy()
        new_config["mqtt"]["broker"] = "new-broker"

        mqtt_interface._on_config_change("system", new_config)

        # Config should be updated
        assert mqtt_interface._mqtt_config["broker"] == "new-broker"
