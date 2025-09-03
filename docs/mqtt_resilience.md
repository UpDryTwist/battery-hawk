# MQTT Resilience and Reconnection

The MQTT client includes comprehensive resilience features to handle network failures, broker disconnections, and ensure reliable message delivery in production environments.

## Overview

The resilience system provides:

- **Automatic Reconnection**: Exponential backoff retry mechanism
- **Message Queuing**: Reliable delivery with retry limits
- **Connection Monitoring**: Background health checks
- **State Tracking**: Detailed connection state management
- **Graceful Shutdown**: Clean resource cleanup
- **Configurable Parameters**: Tunable retry and timeout settings

## Connection States

The MQTT client tracks connection state through the `ConnectionState` enum:

| State | Description |
|-------|-------------|
| `DISCONNECTED` | Not connected to broker |
| `CONNECTING` | Initial connection attempt in progress |
| `CONNECTED` | Successfully connected and operational |
| `RECONNECTING` | Attempting to reconnect after failure |
| `FAILED` | Connection failed after maximum retries |

## Reconnection Mechanism

### Exponential Backoff

The client uses exponential backoff with jitter to avoid thundering herd problems:

```python
# Default configuration
reconnection_config = ReconnectionConfig(
    max_retries=10,
    initial_retry_delay=1.0,      # Start with 1 second
    max_retry_delay=300.0,        # Cap at 5 minutes
    backoff_multiplier=2.0,       # Double each time
    jitter_factor=0.1,            # Add 10% random jitter
    connection_timeout=30.0,      # 30 second connection timeout
)
```

### Retry Logic

1. **Initial Failure**: Start retry sequence with initial delay
2. **Exponential Backoff**: Delay = `initial_delay * (multiplier ^ attempt)`
3. **Jitter Addition**: Add random variance to prevent synchronized retries
4. **Maximum Cap**: Never exceed `max_retry_delay`
5. **Failure Limit**: Stop after `max_retries` attempts

## Message Queuing

### Automatic Queuing

Messages are automatically queued when:
- Client is not connected
- Connection fails during publish
- Broker is temporarily unavailable

### Queue Management

```python
# Queue configuration
message_queue_size = 1000        # Maximum queued messages
message_retry_limit = 3          # Retry failed messages 3 times
```

### Queue Processing

1. **FIFO Order**: Messages processed in first-in-first-out order
2. **Retry Logic**: Failed messages are retried up to the limit
3. **Error Handling**: Serialization errors cause immediate message drop
4. **Overflow Protection**: Oldest messages dropped when queue is full

## Background Monitoring

### Health Checks

The client runs periodic health checks to detect connection issues:

```python
health_check_interval = 60.0     # Check every 60 seconds
```

Health checks verify:
- Client object validity
- Connection state consistency
- Optional ping/pong if supported by broker

### Message Processor

A background task continuously processes queued messages when connected:

- Runs every 5 seconds
- Processes all queued messages when connection is available
- Handles retry logic and error recovery

## Configuration

### MQTT Configuration

Add resilience parameters to your MQTT configuration:

```yaml
mqtt:
  enabled: true
  broker: "localhost"
  port: 1883
  
  # Resilience settings
  max_retries: 10
  initial_retry_delay: 1.0
  max_retry_delay: 300.0
  backoff_multiplier: 2.0
  jitter_factor: 0.1
  connection_timeout: 30.0
  health_check_interval: 60.0
  message_queue_size: 1000
  message_retry_limit: 3
```

### Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_retries` | 10 | Maximum reconnection attempts |
| `initial_retry_delay` | 1.0 | Initial retry delay in seconds |
| `max_retry_delay` | 300.0 | Maximum retry delay in seconds |
| `backoff_multiplier` | 2.0 | Exponential backoff multiplier |
| `jitter_factor` | 0.1 | Random jitter factor (0.0-1.0) |
| `connection_timeout` | 30.0 | Connection timeout in seconds |
| `health_check_interval` | 60.0 | Health check interval in seconds |
| `message_queue_size` | 1000 | Maximum queued messages |
| `message_retry_limit` | 3 | Message retry attempts |

## Usage Examples

### Basic Usage with Resilience

```python
from battery_hawk.mqtt import MQTTInterface, ConnectionState

# Create interface (resilience is automatic)
mqtt_interface = MQTTInterface(config_manager)

# Connect with automatic retry
await mqtt_interface.connect()

# Publish with automatic queuing on failure
await mqtt_interface.publish("sensors/temperature", {"value": 23.5})

# Check connection state
if mqtt_interface.connection_state == ConnectionState.CONNECTED:
    print("Connected and ready")

# Get statistics
stats = mqtt_interface.stats
print(f"Messages queued: {stats['messages_queued']}")
print(f"Messages published: {stats['messages_published']}")
```

### Monitoring Connection Health

```python
# Check connection state
state = mqtt_interface.connection_state
print(f"Connection state: {state.value}")

# Get detailed statistics
stats = mqtt_interface.stats
print(f"Total connections: {stats['total_connections']}")
print(f"Total reconnections: {stats['total_reconnections']}")
print(f"Queue size: {stats['queue_size']}")
print(f"Consecutive failures: {stats['consecutive_failures']}")
```

### Graceful Shutdown

```python
# Disconnect gracefully (cancels background tasks)
await mqtt_interface.disconnect()
```

## Error Handling

### Connection Errors

- **Network failures**: Automatic reconnection with backoff
- **Broker unavailable**: Queuing until broker returns
- **Authentication failures**: Logged and retried
- **Timeout errors**: Counted as connection failures

### Message Errors

- **Serialization errors**: Message dropped immediately
- **Network errors**: Message queued for retry
- **Broker errors**: Message retried up to limit
- **Queue overflow**: Oldest messages dropped

### Recovery Strategies

1. **Immediate Retry**: For transient network issues
2. **Exponential Backoff**: For persistent connection problems
3. **Message Queuing**: For temporary broker unavailability
4. **Graceful Degradation**: Continue operation with reduced functionality

## Monitoring and Observability

### Statistics

The client provides comprehensive statistics:

```python
stats = mqtt_interface.stats
# Returns:
{
    "connection_state": "connected",
    "total_connections": 5,
    "total_disconnections": 4,
    "total_reconnections": 3,
    "messages_published": 1250,
    "messages_queued": 15,
    "messages_failed": 2,
    "consecutive_failures": 0,
    "queue_size": 5,
    "last_connection_attempt": 1640995200.0
}
```

### Logging

The client logs important events at appropriate levels:

- **INFO**: Successful connections, reconnections
- **WARNING**: Connection failures, retry attempts
- **ERROR**: Maximum retries exceeded, critical failures
- **DEBUG**: Detailed connection state changes

## Best Practices

### Configuration Tuning

1. **Production**: Use longer delays and more retries
2. **Development**: Use shorter delays for faster feedback
3. **High-traffic**: Increase queue size and retry limits
4. **Low-bandwidth**: Reduce queue size and health check frequency

### Error Handling

1. **Monitor statistics** regularly for health assessment
2. **Set up alerts** for consecutive failures or queue overflow
3. **Log connection events** for troubleshooting
4. **Test failure scenarios** in development

### Performance Optimization

1. **Tune retry parameters** based on network characteristics
2. **Monitor queue size** to prevent memory issues
3. **Adjust health check interval** based on requirements
4. **Use appropriate QoS levels** for message importance

## Integration Example

See `examples/mqtt_resilience_example.py` for a complete demonstration of all resilience features.
