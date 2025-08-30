"""Device factory for creating and managing battery monitoring devices."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar, Union

from ..bm2.device import BM2Device
from ..bm6.device import BM6Device

if TYPE_CHECKING:
    from .connection import BLEConnectionPool

# Type alias for supported devices
DeviceType = Union[BM2Device, BM6Device]

# Type for device constructor arguments
DeviceKwargs = dict[str, Any]


class DeviceFactory:
    """
    Factory for creating device instances based on device type.

    Supports both explicit device type specification and auto-detection
    from BLE advertisement data.
    """

    # Device type registry
    DEVICE_REGISTRY: ClassVar[dict[str, type]] = {
        "BM6": BM6Device,
        "BM2": BM2Device,
    }

    # Auto-detection patterns for BLE advertisement data
    # These patterns help identify device types from advertisement data
    # Order matters - more specific patterns first to avoid conflicts
    DETECTION_PATTERNS: ClassVar[dict[str, dict[str, Any]]] = {
        "BM6": {
            "name_prefixes": ["BM6", "Battery Monitor 6"],
            "service_uuids": ["0000ff00-0000-1000-8000-00805f9b34fb"],
            "manufacturer_data_patterns": [b"BM6", b"Battery Monitor 6"],
        },
        "BM2": {
            "name_prefixes": ["BM2", "Battery Monitor 2"],
            "service_uuids": ["0000ff00-0000-1000-8000-00805f9b34fb"],
            "manufacturer_data_patterns": [b"BM2", b"Battery Monitor 2"],
        },
    }

    def __init__(self, connection_pool: BLEConnectionPool) -> None:
        """
        Initialize the device factory.

        Args:
            connection_pool: BLE connection pool for device connections
        """
        self.connection_pool = connection_pool
        self.logger = logging.getLogger(f"{__name__}.DeviceFactory")

    def create_device(
        self,
        device_type: str,
        mac_address: str,
        **kwargs: DeviceKwargs,
    ) -> DeviceType:
        """
        Create a device instance based on device type.

        Args:
            device_type: Type of device ('BM6', 'BM2')
            mac_address: MAC address of the device
            **kwargs: Additional arguments to pass to device constructor

        Returns:
            Device instance of the specified type

        Raises:
            ValueError: If device type is not supported
        """
        if device_type not in self.DEVICE_REGISTRY:
            supported_types = list(self.DEVICE_REGISTRY.keys())
            raise ValueError(
                f"Unsupported device type '{device_type}'. "
                f"Supported types: {supported_types}",
            )

        device_class = self.DEVICE_REGISTRY[device_type]
        self.logger.info("Creating %s device for %s", device_type, mac_address)

        # Handle different constructor signatures
        if device_type == "BM6":
            # BM6Device expects (device_address, config, connection_pool, logger)
            return device_class(mac_address, None, self.connection_pool, **kwargs)
        if device_type == "BM2":
            # BM2Device expects (device_address, connection_pool, logger)
            # But it inherits from BaseMonitorDevice which expects (device_address, config, connection_pool, logger)
            # So we need to pass None as config
            return device_class(mac_address, None, self.connection_pool, **kwargs)
        # For any future device types, try the BM6 signature first
        try:
            return device_class(mac_address, None, self.connection_pool, **kwargs)
        except TypeError:
            # Fall back to BM2 signature
            return device_class(mac_address, self.connection_pool, **kwargs)

    def auto_detect_device_type(
        self,
        advertisement_data: dict[str, Any],
    ) -> str | None:
        """
        Auto-detect device type from BLE advertisement data.

        Args:
            advertisement_data: Dictionary containing BLE advertisement data
                Expected keys:
                - 'name': Device name
                - 'service_uuids': List of service UUIDs
                - 'manufacturer_data': Manufacturer-specific data

        Returns:
            Detected device type ('BM6', 'BM2') or None if not detected
        """
        self.logger.debug(
            "Auto-detecting device type from advertisement: %s",
            advertisement_data,
        )

        # Handle None or invalid name
        device_name = advertisement_data.get("name", "")
        if device_name is None:
            device_name = ""
        device_name = str(device_name).upper()

        # Handle None or invalid service_uuids
        service_uuids = advertisement_data.get("service_uuids", [])
        if service_uuids is None or not isinstance(service_uuids, list):
            service_uuids = []

        # Handle None or invalid manufacturer_data
        manufacturer_data = advertisement_data.get("manufacturer_data", b"")
        if manufacturer_data is None:
            manufacturer_data = b""

        # Primary detection: Check device name for BM6 or BM2
        if "BM6" in device_name:
            self.logger.info(
                "Detected BM6 by device name: '%s' contains 'BM6'",
                device_name,
            )
            return "BM6"
        if "BM2" in device_name:
            self.logger.info(
                "Detected BM2 by device name: '%s' contains 'BM2'",
                device_name,
            )
            return "BM2"

        # Secondary detection: Check manufacturer data patterns
        if manufacturer_data:
            for device_type, patterns in self.DETECTION_PATTERNS.items():
                for pattern in patterns["manufacturer_data_patterns"]:
                    # Convert both to bytes for comparison
                    if isinstance(pattern, str):
                        pattern_bytes = pattern.encode()
                    else:
                        pattern_bytes = pattern

                    if isinstance(manufacturer_data, str):
                        manufacturer_bytes = manufacturer_data.encode()
                    else:
                        manufacturer_bytes = manufacturer_data

                    if pattern_bytes in manufacturer_bytes:
                        self.logger.info(
                            "Detected %s by manufacturer data: %s",
                            device_type,
                            pattern,
                        )
                        return device_type

        # Tertiary detection: Check service UUIDs (least specific)
        for device_type, patterns in self.DETECTION_PATTERNS.items():
            for uuid in patterns["service_uuids"]:
                if uuid in service_uuids:
                    self.logger.info(
                        "Detected %s by service UUID: %s",
                        device_type,
                        uuid,
                    )
                    return device_type

        self.logger.warning(
            "Could not auto-detect device type from advertisement: %s",
            advertisement_data,
        )
        return None

    def create_device_from_advertisement(
        self,
        mac_address: str,
        advertisement_data: dict[str, Any],
        **kwargs: DeviceKwargs,
    ) -> DeviceType | None:
        """
        Create a device instance by auto-detecting the type from advertisement data.

        Args:
            mac_address: MAC address of the device
            advertisement_data: BLE advertisement data for auto-detection
            **kwargs: Additional arguments to pass to device constructor

        Returns:
            Device instance if type was detected, None otherwise
        """
        device_type = self.auto_detect_device_type(advertisement_data)
        if device_type is None:
            return None

        return self.create_device(device_type, mac_address, **kwargs)

    def get_supported_device_types(self) -> list[str]:
        """
        Get list of supported device types.

        Returns:
            List of supported device type names
        """
        return list(self.DEVICE_REGISTRY.keys())

    def register_device_type(self, device_type: str, device_class: type) -> None:
        """
        Register a new device type with the factory.

        Args:
            device_type: Name of the device type
            device_class: Class to instantiate for this device type
        """
        self.DEVICE_REGISTRY[device_type] = device_class
        self.logger.info("Registered new device type: %s", device_type)

    def unregister_device_type(self, device_type: str) -> None:
        """
        Unregister a device type from the factory.

        Args:
            device_type: Name of the device type to unregister
        """
        if device_type in self.DEVICE_REGISTRY:
            del self.DEVICE_REGISTRY[device_type]
            self.logger.info("Unregistered device type: %s", device_type)
        else:
            self.logger.warning(
                "Attempted to unregister unknown device type: %s",
                device_type,
            )
