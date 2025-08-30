"""Tests for protocol abstraction and dataclasses in battery_hawk_driver.base.protocol."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.battery_hawk_driver.base.connection import BLEConnectionPool
from src.battery_hawk_driver.base.protocol import (
    BaseMonitorDevice,
    BatteryInfo,
    DeviceStatus,
)


# Test dataclass instantiation and field types
def test_battery_info_fields() -> None:
    """Test BatteryInfo dataclass field values and types."""
    info = BatteryInfo(
        voltage=12.5,
        current=1.1,
        temperature=25.0,
        state_of_charge=80.0,
    )
    assert info.voltage == 12.5
    assert info.current == 1.1
    assert info.temperature == 25.0
    assert info.state_of_charge == 80.0
    assert info.capacity is None
    assert isinstance(info, BatteryInfo)


def test_device_status_fields() -> None:
    """Test DeviceStatus dataclass field values and types."""
    status = DeviceStatus(
        connected=True,
        error_code=0,
        error_message=None,
        protocol_version="1.0",
    )
    assert status.connected is True
    assert status.error_code == 0
    assert status.protocol_version == "1.0"
    assert isinstance(status, DeviceStatus)


# Test that BaseMonitorDevice cannot be instantiated directly
# Use a helper function to avoid Pyright error for direct instantiation


def instantiate_base_monitor_device() -> None:
    """Dynamically create a class with BaseMonitorDevice as base, no implementations."""
    base_cls = type("FakeBase", (BaseMonitorDevice,), {})
    base_cls("AA:BB:CC:DD:EE:FF")


def test_base_monitor_device_abstract() -> None:
    """Test that BaseMonitorDevice cannot be instantiated directly (abstract)."""
    with pytest.raises(TypeError):
        instantiate_base_monitor_device()


# Minimal concrete subclass for testing
class DummyDevice(BaseMonitorDevice):
    """Minimal concrete subclass of BaseMonitorDevice for testing."""

    @property
    def protocol_version(self) -> str:
        """Return protocol version string for DummyDevice."""
        return "test"

    @property
    def capabilities(self) -> set[str]:
        """Return supported capabilities for DummyDevice."""
        return {"foo", "bar"}

    async def connect(self) -> None:
        """Simulate connecting the DummyDevice."""
        self._connected = True

    async def disconnect(self) -> None:
        """Simulate disconnecting the DummyDevice."""
        self._connected = False

    async def read_data(self) -> BatteryInfo:
        """Return dummy BatteryInfo data."""
        return BatteryInfo(
            voltage=1.0,
            current=0.1,
            temperature=20.0,
            state_of_charge=50.0,
        )

    async def send_command(
        self,
        command: str,
        params: dict | None = None,
    ) -> DeviceStatus:
        """Simulate sending a command to DummyDevice."""
        return DeviceStatus(connected=True, last_command=command)


def test_dummy_device_instantiation() -> None:
    """Test DummyDevice instantiation and capability checks."""
    dev = DummyDevice("AA:BB:CC:DD:EE:FF")
    assert dev.device_address == "AA:BB:CC:DD:EE:FF"
    assert dev.protocol_version == "test"
    assert dev.has_capability("foo")
    assert not dev.has_capability("baz")


@pytest.mark.asyncio
async def test_dummy_device_async_methods() -> None:
    """Test DummyDevice async methods: connect, read_data, send_command, disconnect."""
    dev = DummyDevice("AA:BB:CC:DD:EE:FF")
    await dev.connect()
    info = await dev.read_data()
    assert isinstance(info, BatteryInfo)
    status = await dev.send_command("ping")
    assert isinstance(status, DeviceStatus)
    await dev.disconnect()


# New: DummyDeviceWithPool for testing base class connection pool logic
class DummyDeviceWithPool(BaseMonitorDevice):
    """Test subclass that uses base class connect/disconnect logic."""

    @property
    def protocol_version(self) -> str:
        """Return protocol version string for DummyDeviceWithPool."""
        return "test"

    @property
    def capabilities(self) -> set[str]:
        """Return supported capabilities for DummyDeviceWithPool."""
        return {"foo", "bar"}

    # Do not override connect/disconnect; use base class logic
    async def read_data(self) -> BatteryInfo:
        """Return dummy BatteryInfo data for testing."""
        return BatteryInfo(
            voltage=1.0,
            current=0.1,
            temperature=20.0,
            state_of_charge=50.0,
        )

    async def send_command(
        self,
        command: str,
        params: dict | None = None,
    ) -> DeviceStatus:
        """Simulate sending a command to DummyDeviceWithPool."""
        return DeviceStatus(connected=True, last_command=command)


@pytest.mark.asyncio
async def test_base_device_connect_disconnect_with_pool_and_logger() -> None:
    """Test BaseMonitorDevice connect/disconnect with injected pool and logger."""
    mock_pool = AsyncMock(spec=BLEConnectionPool)
    mock_logger = MagicMock(spec=logging.Logger)
    dev = DummyDeviceWithPool(
        "AA:BB:CC:DD:EE:FF",
        config=None,
        connection_pool=mock_pool,
        logger=mock_logger,
    )
    await dev.connect()
    mock_logger.info.assert_any_call("Connecting to device %s", "AA:BB:CC:DD:EE:FF")
    mock_pool.connect.assert_awaited_with("AA:BB:CC:DD:EE:FF")
    mock_logger.info.assert_any_call("Connected to device %s", "AA:BB:CC:DD:EE:FF")
    await dev.disconnect()
    mock_logger.info.assert_any_call(
        "Disconnecting from device %s",
        "AA:BB:CC:DD:EE:FF",
    )
    mock_pool.disconnect.assert_awaited_with("AA:BB:CC:DD:EE:FF")
    mock_logger.info.assert_any_call("Disconnected from device %s", "AA:BB:CC:DD:EE:FF")


@pytest.mark.asyncio
async def test_base_device_connect_without_pool_raises() -> None:
    """Test that connect raises if no connection pool is available."""
    dev = DummyDeviceWithPool("AA:BB:CC:DD:EE:FF", config=None, connection_pool=None)
    with pytest.raises(RuntimeError, match="No connection pool available"):
        await dev.connect()


@pytest.mark.asyncio
async def test_base_device_disconnect_without_pool_raises() -> None:
    """Test that disconnect raises if no connection pool is available."""
    dev = DummyDeviceWithPool("AA:BB:CC:DD:EE:FF", config=None, connection_pool=None)
    with pytest.raises(RuntimeError, match="No connection pool available"):
        await dev.disconnect()
