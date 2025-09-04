#!/usr/bin/env python3
"""
Example demonstrating MQTT resilience features.

This script shows how the MQTT client handles connection failures,
automatic reconnection, message queuing, and other resilience features.
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone

from battery_hawk.config.config_manager import ConfigManager
from battery_hawk.mqtt import MQTTInterface


async def demonstrate_basic_connection(
    mqtt_interface: MQTTInterface,
    logger: logging.Logger,
) -> None:
    """Demonstrate basic connection and message queuing."""
    logger.info("=== Testing Basic Connection ===")
    try:
        await mqtt_interface.connect()
        logger.info("✓ Connected successfully!")
    except Exception:
        logger.exception("✗ Connection failed")
        logger.info("This is expected if no MQTT broker is running")

    # Demonstrate message queuing when disconnected
    logger.info("\n=== Testing Message Queuing ===")
    messages_to_send = [
        {
            "topic": "test/device1",
            "data": {
                "voltage": 12.6,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
        {
            "topic": "test/device2",
            "data": {
                "voltage": 12.4,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
        {
            "topic": "test/system",
            "data": {
                "status": "running",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
    ]

    for msg in messages_to_send:
        await mqtt_interface.publish(msg["topic"], msg["data"])
        logger.info("Queued message for topic: %s", msg["topic"])

    # Show queue statistics
    stats = mqtt_interface.stats
    logger.info("Queue statistics:")
    logger.info("  - Messages queued: %d", stats["queue_size"])
    logger.info("  - Messages published: %d", stats["messages_published"])
    logger.info("  - Connection state: %s", stats["connection_state"])


async def demonstrate_reconnection_scenario(
    mqtt_interface: MQTTInterface,
    logger: logging.Logger,
) -> None:
    """Demonstrate reconnection scenario."""
    logger.info("\n=== Testing Reconnection Scenario ===")

    # Publish some messages first
    logger.info("Publishing messages before simulated disconnection...")
    for i in range(5):
        await mqtt_interface.publish(
            f"demo/message/{i}",
            {
                "message_id": i,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": f"Test message {i}",
            },
        )
        await asyncio.sleep(0.5)

    logger.info("Published 5 messages successfully")

    # Simulate connection loss by forcing disconnect
    logger.info("Simulating connection loss...")
    try:
        await mqtt_interface.disconnect()
        logger.info("Disconnected to simulate connection loss")
    except OSError:
        logger.info("Disconnect failed (expected if already disconnected)")

    # Try to publish more messages (should be queued)
    logger.info("Publishing messages while disconnected (will be queued)...")
    for i in range(5, 10):
        await mqtt_interface.publish(
            f"demo/message/{i}",
            {
                "message_id": i,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": f"Queued message {i}",
            },
        )

    stats = mqtt_interface.stats
    logger.info("Messages queued while disconnected: %d", stats["queue_size"])

    # Attempt to reconnect
    logger.info("Attempting to reconnect...")
    try:
        await mqtt_interface.connect()
        logger.info("✓ Reconnected successfully!")

        # Wait for queued messages to be sent
        await asyncio.sleep(2)

        final_stats = mqtt_interface.stats
        logger.info("Final queue size: %d", final_stats["queue_size"])
        logger.info(
            "Total messages published: %d",
            final_stats["messages_published"],
        )

    except OSError:
        logger.info("Reconnection failed (expected if no broker)")


async def main() -> None:
    """Demonstrate MQTT resilience features."""
    # Set up logging to see resilience in action
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    # Initialize configuration manager with resilience settings
    config_manager = ConfigManager()

    # Override MQTT config for demonstration
    mqtt_config = config_manager.get_config("system")["mqtt"]
    mqtt_config.update(
        {
            "enabled": True,
            "broker": "localhost",  # Change to your MQTT broker
            "port": 1883,
            "max_retries": 5,
            "initial_retry_delay": 1.0,
            "max_retry_delay": 30.0,
            "backoff_multiplier": 2.0,
            "connection_timeout": 10.0,
            "health_check_interval": 30.0,
            "message_queue_size": 100,
            "message_retry_limit": 3,
        },
    )

    # Create MQTT interface
    mqtt_interface = MQTTInterface(config_manager)

    logger.info("Starting MQTT resilience demonstration")
    logger.info(
        "Configuration: %s",
        {
            "broker": mqtt_config["broker"],
            "max_retries": mqtt_config["max_retries"],
            "queue_size": mqtt_config["message_queue_size"],
        },
    )

    try:
        # Demonstrate basic connection and message queuing
        await demonstrate_basic_connection(mqtt_interface, logger)

        # Demonstrate reconnection scenario
        await demonstrate_reconnection_scenario(mqtt_interface, logger)

        # Show final statistics
        final_stats = mqtt_interface.stats
        logger.info("\n=== Final Statistics ===")
        logger.info(
            "  - Total messages published: %d",
            final_stats.get("messages_published", 0),
        )
        logger.info("  - Current queue size: %d", final_stats.get("queue_size", 0))

    except Exception:
        logger.exception("Error during demonstration")
    finally:
        # Disconnect gracefully
        logger.info("Disconnecting gracefully...")
        await mqtt_interface.disconnect()
        logger.info("✓ Disconnected successfully")

    logger.info("\n=== Resilience Features Demonstrated ===")
    logger.info("✓ Automatic connection retry with exponential backoff")
    logger.info("✓ Message queuing for failed deliveries")
    logger.info("✓ Connection state tracking and monitoring")
    logger.info("✓ Background health checks")
    logger.info("✓ Graceful shutdown with resource cleanup")
    logger.info("✓ Configurable retry parameters")
    logger.info("✓ Message retry limits and error handling")


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    try:
        # Run main demonstration
        asyncio.run(main())

        logger.info("\n%s", "=" * 60)
        logger.info("To see full resilience features in action:")
        logger.info("1. Start an MQTT broker (e.g., mosquitto)")
        logger.info("2. Run this script")
        logger.info("3. Stop the broker while script is running")
        logger.info("4. Restart the broker to see reconnection")
        logger.info("%s", "=" * 60)

        # Optionally run reconnection scenario
        # asyncio.run(demonstrate_reconnection_scenario())

    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception:
        logger.exception("Demo failed")
        sys.exit(1)
