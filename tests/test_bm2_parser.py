"""Tests for BM2Parser data parsing and validation."""

from src.battery_hawk_driver.bm2.constants import (
    ALARM_HIGH_TEMPERATURE,
    ALARM_HIGH_VOLTAGE,
    ALARM_LOW_TEMPERATURE,
    ALARM_LOW_VOLTAGE,
    DISPLAY_ADVANCED,
    DISPLAY_BASIC,
    DISPLAY_DETAILED,
)
from src.battery_hawk_driver.bm2.parser import BM2Parser


class TestBM2Parser:
    """Test cases for BM2Parser."""

    def test_parse_data_packet_valid(self) -> None:
        """Test parsing a valid BM2 data packet."""
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

        result = BM2Parser.parse_data_packet(bytes(data))

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

    def test_parse_data_packet_invalid_length(self) -> None:
        """Test parsing a data packet with invalid length."""
        data = b"\xaa\x18\x31"  # Too short
        result = BM2Parser.parse_data_packet(data)
        assert result is None

    def test_parse_data_packet_invalid_header(self) -> None:
        """Test parsing a data packet with invalid header."""
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
        result = BM2Parser.parse_data_packet(bytes(data))
        assert result is None

    def test_parse_data_packet_invalid_checksum(self) -> None:
        """Test parsing a data packet with invalid checksum."""
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
        result = BM2Parser.parse_data_packet(bytes(data))
        assert result is None

    def test_parse_voltage_data(self) -> None:
        """Test parsing voltage data."""
        # Use correct packet structure where voltage is at positions 1-2
        # Voltage: 12600 mV (12.6V) = 0x3138 in little-endian
        data = b"\xaa\x38\x31\xb0\x04\xfa\x00\x55\x50\xc3\x01"
        voltage = BM2Parser.parse_voltage_data(data)
        assert voltage == 12.6

    def test_parse_voltage_data_insufficient_length(self) -> None:
        """Test parsing voltage data with insufficient length."""
        data = b"\xaa\x18"
        voltage = BM2Parser.parse_voltage_data(data)
        assert voltage is None

    def test_parse_current_data(self) -> None:
        """Test parsing current data."""
        data = b"\xaa\x18\x31\xb0\x04\xfa\x00\x55\x50\xc3\x01"
        current = BM2Parser.parse_current_data(data)
        assert current == 1.2

    def test_parse_current_data_negative(self) -> None:
        """Test parsing negative current data."""
        # Current: -1920 mA (-1.92A) = 0xF880 in little-endian (signed)
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
        current = BM2Parser.parse_current_data(bytes(data))
        assert current == -1.92

    def test_parse_current_data_insufficient_length(self) -> None:
        """Test parsing current data with insufficient length."""
        data = b"\xaa\x18\x31"
        current = BM2Parser.parse_current_data(data)
        assert current is None

    def test_parse_temperature_data(self) -> None:
        """Test parsing temperature data."""
        data = b"\xaa\x18\x31\xb0\x04\xfa\x00\x55\x50\xc3\x01"
        temperature = BM2Parser.parse_temperature_data(data)
        assert temperature == 25.0

    def test_parse_temperature_data_negative(self) -> None:
        """Test parsing negative temperature data."""
        # Temperature: -250 (-25.0°C) = 0xFF06 in little-endian (signed)
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
        temperature = BM2Parser.parse_temperature_data(bytes(data))
        assert temperature == -25.0

    def test_parse_temperature_data_insufficient_length(self) -> None:
        """Test parsing temperature data with insufficient length."""
        data = b"\xaa\x18\x31\xb0\x04"
        temperature = BM2Parser.parse_temperature_data(data)
        assert temperature is None

    def test_parse_soc_data(self) -> None:
        """Test parsing state of charge data."""
        data = b"\xaa\x18\x31\xb0\x04\xfa\x00\x55\x50\xc3\x01"
        soc = BM2Parser.parse_soc_data(data)
        assert soc == 85

    def test_parse_soc_data_invalid_value(self) -> None:
        """Test parsing SOC data with invalid value."""
        data = bytearray(
            [
                0xAA,  # Header
                0x18,  # Length
                0x31,  # Command
                0xB0,  # Voltage low byte
                0x04,  # Voltage high byte
                0xFA,  # Current low byte
                0x00,  # Current high byte
                0xFF,  # Invalid SOC value
                0x50,  # Capacity low byte
                0xC3,  # Capacity high byte
                0x01,  # Checksum
            ],
        )
        soc = BM2Parser.parse_soc_data(bytes(data))
        assert soc is None

    def test_parse_soc_data_insufficient_length(self) -> None:
        """Test parsing SOC data with insufficient length."""
        data = b"\xaa\x18\x31\xb0\x04\xfa\x00"
        soc = BM2Parser.parse_soc_data(data)
        assert soc is None

    def test_parse_capacity_data(self) -> None:
        """Test parsing capacity data."""
        data = b"\xaa\x18\x31\xb0\x04\xfa\x00\x55\x50\xc3\x01"
        capacity = BM2Parser.parse_capacity_data(data)
        assert capacity == 50.0

    def test_parse_capacity_data_insufficient_length(self) -> None:
        """Test parsing capacity data with insufficient length."""
        data = b"\xaa\x18\x31\xb0\x04\xfa\x00\x55"
        capacity = BM2Parser.parse_capacity_data(data)
        assert capacity is None

    def test_validate_checksum_valid(self) -> None:
        """Test checksum validation with valid data."""
        data = bytearray([0xAA, 0x18, 0x31, 0xB0, 0x04, 0xFA, 0x00, 0x55, 0x50, 0xC3])
        # Calculate correct checksum
        checksum = 0
        for i in range(len(data)):
            checksum ^= data[i]
        data.append(checksum)

        assert BM2Parser.validate_checksum(bytes(data)) is True

    def test_validate_checksum_invalid(self) -> None:
        """Test checksum validation with invalid data."""
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
        assert BM2Parser.validate_checksum(bytes(data)) is False

    def test_extract_raw_values(self) -> None:
        """Test extracting raw values from data packet."""
        # Structure: [Header, Voltage(2), Current(2), Temperature(2), SOC(1), Capacity(2), Checksum]
        # Voltage: 12600 mV (12.6V) = 0x3138 in little-endian
        # Current: 1200 mA (1.2A) = 0x04B0 in little-endian
        # Temperature: 250 (25.0°C) = 0x00FA in little-endian
        # SOC: 85%
        # Capacity: 50000 mAh (50.0Ah) = 0xC350 in little-endian
        data = bytearray([0xAA, 0x38, 0x31, 0xB0, 0x04, 0xFA, 0x00, 0x55, 0x50, 0xC3])
        # Calculate correct checksum
        checksum = 0
        for i in range(len(data)):
            checksum ^= data[i]
        data.append(checksum)

        raw_values = BM2Parser.extract_raw_values(bytes(data))

        assert raw_values is not None
        assert raw_values["voltage_mv"] == 12600  # 0x3138 in little-endian
        assert raw_values["current_ma"] == 1200  # 0x04B0 in little-endian
        assert raw_values["temperature_decidegc"] == 250  # 0x00FA in little-endian
        assert raw_values["soc_percent"] == 85  # 0x55
        assert raw_values["capacity_mah"] == 50000  # 0xC350 in little-endian

    def test_create_battery_info(self) -> None:
        """Test creating battery info from parsed data."""
        parsed_data = {
            "voltage": 12.6,
            "current": 1.2,
            "temperature": 25.0,
            "state_of_charge": 85,
            "capacity": 50.0,
            "power": 15.12,
            "voltage_mv": 12600,
            "current_ma": 1200,
            "capacity_mah": 50000,
            "timestamp": 1234567890.0,
        }

        battery_info = BM2Parser.create_battery_info(parsed_data)

        assert battery_info["voltage"] == 12.6
        assert battery_info["current"] == 1.2
        assert battery_info["temperature"] == 25.0
        assert battery_info["state_of_charge"] == 85
        assert battery_info["capacity"] == 50.0
        assert battery_info["power"] == 15.12
        assert battery_info["timestamp"] == 1234567890.0
        assert battery_info["raw_voltage_mv"] == 12600
        assert battery_info["raw_current_ma"] == 1200
        assert battery_info["raw_capacity_mah"] == 50000

    def test_create_battery_info_empty(self) -> None:
        """Test creating battery info from empty data."""
        battery_info = BM2Parser.create_battery_info({})
        assert battery_info == {}

    def test_is_valid_alarm_type(self) -> None:
        """Test alarm type validation."""
        assert BM2Parser.is_valid_alarm_type(ALARM_LOW_VOLTAGE) is True
        assert BM2Parser.is_valid_alarm_type(ALARM_HIGH_VOLTAGE) is True
        assert BM2Parser.is_valid_alarm_type(ALARM_LOW_TEMPERATURE) is True
        assert BM2Parser.is_valid_alarm_type(ALARM_HIGH_TEMPERATURE) is True
        assert BM2Parser.is_valid_alarm_type(0xFF) is False

    def test_is_valid_display_mode(self) -> None:
        """Test display mode validation."""
        assert BM2Parser.is_valid_display_mode(DISPLAY_BASIC) is True
        assert BM2Parser.is_valid_display_mode(DISPLAY_ADVANCED) is True
        assert BM2Parser.is_valid_display_mode(DISPLAY_DETAILED) is True
        assert BM2Parser.is_valid_display_mode(0xFF) is False

    def test_format_voltage(self) -> None:
        """Test voltage formatting."""
        assert BM2Parser.format_voltage(12.6) == "12.60V"
        assert BM2Parser.format_voltage(3.7) == "3.70V"

    def test_format_current(self) -> None:
        """Test current formatting."""
        assert BM2Parser.format_current(1.2) == "+1.200A"
        assert BM2Parser.format_current(-0.5) == "-0.500A"
        assert BM2Parser.format_current(0.0) == "+0.000A"

    def test_format_temperature(self) -> None:
        """Test temperature formatting."""
        assert BM2Parser.format_temperature(25.0) == "25.0°C"
        assert BM2Parser.format_temperature(-10.5) == "-10.5°C"

    def test_format_soc(self) -> None:
        """Test SOC formatting."""
        assert BM2Parser.format_soc(85) == "85%"
        assert BM2Parser.format_soc(100) == "100%"

    def test_format_capacity(self) -> None:
        """Test capacity formatting."""
        assert BM2Parser.format_capacity(50.0) == "50.000Ah"
        assert BM2Parser.format_capacity(12.5) == "12.500Ah"
