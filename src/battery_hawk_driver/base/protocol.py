"""
Protocol Abstraction Layer for BLE Battery Monitor Devices.

This module defines the abstract base class and data models for implementing
protocols for BLE battery monitor devices (e.g., BM2, BM6). It provides a
standard interface for device connection, data reading, command execution,
protocol versioning, and capability detection.

Extension:
    - Subclass `BaseMonitorDevice` to implement support for a specific device type.
    - Implement all abstract async methods and required properties.
    - Use `BatteryInfo` and `DeviceStatus` dataclasses for structured data.

Example:
    from src.battery_hawk_driver.base.protocol import BaseMonitorDevice, BatteryInfo, DeviceStatus
    import asyncio

    class MyDevice(BaseMonitorDevice):
        @property
        def protocol_version(self) -> str:
            return "1.0"
        @property
        def capabilities(self) -> set[str]:
            return {"read_voltage", "read_soc"}
        async def connect(self) -> None:
            pass  # Implement connection logic
        async def disconnect(self) -> None:
            pass  # Implement disconnect logic
        async def read_data(self) -> BatteryInfo:
            return BatteryInfo(voltage=12.6, current=1.2, temperature=25.0, state_of_charge=90.0)
        async def send_command(self, command: str, params: dict | None = None) -> DeviceStatus:
            return DeviceStatus(connected=True, last_command=command)

    # Usage
    # device = MyDevice("AA:BB:CC:DD:EE:FF")
    # asyncio.run(device.connect())
    # info = asyncio.run(device.read_data())
    # print(info)
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass
from typing import Any

from .connection import BLEConnectionPool


@dataclass
class BatteryInfo:
    """Data model for battery information reported by a BLE monitor device."""

    voltage: float  # Volts
    current: float  # Amperes
    temperature: float  # Celsius
    state_of_charge: float  # Percentage (0-100)
    capacity: float | None = None  # mAh, optional
    cycles: int | None = None  # Charge/discharge cycles
    timestamp: float | None = None  # Unix timestamp
    extra: dict[str, Any] | None = None  # Device-specific extra fields


@dataclass
class DeviceStatus:
    """Data model for device status and connection state."""

    connected: bool
    error_code: int | None = None
    error_message: str | None = None
    protocol_version: str | None = None
    last_command: str | None = None
    extra: dict[str, Any] | None = None


class BaseMonitorDevice(abc.ABC):
    """
    Abstract base class for BLE battery monitor device protocol implementations.

    By default, manages a BLEConnectionPool and logger. Subclasses may override
    these attributes if custom behavior is needed.
    """

    def __init__(
        self,
        device_address: str,
        config: object = None,
        connection_pool: BLEConnectionPool | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize BaseMonitorDevice with device address, config, pool, and logger."""
        self.device_address = device_address
        self.config = config
        self.connection_pool = connection_pool or (
            BLEConnectionPool(config) if config is not None else None
        )
        self.logger = logger or logging.getLogger(
            f"battery_hawk.device.{device_address}",
        )

    @property
    @abc.abstractmethod
    def protocol_version(self) -> str:
        """Return the protocol version implemented by this device."""
        ...

    @property
    @abc.abstractmethod
    def capabilities(self) -> set[str]:
        """Return a set of supported capability strings for this device."""
        ...

    async def connect(self) -> None:
        """
        Establish a BLE connection to the device using the connection pool.

        Subclasses may override this method if custom connection logic is needed.

        Raises:
            Exception if connection fails.
        """
        if self.connection_pool is None:
            raise RuntimeError("No connection pool available for device connection.")
        self.logger.info("Connecting to device %s", self.device_address)
        await self.connection_pool.connect(self.device_address)
        self.logger.info("Connected to device %s", self.device_address)

    async def disconnect(self) -> None:
        """
        Disconnect from the BLE device and clean up resources using the connection pool.

        Subclasses may override this method if custom disconnection logic is needed.
        """
        if self.connection_pool is None:
            raise RuntimeError("No connection pool available for device disconnection.")
        self.logger.info("Disconnecting from device %s", self.device_address)
        await self.connection_pool.disconnect(self.device_address)
        self.logger.info("Disconnected from device %s", self.device_address)

    @abc.abstractmethod
    async def read_data(self) -> BatteryInfo:
        """
        Read battery data from the device.

        Returns:
            BatteryInfo: Parsed battery information.

        Raises:
            Exception if read fails or data is invalid.
        """
        ...

    @abc.abstractmethod
    async def send_command(
        self,
        command: str,
        params: dict[str, Any] | None = None,
    ) -> DeviceStatus:
        """
        Send a command to the device and return its status.

        Args:
            command: Command string to send.
            params: Optional parameters for the command.

        Returns:
            DeviceStatus: Resulting device status after command execution.

        Raises:
            Exception if command fails or is unsupported.
        """
        ...

    def has_capability(self, cap: str) -> bool:
        """Check if the device supports a given capability string."""
        return cap in self.capabilities
