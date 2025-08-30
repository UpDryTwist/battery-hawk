"""BM6 protocol command building and data parsing."""

from __future__ import annotations

from .constants import (
    CMD_REQUEST_BASIC_INFO,
    CMD_REQUEST_CELL_VOLTAGES,
    CMD_REQUEST_VOLTAGE_TEMP,
    CMD_SET_PARAMETER,
    END_MARKER,
    MIN_RESPONSE_LENGTH,
    PROTOCOL_VERSION,
    START_MARKER,
)
from .crypto import BM6Crypto


def build_command(command: int, data: bytes | None = None) -> bytes:
    """
    Build a command packet for BM6 device.

    Args:
        command: Command code (e.g., CMD_REQUEST_BASIC_INFO)
        data: Optional data bytes for the command

    Returns:
        Complete command packet as bytes
    """
    if data is None:
        data = b""

    packet = bytearray([START_MARKER, PROTOCOL_VERSION, command, len(data)])
    packet.extend(data)

    # Calculate checksum (sum of all bytes after start marker up to checksum position)
    checksum = 0
    for i in range(1, len(packet)):
        checksum += packet[i]

    packet.append(0xFF - (checksum % 0x100))  # Checksum byte
    packet.append(END_MARKER)  # End marker

    return bytes(packet)


def build_real_bm6_command(command_hex: str) -> bytes:
    """
    Build a real BM6 command with AES encryption.

    Args:
        command_hex: Hex string command (e.g., "d15507")

    Returns:
        Encrypted command bytes
    """
    # Convert hex string to bytes
    command_bytes = bytes.fromhex(command_hex)

    # Encrypt the command
    crypto = BM6Crypto()
    return crypto.encrypt(command_bytes)


def build_voltage_temp_request() -> bytes:
    """Build encrypted command to request voltage and temperature data from BM6 device."""
    return build_real_bm6_command(CMD_REQUEST_VOLTAGE_TEMP)


def build_basic_info_request() -> bytes:
    """Build command to request basic information from BM6 device."""
    return build_command(CMD_REQUEST_BASIC_INFO)


def build_cell_voltages_request() -> bytes:
    """Build command to request cell voltage information from BM6 device."""
    return build_command(CMD_REQUEST_CELL_VOLTAGES)


def build_set_parameter_command(parameter_id: int, value: int) -> bytes:
    """
    Build command to set a parameter on BM6 device.

    Args:
        parameter_id: Parameter ID to set
        value: Value to set (16-bit)

    Returns:
        Command packet as bytes
    """
    data = bytes([parameter_id, value & 0xFF, (value >> 8) & 0xFF])
    return build_command(CMD_SET_PARAMETER, data)


def validate_response(data: bytes) -> bool:
    """
    Validate that a response packet has the correct structure.

    Args:
        data: Response data to validate

    Returns:
        True if valid, False otherwise
    """
    return (
        len(data) >= MIN_RESPONSE_LENGTH
        and data[0] == START_MARKER
        and data[-1] == END_MARKER
    )


def extract_command(data: bytes) -> int | None:
    """
    Extract command code from response data.

    Args:
        data: Response data

    Returns:
        Command code if valid, None otherwise
    """
    if not validate_response(data):
        return None
    return data[2]


def decode_production_date(raw_date: int) -> str:
    """
    Decode production date from raw value.

    Args:
        raw_date: Raw date value from device

    Returns:
        Formatted date string (YYYY-MM-DD)
    """
    year = 2000 + ((raw_date >> 9) & 0x7F)  # 7 bits for year (2000-2127)
    month = (raw_date >> 5) & 0x0F  # 4 bits for month (1-12)
    day = raw_date & 0x1F  # 5 bits for day (1-31)
    return f"{year}-{month:02d}-{day:02d}"


def decode_protection_status(status: int) -> dict[str, bool]:
    """
    Decode protection status bits.

    Args:
        status: Raw protection status value

    Returns:
        Dictionary of protection status flags
    """
    return {
        "single_cell_overvoltage": bool(status & 0x0001),
        "single_cell_undervoltage": bool(status & 0x0002),
        "battery_overvoltage": bool(status & 0x0004),
        "battery_undervoltage": bool(status & 0x0008),
        "charging_overtemperature": bool(status & 0x0010),
        "charging_undertemperature": bool(status & 0x0020),
        "discharging_overtemperature": bool(status & 0x0040),
        "discharging_undertemperature": bool(status & 0x0080),
        "charging_overcurrent": bool(status & 0x0100),
        "discharging_overcurrent": bool(status & 0x0200),
        "short_circuit": bool(status & 0x0400),
        "front_end_detection_ic_error": bool(status & 0x0800),
        "software_lock_mos": bool(status & 0x1000),
    }


def decode_fet_status(status: int) -> dict[str, bool]:
    """
    Decode FET status byte.

    Args:
        status: Raw FET status value

    Returns:
        Dictionary of FET status flags
    """
    return {
        "charging": bool(status & 0x01),
        "discharging": bool(status & 0x02),
    }
