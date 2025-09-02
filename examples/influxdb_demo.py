#!/usr/bin/env python3
"""
InfluxDB Storage Demo for Battery Hawk

This script demonstrates the InfluxDB client functionality including:
- Connection handling with AsyncIO support
- Database creation and error management
- Storing battery readings
- Querying recent readings
- Health checks and disconnection

Usage:
    python examples/influxdb_demo.py

Requirements:
    - InfluxDB server running on localhost:8086
    - Or set BATTERYHAWK_INFLUXDB_ENABLED=false to run in disabled mode
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from battery_hawk.config.config_manager import ConfigManager
from battery_hawk.core.storage import DataStorage


async def demo_influxdb_storage():
    """Demonstrate InfluxDB storage functionality."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger("influxdb_demo")

    logger.info("Starting InfluxDB Storage Demo")

    # Create a temporary config directory for demo
    config_dir = "/tmp/battery_hawk_demo"
    os.makedirs(config_dir, exist_ok=True)

    try:
        # Initialize configuration manager
        config_manager = ConfigManager(config_dir)
        
        # Enable InfluxDB in configuration (can be overridden by env vars)
        system_config = config_manager.get_config("system")
        system_config["influxdb"]["enabled"] = True
        config_manager.save_config("system")
        
        logger.info("Configuration initialized")

        # Create DataStorage instance
        storage = DataStorage(config_manager)
        logger.info("DataStorage instance created")

        # Test connection
        logger.info("Attempting to connect to InfluxDB...")
        connected = await storage.connect()
        
        if connected:
            logger.info("✅ Successfully connected to InfluxDB")
        else:
            logger.warning("❌ Failed to connect to InfluxDB")
            logger.info("This is expected if InfluxDB is not running")
            logger.info("Set BATTERYHAWK_INFLUXDB_ENABLED=false to test disabled mode")
            return

        # Test health check
        logger.info("Performing health check...")
        healthy = await storage.health_check()
        logger.info(f"Health check result: {'✅ Healthy' if healthy else '❌ Unhealthy'}")

        if not healthy:
            logger.warning("Storage is not healthy, skipping data operations")
            return

        # Test storing battery readings
        logger.info("Storing sample battery readings...")
        
        sample_readings = [
            {
                "device_id": "AA:BB:CC:DD:EE:01",
                "vehicle_id": "demo_vehicle_1",
                "device_type": "BM6",
                "reading": {
                    "voltage": 12.6,
                    "current": 2.5,
                    "temperature": 22.0,
                    "state_of_charge": 85.0,
                }
            },
            {
                "device_id": "AA:BB:CC:DD:EE:02", 
                "vehicle_id": "demo_vehicle_1",
                "device_type": "BM2",
                "reading": {
                    "voltage": 12.4,
                    "current": 1.8,
                    "temperature": 24.0,
                    "state_of_charge": 78.0,
                }
            },
            {
                "device_id": "AA:BB:CC:DD:EE:01",
                "vehicle_id": "demo_vehicle_1", 
                "device_type": "BM6",
                "reading": {
                    "voltage": 12.5,
                    "current": 2.3,
                    "temperature": 23.0,
                    "state_of_charge": 83.0,
                }
            }
        ]

        for i, sample in enumerate(sample_readings):
            success = await storage.store_reading(
                sample["device_id"],
                sample["vehicle_id"],
                sample["device_type"],
                sample["reading"]
            )
            if success:
                logger.info(f"✅ Stored reading {i+1}/{len(sample_readings)}")
            else:
                logger.error(f"❌ Failed to store reading {i+1}/{len(sample_readings)}")
            
            # Small delay between writes
            await asyncio.sleep(0.1)

        # Test querying recent readings
        logger.info("Querying recent readings...")
        
        for device_id in ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"]:
            readings = await storage.get_recent_readings(device_id, limit=5)
            logger.info(f"Retrieved {len(readings)} readings for device {device_id}")
            
            for reading in readings:
                logger.info(f"  - {reading.get('time', 'N/A')}: "
                          f"V={reading.get('voltage', 'N/A')}V, "
                          f"I={reading.get('current', 'N/A')}A, "
                          f"T={reading.get('temperature', 'N/A')}°C")

        # Test vehicle summary
        logger.info("Getting vehicle summary...")
        summary = await storage.get_vehicle_summary("demo_vehicle_1", hours=1)
        logger.info(f"Vehicle summary for last 1 hour:")
        logger.info(f"  - Average voltage: {summary['avg_voltage']:.2f}V")
        logger.info(f"  - Average current: {summary['avg_current']:.2f}A") 
        logger.info(f"  - Average temperature: {summary['avg_temperature']:.1f}°C")
        logger.info(f"  - Reading count: {summary['reading_count']}")

        # Test disconnection
        logger.info("Disconnecting from InfluxDB...")
        await storage.disconnect()
        logger.info("✅ Disconnected successfully")

    except Exception as e:
        logger.exception(f"Demo failed with error: {e}")
    finally:
        # Cleanup
        try:
            import shutil
            shutil.rmtree(config_dir, ignore_errors=True)
            logger.info("Cleaned up temporary files")
        except Exception:
            pass

    logger.info("InfluxDB Storage Demo completed")


async def demo_disabled_mode():
    """Demonstrate storage behavior when InfluxDB is disabled."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger("influxdb_demo_disabled")

    logger.info("Starting InfluxDB Storage Demo (Disabled Mode)")

    # Create a temporary config directory for demo
    config_dir = "/tmp/battery_hawk_demo_disabled"
    os.makedirs(config_dir, exist_ok=True)

    try:
        # Initialize configuration manager with InfluxDB disabled
        config_manager = ConfigManager(config_dir)
        system_config = config_manager.get_config("system")
        system_config["influxdb"]["enabled"] = False
        config_manager.save_config("system")

        # Create DataStorage instance
        storage = DataStorage(config_manager)
        logger.info("DataStorage instance created (InfluxDB disabled)")

        # Test connection (should succeed but not actually connect)
        connected = await storage.connect()
        logger.info(f"Connection result: {connected} (connected={storage.connected})")

        # Test storing reading (should be dropped)
        success = await storage.store_reading(
            "AA:BB:CC:DD:EE:FF",
            "test_vehicle",
            "BM6",
            {"voltage": 12.5, "current": 2.0}
        )
        logger.info(f"Store reading result: {success} (reading was dropped)")

        # Test querying (should return empty)
        readings = await storage.get_recent_readings("AA:BB:CC:DD:EE:FF")
        logger.info(f"Query result: {len(readings)} readings (empty as expected)")

    except Exception as e:
        logger.exception(f"Demo failed with error: {e}")
    finally:
        # Cleanup
        try:
            import shutil
            shutil.rmtree(config_dir, ignore_errors=True)
        except Exception:
            pass

    logger.info("InfluxDB Storage Demo (Disabled Mode) completed")


if __name__ == "__main__":
    # Check if InfluxDB should be disabled via environment variable
    if os.getenv("BATTERYHAWK_INFLUXDB_ENABLED", "").lower() == "false":
        asyncio.run(demo_disabled_mode())
    else:
        asyncio.run(demo_influxdb_storage())
