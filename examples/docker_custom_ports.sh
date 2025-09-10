#!/bin/bash
# Example: Running Battery Hawk with custom ports
# This script demonstrates how to use custom ports to avoid conflicts

set -e

echo "🐳 Battery Hawk - Custom Ports Example"
echo "======================================"

# Check if Docker Compose is available
if ! command -v docker &>/dev/null; then
	echo "❌ Docker is not installed or not in PATH"
	exit 1
fi

if ! docker compose version &>/dev/null; then
	echo "❌ Docker Compose is not available"
	exit 1
fi

# Create custom environment file
echo "📝 Creating custom environment configuration..."
cat >.env.custom <<EOF
# Custom port configuration to avoid conflicts
API_HOST_PORT=5001
INFLUXDB_HOST_PORT=8087
MQTT_HOST_PORT=1884
MQTT_WEBSOCKET_HOST_PORT=9002
ADMINER_HOST_PORT=8081

# Application configuration
BATTERYHAWK_SYSTEM_LOGGING_LEVEL=INFO
BATTERYHAWK_SYSTEM_INFLUXDB_HOST=influxdb
BATTERYHAWK_SYSTEM_INFLUXDB_PORT=8086
BATTERYHAWK_SYSTEM_INFLUXDB_DATABASE=battery_hawk
BATTERYHAWK_SYSTEM_MQTT_BROKER=mqtt-broker
BATTERYHAWK_SYSTEM_MQTT_PORT=1883
BATTERYHAWK_SYSTEM_MQTT_TOPIC_PREFIX=battery_hawk
EOF

echo "✅ Custom environment file created: .env.custom"
echo ""
echo "📋 Custom port mappings:"
echo "  - Battery Hawk API: http://localhost:5001"
echo "  - InfluxDB: http://localhost:8087"
echo "  - MQTT Broker: localhost:1884"
echo "  - MQTT WebSocket: localhost:9002"
echo "  - Adminer (DB Admin): http://localhost:8081"
echo ""

# Start services with custom environment
echo "🚀 Starting Battery Hawk with custom ports..."
docker compose --env-file .env.custom up -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 10

# Check service health
echo "🏥 Checking service health..."

# Check API health
if curl -f -s http://localhost:5001/api/health >/dev/null; then
	echo "✅ Battery Hawk API is healthy (port 5001)"
else
	echo "❌ Battery Hawk API is not responding (port 5001)"
fi

# Check InfluxDB
if curl -f -s http://localhost:8087/ping >/dev/null; then
	echo "✅ InfluxDB is healthy (port 8087)"
else
	echo "❌ InfluxDB is not responding (port 8087)"
fi

# Check Adminer
if curl -f -s http://localhost:8081 >/dev/null; then
	echo "✅ Adminer is healthy (port 8081)"
else
	echo "❌ Adminer is not responding (port 8081)"
fi

echo ""
echo "🎉 Battery Hawk is running with custom ports!"
echo ""
echo "📖 Access URLs:"
echo "  - API Health Check: curl http://localhost:5001/api/health"
echo "  - API Documentation: http://localhost:5001/api/docs/"
echo "  - Database Admin: http://localhost:8081"
echo "  - InfluxDB: http://localhost:8087"
echo ""
echo "🛑 To stop services:"
echo "  docker compose --env-file .env.custom down"
echo ""
echo "📊 To view logs:"
echo "  docker compose --env-file .env.custom logs -f"
echo ""
echo "🔧 To view running containers:"
echo "  docker compose --env-file .env.custom ps"
