#!/usr/bin/env python3
"""
Example demonstrating Battery Hawk Vehicle API endpoints.

This example shows how to interact with the vehicle management API
endpoints using HTTP requests.
"""

from __future__ import annotations

import contextlib
import json
import logging
from typing import Any

import requests

# HTTP status codes
HTTP_OK = 200
HTTP_NO_CONTENT = 204
HTTP_CONFLICT = 409


class VehicleAPIClient:
    """Simple client for Battery Hawk Vehicle API."""

    def __init__(self, base_url: str = "http://localhost:5000") -> None:
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
            },
        )

    def get_vehicles(self) -> dict[str, Any]:
        """Get all vehicles."""
        response = self.session.get(f"{self.base_url}/api/vehicles")
        response.raise_for_status()
        return response.json()

    def get_vehicle(self, vehicle_id: str) -> dict[str, Any]:
        """Get specific vehicle by ID."""
        response = self.session.get(f"{self.base_url}/api/vehicles/{vehicle_id}")
        response.raise_for_status()
        return response.json()

    def create_vehicle(
        self,
        name: str,
        custom_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new vehicle."""
        data = {"data": {"type": "vehicles", "attributes": {"name": name}}}

        if custom_id:
            data["data"]["attributes"]["id"] = custom_id

        response = self.session.post(
            f"{self.base_url}/api/vehicles",
            data=json.dumps(data),
        )
        response.raise_for_status()
        return response.json()

    def update_vehicle(self, vehicle_id: str, **attributes: Any) -> dict[str, Any]:
        """Update vehicle attributes."""
        data = {
            "data": {"type": "vehicles", "id": vehicle_id, "attributes": attributes},
        }

        response = self.session.patch(
            f"{self.base_url}/api/vehicles/{vehicle_id}",
            data=json.dumps(data),
        )
        response.raise_for_status()
        return response.json()

    def delete_vehicle(self, vehicle_id: str) -> bool:
        """Delete a vehicle."""
        response = self.session.delete(f"{self.base_url}/api/vehicles/{vehicle_id}")
        response.raise_for_status()
        return response.status_code == HTTP_NO_CONTENT

    def get_vehicle_devices(self, vehicle_id: str) -> dict[str, Any]:
        """Get all devices associated with a vehicle."""
        response = self.session.get(
            f"{self.base_url}/api/vehicles/{vehicle_id}/devices",
        )
        response.raise_for_status()
        return response.json()


def main() -> None:
    """Run main example function."""
    # Initialize API client
    client = VehicleAPIClient()

    try:
        # Check API health
        health_response = requests.get("http://localhost:5000/api/health", timeout=10)
        if health_response.status_code != HTTP_OK:
            return

        vehicles = client.get_vehicles()

        # Display existing vehicles
        for vehicle in vehicles["data"]:
            vehicle["attributes"]

        new_vehicle = client.create_vehicle("Example Vehicle")
        vehicle_id = new_vehicle["data"]["id"]
        new_vehicle["data"]["attributes"]["name"]

        vehicle_details = client.get_vehicle(vehicle_id)
        vehicle_details["data"]["attributes"]

        updated_vehicle = client.update_vehicle(
            vehicle_id,
            name="Updated Example Vehicle",
        )
        updated_vehicle["data"]["attributes"]["name"]

        vehicle_devices = client.get_vehicle_devices(vehicle_id)
        device_count = vehicle_devices["meta"]["total"]

        if device_count > 0:
            for device in vehicle_devices["data"]:
                device["attributes"]

        try:
            success = client.delete_vehicle(vehicle_id)
            if success:
                pass
            else:
                pass
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == HTTP_CONFLICT:
                e.response.json()
            else:
                raise

        vehicles = client.get_vehicles()

        # Test creating vehicle with custom ID
        custom_vehicle = client.create_vehicle("Custom ID Vehicle", "my_custom_vehicle")
        custom_id = custom_vehicle["data"]["id"]

        # Clean up custom vehicle if it has no devices
        with contextlib.suppress(requests.exceptions.HTTPError):
            client.delete_vehicle(custom_id)

    except requests.exceptions.ConnectionError:
        pass
    except requests.exceptions.HTTPError:
        logger = logging.getLogger(__name__)
        logger.exception("HTTP error occurred")
    except requests.exceptions.RequestException:
        logger = logging.getLogger(__name__)
        logger.exception("Request error occurred")


if __name__ == "__main__":
    main()
