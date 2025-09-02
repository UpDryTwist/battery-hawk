"""
Example storage backend implementations for Battery Hawk.

This module provides example implementations of alternative storage backends
to demonstrate how to extend the storage abstraction layer.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .storage_backends import BaseStorageBackend

if TYPE_CHECKING:
    from battery_hawk.config.config_manager import ConfigManager


class JSONFileStorageBackend(BaseStorageBackend):
    """
    JSON file storage backend implementation for Battery Hawk.
    
    Stores battery readings in JSON files for simple local storage.
    Useful for development, testing, or offline scenarios.
    """

    def __init__(self, config_manager: "ConfigManager") -> None:
        """Initialize JSON file storage backend."""
        self.storage_dir: Path | None = None
        self.readings_file: Path | None = None
        super().__init__(config_manager)

    @property
    def backend_name(self) -> str:
        """Return the name of the storage backend."""
        return "JSONFile"

    @property
    def backend_version(self) -> str:
        """Return the version of the storage backend implementation."""
        return "1.0.0"

    @property
    def capabilities(self) -> set[str]:
        """Return supported capabilities for JSON file backend."""
        return {
            "time_series",
            "backup",
        }

    def _initialize_backend(self) -> None:
        """Initialize the JSON file storage backend."""
        super()._initialize_backend()
        try:
            # Get storage configuration
            storage_config = self.config.get_config("system").get("json_storage", {})
            storage_path = storage_config.get("path", "/data/readings")
            
            self.storage_dir = Path(storage_path)
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            
            self.readings_file = self.storage_dir / "battery_readings.json"
            
            # Initialize empty readings file if it doesn't exist
            if not self.readings_file.exists():
                self._save_readings([])
                
            self.logger.info("JSON file storage initialized at %s", self.storage_dir)
            
        except Exception:
            self.logger.exception("Failed to initialize JSON file storage backend")

    async def connect(self) -> bool:
        """Connect to the JSON file storage (always succeeds if directory is accessible)."""
        try:
            if self.storage_dir and self.storage_dir.exists():
                self.connected = True
                self.logger.info("Connected to JSON file storage")
                return True
            else:
                self.logger.error("Storage directory not accessible")
                return False
        except Exception as e:
            self.logger.exception("Failed to connect to JSON file storage: %s", e)
            return False

    async def disconnect(self) -> None:
        """Disconnect from JSON file storage."""
        self.connected = False
        self.logger.info("Disconnected from JSON file storage")

    async def store_reading(
        self,
        device_id: str,
        vehicle_id: str,
        device_type: str,
        reading: dict[str, Any],
    ) -> bool:
        """Store a battery reading in JSON file."""
        start_time = time.time()
        self.metrics.total_writes += 1
        
        if not self.connected:
            self.logger.warning("Storage not connected, dropping measurement")
            self.metrics.failed_writes += 1
            return False

        try:
            # Load existing readings
            readings = self._load_readings()
            
            # Create new reading entry
            new_reading = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "device_id": device_id,
                "vehicle_id": vehicle_id,
                "device_type": device_type,
                **reading,
            }
            
            # Add to readings list
            readings.append(new_reading)
            
            # Keep only last 10000 readings to prevent file from growing too large
            if len(readings) > 10000:
                readings = readings[-10000:]
            
            # Save back to file
            self._save_readings(readings)
            
            # Update metrics
            write_time = (time.time() - start_time) * 1000
            self.metrics.successful_writes += 1
            self.metrics.avg_write_time_ms = (
                (self.metrics.avg_write_time_ms * (self.metrics.successful_writes - 1) + write_time)
                / self.metrics.successful_writes
            )
            
            self.logger.debug("Stored reading for device %s in JSON file", device_id)
            return True
            
        except Exception as e:
            self.metrics.failed_writes += 1
            self.logger.exception("Failed to store reading for device %s: %s", device_id, e)
            return False

    async def get_recent_readings(
        self,
        device_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get recent readings for a device from JSON file."""
        start_time = time.time()
        self.metrics.total_reads += 1
        
        if not self.connected:
            self.logger.warning("Storage not connected, cannot retrieve readings")
            self.metrics.failed_reads += 1
            return []

        try:
            # Load all readings
            readings = self._load_readings()
            
            # Filter by device_id and sort by timestamp (newest first)
            device_readings = [
                r for r in readings 
                if r.get("device_id") == device_id
            ]
            device_readings.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            # Apply limit
            result = device_readings[:limit]
            
            # Update metrics
            read_time = (time.time() - start_time) * 1000
            self.metrics.successful_reads += 1
            self.metrics.avg_read_time_ms = (
                (self.metrics.avg_read_time_ms * (self.metrics.successful_reads - 1) + read_time)
                / self.metrics.successful_reads
            )
            
            self.logger.debug("Retrieved %d readings for device %s from JSON file", len(result), device_id)
            return result
            
        except Exception as e:
            self.metrics.failed_reads += 1
            self.logger.exception("Failed to get readings for device %s: %s", device_id, e)
            return []

    async def get_vehicle_summary(
        self,
        vehicle_id: str,
        hours: int = 24,
    ) -> dict[str, Any]:
        """Get summary statistics for a vehicle from JSON file."""
        if not self.connected:
            self.logger.warning("Storage not connected, cannot retrieve summary")
            return self._empty_summary(vehicle_id, hours)

        try:
            # Load all readings
            readings = self._load_readings()
            
            # Filter by vehicle_id and time range
            cutoff_time = datetime.now(timezone.utc).timestamp() - (hours * 3600)
            vehicle_readings = []
            
            for reading in readings:
                if reading.get("vehicle_id") == vehicle_id:
                    try:
                        reading_time = datetime.fromisoformat(reading.get("timestamp", "")).timestamp()
                        if reading_time >= cutoff_time:
                            vehicle_readings.append(reading)
                    except (ValueError, TypeError):
                        continue
            
            if not vehicle_readings:
                return self._empty_summary(vehicle_id, hours)
            
            # Calculate averages
            voltages = [r.get("voltage", 0) for r in vehicle_readings if "voltage" in r]
            currents = [r.get("current", 0) for r in vehicle_readings if "current" in r]
            temperatures = [r.get("temperature", 0) for r in vehicle_readings if "temperature" in r]
            
            return {
                "vehicle_id": vehicle_id,
                "period_hours": hours,
                "avg_voltage": sum(voltages) / len(voltages) if voltages else 0.0,
                "avg_current": sum(currents) / len(currents) if currents else 0.0,
                "avg_temperature": sum(temperatures) / len(temperatures) if temperatures else 0.0,
                "reading_count": len(vehicle_readings),
            }
            
        except Exception as e:
            self.logger.exception("Failed to get summary for vehicle %s: %s", vehicle_id, e)
            return self._empty_summary(vehicle_id, hours)

    async def health_check(self) -> bool:
        """Perform a health check on JSON file storage."""
        try:
            if not self.connected:
                return await self.connect()
                
            # Check if storage directory is still accessible
            if self.storage_dir and self.storage_dir.exists() and os.access(self.storage_dir, os.W_OK):
                self.logger.debug("JSON file storage health check passed")
                return True
            else:
                self.logger.error("JSON file storage directory not accessible")
                self.connected = False
                return False
                
        except Exception as e:
            self.logger.exception("JSON file storage health check failed: %s", e)
            self.connected = False
            return False

    def _load_readings(self) -> list[dict[str, Any]]:
        """Load readings from JSON file."""
        try:
            if self.readings_file and self.readings_file.exists():
                with open(self.readings_file, 'r') as f:
                    return json.load(f)
            return []
        except (json.JSONDecodeError, OSError) as e:
            self.logger.warning("Failed to load readings from JSON file: %s", e)
            return []

    def _save_readings(self, readings: list[dict[str, Any]]) -> None:
        """Save readings to JSON file."""
        if self.readings_file:
            with open(self.readings_file, 'w') as f:
                json.dump(readings, f, indent=2)

    def _empty_summary(self, vehicle_id: str, hours: int) -> dict[str, Any]:
        """Return an empty summary dictionary."""
        return {
            "vehicle_id": vehicle_id,
            "period_hours": hours,
            "avg_voltage": 0.0,
            "avg_current": 0.0,
            "avg_temperature": 0.0,
            "reading_count": 0,
        }


class NullStorageBackend(BaseStorageBackend):
    """
    Null storage backend that discards all data.
    
    Useful for testing or when storage is not needed.
    """

    @property
    def backend_name(self) -> str:
        return "Null"

    @property
    def backend_version(self) -> str:
        return "1.0.0"

    @property
    def capabilities(self) -> set[str]:
        return set()

    async def connect(self) -> bool:
        self.connected = True
        self.logger.info("Connected to null storage (data will be discarded)")
        return True

    async def disconnect(self) -> None:
        self.connected = False
        self.logger.info("Disconnected from null storage")

    async def store_reading(self, device_id: str, vehicle_id: str, device_type: str, reading: dict[str, Any]) -> bool:
        self.metrics.total_writes += 1
        self.metrics.successful_writes += 1
        self.logger.debug("Discarded reading for device %s (null storage)", device_id)
        return True

    async def get_recent_readings(self, device_id: str, limit: int = 100) -> list[dict[str, Any]]:
        self.metrics.total_reads += 1
        self.metrics.successful_reads += 1
        return []

    async def get_vehicle_summary(self, vehicle_id: str, hours: int = 24) -> dict[str, Any]:
        return {
            "vehicle_id": vehicle_id,
            "period_hours": hours,
            "avg_voltage": 0.0,
            "avg_current": 0.0,
            "avg_temperature": 0.0,
            "reading_count": 0,
        }

    async def health_check(self) -> bool:
        return True
