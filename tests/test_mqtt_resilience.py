"""Tests for MQTT resilience and reconnection functionality."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from battery_hawk.mqtt.client import (
    ConnectionState,
    MQTTConnectionError,
    MQTTInterface,
    QueuedMessage,
    ReconnectionConfig,
)
from tests.test_mqtt import MockConfigManager


class TestMQTTResilience:
    """Test MQTT resilience features."""

    @pytest.fixture
    def mock_config_manager(self) -> MockConfigManager:
        """Create a mock configuration manager with resilience settings."""
        config_manager = MockConfigManager()
        # Add resilience configuration
        config_manager.configs["system"]["mqtt"].update({
            "max_retries": 3,
            "initial_retry_delay": 0.1,  # Fast for testing
            "max_retry_delay": 1.0,
            "backoff_multiplier": 2.0,
            "jitter_factor": 0.1,
            "connection_timeout": 5.0,
            "health_check_interval": 1.0,  # Fast for testing
            "message_queue_size": 10,
            "message_retry_limit": 2,
        })
        return config_manager

    @pytest.fixture
    def mqtt_interface(self, mock_config_manager: MockConfigManager) -> MQTTInterface:
        """Create MQTT interface with mock configuration."""
        return MQTTInterface(mock_config_manager)

    def test_reconnection_config_creation(self, mqtt_interface: MQTTInterface) -> None:
        """Test reconnection configuration is created correctly."""
        config = mqtt_interface._reconnection_config
        
        assert isinstance(config, ReconnectionConfig)
        assert config.max_retries == 3
        assert config.initial_retry_delay == 0.1
        assert config.max_retry_delay == 1.0
        assert config.message_queue_size == 10

    def test_initial_connection_state(self, mqtt_interface: MQTTInterface) -> None:
        """Test initial connection state."""
        assert mqtt_interface.connection_state == ConnectionState.DISCONNECTED
        assert not mqtt_interface.connected
        assert len(mqtt_interface._message_queue) == 0

    def test_stats_property(self, mqtt_interface: MQTTInterface) -> None:
        """Test stats property returns correct information."""
        stats = mqtt_interface.stats
        
        assert "connection_state" in stats
        assert "consecutive_failures" in stats
        assert "queue_size" in stats
        assert "total_connections" in stats
        assert "messages_published" in stats
        assert "messages_queued" in stats
        assert "messages_failed" in stats

    def test_calculate_retry_delay(self, mqtt_interface: MQTTInterface) -> None:
        """Test retry delay calculation with exponential backoff."""
        # Test exponential backoff
        delay1 = mqtt_interface._calculate_retry_delay(0)
        delay2 = mqtt_interface._calculate_retry_delay(1)
        delay3 = mqtt_interface._calculate_retry_delay(2)
        
        # Should increase exponentially (with some jitter)
        assert delay1 < delay2 < delay3
        assert delay1 >= 0.1  # Minimum delay
        
        # Test max delay cap (allow for small jitter variance)
        large_delay = mqtt_interface._calculate_retry_delay(10)
        max_allowed = mqtt_interface._reconnection_config.max_retry_delay * 1.1  # 10% tolerance for jitter
        assert large_delay <= max_allowed

    @pytest.mark.asyncio
    async def test_message_queuing(self, mqtt_interface: MQTTInterface) -> None:
        """Test message queuing when not connected."""
        # Publish message when not connected
        await mqtt_interface.publish("test/topic", {"message": "test"})
        
        # Message should be queued
        assert len(mqtt_interface._message_queue) == 1
        assert mqtt_interface.stats["messages_queued"] == 1
        
        queued_msg = mqtt_interface._message_queue[0]
        assert queued_msg.topic == "test/topic"
        assert queued_msg.payload == {"message": "test"}
        assert queued_msg.retry_count == 0

    @pytest.mark.asyncio
    async def test_queue_overflow(self, mqtt_interface: MQTTInterface) -> None:
        """Test message queue overflow handling."""
        # Fill queue beyond capacity
        queue_size = mqtt_interface._reconnection_config.message_queue_size
        
        for i in range(queue_size + 5):
            await mqtt_interface.publish(f"test/topic/{i}", {"message": i})
        
        # Queue should be at max capacity
        assert len(mqtt_interface._message_queue) == queue_size
        
        # First messages should have been dropped
        first_msg = mqtt_interface._message_queue[0]
        assert "5" in first_msg.topic  # Message 0-4 should be dropped

    @pytest.mark.asyncio
    async def test_connection_state_transitions(self, mqtt_interface: MQTTInterface) -> None:
        """Test connection state transitions."""
        # Start disconnected
        assert mqtt_interface.connection_state == ConnectionState.DISCONNECTED
        
        # Mock successful connection
        with patch.object(mqtt_interface, '_connect_with_retry') as mock_connect:
            mock_connect.return_value = None
            mqtt_interface._connection_state = ConnectionState.CONNECTED
            
            assert mqtt_interface.connected
            assert mqtt_interface.connection_state == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_publish_with_immediate_success(self, mqtt_interface: MQTTInterface) -> None:
        """Test publishing when connected succeeds immediately."""
        # Mock connected state and client
        mqtt_interface._connection_state = ConnectionState.CONNECTED
        mock_client = MagicMock()
        mock_client.publish = AsyncMock()
        mqtt_interface._client = mock_client
        
        # Publish message
        await mqtt_interface.publish("test/topic", {"message": "test"})
        
        # Should publish immediately, not queue
        assert len(mqtt_interface._message_queue) == 0
        assert mqtt_interface.stats["messages_published"] == 1
        assert mqtt_interface.stats["messages_queued"] == 0
        
        # Verify client.publish was called
        mock_client.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_with_connection_error(self, mqtt_interface: MQTTInterface) -> None:
        """Test publishing when connection error occurs."""
        # Mock connected state and client that fails
        mqtt_interface._connection_state = ConnectionState.CONNECTED
        mock_client = MagicMock()
        mock_client.publish = AsyncMock(side_effect=ConnectionError("Connection lost"))
        mqtt_interface._client = mock_client
        
        # Mock the reconnection method
        with patch.object(mqtt_interface, '_initiate_reconnection') as mock_reconnect:
            mock_reconnect.return_value = None
            
            # Publish message
            await mqtt_interface.publish("test/topic", {"message": "test"})
            
            # Should queue message and initiate reconnection
            assert len(mqtt_interface._message_queue) == 1
            assert mqtt_interface.stats["messages_queued"] == 1
            mock_reconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_message_queue_processing(self, mqtt_interface: MQTTInterface) -> None:
        """Test processing of queued messages."""
        # Add messages to queue
        msg1 = QueuedMessage("test/topic1", {"msg": 1}, False, 0.0)
        msg2 = QueuedMessage("test/topic2", {"msg": 2}, True, 0.0)
        mqtt_interface._message_queue.extend([msg1, msg2])
        
        # Mock connected state and successful publishing
        mqtt_interface._connection_state = ConnectionState.CONNECTED
        mock_client = MagicMock()
        mock_client.publish = AsyncMock()
        mqtt_interface._client = mock_client
        
        # Process queue
        await mqtt_interface._process_message_queue()
        
        # Queue should be empty
        assert len(mqtt_interface._message_queue) == 0
        
        # Both messages should have been published
        assert mock_client.publish.call_count == 2

    @pytest.mark.asyncio
    async def test_message_retry_logic(self, mqtt_interface: MQTTInterface) -> None:
        """Test message retry logic on connection errors."""
        # Add message to queue
        msg = QueuedMessage("test/topic", {"msg": 1}, False, 0.0)
        mqtt_interface._message_queue.append(msg)
        
        # Mock connected state but failing publish
        mqtt_interface._connection_state = ConnectionState.CONNECTED
        mock_client = MagicMock()
        mock_client.publish = AsyncMock(side_effect=ConnectionError("Connection lost"))
        mqtt_interface._client = mock_client
        
        # Process queue
        await mqtt_interface._process_message_queue()
        
        # Message should be requeued with incremented retry count
        assert len(mqtt_interface._message_queue) == 1
        requeued_msg = mqtt_interface._message_queue[0]
        assert requeued_msg.retry_count == 1

    @pytest.mark.asyncio
    async def test_message_retry_limit(self, mqtt_interface: MQTTInterface) -> None:
        """Test message is dropped after retry limit."""
        # Add message with max retries already reached
        msg = QueuedMessage("test/topic", {"msg": 1}, False, 0.0)
        msg.retry_count = mqtt_interface._reconnection_config.message_retry_limit + 1
        mqtt_interface._message_queue.append(msg)
        
        # Mock connected state but failing publish
        mqtt_interface._connection_state = ConnectionState.CONNECTED
        mock_client = MagicMock()
        mock_client.publish = AsyncMock(side_effect=ConnectionError("Connection lost"))
        mqtt_interface._client = mock_client
        
        # Process queue
        await mqtt_interface._process_message_queue()
        
        # Message should be dropped
        assert len(mqtt_interface._message_queue) == 0
        assert mqtt_interface.stats["messages_failed"] == 1

    @pytest.mark.asyncio
    async def test_serialization_error_handling(self, mqtt_interface: MQTTInterface) -> None:
        """Test handling of serialization errors."""
        # Create message with payload that will cause JSON serialization error
        class NonSerializable:
            def __str__(self):
                raise ValueError("Cannot serialize this object")

        # Create a dict payload that contains non-serializable object
        msg = QueuedMessage("test/topic", {"data": NonSerializable()}, False, 0.0)
        mqtt_interface._message_queue.append(msg)

        # Mock connected state
        mqtt_interface._connection_state = ConnectionState.CONNECTED
        mock_client = MagicMock()
        mock_client.publish = AsyncMock()
        mqtt_interface._client = mock_client

        # Process queue
        await mqtt_interface._process_message_queue()

        # Message should be dropped due to serialization error
        assert len(mqtt_interface._message_queue) == 0
        assert mqtt_interface.stats["messages_failed"] == 1

    @pytest.mark.asyncio
    async def test_shutdown_handling(self, mqtt_interface: MQTTInterface) -> None:
        """Test proper shutdown handling."""
        # Set shutdown event
        mqtt_interface._shutdown_event.set()
        
        # Try to connect - should abort
        await mqtt_interface.connect()
        
        # Should remain disconnected
        assert mqtt_interface.connection_state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_disconnect_cleanup(self, mqtt_interface: MQTTInterface) -> None:
        """Test disconnect properly cleans up resources."""
        # Mock some background tasks
        mqtt_interface._reconnect_task = asyncio.create_task(asyncio.sleep(10))
        mqtt_interface._health_check_task = asyncio.create_task(asyncio.sleep(10))
        mqtt_interface._message_processor_task = asyncio.create_task(asyncio.sleep(10))
        
        # Mock client
        mock_client = MagicMock()
        mock_client.__aexit__ = AsyncMock()
        mqtt_interface._client = mock_client
        mqtt_interface._connection_state = ConnectionState.CONNECTED
        
        # Disconnect
        await mqtt_interface.disconnect()
        
        # All tasks should be cancelled
        assert mqtt_interface._reconnect_task.cancelled()
        assert mqtt_interface._health_check_task.cancelled()
        assert mqtt_interface._message_processor_task.cancelled()
        
        # Client should be disconnected
        mock_client.__aexit__.assert_called_once()
        
        # State should be disconnected
        assert mqtt_interface.connection_state == ConnectionState.DISCONNECTED

    def test_config_change_detection(self, mqtt_interface: MQTTInterface) -> None:
        """Test configuration change detection logic."""
        # Store original config
        original_config = mqtt_interface._mqtt_config.copy()

        # Update config manager with new broker
        mqtt_interface.config_manager.configs["system"]["mqtt"]["broker"] = "new-broker"

        # Manually call config update (without triggering reconnection)
        mqtt_interface._mqtt_config = mqtt_interface._get_mqtt_config()

        # Verify config was updated
        assert mqtt_interface._mqtt_config["broker"] == "new-broker"
        assert mqtt_interface._mqtt_config["broker"] != original_config["broker"]

    def test_queued_message_dataclass(self) -> None:
        """Test QueuedMessage dataclass."""
        msg = QueuedMessage(
            topic="test/topic",
            payload={"test": "data"},
            retain=True,
            timestamp=123456.0,
            retry_count=2,
        )
        
        assert msg.topic == "test/topic"
        assert msg.payload == {"test": "data"}
        assert msg.retain is True
        assert msg.timestamp == 123456.0
        assert msg.retry_count == 2

    def test_reconnection_config_dataclass(self) -> None:
        """Test ReconnectionConfig dataclass."""
        config = ReconnectionConfig(
            max_retries=5,
            initial_retry_delay=2.0,
            max_retry_delay=60.0,
            backoff_multiplier=1.5,
            jitter_factor=0.2,
            connection_timeout=15.0,
            health_check_interval=30.0,
            message_queue_size=500,
            message_retry_limit=5,
        )
        
        assert config.max_retries == 5
        assert config.initial_retry_delay == 2.0
        assert config.max_retry_delay == 60.0
        assert config.backoff_multiplier == 1.5
        assert config.jitter_factor == 0.2
        assert config.connection_timeout == 15.0
        assert config.health_check_interval == 30.0
        assert config.message_queue_size == 500
        assert config.message_retry_limit == 5
