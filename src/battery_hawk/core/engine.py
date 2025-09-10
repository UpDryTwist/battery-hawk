"""
Core monitoring engine for Battery Hawk.

This module provides the BatteryHawkCore class, which is the central
AsyncIO-based monitoring engine that manages device polling, state tracking,
and coordinates system operations.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import signal
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    from battery_hawk.config.config_manager import ConfigManager

from battery_hawk_driver.base.connection import BLEConnectionPool
from battery_hawk_driver.base.device_factory import DeviceFactory
from battery_hawk_driver.base.discovery import BLEDiscoveryService

from .auto_config import AutoConfigurationService
from .registry import DeviceRegistry, VehicleRegistry
from .state import DeviceStateManager
from .storage import DataStorage

# Type alias for event handlers
EventHandler = Union[Callable[[dict[str, Any]], None], Callable[[dict[str, Any]], Any]]


class BatteryHawkCore:
    """
    Core monitoring engine for Battery Hawk.

    This class manages the main event loop, device discovery, polling,
    and coordinates all system operations using AsyncIO.
    """

    def __init__(self, config_manager: ConfigManager) -> None:
        """
        Initialize BatteryHawkCore with all required components.

        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager
        self.logger = logging.getLogger("battery_hawk.core")

        # Initialize all required components
        self.connection_pool = BLEConnectionPool(config_manager)
        self.discovery_service = BLEDiscoveryService(config_manager)
        self.device_factory = DeviceFactory(self.connection_pool)
        self.auto_config_service = AutoConfigurationService(
            config_manager,
            self.device_factory,
        )
        self.device_registry = DeviceRegistry(config_manager, self.auto_config_service)
        self.vehicle_registry = VehicleRegistry(config_manager)
        self.data_storage = DataStorage(config_manager)
        self.state_manager = DeviceStateManager()

        # State tracking attributes
        self.running = False
        self.tasks: list[asyncio.Task[Any]] = []
        self.shutdown_event = asyncio.Event()

        # Device management
        self.active_devices: dict[str, Any] = {}
        self.polling_tasks: dict[str, asyncio.Task[Any]] = {}

        # Event handling
        self.event_handlers: dict[str, list[EventHandler]] = {
            "device_discovered": [],
            "device_connected": [],
            "device_disconnected": [],
            "device_error": [],
            "vehicle_associated": [],
            "system_shutdown": [],
        }

        self.logger.info("BatteryHawkCore initialized with all components")

    async def start(self) -> None:
        """
        Start the core monitoring engine.

        This method initializes all components and starts the main event loop
        with discovery and polling tasks.
        """
        try:
            self.logger.info("Starting BatteryHawkCore")
            self.running = True

            # Connect to storage backend
            await self.data_storage.connect()

            # Start connection pool cleanup task
            await self.connection_pool.start_cleanup()

            # Set up signal handlers for graceful shutdown
            self._setup_signal_handlers()

            # Start core tasks
            self.tasks.append(asyncio.create_task(self._run_initial_discovery()))
            self.tasks.append(asyncio.create_task(self._run_periodic_discovery()))
            self.tasks.append(asyncio.create_task(self._run_device_polling()))
            self.tasks.append(asyncio.create_task(self._run_vehicle_association()))

            # Wait for shutdown signal
            await self._wait_for_shutdown()

        except Exception:
            self.logger.exception("Error starting BatteryHawkCore")
            await self.stop()
            raise

    async def stop(self) -> None:
        """
        Stop the core monitoring engine gracefully.

        This method stops all tasks, disconnects from devices,
        and cleans up resources.
        """
        self.logger.info("Stopping BatteryHawkCore")
        self.running = False
        self.shutdown_event.set()

        # Notify system shutdown event handlers
        await self._notify_event_handlers("system_shutdown", {})

        # Disconnect all active devices and notify disconnection events
        await self._disconnect_all_devices()

        # Clear active devices
        self.active_devices.clear()

        # Cancel all polling tasks
        for task in self.polling_tasks.values():
            task.cancel()

        # Wait for all tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

        # Disconnect from storage
        await self.data_storage.disconnect()

        # Shutdown connection pool
        await self.connection_pool.shutdown()

        self.logger.info("BatteryHawkCore stopped")

    async def _disconnect_all_devices(self) -> None:
        """Disconnect all active devices during shutdown."""
        if self.active_devices:
            self.logger.info(
                "Disconnecting %d active devices",
                len(self.active_devices),
            )
            for mac_address, device in self.active_devices.items():
                await self._disconnect_single_device(mac_address, device)
        else:
            self.logger.info("No active devices to disconnect")

    async def _disconnect_single_device(
        self,
        mac_address: str,
        device: dict[str, Any],
    ) -> None:
        """Disconnect a single device and notify event handlers."""
        try:
            self.logger.info("Disconnecting device %s", mac_address)

            # Notify device disconnected event handlers
            await self._notify_event_handlers(
                "device_disconnected",
                {
                    "mac_address": mac_address,
                    "device_type": device.get("device_type", "unknown"),
                },
            )

            # Disconnect device
            await self.connection_pool.disconnect(mac_address)
            self.logger.info("Successfully disconnected device %s", mac_address)
        except Exception:
            self.logger.exception("Error disconnecting device %s", mac_address)

    async def _run_initial_discovery(self) -> None:
        """
        Run initial device discovery on startup.

        This method performs an initial BLE scan to discover devices
        and registers them with the device registry.
        """
        try:
            self.logger.info("Starting initial device discovery")

            # Check if initial scan is enabled
            discovery_config = self.config.get_config("system").get("discovery", {})
            if not discovery_config.get("initial_scan", True):
                self.logger.info("Initial discovery disabled, skipping")
                return

            # Perform discovery scan
            scan_duration = discovery_config.get("scan_duration", 10)
            discovered_devices = await self.discovery_service.scan_for_devices(
                duration=scan_duration,
            )

            # Register discovered devices
            await self.device_registry.register_discovered_devices(discovered_devices)

            # Register devices with state manager and notify event handlers
            for mac_address, device_info in discovered_devices.items():
                with contextlib.suppress(ValueError):
                    await self.state_manager.register_device(
                        mac_address,
                        device_info.get("device_type", "unknown"),
                    )

                    # Notify device discovered event handlers
                    await self._notify_event_handlers(
                        "device_discovered",
                        {
                            "mac_address": mac_address,
                            "device_type": device_info.get("device_type", "unknown"),
                            "name": device_info.get("name", f"Device_{mac_address}"),
                            "rssi": device_info.get("rssi"),
                            "advertisement_data": device_info.get(
                                "advertisement_data",
                                {},
                            ),
                        },
                    )

            self.logger.info(
                "Initial discovery completed: %d devices found",
                len(discovered_devices),
            )

        except Exception:
            self.logger.exception("Error during initial discovery")

    async def _run_periodic_discovery(self) -> None:
        """
        Run periodic device discovery.

        This method performs periodic BLE scans to discover new devices
        at configurable intervals.
        """
        try:
            self.logger.info("Starting periodic device discovery")

            discovery_config = self.config.get_config("system").get("discovery", {})
            periodic_interval = discovery_config.get(
                "periodic_interval",
                43200,
            )  # 12 hours default

            while self.running and not self.shutdown_event.is_set():
                try:
                    # Wait for the configured interval
                    await asyncio.sleep(periodic_interval)

                    if not self.running or self.shutdown_event.is_set():
                        break

                    self.logger.info("Running periodic device discovery")

                    # Perform discovery scan
                    scan_duration = discovery_config.get("scan_duration", 10)
                    discovered_devices = await self.discovery_service.scan_for_devices(
                        duration=scan_duration,
                    )

                    # Register discovered devices
                    await self.device_registry.register_discovered_devices(
                        discovered_devices,
                    )

                    # Register devices with state manager and notify event handlers
                    for mac_address, device_info in discovered_devices.items():
                        with contextlib.suppress(ValueError):
                            await self.state_manager.register_device(
                                mac_address,
                                device_info.get("device_type", "unknown"),
                            )

                            # Notify device discovered event handlers
                            await self._notify_event_handlers(
                                "device_discovered",
                                {
                                    "mac_address": mac_address,
                                    "device_type": device_info.get(
                                        "device_type",
                                        "unknown",
                                    ),
                                    "name": device_info.get(
                                        "name",
                                        f"Device_{mac_address}",
                                    ),
                                    "rssi": device_info.get("rssi"),
                                    "advertisement_data": device_info.get(
                                        "advertisement_data",
                                        {},
                                    ),
                                },
                            )

                    self.logger.info(
                        "Periodic discovery completed: %d devices found",
                        len(discovered_devices),
                    )

                except asyncio.CancelledError:
                    break
                except Exception:
                    self.logger.exception("Error during periodic discovery")
                    # Wait a bit before retrying
                    await asyncio.sleep(60)

        except Exception:
            self.logger.exception("Error in periodic discovery task")

    async def _run_device_polling(self) -> None:
        """
        Run the device polling system.

        This method continuously monitors configured devices and polls them
        at their specified intervals.
        """
        try:
            self.logger.info("Starting device polling system")
            polling_cycle_count = 0

            while self.running and not self.shutdown_event.is_set():
                try:
                    # Get configured devices
                    configured_devices = self.device_registry.get_configured_devices()
                    polling_cycle_count += 1

                    # Start polling tasks for new devices
                    new_tasks_started = 0
                    for device_info in configured_devices:
                        mac_address = device_info.get("mac_address")
                        polling_interval = device_info.get("polling_interval", 3600)

                        if not mac_address:
                            continue

                        # Start polling task if not already running
                        if mac_address not in self.polling_tasks:
                            self.polling_tasks[mac_address] = asyncio.create_task(
                                self._poll_device(mac_address, polling_interval),
                            )
                            self.logger.info(
                                "Started polling for device %s (interval: %ds)",
                                mac_address,
                                polling_interval,
                            )
                            new_tasks_started += 1

                    # Clean up completed tasks
                    completed_tasks = [
                        mac for mac, task in self.polling_tasks.items() if task.done()
                    ]
                    for mac in completed_tasks:
                        del self.polling_tasks[mac]

                    # Log status periodically (every 10 cycles)
                    if polling_cycle_count % 10 == 0:
                        self.logger.info(
                            "Polling status: %d active tasks, %d configured devices",
                            len(self.polling_tasks),
                            len(configured_devices),
                        )

                    # Wait before checking for new devices
                    await asyncio.sleep(30)

                except asyncio.CancelledError:
                    break
                except Exception:
                    self.logger.exception("Error in device polling task")
                    await asyncio.sleep(60)

        except Exception:
            self.logger.exception("Error in device polling system")
        finally:
            self.logger.info("Device polling system stopped")

    async def _poll_device(self, mac_address: str, polling_interval: int) -> None:
        """
        Poll a specific device at the configured interval.

        Args:
            mac_address: MAC address of the device to poll
            polling_interval: Polling interval in seconds
        """
        try:
            # Flag to track if this is the first poll for immediate baseline reading
            first_poll = True

            while self.running and not self.shutdown_event.is_set():
                try:
                    # For first poll, don't wait - take immediate baseline reading
                    if not first_poll:
                        # Wait for the polling interval
                        await asyncio.sleep(polling_interval)

                    if not self.running or self.shutdown_event.is_set():
                        break

                    # Get device information
                    device_info = self.device_registry.get_device(mac_address)
                    if not device_info:
                        self.logger.warning(
                            "Device %s not found in registry",
                            mac_address,
                        )
                        continue

                    # Check if device is already active
                    if mac_address not in self.active_devices:
                        device_type = device_info.get("device_type", "unknown")
                        if device_type == "unknown":
                            self.logger.warning(
                                "Unknown device type for %s, skipping",
                                mac_address,
                            )
                            await self.state_manager.update_connection_state(
                                mac_address,
                                connected=False,
                                error="Unknown device type",
                            )
                            continue

                        try:
                            device = self.device_factory.create_device(
                                device_type,
                                mac_address,
                            )
                            self.active_devices[mac_address] = device

                            # Establish BLE connection and set up notifications
                            await device.connect()

                            # Update connection state
                            await self.state_manager.update_connection_state(
                                mac_address,
                                connected=True,
                            )

                            # Notify device connected event handlers
                            await self._notify_event_handlers(
                                "device_connected",
                                {
                                    "mac_address": mac_address,
                                    "device_type": device_type,
                                    "vehicle_id": device_info.get("vehicle_id"),
                                },
                            )

                        except Exception as e:
                            error_msg = f"Failed to create device: {e!s}"
                            self.logger.exception(
                                "Failed to create device %s",
                                mac_address,
                            )
                            await self.state_manager.update_connection_state(
                                mac_address,
                                connected=False,
                                error=error_msg,
                            )

                            # Notify device error event handlers
                            await self._notify_event_handlers(
                                "device_error",
                                {
                                    "mac_address": mac_address,
                                    "device_type": device_type,
                                    "error": error_msg,
                                },
                            )
                            continue

                    # Poll the device
                    await self._poll_single_device(mac_address, device_info)

                    # Mark first poll as complete to enable normal interval timing
                    if first_poll:
                        first_poll = False
                        self.logger.info(
                            "Completed initial baseline reading for device %s",
                            mac_address,
                        )

                except asyncio.CancelledError:
                    break
                except Exception:
                    self.logger.exception("Error polling device %s", mac_address)
                    # Wait before retrying
                    await asyncio.sleep(60)

        except Exception:
            self.logger.exception("Error in device polling for %s", mac_address)

    async def _poll_single_device(
        self,
        mac_address: str,
        device_info: dict[str, Any],
    ) -> None:
        """
        Poll a single device and store the reading.

        Args:
            mac_address: MAC address of the device
            device_info: Device information from registry
        """
        try:
            # Update polling state to active
            await self.state_manager.update_polling_state(mac_address, active=True)

            device = self.active_devices.get(mac_address)
            if not device:
                self.logger.warning("Device %s not available for polling", mac_address)
                await self.state_manager.update_polling_state(
                    mac_address,
                    active=False,
                    error="Device not available",
                )
                return

            # Read data from device
            try:
                reading = await device.read_data()

                # Update device reading in state manager
                await self.state_manager.update_device_reading(mac_address, reading)

                # Also persist latest reading on the device object for API/persistence
                reading_dict_for_device = {
                    "voltage": getattr(reading, "voltage", None),
                    "current": getattr(reading, "current", None),
                    "temperature": getattr(reading, "temperature", None),
                    "state_of_charge": getattr(reading, "state_of_charge", None),
                    "capacity": getattr(reading, "capacity", None),
                    "cycles": getattr(reading, "cycles", None),
                    "timestamp": getattr(reading, "timestamp", None),
                    "extra": getattr(reading, "extra", {}),
                }
                await self.device_registry.update_latest_reading(
                    mac_address,
                    reading_dict_for_device,
                )

                # Update device status
                device_status = await device.send_command("status")
                await self.state_manager.update_device_status(
                    mac_address,
                    device_status,
                )

                # Persist device status on the device object as well
                status_dict_for_device = {
                    "connected": getattr(device_status, "connected", None),
                    "error_code": getattr(device_status, "error_code", None),
                    "error_message": getattr(device_status, "error_message", None),
                    "protocol_version": getattr(
                        device_status,
                        "protocol_version",
                        None,
                    ),
                    "last_command": getattr(device_status, "last_command", None),
                }
                await self.device_registry.update_device_status(
                    mac_address,
                    status_dict_for_device,
                )

            except (OSError, ConnectionError, TimeoutError) as e:
                error_msg = f"Failed to read device data: {e!s}"
                self.logger.warning(
                    "Error reading device %s: %s",
                    mac_address,
                    error_msg,
                )
                await self.state_manager.update_polling_state(
                    mac_address,
                    active=False,
                    error=error_msg,
                )

                # Notify device error event handlers
                await self._notify_event_handlers(
                    "device_error",
                    {
                        "mac_address": mac_address,
                        "device_type": device_info.get("device_type", "unknown"),
                        "error": error_msg,
                    },
                )
                return

            # Store the reading
            vehicle_id = device_info.get("vehicle_id", "unknown")
            device_type = device_info.get("device_type", "unknown")

            # Convert reading to dictionary format
            reading_dict = {
                "voltage": reading.voltage,
                "current": reading.current,
                "temperature": reading.temperature,
                "state_of_charge": reading.state_of_charge,
                "capacity": getattr(reading, "capacity", None),
                "cycles": getattr(reading, "cycles", None),
                "timestamp": getattr(reading, "timestamp", None),
                "extra": getattr(reading, "extra", {}),
            }

            # Store in data storage
            success = await self.data_storage.store_reading(
                mac_address,
                vehicle_id,
                device_type,
                reading_dict,
            )

            if success:
                # Log successful reading with key metrics at INFO level
                self.logger.info(
                    "Device %s: %.2fV, %.1fA, %.1f°C, %.1f%% SoC",
                    mac_address,
                    reading.voltage or 0.0,
                    reading.current or 0.0,
                    reading.temperature or 0.0,
                    reading.state_of_charge or 0.0,
                )
                # Update polling state to inactive (successful completion)
                await self.state_manager.update_polling_state(mac_address, active=False)
            else:
                self.logger.warning(
                    "Failed to store reading for device %s",
                    mac_address,
                )
                await self.state_manager.update_polling_state(
                    mac_address,
                    active=False,
                    error="Failed to store reading",
                )

        except Exception:
            self.logger.exception("Error polling single device %s", mac_address)
            await self.state_manager.update_polling_state(
                mac_address,
                active=False,
                error="Unexpected error during polling",
            )

    async def _wait_for_shutdown(self) -> None:
        """
        Wait for shutdown signal.

        This method waits for either a shutdown event or system signals
        to initiate graceful shutdown.
        """
        try:
            # Wait for shutdown event
            await self.shutdown_event.wait()
            self.logger.info("Shutdown signal received")
        except Exception:
            self.logger.exception("Error waiting for shutdown")

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        try:
            loop = asyncio.get_event_loop()

            def signal_handler() -> None:
                self.logger.info("Received shutdown signal")
                self.shutdown_event.set()

            # Handle SIGINT and SIGTERM
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, signal_handler)

            self.logger.debug("Signal handlers configured")
        except Exception:
            self.logger.exception("Error setting up signal handlers")

    def get_status(self) -> dict[str, Any]:
        """
        Get the current status of the core engine.

        Returns:
            Dictionary containing status information
        """
        state_summary = self.state_manager.get_summary()

        return {
            "running": self.running,
            "active_tasks": len(self.tasks),
            "active_devices": len(self.active_devices),
            "polling_tasks": len(self.polling_tasks),
            "storage_connected": self.data_storage.is_connected(),
            "discovered_devices": len(self.discovery_service.discovered_devices),
            "configured_devices": len(self.device_registry.get_configured_devices()),
            "vehicles": len(self.vehicle_registry.get_all_vehicles()),
            "state_manager": state_summary,
        }

    def add_event_handler(self, event_type: str, handler: EventHandler) -> None:
        """
        Add an event handler for system events.

        Args:
            event_type: Type of event to handle
            handler: Callback function to handle the event (can be sync or async)
        """
        if event_type in self.event_handlers:
            self.event_handlers[event_type].append(handler)
            self.logger.debug("Added event handler for %s", event_type)
        else:
            self.logger.warning("Unknown event type: %s", event_type)

    def remove_event_handler(self, event_type: str, handler: EventHandler) -> bool:
        """
        Remove an event handler.

        Args:
            event_type: Type of event to remove handler from
            handler: Handler function to remove

        Returns:
            True if handler was removed, False if not found
        """
        if event_type not in self.event_handlers:
            return False

        try:
            self.event_handlers[event_type].remove(handler)
            self.logger.debug("Removed event handler for %s", event_type)
        except ValueError:
            self.logger.warning("Event handler not found for %s", event_type)
            return False
        return True

    def get_event_handlers(
        self,
        event_type: str | None = None,
    ) -> (
        dict[str, list[Callable[[dict[str, Any]], None]]]
        | list[Callable[[dict[str, Any]], None]]
    ):
        """
        Get event handlers for a specific event type or all handlers.

        Args:
            event_type: Optional event type to get handlers for

        Returns:
            Dictionary of all handlers or list of handlers for specific event type
        """
        if event_type is None:
            return self.event_handlers.copy()
        return self.event_handlers.get(event_type, []).copy()

    async def _notify_event_handlers(
        self,
        event_type: str,
        event_data: dict[str, Any],
    ) -> None:
        """
        Notify all registered event handlers for a specific event type.

        Args:
            event_type: Type of event that occurred
            event_data: Event data to pass to handlers
        """
        if event_type not in self.event_handlers:
            return

        for handler in self.event_handlers[event_type]:
            await self._execute_event_handler(handler, event_data, event_type)

    async def _execute_event_handler(
        self,
        handler: EventHandler,
        event_data: dict[str, Any],
        event_type: str,
    ) -> None:
        """Execute a single event handler with error handling."""
        try:
            # Check if handler is async
            if asyncio.iscoroutinefunction(handler):
                await handler(event_data)
            else:
                handler(event_data)
        except Exception:
            self.logger.exception("Error in event handler for %s", event_type)

    async def _run_vehicle_association(self) -> None:
        """
        Run automatic vehicle association for discovered devices.

        This method periodically checks for unassociated devices and
        attempts to associate them with vehicles based on configuration rules.
        """
        try:
            self.logger.info("Starting vehicle association task")

            while self.running and not self.shutdown_event.is_set():
                try:
                    # Wait for the configured interval (default: 1 hour)
                    await asyncio.sleep(3600)

                    if not self.running or self.shutdown_event.is_set():
                        break

                    self.logger.debug("Running vehicle association check")

                    # Get all discovered devices without vehicle association
                    unassociated_devices = [
                        device
                        for device in self.device_registry.devices.values()
                        if device.get("status") == "discovered"
                        and device.get("vehicle_id") is None
                    ]

                    for device_info in unassociated_devices:
                        await self._associate_device_with_vehicle(device_info)

                except asyncio.CancelledError:
                    break
                except Exception:
                    self.logger.exception("Error during vehicle association")
                    # Wait before retrying
                    await asyncio.sleep(300)  # 5 minutes

        except Exception:
            self.logger.exception("Error in vehicle association task")

    async def _associate_device_with_vehicle(self, device_info: dict[str, Any]) -> None:
        """
        Associate a device with a vehicle based on configuration rules.

        Args:
            device_info: Device information dictionary
        """
        try:
            # Try to find a matching vehicle based on rules
            vehicle_id = self._find_matching_vehicle(device_info)

            if vehicle_id:
                # Associate device with existing vehicle
                await self._associate_device_with_existing_vehicle(
                    device_info,
                    vehicle_id,
                )
            else:
                # Create new vehicle and associate device
                await self._associate_device_with_new_vehicle(device_info)

        except Exception:
            self.logger.exception("Error associating device with vehicle")

    async def _associate_device_with_existing_vehicle(
        self,
        device_info: dict[str, Any],
        vehicle_id: str,
    ) -> None:
        """
        Associate a device with an existing vehicle.

        Args:
            device_info: Device information dictionary
            vehicle_id: ID of the existing vehicle
        """
        mac_address = device_info.get("mac_address")
        if not mac_address:
            self.logger.warning("Device info missing MAC address")
            return

        device_type = device_info.get("device_type", "unknown")
        friendly_name = device_info.get("friendly_name", f"Device_{mac_address}")

        # Associate device with vehicle
        success = await self.device_registry.configure_device(
            mac_address,
            device_type,
            friendly_name,
            vehicle_id=vehicle_id,
        )

        if success:
            # Update state manager
            await self.state_manager.set_vehicle_association(mac_address, vehicle_id)

            # Update vehicle device count
            await self._update_vehicle_device_count(vehicle_id)

            self.logger.info(
                "Associated device %s with vehicle %s",
                mac_address,
                vehicle_id,
            )

            # Notify event handlers
            await self._notify_event_handlers(
                "vehicle_associated",
                {
                    "mac_address": mac_address,
                    "vehicle_id": vehicle_id,
                    "device_type": device_type,
                },
            )
        else:
            self.logger.warning(
                "Failed to configure device %s with vehicle %s",
                mac_address,
                vehicle_id,
            )

    async def _associate_device_with_new_vehicle(
        self,
        device_info: dict[str, Any],
    ) -> None:
        """
        Create a new vehicle and associate a device with it.

        Args:
            device_info: Device information dictionary
        """
        mac_address = device_info.get("mac_address")
        if not mac_address:
            self.logger.warning("Device info missing MAC address")
            return

        device_type = device_info.get("device_type", "unknown")
        friendly_name = device_info.get("friendly_name", f"Device_{mac_address}")

        # Create a new vehicle for this device
        vehicle_name = self._generate_vehicle_name(device_info)
        vehicle_id = await self.vehicle_registry.create_vehicle(vehicle_name)

        # Associate device with new vehicle
        success = await self.device_registry.configure_device(
            mac_address,
            device_type,
            friendly_name,
            vehicle_id=vehicle_id,
        )

        if success:
            # Update state manager
            await self.state_manager.set_vehicle_association(mac_address, vehicle_id)

            # Update vehicle device count
            await self._update_vehicle_device_count(vehicle_id)

            self.logger.info(
                "Created new vehicle %s for device %s",
                vehicle_id,
                mac_address,
            )

            # Notify event handlers
            await self._notify_event_handlers(
                "vehicle_associated",
                {
                    "mac_address": mac_address,
                    "vehicle_id": vehicle_id,
                    "device_type": device_type,
                    "new_vehicle": True,
                },
            )
        else:
            self.logger.warning(
                "Failed to configure device %s with new vehicle %s",
                mac_address,
                vehicle_id,
            )

    def _get_vehicle_association_rules(self) -> dict[str, Any]:
        """
        Get vehicle association rules from configuration.

        Returns:
            Dictionary of vehicle association rules
        """
        try:
            system_config = self.config.get_config("system")
            return system_config.get("vehicle_association", {})
        except (KeyError, AttributeError):
            self.logger.warning("Failed to load vehicle association rules")
            return {}

    def _find_matching_vehicle(self, device_info: dict[str, Any]) -> str | None:
        """
        Find a matching vehicle for a device based on association rules.

        Args:
            device_info: Device information dictionary

        Returns:
            Vehicle ID if match found, None otherwise
        """
        try:
            rules = self._get_vehicle_association_rules()
            vehicles = rules.get("vehicles", [])

            for vehicle in vehicles:
                vehicle_id = vehicle.get("id") or vehicle.get("name", "")

                # Check if vehicle has association rules
                association_rules = vehicle.get("association_rules", {})
                if not association_rules:
                    continue

                # Check device type match
                device_type = device_info.get("device_type", "")
                if device_type and device_type != association_rules.get("device_type"):
                    continue

                # Check friendly name pattern match
                friendly_name = device_info.get("friendly_name", "")
                name_pattern = association_rules.get("name_pattern")
                if (
                    name_pattern
                    and friendly_name
                    and re.search(name_pattern, friendly_name)
                ):
                    return vehicle_id

                # Check MAC address pattern match
                mac_address = device_info.get("mac_address", "")
                mac_pattern = association_rules.get("mac_pattern")
                if mac_pattern and mac_address and re.search(mac_pattern, mac_address):
                    return vehicle_id

        except Exception:
            self.logger.exception("Error finding matching vehicle for device")

        return None

    def _generate_vehicle_name(self, device_info: dict[str, Any]) -> str:
        """
        Generate a vehicle name based on device information.

        Args:
            device_info: Device information dictionary

        Returns:
            Generated vehicle name
        """
        try:
            friendly_name = device_info.get("friendly_name", "")
            device_type = device_info.get("device_type", "")

            if friendly_name:
                # Remove common device type prefixes
                prefixes_to_remove = [
                    f"{device_type}_",
                    "Battery Monitor ",
                    "BM2_",
                    "BM6_",
                ]

                for prefix in prefixes_to_remove:
                    if friendly_name.startswith(prefix):
                        friendly_name = friendly_name[len(prefix) :]
                        break

                # If we have a meaningful name after prefix removal
                if friendly_name and not friendly_name.startswith("Device_"):
                    return f"{friendly_name} Vehicle"

            # Fallback to device type based naming
            if device_type:
                return f"{device_type} Vehicle"

        except (KeyError, AttributeError, TypeError):
            self.logger.warning("Error generating vehicle name, using fallback")

        return "Unknown Vehicle"

    async def _update_vehicle_device_count(self, vehicle_id: str) -> None:
        """
        Update the device count for a vehicle.

        Args:
            vehicle_id: ID of the vehicle to update
        """
        try:
            # Count devices associated with this vehicle
            device_count = 0
            for device in self.device_registry.devices.values():
                if device.get("vehicle_id") == vehicle_id:
                    device_count += 1

            # Update vehicle record
            vehicle = self.vehicle_registry.get_vehicle(vehicle_id)
            if vehicle:
                vehicle["device_count"] = device_count
                await self.vehicle_registry.save_vehicles()
        except Exception:
            self.logger.exception(
                "Error updating vehicle device count for %s",
                vehicle_id,
            )
