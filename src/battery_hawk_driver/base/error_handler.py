# pyright: reportCallIssue=false
"""Base error handling functionality for battery monitoring devices."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from functools import wraps
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

if TYPE_CHECKING:
    import logging
    from collections.abc import Awaitable, Callable


P = ParamSpec("P")
T = TypeVar("T")


class ErrorHandler:
    """
    Base error handler for battery monitoring devices.

    Provides common error handling patterns, retry logic, and diagnostic
    information collection for device operations.
    """

    def __init__(
        self,
        device_address: str,
        protocol_name: str,
        logger: logging.Logger,
        default_timeout: float = 30.0,
    ) -> None:
        """
        Initialize the error handler.

        Args:
            device_address: MAC address of the device
            protocol_name: Name of the protocol (BM2, BM6, etc.)
            logger: Logger instance for error logging
            default_timeout: Default timeout for operations in seconds
        """
        self.device_address = device_address
        self.protocol_name = protocol_name
        self.logger = logger
        self.default_timeout = default_timeout
        self._diagnostic_info: dict[str, dict[str, Any]] = {}

    def with_timeout(
        self,
        timeout: float | None = None,
        operation_name: str | None = None,
    ) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
        """Add timeout handling to async operations."""

        def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
            @wraps(func)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                operation = operation_name or func.__name__
                timeout_duration = timeout or self.default_timeout

                try:
                    # Record operation start
                    self._record_operation_start(operation)

                    # Execute with timeout
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=timeout_duration,
                    )
                except TimeoutError:
                    self._record_operation_timeout(operation, timeout_duration)
                    self.logger.exception(
                        "Operation %s timed out after %s seconds for device %s",
                        operation,
                        timeout_duration,
                        self.device_address,
                    )
                    raise self._create_timeout_error(
                        operation,
                        timeout_duration,
                    ) from None

                except Exception as exc:
                    # Record operation error
                    self._record_operation_error(operation, exc)
                    raise
                else:
                    # Record successful operation
                    self._record_operation_success(operation)
                    return result

            return wrapper

        return decorator

    def with_retry(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
    ) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
        """Add retry logic with protocol-specific error handling."""

        def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
            @wraps(func)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                last_exception: Exception | None = None
                for attempt in range(max_attempts):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as exc:  # noqa: BLE001, PERF203
                        last_exception = exc
                        if attempt < max_attempts - 1:
                            delay = min(base_delay * (2**attempt), max_delay)
                            await asyncio.sleep(delay)
                        else:
                            break
                if last_exception is not None:
                    raise last_exception
                raise RuntimeError("Retry loop completed without exception")

            return wrapper

        return decorator

    @asynccontextmanager
    async def operation_context(  # noqa: ANN201
        self,
        operation_name: str,
        timeout: float | None = None,
        *,
        collect_diagnostics: bool = True,
    ):
        """Context manager for operation execution with error handling and diagnostics."""
        operation_id = f"{operation_name}_{int(time.time() * 1000)}"

        if collect_diagnostics:
            self._record_operation_start(operation_name, operation_id)

        try:
            # Execute the operation with timeout
            if timeout is not None:
                result = await asyncio.wait_for(
                    self._execute_operation(operation_name),
                    timeout=timeout,
                )
            else:
                result = await self._execute_operation(operation_name)

            if collect_diagnostics:
                self._record_operation_success(operation_name, operation_id)

            yield result

        except TimeoutError:
            if collect_diagnostics:
                self._record_operation_timeout(
                    operation_name,
                    timeout or self.default_timeout,
                    operation_id,
                )
            self.logger.exception(
                "Operation %s timed out after %s seconds for device %s",
                operation_name,
                timeout or self.default_timeout,
                self.device_address,
            )
            raise self._create_timeout_error(
                operation_name,
                timeout or self.default_timeout,
            ) from None

        except Exception as exc:
            if collect_diagnostics:
                self._record_operation_error(operation_name, exc, operation_id)
            raise

    async def _execute_operation(self, operation_name: str):  # noqa: ANN202
        """Execute operation - to be overridden by subclasses."""
        raise NotImplementedError(
            f"Operation {operation_name} not implemented for {self.protocol_name}",
        )

    def _record_operation_start(
        self,
        operation: str,
        operation_id: str | None = None,
    ) -> None:
        """Record the start of an operation."""
        op_id = operation_id or f"{operation}_{int(time.time() * 1000)}"
        self._diagnostic_info[op_id] = {
            "operation": operation,
            "start_time": time.time(),
            "status": "started",
        }

    def _record_operation_success(
        self,
        operation: str,
        operation_id: str | None = None,
    ) -> None:
        """Record the successful completion of an operation."""
        op_id = operation_id or f"{operation}_{int(time.time() * 1000)}"
        if op_id in self._diagnostic_info:
            end_time = time.time()
            start_time = self._diagnostic_info[op_id]["start_time"]
            self._diagnostic_info[op_id].update(
                {
                    "status": "completed",
                    "end_time": end_time,
                    "duration": end_time - start_time,
                },
            )

    def _record_operation_error(
        self,
        operation: str,
        error: Exception,
        operation_id: str | None = None,
    ) -> None:
        """Record an operation error."""
        op_id = operation_id or f"{operation}_{int(time.time() * 1000)}"
        if op_id in self._diagnostic_info:
            end_time = time.time()
            start_time = self._diagnostic_info[op_id]["start_time"]
            self._diagnostic_info[op_id].update(
                {
                    "status": "error",
                    "end_time": end_time,
                    "duration": end_time - start_time,
                    "error": str(error),
                    "error_type": type(error).__name__,
                },
            )

    def _record_operation_timeout(
        self,
        operation: str,
        timeout_duration: float,
        operation_id: str | None = None,
    ) -> None:
        """Record an operation timeout."""
        op_id = operation_id or f"{operation}_{int(time.time() * 1000)}"
        if op_id in self._diagnostic_info:
            end_time = time.time()
            start_time = self._diagnostic_info[op_id]["start_time"]
            self._diagnostic_info[op_id].update(
                {
                    "status": "timeout",
                    "end_time": end_time,
                    "duration": end_time - start_time,
                    "timeout_duration": timeout_duration,
                },
            )

    def get_diagnostic_info(self) -> dict[str, dict[str, Any]]:
        """
        Get diagnostic information for all recorded operations.

        Returns:
            Dictionary containing diagnostic information for all operations
        """
        return self._diagnostic_info.copy()

    def clear_diagnostic_info(self) -> None:
        """Clear all diagnostic information."""
        self._diagnostic_info.clear()

    def _get_timeout_error_class(self) -> type[Exception]:
        """Get the appropriate timeout error class for this protocol."""
        return Exception

    def _create_timeout_error(
        self,
        operation: str,
        timeout_duration: float,
    ) -> Exception:
        """Create a timeout error for the given operation."""
        error_class = self._get_timeout_error_class()
        return error_class(
            f"Operation {operation} timed out after {timeout_duration} seconds",
        )

    def get_error_recovery_strategy(
        self,
        error: Exception,
        operation: str,
    ) -> dict[str, Any]:
        """Get error recovery strategy based on error type and operation."""
        error_type = type(error).__name__

        # Base recovery strategies
        strategies = {
            "retry": {
                "should_retry": False,
                "max_attempts": 1,
                "base_delay": 1.0,
            },
            "fallback": {
                "should_fallback": False,
                "fallback_operation": None,
            },
            "logging": {
                "level": "error",
                "include_context": True,
            },
        }

        # Protocol-specific strategies
        if "Connection" in error_type:
            strategies["retry"]["should_retry"] = True
            strategies["retry"]["max_attempts"] = 3
            strategies["retry"]["base_delay"] = 2.0
        elif "Timeout" in error_type:
            strategies["retry"]["should_retry"] = True
            strategies["retry"]["max_attempts"] = 2
            strategies["retry"]["base_delay"] = 1.0
        elif "Protocol" in error_type:
            strategies["logging"]["level"] = "warning"
            strategies["retry"]["should_retry"] = False

        # Operation-specific adjustments
        if operation in ("connect", "discover") and strategies["retry"]["should_retry"]:
            # Connection operations should be more aggressive with retries
            strategies["retry"]["max_attempts"] = max(
                strategies["retry"]["max_attempts"],
                3,
            )

        return strategies
