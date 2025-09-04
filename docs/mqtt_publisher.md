# MQTT Interface Documentation

The Battery Hawk MQTT interface provides comprehensive messaging capabilities for real-time battery monitoring data, device status updates, and system integration. This documentation covers the complete MQTT implementation including topics, publishing, resilience, and integration.

## Overview

The Battery Hawk MQTT interface consists of several components working together:

- **MQTTTopics**: Topic structure and helper functions according to PRD specification
- **MQTTInterface**: Low-level MQTT client with resilience and reconnection
- **MQTTPublisher**: High-level publishing methods for Battery Hawk data types
- **MQTTEventHandler**: Event-driven publishing integration with core engine
- **MQTTService**: Complete service integration for production use

## Topic Structure (PRD Compliant)

Battery Hawk uses a structured topic hierarchy as defined in the Product Requirements Document:

```
battery_hawk/device/{mac}/reading     # Device reading updates
battery_hawk/device/{mac}/status      # Device connection status
battery_hawk/vehicle/{id}/summary     # Vehicle summary data
battery_hawk/system/status            # System status updates
battery_hawk/discovery/found          # New device discovered
```

### Topic Features

- **Configurable Prefix**: Default `battery_hawk`, customizable per deployment
- **Wildcard Support**: Subscription patterns for monitoring multiple devices
- **QoS Levels**: Appropriate QoS per message type (1 for data, 2 for critical)
- **Retention**: Status and summary messages retained, readings are not
- **Validation**: MAC address and vehicle ID format validation

## Usage

### Basic Setup

```python
from battery_hawk.config.config_manager import ConfigManager
from battery_hawk.mqtt import MQTTInterface, MQTTPublisher

# Initialize components
config_manager = ConfigManager()
mqtt_interface = MQTTInterface(config_manager)
publisher = MQTTPublisher(mqtt_interface)

# Connect to MQTT broker
await mqtt_interface.connect()
```

### Publishing Device Readings

Device readings contain battery sensor data from individual monitoring devices:

```python
from battery_hawk_driver.base.protocol import BatteryInfo

reading = BatteryInfo(
    voltage=12.6,
    current=2.5,
    temperature=25.0,
    state_of_charge=85.0,
    capacity=100.0,
    cycles=150,
)

await publisher.publish_device_reading(
    device_id="AA:BB:CC:DD:EE:FF",
    reading=reading,
    vehicle_id="my_vehicle",  # Optional
    device_type="BM2",  # Optional
)
```

**Topic Structure**: `devices/{device_id}/readings`
**QoS Level**: 1 (important but not critical)
**Retention**: False (time-series data)

### Publishing Device Status

Device status messages indicate connection state and operational status:

```python
from battery_hawk_driver.base.protocol import DeviceStatus

# Connected status
status = DeviceStatus(
    connected=True,
    protocol_version="1.0",
    last_command="read_data",
)

await publisher.publish_device_status(
    device_id="AA:BB:CC:DD:EE:FF",
    status=status,
    device_type="BM2",  # Optional
)

# Disconnected with error
error_status = DeviceStatus(
    connected=False,
    error_code=1001,
    error_message="Connection timeout",
)

await publisher.publish_device_status(
    device_id="AA:BB:CC:DD:EE:FF",
    status=error_status,
)
```

**Topic Structure**: `devices/{device_id}/status`
**QoS Level**: 1 (important)
**Retention**: True (last known state)

### Publishing Vehicle Summary

Vehicle summaries contain aggregated data for vehicles with multiple devices:

```python
summary_data = {
    "total_devices": 3,
    "connected_devices": 2,
    "average_voltage": 12.4,
    "total_capacity": 300.0,
    "overall_health": "good",
    "devices": [
        {"id": "device1", "status": "connected", "voltage": 12.6},
        {"id": "device2", "status": "connected", "voltage": 12.2},
        {"id": "device3", "status": "disconnected"},
    ],
}

await publisher.publish_vehicle_summary("my_vehicle", summary_data)
```

**Topic Structure**: `vehicles/{vehicle_id}/summary`
**QoS Level**: 1 (important)
**Retention**: True (last known state)

### Publishing System Status

System status messages contain overall system health and operational information:

```python
status_data = {
    "core": {
        "running": True,
        "uptime_seconds": 3600,
        "version": "1.0.0",
    },
    "storage": {
        "influxdb_connected": True,
        "disk_usage_percent": 45.2,
    },
    "components": {
        "mqtt": "connected",
        "bluetooth": "active",
        "api": "running",
    },
}

await publisher.publish_system_status(status_data)
```

**Topic Structure**: `system/status`
**QoS Level**: 2 (critical)
**Retention**: True (last known state)

## Message Structure

### Device Reading Message

```json
{
    "device_id": "AA:BB:CC:DD:EE:FF",
    "timestamp": "2024-01-15T10:30:00.000Z",
    "voltage": 12.6,
    "current": 2.5,
    "temperature": 25.0,
    "state_of_charge": 85.0,
    "capacity": 100.0,
    "cycles": 150,
    "power": 31.5,
    "vehicle_id": "my_vehicle",
    "device_type": "BM2",
    "extra": {
        "device_type": "BM2",
        "raw_data": {...}
    }
}
```

### Device Status Message

```json
{
    "device_id": "AA:BB:CC:DD:EE:FF",
    "timestamp": "2024-01-15T10:30:00.000Z",
    "connected": true,
    "protocol_version": "1.0",
    "last_command": "read_data",
    "device_type": "BM2",
    "extra": {
        "signal_strength": -45
    }
}
```

### Vehicle Summary Message

```json
{
    "vehicle_id": "my_vehicle",
    "timestamp": "2024-01-15T10:30:00.000Z",
    "total_devices": 3,
    "connected_devices": 2,
    "average_voltage": 12.4,
    "total_capacity": 300.0,
    "overall_health": "good",
    "devices": [...]
}
```

### System Status Message

```json
{
    "timestamp": "2024-01-15T10:30:00.000Z",
    "core": {
        "running": true,
        "uptime_seconds": 3600,
        "version": "1.0.0"
    },
    "storage": {
        "influxdb_connected": true,
        "disk_usage_percent": 45.2
    },
    "components": {
        "mqtt": "connected",
        "bluetooth": "active",
        "api": "running"
    }
}
```

## QoS and Retention Strategy

| Message Type | QoS Level | Retention | Rationale |
|--------------|-----------|-----------|-----------|
| Device Readings | 1 | False | Important but time-series data |
| Device Status | 1 | True | Important state information |
| Vehicle Summary | 1 | True | Important aggregated state |
| System Status | 2 | True | Critical system information |

## Error Handling

All publishing methods include comprehensive error handling:

- **Connection Errors**: Automatically detected and reported
- **Serialization Errors**: JSON serialization failures are caught
- **Timeout Errors**: Network timeouts are handled gracefully
- **Logging**: All errors are logged with appropriate context

```python
try:
    await publisher.publish_device_reading(device_id, reading)
except MQTTConnectionError as e:
    logger.error("MQTT connection failed: %s", e)
except ValueError as e:
    logger.error("Data serialization failed: %s", e)
```

## Configuration

The publisher uses the existing MQTT configuration from the config manager:

```yaml
mqtt:
  enabled: true
  broker: "localhost"
  port: 1883
  topic_prefix: "batteryhawk"
  qos: 1  # Default QoS level
  keepalive: 60
  timeout: 10
  retries: 3
```

## Event Handler System

The `MQTTEventHandler` class provides automatic event-driven publishing by registering handlers with the core engine and state manager. This eliminates the need for manual publishing calls throughout the application.

### Setup

```python
from battery_hawk.mqtt import MQTTEventHandler

# Create event handler
event_handler = MQTTEventHandler(core_engine, mqtt_publisher)

# Register all event handlers
event_handler.register_all_handlers()

# Events will now be automatically published to MQTT
```

### Supported Events

| Event Type | Source | Trigger | Published Topic |
|------------|--------|---------|-----------------|
| Device Discovery | Core Engine | Device found during scan | `devices/{device_id}/discovered` |
| Device Reading | State Manager | New battery reading | `devices/{device_id}/readings` |
| Device Status | State Manager | Status change | `devices/{device_id}/status` |
| Connection Change | State Manager | Connection state change | `devices/{device_id}/status` |
| Vehicle Association | Core Engine | Device assigned to vehicle | `vehicles/{vehicle_id}/device_associated` |
| Vehicle Update | State Manager | Vehicle association change | `vehicles/{vehicle_id}/summary` |
| System Shutdown | Core Engine | System shutdown initiated | `system/shutdown` |

### Event Handler Methods

#### Device Events
- `on_device_discovered()` - Publishes device discovery notifications
- `on_device_reading()` - Publishes battery readings and updates vehicle summary
- `on_device_status_change()` - Publishes device status changes
- `on_device_connection_change()` - Publishes connection state changes

#### Vehicle Events
- `on_vehicle_associated()` - Publishes vehicle association events
- `on_vehicle_update()` - Updates vehicle summaries when associations change

#### System Events
- `on_system_shutdown()` - Publishes system shutdown notifications
- `on_system_status_change()` - Publishes system status updates (called manually)

### Vehicle Summary Generation

The event handler automatically generates and publishes vehicle summaries containing:

- Total and connected device counts
- Average voltage and total capacity
- Overall health assessment
- Individual device status
- Health score calculation

Vehicle summaries are cached to avoid redundant updates when data hasn't changed.

### Cleanup

```python
# Unregister all event handlers when shutting down
event_handler.unregister_all_handlers()
```

## Integration Examples

- `examples/mqtt_publisher_example.py` - Manual publishing example
- `examples/mqtt_event_handler_example.py` - Automatic event-driven publishing example
