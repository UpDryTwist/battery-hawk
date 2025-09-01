"""Test BM6 device integration with real BLE operations."""

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
async def test_bm6_device_connect_and_disconnect() -> None:
    """Test BM6 device connection and disconnection with real BLE operations."""
    # Create connection pool in test mode
    pool = BLEConnectionPool(DummyConfig(2), cleanup_interval=0.05, test_mode=True)

    # Create BM6 device
    device = BM6Device(
        device_address="AA:BB:CC:DD:EE:01",
        config=DummyConfig(),
        connection_pool=pool,
    )

    # Test connection
    await device.connect()

    # Verify connection is active
    assert pool.is_connected("AA:BB:CC:DD:EE:01")

    # Verify notifications are set up
    health = await pool.get_connection_health("AA:BB:CC:DD:EE:01")
    assert health["active_notifications"] == 1
    assert (
        "0000fff4-0000-1000-8000-00805f9b34fb" in health["notification_characteristics"]
    )

    # Test disconnection
    await device.disconnect()

    # Verify connection is cleaned up
    assert not pool.is_connected("AA:BB:CC:DD:EE:01")

    await pool.shutdown()


@pytest.mark.asyncio
async def test_bm6_device_commands() -> None:
    """Test BM6 device command sending."""
    # Create connection pool in test mode
    pool = BLEConnectionPool(DummyConfig(2), cleanup_interval=0.05, test_mode=True)

    # Create BM6 device
    device = BM6Device(
        device_address="AA:BB:CC:DD:EE:01",
        config=DummyConfig(),
        connection_pool=pool,
    )

    # Connect device
    await device.connect()

    # Test voltage/temp request
    await device.request_voltage_temp()

    # Test basic info request
    await device.request_basic_info()

    # Test cell voltages request
    await device.request_cell_voltages()

    # Test send_command interface
    status = await device.send_command("request_voltage_temp")
    assert status.connected is True
    assert status.last_command == "request_voltage_temp"

    # Clean up
    await device.disconnect()
    await pool.shutdown()


@pytest.mark.asyncio
async def test_bm6_device_notification_handler() -> None:
    """Test BM6 device notification handling."""
    # Create connection pool in test mode
    pool = BLEConnectionPool(DummyConfig(2), cleanup_interval=0.05, test_mode=True)

    # Create BM6 device
    device = BM6Device(
        device_address="AA:BB:CC:DD:EE:01",
        config=DummyConfig(),
        connection_pool=pool,
    )

    # Connect device
    await device.connect()

    # Test notification handler with mock data
    # This simulates receiving encrypted BM6 data
    mock_notification_data = bytearray(
        b"\x00" * 16
    )  # 16 bytes of zeros as mock encrypted data

    # Call notification handler directly
    device._notification_handler(
        "0000fff4-0000-1000-8000-00805f9b34fb", mock_notification_data
    )

    # The handler should not crash and should log appropriately
    # (The actual parsing may fail with mock data, but that's expected)

    # Clean up
    await device.disconnect()
    await pool.shutdown()


@pytest.mark.asyncio
async def test_bm6_device_error_handling() -> None:
    """Test BM6 device error handling."""
    # Create BM6 device without connection pool (no config so no default pool is created)
    device = BM6Device(
        device_address="AA:BB:CC:DD:EE:01",
        config=None,
        connection_pool=None,
    )

    # Test that operations fail gracefully without connection pool
    from src.battery_hawk_driver.bm6.exceptions import BM6ConnectionError

    with pytest.raises(BM6ConnectionError):
        await device.connect()

    with pytest.raises(RuntimeError):
        await device.request_voltage_temp()

    with pytest.raises(RuntimeError):
        await device.request_basic_info()

    with pytest.raises(RuntimeError):
        await device.request_cell_voltages()
