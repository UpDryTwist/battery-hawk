"""BLE connection pool manager for async BLE operations."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

try:
    from bleak import BleakClient
    from bleak.exc import BleakError

    BLEAK_AVAILABLE = True
except ImportError:
    BleakClient = None
    BleakError = Exception
    BLEAK_AVAILABLE = False

from .state import ConnectionState, ConnectionStateManager

# Global semaphore to coordinate BLE scanning operations
# This prevents multiple scanning operations from running simultaneously
# which causes "Operation already in progress" errors in BlueZ
_ble_scan_semaphore: asyncio.Semaphore | None = None


def get_ble_scan_semaphore() -> asyncio.Semaphore:
    """Get or create the global BLE scan coordination semaphore."""
    global _ble_scan_semaphore  # noqa: PLW0603
    if _ble_scan_semaphore is None:
        _ble_scan_semaphore = asyncio.Semaphore(1)  # Only one scan at a time
    return _ble_scan_semaphore


class BLEConnectionError(Exception):
    """Exception raised when BLE connection operations fail."""

    def __init__(self, message: str, device_address: str | None = None) -> None:
        """Initialize BLE connection error."""
        super().__init__(message)
        self.device_address = device_address


class BLEOperationError(Exception):
    """Exception raised when BLE GATT operations fail."""

    def __init__(self, message: str, device_address: str | None = None) -> None:
        """Initialize BLE operation error."""
        super().__init__(message)
        self.device_address = device_address


class MockBleakClient:
    """Mock BleakClient for testing purposes."""

    def __init__(self, address: str, timeout: float = 30.0) -> None:
        """Initialize mock client."""
        self.address = address
        self.timeout = timeout
        self.is_connected = False
        self._notifications: dict[str, Callable] = {}

    async def connect(self) -> None:
        """Mock connect method."""
        self.is_connected = True

    async def disconnect(self) -> None:
        """Mock disconnect method."""
        self.is_connected = False
        self._notifications.clear()

    async def write_gatt_char(
        self,
        char_uuid: str,
        data: bytes,
        *,
        response: bool = True,  # noqa: ARG002
    ) -> None:
        """Mock write method that simulates device responses."""
        if not self.is_connected:
            raise BleakError("Not connected")

        # Simulate device response by triggering notifications
        await self._simulate_device_response(char_uuid, data)

    async def start_notify(self, char_uuid: str, callback: Callable) -> None:
        """Mock start notifications method."""
        if not self.is_connected:
            raise BleakError("Not connected")
        self._notifications[char_uuid] = callback

    async def stop_notify(self, char_uuid: str) -> None:
        """Mock stop notifications method."""
        if not self.is_connected:
            raise BleakError("Not connected")
        if char_uuid in self._notifications:
            del self._notifications[char_uuid]

    async def _simulate_device_response(self, _char_uuid: str, data: bytes) -> None:
        """Simulate device response to commands."""
        # Simulate a small delay for device processing
        await asyncio.sleep(0.1)

        # Generate mock response data based on device type (detected from address)
        if "BM6" in self.address or self.address.endswith("01"):
            response_data = self._generate_bm6_response(data)
        elif "BM2" in self.address or self.address.endswith("02"):
            response_data = self._generate_bm2_response(data)
        else:
            # Default to BM6 response
            response_data = self._generate_bm6_response(data)

        # Trigger notification callback if registered
        logger = logging.getLogger(__name__)
        for notify_uuid, callback in self._notifications.items():
            if callback:
                try:
                    callback(notify_uuid, response_data)
                except (TypeError, ValueError, AttributeError) as exc:
                    # Log callback errors in mock but don't raise
                    logger.debug("Mock notification callback error: %s", exc)

    def _generate_bm6_response(self, _command_data: bytes) -> bytes:
        """Generate mock BM6 response data."""
        # Mock BM6 voltage/temperature response
        # Format: [header][voltage_high][voltage_low][temp_high][temp_low][checksum]
        voltage = 1250  # 12.50V (in centivolt)
        temperature = 250  # 25.0°C (in decidegree)

        response = bytearray(
            [
                0xDD,
                0x5A,
                0x00,
                0x02,
                0x56,
                0x78,
                0x00,
                0x20,  # Header
                (voltage >> 8) & 0xFF,
                voltage & 0xFF,  # Voltage
                (temperature >> 8) & 0xFF,
                temperature & 0xFF,  # Temperature
                0x85,
                0x00,
                0x00,
                0x00,  # SoC and other data
                0x77,  # Checksum (mock)
            ],
        )
        return bytes(response)

    def _generate_bm2_response(self, _command_data: bytes) -> bytes:
        """Generate mock BM2 response data."""
        # Mock BM2 response data
        voltage_bytes = (1000).to_bytes(2, byteorder="little")  # 10.00V
        current_bytes = (100).to_bytes(2, byteorder="little", signed=True)  # 1.00A
        temp_bytes = (20).to_bytes(1, byteorder="little", signed=True)  # 20°C
        soc_bytes = (100).to_bytes(1, byteorder="little")  # 100%
        capacity_bytes = (400).to_bytes(2, byteorder="little")  # 400mAh

        data = (
            b"\xaa"
            + voltage_bytes
            + current_bytes
            + temp_bytes
            + soc_bytes
            + capacity_bytes
        )
        checksum = sum(data) & 0xFF
        return data + bytes([checksum])


class BLEConnectionPool:
    """Async BLE connection pool manager with connection limiting and queuing."""

    def __init__(
        self,
        config_manager: Any,
        cleanup_interval: float = 5.0,
        *,
        test_mode: bool = False,
    ) -> None:
        """
        Initialize BLEConnectionPool with config manager and cleanup interval.

        Args:
            config_manager: Accepts Any for compatibility with dynamic config objects.
            cleanup_interval: Interval in seconds for cleaning up stale connections.
            test_mode: If True, use mock connections instead of real BLE connections.
        """
        self.config = config_manager
        self.max_connections: int = self.config.get_config("system")["bluetooth"].get(
            "max_concurrent_connections",
            3,
        )
        # Optional adapter selection (e.g., 'hci0')
        try:
            self.adapter: str | None = (
                self.config.get_config("system").get("bluetooth", {}).get("adapter")
            )
        except (AttributeError, TypeError, KeyError):
            # Be resilient to unexpected config shapes or missing get_config
            self.adapter = None
        self.active_connections: dict[str, dict] = {}
        self.connection_queue: asyncio.Queue = asyncio.Queue()
        self.connection_history: list[dict] = []
        self.logger = logging.getLogger("battery_hawk.ble_connection_pool")
        self._cleanup_task: asyncio.Task | None = None
        self.connection_timeout: float = 30.0  # seconds
        self._cleanup_interval: float = cleanup_interval
        self._shutdown_event = asyncio.Event()
        self.test_mode: bool = test_mode

        # Connection state management
        self.device_states: dict[str, ConnectionStateManager] = {}
        self.reconnection_enabled: bool = True
        self.max_reconnection_attempts: int = 3
        self.reconnection_delay: float = 2.0

        # Track pending connections to prevent race conditions
        self._pending_connections: set[str] = set()

        # Don't start cleanup task immediately - will be started when needed

    def _get_state_manager(self, device_address: str) -> ConnectionStateManager:
        """Get or create a state manager for a device."""
        if device_address not in self.device_states:
            self.device_states[device_address] = ConnectionStateManager()
        return self.device_states[device_address]

    def get_device_state(self, device_address: str) -> ConnectionState:
        """Get the current connection state for a device."""
        state_manager = self._get_state_manager(device_address)
        return state_manager.state

    def get_device_state_history(
        self,
        device_address: str,
        limit: int = 20,
    ) -> list[tuple[ConnectionState, float]]:
        """Get the state transition history for a device."""
        state_manager = self._get_state_manager(device_address)
        return state_manager.get_state_history(limit)

    def _start_cleanup_task(self) -> None:
        """Start background task for cleaning up stale connections."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_stale_connections())

    async def start_cleanup(self) -> None:
        """Start the cleanup task. Call this when the event loop is running."""
        self._start_cleanup_task()

    async def shutdown(self) -> None:
        """Stop the background cleanup task. Use in tests to avoid pending tasks."""
        self._shutdown_event.set()
        if self._cleanup_task:
            await self._cleanup_task

    async def connect(self, device_address: str) -> dict:
        """Request a connection to a BLE device. Queues if pool is full."""
        # Start cleanup task if not already started
        if self._cleanup_task is None:
            await self.start_cleanup()

        if device_address in self.active_connections:
            self.logger.info("Already connected to %s", device_address)
            return self.active_connections[device_address]

        # Check if connection is already in progress
        if device_address in self._pending_connections:
            self.logger.info(
                "Connection already in progress for %s, queuing",
                device_address,
            )
            future = asyncio.Future()
            await self.connection_queue.put((device_address, future))
            return await future

        if len(self.active_connections) >= self.max_connections:
            self.logger.info("Max connections reached, queuing %s", device_address)
            future = asyncio.Future()
            await self.connection_queue.put((device_address, future))
            return await future

        return await self._create_connection(device_address)

    async def _create_connection(self, device_address: str) -> dict:  # noqa: PLR0915
        """Create actual BLE connection using BleakClient."""
        if not BLEAK_AVAILABLE and not self.test_mode:
            raise BLEConnectionError(
                "Bleak library is not available. Install with: pip install bleak",
                device_address=device_address,
            )

        # Mark connection as pending to prevent race conditions
        self._pending_connections.add(device_address)

        # Update state to connecting
        state_manager = self._get_state_manager(device_address)
        await state_manager.set_state(ConnectionState.CONNECTING)

        try:
            self.logger.info("Creating BLE connection to %s", device_address)

            # Create BleakClient with timeout (or mock client in test mode)
            if self.test_mode:
                client = MockBleakClient(
                    device_address,
                    timeout=self.connection_timeout,
                )
            else:
                if BleakClient is None:
                    raise BLEConnectionError(
                        "Bleak library is not available",
                        device_address=device_address,
                    )
                # Pass adapter if configured and supported (Linux/BlueZ)
                if getattr(self, "adapter", None):
                    try:
                        client = BleakClient(
                            device_address,
                            timeout=self.connection_timeout,
                            adapter=self.adapter,  # type: ignore[call-arg]
                        )
                    except TypeError:
                        # Fallback for Bleak versions/backends without adapter kwarg
                        client = BleakClient(
                            device_address,
                            timeout=self.connection_timeout,
                        )
                else:
                    client = BleakClient(
                        device_address,
                        timeout=self.connection_timeout,
                    )

            # Attempt to connect using semaphore to coordinate BLE scanning
            # This prevents "Operation already in progress" errors when multiple
            # BLE operations try to scan simultaneously
            scan_semaphore = get_ble_scan_semaphore()
            async with scan_semaphore:
                self.logger.debug(
                    "Acquired BLE scan semaphore for connection to %s",
                    device_address,
                )
                await client.connect()

            # Verify connection was successful
            if not client.is_connected:
                raise BLEConnectionError(
                    f"Failed to establish BLE connection to {device_address}",
                    device_address=device_address,
                )

            # Log successful connection
            self.logger.info("Successfully connected to BLE device %s", device_address)

            # Create connection dictionary with BleakClient instance
            conn = {
                "device_address": device_address,
                "client": client,
                "connected_at": time.time(),
                "notifications": {},  # Track active notifications
                "is_connected": True,
            }

            # Store in active connections
            self.active_connections[device_address] = conn

            # Remove from pending connections
            self._pending_connections.discard(device_address)

            # Update state to connected
            await state_manager.set_state(ConnectionState.CONNECTED)

            # Add to connection history
            self.connection_history.append(
                {
                    "event": "connect",
                    "device_address": device_address,
                    "timestamp": time.time(),
                    "success": True,
                },
            )

        except TimeoutError as e:
            # Handle timeout errors specifically
            error_msg = f"BLE connection timeout for {device_address}: {e}"
            self.logger.exception(error_msg)

            # Remove from pending connections
            self._pending_connections.discard(device_address)

            # Update state to error
            await state_manager.set_state(ConnectionState.ERROR)

            # Add failed connection to history
            self.connection_history.append(
                {
                    "event": "connect_failed",
                    "device_address": device_address,
                    "timestamp": time.time(),
                    "error": str(e),
                    "success": False,
                },
            )

            raise BLEConnectionError(error_msg, device_address=device_address) from e

        except BleakError as e:
            # Handle Bleak-specific errors
            error_msg = f"BLE connection failed for {device_address}: {e}"
            self.logger.exception(error_msg)

            # Remove from pending connections
            self._pending_connections.discard(device_address)

            # Update state to error
            await state_manager.set_state(ConnectionState.ERROR)

            # Add failed connection to history
            self.connection_history.append(
                {
                    "event": "connect_failed",
                    "device_address": device_address,
                    "timestamp": time.time(),
                    "error": str(e),
                    "success": False,
                },
            )

            raise BLEConnectionError(error_msg, device_address=device_address) from e

        except Exception as e:
            # Handle any other unexpected errors
            error_msg = f"Unexpected error connecting to {device_address}: {e}"
            self.logger.exception(error_msg)

            # Remove from pending connections
            self._pending_connections.discard(device_address)

            # Update state to error
            await state_manager.set_state(ConnectionState.ERROR)

            # Add failed connection to history
            self.connection_history.append(
                {
                    "event": "connect_failed",
                    "device_address": device_address,
                    "timestamp": time.time(),
                    "error": str(e),
                    "success": False,
                },
            )

            raise BLEConnectionError(error_msg, device_address=device_address) from e
        else:
            return conn

    async def disconnect(self, device_address: str) -> None:
        """Disconnect from a BLE device and clean up."""
        # Update state to disconnecting
        state_manager = self._get_state_manager(device_address)
        await state_manager.set_state(ConnectionState.DISCONNECTING)

        # Always remove from pending connections, even if not in active connections
        # This handles cases where connection was interrupted during setup
        self._pending_connections.discard(device_address)

        if device_address not in self.active_connections:
            self.logger.warning("No active connection found for %s", device_address)
            # Still update state to disconnected
            await state_manager.set_state(ConnectionState.DISCONNECTED)
            return

        conn = self.active_connections[device_address]

        try:
            # Stop all active notifications first
            if conn.get("notifications"):
                self.logger.debug("Stopping notifications for %s", device_address)
                client = conn.get("client")
                if client and hasattr(client, "is_connected") and client.is_connected:
                    for char_uuid in list(conn["notifications"].keys()):
                        try:
                            await client.stop_notify(char_uuid)
                            self.logger.debug(
                                "Stopped notification for %s on %s",
                                char_uuid,
                                device_address,
                            )
                        except (BleakError, OSError) as e:  # noqa: PERF203
                            self.logger.warning(
                                "Failed to stop notification for %s: %s",
                                char_uuid,
                                e,
                            )
                conn["notifications"].clear()

            # Disconnect the BleakClient
            client = conn.get("client")
            if client and hasattr(client, "disconnect"):
                if hasattr(client, "is_connected") and client.is_connected:
                    await client.disconnect()
                    self.logger.info("Disconnected BLE client for %s", device_address)
                else:
                    self.logger.debug(
                        "BLE client for %s was already disconnected",
                        device_address,
                    )

            # Update connection state
            conn["is_connected"] = False

        except BleakError:
            self.logger.exception(
                "BLE error during disconnect for %s",
                device_address,
            )
        except Exception:
            self.logger.exception(
                "Unexpected error during disconnect for %s",
                device_address,
            )
        finally:
            # Always remove from active connections
            del self.active_connections[device_address]

            # Update state to disconnected
            await state_manager.set_state(ConnectionState.DISCONNECTED)

            # Add to connection history
            self.connection_history.append(
                {
                    "event": "disconnect",
                    "device_address": device_address,
                    "timestamp": time.time(),
                    "success": True,
                },
            )

            self.logger.info("Cleaned up connection for %s", device_address)

            # Process next in queue if any
            if not self.connection_queue.empty():
                future = None
                try:
                    queued_address, future = await self.connection_queue.get()
                    conn = await self._create_connection(queued_address)
                    if not future.done():
                        future.set_result(conn)
                except BLEConnectionError as e:
                    self.logger.exception("Failed to process queued connection")
                    if future is not None and not future.done():
                        future.set_exception(e)

    async def reconnect(
        self,
        device_address: str,
        max_attempts: int | None = None,
    ) -> bool:
        """
        Attempt to reconnect to a device with exponential backoff.

        Args:
            device_address: MAC address of the device to reconnect
            max_attempts: Maximum number of reconnection attempts (uses default if None)

        Returns:
            True if reconnection was successful, False otherwise
        """
        if not self.reconnection_enabled:
            self.logger.info("Reconnection is disabled for %s", device_address)
            return False

        max_attempts = max_attempts or self.max_reconnection_attempts
        state_manager = self._get_state_manager(device_address)

        self.logger.info(
            "Starting reconnection attempts for %s (max attempts: %d)",
            device_address,
            max_attempts,
        )

        for attempt in range(1, max_attempts + 1):
            try:
                self.logger.info(
                    "Reconnection attempt %d/%d for %s",
                    attempt,
                    max_attempts,
                    device_address,
                )

                # Attempt to connect
                await self._create_connection(device_address)

            except BLEConnectionError as e:  # noqa: PERF203
                self.logger.warning(
                    "Reconnection attempt %d/%d failed for %s: %s",
                    attempt,
                    max_attempts,
                    device_address,
                    e,
                )

                # Don't wait after the last attempt
                if attempt < max_attempts:
                    # Exponential backoff with jitter
                    delay = self.reconnection_delay * (2 ** (attempt - 1))
                    # Add some jitter to avoid thundering herd
                    jitter = delay * 0.1 * (0.5 - asyncio.get_event_loop().time() % 1)
                    total_delay = delay + jitter

                    self.logger.info(
                        "Waiting %.2f seconds before next reconnection attempt for %s",
                        total_delay,
                        device_address,
                    )
                    await asyncio.sleep(total_delay)
            else:
                self.logger.info(
                    "Reconnection successful for %s after %d attempts",
                    device_address,
                    attempt,
                )
                return True

        self.logger.error(
            "All reconnection attempts failed for %s",
            device_address,
        )
        await state_manager.set_state(ConnectionState.ERROR)
        return False

    async def write_characteristic(
        self,
        device_address: str,
        char_uuid: str,
        data: bytes,
    ) -> None:
        """
        Write data to a GATT characteristic.

        Args:
            device_address: MAC address of the device
            char_uuid: UUID of the characteristic to write to
            data: Data to write

        Raises:
            BLEConnectionError: If no active connection exists
            BLEOperationError: If the write operation fails
            ValueError: If data is empty or invalid
        """
        # Validate input parameters
        if not data:
            raise ValueError(f"Cannot write empty data to characteristic {char_uuid}")
        if not char_uuid:
            raise ValueError("Characteristic UUID cannot be empty")
        if not device_address:
            raise ValueError("Device address cannot be empty")

        if device_address not in self.active_connections:
            raise BLEConnectionError(
                f"No active connection for device {device_address}",
                device_address=device_address,
            )

        conn = self.active_connections[device_address]
        client = conn.get("client")

        if not client or not hasattr(client, "is_connected") or not client.is_connected:
            raise BLEConnectionError(
                f"BLE client for {device_address} is not connected",
                device_address=device_address,
            )

        try:
            self.logger.debug(
                "Writing %d bytes to characteristic %s on %s",
                len(data),
                char_uuid,
                device_address,
            )
            await client.write_gatt_char(char_uuid, data, response=True)
            self.logger.debug(
                "Successfully wrote %d bytes to characteristic %s on %s",
                len(data),
                char_uuid,
                device_address,
            )

        except BleakError as e:
            error_msg = f"Failed to write to characteristic {char_uuid} on {device_address}: {e}"
            self.logger.exception(error_msg)
            raise BLEOperationError(error_msg, device_address=device_address) from e
        except Exception as e:
            error_msg = f"Unexpected error writing to characteristic {char_uuid} on {device_address}: {e}"
            self.logger.exception(error_msg)
            raise BLEOperationError(error_msg, device_address=device_address) from e

    async def start_notifications(
        self,
        device_address: str,
        char_uuid: str,
        callback: Callable[[str, bytearray], None],
    ) -> None:
        """
        Start notifications for a GATT characteristic.

        Args:
            device_address: MAC address of the device
            char_uuid: UUID of the characteristic to subscribe to
            callback: Function to call when notifications are received

        Raises:
            BLEConnectionError: If no active connection exists
            BLEOperationError: If the notification setup fails
            ValueError: If parameters are invalid
        """
        # Validate input parameters
        if not char_uuid:
            raise ValueError("Characteristic UUID cannot be empty")
        if not device_address:
            raise ValueError("Device address cannot be empty")
        if callback is None:
            raise ValueError("Callback function cannot be None")

        if device_address not in self.active_connections:
            raise BLEConnectionError(
                f"No active connection for device {device_address}",
                device_address=device_address,
            )

        conn = self.active_connections[device_address]
        client = conn.get("client")

        if not client or not hasattr(client, "is_connected") or not client.is_connected:
            raise BLEConnectionError(
                f"BLE client for {device_address} is not connected",
                device_address=device_address,
            )

        try:
            self.logger.debug(
                "Starting notifications for characteristic %s on %s",
                char_uuid,
                device_address,
            )
            await client.start_notify(char_uuid, callback)

            # Track the notification
            conn["notifications"][char_uuid] = callback

            self.logger.debug(
                "Successfully started notifications for %s on %s",
                char_uuid,
                device_address,
            )

        except BleakError as e:
            error_msg = f"Failed to start notifications for {char_uuid} on {device_address}: {e}"
            self.logger.exception(error_msg)
            raise BLEOperationError(error_msg, device_address=device_address) from e
        except Exception as e:
            error_msg = f"Unexpected error starting notifications for {char_uuid} on {device_address}: {e}"
            self.logger.exception(error_msg)
            raise BLEOperationError(error_msg, device_address=device_address) from e

    async def stop_notifications(self, device_address: str, char_uuid: str) -> None:
        """
        Stop notifications for a GATT characteristic.

        Args:
            device_address: MAC address of the device
            char_uuid: UUID of the characteristic to unsubscribe from

        Raises:
            BLEConnectionError: If no active connection exists
            BLEOperationError: If stopping notifications fails
        """
        if device_address not in self.active_connections:
            raise BLEConnectionError(
                f"No active connection for device {device_address}",
                device_address=device_address,
            )

        conn = self.active_connections[device_address]
        client = conn.get("client")

        if not client or not hasattr(client, "is_connected") or not client.is_connected:
            raise BLEConnectionError(
                f"BLE client for {device_address} is not connected",
                device_address=device_address,
            )

        try:
            self.logger.debug(
                "Stopping notifications for characteristic %s on %s",
                char_uuid,
                device_address,
            )
            await client.stop_notify(char_uuid)

            # Remove from tracked notifications
            if char_uuid in conn["notifications"]:
                del conn["notifications"][char_uuid]

            self.logger.debug(
                "Successfully stopped notifications for %s on %s",
                char_uuid,
                device_address,
            )

        except BleakError as e:
            error_msg = (
                f"Failed to stop notifications for {char_uuid} on {device_address}: {e}"
            )
            self.logger.exception(error_msg)
            raise BLEOperationError(error_msg, device_address=device_address) from e
        except Exception as e:
            error_msg = f"Unexpected error stopping notifications for {char_uuid} on {device_address}: {e}"
            self.logger.exception(error_msg)
            raise BLEOperationError(error_msg, device_address=device_address) from e

    async def _cleanup_stale_connections(self) -> None:
        """Periodically clean up connections that have timed out or are no longer connected."""
        try:
            while not self._shutdown_event.is_set():
                now = time.time()
                stale = []
                reconnect_candidates = []

                for addr, conn in self.active_connections.items():
                    # Check if connection has timed out
                    if now - conn["connected_at"] > self.connection_timeout:
                        stale.append(addr)
                        continue

                    # Check if BLE client is still connected
                    client = conn.get("client")
                    if (
                        client
                        and hasattr(client, "is_connected")
                        and not client.is_connected
                    ):
                        self.logger.info(
                            "BLE client for %s is no longer connected",
                            addr,
                        )
                        stale.append(addr)
                        # Mark for potential reconnection if enabled
                        if self.reconnection_enabled:
                            reconnect_candidates.append(addr)
                        continue

                    # Update connection state if needed
                    if (
                        conn.get("is_connected", True)
                        and client
                        and hasattr(client, "is_connected")
                    ):
                        conn["is_connected"] = client.is_connected

                # Clean up stale connections
                for addr in stale:
                    self.logger.info("Cleaning up stale connection %s", addr)
                    await self.disconnect(addr)

                # Attempt reconnection for candidates (but don't block cleanup)
                for addr in reconnect_candidates:
                    if (
                        addr not in self.active_connections
                    ):  # Only if not already reconnected
                        # Start reconnection in background
                        asyncio.create_task(self._background_reconnect(addr))  # noqa: RUF006
                        # Don't await the task to avoid blocking cleanup

                # Wait for next cleanup cycle or shutdown
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self._cleanup_interval,
                    )
                except TimeoutError:
                    continue
        except asyncio.CancelledError:
            pass

    async def _background_reconnect(self, device_address: str) -> None:
        """Perform background reconnection for a device."""
        try:
            self.logger.info("Starting background reconnection for %s", device_address)
            success = await self.reconnect(device_address)
            if success:
                self.logger.info(
                    "Background reconnection successful for %s",
                    device_address,
                )
            else:
                self.logger.warning(
                    "Background reconnection failed for %s",
                    device_address,
                )
        except Exception:
            self.logger.exception(
                "Error during background reconnection for %s",
                device_address,
            )

    def get_active_connections(self) -> dict[str, dict]:
        """
        Get all active connections.

        Returns:
            Dict of device_address to connection object.
        """
        return self.active_connections

    def get_queued_device_addresses(self) -> list[str]:
        """Get a list of device addresses currently queued for connection."""
        # Accessing private _queue is required to peek at asyncio.Queue contents; no public API exists.
        return [item[0] for item in list(self.connection_queue._queue)]  # type: ignore[attr-defined]  # noqa: SLF001

    def get_connection_stats(self) -> dict:
        """
        Get statistics about connections (counts, history).

        Returns:
            Dict with stats.
        """
        # Count connected vs disconnected
        connected_count = 0
        disconnected_count = 0

        for conn in self.active_connections.values():
            if conn.get("is_connected", True):
                connected_count += 1
            else:
                disconnected_count += 1

        # Count devices by state
        state_counts = {}
        for state_manager in self.device_states.values():
            state = state_manager.state
            state_counts[state.name] = state_counts.get(state.name, 0) + 1

        return {
            "active": len(self.active_connections),
            "connected": connected_count,
            "disconnected": disconnected_count,
            "pending": len(self._pending_connections),
            "queued": self.connection_queue.qsize(),
            "history": self.connection_history[-20:],  # last 20 events
            "bleak_available": BLEAK_AVAILABLE,
            "state_counts": state_counts,
            "total_devices": len(self.device_states),
            "reconnection_enabled": self.reconnection_enabled,
        }

    def is_connected(self, device_address: str) -> bool:
        """
        Check if a device is currently connected.

        Args:
            device_address: MAC address of the device

        Returns:
            True if device is connected, False otherwise
        """
        if device_address not in self.active_connections:
            return False

        conn = self.active_connections[device_address]
        client = conn.get("client")

        # Check both our tracking and the actual BLE client state
        if client and hasattr(client, "is_connected"):
            is_connected = client.is_connected
            # Update our tracking
            conn["is_connected"] = is_connected
            return is_connected

        return conn.get("is_connected", False)

    async def get_connection_health(self, device_address: str) -> dict:
        """
        Get detailed health information for a connection.

        Args:
            device_address: MAC address of the device

        Returns:
            Dict with connection health information
        """
        # Get state information
        state_manager = self._get_state_manager(device_address)
        current_state = state_manager.state
        state_history = state_manager.get_state_history(5)  # Last 5 state changes

        health = {
            "device_address": device_address,
            "current_state": current_state.name,
            "state_history": [
                {"state": state.name, "timestamp": timestamp}
                for state, timestamp in state_history
            ],
        }

        if device_address not in self.active_connections:
            health.update(
                {
                    "connected": False,
                    "error": "No active connection found",
                },
            )
            return health

        conn = self.active_connections[device_address]
        client = conn.get("client")

        health.update(
            {
                "connected_at": conn.get("connected_at"),
                "connection_age": time.time() - conn.get("connected_at", 0),
                "active_notifications": len(conn.get("notifications", {})),
                "notification_characteristics": list(
                    conn.get("notifications", {}).keys(),
                ),
            },
        )

        if client and hasattr(client, "is_connected"):
            health["connected"] = client.is_connected
            health["client_type"] = type(client).__name__
        else:
            health["connected"] = False
            health["error"] = "No BLE client available"

        return health

    def enable_reconnection(self, *, enabled: bool = True) -> None:
        """Enable or disable automatic reconnection."""
        self.reconnection_enabled = enabled
        self.logger.info(
            "Automatic reconnection %s",
            "enabled" if enabled else "disabled",
        )

    def set_reconnection_config(
        self,
        max_attempts: int | None = None,
        delay: float | None = None,
    ) -> None:
        """
        Configure reconnection behavior.

        Args:
            max_attempts: Maximum number of reconnection attempts
            delay: Base delay between reconnection attempts (exponential backoff applied)
        """
        if max_attempts is not None:
            self.max_reconnection_attempts = max_attempts
            self.logger.info("Set max reconnection attempts to %d", max_attempts)

        if delay is not None:
            self.reconnection_delay = delay
            self.logger.info("Set reconnection delay to %.2f seconds", delay)

    def get_reconnection_config(self) -> dict:
        """Get current reconnection configuration."""
        return {
            "enabled": self.reconnection_enabled,
            "max_attempts": self.max_reconnection_attempts,
            "delay": self.reconnection_delay,
        }
