"""
Registry classes for managing devices and vehicles in Battery Hawk.

This module provides the DeviceRegistry and VehicleRegistry classes for
tracking discovered devices and managing vehicle configurations.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from battery_hawk.config.config_manager import ConfigManager


class DeviceRegistry:
    """
    Registry for managing discovered and configured BLE devices.

    Tracks device metadata, configuration, and association with vehicles.
    Provides thread-safe operations for device management.
    """

    def __init__(self, config_manager: ConfigManager) -> None:
        """
        Initialize DeviceRegistry with configuration manager.

        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager
        self.logger = logging.getLogger("battery_hawk.device_registry")
        self.devices: dict[str, dict[str, Any]] = {}
        self._load_devices()

    def _load_devices(self) -> None:
        """Load devices from configuration."""
        try:
            devices_config = self.config.get_config("devices")
            self.devices = devices_config.get("devices", {})
            self.logger.info("Loaded %d devices from configuration", len(self.devices))
        except Exception:
            self.logger.exception("Failed to load devices")
            self.devices = {}

    async def register_discovered_devices(
        self,
        discovered_devices: dict[str, dict[str, Any]],
    ) -> None:
        """
        Register discovered devices with the registry.

        Args:
            discovered_devices: Dictionary of discovered device metadata
        """
        for mac_address, device_info in discovered_devices.items():
            if mac_address not in self.devices:
                self.devices[mac_address] = {
                    "mac_address": mac_address,
                    "device_type": device_info.get("device_type", "unknown"),
                    "friendly_name": device_info.get("name", f"Device_{mac_address}"),
                    "vehicle_id": None,
                    "status": "discovered",
                    "discovered_at": datetime.now(UTC).isoformat(),
                    "configured_at": None,
                    "polling_interval": 3600,  # Default 1 hour
                    "connection_config": {
                        "retry_attempts": 3,
                        "retry_interval": 60,
                        "reconnection_delay": 300,
                    },
                }
                self.logger.info("Registered discovered device: %s", mac_address)

        await self._save_devices()

    async def configure_device(
        self,
        mac_address: str,
        device_type: str,
        friendly_name: str,
        vehicle_id: str | None = None,
        polling_interval: int = 3600,
    ) -> bool:
        """
        Configure a discovered device.

        Args:
            mac_address: MAC address of the device
            device_type: Type of device (BM6, BM2, etc.)
            friendly_name: Human-readable name for the device
            vehicle_id: Optional vehicle ID to associate with
            polling_interval: Polling interval in seconds

        Returns:
            True if device was configured successfully
        """
        if mac_address not in self.devices:
            self.logger.warning(
                "Attempted to configure unknown device: %s",
                mac_address,
            )
            return False

        self.devices[mac_address].update(
            {
                "device_type": device_type,
                "friendly_name": friendly_name,
                "vehicle_id": vehicle_id,
                "status": "configured",
                "configured_at": datetime.now(UTC).isoformat(),
                "polling_interval": polling_interval,
            },
        )

        self.logger.info("Configured device %s as %s", mac_address, device_type)
        await self._save_devices()
        return True

    def get_device(self, mac_address: str) -> dict[str, Any] | None:
        """
        Get device information by MAC address.

        Args:
            mac_address: MAC address of the device

        Returns:
            Device information dictionary or None if not found
        """
        return self.devices.get(mac_address)

    def get_configured_devices(self) -> list[dict[str, Any]]:
        """
        Get all configured devices.

        Returns:
            List of configured device dictionaries
        """
        return [
            device
            for device in self.devices.values()
            if device.get("status") == "configured"
        ]

    def get_devices_by_vehicle(self, vehicle_id: str) -> list[dict[str, Any]]:
        """
        Get all devices associated with a vehicle.

        Args:
            vehicle_id: Vehicle ID to filter by

        Returns:
            List of device dictionaries for the vehicle
        """
        return [
            device
            for device in self.devices.values()
            if device.get("vehicle_id") == vehicle_id
        ]

    async def remove_device(self, mac_address: str) -> bool:
        """
        Remove a device from the registry.

        Args:
            mac_address: MAC address of the device to remove

        Returns:
            True if device was removed successfully
        """
        if mac_address not in self.devices:
            self.logger.warning("Attempted to remove unknown device: %s", mac_address)
            return False

        del self.devices[mac_address]
        self.logger.info("Removed device: %s", mac_address)
        await self._save_devices()
        return True

    async def _save_devices(self) -> None:
        """Save devices to configuration."""
        try:
            devices_config = self.config.get_config("devices")
            devices_config["devices"] = self.devices
            self.config.save_config("devices")
            self.logger.debug("Saved devices to configuration")
        except Exception:
            self.logger.exception("Failed to save devices")


class VehicleRegistry:
    """
    Registry for managing vehicle configurations.

    Tracks vehicle metadata and their associated devices.
    Provides thread-safe operations for vehicle management.
    """

    def __init__(self, config_manager: ConfigManager) -> None:
        """
        Initialize VehicleRegistry with configuration manager.

        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager
        self.logger = logging.getLogger("battery_hawk.vehicle_registry")
        self.vehicles: dict[str, dict[str, Any]] = {}
        self._load_vehicles()

    def _load_vehicles(self) -> None:
        """Load vehicles from configuration."""
        try:
            vehicles_config = self.config.get_config("vehicles")
            self.vehicles = vehicles_config.get("vehicles", {})
            self.logger.info(
                "Loaded %d vehicles from configuration",
                len(self.vehicles),
            )
        except Exception:
            self.logger.exception("Failed to load vehicles")
            self.vehicles = {}

    async def create_vehicle(self, name: str, vehicle_id: str | None = None) -> str:
        """
        Create a new vehicle.

        Args:
            name: Human-readable name for the vehicle
            vehicle_id: Optional custom vehicle ID

        Returns:
            Vehicle ID of the created vehicle
        """
        if vehicle_id is None:
            # Generate sequential vehicle ID
            vehicle_id = f"vehicle_{len(self.vehicles) + 1}"

        if vehicle_id in self.vehicles:
            self.logger.warning("Vehicle ID %s already exists", vehicle_id)
            return vehicle_id

        self.vehicles[vehicle_id] = {
            "name": name,
            "created_at": datetime.now(UTC).isoformat(),
            "device_count": 0,
        }

        self.logger.info("Created vehicle %s: %s", vehicle_id, name)
        await self._save_vehicles()
        return vehicle_id

    def get_vehicle(self, vehicle_id: str) -> dict[str, Any] | None:
        """
        Get vehicle information by ID.

        Args:
            vehicle_id: Vehicle ID

        Returns:
            Vehicle information dictionary or None if not found
        """
        return self.vehicles.get(vehicle_id)

    def get_all_vehicles(self) -> list[dict[str, Any]]:
        """
        Get all vehicles.

        Returns:
            List of vehicle dictionaries
        """
        return list(self.vehicles.values())

    async def update_vehicle_name(self, vehicle_id: str, name: str) -> bool:
        """
        Update vehicle name.

        Args:
            vehicle_id: Vehicle ID
            name: New name for the vehicle

        Returns:
            True if vehicle was updated successfully
        """
        if vehicle_id not in self.vehicles:
            self.logger.warning("Attempted to update unknown vehicle: %s", vehicle_id)
            return False

        self.vehicles[vehicle_id]["name"] = name
        self.logger.info("Updated vehicle %s name to: %s", vehicle_id, name)
        await self._save_vehicles()
        return True

    async def delete_vehicle(self, vehicle_id: str) -> bool:
        """
        Delete a vehicle.

        Args:
            vehicle_id: Vehicle ID to delete

        Returns:
            True if vehicle was deleted successfully
        """
        if vehicle_id not in self.vehicles:
            self.logger.warning("Attempted to delete unknown vehicle: %s", vehicle_id)
            return False

        del self.vehicles[vehicle_id]
        self.logger.info("Deleted vehicle: %s", vehicle_id)
        await self._save_vehicles()
        return True

    async def save_vehicles(self) -> None:
        """Save vehicles to configuration."""
        await self._save_vehicles()

    async def _save_vehicles(self) -> None:
        """Save vehicles to configuration."""
        try:
            vehicles_config = self.config.get_config("vehicles")
            vehicles_config["vehicles"] = self.vehicles
            self.config.save_config("vehicles")
            self.logger.debug("Saved vehicles to configuration")
        except Exception:
            self.logger.exception("Failed to save vehicles")
