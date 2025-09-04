#!/usr/bin/env python3
"""
Example demonstrating the MQTT publisher functionality.

This script shows how to use the MQTTPublisher class to publish different
types of Battery Hawk data to MQTT topics.
"""

import asyncio
import logging
from datetime import datetime, timezone

from battery_hawk.config.config_manager import ConfigManager
from battery_hawk.mqtt import MQTTInterface, MQTTPublisher
from battery_hawk_driver.base.protocol import BatteryInfo, DeviceStatus


async def main() -> None:
    """Demonstrate MQTT publisher functionality."""
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Initialize configuration manager
    config_manager = ConfigManager()

    # Create MQTT interface and publisher
    mqtt_interface = MQTTInterface(config_manager)
    publisher = MQTTPublisher(mqtt_interface)

    try:
        # Connect to MQTT broker
        logger.info("Connecting to MQTT broker...")
        await mqtt_interface.connect()
        logger.info("Connected successfully!")

        # Example 1: Publish device reading
        logger.info("Publishing device reading...")
        device_id = "AA:BB:CC:DD:EE:FF"
        reading = BatteryInfo(
            voltage=12.6,
            current=2.5,
            temperature=25.0,
            state_of_charge=85.0,
            capacity=100.0,
            cycles=150,
            timestamp=datetime.now(timezone.utc).timestamp(),
        )

        await publisher.publish_device_reading(
            device_id=device_id,
            reading=reading,
            vehicle_id="my_vehicle",
            device_type="BM2",
        )
        logger.info("Device reading published to: devices/%s/readings", device_id)

        # Example 2: Publish device status (connected)
        logger.info("Publishing device status (connected)...")
        status = DeviceStatus(
            connected=True,
            protocol_version="1.0",
            last_command="read_data",
        )

        await publisher.publish_device_status(
            device_id=device_id,
            status=status,
            device_type="BM2",
        )
        logger.info("Device status published to: devices/%s/status", device_id)

        # Example 3: Publish device status (disconnected with error)
        logger.info("Publishing device status (disconnected)...")
        error_status = DeviceStatus(
            connected=False,
            error_code=1001,
            error_message="Connection timeout after 30 seconds",
        )

        await publisher.publish_device_status(
            device_id=device_id,
            status=error_status,
            device_type="BM2",
        )
        logger.info("Device error status published")

        # Example 4: Publish vehicle summary
        logger.info("Publishing vehicle summary...")
        vehicle_summary = {
            "total_devices": 3,
            "connected_devices": 2,
            "disconnected_devices": 1,
            "average_voltage": 12.4,
            "total_capacity": 300.0,
            "average_soc": 78.5,
            "overall_health": "good",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "devices": [
                {
                    "id": "AA:BB:CC:DD:EE:FF",
                    "status": "connected",
                    "voltage": 12.6,
                    "soc": 85.0,
                },
                {
                    "id": "11:22:33:44:55:66",
                    "status": "connected",
                    "voltage": 12.2,
                    "soc": 72.0,
                },
                {
                    "id": "77:88:99:AA:BB:CC",
                    "status": "disconnected",
                    "last_seen": "2024-01-15T10:30:00Z",
                },
            ],
        }

        await publisher.publish_vehicle_summary("my_vehicle", vehicle_summary)
        logger.info("Vehicle summary published to: vehicles/my_vehicle/summary")

        # Example 5: Publish system status
        logger.info("Publishing system status...")
        system_status = {
            "core": {
                "running": True,
                "uptime_seconds": 3600,
                "version": "1.0.0",
                "memory_usage_mb": 128.5,
                "cpu_usage_percent": 15.2,
            },
            "storage": {
                "influxdb_connected": True,
                "disk_usage_percent": 45.2,
                "database_size_mb": 1024.0,
                "retention_policy": "30d",
            },
            "components": {
                "mqtt": "connected",
                "bluetooth": "active",
                "api": "running",
                "discovery": "idle",
            },
            "statistics": {
                "total_devices": 5,
                "active_connections": 3,
                "messages_published": 1250,
                "errors_last_hour": 2,
            },
        }

        await publisher.publish_system_status(system_status)
        logger.info("System status published to: system/status")

        # Wait a moment for messages to be sent
        await asyncio.sleep(1)
        logger.info("All messages published successfully!")

    except Exception:
        logger.exception("Error during MQTT publishing")
        raise
    finally:
        # Disconnect from MQTT broker
        logger.info("Disconnecting from MQTT broker...")
        await mqtt_interface.disconnect()
        logger.info("Disconnected.")


if __name__ == "__main__":
    asyncio.run(main())
