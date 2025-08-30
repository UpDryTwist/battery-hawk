"""Tests for BM2-specific exceptions."""

import pytest

from src.battery_hawk_driver.bm2.exceptions import (
    BM2AlarmError,
    BM2ConnectionError,
    BM2DisplayError,
    BM2Error,
    BM2ProtocolError,
    BM2TimeoutError,
)


class TestBM2Error:
    """Test the base BM2Error class."""

    def test_bm2_error_initialization(self) -> None:
        """Test BM2Error initialization."""
        error = BM2Error("Test error message")
        assert error.message == "Test error message"
        assert error.error_code == 0

    def test_bm2_error_with_context(self) -> None:
        """Test BM2Error with context information."""
        context = {"operation": "read_data", "device_address": "AA:BB:CC:DD:EE:FF"}
        error = BM2Error("Test error", context=context)
        assert error.context == context

    def test_bm2_error_inheritance(self) -> None:
        """Test that BM2Error inherits from Exception."""
        error = BM2Error("Test error")
        assert isinstance(error, Exception)


class TestBM2ConnectionError:
    """Test BM2ConnectionError."""

    def test_bm2_connection_error_initialization(self) -> None:
        """Test BM2ConnectionError initialization."""
        error = BM2ConnectionError("Connection failed")
        assert error.message == "Connection failed"
        assert error.error_code == 2001

    def test_bm2_connection_error_with_device_address(self) -> None:
        """Test BM2ConnectionError with device address."""
        error = BM2ConnectionError(
            "Connection failed",
            device_address="AA:BB:CC:DD:EE:FF",
        )
        assert error.device_address == "AA:BB:CC:DD:EE:FF"

    def test_bm2_connection_error_inheritance(self) -> None:
        """Test that BM2ConnectionError inherits from BM2Error."""
        error = BM2ConnectionError("Connection failed")
        assert isinstance(error, BM2Error)


class TestBM2ProtocolError:
    """Test BM2ProtocolError."""

    def test_bm2_protocol_error_initialization(self) -> None:
        """Test BM2ProtocolError initialization."""
        error = BM2ProtocolError("Protocol violation")
        assert error.message == "Protocol violation"
        assert error.error_code == 2005

    def test_bm2_protocol_error_with_context(self) -> None:
        """Test BM2ProtocolError with context."""
        error = BM2ProtocolError(
            "Protocol violation",
            device_address="AA:BB:CC:DD:EE:FF",
            protocol_version="1.0",
            violation_type="invalid_command",
        )
        assert error.context["protocol_version"] == "1.0"
        assert error.context["violation_type"] == "invalid_command"

    def test_bm2_protocol_error_inheritance(self) -> None:
        """Test that BM2ProtocolError inherits from BM2Error."""
        error = BM2ProtocolError("Protocol violation")
        assert isinstance(error, BM2Error)


class TestBM2TimeoutError:
    """Test BM2TimeoutError."""

    def test_bm2_timeout_error_initialization(self) -> None:
        """Test BM2TimeoutError initialization."""
        error = BM2TimeoutError(
            "Operation timed out",
            operation="read_data",
            timeout_duration=30.0,
        )
        assert error.message == "Operation timed out"
        assert error.context["operation"] == "read_data"
        assert error.context["timeout_duration"] == 30.0
        assert error.error_code == 2004

    def test_bm2_timeout_error_with_device_address(self) -> None:
        """Test BM2TimeoutError with device address."""
        error = BM2TimeoutError(
            "Operation timed out",
            device_address="AA:BB:CC:DD:EE:FF",
            operation="read_data",
            timeout_duration=30.0,
        )
        assert error.device_address == "AA:BB:CC:DD:EE:FF"

    def test_bm2_timeout_error_inheritance(self) -> None:
        """Test that BM2TimeoutError inherits from BM2Error."""
        error = BM2TimeoutError("Operation timed out")
        assert isinstance(error, BM2Error)


class TestBM2AlarmError:
    """Test BM2AlarmError."""

    def test_bm2_alarm_error_initialization(self) -> None:
        """Test BM2AlarmError initialization."""
        error = BM2AlarmError("Alarm configuration failed")
        assert error.message == "Alarm configuration failed"
        assert error.error_code == 2009

    def test_bm2_alarm_error_with_alarm_type(self) -> None:
        """Test BM2AlarmError with alarm type."""
        error = BM2AlarmError("Alarm configuration failed", alarm_type=1)
        assert error.context["alarm_type"] == 1

    def test_bm2_alarm_error_inheritance(self) -> None:
        """Test that BM2AlarmError inherits from BM2Error."""
        error = BM2AlarmError("Alarm configuration failed")
        assert isinstance(error, BM2Error)


class TestBM2DisplayError:
    """Test BM2DisplayError."""

    def test_bm2_display_error_initialization(self) -> None:
        """Test BM2DisplayError initialization."""
        error = BM2DisplayError("Display configuration failed")
        assert error.message == "Display configuration failed"
        assert error.error_code == 2010

    def test_bm2_display_error_with_display_mode(self) -> None:
        """Test BM2DisplayError with display mode."""
        error = BM2DisplayError("Display configuration failed", display_mode=1)
        assert error.context["display_mode"] == 1

    def test_bm2_display_error_inheritance(self) -> None:
        """Test that BM2DisplayError inherits from BM2Error."""
        error = BM2DisplayError("Display configuration failed")
        assert isinstance(error, BM2Error)


class TestBM2ErrorHierarchy:
    """Test the BM2 error hierarchy."""

    @pytest.mark.parametrize(
        "error_class",
        [
            BM2ConnectionError,
            BM2ProtocolError,
            BM2TimeoutError,
            BM2AlarmError,
            BM2DisplayError,
        ],
    )
    def test_error_inheritance(self, error_class: type[BM2Error]) -> None:
        """Test that error classes inherit from BM2Error."""
        assert issubclass(error_class, BM2Error)

    @pytest.mark.parametrize(
        ("error_class", "expected_code"),
        [
            (BM2ConnectionError, 2001),
            (BM2ProtocolError, 2005),
            (BM2TimeoutError, 2004),
            (BM2AlarmError, 2009),
            (BM2DisplayError, 2010),
        ],
    )
    def test_error_codes(self, error_class: type[BM2Error], expected_code: int) -> None:
        """Test that error classes have correct error codes."""
        # Create an instance to access the error_code
        error = error_class("Test error")
        assert error.error_code == expected_code


class TestBM2ErrorContext:
    """Test BM2 error context handling."""

    def test_error_context_preservation(self) -> None:
        """Test that error context is properly preserved."""
        error = BM2ProtocolError(
            "Protocol violation",
            device_address="AA:BB:CC:DD:EE:FF",
            protocol_version="1.0",
            violation_type="invalid_command",
        )
        assert error.context["protocol_version"] == "1.0"
        assert error.context["violation_type"] == "invalid_command"

    def test_error_context_modification(self) -> None:
        """Test that error context can be modified."""
        error = BM2ProtocolError("Protocol violation")
        error.context["additional_info"] = "test"
        assert error.context["additional_info"] == "test"

    def test_error_context_default(self) -> None:
        """Test that error context defaults to empty dict."""
        error = BM2ProtocolError("Protocol violation")
        assert error.context == {}


class TestBM2ErrorSerialization:
    """Test BM2 error serialization."""

    def test_error_to_dict(self) -> None:
        """Test converting error to dictionary."""
        error = BM2ProtocolError(
            "Protocol violation",
            device_address="AA:BB:CC:DD:EE:FF",
            protocol_version="1.0",
            violation_type="invalid_command",
        )
        error_dict = error.to_dict()
        assert error_dict["error_type"] == "BM2ProtocolError"
        assert error_dict["message"] == "Protocol violation"
        assert error_dict["error_code"] == 2005
        assert error_dict["context"]["protocol_version"] == "1.0"

    def test_timeout_error_to_dict(self) -> None:
        """Test converting timeout error to dictionary."""
        error = BM2TimeoutError(
            "Operation timed out",
            operation="read_data",
            timeout_duration=30.0,
        )
        error_dict = error.to_dict()
        assert error_dict["error_type"] == "BM2TimeoutError"
        assert error_dict["message"] == "Operation timed out"
        assert error_dict["error_code"] == 2004
        assert error_dict["context"]["operation"] == "read_data"
        assert error_dict["context"]["timeout_duration"] == 30.0


class TestBM2ErrorComparison:
    """Test BM2 error comparison."""

    def test_error_equality(self) -> None:
        """Test error equality."""
        error1 = BM2ConnectionError("Connection failed")
        error2 = BM2ConnectionError("Connection failed")
        # Errors with same message should be equal
        assert str(error1) == str(error2)

    def test_error_inequality(self) -> None:
        """Test error inequality."""
        error1 = BM2ConnectionError("Connection failed")
        error2 = BM2ConnectionError("Different error")
        assert str(error1) != str(error2)

    def test_different_error_types(self) -> None:
        """Test that different error types are not equal."""
        error1 = BM2ConnectionError("Error")
        error2 = BM2ProtocolError("Error")
        assert type(error1) is not type(error2)


class TestBM2ErrorMessages:
    """Test BM2 error message formatting."""

    def test_simple_error_message(self) -> None:
        """Test simple error message."""
        error = BM2Error("Simple error")
        assert str(error) == "BM2 Error: Simple error"

    def test_error_message_with_context(self) -> None:
        """Test error message with context."""
        error = BM2Error("Error with context", device_address="AA:BB:CC:DD:EE:FF")
        assert str(error) == "BM2 Error (AA:BB:CC:DD:EE:FF): Error with context"

    def test_timeout_error_message(self) -> None:
        """Test timeout error message."""
        error = BM2TimeoutError(
            "Operation timed out",
            operation="read_data",
            timeout_duration=30.0,
        )
        assert "Operation timed out" in str(error)
        assert error.context["operation"] == "read_data"
        assert error.context["timeout_duration"] == 30.0

    def test_connection_error_message(self) -> None:
        """Test connection error message."""
        error = BM2ConnectionError(
            "Connection failed",
            device_address="AA:BB:CC:DD:EE:FF",
        )
        assert str(error) == "BM2 Error (AA:BB:CC:DD:EE:FF): Connection failed"
        assert error.device_address == "AA:BB:CC:DD:EE:FF"
