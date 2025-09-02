"""
Readings-related API endpoints for Battery Hawk.

This module implements device readings endpoints following JSON-API
specification for consistent data formatting and error handling.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from flask import Flask, request

if TYPE_CHECKING:
    from battery_hawk.core.engine import BatteryHawkCore

logger = logging.getLogger("battery_hawk.api.readings")


def run_async(coro):
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
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def format_reading_resource(
    reading_data: dict[str, Any], device_id: str, reading_id: str = None
) -> dict[str, Any]:
    """
    Format reading data as JSON-API resource object.

    Args:
        reading_data: Raw reading data from storage
        device_id: Device MAC address
        reading_id: Optional reading ID (timestamp-based)

    Returns:
        JSON-API formatted resource object
    """
    # Generate reading ID from timestamp if not provided
    if reading_id is None:
        timestamp = reading_data.get("time", datetime.now(timezone.utc).isoformat())
        if isinstance(timestamp, str):
            reading_id = f"{device_id}_{timestamp.replace(':', '-').replace('.', '-')}"
        else:
            reading_id = f"{device_id}_{int(timestamp.timestamp())}"

    return {
        "type": "readings",
        "id": reading_id,
        "attributes": {
            "device_id": device_id,
            "timestamp": reading_data.get("time"),
            "voltage": reading_data.get("voltage"),
            "current": reading_data.get("current"),
            "temperature": reading_data.get("temperature"),
            "state_of_charge": reading_data.get("state_of_charge"),
            "power": reading_data.get("power"),
            "device_type": reading_data.get("device_type"),
            "vehicle_id": reading_data.get("vehicle_id"),
        },
        "links": {
            "self": f"/api/readings/{device_id}/{reading_id}",
            "device": f"/api/devices/{device_id}",
        },
        "relationships": {
            "device": {
                "links": {
                    "self": f"/api/readings/{device_id}/relationships/device",
                    "related": f"/api/devices/{device_id}",
                },
                "data": {"type": "devices", "id": device_id},
            }
        },
    }


def format_error_response(
    message: str, status_code: int = 400, field: str | None = None
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
    error = {
        "status": str(status_code),
        "title": "Validation Error" if status_code == 400 else "Error",
        "detail": message,
    }

    if field:
        error["source"] = {"parameter": field}

    return {"errors": [error]}, status_code


def parse_query_params(request_args: dict) -> dict[str, Any]:
    """
    Parse and validate query parameters for readings endpoint.

    Args:
        request_args: Flask request arguments

    Returns:
        Dictionary of parsed parameters

    Raises:
        ValueError: If parameters are invalid
    """
    params = {}

    # Parse limit parameter
    limit = request_args.get("limit", "100")
    try:
        params["limit"] = int(limit)
        if params["limit"] <= 0 or params["limit"] > 1000:
            raise ValueError("Limit must be between 1 and 1000")
    except ValueError as e:
        raise ValueError(f"Invalid limit parameter: {e}") from e

    # Parse offset parameter for pagination
    offset = request_args.get("offset", "0")
    try:
        params["offset"] = int(offset)
        if params["offset"] < 0:
            raise ValueError("Offset must be non-negative")
    except ValueError as e:
        raise ValueError(f"Invalid offset parameter: {e}") from e

    # Parse sort parameter
    sort = request_args.get("sort", "-timestamp")
    if sort not in [
        "-timestamp",
        "timestamp",
        "-voltage",
        "voltage",
        "-current",
        "current",
    ]:
        raise ValueError(
            "Invalid sort parameter. Allowed: timestamp, -timestamp, voltage, -voltage, current, -current"
        )
    params["sort"] = sort

    # Parse filter parameters
    if "filter[start_time]" in request_args:
        try:
            # Validate ISO format timestamp
            datetime.fromisoformat(
                request_args["filter[start_time]"].replace("Z", "+00:00")
            )
            params["start_time"] = request_args["filter[start_time]"]
        except ValueError as e:
            raise ValueError(f"Invalid start_time filter: {e}") from e

    if "filter[end_time]" in request_args:
        try:
            datetime.fromisoformat(
                request_args["filter[end_time]"].replace("Z", "+00:00")
            )
            params["end_time"] = request_args["filter[end_time]"]
        except ValueError as e:
            raise ValueError(f"Invalid end_time filter: {e}") from e

    return params


def setup_readings_routes(app: Flask, core_engine: BatteryHawkCore) -> None:
    """
    Setup readings-related API routes.

    Args:
        app: Flask application instance
        core_engine: Core engine instance
    """

    @app.route("/api/readings/<mac_address>", methods=["GET"])
    def get_device_readings(mac_address: str) -> tuple[dict[str, Any], int]:
        """
        Get readings for a specific device.

        Args:
            mac_address: Device MAC address

        Returns:
            JSON-API formatted response with device readings
        """
        try:
            # Check if device exists
            device_data = core_engine.device_registry.get_device(mac_address)
            if not device_data:
                return format_error_response(f"Device {mac_address} not found", 404)

            # Parse query parameters
            try:
                params = parse_query_params(request.args)
            except ValueError as e:
                return format_error_response(str(e), 400)

            # Get readings from storage (get more than needed for pagination)
            # We need to get enough data to handle offset + limit
            storage_limit = max(params["offset"] + params["limit"], 100)
            readings = run_async(
                core_engine.data_storage.get_recent_readings(
                    device_id=mac_address, limit=storage_limit
                )
            )

            # Format as JSON-API resource collection
            data = []
            for reading in readings:
                data.append(format_reading_resource(reading, mac_address))

            # Apply sorting (storage returns newest first by default)
            if params["sort"] == "timestamp":
                data.reverse()
            # For other sorts, we'd need to implement in storage layer
            # For now, we'll just support timestamp sorting

            # Apply pagination
            offset = params["offset"]
            limit = params["limit"]
            total_count = len(data)
            paginated_data = (
                data[offset : offset + limit] if offset < total_count else []
            )

            # Build pagination links
            links = {
                "self": f"/api/readings/{mac_address}?limit={limit}&offset={offset}"
            }

            if offset > 0:
                prev_offset = max(0, offset - limit)
                links["prev"] = (
                    f"/api/readings/{mac_address}?limit={limit}&offset={prev_offset}"
                )

            if offset + limit < total_count:
                next_offset = offset + limit
                links["next"] = (
                    f"/api/readings/{mac_address}?limit={limit}&offset={next_offset}"
                )

            response = {
                "data": paginated_data,
                "meta": {
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "device_id": mac_address,
                },
                "links": links,
            }

            logger.debug(
                "Retrieved %d readings for device: %s", len(paginated_data), mac_address
            )
            return response, 200

        except Exception as e:
            logger.exception("Error retrieving readings for device %s", mac_address)
            return format_error_response(f"Internal server error: {e!s}", 500)

    @app.route("/api/readings/<mac_address>/latest", methods=["GET"])
    def get_latest_reading(mac_address: str) -> tuple[dict[str, Any], int]:
        """
        Get the latest reading for a specific device.

        Args:
            mac_address: Device MAC address

        Returns:
            JSON-API formatted response with latest reading
        """
        try:
            # Check if device exists
            device_data = core_engine.device_registry.get_device(mac_address)
            if not device_data:
                return format_error_response(f"Device {mac_address} not found", 404)

            # Get latest reading from state manager
            device_state = core_engine.state_manager.get_device_state(mac_address)
            if not device_state or not device_state.latest_reading:
                return format_error_response(
                    f"No readings available for device {mac_address}", 404
                )

            # Convert BatteryInfo to dict format
            # Calculate power from voltage and current
            power = None
            if (
                device_state.latest_reading.voltage
                and device_state.latest_reading.current
            ):
                power = (
                    device_state.latest_reading.voltage
                    * device_state.latest_reading.current
                )

            reading_data = {
                "time": device_state.last_reading_time.isoformat()
                if device_state.last_reading_time
                else None,
                "voltage": device_state.latest_reading.voltage,
                "current": device_state.latest_reading.current,
                "temperature": device_state.latest_reading.temperature,
                "state_of_charge": device_state.latest_reading.state_of_charge,
                "power": power,
                "device_type": device_state.device_type,
                "vehicle_id": device_data.get("vehicle_id"),
            }

            response = {
                "data": format_reading_resource(reading_data, mac_address),
                "links": {"self": f"/api/readings/{mac_address}/latest"},
            }

            logger.debug("Retrieved latest reading for device: %s", mac_address)
            return response, 200

        except Exception as e:
            logger.exception(
                "Error retrieving latest reading for device %s", mac_address
            )
            return format_error_response(f"Internal server error: {e!s}", 500)
