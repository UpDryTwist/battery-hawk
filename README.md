[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/UpDryTwist/battery-hawk/graphs/commit-activity)
[![MIT license](https://img.shields.io/badge/License-MIT-blue.svg)](https://lbesson.mit-license.org/)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Poetry](https://img.shields.io/badge/dependency%20management-poetry-blue.svg)](https://python-poetry.org/)
[![buymecoffee](https://img.shields.io/badge/-buy_me_a%C2%A0coffee-gray?logo=buy-me-a-coffee)](https://www.buymeacoffee.com/UpDryTwist)

# Battery Hawk 🔋🦅

**Battery Hawk** is a comprehensive battery monitoring system that uses Bluetooth Low Energy (BLE) battery monitors (BM2, BM6, BM7, and compatible devices) to monitor batteries in cars, boats, RVs, and other vehicles. It provides real-time monitoring, data collection, alerting, and a complete REST API for integration with other systems.

## 🌟 Features

- **🔍 Device Discovery**: Automatic discovery of BLE battery monitors
- **📊 Real-time Monitoring**: Continuous battery voltage, current, temperature, and state-of-charge monitoring
- **🚗 Vehicle Management**: Organize devices by vehicle for better fleet management
- **📈 Data Storage**: Store historical data in InfluxDB with configurable retention policies
- **🔔 MQTT Integration**: Publish readings to MQTT brokers for home automation
- **🌐 REST API**: Complete JSON-API compliant REST interface with interactive documentation
- **🐳 Docker Support**: Containerized deployment with Docker Compose
- **⚡ Rate Limiting**: Production-ready API with rate limiting and security headers
- **📚 Interactive Documentation**: Swagger/OpenAPI documentation at `/api/docs/`
- **🔒 Security**: Comprehensive validation, error handling, and security middleware

## 📖 Documentation

### API Documentation
- **Interactive API Documentation**: [http://localhost:5000/api/docs/](http://localhost:5000/api/docs/) (when running)
- **OpenAPI Specification**: [http://localhost:5000/api/docs/apispec.json](http://localhost:5000/api/docs/apispec.json)
- **API Examples**: See `examples/complete_api_example.py` for comprehensive usage examples

### Additional Documentation
- **💻 [CLI Documentation](docs/CLI.md)**: Complete command-line interface reference
- **📖 [Complete API Documentation](docs/API.md)**: Comprehensive API reference with examples
- **🚀 [Deployment Guide](docs/DEPLOYMENT.md)**: Production deployment scenarios and configurations
- **🔧 [Troubleshooting Guide](docs/TROUBLESHOOTING.md)**: Common issues and solutions
- **🤝 [Contributing Guide](CONTRIBUTING.md)**: Development setup and contribution guidelines
- **⚙️ Configuration Guide**: See [Configuration](#-configuration) section below
- **🧪 Development Setup**: See [Development](#-development) section below

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+** (required)
- **Poetry** for dependency management
- **Bluetooth adapter** with BLE support
- **InfluxDB** (optional, for data storage)
- **MQTT Broker** (optional, for MQTT integration)

### Installation

#### Option 1: Using Poetry (Recommended for Development)

```bash
# Clone the repository
git clone https://github.com/UpDryTwist/battery-hawk.git
cd battery-hawk

# Install dependencies
poetry install

# Activate the virtual environment
poetry shell

# Run the application
python -m battery_hawk
```

#### Option 2: Using Docker (Recommended for Production)

```bash
# Clone the repository
git clone https://github.com/UpDryTwist/battery-hawk.git
cd battery-hawk

# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f battery-hawk
```

#### Option 3: Using Make

```bash
# Build Docker image
make docker-build

# Run with Docker Compose
make docker-up

# View logs
make docker-logs
```

### First Run

1. **Start the application** using one of the methods above
2. **Access the web interface** at [http://localhost:5000](http://localhost:5000)
3. **View API documentation** at [http://localhost:5000/api/docs/](http://localhost:5000/api/docs/)
4. **Check system status** at [http://localhost:5000/api/system/status](http://localhost:5000/api/system/status)

## ⚙️ Configuration

Battery Hawk uses a hierarchical configuration system with environment variables and configuration files.

### Environment Variables

Create a `.env` file in the project root:

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=5000

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=/var/log/battery-hawk/battery-hawk.log

# Bluetooth Configuration
BLUETOOTH_MAX_CONCURRENT_CONNECTIONS=5
BLUETOOTH_SCAN_DURATION=10

# InfluxDB Configuration (optional)
INFLUXDB_ENABLED=true
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=your-influxdb-token
INFLUXDB_ORG=your-org
INFLUXDB_BUCKET=battery-hawk

# MQTT Configuration (optional)
MQTT_ENABLED=true
MQTT_BROKER=localhost
MQTT_PORT=1883
MQTT_USERNAME=your-username
MQTT_PASSWORD=your-password
MQTT_TOPIC_PREFIX=battery-hawk
```

### Configuration File

Create `config/battery-hawk.yaml`:

```yaml
api:
  host: "0.0.0.0"
  port: 5000
  cors_enabled: true

logging:
  level: "INFO"
  file: "/var/log/battery-hawk/battery-hawk.log"
  max_size: "10MB"
  backup_count: 5

bluetooth:
  max_concurrent_connections: 5
  scan_duration: 10
  retry_attempts: 3
  retry_delay: 5

discovery:
  scan_interval: 300
  device_timeout: 600

influxdb:
  enabled: true
  url: "http://localhost:8086"
  token: "your-influxdb-token"
  org: "your-org"
  bucket: "battery-hawk"
  retention_policy: "30d"

mqtt:
  enabled: true
  broker: "localhost"
  port: 1883
  username: "your-username"
  password: "your-password"
  topic_prefix: "battery-hawk"
  qos: 1
```

### Runtime Configuration

You can also update configuration through the REST API:

```bash
# Update logging level
curl -X PATCH http://localhost:5000/api/system/config \
  -H "Content-Type: application/vnd.api+json" \
  -d '{
    "data": {
      "type": "system-config",
      "id": "current",
      "attributes": {
        "logging": {
          "level": "DEBUG"
        }
      }
    }
  }'
```

## 🔧 Usage

Battery Hawk provides both a comprehensive command-line interface and a REST API for all operations.

### Command Line Interface

The CLI provides complete management capabilities with intuitive commands:

```bash
# Show all available commands
battery-hawk --help

# Service management
battery-hawk service start --api --mqtt --daemon
battery-hawk service status
battery-hawk service stop

# Device management
battery-hawk device scan --duration 10 --connect
battery-hawk device add AA:BB:CC:DD:EE:FF --device-type BM6 --name "Main Battery"
battery-hawk device list
battery-hawk device status AA:BB:CC:DD:EE:FF

# Vehicle management
battery-hawk vehicle add my-car --name "My Car" --type car
battery-hawk vehicle associate my-car AA:BB:CC:DD:EE:FF
battery-hawk vehicle list

# Data management
battery-hawk data query --device AA:BB:CC:DD:EE:FF --limit 10
battery-hawk data export readings.csv --format csv --start 2024-01-01T00:00:00
battery-hawk data stats

# MQTT operations
battery-hawk mqtt status
battery-hawk mqtt publish device/test "Hello World"
battery-hawk mqtt monitor --duration 30

# System monitoring
battery-hawk system health
battery-hawk system diagnose
battery-hawk system metrics
```

#### CLI Command Groups

| Command Group | Description | Key Commands |
|---------------|-------------|--------------|
| `service` | Service management | `start`, `stop`, `status`, `restart` |
| `device` | Device operations | `scan`, `connect`, `add`, `remove`, `list`, `status`, `readings` |
| `vehicle` | Vehicle management | `add`, `remove`, `list`, `show`, `associate` |
| `data` | Data operations | `query`, `export`, `stats`, `cleanup` |
| `mqtt` | MQTT management | `status`, `publish`, `topics`, `monitor`, `test` |
| `system` | System monitoring | `health`, `logs`, `metrics`, `diagnose` |
| `config` | Configuration | `show`, `set`, `save`, `list` |

### REST API Usage

#### Device Management

##### Discover Devices
```bash
# Get all discovered devices
curl http://localhost:5000/api/devices

# Get specific device
curl http://localhost:5000/api/devices/AA:BB:CC:DD:EE:FF
```

##### Configure a Device
```bash
curl -X POST http://localhost:5000/api/devices \
  -H "Content-Type: application/vnd.api+json" \
  -d '{
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
  }'
```

#### Vehicle Management

##### CLI Commands
```bash
# Add a new vehicle
battery-hawk vehicle add my-car --name "My Car" --type car --description "Daily driver"

# List all vehicles
battery-hawk vehicle list

# Show vehicle details
battery-hawk vehicle show my-car

# Associate device with vehicle
battery-hawk vehicle associate my-car AA:BB:CC:DD:EE:FF

# Remove vehicle
battery-hawk vehicle remove my-car
```

##### API Commands
```bash
# Create a Vehicle
curl -X POST http://localhost:5000/api/vehicles \
  -H "Content-Type: application/vnd.api+json" \
  -d '{
    "data": {
      "type": "vehicles",
      "attributes": {
        "name": "My Car"
      }
    }
  }'
```

### Data Access and Management

#### CLI Commands
```bash
# Query recent readings
battery-hawk data query --device AA:BB:CC:DD:EE:FF --limit 10 --format table

# Query readings by time range
battery-hawk data query --start 2024-01-01T00:00:00 --end 2024-01-02T00:00:00 --format json

# Export data to CSV
battery-hawk data export readings.csv --format csv --device AA:BB:CC:DD:EE:FF

# Export data to Excel
battery-hawk data export readings.xlsx --format xlsx --vehicle my-car

# Show database statistics
battery-hawk data stats

# Clean up old data
battery-hawk data cleanup --older-than 30d --dry-run
battery-hawk data cleanup --older-than 1y --force
```

#### API Commands
```bash
# Get latest reading for a device
curl http://localhost:5000/api/readings/AA:BB:CC:DD:EE:FF/latest

# Get historical readings with pagination
curl "http://localhost:5000/api/readings/AA:BB:CC:DD:EE:FF?limit=10&offset=0&sort=-timestamp"
```

### System Monitoring

#### CLI Commands
```bash
# Comprehensive health check
battery-hawk system health

# Run diagnostic tests
battery-hawk system diagnose --verbose

# Show system metrics
battery-hawk system metrics

# View application logs
battery-hawk system logs --lines 50 --level INFO

# Follow logs in real-time
battery-hawk system logs --follow
```

#### API Commands
```bash
# Get system status
curl http://localhost:5000/api/system/status

# Get system health
curl http://localhost:5000/api/system/health

# Get current configuration
curl http://localhost:5000/api/system/config
```

### Using Docker Compose

The included `docker-compose.yml` provides a complete stack with InfluxDB and optional MQTT:

```bash
# Start the complete stack
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the stack
docker-compose down

# Update and restart
docker-compose pull && docker-compose up -d
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Bluetooth Permission Issues
```bash
# Add user to bluetooth group (Linux)
sudo usermod -a -G bluetooth $USER

# Restart bluetooth service
sudo systemctl restart bluetooth

# Check bluetooth status
sudo systemctl status bluetooth
```

#### 2. Device Discovery Problems
```bash
# Check if devices are discoverable
sudo hcitool lescan

# Reset bluetooth adapter
sudo hciconfig hci0 down
sudo hciconfig hci0 up

# Check application logs
docker-compose logs battery-hawk | grep -i bluetooth
```

#### 3. API Connection Issues
```bash
# CLI health check
battery-hawk system health

# CLI diagnostic check
battery-hawk system diagnose

# Check if API is running
curl http://localhost:5000/api/health

# Check system status
curl http://localhost:5000/api/system/status

# View detailed logs
docker-compose logs -f battery-hawk
```

#### 4. CLI Troubleshooting
```bash
# Check CLI installation
battery-hawk --help

# Test configuration loading
battery-hawk config list

# Test device scanning
battery-hawk device scan --duration 5

# Check service status
battery-hawk service status

# View system logs through CLI
battery-hawk system logs --lines 20 --level ERROR
```

#### 5. Database Connection Issues
```bash
# Check InfluxDB status
docker-compose logs influxdb

# Test InfluxDB connection
curl http://localhost:8086/health

# Reset InfluxDB data (WARNING: destroys data)
docker-compose down -v
docker-compose up -d
```

### Log Analysis

#### Enable Debug Logging
```bash
# Via API
curl -X PATCH http://localhost:5000/api/system/config \
  -H "Content-Type: application/vnd.api+json" \
  -d '{
    "data": {
      "type": "system-config",
      "id": "current",
      "attributes": {
        "logging": {"level": "DEBUG"}
      }
    }
  }'

# Via environment variable
export LOG_LEVEL=DEBUG
```

#### Common Log Patterns
```bash
# Connection issues
docker-compose logs battery-hawk | grep -i "connection\|timeout\|error"

# Device discovery
docker-compose logs battery-hawk | grep -i "discover\|scan\|found"

# API requests
docker-compose logs battery-hawk | grep -i "request\|response\|api"

# Validation errors
docker-compose logs battery-hawk | grep -i "validation\|invalid"
```

### Performance Tuning

#### Bluetooth Optimization
```yaml
# In config/battery-hawk.yaml
bluetooth:
  max_concurrent_connections: 3  # Reduce for stability
  scan_duration: 5              # Shorter scans
  retry_attempts: 2             # Fewer retries
```

#### API Rate Limiting
```yaml
# Adjust rate limits for high-traffic scenarios
api:
  rate_limit_per_minute: 200
  rate_limit_burst: 400
```

### Health Checks

#### System Health Endpoint
```bash
# Quick health check
curl http://localhost:5000/api/system/health

# Detailed status
curl http://localhost:5000/api/system/status | jq .
```

#### Docker Health Checks
```bash
# Check container health
docker-compose ps

# View health check logs
docker inspect battery-hawk_battery-hawk_1 | jq '.[0].State.Health'
```

## 🧪 Development

### Development Setup

```bash
# Clone and setup
git clone https://github.com/UpDryTwist/battery-hawk.git
cd battery-hawk

# Install development dependencies
poetry install --with dev

# Activate virtual environment
poetry shell

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run with coverage
pytest --cov=src/battery_hawk --cov-report=html

# Run linting
ruff check src/ tests/
ruff format src/ tests/

# Type checking
mypy src/
```

### Testing

#### Unit Tests
```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/test_api*.py          # API tests
pytest tests/test_core*.py         # Core functionality tests
pytest tests/test_validation*.py   # Validation tests

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=src/battery_hawk --cov-report=term-missing
```

#### Integration Tests
```bash
# Run integration tests (requires Bluetooth)
pytest tests/integration/ -m integration

# Run API integration tests
pytest tests/test_api_integration.py
```

#### Load Testing
```bash
# Install load testing tools
pip install locust

# Run API load tests
locust -f tests/load/api_load_test.py --host=http://localhost:5000
```

### Code Quality

#### Linting and Formatting
```bash
# Check code style
ruff check src/ tests/

# Auto-fix issues
ruff check --fix src/ tests/

# Format code
ruff format src/ tests/

# Sort imports
isort src/ tests/
```

#### Type Checking
```bash
# Run type checking
mypy src/

# Check specific module
mypy src/battery_hawk/api/
```

### Building and Deployment

#### Docker Build
```bash
# Build development image
docker build -t battery-hawk:dev .

# Build production image
docker build -t battery-hawk:latest -f Dockerfile.prod .

# Multi-platform build
docker buildx build --platform linux/amd64,linux/arm64 -t battery-hawk:latest .
```

#### Release Process
```bash
# Update version
poetry version patch  # or minor, major

# Build package
poetry build

# Run full test suite
pytest

# Create release
git tag v$(poetry version -s)
git push origin v$(poetry version -s)
```

## 📊 Monitoring and Observability

### Metrics and Monitoring

Battery Hawk exposes several monitoring endpoints:

- **Health Check**: `GET /api/health` - Basic health status
- **System Status**: `GET /api/system/status` - Detailed system information
- **System Health**: `GET /api/system/health` - Component health status

### Integration with Monitoring Systems

#### Prometheus Integration
```yaml
# Add to prometheus.yml
scrape_configs:
  - job_name: 'battery-hawk'
    static_configs:
      - targets: ['localhost:5000']
    metrics_path: '/api/metrics'
    scrape_interval: 30s
```

#### Grafana Dashboard
Import the included Grafana dashboard from `monitoring/grafana-dashboard.json` for comprehensive monitoring visualization.

### Log Management

#### Structured Logging
Battery Hawk uses structured JSON logging for better log analysis:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "logger": "battery_hawk.api",
  "message": "Device reading received",
  "device_id": "AA:BB:CC:DD:EE:FF",
  "voltage": 12.5,
  "current": 2.1
}
```

#### Log Aggregation
Configure log shipping to your preferred log aggregation system:

```yaml
# For ELK Stack
logging:
  handlers:
    - type: elasticsearch
      hosts: ["localhost:9200"]
      index: battery-hawk-logs

# For Loki
logging:
  handlers:
    - type: loki
      url: http://localhost:3100/loki/api/v1/push
```

## 🔒 Security Considerations

### Production Deployment

1. **API Security**:
   - Enable API key authentication
   - Use HTTPS with proper certificates
   - Configure rate limiting appropriately
   - Implement IP whitelisting if needed

2. **Network Security**:
   - Use firewall rules to restrict access
   - Consider VPN for remote access
   - Isolate Bluetooth adapter if possible

3. **Data Security**:
   - Encrypt data at rest in InfluxDB
   - Use secure MQTT connections (TLS)
   - Regular backup of configuration and data

### Authentication Setup

```bash
# Generate API key
export API_KEY=$(openssl rand -hex 32)

# Configure authentication
curl -X PATCH http://localhost:5000/api/system/config \
  -H "Content-Type: application/vnd.api+json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "data": {
      "type": "system-config",
      "id": "current",
      "attributes": {
        "api": {
          "authentication_required": true,
          "api_key": "'$API_KEY'"
        }
      }
    }
  }'
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Quick Contribution Steps

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes** and add tests
4. **Run the test suite**: `pytest`
5. **Commit your changes**: `git commit -m 'Add amazing feature'`
6. **Push to the branch**: `git push origin feature/amazing-feature`
7. **Open a Pull Request**

### Development Guidelines

- Follow PEP 8 style guidelines
- Add tests for new functionality
- Update documentation for API changes
- Use type hints for all new code
- Write descriptive commit messages

## 📋 Roadmap

### Current Version (v1.0)
- ✅ BLE device discovery and monitoring
- ✅ REST API with comprehensive validation
- ✅ InfluxDB integration
- ✅ MQTT publishing
- ✅ Docker containerization
- ✅ Interactive API documentation

### Upcoming Features (v1.1)
- 🔄 Web dashboard UI
- 🔄 Advanced alerting system
- 🔄 Historical data analysis
- 🔄 Mobile app support
- 🔄 Multi-tenant support

### Future Enhancements (v2.0)
- 📋 Machine learning for battery health prediction
- 📋 Integration with home automation systems
- 📋 Advanced reporting and analytics
- 📋 Cloud deployment options
- 📋 Enterprise features

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Credits and Sources

- **BLE Protocol**: Based on reverse engineering of BM6/BM7 devices
- **Flask**: Web framework for the REST API
- **InfluxDB**: Time-series database for data storage
- **Docker**: Containerization platform
- **Poetry**: Python dependency management
- **Marshmallow**: Data validation and serialization
- **Swagger/OpenAPI**: API documentation

## 📚 Complete Documentation Index

### Core Documentation
- **💻 [CLI Documentation](docs/CLI.md)** - Complete command-line interface reference
- **📖 [API Documentation](docs/API.md)** - Complete REST API reference
- **🚀 [Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment scenarios
- **🔧 [Troubleshooting Guide](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **🤝 [Contributing Guide](CONTRIBUTING.md)** - Development and contribution guidelines

### Interactive Documentation
- **🌐 [Swagger UI](http://localhost:5000/api/docs/)** - Interactive API explorer (when running)
- **📋 [OpenAPI Spec](http://localhost:5000/api/docs/apispec.json)** - Machine-readable API specification

### Examples and Tutorials
- **💻 [CLI Examples](examples/cli_examples.sh)** - Comprehensive command-line usage examples
- **🌐 [Complete API Example](examples/complete_api_example.py)** - Comprehensive REST API usage examples
- **🐳 [Docker Examples](docker-compose.yml)** - Container deployment examples
- **⚙️ [Configuration Examples](config/)** - Sample configuration files

### Development Resources
- **🧪 [Testing Guide](tests/)** - Test suite and testing guidelines
- **🏗️ [Architecture Overview](src/battery_hawk/)** - Code structure and design
- **📊 [Monitoring Setup](monitoring/)** - Grafana dashboards and Prometheus config

## 📞 Support

- **📖 Documentation**: [Complete Documentation Index](#-complete-documentation-index)
- **🌐 Interactive API Docs**: [http://localhost:5000/api/docs/](http://localhost:5000/api/docs/) (when running)
- **🐛 Issues**: [GitHub Issues](https://github.com/UpDryTwist/battery-hawk/issues)
- **💬 Discussions**: [GitHub Discussions](https://github.com/UpDryTwist/battery-hawk/discussions)
- **📧 Email**: [Support Email](mailto:support@batteryhawk.com)

## ☕ Support the Project

If you find Battery Hawk useful, consider supporting the project:

[![Buy Me A Coffee](https://img.shields.io/badge/-buy_me_a%C2%A0coffee-gray?logo=buy-me-a-coffee)](https://www.buymeacoffee.com/UpDryTwist)

---

**Battery Hawk** - Keep your batteries healthy and your vehicles ready! 🔋🦅
