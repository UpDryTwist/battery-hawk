"""Test real BM6 protocol implementation."""

from battery_hawk_driver.bm6.constants import (
    BM6_AES_KEY,
    CMD_REQUEST_VOLTAGE_TEMP,
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
        # Use 16-byte test data since BM6 protocol works with 16-byte blocks
        test_data = b"test data\x00\x00\x00\x00\x00\x00\x00"  # Pad to 16 bytes

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

    def test_parse_bm6_real_time_data_with_values(self) -> None:
        """Test parsing BM6 real-time data with actual values."""
        # Simulate BM6 response: d15507 + status + temp_sign + skip + temp + state + voltage + padding
        # d15507 = command response
        # 00 = status (normal)
        # 00 = temperature sign (positive)
        # 00 = skip byte
        # 14 = temperature (20°C)
        # 64 = state of charge (100%)
        # 05dc = voltage (15.00V)
        test_hex = "d15507000000146405dc0000000000"
        test_data = bytes.fromhex(test_hex)

        result = self.parser._parse_real_time_data(test_data)

        assert result is not None
        assert result["voltage"] == 15.00  # 0x05dc / 100
        assert result["temperature"] == 20  # 0x14 with positive sign
        assert result["state_of_charge"] == 100  # 0x64

    def test_parse_bm6_real_time_data_negative_temp(self) -> None:
        """Test parsing BM6 real-time data with negative temperature."""
        # d15507 + status + temp_sign + temp + state + voltage + padding
        # 01 = temperature sign (negative)
        # 0a = temperature (10°C, but negative = -10°C)
        test_hex = "d155070001050a32012c0000000000"
        test_data = bytes.fromhex(test_hex)

        result = self.parser._parse_real_time_data(test_data)

        assert result is not None
        assert result["temperature"] == -10  # 0x0a with negative sign
        assert result["state_of_charge"] == 50  # 0x32
        assert result["voltage"] == 3.00  # 0x012c / 100

    def test_parse_bm6_invalid_prefix(self) -> None:
        """Test that data without BM6 prefix is rejected."""
        # Invalid prefix (not d15507)
        test_hex = "ff55070000146405dc000000000000"
        test_data = bytes.fromhex(test_hex)

        result = self.parser._parse_real_time_data(test_data)

        assert result is None

    def test_parse_real_time_data(self) -> None:
        """Test parsing complete real-time data."""
        # Simulate BM6 response with voltage=15.00V, temperature=20°C, SOC=100%
        # d15507 = command response
        # 00 = status (normal)
        # 00 = temperature sign (positive)
        # 00 = skip byte
        # 14 = temperature (20°C)
        # 64 = state of charge (100%)
        # 05dc = voltage (15.00V)
        test_data = bytes.fromhex("d15507000000146405dc0000000000")

        result = self.parser._parse_real_time_data(test_data)

        assert result is not None
        assert result["voltage"] == 15.00
        assert result["temperature"] == 20.0
        assert result["state_of_charge"] == 100

    def test_parse_real_bm6_data_with_encryption(self) -> None:
        """Test parsing encrypted BM6 data."""
        # Create test data in correct BM6 format
        test_data = bytes.fromhex("d15507000000146405dc0000000000")

        # Encrypt the data
        crypto = BM6Crypto()
        encrypted_data = crypto.encrypt(test_data)

        # Parse the encrypted data
        result = self.parser.parse_real_bm6_data(encrypted_data)

        assert result is not None
        assert result["voltage"] == 15.00
        assert result["temperature"] == 20.0
        assert result["state_of_charge"] == 100
        assert result["voltage"] == 15.00
        assert result["temperature"] == 20.0
        assert result["state_of_charge"] == 100
