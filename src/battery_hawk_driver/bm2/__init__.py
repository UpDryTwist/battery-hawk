"""BM2 battery monitor protocol implementation."""

from .constants import (
    ALARM_HIGH_TEMPERATURE,
    ALARM_HIGH_VOLTAGE,
    ALARM_LOW_TEMPERATURE,
    ALARM_LOW_VOLTAGE,
    BM2_COMMAND_CHARACTERISTIC_UUID,
    BM2_CONFIG_CHARACTERISTIC_UUID,
    BM2_DATA_CHARACTERISTIC_UUID,
    BM2_INFO_CHARACTERISTIC_UUID,
    BM2_SERVICE_UUID,
    CMD_CONFIGURE_DISPLAY,
    CMD_REQUEST_BATTERY_DATA,
    CMD_RESET_DEVICE,
    CMD_SET_ALARM_THRESHOLD,
    CMD_SET_BATTERY_CAPACITY,
    DATA_PACKET_HEADER,
    DISPLAY_ADVANCED,
    DISPLAY_BASIC,
    DISPLAY_DETAILED,
    MIN_DATA_PACKET_LENGTH,
)
from .device import BM2Device
from .parser import BM2Parser
from .protocol import (
    build_configure_display_command,
    build_request_battery_data_command,
    build_reset_device_command,
    build_set_alarm_threshold_command,
    build_set_battery_capacity_command,
    get_alarm_type_name,
    get_display_mode_name,
    parse_battery_data,
    validate_data_packet,
)

__all__ = [
    # Constants
    "ALARM_HIGH_TEMPERATURE",
    "ALARM_HIGH_VOLTAGE",
    "ALARM_LOW_TEMPERATURE",
    "ALARM_LOW_VOLTAGE",
    "BM2_COMMAND_CHARACTERISTIC_UUID",
    "BM2_CONFIG_CHARACTERISTIC_UUID",
    "BM2_DATA_CHARACTERISTIC_UUID",
    "BM2_INFO_CHARACTERISTIC_UUID",
    "BM2_SERVICE_UUID",
    "CMD_CONFIGURE_DISPLAY",
    "CMD_REQUEST_BATTERY_DATA",
    "CMD_RESET_DEVICE",
    "CMD_SET_ALARM_THRESHOLD",
    "CMD_SET_BATTERY_CAPACITY",
    "DATA_PACKET_HEADER",
    "DISPLAY_ADVANCED",
    "DISPLAY_BASIC",
    "DISPLAY_DETAILED",
    "MIN_DATA_PACKET_LENGTH",
    # Main device class
    "BM2Device",
    # Parser class
    "BM2Parser",
    # Protocol functions
    "build_configure_display_command",
    "build_request_battery_data_command",
    "build_reset_device_command",
    "build_set_alarm_threshold_command",
    "build_set_battery_capacity_command",
    "get_alarm_type_name",
    "get_display_mode_name",
    "parse_battery_data",
    "validate_data_packet",
]
