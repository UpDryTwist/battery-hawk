#!/usr/bin/env python3
"""
Example demonstrating MQTT resilience features.

This script shows how the MQTT client handles connection failures,
automatic reconnection, message queuing, and other resilience features.
"""

import asyncio
import logging
from datetime import datetime

from battery_hawk.config.config_manager import ConfigManager
from battery_hawk.mqtt import ConnectionState, MQTTInterface


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
        # 1. Demonstrate connection with retry
        logger.info("=== Testing Connection with Retry ===")
        try:
            await mqtt_interface.connect()
            logger.info("✓ Connected successfully!")
        except Exception as e:
            logger.error("✗ Connection failed: %s", e)
            logger.info("This is expected if no MQTT broker is running")

        # 2. Demonstrate message queuing when disconnected
        logger.info("\n=== Testing Message Queuing ===")

        # Publish messages while potentially disconnected
        messages_to_send = [
            {
                "topic": "test/device1",
                "data": {"voltage": 12.6, "timestamp": datetime.now().isoformat()},
            },
            {
                "topic": "test/device2",
                "data": {"voltage": 12.4, "timestamp": datetime.now().isoformat()},
            },
            {
                "topic": "test/system",
                "data": {"status": "running", "timestamp": datetime.now().isoformat()},
            },
        ]

        for msg in messages_to_send:
            await mqtt_interface.publish(msg["topic"], msg["data"])
            logger.info("Queued message to %s", msg["topic"])

        # Show queue status
        stats = mqtt_interface.stats
        logger.info(
            "Queue status: %d messages queued, %d published",
            stats["messages_queued"],
            stats["messages_published"],
        )

        # 3. Demonstrate connection state monitoring
        logger.info("\n=== Connection State Monitoring ===")
        logger.info(
            "Current connection state: %s",
            mqtt_interface.connection_state.value,
        )
        logger.info("Connected: %s", mqtt_interface.connected)

        # Show detailed statistics
        logger.info("Statistics: %s", mqtt_interface.stats)

        # 4. Simulate connection recovery (if broker becomes available)
        if mqtt_interface.connection_state != ConnectionState.CONNECTED:
            logger.info("\n=== Simulating Connection Recovery ===")
            logger.info(
                "If MQTT broker becomes available, messages will be automatically published",
            )
            logger.info("The client will:")
            logger.info("  - Automatically retry connection with exponential backoff")
            logger.info("  - Process queued messages when connection is restored")
            logger.info("  - Monitor connection health with periodic checks")

        # 5. Demonstrate graceful shutdown
        logger.info("\n=== Testing Graceful Shutdown ===")

        # Wait a bit to show background tasks working
        await asyncio.sleep(2)

        # Show final statistics
        final_stats = mqtt_interface.stats
        logger.info("Final statistics:")
        logger.info("  - Total connections: %d", final_stats["total_connections"])
        logger.info("  - Total disconnections: %d", final_stats["total_disconnections"])
        logger.info("  - Total reconnections: %d", final_stats["total_reconnections"])
        logger.info("  - Messages published: %d", final_stats["messages_published"])
        logger.info("  - Messages queued: %d", final_stats["messages_queued"])
        logger.info("  - Messages failed: %d", final_stats["messages_failed"])
        logger.info("  - Current queue size: %d", final_stats["queue_size"])

    except Exception as e:
        logger.error("Error during demonstration: %s", e)
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


async def demonstrate_reconnection_scenario() -> None:
    """Demonstrate a realistic reconnection scenario."""
    logger = logging.getLogger("reconnection_demo")

    # Create a second interface for reconnection demo
    config_manager = ConfigManager()
    mqtt_interface = MQTTInterface(config_manager)

    logger.info("\n=== Reconnection Scenario Demo ===")

    try:
        # Try to connect
        await mqtt_interface.connect()

        # Publish some messages
        for i in range(5):
            await mqtt_interface.publish(
                f"demo/message/{i}",
                {
                    "message_id": i,
                    "timestamp": datetime.now().isoformat(),
                    "data": f"Test message {i}",
                },
            )
            await asyncio.sleep(0.5)

        logger.info("Published 5 messages successfully")

        # Simulate connection loss by forcing disconnect
        logger.info("Simulating connection loss...")
        if mqtt_interface._client:
            try:
                await mqtt_interface._client.__aexit__(None, None, None)
                mqtt_interface._client = None
                mqtt_interface._connection_state = ConnectionState.DISCONNECTED
            except Exception:
                pass

        # Try to publish more messages (should be queued)
        logger.info("Publishing messages while disconnected (will be queued)...")
        for i in range(5, 10):
            await mqtt_interface.publish(
                f"demo/message/{i}",
                {
                    "message_id": i,
                    "timestamp": datetime.now().isoformat(),
                    "data": f"Queued message {i}",
                },
            )

        stats = mqtt_interface.stats
        logger.info("Messages queued during disconnection: %d", stats["queue_size"])

        # Attempt reconnection
        logger.info("Attempting reconnection...")
        try:
            await mqtt_interface.connect()
            logger.info("✓ Reconnected successfully!")

            # Wait for queued messages to be processed
            await asyncio.sleep(2)

            final_stats = mqtt_interface.stats
            logger.info("Final queue size: %d", final_stats["queue_size"])
            logger.info(
                "Total messages published: %d",
                final_stats["messages_published"],
            )

        except Exception as e:
            logger.info("Reconnection failed (expected if no broker): %s", e)

    except Exception as e:
        logger.info("Demo failed (expected if no broker): %s", e)

    finally:
        await mqtt_interface.disconnect()


if __name__ == "__main__":
    try:
        # Run main demonstration
        asyncio.run(main())

        print("\n" + "=" * 60)
        print("To see full resilience features in action:")
        print("1. Start an MQTT broker (e.g., mosquitto)")
        print("2. Run this script")
        print("3. Stop the broker while script is running")
        print("4. Restart the broker to see reconnection")
        print("=" * 60)

        # Optionally run reconnection scenario
        # asyncio.run(demonstrate_reconnection_scenario())

    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"Demo failed: {e}")
        exit(1)
