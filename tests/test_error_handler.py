"""Tests for error handling functionality."""

from __future__ import annotations

import asyncio
import logging

import pytest

from src.battery_hawk_driver.base.error_handler import (
    ErrorHandler,
)
from src.battery_hawk_driver.bm2.bm2_error_handler import BM2ErrorHandler
from src.battery_hawk_driver.bm2.exceptions import (
    BM2ConnectionError,
    BM2ProtocolError,
    BM2TimeoutError,
)
from src.battery_hawk_driver.bm6.bm6_error_handler import BM6ErrorHandler
from src.battery_hawk_driver.bm6.exceptions import (
    BM6ConnectionError,
    BM6ProtocolError,
    BM6TimeoutError,
)


class TestErrorHandler:
    """Test cases for the base ErrorHandler class."""

    def test_error_handler_initialization(self) -> None:
        """Test that ErrorHandler can be initialized correctly."""
        handler = ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            protocol_name="TEST",
            logger=logging.getLogger("test"),
        )
        assert handler.device_address == "AA:BB:CC:DD:EE:FF"
        assert handler.protocol_name == "TEST"
        assert handler.logger is not None

    def test_diagnostic_info_initialization(self) -> None:
        """Test that diagnostic info is properly initialized."""
        handler = ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            protocol_name="TEST",
            logger=logging.getLogger("test"),
        )
        # Record some operations
        handler._record_operation_start("test_operation")
        assert len(handler._diagnostic_info) > 0

        handler.clear_diagnostic_info()
        assert len(handler._diagnostic_info) == 0

    def test_record_operation_lifecycle(self) -> None:
        """Test recording operation start, success, and error states."""
        handler = ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            protocol_name="TEST",
            logger=logging.getLogger("test"),
        )
        # Record operation start
        handler._record_operation_start("test_operation", "op_123")
        assert "op_123" in handler._diagnostic_info
        assert handler._diagnostic_info["op_123"]["status"] == "started"

        # Record operation success
        handler._record_operation_success("test_operation", "op_123")
        assert handler._diagnostic_info["op_123"]["status"] == "completed"
        assert "duration" in handler._diagnostic_info["op_123"]

    def test_record_operation_error(self) -> None:
        """Test recording operation errors."""
        handler = ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            protocol_name="TEST",
            logger=logging.getLogger("test"),
        )

        handler._record_operation_start("test_operation", "op_123")
        test_exception = ValueError("Test error")
        handler._record_operation_error("test_operation", test_exception, "op_123")

        assert handler._diagnostic_info["op_123"]["status"] == "error"
        assert handler._diagnostic_info["op_123"]["error"] == "Test error"
        assert handler._diagnostic_info["op_123"]["error_type"] == "ValueError"

    def test_record_operation_timeout(self) -> None:
        """Test recording operation timeouts."""
        handler = ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            protocol_name="TEST",
            logger=logging.getLogger("test"),
        )

        handler._record_operation_start("test_operation", "op_123")
        handler._record_operation_timeout("test_operation", 30.0, "op_123")

        assert handler._diagnostic_info["op_123"]["status"] == "timeout"
        assert handler._diagnostic_info["op_123"]["timeout_duration"] == 30.0

    def test_get_error_recovery_strategy(self) -> None:
        """Test getting appropriate error recovery strategies."""
        handler = ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            protocol_name="TEST",
            logger=logging.getLogger("test"),
        )

        # Test connection error strategy - create a custom exception with "Connection" in the name
        class CustomConnectionError(Exception):
            pass

        strategy = handler.get_error_recovery_strategy(
            CustomConnectionError("Connection failed"),
            "connect",
        )
        assert strategy["retry"]["should_retry"] is True

        # Test timeout error strategy - create a custom exception with "Timeout" in the name
        class CustomTimeoutError(Exception):
            pass

        strategy = handler.get_error_recovery_strategy(
            CustomTimeoutError("Operation timed out"),
            "read_data",
        )
        assert strategy["retry"]["should_retry"] is True

        # Test generic error strategy
        strategy = handler.get_error_recovery_strategy(
            ValueError("Generic error"),
            "test",
        )
        assert strategy["retry"]["should_retry"] is False

    def test_get_timeout_error_class_base(self) -> None:
        """Test that base class returns generic Exception for timeout errors."""
        handler = ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            protocol_name="UNKNOWN",
            logger=logging.getLogger("test"),
        )
        # Base class should return generic Exception
        assert handler._get_timeout_error_class() is Exception

    def test_create_timeout_error_base(self) -> None:
        """Test creating timeout errors with base class."""
        handler = ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            protocol_name="UNKNOWN",
            logger=logging.getLogger("test"),
        )
        error = handler._create_timeout_error("read_data", 30.0)
        assert isinstance(error, Exception)
        assert str(error) == "Operation read_data timed out after 30.0 seconds"


class TestBM6ErrorHandler:
    """Test cases for BM6-specific error handling."""

    def test_bm6_create_timeout_error(self) -> None:
        """Test creating BM6-specific timeout errors."""
        handler = BM6ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            logger=logging.getLogger("test"),
        )
        error = handler._create_timeout_error("read_data", 30.0)
        assert isinstance(error, BM6TimeoutError)
        assert error.device_address == "AA:BB:CC:DD:EE:FF"
        assert error.context["operation"] == "read_data"
        assert error.context["timeout_duration"] == 30.0

    def test_bm6_error_recovery_strategies(self) -> None:
        """Test BM6-specific error recovery strategies."""
        handler = BM6ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            logger=logging.getLogger("test"),
        )

        # Test BM6-specific exceptions
        strategy = handler.get_error_recovery_strategy(
            BM6ConnectionError("Connection failed"),
            "connect",
        )
        assert strategy["retry"]["should_retry"] is True

        strategy = handler.get_error_recovery_strategy(
            BM6ProtocolError("Protocol error"),
            "read_data",
        )
        assert strategy["retry"]["should_retry"] is False

        strategy = handler.get_error_recovery_strategy(
            BM6TimeoutError("Timeout", operation="read_data", timeout_duration=30.0),
            "read_data",
        )
        assert strategy["retry"]["should_retry"] is True


class TestBM2ErrorHandler:
    """Test cases for BM2-specific error handling."""

    def test_bm2_create_timeout_error(self) -> None:
        """Test creating BM2-specific timeout errors."""
        handler = BM2ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            logger=logging.getLogger("test"),
        )
        error = handler._create_timeout_error("read_data", 25.0)
        assert isinstance(error, BM2TimeoutError)
        assert error.device_address == "AA:BB:CC:DD:EE:FF"
        assert error.context["operation"] == "read_data"
        assert error.context["timeout_duration"] == 25.0

    def test_bm2_error_recovery_strategies(self) -> None:
        """Test BM2-specific error recovery strategies."""
        handler = BM2ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            logger=logging.getLogger("test"),
        )

        # Test BM2-specific exceptions
        strategy = handler.get_error_recovery_strategy(
            BM2ConnectionError("Connection failed"),
            "connect",
        )
        assert strategy["retry"]["should_retry"] is True

        strategy = handler.get_error_recovery_strategy(
            BM2ProtocolError("Protocol error"),
            "read_data",
        )
        assert strategy["retry"]["should_retry"] is False

        strategy = handler.get_error_recovery_strategy(
            BM2TimeoutError("Timeout", operation="read_data", timeout_duration=25.0),
            "read_data",
        )
        assert strategy["retry"]["should_retry"] is True


class TestErrorHandlerRetryLogic:
    """Test cases for retry logic functionality."""

    @pytest.mark.asyncio
    async def test_retry_decorator_success(self) -> None:
        """Test that retry decorator works correctly for successful operations."""
        handler = BM6ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            logger=logging.getLogger("test"),
        )

        call_count = 0

        @handler.with_retry(max_attempts=3, base_delay=0.1)
        async def successful_operation() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_operation()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_decorator_failure(self) -> None:
        """Test that retry decorator retries on failure."""
        handler = BM6ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            logger=logging.getLogger("test"),
        )

        call_count = 0

        @handler.with_retry(max_attempts=3, base_delay=0.1)
        async def failing_operation() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("Operation failed")

        with pytest.raises(ValueError, match="Operation failed"):
            await failing_operation()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_decorator_partial_success(self) -> None:
        """Test that retry decorator succeeds after some failures."""
        handler = BM6ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            logger=logging.getLogger("test"),
        )

        call_count = 0

        @handler.with_retry(max_attempts=3, base_delay=0.1)
        async def partially_failing_operation() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Operation failed")
            return "success"

        result = await partially_failing_operation()
        assert result == "success"
        assert call_count == 3


class TestErrorHandlerOperationContext:
    """Test cases for operation context manager."""

    @pytest.mark.asyncio
    async def test_operation_context_success(self) -> None:
        """Test operation context manager for successful operations."""
        handler = BM6ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            logger=logging.getLogger("test"),
        )

        # Override the _execute_operation method for testing
        async def mock_execute_operation(operation_name: str) -> str:
            return "success"

        handler._execute_operation = mock_execute_operation

        async with handler.operation_context("test_operation", timeout=1.0):
            pass  # The context manager handles the execution

        # Verify operation was recorded
        diagnostic_info = handler.get_diagnostic_info()
        assert len(diagnostic_info) > 0
        assert any(
            op.get("operation") == "test_operation" for op in diagnostic_info.values()
        )

    @pytest.mark.asyncio
    async def test_operation_context_timeout(self) -> None:
        """Test operation context manager for timeout scenarios."""
        handler = BM6ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            logger=logging.getLogger("test"),
        )

        # Override the _execute_operation method for testing
        async def mock_execute_operation(operation_name: str) -> str:
            await asyncio.sleep(1.0)  # This will cause a timeout
            return "success"

        handler._execute_operation = mock_execute_operation

        with pytest.raises(BM6TimeoutError):
            async with handler.operation_context(
                "test_operation",
                timeout=0.1,
            ):
                pass

    @pytest.mark.asyncio
    async def test_operation_context_error(self) -> None:
        """Test operation context manager for error scenarios."""
        handler = BM6ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            logger=logging.getLogger("test"),
        )

        # Override the _execute_operation method for testing
        async def mock_execute_operation(operation_name: str) -> str:
            raise ValueError("Test error")

        handler._execute_operation = mock_execute_operation

        with pytest.raises(ValueError, match="Test error"):
            async with handler.operation_context("test_operation", timeout=1.0):
                pass

    @pytest.mark.asyncio
    async def test_operation_context_with_different_results(self) -> None:
        """Test operation context manager with different operation results."""
        handler = BM6ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            logger=logging.getLogger("test"),
        )

        operation_results: dict[str, str | Exception] = {
            "success_op": "success",
            "error_op": ValueError("Test error"),
            "timeout_op": BM6TimeoutError(
                "Timeout",
                operation="timeout_op",
                timeout_duration=1.0,
            ),
        }

        async def mock_execute_operation(operation_name: str) -> str | Exception:
            result = operation_results[operation_name]
            if isinstance(result, Exception):
                raise result
            return result

        handler._execute_operation = mock_execute_operation

        # Test successful operation
        async with handler.operation_context("success_op", timeout=1.0):
            pass

        # Test error operation
        with pytest.raises(ValueError, match="Test error"):
            async with handler.operation_context("error_op", timeout=1.0):
                pass

        # Test timeout operation
        with pytest.raises(BM6TimeoutError):
            async with handler.operation_context("timeout_op", timeout=1.0):
                pass

    @pytest.mark.asyncio
    async def test_operation_context_diagnostic_info(self) -> None:
        """Test that operation context properly records diagnostic information."""
        handler = BM6ErrorHandler(
            device_address="AA:BB:CC:DD:EE:FF",
            logger=logging.getLogger("test"),
        )

        # Override the _execute_operation method for testing
        async def mock_execute_operation(operation_name: str) -> str:
            return "success"

        handler._execute_operation = mock_execute_operation

        async with handler.operation_context("test_operation", timeout=1.0):
            pass

        # Verify diagnostic info was recorded
        diagnostic_info = handler.get_diagnostic_info()
        assert len(diagnostic_info) > 0

        # Find the operation in diagnostic info
        operation_found = False
        for op_info in diagnostic_info.values():
            if op_info.get("operation") == "test_operation":
                operation_found = True
                assert op_info["status"] == "completed"
                assert "duration" in op_info
                assert "start_time" in op_info
                break

        assert operation_found, "Operation not found in diagnostic info"
