"""Tests for BLEDiscoveryService and BLE device discovery logic."""

import json
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.battery_hawk_driver.base.discovery import BLEDiscoveryService


class DummyConfig:
    """Dummy config for BLEDiscoveryService tests."""

    config_dir = "."


@pytest.fixture
def temp_storage(tmp_path: "Path") -> str:
    """Fixture for temporary storage path for discovered devices."""
    return str(tmp_path.joinpath("discovered_devices.json"))


@pytest.fixture(autouse=True)
def cleanup_storage(temp_storage: str) -> None:
    """Fixture to clean up storage file after each test."""
    if os.path.exists(temp_storage):
        os.remove(temp_storage)


@pytest.mark.asyncio
async def test_scan_for_devices_and_persistence(temp_storage: str) -> None:
    """Test BLEDiscoveryService.scan_for_devices and persistence."""
    fake_device = MagicMock()
    fake_device.address = "AA:BB:CC:DD:EE:FF"
    fake_device.name = "BMTest"
    fake_device.rssi = -60

    # Create mock advertisement data
    fake_advertisement = MagicMock()
    fake_advertisement.service_uuids = ["0000ff01-0000-1000-8000-00805f9b34fb"]
    fake_advertisement.manufacturer_data = {0x0590: b"\x01\x02\x03\x04"}
    fake_advertisement.service_data = {
        "0000ff01-0000-1000-8000-00805f9b34fb": b"\x05\x06\x07\x08",
    }
    fake_advertisement.local_name = "BM6_Test_Device"
    fake_advertisement.tx_power = -12

    async def async_discover(*args: object, **kwargs: object) -> dict:
        """Fake async discover returning a list of fake devices with advertisement data."""
        return {fake_device.address: (fake_device, fake_advertisement)}

    with patch("src.battery_hawk_driver.base.discovery.BleakScanner") as mock_scanner:
        mock_scanner.discover = async_discover
        service = BLEDiscoveryService(DummyConfig(), storage_path=temp_storage)
        devices = await service.scan_for_devices(duration=1)
        assert "AA:BB:CC:DD:EE:FF" in devices

        # Check that advertisement data was captured
        device_info = devices["AA:BB:CC:DD:EE:FF"]
        assert "advertisement_data" in device_info

        adv_data = device_info["advertisement_data"]
        assert adv_data["service_uuids"] == ["0000ff01-0000-1000-8000-00805f9b34fb"]
        assert adv_data["manufacturer_data"] == {"1424": "01020304"}  # 0x0590 = 1424
        assert adv_data["service_data"] == {
            "0000ff01-0000-1000-8000-00805f9b34fb": "05060708",
        }
        assert adv_data["local_name"] == "BM6_Test_Device"
        assert adv_data["tx_power"] == -12

        # Check persistence
        assert os.path.exists(temp_storage)
        # Blocking open is acceptable here for test coverage; no async alternative for file reading in this context.
        with open(temp_storage) as f:  # noqa: ASYNC230
            data = json.load(f)
            assert "AA:BB:CC:DD:EE:FF" in data
            assert "advertisement_data" in data["AA:BB:CC:DD:EE:FF"]


@pytest.mark.asyncio
async def test_scan_for_devices_with_minimal_advertisement_data(
    temp_storage: str,
) -> None:
    """Test scanning with minimal advertisement data."""
    fake_device = MagicMock()
    fake_device.address = "AA:BB:CC:DD:EE:01"
    fake_device.name = "BM2_Test"
    fake_device.rssi = -70

    # Create mock advertisement data with minimal fields
    fake_advertisement = MagicMock()
    fake_advertisement.service_uuids = None
    fake_advertisement.manufacturer_data = None
    fake_advertisement.service_data = None
    fake_advertisement.local_name = None
    fake_advertisement.tx_power = None
    fake_advertisement.platform_data = None

    async def async_discover(*args: object, **kwargs: object) -> dict:
        """Fake async discover returning a list of fake devices with minimal advertisement data."""
        return {fake_device.address: (fake_device, fake_advertisement)}

    with patch("src.battery_hawk_driver.base.discovery.BleakScanner") as mock_scanner:
        mock_scanner.discover = async_discover
        service = BLEDiscoveryService(DummyConfig(), storage_path=temp_storage)
        devices = await service.scan_for_devices(duration=1)
        assert "AA:BB:CC:DD:EE:01" in devices

        # Check that advertisement data was captured (should be empty)
        device_info = devices["AA:BB:CC:DD:EE:01"]
        assert "advertisement_data" in device_info
        assert device_info["advertisement_data"] == {}


@pytest.mark.asyncio
async def test_scan_for_devices_with_none_advertisement_data(temp_storage: str) -> None:
    """Test scanning when advertisement data is None."""
    fake_device = MagicMock()
    fake_device.address = "AA:BB:CC:DD:EE:02"
    fake_device.name = "BM6_Test"
    fake_device.rssi = -50

    async def async_discover(*args: object, **kwargs: object) -> dict:
        """Fake async discover returning a list of fake devices with None advertisement data."""
        return {fake_device.address: (fake_device, None)}

    with patch("src.battery_hawk_driver.base.discovery.BleakScanner") as mock_scanner:
        mock_scanner.discover = async_discover
        service = BLEDiscoveryService(DummyConfig(), storage_path=temp_storage)
        devices = await service.scan_for_devices(duration=1)
        assert "AA:BB:CC:DD:EE:02" in devices

        # Check that advertisement data was captured (should be empty)
        device_info = devices["AA:BB:CC:DD:EE:02"]
        assert "advertisement_data" in device_info
        assert device_info["advertisement_data"] == {}


def test_extract_advertisement_data_with_error() -> None:
    """Test _extract_advertisement_data when an exception occurs."""
    service = BLEDiscoveryService(DummyConfig())

    # Create a mock that will cause an exception during data processing
    fake_advertisement = MagicMock()
    fake_advertisement.service_uuids = ["valid_uuid"]
    fake_advertisement.manufacturer_data = MagicMock()
    fake_advertisement.manufacturer_data.items.side_effect = AttributeError(
        "Test error",
    )
    fake_advertisement.service_data = {"valid_uuid": b"valid_data"}
    fake_advertisement.local_name = "valid_name"
    fake_advertisement.tx_power = -12
    fake_advertisement.platform_data = {"valid": "data"}

    # Accessing private method for test coverage; no public alternative exists.
    result = service._extract_advertisement_data(fake_advertisement)

    assert "error" in result
    assert "Test error" in result["error"]


def test_extract_advertisement_data_with_complete_data() -> None:
    """Test _extract_advertisement_data with complete advertisement data."""
    service = BLEDiscoveryService(DummyConfig())

    # Create mock advertisement data
    fake_advertisement = MagicMock()
    fake_advertisement.service_uuids = [
        "0000ff01-0000-1000-8000-00805f9b34fb",
        "0000ff02-0000-1000-8000-00805f9b34fb",
    ]
    fake_advertisement.manufacturer_data = {
        0x0590: b"\x01\x02\x03\x04",
        0x0591: b"\x05\x06\x07\x08",
    }
    fake_advertisement.service_data = {
        "0000ff01-0000-1000-8000-00805f9b34fb": b"\x09\x0a\x0b\x0c",
        "0000ff02-0000-1000-8000-00805f9b34fb": b"\x0d\x0e\x0f\x10",
    }
    fake_advertisement.local_name = "BM6_Test_Device"
    fake_advertisement.tx_power = -12
    fake_advertisement.platform_data = {"platform": "test"}

    # Accessing private method for test coverage; no public alternative exists.
    result = service._extract_advertisement_data(fake_advertisement)

    assert result["service_uuids"] == [
        "0000ff01-0000-1000-8000-00805f9b34fb",
        "0000ff02-0000-1000-8000-00805f9b34fb",
    ]
    assert result["manufacturer_data"] == {
        "1424": "01020304",
        "1425": "05060708",
    }  # 0x0590=1424, 0x0591=1425
    assert result["service_data"] == {
        "0000ff01-0000-1000-8000-00805f9b34fb": "090a0b0c",
        "0000ff02-0000-1000-8000-00805f9b34fb": "0d0e0f10",
    }
    assert result["local_name"] == "BM6_Test_Device"
    assert result["tx_power"] == -12
    assert result["platform_data"] == "{'platform': 'test'}"


def test_extract_advertisement_data_with_none() -> None:
    """Test _extract_advertisement_data with None advertisement data."""
    service = BLEDiscoveryService(DummyConfig())

    # Accessing private method for test coverage; no public alternative exists.
    result = service._extract_advertisement_data(None)

    assert result == {}


def test_extract_advertisement_data_with_empty_fields() -> None:
    """Test _extract_advertisement_data with empty advertisement fields."""
    service = BLEDiscoveryService(DummyConfig())

    # Create mock advertisement data with empty fields
    fake_advertisement = MagicMock()
    fake_advertisement.service_uuids = []
    fake_advertisement.manufacturer_data = {}
    fake_advertisement.service_data = {}
    fake_advertisement.local_name = ""
    fake_advertisement.tx_power = None
    fake_advertisement.platform_data = None

    # Accessing private method for test coverage; no public alternative exists.
    result = service._extract_advertisement_data(fake_advertisement)

    # Should not include empty fields
    assert "service_uuids" not in result
    assert "manufacturer_data" not in result
    assert "service_data" not in result
    assert "local_name" not in result
    assert "tx_power" not in result
    assert "platform_data" not in result


def test_get_discovered_devices_and_get_device(temp_storage: str) -> None:
    """Test get_discovered_devices and get_device methods."""
    service = BLEDiscoveryService(DummyConfig(), storage_path=temp_storage)
    service.discovered_devices = {
        "11:22:33:44:55:66": {"mac_address": "11:22:33:44:55:66"},
    }
    assert service.get_device("11:22:33:44:55:66") == {
        "mac_address": "11:22:33:44:55:66",
    }
    assert service.get_device("00:00:00:00:00:00") is None
    assert "11:22:33:44:55:66" in service.get_discovered_devices()


def test_filtering_logic(temp_storage: str) -> None:
    """Test _is_potential_battery_monitor logic (accepts all for now)."""
    service = BLEDiscoveryService(DummyConfig(), storage_path=temp_storage)
    dummy_device = MagicMock()
    dummy_device.name = "BMTest"
    # Accept all for now
    # Accessing private method for test coverage; no public alternative exists.
    assert service._is_potential_battery_monitor(dummy_device)


@pytest.mark.asyncio
async def test_bleak_unavailable(temp_storage: str) -> None:
    """Test scan_for_devices when Bleak is unavailable."""
    with patch("src.battery_hawk_driver.base.discovery.BleakScanner", None):
        service = BLEDiscoveryService(DummyConfig(), storage_path=temp_storage)
        result = await service.scan_for_devices(duration=1)
        assert result == {}


@pytest.mark.asyncio
async def test_scan_until_new_device(temp_storage: str) -> None:
    """Test scanning until a new device is found."""
    fake_device1 = MagicMock()
    fake_device1.address = "AA:BB:CC:DD:EE:01"
    fake_device1.name = "BM6-Test1"

    fake_device2 = MagicMock()
    fake_device2.address = "AA:BB:CC:DD:EE:02"
    fake_device2.name = "BM6-Test2"

    fake_advertisement = MagicMock()
    fake_advertisement.rssi = -50

    call_count = 0

    async def async_discover(*args: object, **kwargs: object) -> dict:
        """Fake async discover returning different devices on each call."""
        nonlocal call_count
        if call_count == 0:
            call_count += 1
            return {fake_device1.address: (fake_device1, fake_advertisement)}
        if call_count == 1:
            call_count += 1
            return {fake_device2.address: (fake_device2, fake_advertisement)}
        return {}

    with patch("src.battery_hawk_driver.base.discovery.BleakScanner") as mock_scanner:
        mock_scanner.discover = async_discover
        service = BLEDiscoveryService(
            DummyConfig(),
            storage_path=temp_storage,
            disable_storage=True,
        )

        # First scan should find the first device
        devices = await service.scan_for_devices(
            duration=30,
            scan_until_new_device=True,
            short_timeout=1,
        )

        # Should have found one device
        assert len(devices) == 1
        assert "AA:BB:CC:DD:EE:01" in devices

        # Second scan should find the second device and stop
        devices = await service.scan_for_devices(
            duration=30,
            scan_until_new_device=True,
            short_timeout=1,
        )

        # Should have found both devices
        assert len(devices) == 2
        assert "AA:BB:CC:DD:EE:01" in devices
        assert "AA:BB:CC:DD:EE:02" in devices


@pytest.mark.asyncio
async def test_discover_passes_adapter_kwarg() -> None:
    """Ensure BLEDiscoveryService passes adapter kwarg to BleakScanner.discover when configured."""

    class Cfg:
        def __init__(self) -> None:
            self.config_dir = "."

        def get_config(self, section: str) -> dict:
            assert section == "system"
            return {"bluetooth": {"adapter": "hci1"}}

    async def async_discover(*_args: object, **kwargs: object) -> dict:
        # Assert adapter is threaded through
        assert kwargs.get("adapter") == "hci1"
        return {}

    with patch("src.battery_hawk_driver.base.discovery.BleakScanner") as mock_scanner:
        mock_scanner.discover = async_discover
        service = BLEDiscoveryService(Cfg(), disable_storage=True)
        devices = await service.scan_for_devices(duration=1)
        assert devices == {}


@pytest.mark.asyncio
async def test_discover_adapter_fallback_on_typeerror() -> None:
    """If BleakScanner.discover doesn't accept adapter, we should fall back without it."""

    class Cfg:
        def __init__(self) -> None:
            self.config_dir = "."

        def get_config(self, section: str) -> dict:
            assert section == "system"
            return {"bluetooth": {"adapter": "hci2"}}

    call_log: list[dict] = []

    async def async_discover(*_args: object, **kwargs: object) -> dict:
        call_log.append(kwargs)
        if "adapter" in kwargs:
            raise TypeError("unexpected keyword argument 'adapter'")
        return {}

    with patch("src.battery_hawk_driver.base.discovery.BleakScanner") as mock_scanner:
        mock_scanner.discover = async_discover
        service = BLEDiscoveryService(Cfg(), disable_storage=True)
        devices = await service.scan_for_devices(duration=1)
        assert devices == {}
        # First call attempted with adapter, second without
        assert any("adapter" in k for k in call_log)
        assert any("adapter" not in k for k in call_log)
