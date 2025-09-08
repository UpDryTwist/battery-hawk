#!/usr/bin/env python3
"""
Example demonstrating automatic device configuration functionality.

This script shows how to use the auto-configuration service to automatically
configure discovered BLE battery monitoring devices.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the src directory to the path so we can import battery_hawk modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from battery_hawk.config.config_manager import ConfigManager
from battery_hawk.core.auto_config import AutoConfigurationService
from battery_hawk.core.auto_config_rules import AutoConfigurationRulesEngine
from battery_hawk.core.registry import DeviceRegistry
from battery_hawk_driver.base.connection import BLEConnectionPool
from battery_hawk_driver.base.device_factory import DeviceFactory
from battery_hawk_driver.base.discovery import BLEDiscoveryService


async def main() -> int:
    """Main example function."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    logger.info("Starting auto-configuration example")

    try:
        # Initialize configuration manager with local config directory
        config_dir = Path(__file__).parent.parent / "local-instance" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_manager = ConfigManager(str(config_dir))

        # Enable auto-configuration
        system_config = config_manager.get_config("system")
        system_config["discovery"]["auto_configure"]["enabled"] = True
        config_manager.save_config("system")

        logger.info("Auto-configuration enabled")

        # Initialize components
        connection_pool = BLEConnectionPool(config_manager, test_mode=True)
        device_factory = DeviceFactory(connection_pool)
        auto_config_service = AutoConfigurationService(config_manager, device_factory)
        device_registry = DeviceRegistry(config_manager, auto_config_service)
        discovery_service = BLEDiscoveryService(config_manager)

        # Check auto-configuration status
        logger.info("Auto-configuration status:")
        logger.info("  Enabled: %s", auto_config_service.is_enabled())
        logger.info(
            "  Confidence threshold: %.2f",
            auto_config_service.get_confidence_threshold(),
        )

        # Simulate discovered devices
        sample_devices = {
            "50:54:7B:81:33:39": {
                "mac_address": "50:54:7B:81:33:39",
                "name": "BM6",
                "rssi": -36,
                "discovered_at": "2025-09-06T18:33:40.434205+00:00",
                "status": "discovered",
                "advertisement_data": {
                    "local_name": "BM6",
                    "service_uuids": ["0000fff0-0000-1000-8000-00805f9b34fb"],
                    "manufacturer_data": {"3218": "0071cf9a5094ca58ad4da17bc6e1"},
                },
            },
            "50:54:7B:81:33:40": {
                "mac_address": "50:54:7B:81:33:40",
                "name": "BM2",
                "rssi": -45,
                "discovered_at": "2025-09-06T18:33:45.434205+00:00",
                "status": "discovered",
                "advertisement_data": {
                    "local_name": "BM2",
                    "service_uuids": ["0000fff0-0000-1000-8000-00805f9b34fb"],
                    "manufacturer_data": {"3218": "0071cf9a5094ca58ad4da17bc6e1"},
                },
            },
        }

        logger.info("Simulating discovery of %d devices", len(sample_devices))

        # Register discovered devices (this will trigger auto-configuration)
        await device_registry.register_discovered_devices(sample_devices)

        # Show configured devices
        configured_devices = device_registry.get_configured_devices()
        logger.info("Configured devices after auto-configuration:")
        for device in configured_devices:
            logger.info(
                "  %s: %s (%s) - %ds polling",
                device.get("mac_address"),
                device.get("friendly_name"),
                device.get("device_type"),
                device.get("polling_interval"),
            )

        # Demonstrate rules engine
        logger.info("\nDemonstrating rules engine:")
        rules_engine = AutoConfigurationRulesEngine(config_manager)

        for mac_address, device_info in sample_devices.items():
            advertisement_data = device_info.get("advertisement_data", {})
            detected_type = device_factory.auto_detect_device_type(advertisement_data)

            result = rules_engine.evaluate_device(
                mac_address,
                device_info,
                detected_type,
            )

            logger.info("Device %s:", mac_address)
            logger.info("  Detected type: %s", detected_type)
            logger.info("  Should configure: %s", result.should_configure)
            if result.should_configure:
                logger.info("  Suggested name: %s", result.friendly_name)
                logger.info("  Polling interval: %ds", result.polling_interval)
                logger.info("  Confidence: %.2f", result.confidence)
                logger.info("  Rule: %s", result.rule_name)

        # Demonstrate manual auto-configuration run
        logger.info("\nRunning manual auto-configuration (dry run):")

        # Add another device that wasn't auto-configured
        new_device = {
            "50:54:7B:81:33:41": {
                "mac_address": "50:54:7B:81:33:41",
                "name": "Unknown Device",
                "rssi": -50,
                "discovered_at": "2025-09-06T18:34:00.434205+00:00",
                "status": "discovered",
                "advertisement_data": {
                    "local_name": "BM6",
                    "service_uuids": ["0000fff0-0000-1000-8000-00805f9b34fb"],
                },
            },
        }

        # Register without auto-configuration (simulate manual discovery)
        device_registry.devices.update(new_device)

        # Process for auto-configuration
        results = await auto_config_service.process_discovered_devices(
            new_device,
            device_registry,
        )

        logger.info("Auto-configuration results:")
        for mac_address, success in results.items():
            logger.info("  %s: %s", mac_address, "Configured" if success else "Skipped")

        logger.info("Auto-configuration example completed successfully")

    except Exception:
        logger.exception("Error in auto-configuration example")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
