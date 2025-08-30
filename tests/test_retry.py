"""Tests for retry functionality."""

import asyncio
import time
from typing import NoReturn

import pytest

from src.battery_hawk_driver.base.retry import (
    BLERetryError,
    CircuitBreaker,
    CircuitBreakerOpenError,
    exponential_backoff,
    retry_async,
)


@pytest.mark.asyncio
async def test_retry_async_eventual_success() -> None:
    """Test retry_async decorator with eventual success."""
    calls = {"count": 0}

    @retry_async(attempts=3, base_delay=0.01, max_delay=0.05)
    async def flaky() -> str:
        """Flaky async function that succeeds on second call."""
        calls["count"] += 1
        if calls["count"] < 2:
            raise ValueError("fail")
        return "ok"

    result = await flaky()
    assert result == "ok"
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_retry_async_all_fail() -> None:
    """Test retry_async decorator when all attempts fail."""

    @retry_async(attempts=2, base_delay=0.01, max_delay=0.05, exceptions=(ValueError,))
    async def always_fail() -> NoReturn:
        """Async function that always fails."""
        raise ValueError("fail")

    with pytest.raises(BLERetryError):
        await always_fail()


def test_exponential_backoff_increases() -> None:
    """Test that exponential_backoff increases with attempts."""
    delays = [
        exponential_backoff(i, base_delay=0.01, max_delay=0.1, jitter=0)
        for i in range(5)
    ]
    assert all(delays[i] < delays[i + 1] for i in range(len(delays) - 1))
    # Test jitter
    d1 = exponential_backoff(2, base_delay=0.01, max_delay=0.1, jitter=0.5)
    d2 = exponential_backoff(2, base_delay=0.01, max_delay=0.1, jitter=0.5)
    assert abs(d1 - d2) < 0.1  # Should be close, but not always equal


def test_circuit_breaker_blocks_and_recovers() -> None:
    """Test CircuitBreaker blocks after failures and recovers after timeout."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
    assert not cb.is_open()
    cb.record_failure()
    assert not cb.is_open()
    cb.record_failure()
    assert cb.is_open()
    # Wait for recovery
    time.sleep(0.12)
    assert not cb.is_open()


@pytest.mark.asyncio
async def test_retry_async_with_circuit_breaker() -> None:
    """Test retry_async with circuit breaker blocking and recovery."""
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

    @retry_async(attempts=2, base_delay=0.01, max_delay=0.05, circuit_breaker=cb)
    async def fail_once() -> NoReturn:
        """Async function that always fails to trigger circuit breaker."""
        raise RuntimeError("fail")

    # First call triggers circuit breaker (should raise CircuitBreakerOpen)
    with pytest.raises(CircuitBreakerOpenError):
        await fail_once()
    # Now circuit breaker is open (should raise CircuitBreakerOpen)
    with pytest.raises(CircuitBreakerOpenError):
        await fail_once()
    # Wait for recovery
    await asyncio.sleep(0.12)
    # Should retry again (and fail, so CircuitBreakerOpen again)
    with pytest.raises(CircuitBreakerOpenError):
        await fail_once()
