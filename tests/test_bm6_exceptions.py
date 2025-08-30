"""Tests for BM6 protocol-specific exception classes."""

import pytest

from src.battery_hawk_driver.bm6.exceptions import (
    BM6ChecksumError,
    BM6CommandError,
    BM6ConnectionError,
    BM6DataParsingError,
    BM6Error,
    BM6NotificationError,
    BM6ProtocolError,
    BM6StateError,
    BM6TimeoutError,
)


class TestBM6Error:
    """Test the base BM6Error class."""

    def test_basic_error_creation(self) -> None:
        """Test basic BM6Error creation."""
        error = BM6Error("Test error message")
        assert error.message == "Test error message"
        assert error.device_address is None
        assert error.context == {}
        assert error.error_code == 0

    def test_error_with_device_address(self) -> None:
        """Test BM6Error with device address."""
        error = BM6Error("Test error", device_address="AA:BB:CC:DD:EE:FF")
        assert error.device_address == "AA:BB:CC:DD:EE:FF"
        assert str(error) == "BM6 Error (AA:BB:CC:DD:EE:FF): Test error"

    def test_error_with_context(self) -> None:
        """Test BM6Error with context information."""
        context = {"operation": "read_data", "attempt": 1}
        error = BM6Error("Test error", context=context)
        assert error.context == context

    def test_error_string_representation(self) -> None:
        """Test string representation of BM6Error."""
        error = BM6Error("Test error")
        assert str(error) == "BM6 Error: Test error"

        error_with_address = BM6Error("Test error", device_address="AA:BB:CC:DD:EE:FF")
        assert str(error_with_address) == "BM6 Error (AA:BB:CC:DD:EE:FF): Test error"

    def test_error_to_dict(self) -> None:
        """Test conversion of BM6Error to dictionary."""
        context = {"operation": "read_data"}
        error = BM6Error(
            "Test error",
            device_address="AA:BB:CC:DD:EE:FF",
            context=context,
        )
        error_dict = error.to_dict()
        assert error_dict["error_type"] == "BM6Error"
        assert error_dict["message"] == "Test error"
        assert error_dict["device_address"] == "AA:BB:CC:DD:EE:FF"
        assert error_dict["error_code"] == 0
        assert error_dict["context"] == context


class TestBM6ConnectionError:
    """Test BM6ConnectionError class."""

    def test_connection_error_creation(self) -> None:
        """Test BM6ConnectionError creation."""
        error = BM6ConnectionError(
            "Connection failed",
            device_address="AA:BB:CC:DD:EE:FF",
            connection_attempt=3,
            timeout=10.0,
        )
        assert error.ERROR_CODE == 1001
        assert error.device_address == "AA:BB:CC:DD:EE:FF"
        assert error.context["connection_attempt"] == 3
        assert error.context["timeout"] == 10.0

    def test_connection_error_to_dict(self) -> None:
        """Test BM6ConnectionError to_dict method."""
        error = BM6ConnectionError(
            "Connection failed",
            device_address="AA:BB:CC:DD:EE:FF",
            connection_attempt=2,
            timeout=5.0,
        )
        error_dict = error.to_dict()
        assert error_dict["error_type"] == "BM6ConnectionError"
        assert error_dict["error_code"] == 1001
        assert error_dict["context"]["connection_attempt"] == 2
        assert error_dict["context"]["timeout"] == 5.0


class TestBM6DataParsingError:
    """Test BM6DataParsingError class."""

    def test_data_parsing_error_creation(self) -> None:
        """Test BM6DataParsingError creation."""
        raw_data = b"\x01\x02\x03\x04"
        error = BM6DataParsingError(
            "Invalid data format",
            device_address="AA:BB:CC:DD:EE:FF",
            raw_data=raw_data,
            expected_format="8 bytes",
        )
        assert error.ERROR_CODE == 1002
        assert error.context["raw_data"] == "01020304"
        assert error.context["expected_format"] == "8 bytes"

    def test_data_parsing_error_with_none_data(self) -> None:
        """Test BM6DataParsingError with None raw_data."""
        error = BM6DataParsingError(
            "Invalid data format",
            raw_data=None,
            expected_format="8 bytes",
        )
        assert error.context["raw_data"] is None


class TestBM6CommandError:
    """Test BM6CommandError class."""

    def test_command_error_creation(self) -> None:
        """Test BM6CommandError creation."""
        params = {"param1": "value1", "param2": 123}
        response_data = b"\x05\x06\x07\x08"
        error = BM6CommandError(
            "Command execution failed",
            device_address="AA:BB:CC:DD:EE:FF",
            command="read_data",
            parameters=params,
            response_data=response_data,
        )
        assert error.ERROR_CODE == 1003
        assert error.context["command"] == "read_data"
        assert error.context["parameters"] == params
        assert error.context["response_data"] == "05060708"


class TestBM6TimeoutError:
    """Test BM6TimeoutError class."""

    def test_timeout_error_creation(self) -> None:
        """Test BM6TimeoutError creation."""
        error = BM6TimeoutError(
            "Operation timed out",
            device_address="AA:BB:CC:DD:EE:FF",
            operation="read_data",
            timeout_duration=30.0,
        )
        assert error.ERROR_CODE == 1004
        assert error.context["operation"] == "read_data"
        assert error.context["timeout_duration"] == 30.0


class TestBM6ProtocolError:
    """Test BM6ProtocolError class."""

    def test_protocol_error_creation(self) -> None:
        """Test BM6ProtocolError creation."""
        error = BM6ProtocolError(
            "Protocol violation",
            device_address="AA:BB:CC:DD:EE:FF",
            protocol_version="1.0",
            violation_type="invalid_command",
        )
        assert error.ERROR_CODE == 1005
        assert error.context["protocol_version"] == "1.0"
        assert error.context["violation_type"] == "invalid_command"


class TestBM6NotificationError:
    """Test BM6NotificationError class."""

    def test_notification_error_creation(self) -> None:
        """Test BM6NotificationError creation."""
        notification_data = b"\x09\x0a\x0b\x0c"
        error = BM6NotificationError(
            "Notification handling failed",
            device_address="AA:BB:CC:DD:EE:FF",
            characteristic_uuid="0000ff01-0000-1000-8000-00805f9b34fb",
            notification_data=notification_data,
        )
        assert error.ERROR_CODE == 1006
        assert (
            error.context["characteristic_uuid"]
            == "0000ff01-0000-1000-8000-00805f9b34fb"
        )
        assert error.context["notification_data"] == "090a0b0c"


class TestBM6ChecksumError:
    """Test BM6ChecksumError class."""

    def test_checksum_error_creation(self) -> None:
        """Test BM6ChecksumError creation."""
        error = BM6ChecksumError(
            "Checksum validation failed",
            device_address="AA:BB:CC:DD:EE:FF",
            calculated_checksum=0x55,
            expected_checksum=0xAA,
            data_length=8,
        )
        assert error.ERROR_CODE == 1007
        assert error.context["calculated_checksum"] == 0x55
        assert error.context["expected_checksum"] == 0xAA
        assert error.context["data_length"] == 8


class TestBM6StateError:
    """Test BM6StateError class."""

    def test_state_error_creation(self) -> None:
        """Test BM6StateError creation."""
        error = BM6StateError(
            "Invalid device state",
            device_address="AA:BB:CC:DD:EE:FF",
            current_state="disconnected",
            required_state="connected",
            operation="read_data",
        )
        assert error.ERROR_CODE == 1008
        assert error.context["current_state"] == "disconnected"
        assert error.context["required_state"] == "connected"
        assert error.context["operation"] == "read_data"


class TestBM6ErrorInheritance:
    """Test that all BM6 error classes properly inherit from BM6Error."""

    @pytest.mark.parametrize(
        "error_class",
        [
            BM6ConnectionError,
            BM6DataParsingError,
            BM6CommandError,
            BM6TimeoutError,
            BM6ProtocolError,
            BM6NotificationError,
            BM6ChecksumError,
            BM6StateError,
        ],
    )
    def test_error_inheritance(self, error_class: type) -> None:
        """Test that error classes inherit from BM6Error."""
        assert issubclass(error_class, BM6Error)

    @pytest.mark.parametrize(
        ("error_class", "expected_code"),
        [
            (BM6ConnectionError, 1001),
            (BM6DataParsingError, 1002),
            (BM6CommandError, 1003),
            (BM6TimeoutError, 1004),
            (BM6ProtocolError, 1005),
            (BM6NotificationError, 1006),
            (BM6ChecksumError, 1007),
            (BM6StateError, 1008),
        ],
    )
    def test_error_codes(self, error_class: type, expected_code: int) -> None:
        """Test that error classes have correct error codes."""
        assert expected_code == error_class.ERROR_CODE


class TestBM6ErrorContext:
    """Test error context handling."""

    def test_error_context_preservation(self) -> None:
        """Test that error context is properly preserved."""
        # Test that error context is properly preserved
        error = BM6ConnectionError(
            "Connection failed",
            device_address="AA:BB:CC:DD:EE:FF",
            connection_attempt=3,
            timeout=10.0,
        )
        # The context should include both the base context and the specific context
        assert "connection_attempt" in error.context
        assert "timeout" in error.context
        assert error.context["connection_attempt"] == 3
        assert error.context["timeout"] == 10.0

    def test_error_context_in_to_dict(self) -> None:
        """Test that context is included in to_dict output."""
        error = BM6DataParsingError(
            "Invalid data",
            device_address="AA:BB:CC:DD:EE:FF",
            raw_data=b"\x01\x02",
            expected_format="4 bytes",
        )
        error_dict = error.to_dict()
        assert "context" in error_dict
        assert error_dict["context"]["raw_data"] == "0102"
        assert error_dict["context"]["expected_format"] == "4 bytes"
