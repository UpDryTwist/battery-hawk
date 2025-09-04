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
"""
Module that contains the command line application.

Note: This module contains many noqa comments to suppress linting warnings
for optional dependencies, async file operations, and methods that may not
be implemented yet in the core modules.
"""
# ruff: noqa: ASYNC230, TRY300, PLC0415, TRY400, BLE001, DTZ005, DTZ006, PERF203, PERF401, FBT003, S110
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportPossiblyUnboundVariable=false

from __future__ import annotations

import argparse
import asyncio
import contextlib
import csv
import json
import logging
import os
import signal
import sys
import time
from typing import TYPE_CHECKING, Any

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import psutil
except ImportError:
    psutil = None

try:
    import requests
except ImportError:
    requests = None

try:
    import bleak
except ImportError:
    bleak = None

try:
    import aiofiles
except ImportError:
    aiofiles = None

from battery_hawk.cli_mqtt import (
    mqtt_list_topics,
    mqtt_monitor,
    mqtt_service_test,
    mqtt_status,
    mqtt_test_publish,
)
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

    # Validate log level
    if not hasattr(logging, log_level):
        print(f"Warning: Invalid log level '{log_level}', using INFO", file=sys.stderr)  # noqa: T201
        log_level = "INFO"

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
        force=True,  # Override any existing configuration
    )

    # Reduce noise from external libraries
    logging.getLogger("bleak").setLevel(logging.WARNING)
    logging.getLogger("aiomqtt").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Log the configuration
    logger = logging.getLogger("battery_hawk.setup")
    logger.info("Logging configured at %s level", log_level)


def get_parser() -> argparse.ArgumentParser:  # noqa: PLR0915
    """
    Return the CLI argument parser with subcommands for all Battery Hawk functionality.

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

    # service
    service_parser = subparsers.add_parser(
        "service",
        help="Service management commands",
        description="Manage Battery Hawk services (core engine, API server, MQTT)",
    )
    service_subparsers = service_parser.add_subparsers(
        dest="service_command",
        required=True,
    )

    # service start
    start_parser = service_subparsers.add_parser(
        "start",
        help="Start Battery Hawk services",
        description="Start the core monitoring engine and optional services",
    )
    _ = start_parser.add_argument(
        "--api",
        action="store_true",
        help="Start the REST API server",
    )
    _ = start_parser.add_argument(
        "--mqtt",
        action="store_true",
        help="Start the MQTT service",
    )
    _ = start_parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run in daemon mode (background)",
    )
    _ = start_parser.add_argument(
        "--pid-file",
        type=str,
        help="Write process ID to file (daemon mode only)",
    )

    # service stop
    stop_parser = service_subparsers.add_parser(
        "stop",
        help="Stop Battery Hawk services",
        description="Stop running Battery Hawk services",
    )
    _ = stop_parser.add_argument(
        "--pid-file",
        type=str,
        help="Read process ID from file",
    )
    _ = stop_parser.add_argument(
        "--force",
        action="store_true",
        help="Force stop using SIGKILL",
    )

    # service status
    status_parser = service_subparsers.add_parser(
        "status",
        help="Show service status",
        description="Show status of Battery Hawk services",
    )
    _ = status_parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table)",
    )

    # service restart
    restart_parser = service_subparsers.add_parser(
        "restart",
        help="Restart Battery Hawk services",
        description="Restart Battery Hawk services",
    )
    _ = restart_parser.add_argument(
        "--api",
        action="store_true",
        help="Restart the REST API server",
    )
    _ = restart_parser.add_argument(
        "--mqtt",
        action="store_true",
        help="Restart the MQTT service",
    )

    # mqtt
    mqtt_parser = subparsers.add_parser(
        "mqtt",
        help="MQTT management commands",
        description="Manage MQTT connectivity, testing, and monitoring",
    )
    mqtt_subparsers = mqtt_parser.add_subparsers(dest="mqtt_command", required=True)

    # mqtt status
    _ = mqtt_subparsers.add_parser(
        "status",
        help="Show MQTT connection status and configuration",
        description="Show MQTT connection status and test connectivity",
    )

    # mqtt publish
    mqtt_publish_parser = mqtt_subparsers.add_parser(
        "publish",
        help="Publish a test message to MQTT",
        description="Publish a test message to an MQTT topic",
    )
    _ = mqtt_publish_parser.add_argument(
        "topic",
        type=str,
        help="MQTT topic to publish to (relative to prefix)",
    )
    _ = mqtt_publish_parser.add_argument(
        "message",
        type=str,
        help="Message to publish (JSON or string)",
    )
    _ = mqtt_publish_parser.add_argument(
        "--retain",
        action="store_true",
        help="Set retain flag on message",
    )

    # mqtt topics
    _ = mqtt_subparsers.add_parser(
        "topics",
        help="List available MQTT topics",
        description="List all available MQTT topic patterns and examples",
    )

    # mqtt monitor
    mqtt_monitor_parser = mqtt_subparsers.add_parser(
        "monitor",
        help="Monitor MQTT messages",
        description="Monitor and display incoming MQTT messages",
    )
    _ = mqtt_monitor_parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Monitoring duration in seconds (default: 30)",
    )

    # mqtt test
    _ = mqtt_subparsers.add_parser(
        "test",
        help="Test MQTT service functionality",
        description="Test MQTT service with sample data",
    )

    # device
    device_parser = subparsers.add_parser(
        "device",
        help="Device management commands",
        description="Manage battery monitoring devices",
    )
    device_subparsers = device_parser.add_subparsers(
        dest="device_command",
        required=True,
    )

    # device list
    device_list_parser = device_subparsers.add_parser(
        "list",
        help="List registered devices",
        description="List all registered battery monitoring devices",
    )
    _ = device_list_parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table)",
    )

    # device add
    device_add_parser = device_subparsers.add_parser(
        "add",
        help="Register a new device",
        description="Register a new battery monitoring device",
    )
    _ = device_add_parser.add_argument(
        "mac_address",
        type=str,
        help="MAC address of the device (e.g., AA:BB:CC:DD:EE:FF)",
    )
    _ = device_add_parser.add_argument(
        "--device-type",
        type=str,
        choices=["BM6", "BM2"],
        required=True,
        help="Device type",
    )
    _ = device_add_parser.add_argument(
        "--name",
        type=str,
        help="Human-readable name for the device",
    )
    _ = device_add_parser.add_argument(
        "--polling-interval",
        type=int,
        default=3600,
        help="Polling interval in seconds (default: 3600)",
    )
    _ = device_add_parser.add_argument(
        "--vehicle-id",
        type=str,
        help="Associate device with a vehicle",
    )

    # device remove
    device_remove_parser = device_subparsers.add_parser(
        "remove",
        help="Remove a device",
        description="Remove a device from the registry",
    )
    _ = device_remove_parser.add_argument(
        "mac_address",
        type=str,
        help="MAC address of the device to remove",
    )
    _ = device_remove_parser.add_argument(
        "--force",
        action="store_true",
        help="Force removal without confirmation",
    )

    # device status
    device_status_parser = device_subparsers.add_parser(
        "status",
        help="Show device status",
        description="Show connection status and recent activity for devices",
    )
    _ = device_status_parser.add_argument(
        "mac_address",
        type=str,
        nargs="?",
        help="MAC address of specific device (optional)",
    )
    _ = device_status_parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table)",
    )

    # device readings
    device_readings_parser = device_subparsers.add_parser(
        "readings",
        help="Show recent device readings",
        description="Show recent battery readings from a device",
    )
    _ = device_readings_parser.add_argument(
        "mac_address",
        type=str,
        help="MAC address of the device",
    )
    _ = device_readings_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of recent readings to show (default: 10)",
    )
    _ = device_readings_parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table)",
    )

    # vehicle
    vehicle_parser = subparsers.add_parser(
        "vehicle",
        help="Vehicle management commands",
        description="Manage vehicles and device associations",
    )
    vehicle_subparsers = vehicle_parser.add_subparsers(
        dest="vehicle_command",
        required=True,
    )

    # vehicle list
    vehicle_list_parser = vehicle_subparsers.add_parser(
        "list",
        help="List vehicles",
        description="List all configured vehicles",
    )
    _ = vehicle_list_parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table)",
    )

    # vehicle add
    vehicle_add_parser = vehicle_subparsers.add_parser(
        "add",
        help="Add a new vehicle",
        description="Add a new vehicle to the registry",
    )
    _ = vehicle_add_parser.add_argument(
        "vehicle_id",
        type=str,
        help="Unique identifier for the vehicle",
    )
    _ = vehicle_add_parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Human-readable name for the vehicle",
    )
    _ = vehicle_add_parser.add_argument(
        "--description",
        type=str,
        help="Description of the vehicle",
    )
    _ = vehicle_add_parser.add_argument(
        "--type",
        type=str,
        choices=["car", "boat", "rv", "motorcycle", "other"],
        default="other",
        help="Type of vehicle (default: other)",
    )

    # vehicle remove
    vehicle_remove_parser = vehicle_subparsers.add_parser(
        "remove",
        help="Remove a vehicle",
        description="Remove a vehicle from the registry",
    )
    _ = vehicle_remove_parser.add_argument(
        "vehicle_id",
        type=str,
        help="Vehicle ID to remove",
    )
    _ = vehicle_remove_parser.add_argument(
        "--force",
        action="store_true",
        help="Force removal without confirmation",
    )

    # vehicle show
    vehicle_show_parser = vehicle_subparsers.add_parser(
        "show",
        help="Show vehicle details",
        description="Show detailed information about a vehicle and its devices",
    )
    _ = vehicle_show_parser.add_argument(
        "vehicle_id",
        type=str,
        help="Vehicle ID to show",
    )
    _ = vehicle_show_parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table)",
    )

    # vehicle associate
    vehicle_associate_parser = vehicle_subparsers.add_parser(
        "associate",
        help="Associate device with vehicle",
        description="Associate a device with a vehicle",
    )
    _ = vehicle_associate_parser.add_argument(
        "vehicle_id",
        type=str,
        help="Vehicle ID",
    )
    _ = vehicle_associate_parser.add_argument(
        "mac_address",
        type=str,
        help="MAC address of device to associate",
    )

    # data
    data_parser = subparsers.add_parser(
        "data",
        help="Data management commands",
        description="Manage stored battery data and database operations",
    )
    data_subparsers = data_parser.add_subparsers(dest="data_command", required=True)

    # data query
    data_query_parser = data_subparsers.add_parser(
        "query",
        help="Query battery readings",
        description="Query historical battery readings from the database",
    )
    _ = data_query_parser.add_argument(
        "--device",
        type=str,
        help="Filter by device MAC address",
    )
    _ = data_query_parser.add_argument(
        "--vehicle",
        type=str,
        help="Filter by vehicle ID",
    )
    _ = data_query_parser.add_argument(
        "--start",
        type=str,
        help="Start time (ISO format: 2024-01-01T00:00:00)",
    )
    _ = data_query_parser.add_argument(
        "--end",
        type=str,
        help="End time (ISO format: 2024-01-01T23:59:59)",
    )
    _ = data_query_parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of readings to return (default: 100)",
    )
    _ = data_query_parser.add_argument(
        "--format",
        choices=["json", "table", "csv"],
        default="table",
        help="Output format (default: table)",
    )

    # data export
    data_export_parser = data_subparsers.add_parser(
        "export",
        help="Export battery data",
        description="Export battery data to various formats",
    )
    _ = data_export_parser.add_argument(
        "output_file",
        type=str,
        help="Output file path",
    )
    _ = data_export_parser.add_argument(
        "--format",
        choices=["csv", "json", "xlsx"],
        default="csv",
        help="Export format (default: csv)",
    )
    _ = data_export_parser.add_argument(
        "--device",
        type=str,
        help="Filter by device MAC address",
    )
    _ = data_export_parser.add_argument(
        "--vehicle",
        type=str,
        help="Filter by vehicle ID",
    )
    _ = data_export_parser.add_argument(
        "--start",
        type=str,
        help="Start time (ISO format)",
    )
    _ = data_export_parser.add_argument(
        "--end",
        type=str,
        help="End time (ISO format)",
    )

    # data stats
    data_stats_parser = data_subparsers.add_parser(
        "stats",
        help="Show database statistics",
        description="Show database storage statistics and metrics",
    )
    _ = data_stats_parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table)",
    )

    # data cleanup
    data_cleanup_parser = data_subparsers.add_parser(
        "cleanup",
        help="Database maintenance operations",
        description="Perform database cleanup and maintenance",
    )
    _ = data_cleanup_parser.add_argument(
        "--older-than",
        type=str,
        help="Remove data older than specified time (e.g., '30d', '1y')",
    )
    _ = data_cleanup_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    _ = data_cleanup_parser.add_argument(
        "--force",
        action="store_true",
        help="Force cleanup without confirmation",
    )

    # system
    system_parser = subparsers.add_parser(
        "system",
        help="System monitoring and diagnostics",
        description="System health monitoring, logs, and troubleshooting tools",
    )
    system_subparsers = system_parser.add_subparsers(
        dest="system_command",
        required=True,
    )

    # system health
    system_health_parser = system_subparsers.add_parser(
        "health",
        help="System health check",
        description="Perform comprehensive system health check",
    )
    _ = system_health_parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table)",
    )

    # system logs
    system_logs_parser = system_subparsers.add_parser(
        "logs",
        help="View application logs",
        description="View and filter application logs",
    )
    _ = system_logs_parser.add_argument(
        "--level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Filter by log level",
    )
    _ = system_logs_parser.add_argument(
        "--lines",
        type=int,
        default=50,
        help="Number of recent log lines to show (default: 50)",
    )
    _ = system_logs_parser.add_argument(
        "--follow",
        action="store_true",
        help="Follow log output (like tail -f)",
    )

    # system metrics
    system_metrics_parser = system_subparsers.add_parser(
        "metrics",
        help="Show system metrics",
        description="Display system performance metrics and statistics",
    )
    _ = system_metrics_parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table)",
    )

    # system diagnose
    system_diagnose_parser = system_subparsers.add_parser(
        "diagnose",
        help="Run diagnostic checks",
        description="Run comprehensive diagnostic checks and troubleshooting",
    )
    _ = system_diagnose_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed diagnostic information",
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

    except Exception as e:
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
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
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
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
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

                except Exception as e:
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

        except Exception as e:
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
            sys.stdout.write(json.dumps(device_info, indent=2) + "\n")
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

        except TimeoutError:
            print(f"Connection timeout on attempt {attempt + 1}")  # noqa: T201
            with contextlib.suppress(Exception):
                await device.disconnect()
        except Exception as e:
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
        except Exception:
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


async def start_service(  # noqa: PLR0915
    config_manager: ConfigManager,
    enable_api: bool,
    enable_mqtt: bool,
    daemon_mode: bool,
    pid_file: str | None,
) -> int:
    """
    Start Battery Hawk services.

    Args:
        config_manager: Configuration manager instance
        enable_api: Whether to start the API server
        enable_mqtt: Whether to start the MQTT service
        daemon_mode: Whether to run in daemon mode
        pid_file: Path to write process ID file

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        from battery_hawk.api.api import BatteryHawkAPI
        from battery_hawk.core.engine import BatteryHawkCore
        from battery_hawk.mqtt.service import MQTTService

        logger = logging.getLogger("battery_hawk.service")

        if daemon_mode:
            logger.info("Starting Battery Hawk in daemon mode")
            if pid_file:
                if aiofiles:
                    async with aiofiles.open(pid_file, "w") as f:
                        await f.write(str(os.getpid()))
                else:
                    # Fallback to sync operation
                    with open(pid_file, "w") as f:
                        f.write(str(os.getpid()))
                logger.info("PID written to %s", pid_file)
        else:
            logger.info("Starting Battery Hawk services")

        # Initialize core engine
        core_engine = BatteryHawkCore(config_manager)

        # Initialize optional services
        api_server = None
        mqtt_service = None

        if enable_api:
            api_server = BatteryHawkAPI(config_manager, core_engine)
            logger.info("API server initialized")

        if enable_mqtt:
            mqtt_service = MQTTService(config_manager)
            if mqtt_service.enabled:
                logger.info("MQTT service initialized")
            else:
                logger.warning("MQTT service is disabled in configuration")
                mqtt_service = None

        # Start services
        try:
            # Start API server if enabled
            if api_server:
                await api_server.start_async()

            # Start MQTT service if enabled
            if mqtt_service:
                await mqtt_service.start()

            # Start core engine (this will run until shutdown)
            await core_engine.start()

        except KeyboardInterrupt:
            logger.info("Shutdown requested by user")
        except Exception:
            logger.exception("Service error")
            return 1
        finally:
            # Cleanup
            if api_server:
                await api_server.stop_async()
            if mqtt_service:
                await mqtt_service.stop()
            await core_engine.stop()

            # Remove PID file if created
            if daemon_mode and pid_file and os.path.exists(pid_file):
                os.unlink(pid_file)

        logger.info("Battery Hawk services stopped")
        return 0

    except Exception:
        logger = logging.getLogger("battery_hawk.service")
        logger.exception("Failed to start services")
        return 1


async def stop_service(pid_file: str | None, force: bool) -> int:
    """
    Stop Battery Hawk services.

    Args:
        pid_file: Path to read process ID from
        force: Whether to force stop with SIGKILL

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        logger = logging.getLogger("battery_hawk.service")

        if not pid_file:
            logger.error("PID file not specified")
            return 1

        if not os.path.exists(pid_file):
            logger.error("PID file not found: %s", pid_file)
            return 1

        # Read PID from file
        if aiofiles:
            async with aiofiles.open(pid_file) as f:
                pid_content = await f.read()
                pid = int(pid_content.strip())
        else:
            # Fallback to sync operation
            with open(pid_file) as f:
                pid = int(f.read().strip())

        logger.info("Stopping process %d", pid)

        # Send signal to process
        try:
            if force:
                os.kill(pid, signal.SIGKILL)
                logger.info("Sent SIGKILL to process %d", pid)
            else:
                os.kill(pid, signal.SIGTERM)
                logger.info("Sent SIGTERM to process %d", pid)

            # Wait for process to exit
            for _ in range(30):  # Wait up to 30 seconds
                try:
                    os.kill(pid, 0)  # Check if process still exists
                    await asyncio.sleep(1)
                except ProcessLookupError:
                    break
            else:
                if not force:
                    logger.warning("Process did not exit, sending SIGKILL")
                    os.kill(pid, signal.SIGKILL)

            # Remove PID file
            os.unlink(pid_file)
            logger.info("Service stopped successfully")
            return 0

        except ProcessLookupError:
            logger.info("Process %d not found (already stopped)", pid)
            os.unlink(pid_file)
            return 0

    except Exception:
        logger = logging.getLogger("battery_hawk.service")
        logger.exception("Failed to stop service")
        return 1


async def service_status(config_manager: ConfigManager, output_format: str) -> int:
    """
    Show service status.

    Args:
        config_manager: Configuration manager instance
        output_format: Output format ('json' or 'table')

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        logger = logging.getLogger("battery_hawk.service")

        # Check if services are configured
        system_config = config_manager.get_config("system")
        api_config = system_config.get("api", {})
        mqtt_config = system_config.get("mqtt", {})

        status_data = {
            "core_engine": {"configured": True, "running": False},
            "api_server": {
                "configured": api_config.get("enabled", True),
                "running": False,
                "host": api_config.get("host", "localhost"),
                "port": api_config.get("port", 5000),
            },
            "mqtt_service": {
                "configured": mqtt_config.get("enabled", False),
                "running": False,
                "broker": mqtt_config.get("broker", "not configured"),
                "port": mqtt_config.get("port", 1883),
            },
        }

        # Try to check if API server is running
        try:
            if requests:
                api_url = f"http://{status_data['api_server']['host']}:{status_data['api_server']['port']}/api/health"
                response = requests.get(api_url, timeout=5)
                http_ok = 200
                if response.status_code == http_ok:
                    health_data = response.json()
                    status_data["api_server"]["running"] = True
                    status_data["core_engine"]["running"] = health_data.get(
                        "core_running",
                        False,
                    )
        except Exception:  # nosec B110
            # API server not running or not accessible
            pass

        if output_format == "json":
            sys.stdout.write(json.dumps(status_data, indent=2) + "\n")
        else:
            logger.info("Battery Hawk Service Status")
            logger.info("=" * 40)
            logger.info("Core Engine:")
            logger.info("  Configured: %s", status_data["core_engine"]["configured"])
            logger.info("  Running: %s", status_data["core_engine"]["running"])
            logger.info("")
            logger.info("API Server:")
            logger.info("  Configured: %s", status_data["api_server"]["configured"])
            logger.info("  Running: %s", status_data["api_server"]["running"])
            logger.info(
                "  Address: %s:%s",
                status_data["api_server"]["host"],
                status_data["api_server"]["port"],
            )
            logger.info("")
            logger.info("MQTT Service:")
            logger.info("  Configured: %s", status_data["mqtt_service"]["configured"])
            logger.info("  Running: %s", status_data["mqtt_service"]["running"])
            logger.info(
                "  Broker: %s:%s",
                status_data["mqtt_service"]["broker"],
                status_data["mqtt_service"]["port"],
            )

        return 0

    except Exception:
        logger = logging.getLogger("battery_hawk.service")
        logger.exception("Failed to get service status")
        return 1


async def device_list(config_manager: ConfigManager, output_format: str) -> int:
    """
    List registered devices.

    Args:
        config_manager: Configuration manager instance
        output_format: Output format ('json' or 'table')

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        from battery_hawk.core.registry import DeviceRegistry

        logger = logging.getLogger("battery_hawk.device_list")
        device_registry = DeviceRegistry(config_manager)

        devices = device_registry.get_configured_devices()

        if output_format == "json":
            sys.stdout.write(json.dumps(devices, indent=2) + "\n")
        else:
            if not devices:
                logger.info("No devices registered")
                return 0

            logger.info("Registered Devices:")
            logger.info("=" * 60)
            for device in devices:
                logger.info("MAC Address: %s", device.get("mac_address", "Unknown"))
                logger.info("  Type: %s", device.get("device_type", "Unknown"))
                logger.info("  Name: %s", device.get("name", "Unnamed"))
                logger.info(
                    "  Polling Interval: %ds",
                    device.get("polling_interval", 3600),
                )
                logger.info("  Vehicle ID: %s", device.get("vehicle_id", "None"))
                logger.info("  Last Seen: %s", device.get("last_seen", "Never"))
                logger.info("")

        return 0

    except Exception:
        logger = logging.getLogger("battery_hawk.device_list")
        logger.exception("Failed to list devices")
        return 1


async def device_add(
    config_manager: ConfigManager,
    mac_address: str,
    device_type: str,
    name: str | None,
    polling_interval: int,
    vehicle_id: str | None,
) -> int:
    """
    Add a new device to the registry.

    Args:
        config_manager: Configuration manager instance
        mac_address: MAC address of the device
        device_type: Type of device (BM6, BM2)
        name: Human-readable name for the device
        polling_interval: Polling interval in seconds
        vehicle_id: Vehicle ID to associate with

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        from battery_hawk.core.registry import DeviceRegistry

        logger = logging.getLogger("battery_hawk.device_add")
        device_registry = DeviceRegistry(config_manager)

        # Validate MAC address format
        import re

        if not re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", mac_address):
            logger.error("Invalid MAC address format: %s", mac_address)
            return 1

        # Check if device already exists
        existing_devices = device_registry.get_configured_devices()
        for device in existing_devices:
            if device.get("mac_address", "").lower() == mac_address.lower():
                logger.error("Device %s is already registered", mac_address)
                return 1

        # Create device configuration
        device_config = {
            "mac_address": mac_address.upper(),
            "device_type": device_type,
            "name": name or f"{device_type} Device",
            "polling_interval": polling_interval,
            "enabled": True,
            "added_at": time.time(),
        }

        if vehicle_id:
            device_config["vehicle_id"] = vehicle_id

        # Add device to registry
        await device_registry.register_device(mac_address, device_config)

        logger.info("Device %s registered successfully", mac_address)
        logger.info("  Type: %s", device_type)
        logger.info("  Name: %s", device_config["name"])
        logger.info("  Polling Interval: %ds", polling_interval)
        if vehicle_id:
            logger.info("  Vehicle ID: %s", vehicle_id)

        return 0

    except Exception:
        logger = logging.getLogger("battery_hawk.device_add")
        logger.exception("Failed to add device")
        return 1


async def device_remove(
    config_manager: ConfigManager,
    mac_address: str,
    force: bool,
) -> int:
    """
    Remove a device from the registry.

    Args:
        config_manager: Configuration manager instance
        mac_address: MAC address of the device to remove
        force: Force removal without confirmation

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        from battery_hawk.core.registry import DeviceRegistry

        logger = logging.getLogger("battery_hawk.device_remove")
        device_registry = DeviceRegistry(config_manager)

        # Check if device exists
        existing_devices = device_registry.get_configured_devices()
        device_found = None
        for device in existing_devices:
            if device.get("mac_address", "").lower() == mac_address.lower():
                device_found = device
                break

        if not device_found:
            logger.error("Device %s not found in registry", mac_address)
            return 1

        # Confirm removal unless forced
        if not force:
            logger.info("Device to remove:")
            logger.info("  MAC Address: %s", device_found.get("mac_address"))
            logger.info("  Type: %s", device_found.get("device_type"))
            logger.info("  Name: %s", device_found.get("name"))

            response = input("Are you sure you want to remove this device? (y/N): ")
            if response.lower() not in ["y", "yes"]:
                logger.info("Device removal cancelled")
                return 0

        # Remove device from registry
        await device_registry.unregister_device(mac_address)

        logger.info("Device %s removed successfully", mac_address)
        return 0

    except Exception:
        logger = logging.getLogger("battery_hawk.device_remove")
        logger.exception("Failed to remove device")
        return 1


async def device_status(
    config_manager: ConfigManager,
    mac_address: str | None,
    output_format: str,
) -> int:
    """
    Show device status.

    Args:
        config_manager: Configuration manager instance
        mac_address: MAC address of specific device (optional)
        output_format: Output format ('json' or 'table')

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        from battery_hawk.core.registry import DeviceRegistry
        from battery_hawk.core.state import DeviceStateManager

        logger = logging.getLogger("battery_hawk.device_status")
        device_registry = DeviceRegistry(config_manager)
        state_manager = DeviceStateManager()

        devices = device_registry.get_configured_devices()

        if mac_address:
            # Filter to specific device
            devices = [
                d
                for d in devices
                if d.get("mac_address", "").lower() == mac_address.lower()
            ]
            if not devices:
                logger.error("Device %s not found", mac_address)
                return 1

        status_data = []
        for device in devices:
            mac = device.get("mac_address", "")
            device_state = state_manager.get_device_state(mac)

            status_info = {
                "mac_address": mac,
                "name": device.get("name", "Unnamed"),
                "device_type": device.get("device_type", "Unknown"),
                "connection_state": device_state.connection_state.value
                if device_state
                else "unknown",
                "last_seen": device_state.last_seen.isoformat()
                if device_state and device_state.last_seen
                else "Never",
                "last_reading": device_state.last_reading_time.isoformat()
                if device_state and device_state.last_reading_time
                else "Never",
                "total_readings": device_state.total_readings if device_state else 0,
                "connection_attempts": device_state.connection_attempts
                if device_state
                else 0,
                "enabled": device.get("enabled", True),
            }
            status_data.append(status_info)

        if output_format == "json":
            sys.stdout.write(json.dumps(status_data, indent=2) + "\n")
        else:
            if not status_data:
                logger.info("No devices found")
                return 0

            logger.info("Device Status:")
            logger.info("=" * 80)
            for status in status_data:
                logger.info("Device: %s (%s)", status["name"], status["mac_address"])
                logger.info("  Type: %s", status["device_type"])
                logger.info("  Connection State: %s", status["connection_state"])
                logger.info("  Enabled: %s", status["enabled"])
                logger.info("  Last Seen: %s", status["last_seen"])
                logger.info("  Last Reading: %s", status["last_reading"])
                logger.info("  Total Readings: %s", status["total_readings"])
                logger.info("  Connection Attempts: %s", status["connection_attempts"])
                logger.info("")

        return 0

    except Exception:
        logger = logging.getLogger("battery_hawk.device_status")
        logger.exception("Failed to get device status")
        return 1


async def device_readings(
    config_manager: ConfigManager,
    mac_address: str,
    limit: int,
    output_format: str,
) -> int:
    """
    Show recent device readings.

    Args:
        config_manager: Configuration manager instance
        mac_address: MAC address of the device
        limit: Number of recent readings to show
        output_format: Output format ('json' or 'table')

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        from battery_hawk.core.storage import DataStorage

        logger = logging.getLogger("battery_hawk.device_readings")
        data_storage = DataStorage(config_manager)

        # Connect to storage
        await data_storage.connect()

        if not data_storage.connected:
            logger.error("Could not connect to data storage")
            return 1

        # Query recent readings
        readings = await data_storage.query_readings(
            device_id=mac_address,
            limit=limit,
        )

        if output_format == "json":
            sys.stdout.write(json.dumps(readings, indent=2) + "\n")
        else:
            if not readings:
                logger.info("No readings found for device %s", mac_address)
                return 0

            logger.info("Recent Readings for %s:", mac_address)
            logger.info("=" * 80)
            for reading in readings:
                timestamp = reading.get("timestamp", "Unknown")
                logger.info("Timestamp: %s", timestamp)
                logger.info("  Voltage: %s V", reading.get("voltage", "N/A"))
                logger.info("  Current: %s A", reading.get("current", "N/A"))
                logger.info("  Temperature: %s °C", reading.get("temperature", "N/A"))
                logger.info(
                    "  State of Charge: %s%%",
                    reading.get("state_of_charge", "N/A"),
                )
                logger.info("  Capacity: %s Ah", reading.get("capacity", "N/A"))
                logger.info("")

        await data_storage.disconnect()
        return 0

    except Exception:
        logger = logging.getLogger("battery_hawk.device_readings")
        logger.exception("Failed to get device readings")
        return 1


async def vehicle_list(config_manager: ConfigManager, output_format: str) -> int:
    """
    List vehicles.

    Args:
        config_manager: Configuration manager instance
        output_format: Output format ('json' or 'table')

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        from battery_hawk.core.registry import VehicleRegistry

        logger = logging.getLogger("battery_hawk.vehicle_list")
        vehicle_registry = VehicleRegistry(config_manager)

        vehicles = vehicle_registry.get_all_vehicles()

        if output_format == "json":
            sys.stdout.write(json.dumps(vehicles, indent=2) + "\n")
        else:
            if not vehicles:
                logger.info("No vehicles configured")
                return 0

            logger.info("Configured Vehicles:")
            logger.info("=" * 60)
            for vehicle_id, vehicle_info in vehicles.items():
                logger.info("Vehicle ID: %s", vehicle_id)
                logger.info("  Name: %s", vehicle_info.get("name", "Unnamed"))
                logger.info("  Type: %s", vehicle_info.get("type", "Unknown"))
                logger.info(
                    "  Description: %s",
                    vehicle_info.get("description", "None"),
                )

                # Show associated devices
                devices = vehicle_info.get("devices", [])
                if devices:
                    logger.info("  Associated Devices:")
                    for device_mac in devices:
                        logger.info("    - %s", device_mac)
                else:
                    logger.info("  Associated Devices: None")
                logger.info("")

        return 0

    except Exception:
        logger = logging.getLogger("battery_hawk.vehicle_list")
        logger.exception("Failed to list vehicles")
        return 1


async def vehicle_add(
    config_manager: ConfigManager,
    vehicle_id: str,
    name: str,
    description: str | None,
    vehicle_type: str,
) -> int:
    """
    Add a new vehicle.

    Args:
        config_manager: Configuration manager instance
        vehicle_id: Unique identifier for the vehicle
        name: Human-readable name for the vehicle
        description: Description of the vehicle
        vehicle_type: Type of vehicle

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        from battery_hawk.core.registry import VehicleRegistry

        logger = logging.getLogger("battery_hawk.vehicle_add")
        vehicle_registry = VehicleRegistry(config_manager)

        # Check if vehicle already exists
        existing_vehicles = vehicle_registry.get_all_vehicles()
        if vehicle_id in existing_vehicles:
            logger.error("Vehicle %s already exists", vehicle_id)
            return 1

        # Create vehicle configuration
        vehicle_config = {
            "name": name,
            "type": vehicle_type,
            "description": description or "",
            "devices": [],
            "created_at": time.time(),
        }

        # Add vehicle to registry
        await vehicle_registry.register_vehicle(vehicle_id, vehicle_config)

        logger.info("Vehicle %s added successfully", vehicle_id)
        logger.info("  Name: %s", name)
        logger.info("  Type: %s", vehicle_type)
        if description:
            logger.info("  Description: %s", description)

        return 0

    except Exception:
        logger = logging.getLogger("battery_hawk.vehicle_add")
        logger.exception("Failed to add vehicle")
        return 1


async def vehicle_remove(
    config_manager: ConfigManager,
    vehicle_id: str,
    force: bool,
) -> int:
    """
    Remove a vehicle.

    Args:
        config_manager: Configuration manager instance
        vehicle_id: Vehicle ID to remove
        force: Force removal without confirmation

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        from battery_hawk.core.registry import VehicleRegistry

        logger = logging.getLogger("battery_hawk.vehicle_remove")
        vehicle_registry = VehicleRegistry(config_manager)

        # Check if vehicle exists
        existing_vehicles = vehicle_registry.get_all_vehicles()
        if vehicle_id not in existing_vehicles:
            logger.error("Vehicle %s not found", vehicle_id)
            return 1

        vehicle_info = existing_vehicles[vehicle_id]

        # Confirm removal unless forced
        if not force:
            logger.info("Vehicle to remove:")
            logger.info("  ID: %s", vehicle_id)
            logger.info("  Name: %s", vehicle_info.get("name"))
            logger.info("  Type: %s", vehicle_info.get("type"))

            devices = vehicle_info.get("devices", [])
            if devices:
                logger.info("  Associated Devices: %s", ", ".join(devices))
                logger.warning("Removing this vehicle will disassociate all devices!")

            response = input("Are you sure you want to remove this vehicle? (y/N): ")
            if response.lower() not in ["y", "yes"]:
                logger.info("Vehicle removal cancelled")
                return 0

        # Remove vehicle from registry
        await vehicle_registry.unregister_vehicle(vehicle_id)

        logger.info("Vehicle %s removed successfully", vehicle_id)
        return 0

    except Exception:
        logger = logging.getLogger("battery_hawk.vehicle_remove")
        logger.exception("Failed to remove vehicle")
        return 1


async def vehicle_show(
    config_manager: ConfigManager,
    vehicle_id: str,
    output_format: str,
) -> int:
    """
    Show vehicle details.

    Args:
        config_manager: Configuration manager instance
        vehicle_id: Vehicle ID to show
        output_format: Output format ('json' or 'table')

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        from battery_hawk.core.registry import DeviceRegistry, VehicleRegistry

        logger = logging.getLogger("battery_hawk.vehicle_show")
        vehicle_registry = VehicleRegistry(config_manager)
        device_registry = DeviceRegistry(config_manager)

        # Get vehicle info
        vehicles = vehicle_registry.get_all_vehicles()
        if vehicle_id not in vehicles:
            logger.error("Vehicle %s not found", vehicle_id)
            return 1

        vehicle_info = vehicles[vehicle_id]

        # Get device details for associated devices
        all_devices = device_registry.get_configured_devices()
        associated_devices = []
        for device in all_devices:
            if device.get("vehicle_id") == vehicle_id:
                associated_devices.append(device)

        vehicle_data = {
            "vehicle_id": vehicle_id,
            "name": vehicle_info.get("name"),
            "type": vehicle_info.get("type"),
            "description": vehicle_info.get("description"),
            "created_at": vehicle_info.get("created_at"),
            "associated_devices": associated_devices,
        }

        if output_format == "json":
            sys.stdout.write(json.dumps(vehicle_data, indent=2) + "\n")
        else:
            logger.info("Vehicle Details:")
            logger.info("=" * 60)
            logger.info("Vehicle ID: %s", vehicle_id)
            logger.info("Name: %s", vehicle_info.get("name", "Unnamed"))
            logger.info("Type: %s", vehicle_info.get("type", "Unknown"))
            logger.info("Description: %s", vehicle_info.get("description", "None"))

            created_at = vehicle_info.get("created_at")
            if created_at:
                import datetime

                created_time = datetime.datetime.fromtimestamp(created_at)
                logger.info("Created: %s", created_time.strftime("%Y-%m-%d %H:%M:%S"))

            logger.info("")
            logger.info("Associated Devices:")
            if associated_devices:
                for device in associated_devices:
                    logger.info(
                        "  - %s (%s) - %s",
                        device.get("mac_address"),
                        device.get("device_type"),
                        device.get("name", "Unnamed"),
                    )
            else:
                logger.info("  None")

        return 0

    except Exception:
        logger = logging.getLogger("battery_hawk.vehicle_show")
        logger.exception("Failed to show vehicle")
        return 1


async def vehicle_associate(
    config_manager: ConfigManager,
    vehicle_id: str,
    mac_address: str,
) -> int:
    """
    Associate a device with a vehicle.

    Args:
        config_manager: Configuration manager instance
        vehicle_id: Vehicle ID
        mac_address: MAC address of device to associate

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        from battery_hawk.core.registry import DeviceRegistry, VehicleRegistry

        logger = logging.getLogger("battery_hawk.vehicle_associate")
        vehicle_registry = VehicleRegistry(config_manager)
        device_registry = DeviceRegistry(config_manager)

        # Check if vehicle exists
        vehicles = vehicle_registry.get_all_vehicles()
        if vehicle_id not in vehicles:
            logger.error("Vehicle %s not found", vehicle_id)
            return 1

        # Check if device exists
        devices = device_registry.get_configured_devices()
        device_found = None
        for device in devices:
            if device.get("mac_address", "").lower() == mac_address.lower():
                device_found = device
                break

        if not device_found:
            logger.error("Device %s not found", mac_address)
            return 1

        # Associate device with vehicle
        await vehicle_registry.associate_device(vehicle_id, mac_address)

        logger.info("Device %s associated with vehicle %s", mac_address, vehicle_id)
        logger.info(
            "  Device: %s (%s)",
            device_found.get("name", "Unnamed"),
            device_found.get("device_type"),
        )
        logger.info("  Vehicle: %s", vehicles[vehicle_id].get("name", "Unnamed"))

        return 0

    except Exception:
        logger = logging.getLogger("battery_hawk.vehicle_associate")
        logger.exception("Failed to associate device with vehicle")
        return 1


async def data_query(
    config_manager: ConfigManager,
    device_id: str | None,
    vehicle_id: str | None,
    start_time: str | None,
    end_time: str | None,
    limit: int,
    output_format: str,
) -> int:
    """
    Query battery readings.

    Args:
        config_manager: Configuration manager instance
        device_id: Filter by device MAC address
        vehicle_id: Filter by vehicle ID
        start_time: Start time filter
        end_time: End time filter
        limit: Maximum number of readings
        output_format: Output format

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        import datetime

        from battery_hawk.core.storage import DataStorage

        logger = logging.getLogger("battery_hawk.data_query")
        data_storage = DataStorage(config_manager)

        # Connect to storage
        await data_storage.connect()

        if not data_storage.connected:
            logger.error("Could not connect to data storage")
            return 1

        # Parse time filters
        start_dt = None
        end_dt = None
        if start_time:
            try:
                start_dt = datetime.datetime.fromisoformat(start_time)
            except ValueError:
                logger.error("Invalid start time format: %s", start_time)
                return 1

        if end_time:
            try:
                end_dt = datetime.datetime.fromisoformat(end_time)
            except ValueError:
                logger.error("Invalid end time format: %s", end_time)
                return 1

        # Query readings
        readings = await data_storage.query_readings(
            device_id=device_id,
            vehicle_id=vehicle_id,
            start_time=start_dt,
            end_time=end_dt,
            limit=limit,
        )

        if output_format == "json":
            sys.stdout.write(json.dumps(readings, indent=2) + "\n")
        elif output_format == "csv":
            if readings:
                # Print CSV header
                headers = readings[0].keys()
                sys.stdout.write(",".join(headers) + "\n")
                # Print data rows
                for reading in readings:
                    values = [str(reading.get(h, "")) for h in headers]
                    sys.stdout.write(",".join(values) + "\n")
        else:  # table format
            if not readings:
                logger.info("No readings found matching criteria")
                return 0

            logger.info("Battery Readings:")
            logger.info("=" * 100)
            for reading in readings:
                timestamp = reading.get("timestamp", "Unknown")
                device = reading.get("device_id", "Unknown")
                logger.info("Time: %s | Device: %s", timestamp, device)
                logger.info(
                    "  Voltage: %s V | Current: %s A | Temp: %s°C | SoC: %s%%",
                    reading.get("voltage", "N/A"),
                    reading.get("current", "N/A"),
                    reading.get("temperature", "N/A"),
                    reading.get("state_of_charge", "N/A"),
                )
                logger.info("")

        await data_storage.disconnect()
        return 0

    except Exception:
        logger = logging.getLogger("battery_hawk.data_query")
        logger.exception("Failed to query data")
        return 1


async def data_export(  # noqa: PLR0911, PLR0915
    config_manager: ConfigManager,
    output_file: str,
    export_format: str,
    device_id: str | None,
    vehicle_id: str | None,
    start_time: str | None,
    end_time: str | None,
) -> int:
    """
    Export battery data.

    Args:
        config_manager: Configuration manager instance
        output_file: Output file path
        export_format: Export format
        device_id: Filter by device MAC address
        vehicle_id: Filter by vehicle ID
        start_time: Start time filter
        end_time: End time filter

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        import datetime

        from battery_hawk.core.storage import DataStorage

        logger = logging.getLogger("battery_hawk.data_export")
        data_storage = DataStorage(config_manager)

        # Connect to storage
        await data_storage.connect()

        if not data_storage.connected:
            logger.error("Could not connect to data storage")
            return 1

        # Parse time filters
        start_dt = None
        end_dt = None
        if start_time:
            try:
                start_dt = datetime.datetime.fromisoformat(start_time)
            except ValueError:
                logger.error("Invalid start time format: %s", start_time)
                return 1

        if end_time:
            try:
                end_dt = datetime.datetime.fromisoformat(end_time)
            except ValueError:
                logger.error("Invalid end time format: %s", end_time)
                return 1

        # Query all matching readings
        readings = await data_storage.query_readings(
            device_id=device_id,
            vehicle_id=vehicle_id,
            start_time=start_dt,
            end_time=end_dt,
            limit=None,  # No limit for export
        )

        if not readings:
            logger.warning("No data found matching criteria")
            return 0

        # Export data
        if export_format == "csv":
            if aiofiles:
                async with aiofiles.open(output_file, "w") as csvfile:
                    if readings:
                        fieldnames = readings[0].keys()
                        # Write CSV header
                        await csvfile.write(",".join(fieldnames) + "\n")
                        # Write data rows
                        for reading in readings:
                            values = [str(reading.get(h, "")) for h in fieldnames]
                            await csvfile.write(",".join(values) + "\n")
            else:
                # Fallback to sync operation
                with open(output_file, "w", newline="") as csvfile:
                    if readings:
                        fieldnames = readings[0].keys()
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(readings)

        elif export_format == "json":
            if aiofiles:
                async with aiofiles.open(output_file, "w") as jsonfile:
                    await jsonfile.write(json.dumps(readings, indent=2))
            else:
                # Fallback to sync operation
                with open(output_file, "w") as jsonfile:
                    json.dump(readings, jsonfile, indent=2)

        elif export_format == "xlsx":
            try:
                if pd:
                    dataframe = pd.DataFrame(readings)
                    dataframe.to_excel(output_file, index=False)
                else:
                    msg = "pandas required for Excel export. Install with: pip install pandas openpyxl"
                    raise ImportError(msg)
            except ImportError:
                logger.error(
                    "pandas required for Excel export. Install with: pip install pandas openpyxl",
                )
                return 1

        logger.info("Exported %d readings to %s", len(readings), output_file)
        await data_storage.disconnect()
        return 0

    except Exception:
        logger = logging.getLogger("battery_hawk.data_export")
        logger.exception("Failed to export data")
        return 1


async def data_stats(config_manager: ConfigManager, output_format: str) -> int:
    """
    Show database statistics.

    Args:
        config_manager: Configuration manager instance
        output_format: Output format ('json' or 'table')

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        from battery_hawk.core.storage import DataStorage

        logger = logging.getLogger("battery_hawk.data_stats")
        data_storage = DataStorage(config_manager)

        # Connect to storage
        await data_storage.connect()

        if not data_storage.connected:
            logger.error("Could not connect to data storage")
            return 1

        # Get storage statistics
        stats = await data_storage.get_statistics()

        if output_format == "json":
            sys.stdout.write(json.dumps(stats, indent=2) + "\n")
        else:
            logger.info("Database Statistics:")
            logger.info("=" * 50)
            logger.info("Total Readings: %s", stats.get("total_readings", "Unknown"))
            logger.info("Total Devices: %s", stats.get("total_devices", "Unknown"))
            logger.info(
                "Date Range: %s to %s",
                stats.get("earliest_reading", "Unknown"),
                stats.get("latest_reading", "Unknown"),
            )
            logger.info("Database Size: %s", stats.get("database_size", "Unknown"))

            # Show per-device statistics
            device_stats = stats.get("device_statistics", {})
            if device_stats:
                logger.info("")
                logger.info("Per-Device Statistics:")
                for device_id, device_data in device_stats.items():
                    logger.info("  %s:", device_id)
                    logger.info("    Readings: %s", device_data.get("reading_count", 0))
                    logger.info(
                        "    Last Reading: %s",
                        device_data.get("last_reading", "Never"),
                    )

        await data_storage.disconnect()
        return 0

    except Exception:
        logger = logging.getLogger("battery_hawk.data_stats")
        logger.exception("Failed to get database statistics")
        return 1


async def data_cleanup(  # noqa: PLR0911
    config_manager: ConfigManager,
    older_than: str | None,
    dry_run: bool,
    force: bool,
) -> int:
    """
    Perform database cleanup.

    Args:
        config_manager: Configuration manager instance
        older_than: Remove data older than specified time
        dry_run: Show what would be deleted without deleting
        force: Force cleanup without confirmation

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        import datetime
        import re

        from battery_hawk.core.storage import DataStorage

        logger = logging.getLogger("battery_hawk.data_cleanup")
        data_storage = DataStorage(config_manager)

        # Connect to storage
        await data_storage.connect()

        if not data_storage.connected:
            logger.error("Could not connect to data storage")
            return 1

        # Parse older_than parameter
        cutoff_date = None
        if older_than:
            # Parse time expressions like "30d", "1y", "6m"
            match = re.match(r"(\d+)([dwmy])", older_than.lower())
            if not match:
                logger.error(
                    "Invalid time format: %s. Use format like '30d', '1y', '6m'",
                    older_than,
                )
                return 1

            amount, unit = match.groups()
            amount = int(amount)

            now = datetime.datetime.now()
            if unit == "d":
                cutoff_date = now - datetime.timedelta(days=amount)
            elif unit == "w":
                cutoff_date = now - datetime.timedelta(weeks=amount)
            elif unit == "m":
                cutoff_date = now - datetime.timedelta(days=amount * 30)  # Approximate
            elif unit == "y":
                cutoff_date = now - datetime.timedelta(days=amount * 365)  # Approximate

        if not cutoff_date:
            logger.error("No cleanup criteria specified. Use --older-than parameter")
            return 1

        # Get count of records to be deleted
        records_to_delete = await data_storage.count_readings_before(cutoff_date)

        if records_to_delete == 0:
            logger.info("No records found older than %s", cutoff_date.isoformat())
            return 0

        logger.info(
            "Found %d records older than %s",
            records_to_delete,
            cutoff_date.isoformat(),
        )

        if dry_run:
            logger.info("DRY RUN: Would delete %d records", records_to_delete)
            return 0

        # Confirm deletion unless forced
        if not force:
            response = input(
                f"Are you sure you want to delete {records_to_delete} records? (y/N): ",
            )
            if response.lower() not in ["y", "yes"]:
                logger.info("Cleanup cancelled")
                return 0

        # Perform cleanup
        deleted_count = await data_storage.delete_readings_before(cutoff_date)
        logger.info("Successfully deleted %d records", deleted_count)

        await data_storage.disconnect()
        return 0

    except Exception:
        logger = logging.getLogger("battery_hawk.data_cleanup")
        logger.exception("Failed to perform database cleanup")
        return 1


async def system_health(config_manager: ConfigManager, output_format: str) -> int:  # noqa: PLR0915
    """
    Perform system health check.

    Args:
        config_manager: Configuration manager instance
        output_format: Output format ('json' or 'table')

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        logger = logging.getLogger("battery_hawk.system_health")

        health_data = {
            "overall_status": "healthy",
            "checks": {},
            "timestamp": time.time(),
        }

        # Check configuration
        try:
            system_config = config_manager.get_config("system")
            health_data["checks"]["configuration"] = {
                "status": "ok",
                "message": "Configuration loaded successfully",
            }
        except Exception as e:
            health_data["checks"]["configuration"] = {
                "status": "error",
                "message": f"Configuration error: {e}",
            }
            health_data["overall_status"] = "unhealthy"

        # Check data storage connectivity
        try:
            from battery_hawk.core.storage import DataStorage

            data_storage = DataStorage(config_manager)
            await data_storage.connect()
            if data_storage.connected:
                health_data["checks"]["data_storage"] = {
                    "status": "ok",
                    "message": "Data storage connected",
                }
                await data_storage.disconnect()
            else:
                health_data["checks"]["data_storage"] = {
                    "status": "warning",
                    "message": "Data storage not connected",
                }
        except Exception as e:
            health_data["checks"]["data_storage"] = {
                "status": "error",
                "message": f"Data storage error: {e}",
            }
            health_data["overall_status"] = "unhealthy"

        # Check MQTT connectivity
        try:
            mqtt_config = system_config.get("mqtt", {})
            if mqtt_config.get("enabled", False):
                from battery_hawk.mqtt.client import MQTTInterface

                mqtt_interface = MQTTInterface(config_manager)
                await mqtt_interface.connect()
                if mqtt_interface.connected:
                    health_data["checks"]["mqtt"] = {
                        "status": "ok",
                        "message": "MQTT connected",
                    }
                    await mqtt_interface.disconnect()
                else:
                    health_data["checks"]["mqtt"] = {
                        "status": "warning",
                        "message": "MQTT not connected",
                    }
            else:
                health_data["checks"]["mqtt"] = {
                    "status": "info",
                    "message": "MQTT disabled",
                }
        except Exception as e:
            health_data["checks"]["mqtt"] = {
                "status": "error",
                "message": f"MQTT error: {e}",
            }

        # Check Bluetooth availability
        try:
            import bleak

            _ = bleak.BleakScanner()
            health_data["checks"]["bluetooth"] = {
                "status": "ok",
                "message": "Bluetooth adapter available",
            }
        except Exception as e:
            health_data["checks"]["bluetooth"] = {
                "status": "error",
                "message": f"Bluetooth error: {e}",
            }
            health_data["overall_status"] = "unhealthy"

        if output_format == "json":
            sys.stdout.write(json.dumps(health_data, indent=2) + "\n")
        else:
            status_icon = "✓" if health_data["overall_status"] == "healthy" else "✗"
            logger.info("System Health Check %s", status_icon)
            logger.info("=" * 50)
            logger.info("Overall Status: %s", health_data["overall_status"].upper())
            logger.info("")

            for check_name, check_data in health_data["checks"].items():
                status = check_data["status"]
                icon = {"ok": "✓", "warning": "⚠", "error": "✗", "info": "i"}.get(
                    status,
                    "?",
                )
                logger.info(
                    "%s %s: %s",
                    icon,
                    check_name.replace("_", " ").title(),
                    check_data["message"],
                )

        return 0 if health_data["overall_status"] == "healthy" else 1

    except Exception:
        logger = logging.getLogger("battery_hawk.system_health")
        logger.exception("Failed to perform health check")
        return 1


async def system_logs(
    config_manager: ConfigManager,
    level: str | None,
    lines: int,
    follow: bool,
) -> int:
    """
    View application logs.

    Args:
        config_manager: Configuration manager instance
        level: Filter by log level
        lines: Number of recent log lines to show
        follow: Follow log output

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        logger = logging.getLogger("battery_hawk.system_logs")

        # Get log file path from configuration
        log_config = config_manager.get_config("system").get("logging", {})
        log_file = log_config.get("file")

        if not log_file or not os.path.exists(log_file):
            logger.error("Log file not found or not configured")
            return 1

        if follow:
            logger.info("Following log file: %s (Press Ctrl+C to stop)", log_file)
            # Simple tail -f implementation
            with open(log_file) as f:
                # Go to end of file
                f.seek(0, 2)
                try:
                    while True:
                        line = f.readline()
                        if line:
                            if not level or level in line:
                                sys.stdout.write(line.rstrip() + "\n")
                        else:
                            await asyncio.sleep(0.1)
                except KeyboardInterrupt:
                    logger.info("Log following stopped")
        else:
            # Show recent lines
            with open(log_file) as f:
                all_lines = f.readlines()
                recent_lines = (
                    all_lines[-lines:] if len(all_lines) > lines else all_lines
                )

                for line in recent_lines:
                    if not level or level in line:
                        sys.stdout.write(line.rstrip() + "\n")

        return 0

    except Exception:
        logger = logging.getLogger("battery_hawk.system_logs")
        logger.exception("Failed to view logs")
        return 1


async def system_metrics(config_manager: ConfigManager, output_format: str) -> int:  # noqa: PLR0915
    """
    Show system metrics.

    Args:
        config_manager: Configuration manager instance
        output_format: Output format ('json' or 'table')

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        import platform

        import psutil

        logger = logging.getLogger("battery_hawk.system_metrics")

        # Collect system metrics
        metrics = {
            "system": {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "uptime": time.time() - psutil.boot_time(),
            },
            "cpu": {
                "usage_percent": psutil.cpu_percent(interval=1),
                "count": psutil.cpu_count(),
                "load_average": psutil.getloadavg()
                if hasattr(psutil, "getloadavg")
                else None,
            },
            "memory": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "used": psutil.virtual_memory().used,
                "percent": psutil.virtual_memory().percent,
            },
            "disk": {
                "total": psutil.disk_usage("/").total,
                "used": psutil.disk_usage("/").used,
                "free": psutil.disk_usage("/").free,
                "percent": psutil.disk_usage("/").percent,
            },
            "network": {
                "bytes_sent": psutil.net_io_counters().bytes_sent,
                "bytes_recv": psutil.net_io_counters().bytes_recv,
                "packets_sent": psutil.net_io_counters().packets_sent,
                "packets_recv": psutil.net_io_counters().packets_recv,
            },
        }

        # Add Battery Hawk specific metrics if available
        try:
            from battery_hawk.core.storage import DataStorage

            data_storage = DataStorage(config_manager)
            await data_storage.connect()
            if data_storage.connected:
                storage_stats = await data_storage.get_statistics()
                metrics["battery_hawk"] = {
                    "total_readings": storage_stats.get("total_readings", 0),
                    "total_devices": storage_stats.get("total_devices", 0),
                    "storage_connected": True,
                }
                await data_storage.disconnect()
            else:
                metrics["battery_hawk"] = {"storage_connected": False}
        except Exception:
            metrics["battery_hawk"] = {"storage_connected": False}

        if output_format == "json":
            sys.stdout.write(json.dumps(metrics, indent=2) + "\n")
        else:
            logger.info("System Metrics:")
            logger.info("=" * 60)

            # System info
            logger.info("System:")
            logger.info("  Platform: %s", metrics["system"]["platform"])
            logger.info("  Python: %s", metrics["system"]["python_version"])
            logger.info("  Uptime: %.1f hours", metrics["system"]["uptime"] / 3600)

            # CPU
            logger.info("CPU:")
            logger.info("  Usage: %.1f%%", metrics["cpu"]["usage_percent"])
            logger.info("  Cores: %d", metrics["cpu"]["count"])

            # Memory
            mem = metrics["memory"]
            logger.info("Memory:")
            logger.info("  Total: %.1f GB", mem["total"] / (1024**3))
            logger.info(
                "  Used: %.1f GB (%.1f%%)",
                mem["used"] / (1024**3),
                mem["percent"],
            )
            logger.info("  Available: %.1f GB", mem["available"] / (1024**3))

            # Disk
            disk = metrics["disk"]
            logger.info("Disk:")
            logger.info("  Total: %.1f GB", disk["total"] / (1024**3))
            logger.info(
                "  Used: %.1f GB (%.1f%%)",
                disk["used"] / (1024**3),
                disk["percent"],
            )
            logger.info("  Free: %.1f GB", disk["free"] / (1024**3))

            # Battery Hawk
            bh = metrics["battery_hawk"]
            logger.info("Battery Hawk:")
            logger.info("  Storage Connected: %s", bh["storage_connected"])
            if bh.get("total_readings"):
                logger.info("  Total Readings: %s", bh["total_readings"])
                logger.info("  Total Devices: %s", bh["total_devices"])

        return 0

    except ImportError:
        logger = logging.getLogger("battery_hawk.system_metrics")
        logger.error(
            "psutil required for system metrics. Install with: pip install psutil",
        )
        return 1
    except Exception:
        logger = logging.getLogger("battery_hawk.system_metrics")
        logger.exception("Failed to get system metrics")
        return 1


async def system_diagnose(config_manager: ConfigManager, verbose: bool) -> int:  # noqa: PLR0915
    """
    Run diagnostic checks.

    Args:
        config_manager: Configuration manager instance
        verbose: Show detailed diagnostic information

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        logger = logging.getLogger("battery_hawk.system_diagnose")

        logger.info("Running Battery Hawk Diagnostics...")
        logger.info("=" * 60)

        issues_found = 0

        # Check Python version
        import sys

        python_version = sys.version_info
        if python_version < (3, 12):
            logger.error(
                "✗ Python version %d.%d.%d is below minimum required (3.12)",
                python_version.major,
                python_version.minor,
                python_version.micro,
            )
            issues_found += 1
        else:
            logger.info(
                "✓ Python version %d.%d.%d is supported",
                python_version.major,
                python_version.minor,
                python_version.micro,
            )

        # Check required packages
        required_packages = ["bleak", "influxdb_client", "flask", "asyncio_mqtt"]
        for package in required_packages:
            try:
                __import__(package)
                logger.info("✓ Package %s is available", package)
            except ImportError:
                logger.error("✗ Required package %s is missing", package)
                issues_found += 1

        # Check Bluetooth
        try:
            import bleak

            _ = bleak.BleakScanner()
            logger.info("✓ Bluetooth adapter is available")
        except Exception as e:
            logger.error("✗ Bluetooth adapter issue: %s", e)
            issues_found += 1

        # Check configuration files
        config_sections = ["system", "devices", "vehicles"]
        for section in config_sections:
            try:
                config = config_manager.get_config(section)
                logger.info("✓ Configuration section '%s' loaded", section)
                if verbose:
                    logger.info("    Keys: %s", list(config.keys()))
            except Exception as e:
                logger.warning("⚠ Configuration section '%s' issue: %s", section, e)

        # Check data storage
        try:
            from battery_hawk.core.storage import DataStorage

            data_storage = DataStorage(config_manager)
            await data_storage.connect()
            if data_storage.connected:
                logger.info("✓ Data storage connection successful")
                await data_storage.disconnect()
            else:
                logger.warning("⚠ Data storage connection failed")
        except Exception as e:
            logger.error("✗ Data storage error: %s", e)
            issues_found += 1

        # Check MQTT if enabled
        try:
            mqtt_config = config_manager.get_config("system").get("mqtt", {})
            if mqtt_config.get("enabled", False):
                from battery_hawk.mqtt.client import MQTTInterface

                mqtt_interface = MQTTInterface(config_manager)
                await mqtt_interface.connect()
                if mqtt_interface.connected:
                    logger.info("✓ MQTT connection successful")
                    await mqtt_interface.disconnect()
                else:
                    logger.warning("⚠ MQTT connection failed")
            else:
                logger.info("i MQTT is disabled")
        except Exception as e:
            logger.error("✗ MQTT error: %s", e)

        # Summary
        logger.info("")
        if issues_found == 0:
            logger.info("✓ All diagnostic checks passed!")
            return 0
        logger.error("✗ Found %d issues that need attention", issues_found)
        return 1

    except Exception:
        logger = logging.getLogger("battery_hawk.system_diagnose")
        logger.exception("Failed to run diagnostics")
        return 1


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
    except Exception as e:
        print(  # noqa: T201
            f"Error: Could not create config directory '{opts.config_dir}': {e}",
            file=sys.stderr,
        )
        return 1
    # Initialize ConfigManager with error handling
    try:
        config_manager = ConfigManager(config_dir=opts.config_dir)
        setup_logging(config_manager)
    except Exception as e:
        print(f"Error: Failed to initialize config manager: {e}", file=sys.stderr)  # noqa: T201
        return 1

    # Ensure cleanup happens on exit
    try:
        return _handle_command(opts, config_manager)
    finally:
        config_manager.cleanup()


def _handle_command(opts: argparse.Namespace, config_manager: ConfigManager) -> int:  # noqa: PLR0911, PLR0915
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
        except Exception as e:
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
            except Exception:
                value = opts.value
            d[opts.key[-1]] = value
            config_manager.save_config(opts.section)  # Immediately persist changes
            print(f"Set {opts.section} {'.'.join(opts.key)} = {value}")  # noqa: T201
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)  # noqa: T201
            return 1
        return 0

    if opts.command == "save":
        try:
            config_manager.save_config(opts.section)
            print(f"Saved config section '{opts.section}' to disk.")  # noqa: T201
        except Exception as e:
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

    if opts.command == "service":
        if opts.service_command == "start":
            return asyncio.run(
                start_service(
                    config_manager,
                    opts.api,
                    opts.mqtt,
                    opts.daemon,
                    opts.pid_file,
                ),
            )
        if opts.service_command == "stop":
            return asyncio.run(
                stop_service(
                    opts.pid_file,
                    opts.force,
                ),
            )
        if opts.service_command == "status":
            return asyncio.run(
                service_status(
                    config_manager,
                    opts.format,
                ),
            )
        if opts.service_command == "restart":
            # Stop first, then start
            if opts.pid_file:
                stop_result = asyncio.run(
                    stop_service(opts.pid_file, force=False),
                )
                if stop_result != 0:
                    return stop_result

            return asyncio.run(
                start_service(
                    config_manager,
                    opts.api,
                    opts.mqtt,
                    False,  # Don't run in daemon mode for restart
                    opts.pid_file,
                ),
            )

    if opts.command == "mqtt":
        if opts.mqtt_command == "status":
            return asyncio.run(mqtt_status(config_manager))
        if opts.mqtt_command == "publish":
            return asyncio.run(
                mqtt_test_publish(
                    config_manager,
                    opts.topic,
                    opts.message,
                    retain=opts.retain,
                ),
            )
        if opts.mqtt_command == "topics":
            return asyncio.run(mqtt_list_topics(config_manager))
        if opts.mqtt_command == "monitor":
            return asyncio.run(
                mqtt_monitor(
                    config_manager,
                    opts.duration,
                ),
            )
        if opts.mqtt_command == "test":
            return asyncio.run(mqtt_service_test(config_manager))

    if opts.command == "device":
        if opts.device_command == "list":
            return asyncio.run(device_list(config_manager, opts.format))
        if opts.device_command == "add":
            return asyncio.run(
                device_add(
                    config_manager,
                    opts.mac_address,
                    opts.device_type,
                    opts.name,
                    opts.polling_interval,
                    opts.vehicle_id,
                ),
            )
        if opts.device_command == "remove":
            return asyncio.run(
                device_remove(
                    config_manager,
                    opts.mac_address,
                    opts.force,
                ),
            )
        if opts.device_command == "status":
            return asyncio.run(
                device_status(
                    config_manager,
                    opts.mac_address,
                    opts.format,
                ),
            )
        if opts.device_command == "readings":
            return asyncio.run(
                device_readings(
                    config_manager,
                    opts.mac_address,
                    opts.limit,
                    opts.format,
                ),
            )

    if opts.command == "vehicle":
        if opts.vehicle_command == "list":
            return asyncio.run(vehicle_list(config_manager, opts.format))
        if opts.vehicle_command == "add":
            return asyncio.run(
                vehicle_add(
                    config_manager,
                    opts.vehicle_id,
                    opts.name,
                    opts.description,
                    opts.type,
                ),
            )
        if opts.vehicle_command == "remove":
            return asyncio.run(
                vehicle_remove(
                    config_manager,
                    opts.vehicle_id,
                    opts.force,
                ),
            )
        if opts.vehicle_command == "show":
            return asyncio.run(
                vehicle_show(
                    config_manager,
                    opts.vehicle_id,
                    opts.format,
                ),
            )
        if opts.vehicle_command == "associate":
            return asyncio.run(
                vehicle_associate(
                    config_manager,
                    opts.vehicle_id,
                    opts.mac_address,
                ),
            )

    if opts.command == "data":
        if opts.data_command == "query":
            return asyncio.run(
                data_query(
                    config_manager,
                    opts.device,
                    opts.vehicle,
                    opts.start,
                    opts.end,
                    opts.limit,
                    opts.format,
                ),
            )
        if opts.data_command == "export":
            return asyncio.run(
                data_export(
                    config_manager,
                    opts.output_file,
                    opts.format,
                    opts.device,
                    opts.vehicle,
                    opts.start,
                    opts.end,
                ),
            )
        if opts.data_command == "stats":
            return asyncio.run(data_stats(config_manager, opts.format))
        if opts.data_command == "cleanup":
            return asyncio.run(
                data_cleanup(
                    config_manager,
                    opts.older_than,
                    opts.dry_run,
                    opts.force,
                ),
            )

    if opts.command == "system":
        if opts.system_command == "health":
            return asyncio.run(system_health(config_manager, opts.format))
        if opts.system_command == "logs":
            return asyncio.run(
                system_logs(
                    config_manager,
                    opts.level,
                    opts.lines,
                    opts.follow,
                ),
            )
        if opts.system_command == "metrics":
            return asyncio.run(system_metrics(config_manager, opts.format))
        if opts.system_command == "diagnose":
            return asyncio.run(system_diagnose(config_manager, opts.verbose))

    print("Unknown command.", file=sys.stderr)  # noqa: T201
    return 1
