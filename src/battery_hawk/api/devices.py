"""
Device-related API endpoints for Battery Hawk.

This module implements all device management endpoints following JSON-API
specification for consistent data formatting and error handling.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Coroutine

from flasgger import swag_from
from flask import Flask, request

if TYPE_CHECKING:
    from battery_hawk.core.engine import BatteryHawkCore

from .schemas import DeviceConfigurationSchema, PaginationQuerySchema
from .validation import (
    format_error_response,
    handle_api_errors,
    require_content_type,
    validate_json_request,
    validate_query_params,
)

logger = logging.getLogger("battery_hawk.api.devices")


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """
    Run an async coroutine in a sync context.

    Args:
        coro: Coroutine to run

    Returns:
        Result of the coroutine
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an event loop, we need to use a different approach
            # This is a simplified version - in production you might want to use
            # asyncio.create_task() or similar
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(coro)


class DeviceValidationError(Exception):
    """Exception raised for device validation errors."""

    def __init__(self, message: str, field: str | None = None) -> None:
        """
        Initialize DeviceValidationError.

        Args:
            message: Error message
            field: Field that caused the validation error
        """
        super().__init__(message)
        self.message = message
        self.field = field


def validate_device_data(
    data: dict[str, Any],
    required_fields: list[str] | None = None,
) -> None:
    """
    Validate device data according to JSON-API specification.

    Args:
        data: Device data to validate
        required_fields: List of required fields

    Raises:
        DeviceValidationError: If validation fails
    """
    if not isinstance(data, dict):
        raise DeviceValidationError("Request data must be an object")

    if "data" not in data:
        raise DeviceValidationError("Request must contain 'data' member")

    resource = data["data"]
    if not isinstance(resource, dict):
        raise DeviceValidationError("Data member must be an object")

    if "type" not in resource:
        raise DeviceValidationError("Resource must contain 'type' member")

    if resource["type"] != "devices":
        raise DeviceValidationError("Resource type must be 'devices'")

    # Validate required fields if specified
    if required_fields:
        attributes = resource.get("attributes", {})
        for field in required_fields:
            if field not in attributes:
                raise DeviceValidationError(f"Missing required field: {field}", field)


def format_device_resource(
    device_data: dict[str, Any],
    mac_address: str,
) -> dict[str, Any]:
    """
    Format device data as JSON-API resource object.

    Args:
        device_data: Raw device data from registry
        mac_address: Device MAC address

    Returns:
        JSON-API formatted resource object
    """
    return {
        "type": "devices",
        "id": mac_address,
        "attributes": {
            "mac_address": device_data.get("mac_address", mac_address),
            "device_type": device_data.get("device_type", "unknown"),
            "friendly_name": device_data.get("friendly_name", f"Device_{mac_address}"),
            "vehicle_id": device_data.get("vehicle_id"),
            "status": device_data.get("status", "discovered"),
            "discovered_at": device_data.get("discovered_at"),
            "configured_at": device_data.get("configured_at"),
            "polling_interval": device_data.get("polling_interval", 3600),
            "connection_config": device_data.get("connection_config", {}),
            # Expose latest reading and runtime device status if present
            "latest_reading": device_data.get("latest_reading"),
            "last_reading_time": device_data.get("last_reading_time"),
            "device_status": device_data.get("device_status"),
            "last_status_update": device_data.get("last_status_update"),
        },
        "links": {"self": f"/api/devices/{mac_address}"},
        "relationships": {
            "vehicle": {
                "links": {
                    "self": f"/api/devices/{mac_address}/relationships/vehicle",
                    "related": f"/api/devices/{mac_address}/vehicle",
                },
                "data": {"type": "vehicles", "id": device_data.get("vehicle_id")}
                if device_data.get("vehicle_id")
                else None,
            },
        },
    }


def setup_device_routes(app: Flask, core_engine: BatteryHawkCore) -> None:  # noqa: PLR0915
    """
    Set up device-related API routes.

    Args:
        app: Flask application instance
        core_engine: Core engine instance
    """

    @app.route("/api/devices", methods=["GET"])
    @validate_query_params(PaginationQuerySchema)
    @handle_api_errors
    @swag_from(
        {
            "tags": ["Devices"],
            "summary": "Get all devices",
            "description": "Retrieve a list of all battery monitoring devices",
            "parameters": [
                {
                    "name": "limit",
                    "in": "query",
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 1000,
                    "default": 100,
                    "description": "Maximum number of devices to return",
                },
                {
                    "name": "offset",
                    "in": "query",
                    "type": "integer",
                    "minimum": 0,
                    "default": 0,
                    "description": "Number of devices to skip for pagination",
                },
            ],
            "responses": {
                "200": {
                    "description": "List of devices",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "data": {
                                "type": "array",
                                "items": {"$ref": "#/definitions/DeviceResource"},
                            },
                            "meta": {
                                "type": "object",
                                "properties": {
                                    "total": {"type": "integer"},
                                    "limit": {"type": "integer"},
                                    "offset": {"type": "integer"},
                                },
                            },
                        },
                    },
                },
            },
        },
    )
    def get_devices(validated_params: dict[str, Any]) -> tuple[dict[str, Any], int]:  # noqa: ARG001
        """
        Get all devices.

        Args:
            validated_params: Validated query parameters

        Returns:
            JSON-API formatted response with all devices
        """
        try:
            # Get all devices from registry
            devices = core_engine.device_registry.devices

            # Format as JSON-API resource collection
            data = []
            for mac_address, device_data in devices.items():
                data.append(format_device_resource(device_data, mac_address))

            response = {
                "data": data,
                "meta": {"total": len(data)},
                "links": {"self": "/api/devices"},
            }

        except Exception as e:
            logger.exception("Error retrieving devices")
            return format_error_response(f"Internal server error: {e!s}", 500)
        else:
            logger.info("Retrieved %d devices", len(data))
            return response, 200

    @app.route("/api/devices/<mac_address>", methods=["GET"])
    def get_device(mac_address: str) -> tuple[dict[str, Any], int]:
        """
        Get specific device by MAC address.

        Args:
            mac_address: Device MAC address

        Returns:
            JSON-API formatted response with device data
        """
        try:
            # Get device from registry
            device_data = core_engine.device_registry.get_device(mac_address)

            if not device_data:
                return format_error_response(f"Device {mac_address} not found", 404)

            response = {
                "data": format_device_resource(device_data, mac_address),
                "links": {"self": f"/api/devices/{mac_address}"},
            }

        except Exception as e:
            logger.exception("Error retrieving device %s", mac_address)
            return format_error_response(f"Internal server error: {e!s}", 500)
        else:
            logger.debug("Retrieved device: %s", mac_address)
            return response, 200

    @app.route("/api/devices", methods=["POST"])
    @require_content_type("application/vnd.api+json")
    @validate_json_request(DeviceConfigurationSchema)
    @handle_api_errors
    @swag_from(
        {
            "tags": ["Devices"],
            "summary": "Configure a device",
            "description": "Configure a discovered device for monitoring",
            "consumes": ["application/vnd.api+json"],
            "parameters": [
                {
                    "name": "body",
                    "in": "body",
                    "required": True,
                    "schema": {
                        "type": "object",
                        "required": ["data"],
                        "properties": {
                            "data": {
                                "type": "object",
                                "required": ["type", "attributes"],
                                "properties": {
                                    "type": {"type": "string", "enum": ["devices"]},
                                    "attributes": {
                                        "$ref": "#/definitions/DeviceAttributes",
                                    },
                                },
                            },
                        },
                    },
                },
            ],
            "responses": {
                "201": {
                    "description": "Device configured successfully",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "data": {"$ref": "#/definitions/DeviceResource"},
                        },
                    },
                },
                "400": {"$ref": "#/responses/400"},
                "404": {"$ref": "#/responses/404"},
                "409": {"$ref": "#/responses/409"},
            },
        },
    )
    def configure_device(validated_data: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """
        Configure a new device.

        Args:
            validated_data: Validated request data

        Returns:
            JSON-API formatted response with configured device data
        """
        try:
            # Extract validated attributes
            attributes = validated_data["data"]["attributes"]
            mac_address = attributes["mac_address"]
            device_type = attributes["device_type"]
            friendly_name = attributes["friendly_name"]
            vehicle_id = attributes.get("vehicle_id")
            polling_interval = attributes.get("polling_interval", 3600)

            # Check if device exists
            existing_device = core_engine.device_registry.get_device(mac_address)
            if not existing_device:
                return format_error_response(
                    f"Device {mac_address} not found. Device must be discovered first.",
                    404,
                )

            # Configure the device
            success = run_async(
                core_engine.device_registry.configure_device(
                    mac_address=mac_address,
                    device_type=device_type,
                    friendly_name=friendly_name,
                    vehicle_id=vehicle_id,
                    polling_interval=polling_interval,
                ),
            )

            if not success:
                return format_error_response(
                    f"Failed to configure device {mac_address}",
                    500,
                )

            # Get updated device data
            updated_device = core_engine.device_registry.get_device(mac_address)
            if updated_device is None:
                return format_error_response(
                    f"Device {mac_address} not found after configuration",
                    404,
                )

            response = {
                "data": format_device_resource(updated_device, mac_address),
                "links": {"self": f"/api/devices/{mac_address}"},
            }

        except DeviceValidationError as e:
            return format_error_response(e.message, 400, e.field)
        except Exception as e:
            logger.exception("Error configuring device")
            return format_error_response(f"Internal server error: {e!s}", 500)
        else:
            logger.info("Configured device: %s as %s", mac_address, device_type)
            return response, 200

    @app.route("/api/devices/<mac_address>", methods=["PATCH"])
    def update_device(mac_address: str) -> tuple[dict[str, Any], int]:  # noqa: PLR0911
        """
        Update an existing device.

        Args:
            mac_address: Device MAC address

        Returns:
            JSON-API formatted response with updated device data
        """
        try:
            # Check if device exists
            existing_device = core_engine.device_registry.get_device(mac_address)
            if not existing_device:
                return format_error_response(f"Device {mac_address} not found", 404)

            # Validate request data
            request_data = request.get_json()
            if not request_data:
                return format_error_response("Request body must contain JSON data", 400)

            validate_device_data(request_data)

            resource = request_data["data"]

            # Validate resource ID matches URL parameter
            if "id" in resource and resource["id"] != mac_address:
                return format_error_response(
                    "Resource ID must match URL parameter",
                    409,
                )

            attributes = resource.get("attributes", {})

            # Extract update fields (only update provided fields)
            device_type = attributes.get(
                "device_type",
                existing_device.get("device_type"),
            )
            friendly_name = attributes.get(
                "friendly_name",
                existing_device.get("friendly_name"),
            )
            vehicle_id = attributes.get("vehicle_id", existing_device.get("vehicle_id"))
            polling_interval = attributes.get(
                "polling_interval",
                existing_device.get("polling_interval", 3600),
            )

            # Update the device
            success = run_async(
                core_engine.device_registry.configure_device(
                    mac_address=mac_address,
                    device_type=device_type,
                    friendly_name=friendly_name,
                    vehicle_id=vehicle_id,
                    polling_interval=polling_interval,
                ),
            )

            if not success:
                return format_error_response(
                    f"Failed to update device {mac_address}",
                    500,
                )

            # Get updated device data
            updated_device = core_engine.device_registry.get_device(mac_address)
            if updated_device is None:
                return format_error_response(
                    f"Device {mac_address} not found after update",
                    404,
                )

            response = {
                "data": format_device_resource(updated_device, mac_address),
                "links": {"self": f"/api/devices/{mac_address}"},
            }

        except DeviceValidationError as e:
            return format_error_response(e.message, 400, e.field)
        except Exception as e:
            logger.exception("Error updating device %s", mac_address)
            return format_error_response(f"Internal server error: {e!s}", 500)
        else:
            logger.info("Updated device: %s", mac_address)
            return response, 200

    @app.route("/api/devices/<mac_address>", methods=["DELETE"])
    def delete_device(mac_address: str) -> tuple[dict[str, Any], int]:
        """
        Delete a device.

        Args:
            mac_address: Device MAC address

        Returns:
            JSON-API formatted response confirming deletion
        """
        try:
            # Check if device exists
            existing_device = core_engine.device_registry.get_device(mac_address)
            if not existing_device:
                return format_error_response(f"Device {mac_address} not found", 404)

            # Remove device from registry
            success = run_async(core_engine.device_registry.remove_device(mac_address))

            if not success:
                return format_error_response(
                    f"Failed to delete device {mac_address}",
                    500,
                )

            # Also remove from state manager if present
            run_async(core_engine.state_manager.unregister_device(mac_address))

        except Exception as e:
            logger.exception("Error deleting device %s", mac_address)
            return format_error_response(f"Internal server error: {e!s}", 500)
        else:
            logger.info("Deleted device: %s", mac_address)
            # Return 204 No Content for successful deletion
            return {}, 204
