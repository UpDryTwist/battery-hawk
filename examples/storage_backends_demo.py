#!/usr/bin/env python3
"""
Storage Backends Demo for Battery Hawk.

This script demonstrates the storage backend abstraction including:
- Abstract base class usage
- Factory pattern for backend creation
- Multiple backend implementations (InfluxDB, JSON, Null)
- Backend switching and comparison
- Metrics and health monitoring

Usage:
    python examples/storage_backends_demo.py

Requirements:
    - For InfluxDB demo: InfluxDB server running on localhost:8086
    - For JSON demo: Write access to /tmp directory
    - For Null demo: No requirements
"""

import asyncio
import contextlib
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from battery_hawk.config.config_manager import ConfigManager
from battery_hawk.core.storage import StorageBackendFactory
from battery_hawk.core.storage_backends import BaseStorageBackend


async def demo_backend(
    backend_name: str,
    backend: BaseStorageBackend,
    logger: logging.Logger,
) -> None:
    """Demonstrate a storage backend."""
    logger.info("\n%s", "=" * 60)
    logger.info("Testing %s Storage Backend", backend_name)
    logger.info("%s", "=" * 60)

    # Show backend information
    info = await backend.get_storage_info()
    logger.info("Backend: %s v%s", info["backend_name"], info["backend_version"])
    logger.info("Capabilities: %s", ", ".join(info["capabilities"]))

    # Test connection
    logger.info("Connecting to backend...")
    connected = await backend.connect()
    logger.info("Connection result: %s", "✅ Success" if connected else "❌ Failed")

    if not connected:
        logger.warning("Skipping further tests due to connection failure")
        return

    # Test health check
    logger.info("Performing health check...")
    healthy = await backend.health_check()
    logger.info("Health check: %s", "✅ Healthy" if healthy else "❌ Unhealthy")

    # Test storing readings
    logger.info("Storing sample battery readings...")
    sample_readings = [
        {
            "device_id": "AA:BB:CC:DD:EE:01",
            "vehicle_id": "demo_vehicle_1",
            "device_type": "BM6",
            "reading": {"voltage": 12.6, "current": 2.5, "temperature": 22.0},
        },
        {
            "device_id": "AA:BB:CC:DD:EE:02",
            "vehicle_id": "demo_vehicle_1",
            "device_type": "BM2",
            "reading": {"voltage": 12.4, "current": 1.8, "temperature": 24.0},
        },
        {
            "device_id": "AA:BB:CC:DD:EE:01",
            "vehicle_id": "demo_vehicle_2",
            "device_type": "BM6",
            "reading": {"voltage": 12.5, "current": 2.3, "temperature": 23.0},
        },
    ]

    for i, sample in enumerate(sample_readings):
        success = await backend.store_reading(
            sample["device_id"],
            sample["vehicle_id"],
            sample["device_type"],
            sample["reading"],
        )
        status = "✅" if success else "❌"
        logger.info("  %s Stored reading %d/%d", status, i + 1, len(sample_readings))
        await asyncio.sleep(0.1)  # Small delay

    # Test querying readings
    logger.info("Querying recent readings...")
    for device_id in ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"]:
        readings = await backend.get_recent_readings(device_id, limit=5)
        logger.info("  Device %s: %d readings", device_id, len(readings))

        for reading in readings[:2]:  # Show first 2 readings
            voltage = reading.get("voltage", "N/A")
            current = reading.get("current", "N/A")
            temp = reading.get("temperature", "N/A")
            logger.info("    - V=%sV, I=%sA, T=%s°C", voltage, current, temp)

    # Test vehicle summaries
    logger.info("Getting vehicle summaries...")
    for vehicle_id in ["demo_vehicle_1", "demo_vehicle_2"]:
        summary = await backend.get_vehicle_summary(vehicle_id, hours=1)
        logger.info("  Vehicle %s:", vehicle_id)
        logger.info("    - Readings: %d", summary["reading_count"])
        logger.info("    - Avg voltage: %.2fV", summary["avg_voltage"])
        logger.info("    - Avg current: %.2fA", summary["avg_current"])
        logger.info("    - Avg temperature: %.1f°C", summary["avg_temperature"])

    # Show metrics
    metrics = backend.get_metrics()
    logger.info("Backend metrics:")
    logger.info("  - Total writes: %d", metrics.total_writes)
    logger.info("  - Successful writes: %d", metrics.successful_writes)
    logger.info("  - Failed writes: %d", metrics.failed_writes)
    logger.info("  - Total reads: %d", metrics.total_reads)
    logger.info("  - Successful reads: %d", metrics.successful_reads)
    logger.info("  - Failed reads: %d", metrics.failed_reads)
    logger.info("  - Avg write time: %.2fms", metrics.avg_write_time_ms)
    logger.info("  - Avg read time: %.2fms", metrics.avg_read_time_ms)

    # Test disconnection
    logger.info("Disconnecting from backend...")
    await backend.disconnect()
    logger.info("✅ Disconnected successfully")


def setup_storage_demo() -> tuple[str, str, str, logging.Logger]:
    """Set up the storage backends demo environment."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("storage_backends_demo")

    logger.info("Starting Storage Backends Demo")

    # Create temporary directories for demo
    temp_dir = tempfile.mkdtemp()
    config_dir = os.path.join(temp_dir, "config")
    storage_dir = os.path.join(temp_dir, "storage")
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(storage_dir, exist_ok=True)

    return temp_dir, config_dir, storage_dir, logger


def setup_storage_config(
    config_manager: ConfigManager,
    storage_dir: str,
    logger: logging.Logger,
) -> None:
    """Set up storage backend configuration."""
    # Configure storage backends
    system_config = config_manager.get_config("system")
    system_config["influxdb"]["enabled"] = True  # Will fail if InfluxDB not running
    system_config["json_storage"] = {"path": storage_dir}
    config_manager.save_config("system")

    logger.info("Configuration initialized")


async def test_single_backend_safe(
    backend_name: str,
    backend_type: str,
    config_manager: ConfigManager,
    logger: logging.Logger,
) -> tuple[str, str, bool]:
    """Test a single backend safely with proper error handling."""
    try:
        backend = StorageBackendFactory.create_backend(
            backend_type,
            config_manager,
        )
        await demo_backend(backend_name, backend, logger)
    except (ConnectionError, TimeoutError, OSError) as conn_error:
        logger.warning(
            "Connection failed for %s backend: %s",
            backend_name,
            conn_error,
        )
        return (backend_name, backend_type, False)
    except ImportError as import_error:
        logger.warning(
            "Import failed for %s backend: %s",
            backend_name,
            import_error,
        )
        return (backend_name, backend_type, False)
    else:
        return (backend_name, backend_type, True)


async def test_backend_comparison(
    config_manager: ConfigManager,
    logger: logging.Logger,
) -> None:
    """Test and compare different storage backends."""
    # Show available backends
    available_backends = StorageBackendFactory.get_available_backends()
    logger.info("Available storage backends: %s", ", ".join(available_backends))

    # Test each backend
    backends_to_test = [
        ("Null", "null"),
        ("JSON File", "json"),
        ("InfluxDB", "influxdb"),
    ]

    # Test each backend individually to avoid performance overhead in loop
    backend_results = []
    for backend_name, backend_type in backends_to_test:
        result = await test_single_backend_safe(
            backend_name,
            backend_type,
            config_manager,
            logger,
        )
        backend_results.append(result)

    # Demonstrate backend comparison
    await show_backend_comparison(backends_to_test, config_manager, logger)


async def show_backend_comparison(
    backends_to_test: list,
    config_manager: ConfigManager,
    logger: logging.Logger,
) -> None:
    """Show comparison of different storage backends."""
    logger.info("\n%s", "=" * 60)
    logger.info("Backend Comparison Summary")
    logger.info("%s", "=" * 60)

    comparison_data = []
    # Collect backend information for comparison
    for _backend_name, backend_type in backends_to_test:
        backend = None
        try:
            backend = StorageBackendFactory.create_backend(
                backend_type,
                config_manager,
            )
            info = await backend.get_storage_info()
            comparison_data.append(
                {
                    "name": info["backend_name"],
                    "version": info["backend_version"],
                    "capabilities": len(info["capabilities"]),
                    "capability_list": info["capabilities"],
                },
            )
        except (ConnectionError, TimeoutError, OSError) as conn_error:
            logger.warning(
                "Connection failed for backend %s: %s",
                backend_type,
                conn_error,
            )
        except ImportError as import_error:
            logger.warning(
                "Import failed for backend %s: %s",
                backend_type,
                import_error,
            )
        finally:
            if backend and hasattr(backend, "disconnect"):
                with contextlib.suppress(Exception):
                    await backend.disconnect()

    # Print comparison table
    # Constants for display formatting
    max_capabilities_display = 3

    logger.info("%-12s %-8s %-12s %s", "Backend", "Version", "Capabilities", "Features")
    logger.info("-" * 70)
    for data in comparison_data:
        caps_str = ", ".join(data["capability_list"][:max_capabilities_display])
        if len(data["capability_list"]) > max_capabilities_display:
            caps_str += "..."
        logger.info(
            "%-12s %-8s %-12s %s",
            data["name"],
            data["version"],
            data["capabilities"],
            caps_str,
        )


async def demo_storage_backends() -> None:
    """Demonstrate different storage backends."""
    temp_dir, config_dir, storage_dir, logger = setup_storage_demo()

    try:
        # Initialize configuration manager
        config_manager = ConfigManager(config_dir)
        setup_storage_config(config_manager, storage_dir, logger)

        # Test and compare different storage backends
        await test_backend_comparison(config_manager, logger)

        # Demonstrate custom backend registration
        logger.info("\n%s", "=" * 60)
        logger.info("Custom Backend Registration Demo")
        logger.info("%s", "=" * 60)

        # Create a simple custom backend
        class MemoryStorageBackend(BaseStorageBackend):
            def __init__(self, config_manager: Any) -> None:
                self.memory_store = []
                super().__init__(config_manager)

            @property
            def backend_name(self) -> str:
                return "Memory"

            @property
            def backend_version(self) -> str:
                return "1.0.0"

            @property
            def capabilities(self) -> set[str]:
                return {"time_series", "real_time"}

            async def connect(self) -> bool:
                self.connected = True
                return True

            async def disconnect(self) -> None:
                self.connected = False

            async def store_reading(
                self,
                device_id: str,
                vehicle_id: str,
                device_type: str,
                reading: dict,
            ) -> bool:
                if self.connected:
                    self.memory_store.append(
                        {
                            "device_id": device_id,
                            "vehicle_id": vehicle_id,
                            "device_type": device_type,
                            **reading,
                        },
                    )
                    return True
                return False

            async def get_recent_readings(
                self,
                device_id: str,
                limit: int = 100,
            ) -> list[dict]:
                if not self.connected:
                    return []
                device_readings = [
                    r for r in self.memory_store if r.get("device_id") == device_id
                ]
                return device_readings[-limit:]

            async def get_vehicle_summary(
                self,
                vehicle_id: str,
                hours: int = 24,
            ) -> dict:
                return {
                    "vehicle_id": vehicle_id,
                    "period_hours": hours,
                    "avg_voltage": 0.0,
                    "avg_current": 0.0,
                    "avg_temperature": 0.0,
                    "reading_count": 0,
                }

            async def health_check(self) -> bool:
                return self.connected

        # Register and test custom backend
        StorageBackendFactory.register_backend("memory", MemoryStorageBackend)
        logger.info("Registered custom 'memory' backend")

        memory_backend = StorageBackendFactory.create_backend("memory", config_manager)
        await demo_backend("Memory (Custom)", memory_backend, logger)

        logger.info(
            "\nUpdated available backends: %s",
            ", ".join(StorageBackendFactory.get_available_backends()),
        )

    except Exception:
        logger.exception("Demo failed with error")
    finally:
        # Cleanup
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info("Cleaned up temporary files")
        except OSError as cleanup_error:
            logger.warning("Failed to cleanup temporary files: %s", cleanup_error)

    logger.info("Storage Backends Demo completed")


if __name__ == "__main__":
    asyncio.run(demo_storage_backends())
