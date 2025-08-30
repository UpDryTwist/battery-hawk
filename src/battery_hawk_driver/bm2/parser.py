"""BM2 data parsing utilities."""

from __future__ import annotations

from typing import Any

from .constants import (
    ALARM_HIGH_TEMPERATURE,
    ALARM_HIGH_VOLTAGE,
    ALARM_LOW_TEMPERATURE,
    ALARM_LOW_VOLTAGE,
    DISPLAY_ADVANCED,
    DISPLAY_BASIC,
    DISPLAY_DETAILED,
    MIN_DATA_PACKET_LENGTH,
)
from .protocol import parse_battery_data

# Minimum data lengths for different data types
MIN_VOLTAGE_DATA_LENGTH = 3
MIN_CURRENT_DATA_LENGTH = 5
MIN_TEMPERATURE_DATA_LENGTH = 7
MIN_SOC_DATA_LENGTH = 8
MIN_CAPACITY_DATA_LENGTH = 10
MAX_SOC_PERCENTAGE = 100


class BM2Parser:
    """Parser for BM2 battery monitor data."""

    @staticmethod
    def parse_data_packet(data: bytes) -> dict[str, Any] | None:
        """
        Parse a complete BM2 data packet.

        Args:
            data: Raw data packet from BM2 device

        Returns:
            Parsed data dictionary or None if invalid
        """
        return parse_battery_data(data)

    @staticmethod
    def parse_voltage_data(data: bytes) -> float | None:
        """
        Parse voltage data from BM2 response.

        Args:
            data: Raw response data

        Returns:
            Voltage in volts or None if invalid
        """
        if len(data) < MIN_VOLTAGE_DATA_LENGTH:
            return None

        try:
            voltage_mv = int.from_bytes(data[1:3], byteorder="little")
            return voltage_mv / 1000.0  # Convert to volts
        except (IndexError, ValueError):
            return None

    @staticmethod
    def parse_current_data(data: bytes) -> float | None:
        """
        Parse current data from BM2 response.

        Args:
            data: Raw response data

        Returns:
            Current in amps or None if invalid
        """
        if len(data) < MIN_CURRENT_DATA_LENGTH:
            return None

        try:
            current_ma = int.from_bytes(data[3:5], byteorder="little", signed=True)
            return current_ma / 1000.0  # Convert to amps
        except (IndexError, ValueError):
            return None

    @staticmethod
    def parse_temperature_data(data: bytes) -> float | None:
        """
        Parse temperature data from BM2 response.

        Args:
            data: Raw response data

        Returns:
            Temperature in Celsius or None if invalid
        """
        if len(data) < MIN_TEMPERATURE_DATA_LENGTH:
            return None

        try:
            temp_decidegc = int.from_bytes(data[5:7], byteorder="little", signed=True)
            return temp_decidegc / 10.0  # Convert to Celsius
        except (IndexError, ValueError):
            return None

    @staticmethod
    def parse_soc_data(data: bytes) -> int | None:
        """
        Parse state of charge data from BM2 response.

        Args:
            data: Raw response data

        Returns:
            State of charge as percentage (0-100) or None if invalid
        """
        if len(data) < MIN_SOC_DATA_LENGTH:
            return None

        try:
            soc = data[7]
            if 0 <= soc <= MAX_SOC_PERCENTAGE:
                return soc
        except (IndexError, ValueError):
            pass
        return None

    @staticmethod
    def parse_capacity_data(data: bytes) -> float | None:
        """
        Parse capacity data from BM2 response.

        Args:
            data: Raw response data

        Returns:
            Capacity in Ah or None if invalid
        """
        if len(data) < MIN_CAPACITY_DATA_LENGTH:
            return None

        try:
            capacity_mah = int.from_bytes(data[8:10], byteorder="little")
            return capacity_mah / 1000.0  # Convert to Ah
        except (IndexError, ValueError):
            return None

    @staticmethod
    def validate_checksum(data: bytes) -> bool:
        """
        Validate checksum of BM2 data packet.

        Args:
            data: Raw data packet

        Returns:
            True if checksum is valid, False otherwise
        """
        if len(data) < MIN_DATA_PACKET_LENGTH:
            return False

        calculated_checksum = 0
        for i in range(len(data) - 1):
            calculated_checksum ^= data[i]

        return calculated_checksum == data[-1]

    @staticmethod
    def extract_raw_values(data: bytes) -> dict[str, int] | None:
        """
        Extract raw values from BM2 data packet without conversion.

        Args:
            data: Raw data packet

        Returns:
            Dictionary of raw values or None if invalid
        """
        if not BM2Parser.validate_checksum(data):
            return None

        if len(data) < MIN_DATA_PACKET_LENGTH:
            return None

        try:
            return {
                "voltage_mv": int.from_bytes(data[1:3], byteorder="little"),
                "current_ma": int.from_bytes(
                    data[3:5],
                    byteorder="little",
                    signed=True,
                ),
                "temperature_decidegc": int.from_bytes(
                    data[5:7],
                    byteorder="little",
                    signed=True,
                ),
                "soc_percent": data[7],
                "capacity_mah": int.from_bytes(data[8:10], byteorder="little"),
            }
        except (IndexError, ValueError):
            return None

    @staticmethod
    def create_battery_info(parsed_data: dict[str, Any]) -> dict[str, Any]:
        """
        Create a standardized battery info object from parsed data.

        Args:
            parsed_data: Parsed battery data

        Returns:
            Standardized battery info dictionary
        """
        if not parsed_data:
            return {}

        return {
            "device_type": "BM2",
            "voltage": parsed_data.get("voltage"),
            "current": parsed_data.get("current"),
            "temperature": parsed_data.get("temperature"),
            "state_of_charge": parsed_data.get("state_of_charge"),
            "capacity": parsed_data.get("capacity"),
            "power": parsed_data.get("power"),
            "raw_voltage_mv": parsed_data.get("voltage_mv"),
            "raw_current_ma": parsed_data.get("current_ma"),
            "raw_capacity_mah": parsed_data.get("capacity_mah"),
            "timestamp": parsed_data.get("timestamp"),
        }

    @staticmethod
    def is_valid_alarm_type(alarm_type: int) -> bool:
        """
        Check if alarm type is valid.

        Args:
            alarm_type: Alarm type code

        Returns:
            True if valid, False otherwise
        """
        valid_alarms = {
            ALARM_LOW_VOLTAGE,
            ALARM_HIGH_VOLTAGE,
            ALARM_LOW_TEMPERATURE,
            ALARM_HIGH_TEMPERATURE,
        }
        return alarm_type in valid_alarms

    @staticmethod
    def is_valid_display_mode(display_mode: int) -> bool:
        """
        Check if display mode is valid.

        Args:
            display_mode: Display mode code

        Returns:
            True if valid, False otherwise
        """
        valid_modes = {DISPLAY_BASIC, DISPLAY_ADVANCED, DISPLAY_DETAILED}
        return display_mode in valid_modes

    @staticmethod
    def format_voltage(voltage_v: float) -> str:
        """
        Format voltage for display.

        Args:
            voltage_v: Voltage in volts

        Returns:
            Formatted voltage string
        """
        return f"{voltage_v:.2f}V"

    @staticmethod
    def format_current(current_a: float) -> str:
        """
        Format current for display.

        Args:
            current_a: Current in amps

        Returns:
            Formatted current string
        """
        if current_a >= 0:
            return f"+{current_a:.3f}A"
        return f"{current_a:.3f}A"

    @staticmethod
    def format_temperature(temperature_c: float) -> str:
        """
        Format temperature for display.

        Args:
            temperature_c: Temperature in Celsius

        Returns:
            Formatted temperature string
        """
        return f"{temperature_c:.1f}°C"

    @staticmethod
    def format_soc(soc_percent: int) -> str:
        """
        Format state of charge for display.

        Args:
            soc_percent: State of charge as percentage

        Returns:
            Formatted SOC string
        """
        return f"{soc_percent}%"

    @staticmethod
    def format_capacity(capacity_ah: float) -> str:
        """
        Format capacity for display.

        Args:
            capacity_ah: Capacity in Ah

        Returns:
            Formatted capacity string
        """
        return f"{capacity_ah:.3f}Ah"
