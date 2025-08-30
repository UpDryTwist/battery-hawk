"""BM2 protocol-specific exception classes and error handling."""

from __future__ import annotations

from typing import Any


class BM2Error(Exception):
    """Base exception class for BM2 protocol errors."""

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Initialize BM2Error with message, device address, and context."""
        super().__init__(message)
        self.message = message
        self.device_address = device_address
        self.context = context or {}
        self.error_code = getattr(self, "ERROR_CODE", 0)

    def __str__(self) -> str:
        """Return string representation with device address if available."""
        if self.device_address:
            return f"BM2 Error ({self.device_address}): {self.message}"
        return f"BM2 Error: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for logging/diagnostics."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "device_address": self.device_address,
            "error_code": self.error_code,
            "context": self.context,
        }


class BM2ConnectionError(BM2Error):
    """Raised when BM2 device connection fails."""

    ERROR_CODE = 2001

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        connection_attempt: int | None = None,
        timeout: float | None = None,
    ) -> None:
        """Initialize BM2ConnectionError with connection-specific details."""
        context = {
            "connection_attempt": connection_attempt,
            "timeout": timeout,
        }
        super().__init__(message, device_address, context)


class BM2DataParsingError(BM2Error):
    """Raised when BM2 data parsing fails."""

    ERROR_CODE = 2002

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        raw_data: bytes | None = None,
        expected_format: str | None = None,
    ) -> None:
        """Initialize BM2DataParsingError with parsing-specific details."""
        context = {
            "raw_data": raw_data.hex() if raw_data else None,
            "expected_format": expected_format,
        }
        super().__init__(message, device_address, context)


class BM2CommandError(BM2Error):
    """Raised when BM2 command execution fails."""

    ERROR_CODE = 2003

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        command: str | None = None,
        parameters: dict[str, Any] | None = None,
        response_data: bytes | None = None,
    ) -> None:
        """Initialize BM2CommandError with command-specific details."""
        context = {
            "command": command,
            "parameters": parameters,
            "response_data": response_data.hex() if response_data else None,
        }
        super().__init__(message, device_address, context)


class BM2TimeoutError(BM2Error):
    """Raised when BM2 operation times out."""

    ERROR_CODE = 2004

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        operation: str | None = None,
        timeout_duration: float | None = None,
    ) -> None:
        """Initialize BM2TimeoutError with timeout-specific details."""
        context = {
            "operation": operation,
            "timeout_duration": timeout_duration,
        }
        super().__init__(message, device_address, context)


class BM2ProtocolError(BM2Error):
    """Raised when BM2 protocol violation occurs."""

    ERROR_CODE = 2005

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        protocol_version: str | None = None,
        violation_type: str | None = None,
    ) -> None:
        """Initialize BM2ProtocolError with protocol-specific details."""
        context = {}
        if protocol_version is not None:
            context["protocol_version"] = protocol_version
        if violation_type is not None:
            context["violation_type"] = violation_type
        super().__init__(message, device_address, context)


class BM2NotificationError(BM2Error):
    """Raised when BM2 notification handling fails."""

    ERROR_CODE = 2006

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        characteristic_uuid: str | None = None,
        notification_data: bytes | None = None,
    ) -> None:
        """Initialize BM2NotificationError with notification-specific details."""
        context = {
            "characteristic_uuid": characteristic_uuid,
            "notification_data": notification_data.hex() if notification_data else None,
        }
        super().__init__(message, device_address, context)


class BM2ChecksumError(BM2Error):
    """Raised when BM2 data checksum validation fails."""

    ERROR_CODE = 2007

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        calculated_checksum: int | None = None,
        expected_checksum: int | None = None,
        data_length: int | None = None,
    ) -> None:
        """Initialize BM2ChecksumError with checksum-specific details."""
        context = {
            "calculated_checksum": calculated_checksum,
            "expected_checksum": expected_checksum,
            "data_length": data_length,
        }
        super().__init__(message, device_address, context)


class BM2StateError(BM2Error):
    """Raised when BM2 device is in an invalid state for the requested operation."""

    ERROR_CODE = 2008

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        current_state: str | None = None,
        required_state: str | None = None,
        operation: str | None = None,
    ) -> None:
        """Initialize BM2StateError with state-specific details."""
        context = {
            "current_state": current_state,
            "required_state": required_state,
            "operation": operation,
        }
        super().__init__(message, device_address, context)


class BM2AlarmError(BM2Error):
    """Raised when BM2 alarm configuration fails."""

    ERROR_CODE = 2009

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        alarm_type: int | None = None,
        threshold_value: int | None = None,
        current_value: int | None = None,
    ) -> None:
        """Initialize BM2AlarmError with alarm-specific details."""
        context = {
            "alarm_type": alarm_type,
            "threshold_value": threshold_value,
            "current_value": current_value,
        }
        super().__init__(message, device_address, context)


class BM2DisplayError(BM2Error):
    """Raised when BM2 display configuration fails."""

    ERROR_CODE = 2010

    def __init__(
        self,
        message: str,
        device_address: str | None = None,
        display_mode: int | None = None,
        current_mode: int | None = None,
    ) -> None:
        """Initialize BM2DisplayError with display-specific details."""
        context = {
            "display_mode": display_mode,
            "current_mode": current_mode,
        }
        super().__init__(message, device_address, context)
