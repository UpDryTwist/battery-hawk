# Docker Deployment Guide for Battery Hawk

This comprehensive guide covers Docker deployment options for Battery Hawk, from development to production environments.

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Docker Files Overview](#docker-files-overview)
- [Development Setup](#development-setup)
- [Production Deployment](#production-deployment)
- [Configuration](#configuration)
- [Security Considerations](#security-considerations)
- [Monitoring and Health Checks](#monitoring-and-health-checks)
- [Troubleshooting](#troubleshooting)

## 🚀 Quick Start

### Development (Recommended for Testing)

```bash
# Clone repository
git clone https://github.com/UpDryTwist/battery-hawk.git
cd battery-hawk

# Copy environment template
cp .env.docker .env
# Edit .env with your settings

# Start development stack
docker-compose up -d

# View logs
docker-compose logs -f battery-hawk

# Health check
curl http://localhost:5000/api/health
```

### Production

```bash
# Use production compose file
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Or with environment file
docker-compose --env-file .env.production -f docker-compose.prod.yml up -d
```

## 📁 Docker Files Overview

### Core Files

| File | Purpose | Environment |
|------|---------|-------------|
| `Dockerfile` | Development build | Development |
| `Dockerfile.prod` | Production-optimized build | Production |
| `docker-compose.yml` | Base services configuration | All |
| `docker-compose.override.yml` | Development overrides | Development |
| `docker-compose.prod.yml` | Production configuration | Production |
| `.env.docker` | Environment template | All |

### Configuration Files

| File | Purpose |
|------|---------|
| `nginx/nginx.conf` | Reverse proxy configuration |
| `local-instance/mosquitto/config/mosquitto.conf` | MQTT broker config |

## 🛠️ Development Setup

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- Bluetooth adapter (for real device testing)

### Development Stack

The development setup includes:

- **Battery Hawk**: Main application with hot-reload
- **InfluxDB 1.8**: Time-series database
- **Mosquitto**: MQTT broker
- **Adminer**: Database administration tool
- **MQTT Client**: Testing utilities

### Starting Development Environment

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d battery-hawk

# View logs
docker-compose logs -f

# Execute commands in container
docker-compose exec battery-hawk bash

# Run tests in container
docker-compose exec battery-hawk pytest

# Stop services
docker-compose down

# Remove volumes (reset data)
docker-compose down -v
```

### Development Features

- **Hot Reload**: Source code mounted as volume
- **Debug Logging**: Enabled by default
- **Test Mode**: Bluetooth test mode available
- **Port Exposure**: API accessible on localhost:5000
- **Database Admin**: Adminer available on localhost:8080

## 🏭 Production Deployment

### Production Features

- **Optimized Images**: Multi-stage builds with minimal attack surface
- **Security Hardening**: Non-root users, read-only filesystems where possible
- **Resource Limits**: CPU and memory constraints
- **Health Checks**: Comprehensive monitoring
- **SSL/TLS**: Nginx reverse proxy with HTTPS
- **Secrets Management**: Environment-based configuration

### Production Deployment Options

#### Option 1: Docker Compose (Recommended)

```bash
# Create production environment file
cp .env.docker .env.production
# Edit .env.production with secure values

# Deploy production stack
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Monitor deployment
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs -f
```

#### Option 2: Standalone Containers

```bash
# Build production image
docker build -f Dockerfile.prod -t battery-hawk:prod .

# Run with production settings
docker run -d \
  --name battery-hawk-prod \
  --privileged \
  --network host \
  -v battery_hawk_data:/data \
  -v battery_hawk_config:/config \
  -v battery_hawk_logs:/logs \
  -v /var/run/dbus:/var/run/dbus:ro \
  -e BATTERYHAWK_LOGGING_LEVEL=INFO \
  battery-hawk:prod
```

### SSL/TLS Setup

1. **Generate SSL Certificates**:
```bash
# Self-signed (development)
mkdir -p nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/key.pem \
  -out nginx/ssl/cert.pem

# Let's Encrypt (production)
certbot certonly --standalone -d your-domain.com
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/cert.pem
cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/key.pem
```

2. **Update nginx configuration** in `nginx/nginx.conf`

3. **Enable nginx service** in production compose file

## ⚙️ Configuration

### Environment Variables

#### Application Configuration
Battery Hawk uses the `BATTERYHAWK_` prefix for all application environment variables:

```bash
# API Configuration
BATTERYHAWK_API_PORT=5000

# Logging Configuration (with timestamps)
BATTERYHAWK_LOGGING_LEVEL=INFO
BATTERYHAWK_LOGGING_FILE=/logs/battery_hawk.log
BATTERYHAWK_LOGGING_FORMAT="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
BATTERYHAWK_LOGGING_DATE_FORMAT="%Y-%m-%d %H:%M:%S"

# Database Configuration
BATTERYHAWK_INFLUXDB_HOST=influxdb
BATTERYHAWK_INFLUXDB_PORT=8086
BATTERYHAWK_INFLUXDB_DATABASE=battery_hawk

# MQTT Configuration
BATTERYHAWK_MQTT_BROKER=mqtt-broker
BATTERYHAWK_MQTT_PORT=1883
BATTERYHAWK_MQTT_TOPIC_PREFIX=battery_hawk
```

#### Port Configuration
Host port mappings can be customized through environment variables:

```bash
# Service host ports (for development/bridge networking)
API_HOST_PORT=5000              # Battery Hawk API
INFLUXDB_HOST_PORT=8086         # InfluxDB database
MQTT_HOST_PORT=1883             # MQTT broker
MQTT_WEBSOCKET_HOST_PORT=9001   # MQTT WebSocket
ADMINER_HOST_PORT=8080          # Database admin (dev only)
NGINX_HTTP_HOST_PORT=80         # Nginx HTTP (prod only)
NGINX_HTTPS_HOST_PORT=443       # Nginx HTTPS (prod only)
```

**Examples:**
```bash
# Use alternative ports to avoid conflicts
API_HOST_PORT=5001
INFLUXDB_HOST_PORT=8087
ADMINER_HOST_PORT=8081

# Start with custom ports
docker compose up -d

# Test port configuration without starting services
docker compose --env-file .env config | grep -A 2 "ports:"
```

#### Testing Port Configuration
You can verify your port configuration before starting services:

```bash
# Create test environment file
echo "API_HOST_PORT=5001
ADMINER_HOST_PORT=8081
INFLUXDB_HOST_PORT=8087" > .env.test

# Check the resolved configuration
docker compose --env-file .env.test config

# Run the custom ports example
./examples/docker_custom_ports.sh
```

### Configuration Files

Configuration files are stored in `/config` within containers:

- `system.json`: System configuration
- `devices.json`: Device registry
- `vehicles.json`: Vehicle definitions

### Volume Mapping

| Container Path | Purpose | Production Volume |
|----------------|---------|-------------------|
| `/data` | Application data | `battery_hawk_data` |
| `/config` | Configuration files | `battery_hawk_config` |
| `/logs` | Application logs | `battery_hawk_logs` |
| `/var/run/dbus` | D-Bus socket (BLE) | Host mount (read-only) |

## 🔒 Security Considerations

### Container Security

1. **Non-root Execution**: All containers run as non-root users
2. **Read-only Filesystems**: Where possible, containers use read-only root filesystems
3. **No New Privileges**: Security option prevents privilege escalation
4. **Resource Limits**: CPU and memory limits prevent resource exhaustion
5. **Minimal Attack Surface**: Production images contain only necessary components

### Network Security

1. **Reverse Proxy**: Nginx handles SSL termination and request filtering
2. **Rate Limiting**: API endpoints have rate limiting configured
3. **CORS Configuration**: Proper CORS headers for API access
4. **Security Headers**: Comprehensive security headers in responses

### Secrets Management

1. **Environment Variables**: Sensitive data via environment variables
2. **Docker Secrets**: For orchestration platforms supporting secrets
3. **External Secret Stores**: Integration with HashiCorp Vault, AWS Secrets Manager

### BLE Security Considerations

- **Privileged Mode**: Required for Bluetooth Low Energy access
- **Host Network**: Necessary for BLE adapter access
- **D-Bus Access**: Read-only access to system D-Bus

## 📊 Monitoring and Health Checks

### Health Check Endpoints

| Endpoint | Purpose | Response |
|----------|---------|----------|
| `/api/health` | Basic health check | Service status |
| `/api/system/health` | Comprehensive health | Component status |
| `/api/system/status` | System metrics | Detailed status |

### Docker Health Checks

All services include Docker health checks:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5000/api/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### Monitoring Commands

```bash
# Check container health
docker-compose ps

# View health check logs
docker inspect battery-hawk | jq '.[0].State.Health'

# Monitor resource usage
docker stats

# View application logs
docker-compose logs -f battery-hawk

# Follow health checks
watch -n 5 'curl -s http://localhost:5000/api/health | jq .'
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Bluetooth Permission Issues

```bash
# Check Bluetooth status
docker-compose exec battery-hawk hciconfig

# Verify D-Bus access
docker-compose exec battery-hawk ls -la /var/run/dbus

# Check container privileges
docker inspect battery-hawk | jq '.[0].HostConfig.Privileged'
```

#### 2. Container Startup Issues

```bash
# Check container logs
docker-compose logs battery-hawk

# Verify environment variables
docker-compose exec battery-hawk env | grep BATTERYHAWK

# Check file permissions
docker-compose exec battery-hawk ls -la /config /data /logs
```

#### 3. Network Connectivity

```bash
# Test container networking
docker-compose exec battery-hawk ping influxdb
docker-compose exec battery-hawk ping mqtt-broker

# Check port bindings
docker-compose ps
netstat -tlnp | grep :5000
```

#### 4. Health Check Failures

```bash
# Manual health check
docker-compose exec battery-hawk curl -f http://localhost:5000/api/health

# Check API logs
docker-compose logs battery-hawk | grep -i error

# Verify service dependencies
docker-compose exec battery-hawk curl http://influxdb:8086/ping
```

### Debug Mode

Enable debug logging for troubleshooting:

```bash
# Set debug environment
echo "BATTERYHAWK_LOGGING_LEVEL=DEBUG" >> .env

# Restart services
docker-compose restart battery-hawk

# View debug logs
docker-compose logs -f battery-hawk
```

### Performance Tuning

```bash
# Monitor resource usage
docker stats

# Adjust resource limits in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '2.0'

# Optimize for your hardware
```

---

For additional help, see:
- [Main Documentation](../README.md)
- [API Documentation](API.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)
- [Deployment Guide](DEPLOYMENT.md)
