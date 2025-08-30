"""BM6 protocol-specific exception classes and error handling."""

from __future__ import annotations

from typing import Any


class BM6Error(Exception):
    """Base exception class for BM6 protocol errors."""

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Initialize BM6Error with message, device address, and context."""
        super().__init__(message)
        self.message = message
        self.device_address = device_address
        self.context = context or {}
        self.error_code = getattr(self, "ERROR_CODE", 0)

    def __str__(self) -> str:
        """Return string representation with device address if available."""
        if self.device_address:
            return f"BM6 Error ({self.device_address}): {self.message}"
        return f"BM6 Error: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for logging/diagnostics."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "device_address": self.device_address,
            "error_code": self.error_code,
            "context": self.context,
        }


class BM6ConnectionError(BM6Error):
    """Raised when BM6 device connection fails."""

    ERROR_CODE = 1001

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        connection_attempt: int | None = None,
        timeout: float | None = None,
    ) -> None:
        """Initialize BM6ConnectionError with connection-specific details."""
        context = {
            "connection_attempt": connection_attempt,
            "timeout": timeout,
        }
        super().__init__(message, device_address, context)


class BM6DataParsingError(BM6Error):
    """Raised when BM6 data parsing fails."""

    ERROR_CODE = 1002

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        raw_data: bytes | None = None,
        expected_format: str | None = None,
    ) -> None:
        """Initialize BM6DataParsingError with parsing-specific details."""
        context = {
            "raw_data": raw_data.hex() if raw_data else None,
            "expected_format": expected_format,
        }
        super().__init__(message, device_address, context)


class BM6CommandError(BM6Error):
    """Raised when BM6 command execution fails."""

    ERROR_CODE = 1003

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        command: str | None = None,
        parameters: dict[str, Any] | None = None,
        response_data: bytes | None = None,
    ) -> None:
        """Initialize BM6CommandError with command-specific details."""
        context = {
            "command": command,
            "parameters": parameters,
            "response_data": response_data.hex() if response_data else None,
        }
        super().__init__(message, device_address, context)


class BM6TimeoutError(BM6Error):
    """Raised when BM6 operation times out."""

    ERROR_CODE = 1004

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        operation: str | None = None,
        timeout_duration: float | None = None,
    ) -> None:
        """Initialize BM6TimeoutError with timeout-specific details."""
        context = {
            "operation": operation,
            "timeout_duration": timeout_duration,
        }
        super().__init__(message, device_address, context)


class BM6ProtocolError(BM6Error):
    """Raised when BM6 protocol violation occurs."""

    ERROR_CODE = 1005

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        protocol_version: str | None = None,
        violation_type: str | None = None,
    ) -> None:
        """Initialize BM6ProtocolError with protocol-specific details."""
        context = {
            "protocol_version": protocol_version,
            "violation_type": violation_type,
        }
        super().__init__(message, device_address, context)


class BM6NotificationError(BM6Error):
    """Raised when BM6 notification handling fails."""

    ERROR_CODE = 1006

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        characteristic_uuid: str | None = None,
        notification_data: bytes | None = None,
    ) -> None:
        """Initialize BM6NotificationError with notification-specific details."""
        context = {
            "characteristic_uuid": characteristic_uuid,
            "notification_data": notification_data.hex() if notification_data else None,
        }
        super().__init__(message, device_address, context)


class BM6ChecksumError(BM6Error):
    """Raised when BM6 data checksum validation fails."""

    ERROR_CODE = 1007

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        calculated_checksum: int | None = None,
        expected_checksum: int | None = None,
        data_length: int | None = None,
    ) -> None:
        """Initialize BM6ChecksumError with checksum-specific details."""
        context = {
            "calculated_checksum": calculated_checksum,
            "expected_checksum": expected_checksum,
            "data_length": data_length,
        }
        super().__init__(message, device_address, context)


class BM6StateError(BM6Error):
    """Raised when BM6 device is in an invalid state for the requested operation."""

    ERROR_CODE = 1008

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        current_state: str | None = None,
        required_state: str | None = None,
        operation: str | None = None,
    ) -> None:
        """Initialize BM6StateError with state-specific details."""
        context = {
            "current_state": current_state,
            "required_state": required_state,
            "operation": operation,
        }
        super().__init__(message, device_address, context)
