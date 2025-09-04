"""
MQTT service integration for Battery Hawk.

This module provides the main MQTT service that integrates with the core engine
and provides a complete MQTT interface for Battery Hawk.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from battery_hawk_driver.base.protocol import BatteryInfo, DeviceStatus

if TYPE_CHECKING:
    from battery_hawk.config.config_manager import ConfigManager
    from battery_hawk.core.engine import BatteryHawkCore

    from .topics import MQTTTopics

from .client import MQTTEventHandler, MQTTInterface, MQTTPublisher


class MQTTService:
    """
    Main MQTT service for Battery Hawk.

    This service integrates MQTT functionality with the core engine,
    providing automatic event handling, message publishing, and
    subscription management.
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        core_engine: BatteryHawkCore | None = None,
    ) -> None:
        """
        Initialize MQTT service.

        Args:
            config_manager: Configuration manager instance
            core_engine: Optional core engine instance for event integration
        """
        self.config_manager = config_manager
        self.core_engine = core_engine
        self.logger = logging.getLogger("battery_hawk.mqtt.service")

        # Initialize MQTT components
        self.mqtt_interface = MQTTInterface(config_manager)
        self.mqtt_publisher = MQTTPublisher(self.mqtt_interface)
        self.mqtt_event_handler = (
            MQTTEventHandler(
                core_engine=core_engine,
                mqtt_publisher=self.mqtt_publisher,
            )
            if core_engine
            else None
        )

        # Service state
        self.running = False
        self.tasks: list[asyncio.Task] = []

        # Get MQTT configuration
        self._mqtt_config = config_manager.get_config("system").get("mqtt", {})

    @property
    def enabled(self) -> bool:
        """Check if MQTT service is enabled."""
        return self._mqtt_config.get("enabled", False)

    @property
    def connected(self) -> bool:
        """Check if MQTT service is connected."""
        return self.mqtt_interface.connected

    @property
    def topics(self) -> MQTTTopics:
        """Get MQTT topics helper."""
        return self.mqtt_interface.topics

    async def start(self) -> None:
        """
        Start the MQTT service.

        This method:
        1. Connects to the MQTT broker
        2. Sets up event handlers with the core engine
        3. Starts background tasks
        4. Sets up subscriptions
        """
        if not self.enabled:
            self.logger.info("MQTT service is disabled")
            return

        if self.running:
            self.logger.warning("MQTT service is already running")
            return

        try:
            self.logger.info("Starting MQTT service")
            self.running = True

            # Connect to MQTT broker
            await self.mqtt_interface.connect()

            if self.connected:
                self.logger.info("MQTT service connected successfully")

                # Register event handlers with core engine
                if self.core_engine:
                    await self._register_core_event_handlers()

                # Set up subscriptions for incoming messages
                await self._setup_subscriptions()

                # Start background tasks
                await self._start_background_tasks()

                # Publish initial system status
                await self._publish_initial_status()

            else:
                self.logger.warning("MQTT service started but not connected")

        except Exception:
            self.logger.exception("Failed to start MQTT service")
            self.running = False
            raise

    async def stop(self) -> None:
        """
        Stop the MQTT service.

        This method:
        1. Cancels background tasks
        2. Unregisters event handlers
        3. Disconnects from MQTT broker
        """
        if not self.running:
            return

        self.logger.info("Stopping MQTT service")
        self.running = False

        try:
            # Cancel background tasks
            for task in self.tasks:
                if not task.done():
                    task.cancel()

            # Wait for tasks to complete
            if self.tasks:
                await asyncio.gather(*self.tasks, return_exceptions=True)

            # Unregister event handlers
            if self.core_engine:
                await self._unregister_core_event_handlers()

            # Disconnect from MQTT broker
            await self.mqtt_interface.disconnect()

            self.logger.info("MQTT service stopped")

        except Exception:
            self.logger.exception("Error stopping MQTT service")

    async def _register_core_event_handlers(self) -> None:
        """Register MQTT event handlers with the core engine."""
        if not self.core_engine or not self.mqtt_event_handler:
            return

        # Register handlers for core events
        event_mappings = {
            "device.discovered": self.mqtt_event_handler.on_device_discovered,
            "device.reading": self.mqtt_event_handler.on_device_reading,
            "device.status_change": self.mqtt_event_handler.on_device_status_change,
            "device.connection_change": self.mqtt_event_handler.on_device_connection_change,
            "vehicle.associated": self.mqtt_event_handler.on_vehicle_associated,
            "system.shutdown": self.mqtt_event_handler.on_system_shutdown,
            "system.status_change": self.mqtt_event_handler.on_system_status_change,
        }

        for event_name, handler in event_mappings.items():
            self.core_engine.add_event_handler(event_name, handler)
            self.logger.debug("Registered MQTT handler for event: %s", event_name)

    async def _unregister_core_event_handlers(self) -> None:
        """Unregister MQTT event handlers from the core engine."""
        if not self.core_engine or not self.mqtt_event_handler:
            return

        # Unregister all handlers
        self.mqtt_event_handler.unregister_all_handlers()
        self.logger.debug("Unregistered all MQTT event handlers")

    async def _setup_subscriptions(self) -> None:
        """Set up MQTT subscriptions for incoming messages."""
        try:
            # Subscribe to command topics (if needed in the future)
            # For now, Battery Hawk is primarily a publisher

            # Example: Subscribe to system commands
            # await self.mqtt_interface.subscribe(
            #     self.topics.system_commands(),
            #     self._handle_system_command
            # )

            self.logger.debug("MQTT subscriptions set up")

        except Exception:
            self.logger.exception("Failed to set up MQTT subscriptions")

    async def _start_background_tasks(self) -> None:
        """Start background tasks for the MQTT service."""
        # Start periodic status publishing
        self.tasks.append(asyncio.create_task(self._periodic_status_publisher()))

        # Start connection monitoring
        self.tasks.append(asyncio.create_task(self._connection_monitor()))

        self.logger.debug("Started MQTT background tasks")

    async def _publish_initial_status(self) -> None:
        """Publish initial system status."""
        try:
            status_data = {
                "status": "running",
                "mqtt_enabled": True,
                "mqtt_connected": self.connected,
                "service_version": "1.0.0",
                "components": {
                    "mqtt_interface": "active",
                    "mqtt_publisher": "active",
                    "mqtt_event_handler": "active",
                },
            }

            if self.core_engine:
                # Add core engine status if available
                status_data.update(
                    {
                        "core_engine": "active",
                        "total_devices": len(
                            self.core_engine.device_registry.get_all_devices(),
                        ),
                        "configured_devices": len(
                            self.core_engine.device_registry.get_configured_devices(),
                        ),
                    },
                )

            await self.mqtt_publisher.publish_system_status(status_data)
            self.logger.debug("Published initial system status")

        except Exception:
            self.logger.exception("Failed to publish initial status")

    async def _periodic_status_publisher(self) -> None:
        """Periodically publish system status."""
        status_interval = self._mqtt_config.get(
            "status_interval",
            300,
        )  # 5 minutes default

        while self.running:
            try:
                await asyncio.sleep(status_interval)

                if not self.running:
                    break

                # Publish periodic status update
                status_data = {
                    "status": "running",
                    "uptime": asyncio.get_event_loop().time(),
                    "mqtt_connected": self.connected,
                    "mqtt_stats": self.mqtt_interface.stats,
                }

                if self.core_engine:
                    # Add core engine metrics
                    status_data.update(
                        {
                            "total_devices": len(
                                self.core_engine.device_registry.get_all_devices(),
                            ),
                            "configured_devices": len(
                                self.core_engine.device_registry.get_configured_devices(),
                            ),
                            "active_polling_tasks": len(self.core_engine.polling_tasks),
                        },
                    )

                await self.mqtt_publisher.publish_system_status(status_data)
                self.logger.debug("Published periodic system status")

            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Error in periodic status publisher")
                # Continue running despite errors

    async def _connection_monitor(self) -> None:
        """Monitor MQTT connection and handle reconnections."""
        check_interval = 30  # Check every 30 seconds

        while self.running:
            try:
                await asyncio.sleep(check_interval)

                if not self.running:
                    break

                # Check connection status
                if not self.connected and self.enabled:
                    self.logger.warning("MQTT connection lost, attempting reconnection")
                    try:
                        await self.mqtt_interface.connect()
                        if self.connected:
                            self.logger.info("MQTT connection restored")
                    except Exception:
                        self.logger.exception("Failed to reconnect to MQTT")

            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Error in connection monitor")

    async def publish_device_reading(
        self,
        device_id: str,
        reading_data: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """
        Publish device reading data.

        Args:
            device_id: Device MAC address
            reading_data: Battery reading data
            **kwargs: Additional parameters for publishing
        """
        if not self.connected:
            self.logger.warning("Cannot publish device reading - MQTT not connected")
            return

        try:
            # Convert reading_data to BatteryInfo if needed

            if isinstance(reading_data, dict):
                reading = BatteryInfo(**reading_data)
            else:
                reading = reading_data

            await self.mqtt_publisher.publish_device_reading(
                device_id=device_id,
                reading=reading,
                **kwargs,
            )

        except Exception:
            self.logger.exception("Failed to publish device reading")

    async def publish_device_status(
        self,
        device_id: str,
        status_data: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """
        Publish device status data.

        Args:
            device_id: Device MAC address
            status_data: Device status data
            **kwargs: Additional parameters for publishing
        """
        if not self.connected:
            self.logger.warning("Cannot publish device status - MQTT not connected")
            return

        try:
            # Convert status_data to DeviceStatus if needed

            if isinstance(status_data, dict):
                status = DeviceStatus(**status_data)
            else:
                status = status_data

            await self.mqtt_publisher.publish_device_status(
                device_id=device_id,
                status=status,
                **kwargs,
            )

        except Exception:
            self.logger.exception("Failed to publish device status")

    async def publish_vehicle_summary(
        self,
        vehicle_id: str,
        summary_data: dict[str, Any],
    ) -> None:
        """
        Publish vehicle summary data.

        Args:
            vehicle_id: Vehicle identifier
            summary_data: Vehicle summary data
        """
        if not self.connected:
            self.logger.warning("Cannot publish vehicle summary - MQTT not connected")
            return

        try:
            await self.mqtt_publisher.publish_vehicle_summary(
                vehicle_id=vehicle_id,
                summary_data=summary_data,
            )

        except Exception:
            self.logger.exception("Failed to publish vehicle summary")

    def get_stats(self) -> dict[str, Any]:
        """Get MQTT service statistics."""
        return {
            "enabled": self.enabled,
            "running": self.running,
            "connected": self.connected,
            "mqtt_stats": self.mqtt_interface.stats if self.mqtt_interface else {},
            "background_tasks": len(self.tasks),
        }
