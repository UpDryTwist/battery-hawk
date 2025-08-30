"""BM6 protocol implementation for Battery Hawk."""

from .constants import (
    BM6_DEVICE_NAME_UUID,
    BM6_NOTIFY_CHARACTERISTIC_UUID,
    BM6_SERVICE_UUID,
    BM6_WRITE_CHARACTERISTIC_UUID,
    CMD_REQUEST_BASIC_INFO,
    CMD_REQUEST_CELL_VOLTAGES,
    CMD_SET_PARAMETER,
)
from .device import BM6Device
from .parser import BM6Parser
from .protocol import (
    build_basic_info_request,
    build_cell_voltages_request,
    build_command,
    build_set_parameter_command,
    decode_fet_status,
    decode_production_date,
    decode_protection_status,
    extract_command,
    validate_response,
)

__version__ = "0.0.1-dev0"

__all__ = [
    "BM6_DEVICE_NAME_UUID",
    "BM6_NOTIFY_CHARACTERISTIC_UUID",
    "BM6_SERVICE_UUID",
    "BM6_WRITE_CHARACTERISTIC_UUID",
    "CMD_REQUEST_BASIC_INFO",
    "CMD_REQUEST_CELL_VOLTAGES",
    "CMD_SET_PARAMETER",
    "BM6Device",
    "BM6Parser",
    "build_basic_info_request",
    "build_cell_voltages_request",
    "build_command",
    "build_set_parameter_command",
    "decode_fet_status",
    "decode_production_date",
    "decode_protection_status",
    "extract_command",
    "validate_response",
]
