"""Tests for BLEConnectionPool connection management and queuing."""

import asyncio

import pytest

from src.battery_hawk_driver.base.connection import BLEConnectionPool


class DummyConfig:
    """Dummy config for BLEConnectionPool tests."""

    def __init__(self, max_concurrent_connections: int = 2) -> None:
        """Initialize DummyConfig with max concurrent connections."""
        self._max = max_concurrent_connections

    def get_config(self, section: str) -> dict:
        """Return config dict for the given section."""
        if section == "system":
            return {"bluetooth": {"max_concurrent_connections": self._max}}
        return {}


@pytest.mark.asyncio
async def test_connect_and_disconnect_basic() -> None:
    """Test basic connection and disconnection workflow."""
    pool = BLEConnectionPool(DummyConfig(2), cleanup_interval=0.05)
    conn1 = await pool.connect("AA:BB:CC:DD:EE:01")
    assert conn1["device_address"] == "AA:BB:CC:DD:EE:01"
    assert "AA:BB:CC:DD:EE:01" in pool.get_active_connections()
    await pool.disconnect("AA:BB:CC:DD:EE:01")
    assert "AA:BB:CC:DD:EE:01" not in pool.get_active_connections()
    await pool.shutdown()


@pytest.mark.asyncio
async def test_connection_queueing() -> None:
    """Test that connections are queued when pool is full and dequeued on disconnect."""
    pool = BLEConnectionPool(DummyConfig(1), cleanup_interval=0.05)
    await pool.connect("AA:BB:CC:DD:EE:01")
    # Second connection should be queued
    fut = asyncio.create_task(pool.connect("AA:BB:CC:DD:EE:02"))
    await asyncio.sleep(0.1)  # Let it queue
    assert pool.connection_queue.qsize() == 1
    # Disconnect first, queued should be processed
    await pool.disconnect("AA:BB:CC:DD:EE:01")
    conn2 = await fut
    assert conn2["device_address"] == "AA:BB:CC:DD:EE:02"
    assert "AA:BB:CC:DD:EE:02" in pool.get_active_connections()
    await pool.shutdown()


@pytest.mark.asyncio
async def test_stale_connection_cleanup() -> None:
    """Test that stale connections are cleaned up after timeout."""
    pool = BLEConnectionPool(DummyConfig(1), cleanup_interval=0.05)
    pool.connection_timeout = 0.1  # Fast timeout for test
    await pool.connect("AA:BB:CC:DD:EE:01")
    await asyncio.sleep(0.15)
    # Wait for cleanup task to run
    await asyncio.sleep(0.1)
    assert "AA:BB:CC:DD:EE:01" not in pool.get_active_connections()
    await pool.shutdown()


@pytest.mark.asyncio
async def test_double_connect_and_release() -> None:
    """Test connecting to the same device twice and double release edge case."""
    pool = BLEConnectionPool(DummyConfig(2), cleanup_interval=0.05)
    conn1 = await pool.connect("AA:BB:CC:DD:EE:01")
    conn2 = await pool.connect("AA:BB:CC:DD:EE:01")
    assert conn1 is conn2
    await pool.disconnect("AA:BB:CC:DD:EE:01")
    # Second disconnect should be a no-op
    await pool.disconnect("AA:BB:CC:DD:EE:01")
    assert "AA:BB:CC:DD:EE:01" not in pool.get_active_connections()
    await pool.shutdown()


@pytest.mark.asyncio
async def test_connection_stats() -> None:
    """Test that connection stats are tracked correctly."""
    pool = BLEConnectionPool(DummyConfig(1), cleanup_interval=0.05)
    await pool.connect("AA:BB:CC:DD:EE:01")
    stats = pool.get_connection_stats()
    assert stats["active"] == 1
    assert stats["queued"] == 0
    # Start the second connection (should queue)
    fut2 = asyncio.create_task(pool.connect("AA:BB:CC:DD:EE:02"))  # noqa: F841, RUF006
    # Wait until the queue is populated or timeout
    for _ in range(20):
        queued = pool.get_queued_device_addresses()
        if queued == ["AA:BB:CC:DD:EE:02"]:
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Second connection was not queued in time")
    stats = pool.get_connection_stats()
    assert stats["active"] == 1
    await pool.disconnect("AA:BB:CC:DD:EE:01")
    stats = pool.get_connection_stats()
    assert stats["active"] == 1
    assert pool.get_queued_device_addresses() == []
    await pool.disconnect("AA:BB:CC:DD:EE:02")
    stats = pool.get_connection_stats()
    assert stats["active"] == 0
    assert stats["queued"] == 0
    await pool.shutdown()
