# Battery Hawk CLI Documentation

The Battery Hawk command-line interface provides comprehensive management capabilities for all aspects of the battery monitoring system. This document covers all available commands and their usage.

## 🚀 Getting Started

### Installation and Setup

```bash
# Install Battery Hawk
poetry install

# Activate environment
poetry shell

# Check CLI is working
battery-hawk --help

# Set configuration directory (optional)
export BATTERYHAWK_CONFIG_DIR=/path/to/config
```
```bash
$ battery-hawk --help | sed -n '1,40p'
usage: battery-hawk [-h] [--config-dir CONFIG_DIR] [--bluetooth-adapter ADAPTER] {service,device,config,readings,vehicles,data,system} ...

Battery Hawk CLI

options:
  -h, --help            show this help message and exit
  --config-dir CONFIG_DIR
                        Directory for configuration files (default: /data or $BATTERYHAWK_CONFIG_DIR)
  --bluetooth-adapter ADAPTER
                        Select Bluetooth adapter (e.g., hci0/hci1). Overrides config/env for this run

commands:
  {service,device,config,readings,vehicles,data,system}
                        Command groups
  service              Manage Battery Hawk services (engine, API, MQTT)
  device               Manage devices (scan, connect, read)
  config               View and update configuration
  readings             Query stored readings
  vehicles             Manage vehicles
  data                 Export, import, and cleanup data
  system               System utilities and diagnostics
```


### Basic Usage

```bash
# Show all available commands
battery-hawk --help

# Show help for specific command group
battery-hawk service --help
battery-hawk device --help
```

## 📋 Command Reference

### Global Options

All commands support these global options:

- `--config-dir CONFIG_DIR` - Directory for configuration files (default: /data or $BATTERYHAWK_CONFIG_DIR)
- `--bluetooth-adapter ADAPTER` - Select Bluetooth adapter (e.g., hci0/hci1). Overrides config/env for this run
- `--help` - Show help message

### Output Formats

Many commands support multiple output formats:

- `--format table` - Human-readable table format (default)
- `--format json` - JSON format for scripting
- `--format csv` - CSV format for data export

## 🔧 Service Management (`service`)

Manage Battery Hawk services including the core engine, API server, and MQTT service.

### `service start`

Start Battery Hawk services with optional components.

```bash
# Start core engine only
battery-hawk service start

# Start with API server
battery-hawk service start --api

# Start with MQTT service
battery-hawk service start --mqtt

# Start all services
battery-hawk service start --api --mqtt

# Start in daemon mode
battery-hawk service start --api --mqtt --daemon --pid-file /var/run/battery-hawk.pid
```

**Options:**
- `--api` - Start the REST API server
- `--mqtt` - Start the MQTT service
- `--daemon` - Run in background mode
- `--pid-file PATH` - Write process ID to file (daemon mode only)

### `service stop`

Stop running Battery Hawk services.

```bash
# Stop using PID file
battery-hawk service stop --pid-file /var/run/battery-hawk.pid

# Force stop with SIGKILL
battery-hawk service stop --pid-file /var/run/battery-hawk.pid --force
```

**Options:**
- `--pid-file PATH` - Read process ID from file
- `--force` - Force stop using SIGKILL

### `service status`

Show status of Battery Hawk services.

```bash
# Show service status
battery-hawk service status

# JSON output
battery-hawk service status --format json
```

**Options:**
- `--format {json,table}` - Output format (default: table)

### `service restart`

Restart Battery Hawk services.

```bash
# Restart all services
battery-hawk service restart --api --mqtt --pid-file /var/run/battery-hawk.pid
```

**Options:**
- `--api` - Restart the REST API server
- `--mqtt` - Restart the MQTT service

## 📱 Device Management (`device`)

Comprehensive device management for battery monitors.

### `device scan`

Scan for BLE battery monitor devices.

```bash
# Basic scan
battery-hawk device scan

# Scan with connection test
battery-hawk device scan --connect

# Custom duration and format
battery-hawk device scan --duration 15 --format json

# Scan until new device found
battery-hawk device scan --scan-until-new --short-timeout 5

# Adapter selection examples
# Use a specific Bluetooth adapter for this run only
battery-hawk device scan --bluetooth-adapter hci1 --duration 10

# Persisted config approach (affects future runs)
# Either via CLI config set:
battery-hawk config set system bluetooth '{"adapter": "hci1"}' && battery-hawk config save system
# Or via environment variable for container/host:
export BATTERYHAWK_SYSTEM_BLUETOOTH_ADAPTER=hci1

```

**Options:**
- `--duration SECONDS` - Scan duration in seconds (default: 10)
- `--connect` - Connect to discovered devices and retrieve information
- `--format {json,table}` - Output format (default: table)
- `--no-storage` - Disable loading from and writing to device storage file
- `--scan-until-new` - Stop scanning when a new device is found
- `--short-timeout SECONDS` - Timeout for individual scans when using --scan-until-new

### `device connect`

Connect to a specific device by MAC address.

```bash
# Connect to device
battery-hawk device connect AA:BB:CC:DD:EE:FF

# Specify device type
battery-hawk device connect AA:BB:CC:DD:EE:FF --device-type BM6

# Custom timeout and retries
battery-hawk device connect AA:BB:CC:DD:EE:FF --timeout 45 --retry-attempts 5
```

**Options:**
- `--device-type {BM6,BM2,auto}` - Device type to use (default: auto-detect)
- `--timeout SECONDS` - Connection timeout in seconds (default: 30)
- `--retry-attempts COUNT` - Number of connection retry attempts (default: 3)
- `--retry-delay SECONDS` - Delay between retry attempts in seconds (default: 2.0)
- `--format {json,table}` - Output format for device information (default: table)

### `device list`

List all registered devices.

```bash
# List devices
battery-hawk device list

# JSON output
battery-hawk device list --format json
```

**Options:**
- `--format {json,table}` - Output format (default: table)

### `device add`

Register a new device.

```bash
# Add device with required parameters
battery-hawk device add AA:BB:CC:DD:EE:FF --device-type BM6

# Add with full configuration
battery-hawk device add AA:BB:CC:DD:EE:FF \
  --device-type BM6 \
  --name "Main Battery" \
  --polling-interval 1800 \
  --vehicle-id my-car
```

**Options:**
- `--device-type {BM6,BM2}` - Device type (required)
- `--name NAME` - Human-readable name for the device
- `--polling-interval SECONDS` - Polling interval in seconds (default: 3600)
- `--vehicle-id ID` - Associate device with a vehicle

### `device remove`

Remove a device from the registry.

```bash
# Remove device with confirmation
battery-hawk device remove AA:BB:CC:DD:EE:FF

# Force removal without confirmation
battery-hawk device remove AA:BB:CC:DD:EE:FF --force
```

**Options:**
- `--force` - Force removal without confirmation

### `device status`

Show device connection status and activity.

```bash
# Show status for all devices
battery-hawk device status

# Show status for specific device
battery-hawk device status AA:BB:CC:DD:EE:FF

# JSON output
battery-hawk device status --format json
```

**Options:**
- `--format {json,table}` - Output format (default: table)

### `device readings`

Show recent battery readings from a device.

```bash
# Show recent readings
battery-hawk device readings AA:BB:CC:DD:EE:FF

# Show more readings
battery-hawk device readings AA:BB:CC:DD:EE:FF --limit 20

# JSON output
battery-hawk device readings AA:BB:CC:DD:EE:FF --format json
```

**Options:**
- `--limit COUNT` - Number of recent readings to show (default: 10)
- `--format {json,table}` - Output format (default: table)

## 🚗 Vehicle Management (`vehicle`)

Manage vehicles and device associations.

### `vehicle list`

List all configured vehicles.

```bash
# List vehicles
battery-hawk vehicle list

# JSON output
battery-hawk vehicle list --format json
```

**Options:**
- `--format {json,table}` - Output format (default: table)

### `vehicle add`

Add a new vehicle to the registry.

```bash
# Add vehicle with required name
battery-hawk vehicle add my-car --name "My Car"

# Add with full details
battery-hawk vehicle add boat1 \
  --name "Fishing Boat" \
  --type boat \
  --description "Weekend fishing boat"
```

**Options:**
- `--name NAME` - Human-readable name for the vehicle (required)
- `--description TEXT` - Description of the vehicle
- `--type {car,boat,rv,motorcycle,other}` - Type of vehicle (default: other)

### `vehicle remove`

Remove a vehicle from the registry.

```bash
# Remove vehicle with confirmation
battery-hawk vehicle remove my-car

# Force removal without confirmation
battery-hawk vehicle remove my-car --force
```

**Options:**
- `--force` - Force removal without confirmation

### `vehicle show`

Show detailed information about a vehicle and its devices.

```bash
# Show vehicle details
battery-hawk vehicle show my-car

# JSON output
battery-hawk vehicle show my-car --format json
```

**Options:**
- `--format {json,table}` - Output format (default: table)

### `vehicle associate`

Associate a device with a vehicle.

```bash
# Associate device with vehicle
battery-hawk vehicle associate my-car AA:BB:CC:DD:EE:FF
```

## 📊 Data Management (`data`)

Manage stored battery data and database operations.

### `data query`

Query historical battery readings from the database.

```bash
# Query recent readings
battery-hawk data query --limit 50

# Query by device
battery-hawk data query --device AA:BB:CC:DD:EE:FF --limit 10

# Query by vehicle
battery-hawk data query --vehicle my-car --limit 20

# Query by time range
battery-hawk data query \
  --start 2024-01-01T00:00:00 \
  --end 2024-01-02T00:00:00 \
  --format json

# CSV output
battery-hawk data query --device AA:BB:CC:DD:EE:FF --format csv
```

**Options:**
- `--device MAC` - Filter by device MAC address
- `--vehicle ID` - Filter by vehicle ID
- `--start TIME` - Start time (ISO format: 2024-01-01T00:00:00)
- `--end TIME` - End time (ISO format: 2024-01-01T23:59:59)
- `--limit COUNT` - Maximum number of readings to return (default: 100)
- `--format {json,table,csv}` - Output format (default: table)

### `data export`

Export battery data to various formats.

```bash
# Export to CSV
battery-hawk data export readings.csv --format csv

# Export specific device data
battery-hawk data export device_data.csv \
  --format csv \
  --device AA:BB:CC:DD:EE:FF

# Export vehicle data to Excel
battery-hawk data export vehicle_data.xlsx \
  --format xlsx \
  --vehicle my-car

# Export with time range
battery-hawk data export monthly_data.json \
  --format json \
  --start 2024-01-01T00:00:00 \
  --end 2024-01-31T23:59:59
```

**Options:**
- `--format {csv,json,xlsx}` - Export format (default: csv)
- `--device MAC` - Filter by device MAC address
- `--vehicle ID` - Filter by vehicle ID
- `--start TIME` - Start time (ISO format)
- `--end TIME` - End time (ISO format)

### `data stats`

Show database storage statistics and metrics.

```bash
# Show database statistics
battery-hawk data stats

# JSON output
battery-hawk data stats --format json
```

**Options:**
- `--format {json,table}` - Output format (default: table)

### `data cleanup`

Perform database cleanup and maintenance operations.

```bash
# Dry run - show what would be deleted
battery-hawk data cleanup --older-than 30d --dry-run

# Delete data older than 1 year
battery-hawk data cleanup --older-than 1y --force

# Interactive cleanup
battery-hawk data cleanup --older-than 6m
```

**Options:**
- `--older-than TIME` - Remove data older than specified time (e.g., '30d', '1y', '6m')
- `--dry-run` - Show what would be deleted without actually deleting
- `--force` - Force cleanup without confirmation

**Time Format Examples:**
- `30d` - 30 days
- `6m` - 6 months (approximate)
- `1y` - 1 year (approximate)
- `2w` - 2 weeks

## 📡 MQTT Management (`mqtt`)

Manage MQTT connectivity, testing, and monitoring.

### `mqtt status`

Show MQTT connection status and configuration.

```bash
# Show MQTT status
battery-hawk mqtt status
```

### `mqtt publish`

Publish a test message to an MQTT topic.

```bash
# Publish simple message
battery-hawk mqtt publish device/test "Hello World"

# Publish JSON message
battery-hawk mqtt publish device/reading '{"voltage": 12.5, "current": 2.1}'

# Publish with retain flag
battery-hawk mqtt publish device/status "online" --retain
```

**Options:**
- `--retain` - Set retain flag on message

### `mqtt topics`

List all available MQTT topic patterns and examples.

```bash
# List MQTT topics
battery-hawk mqtt topics
```

### `mqtt monitor`

Monitor and display incoming MQTT messages.

```bash
# Monitor for 30 seconds
battery-hawk mqtt monitor

# Monitor for custom duration
battery-hawk mqtt monitor --duration 60
```

**Options:**
- `--duration SECONDS` - Monitoring duration in seconds (default: 30)

### `mqtt test`

Test MQTT service functionality with sample data.

```bash
# Test MQTT service
battery-hawk mqtt test
```

## 🔍 System Monitoring (`system`)

System health monitoring, logs, and troubleshooting tools.

### `system health`

Perform comprehensive system health check.

```bash
# Health check
battery-hawk system health

# JSON output
battery-hawk system health --format json
```

**Options:**
- `--format {json,table}` - Output format (default: table)

### `system logs`

View and filter application logs.

```bash
# View recent logs
battery-hawk system logs

# View more lines
battery-hawk system logs --lines 100

# Filter by log level
battery-hawk system logs --level ERROR

# Follow logs in real-time
battery-hawk system logs --follow
```

**Options:**
- `--level {DEBUG,INFO,WARNING,ERROR,CRITICAL}` - Filter by log level
- `--lines COUNT` - Number of recent log lines to show (default: 50)
- `--follow` - Follow log output (like tail -f)

### `system metrics`

Show system performance metrics and statistics.

```bash
# Show system metrics
battery-hawk system metrics

# JSON output
battery-hawk system metrics --format json
```

**Options:**
- `--format {json,table}` - Output format (default: table)

### `system diagnose`

Run comprehensive diagnostic checks and troubleshooting.

```bash
# Run diagnostics
battery-hawk system diagnose

# Verbose diagnostics
battery-hawk system diagnose --verbose
```

**Options:**
- `--verbose` - Show detailed diagnostic information

## ⚙️ Configuration Management (`config`)

Manage Battery Hawk configuration settings.

### `config show`

Display configuration sections or specific keys.

```bash
# Show entire section
battery-hawk config show system

# Show specific key
battery-hawk config show system logging level

# Show nested configuration
battery-hawk config show devices
```

### `config set`

Set configuration values.

```bash
# Set simple value
battery-hawk config set system logging level INFO

# Set JSON value
battery-hawk config set system api '{"host": "0.0.0.0", "port": 5000}'
```

### `config save`

Save a configuration section to disk.

```bash
# Save configuration section
battery-hawk config save system
```

### `config list`

List all available configuration sections.

```bash
# List config sections
battery-hawk config list
```

## 🔧 Common Usage Patterns

### Initial Setup

```bash
# 1. Check system health
battery-hawk system health

# 2. Scan for devices
battery-hawk device scan --connect

# 3. Add discovered device
battery-hawk device add AA:BB:CC:DD:EE:FF --device-type BM6 --name "Main Battery"

# 4. Create vehicle
battery-hawk vehicle add my-car --name "My Car" --type car

# 5. Associate device with vehicle
battery-hawk vehicle associate my-car AA:BB:CC:DD:EE:FF

# 6. Start services
battery-hawk service start --api --mqtt
```

### Daily Operations

```bash
# Check service status
battery-hawk service status

# Check device status
battery-hawk device status

# View recent readings
battery-hawk device readings AA:BB:CC:DD:EE:FF --limit 5

# Check system health
battery-hawk system health
```

### Data Management

```bash
# Export weekly data
battery-hawk data export weekly_$(date +%Y%m%d).csv \
  --start $(date -d '7 days ago' +%Y-%m-%dT00:00:00) \
  --end $(date +%Y-%m-%dT23:59:59)

# Clean up old data (monthly)
battery-hawk data cleanup --older-than 90d --dry-run
battery-hawk data cleanup --older-than 90d --force

# Check database statistics
battery-hawk data stats
```

### Troubleshooting

```bash
# Run full diagnostics
battery-hawk system diagnose --verbose

# Check logs for errors
battery-hawk system logs --level ERROR --lines 20

# Test MQTT connectivity
battery-hawk mqtt status
battery-hawk mqtt test

# Check device connectivity
battery-hawk device scan --duration 5
battery-hawk device status
```

## 📝 Scripting and Automation

### JSON Output for Scripts

Most commands support JSON output for easy parsing in scripts:

```bash
# Get device list as JSON
DEVICES=$(battery-hawk device list --format json)

# Get system status as JSON
STATUS=$(battery-hawk system health --format json)

# Export data programmatically
battery-hawk data export "backup_$(date +%Y%m%d).json" --format json
```

### Exit Codes

All CLI commands return appropriate exit codes:

- `0` - Success
- `1` - General error or failure
- `2` - Invalid arguments or configuration

### Environment Variables

- `BATTERYHAWK_CONFIG_DIR` - Configuration directory path
- `BATTERYHAWK_SYSTEM_BLUETOOTH_ADAPTER` - Select Bluetooth adapter (e.g., hci0)

- `LOG_LEVEL` - Override logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

## 🆘 Getting Help

```bash
# General help
battery-hawk --help

# Command group help
battery-hawk service --help
battery-hawk device --help

# Specific command help
battery-hawk device add --help
battery-hawk data query --help
```

For more detailed information, see the complete documentation at [docs/](../docs/).
