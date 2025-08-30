"""BM2 protocol command building and data parsing."""

from __future__ import annotations

from .constants import (
    ALARM_HIGH_TEMPERATURE,
    ALARM_HIGH_VOLTAGE,
    ALARM_LOW_TEMPERATURE,
    ALARM_LOW_VOLTAGE,
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


def build_request_battery_data_command() -> bytes:
    """Build command to request battery data from BM2 device."""
    return bytes([CMD_REQUEST_BATTERY_DATA])


def build_set_alarm_threshold_command(alarm_type: int, threshold_value: int) -> bytes:
    """
    Build command to set alarm threshold on BM2 device.

    Args:
        alarm_type: Type of alarm (ALARM_LOW_VOLTAGE, ALARM_HIGH_VOLTAGE, etc.)
        threshold_value: Threshold value in appropriate units

    Returns:
        Command packet as bytes
    """
    command = bytearray([CMD_SET_ALARM_THRESHOLD, alarm_type])
    command.extend(threshold_value.to_bytes(2, byteorder="little"))
    return bytes(command)


def build_configure_display_command(display_mode: int) -> bytes:
    """
    Build command to configure display mode on BM2 device.

    Args:
        display_mode: Display mode (DISPLAY_BASIC, DISPLAY_ADVANCED, DISPLAY_DETAILED)

    Returns:
        Command packet as bytes
    """
    return bytes([CMD_CONFIGURE_DISPLAY, display_mode])


def build_reset_device_command() -> bytes:
    """Build command to reset BM2 device to factory settings."""
    return bytes([CMD_RESET_DEVICE])


def build_set_battery_capacity_command(capacity_mah: int) -> bytes:
    """
    Build command to set battery capacity on BM2 device.

    Args:
        capacity_mah: Battery capacity in mAh

    Returns:
        Command packet as bytes
    """
    command = bytearray([CMD_SET_BATTERY_CAPACITY])
    command.extend(capacity_mah.to_bytes(2, byteorder="little"))
    return bytes(command)


def validate_data_packet(data: bytes) -> bool:
    """
    Validate that a data packet has the correct structure.

    Args:
        data: Data packet to validate

    Returns:
        True if valid, False otherwise
    """
    if len(data) < MIN_DATA_PACKET_LENGTH:
        return False

    if data[0] != DATA_PACKET_HEADER:
        return False

    # Verify checksum
    calculated_checksum = 0
    for i in range(len(data) - 1):
        calculated_checksum ^= data[i]

    return calculated_checksum == data[-1]


def parse_battery_data(data: bytes) -> dict[str, object] | None:
    """
    Parse BM2 battery monitor data packet.

    Args:
        data: Raw data packet from BM2 device

    Returns:
        Parsed battery data dictionary or None if invalid
    """
    if not validate_data_packet(data):
        return None

    try:
        # Parse voltage (2 bytes, little-endian, in mV)
        voltage_mv = int.from_bytes(data[1:3], byteorder="little")
        voltage_v = voltage_mv / 1000.0  # Convert to volts

        # Parse current (2 bytes, little-endian, signed, in mA)
        current_ma = int.from_bytes(data[3:5], byteorder="little", signed=True)
        current_a = current_ma / 1000.0  # Convert to amps

        # Parse temperature (2 bytes, little-endian, signed, in 0.1°C)
        temp_decidegc = int.from_bytes(data[5:7], byteorder="little", signed=True)
        temperature_c = temp_decidegc / 10.0  # Convert to Celsius

        # Parse state of charge (1 byte, percentage)
        soc_percent = data[7]

        # Parse remaining capacity (2 bytes, little-endian, in mAh)
        capacity_mah = int.from_bytes(data[8:10], byteorder="little")
        capacity_ah = capacity_mah / 1000.0  # Convert to Ah

        # Calculate power (voltage * current)
        power_w = voltage_v * current_a

    except (IndexError, ValueError):
        # Log error but don't raise to avoid breaking the monitoring loop
        return None
    else:
        return {
            "voltage": voltage_v,
            "current": current_a,
            "temperature": temperature_c,
            "state_of_charge": soc_percent,
            "capacity": capacity_ah,
            "power": power_w,
            "voltage_mv": voltage_mv,
            "current_ma": current_ma,
            "capacity_mah": capacity_mah,
        }


def get_alarm_type_name(alarm_type: int) -> str:
    """
    Get human-readable name for alarm type.

    Args:
        alarm_type: Alarm type code

    Returns:
        Human-readable alarm type name
    """
    alarm_names = {
        ALARM_LOW_VOLTAGE: "Low Voltage",
        ALARM_HIGH_VOLTAGE: "High Voltage",
        ALARM_LOW_TEMPERATURE: "Low Temperature",
        ALARM_HIGH_TEMPERATURE: "High Temperature",
    }
    return alarm_names.get(alarm_type, f"Unknown Alarm ({alarm_type})")


def get_display_mode_name(display_mode: int) -> str:
    """
    Get human-readable name for display mode.

    Args:
        display_mode: Display mode code

    Returns:
        Human-readable display mode name
    """
    mode_names = {
        DISPLAY_BASIC: "Basic",
        DISPLAY_ADVANCED: "Advanced",
        DISPLAY_DETAILED: "Detailed",
    }
    return mode_names.get(display_mode, f"Unknown Mode ({display_mode})")
