"""
Tests for InfluxDB storage implementation.

This module tests the DataStorage class with InfluxDB backend functionality
including connection handling, data writing, and querying.
"""

import json
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

    @patch("battery_hawk.core.storage.InfluxDBClient1x")
    @patch("battery_hawk.core.storage.requests")
    async def test_connect_success(
        self,
        mock_requests: Any,
        mock_influx_client_1x: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test successful connection to InfluxDB 1.x."""
        # Setup mocks for version detection
        mock_response = MagicMock()
        mock_response.headers = {"X-Influxdb-Version": "1.8.10"}
        mock_requests.get.return_value = mock_response

        # Setup InfluxDB 1.x client mock
        mock_client_instance = MagicMock()
        mock_client_instance.ping = MagicMock()
        mock_client_instance.create_database = MagicMock()
        mock_influx_client_1x.return_value = mock_client_instance

        storage = DataStorage(mock_config_manager)
        result = await storage.connect()

        assert result is True
        assert storage.connected is True
        assert storage.client_1x is not None
        assert storage._influxdb_version == "1.x"
        mock_influx_client_1x.assert_called_once()
        mock_client_instance.ping.assert_called_once()

        # Cleanup
        await storage.disconnect()

    @patch("battery_hawk.core.storage.requests")
    async def test_connect_failure(
        self,
        mock_requests: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test connection failure to InfluxDB."""
        # Setup mocks to raise exception during version detection
        mock_requests.get.side_effect = Exception("Connection failed")

        storage = DataStorage(mock_config_manager)
        result = await storage.connect()

        assert result is False
        assert storage.connected is False
        assert storage.client is None
        assert storage.client_1x is None

    async def test_connect_disabled(self, mock_config_manager_disabled: Any) -> None:
        """Test connection when InfluxDB is disabled."""
        storage = DataStorage(mock_config_manager_disabled)
        result = await storage.connect()

        assert result is True
        assert storage.connected is False
        assert storage.client is None

    @patch("battery_hawk.core.storage.InfluxDBClient1x")
    @patch("battery_hawk.core.storage.requests")
    async def test_store_reading_success(
        self,
        mock_requests: Any,
        mock_influx_client_1x: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test successful storage of battery reading."""
        # Setup mocks for version detection
        mock_response = MagicMock()
        mock_response.headers = {"X-Influxdb-Version": "1.8.10"}
        mock_requests.get.return_value = mock_response

        # Setup InfluxDB 1.x client mock
        mock_client_instance = MagicMock()
        mock_client_instance.ping = MagicMock()
        mock_client_instance.create_database = MagicMock()
        mock_client_instance.write_points = MagicMock()
        mock_influx_client_1x.return_value = mock_client_instance

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
        mock_client_instance.write_points.assert_called_once()

        # Cleanup
        await storage.disconnect()

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

    @patch("battery_hawk.core.storage.InfluxDBClient1x")
    @patch("battery_hawk.core.storage.requests")
    async def test_get_recent_readings_success(
        self,
        mock_requests: Any,
        mock_influx_client_1x: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test successful retrieval of recent readings."""
        # Setup mocks for version detection
        mock_response = MagicMock()
        mock_response.headers = {"X-Influxdb-Version": "1.8.10"}
        mock_requests.get.return_value = mock_response

        # Setup InfluxDB 1.x client mock
        mock_client_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.get_points.return_value = [
            {"time": "2023-01-01T00:00:00Z", "voltage": 12.5, "current": 2.3},
            {"time": "2023-01-01T01:00:00Z", "voltage": 12.4, "current": 2.1},
        ]
        mock_client_instance.query.return_value = mock_result
        mock_client_instance.ping = MagicMock()
        mock_client_instance.create_database = MagicMock()
        mock_influx_client_1x.return_value = mock_client_instance

        # Add empty retention policies to avoid setup issues
        mock_config_manager.configs["system"]["influxdb"]["retention_policies"] = {}

        storage = DataStorage(mock_config_manager)

        # Mock the retention policy setup to avoid issues
        with patch.object(storage, "_setup_retention_policies") as mock_setup:
            mock_setup.return_value = None
            await storage.connect()

        result = await storage.get_recent_readings("AA:BB:CC:DD:EE:FF", limit=10)

        assert len(result) == 2
        assert result[0]["voltage"] == 12.5
        # Verify that query was called (multiple times due to retention policies + actual query)
        assert mock_client_instance.query.call_count >= 1

        # Verify the actual data query was made
        query_calls = [str(call) for call in mock_client_instance.query.call_args_list]
        data_query_made = any("SELECT * FROM" in call for call in query_calls)
        assert data_query_made

        # Cleanup
        await storage.disconnect()

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
    @patch("battery_hawk.core.storage.requests")
    async def test_health_check_success(
        self,
        mock_requests: Any,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test successful health check."""
        # Mock version detection to 2.x to match the 2.x client being patched
        mock_response = MagicMock()
        mock_response.headers = {"X-Influxdb-Version": "2.0.0"}
        mock_requests.get.return_value = mock_response

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

        # Cleanup
        await storage.disconnect()

    @patch("battery_hawk.core.storage.InfluxDBClient1x")
    @patch("battery_hawk.core.storage.requests")
    async def test_health_check_failure(
        self,
        mock_requests: Any,
        mock_influx_client_1x: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test health check failure."""
        # Setup mocks for version detection
        mock_response = MagicMock()
        mock_response.headers = {"X-Influxdb-Version": "1.8.10"}
        mock_requests.get.return_value = mock_response

        # Setup InfluxDB 1.x client mock
        mock_client_instance = MagicMock()
        mock_client_instance.ping.side_effect = Exception("Ping failed")
        mock_client_instance.create_database = MagicMock()
        mock_influx_client_1x.return_value = mock_client_instance

        storage = DataStorage(mock_config_manager)
        await storage.connect()

        result = await storage.health_check()

        assert result is False
        assert storage.connected is False

        # Cleanup
        await storage.disconnect()

    @patch("battery_hawk.core.storage.InfluxDBClient1x")
    @patch("battery_hawk.core.storage.requests")
    async def test_disconnect(
        self,
        mock_requests: Any,
        mock_influx_client_1x: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test disconnection from InfluxDB."""
        # Setup mocks for version detection
        mock_response = MagicMock()
        mock_response.headers = {"X-Influxdb-Version": "1.8.10"}
        mock_requests.get.return_value = mock_response

        # Setup InfluxDB 1.x client mock
        mock_client_instance = MagicMock()
        mock_client_instance.ping = MagicMock()
        mock_client_instance.create_database = MagicMock()
        mock_client_instance.close = MagicMock()
        mock_influx_client_1x.return_value = mock_client_instance

        storage = DataStorage(mock_config_manager)
        await storage.connect()
        assert storage.connected is True

        await storage.disconnect()

        assert storage.connected is False
        assert storage.client_1x is None
        mock_client_instance.close.assert_called_once()


@pytest.mark.asyncio
class TestInfluxDBRetentionPolicies:
    """Test cases for InfluxDB retention policy management."""

    @patch("battery_hawk.core.storage.InfluxDBClient1x")
    @patch("battery_hawk.core.storage.requests")
    async def test_setup_retention_policies(
        self,
        mock_requests: Any,
        mock_influx_client_1x: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test setting up retention policies during connection."""
        # Setup mocks for version detection
        mock_response = MagicMock()
        mock_response.headers = {"X-Influxdb-Version": "1.8.10"}
        mock_requests.get.return_value = mock_response

        # Setup InfluxDB 1.x client mock
        mock_client_instance = MagicMock()
        mock_client_instance.ping = MagicMock()
        mock_client_instance.create_database = MagicMock()
        mock_client_instance.query = MagicMock()
        mock_influx_client_1x.return_value = mock_client_instance

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
        assert mock_client_instance.query.call_count >= 2  # At least 2 policies created

        # Cleanup
        await storage.disconnect()

    @patch("battery_hawk.core.storage.InfluxDBClient1x")
    @patch("battery_hawk.core.storage.requests")
    async def test_get_retention_policies(
        self,
        mock_requests: Any,
        mock_influx_client_1x: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test retrieving retention policies."""
        # Setup mocks for version detection
        mock_response = MagicMock()
        mock_response.headers = {"X-Influxdb-Version": "1.8.10"}
        mock_requests.get.return_value = mock_response

        # Setup InfluxDB 1.x client mock
        mock_client_instance = MagicMock()
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
        mock_client_instance.query.return_value = mock_result
        mock_client_instance.ping = MagicMock()
        mock_client_instance.create_database = MagicMock()
        mock_influx_client_1x.return_value = mock_client_instance

        # Add empty retention policies to avoid setup issues
        mock_config_manager.configs["system"]["influxdb"]["retention_policies"] = {}

        storage = DataStorage(mock_config_manager)

        # Mock the retention policy setup to avoid issues
        with patch.object(storage, "_setup_retention_policies") as mock_setup:
            mock_setup.return_value = None
            await storage.connect()

        policies = await storage.get_retention_policies("test_database")

        assert len(policies) == 2
        assert policies[0]["name"] == "autogen"
        assert policies[1]["name"] == "long_term"
        mock_client_instance.query.assert_called()

        # Cleanup
        await storage.disconnect()

    @patch("battery_hawk.core.storage.InfluxDBClient1x")
    @patch("battery_hawk.core.storage.requests")
    async def test_drop_retention_policy(
        self,
        mock_requests: Any,
        mock_influx_client_1x: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test dropping a retention policy."""
        # Setup mocks for version detection
        mock_response = MagicMock()
        mock_response.headers = {"X-Influxdb-Version": "1.8.10"}
        mock_requests.get.return_value = mock_response

        # Setup InfluxDB 1.x client mock
        mock_client_instance = MagicMock()
        mock_client_instance.ping = MagicMock()
        mock_client_instance.create_database = MagicMock()
        mock_client_instance.query = MagicMock()
        mock_influx_client_1x.return_value = mock_client_instance

        # Add empty retention policies to avoid setup issues
        mock_config_manager.configs["system"]["influxdb"]["retention_policies"] = {}

        storage = DataStorage(mock_config_manager)

        # Mock the retention policy setup to avoid issues
        with patch.object(storage, "_setup_retention_policies") as mock_setup:
            mock_setup.return_value = None
            await storage.connect()

        result = await storage.drop_retention_policy("test_database", "old_policy")

        assert result is True
        mock_client_instance.query.assert_called()
        # Verify DROP RETENTION POLICY query was called
        drop_call = None
        for call in mock_client_instance.query.call_args_list:
            if "DROP RETENTION POLICY" in str(call):
                drop_call = call
                break
        assert drop_call is not None

        # Cleanup
        await storage.disconnect()

    async def test_get_retention_policy_for_measurement(
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

    @patch("battery_hawk.core.storage.InfluxDBClient1x")
    @patch("battery_hawk.core.storage.requests")
    async def test_store_reading_with_retention_policy(
        self,
        mock_requests: Any,
        mock_influx_client_1x: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test storing readings with retention policy selection."""
        # Setup mocks for version detection
        mock_response = MagicMock()
        mock_response.headers = {"X-Influxdb-Version": "1.8.10"}
        mock_requests.get.return_value = mock_response

        # Setup InfluxDB 1.x client mock
        mock_client_instance = MagicMock()
        mock_client_instance.ping = MagicMock()
        mock_client_instance.create_database = MagicMock()
        mock_client_instance.write_points = MagicMock()
        mock_client_instance.query = MagicMock()
        mock_influx_client_1x.return_value = mock_client_instance

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
        mock_client_instance.write_points.assert_called_once()

        # Verify retention policy was passed to write call
        write_call_args = mock_client_instance.write_points.call_args
        assert (
            write_call_args[0][3] == "autogen"
        )  # retention policy argument (4th parameter)

        # Cleanup
        await storage.disconnect()


@pytest.mark.asyncio
class TestInfluxDBErrorHandling:
    """Test cases for InfluxDB error handling and recovery."""

    @patch("battery_hawk.core.storage.requests")
    async def test_connection_retry_on_failure(
        self,
        mock_requests: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test connection retry logic on failure."""
        # Setup mocks to always fail during version detection
        mock_requests.get.side_effect = ConnectionError("Connection failed")

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

    @patch("battery_hawk.core.storage.InfluxDBClient1x")
    @patch("battery_hawk.core.storage.requests")
    async def test_buffer_flush_on_reconnection(
        self,
        mock_requests: Any,
        mock_influx_client_1x: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test that buffered readings are flushed when connection is restored."""
        # Setup mocks for version detection
        mock_response = MagicMock()
        mock_response.headers = {"X-Influxdb-Version": "1.8.10"}
        mock_requests.get.return_value = mock_response

        # Setup InfluxDB 1.x client mock
        mock_client_instance = MagicMock()
        mock_client_instance.ping = MagicMock()
        mock_client_instance.create_database = MagicMock()
        mock_client_instance.write_points = MagicMock()
        mock_client_instance.query = MagicMock()
        mock_influx_client_1x.return_value = mock_client_instance

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
        assert mock_client_instance.write_points.call_count >= 2

        # Cleanup
        await storage.disconnect()

    @patch("battery_hawk.core.storage.InfluxDBClient1x")
    @patch("battery_hawk.core.storage.requests")
    async def test_write_timeout_handling(
        self,
        mock_requests: Any,
        mock_influx_client_1x: Any,
        mock_config_manager: Any,
    ) -> None:
        """Test handling of write operation timeouts."""
        # Setup mocks for version detection
        mock_response = MagicMock()
        mock_response.headers = {"X-Influxdb-Version": "1.8.10"}
        mock_requests.get.return_value = mock_response

        # Setup InfluxDB 1.x client mock
        mock_client_instance = MagicMock()

        # Make write operation hang (simulate timeout)
        def slow_write(*_args: Any, **_kwargs: Any) -> None:
            time.sleep(10)  # Longer than timeout

        mock_client_instance.write_points.side_effect = slow_write
        mock_client_instance.ping = MagicMock()
        mock_client_instance.create_database = MagicMock()
        mock_client_instance.query = MagicMock()
        mock_influx_client_1x.return_value = mock_client_instance

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

        # Cleanup
        await storage.disconnect()

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

    async def test_filter_influxdb_fields_empty_dict(self) -> None:
        """Test that empty dictionaries are filtered out from InfluxDB fields."""
        storage = DataStorage(MagicMock())

        # Test data with empty extra field (the original problem)
        reading = {
            "voltage": 12.5,
            "current": 2.3,
            "temperature": 25.0,
            "state_of_charge": 85.0,
            "extra": {},  # Empty dict that caused the InfluxDB error
        }

        filtered = storage._filter_influxdb_fields(reading)

        # Empty dict should be filtered out
        assert "extra" not in filtered
        assert filtered["voltage"] == 12.5
        assert filtered["current"] == 2.3
        assert filtered["temperature"] == 25.0
        assert filtered["state_of_charge"] == 85.0

    async def test_filter_influxdb_fields_non_empty_dict(self) -> None:
        """Test that non-empty dictionaries are converted to JSON strings."""
        storage = DataStorage(MagicMock())

        # Test data with non-empty extra field
        reading = {
            "voltage": 12.5,
            "extra": {"cell_count": 4, "software_version": 1.2},
        }

        filtered = storage._filter_influxdb_fields(reading)

        # Non-empty dict should be converted to JSON string
        assert "extra" in filtered
        assert isinstance(filtered["extra"], str)

        parsed_extra = json.loads(filtered["extra"])
        assert parsed_extra["cell_count"] == 4
        assert parsed_extra["software_version"] == 1.2

    async def test_filter_influxdb_fields_none_values(self) -> None:
        """Test that None values are filtered out."""
        storage = DataStorage(MagicMock())

        reading = {
            "voltage": 12.5,
            "current": None,
            "temperature": 25.0,
            "capacity": None,
        }

        filtered = storage._filter_influxdb_fields(reading)

        # None values should be filtered out
        assert "current" not in filtered
        assert "capacity" not in filtered
        assert filtered["voltage"] == 12.5
        assert filtered["temperature"] == 25.0

    async def test_filter_influxdb_fields_empty_list(self) -> None:
        """Test that empty lists are filtered out."""
        storage = DataStorage(MagicMock())

        reading = {
            "voltage": 12.5,
            "cell_voltages": [],  # Empty list
            "temperatures": [25.0, 26.0],  # Non-empty list
        }

        filtered = storage._filter_influxdb_fields(reading)

        # Empty list should be filtered out
        assert "cell_voltages" not in filtered
        # Non-empty list should be converted to JSON string
        assert "temperatures" in filtered
        assert isinstance(filtered["temperatures"], str)

        parsed_temps = json.loads(filtered["temperatures"])
        assert parsed_temps == [25.0, 26.0]


@pytest.mark.asyncio
class TestInfluxDBV2Behavior:
    """Tests specific to InfluxDB 2.x behavior (org/bucket/token handling)."""

    @patch("battery_hawk.core.storage.InfluxDBClient")
    @patch("battery_hawk.core.storage.requests")
    async def test_v2_client_uses_token_and_org(
        self,
        mock_requests: Any,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """Ensure v2 client is created with token and org, not username/password."""
        # Simulate InfluxDB 2.x
        mock_response = MagicMock()
        mock_response.headers = {"X-Influxdb-Version": "2.7.12"}
        mock_requests.get.return_value = mock_response

        # Prepare client mocks
        mock_client_instance = MagicMock()
        mock_client_instance.ping = MagicMock()
        mock_client_instance.write_api.return_value = MagicMock()
        mock_client_instance.query_api.return_value = MagicMock()
        mock_influx_client.return_value = mock_client_instance

        # Configure v2-specific settings
        mock_config_manager.configs["system"]["influxdb"].update(
            {
                "token": "test-token",
                "org": "battery-hawk",
                "bucket": "test_bucket",
            },
        )

        storage = DataStorage(mock_config_manager)
        await storage.connect()

        # Verify client constructed with token & org
        called_kwargs = mock_influx_client.call_args.kwargs
        assert called_kwargs.get("token") == "test-token"
        assert called_kwargs.get("org") == "battery-hawk"
        # username/password should not be passed when token/org present
        assert "username" not in called_kwargs
        assert "password" not in called_kwargs

        await storage.disconnect()

    @patch("battery_hawk.core.storage.InfluxDBClient")
    @patch("battery_hawk.core.storage.requests")
    async def test_v2_query_uses_org_not_database(
        self,
        mock_requests: Any,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """get_recent_readings() should pass org to QueryAPI in v2."""
        # Simulate InfluxDB 2.x
        mock_response = MagicMock()
        mock_response.headers = {"X-Influxdb-Version": "2.7.12"}
        mock_requests.get.return_value = mock_response

        # Prepare client mocks
        mock_client_instance = MagicMock()
        mock_query_api = MagicMock()
        mock_query_api.query = MagicMock(return_value=[])
        mock_client_instance.ping = MagicMock()
        mock_client_instance.query_api.return_value = mock_query_api
        mock_client_instance.write_api.return_value = MagicMock()
        mock_influx_client.return_value = mock_client_instance

        # Configure v2-specific settings
        mock_config_manager.configs["system"]["influxdb"].update(
            {
                "token": "token",
                "org": "battery-hawk",
                "bucket": "test_bucket",
            },
        )

        storage = DataStorage(mock_config_manager)
        await storage.connect()

        # Call method under test
        _ = await storage.get_recent_readings("AA:BB:CC:DD:EE:FF", limit=5)

        # Assert query called with org as second positional arg
        assert mock_query_api.query.call_count >= 1
        args, _kwargs = mock_query_api.query.call_args
        # Expect args like (query_string, "battery-hawk")
        assert len(args) >= 2
        assert args[1] == "battery-hawk"
        # Database should not be passed positionally in v2 path

        await storage.disconnect()

    @patch("battery_hawk.core.storage.InfluxDBClient")
    @patch("battery_hawk.core.storage.requests")
    async def test_v2_write_uses_bucket_and_org_named_args(
        self,
        mock_requests: Any,
        mock_influx_client: Any,
        mock_config_manager: Any,
    ) -> None:
        """store_reading() should call write_api.write(bucket=..., org=..., ...)."""
        # Simulate InfluxDB 2.x
        mock_response = MagicMock()
        mock_response.headers = {"X-Influxdb-Version": "2.7.12"}
        mock_requests.get.return_value = mock_response

        # Prepare client mocks
        mock_client_instance = MagicMock()
        mock_write_api = MagicMock()
        mock_query_api = MagicMock()
        mock_client_instance.ping = MagicMock()
        mock_client_instance.write_api.return_value = mock_write_api
        mock_client_instance.query_api.return_value = mock_query_api
        mock_influx_client.return_value = mock_client_instance

        # Configure v2-specific settings
        mock_config_manager.configs["system"]["influxdb"].update(
            {
                "token": "token",
                "org": "battery-hawk",
                "bucket": "test_bucket",
            },
        )

        storage = DataStorage(mock_config_manager)
        await storage.connect()

        # Perform a write
        result = await storage.store_reading(
            "AA:BB:CC:DD:EE:FF",
            "vehicle_1",
            "BM6",
            {"voltage": 12.3, "current": 1.2, "temperature": 22.0},
        )

        assert result is True
        assert mock_write_api.write.call_count >= 1
        _args, wkwargs = mock_write_api.write.call_args
        # Ensure named args include bucket and org
        assert wkwargs.get("bucket") == "test_bucket"
        assert wkwargs.get("org") == "battery-hawk"
        assert "record" in wkwargs

        await storage.disconnect()
