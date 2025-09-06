"""
CLI commands for MQTT functionality.

This module provides command-line interface commands for managing
MQTT connectivity, testing, and monitoring.
"""

import asyncio
import json
import logging

from battery_hawk.config.config_manager import ConfigManager
from battery_hawk.mqtt import MQTTInterface, MQTTService


async def mqtt_status(config_manager: ConfigManager) -> int:
    """
    Show MQTT connection status and configuration.

    Args:
        config_manager: Configuration manager instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Get MQTT configuration
        mqtt_config = config_manager.get_config("system").get("mqtt", {})

        logger = logging.getLogger("battery_hawk.mqtt_status")

        logger.info("MQTT Configuration:")
        logger.info("  Enabled: %s", mqtt_config.get("enabled", False))
        logger.info("  Broker: %s", mqtt_config.get("broker", "not configured"))
        logger.info("  Port: %s", mqtt_config.get("port", 1883))
        logger.info(
            "  Topic Prefix: %s",
            mqtt_config.get("topic_prefix", "battery_hawk"),
        )
        logger.info("  QoS: %s", mqtt_config.get("qos", 1))
        logger.info("  TLS: %s", mqtt_config.get("tls", False))

        if not mqtt_config.get("enabled", False):
            logger.warning(
                "MQTT is disabled. Enable it in configuration to use MQTT features.",
            )
            return 0

        # Test connection
        logger.info("Testing MQTT connection...")
        mqtt_interface = MQTTInterface(config_manager)

        try:
            await mqtt_interface.connect()

            if mqtt_interface.connected:
                logger.info("✓ Successfully connected to MQTT broker")

                # Show connection stats
                stats = mqtt_interface.stats
                logger.info("  Connection State: %s", stats["connection_state"])
                logger.info("  Total Connections: %s", stats["total_connections"])
                logger.info("  Messages Published: %s", stats["messages_published"])
                logger.info("  Messages Queued: %s", stats["messages_queued"])
                logger.info("  Queue Size: %s", stats["queue_size"])

            else:
                logger.error("✗ Failed to connect to MQTT broker")
                return 1

        except Exception:
            logger.exception("✗ Connection failed")
            return 1
        else:
            return 0
        finally:
            await mqtt_interface.disconnect()

    except Exception:
        logger = logging.getLogger("battery_hawk.mqtt_status")
        logger.exception("Error checking MQTT status")
        return 1


async def mqtt_test_publish(
    config_manager: ConfigManager,
    topic: str,
    message: str,
    *,
    retain: bool = False,
) -> int:
    """
    Test MQTT publishing with a custom message.

    Args:
        config_manager: Configuration manager instance
        topic: Topic to publish to (without prefix)
        message: Message to publish (JSON string or plain text)
        retain: Whether to retain the message

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        mqtt_interface = MQTTInterface(config_manager)

        # Parse message as JSON if possible
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            payload = message

        logger = logging.getLogger("battery_hawk.mqtt_publish")

        logger.info("Publishing to topic: %s/%s", mqtt_interface.topics.prefix, topic)
        logger.info("Message: %s", message)
        logger.info("Retain: %s", retain)

        await mqtt_interface.connect()

        if not mqtt_interface.connected:
            logger.error("✗ Failed to connect to MQTT broker")
            return 1

        await mqtt_interface.publish(topic, payload, retain=retain)
        logger.info("✓ Message published successfully")

        await mqtt_interface.disconnect()

    except Exception:
        logger = logging.getLogger("battery_hawk.mqtt_publish")
        logger.exception("Error publishing message")
        return 1
    else:
        return 0


async def mqtt_list_topics(config_manager: ConfigManager) -> int:
    """
    List all available MQTT topics and their patterns.

    Args:
        config_manager: Configuration manager instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        mqtt_interface = MQTTInterface(config_manager)
        topics = mqtt_interface.topics

        logger = logging.getLogger("battery_hawk.mqtt_topics")

        logger.info("MQTT Topics (prefix: %s)", topics.prefix)
        logger.info("=" * 50)

        # Get all topic patterns
        patterns = topics.list_all_patterns()

        for topic_type, info in patterns.items():
            logger.info("%s:", topic_type.replace("_", " ").title())
            logger.info("  Pattern: %s", info.pattern)
            logger.info("  Description: %s", info.description)
            logger.info("  QoS: %s", info.qos)
            logger.info("  Retain: %s", info.retain)
            logger.info("  Example: %s", info.example)

        logger.info("Wildcard Patterns:")
        logger.info("  All device readings: %s", topics.all_device_readings())
        logger.info("  All device status: %s", topics.all_device_status())
        logger.info("  All vehicle summaries: %s", topics.all_vehicle_summaries())
        logger.info("  All topics: %s", topics.all_topics_recursive())

        logger.info("Subscription Topics:")
        subscription_topics = topics.get_subscription_topics()
        for topic in subscription_topics:
            logger.info("  %s", topic)

    except Exception:
        logger = logging.getLogger("battery_hawk.mqtt_topics")
        logger.exception("Error listing topics")
        return 1
    else:
        return 0


async def mqtt_monitor(config_manager: ConfigManager, duration: int = 60) -> int:
    """
    Monitor MQTT messages for a specified duration.

    Args:
        config_manager: Configuration manager instance
        duration: Duration to monitor in seconds

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        mqtt_interface = MQTTInterface(config_manager)

        logger = logging.getLogger("battery_hawk.mqtt_monitor")

        logger.info("Monitoring MQTT messages for %d seconds...", duration)
        logger.info("Press Ctrl+C to stop early")

        await mqtt_interface.connect()

        if not mqtt_interface.connected:
            logger.error("✗ Failed to connect to MQTT broker")
            return 1

        # Message counter
        message_count = 0

        def message_handler(topic: str, payload: str) -> None:
            nonlocal message_count
            message_count += 1
            logger.info("[%d] %s: %s", message_count, topic, payload)

        # Subscribe to all Battery Hawk topics
        await mqtt_interface.subscribe(
            mqtt_interface.topics.all_topics_recursive().replace(
                f"{mqtt_interface.topics.prefix}/",
                "",
            ),
            message_handler,
        )

        logger.info("✓ Subscribed to %s", mqtt_interface.topics.all_topics_recursive())
        logger.info("Waiting for messages...")

        # Monitor for specified duration
        try:
            await asyncio.sleep(duration)
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")

        logger.info("Received %d messages", message_count)
        await mqtt_interface.disconnect()

    except Exception:
        logger = logging.getLogger("battery_hawk.mqtt_monitor")
        logger.exception("Error monitoring MQTT")
        return 1
    else:
        return 0


async def mqtt_service_test(config_manager: ConfigManager) -> int:
    """
    Test the complete MQTT service functionality.

    Args:
        config_manager: Configuration manager instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        logger = logging.getLogger("battery_hawk.mqtt_test")
        logger.info("Testing MQTT service...")

        # Create and start MQTT service
        mqtt_service = MQTTService(config_manager)

        if not mqtt_service.enabled:
            logger.error("MQTT service is disabled in configuration")
            return 1

        await mqtt_service.start()

        if not mqtt_service.connected:
            logger.error("✗ MQTT service failed to connect")
            return 1

        logger.info("✓ MQTT service started successfully")

        # Test publishing various message types
        logger.info("Testing message publishing...")

        # Test device reading
        test_reading_data = {
            "voltage": 12.6,
            "current": 2.5,
            "temperature": 25.0,
            "state_of_charge": 85.0,
            "capacity": 100.0,
            "cycles": 150,
        }

        await mqtt_service.publish_device_reading(
            device_id="AA:BB:CC:DD:EE:FF",
            reading_data=test_reading_data,
            vehicle_id="test_vehicle",
            device_type="BM6",
        )
        logger.info("✓ Published test device reading")

        # Test device status
        test_status_data = {
            "connected": True,
            "protocol_version": "1.0",
            "last_command": "read_data",
        }

        await mqtt_service.publish_device_status(
            device_id="AA:BB:CC:DD:EE:FF",
            status_data=test_status_data,
            device_type="BM6",
        )
        logger.info("✓ Published test device status")

        # Test vehicle summary
        test_summary_data = {
            "total_devices": 1,
            "connected_devices": 1,
            "total_voltage": 12.6,
            "average_soc": 85.0,
            "devices": [{"device_id": "AA:BB:CC:DD:EE:FF", "status": "connected"}],
        }

        await mqtt_service.publish_vehicle_summary(
            vehicle_id="test_vehicle",
            summary_data=test_summary_data,
        )
        logger.info("✓ Published test vehicle summary")

        # Show service stats
        stats = mqtt_service.get_stats()
        logger.info("Service Statistics:")
        logger.info("  Enabled: %s", stats["enabled"])
        logger.info("  Running: %s", stats["running"])
        logger.info("  Connected: %s", stats["connected"])
        logger.info("  Background Tasks: %s", stats["background_tasks"])

        # Stop service
        await mqtt_service.stop()
        logger.info("✓ MQTT service stopped successfully")

    except Exception:
        logger = logging.getLogger("battery_hawk.mqtt_test")
        logger.exception("Error testing MQTT service")
        return 1
    else:
        return 0


def setup_mqtt_logging() -> None:
    """Set up logging for MQTT CLI commands with timestamps."""
    # Enhanced format with explicit timestamp format
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Clear any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Set up console handler with timestamp formatter
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.INFO)

    # Reduce noise from external libraries
    logging.getLogger("aiomqtt").setLevel(logging.WARNING)
    logging.getLogger("bleak").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Log the configuration
    logger = logging.getLogger("battery_hawk.mqtt_cli")
    logger.info("MQTT CLI logging configured with timestamps at INFO level")
