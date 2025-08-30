"""Connection state management for BLE devices."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from enum import Enum, auto
from typing import Any, cast


class ConnectionState(Enum):
    """Enum representing BLE device connection states."""

    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    DISCONNECTING = auto()
    ERROR = auto()


class ConnectionStateManager:
    """State manager for BLE device connections, with event callbacks and history."""

    def __init__(self) -> None:
        """Initialize ConnectionStateManager with default state and history."""
        self._state: ConnectionState = ConnectionState.DISCONNECTED
        self._history: list[tuple[ConnectionState, float]] = [
            (self._state, time.time()),
        ]
        self._callbacks: dict[
            ConnectionState,
            list[Callable[[ConnectionState], Any]],
        ] = {}
        self._lock = asyncio.Lock()

    @property
    def state(self) -> ConnectionState:
        """Get the current connection state."""
        return self._state

    @property
    def history(self) -> list[tuple[ConnectionState, float]]:
        """Get the history of state transitions as (state, timestamp) tuples."""
        return self._history.copy()

    def on_state(
        self,
        state: ConnectionState,
        callback: Callable[[ConnectionState], Any],
    ) -> None:
        """
        Register a callback to be called when the given state is entered.

        Args:
            state: The ConnectionState to listen for.
            callback: Function to call with the new state.
        """
        self._callbacks.setdefault(state, []).append(callback)

    async def set_state(self, new_state: ConnectionState) -> None:
        """
        Transition to a new state, record history, and trigger callbacks.

        Args:
            new_state: The new ConnectionState to transition to.
        """
        async with self._lock:
            if new_state != self._state:
                self._state = new_state
                self._history.append((new_state, time.time()))
                for cb in self._callbacks.get(new_state, []):
                    result = cb(new_state)
                    if asyncio.iscoroutine(result):
                        await cast("Awaitable", result)

    async def auto_reconnect(self, max_attempts: int = 3, delay: float = 2.0) -> None:
        """Stub for automatic reconnection logic. To be integrated with device logic."""
        for _attempt in range(max_attempts):
            await self.set_state(ConnectionState.CONNECTING)
            # Insert actual connection logic here
            await asyncio.sleep(delay)
            # For now, always fail
            await self.set_state(ConnectionState.ERROR)
        await self.set_state(ConnectionState.DISCONNECTED)

    def get_state_history(self, limit: int = 20) -> list[tuple[ConnectionState, float]]:
        """
        Get the most recent state transitions.

        Args:
            limit: Maximum number of history entries to return.

        Returns:
            List of (state, timestamp) tuples.
        """
        return self._history[-limit:]
