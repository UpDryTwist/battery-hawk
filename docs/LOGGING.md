# Battery Hawk Logging Configuration

Battery Hawk provides comprehensive logging capabilities with timestamps, file rotation, and flexible configuration options.

## 📋 Table of Contents

- [Default Configuration](#default-configuration)
- [Timestamp Format](#timestamp-format)
- [File Logging](#file-logging)
- [Environment Variables](#environment-variables)
- [Docker Configuration](#docker-configuration)
- [Custom Formats](#custom-formats)
- [Log Rotation](#log-rotation)
- [Testing](#testing)

## 🔧 Default Configuration

Battery Hawk uses a structured logging configuration with timestamps enabled by default:

```json
{
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S",
    "file": null,
    "max_bytes": 10485760,
    "backup_count": 5
  }
}
```

## ⏰ Timestamp Format

All log messages include timestamps in the format: `YYYY-MM-DD HH:MM:SS`

**Example log output:**
```
2025-09-06 10:31:52 - battery_hawk.config - INFO - Logging configured: level=INFO, format includes timestamps
2025-09-06 10:31:52 - battery_hawk.ble - INFO - Scanning for BLE devices...
2025-09-06 10:31:53 - battery_hawk.device - WARNING - Device AA:BB:CC:DD:EE:FF connection timeout
```

## 📁 File Logging

### Enable File Logging

File logging is optional and can be enabled through configuration:

#### Via Configuration File
```bash
# Set log file path
battery-hawk config set system logging file /var/log/battery-hawk/battery-hawk.log
```

#### Via Environment Variable
```bash
export BATTERYHAWK_SYSTEM_LOGGING_FILE=/logs/battery_hawk.log
```

#### Via Docker
```bash
# In .env file
BATTERYHAWK_SYSTEM_LOGGING_FILE=/logs/battery_hawk.log
```

### Log File Features

- **Automatic Directory Creation**: Log directories are created automatically
- **UTF-8 Encoding**: All log files use UTF-8 encoding
- **Rotation**: Automatic log rotation when files exceed size limits
- **Backup Retention**: Configurable number of backup files to keep

## 🌍 Environment Variables

All logging configuration can be overridden using environment variables:

| Variable | Purpose | Default |
|----------|---------|---------|
| `BATTERYHAWK_SYSTEM_LOGGING_LEVEL` | Log level | `INFO` |
| `BATTERYHAWK_SYSTEM_LOGGING_FILE` | Log file path | `null` (console only) |
| `BATTERYHAWK_SYSTEM_LOGGING_FORMAT` | Log message format | `%(asctime)s - %(name)s - %(levelname)s - %(message)s` |
| `BATTERYHAWK_SYSTEM_LOGGING_DATE_FORMAT` | Timestamp format | `%Y-%m-%d %H:%M:%S` |
| `BATTERYHAWK_SYSTEM_LOGGING_MAX_BYTES` | Max file size before rotation | `10485760` (10MB) |
| `BATTERYHAWK_SYSTEM_LOGGING_BACKUP_COUNT` | Number of backup files | `5` |

### Examples

```bash
# Debug logging with custom format
export BATTERYHAWK_SYSTEM_LOGGING_LEVEL=DEBUG
export BATTERYHAWK_SYSTEM_LOGGING_FORMAT="[%(asctime)s] %(levelname)-8s | %(name)s | %(message)s"

# File logging with custom rotation
export BATTERYHAWK_SYSTEM_LOGGING_FILE=/var/log/battery-hawk/debug.log
export BATTERYHAWK_SYSTEM_LOGGING_MAX_BYTES=52428800  # 50MB
export BATTERYHAWK_SYSTEM_LOGGING_BACKUP_COUNT=10
```

## 🐳 Docker Configuration

### Development
```yaml
# docker-compose.override.yml
environment:
  - BATTERYHAWK_SYSTEM_LOGGING_LEVEL=DEBUG
  - BATTERYHAWK_SYSTEM_LOGGING_FILE=/logs/battery_hawk.log
```

### Production
```yaml
# docker-compose.prod.yml
environment:
  - BATTERYHAWK_SYSTEM_LOGGING_LEVEL=INFO
  - BATTERYHAWK_SYSTEM_LOGGING_FILE=/logs/battery_hawk.log
volumes:
  - battery_hawk_logs:/logs
```

### Environment File
```bash
# .env.docker
BATTERYHAWK_SYSTEM_LOGGING_LEVEL=INFO
BATTERYHAWK_SYSTEM_LOGGING_FILE=/logs/battery_hawk.log
BATTERYHAWK_SYSTEM_LOGGING_FORMAT="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
BATTERYHAWK_SYSTEM_LOGGING_DATE_FORMAT="%Y-%m-%d %H:%M:%S"
BATTERYHAWK_SYSTEM_LOGGING_MAX_BYTES=10485760
BATTERYHAWK_SYSTEM_LOGGING_BACKUP_COUNT=5
```

## 🎨 Custom Formats

### Available Format Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `%(asctime)s` | Timestamp | `2025-09-06 10:31:52` |
| `%(name)s` | Logger name | `battery_hawk.ble` |
| `%(levelname)s` | Log level | `INFO` |
| `%(message)s` | Log message | `Device connected` |
| `%(filename)s` | Source filename | `device.py` |
| `%(lineno)d` | Line number | `42` |
| `%(funcName)s` | Function name | `connect_device` |

### Custom Format Examples

```bash
# Compact format
BATTERYHAWK_SYSTEM_LOGGING_FORMAT="%(asctime)s [%(levelname)s] %(message)s"

# Detailed format with source info
BATTERYHAWK_SYSTEM_LOGGING_FORMAT="%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s"

# JSON-like format
BATTERYHAWK_SYSTEM_LOGGING_FORMAT='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
```

## 🔄 Log Rotation

Log rotation prevents log files from growing too large:

### Configuration
- **Max Size**: Default 10MB (`max_bytes`)
- **Backup Count**: Default 5 files (`backup_count`)
- **Naming**: `battery_hawk.log`, `battery_hawk.log.1`, `battery_hawk.log.2`, etc.

### Example
```bash
# Configure 50MB files with 10 backups
battery-hawk config set system logging max_bytes 52428800
battery-hawk config set system logging backup_count 10
```

## 🧪 Testing

### Test Logging Configuration
```bash
# Run logging tests
make test-logging

# Or directly
python examples/test_logging_config.py
```

### Manual Testing
```bash
# Test console logging
battery-hawk system health

# Test file logging
export BATTERYHAWK_SYSTEM_LOGGING_FILE=/tmp/test.log
battery-hawk system health
cat /tmp/test.log

# Test debug level
export BATTERYHAWK_SYSTEM_LOGGING_LEVEL=DEBUG
battery-hawk scan --duration 5
```

## 📊 Log Levels

| Level | When to Use | Example |
|-------|-------------|---------|
| `DEBUG` | Development, detailed troubleshooting | BLE packet details, internal state |
| `INFO` | Normal operation, important events | Device connections, API requests |
| `WARNING` | Recoverable issues, deprecations | Connection timeouts, retries |
| `ERROR` | Errors that don't stop operation | Device communication failures |
| `CRITICAL` | Severe errors that may stop operation | Database connection lost |

## 🔍 Viewing Logs

### CLI Commands
```bash
# View recent logs
battery-hawk system logs --lines 50

# Filter by level
battery-hawk system logs --level ERROR

# Follow logs in real-time
battery-hawk system logs --follow
```

### Docker Commands
```bash
# View container logs
docker compose logs -f battery-hawk

# View specific number of lines
docker compose logs --tail 100 battery-hawk

# Follow logs with timestamps
docker compose logs -f -t battery-hawk
```

## 🚨 Troubleshooting

### Common Issues

#### Log File Not Created
```bash
# Check permissions
ls -la /var/log/battery-hawk/

# Check directory exists
mkdir -p /var/log/battery-hawk/

# Check configuration
battery-hawk config show system logging
```

#### No Timestamps in Output
```bash
# Verify format includes %(asctime)s
battery-hawk config show system logging format

# Reset to default format
battery-hawk config set system logging format "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

#### Log Rotation Not Working
```bash
# Check file size limits
battery-hawk config show system logging max_bytes

# Verify backup count
battery-hawk config show system logging backup_count
```

---

For more information, see:
- [Main Documentation](../README.md)
- [Docker Guide](DOCKER.md)
- [Troubleshooting](TROUBLESHOOTING.md)
