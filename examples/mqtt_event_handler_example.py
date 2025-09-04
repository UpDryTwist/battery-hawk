#!/usr/bin/env python3
"""
Example demonstrating the MQTT event handler system.

This script shows how to set up the event handler registration system
to automatically publish MQTT messages when core engine events occur.
"""

import asyncio
import logging
from datetime import datetime

from battery_hawk.config.config_manager import ConfigManager
from battery_hawk.core.engine import BatteryHawkCore
from battery_hawk.mqtt import MQTTEventHandler, MQTTInterface, MQTTPublisher
from battery_hawk_driver.base.protocol import BatteryInfo, DeviceStatus


async def main() -> None:
    """Demonstrate MQTT event handler system."""
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Initialize configuration manager
    config_manager = ConfigManager()

    # Create core engine (normally this would be done in the main application)
    core_engine = BatteryHawkCore(config_manager)

    # Create MQTT components
    mqtt_interface = MQTTInterface(config_manager)
    publisher = MQTTPublisher(mqtt_interface)
    event_handler = MQTTEventHandler(core_engine, publisher)

    try:
        # Connect to MQTT broker
        logger.info("Connecting to MQTT broker...")
        await mqtt_interface.connect()
        logger.info("Connected successfully!")

        # Register all event handlers with the core engine
        logger.info("Registering MQTT event handlers...")
        event_handler.register_all_handlers()
        logger.info("Event handlers registered!")

        # Simulate some core engine events to demonstrate the system
        logger.info("Simulating core engine events...")

        # 1. Simulate device discovery event
        logger.info("Simulating device discovery...")
        discovery_event = {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "device_type": "BM2",
            "name": "Test Battery Monitor",
            "rssi": -45,
            "advertisement_data": {"manufacturer": "test"},
        }
        await event_handler.on_device_discovered(discovery_event)
        logger.info("Device discovery event processed")

        # 2. Simulate device reading update
        logger.info("Simulating device reading update...")
        from battery_hawk.core.state import DeviceState

        device_state = DeviceState("AA:BB:CC:DD:EE:FF", "BM2")
        device_state.vehicle_id = "test_vehicle"

        reading = BatteryInfo(
            voltage=12.6,
            current=2.5,
            temperature=25.0,
            state_of_charge=85.0,
            capacity=100.0,
            cycles=150,
            timestamp=datetime.now().timestamp(),
        )
        device_state.update_reading(reading)

        await event_handler.on_device_reading("AA:BB:CC:DD:EE:FF", device_state, None)
        logger.info("Device reading event processed")

        # 3. Simulate device status change
        logger.info("Simulating device status change...")
        status = DeviceStatus(
            connected=True,
            protocol_version="1.0",
            last_command="read_data",
        )
        device_state.update_status(status)

        await event_handler.on_device_status_change(
            "AA:BB:CC:DD:EE:FF",
            device_state,
            None,
        )
        logger.info("Device status change event processed")

        # 4. Simulate vehicle association
        logger.info("Simulating vehicle association...")
        association_event = {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "vehicle_id": "test_vehicle",
            "device_type": "BM2",
            "new_vehicle": True,
        }
        await event_handler.on_vehicle_associated(association_event)
        logger.info("Vehicle association event processed")

        # 5. Simulate system status update
        logger.info("Simulating system status update...")
        system_status = {
            "core": {
                "running": True,
                "uptime_seconds": 3600,
                "version": "1.0.0",
                "memory_usage_mb": 128.5,
            },
            "storage": {
                "influxdb_connected": True,
                "disk_usage_percent": 45.2,
                "database_size_mb": 1024.0,
            },
            "components": {
                "mqtt": "connected",
                "bluetooth": "active",
                "api": "running",
                "discovery": "idle",
            },
            "statistics": {
                "total_devices": 1,
                "active_connections": 1,
                "messages_published": 5,
                "errors_last_hour": 0,
            },
        }
        await event_handler.on_system_status_change(system_status)
        logger.info("System status update event processed")

        # 6. Demonstrate periodic system status publishing
        logger.info("Setting up periodic system status publishing...")

        async def periodic_system_status():
            """Periodically publish system status updates."""
            while True:
                try:
                    # In a real application, this would get actual system status
                    current_status = {
                        "core": {
                            "running": True,
                            "uptime_seconds": 3660,  # Incremented
                            "version": "1.0.0",
                            "memory_usage_mb": 130.2,  # Slightly changed
                        },
                        "storage": {
                            "influxdb_connected": True,
                            "disk_usage_percent": 45.3,  # Slightly changed
                            "database_size_mb": 1025.0,  # Slightly changed
                        },
                        "components": {
                            "mqtt": "connected",
                            "bluetooth": "active",
                            "api": "running",
                            "discovery": "idle",
                        },
                        "statistics": {
                            "total_devices": 1,
                            "active_connections": 1,
                            "messages_published": 10,  # Incremented
                            "errors_last_hour": 0,
                        },
                    }

                    await event_handler.on_system_status_change(current_status)
                    logger.info("Periodic system status published")

                    # Wait 30 seconds before next update
                    await asyncio.sleep(30)

                except Exception as e:
                    logger.error("Error in periodic status update: %s", e)
                    await asyncio.sleep(30)

        # Start periodic status task
        status_task = asyncio.create_task(periodic_system_status())

        # Let the system run for a while to demonstrate periodic updates
        logger.info("Running system for 2 minutes to demonstrate periodic updates...")
        logger.info("Press Ctrl+C to stop")

        try:
            await asyncio.sleep(120)  # Run for 2 minutes
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")

        # Cancel the periodic task
        status_task.cancel()
        try:
            await status_task
        except asyncio.CancelledError:
            pass

        logger.info("All events processed successfully!")

    except Exception as e:
        logger.error("Error during MQTT event handling: %s", e)
        raise
    finally:
        # Unregister event handlers
        logger.info("Unregistering MQTT event handlers...")
        event_handler.unregister_all_handlers()

        # Disconnect from MQTT broker
        logger.info("Disconnecting from MQTT broker...")
        await mqtt_interface.disconnect()
        logger.info("Disconnected.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
