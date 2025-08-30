"""BM6 data parsing utilities."""

from __future__ import annotations

import logging
from typing import Any

from .constants import (
    CAPACITY_CONVERSION_FACTOR,
    CELL_VOLTAGE_CONVERSION_FACTOR,
    CURRENT_CONVERSION_FACTOR,
    MIN_BASIC_INFO_LENGTH,
    MIN_CELL_VOLTAGES_LENGTH,
    MIN_NOTIFICATION_LENGTH,
    SOC_PATTERN,
    SOFTWARE_VERSION_CONVERSION_FACTOR,
    TEMPERATURE_CONVERSION_FACTOR,
    TEMPERATURE_PATTERN,
    TEMPERATURE_SIGN_BIT,
    VOLTAGE_CONVERSION_FACTOR,
    VOLTAGE_PATTERN,
)
from .crypto import BM6Crypto
from .protocol import (
    CMD_REQUEST_BASIC_INFO,
    CMD_REQUEST_CELL_VOLTAGES,
    decode_fet_status,
    decode_production_date,
    decode_protection_status,
    extract_command,
    validate_response,
)


class BM6Parser:
    """Parser for BM6 device responses."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Initialize BM6 parser with crypto support."""
        self.logger = logger or logging.getLogger(__name__)
        self.crypto = BM6Crypto(logger)

    def parse_response(self, data: bytes) -> dict[str, Any] | None:
        """
        Parse response data from BM6 device.

        Args:
            data: Raw response data from device

        Returns:
            Parsed data dictionary or None if invalid
        """
        if not validate_response(data):
            return None

        command = extract_command(data)
        if command is None:
            return None

        if command == CMD_REQUEST_BASIC_INFO:
            return self._parse_basic_info(data)
        if command == CMD_REQUEST_CELL_VOLTAGES:
            return self._parse_cell_voltages(data)
        return None  # Unknown command

    def parse_real_bm6_data(self, data: bytes) -> dict[str, Any] | None:
        """
        Parse real BM6 data with AES decryption.

        Args:
            data: Raw encrypted data from device

        Returns:
            Parsed data dictionary or None if invalid
        """
        try:
            # Decrypt the data
            decrypted = self.crypto.decrypt(data)

            # Try to parse as real-time data first
            result = self._parse_real_time_data(decrypted)
            if result:
                return result

            # Fall back to legacy parsing
            return self.parse_notification(decrypted)

        except Exception:
            self.logger.exception("Failed to parse real BM6 data")
            return None

    def _parse_real_time_data(self, data: bytes) -> dict[str, Any] | None:
        """
        Parse real-time BM6 data with hex patterns.

        Args:
            data: Decrypted data from device

        Returns:
            Parsed data dictionary or None if invalid
        """
        result: dict[str, Any] = {}

        # Convert to hex string for pattern matching
        hex_data = data.hex()

        # Parse voltage (pattern: 55aa + 4 hex digits)
        voltage_match = self._find_pattern(hex_data, VOLTAGE_PATTERN)
        if voltage_match:
            voltage_hex = voltage_match[4:8]  # 4 hex digits after pattern
            try:
                voltage_raw = int(voltage_hex, 16)
                voltage = voltage_raw / VOLTAGE_CONVERSION_FACTOR
                result["voltage"] = voltage
            except ValueError:
                self.logger.warning("Failed to parse voltage from hex: %s", voltage_hex)

        # Parse temperature (pattern: 55bb + 4 hex digits)
        temp_match = self._find_pattern(hex_data, TEMPERATURE_PATTERN)
        if temp_match:
            temp_hex = temp_match[4:8]  # 4 hex digits after pattern
            try:
                temp_raw = int(temp_hex, 16)

                # Check for negative temperature sign bit
                if temp_raw & TEMPERATURE_SIGN_BIT:
                    # Negative temperature
                    temp_raw = temp_raw & 0xFFFE  # Clear sign bit
                    temperature = -(temp_raw / TEMPERATURE_CONVERSION_FACTOR)
                else:
                    # Positive temperature
                    temperature = temp_raw / TEMPERATURE_CONVERSION_FACTOR

                result["temperature"] = temperature
            except ValueError:
                self.logger.warning(
                    "Failed to parse temperature from hex: %s",
                    temp_hex,
                )

        # Parse state of charge (pattern: 55cc + 2 hex digits)
        soc_match = self._find_pattern(hex_data, SOC_PATTERN)
        if soc_match:
            soc_hex = soc_match[4:6]  # 2 hex digits after pattern
            try:
                soc_raw = int(soc_hex, 16)
                state_of_charge = soc_raw  # Already in percentage (0-100)
                result["state_of_charge"] = state_of_charge
            except ValueError:
                self.logger.warning("Failed to parse SOC from hex: %s", soc_hex)

        return result if result else None

    def _find_pattern(self, hex_data: str, pattern: str) -> str | None:
        """
        Find a pattern in hex data.

        Args:
            hex_data: Hex string data
            pattern: Pattern to find

        Returns:
            Found pattern with data or None
        """
        try:
            index = hex_data.find(pattern)
            if index != -1:
                # Return pattern + next 4 characters (for voltage/temp) or 2 (for SOC)
                data_length = (
                    4 if pattern in [VOLTAGE_PATTERN, TEMPERATURE_PATTERN] else 2
                )
                end_index = index + len(pattern) + data_length
                if end_index <= len(hex_data):
                    return hex_data[index:end_index]
        except (ValueError, IndexError) as exc:
            self.logger.debug("Error finding pattern %s: %s", pattern, exc)
        return None

    @staticmethod
    def _parse_basic_info(data: bytes) -> dict[str, Any] | None:
        """
        Parse basic information response.

        Args:
            data: Raw response data

        Returns:
            Parsed basic info dictionary or None if invalid
        """
        if len(data) < MIN_BASIC_INFO_LENGTH:  # Minimum length for basic info
            return None

        result = {
            "voltage": int.from_bytes(data[4:6], byteorder="little")
            / VOLTAGE_CONVERSION_FACTOR,  # Volts
            "current": int.from_bytes(data[6:8], byteorder="little", signed=True)
            / CURRENT_CONVERSION_FACTOR,  # Amps
            "remaining_capacity": int.from_bytes(data[8:10], byteorder="little")
            / CAPACITY_CONVERSION_FACTOR,  # Ah
            "nominal_capacity": int.from_bytes(data[10:12], byteorder="little")
            / CAPACITY_CONVERSION_FACTOR,  # Ah
            "cycles": int.from_bytes(data[12:14], byteorder="little"),
            "production_date": decode_production_date(
                int.from_bytes(data[14:16], byteorder="little"),
            ),
            "balance_status": int.from_bytes(data[16:18], byteorder="little"),
            "protection_status": decode_protection_status(
                int.from_bytes(data[18:20], byteorder="little"),
            ),
            "software_version": data[20] / SOFTWARE_VERSION_CONVERSION_FACTOR,
            "state_of_charge": data[21],  # 0-100%
            "fet_status": decode_fet_status(data[22]),
            "cell_count": data[23],
        }

        # Parse cell voltages if included
        cell_voltages = []
        cell_count = result["cell_count"]
        for i in range(cell_count):
            if len(data) >= 24 + ((i + 1) * 2):
                offset = 24 + (i * 2)
                cell_voltage = (
                    int.from_bytes(data[offset : offset + 2], byteorder="little")
                    / CELL_VOLTAGE_CONVERSION_FACTOR
                )  # Volts
                cell_voltages.append(cell_voltage)

        if cell_voltages:
            result["cell_voltages"] = cell_voltages

        # Parse temperatures if included
        temp_offset = 24 + (cell_count * 2)
        temperatures = []
        temp_count = (len(data) - temp_offset - 1) // 2  # -1 for end marker

        for i in range(temp_count):
            if len(data) >= temp_offset + ((i + 1) * 2):
                offset = temp_offset + (i * 2)
                temp = (
                    int.from_bytes(
                        data[offset : offset + 2],
                        byteorder="little",
                        signed=True,
                    )
                    / TEMPERATURE_CONVERSION_FACTOR
                )  # Celsius
                temperatures.append(temp)

        if temperatures:
            result["temperatures"] = temperatures

        return result

    @staticmethod
    def _parse_cell_voltages(data: bytes) -> dict[str, Any] | None:
        """
        Parse cell voltages response.

        Args:
            data: Raw response data

        Returns:
            Parsed cell voltages dictionary or None if invalid
        """
        if (
            len(data) < MIN_CELL_VOLTAGES_LENGTH
        ):  # Minimum length for cell voltages response
            return None

        cell_count = data[4]
        result: dict[str, Any] = {"cell_count": cell_count}

        # Parse cell voltages
        cell_voltages: list[float] = []
        for i in range(cell_count):
            if len(data) >= 5 + ((i + 1) * 2):
                offset = 5 + (i * 2)
                cell_voltage = (
                    int.from_bytes(data[offset : offset + 2], byteorder="little")
                    / CELL_VOLTAGE_CONVERSION_FACTOR
                )  # Volts
                cell_voltages.append(cell_voltage)

        result["cell_voltages"] = cell_voltages
        return result

    def parse_notification(self, data: bytes) -> dict[str, Any] | None:
        """
        Parse notification data from BM6 device (legacy format).

        This method handles the older notification format used by some BM6 implementations.

        Args:
            data: Raw notification data

        Returns:
            Parsed data dictionary or None if invalid
        """
        if len(data) < MIN_NOTIFICATION_LENGTH:
            return None  # Invalid data length

        # Extract basic parameters
        voltage = (
            int.from_bytes(data[0:2], byteorder="little") / VOLTAGE_CONVERSION_FACTOR
        )  # Volts
        current = (
            int.from_bytes(data[2:4], byteorder="little", signed=True)
            / CURRENT_CONVERSION_FACTOR
        )  # Amps
        remaining_capacity = (
            int.from_bytes(data[4:6], byteorder="little") / CAPACITY_CONVERSION_FACTOR
        )  # Ah
        nominal_capacity = (
            int.from_bytes(data[6:8], byteorder="little") / CAPACITY_CONVERSION_FACTOR
        )  # Ah
        cycles = int.from_bytes(data[8:10], byteorder="little")
        production_date = int.from_bytes(data[10:12], byteorder="little")
        balance_status = int.from_bytes(data[12:14], byteorder="little")
        protection_status = int.from_bytes(data[14:16], byteorder="little")
        software_version = data[16] / SOFTWARE_VERSION_CONVERSION_FACTOR
        remaining_capacity_percent = data[17]  # 0-100%
        fet_status = data[18]
        cell_count = data[19]

        result = {
            "voltage": voltage,
            "current": current,
            "remaining_capacity": remaining_capacity,
            "nominal_capacity": nominal_capacity,
            "cycles": cycles,
            "production_date": decode_production_date(production_date),
            "balance_status": balance_status,
            "protection_status": decode_protection_status(protection_status),
            "software_version": software_version,
            "state_of_charge": remaining_capacity_percent,
            "fet_status": decode_fet_status(fet_status),
            "cell_count": cell_count,
        }

        # Process cell voltages if available
        cell_voltages = []
        if len(data) >= 20 + (cell_count * 2):
            for i in range(cell_count):
                offset = 20 + (i * 2)
                cell_voltage = (
                    int.from_bytes(data[offset : offset + 2], byteorder="little")
                    / CELL_VOLTAGE_CONVERSION_FACTOR
                )
                cell_voltages.append(cell_voltage)

        if cell_voltages:
            result["cell_voltages"] = cell_voltages

        # Process temperatures if available
        temperatures = []
        temp_count = (len(data) - 20 - (cell_count * 2)) // 2
        for i in range(temp_count):
            offset = 20 + (cell_count * 2) + (i * 2)
            if len(data) >= offset + 2:
                temp = (
                    int.from_bytes(
                        data[offset : offset + 2],
                        byteorder="little",
                        signed=True,
                    )
                    / TEMPERATURE_CONVERSION_FACTOR
                )
                temperatures.append(temp)

        if temperatures:
            result["temperatures"] = temperatures

        return result
