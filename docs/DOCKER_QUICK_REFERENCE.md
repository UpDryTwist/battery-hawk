# Docker Quick Reference for Battery Hawk

## 🚀 Quick Commands

### Development Setup
```bash
# Start development stack
docker-compose up -d

# View logs
docker-compose logs -f battery-hawk

# Execute commands in container
docker-compose exec battery-hawk bash

# Run tests
docker-compose exec battery-hawk pytest

# Stop services
docker-compose down
```

### Production Deployment
```bash
# Start production stack
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# With environment file
docker-compose --env-file .env.production -f docker-compose.prod.yml up -d

# Check health
curl https://your-domain.com/api/health
```

### Monitoring
```bash
# Check container status
docker-compose ps

# View resource usage
docker stats

# Check health status
docker inspect battery-hawk | jq '.[0].State.Health'

# Follow logs
docker-compose logs -f
```

### Troubleshooting
```bash
# Debug mode
echo "BATTERYHAWK_LOGGING_LEVEL=DEBUG" >> .env
docker-compose restart battery-hawk

# Check Bluetooth
docker-compose exec battery-hawk hciconfig

# Test connectivity
docker-compose exec battery-hawk ping influxdb
docker-compose exec battery-hawk curl http://localhost:5000/api/health

# Reset data
docker-compose down -v
```

### Maintenance
```bash
# Update images
docker-compose pull

# Rebuild images
docker-compose build --no-cache

# Clean up
docker system prune -a

# Backup volumes
docker run --rm -v battery_hawk_data:/data -v $(pwd):/backup alpine tar czf /backup/data-backup.tar.gz -C /data .
```

## 📁 File Structure

```
battery-hawk/
├── Dockerfile                    # Development build
├── Dockerfile.prod              # Production build
├── docker-compose.yml           # Base services
├── docker-compose.override.yml  # Development overrides
├── docker-compose.prod.yml      # Production configuration
├── .env.docker                  # Environment template
├── nginx/
│   └── nginx.conf               # Reverse proxy config
└── local-instance/
    ├── data/                    # Application data
    ├── config/                  # Configuration files
    ├── logs/                    # Log files
    └── mosquitto/               # MQTT broker config
```

## 🔧 Environment Variables

### Required
```bash
BATTERYHAWK_INFLUXDB_HOST=influxdb
BATTERYHAWK_INFLUXDB_PORT=8086
BATTERYHAWK_INFLUXDB_DATABASE=battery_hawk
BATTERYHAWK_LOGGING_LEVEL=INFO
```

### Optional
```bash
BATTERYHAWK_API_PORT=5000
BATTERYHAWK_MQTT_BROKER=mqtt-broker
BATTERYHAWK_MQTT_PORT=1883
BATTERYHAWK_MQTT_TOPIC_PREFIX=battery_hawk
```

## 🏥 Health Checks

### Endpoints
- `/api/health` - Basic health check
- `/api/system/health` - Comprehensive health
- `/api/system/status` - System metrics

### Commands
```bash
# Quick health check
curl http://localhost:5000/api/health

# Detailed health
curl http://localhost:5000/api/system/health | jq .

# Container health
docker-compose ps
```

## 🔒 Security Notes

### BLE Requirements
- `privileged: true` - Required for Bluetooth access
- `network_mode: host` - Necessary for BLE adapter
- `/var/run/dbus` mount - D-Bus communication

### Production Security
- Non-root user execution
- Read-only filesystems where possible
- Resource limits configured
- Security headers in nginx
- Rate limiting enabled

## 📊 Ports

| Service | Port | Purpose |
|---------|------|---------|
| Battery Hawk | 5000 | API server |
| InfluxDB | 8086 | Database |
| MQTT | 1883 | MQTT broker |
| MQTT WebSocket | 9001 | WebSocket |
| Adminer | 8080 | DB admin (dev only) |
| Nginx | 80/443 | Reverse proxy (prod) |

## 🆘 Common Issues

### Bluetooth Not Working
```bash
# Check privileges
docker inspect battery-hawk | jq '.[0].HostConfig.Privileged'

# Verify D-Bus mount
docker-compose exec battery-hawk ls -la /var/run/dbus

# Test Bluetooth
docker-compose exec battery-hawk hciconfig
```

### Permission Errors
```bash
# Check file ownership
docker-compose exec battery-hawk ls -la /config /data /logs

# Fix permissions
docker-compose exec battery-hawk chown -R batteryhawk:batteryhawk /config /data /logs
```

### Container Won't Start
```bash
# Check logs
docker-compose logs battery-hawk

# Verify environment
docker-compose exec battery-hawk env | grep BATTERYHAWK

# Test dependencies
docker-compose exec battery-hawk ping influxdb
```

---

📖 **For complete documentation, see [Docker Deployment Guide](DOCKER.md)**
