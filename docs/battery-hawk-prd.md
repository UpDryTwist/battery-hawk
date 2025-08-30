# Battery Hawk Product Requirements Document

## Overview

Battery Hawk is a containerized battery monitoring solution that runs on Raspberry Pi or Linux servers. It uses Bluetooth Low Energy (BLE) to communicate with BM6 or BM2 battery monitoring hardware, providing real-time data collection, historical storage, and integration capabilities for vehicle battery management across car and boat applications.

## Core Features

**BLE Device Communication**
- Connect to BM6 and BM2 battery monitoring hardware via Bluetooth Low Energy
- Automatic device discovery with configurable scanning intervals
- Extensible protocol support for future battery monitor types

**Multi-Vehicle Fleet Management**
- Support multiple battery monitors across multiple vehicles
- Automatic device-to-vehicle association with manual override capability
- Independent polling and connection management per device

**Data Collection & Storage**
- Configurable polling intervals for battery data collection
- Time series data storage using InfluxDB with automatic tagging
- Local JSON configuration storage with hot-reload capability

**Integration Interfaces**
- Command-line interface for setup and management
- RESTful API with JSON-API standard compliance
- MQTT messaging interface using UpDryTwist implementation
- Home Assistant custom component integration

## Personas & Use Cases

### Primary Persona

- **DIY Auto/Marine Enthusiast**
  - Owns one or more vehicles
  - Runs a small home automation stack (typically Home Assistant + InfluxDB)
  - Comfortable with Docker Compose and basic Linux/IoT concepts

### Example Use Cases

- Detecting slow battery drain in stored vehicles
- Logging charge/discharge cycles during solar charging
- Alerting on voltage drops during winter storage                                            |


## Technical Architecture

### Project Structure
```
battery_hawk/                 # Main application package
├── core/                    # Core monitoring and data collection
├── api/                     # Flask REST API implementation
├── mqtt/                    # MQTT messaging interface
└── config/                  # Configuration management

battery_hawk_driver/         # BLE communication package
├── bm6/                     # BM6 protocol implementation
├── bm2/                     # BM2 protocol implementation
└── base/                    # Shared BLE communication base

homeassistant_battery_hawk/  # Home Assistant integration package
```

### System Components

**Core Engine (AsyncIO-based)**
- Main event loop managing all system operations
- Separate async tasks for device polling, API serving, and MQTT messaging
- Centralized device state management with thread-safe operations

**BLE Communication Layer**
- Bleak-based Bluetooth Low Energy interface
- Device discovery service with configurable scanning intervals
- Connection pool management with configurable concurrency limits
- Protocol abstraction supporting BM6/BM2 with extensibility for future devices

**Data Storage Layer**
- InfluxDB time series database for measurement storage
- Local JSON file storage for configuration and device registry
- Database abstraction layer supporting future time series backends

**API Layer**
- Flask-based REST API running in dedicated async thread
- MQTT messaging interface using UpDryTwist implementation
- JSON-API standard compliance for all HTTP responses

### Data Models

**Device Reading Schema (InfluxDB)**
```json
{
  "measurement": "battery_reading",
  "time": "2025-07-12T10:30:00Z",
  "tags": {
    "device_id": "AA:BB:CC:DD:EE:FF",
    "device_name": "BM6_Starter",
    "vehicle_name": "Vehicle_1",
    "device_type": "BM6"
  },
  "fields": {
    "voltage": 12.65,
    "current": -2.34,
    "state_of_charge": 85.2,
    "temperature": 23.5,
    "power": -30.4
  }
}
```

**Device Registry Schema (devices.json)**
```json
{
  "version": "1.0",
  "devices": {
    "AA:BB:CC:DD:EE:FF": {
      "mac_address": "AA:BB:CC:DD:EE:FF",
      "device_type": "BM6",
      "friendly_name": "Starter Battery",
      "vehicle_id": "vehicle_1",
      "status": "configured",
      "discovered_at": "2025-07-12T10:00:00Z",
      "configured_at": "2025-07-12T10:05:00Z",
      "polling_interval": 3600,
      "connection_config": {
        "retry_attempts": 3,
        "retry_interval": 60,
        "reconnection_delay": 300
      }
    }
  }
}
```

**Vehicle Registry Schema (vehicles.json)**
```json
{
  "version": "1.0",
  "vehicles": {
    "vehicle_1": {
      "name": "Vehicle 1",
      "created_at": "2025-07-12T10:00:00Z",
      "device_count": 1
    }
  }
}
```

**System Configuration Schema (system.json)**
```json
{
  "version": "1.0",
  "discovery": {
    "initial_scan": true,
    "periodic_interval": 43200,
    "scan_duration": 10
  },
  "bluetooth": {
    "max_concurrent_connections": 1,
    "connection_timeout": 30
  },
  "influxdb": {
    "enabled": true,
    "host": "localhost",
    "port": 8086,
    "database": "battery_hawk",
    "username": "",
    "password": ""
  },
  "logging": {
    "level": "INFO",
    "file_logging": false,
    "log_file": "/data/battery_hawk.log"
  },
  "api": {
    "port": 5000,
    "host": "0.0.0.0"
  },
  "mqtt": {
    "enabled": false,
    "broker": "localhost",
    "port": 1883,
    "topic_prefix": "battery_hawk"
  }
}
```

### APIs and Integrations

**REST API Endpoints**
```
GET    /api/devices              # List all devices
GET    /api/devices/{mac}        # Get specific device
POST   /api/devices/{mac}        # Configure device
PATCH  /api/devices/{mac}        # Update device configuration
DELETE /api/devices/{mac}        # Remove device

GET    /api/vehicles             # List all vehicles
GET    /api/vehicles/{id}        # Get specific vehicle
POST   /api/vehicles             # Create vehicle
PATCH  /api/vehicles/{id}        # Update vehicle
DELETE /api/vehicles/{id}        # Remove vehicle

GET    /api/readings/{mac}       # Get recent readings for device
GET    /api/system/config        # Get system configuration
PATCH  /api/system/config        # Update system configuration
GET    /api/system/status        # Get system status
```

**MQTT Topics (UpDryTwist Implementation)**
```
battery_hawk/device/{mac}/reading     # Device reading updates
battery_hawk/device/{mac}/status      # Device connection status
battery_hawk/vehicle/{id}/summary     # Vehicle summary data
battery_hawk/system/status            # System status updates
battery_hawk/discovery/found          # New device discovered
```

## Device Management

### Discovery and Registration
- **Initial Discovery**: Automatic BLE scanning during system startup
- **Periodic Discovery**: Configurable scanning every 12 hours (default)
- **Device States**: discovered → configured → connected/disconnected/error
- **Auto-Registration**: New devices stored with "discovered" status awaiting configuration

### Connection Management
- **Startup Reconnection**: Automatic reconnection to all configured devices
- **Retry Logic**: Configurable retry attempts (default: 3) with 60-second intervals
- **Disconnection Handling**: 300-second delay before reconnection attempts
- **Concurrent Connections**: Configurable limit (default: 1) with queuing
- **State Tracking**: Real-time device status monitoring

### Polling Configuration
- **Per-Device Intervals**: Configurable polling frequency (default: 1 hour)
- **Timestamp Handling**: All measurements timestamped with system UTC time
- **Data Validation**: Invalid or corrupted readings automatically discarded
- **Disconnected Devices**: Automatic polling suspension for unreachable devices

## Data Storage

### Time Series Database (InfluxDB)
- **Primary Storage**: InfluxDB for all measurement data
- **Data Organization**: Unified measurements with device/vehicle tags
- **Retention Policy**: Weeks detail → Monthly consolidation → Yearly summaries
- **Offline Resilience**: Measurements dropped when InfluxDB unavailable
- **Future Compatibility**: Database abstraction layer for alternative backends

### Local Storage (JSON Files)
- **Configuration Files**: Separate JSON files for devices, vehicles, and system config
- **Version Management**: All configuration files include version field for upgrade compatibility
- **Hot Reload**: Configuration changes applied without service restart
- **Storage Location**: `/data/` directory with Docker volume mounting

## Vehicle Organization

### Vehicle Model
- **Simple Structure**: Vehicles identified by name only
- **Multi-Device Support**: Multiple battery monitors per vehicle
- **Auto-Creation**: New vehicle created automatically for each discovered device
- **Default Naming**: Sequential "Vehicle N" naming pattern

### Data Organization
- **Measurement Tagging**: Vehicle information included in all time series data
- **Device Reassignment**: Historical data unchanged when devices move between vehicles
- **Future Data**: New vehicle association applies only to subsequent measurements

## Configuration Management

### Environment Variables
- **Naming Convention**: All settings available as `BATTERYHAWK_VARIABLENAME`
- **Precedence**: Environment variables override configuration file settings
- **Dual Configuration**: All settings configurable via both environment and files

### Configuration Files
- **Location**: All files stored in `/data/` directory
- **Hot Reload**: Changes applied without restart
- **Version Control**: Schema versioning for upgrade compatibility

## Docker Deployment

### Container Requirements
- **Base Image**: Debian-based (Ubuntu/Raspberry Pi OS compatible)
- **Required Packages**: BlueZ, D-Bus, Python 3, Flask, Bleak, UpDryTwist
- **Architecture Support**: Multi-arch builds (arm/v6, arm/v7, arm64, amd64)

### Bluetooth Configuration
- **Capabilities**: `--cap-add=NET_ADMIN` for BLE adapter control
- **Network Mode**: `--net=host` for direct Bluetooth access
- **Service Management**: Container runs D-Bus and BlueZ internally
- **Host Requirements**: Host Bluetooth service must be disabled

### Run Command
```bash
docker run --net=host --cap-add=NET_ADMIN -v /data:/data -e BATTERYHAWK_INFLUXDB_HOST=influxdb-server battery-hawk
```

### External Dependencies
- **InfluxDB**: External instance configured via environment variables
- **MQTT Broker**: Optional external broker for MQTT integration

## Command Line Interface

### Scanning and Testing Interface
- **Scanning**: Run a scan for any local BM6 or BM2 devices from the command-line. Either list devices, or connect and retrieve information, based on switch

## Error Handling and Logging

### Logging Configuration
- **Levels**: DEBUG, INFO, WARN, ERROR with INFO as production default
- **Guidelines**:
  - DEBUG: Detailed operational information
  - INFO: Normal operations including expected BLE disconnections
  - WARN: Anomalous conditions (InfluxDB unavailable)
  - ERROR: Processing failures requiring attention
- **Output**: Configurable stdout/stderr and file logging

### System Resilience
- **Database Failures**: Graceful degradation with WARN logging and reconnection attempts
- **Device Failures**: Continued operation with INFO logging for expected disconnections
- **No Health Endpoints**: Status monitoring via comprehensive logging

## BLE Communication

### Implementation
- **Library**: Bleak for cross-platform BLE communication
- **Protocol Support**: BM6 and BM2 with extensible architecture
- **Reference Implementation**: Based on established BM6 implementations from:
  - https://github.com/JeffWDH/bm6-battery-monitor/blob/main/bm6-battery-monitor.py
  - https://github.com/Rafciq/BM6/blob/main/custom_components/bm6/battery.py
  - https://github.com/Rafciq/BM6/blob/main/custom_components/bm6/bm6_connect.py

### Device Communication
- **AsyncIO Integration**: BLE operations integrated with main async event loop
- **Connection Pooling**: Managed connections with configurable concurrency
- **Error Handling**: Automatic retry logic with exponential backoff
- **Protocol Abstraction**: Extensible base classes for future device types

## Home Assistant Integration

### Discovery and Setup
- **Integration Type**: Custom component with automatic discovery
- **Discovery Method**: BLE scanning for Battery Hawk instances
- **Entity Creation**: Separate device per battery monitor
- **Sensor Data**: All available metrics (voltage, current, SoC, temperature)

### Entity Structure
- **Device Mapping**: Each battery monitor becomes individual HA device
- **Sensor Entities**: Multiple sensors per device for different metrics
- **Discovery Configuration**: Automatic entity creation via HA discovery protocols

## Development Roadmap

### Phase 1: MVP
- BM6 protocol implementation with Bleak
- Device discovery and basic connection management
- CLI interface for device configuration
- Local JSON storage for device registry

### Phase 2: Core Services
- InfluxDB integration with time series storage
- BM2 protocol support
- Flask REST API implementation
- MQTT interface using UpDryTwist

### Phase 3: Integration
- Home Assistant custom component
- Advanced error handling and resilience
- Production Docker container with multi-arch support
- Configuration management with hot reload

### Phase 4: Enhancement
- Additional time series database backends
- Enhanced vehicle management features
- Advanced monitoring and alerting capabilities
- Performance optimization for large device fleets

## Appendix

### Reference Implementation Sources
- BM6 Protocol: Multiple open-source implementations provide reference for BLE communication patterns
- Docker BLE: Container configuration based on BlueZ containerization best practices
- InfluxDB Integration: Standard Python client library implementation
- MQTT: UpDryTwist library provides async MQTT capabilities

### Technical Considerations
- **Raspberry Pi Optimization**: No specific optimizations required beyond standard Python/Docker practices
- **Resource Constraints**: Default configuration suitable for Raspberry Pi 3+ hardware
- **Scalability**: Architecture supports monitoring dozens of devices per instance
