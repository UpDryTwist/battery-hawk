#!/usr/bin/env python3
"""
Complete Battery Hawk API Example.

This example demonstrates all available API endpoints including devices,
vehicles, readings, and system management.
"""

import json
import logging
from typing import Any

import requests

# HTTP status codes
HTTP_NOT_FOUND = 404


class BatteryHawkAPIClient:
    """Complete client for Battery Hawk API."""

    def __init__(self, base_url: str = "http://localhost:5000") -> None:
        """
        Initialize API client.

        Args:
            base_url: Base URL of the Battery Hawk API
        """
        self.base_url = base_url
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)
        self.session.headers.update(
            {
                "Content-Type": "application/vnd.api+json",
                "Accept": "application/vnd.api+json",
            },
        )

    # Health and Version endpoints
    def get_health(self) -> dict[str, Any]:
        """Get API health status."""
        response = self.session.get(f"{self.base_url}/api/health")
        response.raise_for_status()
        return response.json()

    def get_version(self) -> dict[str, Any]:
        """Get API version information."""
        response = self.session.get(f"{self.base_url}/api/version")
        response.raise_for_status()
        return response.json()

    # Device endpoints
    def get_devices(self) -> dict[str, Any]:
        """Get all devices."""
        response = self.session.get(f"{self.base_url}/api/devices")
        response.raise_for_status()
        return response.json()

    def get_device(self, mac_address: str) -> dict[str, Any]:
        """Get specific device."""
        response = self.session.get(f"{self.base_url}/api/devices/{mac_address}")
        response.raise_for_status()
        return response.json()

    # Vehicle endpoints
    def get_vehicles(self) -> dict[str, Any]:
        """Get all vehicles."""
        response = self.session.get(f"{self.base_url}/api/vehicles")
        response.raise_for_status()
        return response.json()

    def create_vehicle(self, name: str) -> dict[str, Any]:
        """Create a new vehicle."""
        data = {"data": {"type": "vehicles", "attributes": {"name": name}}}
        response = self.session.post(
            f"{self.base_url}/api/vehicles",
            data=json.dumps(data),
        )
        response.raise_for_status()
        return response.json()

    # Readings endpoints
    def get_device_readings(self, mac_address: str, limit: int = 10) -> dict[str, Any]:
        """Get device readings."""
        response = self.session.get(
            f"{self.base_url}/api/readings/{mac_address}?limit={limit}",
        )
        response.raise_for_status()
        return response.json()

    def get_latest_reading(self, mac_address: str) -> dict[str, Any]:
        """Get latest reading for device."""
        response = self.session.get(
            f"{self.base_url}/api/readings/{mac_address}/latest",
        )
        response.raise_for_status()
        return response.json()

    # System endpoints
    def get_system_config(self) -> dict[str, Any]:
        """Get system configuration."""
        response = self.session.get(f"{self.base_url}/api/system/config")
        response.raise_for_status()
        return response.json()

    def get_system_status(self) -> dict[str, Any]:
        """Get system status."""
        response = self.session.get(f"{self.base_url}/api/system/status")
        response.raise_for_status()
        return response.json()

    def get_system_health(self) -> dict[str, Any]:
        """Get system health."""
        response = self.session.get(f"{self.base_url}/api/system/health")
        response.raise_for_status()
        return response.json()

    def update_system_config(self, **config_updates: object) -> dict[str, Any]:
        """Update system configuration."""
        data = {
            "data": {
                "type": "system-config",
                "id": "current",
                "attributes": config_updates,
            },
        }
        response = self.session.patch(
            f"{self.base_url}/api/system/config",
            data=json.dumps(data),
        )
        response.raise_for_status()
        return response.json()


def main() -> None:
    """Demonstrate complete API functionality."""
    # Initialize logger
    logger = logging.getLogger(__name__)

    # Initialize API client
    client = BatteryHawkAPIClient()

    try:
        # 1. Check API health and version

        client.get_health()

        client.get_version()

        # 2. System Status and Configuration

        client.get_system_health()

        system_status = client.get_system_status()
        system_status["data"]["attributes"]["core"]

        system_status["data"]["attributes"]["components"]

        # 3. Devices

        devices = client.get_devices()
        device_count = devices["meta"]["total"]

        if device_count > 0:
            # Show first device details
            first_device = devices["data"][0]
            mac_address = first_device["id"]
            attrs = first_device.get("attributes", {})
            logger.info(
                "First device latest_reading: %s",
                json.dumps(attrs.get("latest_reading")),
            )
            logger.info(
                "First device status: %s",
                json.dumps(attrs.get("device_status")),
            )

            # 4. Device Readings

            try:
                latest_reading = client.get_latest_reading(mac_address)
                latest_reading["data"]["attributes"]

                # Get historical readings
                readings = client.get_device_readings(mac_address, limit=5)
                readings["meta"]["total"]

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == HTTP_NOT_FOUND:
                    logger.warning("Device not found: %s", mac_address)
                else:
                    raise

        # 5. Vehicles

        vehicles = client.get_vehicles()
        vehicles["meta"]["total"]

        for vehicle in vehicles["data"]:
            vehicle["attributes"]

        # 6. Configuration Management

        config = client.get_system_config()
        config["data"]["attributes"]

        # Example configuration update (commented out to avoid changing settings)
        # print("\n   Updating logging level to DEBUG...")
        # updated_config = client.update_system_config(
        #     logging={"level": "DEBUG"}
        # )
        # print(f"   New logging level: {updated_config['data']['attributes']['logging']['level']}")

    except requests.exceptions.ConnectionError:
        logger.exception("Connection error")
    except requests.exceptions.HTTPError:
        logger.exception("HTTP error")
    except Exception:
        logger.exception("Unexpected error")


if __name__ == "__main__":
    main()
