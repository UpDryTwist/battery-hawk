"""
CLI commands for MQTT functionality.

This module provides command-line interface commands for managing
MQTT connectivity, testing, and monitoring.
"""

import asyncio
import json
import logging
import sys
from typing import Any, Dict

from battery_hawk.config.config_manager import ConfigManager
from battery_hawk.mqtt import MQTTInterface, MQTTService, MQTTTopics


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
        
        print("MQTT Configuration:")
        print(f"  Enabled: {mqtt_config.get('enabled', False)}")
        print(f"  Broker: {mqtt_config.get('broker', 'not configured')}")
        print(f"  Port: {mqtt_config.get('port', 1883)}")
        print(f"  Topic Prefix: {mqtt_config.get('topic_prefix', 'battery_hawk')}")
        print(f"  QoS: {mqtt_config.get('qos', 1)}")
        print(f"  TLS: {mqtt_config.get('tls', False)}")
        
        if not mqtt_config.get("enabled", False):
            print("\nMQTT is disabled. Enable it in configuration to use MQTT features.")
            return 0
        
        # Test connection
        print("\nTesting MQTT connection...")
        mqtt_interface = MQTTInterface(config_manager)
        
        try:
            await mqtt_interface.connect()
            
            if mqtt_interface.connected:
                print("✓ Successfully connected to MQTT broker")
                
                # Show connection stats
                stats = mqtt_interface.stats
                print(f"  Connection State: {stats['connection_state']}")
                print(f"  Total Connections: {stats['total_connections']}")
                print(f"  Messages Published: {stats['messages_published']}")
                print(f"  Messages Queued: {stats['messages_queued']}")
                print(f"  Queue Size: {stats['queue_size']}")
                
            else:
                print("✗ Failed to connect to MQTT broker")
                return 1
                
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return 1
        finally:
            await mqtt_interface.disconnect()
        
        return 0
        
    except Exception as e:
        print(f"Error checking MQTT status: {e}", file=sys.stderr)
        return 1


async def mqtt_test_publish(
    config_manager: ConfigManager,
    topic: str,
    message: str,
    retain: bool = False
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
        
        print(f"Publishing to topic: {mqtt_interface.topics.prefix}/{topic}")
        print(f"Message: {message}")
        print(f"Retain: {retain}")
        
        await mqtt_interface.connect()
        
        if not mqtt_interface.connected:
            print("✗ Failed to connect to MQTT broker")
            return 1
        
        await mqtt_interface.publish(topic, payload, retain=retain)
        print("✓ Message published successfully")
        
        await mqtt_interface.disconnect()
        return 0
        
    except Exception as e:
        print(f"Error publishing message: {e}", file=sys.stderr)
        return 1


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
        
        print(f"MQTT Topics (prefix: {topics.prefix})")
        print("=" * 50)
        
        # Get all topic patterns
        patterns = topics.list_all_patterns()
        
        for topic_type, info in patterns.items():
            print(f"\n{topic_type.replace('_', ' ').title()}:")
            print(f"  Pattern: {info.pattern}")
            print(f"  Description: {info.description}")
            print(f"  QoS: {info.qos}")
            print(f"  Retain: {info.retain}")
            print(f"  Example: {info.example}")
        
        print("\nWildcard Patterns:")
        print(f"  All device readings: {topics.all_device_readings()}")
        print(f"  All device status: {topics.all_device_status()}")
        print(f"  All vehicle summaries: {topics.all_vehicle_summaries()}")
        print(f"  All topics: {topics.all_topics_recursive()}")
        
        print("\nSubscription Topics:")
        subscription_topics = topics.get_subscription_topics()
        for topic in subscription_topics:
            print(f"  {topic}")
        
        return 0
        
    except Exception as e:
        print(f"Error listing topics: {e}", file=sys.stderr)
        return 1


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
        
        print(f"Monitoring MQTT messages for {duration} seconds...")
        print("Press Ctrl+C to stop early")
        
        await mqtt_interface.connect()
        
        if not mqtt_interface.connected:
            print("✗ Failed to connect to MQTT broker")
            return 1
        
        # Message counter
        message_count = 0
        
        def message_handler(topic: str, payload: str) -> None:
            nonlocal message_count
            message_count += 1
            print(f"[{message_count}] {topic}: {payload}")
        
        # Subscribe to all Battery Hawk topics
        await mqtt_interface.subscribe(
            mqtt_interface.topics.all_topics_recursive().replace(f"{mqtt_interface.topics.prefix}/", ""),
            message_handler
        )
        
        print(f"✓ Subscribed to {mqtt_interface.topics.all_topics_recursive()}")
        print("Waiting for messages...\n")
        
        # Monitor for specified duration
        try:
            await asyncio.sleep(duration)
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
        
        print(f"\nReceived {message_count} messages")
        await mqtt_interface.disconnect()
        return 0
        
    except Exception as e:
        print(f"Error monitoring MQTT: {e}", file=sys.stderr)
        return 1


async def mqtt_service_test(config_manager: ConfigManager) -> int:
    """
    Test the complete MQTT service functionality.
    
    Args:
        config_manager: Configuration manager instance
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        print("Testing MQTT service...")
        
        # Create and start MQTT service
        mqtt_service = MQTTService(config_manager)
        
        if not mqtt_service.enabled:
            print("MQTT service is disabled in configuration")
            return 1
        
        await mqtt_service.start()
        
        if not mqtt_service.connected:
            print("✗ MQTT service failed to connect")
            return 1
        
        print("✓ MQTT service started successfully")
        
        # Test publishing various message types
        print("\nTesting message publishing...")
        
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
            device_type="BM6"
        )
        print("✓ Published test device reading")
        
        # Test device status
        test_status_data = {
            "connected": True,
            "protocol_version": "1.0",
            "last_command": "read_data",
        }
        
        await mqtt_service.publish_device_status(
            device_id="AA:BB:CC:DD:EE:FF",
            status_data=test_status_data,
            device_type="BM6"
        )
        print("✓ Published test device status")
        
        # Test vehicle summary
        test_summary_data = {
            "total_devices": 1,
            "connected_devices": 1,
            "total_voltage": 12.6,
            "average_soc": 85.0,
            "devices": [
                {"device_id": "AA:BB:CC:DD:EE:FF", "status": "connected"}
            ]
        }
        
        await mqtt_service.publish_vehicle_summary(
            vehicle_id="test_vehicle",
            summary_data=test_summary_data
        )
        print("✓ Published test vehicle summary")
        
        # Show service stats
        stats = mqtt_service.get_stats()
        print(f"\nService Statistics:")
        print(f"  Enabled: {stats['enabled']}")
        print(f"  Running: {stats['running']}")
        print(f"  Connected: {stats['connected']}")
        print(f"  Background Tasks: {stats['background_tasks']}")
        
        # Stop service
        await mqtt_service.stop()
        print("✓ MQTT service stopped successfully")
        
        return 0
        
    except Exception as e:
        print(f"Error testing MQTT service: {e}", file=sys.stderr)
        return 1


def setup_mqtt_logging() -> None:
    """Set up logging for MQTT CLI commands."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Reduce noise from MQTT library
    logging.getLogger("aiomqtt").setLevel(logging.WARNING)
