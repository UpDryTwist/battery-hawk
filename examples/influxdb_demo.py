#!/usr/bin/env python3
"""
InfluxDB Storage Demo for Battery Hawk.

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
import shutil
import sys
import tempfile
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from battery_hawk.config.config_manager import ConfigManager
from battery_hawk.core.storage import DataStorage


def setup_influxdb_demo() -> tuple[str, logging.Logger]:
    """Set up the InfluxDB demo environment."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("influxdb_demo")

    logger.info("Starting InfluxDB Storage Demo")

    # Create a temporary config directory for demo
    config_dir = tempfile.mkdtemp(prefix="battery_hawk_demo_")
    os.makedirs(config_dir, exist_ok=True)

    return config_dir, logger


async def test_influxdb_connection(
    storage: DataStorage,
    logger: logging.Logger,
) -> bool:
    """Test InfluxDB connection and health."""
    # Test connection
    logger.info("Attempting to connect to InfluxDB...")
    connected = await storage.connect()

    if connected:
        logger.info("✅ Successfully connected to InfluxDB")
    else:
        logger.warning("❌ Failed to connect to InfluxDB")
        logger.info("This is expected if InfluxDB is not running")
        logger.info("Set BATTERYHAWK_INFLUXDB_ENABLED=false to test disabled mode")
        return False

    # Test health check
    logger.info("Performing health check...")
    healthy = await storage.health_check()
    logger.info(
        "Health check result: %s",
        "✅ Healthy" if healthy else "❌ Unhealthy",
    )
    return True


async def demo_data_operations(storage: DataStorage, logger: logging.Logger) -> None:
    """Demonstrate data storage and retrieval operations."""
    # Store sample readings
    logger.info("\n%s", "=" * 50)
    logger.info("Storing Sample Battery Readings")
    logger.info("%s", "=" * 50)

    sample_readings = [
        {
            "device_id": "AA:BB:CC:DD:EE:01",
            "vehicle_id": "demo_vehicle_1",
            "device_type": "BM6",
            "data": {"voltage": 12.6, "current": 2.5, "temperature": 22.0},
        },
        {
            "device_id": "AA:BB:CC:DD:EE:02",
            "vehicle_id": "demo_vehicle_1",
            "device_type": "BM6",
            "data": {"voltage": 12.4, "current": 1.8, "temperature": 21.5},
        },
        {
            "device_id": "AA:BB:CC:DD:EE:01",
            "vehicle_id": "demo_vehicle_2",
            "device_type": "BM6",
            "data": {"voltage": 12.5, "current": 2.3, "temperature": 23.0},
        },
    ]

    for i, reading in enumerate(sample_readings):
        success = await storage.store_reading(
            reading["device_id"],
            reading["vehicle_id"],
            reading["device_type"],
            reading["data"],
        )
        if success:
            logger.info("✅ Stored reading %d/%d", i + 1, len(sample_readings))
        else:
            logger.error(
                "❌ Failed to store reading %d/%d",
                i + 1,
                len(sample_readings),
            )

    # Query recent readings
    logger.info("\n%s", "=" * 50)
    logger.info("Querying Recent Readings")
    logger.info("%s", "=" * 50)

    for device_id in ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"]:
        readings = await storage.get_recent_readings(device_id, limit=5)
        logger.info("Retrieved %d readings for device %s", len(readings), device_id)

        for reading in readings:
            logger.info(
                "  - %s: V=%sV, I=%sA, T=%s°C",
                reading.get("time", "N/A"),
                reading.get("voltage", "N/A"),
                reading.get("current", "N/A"),
                reading.get("temperature", "N/A"),
            )

    # Get vehicle summary
    logger.info("\n%s", "=" * 50)
    logger.info("Vehicle Summary")
    logger.info("%s", "=" * 50)

    summary = await storage.get_vehicle_summary("demo_vehicle_1", hours=1)
    logger.info("Vehicle summary for last 1 hour:")
    logger.info("  - Average voltage: %.2fV", summary["avg_voltage"])
    logger.info("  - Average current: %.2fA", summary["avg_current"])
    logger.info("  - Average temperature: %.1f°C", summary["avg_temperature"])
    logger.info("  - Reading count: %d", summary["reading_count"])


async def demo_influxdb_storage() -> None:
    """Demonstrate InfluxDB storage functionality."""
    config_dir, logger = setup_influxdb_demo()

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

        # Test connection and health
        if not await test_influxdb_connection(storage, logger):
            return

        # Demonstrate data operations
        await demo_data_operations(storage, logger)

        # Test disconnection
        logger.info("Disconnecting from InfluxDB...")
        await storage.disconnect()
        logger.info("✅ Disconnected successfully")

    except Exception:
        logger.exception("Demo failed with error")
    finally:
        # Cleanup
        try:
            shutil.rmtree(config_dir, ignore_errors=True)
            logger.info("Cleaned up temporary files")
        except OSError as cleanup_error:
            logger.warning("Failed to cleanup temporary files: %s", cleanup_error)

    logger.info("InfluxDB Storage Demo completed")


async def demo_disabled_mode() -> None:
    """Demonstrate storage behavior when InfluxDB is disabled."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("influxdb_demo_disabled")

    logger.info("Starting InfluxDB Storage Demo (Disabled Mode)")

    # Create a temporary config directory for demo
    config_dir = tempfile.mkdtemp(prefix="battery_hawk_demo_disabled_")
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
        logger.info(
            "Connection result: %s (connected=%s)",
            connected,
            storage.connected,
        )

        # Test storing reading (should be dropped)
        success = await storage.store_reading(
            "AA:BB:CC:DD:EE:FF",
            "test_vehicle",
            "BM6",
            {"voltage": 12.5, "current": 2.0},
        )
        logger.info("Store reading result: %s (reading was dropped)", success)

        # Test querying (should return empty)
        readings = await storage.get_recent_readings("AA:BB:CC:DD:EE:FF")
        logger.info("Query result: %d readings (empty as expected)", len(readings))

    except Exception:
        logger.exception("Demo failed with error")
    finally:
        # Cleanup
        try:
            shutil.rmtree(config_dir, ignore_errors=True)
        except OSError as cleanup_error:
            logger.warning("Failed to cleanup temporary files: %s", cleanup_error)

    logger.info("InfluxDB Storage Demo (Disabled Mode) completed")


if __name__ == "__main__":
    # Check if InfluxDB should be disabled via environment variable
    if os.getenv("BATTERYHAWK_INFLUXDB_ENABLED", "").lower() == "false":
        asyncio.run(demo_disabled_mode())
    else:
        asyncio.run(demo_influxdb_storage())
