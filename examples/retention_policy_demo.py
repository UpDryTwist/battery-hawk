#!/usr/bin/env python3
"""
InfluxDB Retention Policy Demo for Battery Hawk

This script demonstrates the InfluxDB retention policy management functionality including:
- Automatic retention policy creation during connection
- Configuration-driven policy setup
- Policy-based data storage
- Retention policy querying and management
- Performance optimization through data lifecycle management

Usage:
    python examples/retention_policy_demo.py

Requirements:
    - InfluxDB server running on localhost:8086
    - Or set BATTERYHAWK_INFLUXDB_ENABLED=false to run in simulation mode
"""

import asyncio
import logging
import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from battery_hawk.config.config_manager import ConfigManager
from battery_hawk.core.storage import InfluxDBStorageBackend


async def demo_retention_policies():
    """Demonstrate InfluxDB retention policy functionality."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger("retention_policy_demo")

    logger.info("Starting InfluxDB Retention Policy Demo")

    # Create temporary config directory for demo
    temp_dir = tempfile.mkdtemp()
    config_dir = os.path.join(temp_dir, "config")
    os.makedirs(config_dir, exist_ok=True)

    try:
        # Initialize configuration manager
        config_manager = ConfigManager(config_dir)
        
        # Configure InfluxDB with multiple retention policies
        system_config = config_manager.get_config("system")
        system_config["influxdb"] = {
            "enabled": True,
            "host": "localhost",
            "port": 8086,
            "database": "battery_hawk_retention_demo",
            "username": "",
            "password": "",
            "timeout": 10000,
            "retries": 3,
            "retention_policies": {
                "default": {
                    "name": "autogen",
                    "duration": "30d",
                    "replication": 1,
                    "shard_duration": "1d",
                    "default": True
                },
                "short_term": {
                    "name": "short_term",
                    "duration": "7d",
                    "replication": 1,
                    "shard_duration": "1h",
                    "default": False
                },
                "long_term": {
                    "name": "long_term",
                    "duration": "365d",
                    "replication": 1,
                    "shard_duration": "7d",
                    "default": False
                },
                "critical_events": {
                    "name": "critical_events",
                    "duration": "1095d",  # 3 years
                    "replication": 1,
                    "shard_duration": "30d",
                    "default": False
                }
            }
        }
        config_manager.save_config("system")
        
        logger.info("Configuration initialized with retention policies")

        # Create InfluxDB storage backend
        storage = InfluxDBStorageBackend(config_manager)
        logger.info("InfluxDB storage backend created")

        # Test connection (this will create retention policies)
        logger.info("Connecting to InfluxDB (this will setup retention policies)...")
        connected = await storage.connect()
        
        if not connected:
            logger.warning("❌ Failed to connect to InfluxDB")
            logger.info("This is expected if InfluxDB is not running")
            logger.info("The demo will show the configuration and logic without actual database operations")
            
            # Show configuration even if not connected
            config = storage._get_influx_config()
            logger.info("\n" + "="*60)
            logger.info("Configured Retention Policies:")
            logger.info("="*60)
            
            for policy_key, policy_config in config.get("retention_policies", {}).items():
                logger.info(f"Policy: {policy_key}")
                logger.info(f"  Name: {policy_config.get('name')}")
                logger.info(f"  Duration: {policy_config.get('duration')}")
                logger.info(f"  Replication: {policy_config.get('replication')}")
                logger.info(f"  Shard Duration: {policy_config.get('shard_duration')}")
                logger.info(f"  Default: {policy_config.get('default')}")
                logger.info("")
            
            return

        logger.info("✅ Successfully connected to InfluxDB")

        # Query existing retention policies
        logger.info("\n" + "="*60)
        logger.info("Querying Retention Policies")
        logger.info("="*60)
        
        database_name = system_config["influxdb"]["database"]
        policies = await storage.get_retention_policies(database_name)
        
        if policies:
            logger.info(f"Found {len(policies)} retention policies:")
            for policy in policies:
                logger.info(f"  - {policy.get('name', 'Unknown')}: "
                          f"duration={policy.get('duration', 'N/A')}, "
                          f"replication={policy.get('replicaN', 'N/A')}, "
                          f"default={policy.get('default', False)}")
        else:
            logger.info("No retention policies found or query failed")

        # Demonstrate policy-based data storage
        logger.info("\n" + "="*60)
        logger.info("Testing Policy-Based Data Storage")
        logger.info("="*60)
        
        test_readings = [
            {
                "description": "Normal reading (should use default policy)",
                "device_id": "AA:BB:CC:DD:EE:01",
                "vehicle_id": "demo_vehicle_1",
                "device_type": "BM6",
                "reading": {"voltage": 12.5, "current": 2.3, "temperature": 25.0}
            },
            {
                "description": "High current reading (should use short-term policy)",
                "device_id": "AA:BB:CC:DD:EE:02",
                "vehicle_id": "demo_vehicle_1",
                "device_type": "BM6",
                "reading": {"voltage": 11.8, "current": 15.5, "temperature": 35.0}
            },
            {
                "description": "Another normal reading",
                "device_id": "AA:BB:CC:DD:EE:03",
                "vehicle_id": "demo_vehicle_2",
                "device_type": "BM2",
                "reading": {"voltage": 12.7, "current": 1.8, "temperature": 22.0}
            }
        ]
        
        for test_case in test_readings:
            logger.info(f"Testing: {test_case['description']}")
            
            # Show which policy would be selected
            policy = storage._get_retention_policy_for_measurement(test_case["reading"])
            logger.info(f"  Selected retention policy: {policy or 'default'}")
            
            # Store the reading
            success = await storage.store_reading(
                test_case["device_id"],
                test_case["vehicle_id"],
                test_case["device_type"],
                test_case["reading"]
            )
            
            status = "✅ Success" if success else "❌ Failed"
            logger.info(f"  Storage result: {status}")
            logger.info("")

        # Show retention policy logic
        logger.info("\n" + "="*60)
        logger.info("Retention Policy Selection Logic")
        logger.info("="*60)
        logger.info("Current logic:")
        logger.info("  - High current readings (>10A): short_term policy (7 days)")
        logger.info("  - Normal readings: default policy (30 days)")
        logger.info("  - Future: Could add logic for:")
        logger.info("    * Critical events (voltage < 11V): critical_events policy (3 years)")
        logger.info("    * Temperature extremes: long_term policy (1 year)")
        logger.info("    * Device type specific policies")
        logger.info("    * Time-based policies (e.g., weekend vs weekday)")

        # Show storage optimization benefits
        logger.info("\n" + "="*60)
        logger.info("Storage Optimization Benefits")
        logger.info("="*60)
        logger.info("Retention policies provide several benefits:")
        logger.info("  1. Automatic data lifecycle management")
        logger.info("  2. Reduced storage costs and improved performance")
        logger.info("  3. Compliance with data retention requirements")
        logger.info("  4. Optimized query performance through shard management")
        logger.info("  5. Flexible data retention based on data importance")

        # Test health check
        logger.info("\n" + "="*60)
        logger.info("Health Check")
        logger.info("="*60)
        healthy = await storage.health_check()
        logger.info(f"Storage health: {'✅ Healthy' if healthy else '❌ Unhealthy'}")

        # Show metrics
        metrics = storage.get_metrics()
        logger.info(f"Total writes: {metrics.total_writes}")
        logger.info(f"Successful writes: {metrics.successful_writes}")
        logger.info(f"Connection uptime: {metrics.connection_uptime_seconds:.1f}s")

        # Disconnect
        logger.info("\n" + "="*60)
        logger.info("Cleanup")
        logger.info("="*60)
        await storage.disconnect()
        logger.info("✅ Disconnected from InfluxDB")

    except Exception as e:
        logger.exception(f"Demo failed with error: {e}")
    finally:
        # Cleanup
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info("Cleaned up temporary files")
        except Exception:
            pass

    logger.info("InfluxDB Retention Policy Demo completed")


if __name__ == "__main__":
    asyncio.run(demo_retention_policies())
