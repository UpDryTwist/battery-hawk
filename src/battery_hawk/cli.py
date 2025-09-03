# Why does this file exist, and why not put this in `__main__`?
#
# You might be tempted to import things from `__main__` later,
# but that will cause problems: the code will get executed twice:
#
# - When you run `python -m battery_hawk` python will execute
#   `__main__.py` as a script. That means there won't be any
#   `battery_hawk.__main__` in `sys.modules`.
# - When you import `__main__` it will get executed again (as a module) because
#   there's no `battery_hawk.__main__` in `sys.modules`.
"""Module that contains the command line application."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import sys
from typing import TYPE_CHECKING, Any

from battery_hawk.config.config_manager import ConfigManager

if TYPE_CHECKING:
    from battery_hawk_driver.base.connection import BLEConnectionPool
    from battery_hawk_driver.base.device_factory import DeviceFactory
    from battery_hawk_driver.base.protocol import BatteryInfo

from battery_hawk_driver.base.connection import BLEConnectionPool
from battery_hawk_driver.base.device_factory import DeviceFactory
from battery_hawk_driver.base.discovery import BLEDiscoveryService


def setup_logging(config_manager: ConfigManager) -> None:
    """Set up basic logging configuration."""
    log_level = (
        config_manager.get_config("system").get("logging", {}).get("level", "INFO")
    )

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )


def get_parser() -> argparse.ArgumentParser:
    """
    Return the CLI argument parser with subcommands for config management.

    Returns:
        An argparse parser.
    """
    parser = argparse.ArgumentParser(prog="battery-hawk")
    _ = parser.add_argument(
        "--config-dir",
        type=str,
        default=os.environ.get("BATTERYHAWK_CONFIG_DIR", "/data"),
        help="Directory for configuration files (default: /data or $BATTERYHAWK_CONFIG_DIR)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # show
    show_parser = subparsers.add_parser("show", help="Show a config section or key")
    _ = show_parser.add_argument(
        "section",
        type=str,
        help="Config section (system/devices/vehicles)",
    )
    _ = show_parser.add_argument(
        "key",
        type=str,
        nargs="*",
        help="Optional nested key(s)",
    )

    # set
    set_parser = subparsers.add_parser("set", help="Set a config value")
    _ = set_parser.add_argument(
        "section",
        type=str,
        help="Config section (system/devices/vehicles)",
    )
    _ = set_parser.add_argument(
        "key",
        type=str,
        nargs="+",
        help="Nested key(s) to set (e.g. logging level)",
    )
    _ = set_parser.add_argument("value", type=str, help="Value to set (JSON or string)")

    # save
    save_parser = subparsers.add_parser("save", help="Save a config section to disk")
    _ = save_parser.add_argument("section", type=str, help="Config section to save")

    # list
    _list_parser = subparsers.add_parser("list", help="List all config sections")

    # scan
    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan for BM6 and BM2 battery monitor devices",
        description="Scan for BM6 and BM2 battery monitor devices",
    )
    _ = scan_parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Scan duration in seconds (default: 10)",
    )
    _ = scan_parser.add_argument(
        "--connect",
        action="store_true",
        help="Connect to discovered devices and retrieve information",
    )
    _ = scan_parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table)",
    )
    _ = scan_parser.add_argument(
        "--no-storage",
        action="store_true",
        help="Disable loading from and writing to device storage file",
    )
    _ = scan_parser.add_argument(
        "--scan-until-new",
        action="store_true",
        help="Stop scanning when a new device is found",
    )
    _ = scan_parser.add_argument(
        "--short-timeout",
        type=int,
        help="Timeout for individual scans when using --scan-until-new "
        "(defaults to max of 5 seconds or 10%% of duration)",
    )

    # connect
    connect_parser = subparsers.add_parser(
        "connect",
        help="Connect to a specific device by MAC address",
        description="Connect to a specific BM6 or BM2 device by MAC address, retrieve information, and disconnect",
    )
    _ = connect_parser.add_argument(
        "mac_address",
        type=str,
        help="MAC address of the device to connect to (e.g., AA:BB:CC:DD:EE:FF)",
    )
    _ = connect_parser.add_argument(
        "--device-type",
        type=str,
        choices=["BM6", "BM2", "auto"],
        default="auto",
        help="Device type to use (default: auto-detect)",
    )
    _ = connect_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Connection timeout in seconds (default: 30)",
    )
    _ = connect_parser.add_argument(
        "--retry-attempts",
        type=int,
        default=3,
        help="Number of connection retry attempts (default: 3)",
    )
    _ = connect_parser.add_argument(
        "--retry-delay",
        type=float,
        default=2.0,
        help="Delay between retry attempts in seconds (default: 2.0)",
    )
    _ = connect_parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format for device information (default: table)",
    )

    return parser


def _display_advertisement_data(discovered_devices: dict[str, Any]) -> None:
    """Display advertisement data for discovered devices."""
    print("\nAdvertisement Data:")  # noqa: T201
    print("=" * 80)  # noqa: T201
    for mac, device_info in discovered_devices.items():
        print(f"\nDevice: {mac}")  # noqa: T201
        print(f"  Name: {device_info.get('name', 'Unknown')}")  # noqa: T201

        adv_data = device_info.get("advertisement_data", {})
        if not adv_data:
            print("  Advertisement Data: None")  # noqa: T201
            continue

        # Service UUIDs
        service_uuids = adv_data.get("service_uuids", [])
        if service_uuids:
            print(f"  Service UUIDs: {', '.join(service_uuids)}")  # noqa: T201

        # Manufacturer data
        manufacturer_data = adv_data.get("manufacturer_data", {})
        if manufacturer_data:
            print("  Manufacturer Data:")  # noqa: T201
            for company_id, data in manufacturer_data.items():
                print(f"    Company ID {company_id}: {data}")  # noqa: T201

        # Service data
        service_data = adv_data.get("service_data", {})
        if service_data:
            print("  Service Data:")  # noqa: T201
            for service_uuid, data in service_data.items():
                print(f"    {service_uuid}: {data}")  # noqa: T201

        # Local name
        local_name = adv_data.get("local_name")
        if local_name:
            print(f"  Local Name: {local_name}")  # noqa: T201

        # TX power
        tx_power = adv_data.get("tx_power")
        if tx_power is not None:
            print(f"  TX Power: {tx_power} dBm")  # noqa: T201

        # Platform data
        platform_data = adv_data.get("platform_data")
        if platform_data:
            print(f"  Platform Data: {platform_data}")  # noqa: T201


async def scan_devices(
    config_manager: ConfigManager,
    duration: int,
    connect: bool,
    output_format: str,
    no_storage: bool,
    scan_until_new: bool,
    short_timeout: int | None,
) -> int:
    """
    Scan for BLE battery monitor devices.

    Args:
        config_manager: Configuration manager instance
        duration: Scan duration in seconds
        connect: Whether to connect to devices and retrieve information
        output_format: Output format ('json' or 'table')
        no_storage: Whether to disable loading from and writing to device storage file
        scan_until_new: Whether to stop scanning when a new device is found
        short_timeout: Timeout for individual scans when using scan_until_new

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        discovered_devices = await _perform_scan(
            config_manager,
            duration,
            no_storage,
            scan_until_new,
            short_timeout,
        )

        if not discovered_devices:
            return _handle_no_devices_found(duration, output_format)

        if output_format == "json":
            return await _handle_json_output(
                discovered_devices,
                duration,
                connect,
                config_manager,
            )
        return await _handle_table_output(discovered_devices, connect, config_manager)

    except Exception as e:  # noqa: BLE001
        print(f"Error during device scan: {e}", file=sys.stderr)  # noqa: T201
        return 1


async def _perform_scan(
    config_manager: ConfigManager,
    duration: int,
    no_storage: bool,
    scan_until_new: bool,
    short_timeout: int | None,
) -> dict[str, Any]:
    """Perform the BLE scan and return discovered devices."""
    discovery_service = BLEDiscoveryService(config_manager)

    scan_description = f"Scanning for BM6 and BM2 devices for {duration} seconds"
    if scan_until_new:
        scan_description += " (stopping when new device found)"
    print(f"{scan_description}...")  # noqa: T201

    return await discovery_service.scan_for_devices(
        duration,
        no_storage,
        scan_until_new_device=scan_until_new,
        short_timeout=short_timeout,
    )


def _handle_no_devices_found(duration: int, output_format: str) -> int:
    """Handle the case when no devices are found."""
    if output_format == "json":
        result = {
            "scan_duration": duration,
            "devices_found": 0,
            "devices": {},
        }
        print(json.dumps(result, indent=2))  # noqa: T201
    else:
        print("No devices found.")  # noqa: T201
    return 0


async def _handle_json_output(
    discovered_devices: dict[str, Any],
    duration: int,
    connect: bool,
    config_manager: ConfigManager,
) -> int:
    """Handle JSON format output."""
    result = {
        "scan_duration": duration,
        "devices_found": len(discovered_devices),
        "devices": discovered_devices,
    }
    if connect:
        result["connected_devices"] = await _connect_and_retrieve_info(
            discovered_devices,
            config_manager,
        )
    print(json.dumps(result, indent=2))  # noqa: T201
    return 0


async def _handle_table_output(
    discovered_devices: dict[str, Any],
    connect: bool,
    config_manager: ConfigManager,
) -> int:
    """Handle table format output."""
    _print_device_table(discovered_devices)
    _display_advertisement_data(discovered_devices)

    if connect:
        await _handle_device_connections(discovered_devices, config_manager)

    return 0


def _print_device_table(discovered_devices: dict[str, Any]) -> None:
    """Print the device table."""
    print(f"\nFound {len(discovered_devices)} device(s):")  # noqa: T201
    print("-" * 80)  # noqa: T201
    print(f"{'MAC Address':<18} {'Name':<20} {'RSSI':<8} {'Discovered At'}")  # noqa: T201
    print("-" * 80)  # noqa: T201

    for mac, device_info in discovered_devices.items():
        rssi = device_info.get("rssi", "N/A")
        if rssi is None:
            rssi = "N/A"
        discovered_at = device_info.get("discovered_at", "Unknown")
        name = device_info.get("name", "Unknown")
        print(f"{mac:<18} {name:<20} {rssi:<8} {discovered_at}")  # noqa: T201


async def _handle_device_connections(
    discovered_devices: dict[str, Any],
    config_manager: ConfigManager,
) -> None:
    """Handle device connections and display information."""
    print("\nConnecting to devices and retrieving information...")  # noqa: T201
    connected_info = await _connect_and_retrieve_info(
        discovered_devices,
        config_manager,
    )
    if connected_info:
        _print_connected_device_info(connected_info)


def _print_connected_device_info(connected_info: dict[str, Any]) -> None:
    """Print information about connected devices."""
    print("\nDevice Information:")  # noqa: T201
    print("-" * 80)  # noqa: T201
    for mac, info in connected_info.items():
        print(f"\nDevice: {mac}")  # noqa: T201
        print(f"  Type: {info.get('device_type', 'Unknown')}")  # noqa: T201
        print(f"  Status: {info.get('status', 'Unknown')}")  # noqa: T201
        if "error" in info:
            print(f"  Error: {info['error']}")  # noqa: T201
        elif "data" in info:
            data = info["data"]
            print(f"  Voltage: {getattr(data, 'voltage', 'N/A')}V")  # noqa: T201
            print(f"  Current: {getattr(data, 'current', 'N/A')}A")  # noqa: T201
            print(  # noqa: T201
                f"  State of Charge: {getattr(data, 'state_of_charge', 'N/A')}%",
            )
            print(  # noqa: T201
                f"  Temperature: {getattr(data, 'temperature', 'N/A')}°C",
            )


async def _connect_and_retrieve_info(
    discovered_devices: dict[str, Any],
    config_manager: ConfigManager,
) -> dict[str, Any]:
    """
    Connect to discovered devices and retrieve information.

    Args:
        discovered_devices: Dictionary of discovered devices
        config_manager: Configuration manager instance

    Returns:
        Dictionary of device information
    """
    connected_info = {}

    # Initialize connection pool and device factory
    bluetooth_config = config_manager.get_config("system").get("bluetooth", {})
    test_mode = bluetooth_config.get("test_mode", False) or bluetooth_config.get(
        "test",
        {},
    ).get("mode", False)
    connection_pool = BLEConnectionPool(config_manager, test_mode=test_mode)
    device_factory = DeviceFactory(connection_pool)

    for mac, device_info in discovered_devices.items():
        try:
            # Try to auto-detect device type from advertisement data
            # For now, we'll use a simple heuristic based on device name
            device_name = device_info.get("name", "").upper()
            device_type = None

            if "BM6" in device_name:
                device_type = "BM6"
            elif "BM2" in device_name:
                device_type = "BM2"
            else:
                # Try to create device and let factory auto-detect
                advertisement_data = {
                    "name": device_name,
                    "service_uuids": [],
                    "manufacturer_data": b"",
                }
                device: Any = device_factory.create_device_from_advertisement(
                    mac,
                    advertisement_data,
                )
                if device is not None:
                    device_type = "Unknown"  # Auto-detected but type unknown
                else:
                    connected_info[mac] = {
                        "device_type": "Unknown",
                        "status": "failed",
                        "error": "Could not determine device type",
                    }
                    continue

            if device_type in ["BM6", "BM2"]:
                # Create device and attempt connection
                device = device_factory.create_device(device_type, mac)

                try:
                    await device.connect()
                    # Read device information
                    device_data = await device.read_data()
                    device_info_data = await device.get_device_info()

                    connected_info[mac] = {
                        "device_type": device_type,
                        "status": "connected",
                        "data": device_data,
                        "device_info": device_info_data,
                    }

                    await device.disconnect()

                except Exception as e:  # noqa: BLE001
                    connected_info[mac] = {
                        "device_type": device_type,
                        "status": "failed",
                        "error": str(e),
                    }
            else:
                connected_info[mac] = {
                    "device_type": "Unknown",
                    "status": "skipped",
                    "error": "Unsupported device type",
                }

        except Exception as e:  # noqa: BLE001
            connected_info[mac] = {
                "device_type": "Unknown",
                "status": "failed",
                "error": str(e),
            }

    return connected_info


async def connect_to_device(
    config_manager: ConfigManager,
    mac_address: str,
    device_type: str,
    timeout: int,
    retry_attempts: int,
    retry_delay: float,
    output_format: str,
) -> int:
    """
    Connect to a specific device by MAC address and retrieve information.

    Args:
        config_manager: Configuration manager instance
        mac_address: MAC address of the device to connect to
        device_type: Type of device ('BM6', 'BM2', 'auto')
        timeout: Connection timeout in seconds
        retry_attempts: Number of connection retry attempts
        retry_delay: Delay between retry attempts in seconds
        output_format: Output format ('json' or 'table')

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = logging.getLogger(__name__)

    try:
        # Auto-detect device type if needed
        if device_type == "auto":
            bluetooth_config = config_manager.get_config("system").get("bluetooth", {})
            test_mode = bluetooth_config.get(
                "test_mode",
                False,
            ) or bluetooth_config.get("test", {}).get("mode", False)
            device_factory = DeviceFactory(
                BLEConnectionPool(config_manager, test_mode=test_mode),
            )
            detected_type = await _auto_detect_device_type(
                mac_address,
                device_factory,
                config_manager,
            )
            if detected_type is None:
                logger.error(
                    "Could not auto-detect device type for %s",
                    mac_address,
                )
                return 1
            device_type = detected_type

        # Create device instance
        bluetooth_config = config_manager.get_config("system").get("bluetooth", {})
        test_mode = bluetooth_config.get("test_mode", False) or bluetooth_config.get(
            "test",
            {},
        ).get("mode", False)
        connection_pool = BLEConnectionPool(config_manager, test_mode=test_mode)
        device_factory = DeviceFactory(connection_pool)
        device = device_factory.create_device(device_type, mac_address)

        # Connect and retrieve information
        device_info = await _connect_with_retry(
            device,
            timeout,
            retry_attempts,
            retry_delay,
        )

        if device_info is None:
            logger.error(
                "Failed to connect to device %s after %d attempts",
                mac_address,
                retry_attempts,
            )
            return 1

        # Output device information
        if output_format == "json":
            print(json.dumps(device_info, indent=2))  # noqa: T201
        else:
            _print_device_information(device_info)

    except Exception:
        logger.exception("Error connecting to device %s", mac_address)
        return 1

    return 0


async def _auto_detect_device_type(
    mac_address: str,
    device_factory: DeviceFactory,
    config_manager: ConfigManager,
) -> str | None:
    """
    Auto-detect device type by scanning for the device.

    Args:
        mac_address: MAC address of the device
        device_factory: Device factory instance
        config_manager: Configuration manager instance

    Returns:
        Detected device type or None if not found
    """
    with contextlib.suppress(Exception):
        # Scan for devices to find the target device
        discovery_service = BLEDiscoveryService(config_manager)
        discovered_devices = await discovery_service.scan_for_devices(duration=5)

        if mac_address not in discovered_devices:
            return None

        device_info = discovered_devices[mac_address]
        advertisement_data = device_info.get("advertisement_data", {})

        # Try to auto-detect from advertisement data using DeviceFactory
        detected_type = device_factory.auto_detect_device_type(advertisement_data)
        if detected_type:
            return detected_type

        # Fallback: Check device name directly if DeviceFactory detection failed
        device_name = device_info.get("name", "").upper()
        if "BM6" in device_name:
            return "BM6"
        if "BM2" in device_name:
            return "BM2"

    return None


async def _connect_with_retry(
    device: Any,
    timeout: int,
    retry_attempts: int,
    retry_delay: float,
) -> dict[str, Any] | None:
    """
    Connect to device with retry logic and retrieve information.

    Args:
        device: Device instance to connect to
        timeout: Connection timeout in seconds
        retry_attempts: Number of connection retry attempts
        retry_delay: Delay between retry attempts in seconds

    Returns:
        Device information dictionary or None if connection failed
    """
    for attempt in range(retry_attempts):
        try:
            if attempt > 0:
                print(f"Retry attempt {attempt + 1}/{retry_attempts}...")  # noqa: T201
                await asyncio.sleep(retry_delay)

            # Connect to device
            await asyncio.wait_for(device.connect(), timeout=timeout)

            # Retrieve device information
            device_data = await asyncio.wait_for(device.read_data(), timeout=timeout)
            device_info_data = await asyncio.wait_for(
                device.get_device_info(),
                timeout=timeout,
            )

            # Disconnect from device
            await device.disconnect()

            # Compile device information
            return {
                "mac_address": device.device_address,
                "device_type": getattr(device, "device_type", "Unknown"),
                "protocol_version": getattr(device, "protocol_version", "Unknown"),
                "capabilities": list(getattr(device, "capabilities", set())),
                "connection_status": "success",
                "battery_data": _format_battery_data(device_data),
                "device_info": device_info_data,
                "latest_data": getattr(device, "latest_data", {}),
            }

        except TimeoutError:  # noqa: PERF203
            print(f"Connection timeout on attempt {attempt + 1}")  # noqa: T201
            with contextlib.suppress(Exception):
                await device.disconnect()
        except Exception as e:  # noqa: BLE001
            print(f"Connection error on attempt {attempt + 1}: {e}")  # noqa: T201
            with contextlib.suppress(Exception):
                await device.disconnect()

    return None


def _format_battery_data(battery_info: BatteryInfo | None) -> dict[str, Any]:
    """
    Format battery data for display.

    Args:
        battery_info: BatteryInfo object from device

    Returns:
        Formatted battery data dictionary
    """
    if battery_info is None:
        return {}

    # Helper function to safely get attribute values
    def safe_getattr(obj: object, attr: str, default: object = None) -> object:
        """Safely get attribute value, handling AsyncMock objects."""
        try:
            value = getattr(obj, attr, default)
            # If it's an AsyncMock, return a string representation
            if hasattr(value, "_mock_name") and hasattr(value, "_mock_return_value"):
                return f"<{getattr(value, '_mock_name', 'mock')}>"
        except Exception:  # noqa: BLE001
            return default
        return value

    return {
        "voltage": safe_getattr(battery_info, "voltage", None),
        "current": safe_getattr(battery_info, "current", None),
        "temperature": safe_getattr(battery_info, "temperature", None),
        "state_of_charge": safe_getattr(battery_info, "state_of_charge", None),
        "capacity": safe_getattr(battery_info, "capacity", None),
        "cycles": safe_getattr(battery_info, "cycles", None),
        "timestamp": safe_getattr(battery_info, "timestamp", None),
        "extra": safe_getattr(battery_info, "extra", {}),
    }


def _print_device_information(device_info: dict[str, Any]) -> None:
    """
    Print device information in a formatted table.

    Args:
        device_info: Device information dictionary
    """
    print("\nDevice Information")  # noqa: T201
    print("=" * 80)  # noqa: T201

    # Basic device information
    print(f"MAC Address: {device_info.get('mac_address', 'Unknown')}")  # noqa: T201
    print(f"Device Type: {device_info.get('device_type', 'Unknown')}")  # noqa: T201
    print(f"Protocol Version: {device_info.get('protocol_version', 'Unknown')}")  # noqa: T201
    print(f"Connection Status: {device_info.get('connection_status', 'Unknown')}")  # noqa: T201

    # Capabilities
    capabilities = device_info.get("capabilities", [])
    if capabilities:
        print(f"Capabilities: {', '.join(capabilities)}")  # noqa: T201

    # Device info
    device_info_data = device_info.get("device_info", {})
    if device_info_data:
        print("\nDevice Details:")  # noqa: T201
        for key, value in device_info_data.items():
            print(f"  {key.replace('_', ' ').title()}: {value}")  # noqa: T201

    # Battery data
    battery_data = device_info.get("battery_data", {})
    if battery_data:
        print("\nBattery Information:")  # noqa: T201
        if battery_data.get("voltage") is not None:
            print(f"  Voltage: {battery_data['voltage']}V")  # noqa: T201
        if battery_data.get("current") is not None:
            print(f"  Current: {battery_data['current']}A")  # noqa: T201
        if battery_data.get("temperature") is not None:
            print(f"  Temperature: {battery_data['temperature']}°C")  # noqa: T201
        if battery_data.get("state_of_charge") is not None:
            print(f"  State of Charge: {battery_data['state_of_charge']}%")  # noqa: T201
        if battery_data.get("capacity") is not None:
            print(f"  Capacity: {battery_data['capacity']}mAh")  # noqa: T201
        if battery_data.get("cycles") is not None:
            print(f"  Cycles: {battery_data['cycles']}")  # noqa: T201
        if battery_data.get("timestamp") is not None:
            print(f"  Timestamp: {battery_data['timestamp']}")  # noqa: T201

        # Extra data - handle safely to avoid iteration errors
        extra_data = battery_data.get("extra", {})
        if extra_data and isinstance(extra_data, dict):
            print("  Extra Data:")  # noqa: T201
            for key, value in extra_data.items():
                print(f"    {key.replace('_', ' ').title()}: {value}")  # noqa: T201

    # Latest data - handle safely to avoid iteration errors
    latest_data = device_info.get("latest_data", {})
    if latest_data and isinstance(latest_data, dict):
        print("\nLatest Raw Data:")  # noqa: T201
        for key, value in latest_data.items():
            print(f"  {key.replace('_', ' ').title()}: {value}")  # noqa: T201


def main(args: list[str] | None = None) -> int:
    """
    Run the main program.
    This function is executed when you type `battery_hawk` or `python -m battery_hawk`.

    Arguments:
        args: Arguments passed from the command line.

    Returns:
        An exit code.
    """
    parser = get_parser()
    opts = parser.parse_args(args=args)
    # Ensure config directory exists
    try:
        os.makedirs(opts.config_dir, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        print(  # noqa: T201
            f"Error: Could not create config directory '{opts.config_dir}': {e}",
            file=sys.stderr,
        )
        return 1
    # Initialize ConfigManager with error handling
    try:
        config_manager = ConfigManager(config_dir=opts.config_dir)
        setup_logging(config_manager)
    except Exception as e:  # noqa: BLE001
        print(f"Error: Failed to initialize config manager: {e}", file=sys.stderr)  # noqa: T201
        return 1

    # Ensure cleanup happens on exit
    try:
        return _handle_command(opts, config_manager)
    finally:
        config_manager.cleanup()


def _handle_command(opts: argparse.Namespace, config_manager: ConfigManager) -> int:  # noqa: PLR0911
    """Handle the CLI command with proper error handling."""
    if opts.command == "show":
        try:
            cfg = config_manager.get_config(opts.section)
            val = cfg
            for k in opts.key:
                if k not in val:
                    print(  # noqa: T201
                        f"Error: Key '{k}' not found in config section '{opts.section}'",
                        file=sys.stderr,
                    )
                    return 1
                val = val[k]
            print(val)  # noqa: T201
        except Exception as e:  # noqa: BLE001
            print(f"Error: {e}", file=sys.stderr)  # noqa: T201
            return 1
        return 0

    if opts.command == "set":
        try:
            cfg = config_manager.get_config(opts.section)
            d = cfg
            for k in opts.key[:-1]:
                d = d.setdefault(k, {})
            try:
                value = json.loads(opts.value)
            except Exception:  # noqa: BLE001
                value = opts.value
            d[opts.key[-1]] = value
            config_manager.save_config(opts.section)  # Immediately persist changes
            print(f"Set {opts.section} {'.'.join(opts.key)} = {value}")  # noqa: T201
        except Exception as e:  # noqa: BLE001
            print(f"Error: {e}", file=sys.stderr)  # noqa: T201
            return 1
        return 0

    if opts.command == "save":
        try:
            config_manager.save_config(opts.section)
            print(f"Saved config section '{opts.section}' to disk.")  # noqa: T201
        except Exception as e:  # noqa: BLE001
            print(f"Error: {e}", file=sys.stderr)  # noqa: T201
            return 1
        return 0

    if opts.command == "list":
        print("Available config sections:")  # noqa: T201
        for section in config_manager.configs:
            print(f"- {section}")  # noqa: T201
        return 0

    if opts.command == "scan":
        return asyncio.run(
            scan_devices(
                config_manager,
                opts.duration,
                opts.connect,
                opts.format,
                opts.no_storage,
                opts.scan_until_new,
                opts.short_timeout,
            ),
        )

    if opts.command == "connect":
        return asyncio.run(
            connect_to_device(
                config_manager,
                opts.mac_address,
                opts.device_type,
                opts.timeout,
                opts.retry_attempts,
                opts.retry_delay,
                opts.format,
            ),
        )

    print("Unknown command.", file=sys.stderr)  # noqa: T201
    return 1
