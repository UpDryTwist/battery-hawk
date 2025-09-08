"""Auto-configuration service for discovered devices."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from battery_hawk.config.config_manager import ConfigManager
    from battery_hawk_driver.base.device_factory import DeviceFactory


class AutoConfigurationService:
    """
    Service for automatically configuring discovered devices.

    This service monitors discovered devices and automatically configures them
    based on configurable rules and device detection patterns.
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        device_factory: DeviceFactory,
    ) -> None:
        """
        Initialize the auto-configuration service.

        Args:
            config_manager: Configuration manager instance
            device_factory: Device factory for auto-detection
        """
        self.config_manager = config_manager
        self.device_factory = device_factory
        self.logger = logging.getLogger(__name__)

    def is_enabled(self) -> bool:
        """
        Check if auto-configuration is enabled.

        Returns:
            True if auto-configuration is enabled (default: True)
        """
        discovery_config = self.config_manager.get_config("system").get("discovery", {})
        auto_config = discovery_config.get("auto_configure", {})
        return auto_config.get(
            "enabled",
            True,
        )  # Default to True to match default config

    def get_confidence_threshold(self) -> float:
        """
        Get the confidence threshold for auto-configuration.

        Returns:
            Confidence threshold (0.0 to 1.0)
        """
        discovery_config = self.config_manager.get_config("system").get("discovery", {})
        auto_config = discovery_config.get("auto_configure", {})
        return auto_config.get("confidence_threshold", 0.8)

    def should_auto_configure_device(
        self,
        mac_address: str,
        device_info: dict[str, Any],
        detected_type: str | None = None,
    ) -> bool:
        """
        Determine if a device should be auto-configured.

        Args:
            mac_address: MAC address of the device
            device_info: Device information from discovery
            detected_type: Auto-detected device type

        Returns:
            True if device should be auto-configured
        """
        if not self.is_enabled():
            self.logger.debug("Auto-configuration is disabled")
            return False

        if not detected_type:
            self.logger.debug(
                "No device type detected for %s, skipping auto-configuration",
                mac_address,
            )
            return False

        # Check if device type has auto-configuration rules
        discovery_config = self.config_manager.get_config("system").get("discovery", {})
        auto_config = discovery_config.get("auto_configure", {})
        rules = auto_config.get("rules", {})

        device_rules = rules.get(detected_type, {})
        if not device_rules.get("auto_configure", True):
            self.logger.debug(
                "Auto-configuration disabled for device type %s",
                detected_type,
            )
            return False

        # Check if device is already configured
        status = device_info.get("status", "discovered")
        if status == "configured":
            self.logger.debug(
                "Device %s is already configured, skipping auto-configuration",
                mac_address,
            )
            return False

        return True

    def generate_device_name(
        self,
        mac_address: str,
        device_type: str,
        device_info: dict[str, Any],
    ) -> str:
        """
        Generate a friendly name for the device.

        Args:
            mac_address: MAC address of the device
            device_type: Detected device type
            device_info: Device information from discovery

        Returns:
            Generated device name
        """
        discovery_config = self.config_manager.get_config("system").get("discovery", {})
        auto_config = discovery_config.get("auto_configure", {})

        if not auto_config.get("auto_assign_names", True):
            # Use device name from advertisement if available
            return device_info.get("name", f"Device_{mac_address}")

        rules = auto_config.get("rules", {})
        device_rules = rules.get(device_type, {})

        # Get name template
        name_template = device_rules.get(
            "default_name_template",
            f"{device_type} Device {{mac_suffix}}",
        )

        # Extract MAC suffix (last 4 characters)
        mac_suffix = mac_address.replace(":", "")[-4:].upper()

        # Format the template
        try:
            return name_template.format(
                mac_address=mac_address,
                mac_suffix=mac_suffix,
                device_type=device_type,
                original_name=device_info.get("name", "Unknown"),
            )
        except (KeyError, ValueError) as e:
            self.logger.warning(
                "Failed to format name template '%s': %s",
                name_template,
                e,
            )
            return f"{device_type} Device {mac_suffix}"

    def get_polling_interval(self, device_type: str) -> int:
        """
        Get the polling interval for a device type.

        Args:
            device_type: Device type

        Returns:
            Polling interval in seconds
        """
        discovery_config = self.config_manager.get_config("system").get("discovery", {})
        auto_config = discovery_config.get("auto_configure", {})
        rules = auto_config.get("rules", {})

        device_rules = rules.get(device_type, {})
        return device_rules.get(
            "polling_interval",
            auto_config.get("default_polling_interval", 3600),
        )

    async def auto_configure_device(
        self,
        mac_address: str,
        device_info: dict[str, Any],
        device_registry: Any,  # Avoid circular import
    ) -> bool:
        """
        Automatically configure a discovered device.

        Args:
            mac_address: MAC address of the device
            device_info: Device information from discovery
            device_registry: Device registry instance

        Returns:
            True if device was successfully auto-configured
        """
        try:
            # Auto-detect device type
            advertisement_data = device_info.get("advertisement_data", {})
            detected_type = self.device_factory.auto_detect_device_type(
                advertisement_data,
            )

            if not self.should_auto_configure_device(
                mac_address,
                device_info,
                detected_type,
            ):
                return False

            # Generate configuration
            friendly_name = self.generate_device_name(
                mac_address,
                detected_type or "Unknown",
                device_info,
            )
            polling_interval = self.get_polling_interval(detected_type or "Unknown")

            # Configure the device
            success = await device_registry.configure_device(
                mac_address=mac_address,
                device_type=detected_type,
                friendly_name=friendly_name,
                vehicle_id=None,  # No automatic vehicle assignment
                polling_interval=polling_interval,
            )

            if success:
                self.logger.info(
                    "Auto-configured device %s as %s (%s)",
                    mac_address,
                    detected_type,
                    friendly_name,
                )
                return True
            self.logger.warning(
                "Failed to auto-configure device %s",
                mac_address,
            )
            return False  # noqa: TRY300

        except Exception:
            self.logger.exception(
                "Error during auto-configuration of device %s",
                mac_address,
            )
            return False

    async def process_discovered_devices(
        self,
        discovered_devices: dict[str, dict[str, Any]],
        device_registry: Any,  # Avoid circular import
    ) -> dict[str, bool]:
        """
        Process a batch of discovered devices for auto-configuration.

        Args:
            discovered_devices: Dictionary of discovered devices
            device_registry: Device registry instance

        Returns:
            Dictionary mapping MAC addresses to configuration success status
        """
        results = {}

        if not self.is_enabled():
            self.logger.debug("Auto-configuration is disabled")
            return results

        for mac_address, device_info in discovered_devices.items():
            try:
                success = await self.auto_configure_device(
                    mac_address,
                    device_info,
                    device_registry,
                )
                results[mac_address] = success
            except Exception:  # noqa: PERF203
                self.logger.exception(
                    "Error processing device %s for auto-configuration",
                    mac_address,
                )
                results[mac_address] = False

        configured_count = sum(1 for success in results.values() if success)
        if configured_count > 0:
            self.logger.info(
                "Auto-configured %d out of %d discovered devices",
                configured_count,
                len(discovered_devices),
            )

        return results
