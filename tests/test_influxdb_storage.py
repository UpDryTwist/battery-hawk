"""
Tests for InfluxDB storage implementation.

This module tests the DataStorage class with InfluxDB backend functionality
including connection handling, data writing, and querying.
"""

import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from battery_hawk.core.storage import DataStorage


class MockConfigManager:
    """Mock configuration manager for testing."""

    def __init__(self, influxdb_enabled: bool = True) -> None:
        """Initialize mock configuration manager."""
        self.configs = {
            "system": {
                "version": "1.0",
                "influxdb": {
                    "enabled": influxdb_enabled,
                    "host": "localhost",
                    "port": 8086,
                    "database": "test_battery_hawk",
                    "username": "test_user",
                    "password": "test_pass",
                    "timeout": 5000,
                    "retries": 2,
                    "error_recovery": {
                        "max_retry_attempts": 3,
                        "retry_delay_seconds": 1.0,
                        "retry_backoff_multiplier": 2.0,
                        "max_retry_delay_seconds": 60.0,
                        "buffer_max_size": 10000,
                        "buffer_flush_interval_seconds": 30.0,
                        "connection_timeout_seconds": 30.0,
                        "health_check_interval_seconds": 60.0,
                    },
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

    def get_config(self, section: str) -> dict:
        """Get configuration section."""
        return self.configs.get(section, {})


@pytest.fixture
def mock_config_manager() -> MockConfigManager:
    """Fixture for mock configuration manager."""
    return MockConfigManager()


@pytest.fixture
def mock_config_manager_disabled() -> MockConfigManager:
    """Fixture for mock configuration manager with InfluxDB disabled."""
    return MockConfigManager(influxdb_enabled=False)


@pytest.mark.asyncio
class TestDataStorageInfluxDB:
    """Test cases for DataStorage with InfluxDB backend."""

    async def test_initialization_disabled(
        self,
        mock_config_manager_disabled: Any,
    ) -> None:
        """Test DataStorage initialization with InfluxDB disabled."""
        storage = DataStorage(mock_config_manager_disabled)
        assert storage.client is None
        assert not storage.connected

    @patch("battery_hawk.core.storage.InfluxDBClient")
    async def test_connect_success(
        self,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test successful connection to InfluxDB."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_client_instance.ping = MagicMock()
        mock_client_instance.create_database = MagicMock()
        mock_client_instance.write_api.return_value = MagicMock()
        mock_client_instance.query_api.return_value = MagicMock()
        mock_influx_client.return_value = mock_client_instance

        storage = DataStorage(mock_config_manager)
        result = await storage.connect()

        assert result is True
        assert storage.connected is True
        assert storage.client is not None
        mock_influx_client.assert_called_once()
        mock_client_instance.ping.assert_called_once()

    @patch("battery_hawk.core.storage.InfluxDBClient")
    async def test_connect_failure(
        self,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test connection failure to InfluxDB."""
        # Setup mocks to raise exception
        mock_influx_client.side_effect = Exception("Connection failed")

        storage = DataStorage(mock_config_manager)
        result = await storage.connect()

        assert result is False
        assert storage.connected is False
        assert storage.client is None

    async def test_connect_disabled(self, mock_config_manager_disabled: Any) -> None:
        """Test connection when InfluxDB is disabled."""
        storage = DataStorage(mock_config_manager_disabled)
        result = await storage.connect()

        assert result is True
        assert storage.connected is False
        assert storage.client is None

    @patch("battery_hawk.core.storage.InfluxDBClient")
    async def test_store_reading_success(
        self,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test successful storage of battery reading."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_write_api = MagicMock()
        mock_client_instance.ping = MagicMock()
        mock_client_instance.create_database = MagicMock()
        mock_client_instance.write_api.return_value = mock_write_api
        mock_client_instance.query_api.return_value = MagicMock()
        mock_influx_client.return_value = mock_client_instance

        storage = DataStorage(mock_config_manager)
        await storage.connect()

        # Test data
        device_id = "AA:BB:CC:DD:EE:FF"
        vehicle_id = "vehicle_1"
        device_type = "BM6"
        reading = {
            "voltage": 12.5,
            "current": 2.3,
            "temperature": 25.0,
        }

        result = await storage.store_reading(
            device_id,
            vehicle_id,
            device_type,
            reading,
        )

        assert result is True
        mock_write_api.write.assert_called_once()

    async def test_store_reading_not_connected(
        self,
        mock_config_manager: Any,
    ) -> None:
        """Test storage when not connected (should buffer)."""
        storage = DataStorage(mock_config_manager)
        # Don't connect

        result = await storage.store_reading("device", "vehicle", "BM6", {})

        # With error handling, readings are buffered when not connected
        assert result is True
        assert len(storage._reading_buffer) == 1

    @patch("battery_hawk.core.storage.InfluxDBClient")
    async def test_get_recent_readings_success(
        self,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test successful retrieval of recent readings."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_query_api = MagicMock()
        mock_result = MagicMock()
        mock_result.get_points.return_value = [
            {"time": "2023-01-01T00:00:00Z", "voltage": 12.5, "current": 2.3},
            {"time": "2023-01-01T01:00:00Z", "voltage": 12.4, "current": 2.1},
        ]
        mock_query_api.query.return_value = mock_result
        mock_client_instance.ping = MagicMock()
        mock_client_instance.create_database = MagicMock()
        mock_client_instance.write_api.return_value = MagicMock()
        mock_client_instance.query_api.return_value = mock_query_api
        mock_influx_client.return_value = mock_client_instance

        storage = DataStorage(mock_config_manager)
        await storage.connect()

        result = await storage.get_recent_readings("AA:BB:CC:DD:EE:FF", limit=10)

        assert len(result) == 2
        assert result[0]["voltage"] == 12.5
        # Verify that query was called (multiple times due to retention policies + actual query)
        assert mock_query_api.query.call_count >= 1

        # Verify the actual data query was made
        query_calls = [str(call) for call in mock_query_api.query.call_args_list]
        data_query_made = any("SELECT * FROM" in call for call in query_calls)
        assert data_query_made

    async def test_get_recent_readings_not_connected(
        self,
        mock_config_manager: Any,
    ) -> None:
        """Test reading retrieval when not connected."""
        storage = DataStorage(mock_config_manager)
        # Don't connect

        result = await storage.get_recent_readings("device")

        assert result == []

    @patch("battery_hawk.core.storage.InfluxDBClient")
    async def test_health_check_success(
        self,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test successful health check."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_client_instance.ping = MagicMock()
        mock_client_instance.create_database = MagicMock()
        mock_client_instance.write_api.return_value = MagicMock()
        mock_client_instance.query_api.return_value = MagicMock()
        mock_influx_client.return_value = mock_client_instance

        storage = DataStorage(mock_config_manager)
        await storage.connect()

        result = await storage.health_check()

        assert result is True

    @patch("battery_hawk.core.storage.InfluxDBClient")
    async def test_health_check_failure(
        self,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test health check failure."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_client_instance.ping.side_effect = Exception("Ping failed")
        mock_client_instance.create_database = MagicMock()
        mock_client_instance.write_api.return_value = MagicMock()
        mock_client_instance.query_api.return_value = MagicMock()
        mock_influx_client.return_value = mock_client_instance

        storage = DataStorage(mock_config_manager)
        await storage.connect()

        result = await storage.health_check()

        assert result is False
        assert storage.connected is False

    @patch("battery_hawk.core.storage.InfluxDBClient")
    async def test_disconnect(
        self,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test disconnection from InfluxDB."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_write_api = MagicMock()
        mock_client_instance.ping = MagicMock()
        mock_client_instance.create_database = MagicMock()
        mock_client_instance.write_api.return_value = mock_write_api
        mock_client_instance.query_api.return_value = MagicMock()
        mock_influx_client.return_value = mock_client_instance

        storage = DataStorage(mock_config_manager)
        await storage.connect()
        assert storage.connected is True

        await storage.disconnect()

        assert storage.connected is False
        assert storage.client is None
        mock_write_api.close.assert_called_once()
        mock_client_instance.close.assert_called_once()


@pytest.mark.asyncio
class TestInfluxDBRetentionPolicies:
    """Test cases for InfluxDB retention policy management."""

    @patch("battery_hawk.core.storage.InfluxDBClient")
    async def test_setup_retention_policies(
        self,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test setting up retention policies during connection."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_query_api = MagicMock()
        mock_client_instance.ping = MagicMock()
        mock_client_instance.write_api.return_value = MagicMock()
        mock_client_instance.query_api.return_value = mock_query_api
        mock_influx_client.return_value = mock_client_instance

        # Add retention policies to config
        mock_config_manager.configs["system"]["influxdb"]["retention_policies"] = {
            "default": {
                "name": "autogen",
                "duration": "30d",
                "replication": 1,
                "shard_duration": "1d",
                "default": True,
            },
            "long_term": {
                "name": "long_term",
                "duration": "365d",
                "replication": 1,
                "shard_duration": "7d",
                "default": False,
            },
        }

        storage = DataStorage(mock_config_manager)
        result = await storage.connect()

        assert result is True
        # Verify retention policy queries were executed
        assert mock_query_api.query.call_count >= 2  # At least 2 policies created

    @patch("battery_hawk.core.storage.InfluxDBClient")
    async def test_get_retention_policies(
        self,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test retrieving retention policies."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_query_api = MagicMock()
        mock_result = MagicMock()
        mock_result.get_points.return_value = [
            {"name": "autogen", "duration": "0s", "replicaN": 1, "default": True},
            {
                "name": "long_term",
                "duration": "8760h0m0s",
                "replicaN": 1,
                "default": False,
            },
        ]
        mock_query_api.query.return_value = mock_result
        mock_client_instance.ping = MagicMock()
        mock_client_instance.write_api.return_value = MagicMock()
        mock_client_instance.query_api.return_value = mock_query_api
        mock_influx_client.return_value = mock_client_instance

        storage = DataStorage(mock_config_manager)
        await storage.connect()

        policies = await storage.get_retention_policies("test_database")

        assert len(policies) == 2
        assert policies[0]["name"] == "autogen"
        assert policies[1]["name"] == "long_term"
        mock_query_api.query.assert_called()

    @patch("battery_hawk.core.storage.InfluxDBClient")
    async def test_drop_retention_policy(
        self,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test dropping a retention policy."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_query_api = MagicMock()
        mock_client_instance.ping = MagicMock()
        mock_client_instance.write_api.return_value = MagicMock()
        mock_client_instance.query_api.return_value = mock_query_api
        mock_influx_client.return_value = mock_client_instance

        storage = DataStorage(mock_config_manager)
        await storage.connect()

        result = await storage.drop_retention_policy("test_database", "old_policy")

        assert result is True
        mock_query_api.query.assert_called()
        # Verify DROP RETENTION POLICY query was called
        drop_call = None
        for call in mock_query_api.query.call_args_list:
            if "DROP RETENTION POLICY" in str(call):
                drop_call = call
                break
        assert drop_call is not None

    def test_get_retention_policy_for_measurement(
        self,
        mock_config_manager: Any,
    ) -> None:
        """Test retention policy selection for measurements."""
        # Add retention policies to config
        mock_config_manager.configs["system"]["influxdb"]["retention_policies"] = {
            "default": {
                "name": "autogen",
                "duration": "30d",
                "replication": 1,
                "default": True,
            },
            "short_term": {
                "name": "short_term",
                "duration": "7d",
                "replication": 1,
                "default": False,
            },
        }

        storage = DataStorage(mock_config_manager)

        # Test normal reading uses default policy
        normal_reading = {"voltage": 12.5, "current": 2.3, "temperature": 25.0}
        policy = storage._get_retention_policy_for_measurement(normal_reading)
        assert policy == "autogen"

        # Test high current reading uses short-term policy
        high_current_reading = {"voltage": 12.5, "current": 15.0, "temperature": 25.0}
        policy = storage._get_retention_policy_for_measurement(high_current_reading)
        assert policy == "short_term"

    @patch("battery_hawk.core.storage.InfluxDBClient")
    async def test_store_reading_with_retention_policy(
        self,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test storing readings with retention policy selection."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_write_api = MagicMock()
        mock_client_instance.ping = MagicMock()
        mock_client_instance.write_api.return_value = mock_write_api
        mock_client_instance.query_api.return_value = MagicMock()
        mock_influx_client.return_value = mock_client_instance

        # Add retention policies to config
        mock_config_manager.configs["system"]["influxdb"]["retention_policies"] = {
            "default": {
                "name": "autogen",
                "duration": "30d",
                "replication": 1,
                "default": True,
            },
        }

        storage = DataStorage(mock_config_manager)
        await storage.connect()

        # Test storing reading
        reading = {"voltage": 12.5, "current": 2.3, "temperature": 25.0}
        result = await storage.store_reading(
            "AA:BB:CC:DD:EE:FF",
            "vehicle_1",
            "BM6",
            reading,
        )

        assert result is True
        mock_write_api.write.assert_called_once()

        # Verify retention policy was passed to write call
        write_call_args = mock_write_api.write.call_args
        assert write_call_args[0][1] == "autogen"  # retention policy argument


@pytest.mark.asyncio
class TestInfluxDBErrorHandling:
    """Test cases for InfluxDB error handling and recovery."""

    @patch("battery_hawk.core.storage.InfluxDBClient")
    async def test_connection_retry_on_failure(
        self,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test connection retry logic on failure."""
        # Setup mocks to always fail
        mock_client_instance = MagicMock()
        mock_client_instance.ping.side_effect = ConnectionError("Connection failed")
        mock_client_instance.write_api.return_value = MagicMock()
        mock_client_instance.query_api.return_value = MagicMock()
        mock_influx_client.return_value = mock_client_instance

        # Configure shorter retry delays for testing
        mock_config_manager.configs["system"]["influxdb"]["error_recovery"] = {
            "max_retry_attempts": 2,
            "retry_delay_seconds": 0.1,
            "retry_backoff_multiplier": 1.0,
            "max_retry_delay_seconds": 1.0,
            "buffer_max_size": 100,
            "buffer_flush_interval_seconds": 1.0,
            "connection_timeout_seconds": 1.0,  # Short timeout for testing
            "health_check_interval_seconds": 10.0,
        }

        storage = DataStorage(mock_config_manager)

        # Connection attempt should fail
        result = await storage.connect()

        # Should fail and not be connected
        assert result is False
        assert storage.connected is False

        # Verify retry delay calculation works
        delay1 = storage._calculate_retry_delay(0)
        delay2 = storage._calculate_retry_delay(1)
        assert delay2 >= delay1  # Should increase with backoff

    @patch("battery_hawk.core.storage.InfluxDBClient")
    async def test_reading_buffering_when_disconnected(
        self,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test that readings are buffered when connection is lost."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_write_api = MagicMock()
        mock_client_instance.ping = MagicMock()
        mock_client_instance.write_api.return_value = mock_write_api
        mock_client_instance.query_api.return_value = MagicMock()
        mock_influx_client.return_value = mock_client_instance

        storage = DataStorage(mock_config_manager)

        # Test storing reading when not connected (should buffer)
        result = await storage.store_reading(
            "AA:BB:CC:DD:EE:FF",
            "vehicle_1",
            "BM6",
            {"voltage": 12.5, "current": 2.3},
        )

        assert result is True  # Should succeed (buffered)
        assert len(storage._reading_buffer) == 1

        # Verify buffered reading content
        buffered = storage._reading_buffer[0]
        assert buffered.device_id == "AA:BB:CC:DD:EE:FF"
        assert buffered.reading["voltage"] == 12.5

    @patch("battery_hawk.core.storage.InfluxDBClient")
    async def test_buffer_flush_on_reconnection(
        self,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test that buffered readings are flushed when connection is restored."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_write_api = MagicMock()
        mock_client_instance.ping = MagicMock()
        mock_client_instance.write_api.return_value = mock_write_api
        mock_client_instance.query_api.return_value = MagicMock()
        mock_influx_client.return_value = mock_client_instance

        storage = DataStorage(mock_config_manager)

        # Buffer some readings while disconnected
        await storage.store_reading("device1", "vehicle1", "BM6", {"voltage": 12.5})
        await storage.store_reading("device2", "vehicle1", "BM6", {"voltage": 12.4})

        assert len(storage._reading_buffer) == 2

        # Connect (should trigger buffer flush)
        await storage.connect()

        # Manually flush buffer to test
        await storage._flush_buffer()

        # Verify writes were called for buffered readings
        assert mock_write_api.write.call_count >= 2

    @patch("battery_hawk.core.storage.InfluxDBClient")
    async def test_write_timeout_handling(
        self,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test handling of write operation timeouts."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_write_api = MagicMock()

        # Make write operation hang (simulate timeout)
        def slow_write(*args: Any, **kwargs: Any) -> None:
            time.sleep(10)  # Longer than timeout

        mock_write_api.write.side_effect = slow_write
        mock_client_instance.ping = MagicMock()
        mock_client_instance.write_api.return_value = mock_write_api
        mock_client_instance.query_api.return_value = MagicMock()
        mock_influx_client.return_value = mock_client_instance

        # Configure short timeout for testing
        mock_config_manager.configs["system"]["influxdb"]["error_recovery"][
            "connection_timeout_seconds"
        ] = 0.1

        storage = DataStorage(mock_config_manager)
        await storage.connect()

        # This should timeout and buffer the reading
        result = await storage.store_reading(
            "AA:BB:CC:DD:EE:FF",
            "vehicle_1",
            "BM6",
            {"voltage": 12.5},
        )

        # Should fail direct write but succeed in buffering
        assert result is True
        assert len(storage._reading_buffer) == 1

    async def test_connection_error_detection(
        self,
        mock_config_manager: Any,
    ) -> None:
        """Test connection error detection logic."""
        storage = DataStorage(mock_config_manager)

        # Test various connection-related errors
        connection_errors = [
            ConnectionError("Connection refused"),
            Exception("connection timeout"),  # Changed to lowercase
            Exception("Network unreachable"),
            Exception("Connection reset by peer"),
            Exception("Broken pipe"),
        ]

        for error in connection_errors:
            assert storage._is_connection_error(error) is True

        # Test non-connection errors
        non_connection_errors = [
            ValueError("Invalid value"),
            KeyError("Missing key"),
            Exception("Some other error"),
        ]

        for error in non_connection_errors:
            assert storage._is_connection_error(error) is False

    async def test_retry_delay_calculation(self, mock_config_manager: Any) -> None:
        """Test exponential backoff retry delay calculation."""
        storage = DataStorage(mock_config_manager)

        # Test exponential backoff
        delay1 = storage._calculate_retry_delay(0)
        delay2 = storage._calculate_retry_delay(1)
        delay3 = storage._calculate_retry_delay(2)

        assert delay1 == 1.0  # Base delay
        assert delay2 == 2.0  # 1.0 * 2^1
        assert delay3 == 4.0  # 1.0 * 2^2

        # Test max delay cap
        large_delay = storage._calculate_retry_delay(10)
        assert large_delay <= storage._error_recovery_config.max_retry_delay_seconds

    @patch("battery_hawk.core.storage.InfluxDBClient")
    async def test_buffer_size_limit(
        self,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test that buffer respects size limits."""
        # Configure small buffer for testing
        mock_config_manager.configs["system"]["influxdb"]["error_recovery"][
            "buffer_max_size"
        ] = 3

        storage = DataStorage(mock_config_manager)

        # Add readings beyond buffer limit
        for i in range(5):
            await storage.store_reading(
                f"device{i}",
                "vehicle1",
                "BM6",
                {"voltage": 12.0 + i},
            )

        # Buffer should only contain last 3 readings
        assert len(storage._reading_buffer) == 3

        # Verify it contains the most recent readings
        device_ids = [reading.device_id for reading in storage._reading_buffer]
        assert "device2" in device_ids
        assert "device3" in device_ids
        assert "device4" in device_ids
