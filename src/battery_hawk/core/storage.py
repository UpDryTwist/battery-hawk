"""
Data storage abstraction for Battery Hawk.

This module provides the DataStorage class for storing battery readings
and other data in various backends (InfluxDB, etc.). It includes both
the abstract base class and concrete implementations.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

from influxdb_client.client.influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import ASYNCHRONOUS
from influxdb_client.domain.write_precision import WritePrecision

from .storage_backends import BaseStorageBackend

if TYPE_CHECKING:
    from battery_hawk.config.config_manager import ConfigManager

# Constants
HIGH_CURRENT_THRESHOLD = 10  # Amperes - threshold for high current readings
MAX_QUERY_LIMIT = 10000  # Maximum number of records to return in a single query
MAX_HOURS_QUERY = 8760  # Maximum hours for time-based queries (1 year)


_UUID_LIKE = re.compile(
    r"^[A-Fa-f0-9-]{1,64}$",
)  # or use uuid.UUID to require true UUIDs


def require_uuid_like(value: str, name: str) -> str:
    """Validate that value is a UUID-like string."""
    if not isinstance(value, str) or not _UUID_LIKE.fullmatch(value):
        raise ValueError(f"Invalid {name}")
    return value


def require_int_in_range(
    value: Any,
    name: str,
    *,
    min_: int = 1,
    max_: int = 10_000,
) -> int:
    """Validate that value is an integer within the specified range."""
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an integer") from None
    if not (min_ <= ivalue <= max_):
        raise ValueError(f"{name} must be between {min_} and {max_}") from None
    return ivalue


def influxql_quote(s: str) -> str:
    """
    Minimal escaping for InfluxQL string literals.
    InfluxQL uses single quotes for strings; backslash escapes are supported.
    """
    if not isinstance(s, str):
        raise TypeError("expected string")
    s = s.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{s}'"


class ConnectionState(Enum):
    """Connection state enumeration for tracking database connectivity."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass
class BufferedReading:
    """Data structure for buffering readings during outages."""

    device_id: str
    vehicle_id: str
    device_type: str
    reading: dict[str, Any]
    timestamp: datetime
    retry_count: int = 0
    retention_policy: str | None = None


@dataclass
class ErrorRecoveryConfig:
    """Configuration for error recovery behavior."""

    max_retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    retry_backoff_multiplier: float = 2.0
    max_retry_delay_seconds: float = 60.0
    buffer_max_size: int = 10000
    buffer_flush_interval_seconds: float = 30.0
    connection_timeout_seconds: float = 30.0
    health_check_interval_seconds: float = 60.0


class InfluxDBStorageBackend(BaseStorageBackend):
    """
    InfluxDB storage backend implementation for Battery Hawk monitoring data.

    Provides AsyncIO-compatible interface for storing time series data in InfluxDB
    with connection handling, database creation, and error management.
    """

    def __init__(self, config_manager: ConfigManager) -> None:
        """
        Initialize InfluxDB storage backend with configuration manager.

        Args:
            config_manager: Configuration manager instance
        """
        self.client: InfluxDBClient | None = None
        self.write_api: Any | None = None
        self.query_api: Any | None = None
        self._connection_lock = asyncio.Lock()
        self._connection_start_time: float | None = None

        # Error handling and recovery
        self._connection_state = ConnectionState.DISCONNECTED
        self._error_recovery_config = ErrorRecoveryConfig()
        self._reading_buffer: deque[BufferedReading] = deque(
            maxlen=self._error_recovery_config.buffer_max_size,
        )
        self._retry_counts: dict[str, int] = {}
        self._last_connection_attempt: float = 0.0
        self._background_tasks: set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()

        super().__init__(config_manager)

    @property
    def backend_name(self) -> str:
        """Return the name of the storage backend."""
        return "InfluxDB"

    @property
    def backend_version(self) -> str:
        """Return the version of the storage backend implementation."""
        return "1.0.0"

    @property
    def capabilities(self) -> set[str]:
        """Return supported capabilities for InfluxDB backend."""
        return {
            "time_series",
            "aggregation",
            "retention",
            "real_time",
            "clustering",
        }

    def _initialize_backend(self) -> None:
        """Initialize the InfluxDB storage backend based on configuration."""
        super()._initialize_backend()
        try:
            influx_config = self.config.get_config("system").get("influxdb", {})
            if influx_config.get("enabled", False):
                self.logger.info("InfluxDB storage enabled")
                # Client will be initialized in connect() method

                # Initialize error recovery configuration
                self._initialize_error_recovery()

                # Start background tasks
                self._start_background_tasks()
            else:
                self.logger.info("InfluxDB storage disabled")
        except Exception:
            self.logger.exception("Failed to initialize InfluxDB storage backend")

    def _initialize_error_recovery(self) -> None:
        """Initialize error recovery configuration from settings."""
        try:
            config = self._get_influx_config()
            error_config = config.get("error_recovery", {})

            self._error_recovery_config = ErrorRecoveryConfig(
                max_retry_attempts=error_config.get("max_retry_attempts", 3),
                retry_delay_seconds=error_config.get("retry_delay_seconds", 1.0),
                retry_backoff_multiplier=error_config.get(
                    "retry_backoff_multiplier",
                    2.0,
                ),
                max_retry_delay_seconds=error_config.get(
                    "max_retry_delay_seconds",
                    60.0,
                ),
                buffer_max_size=error_config.get("buffer_max_size", 10000),
                buffer_flush_interval_seconds=error_config.get(
                    "buffer_flush_interval_seconds",
                    30.0,
                ),
                connection_timeout_seconds=error_config.get(
                    "connection_timeout_seconds",
                    30.0,
                ),
                health_check_interval_seconds=error_config.get(
                    "health_check_interval_seconds",
                    60.0,
                ),
            )

            # Update buffer max size
            self._reading_buffer = deque(
                maxlen=self._error_recovery_config.buffer_max_size,
            )

            self.logger.info(
                "Error recovery initialized: max_retries=%d, buffer_size=%d",
                self._error_recovery_config.max_retry_attempts,
                self._error_recovery_config.buffer_max_size,
            )

        except Exception:
            self.logger.exception("Failed to initialize error recovery")

    def _start_background_tasks(self) -> None:
        """Start background tasks for error recovery and maintenance."""
        try:
            # Start buffer flush task
            flush_task = asyncio.create_task(self._buffer_flush_loop())
            self._background_tasks.add(flush_task)
            flush_task.add_done_callback(self._background_tasks.discard)

            # Start health check task
            health_task = asyncio.create_task(self._health_check_loop())
            self._background_tasks.add(health_task)
            health_task.add_done_callback(self._background_tasks.discard)

            self.logger.debug("Started background tasks for error recovery")

        except Exception:
            self.logger.exception("Failed to start background tasks")

    def _get_influx_config(self) -> dict[str, Any]:
        """
        Get InfluxDB configuration with defaults and environment variable overrides.

        Returns:
            Dictionary containing InfluxDB connection parameters
        """
        influx_config = self.config.get_config("system").get("influxdb", {})

        # Set defaults for missing configuration
        defaults = {
            "host": "localhost",
            "port": 8086,
            "database": "battery_hawk",
            "username": "",
            "password": "",
            "timeout": 10000,  # 10 seconds
            "retries": 3,
            "retention_policies": {
                "default": {
                    "name": "autogen",
                    "duration": "30d",
                    "replication": 1,
                    "shard_duration": "1d",
                    "default": True,
                },
            },
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
        }

        # Merge with defaults
        for key, default_value in defaults.items():
            if key not in influx_config:
                influx_config[key] = default_value

        return influx_config

    async def connect(self) -> bool:
        """
        Connect to the InfluxDB storage backend with enhanced error handling.

        Returns:
            True if connection was successful
        """
        return await self._connect_with_retry()

    async def _connect_with_retry(self, *, is_retry: bool = False) -> bool:
        """
        Connect to InfluxDB with retry logic and error recovery.

        Args:
            is_retry: Whether this is a retry attempt

        Returns:
            True if connection was successful
        """
        async with self._connection_lock:
            try:
                # Update connection state
                self._connection_state = (
                    ConnectionState.RECONNECTING
                    if is_retry
                    else ConnectionState.CONNECTING
                )
                self._last_connection_attempt = time.time()

                influx_config = self.config.get_config("system").get("influxdb", {})
                if not influx_config.get("enabled", False):
                    self.logger.info("InfluxDB storage disabled")
                    self.connected = False
                    self._connection_state = ConnectionState.DISCONNECTED
                    return True

                config = self._get_influx_config()

                # Build connection URL
                url = f"http://{config['host']}:{config['port']}"

                retry_msg = " (retry)" if is_retry else ""
                self.logger.info("Connecting to InfluxDB at %s%s", url, retry_msg)

                # Initialize InfluxDB client with timeout
                self.client = InfluxDBClient(
                    url=url,
                    username=config["username"] if config["username"] else None,
                    password=config["password"] if config["password"] else None,
                    timeout=config["timeout"],
                )

                # Initialize APIs
                self.write_api = self.client.write_api(write_options=ASYNCHRONOUS)
                self.query_api = self.client.query_api()

                # Test connection with timeout
                await asyncio.wait_for(
                    self._test_connection(),
                    timeout=self._error_recovery_config.connection_timeout_seconds,
                )

                # Create database if it doesn't exist (for InfluxDB 1.x)
                await self._ensure_database_exists(config["database"])

                # Setup retention policies
                await self._setup_retention_policies(config["database"])

                # Connection successful
                self.connected = True
                self._connection_state = ConnectionState.CONNECTED
                self._connection_start_time = time.time()
                self._retry_counts.clear()  # Clear retry counts on successful connection

                success_msg = (
                    "Successfully reconnected to InfluxDB"
                    if is_retry
                    else "Successfully connected to InfluxDB"
                )
                self.logger.info(success_msg)

                # Flush buffered readings on successful connection
                if is_retry and self._reading_buffer:
                    task = asyncio.create_task(self._flush_buffer())
                    # Task runs in background, no need to await
                    task.add_done_callback(
                        lambda _: None,
                    )  # Prevent warnings about unawaited task

                return True  # noqa: TRY300

            except TimeoutError:
                self.logger.exception(
                    "Connection to InfluxDB timed out after %ds",
                    self._error_recovery_config.connection_timeout_seconds,
                )
                await self._handle_connection_failure()
                return False
            except Exception:
                self.logger.exception("Failed to connect to InfluxDB")
                await self._handle_connection_failure()
                return False

    async def _handle_connection_failure(self) -> None:
        """Handle connection failure with appropriate cleanup and state management."""
        try:
            await self._cleanup_connection()
            self._connection_state = ConnectionState.FAILED

            # Schedule retry if not exceeded max attempts
            retry_key = "connection"
            current_retries = self._retry_counts.get(retry_key, 0)

            if current_retries < self._error_recovery_config.max_retry_attempts:
                self._retry_counts[retry_key] = current_retries + 1
                retry_delay = self._calculate_retry_delay(current_retries)

                self.logger.warning(
                    "Connection failed, will retry in %.1fs (attempt %d/%d)",
                    retry_delay,
                    current_retries + 1,
                    self._error_recovery_config.max_retry_attempts,
                )

                # Schedule retry
                retry_task = asyncio.create_task(self._schedule_retry(retry_delay))
                retry_task.add_done_callback(lambda _: None)  # Prevent warnings
            else:
                self.logger.error(
                    "Connection failed after %d attempts, giving up",
                    self._error_recovery_config.max_retry_attempts,
                )
                self._retry_counts[retry_key] = 0  # Reset for future attempts

        except Exception:
            self.logger.exception("Error handling connection failure")

    def _calculate_retry_delay(self, retry_count: int) -> float:
        """
        Calculate retry delay with exponential backoff.

        Args:
            retry_count: Current retry attempt count

        Returns:
            Delay in seconds
        """
        delay = self._error_recovery_config.retry_delay_seconds * (
            self._error_recovery_config.retry_backoff_multiplier**retry_count
        )
        return min(delay, self._error_recovery_config.max_retry_delay_seconds)

    async def _schedule_retry(self, delay: float) -> None:
        """
        Schedule a connection retry after a delay.

        Args:
            delay: Delay in seconds before retry
        """
        try:
            await asyncio.sleep(delay)
            if (
                not self.connected
                and self._connection_state != ConnectionState.CONNECTED
            ):
                await self._connect_with_retry(is_retry=True)
        except Exception:
            self.logger.exception("Error during scheduled retry")

    async def _test_connection(self) -> None:
        """Test the InfluxDB connection by pinging the server."""
        if not self.client:
            raise ConnectionError("InfluxDB client not initialized")

        # Run ping in executor to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.client.ping)

    async def _ensure_database_exists(self, database_name: str) -> None:
        """
        Ensure the database exists, create it if it doesn't.

        Args:
            database_name: Name of the database to create
        """
        if not self.client:
            raise ConnectionError("InfluxDB client not initialized")

        try:
            # For InfluxDB 1.x, we need to create the database
            # This is a no-op for InfluxDB 2.x which uses buckets
            if self.query_api:
                loop = asyncio.get_event_loop()

                # Use query API to create database
                create_db_query = f'CREATE DATABASE "{database_name}"'
                await loop.run_in_executor(None, self.query_api.query, create_db_query)
                self.logger.info(
                    "Database '%s' created or already exists",
                    database_name,
                )
        except (ConnectionError, OSError, ValueError) as e:
            # Database might already exist or we might be using InfluxDB 2.x
            self.logger.debug("Database creation result: %s", e)

    async def _cleanup_connection(self) -> None:
        """Clean up connection resources."""
        try:
            if self.write_api:
                self.write_api.close()
                self.write_api = None
            if self.client:
                self.client.close()
                self.client = None
            self.query_api = None
            self.connected = False
        except Exception:
            self.logger.exception("Error during connection cleanup")

    async def _buffer_flush_loop(self) -> None:
        """Background task to periodically flush buffered readings."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(
                    self._error_recovery_config.buffer_flush_interval_seconds,
                )
                if self.connected and self._reading_buffer:
                    await self._flush_buffer()
            except asyncio.CancelledError:  # noqa: PERF203
                break
            except Exception:
                self.logger.exception("Error in buffer flush loop")

    async def _health_check_loop(self) -> None:
        """Background task to periodically check connection health."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(
                    self._error_recovery_config.health_check_interval_seconds,
                )
                if self.connected:
                    healthy = await self.health_check()
                    if (
                        not healthy
                        and self._connection_state == ConnectionState.CONNECTED
                    ):
                        self.logger.warning(
                            "Health check failed, attempting reconnection",
                        )
                        await self._connect_with_retry(is_retry=True)
            except asyncio.CancelledError:  # noqa: PERF203
                break
            except Exception:
                self.logger.exception("Error in health check loop")

    async def _flush_buffer(self) -> None:
        """Flush buffered readings to InfluxDB."""
        if not self.connected or not self._reading_buffer:
            return

        flushed_count = 0
        failed_count = 0

        # Process buffered readings
        while self._reading_buffer and self.connected:
            try:
                buffered_reading = self._reading_buffer.popleft()

                # Attempt to store the buffered reading
                success = await self._store_reading_internal(
                    buffered_reading.device_id,
                    buffered_reading.vehicle_id,
                    buffered_reading.device_type,
                    buffered_reading.reading,
                    buffered_reading.retention_policy,
                )

                if success:
                    flushed_count += 1
                else:
                    # Re-queue if not exceeded retry limit
                    buffered_reading.retry_count += 1
                    if (
                        buffered_reading.retry_count
                        <= self._error_recovery_config.max_retry_attempts
                    ):
                        self._reading_buffer.append(buffered_reading)
                    else:
                        failed_count += 1
                        self.logger.warning(
                            "Dropping buffered reading after %d retries",
                            buffered_reading.retry_count,
                        )

            except Exception:  # noqa: PERF203
                self.logger.exception("Error flushing buffered reading")
                failed_count += 1

        if flushed_count > 0 or failed_count > 0:
            self.logger.info(
                "Buffer flush completed: %d flushed, %d failed, %d remaining",
                flushed_count,
                failed_count,
                len(self._reading_buffer),
            )

    async def _setup_retention_policies(self, database_name: str) -> None:
        """
        Set up retention policies for the database based on configuration.

        Args:
            database_name: Name of the database to setup policies for
        """
        if not self.client or not self.query_api:
            self.logger.warning(
                "Cannot setup retention policies: client not initialized",
            )
            return

        try:
            config = self._get_influx_config()
            retention_policies = config.get("retention_policies", {})

            if not retention_policies:
                self.logger.info("No retention policies configured")
                return

            self.logger.info(
                "Setting up retention policies for database '%s'",
                database_name,
            )

            for policy_config in retention_policies.values():
                await self._create_retention_policy(database_name, policy_config)

        except Exception:
            self.logger.exception("Failed to setup retention policies")

    async def _create_retention_policy(
        self,
        database_name: str,
        policy_config: dict[str, Any],
    ) -> None:
        """
        Create or update a retention policy.

        Args:
            database_name: Name of the database
            policy_config: Retention policy configuration
        """
        if not self.query_api:
            return

        try:
            policy_name = policy_config.get("name", "autogen")
            duration = policy_config.get("duration", "30d")
            replication = policy_config.get("replication", 1)
            shard_duration = policy_config.get("shard_duration", "1d")
            is_default = policy_config.get("default", False)

            # Build CREATE RETENTION POLICY query
            query_parts = [
                f'CREATE RETENTION POLICY "{policy_name}"',
                f'ON "{database_name}"',
                f"DURATION {duration}",
                f"REPLICATION {replication}",
                f"SHARD DURATION {shard_duration}",
            ]

            if is_default:
                query_parts.append("DEFAULT")

            query = " ".join(query_parts)

            self.logger.debug("Creating retention policy: %s", query)

            # Execute query asynchronously
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.query_api.query, query)

            self.logger.info(
                "Created retention policy '%s' (duration: %s, replication: %d, default: %s)",
                policy_name,
                duration,
                replication,
                is_default,
            )

        except Exception as e:
            # Policy might already exist, try to update it
            if "already exists" in str(e).lower():
                self.logger.debug(
                    "Retention policy '%s' already exists, attempting update",
                    policy_config.get("name"),
                )
                await self._update_retention_policy(database_name, policy_config)
            else:
                self.logger.exception(
                    "Failed to create retention policy '%s'",
                    policy_config.get("name"),
                )

    async def _update_retention_policy(
        self,
        database_name: str,
        policy_config: dict[str, Any],
    ) -> None:
        """
        Update an existing retention policy.

        Args:
            database_name: Name of the database
            policy_config: Retention policy configuration
        """
        if not self.query_api:
            return

        try:
            policy_name = policy_config.get("name", "autogen")
            duration = policy_config.get("duration", "30d")
            replication = policy_config.get("replication", 1)
            shard_duration = policy_config.get("shard_duration", "1d")
            is_default = policy_config.get("default", False)

            # Build ALTER RETENTION POLICY query
            query_parts = [
                f'ALTER RETENTION POLICY "{policy_name}"',
                f'ON "{database_name}"',
                f"DURATION {duration}",
                f"REPLICATION {replication}",
                f"SHARD DURATION {shard_duration}",
            ]

            if is_default:
                query_parts.append("DEFAULT")

            query = " ".join(query_parts)

            self.logger.debug("Updating retention policy: %s", query)

            # Execute query asynchronously
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.query_api.query, query)

            self.logger.info(
                "Updated retention policy '%s' (duration: %s, replication: %d, default: %s)",
                policy_name,
                duration,
                replication,
                is_default,
            )

        except Exception:
            self.logger.exception(
                "Failed to update retention policy '%s'",
                policy_config.get("name"),
            )

    async def get_retention_policies(self, database_name: str) -> list[dict[str, Any]]:
        """
        Get all retention policies for a database.

        Args:
            database_name: Name of the database

        Returns:
            List of retention policy information
        """
        if not self.connected or not self.query_api:
            self.logger.warning(
                "Storage not connected, cannot retrieve retention policies",
            )
            return []

        try:
            query = f'SHOW RETENTION POLICIES ON "{database_name}"'

            self.logger.debug(
                "Querying retention policies for database %s",
                database_name,
            )

            # Execute query asynchronously
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.query_api.query, query)

            # Convert result to list of dictionaries
            policies = []
            if result:
                policies.extend(dict(point) for point in result.get_points())

            self.logger.debug(
                "Retrieved %d retention policies for database %s",
                len(policies),
                database_name,
            )
        except Exception:
            self.logger.exception(
                "Failed to get retention policies for database %s",
                database_name,
            )
            return []
        else:
            return policies

    async def drop_retention_policy(self, database_name: str, policy_name: str) -> bool:
        """
        Drop a retention policy from a database.

        Args:
            database_name: Name of the database
            policy_name: Name of the retention policy to drop

        Returns:
            True if policy was dropped successfully
        """
        if not self.connected or not self.query_api:
            self.logger.warning("Storage not connected, cannot drop retention policy")
            return False

        try:
            query = f'DROP RETENTION POLICY "{policy_name}" ON "{database_name}"'

            self.logger.debug("Dropping retention policy: %s", query)

            # Execute query asynchronously
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.query_api.query, query)

            self.logger.info(
                "Dropped retention policy '%s' from database '%s'",
                policy_name,
                database_name,
            )
        except Exception:
            self.logger.exception(
                "Failed to drop retention policy '%s'",
                policy_name,
            )
            return False
        else:
            return True

    def _get_retention_policy_for_measurement(
        self,
        reading: dict[str, Any],
    ) -> str | None:
        """
        Determine which retention policy to use for a measurement based on data characteristics.

        Args:
            reading: Battery reading data

        Returns:
            Retention policy name or None for default
        """
        try:
            config = self._get_influx_config()
            retention_policies = config.get("retention_policies", {})

            # Simple logic: use different policies based on data characteristics
            # This can be extended with more sophisticated rules

            # For high-frequency data (e.g., current spikes), use short-term policy
            current = reading.get("current", 0)
            if abs(current) > HIGH_CURRENT_THRESHOLD:
                for policy_config in retention_policies.values():
                    if policy_config.get("name") == "short_term":
                        return policy_config["name"]

            # For normal readings, use default policy
            for policy_config in retention_policies.values():
                if policy_config.get("default", False):
                    return policy_config["name"]

            # Fallback to None (InfluxDB default)
        except (KeyError, ValueError, TypeError):
            self.logger.debug("Error determining retention policy, using default")
            return None
        else:
            return None

    async def disconnect(self) -> None:
        """Disconnect from the InfluxDB storage backend with proper cleanup."""
        async with self._connection_lock:
            try:
                # Signal shutdown to background tasks
                self._shutdown_event.set()

                # Cancel background tasks
                for task in self._background_tasks:
                    if not task.done():
                        task.cancel()

                # Wait for tasks to complete
                if self._background_tasks:
                    await asyncio.gather(
                        *self._background_tasks,
                        return_exceptions=True,
                    )
                    self._background_tasks.clear()

                # Flush any remaining buffered readings
                if self.connected and self._reading_buffer:
                    self.logger.info(
                        "Flushing %d buffered readings before disconnect",
                        len(self._reading_buffer),
                    )
                    await self._flush_buffer()

                # Cleanup connection
                if self.connected:
                    await self._cleanup_connection()
                    self.logger.info("Disconnected from InfluxDB")

                # Reset state
                self._connection_state = ConnectionState.DISCONNECTED
                self._retry_counts.clear()

            except Exception:
                self.logger.exception("Error disconnecting from InfluxDB")

    async def store_reading(
        self,
        device_id: str,
        vehicle_id: str,
        device_type: str,
        reading: dict[str, Any],
    ) -> bool:
        """
        Store a battery reading with enhanced error handling and buffering.

        Args:
            device_id: MAC address of the device
            vehicle_id: ID of the vehicle
            device_type: Type of device (BM6, BM2, etc.)
            reading: Battery reading data

        Returns:
            True if storage was successful or buffered
        """
        self.metrics.total_writes += 1

        # If not connected, buffer the reading
        if not self.connected or not self.write_api:
            return await self._buffer_reading(
                device_id,
                vehicle_id,
                device_type,
                reading,
            )

        # Get retention policy for this measurement
        retention_policy = self._get_retention_policy_for_measurement(reading)

        # Attempt to store directly
        success = await self._store_reading_internal(
            device_id,
            vehicle_id,
            device_type,
            reading,
            retention_policy,
        )

        if not success:
            # If direct storage failed, buffer the reading
            return await self._buffer_reading(
                device_id,
                vehicle_id,
                device_type,
                reading,
                retention_policy,
            )

        return True

    async def _store_reading_internal(
        self,
        device_id: str,
        vehicle_id: str,
        device_type: str,
        reading: dict[str, Any],
        retention_policy: str | None = None,
    ) -> bool:
        """
        Store a reading directly to InfluxDB.

        Args:
            device_id: MAC address of the device
            vehicle_id: ID of the vehicle
            device_type: Type of device (BM6, BM2, etc.)
            reading: Battery reading data
            retention_policy: Retention policy to use

        Returns:
            True if storage was successful
        """
        start_time = time.time()

        if not self.connected or not self.write_api:
            return False

        try:
            # Get device and vehicle info for additional tagging
            device_config = (
                self.config.get_config("devices").get("devices", {}).get(device_id, {})
            )
            vehicle_config = (
                self.config.get_config("vehicles")
                .get("vehicles", {})
                .get(vehicle_id, {})
            )

            # Get database name from config
            influx_config = self._get_influx_config()
            database = influx_config["database"]

            # Create data point for InfluxDB
            point_data = {
                "measurement": "battery_reading",
                "tags": {
                    "device_id": device_id,
                    "vehicle_id": vehicle_id,
                    "device_type": device_type,
                    "device_name": device_config.get("name", "Unknown"),
                    "vehicle_name": vehicle_config.get("name", "Unknown"),
                },
                "fields": reading,
                "time": datetime.now(timezone.utc),
            }

            # Write data point asynchronously with timeout
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    self.write_api.write,
                    database,
                    retention_policy,  # retention policy
                    point_data,
                    WritePrecision.S,  # second precision
                ),
                timeout=self._error_recovery_config.connection_timeout_seconds,
            )

            # Update metrics
            write_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            self.metrics.successful_writes += 1
            self.metrics.avg_write_time_ms = (
                self.metrics.avg_write_time_ms * (self.metrics.successful_writes - 1)
                + write_time
            ) / self.metrics.successful_writes

            self.logger.debug("Stored reading for device %s", device_id)
        except TimeoutError:
            self.logger.warning("Write operation timed out for device %s", device_id)
            self.metrics.failed_writes += 1
            # Mark connection as potentially failed
            if self._connection_state == ConnectionState.CONNECTED:
                self._connection_state = ConnectionState.FAILED
                retry_task = asyncio.create_task(
                    self._connect_with_retry(is_retry=True),
                )
                retry_task.add_done_callback(lambda _: None)  # Prevent warnings
            return False
        except Exception as e:
            self.metrics.failed_writes += 1
            self.logger.exception(
                "Failed to store reading for device %s",
                device_id,
            )
            # Check if this is a connection-related error
            if self._is_connection_error(e):
                self.logger.warning("Connection error detected, marking as failed")
                self.connected = False
                self._connection_state = ConnectionState.FAILED
                retry_task = asyncio.create_task(
                    self._connect_with_retry(is_retry=True),
                )
                retry_task.add_done_callback(lambda _: None)  # Prevent warnings
            return False
        else:
            return True

    async def _buffer_reading(
        self,
        device_id: str,
        vehicle_id: str,
        device_type: str,
        reading: dict[str, Any],
        retention_policy: str | None = None,
    ) -> bool:
        """
        Buffer a reading when direct storage is not possible.

        Args:
            device_id: MAC address of the device
            vehicle_id: ID of the vehicle
            device_type: Type of device (BM6, BM2, etc.)
            reading: Battery reading data
            retention_policy: Retention policy to use

        Returns:
            True if reading was buffered successfully
        """
        try:
            # Check if buffer is full
            if len(self._reading_buffer) >= self._error_recovery_config.buffer_max_size:
                self.logger.warning("Buffer full, dropping oldest reading")
                # Buffer will automatically drop oldest due to maxlen

            # Create buffered reading
            buffered_reading = BufferedReading(
                device_id=device_id,
                vehicle_id=vehicle_id,
                device_type=device_type,
                reading=reading.copy(),
                timestamp=datetime.now(timezone.utc),
                retention_policy=retention_policy,
            )

            # Add to buffer
            self._reading_buffer.append(buffered_reading)

            self.logger.debug(
                "Buffered reading for device %s (buffer size: %d)",
                device_id,
                len(self._reading_buffer),
            )
        except Exception:
            self.logger.exception(
                "Failed to buffer reading for device %s",
                device_id,
            )
            return False
        else:
            return True

    def _is_connection_error(self, error: Exception) -> bool:
        """
        Check if an error indicates a connection problem.

        Args:
            error: Exception to check

        Returns:
            True if error indicates connection problem
        """
        error_str = str(error).lower()
        connection_indicators = [
            "connection",
            "timeout",
            "network",
            "unreachable",
            "refused",
            "reset",
            "broken",
            "closed",
            "unavailable",
        ]
        return any(indicator in error_str for indicator in connection_indicators)

    async def get_recent_readings(
        self,
        device_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get recent readings for a device from InfluxDB.

        Args:
            device_id: MAC address of the device
            limit: Maximum number of readings to return

        Returns:
            List of recent readings
        """
        start_time = time.time()
        self.metrics.total_reads += 1

        if not self.connected or not self.query_api:
            self.logger.warning("Storage not connected, cannot retrieve readings")
            self.metrics.failed_reads += 1
            return []

        try:
            # Get database name from config
            influx_config = self._get_influx_config()
            database = influx_config["database"]

            # Validate inputs to prevent injection
            if not device_id.replace(":", "").replace("-", "").isalnum():
                raise ValueError("Invalid device_id format")
            if not isinstance(limit, int) or limit <= 0 or limit > MAX_QUERY_LIMIT:
                raise ValueError("Invalid limit value")

            # Build InfluxDB query (inputs validated above)
            query = f"""
                SELECT * FROM "battery_reading"
                WHERE "device_id" = {influxql_quote(device_id)}
                ORDER BY time DESC
                LIMIT {limit}
            """  # nosec B608  # noqa: S608

            self.logger.debug(
                "Querying readings for device %s (limit: %d)",
                device_id,
                limit,
            )

            # Execute query asynchronously
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.query_api.query,
                query,
                database,
            )

            # Convert result to list of dictionaries
            readings = []
            if result:
                readings.extend(dict(point) for point in result.get_points())

            # Update metrics
            read_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            self.metrics.successful_reads += 1
            self.metrics.avg_read_time_ms = (
                self.metrics.avg_read_time_ms * (self.metrics.successful_reads - 1)
                + read_time
            ) / self.metrics.successful_reads

            self.logger.debug(
                "Retrieved %d readings for device %s",
                len(readings),
                device_id,
            )
        except Exception:
            self.metrics.failed_reads += 1
            self.logger.exception(
                "Failed to get readings for device %s",
                device_id,
            )
            return []
        else:
            return readings

    async def get_vehicle_summary(
        self,
        vehicle_id: str,
        hours: int = 24,
    ) -> dict[str, Any]:
        """
        Get summary statistics for a vehicle over a time period from InfluxDB.

        Args:
            vehicle_id: Vehicle ID
            hours: Number of hours to look back

        Returns:
            Summary statistics dictionary
        """
        if not self.connected or not self.query_api:
            self.logger.warning("Storage not connected, cannot retrieve summary")
            return self._empty_summary(vehicle_id, hours)

        try:
            # Get database name from config
            influx_config = self._get_influx_config()
            database = influx_config["database"]

            # Validate inputs to prevent injection
            if not vehicle_id.replace("_", "").replace("-", "").isalnum():
                raise ValueError("Invalid vehicle_id format")
            if (
                not isinstance(hours, (int, float))
                or hours <= 0
                or hours > MAX_HOURS_QUERY
            ):
                raise ValueError("Invalid hours value")

            # Build InfluxDB aggregation query (inputs validated above)
            query = f"""
                SELECT
                    MEAN("voltage") as avg_voltage,
                    MEAN("current") as avg_current,
                    MEAN("temperature") as avg_temperature,
                    COUNT("voltage") as reading_count
                FROM "battery_reading"
                WHERE "vehicle_id" = {influxql_quote(vehicle_id)}
                AND time > now() - {hours}h
            """  # nosec B608  # noqa: S608

            self.logger.debug(
                "Getting summary for vehicle %s (period: %d hours)",
                vehicle_id,
                hours,
            )

            # Execute query asynchronously
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.query_api.query,
                query,
                database,
            )

            # Process result
            if result:
                points = list(result.get_points())
                if points:
                    point = points[0]
                    return {
                        "vehicle_id": vehicle_id,
                        "period_hours": hours,
                        "avg_voltage": float(point.get("avg_voltage", 0.0) or 0.0),
                        "avg_current": float(point.get("avg_current", 0.0) or 0.0),
                        "avg_temperature": float(
                            point.get("avg_temperature", 0.0) or 0.0,
                        ),
                        "reading_count": int(point.get("reading_count", 0) or 0),
                    }

            # No data found
            return self._empty_summary(vehicle_id, hours)

        except Exception:
            self.logger.exception(
                "Failed to get summary for vehicle %s",
                vehicle_id,
            )
            return self._empty_summary(vehicle_id, hours)

    def _empty_summary(self, vehicle_id: str, hours: int) -> dict[str, Any]:
        """Return an empty summary dictionary."""
        return {
            "vehicle_id": vehicle_id,
            "period_hours": hours,
            "avg_voltage": 0.0,
            "avg_current": 0.0,
            "avg_temperature": 0.0,
            "reading_count": 0,
        }

    def is_connected(self) -> bool:
        """
        Check if storage backend is connected.

        Returns:
            True if connected
        """
        return self.connected

    async def health_check(self) -> bool:
        """
        Perform a health check on the InfluxDB storage backend.

        Returns:
            True if storage is healthy
        """
        try:
            # If not connected, try to connect first
            if not self.connected:
                return await self.connect()

            # If still not connected after connect attempt, fail
            if not self.client:
                return False

            # Ping the InfluxDB server
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.client.ping)

            # Update connection uptime
            if self._connection_start_time:
                self.metrics.connection_uptime_seconds = (
                    time.time() - self._connection_start_time
                )

            self.logger.debug("InfluxDB health check passed")
        except Exception:
            self.logger.exception("InfluxDB health check failed")
            # Mark as disconnected if health check fails
            self.connected = False
            self._connection_start_time = None
            return False
        else:
            return True


class StorageBackendFactory:
    """
    Factory class for creating storage backend instances.

    Provides a centralized way to create and configure different storage
    backends based on configuration settings.
    """

    _backends: ClassVar[dict[str, type[BaseStorageBackend]]] = {
        "influxdb": InfluxDBStorageBackend,
    }

    @classmethod
    def _register_example_backends(cls) -> None:
        """Register example backends if available."""
        try:
            from .storage_backends_examples import (  # noqa: PLC0415
                JSONFileStorageBackend,
                NullStorageBackend,
            )

            cls._backends["json"] = JSONFileStorageBackend
            cls._backends["null"] = NullStorageBackend
        except ImportError:
            pass  # Example backends not available

    @classmethod
    def create_backend(
        cls,
        backend_type: str,
        config_manager: ConfigManager,
    ) -> BaseStorageBackend:
        """
        Create a storage backend instance.

        Args:
            backend_type: Type of backend to create ("influxdb", "json", "null", etc.)
            config_manager: Configuration manager instance

        Returns:
            Storage backend instance

        Raises:
            ValueError: If backend type is not supported
        """
        # Auto-register example backends on first use
        cls._register_example_backends()

        if backend_type not in cls._backends:
            available = ", ".join(cls._backends.keys())
            raise ValueError(
                f"Unsupported backend type '{backend_type}'. Available: {available}",
            )

        backend_class = cls._backends[backend_type]
        return backend_class(config_manager)

    @classmethod
    def get_available_backends(cls) -> list[str]:
        """
        Get list of available backend types.

        Returns:
            List of available backend type names
        """
        # Auto-register example backends
        cls._register_example_backends()
        return list(cls._backends.keys())

    @classmethod
    def register_backend(cls, backend_type: str, backend_class: type) -> None:
        """
        Register a new storage backend type.

        Args:
            backend_type: Name of the backend type
            backend_class: Backend class that inherits from BaseStorageBackend
        """
        if not issubclass(backend_class, BaseStorageBackend):
            raise TypeError("Backend class must inherit from BaseStorageBackend")

        cls._backends[backend_type] = backend_class


# Compatibility alias for existing code
DataStorage = InfluxDBStorageBackend
