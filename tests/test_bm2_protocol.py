"""Unit tests for BM2 protocol."""

from src.battery_hawk_driver.bm2.constants import (
    ALARM_HIGH_TEMPERATURE,
    ALARM_HIGH_VOLTAGE,
    ALARM_LOW_TEMPERATURE,
    ALARM_LOW_VOLTAGE,
    CMD_CONFIGURE_DISPLAY,
    CMD_REQUEST_BATTERY_DATA,
    CMD_RESET_DEVICE,
    CMD_SET_ALARM_THRESHOLD,
    CMD_SET_BATTERY_CAPACITY,
    DISPLAY_ADVANCED,
    DISPLAY_BASIC,
    DISPLAY_DETAILED,
)
from src.battery_hawk_driver.bm2.protocol import (
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


class TestBM2Protocol:
    """Test cases for BM2 protocol functions."""

    def test_build_request_battery_data_command(self) -> None:
        """Test building request battery data command."""
        command = build_request_battery_data_command()
        assert command == bytes([CMD_REQUEST_BATTERY_DATA])

    def test_build_set_alarm_threshold_command(self) -> None:
        """Test building set alarm threshold command."""
        command = build_set_alarm_threshold_command(ALARM_LOW_VOLTAGE, 11000)
        expected = [
            CMD_SET_ALARM_THRESHOLD,
            ALARM_LOW_VOLTAGE,
            0xF8,
            0x2A,
        ]  # 11000 in little-endian
        assert command == bytes(expected)

    def test_build_set_alarm_threshold_command_high_value(self) -> None:
        """Test building set alarm threshold command with high value."""
        command = build_set_alarm_threshold_command(ALARM_HIGH_VOLTAGE, 15000)
        expected = [
            CMD_SET_ALARM_THRESHOLD,
            ALARM_HIGH_VOLTAGE,
            0x98,
            0x3A,
        ]  # 15000 in little-endian
        assert command == bytes(expected)

    def test_build_configure_display_command(self) -> None:
        """Test building configure display command."""
        command = build_configure_display_command(DISPLAY_BASIC)
        assert command == bytes([CMD_CONFIGURE_DISPLAY, DISPLAY_BASIC])

    def test_build_configure_display_command_advanced(self) -> None:
        """Test building configure display command for advanced mode."""
        command = build_configure_display_command(DISPLAY_ADVANCED)
        assert command == bytes([CMD_CONFIGURE_DISPLAY, DISPLAY_ADVANCED])

    def test_build_reset_device_command(self) -> None:
        """Test building reset device command."""
        command = build_reset_device_command()
        assert command == bytes([CMD_RESET_DEVICE])

    def test_build_set_battery_capacity_command(self) -> None:
        """Test building set battery capacity command."""
        command = build_set_battery_capacity_command(50000)
        expected = [CMD_SET_BATTERY_CAPACITY, 0x50, 0xC3]  # 50000 in little-endian
        assert command == bytes(expected)

    def test_validate_data_packet_valid(self) -> None:
        """Test validating a valid data packet."""
        # Create a valid BM2 data packet
        data = bytearray(
            [
                0xAA,  # Header
                0x18,  # Length
                0x31,  # Command
                0xB0,  # Voltage low byte
                0x04,  # Voltage high byte
                0xFA,  # Current low byte
                0x00,  # Current high byte
                0x55,  # SOC
                0x50,  # Capacity low byte
                0xC3,  # Capacity high byte
            ],
        )
        # Calculate correct checksum
        checksum = 0
        for i in range(len(data)):
            checksum ^= data[i]
        data.append(checksum)

        assert validate_data_packet(bytes(data)) is True

    def test_validate_data_packet_invalid_length(self) -> None:
        """Test validating a data packet with invalid length."""
        data = b"\xaa\x18\x31"  # Too short
        assert validate_data_packet(data) is False

    def test_validate_data_packet_invalid_header(self) -> None:
        """Test validating a data packet with invalid header."""
        data = bytearray(
            [
                0xBB,  # Wrong header
                0x18,  # Length
                0x31,  # Command
                0xB0,  # Voltage low byte
                0x04,  # Voltage high byte
                0xFA,  # Current low byte
                0x00,  # Current high byte
                0x55,  # SOC
                0x50,  # Capacity low byte
                0xC3,  # Capacity high byte
                0x01,  # Checksum
            ],
        )
        assert validate_data_packet(bytes(data)) is False

    def test_validate_data_packet_invalid_checksum(self) -> None:
        """Test validating a data packet with invalid checksum."""
        data = bytearray(
            [
                0xAA,  # Header
                0x18,  # Length
                0x31,  # Command
                0xB0,  # Voltage low byte
                0x04,  # Voltage high byte
                0xFA,  # Current low byte
                0x00,  # Current high byte
                0x55,  # SOC
                0x50,  # Capacity low byte
                0xC3,  # Capacity high byte
                0xFF,  # Wrong checksum
            ],
        )
        assert validate_data_packet(bytes(data)) is False

    def test_parse_battery_data_valid(self) -> None:
        """Test parsing valid battery data."""
        # Create a valid BM2 data packet
        # Structure: [Header, Voltage(2), Current(2), Temperature(2), SOC(1), Capacity(2), Checksum]
        # Voltage: 12600 mV (12.6V) = 0x3138 in little-endian
        # Current: 1200 mA (1.2A) = 0x04B0 in little-endian
        # Temperature: 250 (25.0°C) = 0x00FA in little-endian
        # SOC: 85%
        # Capacity: 50000 mAh (50.0Ah) = 0xC350 in little-endian
        data = bytearray(
            [
                0xAA,  # Header
                0x38,  # Voltage low byte (12600 = 0x3138)
                0x31,  # Voltage high byte
                0xB0,  # Current low byte (1200 = 0x04B0)
                0x04,  # Current high byte
                0xFA,  # Temperature low byte (250 = 0x00FA)
                0x00,  # Temperature high byte
                0x55,  # SOC (85%)
                0x50,  # Capacity low byte (50000 = 0xC350)
                0xC3,  # Capacity high byte
            ],
        )
        # Calculate correct checksum
        checksum = 0
        for i in range(len(data)):
            checksum ^= data[i]
        data.append(checksum)

        result = parse_battery_data(bytes(data))

        assert result is not None
        assert result["voltage"] == 12.6
        assert result["current"] == 1.2
        assert result["temperature"] == 25.0
        assert result["state_of_charge"] == 85
        assert result["capacity"] == 50.0
        assert result["power"] == 15.12  # 12.6 * 1.2
        assert result["voltage_mv"] == 12600
        assert result["current_ma"] == 1200
        assert result["capacity_mah"] == 50000

    def test_parse_battery_data_negative_current(self) -> None:
        """Test parsing battery data with negative current."""
        # Create data packet with negative current (-1920 mA = -1.92A)
        data = bytearray(
            [
                0xAA,  # Header
                0x38,  # Voltage low byte
                0x31,  # Voltage high byte
                0x80,  # Current low byte (negative)
                0xF8,  # Current high byte (negative)
                0xFA,  # Temperature low byte
                0x00,  # Temperature high byte
                0x55,  # SOC
                0x50,  # Capacity low byte
                0xC3,  # Capacity high byte
            ],
        )
        # Calculate correct checksum
        checksum = 0
        for i in range(len(data)):
            checksum ^= data[i]
        data.append(checksum)

        result = parse_battery_data(bytes(data))

        assert result is not None
        assert result["current"] == -1.92
        assert result["power"] == -24.192  # 12.6 * -1.92

    def test_parse_battery_data_negative_temperature(self) -> None:
        """Test parsing battery data with negative temperature."""
        # Create data packet with negative temperature (-250 = -25.0°C)
        data = bytearray(
            [
                0xAA,  # Header
                0x38,  # Voltage low byte
                0x31,  # Voltage high byte
                0xB0,  # Current low byte
                0x04,  # Current high byte
                0x06,  # Temperature low byte (negative)
                0xFF,  # Temperature high byte (negative)
                0x55,  # SOC
                0x50,  # Capacity low byte
                0xC3,  # Capacity high byte
            ],
        )
        # Calculate correct checksum
        checksum = 0
        for i in range(len(data)):
            checksum ^= data[i]
        data.append(checksum)

        result = parse_battery_data(bytes(data))

        assert result is not None
        assert result["temperature"] == -25.0

    def test_parse_battery_data_invalid(self) -> None:
        """Test parsing invalid battery data."""
        data = b"\xaa\x18\x31"  # Too short
        result = parse_battery_data(data)
        assert result is None

    def test_get_alarm_type_name(self) -> None:
        """Test getting alarm type names."""
        assert get_alarm_type_name(ALARM_LOW_VOLTAGE) == "Low Voltage"
        assert get_alarm_type_name(ALARM_HIGH_VOLTAGE) == "High Voltage"
        assert get_alarm_type_name(ALARM_LOW_TEMPERATURE) == "Low Temperature"
        assert get_alarm_type_name(ALARM_HIGH_TEMPERATURE) == "High Temperature"
        assert get_alarm_type_name(0xFF) == "Unknown Alarm (255)"

    def test_get_display_mode_name(self) -> None:
        """Test getting display mode names."""
        assert get_display_mode_name(DISPLAY_BASIC) == "Basic"
        assert get_display_mode_name(DISPLAY_ADVANCED) == "Advanced"
        assert get_display_mode_name(DISPLAY_DETAILED) == "Detailed"
        assert get_display_mode_name(0xFF) == "Unknown Mode (255)"

    def test_command_building_edge_cases(self) -> None:
        """Test command building with edge case values."""
        # Test with zero values
        command = build_set_alarm_threshold_command(ALARM_LOW_VOLTAGE, 0)
        expected = [CMD_SET_ALARM_THRESHOLD, ALARM_LOW_VOLTAGE, 0x00, 0x00]
        assert command == bytes(expected)

        # Test with maximum values
        command = build_set_battery_capacity_command(65535)
        expected = [CMD_SET_BATTERY_CAPACITY, 0xFF, 0xFF]
        assert command == bytes(expected)

    def test_data_parsing_edge_cases(self) -> None:
        """Test data parsing with edge case values."""
        # Test with zero values
        data = bytearray(
            [
                0xAA,  # Header
                0x00,  # Voltage low byte (0V)
                0x00,  # Voltage high byte
                0x00,  # Current low byte (0A)
                0x00,  # Current high byte
                0x00,  # Temperature low byte (0°C)
                0x00,  # Temperature high byte
                0x00,  # SOC (0%)
                0x00,  # Capacity low byte (0Ah)
                0x00,  # Capacity high byte
            ],
        )
        # Calculate correct checksum
        checksum = 0
        for i in range(len(data)):
            checksum ^= data[i]
        data.append(checksum)

        result = parse_battery_data(bytes(data))

        assert result is not None
        assert result["voltage"] == 0.0
        assert result["current"] == 0.0
        assert result["state_of_charge"] == 0
        assert result["capacity"] == 0.0
        assert result["power"] == 0.0
