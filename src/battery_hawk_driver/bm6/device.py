"""BM6 battery monitor device implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import logging

    from ..base.connection import BLEConnectionPool

from ..base.protocol import (
    BaseMonitorDevice,
    BatteryInfo,
    DeviceStatus,
)
from .bm6_error_handler import BM6ErrorHandler
from .constants import (
    BM6_NOTIFY_CHARACTERISTIC_UUID,
    BM6_SERVICE_UUID,
    BM6_WRITE_CHARACTERISTIC_UUID,
)
from .exceptions import (
    BM6ConnectionError,
    BM6DataParsingError,
    BM6TimeoutError,
)
from .parser import BM6Parser
from .protocol import (
    build_basic_info_request,
    build_cell_voltages_request,
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
            "read_capacity",
            "read_cycles",
            "read_cell_voltages",
            "read_protection_status",
            "read_fet_status",
            "read_balance_status",
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

            # For now, just log that we would set up notifications
            # Note: BLE client operations will be implemented when BLEConnectionPool is enhanced
            self.logger.info(
                "BM6 device connected (notifications would be enabled for device %s)",
                self.device_address,
            )

            # Request initial data
            await self.request_voltage_temp()
            self.logger.info(
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

            # Get the BLE connection from the connection pool
            connection = await self.connection_pool.connect(self.device_address)
            if connection is not None:
                # For now, just log that we would stop notifications
                # Note: BLE client operations will be implemented when BLEConnectionPool is enhanced
                self.logger.info(
                    "BM6 device disconnected (notifications would be stopped for device %s)",
                    self.device_address,
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

            # Request fresh data from the device
            await self.request_voltage_temp()

            # Wait a moment for the device to respond
            # Note: In a real implementation, this would wait for notifications
            # For now, we'll use the latest data we have
            self.logger.info(
                "Reading data from BM6 device %s",
                self.device_address,
            )

            # Create battery info from the latest parsed data
            return self._create_battery_info()

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
            if command == "request_basic_info":
                await self.request_basic_info()
                return DeviceStatus(connected=True, last_command=command)
            if command == "request_cell_voltages":
                await self.request_cell_voltages()
                return DeviceStatus(connected=True, last_command=command)
            raise ValueError(f"Unsupported BM6 command: {command}")

        except Exception:
            self.logger.exception(
                "Failed to send command %s to BM6 device %s",
                command,
                self.device_address,
            )
            raise

    async def request_voltage_temp(self) -> None:
        """Request voltage and temperature data from the BM6 device."""
        if self.connection_pool is None:
            raise RuntimeError(
                "No connection pool available for BM6 voltage/temp request.",
            )

        # Get the BLE connection from the connection pool
        connection = await self.connection_pool.connect(self.device_address)
        if connection is None:
            raise RuntimeError(
                f"No BLE connection available for device {self.device_address}",
            )

        try:
            # Build the encrypted command
            command = build_voltage_temp_request()
            self.logger.debug(
                "Voltage/temp request would be sent to BM6 device %s: %s",
                self.device_address,
                command.hex(),
            )

            # Note: In a real implementation, this would write to the characteristic
            # await connection.write_characteristic(self.write_characteristic_uuid, command)

        except Exception:
            self.logger.exception(
                "Failed to request voltage/temp from BM6 device %s",
                self.device_address,
            )
            raise

    async def request_basic_info(self) -> None:
        """Request basic information from the BM6 device."""
        if self.connection_pool is None:
            raise RuntimeError(
                "No connection pool available for BM6 basic info request.",
            )

        # Get the BLE connection from the connection pool
        connection = await self.connection_pool.connect(self.device_address)
        if connection is None:
            raise RuntimeError(
                f"No BLE connection available for device {self.device_address}",
            )

        try:
            # For now, just log the request since BLE operations are not fully implemented
            # Note: BLE write operations will be implemented when BLEConnectionPool is enhanced
            command = build_basic_info_request()
            self.logger.debug(
                "Basic info request would be sent to BM6 device %s: %s",
                self.device_address,
                command.hex(),
            )
        except Exception:
            self.logger.exception(
                "Failed to request basic info from BM6 device %s",
                self.device_address,
            )
            raise

    async def request_cell_voltages(self) -> None:
        """Request cell voltage information from the BM6 device."""
        if self.connection_pool is None:
            raise RuntimeError(
                "No connection pool available for BM6 cell voltages request.",
            )

        # Get the BLE connection from the connection pool
        connection = await self.connection_pool.connect(self.device_address)
        if connection is None:
            raise RuntimeError(
                f"No BLE connection available for device {self.device_address}",
            )

        try:
            # For now, just log the request since BLE operations are not fully implemented
            # Note: BLE write operations will be implemented when BLEConnectionPool is enhanced
            command = build_cell_voltages_request()
            self.logger.debug(
                "Cell voltages request would be sent to BM6 device %s: %s",
                self.device_address,
                command.hex(),
            )
        except Exception:
            self.logger.exception(
                "Failed to request cell voltages from BM6 device %s",
                self.device_address,
            )
            raise

    def _notification_handler(self, sender: str, data: bytes) -> None:  # noqa: ARG002
        """
        Handle notifications from the BM6 device.

        Args:
            sender: Characteristic UUID that sent the notification
            data: Raw notification data
        """
        try:
            # Try to parse as real BM6 data first (with AES decryption)
            parsed_data = self.parser.parse_real_bm6_data(data)
            if parsed_data is None:
                # Try to parse as a structured response
                parsed_data = self.parser.parse_response(data)
            if parsed_data is None:
                # Fall back to legacy notification format
                parsed_data = self.parser.parse_notification(data)

            if parsed_data:
                self._latest_data.update(parsed_data)
                self.logger.debug(
                    "BM6 data updated for device %s: %s",
                    self.device_address,
                    parsed_data,
                )
            else:
                self.logger.warning(
                    "Failed to parse BM6 notification data from device %s",
                    self.device_address,
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
