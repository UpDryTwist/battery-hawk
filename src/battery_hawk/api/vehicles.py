"""
Vehicle-related API endpoints for Battery Hawk.

This module implements all vehicle management endpoints following JSON-API
specification for consistent data formatting and error handling.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import TYPE_CHECKING, Any

from flask import Flask, request

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from battery_hawk.core.engine import BatteryHawkCore

from .constants import HTTP_BAD_REQUEST
from .devices import format_device_resource

logger = logging.getLogger("battery_hawk.api.vehicles")


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
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(coro)


class VehicleValidationError(Exception):
    """Exception raised for vehicle validation errors."""

    def __init__(self, message: str, field: str | None = None) -> None:
        """
        Initialize VehicleValidationError.

        Args:
            message: Error message
            field: Field that caused the validation error
        """
        super().__init__(message)
        self.message = message
        self.field = field


def validate_vehicle_data(
    data: dict[str, Any],
    required_fields: list[str] | None = None,
) -> None:
    """
    Validate vehicle data according to JSON-API specification.

    Args:
        data: Vehicle data to validate
        required_fields: List of required fields

    Raises:
        VehicleValidationError: If validation fails
    """
    if not isinstance(data, dict):
        raise VehicleValidationError("Request data must be an object")

    if "data" not in data:
        raise VehicleValidationError("Request must contain 'data' member")

    resource = data["data"]
    if not isinstance(resource, dict):
        raise VehicleValidationError("Data member must be an object")

    if "type" not in resource:
        raise VehicleValidationError("Resource must contain 'type' member")

    if resource["type"] != "vehicles":
        raise VehicleValidationError("Resource type must be 'vehicles'")

    # Validate required fields if specified
    if required_fields:
        attributes = resource.get("attributes", {})
        for field in required_fields:
            if field not in attributes:
                raise VehicleValidationError(f"Missing required field: {field}", field)


def format_vehicle_resource(
    vehicle_data: dict[str, Any],
    vehicle_id: str,
    device_count: int = 0,
) -> dict[str, Any]:
    """
    Format vehicle data as JSON-API resource object.

    Args:
        vehicle_data: Raw vehicle data from registry
        vehicle_id: Vehicle ID
        device_count: Number of devices associated with this vehicle

    Returns:
        JSON-API formatted resource object
    """
    return {
        "type": "vehicles",
        "id": vehicle_id,
        "attributes": {
            "name": vehicle_data.get("name", f"Vehicle {vehicle_id}"),
            "created_at": vehicle_data.get("created_at"),
            "device_count": device_count,
        },
        "links": {"self": f"/api/vehicles/{vehicle_id}"},
        "relationships": {
            "devices": {
                "links": {
                    "self": f"/api/vehicles/{vehicle_id}/relationships/devices",
                    "related": f"/api/vehicles/{vehicle_id}/devices",
                },
            },
        },
    }


def format_error_response(
    message: str,
    status_code: int = 400,
    field: str | None = None,
) -> tuple[dict[str, Any], int]:
    """
    Format error response according to JSON-API specification.

    Args:
        message: Error message
        status_code: HTTP status code
        field: Field that caused the error

    Returns:
        Tuple of (error response dict, status code)
    """
    error: dict[str, Any] = {
        "status": str(status_code),
        "title": "Validation Error" if status_code == HTTP_BAD_REQUEST else "Error",
        "detail": message,
    }

    if field:
        error["source"] = {"pointer": f"/data/attributes/{field}"}

    return {"errors": [error]}, status_code


def setup_vehicle_routes(app: Flask, core_engine: BatteryHawkCore) -> None:  # noqa: PLR0915
    """
    Set up vehicle-related API routes.

    Args:
        app: Flask application instance
        core_engine: Core engine instance
    """

    @app.route("/api/vehicles", methods=["GET"])
    def get_vehicles() -> tuple[dict[str, Any], int]:
        """
        Get all vehicles.

        Returns:
            JSON-API formatted response with all vehicles
        """
        try:
            # Get all vehicles from registry
            vehicles = core_engine.vehicle_registry.vehicles

            # Format as JSON-API resource collection
            data = []
            for vehicle_id, vehicle_data in vehicles.items():
                # Get device count for this vehicle
                device_count = len(
                    core_engine.device_registry.get_devices_by_vehicle(vehicle_id),
                )
                data.append(
                    format_vehicle_resource(vehicle_data, vehicle_id, device_count),
                )

            response = {
                "data": data,
                "meta": {"total": len(data)},
                "links": {"self": "/api/vehicles"},
            }

        except Exception as e:
            logger.exception("Error retrieving vehicles")
            return format_error_response(f"Internal server error: {e!s}", 500)
        else:
            logger.info("Retrieved %d vehicles", len(data))
            return response, 200

    @app.route("/api/vehicles/<vehicle_id>", methods=["GET"])
    def get_vehicle(vehicle_id: str) -> tuple[dict[str, Any], int]:
        """
        Get specific vehicle by ID.

        Args:
            vehicle_id: Vehicle ID

        Returns:
            JSON-API formatted response with vehicle data
        """
        try:
            # Get vehicle from registry
            vehicle_data = core_engine.vehicle_registry.get_vehicle(vehicle_id)

            if not vehicle_data:
                return format_error_response(f"Vehicle {vehicle_id} not found", 404)

            # Get device count for this vehicle
            device_count = len(
                core_engine.device_registry.get_devices_by_vehicle(vehicle_id),
            )

            response = {
                "data": format_vehicle_resource(vehicle_data, vehicle_id, device_count),
                "links": {"self": f"/api/vehicles/{vehicle_id}"},
            }

        except Exception as e:
            logger.exception("Error retrieving vehicle %s", vehicle_id)
            return format_error_response(f"Internal server error: {e!s}", 500)
        else:
            logger.debug("Retrieved vehicle: %s", vehicle_id)
            return response, 200

    @app.route("/api/vehicles", methods=["POST"])
    def create_vehicle() -> tuple[dict[str, Any], int]:
        """
        Create a new vehicle.

        Returns:
            JSON-API formatted response with created vehicle data
        """
        try:
            # Validate request data
            request_data = request.get_json()
            if not request_data:
                return format_error_response("Request body must contain JSON data", 400)

            validate_vehicle_data(request_data, ["name"])

            attributes = request_data["data"]["attributes"]
            name = attributes["name"]
            custom_id = attributes.get("id")  # Optional custom vehicle ID

            # Create the vehicle
            vehicle_id = run_async(
                core_engine.vehicle_registry.create_vehicle(name, custom_id),
            )

            # Get created vehicle data
            vehicle_data = core_engine.vehicle_registry.get_vehicle(vehicle_id)
            if vehicle_data is None:
                return format_error_response(
                    f"Vehicle {vehicle_id} not found after creation",
                    404,
                )

            response = {
                "data": format_vehicle_resource(vehicle_data, vehicle_id, 0),
                "links": {"self": f"/api/vehicles/{vehicle_id}"},
            }

        except VehicleValidationError as e:
            return format_error_response(e.message, 400, e.field)
        except Exception as e:
            logger.exception("Error creating vehicle")
            return format_error_response(f"Internal server error: {e!s}", 500)
        else:
            logger.info("Created vehicle: %s (%s)", vehicle_id, name)
            return response, 201

    @app.route("/api/vehicles/<vehicle_id>", methods=["PATCH"])
    def update_vehicle(vehicle_id: str) -> tuple[dict[str, Any], int]:  # noqa: PLR0911
        """
        Update an existing vehicle.

        Args:
            vehicle_id: Vehicle ID

        Returns:
            JSON-API formatted response with updated vehicle data
        """
        try:
            # Check if vehicle exists
            existing_vehicle = core_engine.vehicle_registry.get_vehicle(vehicle_id)
            if not existing_vehicle:
                return format_error_response(f"Vehicle {vehicle_id} not found", 404)

            # Validate request data
            request_data = request.get_json()
            if not request_data:
                return format_error_response("Request body must contain JSON data", 400)

            validate_vehicle_data(request_data)

            resource = request_data["data"]

            # Validate resource ID matches URL parameter
            if "id" in resource and resource["id"] != vehicle_id:
                return format_error_response(
                    "Resource ID must match URL parameter",
                    409,
                )

            attributes = resource.get("attributes", {})

            # Extract update fields (only update provided fields)
            name = attributes.get("name", existing_vehicle.get("name"))

            # Update the vehicle
            success = run_async(
                core_engine.vehicle_registry.update_vehicle_name(vehicle_id, name),
            )

            if not success:
                return format_error_response(
                    f"Failed to update vehicle {vehicle_id}",
                    500,
                )

            # Get updated vehicle data
            updated_vehicle = core_engine.vehicle_registry.get_vehicle(vehicle_id)
            if updated_vehicle is None:
                return format_error_response(
                    f"Vehicle {vehicle_id} not found after update",
                    404,
                )

            device_count = len(
                core_engine.device_registry.get_devices_by_vehicle(vehicle_id),
            )

            response = {
                "data": format_vehicle_resource(
                    updated_vehicle,
                    vehicle_id,
                    device_count,
                ),
                "links": {"self": f"/api/vehicles/{vehicle_id}"},
            }

        except VehicleValidationError as e:
            return format_error_response(e.message, 400, e.field)
        except Exception as e:
            logger.exception("Error updating vehicle %s", vehicle_id)
            return format_error_response(f"Internal server error: {e!s}", 500)
        else:
            logger.info("Updated vehicle: %s", vehicle_id)
            return response, 200

    @app.route("/api/vehicles/<vehicle_id>", methods=["DELETE"])
    def delete_vehicle(vehicle_id: str) -> tuple[dict[str, Any], int]:
        """
        Delete a vehicle.

        Args:
            vehicle_id: Vehicle ID

        Returns:
            JSON-API formatted response confirming deletion
        """
        try:
            # Check if vehicle exists
            existing_vehicle = core_engine.vehicle_registry.get_vehicle(vehicle_id)
            if not existing_vehicle:
                return format_error_response(f"Vehicle {vehicle_id} not found", 404)

            # Check if vehicle has associated devices
            associated_devices = core_engine.device_registry.get_devices_by_vehicle(
                vehicle_id,
            )
            if associated_devices:
                device_macs = [
                    device.get("mac_address", "unknown")
                    for device in associated_devices
                ]
                return format_error_response(
                    f"Cannot delete vehicle {vehicle_id}. It has {len(associated_devices)} associated devices: {', '.join(device_macs)}. "
                    "Please remove or reassign devices before deleting the vehicle.",
                    409,
                )

            # Delete vehicle from registry
            success = run_async(core_engine.vehicle_registry.delete_vehicle(vehicle_id))

            if not success:
                return format_error_response(
                    f"Failed to delete vehicle {vehicle_id}",
                    500,
                )

        except Exception as e:
            logger.exception("Error deleting vehicle %s", vehicle_id)
            return format_error_response(f"Internal server error: {e!s}", 500)
        else:
            logger.info("Deleted vehicle: %s", vehicle_id)
            # Return 204 No Content for successful deletion
            return {}, 204

    @app.route("/api/vehicles/<vehicle_id>/devices", methods=["GET"])
    def get_vehicle_devices(vehicle_id: str) -> tuple[dict[str, Any], int]:
        """
        Get all devices associated with a vehicle.

        Args:
            vehicle_id: Vehicle ID

        Returns:
            JSON-API formatted response with vehicle's devices
        """
        try:
            # Check if vehicle exists
            vehicle_data = core_engine.vehicle_registry.get_vehicle(vehicle_id)
            if not vehicle_data:
                return format_error_response(f"Vehicle {vehicle_id} not found", 404)

            # Get devices for this vehicle
            devices = core_engine.device_registry.get_devices_by_vehicle(vehicle_id)

            # Format as JSON-API resource collection
            data = []
            for device in devices:
                mac_address = device.get("mac_address")
                if mac_address:
                    data.append(format_device_resource(device, mac_address))

            response = {
                "data": data,
                "meta": {"total": len(data), "vehicle_id": vehicle_id},
                "links": {
                    "self": f"/api/vehicles/{vehicle_id}/devices",
                    "related": f"/api/vehicles/{vehicle_id}",
                },
            }

        except Exception as e:
            logger.exception("Error retrieving devices for vehicle %s", vehicle_id)
            return format_error_response(f"Internal server error: {e!s}", 500)
        else:
            logger.debug("Retrieved %d devices for vehicle: %s", len(data), vehicle_id)
            return response, 200
