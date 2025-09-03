# Battery Hawk Deployment Guide

This guide covers various deployment scenarios for Battery Hawk, from development to production environments.

## 🚀 Deployment Options

### 1. Docker Compose (Recommended)
Best for most use cases, provides complete stack with dependencies.

### 2. Standalone Docker
For custom container orchestration or existing infrastructure.

### 3. Systemd Service
For direct installation on Linux systems.

### 4. Kubernetes
For scalable, cloud-native deployments.

## 🐳 Docker Compose Deployment

### Quick Start
```bash
# Clone repository
git clone https://github.com/UpDryTwist/battery-hawk.git
cd battery-hawk

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start services
docker-compose up -d

# Verify deployment
curl http://localhost:5000/api/health
```

### Production Configuration

#### Environment Variables (.env)
```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=5000
API_WORKERS=4

# Security
API_KEY=your-secure-api-key-here
CORS_ORIGINS=https://yourdomain.com

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/battery-hawk/battery-hawk.log

# Database
INFLUXDB_ENABLED=true
INFLUXDB_URL=http://influxdb:8086
INFLUXDB_TOKEN=your-influxdb-token
INFLUXDB_ORG=your-organization
INFLUXDB_BUCKET=battery-hawk
INFLUXDB_RETENTION=30d

# MQTT
MQTT_ENABLED=true
MQTT_BROKER=mqtt-broker
MQTT_PORT=1883
MQTT_USERNAME=battery-hawk
MQTT_PASSWORD=secure-password
MQTT_TLS=true

# Bluetooth
BLUETOOTH_MAX_CONNECTIONS=5
BLUETOOTH_SCAN_DURATION=10
```

#### Production Docker Compose
```yaml
version: '3.8'

services:
  battery-hawk:
    build:
      context: .
      dockerfile: Dockerfile.prod
    restart: unless-stopped
    privileged: true
    network_mode: host
    environment:
      - LOG_LEVEL=INFO
      - API_KEY=${API_KEY}
    volumes:
      - ./config:/app/config:ro
      - ./logs:/var/log/battery-hawk
      - /var/run/dbus:/var/run/dbus:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  influxdb:
    image: influxdb:2.7
    restart: unless-stopped
    ports:
      - "8086:8086"
    environment:
      - INFLUXDB_DB=battery-hawk
      - INFLUXDB_ADMIN_USER=admin
      - INFLUXDB_ADMIN_PASSWORD=${INFLUXDB_ADMIN_PASSWORD}
    volumes:
      - influxdb_data:/var/lib/influxdb2
      - ./influxdb/config:/etc/influxdb2
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8086/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  mqtt:
    image: eclipse-mosquitto:2.0
    restart: unless-stopped
    ports:
      - "1883:1883"
      - "9001:9001"
    volumes:
      - ./mqtt/config:/mosquitto/config
      - ./mqtt/data:/mosquitto/data
      - ./mqtt/log:/mosquitto/log
    healthcheck:
      test: ["CMD", "mosquitto_pub", "-h", "localhost", "-t", "test", "-m", "health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - battery-hawk

volumes:
  influxdb_data:
```

### SSL/TLS Configuration

#### Nginx Configuration (nginx/nginx.conf)
```nginx
events {
    worker_connections 1024;
}

http {
    upstream battery-hawk {
        server localhost:5000;
    }

    server {
        listen 80;
        server_name yourdomain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name yourdomain.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!annul:!MD5;

        location / {
            proxy_pass http://battery-hawk;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /api/docs/ {
            proxy_pass http://battery-hawk;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
```

## 🔧 Standalone Docker Deployment

### Build Custom Image
```bash
# Build production image
docker build -t battery-hawk:latest -f Dockerfile.prod .

# Run with custom configuration
docker run -d \
  --name battery-hawk \
  --privileged \
  --network host \
  -v $(pwd)/config:/app/config:ro \
  -v $(pwd)/logs:/var/log/battery-hawk \
  -v /var/run/dbus:/var/run/dbus:ro \
  -e LOG_LEVEL=INFO \
  -e API_KEY=your-api-key \
  battery-hawk:latest
```

### Health Monitoring
```bash
# Health check script
#!/bin/bash
if curl -f http://localhost:5000/api/health > /dev/null 2>&1; then
    echo "Battery Hawk is healthy"
    exit 0
else
    echo "Battery Hawk is unhealthy"
    exit 1
fi
```

## 🖥️ Systemd Service Deployment

### Installation
```bash
# Create user
sudo useradd -r -s /bin/false battery-hawk
sudo usermod -a -G bluetooth battery-hawk

# Install application
sudo mkdir -p /opt/battery-hawk
sudo cp -r . /opt/battery-hawk/
sudo chown -R battery-hawk:battery-hawk /opt/battery-hawk

# Install dependencies
cd /opt/battery-hawk
sudo -u battery-hawk poetry install --only=main
```

### Service Configuration
```ini
# /etc/systemd/system/battery-hawk.service
[Unit]
Description=Battery Hawk Monitoring Service
After=network.target bluetooth.service
Wants=bluetooth.service

[Service]
Type=simple
User=battery-hawk
Group=battery-hawk
WorkingDirectory=/opt/battery-hawk
Environment=PATH=/opt/battery-hawk/.venv/bin
ExecStart=/opt/battery-hawk/.venv/bin/python -m battery_hawk
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/battery-hawk /opt/battery-hawk/data

[Install]
WantedBy=multi-user.target
```

### Service Management
```bash
# Enable and start service
sudo systemctl enable battery-hawk
sudo systemctl start battery-hawk

# Check status
sudo systemctl status battery-hawk

# View logs
sudo journalctl -u battery-hawk -f
```

## ☸️ Kubernetes Deployment

### Namespace and ConfigMap
```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: battery-hawk

---
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: battery-hawk-config
  namespace: battery-hawk
data:
  config.yaml: |
    api:
      host: "0.0.0.0"
      port: 5000
    logging:
      level: "INFO"
    bluetooth:
      max_concurrent_connections: 5
    influxdb:
      enabled: true
      url: "http://influxdb:8086"
```

### Deployment
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: battery-hawk
  namespace: battery-hawk
spec:
  replicas: 1
  selector:
    matchLabels:
      app: battery-hawk
  template:
    metadata:
      labels:
        app: battery-hawk
    spec:
      containers:
      - name: battery-hawk
        image: battery-hawk:latest
        ports:
        - containerPort: 5000
        env:
        - name: LOG_LEVEL
          value: "INFO"
        volumeMounts:
        - name: config
          mountPath: /app/config
        - name: dbus
          mountPath: /var/run/dbus
        securityContext:
          privileged: true
        livenessProbe:
          httpGet:
            path: /api/health
            port: 5000
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /api/health
            port: 5000
          initialDelaySeconds: 5
          periodSeconds: 10
      volumes:
      - name: config
        configMap:
          name: battery-hawk-config
      - name: dbus
        hostPath:
          path: /var/run/dbus
      nodeSelector:
        bluetooth: "true"
```

### Service and Ingress
```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: battery-hawk
  namespace: battery-hawk
spec:
  selector:
    app: battery-hawk
  ports:
  - port: 80
    targetPort: 5000
  type: ClusterIP

---
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: battery-hawk
  namespace: battery-hawk
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - battery-hawk.yourdomain.com
    secretName: battery-hawk-tls
  rules:
  - host: battery-hawk.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: battery-hawk
            port:
              number: 80
```

## 🔒 Security Hardening

### API Security
```bash
# Generate secure API key
openssl rand -hex 32

# Configure authentication
export API_KEY="your-generated-key"

# Use HTTPS only
export FORCE_HTTPS=true
```

### Network Security
```bash
# Firewall configuration
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 5000/tcp  # Block direct API access
sudo ufw enable
```

### Container Security
```yaml
# Security context in Docker Compose
security_opt:
  - no-new-privileges:true
  - seccomp:unconfined
read_only: true
tmpfs:
  - /tmp
  - /var/tmp
```

## 📊 Monitoring Setup

### Prometheus Configuration
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'battery-hawk'
    static_configs:
      - targets: ['battery-hawk:5000']
    metrics_path: '/api/metrics'
    scrape_interval: 30s
```

### Grafana Dashboard
```json
{
  "dashboard": {
    "title": "Battery Hawk Monitoring",
    "panels": [
      {
        "title": "System Health",
        "type": "stat",
        "targets": [
          {
            "expr": "battery_hawk_health_status"
          }
        ]
      }
    ]
  }
}
```

## 🔄 Backup and Recovery

### Configuration Backup
```bash
# Backup configuration
kubectl get configmap battery-hawk-config -o yaml > config-backup.yaml

# Backup secrets
kubectl get secret battery-hawk-secrets -o yaml > secrets-backup.yaml
```

### Data Backup
```bash
# InfluxDB backup
docker exec influxdb influx backup /backup
docker cp influxdb:/backup ./influxdb-backup

# Restore
docker cp ./influxdb-backup influxdb:/restore
docker exec influxdb influx restore /restore
```

## 🚀 Scaling Considerations

### Horizontal Scaling
- Use load balancer for multiple API instances
- Shared storage for configuration
- Centralized logging and monitoring

### Performance Tuning
- Adjust worker processes based on CPU cores
- Optimize database connection pooling
- Configure appropriate rate limits

---

For production deployments, always test thoroughly in a staging environment first.
