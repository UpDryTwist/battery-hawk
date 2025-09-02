#!/usr/bin/env python3
"""
Storage Backends Demo for Battery Hawk

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
import logging
import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from battery_hawk.config.config_manager import ConfigManager
from battery_hawk.core.storage import StorageBackendFactory
from battery_hawk.core.storage_backends import BaseStorageBackend


async def demo_backend(backend_name: str, backend: BaseStorageBackend, logger: logging.Logger):
    """Demonstrate a storage backend."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing {backend_name} Storage Backend")
    logger.info(f"{'='*60}")
    
    # Show backend information
    info = await backend.get_storage_info()
    logger.info(f"Backend: {info['backend_name']} v{info['backend_version']}")
    logger.info(f"Capabilities: {', '.join(info['capabilities'])}")
    
    # Test connection
    logger.info("Connecting to backend...")
    connected = await backend.connect()
    logger.info(f"Connection result: {'✅ Success' if connected else '❌ Failed'}")
    
    if not connected:
        logger.warning("Skipping further tests due to connection failure")
        return
    
    # Test health check
    logger.info("Performing health check...")
    healthy = await backend.health_check()
    logger.info(f"Health check: {'✅ Healthy' if healthy else '❌ Unhealthy'}")
    
    # Test storing readings
    logger.info("Storing sample battery readings...")
    sample_readings = [
        {
            "device_id": "AA:BB:CC:DD:EE:01",
            "vehicle_id": "demo_vehicle_1",
            "device_type": "BM6",
            "reading": {"voltage": 12.6, "current": 2.5, "temperature": 22.0}
        },
        {
            "device_id": "AA:BB:CC:DD:EE:02",
            "vehicle_id": "demo_vehicle_1", 
            "device_type": "BM2",
            "reading": {"voltage": 12.4, "current": 1.8, "temperature": 24.0}
        },
        {
            "device_id": "AA:BB:CC:DD:EE:01",
            "vehicle_id": "demo_vehicle_2",
            "device_type": "BM6", 
            "reading": {"voltage": 12.5, "current": 2.3, "temperature": 23.0}
        }
    ]
    
    for i, sample in enumerate(sample_readings):
        success = await backend.store_reading(
            sample["device_id"],
            sample["vehicle_id"],
            sample["device_type"],
            sample["reading"]
        )
        status = "✅" if success else "❌"
        logger.info(f"  {status} Stored reading {i+1}/{len(sample_readings)}")
        await asyncio.sleep(0.1)  # Small delay
    
    # Test querying readings
    logger.info("Querying recent readings...")
    for device_id in ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"]:
        readings = await backend.get_recent_readings(device_id, limit=5)
        logger.info(f"  Device {device_id}: {len(readings)} readings")
        
        for reading in readings[:2]:  # Show first 2 readings
            voltage = reading.get("voltage", "N/A")
            current = reading.get("current", "N/A")
            temp = reading.get("temperature", "N/A")
            logger.info(f"    - V={voltage}V, I={current}A, T={temp}°C")
    
    # Test vehicle summaries
    logger.info("Getting vehicle summaries...")
    for vehicle_id in ["demo_vehicle_1", "demo_vehicle_2"]:
        summary = await backend.get_vehicle_summary(vehicle_id, hours=1)
        logger.info(f"  Vehicle {vehicle_id}:")
        logger.info(f"    - Readings: {summary['reading_count']}")
        logger.info(f"    - Avg voltage: {summary['avg_voltage']:.2f}V")
        logger.info(f"    - Avg current: {summary['avg_current']:.2f}A")
        logger.info(f"    - Avg temperature: {summary['avg_temperature']:.1f}°C")
    
    # Show metrics
    metrics = backend.get_metrics()
    logger.info("Backend metrics:")
    logger.info(f"  - Total writes: {metrics.total_writes}")
    logger.info(f"  - Successful writes: {metrics.successful_writes}")
    logger.info(f"  - Failed writes: {metrics.failed_writes}")
    logger.info(f"  - Total reads: {metrics.total_reads}")
    logger.info(f"  - Successful reads: {metrics.successful_reads}")
    logger.info(f"  - Failed reads: {metrics.failed_reads}")
    logger.info(f"  - Avg write time: {metrics.avg_write_time_ms:.2f}ms")
    logger.info(f"  - Avg read time: {metrics.avg_read_time_ms:.2f}ms")
    
    # Test disconnection
    logger.info("Disconnecting from backend...")
    await backend.disconnect()
    logger.info("✅ Disconnected successfully")


async def demo_storage_backends():
    """Demonstrate different storage backends."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger("storage_backends_demo")
    
    logger.info("Starting Storage Backends Demo")
    
    # Create temporary directories for demo
    temp_dir = tempfile.mkdtemp()
    config_dir = os.path.join(temp_dir, "config")
    storage_dir = os.path.join(temp_dir, "storage")
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(storage_dir, exist_ok=True)
    
    try:
        # Initialize configuration manager
        config_manager = ConfigManager(config_dir)
        
        # Configure storage backends
        system_config = config_manager.get_config("system")
        system_config["influxdb"]["enabled"] = True  # Will fail if InfluxDB not running
        system_config["json_storage"] = {"path": storage_dir}
        config_manager.save_config("system")
        
        logger.info("Configuration initialized")
        
        # Show available backends
        available_backends = StorageBackendFactory.get_available_backends()
        logger.info(f"Available storage backends: {', '.join(available_backends)}")
        
        # Test each backend
        backends_to_test = [
            ("Null", "null"),
            ("JSON File", "json"),
            ("InfluxDB", "influxdb"),
        ]
        
        for backend_name, backend_type in backends_to_test:
            try:
                backend = StorageBackendFactory.create_backend(backend_type, config_manager)
                await demo_backend(backend_name, backend, logger)
            except Exception as e:
                logger.error(f"Failed to test {backend_name} backend: {e}")
                continue
        
        # Demonstrate backend comparison
        logger.info(f"\n{'='*60}")
        logger.info("Backend Comparison Summary")
        logger.info(f"{'='*60}")
        
        comparison_data = []
        for backend_name, backend_type in backends_to_test:
            try:
                backend = StorageBackendFactory.create_backend(backend_type, config_manager)
                info = await backend.get_storage_info()
                comparison_data.append({
                    "name": info["backend_name"],
                    "version": info["backend_version"],
                    "capabilities": len(info["capabilities"]),
                    "capability_list": info["capabilities"]
                })
            except Exception:
                continue
        
        # Print comparison table
        logger.info(f"{'Backend':<12} {'Version':<8} {'Capabilities':<12} {'Features'}")
        logger.info("-" * 70)
        for data in comparison_data:
            caps_str = ", ".join(data["capability_list"][:3])  # Show first 3
            if len(data["capability_list"]) > 3:
                caps_str += "..."
            logger.info(f"{data['name']:<12} {data['version']:<8} {data['capabilities']:<12} {caps_str}")
        
        # Demonstrate custom backend registration
        logger.info(f"\n{'='*60}")
        logger.info("Custom Backend Registration Demo")
        logger.info(f"{'='*60}")
        
        # Create a simple custom backend
        class MemoryStorageBackend(BaseStorageBackend):
            def __init__(self, config_manager):
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
            
            async def store_reading(self, device_id: str, vehicle_id: str, device_type: str, reading: dict) -> bool:
                if self.connected:
                    self.memory_store.append({
                        "device_id": device_id,
                        "vehicle_id": vehicle_id,
                        "device_type": device_type,
                        **reading
                    })
                    return True
                return False
            
            async def get_recent_readings(self, device_id: str, limit: int = 100) -> list[dict]:
                if not self.connected:
                    return []
                device_readings = [r for r in self.memory_store if r.get("device_id") == device_id]
                return device_readings[-limit:]
            
            async def get_vehicle_summary(self, vehicle_id: str, hours: int = 24) -> dict:
                return {"vehicle_id": vehicle_id, "period_hours": hours, "avg_voltage": 0.0, 
                       "avg_current": 0.0, "avg_temperature": 0.0, "reading_count": 0}
            
            async def health_check(self) -> bool:
                return self.connected
        
        # Register and test custom backend
        StorageBackendFactory.register_backend("memory", MemoryStorageBackend)
        logger.info("Registered custom 'memory' backend")
        
        memory_backend = StorageBackendFactory.create_backend("memory", config_manager)
        await demo_backend("Memory (Custom)", memory_backend, logger)
        
        logger.info(f"\nUpdated available backends: {', '.join(StorageBackendFactory.get_available_backends())}")
        
    except Exception as e:
        logger.exception(f"Demo failed with error: {e}")
    finally:
        # Cleanup
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info("Cleaned up temporary files")
        except Exception:
            pass
    
    logger.info("Storage Backends Demo completed")


if __name__ == "__main__":
    asyncio.run(demo_storage_backends())
