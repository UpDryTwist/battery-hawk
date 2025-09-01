"""BM6 data parsing utilities."""

from __future__ import annotations

import logging
from typing import Any

from .constants import (
    BM6_REALTIME_RESPONSE_PREFIX,
    BM6_VERSION_RESPONSE_PREFIX,
    CAPACITY_CONVERSION_FACTOR,
    CELL_VOLTAGE_CONVERSION_FACTOR,
    CURRENT_CONVERSION_FACTOR,
    MIN_BASIC_INFO_LENGTH,
    MIN_CELL_VOLTAGES_LENGTH,
    MIN_NOTIFICATION_LENGTH,
    RAPID_ACCELERATION_POSITION_END,
    RAPID_ACCELERATION_POSITION_START,
    RAPID_DECELERATION_POSITION_END,
    RAPID_DECELERATION_POSITION_START,
    SOC_POSITION_END,
    SOC_POSITION_START,
    SOFTWARE_VERSION_CONVERSION_FACTOR,
    STATE_POSITION_END,
    STATE_POSITION_START,
    TEMPERATURE_CONVERSION_FACTOR,
    TEMPERATURE_POSITION_END,
    TEMPERATURE_POSITION_START,
    TEMPERATURE_SIGN_POSITION_END,
    TEMPERATURE_SIGN_POSITION_START,
    VOLTAGE_CONVERSION_FACTOR,
    VOLTAGE_POSITION_END,
    VOLTAGE_POSITION_START,
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
            self.logger.info(
                "Attempting to decrypt BM6 data (%d bytes): %s",
                len(data),
                data.hex(),
            )

            # Decrypt the data
            decrypted = self.crypto.decrypt(data)

            self.logger.info(
                "Decrypted BM6 data (%d bytes): %s",
                len(decrypted),
                decrypted.hex(),
            )

            # Try to parse as real-time data first
            result = self._parse_real_time_data(decrypted)
            if result:
                self.logger.info("Successfully parsed as real-time data: %s", result)
                return result

            # Next, try to parse as version data
            result = self._parse_version_data(decrypted)
            if result:
                self.logger.info("Successfully parsed as version data: %s", result)
                return result

            # Fall back to legacy parsing
            legacy_result = self.parse_notification(decrypted)
            if legacy_result:
                self.logger.info(
                    "Successfully parsed as legacy notification: %s",
                    legacy_result,
                )
                return legacy_result

            # If we get here, all parsing methods failed
            self.logger.info("Failed to parse decrypted data with any method")
            return None  # noqa: TRY300

        except Exception:
            self.logger.exception("Failed to parse real BM6 data")
            return None

    def _parse_real_time_data(self, data: bytes) -> dict[str, Any] | None:
        """
        Parse real-time BM6 data using correct BM6 format.

        Args:
            data: Decrypted data from device

        Returns:
            Parsed data dictionary or None if invalid
        """
        # Convert to hex string for parsing
        hex_data = data.hex()
        self.logger.info("Parsing BM6 real-time data from hex: %s", hex_data)

        # Check if this is a BM6 response (should start with d15507)
        if not hex_data.startswith(BM6_REALTIME_RESPONSE_PREFIX):
            self.logger.info(
                "Data does not start with BM6 response prefix (%s)",
                BM6_REALTIME_RESPONSE_PREFIX,
            )
            return None

        # If the next two characters past the prefix are FF, then this is just an echo and not the real reasponse
        if hex_data[6:8] == "ff":
            self.logger.info("Data is just an echo, not the real response")
            return None

        # Ensure we have enough data
        if len(hex_data) < max(
            VOLTAGE_POSITION_END,
            TEMPERATURE_POSITION_END,
            SOC_POSITION_END,
            STATE_POSITION_END,
            RAPID_ACCELERATION_POSITION_END,
            RAPID_DECELERATION_POSITION_END,
        ):
            self.logger.warning(
                "Insufficient data length (%d chars) for BM6 parsing",
                len(hex_data),
            )
            return None

        result: dict[str, Any] = {}

        try:
            # Parse voltage (position 14-18 in hex string)
            voltage_hex = hex_data[VOLTAGE_POSITION_START:VOLTAGE_POSITION_END]
            voltage_raw = int(voltage_hex, 16)
            voltage = voltage_raw / VOLTAGE_CONVERSION_FACTOR
            result["voltage"] = voltage
            self.logger.info("Parsed voltage: %s -> %.2fV", voltage_hex, voltage)

            # Parse temperature (position 8-10, with sign at 6-8)
            temp_sign_hex = hex_data[
                TEMPERATURE_SIGN_POSITION_START:TEMPERATURE_SIGN_POSITION_END
            ]
            temp_hex = hex_data[TEMPERATURE_POSITION_START:TEMPERATURE_POSITION_END]

            temperature_raw = int(temp_hex, 16)
            temperature_sign = int(temp_sign_hex, 16)

            # For real-time data, temperature is already in degrees Celsius (not decidegrees)
            temperature = float(temperature_raw)
            temperature = -temperature if temperature_sign == 1 else temperature

            result["temperature"] = temperature
            self.logger.info(
                "Parsed temperature: sign=%s, value=%s -> %.1f°C",
                temp_sign_hex,
                temp_hex,
                temperature,
            )

            # Parse state of charge (position 12-14)
            soc_hex = hex_data[SOC_POSITION_START:SOC_POSITION_END]
            soc = int(soc_hex, 16)
            result["state_of_charge"] = soc
            self.logger.info("Parsed SoC: %s -> %d%%", soc_hex, soc)

            # Parse state (position 10-12)
            state_hex = hex_data[STATE_POSITION_START:STATE_POSITION_END]
            state = int(state_hex, 16)
            result["state"] = state
            self.logger.info("Parsed state: %s -> %d", state_hex, state)

            # Parse rapid acceleration (position 18-22)
            rapid_acceleration_hex = hex_data[
                RAPID_ACCELERATION_POSITION_START:RAPID_ACCELERATION_POSITION_END
            ]
            rapid_acceleration = int(rapid_acceleration_hex, 16)
            result["rapid_acceleration"] = rapid_acceleration
            self.logger.info(
                "Parsed rapid acceleration: %s -> %d",
                rapid_acceleration_hex,
                rapid_acceleration,
            )

            # Parse rapid deceleration (position 22-26)
            rapid_deceleration_hex = hex_data[
                RAPID_DECELERATION_POSITION_START:RAPID_DECELERATION_POSITION_END
            ]
            rapid_deceleration = int(rapid_deceleration_hex, 16)
            result["rapid_deceleration"] = rapid_deceleration
            self.logger.info(
                "Parsed rapid deceleration: %s -> %d",
                rapid_deceleration_hex,
                rapid_deceleration,
            )

        except (ValueError, IndexError) as e:
            self.logger.warning("Failed to parse BM6 real-time data: %s", e)
            return None
        else:
            return result

    def _parse_version_data(self, data: bytes) -> dict[str, Any] | None:
        """
        Parse version data from BM6 device.

        Args:
            data: Raw response data

        Returns:
            Parsed version data dictionary or None if invalid
        """
        # Convert to hex string for parsing
        hex_data = data.hex()
        self.logger.info("Parsing BM6 version data from hex: %s", hex_data)

        # Check if this is a BM6 response (should start with d15501)
        if not hex_data.startswith(BM6_VERSION_RESPONSE_PREFIX):
            self.logger.info(
                "Data does not start with BM6 version response prefix (%s)",
                BM6_VERSION_RESPONSE_PREFIX,
            )
            return None

        # The firmware version is in the remainder of the response length, after the header
        try:
            firmware_version = hex_data[6:]
            return {"firmware_version": firmware_version}  # noqa: TRY300
        except (ValueError, IndexError) as e:
            self.logger.warning("Failed to parse BM6 version data: %s", e)
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
