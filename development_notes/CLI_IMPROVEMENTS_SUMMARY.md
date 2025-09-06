# Battery Hawk CLI Improvements Summary

## Overview

The Battery Hawk command-line interface has been significantly enhanced to provide comprehensive coverage of all major functionality. The CLI now offers a complete set of commands for managing services, devices, vehicles, data, MQTT, and system monitoring.

## New Command Structure

The CLI now follows a hierarchical structure with the following main command groups:

```
battery-hawk
├── config          # Configuration management (existing)
├── scan/connect     # Device discovery (existing)
├── service          # Service management (NEW)
├── mqtt             # MQTT operations (NEW)
├── device           # Device management (NEW)
├── vehicle          # Vehicle management (NEW)
├── data             # Data management (NEW)
└── system           # System monitoring (NEW)
```

## New Command Groups Added

### 1. Service Management (`service`)

Commands for managing Battery Hawk services:

- `service start` - Start core monitoring engine with optional API and MQTT services
  - `--api` - Start REST API server
  - `--mqtt` - Start MQTT service
  - `--daemon` - Run in background mode
  - `--pid-file` - Write process ID to file

- `service stop` - Stop running services
  - `--pid-file` - Read process ID from file
  - `--force` - Force stop with SIGKILL

- `service status` - Show service status and health
  - `--format` - Output format (json/table)

- `service restart` - Restart services
  - `--api` - Restart API server
  - `--mqtt` - Restart MQTT service

### 2. MQTT Management (`mqtt`)

Integrated MQTT commands from `cli_mqtt.py`:

- `mqtt status` - Show MQTT configuration and test connection
- `mqtt publish <topic> <message>` - Publish test messages
  - `--retain` - Set retain flag
- `mqtt topics` - List available MQTT topic patterns
- `mqtt monitor` - Monitor incoming MQTT messages
  - `--duration` - Monitoring duration in seconds
- `mqtt test` - Test MQTT service functionality

### 3. Device Management (`device`)

Comprehensive device management commands:

- `device list` - List all registered devices
  - `--format` - Output format (json/table)

- `device add <mac_address>` - Register new device
  - `--device-type` - Device type (BM6/BM2)
  - `--name` - Human-readable name
  - `--polling-interval` - Polling interval in seconds
  - `--vehicle-id` - Associate with vehicle

- `device remove <mac_address>` - Remove device from registry
  - `--force` - Force removal without confirmation

- `device status [mac_address]` - Show device connection status
  - `--format` - Output format (json/table)

- `device readings <mac_address>` - Show recent battery readings
  - `--limit` - Number of readings to show
  - `--format` - Output format (json/table)

### 4. Vehicle Management (`vehicle`)

Vehicle and device association management:

- `vehicle list` - List all configured vehicles
  - `--format` - Output format (json/table)

- `vehicle add <vehicle_id>` - Add new vehicle
  - `--name` - Vehicle name (required)
  - `--description` - Vehicle description
  - `--type` - Vehicle type (car/boat/rv/motorcycle/other)

- `vehicle remove <vehicle_id>` - Remove vehicle
  - `--force` - Force removal without confirmation

- `vehicle show <vehicle_id>` - Show vehicle details and associated devices
  - `--format` - Output format (json/table)

- `vehicle associate <vehicle_id> <mac_address>` - Associate device with vehicle

### 5. Data Management (`data`)

Database and data management operations:

- `data query` - Query historical battery readings
  - `--device` - Filter by device MAC address
  - `--vehicle` - Filter by vehicle ID
  - `--start` - Start time (ISO format)
  - `--end` - End time (ISO format)
  - `--limit` - Maximum number of readings
  - `--format` - Output format (json/table/csv)

- `data export <output_file>` - Export data to files
  - `--format` - Export format (csv/json/xlsx)
  - `--device` - Filter by device
  - `--vehicle` - Filter by vehicle
  - `--start/--end` - Time range filters

- `data stats` - Show database statistics and metrics
  - `--format` - Output format (json/table)

- `data cleanup` - Database maintenance operations
  - `--older-than` - Remove data older than specified time (e.g., '30d', '1y')
  - `--dry-run` - Show what would be deleted
  - `--force` - Force cleanup without confirmation

### 6. System Monitoring (`system`)

System health and troubleshooting tools:

- `system health` - Comprehensive system health check
  - `--format` - Output format (json/table)

- `system logs` - View application logs
  - `--level` - Filter by log level
  - `--lines` - Number of recent lines to show
  - `--follow` - Follow log output (like tail -f)

- `system metrics` - Show system performance metrics
  - `--format` - Output format (json/table)

- `system diagnose` - Run diagnostic checks
  - `--verbose` - Show detailed diagnostic information

## Key Features

### Consistent Interface
- All commands follow consistent argument patterns
- Standardized `--format` options (json/table/csv where applicable)
- Consistent error handling and logging

### Comprehensive Coverage
- Complete service lifecycle management
- Full device and vehicle management
- Data querying and export capabilities
- System monitoring and troubleshooting

### Production Ready
- Daemon mode support for services
- PID file management
- Graceful shutdown handling
- Comprehensive error handling

### User Friendly
- Detailed help text for all commands
- Confirmation prompts for destructive operations
- Multiple output formats
- Verbose and quiet modes where appropriate

## Usage Examples

```bash
# Start services in daemon mode
battery-hawk service start --api --mqtt --daemon --pid-file /var/run/battery-hawk.pid

# Add a new device
battery-hawk device add AA:BB:CC:DD:EE:FF --device-type BM6 --name "Main Battery" --vehicle-id boat1

# Query recent readings
battery-hawk data query --device AA:BB:CC:DD:EE:FF --limit 10 --format json

# Export data to CSV
battery-hawk data export readings.csv --format csv --start 2024-01-01T00:00:00

# Check system health
battery-hawk system health

# Monitor MQTT messages
battery-hawk mqtt monitor --duration 60
```

## Implementation Notes

- All new commands are implemented as async functions for consistency
- Proper error handling with meaningful error messages
- Integration with existing configuration management
- Backward compatibility with existing commands maintained
- Comprehensive logging throughout all operations

This enhancement makes the Battery Hawk CLI a complete management interface suitable for both development and production use.
