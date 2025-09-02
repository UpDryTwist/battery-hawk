#!/usr/bin/env python3
"""
Example demonstrating Battery Hawk Vehicle API endpoints.

This example shows how to interact with the vehicle management API
endpoints using HTTP requests.
"""

import json
from typing import Any, Dict

import requests


class VehicleAPIClient:
    """Simple client for Battery Hawk Vehicle API."""

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

    def get_vehicles(self) -> Dict[str, Any]:
        """Get all vehicles."""
        response = self.session.get(f"{self.base_url}/api/vehicles")
        response.raise_for_status()
        return response.json()

    def get_vehicle(self, vehicle_id: str) -> Dict[str, Any]:
        """Get specific vehicle by ID."""
        response = self.session.get(f"{self.base_url}/api/vehicles/{vehicle_id}")
        response.raise_for_status()
        return response.json()

    def create_vehicle(self, name: str, custom_id: str = None) -> Dict[str, Any]:
        """Create a new vehicle."""
        data = {"data": {"type": "vehicles", "attributes": {"name": name}}}

        if custom_id:
            data["data"]["attributes"]["id"] = custom_id

        response = self.session.post(
            f"{self.base_url}/api/vehicles", data=json.dumps(data)
        )
        response.raise_for_status()
        return response.json()

    def update_vehicle(self, vehicle_id: str, **attributes) -> Dict[str, Any]:
        """Update vehicle attributes."""
        data = {
            "data": {"type": "vehicles", "id": vehicle_id, "attributes": attributes}
        }

        response = self.session.patch(
            f"{self.base_url}/api/vehicles/{vehicle_id}", data=json.dumps(data)
        )
        response.raise_for_status()
        return response.json()

    def delete_vehicle(self, vehicle_id: str) -> bool:
        """Delete a vehicle."""
        response = self.session.delete(f"{self.base_url}/api/vehicles/{vehicle_id}")
        response.raise_for_status()
        return response.status_code == 204

    def get_vehicle_devices(self, vehicle_id: str) -> Dict[str, Any]:
        """Get all devices associated with a vehicle."""
        response = self.session.get(
            f"{self.base_url}/api/vehicles/{vehicle_id}/devices"
        )
        response.raise_for_status()
        return response.json()


def main():
    """Main example function."""
    print("Battery Hawk Vehicle API Example")
    print("=" * 40)

    # Initialize API client
    client = VehicleAPIClient()

    try:
        # Check API health
        health_response = requests.get("http://localhost:5000/api/health")
        if health_response.status_code != 200:
            print("❌ API server is not running. Please start the API server first.")
            return

        print("✅ API server is running")

        print("\n1. Getting all vehicles...")
        vehicles = client.get_vehicles()
        print(f"   Found {vehicles['meta']['total']} vehicles")

        # Display existing vehicles
        for vehicle in vehicles["data"]:
            attrs = vehicle["attributes"]
            print(
                f"   - {vehicle['id']}: {attrs['name']} ({attrs['device_count']} devices)"
            )

        print("\n2. Creating a new vehicle...")
        new_vehicle = client.create_vehicle("Example Vehicle")
        vehicle_id = new_vehicle["data"]["id"]
        vehicle_name = new_vehicle["data"]["attributes"]["name"]
        print(f"   ✅ Created vehicle: {vehicle_id} ({vehicle_name})")

        print(f"\n3. Getting details for vehicle {vehicle_id}...")
        vehicle_details = client.get_vehicle(vehicle_id)
        attrs = vehicle_details["data"]["attributes"]
        print(f"   Name: {attrs['name']}")
        print(f"   Created: {attrs['created_at']}")
        print(f"   Device Count: {attrs['device_count']}")

        print("\n4. Updating vehicle name...")
        updated_vehicle = client.update_vehicle(
            vehicle_id, name="Updated Example Vehicle"
        )
        new_name = updated_vehicle["data"]["attributes"]["name"]
        print(f"   ✅ Updated vehicle name to: {new_name}")

        print(f"\n5. Getting devices for vehicle {vehicle_id}...")
        vehicle_devices = client.get_vehicle_devices(vehicle_id)
        device_count = vehicle_devices["meta"]["total"]
        print(f"   Vehicle has {device_count} associated devices")

        if device_count > 0:
            print("   Devices:")
            for device in vehicle_devices["data"]:
                device_attrs = device["attributes"]
                print(
                    f"   - {device['id']}: {device_attrs['friendly_name']} ({device_attrs['device_type']})"
                )

        print(f"\n6. Attempting to delete vehicle {vehicle_id}...")
        try:
            success = client.delete_vehicle(vehicle_id)
            if success:
                print(f"   ✅ Vehicle {vehicle_id} deleted successfully")
            else:
                print(f"   ❌ Failed to delete vehicle {vehicle_id}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 409:
                error_data = e.response.json()
                print(
                    f"   ⚠️  Cannot delete vehicle: {error_data['errors'][0]['detail']}"
                )
            else:
                raise

        print("\n7. Final vehicle count...")
        vehicles = client.get_vehicles()
        print(f"   Total vehicles: {vehicles['meta']['total']}")

        # Test creating vehicle with custom ID
        print("\n8. Creating vehicle with custom ID...")
        custom_vehicle = client.create_vehicle("Custom ID Vehicle", "my_custom_vehicle")
        custom_id = custom_vehicle["data"]["id"]
        print(f"   ✅ Created vehicle with custom ID: {custom_id}")

        # Clean up custom vehicle if it has no devices
        try:
            client.delete_vehicle(custom_id)
            print(f"   ✅ Cleaned up custom vehicle: {custom_id}")
        except requests.exceptions.HTTPError:
            print("   ⚠️  Could not clean up custom vehicle (may have devices)")

        print("\n✅ Vehicle API example completed successfully!")

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
