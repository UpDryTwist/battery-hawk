# Battery Hawk API Documentation

This document provides comprehensive documentation for the Battery Hawk REST API. For interactive documentation, visit `/api/docs/` when the application is running.

> **💡 Alternative Interface**: Battery Hawk also provides a comprehensive command-line interface (CLI) for all operations. See [CLI Documentation](CLI.md) for complete CLI usage.

## 🌐 API Overview

The Battery Hawk API follows the [JSON-API specification](https://jsonapi.org/) for consistent data formatting and provides comprehensive battery monitoring capabilities.

### Base URL
```
http://localhost:5000/api
```

### Content Type
All requests must use the JSON-API content type:
```
Content-Type: application/vnd.api+json
```

### Authentication
Currently, the API does not require authentication by default. For production deployments, enable API key authentication:

```bash
# Include API key in requests
curl -H "X-API-Key: your-api-key" http://localhost:5000/api/devices
```

### Rate Limiting
- **Default**: 100 requests per minute per IP
- **Burst**: 200 requests per minute per IP
- **Headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

## 📊 Response Format

All responses follow the JSON-API specification:

### Success Response
```json
{
  "data": {
    "type": "devices",
    "id": "AA:BB:CC:DD:EE:FF",
    "attributes": {
      "friendly_name": "Main Battery",
      "device_type": "BM6",
      "status": "configured"
    }
  },
  "meta": {
    "total": 1
  }
}
```

### Error Response
```json
{
  "errors": [
    {
      "id": "unique-error-id",
      "status": "400",
      "code": "VALIDATION_ERROR",
      "title": "Validation Error",
      "detail": "Invalid MAC address format",
      "source": {
        "pointer": "/data/attributes/mac_address"
      }
    }
  ]
}
```

## 🔍 General Endpoints

### Health Check
Check API health status.

```http
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "core_running": true,
  "version": "1.0.0"
}
```

### Version Information
Get API and core version information.

```http
GET /api/version
```

**Response:**
```json
{
  "api_version": "1.0.0",
  "core_version": "1.0.0",
  "python_version": "3.12.1",
  "build_date": "2024-01-15T10:00:00Z"
}
```

## 🔧 Device Management

### List All Devices
Get all discovered and configured devices.

```http
GET /api/devices?limit=10&offset=0
```

**Query Parameters:**
- `limit` (integer, 1-1000): Maximum number of devices to return (default: 100)
- `offset` (integer, ≥0): Number of devices to skip for pagination (default: 0)

**Response:**
```json
{
  "data": [
    {
      "type": "devices",
      "id": "AA:BB:CC:DD:EE:FF",
      "attributes": {
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "device_type": "BM6",
        "friendly_name": "Main Battery",
        "vehicle_id": "my-car",
        "status": "configured",
        "polling_interval": 3600,
        "discovered_at": "2024-01-15T10:00:00Z",
        "configured_at": "2024-01-15T10:05:00Z",
        "connection_config": {
          "retry_attempts": 3,
          "retry_interval": 60,
          "reconnection_delay": 300
        },
        "latest_reading": {
          "voltage": 12.6,
          "current": 1.2,
          "temperature": 25.0,
          "state_of_charge": 85.0,
          "capacity": 50.0,
          "cycles": 10,
          "timestamp": 1234567890.0,
          "extra": {"device_type": "BM6"}
        },
        "last_reading_time": "2024-01-15T10:30:00Z",
        "device_status": {
          "connected": true,
          "error_code": null,
          "error_message": null,
          "protocol_version": "1.0",
          "last_command": "status"
        },
        "last_status_update": "2024-01-15T10:30:01Z"
      }
    }
  ],
  "meta": {
    "total": 1,
    "limit": 10,
    "offset": 0
  },
  "links": {
    "self": "/api/devices?limit=10&offset=0",
    "next": "/api/devices?limit=10&offset=10"
  }
}
```

### Get Specific Device
Get details for a specific device.

```http
GET /api/devices/{mac_address}
```

**Path Parameters:**
- `mac_address` (string): Device MAC address (e.g., "AA:BB:CC:DD:EE:FF")

**Response Includes:**
- Configuration fields: mac_address, device_type, friendly_name, vehicle_id, status, discovered_at, configured_at, polling_interval, connection_config
- Latest telemetry fields:
  - latest_reading: { voltage, current, temperature, state_of_charge, capacity, cycles, timestamp, extra }
  - last_reading_time: ISO timestamp when the latest_reading was captured
- Runtime status fields:
  - device_status: { connected, error_code, error_message, protocol_version, last_command }
  - last_status_update: ISO timestamp when device_status was updated

### Configure Device
Configure a discovered device for monitoring.

```http
POST /api/devices
Content-Type: application/vnd.api+json
```

**Request Body:**
```json
{
  "data": {
    "type": "devices",
    "attributes": {
      "mac_address": "AA:BB:CC:DD:EE:FF",
      "device_type": "BM6",
      "friendly_name": "Main Battery",
      "vehicle_id": "my-car",
      "polling_interval": 3600
    }
  }
}
```

**Validation Rules:**
- `mac_address`: Valid MAC address format (AA:BB:CC:DD:EE:FF)
- `device_type`: One of "BM2", "BM6", "BM7", "GENERIC"
- `friendly_name`: 1-100 characters
- `vehicle_id`: Optional, 1-50 characters
- `polling_interval`: 60-86400 seconds (default: 3600)

### Update Device
Update device configuration.

```http
PATCH /api/devices/{mac_address}
Content-Type: application/vnd.api+json
```

### Delete Device
Remove device configuration.

```http
DELETE /api/devices/{mac_address}
```

## 🚗 Vehicle Management

### List All Vehicles
Get all configured vehicles.

```http
GET /api/vehicles?limit=10&offset=0
```

### Get Specific Vehicle
Get details for a specific vehicle.

```http
GET /api/vehicles/{vehicle_id}
```

### Create Vehicle
Create a new vehicle.

```http
POST /api/vehicles
Content-Type: application/vnd.api+json
```

**Request Body:**
```json
{
  "data": {
    "type": "vehicles",
    "attributes": {
      "name": "My Car",
      "id": "my-car"
    }
  }
}
```

**Validation Rules:**
- `name`: Required, 1-100 characters
- `id`: Optional custom ID, 1-50 characters (auto-generated if not provided)

### Get Vehicle Devices
Get all devices associated with a vehicle.

```http
GET /api/vehicles/{vehicle_id}/devices
```

## 📈 Data Access

### Get Device Readings
Get historical readings for a device.

```http
GET /api/readings/{mac_address}?limit=10&offset=0&sort=-timestamp
```

**Query Parameters:**
- `limit` (integer, 1-1000): Maximum readings to return (default: 100)
- `offset` (integer, ≥0): Number of readings to skip (default: 0)
- `sort` (string): Sort field and direction
  - Options: `timestamp`, `-timestamp`, `voltage`, `-voltage`, `current`, `-current`, `temperature`, `-temperature`
  - Default: `-timestamp` (newest first)
- `filter[start_time]` (ISO 8601): Filter readings after this time
- `filter[end_time]` (ISO 8601): Filter readings before this time

**Response:**
```json
{
  "data": [
    {
      "type": "readings",
      "id": "reading-id",
      "attributes": {
        "device_id": "AA:BB:CC:DD:EE:FF",
        "timestamp": "2024-01-15T10:30:00Z",
        "voltage": 12.5,
        "current": 2.1,
        "temperature": 25.0,
        "state_of_charge": 85.0,
        "power": 26.25,
        "device_type": "BM6",
        "vehicle_id": "my-car"
      }
    }
  ],
  "meta": {
    "total": 100,
    "limit": 10,
    "offset": 0
  }
}
```

### Get Latest Reading
Get the most recent reading for a device.

```http
GET /api/readings/{mac_address}/latest
```

## ⚙️ System Management

### Get System Configuration
Get current system configuration.

```http
GET /api/system/config
```

**Response:**
```json
{
  "data": {
    "type": "system-config",
    "id": "current",
    "attributes": {
      "logging": {
        "level": "INFO",
        "file": "/var/log/battery-hawk.log"
      },
      "bluetooth": {
        "max_concurrent_connections": 5,
        "scan_duration": 10
      },
      "api": {
        "port": 5000,
        "cors_enabled": true
      },
      "influxdb": {
        "enabled": true,
        "url": "http://localhost:8086"
      },
      "mqtt": {
        "enabled": true,
        "broker": "localhost"
      }
    }
  }
}
```

### Update System Configuration
Update system configuration (safe fields only).

```http
PATCH /api/system/config
Content-Type: application/vnd.api+json
```

**Request Body:**
```json
{
  "data": {
    "type": "system-config",
    "id": "current",
    "attributes": {
      "logging": {
        "level": "DEBUG"
      },
      "bluetooth": {
        "max_concurrent_connections": 3
      }
    }
  }
}
```

**Allowed Configuration Sections:**
- `logging`: Log level and file settings
- `bluetooth`: Bluetooth adapter settings
- `discovery`: Device discovery settings
- `influxdb`: InfluxDB connection settings
- `mqtt`: MQTT broker settings
- `api`: API server settings

**Validation Rules:**
- `logging.level`: One of "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
- `bluetooth.max_concurrent_connections`: 1-10
- `api.port`: 1024-65535

### Get System Status
Get comprehensive system status.

```http
GET /api/system/status
```

### Get System Health
Get system health check.

```http
GET /api/system/health
```

**Response (Healthy):**
```json
{
  "data": {
    "type": "system-health",
    "id": "current",
    "attributes": {
      "healthy": true,
      "components": {
        "core": "healthy",
        "storage": "healthy",
        "bluetooth": "healthy"
      },
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
}
```

**HTTP Status Codes:**
- `200`: System is healthy
- `503`: System is unhealthy

## 🚨 Error Handling

### HTTP Status Codes
- `200`: Success
- `201`: Created
- `400`: Bad Request (validation error)
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `405`: Method Not Allowed
- `409`: Conflict
- `415`: Unsupported Media Type
- `422`: Unprocessable Entity
- `429`: Too Many Requests (rate limited)
- `500`: Internal Server Error
- `503`: Service Unavailable

### Common Error Codes
- `VALIDATION_ERROR`: Request validation failed
- `NOT_FOUND`: Resource not found
- `CONFLICT`: Resource already exists
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `UNSUPPORTED_MEDIA_TYPE`: Invalid content type
- `INTERNAL_ERROR`: Server error

## 📝 Examples

### Complete Device Setup Workflow

```bash
# 1. Check system health
curl http://localhost:5000/api/system/health

# 2. Create a vehicle
curl -X POST http://localhost:5000/api/vehicles \
  -H "Content-Type: application/vnd.api+json" \
  -d '{
    "data": {
      "type": "vehicles",
      "attributes": {"name": "My Car"}
    }
  }'

# 3. List discovered devices
curl http://localhost:5000/api/devices

# 4. Configure a device
curl -X POST http://localhost:5000/api/devices \
  -H "Content-Type: application/vnd.api+json" \
  -d '{
    "data": {
      "type": "devices",
      "attributes": {
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "device_type": "BM6",
        "friendly_name": "Main Battery",
        "vehicle_id": "my-car"
      }
    }
  }'

# 5. Get latest reading
curl http://localhost:5000/api/readings/AA:BB:CC:DD:EE:FF/latest
```

For more examples, see `examples/complete_api_example.py` in the repository.

---

For interactive API exploration, visit `/api/docs/` when the application is running.
