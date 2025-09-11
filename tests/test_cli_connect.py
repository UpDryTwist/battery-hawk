"""Tests for CLI connect functionality."""

import io
import os
import subprocess
import sys
from contextlib import redirect_stdout
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from battery_hawk.config.config_manager import ConfigManager
from src.battery_hawk.cli import _auto_detect_device_type, connect_to_device
from src.battery_hawk_driver.base.device_factory import DeviceFactory
from src.battery_hawk_driver.base.protocol import BatteryInfo


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
    """Run CLI command and return exit code, stdout, stderr."""
    # subprocess.run is safe here because input is controlled and not untrusted (test context)
    env = os.environ.copy()
    env["BATTERYHAWK_SYSTEM_BLUETOOTH_TEST_MODE"] = "true"
    cmd = [sys.executable, "-m", "battery_hawk", "--config-dir", config_dir]
    result = subprocess.run(
        [*cmd, *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


class TestCLIConnect:
    """Test cases for CLI connect functionality."""

    @pytest.mark.asyncio
    async def test_connect_to_device_success_bm6(self, temp_config_dir: str) -> None:
        """Test successful connection to BM6 device."""
        config_manager = ConfigManager(temp_config_dir)

        with (
            patch("src.battery_hawk.cli.BLEConnectionPool") as mock_pool,
            patch("src.battery_hawk.cli.DeviceFactory") as mock_factory,
        ):
            mock_connection_pool = MagicMock()
            mock_pool.return_value = mock_connection_pool

            mock_device_factory = MagicMock()
            mock_factory.return_value = mock_device_factory

            # Mock device creation and connection
            mock_device = MagicMock()
            mock_device.device_address = "AA:BB:CC:DD:EE:FF"
            mock_device.device_type = "BM6"
            mock_device.protocol_version = "1.0"
            mock_device.capabilities = {
                "read_voltage",
                "read_current",
                "read_temperature",
            }
            mock_device.connect = AsyncMock()
            mock_device.disconnect = AsyncMock()
            mock_device.get_device_info = AsyncMock(
                return_value={"device_name": "BM6_Test"},
            )

            # Mock BatteryInfo object
            mock_battery_info = BatteryInfo(
                voltage=12.5,
                current=-1.2,
                temperature=25.0,
                state_of_charge=85.0,
                capacity=50.0,
                cycles=10,
                timestamp=1234567890.0,
                extra={"device_type": "BM6"},
            )
            mock_device.read_data = AsyncMock(return_value=mock_battery_info)
            mock_device.latest_data = {"voltage": 12.5, "current": -1.2}

            mock_device_factory.create_device.return_value = mock_device

            result = await connect_to_device(
                config_manager,
                "AA:BB:CC:DD:EE:FF",
                "BM6",
                30,
                3,
                2.0,
                "table",
            )

            assert result == 0

    @pytest.mark.asyncio
    async def test_connect_to_device_success_bm2(self, temp_config_dir: str) -> None:
        """Test successful connection to BM2 device."""
        config_manager = ConfigManager(temp_config_dir)

        with (
            patch("src.battery_hawk.cli.BLEConnectionPool") as mock_pool,
            patch("src.battery_hawk.cli.DeviceFactory") as mock_factory,
        ):
            mock_connection_pool = MagicMock()
            mock_pool.return_value = mock_connection_pool

            mock_device_factory = MagicMock()
            mock_factory.return_value = mock_device_factory

            # Mock device creation and connection
            mock_device = MagicMock()
            mock_device.device_address = "AA:BB:CC:DD:EE:FF"
            mock_device.device_type = "BM2"
            mock_device.protocol_version = "1.0"
            mock_device.capabilities = {"read_voltage", "read_current"}
            mock_device.connect = AsyncMock()
            mock_device.disconnect = AsyncMock()
            mock_device.get_device_info = AsyncMock(
                return_value={"device_name": "BM2_Test"},
            )

            # Mock BatteryInfo object
            mock_battery_info = BatteryInfo(
                voltage=12.3,
                current=-0.8,
                temperature=24.0,
                state_of_charge=80.0,
                capacity=45.0,
                cycles=5,
                timestamp=1234567890.0,
                extra={"device_type": "BM2"},
            )
            mock_device.read_data = AsyncMock(return_value=mock_battery_info)
            mock_device.latest_data = {"voltage": 12.3, "current": -0.8}

            mock_device_factory.create_device.return_value = mock_device

            result = await connect_to_device(
                config_manager,
                "AA:BB:CC:DD:EE:FF",
                "BM2",
                30,
                3,
                2.0,
                "table",
            )

            assert result == 0

    @pytest.mark.asyncio
    async def test_connect_to_device_auto_detect_success(
        self,
        temp_config_dir: str,
    ) -> None:
        """Test successful connection with auto-detection."""
        config_manager = ConfigManager(temp_config_dir)

        with (
            patch("src.battery_hawk.cli.BLEConnectionPool") as mock_pool,
            patch("src.battery_hawk.cli.DeviceFactory") as mock_factory,
            patch("src.battery_hawk.cli.BLEDiscoveryService") as mock_discovery,
        ):
            mock_connection_pool = MagicMock()
            mock_pool.return_value = mock_connection_pool

            mock_device_factory = MagicMock()
            mock_factory.return_value = mock_device_factory

            # Mock discovery service
            mock_discovery_service = MagicMock()
            mock_discovery_service.scan_for_devices = AsyncMock(
                return_value={
                    "AA:BB:CC:DD:EE:FF": {
                        "name": "BM6_Test",
                        "advertisement_data": {
                            "service_uuids": ["0000ff00-0000-1000-8000-00805f9b34fb"],
                            "manufacturer_data": b"BM6",
                        },
                    },
                },
            )
            mock_discovery.return_value = mock_discovery_service

            # Mock auto-detection
            mock_device_factory.auto_detect_device_type.return_value = "BM6"

            # Mock device creation and connection
            mock_device = MagicMock()
            mock_device.device_address = "AA:BB:CC:DD:EE:FF"
            mock_device.device_type = "BM6"
            mock_device.protocol_version = "1.0"
            mock_device.capabilities = {
                "read_voltage",
                "read_current",
                "read_temperature",
            }
            mock_device.connect = AsyncMock()
            mock_device.disconnect = AsyncMock()
            mock_device.get_device_info = AsyncMock(
                return_value={"device_name": "BM6_Test"},
            )

            # Mock BatteryInfo object
            mock_battery_info = BatteryInfo(
                voltage=12.5,
                current=-1.2,
                temperature=25.0,
                state_of_charge=85.0,
                capacity=50.0,
                cycles=10,
                timestamp=1234567890.0,
                extra={"device_type": "BM6"},
            )
            mock_device.read_data = AsyncMock(return_value=mock_battery_info)
            mock_device.latest_data = {"voltage": 12.5, "current": -1.2}

            mock_device_factory.create_device.return_value = mock_device

            result = await connect_to_device(
                config_manager,
                "AA:BB:CC:DD:EE:FF",
                "auto",
                30,
                3,
                2.0,
                "table",
            )

            assert result == 0

    @pytest.mark.asyncio
    async def test_connect_to_device_auto_detect_failure(
        self,
        temp_config_dir: str,
    ) -> None:
        """Test connection failure when auto-detection fails."""
        config_manager = ConfigManager(temp_config_dir)

        with (
            patch("src.battery_hawk.cli.BLEConnectionPool") as mock_pool,
            patch("src.battery_hawk.cli.DeviceFactory") as mock_factory,
            patch("src.battery_hawk.cli.BLEDiscoveryService") as mock_discovery,
        ):
            mock_connection_pool = MagicMock()
            mock_pool.return_value = mock_connection_pool

            mock_device_factory = MagicMock()
            mock_factory.return_value = mock_device_factory

            # Mock discovery service
            mock_discovery_service = MagicMock()
            mock_discovery_service.scan_for_devices = AsyncMock(return_value={})
            mock_discovery.return_value = mock_discovery_service

            # Mock auto-detection failure
            mock_device_factory.auto_detect_device_type.return_value = None

            result = await connect_to_device(
                config_manager,
                "AA:BB:CC:DD:EE:FF",
                "auto",
                30,
                3,
                2.0,
                "table",
            )

            assert result == 1

    @pytest.mark.asyncio
    async def test_connect_to_device_invalid_device_type(
        self,
        temp_config_dir: str,
    ) -> None:
        """Test connection failure with invalid device type."""
        config_manager = ConfigManager(temp_config_dir)

        result = await connect_to_device(
            config_manager,
            "AA:BB:CC:DD:EE:FF",
            "INVALID",
            30,
            3,
            2.0,
            "table",
        )

        assert result == 1

    @pytest.mark.asyncio
    async def test_connect_to_device_connection_timeout(
        self,
        temp_config_dir: str,
    ) -> None:
        """Test connection timeout handling."""
        config_manager = ConfigManager(temp_config_dir)

        with (
            patch("src.battery_hawk.cli.BLEConnectionPool") as mock_pool,
            patch("src.battery_hawk.cli.DeviceFactory") as mock_factory,
        ):
            mock_connection_pool = MagicMock()
            mock_pool.return_value = mock_connection_pool

            mock_device_factory = MagicMock()
            mock_factory.return_value = mock_device_factory

            # Mock device creation with connection timeout
            mock_device = MagicMock()
            mock_device.connect = AsyncMock(side_effect=Exception("Connection timeout"))
            mock_device.disconnect = AsyncMock()

            mock_device_factory.create_device.return_value = mock_device

            result = await connect_to_device(
                config_manager,
                "AA:BB:CC:DD:EE:FF",
                "BM6",
                1,  # Short timeout
                1,  # No retries
                0.1,  # Short delay
                "table",
            )

            assert result == 1

    @pytest.mark.asyncio
    async def test_connect_to_device_json_output(self, temp_config_dir: str) -> None:
        """Test connection with JSON output format."""
        config_manager = ConfigManager(temp_config_dir)

        with (
            patch("src.battery_hawk.cli.BLEConnectionPool") as mock_pool,
            patch("src.battery_hawk.cli.DeviceFactory") as mock_factory,
        ):
            mock_connection_pool = MagicMock()
            mock_pool.return_value = mock_connection_pool

            mock_device_factory = MagicMock()
            mock_factory.return_value = mock_device_factory

            # Mock device creation and connection
            mock_device = MagicMock()
            mock_device.device_address = "AA:BB:CC:DD:EE:FF"
            mock_device.device_type = "BM6"
            mock_device.protocol_version = "1.0"
            mock_device.capabilities = {"read_voltage", "read_current"}
            mock_device.connect = AsyncMock()
            mock_device.disconnect = AsyncMock()
            mock_device.get_device_info = AsyncMock(
                return_value={"device_name": "BM6_Test"},
            )

            # Mock BatteryInfo object
            mock_battery_info = BatteryInfo(
                voltage=12.5,
                current=1.2,
                temperature=25.0,
                state_of_charge=85.0,
                capacity=50.0,
                cycles=10,
                timestamp=1234567890.0,
                extra={"device_type": "BM6"},
            )
            mock_device.read_data = AsyncMock(return_value=mock_battery_info)
            mock_device.latest_data = {"voltage": 12.5}

            mock_device_factory.create_device.return_value = mock_device

            # Capture stdout to check JSON output
            with redirect_stdout(io.StringIO()) as captured_output:
                result = await connect_to_device(
                    config_manager,
                    "AA:BB:CC:DD:EE:FF",
                    "BM6",
                    30,
                    3,
                    2.0,
                    "json",
                )

            assert result == 0
            output = captured_output.getvalue()
            assert '"mac_address": "AA:BB:CC:DD:EE:FF"' in output
            assert '"device_type": "BM6"' in output
            assert '"voltage": 12.5' in output

    @pytest.mark.asyncio
    async def test_connect_to_device_retry_logic(self, temp_config_dir: str) -> None:
        """Test connection retry logic."""
        config_manager = ConfigManager(temp_config_dir)

        with (
            patch("src.battery_hawk.cli.BLEConnectionPool") as mock_pool,
            patch("src.battery_hawk.cli.DeviceFactory") as mock_factory,
        ):
            mock_connection_pool = MagicMock()
            mock_pool.return_value = mock_connection_pool

            mock_device_factory = MagicMock()
            mock_factory.return_value = mock_device_factory

            # Mock device creation and connection with retries
            mock_device = MagicMock()
            mock_device.device_address = "AA:BB:CC:DD:EE:FF"
            mock_device.device_type = "BM6"
            mock_device.protocol_version = "1.0"
            mock_device.capabilities = {"read_voltage", "read_current"}
            mock_device.disconnect = AsyncMock()

            # First two attempts fail, third succeeds
            mock_device.connect = AsyncMock(
                side_effect=[
                    Exception("Connection failed"),
                    Exception("Connection failed"),
                    None,
                ],
            )
            mock_device.get_device_info = AsyncMock(
                return_value={"device_name": "BM6_Test"},
            )

            # Mock BatteryInfo object
            mock_battery_info = BatteryInfo(
                voltage=12.5,
                current=1.2,
                temperature=25.0,
                state_of_charge=85.0,
                capacity=50.0,
                cycles=10,
                timestamp=1234567890.0,
                extra={"device_type": "BM6"},
            )
            mock_device.read_data = AsyncMock(return_value=mock_battery_info)
            mock_device.latest_data = {"voltage": 12.5}

            mock_device_factory.create_device.return_value = mock_device

            result = await connect_to_device(
                config_manager,
                "AA:BB:CC:DD:EE:FF",
                "BM6",
                30,
                3,  # 3 retry attempts
                0.1,  # Short delay for testing
                "table",
            )

            assert result == 0

    @pytest.mark.asyncio
    async def test_auto_detect_device_type_by_name(self, temp_config_dir: str) -> None:
        """Test auto-detection of device type based on device name."""
        config_manager = ConfigManager(temp_config_dir)

        with (
            patch("src.battery_hawk.cli.BLEConnectionPool") as mock_pool,
            patch("src.battery_hawk.cli.DeviceFactory") as mock_factory,
            patch("src.battery_hawk.cli.BLEDiscoveryService") as mock_discovery,
        ):
            mock_connection_pool = MagicMock()
            mock_pool.return_value = mock_connection_pool

            mock_device_factory = MagicMock()
            mock_factory.return_value = mock_device_factory

            # Mock discovery service with different device names
            mock_discovery_service = MagicMock()
            mock_discovery_service.scan_for_devices = AsyncMock(
                return_value={
                    "AA:BB:CC:DD:EE:FF": {
                        "name": "BM6_Battery_Monitor",
                        "advertisement_data": {
                            "service_uuids": ["0000ff00-0000-1000-8000-00805f9b34fb"],
                            "manufacturer_data": b"BM6",
                        },
                    },
                },
            )
            mock_discovery.return_value = mock_discovery_service

            # Mock DeviceFactory auto-detection to return None (simulating fallback)
            mock_device_factory.auto_detect_device_type.return_value = None

            # Test BM6 detection
            result = await _auto_detect_device_type(
                "AA:BB:CC:DD:EE:FF",
                mock_device_factory,
                config_manager,
            )
            assert result == "BM6"

            # Test BM2 detection
            mock_discovery_service.scan_for_devices = AsyncMock(
                return_value={
                    "AA:BB:CC:DD:EE:FF": {
                        "name": "BM2_Battery_Monitor",
                        "advertisement_data": {
                            "service_uuids": ["0000ff00-0000-1000-8000-00805f9b34fb"],
                            "manufacturer_data": b"BM2",
                        },
                    },
                },
            )
            result = await _auto_detect_device_type(
                "AA:BB:CC:DD:EE:FF",
                mock_device_factory,
                config_manager,
            )
            assert result == "BM2"

            # Test case-insensitive detection
            mock_discovery_service.scan_for_devices = AsyncMock(
                return_value={
                    "AA:BB:CC:DD:EE:FF": {
                        "name": "bm6_test_device",
                        "advertisement_data": {},
                    },
                },
            )
            result = await _auto_detect_device_type(
                "AA:BB:CC:DD:EE:FF",
                mock_device_factory,
                config_manager,
            )
            assert result == "BM6"

            # Test no detection for unknown device
            mock_discovery_service.scan_for_devices = AsyncMock(
                return_value={
                    "AA:BB:CC:DD:EE:FF": {
                        "name": "Unknown_Device",
                        "advertisement_data": {},
                    },
                },
            )
            result = await _auto_detect_device_type(
                "AA:BB:CC:DD:EE:FF",
                mock_device_factory,
                config_manager,
            )
            assert result is None


def test_cli_connect_command_basic(temp_config_dir: str) -> None:
    """Test basic connect command."""
    exit_code, stdout, _stderr = run_cli(
        ["connect", "--device-type", "BM6", "AA:BB:CC:DD:EE:FF"],
        temp_config_dir,
    )
    # Should succeed with mock data implementation
    assert exit_code == 0
    assert "Device Information" in stdout


def test_cli_connect_command_with_device_type(temp_config_dir: str) -> None:
    """Test connect command with device type."""
    exit_code, stdout, _stderr = run_cli(
        ["connect", "--device-type", "BM6", "AA:BB:CC:DD:EE:FF"],
        temp_config_dir,
    )
    # Should succeed with mock data implementation
    assert exit_code == 0
    assert "Device Information" in stdout


def test_cli_connect_command_with_timeout(temp_config_dir: str) -> None:
    """Test connect command with timeout."""
    exit_code, stdout, _stderr = run_cli(
        ["connect", "--device-type", "BM6", "--timeout", "10", "AA:BB:CC:DD:EE:FF"],
        temp_config_dir,
    )
    # Should succeed with mock data implementation
    assert exit_code == 0
    assert "Device Information" in stdout


def test_cli_connect_command_with_retry_options(temp_config_dir: str) -> None:
    """Test connect command with retry options."""
    exit_code, stdout, _stderr = run_cli(
        [
            "connect",
            "--device-type",
            "BM6",
            "--retry-attempts",
            "5",
            "--retry-delay",
            "1.0",
            "AA:BB:CC:DD:EE:FF",
        ],
        temp_config_dir,
    )
    # Should succeed with mock data implementation
    assert exit_code == 0
    assert "Device Information" in stdout


def test_cli_connect_command_json_format(temp_config_dir: str) -> None:
    """Test connect command with JSON format."""
    exit_code, stdout, _stderr = run_cli(
        ["connect", "--device-type", "BM6", "--format", "json", "AA:BB:CC:DD:EE:FF"],
        temp_config_dir,
    )
    # Should succeed with mock data implementation
    assert exit_code == 0
    assert '"mac_address"' in stdout


def test_cli_connect_command_help(temp_config_dir: str) -> None:
    """Test connect command help."""
    exit_code, stdout, _stderr = run_cli(["connect", "--help"], temp_config_dir)
    assert exit_code == 0
    assert "Connect to a specific BM6 or BM2 device by MAC address" in stdout


class TestDeviceFactoryAutoDetection:
    """Test DeviceFactory auto-detection functionality."""

    def test_device_factory_auto_detection_by_name(self) -> None:
        """Test DeviceFactory auto-detection based on device name."""
        # Create a mock connection pool
        mock_connection_pool = MagicMock()
        factory = DeviceFactory(mock_connection_pool)

        # Test BM6 detection
        advertisement_data = {"name": "BM6_Battery_Monitor"}
        result = factory.auto_detect_device_type(advertisement_data)
        assert result == "BM6"

        # Test BM2 detection
        advertisement_data = {"name": "BM2_Battery_Monitor"}
        result = factory.auto_detect_device_type(advertisement_data)
        assert result == "BM2"

        # Test case-insensitive detection
        advertisement_data = {"name": "bm6_test_device"}
        result = factory.auto_detect_device_type(advertisement_data)
        assert result == "BM6"

        # Test with mixed case
        advertisement_data = {"name": "MyBm2Device"}
        result = factory.auto_detect_device_type(advertisement_data)
        assert result == "BM2"

        # Test no detection for unknown device
        advertisement_data = {"name": "Unknown_Device"}
        result = factory.auto_detect_device_type(advertisement_data)
        assert result is None

        # Test with None name
        advertisement_data = {"name": None}
        result = factory.auto_detect_device_type(advertisement_data)
        assert result is None

        # Test with empty name
        advertisement_data = {"name": ""}
        result = factory.auto_detect_device_type(advertisement_data)
        assert result is None
