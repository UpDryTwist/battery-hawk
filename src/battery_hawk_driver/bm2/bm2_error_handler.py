"""BM2 error handler."""

import logging

from ..base.error_handler import ErrorHandler
from .exceptions import BM2TimeoutError


class BM2ErrorHandler(ErrorHandler):
    """Error handler for BM2 protocol devices."""

    def __init__(
        self,
        device_address: str,
        logger: logging.Logger,
        default_timeout: float = 25.0,
    ) -> None:
        """
        Initialize BM2 error handler.

        Args:
            device_address: MAC address of the BM2 device
            logger: Logger instance for error logging
            default_timeout: Default timeout for operations in seconds
        """
        super().__init__(device_address, "BM2", logger, default_timeout)

    def _get_timeout_error_class(self) -> type[Exception]:
        """Get BM2-specific timeout error class."""
        return BM2TimeoutError

    def _create_timeout_error(
        self,
        operation: str,
        timeout_duration: float,
    ) -> Exception:
        """Create BM2-specific timeout error."""
        return BM2TimeoutError(  # type: ignore[reportCallIssue,reportArgumentType]
            f"Operation {operation} timed out after {timeout_duration} seconds",
            device_address=self.device_address,
            operation=operation,
            timeout_duration=timeout_duration,
        )
