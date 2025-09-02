# Battery Hawk Troubleshooting Guide

This guide helps you diagnose and resolve common issues with Battery Hawk.

## 🔍 Quick Diagnostics

### System Health Check
Start with a basic health check to identify issues:

```bash
# Check API health
curl http://localhost:5000/api/health

# Get detailed system status
curl http://localhost:5000/api/system/status | jq .

# Check system health
curl http://localhost:5000/api/system/health
```

### Log Analysis
Enable debug logging for detailed troubleshooting:

```bash
# Enable debug logging via API
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

# View logs (Docker)
docker-compose logs -f battery-hawk

# View logs (systemd)
journalctl -u battery-hawk -f
```

## 🔧 Common Issues

### 1. Application Won't Start

#### Symptoms
- Container exits immediately
- "Connection refused" errors
- Import errors

#### Diagnosis
```bash
# Check container status
docker-compose ps

# View startup logs
docker-compose logs battery-hawk

# Check for port conflicts
netstat -tulpn | grep :5000
```

#### Solutions

**Port Already in Use:**
```bash
# Change port in docker-compose.yml
ports:
  - "5001:5000"  # Use different external port

# Or stop conflicting service
sudo systemctl stop service-using-port-5000
```

**Permission Issues:**
```bash
# Fix file permissions
sudo chown -R $USER:$USER .
chmod +x scripts/*.sh

# Fix Docker permissions
sudo usermod -a -G docker $USER
# Log out and back in
```

**Missing Dependencies:**
```bash
# Rebuild container
docker-compose build --no-cache
docker-compose up -d
```

### 2. Bluetooth Connection Issues

#### Symptoms
- No devices discovered
- "Bluetooth adapter not found"
- Connection timeouts

#### Diagnosis
```bash
# Check Bluetooth adapter
hciconfig
sudo hcitool lescan

# Check Bluetooth service
sudo systemctl status bluetooth

# Check permissions
groups $USER | grep bluetooth
```

#### Solutions

**Bluetooth Service Not Running:**
```bash
sudo systemctl enable bluetooth
sudo systemctl start bluetooth
sudo systemctl restart bluetooth
```

**Permission Issues:**
```bash
# Add user to bluetooth group
sudo usermod -a -G bluetooth $USER

# Set capabilities (alternative)
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(which python3)
```

**Adapter Issues:**
```bash
# Reset Bluetooth adapter
sudo hciconfig hci0 down
sudo hciconfig hci0 up

# Restart Bluetooth stack
sudo systemctl restart bluetooth
```

**Docker Bluetooth Access:**
```yaml
# In docker-compose.yml, add:
services:
  battery-hawk:
    privileged: true
    network_mode: host
    volumes:
      - /var/run/dbus:/var/run/dbus
```

### 3. Device Discovery Problems

#### Symptoms
- Devices not appearing in discovery
- "No devices found" messages
- Intermittent device detection

#### Diagnosis
```bash
# Manual device scan
sudo hcitool lescan | grep -i "BM\|battery"

# Check discovery logs
docker-compose logs battery-hawk | grep -i "discover\|scan"

# Check device status
curl http://localhost:5000/api/devices | jq .
```

#### Solutions

**Increase Scan Duration:**
```bash
curl -X PATCH http://localhost:5000/api/system/config \
  -H "Content-Type: application/vnd.api+json" \
  -d '{
    "data": {
      "type": "system-config",
      "id": "current",
      "attributes": {
        "bluetooth": {
          "scan_duration": 30
        }
      }
    }
  }'
```

**Device-Specific Issues:**
- **BM6 devices**: Ensure device is not in sleep mode
- **BM7 devices**: Check firmware version compatibility
- **Generic devices**: Verify device advertising format

**Environmental Factors:**
- Move closer to devices (< 10 meters)
- Reduce interference (WiFi, other Bluetooth devices)
- Check device battery levels

### 4. Database Connection Issues

#### Symptoms
- "InfluxDB connection failed"
- Data not being stored
- Storage health shows unhealthy

#### Diagnosis
```bash
# Check InfluxDB status
docker-compose logs influxdb

# Test InfluxDB connection
curl http://localhost:8086/health

# Check storage configuration
curl http://localhost:5000/api/system/config | jq .data.attributes.influxdb
```

#### Solutions

**InfluxDB Not Running:**
```bash
# Start InfluxDB
docker-compose up -d influxdb

# Check InfluxDB logs
docker-compose logs -f influxdb
```

**Connection Configuration:**
```bash
# Update InfluxDB settings
curl -X PATCH http://localhost:5000/api/system/config \
  -H "Content-Type: application/vnd.api+json" \
  -d '{
    "data": {
      "type": "system-config",
      "id": "current",
      "attributes": {
        "influxdb": {
          "url": "http://influxdb:8086",
          "token": "your-token",
          "org": "your-org",
          "bucket": "battery-hawk"
        }
      }
    }
  }'
```

**Database Reset (WARNING: Destroys Data):**
```bash
docker-compose down -v
docker-compose up -d
```

### 5. API Issues

#### Symptoms
- 500 Internal Server Error
- Validation errors
- Rate limiting issues

#### Diagnosis
```bash
# Check API logs
docker-compose logs battery-hawk | grep -i "api\|error"

# Test API endpoints
curl -v http://localhost:5000/api/health

# Check rate limits
curl -I http://localhost:5000/api/devices
```

#### Solutions

**Validation Errors:**
```bash
# Check request format
curl -X POST http://localhost:5000/api/devices \
  -H "Content-Type: application/vnd.api+json" \
  -d '{
    "data": {
      "type": "devices",
      "attributes": {
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "device_type": "BM6",
        "friendly_name": "Test Device"
      }
    }
  }'
```

**Rate Limiting:**
```bash
# Check rate limit headers
curl -I http://localhost:5000/api/devices

# Wait for rate limit reset or adjust limits
```

### 6. MQTT Issues

#### Symptoms
- MQTT messages not published
- Connection to broker fails
- Authentication errors

#### Diagnosis
```bash
# Check MQTT configuration
curl http://localhost:5000/api/system/config | jq .data.attributes.mqtt

# Test MQTT broker
mosquitto_pub -h localhost -t test -m "hello"

# Check MQTT logs
docker-compose logs battery-hawk | grep -i mqtt
```

#### Solutions

**Broker Connection:**
```bash
# Update MQTT settings
curl -X PATCH http://localhost:5000/api/system/config \
  -H "Content-Type: application/vnd.api+json" \
  -d '{
    "data": {
      "type": "system-config",
      "id": "current",
      "attributes": {
        "mqtt": {
          "broker": "mqtt-broker",
          "port": 1883,
          "username": "user",
          "password": "pass"
        }
      }
    }
  }'
```

## 🔍 Advanced Diagnostics

### Performance Issues

#### High CPU Usage
```bash
# Check process usage
docker stats

# Reduce scan frequency
curl -X PATCH http://localhost:5000/api/system/config \
  -H "Content-Type: application/vnd.api+json" \
  -d '{
    "data": {
      "type": "system-config",
      "id": "current",
      "attributes": {
        "discovery": {
          "scan_interval": 600
        }
      }
    }
  }'
```

#### Memory Issues
```bash
# Check memory usage
docker stats

# Reduce concurrent connections
curl -X PATCH http://localhost:5000/api/system/config \
  -H "Content-Type: application/vnd.api+json" \
  -d '{
    "data": {
      "type": "system-config",
      "id": "current",
      "attributes": {
        "bluetooth": {
          "max_concurrent_connections": 2
        }
      }
    }
  }'
```

### Network Issues

#### Container Communication
```bash
# Check Docker network
docker network ls
docker network inspect battery-hawk_default

# Test container connectivity
docker exec battery-hawk_battery-hawk_1 ping influxdb
```

#### Firewall Issues
```bash
# Check firewall rules
sudo ufw status
sudo iptables -L

# Allow API port
sudo ufw allow 5000
```

## 📊 Monitoring and Alerting

### Health Monitoring
```bash
# Continuous health check
watch -n 30 'curl -s http://localhost:5000/api/system/health | jq .data.attributes.healthy'

# Log monitoring
tail -f /var/log/battery-hawk/battery-hawk.log | grep -i error
```

### Performance Monitoring
```bash
# API response times
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:5000/api/devices

# Database performance
curl http://localhost:5000/api/system/status | jq .data.attributes.storage
```

## 🆘 Getting Help

### Information to Collect

When seeking help, please provide:

1. **System Information:**
   ```bash
   uname -a
   python3 --version
   docker --version
   docker-compose --version
   ```

2. **Application Status:**
   ```bash
   curl http://localhost:5000/api/system/status | jq .
   ```

3. **Logs:**
   ```bash
   docker-compose logs --tail=100 battery-hawk
   ```

4. **Configuration:**
   ```bash
   # Sanitized configuration (remove secrets)
   curl http://localhost:5000/api/system/config | jq .
   ```

### Support Channels

- **GitHub Issues**: [Report bugs and issues](https://github.com/UpDryTwist/battery-hawk/issues)
- **GitHub Discussions**: [Ask questions and discuss](https://github.com/UpDryTwist/battery-hawk/discussions)
- **Documentation**: [API Documentation](http://localhost:5000/api/docs/)

### Emergency Recovery

#### Complete Reset
```bash
# Stop all services
docker-compose down -v

# Remove all data (WARNING: Destroys all data)
docker system prune -a

# Restart fresh
git pull
docker-compose up -d
```

#### Backup and Restore
```bash
# Backup configuration
curl http://localhost:5000/api/system/config > config-backup.json

# Backup InfluxDB data
docker exec influxdb influx backup /backup

# Restore configuration
curl -X PATCH http://localhost:5000/api/system/config \
  -H "Content-Type: application/vnd.api+json" \
  -d @config-backup.json
```

---

For additional help, please check the [GitHub Issues](https://github.com/UpDryTwist/battery-hawk/issues) or create a new issue with detailed information about your problem.

## 📋 Troubleshooting Checklist

### Before Reporting Issues

- [ ] Checked system health: `curl http://localhost:5000/api/system/health`
- [ ] Reviewed logs with DEBUG level enabled
- [ ] Verified Bluetooth adapter is working: `hciconfig`
- [ ] Tested basic API connectivity: `curl http://localhost:5000/api/health`
- [ ] Checked Docker container status: `docker-compose ps`
- [ ] Verified configuration: `curl http://localhost:5000/api/system/config`
- [ ] Tried restarting services: `docker-compose restart`
- [ ] Checked for port conflicts: `netstat -tulpn | grep :5000`
- [ ] Verified device compatibility and proximity
- [ ] Reviewed documentation and FAQ

### Issue Report Template

```markdown
## Environment
- OS: [Ubuntu 22.04, macOS 13, etc.]
- Python: [3.12.1]
- Docker: [24.0.7]
- Battery Hawk: [v1.0.0]
- Device Model: [BM6 v2.1]

## Problem Description
[Clear description of the issue]

## Steps to Reproduce
1. [First step]
2. [Second step]
3. [Third step]

## Expected Behavior
[What should happen]

## Actual Behavior
[What actually happens]

## System Status
```json
[Output of curl http://localhost:5000/api/system/status]
```

## Logs
```
[Relevant log output with DEBUG level]
```

## Configuration
```json
[Sanitized configuration output]
```
```
