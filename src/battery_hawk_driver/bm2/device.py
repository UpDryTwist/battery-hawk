"""BM2 battery monitor device implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import logging

    from ..base.connection import BLEConnectionPool

from ..base.protocol import (
    BaseMonitorDevice,
    BatteryInfo,
    DeviceStatus,
)
from .bm2_error_handler import BM2ErrorHandler
from .exceptions import (
    BM2ConnectionError,
)
from .protocol import (
    build_configure_display_command,
    build_request_battery_data_command,
    build_reset_device_command,
    build_set_alarm_threshold_command,
    build_set_battery_capacity_command,
    get_alarm_type_name,
    get_display_mode_name,
)


class BM2Device(BaseMonitorDevice):
    """
    BM2 battery monitor device implementation.

    This class implements the BM2 protocol for communicating with BM2 battery
    monitoring devices via Bluetooth Low Energy (BLE).
    """

    def __init__(
        self,
        device_address: str,
        config: object = None,
        connection_pool: BLEConnectionPool | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize BM2 device.

        Args:
            device_address: MAC address of the BM2 device
            config: Configuration object (unused for BM2)
            connection_pool: BLE connection pool for managing connections
            logger: Logger instance for this device
        """
        super().__init__(device_address, config, connection_pool, logger)
        self.device_type = "BM2"
        self.mac_address = device_address
        self._latest_data: dict[str, object] = {}
        # Initialize error handler for BM2-specific error handling
        self.error_handler = BM2ErrorHandler(
            device_address,
            self.logger,
            default_timeout=25.0,  # BM2 typically faster than BM6
        )

    @property
    def protocol_version(self) -> str:
        """Return the BM2 protocol version."""
        return "1.0"

    @property
    def capabilities(self) -> set[str]:
        """Return the capabilities supported by BM2 devices."""
        return {
            "read_data",
            "read_voltage",
            "read_current",
            "read_temperature",
            "read_soc",
            "read_capacity",
            "set_alarm_threshold",
            "configure_display",
            "set_battery_capacity",
            "reset_device",
        }

    async def connect(self) -> None:
        """
        Connect to the BM2 device and set up notifications.

        Raises:
            BM2ConnectionError: If connection fails or no connection pool is available
        """
        try:
            await super().connect()
            if self.connection_pool is None:
                raise BM2ConnectionError(
                    "No connection pool available for BM2 device connection.",
                    device_address=self.device_address,
                )

            connection = await self.connection_pool.connect(self.device_address)
            if connection is None:
                raise BM2ConnectionError(
                    f"Failed to get BLE connection for device {self.device_address}",
                    device_address=self.device_address,
                    connection_attempt=1,
                )

            # For now, just log that we would set up notifications
            # Note: BLE client operations will be implemented when BLEConnectionPool is enhanced
            self.logger.info(
                "BM2 device connected (notifications would be enabled for device %s)",
                self.device_address,
            )
            await self.request_battery_data()
            self.logger.info(
                "Initial data request sent to BM2 device %s",
                self.device_address,
            )
        except BM2ConnectionError:
            # Re-raise BM2-specific connection errors
            raise
        except Exception as exc:
            # Convert generic exceptions to BM2-specific errors
            self.logger.exception("Failed to set up BM2 device %s", self.device_address)
            raise BM2ConnectionError(
                f"Unexpected error during BM2 device setup: {exc}",
                device_address=self.device_address,
            ) from exc

    async def disconnect(self) -> None:
        """
        Disconnect from the BM2 device and clean up resources.

        Raises:
            RuntimeError: If no connection pool is available
        """
        # Get the BLE connection from the connection pool
        if self.connection_pool is None:
            self.logger.warning(
                "No connection pool available for BM2 device %s",
                self.device_address,
            )
            return

        connection = await self.connection_pool.connect(self.device_address)
        if connection is not None:
            # For now, just log that we would stop notifications
            # Note: BLE client operations will be implemented when BLEConnectionPool is enhanced
            self.logger.info(
                "BM2 device disconnected (notifications would be stopped for device %s)",
                self.device_address,
            )

        await super().disconnect()

    async def read_data(self) -> BatteryInfo:
        """
        Read battery data from the BM2 device.

        Returns:
            BatteryInfo: Parsed battery information

        Raises:
            RuntimeError: If read fails or data is invalid
        """
        try:
            # For now, return mock data since BLE operations are not fully implemented
            # Note: BLE read operations will be implemented when BLEConnectionPool is enhanced
            self.logger.info(
                "Reading data from BM2 device %s (mock implementation)",
                self.device_address,
            )

            # Return mock data for testing
            return BatteryInfo(
                voltage=12.6,
                current=1.2,
                temperature=25.0,
                state_of_charge=85.0,
                capacity=50.0,
                cycles=10,
                timestamp=1234567890.0,
                extra={"device_type": "BM2", "raw_data": "mock_data"},
            )
        except Exception:
            self.logger.exception(
                "Failed to read data from BM2 device %s",
                self.device_address,
            )
            raise

    async def send_command(
        self,
        command: str,
        params: dict[str, Any] | None = None,
    ) -> DeviceStatus:
        """
        Send a command to the BM2 device.

        Args:
            command: Command to send
            params: Optional parameters for the command

        Returns:
            DeviceStatus: Resulting device status

        Raises:
            RuntimeError: If command fails or is unsupported
        """
        try:
            # For now, just log the command since BLE operations are not fully implemented
            # Note: BLE command operations will be implemented when BLEConnectionPool is enhanced
            self.logger.info(
                "Sending command %s to BM2 device %s (mock implementation)",
                command,
                self.device_address,
            )

            # Handle different command types
            if command == "request_data":
                await self.request_battery_data()
            elif command == "set_alarm":
                if params:
                    alarm_type = params.get("alarm_type")
                    threshold = params.get("threshold")
                    if alarm_type is not None and threshold is not None:
                        await self.set_alarm_threshold(alarm_type, threshold)
            elif command == "configure_display":
                if params:
                    display_mode = params.get("display_mode")
                    if display_mode is not None:
                        await self.configure_display(display_mode)
            elif command == "set_capacity":
                if params:
                    capacity = params.get("capacity")
                    if capacity is not None:
                        await self.set_battery_capacity(capacity)
            elif command == "reset":
                await self.reset_device()
            else:
                self.logger.warning(
                    "Unknown command %s for BM2 device %s",
                    command,
                    self.device_address,
                )

            return DeviceStatus(
                connected=True,
                last_command=command,
                protocol_version=self.protocol_version,
                extra={"device_type": "BM2"},
            )
        except Exception:
            self.logger.exception(
                "Failed to send command %s to BM2 device %s",
                command,
                self.device_address,
            )
            raise

    async def request_battery_data(self) -> None:
        """
        Request battery data from the BM2 device.

        Raises:
            RuntimeError: If request fails
        """
        try:
            # For now, just log the request since BLE operations are not fully implemented
            # Note: BLE write operations will be implemented when BLEConnectionPool is enhanced
            command = build_request_battery_data_command()
            self.logger.debug(
                "Battery data request would be sent to BM2 device %s: %s",
                self.device_address,
                command.hex(),
            )
        except Exception:
            self.logger.exception(
                "Failed to request battery data from BM2 device %s",
                self.device_address,
            )
            raise

    async def set_alarm_threshold(self, alarm_type: int, threshold_value: int) -> None:
        """
        Set alarm threshold on the BM2 device.

        Args:
            alarm_type: Type of alarm (ALARM_LOW_VOLTAGE, ALARM_HIGH_VOLTAGE, etc.)
            threshold_value: Threshold value in appropriate units

        Raises:
            RuntimeError: If setting alarm fails
        """
        try:
            # For now, just log the request since BLE operations are not fully implemented
            # Note: BLE write operations will be implemented when BLEConnectionPool is enhanced
            command = build_set_alarm_threshold_command(alarm_type, threshold_value)
            alarm_name = get_alarm_type_name(alarm_type)
            self.logger.debug(
                "Alarm threshold request would be sent to BM2 device %s: %s (type: %s, threshold: %d)",
                self.device_address,
                command.hex(),
                alarm_name,
                threshold_value,
            )
        except Exception:
            self.logger.exception(
                "Failed to set alarm threshold on BM2 device %s (type: %d, threshold: %d)",
                self.device_address,
                alarm_type,
                threshold_value,
            )
            raise

    async def configure_display(self, display_mode: int) -> None:
        """
        Configure display mode on the BM2 device.

        Args:
            display_mode: Display mode (DISPLAY_BASIC, DISPLAY_ADVANCED, DISPLAY_DETAILED)

        Raises:
            RuntimeError: If configuration fails
        """
        try:
            # For now, just log the request since BLE operations are not fully implemented
            # Note: BLE write operations will be implemented when BLEConnectionPool is enhanced
            command = build_configure_display_command(display_mode)
            mode_name = get_display_mode_name(display_mode)
            self.logger.debug(
                "Display configuration request would be sent to BM2 device %s: %s (mode: %s)",
                self.device_address,
                command.hex(),
                mode_name,
            )
        except Exception:
            self.logger.exception(
                "Failed to configure display on BM2 device %s (mode: %d)",
                self.device_address,
                display_mode,
            )
            raise

    async def set_battery_capacity(self, capacity_mah: int) -> None:
        """
        Set battery capacity on the BM2 device.

        Args:
            capacity_mah: Battery capacity in mAh

        Raises:
            RuntimeError: If setting capacity fails
        """
        try:
            # For now, just log the request since BLE operations are not fully implemented
            # Note: BLE write operations will be implemented when BLEConnectionPool is enhanced
            command = build_set_battery_capacity_command(capacity_mah)
            self.logger.debug(
                "Battery capacity request would be sent to BM2 device %s: %s (capacity: %d mAh)",
                self.device_address,
                command.hex(),
                capacity_mah,
            )
        except Exception:
            self.logger.exception(
                "Failed to set battery capacity on BM2 device %s (capacity: %d mAh)",
                self.device_address,
                capacity_mah,
            )
            raise

    async def reset_device(self) -> None:
        """
        Reset the BM2 device to factory settings.

        Raises:
            RuntimeError: If reset fails
        """
        try:
            # For now, just log the request since BLE operations are not fully implemented
            # Note: BLE write operations will be implemented when BLEConnectionPool is enhanced
            command = build_reset_device_command()
            self.logger.debug(
                "Reset device request would be sent to BM2 device %s: %s",
                self.device_address,
                command.hex(),
            )
        except Exception:
            self.logger.exception("Failed to reset BM2 device %s", self.device_address)
            raise

    def get_device_info(self) -> dict[str, str] | None:
        """
        Get device information from the BM2 device.

        Returns:
            Device information dictionary or None if unavailable
        """
        try:
            # For now, return mock device info since BLE operations are not fully implemented
            # Note: BLE read operations will be implemented when BLEConnectionPool is enhanced
            self.logger.info(
                "Getting device info from BM2 device %s (mock implementation)",
                self.device_address,
            )

        except Exception:
            self.logger.exception(
                "Failed to get device info from BM2 device %s",
                self.device_address,
            )
            return None
        else:
            return {
                "device_name": "BM2_Battery_Monitor",
                "device_type": "BM2",
                "address": self.device_address,
            }

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

        # Extract capacity (use remaining capacity if available)
        capacity = None
        if self._latest_data.get("capacity"):
            cap_val = self._latest_data["capacity"]
            if isinstance(cap_val, (int, float)):
                capacity = float(cap_val)

        # Extract cycles (use cycle count if available)
        cycles = None
        if self._latest_data.get("cycles"):
            cycle_val = self._latest_data["cycles"]
            if isinstance(cycle_val, int):
                cycles = cycle_val

        # Extract voltage (use battery voltage if available)
        voltage = 12.0  # Default voltage
        if self._latest_data.get("voltage"):
            volt_val = self._latest_data["voltage"]
            if isinstance(volt_val, (int, float)):
                voltage = float(volt_val)

        # Extract current (use battery current if available)
        current = 0.0  # Default current
        if self._latest_data.get("current"):
            curr_val = self._latest_data["current"]
            if isinstance(curr_val, (int, float)):
                current = float(curr_val)

        # Extract state of charge (use SOC if available)
        state_of_charge = 50.0  # Default SOC
        if self._latest_data.get("state_of_charge"):
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
            timestamp=None,  # Will be set by caller
            extra={"device_type": "BM2", "raw_data": self._latest_data},
        )
