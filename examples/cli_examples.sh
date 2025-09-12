#!/bin/bash
# Battery Hawk CLI Examples
# This script demonstrates common CLI usage patterns

set -e

echo "🔋🦅 Battery Hawk CLI Examples"
echo "================================"

# Configuration directory (optional)
export BATTERYHAWK_CONFIG_DIR="/data"

echo ""
echo "📋 1. Initial Setup and Health Check"
echo "------------------------------------"

# Check system health
echo "Checking system health..."
battery-hawk system health

# Run diagnostics
echo "Running system diagnostics..."
battery-hawk system diagnose --verbose

# Check configuration
echo "Listing configuration sections..."
battery-hawk config list

echo ""
echo "🔍 2. Device Discovery and Management"
echo "------------------------------------"

# Scan for devices
# Example: Use a specific Bluetooth adapter just for this scan
# battery-hawk device scan --bluetooth-adapter hci1 --duration 10

echo "Scanning for BLE devices..."
battery-hawk device scan --duration 10 --connect --format table

# List discovered devices
echo "Listing registered devices..."
battery-hawk device list --format table

# Example: Add a device (uncomment and modify MAC address)
# echo "Adding a new device..."
# battery-hawk device add AA:BB:CC:DD:EE:FF \
#   --device-type BM6 \
#   --name "Main Battery" \
#   --polling-interval 3600

# Check device status
echo "Checking device status..."
battery-hawk device status --format table

echo ""
echo "🚗 3. Vehicle Management"
echo "------------------------"

# Add a vehicle
echo "Adding a vehicle..."
battery-hawk vehicle add my-car \
	--name "My Car" \
	--type car \
	--description "Daily driver vehicle"

# List vehicles
echo "Listing vehicles..."
battery-hawk vehicle list --format table

# Show vehicle details
echo "Showing vehicle details..."
battery-hawk vehicle show my-car --format table

# Example: Associate device with vehicle (uncomment and modify MAC address)
# echo "Associating device with vehicle..."
# battery-hawk vehicle associate my-car AA:BB:CC:DD:EE:FF

echo ""
echo "📊 4. Data Management"
echo "--------------------"

# Query recent readings
echo "Querying recent readings..."
battery-hawk data query --limit 10 --format table

# Show database statistics
echo "Showing database statistics..."
battery-hawk data stats --format table

# Example: Export data (uncomment to use)
# echo "Exporting data to CSV..."
# battery-hawk data export readings_$(date +%Y%m%d).csv \
#   --format csv \
#   --start $(date -d '7 days ago' +%Y-%m-%dT00:00:00) \
#   --end $(date +%Y-%m-%dT23:59:59)

# Example: Cleanup old data (dry run)
# echo "Checking what data would be cleaned up..."
# battery-hawk data cleanup --older-than 90d --dry-run

echo ""
echo "📡 5. MQTT Operations"
echo "--------------------"

# Check MQTT status
echo "Checking MQTT status..."
battery-hawk mqtt status

# List MQTT topics
echo "Listing MQTT topics..."
battery-hawk mqtt topics

# Example: Publish test message (uncomment to use)
# echo "Publishing test message..."
# battery-hawk mqtt publish device/test "Hello from CLI"

# Example: Monitor MQTT messages (uncomment to use)
# echo "Monitoring MQTT messages for 10 seconds..."
# battery-hawk mqtt monitor --duration 10

echo ""
echo "🔧 6. Service Management"
echo "-----------------------"

# Check service status
echo "Checking service status..."
battery-hawk service status --format table

# Example: Start services (uncomment to use)
# echo "Starting services..."
# battery-hawk service start --api --mqtt

# Example: Stop services (uncomment to use)
# echo "Stopping services..."
# battery-hawk service stop --pid-file /var/run/battery-hawk.pid

echo ""
echo "🔍 7. System Monitoring"
echo "-----------------------"

# Show system metrics
echo "Showing system metrics..."
battery-hawk system metrics --format table

# View recent logs
echo "Viewing recent logs..."
battery-hawk system logs --lines 10 --level INFO

echo ""
echo "⚙️ 8. Configuration Management"
echo "------------------------------"

# Show system configuration
echo "Showing system configuration..."
battery-hawk config show system

# Example: Set configuration value (uncomment to use)
# echo "Setting log level to INFO..."
# battery-hawk config set system logging level INFO

# Save configuration
echo "Saving system configuration..."
battery-hawk config save system

echo ""
echo "🔄 9. Automation Examples"
echo "-------------------------"

echo "Example automation scripts:"

cat <<'EOF'

# Daily health check script
#!/bin/bash
echo "Daily Battery Hawk Health Check - $(date)"
battery-hawk system health --format json > /var/log/battery-hawk-health.json
if [ $? -eq 0 ]; then
    echo "✓ System healthy"
else
    echo "✗ System issues detected"
    battery-hawk system diagnose --verbose
fi

# Weekly data export script
#!/bin/bash
WEEK_START=$(date -d '7 days ago' +%Y-%m-%dT00:00:00)
WEEK_END=$(date +%Y-%m-%dT23:59:59)
FILENAME="battery_data_week_$(date +%Y%m%d).csv"

battery-hawk data export "$FILENAME" \
  --format csv \
  --start "$WEEK_START" \
  --end "$WEEK_END"

echo "Weekly data exported to $FILENAME"

# Monthly cleanup script
#!/bin/bash
echo "Monthly data cleanup - $(date)"
battery-hawk data cleanup --older-than 90d --dry-run
read -p "Proceed with cleanup? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    battery-hawk data cleanup --older-than 90d --force
    echo "Cleanup completed"
fi

EOF

echo ""
echo "📝 10. JSON Output for Scripting"
echo "--------------------------------"

echo "Examples of using JSON output for scripting:"

# Get device count
DEVICE_COUNT=$(battery-hawk device list --format json | jq '. | length')
echo "Number of registered devices: $DEVICE_COUNT"

# Get system health status
HEALTH_STATUS=$(battery-hawk system health --format json | jq -r '.overall_status')
echo "System health status: $HEALTH_STATUS"

# Example: Check if specific device is online (uncomment and modify MAC address)
# DEVICE_STATUS=$(battery-hawk device status AA:BB:CC:DD:EE:FF --format json | jq -r '.[0].connection_state')
# echo "Device connection state: $DEVICE_STATUS"

echo ""
echo "✅ CLI Examples Complete!"
echo "========================"
echo ""
echo "For more information:"
echo "- CLI Documentation: docs/CLI.md"
echo "- API Documentation: docs/API.md"
echo "- Troubleshooting: docs/TROUBLESHOOTING.md"
echo ""
echo "Get help for any command:"
echo "  battery-hawk --help"
echo "  battery-hawk <command> --help"
echo "  battery-hawk <command> <subcommand> --help"
