"""Tests for CLI scan functionality."""

import io
import os
import subprocess
import sys
from contextlib import redirect_stdout
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from battery_hawk.config.config_manager import ConfigManager
from src.battery_hawk.cli import scan_devices


@pytest.fixture
def temp_config_dir(tmp_path: pytest.TempPathFactory) -> str:
    """Fixture for temporary config directory."""
    return str(tmp_path)


@pytest.fixture(autouse=True)
def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture to clear BATTERYHAWK_ env vars before each test."""
    for k in list(os.environ.keys()):
        if k.startswith("BATTERYHAWK_"):
            monkeypatch.delenv(k, raising=False)


def run_cli(args: list[str], config_dir: str) -> tuple[int, str, str]:
    """Run the CLI as a subprocess and return (exit_code, stdout, stderr)."""
    # subprocess.run is safe here because input is controlled and not untrusted (test context)
    cmd = [sys.executable, "-m", "battery_hawk", "--config-dir", config_dir]
    proc = subprocess.run([*cmd, *args], capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout, proc.stderr


class TestCLIScan:
    """Test suite for CLI scan functionality."""

    @pytest.mark.asyncio
    async def test_scan_devices_no_devices_found(self, temp_config_dir: str) -> None:
        """Test scan when no devices are found."""
        config_manager = ConfigManager(temp_config_dir)

        with patch("src.battery_hawk.cli.BLEDiscoveryService") as mock_discovery:
            mock_service = MagicMock()
            mock_service.scan_for_devices = AsyncMock(return_value={})
            mock_discovery.return_value = mock_service

            result = await scan_devices(
                config_manager,
                5,
                False,
                "table",
                False,
                False,
                None,
            )

            assert result == 0
            mock_service.scan_for_devices.assert_called_once_with(
                5,
                False,
                scan_until_new_device=False,
                short_timeout=None,
            )

    @pytest.mark.asyncio
    async def test_scan_devices_table_format(self, temp_config_dir: str) -> None:
        """Test scan with table format output."""
        config_manager = ConfigManager(temp_config_dir)

        mock_devices = {
            "AA:BB:CC:DD:EE:FF": {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "name": "BM6_Test",
                "rssi": -50,
                "discovered_at": "2025-01-01T12:00:00Z",
                "advertisement_data": {
                    "service_uuids": ["0000ff01-0000-1000-8000-00805f9b34fb"],
                    "manufacturer_data": {"1440": "01020304"},
                    "local_name": "BM6_Test_Device",
                    "tx_power": -12,
                },
            },
        }

        with patch("src.battery_hawk.cli.BLEDiscoveryService") as mock_discovery:
            mock_service = MagicMock()
            mock_service.scan_for_devices = AsyncMock(return_value=mock_devices)
            mock_discovery.return_value = mock_service

            result = await scan_devices(
                config_manager,
                10,
                False,
                "table",
                False,
                False,
                None,
            )

            assert result == 0
            mock_service.scan_for_devices.assert_called_once_with(
                10,
                False,
                scan_until_new_device=False,
                short_timeout=None,
            )

    @pytest.mark.asyncio
    async def test_scan_devices_json_format(self, temp_config_dir: str) -> None:
        """Test scan with JSON format output."""
        config_manager = ConfigManager(temp_config_dir)

        mock_devices = {
            "AA:BB:CC:DD:EE:FF": {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "name": "BM6_Test",
                "rssi": -50,
                "discovered_at": "2025-01-01T12:00:00Z",
                "advertisement_data": {
                    "service_uuids": ["0000ff01-0000-1000-8000-00805f9b34fb"],
                    "manufacturer_data": {"1440": "01020304"},
                    "local_name": "BM6_Test_Device",
                    "tx_power": -12,
                },
            },
        }

        with patch("src.battery_hawk.cli.BLEDiscoveryService") as mock_discovery:
            mock_service = MagicMock()
            mock_service.scan_for_devices = AsyncMock(return_value=mock_devices)
            mock_discovery.return_value = mock_service

            result = await scan_devices(
                config_manager,
                10,
                False,
                "json",
                False,
                False,
                None,
            )

            assert result == 0
            mock_service.scan_for_devices.assert_called_once_with(
                10,
                False,
                scan_until_new_device=False,
                short_timeout=None,
            )

    @pytest.mark.asyncio
    async def test_scan_devices_with_connect_bm6(self, temp_config_dir: str) -> None:
        """Test scan with connect option for BM6 device."""
        config_manager = ConfigManager(temp_config_dir)

        mock_devices = {
            "AA:BB:CC:DD:EE:FF": {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "name": "BM6_Test",
                "rssi": -50,
                "discovered_at": "2025-01-01T12:00:00Z",
                "advertisement_data": {
                    "service_uuids": ["0000ff01-0000-1000-8000-00805f9b34fb"],
                    "manufacturer_data": {"1440": "01020304"},
                    "local_name": "BM6_Test_Device",
                    "tx_power": -12,
                },
            },
        }

        with (
            patch("src.battery_hawk.cli.BLEDiscoveryService") as mock_discovery,
            patch("src.battery_hawk.cli.BLEConnectionPool") as mock_pool,
            patch("src.battery_hawk.cli.DeviceFactory") as mock_factory,
        ):
            mock_service = MagicMock()
            mock_service.scan_for_devices = AsyncMock(return_value=mock_devices)
            mock_discovery.return_value = mock_service

            mock_connection_pool = MagicMock()
            mock_pool.return_value = mock_connection_pool

            mock_device_factory = MagicMock()
            mock_factory.return_value = mock_device_factory

            # Mock device creation and connection
            mock_device = MagicMock()
            mock_device.connect = AsyncMock()
            mock_device.read_data = AsyncMock(
                return_value={
                    "voltage": 12.5,
                    "current": -1.2,
                    "state_of_charge": 85.0,
                    "temperature": 23.5,
                },
            )
            mock_device.get_device_info = AsyncMock(
                return_value={
                    "model": "BM6",
                    "firmware": "1.0.0",
                },
            )
            mock_device.disconnect = AsyncMock()

            mock_device_factory.create_device.return_value = mock_device

            result = await scan_devices(
                config_manager,
                10,
                True,
                "table",
                False,
                False,
                None,
            )

            assert result == 0
            mock_service.scan_for_devices.assert_called_once_with(
                10,
                False,
                scan_until_new_device=False,
                short_timeout=None,
            )
            mock_device.connect.assert_called_once()
            mock_device.read_data.assert_called_once()
            mock_device.get_device_info.assert_called_once()
            mock_device.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_scan_devices_with_connect_bm2(self, temp_config_dir: str) -> None:
        """Test scan with connect option for BM2 device."""
        config_manager = ConfigManager(temp_config_dir)

        mock_devices = {
            "AA:BB:CC:DD:EE:FF": {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "name": "BM2_Test",
                "rssi": -50,
                "discovered_at": "2025-01-01T12:00:00Z",
                "advertisement_data": {
                    "service_uuids": ["0000ff02-0000-1000-8000-00805f9b34fb"],
                    "manufacturer_data": {"1441": "05060708"},
                    "local_name": "BM2_Test_Device",
                    "tx_power": -10,
                },
            },
        }

        with (
            patch("src.battery_hawk.cli.BLEDiscoveryService") as mock_discovery,
            patch("src.battery_hawk.cli.BLEConnectionPool") as mock_pool,
            patch("src.battery_hawk.cli.DeviceFactory") as mock_factory,
        ):
            mock_service = MagicMock()
            mock_service.scan_for_devices = AsyncMock(return_value=mock_devices)
            mock_discovery.return_value = mock_service

            mock_connection_pool = MagicMock()
            mock_pool.return_value = mock_connection_pool

            mock_device_factory = MagicMock()
            mock_factory.return_value = mock_device_factory

            # Mock device creation and connection
            mock_device = MagicMock()
            mock_device.connect = AsyncMock()
            mock_device.read_data = AsyncMock(
                return_value={
                    "voltage": 12.3,
                    "current": -0.8,
                    "state_of_charge": 90.0,
                    "temperature": 22.0,
                },
            )
            mock_device.get_device_info = AsyncMock(
                return_value={
                    "model": "BM2",
                    "firmware": "1.1.0",
                },
            )
            mock_device.disconnect = AsyncMock()

            mock_device_factory.create_device.return_value = mock_device

            result = await scan_devices(
                config_manager,
                10,
                True,
                "table",
                False,
                False,
                None,
            )

            assert result == 0
            mock_service.scan_for_devices.assert_called_once_with(
                10,
                False,
                scan_until_new_device=False,
                short_timeout=None,
            )
            mock_device.connect.assert_called_once()
            mock_device.read_data.assert_called_once()
            mock_device.get_device_info.assert_called_once()
            mock_device.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_scan_devices_connection_error(self, temp_config_dir: str) -> None:
        """Test scan when device connection fails."""
        config_manager = ConfigManager(temp_config_dir)

        mock_devices = {
            "AA:BB:CC:DD:EE:FF": {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "name": "BM6_Test",
                "rssi": -50,
                "discovered_at": "2025-01-01T12:00:00Z",
                "advertisement_data": {
                    "service_uuids": ["0000ff01-0000-1000-8000-00805f9b34fb"],
                    "manufacturer_data": {"1440": "01020304"},
                },
            },
        }

        with (
            patch("src.battery_hawk.cli.BLEDiscoveryService") as mock_discovery,
            patch("src.battery_hawk.cli.BLEConnectionPool") as mock_pool,
            patch("src.battery_hawk.cli.DeviceFactory") as mock_factory,
        ):
            mock_service = MagicMock()
            mock_service.scan_for_devices = AsyncMock(return_value=mock_devices)
            mock_discovery.return_value = mock_service

            mock_connection_pool = MagicMock()
            mock_pool.return_value = mock_connection_pool

            mock_device_factory = MagicMock()
            mock_factory.return_value = mock_device_factory

            # Mock device creation but connection fails
            mock_device = MagicMock()
            mock_device.connect = AsyncMock(side_effect=Exception("Connection failed"))
            mock_device_factory.create_device.return_value = mock_device

            result = await scan_devices(
                config_manager,
                10,
                True,
                "table",
                False,
                False,
                None,
            )

            assert result == 0
            mock_service.scan_for_devices.assert_called_once_with(
                10,
                False,
                scan_until_new_device=False,
                short_timeout=None,
            )
            mock_device.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_scan_devices_unknown_device_type(self, temp_config_dir: str) -> None:
        """Test scan with unknown device type."""
        config_manager = ConfigManager(temp_config_dir)

        mock_devices = {
            "AA:BB:CC:DD:EE:FF": {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "name": "Unknown_Device",
                "rssi": -50,
                "discovered_at": "2025-01-01T12:00:00Z",
                "advertisement_data": {
                    "service_uuids": ["0000ff99-0000-1000-8000-00805f9b34fb"],
                    "manufacturer_data": {"9999": "99999999"},
                },
            },
        }

        with (
            patch("src.battery_hawk.cli.BLEDiscoveryService") as mock_discovery,
            patch("src.battery_hawk.cli.BLEConnectionPool") as mock_pool,
            patch("src.battery_hawk.cli.DeviceFactory") as mock_factory,
        ):
            mock_service = MagicMock()
            mock_service.scan_for_devices = AsyncMock(return_value=mock_devices)
            mock_discovery.return_value = mock_service

            mock_connection_pool = MagicMock()
            mock_pool.return_value = mock_connection_pool

            mock_device_factory = MagicMock()
            mock_factory.return_value = mock_device_factory

            # Mock device factory to return None for unknown device
            mock_device_factory.create_device_from_advertisement.return_value = None

            result = await scan_devices(
                config_manager,
                10,
                True,
                "table",
                False,
                False,
                None,
            )

            assert result == 0
            mock_service.scan_for_devices.assert_called_once_with(
                10,
                False,
                scan_until_new_device=False,
                short_timeout=None,
            )
            mock_device_factory.create_device_from_advertisement.assert_called_once()

    @pytest.mark.asyncio
    async def test_scan_devices_with_empty_advertisement_data(
        self,
        temp_config_dir: str,
    ) -> None:
        """Test scan with empty advertisement data."""
        config_manager = ConfigManager(temp_config_dir)

        mock_devices = {
            "AA:BB:CC:DD:EE:FF": {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "name": "BM6_Test",
                "rssi": -50,
                "discovered_at": "2025-01-01T12:00:00Z",
                "advertisement_data": {},
            },
        }

        with patch("src.battery_hawk.cli.BLEDiscoveryService") as mock_discovery:
            mock_service = MagicMock()
            mock_service.scan_for_devices = AsyncMock(return_value=mock_devices)
            mock_discovery.return_value = mock_service

            result = await scan_devices(
                config_manager,
                10,
                False,
                "table",
                False,
                False,
                None,
            )

            assert result == 0
            mock_service.scan_for_devices.assert_called_once_with(
                10,
                False,
                scan_until_new_device=False,
                short_timeout=None,
            )

    @pytest.mark.asyncio
    async def test_scan_devices_with_complete_advertisement_data(
        self,
        temp_config_dir: str,
    ) -> None:
        """Test scan with complete advertisement data including all fields."""
        config_manager = ConfigManager(temp_config_dir)

        mock_devices = {
            "AA:BB:CC:DD:EE:FF": {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "name": "BM6_Test",
                "rssi": -50,
                "discovered_at": "2025-01-01T12:00:00Z",
                "advertisement_data": {
                    "service_uuids": [
                        "0000ff01-0000-1000-8000-00805f9b34fb",
                        "0000ff02-0000-1000-8000-00805f9b34fb",
                    ],
                    "manufacturer_data": {
                        "1440": "01020304",
                        "1441": "05060708",
                    },
                    "service_data": {
                        "0000ff01-0000-1000-8000-00805f9b34fb": "090a0b0c",
                        "0000ff02-0000-1000-8000-00805f9b34fb": "0d0e0f10",
                    },
                    "local_name": "BM6_Test_Device",
                    "tx_power": -12,
                    "platform_data": "test_platform_data",
                },
            },
        }

        with patch("src.battery_hawk.cli.BLEDiscoveryService") as mock_discovery:
            mock_service = MagicMock()
            mock_service.scan_for_devices = AsyncMock(return_value=mock_devices)
            mock_discovery.return_value = mock_service

            result = await scan_devices(
                config_manager,
                10,
                False,
                "table",
                False,
                False,
                None,
            )

            assert result == 0
            mock_service.scan_for_devices.assert_called_once_with(
                10,
                False,
                scan_until_new_device=False,
                short_timeout=None,
            )

    @pytest.mark.asyncio
    async def test_scan_devices_advertisement_data_display(
        self,
        temp_config_dir: str,
    ) -> None:
        """Test that advertisement data is properly displayed in CLI output."""
        config_manager = ConfigManager(temp_config_dir)

        mock_devices = {
            "AA:BB:CC:DD:EE:FF": {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "name": "BM6_Test",
                "rssi": -50,
                "discovered_at": "2025-01-01T12:00:00Z",
                "advertisement_data": {
                    "service_uuids": [
                        "0000ff01-0000-1000-8000-00805f9b34fb",
                        "0000ff02-0000-1000-8000-00805f9b34fb",
                    ],
                    "manufacturer_data": {
                        "1424": "01020304",
                        "1425": "05060708",
                    },
                    "service_data": {
                        "0000ff01-0000-1000-8000-00805f9b34fb": "090a0b0c",
                        "0000ff02-0000-1000-8000-00805f9b34fb": "0d0e0f10",
                    },
                    "local_name": "BM6_Test_Device",
                    "tx_power": -12,
                    "platform_data": "test_platform_data",
                },
            },
        }

        with patch("src.battery_hawk.cli.BLEDiscoveryService") as mock_discovery:
            mock_service = MagicMock()
            mock_service.scan_for_devices = AsyncMock(return_value=mock_devices)
            mock_discovery.return_value = mock_service

            # Capture stdout to verify advertisement data is displayed
            f = io.StringIO()
            with redirect_stdout(f):
                result = await scan_devices(
                    config_manager,
                    10,
                    False,
                    "table",
                    False,
                    False,
                    None,
                )

            output = f.getvalue()

            assert result == 0
            mock_service.scan_for_devices.assert_called_once_with(
                10,
                False,
                scan_until_new_device=False,
                short_timeout=None,
            )

            # Verify advertisement data is displayed
            assert "Advertisement Data:" in output
            assert "Service UUIDs:" in output
            assert "0000ff01-0000-1000-8000-00805f9b34fb" in output
            assert "0000ff02-0000-1000-8000-00805f9b34fb" in output
            assert "Manufacturer Data:" in output
            assert "Company ID 1424: 01020304" in output
            assert "Company ID 1425: 05060708" in output
            assert "Service Data:" in output
            assert "0000ff01-0000-1000-8000-00805f9b34fb: 090a0b0c" in output
            assert "0000ff02-0000-1000-8000-00805f9b34fb: 0d0e0f10" in output
            assert "Local Name: BM6_Test_Device" in output
            assert "TX Power: -12 dBm" in output
            assert "Platform Data: test_platform_data" in output


def test_cli_scan_command_basic(temp_config_dir: str) -> None:
    """Test basic CLI scan command."""
    exit_code, _stdout, _stderr = run_cli(["scan"], temp_config_dir)
    assert exit_code == 0


def test_cli_scan_command_with_duration(temp_config_dir: str) -> None:
    """Test CLI scan command with custom duration."""
    exit_code, _stdout, _stderr = run_cli(["scan", "--duration", "5"], temp_config_dir)
    assert exit_code == 0


def test_cli_scan_command_json_format(temp_config_dir: str) -> None:
    """Test CLI scan command with JSON format."""
    exit_code, _stdout, _stderr = run_cli(["scan", "--format", "json"], temp_config_dir)
    assert exit_code == 0


def test_cli_scan_command_with_connect(temp_config_dir: str) -> None:
    """Test CLI scan command with connect option."""
    exit_code, _stdout, _stderr = run_cli(["scan", "--connect"], temp_config_dir)
    assert exit_code == 0


def test_cli_scan_command_help(temp_config_dir: str) -> None:
    """Test CLI scan command help."""
    exit_code, _stdout, _stderr = run_cli(["scan", "--help"], temp_config_dir)
    assert exit_code == 0
