"""Tests for ConnectionState and ConnectionStateManager in battery_hawk_driver.base.state."""

import pytest

from src.battery_hawk_driver.base.state import ConnectionState, ConnectionStateManager


@pytest.mark.asyncio
async def test_state_transitions_and_current_state() -> None:
    """Test state transitions and current state tracking."""
    mgr = ConnectionStateManager()
    assert mgr.state == ConnectionState.DISCONNECTED
    await mgr.set_state(ConnectionState.CONNECTING)
    assert mgr.state == ConnectionState.CONNECTING
    await mgr.set_state(ConnectionState.CONNECTED)
    assert mgr.state == ConnectionState.CONNECTED
    await mgr.set_state(ConnectionState.DISCONNECTING)
    assert mgr.state == ConnectionState.DISCONNECTING
    await mgr.set_state(ConnectionState.ERROR)
    assert mgr.state == ConnectionState.ERROR


@pytest.mark.asyncio
async def test_callback_invocation_sync_and_async() -> None:
    """Test callback invocation for sync and async callbacks."""
    mgr = ConnectionStateManager()
    called = {"sync": False, "async": False}

    def sync_cb(state: ConnectionState) -> None:
        """Sync callback for state change."""
        called["sync"] = True

    async def async_cb(state: ConnectionState) -> None:
        """Async callback for state change."""
        called["async"] = True

    mgr.on_state(ConnectionState.CONNECTED, sync_cb)
    mgr.on_state(ConnectionState.CONNECTED, async_cb)
    await mgr.set_state(ConnectionState.CONNECTED)
    assert called["sync"]
    assert called["async"]


@pytest.mark.asyncio
async def test_state_history_and_get_state_history() -> None:
    """Test state history and get_state_history method."""
    mgr = ConnectionStateManager()
    await mgr.set_state(ConnectionState.CONNECTING)
    await mgr.set_state(ConnectionState.CONNECTED)
    await mgr.set_state(ConnectionState.DISCONNECTING)
    await mgr.set_state(ConnectionState.ERROR)
    hist = mgr.get_state_history(limit=3)
    assert len(hist) == 3
    assert hist[-1][0] == ConnectionState.ERROR


@pytest.mark.asyncio
async def test_auto_reconnect_stub() -> None:
    """Test auto_reconnect stub method."""
    mgr = ConnectionStateManager()
    await mgr.auto_reconnect(max_attempts=2, delay=0.01)
    assert mgr.state == ConnectionState.DISCONNECTED
