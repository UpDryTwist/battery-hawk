"""BM6 battery monitor device implementation."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

try:
    from bleak.exc import BleakError
except ImportError:
    BleakError = Exception

if TYPE_CHECKING:
    import logging

    from ..base.connection import BLEConnectionPool

from ..base.protocol import (
    BaseMonitorDevice,
    BatteryInfo,
    DeviceStatus,
)
from ..base.state import ConnectionState
from .bm6_error_handler import BM6ErrorHandler
from .constants import (
    BM6_NOTIFY_CHARACTERISTIC_UUID,
    BM6_SERVICE_UUID,
    BM6_WRITE_CHARACTERISTIC_UUID,
    DEFAULT_DATA_WAIT_TIMEOUT,
)
from .exceptions import (
    BM6ConnectionError,
    BM6DataParsingError,
    BM6TimeoutError,
)
from .parser import BM6Parser
from .protocol import (
    build_voltage_temp_request,
)


class BM6Device(BaseMonitorDevice):
    """BM6 Battery Monitor device implementation."""

    def __init__(
        self,
        device_address: str,
        config: object = None,
        connection_pool: BLEConnectionPool | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize BM6 device."""
        super().__init__(device_address, config, connection_pool, logger)
        self.device_type = "BM6"
        self.mac_address = device_address
        self.service_uuid = BM6_SERVICE_UUID
        self.notify_characteristic_uuid = BM6_NOTIFY_CHARACTERISTIC_UUID
        self.write_characteristic_uuid = BM6_WRITE_CHARACTERISTIC_UUID
        self.parser = BM6Parser(logger)
        self._latest_data: dict[str, object] = {}
        self._data_received_event = asyncio.Event()
        self._data_wait_timeout = (
            getattr(config, "data_wait_timeout", DEFAULT_DATA_WAIT_TIMEOUT)
            if config
            else DEFAULT_DATA_WAIT_TIMEOUT
        )
        # Initialize error handler for BM6-specific error handling
        self.error_handler = BM6ErrorHandler(
            device_address,
            self.logger,
            default_timeout=30.0,
        )
        # Notification handler will be set up when BLE operations are implemented

    @property
    def protocol_version(self) -> str:
        """Return the protocol version implemented by this device."""
        return "1.0"

    @property
    def capabilities(self) -> set[str]:
        """Return a set of supported capability strings for this device."""
        return {
            "read_voltage",
            "read_current",
            "read_temperature",
            "read_state_of_charge",
            "read_state",
            "read_rapid_acceleration",
            "read_rapid_deceleration",
            "read_firmware_version",
        }

    async def connect(self) -> None:
        """Connect to the BM6 device and set up notifications."""
        try:
            await super().connect()

            if self.connection_pool is None:
                raise BM6ConnectionError(
                    "No connection pool available for BM6 device connection.",
                    device_address=self.device_address,
                )

            # Get the BLE connection from the connection pool
            connection = await self.connection_pool.connect(self.device_address)
            if connection is None:
                raise BM6ConnectionError(
                    f"Failed to get BLE connection for device {self.device_address}",
                    device_address=self.device_address,
                    connection_attempt=1,
                )

            # Set up notifications for BM6 data using the real BLE operations
            self.logger.info(
                "Setting up BM6 notifications for device %s on characteristic %s",
                self.device_address,
                self.notify_characteristic_uuid,
            )

            await self.connection_pool.start_notifications(
                self.device_address,
                self.notify_characteristic_uuid,
                self._notification_handler,
            )

            self.logger.info(
                "BM6 device connected and notifications enabled for device %s",
                self.device_address,
            )

            # Request initial data
            await self.request_voltage_temp()
            self.logger.debug(
                "Initial data request sent to BM6 device %s",
                self.device_address,
            )

        except BM6ConnectionError:
            # Re-raise BM6-specific connection errors
            raise
        except Exception as exc:
            # Convert generic exceptions to BM6-specific errors
            self.logger.exception(
                "Failed to set up BM6 device %s",
                self.device_address,
            )
            raise BM6ConnectionError(
                f"Unexpected error during BM6 device setup: {exc}",
                device_address=self.device_address,
            ) from exc

    async def disconnect(self) -> None:
        """Disconnect from the BM6 device."""
        try:
            if self.connection_pool is None:
                raise BM6ConnectionError(
                    "No connection pool available for BM6 device disconnection.",
                    device_address=self.device_address,
                )

            # Stop notifications before disconnecting
            if self.connection_pool.is_connected(self.device_address):
                self.logger.info(
                    "Stopping BM6 notifications for device %s on characteristic %s",
                    self.device_address,
                    self.notify_characteristic_uuid,
                )

                try:
                    await self.connection_pool.stop_notifications(
                        self.device_address,
                        self.notify_characteristic_uuid,
                    )
                    self.logger.info(
                        "BM6 notifications stopped for device %s",
                        self.device_address,
                    )
                except (BleakError, OSError) as e:
                    self.logger.warning(
                        "Failed to stop notifications for BM6 device %s: %s",
                        self.device_address,
                        e,
                    )

            await super().disconnect()

        except BM6ConnectionError:
            # Re-raise BM6-specific connection errors
            raise
        except Exception as exc:
            # Convert generic exceptions to BM6-specific errors
            self.logger.exception(
                "Failed to disconnect BM6 device %s",
                self.device_address,
            )
            raise BM6ConnectionError(
                f"Unexpected error during BM6 device disconnection: {exc}",
                device_address=self.device_address,
            ) from exc

    async def read_data(self) -> BatteryInfo:
        """
        Read battery data from the BM6 device.

        Returns:
            BatteryInfo: Parsed battery information.

        Raises:
            BM6ConnectionError: If connection fails.
            BM6DataParsingError: If data parsing fails.
            BM6TimeoutError: If operation times out.
        """
        try:
            if self.connection_pool is None:
                raise BM6ConnectionError(
                    "No connection pool available for BM6 data reading.",
                    device_address=self.device_address,
                )

            # Get the BLE connection from the connection pool
            connection = await self.connection_pool.connect(self.device_address)
            if connection is None:
                raise BM6ConnectionError(
                    f"No BLE connection available for device {self.device_address}",
                    device_address=self.device_address,
                )

            # Ensure notifications are active on the BM6 notify characteristic
            try:
                health = await self.connection_pool.get_connection_health(
                    self.device_address,
                )
                active_notifs = set(health.get("notification_characteristics", []))
            except (KeyError, AttributeError, TypeError):
                # Health info may be missing or partial depending on adapter/platform
                active_notifs = set()

            if self.notify_characteristic_uuid not in active_notifs:
                self.logger.info(
                    "Enabling notifications for BM6 device %s on characteristic %s",
                    self.device_address,
                    self.notify_characteristic_uuid,
                )
                # Note: Narrow exception handling; allow BLE errors to surface for retry logic.
                await self.connection_pool.start_notifications(
                    self.device_address,
                    self.notify_characteristic_uuid,
                    self._notification_handler,
                )

            # Clear the data received event
            self._data_received_event.clear()

            # Request fresh data from the device
            await self.request_voltage_temp()

            # Wait for actual data response (not just command acknowledgment)
            self.logger.info(
                "Waiting for data response from BM6 device %s (timeout: %.1fs)",
                self.device_address,
                self._data_wait_timeout,
            )

            try:
                await asyncio.wait_for(
                    self._data_received_event.wait(),
                    timeout=self._data_wait_timeout,
                )
                self.logger.info(
                    "Received data response from BM6 device %s",
                    self.device_address,
                )
            except TimeoutError:
                self.logger.warning(
                    "Timeout waiting for data from BM6 device %s after %.1fs",
                    self.device_address,
                    self._data_wait_timeout,
                )
                # Continue with whatever data we have

            # Create battery info from the latest parsed data
            battery_info = self._create_battery_info()
            self.logger.debug(
                "BM6 read_data result for device %s: voltage=%.2fV, current=%.2fA, temp=%.1f°C, SoC=%.1f%%",
                self.device_address,
                battery_info.voltage or 0.0,
                battery_info.current or 0.0,
                battery_info.temperature or 0.0,
                battery_info.state_of_charge or 0.0,
            )
        except (BM6ConnectionError, BM6DataParsingError, BM6TimeoutError):
            # Re-raise BM6-specific errors
            raise
        except Exception as exc:
            # Convert generic exceptions to BM6-specific errors
            self.logger.exception(
                "Failed to read data from BM6 device %s",
                self.device_address,
            )
            raise BM6DataParsingError(
                f"Unexpected error during BM6 data reading: {exc}",
                device_address=self.device_address,
            ) from exc
        else:
            return battery_info

    async def send_command(
        self,
        command: str,
        params: dict[str, object] | None = None,  # noqa: ARG002
    ) -> DeviceStatus:
        """
        Send a command to the BM6 device and return its status.

        Args:
            command: Command string to send.
            params: Optional parameters for the command.

        Returns:
            DeviceStatus: Resulting device status after command execution.

        Raises:
            Exception if command fails or is unsupported.
        """
        if self.connection_pool is None:
            raise RuntimeError("No connection pool available for BM6 command sending.")

        # Get the BLE connection from the connection pool
        connection = await self.connection_pool.connect(self.device_address)
        if connection is None:
            raise RuntimeError(
                f"No BLE connection available for device {self.device_address}",
            )

        try:
            self.logger.info(
                "Sending command %s to BM6 device %s",
                command,
                self.device_address,
            )

            if command == "request_voltage_temp":
                await self.request_voltage_temp()
                return DeviceStatus(connected=True, last_command=command)
            if command == "status":
                # Return current device status without sending any BLE commands
                return DeviceStatus(
                    connected=connection is not None,
                    last_command=command,
                    protocol_version=self.protocol_version,
                    extra={"device_type": "BM6", "device_address": self.device_address},
                )
            raise ValueError(f"Unsupported BM6 command: {command}")

        except Exception:
            self.logger.exception(
                "Failed to send command %s to BM6 device %s",
                command,
                self.device_address,
            )
            raise

    def get_connection_state(self) -> ConnectionState:
        """Get the current connection state of the device."""
        if self.connection_pool is None:
            return ConnectionState.DISCONNECTED
        # Only return tracked state if the device has been tracked
        if self.device_address not in self.connection_pool.device_states:
            return ConnectionState.DISCONNECTED
        return self.connection_pool.get_device_state(self.device_address)

    def get_connection_state_history(
        self,
        limit: int = 10,
    ) -> list[tuple[ConnectionState, float]]:
        """Get the connection state history for this device."""
        if self.connection_pool is None:
            return []
        # Only return history if the device has been tracked
        if self.device_address not in self.connection_pool.device_states:
            return []
        return self.connection_pool.get_device_state_history(self.device_address, limit)

    async def get_detailed_health(self) -> dict:
        """Get detailed health information including connection state."""
        if self.connection_pool is None:
            return {
                "device_address": self.device_address,
                "current_state": ConnectionState.DISCONNECTED.name,
                "connection_state": ConnectionState.DISCONNECTED.name,
                "error": "No connection pool available",
            }

        health = await self.connection_pool.get_connection_health(self.device_address)
        health["device_type"] = "BM6"
        health["service_uuid"] = self.service_uuid
        health["write_characteristic"] = self.write_characteristic_uuid
        health["notify_characteristic"] = self.notify_characteristic_uuid

        return health

    async def force_reconnect(self, max_attempts: int | None = None) -> bool:
        """
        Force a reconnection to the device.

        Args:
            max_attempts: Maximum number of reconnection attempts

        Returns:
            True if reconnection was successful, False otherwise
        """
        if self.connection_pool is None:
            self.logger.error("Cannot reconnect: no connection pool available")
            return False

        try:
            # Disconnect first if connected
            if self.connection_pool.is_connected(self.device_address):
                await self.disconnect()

            # Attempt reconnection
            success = await self.connection_pool.reconnect(
                self.device_address,
                max_attempts,
            )

            if success:
                # Re-setup notifications
                await self.connection_pool.start_notifications(
                    self.device_address,
                    self.notify_characteristic_uuid,
                    self._notification_handler,
                )
                self.logger.info(
                    "Reconnection and notification setup successful for %s",
                    self.device_address,
                )

        except Exception:
            self.logger.exception(
                "Error during forced reconnection for %s",
                self.device_address,
            )
            return False
        else:
            return success

    async def request_voltage_temp(self) -> None:
        """Request voltage and temperature data from the BM6 device."""
        if self.connection_pool is None:
            raise RuntimeError(
                "No connection pool available for BM6 voltage/temp request.",
            )

        # Verify we have an active connection
        if not self.connection_pool.is_connected(self.device_address):
            raise BM6ConnectionError(
                f"No active BLE connection for device {self.device_address}",
                device_address=self.device_address,
            )

        try:
            # Build the encrypted command
            command = build_voltage_temp_request()
            self.logger.debug(
                "Sending voltage/temp request to BM6 device %s: %s",
                self.device_address,
                command.hex(),
            )

            # Send the encrypted command to the BM6 device
            await self.connection_pool.write_characteristic(
                self.device_address,
                self.write_characteristic_uuid,
                command,
            )

            self.logger.debug(
                "Voltage/temp request sent successfully to BM6 device %s",
                self.device_address,
            )

        except Exception:
            self.logger.exception(
                "Failed to request voltage/temp from BM6 device %s",
                self.device_address,
            )
            raise

    def _notification_handler(self, sender: str, data: bytearray) -> None:  # noqa: ARG002
        """
        Handle notifications from the BM6 device.

        Args:
            sender: Characteristic UUID that sent the notification
            data: Raw notification data
        """
        # Validate input data
        if not data:
            self.logger.warning(
                "Received empty notification data from device %s",
                self.device_address,
            )
            return

        try:
            # Convert bytearray to bytes for parser compatibility
            data_bytes = bytes(data)

            # Log raw data for debugging at DEBUG level
            self.logger.debug(
                "BM6 raw notification from device %s (%d bytes): %s",
                self.device_address,
                len(data_bytes),
                data_bytes.hex(),
            )

            # Try to parse as real BM6 data first (with AES decryption)
            parsed_data = self.parser.parse_real_bm6_data(data_bytes)

            if parsed_data:
                self._latest_data.update(parsed_data)
                # Log key data at INFO level for visibility, full data at DEBUG
                if (
                    "voltage" in parsed_data
                    or "temperature" in parsed_data
                    or "state_of_charge" in parsed_data
                ):
                    self.logger.info(
                        "BM6 data received from device %s: voltage=%.2fV, temp=%.1f°C, SoC=%.1f%%",
                        self.device_address,
                        parsed_data.get("voltage", 0.0),
                        parsed_data.get("temperature", 0.0),
                        parsed_data.get("state_of_charge", 0.0),
                    )
                    # Signal that we received actual data (not just command acknowledgment)
                    self._data_received_event.set()
                self.logger.debug(
                    "BM6 full data updated for device %s: %s",
                    self.device_address,
                    parsed_data,
                )
            else:
                self.logger.warning(
                    "Failed to parse BM6 notification data from device %s (received %d bytes): %s",
                    self.device_address,
                    len(data),
                    data_bytes.hex(),
                )

        except Exception:
            self.logger.exception(
                "Error handling BM6 notification from device %s",
                self.device_address,
            )

    def _create_battery_info(self) -> BatteryInfo:
        """
        Create a BatteryInfo object from the latest parsed data.

        Returns:
            BatteryInfo: Battery information object
        """
        # Extract temperature (use first temperature sensor if available)
        temperature = 25.0  # Default temperature
        if self._latest_data.get("temperatures"):
            temps = self._latest_data["temperatures"]
            if isinstance(temps, (list, tuple)) and len(temps) > 0:
                temp_val = temps[0]
                if isinstance(temp_val, (int, float)):
                    temperature = float(temp_val)
        elif "temperature" in self._latest_data:
            temp_val = self._latest_data["temperature"]
            if isinstance(temp_val, (int, float)):
                temperature = float(temp_val)

        # Extract capacity (use remaining capacity if available)
        capacity = None
        if "remaining_capacity" in self._latest_data:
            cap_val = self._latest_data["remaining_capacity"]
            if isinstance(cap_val, (int, float)):
                capacity = float(cap_val)

        # Extract cycles
        cycles = None
        if "cycles" in self._latest_data:
            cycles_val = self._latest_data["cycles"]
            if isinstance(cycles_val, (int, float)):
                cycles = int(cycles_val)

        # Create extra data dictionary with BM6-specific fields
        extra = {}
        for key in [
            "nominal_capacity",
            "cell_count",
            "cell_voltages",
            "temperatures",
            "production_date",
            "balance_status",
            "protection_status",
            "software_version",
            "fet_status",
        ]:
            if key in self._latest_data:
                extra[key] = self._latest_data[key]

        # Extract voltage and current with proper type casting
        voltage = 0.0
        if "voltage" in self._latest_data:
            volt_val = self._latest_data["voltage"]
            if isinstance(volt_val, (int, float)):
                voltage = float(volt_val)

        current = 0.0
        if "current" in self._latest_data:
            curr_val = self._latest_data["current"]
            if isinstance(curr_val, (int, float)):
                current = float(curr_val)

        state_of_charge = 0.0
        if "state_of_charge" in self._latest_data:
            soc_val = self._latest_data["state_of_charge"]
            if isinstance(soc_val, (int, float)):
                state_of_charge = float(soc_val)

        return BatteryInfo(
            voltage=voltage,
            current=current,
            temperature=temperature,
            state_of_charge=state_of_charge,
            capacity=capacity,
            cycles=cycles,
            extra=extra,
        )

    @property
    def latest_data(self) -> dict[str, object]:
        """Get the latest data from the device."""
        return self._latest_data.copy()

    async def get_device_info(self) -> dict[str, str] | None:
        """
        Get device information from the BM6.

        Returns:
            Device information dictionary or None if failed
        """
        if self.connection_pool is None:
            return None

        # Get the BLE connection from the connection pool
        connection = await self.connection_pool.connect(self.device_address)
        if connection is None:
            return None

        try:
            self.logger.info(
                "Getting device info from BM6 device %s",
                self.device_address,
            )

        except Exception:
            self.logger.exception(
                "Failed to get device info from BM6 device %s",
                self.device_address,
            )
            return None
        else:
            return {
                "device_name": "BM6_Battery_Monitor",
                "device_type": "BM6",
                "address": self.device_address,
            }
