"""
BLEManager: Unified BLE Communication Base Layer.

This module provides a high-level async API for BLE device discovery, connection,
data reading, and command execution, integrating discovery, connection pooling,
protocol abstraction, retry logic, and state management.

Features:
    - Async BLE device scanning and metadata collection
    - Connection pool management with concurrency limits
    - Protocol abstraction for device-specific logic
    - Robust retry and circuit breaker error handling
    - Connection state management and event callbacks
    - Extensible for new device types and protocols

Usage Example:
    from src.battery_hawk_driver.base.ble_base import BLEManager
    import asyncio

    async def main():
        # Assume config_manager is an instance of your config system
        manager = BLEManager(config_manager)
        # Scan for devices
        devices = await manager.scan_for_devices(duration=5)
        print("Discovered:", devices)
        if devices:
            addr = next(iter(devices))
            # Connect to device
            device = await manager.connect(addr)
            # Read battery info
            info = await manager.read_data(addr)
            print("Battery info:", info)
            # Send a command
            status = await manager.send_command(addr, "ping")
            print("Command status:", status)
            # Disconnect
            await manager.disconnect(addr)
            # State history
            print("State history:", manager.get_device_history(addr))
    # asyncio.run(main())

Extension:
    - To support a new device type, implement a subclass of BaseMonitorDevice and
      update the connect() method to instantiate the correct protocol class based on
      device metadata.
    - You can inject a protocol factory or registry for more advanced use cases.

Best Practices:
    - Always use async/await for BLEManager methods.
    - Handle BLERetryError and CircuitBreakerOpenError exceptions for robust error handling.
    - Clean up connections with disconnect to avoid resource leaks.
"""

from __future__ import annotations

from .connection import BLEConnectionPool
from .discovery import BLEDiscoveryService
from .protocol import (
    BaseMonitorDevice,
    BatteryInfo,
    DeviceStatus,
)
from .retry import CircuitBreaker, retry_async
from .state import ConnectionState, ConnectionStateManager


class BLEManager:
    """
    Unified BLE communication manager for discovery, connection, and protocol operations.

    This class integrates BLE device discovery, connection pooling, protocol abstraction,
    retry logic, and state management into a single async API. It is the main entry point
    for BLE operations in the system.

    Extension:
        - To support a new device type, implement a subclass of BaseMonitorDevice and
          update the connect() method to instantiate the correct protocol class based on
          device metadata.
        - You can inject a protocol factory or registry for more advanced use cases.
    """

    def __init__(self, config_manager: object) -> None:
        """Initialize BLEManager with a configuration manager."""
        self.config = config_manager
        self.discovery = BLEDiscoveryService(config_manager)
        self.pool = BLEConnectionPool(config_manager)
        self.circuit_breaker = CircuitBreaker()
        self.device_states: dict[str, ConnectionStateManager] = {}
        self.device_protocols: dict[str, BaseMonitorDevice] = {}
        # Device protocol factory/registry could be injected for extensibility

    async def scan_for_devices(self, duration: int = 10) -> dict[str, dict]:
        """
        Scan for BLE devices and return discovered device metadata.

        Args:
            duration: Scan duration in seconds.

        Returns:
            Dict of discovered devices keyed by MAC address. Each value is a dict of device metadata.
        """
        return await self.discovery.scan_for_devices(duration=duration)

    async def connect(self, device_address: str) -> BaseMonitorDevice:
        """
        Connect to a BLE device, returning a protocol instance.

        Args:
            device_address: MAC address of the device.

        Returns:
            BaseMonitorDevice instance for the device.

        Raises:
            BLERetryError: If connection fails after retries.

        Note:
            The default implementation uses a DummyDevice. For real devices, extend this method.
        """
        # Pool manages connection concurrency
        await retry_async(circuit_breaker=self.circuit_breaker)(self.pool.connect)(
            device_address,
        )
        # Create or get protocol instance
        if device_address not in self.device_protocols:
            # For demo, use a dummy protocol; in real code, select based on device type
            class DummyDevice(BaseMonitorDevice):
                @property
                def protocol_version(self) -> str:
                    return "1.0"

                @property
                def capabilities(self) -> set[str]:
                    return {"read_data"}

                async def connect(self) -> None:
                    pass

                async def disconnect(self) -> None:
                    pass

                async def read_data(self) -> BatteryInfo:
                    return BatteryInfo(
                        voltage=12.5,
                        current=1.1,
                        temperature=25.0,
                        state_of_charge=80.0,
                    )

                async def send_command(
                    self,
                    command: str,
                    params: dict | None = None,  # noqa: ARG002
                ) -> DeviceStatus:
                    return DeviceStatus(connected=True, last_command=command)

            self.device_protocols[device_address] = DummyDevice(device_address)
        # State manager
        if device_address not in self.device_states:
            self.device_states[device_address] = ConnectionStateManager()
            await self.device_states[device_address].set_state(
                ConnectionState.CONNECTED,
            )
        return self.device_protocols[device_address]

    async def disconnect(self, device_address: str) -> None:
        """
        Disconnect from a BLE device and clean up resources.

        Args:
            device_address: MAC address of the device.
        """
        await self.pool.disconnect(device_address)
        if device_address in self.device_protocols:
            await self.device_protocols[device_address].disconnect()
        if device_address in self.device_states:
            await self.device_states[device_address].set_state(
                ConnectionState.DISCONNECTED,
            )

    async def read_data(self, device_address: str) -> BatteryInfo:
        """
        Read battery data from a connected device.

        Args:
            device_address: MAC address of the device.

        Returns:
            BatteryInfo instance.

        Raises:
            BLERetryError: If read fails after retries.
        """
        proto = self.device_protocols[device_address]
        return await retry_async(circuit_breaker=self.circuit_breaker)(
            proto.read_data,
        )()

    async def send_command(
        self,
        device_address: str,
        command: str,
        params: dict | None = None,
    ) -> DeviceStatus:
        """
        Send a command to a connected device and return its status.

        Args:
            device_address: MAC address of the device.
            command: Command string.
            params: Optional parameters.

        Returns:
            DeviceStatus instance.

        Raises:
            BLERetryError: If command fails after retries.
        """
        proto = self.device_protocols[device_address]
        return await retry_async(circuit_breaker=self.circuit_breaker)(
            proto.send_command,
        )(command, params)

    def get_device_state(self, device_address: str) -> ConnectionState:
        """
        Get the current connection state for a device.

        Args:
            device_address: MAC address of the device.

        Returns:
            ConnectionState enum value (e.g., CONNECTED, DISCONNECTED).
        """
        if device_address in self.device_states:
            return self.device_states[device_address].state
        return ConnectionState.DISCONNECTED

    def get_device_history(self, device_address: str, limit: int = 20) -> list:
        """
        Get the state transition history for a device.

        Args:
            device_address: MAC address of the device.
            limit: Max number of history entries.

        Returns:
            List of (state, timestamp) tuples.
        """
        if device_address in self.device_states:
            return self.device_states[device_address].get_state_history(limit)
        return []
