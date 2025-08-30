"""Retry logic and circuit breaker for BLE operations."""

from __future__ import annotations

import asyncio
import random
import time
from functools import wraps
from typing import TYPE_CHECKING, ParamSpec, TypeVar

if TYPE_CHECKING:
    import logging
    from collections.abc import Awaitable, Callable

T = TypeVar("T")
P = ParamSpec("P")


class BLERetryError(Exception):
    """Raise when BLE operation fails after all retries."""


class BLEConnectionError(Exception):
    """Raised for BLE connection errors."""


class BLECommandError(Exception):
    """Raised for BLE command execution errors."""


class CircuitBreakerOpenError(Exception):
    """Raise when the circuit breaker is open and calls are blocked."""


class CircuitBreaker:
    """Simple circuit breaker for async BLE operations. Opens after a threshold of failures, blocks calls for a cooldown period."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> None:
        """Initialize CircuitBreaker with failure threshold and recovery timeout."""
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time: float | None = None
        self._open = False

    def record_failure(self) -> None:
        """Record a failure and open the circuit if threshold is reached."""
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self._open = True

    def record_success(self) -> None:
        """Record a successful call and reset the circuit breaker."""
        self.failures = 0
        self._open = False
        self.last_failure_time = None

    def is_open(self) -> bool:
        """Return True if the circuit breaker is open."""
        if self._open:
            if (
                self.last_failure_time
                and (time.time() - self.last_failure_time) > self.recovery_timeout
            ):
                self.record_success()
                return False
            return True
        return False


def exponential_backoff(
    attempt: int,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    jitter: float = 0.2,
) -> float:
    """Calculate exponential backoff delay with jitter."""
    delay = min(base_delay * (2**attempt), max_delay)
    # nosec: B311 - Not used for security/cryptography, only for retry jitter
    # Use of random.random is justified here because this is not a security/cryptography context.
    jitter_amount = delay * jitter * (random.random() * 2 - 1)  # nosec: B311  # noqa: S311
    return max(0.0, delay + jitter_amount)


def retry_async(
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    jitter: float = 0.2,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    logger: logging.Logger | None = None,
    circuit_breaker: CircuitBreaker | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorate an async BLE operation to retry with exponential backoff and optional circuit breaker."""

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exc: Exception | None = None
            for attempt in range(attempts):
                if circuit_breaker and circuit_breaker.is_open():
                    if logger:
                        logger.warning(
                            "Circuit breaker is open; blocking call to %s",
                            func.__name__,
                        )
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker open for {func.__name__}",
                    )
                try:
                    result = await func(*args, **kwargs)
                    if circuit_breaker:
                        circuit_breaker.record_success()
                except exceptions as exc:
                    last_exc = exc
                    if circuit_breaker:
                        circuit_breaker.record_failure()
                    if logger:
                        logger.warning(
                            "Retry %d/%d for %s due to %s: %s",
                            attempt + 1,
                            attempts,
                            func.__name__,
                            type(exc).__name__,
                            exc,
                        )
                    if attempt < attempts - 1:
                        delay = exponential_backoff(
                            attempt,
                            base_delay,
                            max_delay,
                            jitter,
                        )
                        await asyncio.sleep(delay)
                else:
                    return result

            if logger:
                logger.error("All %d attempts failed for %s", attempts, func.__name__)
            raise BLERetryError(
                f"All {attempts} attempts failed for {func.__name__}",
            ) from last_exc

        return wrapper

    return decorator
