"""Test real BM6 protocol implementation."""

from battery_hawk_driver.bm6.constants import (
    BM6_AES_KEY,
    CMD_REQUEST_VOLTAGE_TEMP,
    SOC_PATTERN,
    TEMPERATURE_PATTERN,
    TEMPERATURE_SIGN_BIT,
    VOLTAGE_PATTERN,
)
from battery_hawk_driver.bm6.crypto import BM6Crypto
from battery_hawk_driver.bm6.parser import BM6Parser
from battery_hawk_driver.bm6.protocol import build_voltage_temp_request


class TestBM6Crypto:
    """Test BM6 AES encryption/decryption."""

    def test_aes_key(self) -> None:
        """Test that the AES key is correctly defined."""
        # Key should be "legend" + 0xFF + 0xFE + "0100009"
        expected_key = bytes(
            [108, 101, 97, 103, 101, 110, 100, 255, 254, 48, 49, 48, 48, 48, 48, 57],
        )
        assert expected_key == BM6_AES_KEY
        assert len(BM6_AES_KEY) == 16

    def test_encrypt_decrypt(self) -> None:
        """Test AES encryption and decryption."""
        crypto = BM6Crypto()
        test_data = b"test data"

        encrypted = crypto.encrypt(test_data)
        decrypted = crypto.decrypt(encrypted)

        assert decrypted == test_data

    def test_encrypt_command(self) -> None:
        """Test encryption of BM6 command."""
        crypto = BM6Crypto()
        command_hex = CMD_REQUEST_VOLTAGE_TEMP
        command_bytes = bytes.fromhex(command_hex)

        encrypted = crypto.encrypt(command_bytes)
        decrypted = crypto.decrypt(encrypted)

        assert decrypted == command_bytes


class TestBM6Protocol:
    """Test BM6 protocol commands."""

    def test_build_voltage_temp_request(self) -> None:
        """Test building voltage/temperature request command."""
        command = build_voltage_temp_request()

        # Command should be encrypted
        assert len(command) > 0
        assert isinstance(command, bytes)

        # Should be different from raw command due to encryption
        raw_command = bytes.fromhex(CMD_REQUEST_VOLTAGE_TEMP)
        assert command != raw_command


class TestBM6Parser:
    """Test BM6 data parsing."""

    def setup_method(self) -> None:
        """Set up parser for tests."""
        self.parser = BM6Parser()

    def test_parse_voltage_pattern(self) -> None:
        """Test parsing voltage from hex pattern."""
        # Simulate voltage data: 55aa + 4 hex digits (e.g., 55aa05dc = 15.00V)
        # 0x05dc = 1500, divided by 100 = 15.00V
        test_data = bytes.fromhex("55aa05dc")
        hex_data = test_data.hex()

        voltage_match = self.parser._find_pattern(hex_data, VOLTAGE_PATTERN)
        assert voltage_match == "55aa05dc"

        # Parse the voltage
        voltage_hex = voltage_match[4:8]
        voltage_raw = int(voltage_hex, 16)
        voltage = voltage_raw / 100.0  # VOLTAGE_CONVERSION_FACTOR

        assert voltage == 15.00

    def test_parse_temperature_positive(self) -> None:
        """Test parsing positive temperature."""
        # Simulate temperature data: 55bb + 4 hex digits (e.g., 55bb00c8 = 20.0°C)
        # 0x00c8 = 200, divided by 10 = 20.0°C
        test_data = bytes.fromhex("55bb00c8")
        hex_data = test_data.hex()

        temp_match = self.parser._find_pattern(hex_data, TEMPERATURE_PATTERN)
        assert temp_match == "55bb00c8"

        # Parse the temperature
        temp_hex = temp_match[4:8]
        temp_raw = int(temp_hex, 16)

        # Check for negative temperature sign bit
        if temp_raw & TEMPERATURE_SIGN_BIT:
            temp_raw = temp_raw & 0xFFFE  # Clear sign bit
            temperature = -(temp_raw / 10.0)  # TEMPERATURE_CONVERSION_FACTOR
        else:
            temperature = temp_raw / 10.0

        assert temperature == 20.0

    def test_parse_temperature_negative(self) -> None:
        """Test parsing negative temperature."""
        # Simulate negative temperature data: 55bb + 4 hex digits with sign bit
        # 55bb00c9 = 200 with sign bit set = -20.0°C
        test_data = bytes.fromhex("55bb00c9")
        hex_data = test_data.hex()

        temp_match = self.parser._find_pattern(hex_data, TEMPERATURE_PATTERN)
        assert temp_match == "55bb00c9"

        # Parse the temperature
        temp_hex = temp_match[4:8]
        temp_raw = int(temp_hex, 16)

        # Check for negative temperature sign bit
        if temp_raw & TEMPERATURE_SIGN_BIT:
            temp_raw = temp_raw & 0xFFFE  # Clear sign bit
            temperature = -(temp_raw / 10.0)
        else:
            temperature = temp_raw / 10.0

        assert temperature == -20.0

    def test_parse_soc(self) -> None:
        """Test parsing state of charge."""
        # Simulate SOC data: 55cc + 2 hex digits (e.g., 55cc64 = 100%)
        test_data = bytes.fromhex("55cc64")
        hex_data = test_data.hex()

        soc_match = self.parser._find_pattern(hex_data, SOC_PATTERN)
        assert soc_match == "55cc64"

        # Parse the SOC
        soc_hex = soc_match[4:6]
        soc_raw = int(soc_hex, 16)
        state_of_charge = soc_raw  # Already in percentage

        assert state_of_charge == 100

    def test_parse_real_time_data(self) -> None:
        """Test parsing complete real-time data."""
        # Simulate complete data with voltage, temperature, and SOC
        # 55aa05dc = 15.00V, 55bb00c8 = 20.0°C, 55cc64 = 100%
        test_data = bytes.fromhex("55aa05dc55bb00c855cc64")

        result = self.parser._parse_real_time_data(test_data)

        assert result is not None
        assert result["voltage"] == 15.00
        assert result["temperature"] == 20.0
        assert result["state_of_charge"] == 100

    def test_parse_real_bm6_data_with_encryption(self) -> None:
        """Test parsing encrypted BM6 data."""
        # Create test data
        test_data = bytes.fromhex("55aa05dc55bb00c855cc64")

        # Encrypt the data
        crypto = BM6Crypto()
        encrypted_data = crypto.encrypt(test_data)

        # Parse the encrypted data
        result = self.parser.parse_real_bm6_data(encrypted_data)

        assert result is not None
        assert result["voltage"] == 15.00
        assert result["temperature"] == 20.0
        assert result["state_of_charge"] == 100
