"""Mock BLE devices and services for testing."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, Any

from src.battery_hawk_driver.bm6.crypto import BM6Crypto

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class MockBLEClient:
    """Mock BLE client that simulates device responses."""

    def __init__(self, device_type: str, mac_address: str) -> None:
        """
        Initialize mock BLE client.

        Args:
            device_type: Type of device ('BM6', 'BM2')
            mac_address: MAC address of the device
        """
        self.device_type = device_type
        self.mac_address = mac_address
        self.connected = False
        self.logger = logging.getLogger(f"{__name__}.MockBLEClient.{device_type}")

        # Mock characteristic data
        self._setup_mock_data()

    def _setup_mock_data(self) -> None:
        """Set up mock characteristic data based on device type."""
        if self.device_type == "BM6":
            # BM6 mock data: voltage, current, capacity, soc, temp, power
            self.mock_data = bytes(
                [
                    0xE8,
                    0x03,  # Voltage: 1000 (10.00V)
                    0x64,
                    0x00,  # Current: 100 (1.00A)
                    0x90,
                    0x01,  # Capacity: 400 (400mAh)
                    0x64,  # SOC: 100 (100%)
                    0x14,  # Temperature: 20 (20°C)
                ],
            )
        elif self.device_type == "BM2":
            # BM2 mock data: header, voltage, current, temp, soc, capacity, checksum
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
            self.mock_data = data + bytes([checksum])
        else:
            raise ValueError(f"Unsupported device type: {self.device_type}")

    async def connect(self) -> None:
        """Mock connection to device."""
        await asyncio.sleep(0.1)  # Simulate connection delay
        self.connected = True
        self.logger.info(
            "Mock %s device connected: %s",
            self.device_type,
            self.mac_address,
        )

    async def disconnect(self) -> None:
        """Mock disconnection from device."""
        await asyncio.sleep(0.05)  # Simulate disconnection delay
        self.connected = False
        self.logger.info(
            "Mock %s device disconnected: %s",
            self.device_type,
            self.mac_address,
        )

    async def read_gatt_char(self, char_uuid: str) -> bytes:
        """
        Mock reading GATT characteristic.

        Args:
            char_uuid: Characteristic UUID to read

        Returns:
            Mock data bytes
        """
        if not self.connected:
            raise ConnectionError("Device not connected")

        await asyncio.sleep(0.05)  # Simulate read delay

        # Simulate occasional read failures
        if (
            hasattr(self, "_read_failure_rate")
            and self._read_failure_rate > 0
            and random.random() < self._read_failure_rate
        ):
            raise ConnectionError("Simulated read failure")

        self.logger.debug("Mock read from %s: %s", char_uuid, self.mock_data.hex())
        return self.mock_data

    async def write_gatt_char(self, char_uuid: str, data: bytes) -> None:
        """
        Mock writing to GATT characteristic.

        Args:
            char_uuid: Characteristic UUID to write to
            data: Data to write
        """
        if not self.connected:
            raise ConnectionError("Device not connected")

        await asyncio.sleep(0.05)  # Simulate write delay
        self.logger.debug("Mock write to %s: %s", char_uuid, data.hex())

        # For BM6 devices, simulate a response notification when a command is written
        if self.device_type == "BM6" and hasattr(self, "_notification_callback"):
            # Simulate BM6 response data after a short delay
            task = asyncio.create_task(self._simulate_bm6_response())
            # Store task reference to prevent garbage collection
            self._response_task = task

    def set_read_failure_rate(self, rate: float) -> None:
        """
        Set the rate of simulated read failures.

        Args:
            rate: Failure rate between 0.0 and 1.0
        """
        self._read_failure_rate = max(0.0, min(1.0, rate))

    async def start_notify(
        self,
        char_uuid: str,
        callback: Callable[[str, bytearray], None],
    ) -> None:
        """
        Mock starting notifications on a characteristic.

        Args:
            char_uuid: Characteristic UUID to start notifications on
            callback: Callback function to call when notifications are received
        """
        if not self.connected:
            raise ConnectionError("Device not connected")

        self._notification_callback = callback
        self.logger.debug("Mock notifications started on %s", char_uuid)

    async def stop_notify(self, char_uuid: str) -> None:
        """
        Mock stopping notifications on a characteristic.

        Args:
            char_uuid: Characteristic UUID to stop notifications on
        """
        if hasattr(self, "_notification_callback"):
            delattr(self, "_notification_callback")
        self.logger.debug("Mock notifications stopped on %s", char_uuid)

    async def _simulate_bm6_response(self) -> None:
        """Simulate a BM6 device response after a command is written."""
        await asyncio.sleep(0.1)  # Small delay to simulate device processing

        if hasattr(self, "_notification_callback") and self._notification_callback:
            # Generate mock BM6 response data in the correct format
            unencrypted_data = bytes(
                [
                    0xD1,
                    0x55,
                    0x07,  # BM6 response prefix
                    0x00,  # Status
                    0x00,  # Temperature sign
                    0x00,  # Skip byte
                    0x14,  # Temperature (20°C)
                    0x64,  # SOC (100%)
                    0x05,
                    0xDC,  # Voltage (15.00V)
                    0x00,
                    0x00,
                    0x00,
                    0x00,
                    0x00,
                    0x00,  # Padding
                ],
            )

            # Encrypt the data using BM6 crypto for realistic simulation
            try:
                crypto = BM6Crypto()
                response_data = crypto.encrypt(unencrypted_data)
            except (ImportError, AttributeError):
                # Fall back to unencrypted data if crypto fails
                response_data = unencrypted_data

            try:
                self._notification_callback("", bytearray(response_data))
                self.logger.debug("Simulated BM6 response: %s", response_data.hex())
            except (TypeError, AttributeError) as e:
                self.logger.warning("Failed to send mock notification: %s", e)


class MockBLEDevice:
    """Mock BLE device that simulates advertisement data."""

    def __init__(
        self,
        device_type: str,
        mac_address: str,
        name: str | None = None,
    ) -> None:
        """
        Initialize mock BLE device.

        Args:
            device_type: Type of device ('BM6', 'BM2')
            mac_address: MAC address of the device
            name: Device name (auto-generated if not provided)
        """
        self.device_type = device_type
        self.mac_address = mac_address
        self.name = name or f"{device_type}_Device_{mac_address[-6:]}"
        self.logger = logging.getLogger(f"{__name__}.MockBLEDevice.{device_type}")

        # Setup advertisement data
        self._setup_advertisement_data()

    def _setup_advertisement_data(self) -> None:
        """Set up advertisement data based on device type."""
        if self.device_type == "BM6":
            self.advertisement_data = {
                "name": self.name,
                "service_uuids": ["0000ff00-0000-1000-8000-00805f9b34fb"],
                "manufacturer_data": b"BM6_Battery_Monitor_6",
                "rssi": -65,
                "address": self.mac_address,
            }
        elif self.device_type == "BM2":
            self.advertisement_data = {
                "name": self.name,
                "service_uuids": ["0000ff00-0000-1000-8000-00805f9b34fb"],
                "manufacturer_data": b"BM2_Battery_Monitor_2",
                "rssi": -70,
                "address": self.mac_address,
            }
        else:
            raise ValueError(f"Unsupported device type: {self.device_type}")

    def get_advertisement_data(self) -> dict[str, Any]:
        """
        Get advertisement data for this device.

        Returns:
            Dictionary containing advertisement data
        """
        return self.advertisement_data.copy()


class MockBLEConnectionPool:
    """Mock BLE connection pool for testing."""

    def __init__(self) -> None:
        """Initialize mock connection pool."""
        self.connections: dict[str, MockBLEClient] = {}
        self.logger = logging.getLogger(f"{__name__}.MockBLEConnectionPool")

    async def connect(
        self,
        mac_address: str,
        device_type: str | None = None,
    ) -> MockBLEClient:
        """
        Mock connection to device.

        Args:
            mac_address: MAC address of the device
            device_type: Type of device (auto-detected if not provided)

        Returns:
            Mock BLE client instance
        """
        if mac_address in self.connections:
            client = self.connections[mac_address]
            if not client.connected:
                await client.connect()
            return client

        # Auto-detect device type from MAC address if not provided
        if device_type is None:
            if "BM6" in mac_address or mac_address.endswith("01"):
                device_type = "BM6"
            elif "BM2" in mac_address or mac_address.endswith("02"):
                device_type = "BM2"
            else:
                device_type = "BM6"  # Default

        client = MockBLEClient(device_type, mac_address)
        await client.connect()
        self.connections[mac_address] = client

        self.logger.info(
            "Mock connection established to %s device: %s",
            device_type,
            mac_address,
        )
        return client

    async def release(self, mac_address: str) -> None:
        """
        Mock release of connection.

        Args:
            mac_address: MAC address of the device
        """
        if mac_address in self.connections:
            client = self.connections[mac_address]
            if client.connected:
                await client.disconnect()
            self.logger.info("Mock connection released for: %s", mac_address)

    async def disconnect_all(self) -> None:
        """Disconnect all mock connections."""
        for mac_address in list(self.connections.keys()):
            await self.release(mac_address)
        self.connections.clear()
        self.logger.info("All mock connections disconnected")

    def is_connected(self, mac_address: str) -> bool:
        """
        Check if device is connected.

        Args:
            mac_address: MAC address of the device

        Returns:
            True if device is connected, False otherwise
        """
        if mac_address in self.connections:
            return self.connections[mac_address].connected
        return False

    async def write_characteristic(
        self,
        mac_address: str,
        char_uuid: str,
        data: bytes,
    ) -> None:
        """
        Mock writing to GATT characteristic.

        Args:
            mac_address: MAC address of the device
            char_uuid: Characteristic UUID to write to
            data: Data to write
        """
        if mac_address in self.connections:
            client = self.connections[mac_address]
            await client.write_gatt_char(char_uuid, data)
            self.logger.info(
                "Mock write to %s characteristic %s: %s",
                mac_address,
                char_uuid,
                data.hex(),
            )

    async def start_notifications(
        self,
        mac_address: str,
        char_uuid: str,
        callback: Callable[[str, bytearray], None],
    ) -> None:
        """
        Mock starting notifications for a GATT characteristic.

        Args:
            mac_address: MAC address of the device
            char_uuid: Characteristic UUID to subscribe to
            callback: Function to call when notifications are received
        """
        if mac_address in self.connections:
            client = self.connections[mac_address]
            await client.start_notify(char_uuid, callback)
            self.logger.info(
                "Mock notifications started for %s characteristic %s",
                mac_address,
                char_uuid,
            )

    async def stop_notifications(
        self,
        mac_address: str,
        char_uuid: str,
    ) -> None:
        """
        Mock stopping notifications for a GATT characteristic.

        Args:
            mac_address: MAC address of the device
            char_uuid: Characteristic UUID to stop notifications on
        """
        if mac_address in self.connections:
            client = self.connections[mac_address]
            await client.stop_notify(char_uuid)
            self.logger.info(
                "Mock notifications stopped for %s characteristic %s",
                mac_address,
                char_uuid,
            )

    async def disconnect(self, mac_address: str) -> None:
        """
        Mock disconnecting from a device.

        Args:
            mac_address: MAC address of the device to disconnect from
        """
        if mac_address in self.connections:
            client = self.connections[mac_address]
            client.connected = False
            self.logger.info("Mock device disconnected: %s", mac_address)
        else:
            self.logger.warning(
                "Attempted to disconnect unknown device: %s",
                mac_address,
            )


class MockBLEDiscoveryService:
    """Mock BLE discovery service for testing."""

    def __init__(self) -> None:
        """Initialize mock discovery service."""
        self.discovered_devices: list[MockBLEDevice] = []
        self.logger = logging.getLogger(f"{__name__}.MockBLEDiscoveryService")

    def add_mock_device(
        self,
        device_type: str,
        mac_address: str,
        name: str | None = None,
    ) -> None:
        """
        Add a mock device for discovery.

        Args:
            device_type: Type of device ('BM6', 'BM2')
            mac_address: MAC address of the device
            name: Device name (optional)
        """
        device = MockBLEDevice(device_type, mac_address, name)
        self.discovered_devices.append(device)
        self.logger.info(
            "Added mock %s device for discovery: %s",
            device_type,
            mac_address,
        )

    async def scan_for_devices(self, duration: int = 10) -> list[MockBLEDevice]:
        """
        Mock device discovery scan.

        Args:
            duration: Scan duration in seconds (ignored in mock)

        Returns:
            List of discovered mock devices
        """
        await asyncio.sleep(0.1)  # Simulate scan delay
        self.logger.info(
            "Mock scan completed, found %d devices",
            len(self.discovered_devices),
        )
        return self.discovered_devices.copy()

    def clear_discovered_devices(self) -> None:
        """Clear the list of discovered devices."""
        self.discovered_devices.clear()
        self.logger.info("Cleared discovered devices list")
