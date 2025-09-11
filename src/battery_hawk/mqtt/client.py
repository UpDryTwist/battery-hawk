"""MQTT client interface for Battery Hawk."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import ssl
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from battery_hawk_driver.base.protocol import DeviceStatus

if TYPE_CHECKING:
    from collections.abc import Callable

from aiomqtt import Client, MqttError

from battery_hawk_driver.base.protocol import BatteryInfo

if TYPE_CHECKING:
    from battery_hawk.config.config_manager import ConfigManager
    from battery_hawk.core.engine import BatteryHawkCore
    from battery_hawk.core.state import DeviceState
from .topics import MQTTTopics

# Constants
MAX_PORT_NUMBER = 65535


class ConnectionState(Enum):
    """MQTT connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass
class QueuedMessage:
    """Represents a queued MQTT message."""

    topic: str
    payload: dict[str, Any] | str
    retain: bool
    timestamp: float
    retry_count: int = 0


@dataclass
class ReconnectionConfig:
    """Configuration for MQTT reconnection behavior."""

    max_retries: int = 10
    initial_retry_delay: float = 1.0
    max_retry_delay: float = 300.0  # 5 minutes
    backoff_multiplier: float = 2.0
    jitter_factor: float = 0.1
    connection_timeout: float = 30.0
    health_check_interval: float = 60.0
    message_queue_size: int = 1000
    message_retry_limit: int = 3


class MQTTConnectionError(Exception):
    """Raised when MQTT connection fails."""

    def __init__(self, message: str, broker: str = "", port: int = 0) -> None:
        """Initialize MQTT connection error."""
        super().__init__(message)
        self.broker = broker
        self.port = port


class MQTTInterface:
    """
    MQTT interface for Battery Hawk.

    Provides async MQTT client functionality with automatic reconnection,
    configuration validation, and proper error handling.
    """

    def __init__(self, config_manager: ConfigManager) -> None:
        """
        Initialize MQTT interface.

        Args:
            config_manager: Configuration manager instance for accessing MQTT settings.
        """
        self.config_manager = config_manager
        self.logger = logging.getLogger("battery_hawk.mqtt")
        self._client: Client | None = None
        self._connection_state = ConnectionState.DISCONNECTED
        self._message_handlers: dict[str, Callable[[str, str], None]] = {}

        # Get initial configuration
        self._mqtt_config = self._get_mqtt_config()
        self._reconnection_config = self._get_reconnection_config()

        # Initialize topic helper with configured prefix
        topic_prefix = self._mqtt_config.get("topic_prefix", "battery_hawk")
        self.topics = MQTTTopics(prefix=topic_prefix)

        # Connection management
        self._reconnect_task: asyncio.Task | None = None
        self._health_check_task: asyncio.Task | None = None
        self._message_processor_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()

        # Message queuing for resilience
        self._message_queue: deque[QueuedMessage] = deque(
            maxlen=self._reconnection_config.message_queue_size,
        )
        self._queue_lock = asyncio.Lock()

        # Connection tracking
        self._last_connection_attempt = 0.0
        self._consecutive_failures = 0
        self._connection_start_time = 0.0

        # Statistics
        self._stats = {
            "total_connections": 0,
            "total_disconnections": 0,
            "total_reconnections": 0,
            "messages_published": 0,
            "messages_queued": 0,
            "messages_failed": 0,
        }

        # Register for config changes
        self.config_manager.register_listener(self._on_config_change)

    def _get_mqtt_config(self) -> dict[str, Any]:
        """Get and validate MQTT configuration."""
        system_config = self.config_manager.get_config("system")
        mqtt_config = system_config.get("mqtt", {})

        # Validate required configuration
        if not mqtt_config.get("enabled", False):
            self.logger.info("MQTT is disabled in configuration")
            return mqtt_config

        required_fields = ["broker", "port", "topic_prefix"]
        missing_fields = [
            field for field in required_fields if not mqtt_config.get(field)
        ]

        if missing_fields:
            raise ValueError(
                f"Missing required MQTT configuration fields: {missing_fields}",
            )

        # Validate port range
        port = mqtt_config.get("port", 1883)
        if not isinstance(port, int) or port < 1 or port > MAX_PORT_NUMBER:
            raise ValueError(
                f"Invalid MQTT port: {port}. Must be between 1 and {MAX_PORT_NUMBER}",
            )

        # Validate QoS level
        qos = mqtt_config.get("qos", 1)
        if qos not in [0, 1, 2]:
            raise ValueError(f"Invalid MQTT QoS level: {qos}. Must be 0, 1, or 2")

        self.logger.info(
            "MQTT configuration validated: broker=%s, port=%d, topic_prefix=%s",
            mqtt_config["broker"],
            port,
            mqtt_config["topic_prefix"],
        )

        return mqtt_config

    def _get_reconnection_config(self) -> ReconnectionConfig:
        """Get and validate reconnection configuration."""
        mqtt_config = self._mqtt_config

        return ReconnectionConfig(
            max_retries=mqtt_config.get("max_retries", 10),
            initial_retry_delay=mqtt_config.get("initial_retry_delay", 1.0),
            max_retry_delay=mqtt_config.get("max_retry_delay", 300.0),
            backoff_multiplier=mqtt_config.get("backoff_multiplier", 2.0),
            jitter_factor=mqtt_config.get("jitter_factor", 0.1),
            connection_timeout=mqtt_config.get("connection_timeout", 30.0),
            health_check_interval=mqtt_config.get("health_check_interval", 60.0),
            message_queue_size=mqtt_config.get("message_queue_size", 1000),
            message_retry_limit=mqtt_config.get("message_retry_limit", 3),
        )

    def _on_config_change(self, section: str, _config: dict[str, Any]) -> None:
        """Handle configuration changes."""
        if section == "system":
            old_config = self._mqtt_config.copy()
            old_reconnection_config = self._reconnection_config
            try:
                self._mqtt_config = self._get_mqtt_config()
                self._reconnection_config = self._get_reconnection_config()

                # Check if MQTT-relevant config changed
                mqtt_fields = [
                    "broker",
                    "port",
                    "username",
                    "password",
                    "tls",
                    "topic_prefix",
                ]
                config_changed = any(
                    old_config.get(field) != self._mqtt_config.get(field)
                    for field in mqtt_fields
                )

                # Check if reconnection config changed
                reconnection_changed = (
                    old_reconnection_config.message_queue_size
                    != self._reconnection_config.message_queue_size
                )

                if reconnection_changed:
                    # Update message queue size if it changed
                    new_queue = deque(
                        self._message_queue,
                        maxlen=self._reconnection_config.message_queue_size,
                    )
                    self._message_queue = new_queue

                if (
                    config_changed
                    and self._connection_state == ConnectionState.CONNECTED
                ):
                    self.logger.info("MQTT configuration changed, reconnecting...")
                    task = asyncio.create_task(self._initiate_reconnection())
                    # Store task reference to prevent garbage collection
                    task.add_done_callback(lambda _: None)

            except Exception:
                self.logger.exception("Failed to update MQTT configuration")

    async def connect(self) -> None:
        """
        Connect to MQTT broker with robust reconnection logic.

        Raises:
            MQTTConnectionError: If connection fails after retries.
            ValueError: If configuration is invalid.
        """
        if not self._mqtt_config.get("enabled", False):
            self.logger.info("MQTT is disabled, skipping connection")
            return

        if self._connection_state == ConnectionState.CONNECTED:
            self.logger.warning("Already connected to MQTT broker")
            return

        if self._connection_state == ConnectionState.CONNECTING:
            self.logger.warning("Connection already in progress")
            return

        await self._connect_with_retry()

    def _prepare_client_kwargs(self) -> dict[str, Any]:
        """Prepare connection parameters for MQTT client."""
        broker = self._mqtt_config["broker"]
        port = self._mqtt_config["port"]

        client_kwargs = {
            "hostname": broker,
            "port": port,
            "keepalive": self._mqtt_config.get("keepalive", 60),
            # Note: aiomqtt doesn't accept timeout in constructor
            # Timeout is handled via asyncio.wait_for() in connection logic
        }

        # Add authentication if configured
        username = self._mqtt_config.get("username")
        password = self._mqtt_config.get("password")
        if username:
            client_kwargs["username"] = username
            if password:
                client_kwargs["password"] = password

        # Add TLS if configured
        if self._mqtt_config.get("tls", False):
            ssl_context = ssl.create_default_context()

            # Configure custom certificates if provided
            ca_cert = self._mqtt_config.get("ca_cert")
            cert_file = self._mqtt_config.get("cert_file")
            key_file = self._mqtt_config.get("key_file")

            if ca_cert:
                ssl_context.load_verify_locations(ca_cert)
            if cert_file and key_file:
                ssl_context.load_cert_chain(cert_file, key_file)

            client_kwargs["tls_context"] = ssl_context

        # DEBUG: Log all connection parameters including credentials (sensitive!)
        # Note: This will log sensitive information (username/password). Ensure DEBUG level is used only in safe environments.
        self.logger.debug(
            "MQTT connection parameters: hostname=%s, port=%s, keepalive=%s, username=%s, password=%s, tls=%s, ca_cert=%s, cert_file=%s, key_file=%s",
            broker,
            port,
            self._mqtt_config.get("keepalive", 60),
            username,
            password,
            self._mqtt_config.get("tls", False),
            self._mqtt_config.get("ca_cert"),
            self._mqtt_config.get("cert_file"),
            self._mqtt_config.get("key_file"),
        )

        return client_kwargs

    async def _attempt_single_connection(self, client_kwargs: dict[str, Any]) -> bool:
        """Attempt a single connection to MQTT broker."""
        try:
            # Create client with timeout
            self._client = Client(**client_kwargs)

            # Use asyncio.wait_for to enforce connection timeout
            await asyncio.wait_for(
                self._client.__aenter__(),
                timeout=self._reconnection_config.connection_timeout,
            )

            # Connection successful
            self._connection_state = ConnectionState.CONNECTED
            self._consecutive_failures = 0
            self._stats["total_connections"] += 1

            broker = self._mqtt_config["broker"]
            port = self._mqtt_config["port"]
            self.logger.info(
                "Successfully connected to MQTT broker at %s:%d",
                broker,
                port,
            )

            # Start background tasks
            await self._start_background_tasks()

            # Process any queued messages
            task = asyncio.create_task(self._process_message_queue())
            task.add_done_callback(lambda _: None)

        except (MqttError, OSError, TimeoutError) as e:
            self._consecutive_failures += 1
            # Detailed DEBUG logging for connection failure (includes sensitive info)
            self.logger.debug(
                "MQTT single connection attempt failed: error=%r, hostname=%s, port=%s, keepalive=%s, username=%s, password=%s, tls=%s, timeout=%s",
                e,
                client_kwargs.get("hostname"),
                client_kwargs.get("port"),
                client_kwargs.get("keepalive"),
                client_kwargs.get("username"),
                client_kwargs.get("password"),
                bool(client_kwargs.get("tls_context")),
                self._reconnection_config.connection_timeout,
                exc_info=True,
            )
            raise
        else:
            return True

    async def _handle_retry_delay(self, attempt: int, max_retries: int) -> bool:
        """Handle retry delay with early exit on shutdown. Returns True if should continue."""
        retry_delay = self._calculate_retry_delay(attempt)
        self.logger.warning(
            "MQTT connection attempt %d/%d failed. Retrying in %.1fs...",
            attempt + 1,
            max_retries + 1,
            retry_delay,
        )

        # Wait with early exit on shutdown
        try:
            await asyncio.wait_for(
                self._shutdown_event.wait(),
                timeout=retry_delay,
            )
            # Shutdown requested during wait
            self._connection_state = ConnectionState.DISCONNECTED
        except TimeoutError:
            # Normal retry delay completed
            return True
        else:
            return False

    async def _connect_with_retry(self) -> None:
        """Connect to MQTT broker with retry logic."""
        self._connection_state = ConnectionState.CONNECTING
        self._connection_start_time = time.time()

        broker = self._mqtt_config["broker"]
        port = self._mqtt_config["port"]
        self.logger.info("Connecting to MQTT broker at %s:%d", broker, port)

        client_kwargs = self._prepare_client_kwargs()
        max_retries = self._reconnection_config.max_retries
        last_error = None

        for attempt in range(max_retries + 1):
            if self._shutdown_event.is_set():
                self.logger.info("Shutdown requested, aborting connection attempt")
                self._connection_state = ConnectionState.DISCONNECTED
                return

            self._last_connection_attempt = time.time()

            try:
                if await self._attempt_single_connection(client_kwargs):
                    return  # Connection successful
            except (MqttError, OSError, TimeoutError) as e:
                last_error = e
                # Detailed debug info on failure parameters (sensitive info included)
                self.logger.debug(
                    "MQTT connect_with_retry attempt %d/%d failed: error=%r, hostname=%s, port=%s, keepalive=%s, username=%s, password=%s, tls=%s",
                    attempt + 1,
                    max_retries + 1,
                    e,
                    client_kwargs.get("hostname"),
                    client_kwargs.get("port"),
                    client_kwargs.get("keepalive"),
                    client_kwargs.get("username"),
                    client_kwargs.get("password"),
                    bool(client_kwargs.get("tls_context")),
                    exc_info=True,
                )

                if attempt < max_retries:
                    if not await self._handle_retry_delay(attempt, max_retries):
                        return  # Shutdown requested
                else:
                    self.logger.exception(
                        "MQTT connection attempt %d/%d failed",
                        attempt + 1,
                        max_retries + 1,
                    )

        # If we get here, all attempts failed
        self._connection_state = ConnectionState.FAILED
        error_msg = f"Failed to connect to MQTT broker after {max_retries + 1} attempts: {last_error}"
        self.logger.error(error_msg)
        raise MQTTConnectionError(error_msg, broker, port) from last_error

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff and jitter."""
        base_delay = self._reconnection_config.initial_retry_delay
        max_delay = self._reconnection_config.max_retry_delay
        multiplier = self._reconnection_config.backoff_multiplier
        jitter_factor = self._reconnection_config.jitter_factor

        # Exponential backoff
        delay = base_delay * (multiplier**attempt)
        delay = min(delay, max_delay)

        # Add jitter to avoid thundering herd
        jitter = delay * jitter_factor * (0.5 - time.time() % 1)
        delay += jitter

        return max(delay, 0.1)  # Minimum 100ms delay

    async def _start_background_tasks(self) -> None:
        """Start background monitoring tasks."""
        # Start health check task
        if not self._health_check_task or self._health_check_task.done():
            self._health_check_task = asyncio.create_task(self._health_check_loop())

        # Start message processor task
        if not self._message_processor_task or self._message_processor_task.done():
            self._message_processor_task = asyncio.create_task(
                self._message_processor_loop(),
            )

    async def _health_check_loop(self) -> None:
        """Periodically check connection health."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self._reconnection_config.health_check_interval)

                if self._connection_state == ConnectionState.CONNECTED:
                    # Check if client is still valid
                    if not self._client or not hasattr(self._client, "_client"):
                        self.logger.warning(
                            "MQTT client became invalid, initiating reconnection",
                        )
                        await self._initiate_reconnection()
                        continue

                    # Could add ping/pong check here if needed
                    self.logger.debug("MQTT connection health check passed")

            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Error in health check")

    async def _message_processor_loop(self) -> None:
        """Process queued messages when connection is available."""
        while not self._shutdown_event.is_set():
            try:
                if (
                    self._connection_state == ConnectionState.CONNECTED
                    and self._message_queue
                ):
                    await self._process_message_queue()

                # Check every 5 seconds
                await asyncio.sleep(5.0)

            except asyncio.CancelledError:  # noqa: PERF203
                break
            except Exception:
                self.logger.exception("Error in message processor")

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker and cleanup resources."""
        if self._connection_state == ConnectionState.DISCONNECTED:
            self.logger.debug("Already disconnected from MQTT broker")
            return

        self.logger.info("Disconnecting from MQTT broker")

        # Signal shutdown to background tasks
        self._shutdown_event.set()

        # Update connection state
        old_state = self._connection_state
        self._connection_state = ConnectionState.DISCONNECTED

        if old_state == ConnectionState.CONNECTED:
            self._stats["total_disconnections"] += 1

        # Cancel and wait for background tasks
        tasks_to_cancel = [
            self._reconnect_task,
            self._health_check_task,
            self._message_processor_task,
        ]

        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        # Disconnect client
        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
            except (MqttError, OSError, TimeoutError) as e:
                self.logger.warning("Error during MQTT disconnect: %s", e)
            finally:
                self._client = None

        # Clear shutdown event for potential future connections
        self._shutdown_event.clear()

        self.logger.info("Disconnected from MQTT broker")

    async def _initiate_reconnection(self) -> None:
        """Initiate reconnection process."""
        if self._connection_state == ConnectionState.RECONNECTING:
            self.logger.debug("Reconnection already in progress")
            return

        if self._shutdown_event.is_set():
            self.logger.debug("Shutdown in progress, skipping reconnection")
            return

        self.logger.info("Initiating MQTT reconnection")
        self._connection_state = ConnectionState.RECONNECTING
        self._stats["total_reconnections"] += 1

        # Cancel existing reconnect task if any
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reconnect_task

        # Start new reconnection task
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Reconnection loop with exponential backoff."""
        attempt = 0
        max_retries = self._reconnection_config.max_retries

        while not self._shutdown_event.is_set() and attempt < max_retries:
            try:
                # Disconnect cleanly first
                if self._client:
                    try:
                        await self._client.__aexit__(None, None, None)
                    except (MqttError, OSError) as e:
                        self.logger.debug("Error during reconnection disconnect: %s", e)
                    finally:
                        self._client = None

                # Attempt to reconnect
                await self._connect_with_retry()

                # If we get here, reconnection was successful
                self.logger.info("MQTT reconnection successful")

            except MQTTConnectionError as e:  # noqa: PERF203
                attempt += 1
                if attempt < max_retries:
                    retry_delay = self._calculate_retry_delay(attempt)
                    self.logger.warning(
                        "Reconnection attempt %d/%d failed: %s. Retrying in %.1fs...",
                        attempt,
                        max_retries,
                        e,
                        retry_delay,
                    )

                    # Wait with early exit on shutdown
                    try:
                        await asyncio.wait_for(
                            self._shutdown_event.wait(),
                            timeout=retry_delay,
                        )
                        # Shutdown requested during wait
                    except TimeoutError:
                        # Normal retry delay completed
                        continue
                    else:
                        # Shutdown requested during wait
                        return
                else:
                    self.logger.exception(
                        "Reconnection failed after %d attempts",
                        max_retries,
                    )
                    self._connection_state = ConnectionState.FAILED
                    return

            except Exception:
                self.logger.exception("Unexpected error during reconnection")
                attempt += 1
                if attempt >= max_retries:
                    self._connection_state = ConnectionState.FAILED
                    return
            else:
                # Reconnection successful
                return

        if self._shutdown_event.is_set():
            self.logger.info("Reconnection cancelled due to shutdown")
        else:
            self.logger.error("Reconnection failed after maximum attempts")
            self._connection_state = ConnectionState.FAILED

    @property
    def connected(self) -> bool:
        """Check if connected to MQTT broker."""
        return self._connection_state == ConnectionState.CONNECTED

    @property
    def connection_state(self) -> ConnectionState:
        """Get current connection state."""
        return self._connection_state

    @property
    def stats(self) -> dict[str, Any]:
        """Get connection and message statistics."""
        return {
            **self._stats,
            "connection_state": self._connection_state.value,
            "consecutive_failures": self._consecutive_failures,
            "queue_size": len(self._message_queue),
            "last_connection_attempt": self._last_connection_attempt,
        }

    def _get_topic(self, topic: str) -> str:
        """Get full topic with prefix."""
        prefix = self._mqtt_config.get("topic_prefix", "batteryhawk")
        return f"{prefix}/{topic}"

    async def publish(
        self,
        topic: str,
        payload: dict[str, Any] | str,
        *,
        retain: bool = False,
    ) -> None:
        """
        Publish message to MQTT topic.

        Args:
            topic: Topic to publish to (without prefix).
            payload: Message payload (dict will be JSON-encoded).
            retain: Whether to retain the message.

        Raises:
            MQTTConnectionError: If not connected to broker.
            ValueError: If payload cannot be serialized.
        """
        # Create queued message
        queued_msg = QueuedMessage(
            topic=topic,
            payload=payload,
            retain=retain,
            timestamp=time.time(),
        )

        # Try immediate publish if connected
        if self._connection_state == ConnectionState.CONNECTED and self._client:
            try:
                await self._publish_message(queued_msg)
                self._stats["messages_published"] += 1
            except MQTTConnectionError as e:
                self.logger.warning("Immediate publish failed: %s", e)
                # Fall through to queuing
            else:
                # Message published successfully
                return

        # Queue message for later delivery
        await self._queue_message(queued_msg)

    async def _publish_message(self, msg: QueuedMessage) -> None:
        """Publish a single message to MQTT broker."""
        if not self._client:
            raise MQTTConnectionError("No MQTT client available")

        full_topic = self._get_topic(msg.topic)
        qos = self._mqtt_config.get("qos", 1)

        # Serialize payload if it's a dict
        if isinstance(msg.payload, dict):
            try:
                message = json.dumps(msg.payload, default=str)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Failed to serialize payload: {e}") from e
        else:
            message = str(msg.payload)

        try:
            await self._client.publish(full_topic, message, qos=qos, retain=msg.retain)
            self.logger.debug(
                "Published message to topic '%s' (QoS %d, retain=%s)",
                full_topic,
                qos,
                msg.retain,
            )
        except (MqttError, OSError) as e:
            self.logger.warning("Failed to publish to topic '%s': %s", full_topic, e)
            # Check if this is a connection error
            if self._is_connection_error(e):
                self.logger.warning(
                    "Connection error detected, initiating reconnection...",
                )
                task = asyncio.create_task(self._initiate_reconnection())
                task.add_done_callback(lambda _: None)
            raise MQTTConnectionError(f"Failed to publish message: {e}") from e

    async def _queue_message(self, msg: QueuedMessage) -> None:
        """Queue message for later delivery."""
        async with self._queue_lock:
            # Check if queue is full
            if len(self._message_queue) >= self._reconnection_config.message_queue_size:
                # Remove oldest message to make room
                removed = self._message_queue.popleft()
                self.logger.warning(
                    "Message queue full, dropping oldest message to topic '%s'",
                    removed.topic,
                )

            self._message_queue.append(msg)
            self._stats["messages_queued"] += 1

            self.logger.debug(
                "Queued message to topic '%s' (queue size: %d)",
                msg.topic,
                len(self._message_queue),
            )

    async def _process_message_queue(self) -> None:
        """Process queued messages when connection is available."""
        if self._connection_state != ConnectionState.CONNECTED or not self._client:
            return

        processed_count = 0
        failed_count = 0

        async with self._queue_lock:
            # Process messages in order
            while (
                self._message_queue
                and self._connection_state == ConnectionState.CONNECTED
            ):
                msg = self._message_queue.popleft()

                try:
                    await self._publish_message(msg)
                    processed_count += 1
                    self._stats["messages_published"] += 1

                except MQTTConnectionError:
                    # Connection error - requeue message and stop processing
                    msg.retry_count += 1
                    if msg.retry_count <= self._reconnection_config.message_retry_limit:
                        self._message_queue.appendleft(msg)  # Put back at front
                        self.logger.debug(
                            "Requeued message to topic '%s' (retry %d/%d)",
                            msg.topic,
                            msg.retry_count,
                            self._reconnection_config.message_retry_limit,
                        )
                    else:
                        self.logger.exception(
                            "Dropping message to topic '%s' after %d retries",
                            msg.topic,
                            msg.retry_count,
                        )
                        self._stats["messages_failed"] += 1
                    break

                except ValueError:
                    # Serialization error - drop message
                    self.logger.exception(
                        "Dropping message to topic '%s' due to serialization error",
                        msg.topic,
                    )
                    failed_count += 1
                    self._stats["messages_failed"] += 1

        if processed_count > 0:
            self.logger.info(
                "Processed %d queued messages (%d failed)",
                processed_count,
                failed_count,
            )

    async def subscribe(self, topic: str, handler: Callable[[str, str], None]) -> None:
        """
        Subscribe to MQTT topic.

        Args:
            topic: Topic to subscribe to (without prefix).
            handler: Callback function to handle received messages.

        Raises:
            MQTTConnectionError: If not connected to broker.
        """
        if self._connection_state != ConnectionState.CONNECTED or not self._client:
            raise MQTTConnectionError("Not connected to MQTT broker")

        full_topic = self._get_topic(topic)
        qos = self._mqtt_config.get("qos", 1)

        try:
            await self._client.subscribe(full_topic, qos=qos)
            self._message_handlers[full_topic] = handler

            self.logger.info("Subscribed to topic '%s' (QoS %d)", full_topic, qos)

            # Start message listening task if not already running
            if not hasattr(self, "_message_task") or self._message_task.done():
                self._message_task = asyncio.create_task(self._handle_messages())

        except (MqttError, OSError) as e:
            self.logger.exception("Failed to subscribe to topic '%s'", full_topic)
            raise MQTTConnectionError(f"Failed to subscribe to topic: {e}") from e

    async def unsubscribe(self, topic: str) -> None:
        """
        Unsubscribe from MQTT topic.

        Args:
            topic: Topic to unsubscribe from (without prefix).

        Raises:
            MQTTConnectionError: If not connected to broker.
        """
        if self._connection_state != ConnectionState.CONNECTED or not self._client:
            raise MQTTConnectionError("Not connected to MQTT broker")

        full_topic = self._get_topic(topic)

        try:
            await self._client.unsubscribe(full_topic)
            self._message_handlers.pop(full_topic, None)

            self.logger.info("Unsubscribed from topic '%s'", full_topic)

        except (MqttError, OSError) as e:
            self.logger.exception("Failed to unsubscribe from topic '%s'", full_topic)
            raise MQTTConnectionError(f"Failed to unsubscribe from topic: {e}") from e

    async def _handle_messages(self) -> None:
        """Handle incoming MQTT messages."""
        if not self._client:
            return

        try:
            async for message in self._client.messages:
                topic = message.topic.value
                payload = (
                    message.payload.decode("utf-8")
                    if isinstance(message.payload, bytes)
                    else str(message.payload)
                )

                self.logger.debug(
                    "Received message on topic '%s': %s",
                    topic,
                    payload,
                )

                # Find and call handler
                handler = self._message_handlers.get(topic)
                if handler:
                    try:
                        handler(topic, payload)
                    except Exception:
                        self.logger.exception(
                            "Error in message handler for topic '%s'",
                            topic,
                        )
                else:
                    self.logger.warning(
                        "No handler registered for topic '%s'",
                        topic,
                    )

        except asyncio.CancelledError:
            self.logger.debug("Message handling task cancelled")
        except Exception as e:
            self.logger.exception("Error in message handling")
            # Try to reconnect on connection errors
            if self._is_connection_error(e):
                self.logger.warning(
                    "Connection error in message handling, initiating reconnection...",
                )
                task = asyncio.create_task(self._initiate_reconnection())
                task.add_done_callback(lambda _: None)

    def _is_connection_error(self, error: Exception) -> bool:
        """Check if error is a connection-related error."""
        return isinstance(
            error,
            (MqttError, OSError, ConnectionError, asyncio.TimeoutError),
        )


class MQTTPublisher:
    """
    High-level MQTT publisher for Battery Hawk data types.

    This class provides specialized publishing methods for different types of
    Battery Hawk data with appropriate topic structure, QoS levels, and retention
    flags based on message type.
    """

    def __init__(self, mqtt_interface: MQTTInterface) -> None:
        """
        Initialize MQTT publisher.

        Args:
            mqtt_interface: MQTT interface instance for low-level operations.
        """
        self.mqtt_interface = mqtt_interface
        self.logger = logging.getLogger("battery_hawk.mqtt.publisher")

    async def publish_device_reading(
        self,
        device_id: str,
        reading: BatteryInfo,
        *,
        vehicle_id: str | None = None,
        device_type: str | None = None,
    ) -> None:
        """
        Publish device reading data.

        Args:
            device_id: Device MAC address or identifier.
            reading: Battery reading data.
            vehicle_id: Optional vehicle ID if device is associated with a vehicle.
            device_type: Optional device type (e.g., "BM2", "BM6").

        Raises:
            MQTTConnectionError: If not connected to broker.
            ValueError: If reading data cannot be serialized.
        """
        topic = f"device/{device_id}/reading"

        # Build payload with reading data
        payload = {
            "device_id": device_id,
            "timestamp": reading.timestamp or datetime.now(timezone.utc).isoformat(),
            "voltage": reading.voltage,
            "current": reading.current,
            "temperature": reading.temperature,
            "state_of_charge": reading.state_of_charge,
        }

        # Add optional fields if available
        if reading.capacity is not None:
            payload["capacity"] = reading.capacity
        if reading.cycles is not None:
            payload["cycles"] = reading.cycles
        if vehicle_id:
            payload["vehicle_id"] = vehicle_id
        if device_type:
            payload["device_type"] = device_type
        if reading.extra:
            payload["extra"] = reading.extra

        # Calculate power if voltage and current are available
        if reading.voltage is not None and reading.current is not None:
            payload["power"] = reading.voltage * reading.current

        try:
            # Use QoS 1 for readings (important but not critical)
            # No retention for readings (they're time-series data)
            await self.mqtt_interface.publish(topic, payload, retain=False)
            self.logger.debug(
                "Published device reading for %s (vehicle: %s)",
                device_id,
                vehicle_id or "none",
            )
        except Exception:
            self.logger.exception(
                "Failed to publish device reading for %s",
                device_id,
            )
            raise

    def _build_reading_components(
        self,
        reading: BatteryInfo | dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Build flattened and nested reading components for status payload.

        Returns a tuple of (flat_fields, nested_snapshot).
        """
        if isinstance(reading, dict):
            v = reading.get("voltage")
            c = reading.get("current")
            t = reading.get("temperature")
            soc = reading.get("state_of_charge")
            cap = reading.get("capacity")
            cyc = reading.get("cycles")
            r_ts = reading.get("timestamp")
            extra = reading.get("extra")
        else:
            v = reading.voltage
            c = reading.current
            t = reading.temperature
            soc = reading.state_of_charge
            cap = getattr(reading, "capacity", None)
            cyc = getattr(reading, "cycles", None)
            r_ts = getattr(reading, "timestamp", None)
            extra = getattr(reading, "extra", None)

        flat: dict[str, Any] = {
            "voltage": v,
            "current": c,
            "temperature": t,
            "state_of_charge": soc,
        }
        if cap is not None:
            flat["capacity"] = cap
        if cyc is not None:
            flat["cycles"] = cyc
        if extra:
            flat["reading_extra"] = extra
        if (
            v is not None
            and c is not None
            and isinstance(v, (int, float))
            and isinstance(c, (int, float))
        ):
            flat["power"] = v * c

        nested: dict[str, Any] = {
            "voltage": v,
            "current": c,
            "temperature": t,
            "state_of_charge": soc,
        }
        if cap is not None:
            nested["capacity"] = cap
        if cyc is not None:
            nested["cycles"] = cyc
        if extra:
            nested["extra"] = extra
        if r_ts is not None:
            nested["timestamp"] = r_ts
        if (
            v is not None
            and c is not None
            and isinstance(v, (int, float))
            and isinstance(c, (int, float))
        ):
            nested["power"] = v * c

        return flat, nested

    async def publish_device_status(
        self,
        device_id: str,
        status: DeviceStatus,
        *,
        device_type: str | None = None,
        vehicle_id: str | None = None,
        reading: BatteryInfo | dict[str, Any] | None = None,
    ) -> None:
        """
        Publish device status change.

        The retained device status payload also includes the latest known reading
        values when provided, so that subscribers to the status topic can obtain the
        most recent battery metrics without separately fetching the readings stream.

        Args:
            device_id: Device MAC address or identifier.
            status: Device status information.
            device_type: Optional device type (e.g., "BM2", "BM6").
            vehicle_id: Optional vehicle id if associated.
            reading: Optional latest reading to embed in the status payload.

        Raises:
            MQTTConnectionError: If not connected to broker.
            ValueError: If status data cannot be serialized.
        """
        topic = f"device/{device_id}/status"

        # Build payload with status data
        payload: dict[str, Any] = {
            "device_id": device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "connected": status.connected,
        }

        # Add optional fields if available
        if status.error_code is not None:
            payload["error_code"] = status.error_code
        if status.error_message:
            payload["error_message"] = status.error_message
        if status.protocol_version:
            payload["protocol_version"] = status.protocol_version
        if status.last_command:
            payload["last_command"] = status.last_command
        if device_type:
            payload["device_type"] = device_type
        if vehicle_id:
            payload["vehicle_id"] = vehicle_id
        if status.extra:
            payload["extra"] = status.extra

        # If a latest reading is provided, embed key reading values in the status
        if reading is not None:
            # Build flattened and nested components safely
            flat, nested = self._build_reading_components(reading)
            payload.update(flat)
            payload["latest_reading"] = nested

        try:
            # Use QoS 1 for status changes (important)
            # Retain status messages so new subscribers get last known state
            await self.mqtt_interface.publish(topic, payload, retain=True)
            self.logger.debug(
                "Published device status for %s (connected: %s)",
                device_id,
                status.connected,
            )
        except MQTTConnectionError:
            # Keep original exception type for callers that distinguish connection issues
            self.logger.exception(
                "Failed to publish device status for %s",
                device_id,
            )
            raise
        except Exception:
            # Narrow generic exceptions: log and re-raise to surface unexpected issues
            self.logger.exception(
                "Unexpected error publishing device status for %s",
                device_id,
            )
            raise

    async def publish_vehicle_summary(
        self,
        vehicle_id: str,
        summary_data: dict[str, Any],
    ) -> None:
        """
        Publish aggregated vehicle summary data.

        Args:
            vehicle_id: Vehicle identifier.
            summary_data: Aggregated vehicle data including device readings,
                         overall status, and calculated metrics.

        Raises:
            MQTTConnectionError: If not connected to broker.
            ValueError: If summary data cannot be serialized.
        """
        topic = f"vehicle/{vehicle_id}/summary"

        # Build payload with vehicle summary
        payload = {
            "vehicle_id": vehicle_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **summary_data,
        }

        try:
            # Use QoS 1 for vehicle summaries (important)
            # Retain vehicle summaries so new subscribers get last known state
            await self.mqtt_interface.publish(topic, payload, retain=True)
            self.logger.debug(
                "Published vehicle summary for %s",
                vehicle_id,
            )
        except Exception:
            self.logger.exception(
                "Failed to publish vehicle summary for %s",
                vehicle_id,
            )
            raise

    async def publish_system_status(
        self,
        status_data: dict[str, Any],
    ) -> None:
        """
        Publish system-wide status information.

        Args:
            status_data: System status data including core engine status,
                        storage system status, and component status.

        Raises:
            MQTTConnectionError: If not connected to broker.
            ValueError: If status data cannot be serialized.
        """
        topic = "system/status"

        # Build payload with system status
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **status_data,
        }

        try:
            # Use retain for new subscribers to get last known system status
            await self.mqtt_interface.publish(topic, payload, retain=True)
            self.logger.debug("Published system status")

        except Exception:
            self.logger.exception(
                "Failed to publish system status",
            )
            raise


class MQTTEventHandler:
    """
    Event handler registration system for connecting core engine events to MQTT publishing.

    This class manages the registration of event handlers with the core engine and
    coordinates the publishing of various data types to MQTT topics based on
    system events.
    """

    def __init__(
        self,
        core_engine: BatteryHawkCore,
        mqtt_publisher: MQTTPublisher,
    ) -> None:
        """
        Initialize MQTT event handler.

        Args:
            core_engine: Core engine instance to register event handlers with.
            mqtt_publisher: MQTT publisher instance for publishing messages.
        """
        self.core_engine = core_engine
        self.mqtt_publisher = mqtt_publisher
        self.logger = logging.getLogger("battery_hawk.mqtt.event_handler")

        # Track registered handlers for cleanup
        self._registered_handlers: dict[str, Callable] = {}

        # Track vehicle summary cache for efficient updates
        self._vehicle_summary_cache: dict[str, dict[str, Any]] = {}

    def register_all_handlers(self) -> None:
        """Register all event handlers with the core engine."""
        self.logger.info("Registering MQTT event handlers with core engine")

        # Register core engine event handlers
        self._register_core_engine_handlers()

        # Register state manager event handlers
        self._register_state_manager_handlers()

        self.logger.info("All MQTT event handlers registered successfully")

    def unregister_all_handlers(self) -> None:
        """Unregister all event handlers from the core engine."""
        self.logger.info("Unregistering MQTT event handlers")

        # Unregister core engine handlers
        for event_type, handler in self._registered_handlers.items():
            if event_type.startswith("core_"):
                actual_event_type = event_type[5:]  # Remove 'core_' prefix
                self.core_engine.remove_event_handler(actual_event_type, handler)

        # Unregister state manager handlers
        for event_type, handler in self._registered_handlers.items():
            if event_type.startswith("state_"):
                actual_event_type = event_type[6:]  # Remove 'state_' prefix
                self.core_engine.state_manager.unsubscribe_from_changes(
                    actual_event_type,
                    handler,
                )

        self._registered_handlers.clear()
        self.logger.info("All MQTT event handlers unregistered")

    def _register_core_engine_handlers(self) -> None:
        """Register event handlers with the core engine."""
        # Device discovered handler
        device_discovered_handler = self._create_async_handler(
            self.on_device_discovered,
        )
        self.core_engine.add_event_handler(
            "device_discovered",
            device_discovered_handler,
        )
        self._registered_handlers["core_device_discovered"] = device_discovered_handler

        # Vehicle associated handler
        vehicle_associated_handler = self._create_async_handler(
            self.on_vehicle_associated,
        )
        self.core_engine.add_event_handler(
            "vehicle_associated",
            vehicle_associated_handler,
        )
        self._registered_handlers["core_vehicle_associated"] = (
            vehicle_associated_handler
        )

        # System shutdown handler
        system_shutdown_handler = self._create_async_handler(self.on_system_shutdown)
        self.core_engine.add_event_handler("system_shutdown", system_shutdown_handler)
        self._registered_handlers["core_system_shutdown"] = system_shutdown_handler

    def _register_state_manager_handlers(self) -> None:
        """Register event handlers with the state manager."""
        # Device reading handler
        reading_handler = self._create_state_handler(self.on_device_reading)
        self.core_engine.state_manager.subscribe_to_changes("reading", reading_handler)
        self._registered_handlers["state_reading"] = reading_handler

        # Device status handler
        status_handler = self._create_state_handler(self.on_device_status_change)
        self.core_engine.state_manager.subscribe_to_changes("status", status_handler)
        self._registered_handlers["state_status"] = status_handler

        # Connection state handler
        connection_handler = self._create_state_handler(
            self.on_device_connection_change,
        )
        self.core_engine.state_manager.subscribe_to_changes(
            "connection",
            connection_handler,
        )
        self._registered_handlers["state_connection"] = connection_handler

        # Vehicle association handler
        vehicle_handler = self._create_state_handler(self.on_vehicle_update)
        self.core_engine.state_manager.subscribe_to_changes("vehicle", vehicle_handler)
        self._registered_handlers["state_vehicle"] = vehicle_handler

    def _create_async_handler(self, handler_method: Callable) -> Callable:
        """Create an async wrapper for core engine event handlers."""

        async def async_wrapper(event_data: dict[str, Any]) -> None:
            try:
                await handler_method(event_data)
            except Exception:
                self.logger.exception(
                    "Error in async event handler %s",
                    handler_method.__name__,
                )

        return async_wrapper

    def _create_state_handler(self, handler_method: Callable) -> Callable:
        """Create a wrapper for state manager event handlers."""

        def state_wrapper(
            mac_address: str,
            new_state: DeviceState | None,
            old_state: DeviceState | None,
        ) -> None:
            try:
                # Convert to async task
                task = asyncio.create_task(
                    handler_method(mac_address, new_state, old_state),
                )
                task.add_done_callback(lambda _: None)
            except Exception:
                self.logger.exception(
                    "Error in state event handler %s",
                    handler_method.__name__,
                )

        return state_wrapper

    async def on_device_discovered(self, event_data: dict[str, Any]) -> None:
        """
        Handle device discovered events.

        Args:
            event_data: Event data containing device discovery information.
        """
        try:
            mac_address = event_data.get("mac_address")
            device_type = event_data.get("device_type", "unknown")
            name = event_data.get("name", f"Device_{mac_address}")
            rssi = event_data.get("rssi")

            # Create discovery message payload
            discovery_payload = {
                "device_id": mac_address,
                "device_type": device_type,
                "name": name,
                "rssi": rssi,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "advertisement_data": event_data.get("advertisement_data", {}),
            }

            # Publish device discovery
            topic = "discovery/found"
            await self.mqtt_publisher.mqtt_interface.publish(
                topic,
                discovery_payload,
                retain=False,
            )

            self.logger.debug(
                "Published device discovery for %s (%s)",
                mac_address,
                device_type,
            )

        except Exception:
            self.logger.exception("Failed to handle device discovered event")

    async def on_device_reading(
        self,
        mac_address: str,
        new_state: DeviceState | None,
        old_state: DeviceState | None,  # noqa: ARG002
    ) -> None:
        """
        Handle device reading updates.

        Args:
            mac_address: Device MAC address.
            new_state: New device state with updated reading.
            old_state: Previous device state.
        """
        try:
            if not new_state or not new_state.latest_reading:
                return

            # Get device information
            device_info = self.core_engine.device_registry.get_device(mac_address)
            vehicle_id = (
                new_state.vehicle_id or device_info.get("vehicle_id")
                if device_info
                else None
            )
            device_type = new_state.device_type

            # Publish device reading
            await self.mqtt_publisher.publish_device_reading(
                device_id=mac_address,
                reading=new_state.latest_reading,
                vehicle_id=vehicle_id,
                device_type=device_type,
            )

            # Also update retained status with the latest reading snapshot
            await self.mqtt_publisher.publish_device_status(
                device_id=mac_address,
                status=new_state.device_status
                or DeviceStatus(connected=new_state.connected),
                device_type=device_type,
                vehicle_id=vehicle_id,
                reading=new_state.latest_reading,
            )

            # Update vehicle summary if device is associated with a vehicle
            if vehicle_id:
                await self._update_vehicle_summary(vehicle_id)

            self.logger.debug(
                "Published device reading for %s (vehicle: %s)",
                mac_address,
                vehicle_id or "none",
            )

        except Exception:
            self.logger.exception("Failed to handle device reading event")

    async def on_device_status_change(
        self,
        mac_address: str,
        new_state: DeviceState | None,
        old_state: DeviceState | None,  # noqa: ARG002
    ) -> None:
        """
        Handle device status changes.

        Args:
            mac_address: Device MAC address.
            new_state: New device state with updated status.
            old_state: Previous device state.
        """
        try:
            if not new_state or not new_state.device_status:
                return

            device_type = new_state.device_type

            # Publish device status, including latest reading and vehicle when available
            extra_kwargs: dict[str, Any] = {"device_type": device_type}
            if new_state.vehicle_id:
                extra_kwargs["vehicle_id"] = new_state.vehicle_id
            if new_state.latest_reading:
                extra_kwargs["reading"] = new_state.latest_reading

            await self.mqtt_publisher.publish_device_status(
                device_id=mac_address,
                status=new_state.device_status,
                **extra_kwargs,
            )

            # Update vehicle summary if device is associated with a vehicle
            if new_state.vehicle_id:
                await self._update_vehicle_summary(new_state.vehicle_id)

            self.logger.debug(
                "Published device status for %s (connected: %s)",
                mac_address,
                new_state.device_status.connected,
            )

        except Exception:
            self.logger.exception("Failed to handle device status change event")

    async def on_device_connection_change(
        self,
        mac_address: str,
        new_state: DeviceState | None,
        old_state: DeviceState | None,
    ) -> None:
        """
        Handle device connection state changes.

        Args:
            mac_address: Device MAC address.
            new_state: New device state with updated connection.
            old_state: Previous device state.
        """
        try:
            if not new_state:
                return

            # Check if connection state actually changed
            if old_state and old_state.connected == new_state.connected:
                return

            # Create a DeviceStatus object for connection state

            connection_status = DeviceStatus(
                connected=new_state.connected,
                error_message=new_state.last_connection_error,
            )

            # Publish connection status
            await self.mqtt_publisher.publish_device_status(
                device_id=mac_address,
                status=connection_status,
                device_type=new_state.device_type,
            )

            # Update vehicle summary if device is associated with a vehicle
            if new_state.vehicle_id:
                await self._update_vehicle_summary(new_state.vehicle_id)

            self.logger.debug(
                "Published connection change for %s (connected: %s)",
                mac_address,
                new_state.connected,
            )

        except Exception:
            self.logger.exception("Failed to handle device connection change event")

    async def on_vehicle_associated(self, event_data: dict[str, Any]) -> None:
        """
        Handle vehicle association events.

        Args:
            event_data: Event data containing vehicle association information.
        """
        try:
            mac_address = event_data.get("mac_address")
            vehicle_id = event_data.get("vehicle_id")
            device_type = event_data.get("device_type", "unknown")
            is_new_vehicle = event_data.get("new_vehicle", False)

            if not mac_address or not vehicle_id:
                return

            # Publish vehicle association event
            association_payload = {
                "device_id": mac_address,
                "vehicle_id": vehicle_id,
                "device_type": device_type,
                "new_vehicle": is_new_vehicle,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            }

            topic = f"vehicle/{vehicle_id}/device_associated"  # Custom topic for association events
            await self.mqtt_publisher.mqtt_interface.publish(
                topic,
                association_payload,
                retain=False,
            )

            # Update vehicle summary
            await self._update_vehicle_summary(vehicle_id)

            self.logger.debug(
                "Published vehicle association for device %s to vehicle %s",
                mac_address,
                vehicle_id,
            )

        except Exception:
            self.logger.exception("Failed to handle vehicle association event")

    async def on_vehicle_update(
        self,
        mac_address: str,
        new_state: DeviceState | None,
        old_state: DeviceState | None,
    ) -> None:
        """
        Handle vehicle association updates for devices.

        Args:
            mac_address: Device MAC address.
            new_state: New device state with updated vehicle association.
            old_state: Previous device state.
        """
        try:
            # Check if vehicle association changed
            old_vehicle = old_state.vehicle_id if old_state else None
            new_vehicle = new_state.vehicle_id if new_state else None

            if old_vehicle == new_vehicle:
                return

            # Update summary for old vehicle if it existed
            if old_vehicle:
                await self._update_vehicle_summary(old_vehicle)

            # Update summary for new vehicle if it exists
            if new_vehicle:
                await self._update_vehicle_summary(new_vehicle)

            self.logger.debug(
                "Handled vehicle update for device %s (old: %s, new: %s)",
                mac_address,
                old_vehicle or "none",
                new_vehicle or "none",
            )

        except Exception:
            self.logger.exception("Failed to handle vehicle update event")

    async def on_system_shutdown(self, event_data: dict[str, Any]) -> None:
        """
        Handle system shutdown events.

        Args:
            event_data: Event data for system shutdown.
        """
        try:
            # Publish system shutdown notification
            shutdown_payload = {
                "status": "shutting_down",
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "reason": event_data.get("reason", "normal_shutdown"),
            }

            await self.mqtt_publisher.mqtt_interface.publish(
                "system/shutdown",
                shutdown_payload,
                retain=True,
            )

            self.logger.info("Published system shutdown notification")

        except Exception:
            self.logger.exception("Failed to handle system shutdown event")

    async def on_system_status_change(self, status_data: dict[str, Any]) -> None:
        """
        Handle system status changes (called manually for periodic updates).

        Args:
            status_data: System status data to publish.
        """
        try:
            await self.mqtt_publisher.publish_system_status(status_data)

            self.logger.debug("Published system status update")

        except Exception:
            self.logger.exception("Failed to handle system status change")

    def _collect_vehicle_device_data(
        self,
        vehicle_id: str,
    ) -> tuple[list[dict[str, Any]], int, float, float]:
        """Collect device data for a vehicle."""
        vehicle_devices = []
        connected_count = 0
        total_voltage = 0.0
        total_capacity = 0.0
        voltage_count = 0
        capacity_count = 0

        # Get device states for this vehicle
        all_states = self.core_engine.state_manager.get_all_devices()
        for state in all_states:
            if state.vehicle_id == vehicle_id:
                device_summary = {
                    "id": state.mac_address,
                    "device_type": state.device_type,
                    "connected": state.connected,
                    "last_reading_time": state.last_reading_time.isoformat()
                    if state.last_reading_time
                    else None,
                }

                # Add reading data if available
                if state.latest_reading:
                    device_summary.update(
                        {
                            "voltage": state.latest_reading.voltage,
                            "current": state.latest_reading.current,
                            "temperature": state.latest_reading.temperature,
                            "state_of_charge": state.latest_reading.state_of_charge,
                        },
                    )

                    # Accumulate for averages
                    if state.latest_reading.voltage is not None:
                        total_voltage += state.latest_reading.voltage
                        voltage_count += 1
                    if state.latest_reading.capacity is not None:
                        total_capacity += state.latest_reading.capacity
                        capacity_count += 1

                if state.connected:
                    connected_count += 1

                vehicle_devices.append(device_summary)

        average_voltage = total_voltage / voltage_count if voltage_count > 0 else 0.0
        return vehicle_devices, connected_count, average_voltage, total_capacity

    def _calculate_vehicle_health(
        self,
        connected_count: int,
        total_devices: int,
    ) -> tuple[str, float]:
        """Calculate vehicle health status."""
        excellent_threshold = 0.8
        good_threshold = 0.6
        fair_threshold = 0.4

        health_score = connected_count / total_devices if total_devices > 0 else 0.0
        if health_score >= excellent_threshold:
            overall_health = "excellent"
        elif health_score >= good_threshold:
            overall_health = "good"
        elif health_score >= fair_threshold:
            overall_health = "fair"
        else:
            overall_health = "poor"

        return overall_health, health_score

    def _remove_time_fields(self, data: dict[str, Any]) -> dict[str, Any]:
        """Remove time-based fields that change on every update."""
        clean_data = data.copy()
        clean_data.pop("last_updated", None)

        # Also clean device-level time fields
        if "devices" in clean_data:
            clean_devices = []
            for device in clean_data["devices"]:
                clean_device = device.copy()
                clean_device.pop("last_reading_time", None)
                clean_devices.append(clean_device)
            clean_data["devices"] = clean_devices

        return clean_data

    def _should_update_vehicle_cache(
        self,
        vehicle_id: str,
        summary_data: dict[str, Any],
    ) -> bool:
        """Check if vehicle summary cache should be updated."""
        cache_data = self._remove_time_fields(summary_data)
        cache_key = vehicle_id
        cached_data = self._remove_time_fields(
            self._vehicle_summary_cache.get(cache_key, {}),
        )

        return cache_key not in self._vehicle_summary_cache or cached_data != cache_data

    async def _update_vehicle_summary(self, vehicle_id: str) -> None:
        """
        Update and publish vehicle summary data.

        Args:
            vehicle_id: Vehicle ID to update summary for.
        """
        try:
            # Get vehicle information
            vehicle_info = self.core_engine.vehicle_registry.get_vehicle(vehicle_id)
            if not vehicle_info:
                self.logger.warning("Vehicle %s not found in registry", vehicle_id)
                return

            # Collect device data
            vehicle_devices, connected_count, average_voltage, total_capacity = (
                self._collect_vehicle_device_data(vehicle_id)
            )

            # Calculate health
            total_devices = len(vehicle_devices)
            overall_health, health_score = self._calculate_vehicle_health(
                connected_count,
                total_devices,
            )

            # Build vehicle summary
            summary_data = {
                "name": vehicle_info.get("name", f"Vehicle_{vehicle_id}"),
                "total_devices": total_devices,
                "connected_devices": connected_count,
                "disconnected_devices": total_devices - connected_count,
                "average_voltage": round(average_voltage, 2),
                "total_capacity": round(total_capacity, 2),
                "overall_health": overall_health,
                "health_score": round(health_score, 2),
                "devices": vehicle_devices,
                "last_updated": datetime.now(tz=timezone.utc).isoformat(),
            }

            # Check if cache should be updated
            if self._should_update_vehicle_cache(vehicle_id, summary_data):
                self._vehicle_summary_cache[vehicle_id] = summary_data.copy()

                # Publish vehicle summary
                await self.mqtt_publisher.publish_vehicle_summary(
                    vehicle_id,
                    summary_data,
                )

                self.logger.debug(
                    "Updated vehicle summary for %s (%d devices, %d connected)",
                    vehicle_id,
                    total_devices,
                    connected_count,
                )

        except Exception:
            self.logger.exception(
                "Failed to update vehicle summary for %s",
                vehicle_id,
            )
