#!/usr/bin/env python3
"""
Example demonstrating Battery Hawk Device API endpoints.

This example shows how to interact with the device management API
endpoints using HTTP requests.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

# HTTP status codes
HTTP_OK = 200
HTTP_NO_CONTENT = 204
HTTP_NOT_FOUND = 404


class DeviceAPIClient:
    """Simple client for Battery Hawk Device API."""

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

    def get_devices(self) -> dict[str, Any]:
        """Get all devices."""
        response = self.session.get(f"{self.base_url}/api/devices")
        response.raise_for_status()
        return response.json()

    def get_device(self, mac_address: str) -> dict[str, Any]:
        """Get specific device by MAC address."""
        response = self.session.get(f"{self.base_url}/api/devices/{mac_address}")
        response.raise_for_status()
        return response.json()

    def configure_device(
        self,
        mac_address: str,
        device_type: str,
        friendly_name: str,
        vehicle_id: str | None = None,
        polling_interval: int = 3600,
    ) -> dict[str, Any]:
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
            },
        }

        if vehicle_id:
            data["data"]["attributes"]["vehicle_id"] = vehicle_id

        response = self.session.post(
            f"{self.base_url}/api/devices",
            data=json.dumps(data),
        )
        response.raise_for_status()
        return response.json()

    def update_device(self, mac_address: str, **attributes: object) -> dict[str, Any]:
        """Update device attributes."""
        data = {
            "data": {"type": "devices", "id": mac_address, "attributes": attributes},
        }

        response = self.session.patch(
            f"{self.base_url}/api/devices/{mac_address}",
            data=json.dumps(data),
        )
        response.raise_for_status()
        return response.json()

    def delete_device(self, mac_address: str) -> bool:
        """Delete a device."""
        response = self.session.delete(f"{self.base_url}/api/devices/{mac_address}")
        response.raise_for_status()
        return response.status_code == HTTP_NO_CONTENT


def main() -> None:
    """Demonstrate device API functionality."""
    # Initialize logger
    logger = logging.getLogger(__name__)

    # Initialize API client
    client = DeviceAPIClient()

    try:
        # Check API health
        health_response = requests.get("http://localhost:5000/api/health", timeout=30)
        if health_response.status_code != HTTP_OK:
            return

        # Example device data
        test_mac = "AA:BB:CC:DD:EE:FF"

        # 1) List devices and show latest fields if present
        devices = client.get_devices()
        if devices.get("data"):
            first = devices["data"][0]
            attrs = first.get("attributes", {})
            logger.info("First device: %s", first.get("id"))
            logger.info("Latest reading: %s", json.dumps(attrs.get("latest_reading")))
            logger.info("Device status: %s", json.dumps(attrs.get("device_status")))

        # If test device doesn't exist, we'll simulate it being discovered
        # In a real scenario, devices would be discovered via BLE scanning

        try:
            device = client.get_device(test_mac)
            device_exists = True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == HTTP_NOT_FOUND:
                device_exists = False
            else:
                raise

        if device_exists:
            client.update_device(
                test_mac,
                friendly_name="Updated Test Device",
                polling_interval=1800,
            )

            device = client.get_device(test_mac)
            attrs = device.get("data", {}).get("attributes", {})
            logger.info("Device %s after update", test_mac)
            logger.info("Latest reading: %s", json.dumps(attrs.get("latest_reading")))
            logger.info("Device status: %s", json.dumps(attrs.get("device_status")))

            # Uncomment to test deletion
            # logger.info("Deleting device %s...", test_mac)
            # success = client.delete_device(test_mac)
            # if success:
            #     logger.info("Device %s deleted successfully", test_mac)
        else:
            pass

        # 2) Re-list to show any updates
        devices = client.get_devices()
        logger.info("Device count: %s", devices.get("meta", {}).get("total"))

    except requests.exceptions.ConnectionError:
        pass
    except requests.exceptions.HTTPError:
        logger.exception("HTTP error")
    except Exception:
        logger.exception("Unexpected error")


if __name__ == "__main__":
    main()
