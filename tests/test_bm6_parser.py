"""Tests for BM6 data parsing."""

from __future__ import annotations

from src.battery_hawk_driver.bm6.parser import BM6Parser


class TestBM6Parser:
    """Test BM6 data parser."""

    def setup_method(self) -> None:
        """Set up parser instance for tests."""
        self.parser = BM6Parser()

    def test_parse_response_invalid_data(self) -> None:
        """Test parsing invalid response data."""
        # Too short
        assert self.parser.parse_response(b"") is None
        assert self.parser.parse_response(b"\xdd") is None

        # Invalid markers
        assert self.parser.parse_response(b"\x00\xa5\x03\x00\xfa\x77") is None
        assert self.parser.parse_response(b"\xdd\xa5\x03\x00\xfa\x00") is None

    def test_parse_basic_info_response(self) -> None:
        """Test parsing basic information response."""
        # Sample data packet for basic info (command 0x03)
        # Based on research findings from GitHub repositories
        data = bytes(
            [
                0xDD,
                0xA5,
                0x03,
                0x14,  # Header
                0x64,
                0x0F,  # Voltage (3940 = 39.40V)
                0x2C,
                0x01,  # Current (300 = 3.00A)
                0xD0,
                0x07,  # Remaining capacity (2000 = 20.00Ah)
                0x20,
                0x03,  # Nominal capacity (800 = 8.00Ah)
                0x0A,
                0x00,  # Cycles (10)
                0x25,
                0x2B,  # Production date (2021-09-05)
                0x00,
                0x00,  # Balance status
                0x00,
                0x00,  # Protection status
                0x14,  # Software version (2.0)
                0x64,  # SOC (100%)
                0x03,  # FET status (both on)
                0x04,  # Cell count (4)
                # Cell voltages
                0xD2,
                0x0C,  # Cell 1 (3282 = 3.282V)
                0xD0,
                0x0C,  # Cell 2 (3280 = 3.280V)
                0xCE,
                0x0C,  # Cell 3 (3278 = 3.278V)
                0xD4,
                0x0C,  # Cell 4 (3284 = 3.284V)
                # Temperatures
                0xCE,
                0x00,  # Temp 1 (206 = 20.6°C)
                0xD2,
                0x00,  # Temp 2 (210 = 21.0°C)
                0x8A,  # Checksum
                0x77,  # End marker
            ],
        )

        result = self.parser.parse_response(data)

        assert result is not None
        assert result["voltage"] == 39.40
        assert result["current"] == 3.00
        assert result["remaining_capacity"] == 20.00
        assert result["nominal_capacity"] == 8.00
        assert result["cycles"] == 10
        assert result["production_date"] == "2021-09-05"
        assert result["software_version"] == 2.0
        assert result["state_of_charge"] == 100
        assert result["cell_count"] == 4

        # Check cell voltages
        assert len(result["cell_voltages"]) == 4
        assert result["cell_voltages"][0] == 3.282
        assert result["cell_voltages"][1] == 3.280
        assert result["cell_voltages"][2] == 3.278
        assert result["cell_voltages"][3] == 3.284

        # Check temperatures
        assert len(result["temperatures"]) == 2
        assert result["temperatures"][0] == 20.6
        assert result["temperatures"][1] == 21.0

    def test_parse_basic_info_response_minimal(self) -> None:
        """Test parsing basic information response with minimal data."""
        # Minimal valid basic info response (no cell voltages or temperatures)
        data = bytes(
            [
                0xDD,
                0xA5,
                0x03,
                0x00,  # Header
                0x64,
                0x0F,  # Voltage (3940 = 39.40V)
                0x2C,
                0x01,  # Current (300 = 3.00A)
                0xD0,
                0x07,  # Remaining capacity (2000 = 20.00Ah)
                0x20,
                0x03,  # Nominal capacity (800 = 8.00Ah)
                0x0A,
                0x00,  # Cycles (10)
                0x25,
                0x2B,  # Production date (2021-09-05)
                0x00,
                0x00,  # Balance status
                0x00,
                0x00,  # Protection status
                0x14,  # Software version (2.0)
                0x64,  # SOC (100%)
                0x03,  # FET status (both on)
                0x00,  # Cell count (0)
                0x8A,  # Checksum
                0x77,  # End marker
            ],
        )

        result = self.parser.parse_response(data)

        assert result is not None
        assert result["voltage"] == 39.40
        assert result["current"] == 3.00
        assert result["cell_count"] == 0
        assert "cell_voltages" not in result
        assert "temperatures" not in result

    def test_parse_cell_voltages_response(self) -> None:
        """Test parsing cell voltages response."""
        # Sample cell voltages response
        data = bytes(
            [
                0xDD,
                0xA5,
                0x04,
                0x08,  # Header
                0x04,  # Cell count (4)
                # Cell voltages
                0xD2,
                0x0C,  # Cell 1 (3282 = 3.282V)
                0xD0,
                0x0C,  # Cell 2 (3280 = 3.280V)
                0xCE,
                0x0C,  # Cell 3 (3278 = 3.278V)
                0xD4,
                0x0C,  # Cell 4 (3284 = 3.284V)
                0x8A,  # Checksum
                0x77,  # End marker
            ],
        )

        result = self.parser.parse_response(data)

        assert result is not None
        assert result["cell_count"] == 4
        assert len(result["cell_voltages"]) == 4
        assert result["cell_voltages"][0] == 3.282
        assert result["cell_voltages"][1] == 3.280
        assert result["cell_voltages"][2] == 3.278
        assert result["cell_voltages"][3] == 3.284

    def test_parse_notification_legacy_format(self) -> None:
        """Test parsing legacy notification format."""
        # Legacy notification format (no command structure)
        data = bytes(
            [
                0x64,
                0x0F,  # Voltage (3940 = 39.40V)
                0x2C,
                0x01,  # Current (300 = 3.00A)
                0xD0,
                0x07,  # Remaining capacity (2000 = 20.00Ah)
                0x20,
                0x03,  # Nominal capacity (800 = 8.00Ah)
                0x0A,
                0x00,  # Cycles (10)
                0x25,
                0x2B,  # Production date (2021-09-05)
                0x00,
                0x00,  # Balance status
                0x00,
                0x00,  # Protection status
                0x14,  # Software version (2.0)
                0x64,  # SOC (100%)
                0x03,  # FET status (both on)
                0x04,  # Cell count (4)
                # Cell voltages
                0xD2,
                0x0C,  # Cell 1 (3282 = 3.282V)
                0xD0,
                0x0C,  # Cell 2 (3280 = 3.280V)
                0xCE,
                0x0C,  # Cell 3 (3278 = 3.278V)
                0xD4,
                0x0C,  # Cell 4 (3284 = 3.284V)
                # Temperatures
                0xCE,
                0x00,  # Temp 1 (206 = 20.6°C)
                0xD2,
                0x00,  # Temp 2 (210 = 21.0°C)
            ],
        )

        result = self.parser.parse_notification(data)

        assert result is not None
        assert result["voltage"] == 39.40
        assert result["current"] == 3.00
        assert result["remaining_capacity"] == 20.00
        assert result["nominal_capacity"] == 8.00
        assert result["cycles"] == 10
        assert result["production_date"] == "2021-09-05"
        assert result["software_version"] == 2.0
        assert result["state_of_charge"] == 100
        assert result["cell_count"] == 4

        # Check cell voltages
        assert len(result["cell_voltages"]) == 4
        assert result["cell_voltages"][0] == 3.282
        assert result["cell_voltages"][3] == 3.284

        # Check temperatures
        assert len(result["temperatures"]) == 2
        assert result["temperatures"][0] == 20.6
        assert result["temperatures"][1] == 21.0

    def test_parse_notification_invalid_length(self) -> None:
        """Test parsing notification with invalid length."""
        # Too short
        data = b"\x64\x0f\x2c\x01"  # Only 4 bytes
        assert self.parser.parse_notification(data) is None

    def test_parse_response_unknown_command(self) -> None:
        """Test parsing response with unknown command."""
        data = bytes(
            [
                0xDD,
                0xA5,
                0xFF,
                0x00,  # Header with unknown command
                0x8A,  # Checksum
                0x77,  # End marker
            ],
        )

        assert self.parser.parse_response(data) is None

    def test_parse_basic_info_response_negative_current(self) -> None:
        """Test parsing basic info with negative current (discharging)."""
        data = bytes(
            [
                0xDD,
                0xA5,
                0x03,
                0x00,  # Header
                0x64,
                0x0F,  # Voltage (3940 = 39.40V)
                0xD4,
                0xFE,  # Current (-300 = -3.00A, discharging)
                0xD0,
                0x07,  # Remaining capacity (2000 = 20.00Ah)
                0x20,
                0x03,  # Nominal capacity (800 = 8.00Ah)
                0x0A,
                0x00,  # Cycles (10)
                0x25,
                0x2B,  # Production date (2021-09-05)
                0x00,
                0x00,  # Balance status
                0x00,
                0x00,  # Protection status
                0x14,  # Software version (2.0)
                0x64,  # SOC (100%)
                0x02,  # FET status (discharging only)
                0x00,  # Cell count (0)
                0x8A,  # Checksum
                0x77,  # End marker
            ],
        )

        result = self.parser.parse_response(data)

        assert result is not None
        assert result["voltage"] == 39.40
        assert result["current"] == -3.00  # Negative current
        assert result["fet_status"]["charging"] is False
        assert result["fet_status"]["discharging"] is True

    def test_parse_basic_info_response_negative_temperature(self) -> None:
        """Test parsing basic info with negative temperature."""
        data = bytes(
            [
                0xDD,
                0xA5,
                0x03,
                0x00,  # Header
                0x64,
                0x0F,  # Voltage (3940 = 39.40V)
                0x2C,
                0x01,  # Current (300 = 3.00A)
                0xD0,
                0x07,  # Remaining capacity (2000 = 20.00Ah)
                0x20,
                0x03,  # Nominal capacity (800 = 8.00Ah)
                0x0A,
                0x00,  # Cycles (10)
                0x25,
                0x12,  # Production date (2021-09-05)
                0x00,
                0x00,  # Balance status
                0x00,
                0x00,  # Protection status
                0x14,  # Software version (2.0)
                0x64,  # SOC (100%)
                0x03,  # FET status (both on)
                0x00,  # Cell count (0)
                # Temperature (negative)
                0xCE,
                0xFF,  # Temp (-50 = -5.0°C)
                0x8A,  # Checksum
                0x77,  # End marker
            ],
        )

        result = self.parser.parse_response(data)

        assert result is not None
        assert len(result["temperatures"]) == 1
        assert result["temperatures"][0] == -5.0
