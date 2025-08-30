"""BLE connection pool manager for async BLE operations."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any


class BLEConnectionPool:
    """Async BLE connection pool manager with connection limiting and queuing."""

    def __init__(self, config_manager: Any, cleanup_interval: float = 5.0) -> None:  # noqa: ANN401
        """
        Initialize BLEConnectionPool with config manager and cleanup interval.

        Args:
            config_manager: Accepts Any for compatibility with dynamic config objects.
            cleanup_interval: Interval in seconds for cleaning up stale connections.
        """
        self.config = config_manager
        self.max_connections: int = self.config.get_config("system")["bluetooth"].get(
            "max_concurrent_connections",
            3,
        )
        self.active_connections: dict[str, dict] = {}
        self.connection_queue: asyncio.Queue = asyncio.Queue()
        self.connection_history: list[dict] = []
        self.logger = logging.getLogger("battery_hawk.ble_connection_pool")
        self._cleanup_task: asyncio.Task | None = None
        self.connection_timeout: float = 30.0  # seconds
        self._cleanup_interval: float = cleanup_interval
        self._shutdown_event = asyncio.Event()
        # Don't start cleanup task immediately - will be started when needed

    def _start_cleanup_task(self) -> None:
        """Start background task for cleaning up stale connections."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_stale_connections())

    async def start_cleanup(self) -> None:
        """Start the cleanup task. Call this when the event loop is running."""
        self._start_cleanup_task()

    async def shutdown(self) -> None:
        """Stop the background cleanup task. Use in tests to avoid pending tasks."""
        self._shutdown_event.set()
        if self._cleanup_task:
            await self._cleanup_task

    async def connect(self, device_address: str) -> dict:
        """Request a connection to a BLE device. Queues if pool is full."""
        # Start cleanup task if not already started
        if self._cleanup_task is None:
            await self.start_cleanup()

        if device_address in self.active_connections:
            self.logger.info("Already connected to %s", device_address)
            return self.active_connections[device_address]
        if len(self.active_connections) >= self.max_connections:
            self.logger.info("Max connections reached, queuing %s", device_address)
            future = asyncio.Future()
            await self.connection_queue.put((device_address, future))
            return await future
        return await self._create_connection(device_address)

    async def _create_connection(self, device_address: str) -> dict:
        """Actually create a BLE connection (stub for now)."""
        # TODO(@commit-ready): Integrate with BleakClient or actual BLE connection logic
        conn = {"device_address": device_address, "connected_at": time.time()}
        self.active_connections[device_address] = conn
        self.connection_history.append(
            {
                "event": "connect",
                "device_address": device_address,
                "timestamp": time.time(),
            },
        )
        self.logger.info("Connected to %s", device_address)
        return conn

    async def disconnect(self, device_address: str) -> None:
        """Disconnect from a BLE device and clean up."""
        if device_address in self.active_connections:
            # TODO(@commit-ready): Add actual disconnect logic
            del self.active_connections[device_address]
            self.connection_history.append(
                {
                    "event": "disconnect",
                    "device_address": device_address,
                    "timestamp": time.time(),
                },
            )
            self.logger.info("Disconnected from %s", device_address)
            # Process next in queue if any
            if not self.connection_queue.empty():
                queued_address, future = await self.connection_queue.get()
                conn = await self._create_connection(queued_address)
                if not future.done():
                    future.set_result(conn)

    async def _cleanup_stale_connections(self) -> None:
        """Periodically clean up connections that have timed out."""
        try:
            while not self._shutdown_event.is_set():
                now = time.time()
                stale = [
                    addr
                    for addr, conn in self.active_connections.items()
                    if now - conn["connected_at"] > self.connection_timeout
                ]
                for addr in stale:
                    self.logger.info("Cleaning up stale connection %s", addr)
                    await self.disconnect(addr)
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self._cleanup_interval,
                    )
                except TimeoutError:
                    continue
        except asyncio.CancelledError:
            pass

    def get_active_connections(self) -> dict[str, dict]:
        """
        Get all active connections.

        Returns:
            Dict of device_address to connection object.
        """
        return self.active_connections

    def get_queued_device_addresses(self) -> list[str]:
        """Get a list of device addresses currently queued for connection."""
        # Accessing private _queue is required to peek at asyncio.Queue contents; no public API exists.
        return [item[0] for item in list(self.connection_queue._queue)]  # type: ignore[attr-defined]  # noqa: SLF001

    def get_connection_stats(self) -> dict:
        """
        Get statistics about connections (counts, history).

        Returns:
            Dict with stats.
        """
        return {
            "active": len(self.active_connections),
            "queued": self.connection_queue.qsize(),
            "history": self.connection_history[-20:],  # last 20 events
        }
