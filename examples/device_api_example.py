#!/usr/bin/env python3
"""
Example demonstrating Battery Hawk Device API endpoints.

This example shows how to interact with the device management API
endpoints using HTTP requests.
"""

import json
from typing import Any, Dict

import requests


class DeviceAPIClient:
    """Simple client for Battery Hawk Device API."""

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

    def get_devices(self) -> Dict[str, Any]:
        """Get all devices."""
        response = self.session.get(f"{self.base_url}/api/devices")
        response.raise_for_status()
        return response.json()

    def get_device(self, mac_address: str) -> Dict[str, Any]:
        """Get specific device by MAC address."""
        response = self.session.get(f"{self.base_url}/api/devices/{mac_address}")
        response.raise_for_status()
        return response.json()

    def configure_device(
        self,
        mac_address: str,
        device_type: str,
        friendly_name: str,
        vehicle_id: str = None,
        polling_interval: int = 3600,
    ) -> Dict[str, Any]:
        """Configure a device."""
        data = {
            "data": {
                "type": "devices",
                "attributes": {
                    "mac_address": mac_address,
                    "device_type": device_type,
                    "friendly_name": friendly_name,
                    "polling_interval": polling_interval,
                },
            }
        }

        if vehicle_id:
            data["data"]["attributes"]["vehicle_id"] = vehicle_id

        response = self.session.post(
            f"{self.base_url}/api/devices", data=json.dumps(data)
        )
        response.raise_for_status()
        return response.json()

    def update_device(self, mac_address: str, **attributes) -> Dict[str, Any]:
        """Update device attributes."""
        data = {
            "data": {"type": "devices", "id": mac_address, "attributes": attributes}
        }

        response = self.session.patch(
            f"{self.base_url}/api/devices/{mac_address}", data=json.dumps(data)
        )
        response.raise_for_status()
        return response.json()

    def delete_device(self, mac_address: str) -> bool:
        """Delete a device."""
        response = self.session.delete(f"{self.base_url}/api/devices/{mac_address}")
        response.raise_for_status()
        return response.status_code == 204


def main():
    """Main example function."""
    print("Battery Hawk Device API Example")
    print("=" * 40)

    # Initialize API client
    client = DeviceAPIClient()

    try:
        # Check API health
        health_response = requests.get("http://localhost:5000/api/health")
        if health_response.status_code != 200:
            print("❌ API server is not running. Please start the API server first.")
            return

        print("✅ API server is running")

        # Example device data
        test_mac = "AA:BB:CC:DD:EE:FF"

        print("\n1. Getting all devices...")
        devices = client.get_devices()
        print(f"   Found {devices['meta']['total']} devices")

        # If test device doesn't exist, we'll simulate it being discovered
        # In a real scenario, devices would be discovered via BLE scanning

        print(f"\n2. Checking if test device {test_mac} exists...")
        try:
            device = client.get_device(test_mac)
            print(
                f"   ✅ Device found: {device['data']['attributes']['friendly_name']}"
            )
            device_exists = True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"   ❌ Device {test_mac} not found")
                device_exists = False
            else:
                raise

        if device_exists:
            print(f"\n3. Updating device {test_mac}...")
            updated_device = client.update_device(
                test_mac, friendly_name="Updated Test Device", polling_interval=1800
            )
            print(
                f"   ✅ Updated device: {updated_device['data']['attributes']['friendly_name']}"
            )
            print(
                f"   ✅ New polling interval: {updated_device['data']['attributes']['polling_interval']}s"
            )

            print("\n4. Getting updated device details...")
            device = client.get_device(test_mac)
            attrs = device["data"]["attributes"]
            print(f"   Device Type: {attrs['device_type']}")
            print(f"   Friendly Name: {attrs['friendly_name']}")
            print(f"   Status: {attrs['status']}")
            print(f"   Vehicle ID: {attrs['vehicle_id']}")
            print(f"   Polling Interval: {attrs['polling_interval']}s")

            # Uncomment to test deletion
            # print(f"\n5. Deleting device {test_mac}...")
            # success = client.delete_device(test_mac)
            # if success:
            #     print(f"   ✅ Device {test_mac} deleted successfully")
        else:
            print(
                "\n   Note: To test device configuration, first discover the device via BLE scanning"
            )
            print("   or manually add it to the device registry.")

        print("\n6. Final device count...")
        devices = client.get_devices()
        print(f"   Total devices: {devices['meta']['total']}")

        print("\n✅ Device API example completed successfully!")

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
