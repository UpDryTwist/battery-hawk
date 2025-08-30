"""BM6 error handler."""

import logging

from ..base.error_handler import ErrorHandler
from .exceptions import BM6TimeoutError


class BM6ErrorHandler(ErrorHandler):
    """Error handler for BM6 protocol devices."""

    def __init__(
        self,
        device_address: str,
        logger: logging.Logger,
        default_timeout: float = 30.0,
    ) -> None:
        """
        Initialize BM6 error handler.

        Args:
            device_address: MAC address of the BM6 device
            logger: Logger instance for error logging
            default_timeout: Default timeout for operations in seconds
        """
        super().__init__(device_address, "BM6", logger, default_timeout)

    def _get_timeout_error_class(self) -> type[Exception]:
        """Get BM6-specific timeout error class."""
        return BM6TimeoutError

    def _create_timeout_error(
        self,
        operation: str,
        timeout_duration: float,
    ) -> Exception:
        """Create BM6-specific timeout error."""
        return BM6TimeoutError(  # type: ignore[reportCallIssue,reportArgumentType]
            f"Operation {operation} timed out after {timeout_duration} seconds",
            device_address=self.device_address,
            operation=operation,
            timeout_duration=timeout_duration,
        )
