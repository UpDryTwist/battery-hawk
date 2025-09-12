"""BLE device discovery service for battery monitor devices."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

try:
    from bleak import BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
except ImportError:
    BleakScanner = None  # For environments without Bleak
    BLEDevice = None
    AdvertisementData = None

# Import the BLE scan coordination semaphore
try:
    from .connection import get_ble_scan_semaphore
except ImportError:
    import asyncio

    # Fallback if connection module is not available
    def get_ble_scan_semaphore() -> asyncio.Semaphore:
        """Get or create a fallback BLE scan coordination semaphore."""
        return asyncio.Semaphore(1)


# Constants
TUPLE_SIZE_DEVICE_AND_ADV = 2


class BLEDiscoveryService:
    """Async BLE discovery service for finding battery monitor devices using Bleak."""

    def __init__(
        self,
        config_manager: Any,
        storage_path: str | None = None,
        *,
        disable_storage: bool = False,
    ) -> None:
        """
        Initialize BLEDiscoveryService with config manager and optional storage path.

        Args:
            config_manager: Configuration manager instance
            storage_path: Optional custom path for device storage file
            disable_storage: If True, disable loading from and writing to storage
        """
        self.config = config_manager
        # type: ignore[reportAttributeAccessIssue] - config is duck-typed

        self.discovered_devices: dict[str, dict[str, Any]] = {}
        self.logger = logging.getLogger("battery_hawk.ble_discovery")
        self.storage_path = storage_path or os.path.join(
            getattr(config_manager, "config_dir", "."),
            "discovered_devices.json",
        )
        self.disable_storage = disable_storage
        # Optional adapter selection from config (e.g., 'hci0')
        try:
            self.adapter: str | None = (
                self.config.get_config("system").get("bluetooth", {}).get("adapter")
            )
        except (AttributeError, TypeError, KeyError):
            # Be resilient to unexpected config shapes or missing get_config
            self.adapter = None

        if not self.disable_storage:
            self._load_persistent_devices()

    async def scan_for_devices(
        self,
        duration: int = 10,
        disable_storage: bool | None = None,
        *,
        scan_until_new_device: bool = False,
        short_timeout: int | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Scan for BLE devices and update discovered_devices.

        Args:
            duration: Scan duration in seconds
            disable_storage: If provided, overrides the instance setting for this scan
            scan_until_new_device: If True, stop scanning when a new device is found
            short_timeout: Timeout for individual scans when using scan_until_new_device
                          (defaults to max of 5 seconds or 10% of duration)

        Returns:
            Dictionary of discovered devices keyed by MAC address
        """
        if BleakScanner is None:
            self.logger.error("Bleak library is not installed.")
            return {}

        # Use provided disable_storage or fall back to instance setting
        should_disable_storage = (
            disable_storage if disable_storage is not None else self.disable_storage
        )

        try:
            if scan_until_new_device:
                return await self._scan_until_new_device(
                    duration,
                    short_timeout,
                    should_disable_storage,
                )
            return await self._scan_full_duration(duration, should_disable_storage)
        except Exception:
            self.logger.exception("BLE scan failed")
            return {}

    async def _scan_full_duration(
        self,
        duration: int,
        disable_storage: bool,
    ) -> dict[str, dict[str, Any]]:
        """Scan for the full duration using a single BleakScanner.discover call."""
        # Use return_adv=True to get advertisement data along with device info
        if BleakScanner is None:
            self.logger.error("Bleak library is not installed.")
            return {}

        # Use semaphore to coordinate BLE scanning operations
        scan_semaphore = get_ble_scan_semaphore()
        async with scan_semaphore:
            self.logger.debug("Acquired BLE scan semaphore for device discovery")
            if getattr(self, "adapter", None):
                try:
                    devices = await BleakScanner.discover(
                        timeout=duration,
                        return_adv=True,
                        adapter=self.adapter,  # type: ignore[call-arg]
                    )
                except TypeError:
                    devices = await BleakScanner.discover(
                        timeout=duration,
                        return_adv=True,
                    )
            else:
                devices = await BleakScanner.discover(timeout=duration, return_adv=True)

        # Log how many items were returned from the scanner
        self.logger.debug(
            "Device discovery returned %d item(s)",
            len(devices) if hasattr(devices, "__len__") else -1,
        )

        # Handle the return format: dict values are (device, advertisement_data) tuples
        matched = 0
        for device, advertisement_data in devices.values():
            # Compose a name from device.name or advertised local_name
            name = (
                getattr(device, "name", None)
                or getattr(advertisement_data, "local_name", None)
                or ""
            )

            if hasattr(device, "address") and self._is_potential_battery_monitor_name(
                name,
            ):
                # Extract RSSI, handling MagicMock objects
                rssi = getattr(advertisement_data, "rssi", None)
                if hasattr(rssi, "_mock_name") or hasattr(rssi, "_mock_return_value"):
                    rssi = None  # MagicMock object, use None instead

                device_data = {
                    "mac_address": device.address,  # type: ignore[reportAttributeAccessIssue]
                    "name": name or "Unknown",
                    "rssi": rssi,
                    "discovered_at": datetime.now(UTC).isoformat(),
                    "metadata": self._extract_metadata(device),
                    "advertisement_data": self._extract_advertisement_data(
                        advertisement_data,
                    ),
                }
                self.discovered_devices[device.address] = device_data  # type: ignore[reportAttributeAccessIssue]
                matched += 1

        self.logger.debug("Matched %d potential battery monitor(s)", matched)

        # Only save to storage if not disabled
        if not disable_storage:
            self._save_persistent_devices()

        return self.discovered_devices

    async def _scan_until_new_device(
        self,
        duration: int,
        short_timeout: int | None,
        disable_storage: bool,
    ) -> dict[str, dict[str, Any]]:
        """Scan until a new device is found or duration is exhausted."""
        # Calculate short timeout: max of 5 seconds or 10% of duration
        if short_timeout is None:
            short_timeout = max(5, int(duration * 0.1))

        start_time = asyncio.get_event_loop().time()
        devices_before_scan = set(self.discovered_devices.keys())

        while (asyncio.get_event_loop().time() - start_time) < duration:
            # Do a short scan
            if BleakScanner is None:
                self.logger.error("Bleak library is not installed.")
                return {}

            # Use semaphore to coordinate BLE scanning operations
            scan_semaphore = get_ble_scan_semaphore()
            async with scan_semaphore:
                self.logger.debug(
                    "Acquired BLE scan semaphore for short discovery scan",
                )
                if getattr(self, "adapter", None):
                    try:
                        devices = await BleakScanner.discover(
                            timeout=short_timeout,
                            return_adv=True,
                            adapter=self.adapter,  # type: ignore[call-arg]
                        )
                    except TypeError:
                        devices = await BleakScanner.discover(
                            timeout=short_timeout,
                            return_adv=True,
                        )
                else:
                    devices = await BleakScanner.discover(
                        timeout=short_timeout,
                        return_adv=True,
                    )

            # Debug counts from this short scan
            self.logger.debug(
                "Short scan returned %d item(s)",
                len(devices) if hasattr(devices, "__len__") else -1,
            )

            # Check if any new devices were found
            new_devices_found = False
            matched = 0
            for device, advertisement_data in devices.values():
                # Compose a name from device.name or advertised local_name
                name = (
                    getattr(device, "name", None)
                    or getattr(advertisement_data, "local_name", None)
                    or ""
                )

                if hasattr(
                    device,
                    "address",
                ) and self._is_potential_battery_monitor_name(name):
                    device_address = device.address  # type: ignore[reportAttributeAccessIssue]

                    # Check if this is a new device
                    if device_address not in devices_before_scan:
                        new_devices_found = True

                    matched += 1

                    # Extract RSSI, handling MagicMock objects
                    rssi = getattr(advertisement_data, "rssi", None)
                    if hasattr(rssi, "_mock_name") or hasattr(
                        rssi,
                        "_mock_return_value",
                    ):
                        rssi = None  # MagicMock object, use None instead

                    device_data = {
                        "mac_address": device_address,
                        "name": name or "Unknown",
                        "rssi": rssi,
                        "discovered_at": datetime.now(UTC).isoformat(),
                        "metadata": self._extract_metadata(device),
                        "advertisement_data": self._extract_advertisement_data(
                            advertisement_data,
                        ),
                    }
                    self.discovered_devices[device_address] = device_data

            self.logger.debug("Short scan matched %d potential device(s)", matched)

            # If new devices found, stop scanning
            if new_devices_found:
                self.logger.info("New device found, stopping scan early")
                break

            # Small delay to prevent excessive CPU usage
            await asyncio.sleep(0.1)

        # Only save to storage if not disabled
        if not disable_storage:
            self._save_persistent_devices()

        return self.discovered_devices

    def _is_potential_battery_monitor(self, device: object) -> bool:
        """Use name-based heuristic; kept for backward compatibility."""
        device_name = getattr(device, "name", None) or ""
        return self._is_potential_battery_monitor_name(device_name)

    def _is_potential_battery_monitor_name(self, name: str) -> bool:
        """Return True if name suggests a supported battery monitor (e.g., BM6, BM2)."""
        return "BM" in (name or "").upper()

    def _extract_metadata(self, device: object) -> dict[str, Any]:
        """Extract additional metadata from a Bleak device."""
        return {
            "details": str(device),
        }

    def _extract_advertisement_data(
        self,
        advertisement_data: object,
    ) -> dict[str, Any]:
        """Extract advertisement data from Bleak advertisement object."""
        if advertisement_data is None:
            return {}

        try:
            adv_data: dict[str, Any] = {}

            # Service UUIDs
            if (
                hasattr(advertisement_data, "service_uuids")
                and advertisement_data.service_uuids  # type: ignore[reportAttributeAccessIssue]
            ):
                adv_data["service_uuids"] = list(advertisement_data.service_uuids)  # type: ignore[reportAttributeAccessIssue]

            # Manufacturer data
            if (
                hasattr(advertisement_data, "manufacturer_data")
                and advertisement_data.manufacturer_data  # type: ignore[reportAttributeAccessIssue]
            ):
                manufacturer_data = {}
                for company_id, data in advertisement_data.manufacturer_data.items():  # type: ignore[reportAttributeAccessIssue]
                    # Convert bytes to hex string for JSON serialization
                    manufacturer_data[str(company_id)] = (
                        data.hex() if isinstance(data, bytes) else str(data)
                    )
                adv_data["manufacturer_data"] = manufacturer_data

            # Service data
            if (
                hasattr(advertisement_data, "service_data")
                and advertisement_data.service_data  # type: ignore[reportAttributeAccessIssue]
            ):
                service_data = {}
                for service_uuid, data in advertisement_data.service_data.items():  # type: ignore[reportAttributeAccessIssue]
                    # Convert bytes to hex string for JSON serialization
                    service_data[str(service_uuid)] = (
                        data.hex() if isinstance(data, bytes) else str(data)
                    )
                adv_data["service_data"] = service_data

            # Local name
            if (
                hasattr(advertisement_data, "local_name")
                and advertisement_data.local_name  # type: ignore[reportAttributeAccessIssue]
            ):
                adv_data["local_name"] = advertisement_data.local_name  # type: ignore[reportAttributeAccessIssue]

            # TX power
            if (
                hasattr(advertisement_data, "tx_power")
                and advertisement_data.tx_power is not None  # type: ignore[reportAttributeAccessIssue]
            ):
                adv_data["tx_power"] = advertisement_data.tx_power  # type: ignore[reportAttributeAccessIssue]

            # Platform-specific data
            if (
                hasattr(advertisement_data, "platform_data")
                and advertisement_data.platform_data  # type: ignore[reportAttributeAccessIssue]
            ):
                platform_data = advertisement_data.platform_data  # type: ignore[reportAttributeAccessIssue]
                # Handle MagicMock objects and other non-serializable objects
                if hasattr(platform_data, "_mock_name") or hasattr(
                    platform_data,
                    "_mock_return_value",
                ):
                    # This is a MagicMock object, skip it
                    pass
                else:
                    adv_data["platform_data"] = str(platform_data)

        except (AttributeError, TypeError, ValueError) as e:
            self.logger.warning("Failed to extract advertisement data: %s", e)
            return {"error": str(e)}
        else:
            return adv_data

    def get_discovered_devices(self) -> dict[str, dict[str, Any]]:
        """Return all discovered devices."""
        return self.discovered_devices

    def get_device(self, mac_address: str) -> dict[str, Any] | None:
        """Return metadata for a specific discovered device."""
        return self.discovered_devices.get(mac_address)

    def _save_persistent_devices(self) -> None:
        """Save discovered devices to persistent storage."""
        try:
            with open(self.storage_path, "w") as f:
                json.dump(self.discovered_devices, f, indent=2)
        except Exception:
            self.logger.exception("Failed to save discovered devices")

    def _load_persistent_devices(self) -> None:
        """Load discovered devices from persistent storage."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path) as f:
                    self.discovered_devices = json.load(f)
            except Exception:
                self.logger.exception("Failed to load discovered devices")
