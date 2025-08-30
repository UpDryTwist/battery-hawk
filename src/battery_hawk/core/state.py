"""
Device state management for Battery Hawk.

This module provides the DeviceStateManager class for centralized device state
tracking with thread-safe access and state change notifications.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from battery_hawk_driver.base.protocol import BatteryInfo, DeviceStatus


class DeviceState:
    """
    Represents the current state of a device.

    Contains device information, latest readings, connection status,
    and metadata about the device's current state.
    """

    def __init__(
        self,
        mac_address: str,
        device_type: str,
        friendly_name: str | None = None,
    ) -> None:
        """
        Initialize device state.

        Args:
            mac_address: MAC address of the device
            device_type: Type of device (BM6, BM2, etc.)
            friendly_name: Human-readable name for the device (optional)
        """
        self.mac_address = mac_address
        self.device_type = device_type
        self.friendly_name = friendly_name or f"Device_{mac_address}"

        # Connection state
        self.connected = False
        self.last_connection_attempt: datetime | None = None
        self.connection_error_count = 0
        self.last_connection_error: str | None = None

        # Device data
        self.latest_reading: BatteryInfo | None = None
        self.last_reading_time: datetime | None = None
        self.reading_count = 0

        # Device status
        self.device_status: DeviceStatus | None = None
        self.last_status_update: datetime | None = None

        # Polling state
        self.polling_active = False
        self.last_poll_time: datetime | None = None
        self.polling_error_count = 0
        self.last_polling_error: str | None = None

        # Metadata
        self.created_at = datetime.now(UTC)
        self.last_updated = datetime.now(UTC)
        self.vehicle_id: str | None = None

    def update_reading(self, reading: BatteryInfo) -> None:
        """
        Update the device with new reading data.

        Args:
            reading: New battery reading data
        """
        self.latest_reading = reading
        self.last_reading_time = datetime.now(UTC)
        self.reading_count += 1
        self.last_updated = datetime.now(UTC)

        # Reset error counts on successful reading
        self.connection_error_count = 0
        self.polling_error_count = 0
        self.last_connection_error = None
        self.last_polling_error = None

    def update_status(self, status: DeviceStatus) -> None:
        """
        Update the device status.

        Args:
            status: New device status
        """
        self.device_status = status
        self.last_status_update = datetime.now(UTC)
        self.connected = status.connected
        self.last_updated = datetime.now(UTC)

    def update_connection_state(
        self,
        connected: bool,
        error: str | None = None,
    ) -> None:
        """
        Update the connection state.

        Args:
            connected: Whether the device is connected
            error: Optional error message if connection failed
        """
        self.connected = connected
        self.last_connection_attempt = datetime.now(UTC)
        self.last_updated = datetime.now(UTC)

        if error:
            self.connection_error_count += 1
            self.last_connection_error = error
        else:
            self.connection_error_count = 0
            self.last_connection_error = None

    def update_polling_state(self, active: bool, error: str | None = None) -> None:
        """
        Update the polling state.

        Args:
            active: Whether polling is active
            error: Optional error message if polling failed
        """
        self.polling_active = active
        self.last_poll_time = datetime.now(UTC)
        self.last_updated = datetime.now(UTC)

        if error:
            self.polling_error_count += 1
            self.last_polling_error = error
        else:
            self.polling_error_count = 0
            self.last_polling_error = None

    def set_vehicle_association(self, vehicle_id: str | None) -> None:
        """
        Set vehicle association for this device.

        Args:
            vehicle_id: Vehicle ID to associate with, or None to remove association
        """
        self.vehicle_id = vehicle_id
        self.last_updated = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert device state to dictionary for serialization.

        Returns:
            Dictionary representation of device state
        """
        return {
            "mac_address": self.mac_address,
            "device_type": self.device_type,
            "friendly_name": self.friendly_name,
            "connected": self.connected,
            "last_connection_attempt": self.last_connection_attempt.isoformat()
            if self.last_connection_attempt
            else None,
            "connection_error_count": self.connection_error_count,
            "last_connection_error": self.last_connection_error,
            "latest_reading": {
                "voltage": self.latest_reading.voltage if self.latest_reading else None,
                "current": self.latest_reading.current if self.latest_reading else None,
                "temperature": self.latest_reading.temperature
                if self.latest_reading
                else None,
                "state_of_charge": self.latest_reading.state_of_charge
                if self.latest_reading
                else None,
                "capacity": self.latest_reading.capacity
                if self.latest_reading
                else None,
                "cycles": self.latest_reading.cycles if self.latest_reading else None,
                "timestamp": self.latest_reading.timestamp
                if self.latest_reading
                else None,
            }
            if self.latest_reading
            else None,
            "last_reading_time": self.last_reading_time.isoformat()
            if self.last_reading_time
            else None,
            "reading_count": self.reading_count,
            "device_status": {
                "connected": self.device_status.connected
                if self.device_status
                else None,
                "error_code": self.device_status.error_code
                if self.device_status
                else None,
                "error_message": self.device_status.error_message
                if self.device_status
                else None,
                "protocol_version": self.device_status.protocol_version
                if self.device_status
                else None,
                "last_command": self.device_status.last_command
                if self.device_status
                else None,
            }
            if self.device_status
            else None,
            "last_status_update": self.last_status_update.isoformat()
            if self.last_status_update
            else None,
            "polling_active": self.polling_active,
            "last_poll_time": self.last_poll_time.isoformat()
            if self.last_poll_time
            else None,
            "polling_error_count": self.polling_error_count,
            "last_polling_error": self.last_polling_error,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "vehicle_id": self.vehicle_id,
        }


class DeviceStateManager:
    """
    Centralized device state tracking system.

    Provides thread-safe access to device states and state change notifications
    using the observer pattern. Manages device state updates and provides
    methods for querying device states.
    """

    def __init__(self) -> None:
        """Initialize DeviceStateManager."""
        self.logger = logging.getLogger("battery_hawk.state_manager")

        # Device states storage
        self._states: dict[str, DeviceState] = {}
        self._lock = asyncio.Lock()

        # State change observers
        self._observers: dict[
            str,
            list[Callable[[str, DeviceState | None, DeviceState | None], None]],
        ] = {
            "reading": [],
            "status": [],
            "connection": [],
            "polling": [],
            "all": [],
        }

    async def register_device(self, mac_address: str, device_type: str) -> bool:
        """
        Register a new device.

        Args:
            mac_address: Device MAC address
            device_type: Type of device

        Returns:
            True if device was registered, False if already exists
        """
        async with self._lock:
            if mac_address in self._states:
                return False

            self._states[mac_address] = DeviceState(mac_address, device_type)
            self.logger.debug("Registered device: %s (%s)", mac_address, device_type)
            return True

    async def unregister_device(self, mac_address: str) -> bool:
        """
        Unregister a device.

        Args:
            mac_address: Device MAC address

        Returns:
            True if device was unregistered, False if not found
        """
        async with self._lock:
            if mac_address not in self._states:
                return False

            old_state = self._states[mac_address]
            del self._states[mac_address]
            self.logger.debug("Unregistered device: %s", mac_address)

            # Notify observers of device removal
            self._notify_observers("removed", mac_address, None, old_state)
            return True

    async def update_device_reading(
        self,
        mac_address: str,
        reading: BatteryInfo,
    ) -> bool:
        """
        Update device reading data.

        Args:
            mac_address: Device MAC address
            reading: Battery information

        Returns:
            True if device was updated, False if not found
        """
        async with self._lock:
            if mac_address not in self._states:
                return False

            old_state = self._states[mac_address]
            self._states[mac_address].update_reading(reading)

            # Notify observers of reading update
            self._notify_observers(
                "reading",
                mac_address,
                self._states[mac_address],
                old_state,
            )
            return True

    async def update_device_status(
        self,
        mac_address: str,
        status: DeviceStatus,
    ) -> bool:
        """
        Update device status.

        Args:
            mac_address: Device MAC address
            status: Device status

        Returns:
            True if device was updated, False if not found
        """
        async with self._lock:
            if mac_address not in self._states:
                return False

            old_state = self._states[mac_address]
            self._states[mac_address].update_status(status)

            # Notify observers of status update
            self._notify_observers(
                "status",
                mac_address,
                self._states[mac_address],
                old_state,
            )
            return True

    async def update_connection_state(
        self,
        mac_address: str,
        connected: bool,
        error: str | None = None,
    ) -> bool:
        """
        Update device connection state.

        Args:
            mac_address: Device MAC address
            connected: Connection status
            error: Error message if connection failed

        Returns:
            True if device was updated, False if not found
        """
        async with self._lock:
            if mac_address not in self._states:
                return False

            old_state = self._states[mac_address]
            self._states[mac_address].update_connection_state(connected, error)

            # Notify observers of connection state change
            self._notify_observers(
                "connection",
                mac_address,
                self._states[mac_address],
                old_state,
            )
            return True

    async def update_polling_state(
        self,
        mac_address: str,
        active: bool,
        error: str | None = None,
    ) -> bool:
        """
        Update device polling state.

        Args:
            mac_address: Device MAC address
            active: Polling status
            error: Error message if polling failed

        Returns:
            True if device was updated, False if not found
        """
        async with self._lock:
            if mac_address not in self._states:
                return False

            old_state = self._states[mac_address]
            self._states[mac_address].update_polling_state(active, error)

            # Notify observers of polling state change
            self._notify_observers(
                "polling",
                mac_address,
                self._states[mac_address],
                old_state,
            )
            return True

    async def set_vehicle_association(
        self,
        mac_address: str,
        vehicle_id: str | None,
    ) -> bool:
        """
        Set vehicle association for a device.

        Args:
            mac_address: Device MAC address
            vehicle_id: Vehicle ID to associate with

        Returns:
            True if device was updated, False if not found
        """
        async with self._lock:
            if mac_address not in self._states:
                return False

            old_state = self._states[mac_address]
            self._states[mac_address].set_vehicle_association(vehicle_id)

            # Notify observers of vehicle association change
            self._notify_observers(
                "vehicle",
                mac_address,
                self._states[mac_address],
                old_state,
            )
            return True

    def get_device_state(self, mac_address: str) -> DeviceState | None:
        """
        Get device state by MAC address.

        Args:
            mac_address: MAC address of the device

        Returns:
            DeviceState if found, None otherwise
        """
        return self._states.get(mac_address)

    def get_all_devices(self) -> list[DeviceState]:
        """
        Get all registered devices.

        Returns:
            List of all device states
        """
        return list(self._states.values())

    def get_devices_by_type(self, device_type: str) -> list[DeviceState]:
        """
        Get all devices of a specific type.

        Args:
            device_type: Type of device to filter by

        Returns:
            List of device states of the specified type
        """
        return [
            state for state in self._states.values() if state.device_type == device_type
        ]

    def get_devices_by_vehicle(self, vehicle_id: str) -> list[DeviceState]:
        """
        Get all devices associated with a vehicle.

        Args:
            vehicle_id: Vehicle ID to filter by

        Returns:
            List of device states associated with the vehicle
        """
        return [
            state for state in self._states.values() if state.vehicle_id == vehicle_id
        ]

    def get_connected_devices(self) -> list[DeviceState]:
        """
        Get all currently connected devices.

        Returns:
            List of connected device states
        """
        return [state for state in self._states.values() if state.connected]

    def get_polling_devices(self) -> list[DeviceState]:
        """
        Get all devices with active polling.

        Returns:
            List of device states with active polling
        """
        return [state for state in self._states.values() if state.polling_active]

    def get_devices_with_errors(self) -> list[DeviceState]:
        """
        Get all devices with connection or polling errors.

        Returns:
            List of device states with errors
        """
        return [
            state
            for state in self._states.values()
            if state.connection_error_count > 0 or state.polling_error_count > 0
        ]

    def subscribe_to_changes(
        self,
        event_type: str,
        callback: Callable[[str, DeviceState | None, DeviceState | None], None],
    ) -> None:
        """
        Subscribe to state change events.

        Args:
            event_type: Type of event to subscribe to ('reading', 'status', 'connection', 'polling', 'vehicle', 'removed', 'all')
            callback: Callback function to call when event occurs
        """
        if event_type not in self._observers:
            self.logger.warning("Invalid event type: %s", event_type)
            return

        self._observers[event_type].append(callback)
        self.logger.debug("Added observer for event type: %s", event_type)

    def unsubscribe_from_changes(
        self,
        event_type: str,
        callback: Callable[[str, DeviceState | None, DeviceState | None], None],
    ) -> bool:
        """
        Unsubscribe from state change events.

        Args:
            event_type: Type of event to unsubscribe from
            callback: Callback function to remove

        Returns:
            True if callback was removed, False if not found
        """
        if event_type not in self._observers:
            return False

        try:
            self._observers[event_type].remove(callback)
            self.logger.debug("Removed observer for event type: %s", event_type)
        except ValueError:
            return False
        return True

    def _notify_observers(
        self,
        event_type: str,
        mac_address: str,
        new_state: DeviceState | None,
        old_state: DeviceState | None,
    ) -> None:
        """
        Notify all observers of a state change.

        Args:
            event_type: Type of state change event
            mac_address: MAC address of the device
            new_state: New device state (None if device was removed)
            old_state: Previous device state (None if device was added)
        """
        if event_type not in self._observers:
            return

        # Notify specific event type observers
        self._notify_observer_list(
            self._observers[event_type],
            mac_address,
            new_state,
            old_state,
        )

        # Notify 'all' event type observers
        if "all" in self._observers:
            self._notify_observer_list(
                self._observers["all"],
                mac_address,
                new_state,
                old_state,
            )

    def _notify_observer_list(
        self,
        observers: list[Callable[[str, DeviceState | None, DeviceState | None], None]],
        mac_address: str,
        new_state: DeviceState | None,
        old_state: DeviceState | None,
    ) -> None:
        """
        Notify a list of observers.

        Args:
            observers: List of observer callbacks
            mac_address: MAC address of the device
            new_state: New device state
            old_state: Previous device state
        """
        for callback in observers:
            self._execute_observer_callback(callback, mac_address, new_state, old_state)

    def _execute_observer_callback(
        self,
        callback: Callable[[str, DeviceState | None, DeviceState | None], None],
        mac_address: str,
        new_state: DeviceState | None,
        old_state: DeviceState | None,
    ) -> None:
        """Execute a single observer callback with error handling."""
        try:
            callback(mac_address, new_state, old_state)
        except Exception:
            self.logger.exception("Error in state change observer callback")

    def get_summary(self) -> dict[str, Any]:
        """
        Get a summary of all device states.

        Returns:
            Dictionary with summary statistics
        """
        total_devices = len(self._states)
        connected_devices = len(self.get_connected_devices())
        polling_devices = len(self.get_polling_devices())
        devices_with_errors = len(self.get_devices_with_errors())

        device_types = {}
        for state in self._states.values():
            device_types[state.device_type] = device_types.get(state.device_type, 0) + 1

        return {
            "total_devices": total_devices,
            "connected_devices": connected_devices,
            "polling_devices": polling_devices,
            "devices_with_errors": devices_with_errors,
            "device_types": device_types,
            "last_updated": datetime.now(UTC).isoformat(),
        }
