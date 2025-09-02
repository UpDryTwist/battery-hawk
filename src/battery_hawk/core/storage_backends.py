"""
Storage Backend Abstraction for Battery Hawk.

This module defines the abstract base class and data models for implementing
storage backends for Battery Hawk monitoring data. It provides a standard
interface for database connection, data storage, querying, and health monitoring.

Extension:
    - Subclass `BaseStorageBackend` to implement support for a specific database.
    - Implement all abstract async methods and required properties.
    - Use `StorageConfig` and `StorageHealth` dataclasses for structured data.

Example:
    from src.battery_hawk.core.storage_backends import BaseStorageBackend, StorageConfig, StorageHealth
    import asyncio

    class MyStorageBackend(BaseStorageBackend):
        @property
        def backend_name(self) -> str:
            return "MyDatabase"
        @property
        def backend_version(self) -> str:
            return "1.0"
        @property
        def capabilities(self) -> set[str]:
            return {"time_series", "aggregation", "retention"}
        async def connect(self) -> bool:
            return True  # Implement connection logic
        async def disconnect(self) -> None:
            pass  # Implement disconnect logic
        async def store_reading(self, device_id: str, vehicle_id: str, device_type: str, reading: dict) -> bool:
            return True  # Implement storage logic
        async def get_recent_readings(self, device_id: str, limit: int = 100) -> list[dict]:
            return []  # Implement query logic
        async def get_vehicle_summary(self, vehicle_id: str, hours: int = 24) -> dict:
            return {}  # Implement aggregation logic
        async def health_check(self) -> bool:
            return True  # Implement health check logic

    # Usage
    # backend = MyStorageBackend(config_manager)
    # asyncio.run(backend.connect())
    # success = asyncio.run(backend.store_reading("device", "vehicle", "BM6", {"voltage": 12.5}))
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from battery_hawk.config.config_manager import ConfigManager


@dataclass
class StorageConfig:
    """Configuration data model for storage backends."""
    
    enabled: bool
    backend_type: str
    connection_params: dict[str, Any]
    timeout: int = 10000
    retries: int = 3
    extra: dict[str, Any] | None = None


@dataclass
class StorageHealth:
    """Health status data model for storage backends."""
    
    connected: bool
    backend_name: str
    backend_version: str
    last_check: float | None = None  # Unix timestamp
    error_message: str | None = None
    metrics: dict[str, Any] | None = None  # Backend-specific metrics


@dataclass
class StorageMetrics:
    """Metrics data model for storage backend performance."""
    
    total_writes: int = 0
    successful_writes: int = 0
    failed_writes: int = 0
    total_reads: int = 0
    successful_reads: int = 0
    failed_reads: int = 0
    avg_write_time_ms: float = 0.0
    avg_read_time_ms: float = 0.0
    connection_uptime_seconds: float = 0.0


class BaseStorageBackend(abc.ABC):
    """
    Abstract base class for storage backend implementations.
    
    Provides a standard interface for database operations including connection
    management, data storage, querying, and health monitoring. All storage
    backends should inherit from this class and implement the abstract methods.
    """

    def __init__(self, config_manager: "ConfigManager") -> None:
        """
        Initialize BaseStorageBackend with configuration manager.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager
        self.logger = logging.getLogger(f"battery_hawk.storage.{self.backend_name.lower()}")
        self.connected = False
        self.metrics = StorageMetrics()
        self._initialize_backend()

    def _initialize_backend(self) -> None:
        """Initialize the storage backend. Override in subclasses if needed."""
        self.logger.info("Initializing %s storage backend", self.backend_name)

    @property
    @abc.abstractmethod
    def backend_name(self) -> str:
        """Return the name of the storage backend (e.g., 'InfluxDB', 'PostgreSQL')."""
        ...

    @property
    @abc.abstractmethod
    def backend_version(self) -> str:
        """Return the version of the storage backend implementation."""
        ...

    @property
    @abc.abstractmethod
    def capabilities(self) -> set[str]:
        """
        Return a set of supported capability strings for this backend.
        
        Common capabilities:
        - "time_series": Supports time series data storage
        - "aggregation": Supports data aggregation queries
        - "retention": Supports automatic data retention policies
        - "real_time": Supports real-time data streaming
        - "backup": Supports data backup/restore
        - "clustering": Supports distributed/clustered deployment
        """
        ...

    @abc.abstractmethod
    async def connect(self) -> bool:
        """
        Connect to the storage backend.
        
        Returns:
            True if connection was successful, False otherwise
        """
        ...

    @abc.abstractmethod
    async def disconnect(self) -> None:
        """
        Disconnect from the storage backend and clean up resources.
        """
        ...

    @abc.abstractmethod
    async def store_reading(
        self,
        device_id: str,
        vehicle_id: str,
        device_type: str,
        reading: dict[str, Any],
    ) -> bool:
        """
        Store a battery reading in the storage backend.
        
        Args:
            device_id: MAC address of the device
            vehicle_id: ID of the vehicle
            device_type: Type of device (BM6, BM2, etc.)
            reading: Battery reading data
            
        Returns:
            True if storage was successful, False otherwise
        """
        ...

    @abc.abstractmethod
    async def get_recent_readings(
        self,
        device_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get recent readings for a device.
        
        Args:
            device_id: MAC address of the device
            limit: Maximum number of readings to return
            
        Returns:
            List of recent readings, ordered by timestamp (newest first)
        """
        ...

    @abc.abstractmethod
    async def get_vehicle_summary(
        self,
        vehicle_id: str,
        hours: int = 24,
    ) -> dict[str, Any]:
        """
        Get summary statistics for a vehicle over a time period.
        
        Args:
            vehicle_id: Vehicle ID
            hours: Number of hours to look back
            
        Returns:
            Summary statistics dictionary with keys:
            - vehicle_id: str
            - period_hours: int
            - avg_voltage: float
            - avg_current: float
            - avg_temperature: float
            - reading_count: int
        """
        ...

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """
        Perform a health check on the storage backend.
        
        Returns:
            True if storage is healthy, False otherwise
        """
        ...

    def is_connected(self) -> bool:
        """
        Check if storage backend is connected.
        
        Returns:
            True if connected, False otherwise
        """
        return self.connected

    def has_capability(self, capability: str) -> bool:
        """
        Check if the backend supports a given capability.
        
        Args:
            capability: Capability string to check
            
        Returns:
            True if capability is supported, False otherwise
        """
        return capability in self.capabilities

    def get_metrics(self) -> StorageMetrics:
        """
        Get performance metrics for the storage backend.
        
        Returns:
            StorageMetrics instance with current metrics
        """
        return self.metrics

    def get_health_status(self) -> StorageHealth:
        """
        Get current health status of the storage backend.
        
        Returns:
            StorageHealth instance with current status
        """
        return StorageHealth(
            connected=self.connected,
            backend_name=self.backend_name,
            backend_version=self.backend_version,
            metrics=self.metrics.__dict__,
        )

    async def get_storage_info(self) -> dict[str, Any]:
        """
        Get information about the storage backend.
        
        Returns:
            Dictionary with backend information including name, version,
            capabilities, connection status, and metrics
        """
        return {
            "backend_name": self.backend_name,
            "backend_version": self.backend_version,
            "capabilities": list(self.capabilities),
            "connected": self.connected,
            "health": self.get_health_status().__dict__,
            "metrics": self.get_metrics().__dict__,
        }
