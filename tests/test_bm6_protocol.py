"""Tests for BM6 protocol command building and validation."""

from __future__ import annotations

from src.battery_hawk_driver.bm6.constants import (
    CMD_REQUEST_BASIC_INFO,
    CMD_REQUEST_CELL_VOLTAGES,
    CMD_SET_PARAMETER,
    END_MARKER,
    PROTOCOL_VERSION,
    START_MARKER,
)
from src.battery_hawk_driver.bm6.protocol import (
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


class TestBM6Protocol:
    """Test BM6 protocol functions."""

    def test_build_command_basic(self) -> None:
        """Test building a basic command without data."""
        command = build_command(CMD_REQUEST_BASIC_INFO)

        # Check structure: [START_MARKER, PROTOCOL_VERSION, CMD, LEN, CHECKSUM, END_MARKER]
        assert len(command) == 6
        assert command[0] == START_MARKER
        assert command[1] == PROTOCOL_VERSION
        assert command[2] == CMD_REQUEST_BASIC_INFO
        assert command[3] == 0  # No data
        assert command[5] == END_MARKER

    def test_build_command_with_data(self) -> None:
        """Test building a command with data."""
        data = b"\x01\x02\x03"
        command = build_command(CMD_SET_PARAMETER, data)

        # Check structure: [START_MARKER, PROTOCOL_VERSION, CMD, LEN, DATA..., CHECKSUM, END_MARKER]
        assert len(command) == 9  # 6 + 3 data bytes
        assert command[0] == START_MARKER
        assert command[1] == PROTOCOL_VERSION
        assert command[2] == CMD_SET_PARAMETER
        assert command[3] == 3  # Data length
        assert command[4:7] == data
        assert command[8] == END_MARKER

    def test_build_basic_info_request(self) -> None:
        """Test building basic info request command."""
        command = build_basic_info_request()

        assert len(command) == 6
        assert command[0] == START_MARKER
        assert command[1] == PROTOCOL_VERSION
        assert command[2] == CMD_REQUEST_BASIC_INFO
        assert command[3] == 0  # No data
        assert command[5] == END_MARKER

    def test_build_cell_voltages_request(self) -> None:
        """Test building cell voltages request command."""
        command = build_cell_voltages_request()

        assert len(command) == 6
        assert command[0] == START_MARKER
        assert command[1] == PROTOCOL_VERSION
        assert command[2] == CMD_REQUEST_CELL_VOLTAGES
        assert command[3] == 0  # No data
        assert command[5] == END_MARKER

    def test_build_set_parameter_command(self) -> None:
        """Test building set parameter command."""
        command = build_set_parameter_command(0x01, 0x1234)

        assert len(command) == 9
        assert command[0] == START_MARKER
        assert command[1] == PROTOCOL_VERSION
        assert command[2] == CMD_SET_PARAMETER
        assert command[3] == 3  # 3 data bytes
        assert command[4] == 0x01  # Parameter ID
        assert command[5] == 0x34  # Value low byte
        assert command[6] == 0x12  # Value high byte
        assert command[8] == END_MARKER

    def test_validate_response_valid(self) -> None:
        """Test validating a valid response."""
        # Create a valid response packet
        response = bytes(
            [
                START_MARKER,
                PROTOCOL_VERSION,
                CMD_REQUEST_BASIC_INFO,
                0,
                0xFA,
                END_MARKER,
            ],
        )
        assert validate_response(response) is True

    def test_validate_response_invalid_start(self) -> None:
        """Test validating response with invalid start marker."""
        response = bytes(
            [0x00, PROTOCOL_VERSION, CMD_REQUEST_BASIC_INFO, 0, 0xFA, END_MARKER],
        )
        assert validate_response(response) is False

    def test_validate_response_invalid_end(self) -> None:
        """Test validating response with invalid end marker."""
        response = bytes(
            [START_MARKER, PROTOCOL_VERSION, CMD_REQUEST_BASIC_INFO, 0, 0xFA, 0x00],
        )
        assert validate_response(response) is False

    def test_validate_response_too_short(self) -> None:
        """Test validating response that's too short."""
        response = bytes([START_MARKER, PROTOCOL_VERSION])
        assert validate_response(response) is False

    def test_extract_command_valid(self) -> None:
        """Test extracting command from valid response."""
        response = bytes(
            [
                START_MARKER,
                PROTOCOL_VERSION,
                CMD_REQUEST_BASIC_INFO,
                0,
                0xFA,
                END_MARKER,
            ],
        )
        assert extract_command(response) == CMD_REQUEST_BASIC_INFO

    def test_extract_command_invalid(self) -> None:
        """Test extracting command from invalid response."""
        response = bytes(
            [0x00, PROTOCOL_VERSION, CMD_REQUEST_BASIC_INFO, 0, 0xFA, END_MARKER],
        )
        assert extract_command(response) is None

    def test_decode_production_date(self) -> None:
        """Test decoding production date."""
        # Example: 2021-09-05
        raw_date = 0x2B25  # (21 << 9) | (9 << 5) | 5 = 11045
        date_str = decode_production_date(raw_date)
        assert date_str == "2021-09-05"

    def test_decode_production_date_2023(self) -> None:
        """Test decoding production date for 2023."""
        # Example: 2023-12-31
        raw_date = 0x2F9F  # (23 << 9) | (12 << 5) | 31 = 12191
        date_str = decode_production_date(raw_date)
        assert date_str == "2023-12-31"

    def test_decode_protection_status(self) -> None:
        """Test decoding protection status."""
        # Test various protection flags
        status = 0x0001  # Single cell overvoltage
        protections = decode_protection_status(status)
        assert protections["single_cell_overvoltage"] is True
        assert protections["single_cell_undervoltage"] is False
        assert protections["battery_overvoltage"] is False

        # Test multiple flags
        status = 0x0003  # Single cell overvoltage + undervoltage
        protections = decode_protection_status(status)
        assert protections["single_cell_overvoltage"] is True
        assert protections["single_cell_undervoltage"] is True
        assert protections["battery_overvoltage"] is False

        # Test all flags
        status = 0x1FFF  # All protection flags
        protections = decode_protection_status(status)
        for flag in protections.values():
            assert flag is True

    def test_decode_fet_status(self) -> None:
        """Test decoding FET status."""
        # Test charging only
        status = 0x01
        fet_status = decode_fet_status(status)
        assert fet_status["charging"] is True
        assert fet_status["discharging"] is False

        # Test discharging only
        status = 0x02
        fet_status = decode_fet_status(status)
        assert fet_status["charging"] is False
        assert fet_status["discharging"] is True

        # Test both
        status = 0x03
        fet_status = decode_fet_status(status)
        assert fet_status["charging"] is True
        assert fet_status["discharging"] is True

        # Test neither
        status = 0x00
        fet_status = decode_fet_status(status)
        assert fet_status["charging"] is False
        assert fet_status["discharging"] is False
