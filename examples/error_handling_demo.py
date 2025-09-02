#!/usr/bin/env python3
"""
InfluxDB Error Handling Demo for Battery Hawk

This script demonstrates the comprehensive error handling functionality including:
- Connection loss recovery with exponential backoff
- Write failure management and retry logic
- Data buffering during outages
- Automatic reconnection and buffer flushing
- Health monitoring and failure detection

Usage:
    python examples/error_handling_demo.py

Requirements:
    - InfluxDB server (can be started/stopped during demo to simulate outages)
    - Or run without InfluxDB to see buffering behavior
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
from battery_hawk.core.storage import InfluxDBStorageBackend


async def demo_error_handling():
    """Demonstrate InfluxDB error handling and recovery functionality."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("error_handling_demo")

    logger.info("Starting InfluxDB Error Handling Demo")

    # Create temporary config directory for demo
    temp_dir = tempfile.mkdtemp()
    config_dir = os.path.join(temp_dir, "config")
    os.makedirs(config_dir, exist_ok=True)

    try:
        # Initialize configuration manager
        config_manager = ConfigManager(config_dir)

        # Configure InfluxDB with aggressive error recovery settings for demo
        system_config = config_manager.get_config("system")
        system_config["influxdb"] = {
            "enabled": True,
            "host": "localhost",
            "port": 8086,
            "database": "battery_hawk_error_demo",
            "username": "",
            "password": "",
            "timeout": 5000,
            "retries": 3,
            "error_recovery": {
                "max_retry_attempts": 3,
                "retry_delay_seconds": 2.0,
                "retry_backoff_multiplier": 1.5,
                "max_retry_delay_seconds": 10.0,
                "buffer_max_size": 50,
                "buffer_flush_interval_seconds": 5.0,
                "connection_timeout_seconds": 5.0,
                "health_check_interval_seconds": 10.0,
            },
        }
        config_manager.save_config("system")

        logger.info("Configuration initialized with aggressive error recovery settings")

        # Create InfluxDB storage backend
        storage = InfluxDBStorageBackend(config_manager)
        logger.info("InfluxDB storage backend created")

        # Show initial connection state
        logger.info(f"Initial connection state: {storage._connection_state}")

        # Test 1: Initial connection attempt
        logger.info("\n" + "=" * 60)
        logger.info("Test 1: Initial Connection Attempt")
        logger.info("=" * 60)

        connected = await storage.connect()
        logger.info(f"Connection result: {connected}")
        logger.info(f"Connection state: {storage._connection_state}")
        logger.info(f"Connected: {storage.connected}")

        # Test 2: Store readings (will buffer if not connected)
        logger.info("\n" + "=" * 60)
        logger.info("Test 2: Storing Readings (with buffering if needed)")
        logger.info("=" * 60)

        test_readings = [
            {
                "device_id": "AA:BB:CC:DD:EE:01",
                "voltage": 12.6,
                "current": 2.5,
                "temperature": 22.0,
            },
            {
                "device_id": "AA:BB:CC:DD:EE:02",
                "voltage": 12.4,
                "current": 1.8,
                "temperature": 24.0,
            },
            {
                "device_id": "AA:BB:CC:DD:EE:03",
                "voltage": 12.5,
                "current": 2.3,
                "temperature": 23.0,
            },
            {
                "device_id": "AA:BB:CC:DD:EE:04",
                "voltage": 12.7,
                "current": 1.9,
                "temperature": 21.0,
            },
            {
                "device_id": "AA:BB:CC:DD:EE:05",
                "voltage": 12.3,
                "current": 2.1,
                "temperature": 25.0,
            },
        ]

        for i, reading_data in enumerate(test_readings):
            success = await storage.store_reading(
                reading_data["device_id"],
                "demo_vehicle_1",
                "BM6",
                {k: v for k, v in reading_data.items() if k != "device_id"},
            )

            status = "✅ Success" if success else "❌ Failed"
            logger.info(
                f"Reading {i + 1}: {status} - Device: {reading_data['device_id']}",
            )

            # Small delay between writes
            await asyncio.sleep(0.5)

        # Show buffer status
        buffer_size = len(storage._reading_buffer)
        logger.info(f"Buffer status: {buffer_size} readings buffered")

        # Test 3: Show error recovery configuration
        logger.info("\n" + "=" * 60)
        logger.info("Test 3: Error Recovery Configuration")
        logger.info("=" * 60)

        config = storage._error_recovery_config
        logger.info(f"Max retry attempts: {config.max_retry_attempts}")
        logger.info(f"Retry delay: {config.retry_delay_seconds}s")
        logger.info(f"Backoff multiplier: {config.retry_backoff_multiplier}")
        logger.info(f"Max retry delay: {config.max_retry_delay_seconds}s")
        logger.info(f"Buffer max size: {config.buffer_max_size}")
        logger.info(f"Buffer flush interval: {config.buffer_flush_interval_seconds}s")
        logger.info(f"Connection timeout: {config.connection_timeout_seconds}s")
        logger.info(f"Health check interval: {config.health_check_interval_seconds}s")

        # Test 4: Demonstrate retry delay calculation
        logger.info("\n" + "=" * 60)
        logger.info("Test 4: Retry Delay Calculation (Exponential Backoff)")
        logger.info("=" * 60)

        for retry_count in range(5):
            delay = storage._calculate_retry_delay(retry_count)
            logger.info(f"Retry {retry_count}: delay = {delay:.2f}s")

        # Test 5: Connection error detection
        logger.info("\n" + "=" * 60)
        logger.info("Test 5: Connection Error Detection")
        logger.info("=" * 60)

        test_errors = [
            ConnectionError("Connection refused"),
            TimeoutError("Operation timed out"),
            Exception("Network unreachable"),
            Exception("Connection reset by peer"),
            ValueError("Invalid value"),  # Not a connection error
            KeyError("Missing key"),  # Not a connection error
        ]

        for error in test_errors:
            is_connection_error = storage._is_connection_error(error)
            error_type = "Connection Error" if is_connection_error else "Other Error"
            logger.info(f"{error.__class__.__name__}: '{error}' -> {error_type}")

        # Test 6: Health check
        logger.info("\n" + "=" * 60)
        logger.info("Test 6: Health Check")
        logger.info("=" * 60)

        healthy = await storage.health_check()
        logger.info(
            f"Health check result: {'✅ Healthy' if healthy else '❌ Unhealthy'}",
        )
        logger.info(f"Connection state after health check: {storage._connection_state}")

        # Test 7: Show metrics
        logger.info("\n" + "=" * 60)
        logger.info("Test 7: Storage Metrics")
        logger.info("=" * 60)

        metrics = storage.get_metrics()
        logger.info(f"Total writes: {metrics.total_writes}")
        logger.info(f"Successful writes: {metrics.successful_writes}")
        logger.info(f"Failed writes: {metrics.failed_writes}")
        logger.info(f"Total reads: {metrics.total_reads}")
        logger.info(f"Successful reads: {metrics.successful_reads}")
        logger.info(f"Failed reads: {metrics.failed_reads}")
        logger.info(f"Average write time: {metrics.avg_write_time_ms:.2f}ms")
        logger.info(f"Average read time: {metrics.avg_read_time_ms:.2f}ms")
        logger.info(f"Connection uptime: {metrics.connection_uptime_seconds:.1f}s")

        # Test 8: Simulate connection recovery (if we have buffered data)
        if buffer_size > 0:
            logger.info("\n" + "=" * 60)
            logger.info("Test 8: Simulated Connection Recovery")
            logger.info("=" * 60)

            logger.info(f"Attempting to flush {buffer_size} buffered readings...")

            if storage.connected:
                await storage._flush_buffer()
                remaining_buffer = len(storage._reading_buffer)
                flushed = buffer_size - remaining_buffer
                logger.info(
                    f"Flush completed: {flushed} flushed, {remaining_buffer} remaining",
                )
            else:
                logger.info("Cannot flush - still not connected to InfluxDB")

        # Test 9: Background task status
        logger.info("\n" + "=" * 60)
        logger.info("Test 9: Background Task Status")
        logger.info("=" * 60)

        logger.info(f"Background tasks running: {len(storage._background_tasks)}")
        logger.info(f"Shutdown event set: {storage._shutdown_event.is_set()}")

        # Test 10: Demonstrate graceful shutdown
        logger.info("\n" + "=" * 60)
        logger.info("Test 10: Graceful Shutdown")
        logger.info("=" * 60)

        logger.info("Initiating graceful shutdown...")
        await storage.disconnect()

        logger.info(f"Final connection state: {storage._connection_state}")
        logger.info(
            f"Background tasks after shutdown: {len(storage._background_tasks)}",
        )
        logger.info(f"Shutdown event set: {storage._shutdown_event.is_set()}")

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Demo Summary")
        logger.info("=" * 60)
        logger.info("Error handling features demonstrated:")
        logger.info("  ✅ Connection retry with exponential backoff")
        logger.info("  ✅ Data buffering during outages")
        logger.info("  ✅ Write failure management")
        logger.info("  ✅ Connection error detection")
        logger.info("  ✅ Health monitoring")
        logger.info("  ✅ Background task management")
        logger.info("  ✅ Graceful shutdown with buffer flushing")
        logger.info("  ✅ Comprehensive metrics tracking")

    except Exception as e:
        logger.exception(f"Demo failed with error: {e}")
    finally:
        # Cleanup
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info("Cleaned up temporary files")
        except Exception:
            pass

    logger.info("InfluxDB Error Handling Demo completed")


if __name__ == "__main__":
    asyncio.run(demo_error_handling())
