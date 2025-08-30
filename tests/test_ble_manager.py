"""Tests for BLEManager integration and BLEManager API."""

from unittest.mock import AsyncMock

import pytest

from src.battery_hawk_driver.base.ble_base import BLEManager
from src.battery_hawk_driver.base.protocol import BatteryInfo, DeviceStatus


class DummyConfig:
    """Dummy config for BLEManager tests."""

    def get_config(self, section: str) -> dict:
        """Return config dict for the given section."""
        return {"bluetooth": {"max_concurrent_connections": 2}}


@pytest.mark.asyncio
async def test_scan_for_devices(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test BLEManager.scan_for_devices with monkeypatched discovery."""
    dummy_devices = {
        "AA:BB:CC:DD:EE:01": {"mac_address": "AA:BB:CC:DD:EE:01", "name": "BMTest"},
    }

    async def fake_scan_for_devices(self: object, duration: int = 10) -> dict:
        """Fake scan_for_devices returning dummy devices."""
        return dummy_devices

    monkeypatch.setattr(
        "src.battery_hawk_driver.base.discovery.BLEDiscoveryService.scan_for_devices",
        fake_scan_for_devices,
    )
    manager = BLEManager(DummyConfig())
    devices = await manager.scan_for_devices(duration=1)
    assert devices == dummy_devices


@pytest.mark.asyncio
async def test_connect_read_data_send_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test BLEManager connect, read_data, send_command, and state tracking."""
    # Patch BLEConnectionPool.connect to do nothing
    monkeypatch.setattr(
        "src.battery_hawk_driver.base.connection.BLEConnectionPool.connect",
        AsyncMock(return_value=None),
    )
    manager = BLEManager(DummyConfig())
    addr = "AA:BB:CC:DD:EE:01"
    # Connect (creates DummyDevice)
    device = await manager.connect(addr)
    assert device.device_address == addr
    # Read data
    info = await manager.read_data(addr)
    assert isinstance(info, BatteryInfo)
    # Send command
    status = await manager.send_command(addr, "ping")
    assert isinstance(status, DeviceStatus)
    # State tracking
    assert manager.get_device_state(addr).name == "CONNECTED"
    await manager.disconnect(addr)
    assert manager.get_device_state(addr).name == "DISCONNECTED"


@pytest.mark.asyncio
async def test_state_history(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test BLEManager state history tracking."""
    monkeypatch.setattr(
        "src.battery_hawk_driver.base.connection.BLEConnectionPool.connect",
        AsyncMock(return_value=None),
    )
    manager = BLEManager(DummyConfig())
    addr = "AA:BB:CC:DD:EE:01"
    await manager.connect(addr)
    await manager.disconnect(addr)
    hist = manager.get_device_history(addr)
    assert hist[-1][0].name == "DISCONNECTED"
    assert any(s[0].name == "CONNECTED" for s in hist)
