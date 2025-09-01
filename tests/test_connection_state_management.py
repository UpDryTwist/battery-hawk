"""Test connection state management functionality."""

import pytest

from src.battery_hawk_driver.base.connection import BLEConnectionPool
from src.battery_hawk_driver.base.state import ConnectionState
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
async def test_connection_state_tracking() -> None:
    """Test that connection states are properly tracked."""
    pool = BLEConnectionPool(DummyConfig(2), cleanup_interval=0.05, test_mode=True)

    device_address = "AA:BB:CC:DD:EE:01"

    # Initial state should be disconnected
    assert pool.get_device_state(device_address) == ConnectionState.DISCONNECTED

    # Connect and verify state changes
    await pool.connect(device_address)
    assert pool.get_device_state(device_address) == ConnectionState.CONNECTED

    # Disconnect and verify state changes
    await pool.disconnect(device_address)
    assert pool.get_device_state(device_address) == ConnectionState.DISCONNECTED

    # Check state history
    history = pool.get_device_state_history(device_address)
    assert (
        len(history) >= 3
    )  # DISCONNECTED -> CONNECTING -> CONNECTED -> DISCONNECTING -> DISCONNECTED

    await pool.shutdown()


@pytest.mark.asyncio
async def test_connection_stats_with_states() -> None:
    """Test that connection stats include state information."""
    pool = BLEConnectionPool(DummyConfig(3), cleanup_interval=0.05, test_mode=True)

    # Connect multiple devices
    await pool.connect("AA:BB:CC:DD:EE:01")
    await pool.connect("AA:BB:CC:DD:EE:02")

    stats = pool.get_connection_stats()

    # Check that state counts are included
    assert "state_counts" in stats
    assert "total_devices" in stats
    assert "reconnection_enabled" in stats

    # Should have 2 connected devices
    assert stats["state_counts"].get("CONNECTED", 0) == 2
    assert stats["total_devices"] == 2
    assert stats["reconnection_enabled"] is True

    await pool.shutdown()


@pytest.mark.asyncio
async def test_connection_health_with_states() -> None:
    """Test that connection health includes state information."""
    pool = BLEConnectionPool(DummyConfig(2), cleanup_interval=0.05, test_mode=True)

    device_address = "AA:BB:CC:DD:EE:01"
    await pool.connect(device_address)

    health = await pool.get_connection_health(device_address)

    # Check that state information is included
    assert "current_state" in health
    assert "state_history" in health
    assert health["current_state"] == "CONNECTED"
    assert len(health["state_history"]) > 0

    # Each history entry should have state and timestamp
    for entry in health["state_history"]:
        assert "state" in entry
        assert "timestamp" in entry

    await pool.shutdown()


@pytest.mark.asyncio
async def test_reconnection_functionality() -> None:
    """Test reconnection functionality."""
    pool = BLEConnectionPool(DummyConfig(2), cleanup_interval=0.05, test_mode=True)

    device_address = "AA:BB:CC:DD:EE:01"

    # Configure reconnection
    pool.set_reconnection_config(max_attempts=2, delay=0.1)
    config = pool.get_reconnection_config()
    assert config["max_attempts"] == 2
    assert config["delay"] == 0.1
    assert config["enabled"] is True

    # Test successful reconnection
    success = await pool.reconnect(device_address, max_attempts=1)
    assert success is True
    assert pool.is_connected(device_address)

    await pool.shutdown()


@pytest.mark.asyncio
async def test_reconnection_disabled() -> None:
    """Test that reconnection can be disabled."""
    pool = BLEConnectionPool(DummyConfig(2), cleanup_interval=0.05, test_mode=True)

    device_address = "AA:BB:CC:DD:EE:01"

    # Disable reconnection
    pool.enable_reconnection(enabled=False)
    assert pool.get_reconnection_config()["enabled"] is False

    # Reconnection should fail when disabled
    success = await pool.reconnect(device_address)
    assert success is False

    await pool.shutdown()


@pytest.mark.asyncio
async def test_bm6_device_state_integration() -> None:
    """Test BM6Device integration with connection state management."""
    pool = BLEConnectionPool(DummyConfig(2), cleanup_interval=0.05, test_mode=True)

    device = BM6Device(
        device_address="AA:BB:CC:DD:EE:01",
        config=DummyConfig(),
        connection_pool=pool,
    )

    # Initial state should be disconnected
    assert device.get_connection_state() == ConnectionState.DISCONNECTED

    # Connect and verify state
    await device.connect()
    assert device.get_connection_state() == ConnectionState.CONNECTED

    # Check state history
    history = device.get_connection_state_history()
    assert len(history) > 0

    # Get detailed health
    health = await device.get_detailed_health()
    assert health["device_type"] == "BM6"
    assert health["current_state"] == "CONNECTED"
    assert "service_uuid" in health
    assert "write_characteristic" in health
    assert "notify_characteristic" in health

    # Test force reconnect
    success = await device.force_reconnect(max_attempts=1)
    assert success is True

    await device.disconnect()
    await pool.shutdown()


@pytest.mark.asyncio
async def test_bm6_device_without_connection_pool() -> None:
    """Test BM6Device state methods without connection pool."""
    device = BM6Device(
        device_address="AA:BB:CC:DD:EE:01",
        config=None,  # No config so no default connection pool is created
        connection_pool=None,
    )

    # Should handle missing connection pool gracefully
    assert device.get_connection_state() == ConnectionState.DISCONNECTED
    assert device.get_connection_state_history() == []

    health = await device.get_detailed_health()
    assert health["current_state"] == "DISCONNECTED"
    assert health["connection_state"] == "DISCONNECTED"
    assert "error" in health

    success = await device.force_reconnect()
    assert success is False
