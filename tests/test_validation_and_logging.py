"""Test validation and logging improvements."""

import asyncio

import pytest

from src.battery_hawk_driver.base.connection import BLEConnectionPool
from src.battery_hawk_driver.bm6.device import BM6Device


class DummyConfig:
    """Dummy config for testing."""

    def __init__(self, max_connections: int = 3) -> None:
        """Initialize dummy config."""
        self._max = max_connections

    def get_config(self, section: str) -> dict:
        """Get config section."""
        if section == "system":
            return {"bluetooth": {"max_concurrent_connections": self._max}}
        return {}


@pytest.mark.asyncio
async def test_write_characteristic_validation() -> None:
    """Test validation in write_characteristic method."""
    pool = BLEConnectionPool(DummyConfig(2), cleanup_interval=0.05, test_mode=True)

    # Connect to device
    await pool.connect("AA:BB:CC:DD:EE:01")

    # Test empty data validation
    with pytest.raises(ValueError, match="Cannot write empty data"):
        await pool.write_characteristic("AA:BB:CC:DD:EE:01", "FFF3", b"")

    # Test empty characteristic UUID validation
    with pytest.raises(ValueError, match="Characteristic UUID cannot be empty"):
        await pool.write_characteristic("AA:BB:CC:DD:EE:01", "", b"test")

    # Test empty device address validation
    with pytest.raises(ValueError, match="Device address cannot be empty"):
        await pool.write_characteristic("", "FFF3", b"test")

    # Test valid write should work
    await pool.write_characteristic("AA:BB:CC:DD:EE:01", "FFF3", b"test")

    await pool.shutdown()


@pytest.mark.asyncio
async def test_start_notifications_validation() -> None:
    """Test validation in start_notifications method."""
    pool = BLEConnectionPool(DummyConfig(2), cleanup_interval=0.05, test_mode=True)

    # Connect to device
    await pool.connect("AA:BB:CC:DD:EE:01")

    def dummy_callback(sender: str, data: bytearray) -> None:
        pass

    # Test empty characteristic UUID validation
    with pytest.raises(ValueError, match="Characteristic UUID cannot be empty"):
        await pool.start_notifications("AA:BB:CC:DD:EE:01", "", dummy_callback)

    # Test empty device address validation
    with pytest.raises(ValueError, match="Device address cannot be empty"):
        await pool.start_notifications("", "FFF4", dummy_callback)

    # Test None callback validation
    with pytest.raises(ValueError, match="Callback function cannot be None"):
        await pool.start_notifications("AA:BB:CC:DD:EE:01", "FFF4", None)  # type: ignore[arg-type]

    # Test valid notification setup should work
    await pool.start_notifications("AA:BB:CC:DD:EE:01", "FFF4", dummy_callback)

    await pool.shutdown()


@pytest.mark.asyncio
async def test_connection_race_condition_prevention() -> None:
    """Test that race conditions are prevented in connection management."""
    pool = BLEConnectionPool(DummyConfig(2), cleanup_interval=0.05, test_mode=True)

    device_address = "AA:BB:CC:DD:EE:01"

    # Start multiple concurrent connection attempts
    tasks = [asyncio.create_task(pool.connect(device_address)) for _ in range(5)]

    # Wait for all to complete
    results = await asyncio.gather(*tasks)

    # All should return the same connection object
    first_conn = results[0]
    for conn in results[1:]:
        assert conn is first_conn

    # Should only have one active connection
    assert len(pool.active_connections) == 1
    assert device_address in pool.active_connections

    # Pending connections should be empty after completion
    assert len(pool._pending_connections) == 0

    await pool.shutdown()


@pytest.mark.asyncio
async def test_connection_stats_include_pending() -> None:
    """Test that connection stats include pending connections."""
    pool = BLEConnectionPool(DummyConfig(1), cleanup_interval=0.05, test_mode=True)

    # Connect one device to fill the pool
    await pool.connect("AA:BB:CC:DD:EE:01")

    # Start a second connection that should be queued
    task = asyncio.create_task(pool.connect("AA:BB:CC:DD:EE:02"))
    await asyncio.sleep(0.1)  # Let it queue

    stats = pool.get_connection_stats()

    # Should show pending connections
    assert "pending" in stats
    assert stats["active"] == 1
    assert stats["queued"] == 1

    # Clean up
    await pool.disconnect("AA:BB:CC:DD:EE:01")
    await task  # Let the queued connection complete

    await pool.shutdown()


@pytest.mark.asyncio
async def test_bm6_notification_handler_validation() -> None:
    """Test BM6 notification handler validation."""
    pool = BLEConnectionPool(DummyConfig(2), cleanup_interval=0.05, test_mode=True)

    device = BM6Device(
        device_address="AA:BB:CC:DD:EE:01",
        config=DummyConfig(),
        connection_pool=pool,
    )

    # Test empty data handling
    device._notification_handler("FFF4", bytearray())

    # Test normal data handling (should not raise)
    device._notification_handler("FFF4", bytearray(b"\x00" * 16))

    await pool.shutdown()


@pytest.mark.asyncio
async def test_bm6_connection_validation() -> None:
    """Test BM6 device connection validation."""
    pool = BLEConnectionPool(DummyConfig(2), cleanup_interval=0.05, test_mode=True)

    device = BM6Device(
        device_address="AA:BB:CC:DD:EE:01",
        config=DummyConfig(),
        connection_pool=pool,
    )

    # Test commands without connection should fail with BM6ConnectionError
    from src.battery_hawk_driver.bm6.exceptions import BM6ConnectionError

    with pytest.raises(BM6ConnectionError):
        await device.request_voltage_temp()

    with pytest.raises(BM6ConnectionError):
        await device.request_basic_info()

    with pytest.raises(BM6ConnectionError):
        await device.request_cell_voltages()

    # Connect and verify commands work
    await device.connect()

    # These should not raise exceptions
    await device.request_voltage_temp()
    await device.request_basic_info()
    await device.request_cell_voltages()

    await device.disconnect()
    await pool.shutdown()
