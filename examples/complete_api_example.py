#!/usr/bin/env python3
"""
Complete Battery Hawk API Example.

This example demonstrates all available API endpoints including devices,
vehicles, readings, and system management.
"""

import json
from typing import Any, Dict

import requests


class BatteryHawkAPIClient:
    """Complete client for Battery Hawk API."""

    def __init__(self, base_url: str = "http://localhost:5000"):
        """
        Initialize API client.

        Args:
            base_url: Base URL of the Battery Hawk API
        """
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/vnd.api+json",
                "Accept": "application/vnd.api+json",
            }
        )

    # Health and Version endpoints
    def get_health(self) -> Dict[str, Any]:
        """Get API health status."""
        response = self.session.get(f"{self.base_url}/api/health")
        response.raise_for_status()
        return response.json()

    def get_version(self) -> Dict[str, Any]:
        """Get API version information."""
        response = self.session.get(f"{self.base_url}/api/version")
        response.raise_for_status()
        return response.json()

    # Device endpoints
    def get_devices(self) -> Dict[str, Any]:
        """Get all devices."""
        response = self.session.get(f"{self.base_url}/api/devices")
        response.raise_for_status()
        return response.json()

    def get_device(self, mac_address: str) -> Dict[str, Any]:
        """Get specific device."""
        response = self.session.get(f"{self.base_url}/api/devices/{mac_address}")
        response.raise_for_status()
        return response.json()

    # Vehicle endpoints
    def get_vehicles(self) -> Dict[str, Any]:
        """Get all vehicles."""
        response = self.session.get(f"{self.base_url}/api/vehicles")
        response.raise_for_status()
        return response.json()

    def create_vehicle(self, name: str) -> Dict[str, Any]:
        """Create a new vehicle."""
        data = {"data": {"type": "vehicles", "attributes": {"name": name}}}
        response = self.session.post(
            f"{self.base_url}/api/vehicles", data=json.dumps(data)
        )
        response.raise_for_status()
        return response.json()

    # Readings endpoints
    def get_device_readings(self, mac_address: str, limit: int = 10) -> Dict[str, Any]:
        """Get device readings."""
        response = self.session.get(
            f"{self.base_url}/api/readings/{mac_address}?limit={limit}"
        )
        response.raise_for_status()
        return response.json()

    def get_latest_reading(self, mac_address: str) -> Dict[str, Any]:
        """Get latest reading for device."""
        response = self.session.get(
            f"{self.base_url}/api/readings/{mac_address}/latest"
        )
        response.raise_for_status()
        return response.json()

    # System endpoints
    def get_system_config(self) -> Dict[str, Any]:
        """Get system configuration."""
        response = self.session.get(f"{self.base_url}/api/system/config")
        response.raise_for_status()
        return response.json()

    def get_system_status(self) -> Dict[str, Any]:
        """Get system status."""
        response = self.session.get(f"{self.base_url}/api/system/status")
        response.raise_for_status()
        return response.json()

    def get_system_health(self) -> Dict[str, Any]:
        """Get system health."""
        response = self.session.get(f"{self.base_url}/api/system/health")
        response.raise_for_status()
        return response.json()

    def update_system_config(self, **config_updates) -> Dict[str, Any]:
        """Update system configuration."""
        data = {
            "data": {
                "type": "system-config",
                "id": "current",
                "attributes": config_updates,
            }
        }
        response = self.session.patch(
            f"{self.base_url}/api/system/config", data=json.dumps(data)
        )
        response.raise_for_status()
        return response.json()


def main():
    """Main example function."""
    print("Battery Hawk Complete API Example")
    print("=" * 50)

    # Initialize API client
    client = BatteryHawkAPIClient()

    try:
        # 1. Check API health and version
        print("\n1. API Health and Version")
        print("-" * 30)

        health = client.get_health()
        print(f"   Health: {health['status']}")
        print(f"   Core Running: {health['core_running']}")

        version = client.get_version()
        print(f"   API Version: {version['api_version']}")
        print(f"   Core Version: {version['core_version']}")

        # 2. System Status and Configuration
        print("\n2. System Status and Configuration")
        print("-" * 40)

        system_health = client.get_system_health()
        print(f"   System Healthy: {system_health['data']['attributes']['healthy']}")

        system_status = client.get_system_status()
        core_status = system_status["data"]["attributes"]["core"]
        print(f"   Core Running: {core_status['running']}")
        print(f"   Active Tasks: {core_status['active_tasks']}")
        print(f"   Storage Connected: {core_status['storage_connected']}")

        components = system_status["data"]["attributes"]["components"]
        print(f"   Total Devices: {components['device_registry']['total_devices']}")
        print(
            f"   Configured Devices: {components['device_registry']['configured_devices']}"
        )
        print(f"   Total Vehicles: {components['vehicle_registry']['total_vehicles']}")

        # 3. Devices
        print("\n3. Device Management")
        print("-" * 25)

        devices = client.get_devices()
        device_count = devices["meta"]["total"]
        print(f"   Found {device_count} devices")

        if device_count > 0:
            # Show first device details
            first_device = devices["data"][0]
            mac_address = first_device["id"]
            attrs = first_device["attributes"]

            print(f"   First Device: {mac_address}")
            print(f"     Name: {attrs['friendly_name']}")
            print(f"     Type: {attrs['device_type']}")
            print(f"     Status: {attrs['status']}")
            print(f"     Vehicle: {attrs['vehicle_id'] or 'None'}")

            # 4. Device Readings
            print("\n4. Device Readings")
            print("-" * 20)

            try:
                latest_reading = client.get_latest_reading(mac_address)
                reading_attrs = latest_reading["data"]["attributes"]
                print(f"   Latest Reading for {mac_address}:")
                print(f"     Voltage: {reading_attrs['voltage']}V")
                print(f"     Current: {reading_attrs['current']}A")
                print(f"     Temperature: {reading_attrs['temperature']}°C")
                print(f"     SoC: {reading_attrs['state_of_charge']}%")
                print(f"     Power: {reading_attrs['power']}W")
                print(f"     Timestamp: {reading_attrs['timestamp']}")

                # Get historical readings
                readings = client.get_device_readings(mac_address, limit=5)
                reading_count = readings["meta"]["total"]
                print(f"   Historical Readings: {reading_count} available")

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    print(f"   No readings available for {mac_address}")
                else:
                    raise

        # 5. Vehicles
        print("\n5. Vehicle Management")
        print("-" * 25)

        vehicles = client.get_vehicles()
        vehicle_count = vehicles["meta"]["total"]
        print(f"   Found {vehicle_count} vehicles")

        for vehicle in vehicles["data"]:
            attrs = vehicle["attributes"]
            print(
                f"   Vehicle {vehicle['id']}: {attrs['name']} ({attrs['device_count']} devices)"
            )

        # 6. Configuration Management
        print("\n6. Configuration Management")
        print("-" * 35)

        config = client.get_system_config()
        config_attrs = config["data"]["attributes"]

        print(f"   Current Logging Level: {config_attrs['logging']['level']}")
        print(
            f"   Bluetooth Max Connections: {config_attrs['bluetooth']['max_concurrent_connections']}"
        )
        print(f"   API Port: {config_attrs['api']['port']}")
        print(f"   InfluxDB Enabled: {config_attrs['influxdb']['enabled']}")
        print(f"   MQTT Enabled: {config_attrs['mqtt']['enabled']}")

        # Example configuration update (commented out to avoid changing settings)
        # print("\n   Updating logging level to DEBUG...")
        # updated_config = client.update_system_config(
        #     logging={"level": "DEBUG"}
        # )
        # print(f"   New logging level: {updated_config['data']['attributes']['logging']['level']}")

        print("\n✅ Complete API example finished successfully!")
        print("\nAvailable API Endpoints:")
        print(
            "  Devices: GET /api/devices, GET /api/devices/{mac}, POST /api/devices, PATCH /api/devices/{mac}, DELETE /api/devices/{mac}"
        )
        print(
            "  Vehicles: GET /api/vehicles, GET /api/vehicles/{id}, POST /api/vehicles, PATCH /api/vehicles/{id}, DELETE /api/vehicles/{id}"
        )
        print("  Readings: GET /api/readings/{mac}, GET /api/readings/{mac}/latest")
        print(
            "  System: GET /api/system/config, PATCH /api/system/config, GET /api/system/status, GET /api/system/health"
        )
        print("  General: GET /api/health, GET /api/version")

    except requests.exceptions.ConnectionError:
        print(
            "❌ Could not connect to API server. Make sure it's running on localhost:5000"
        )
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
