"""
System-related API endpoints for Battery Hawk.

This module implements system configuration and status endpoints following JSON-API
specification for consistent data formatting and error handling.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Coroutine

from flask import Flask, request

if TYPE_CHECKING:
    from battery_hawk.core.engine import BatteryHawkCore

from .constants import (
    HTTP_BAD_REQUEST,
    MAX_API_PORT,
    MAX_BLUETOOTH_CONNECTIONS,
    MIN_API_PORT,
    MIN_BLUETOOTH_CONNECTIONS,
)

logger = logging.getLogger("battery_hawk.api.system")


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
            import concurrent.futures  # noqa: PLC0415

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


class SystemValidationError(Exception):
    """Exception raised for system configuration validation errors."""

    def __init__(self, message: str, field: str | None = None) -> None:
        """
        Initialize SystemValidationError.

        Args:
            message: Error message
            field: Field that caused the validation error
        """
        super().__init__(message)
        self.message = message
        self.field = field


def validate_system_config_data(data: dict[str, Any]) -> None:
    """
    Validate system configuration data according to JSON-API specification.

    Args:
        data: System configuration data to validate

    Raises:
        SystemValidationError: If validation fails
    """
    if not isinstance(data, dict):
        raise SystemValidationError("Request data must be an object")

    if "data" not in data:
        raise SystemValidationError("Request must contain 'data' member")

    resource = data["data"]
    if not isinstance(resource, dict):
        raise SystemValidationError("Data member must be an object")

    if "type" not in resource:
        raise SystemValidationError("Resource must contain 'type' member")

    if resource["type"] != "system-config":
        raise SystemValidationError("Resource type must be 'system-config'")


def format_system_config_resource(config_data: dict[str, Any]) -> dict[str, Any]:
    """
    Format system configuration as JSON-API resource object.

    Args:
        config_data: Raw system configuration data

    Returns:
        JSON-API formatted resource object
    """
    return {
        "type": "system-config",
        "id": "current",
        "attributes": config_data,
        "links": {"self": "/api/system/config"},
    }


def format_system_status_resource(status_data: dict[str, Any]) -> dict[str, Any]:
    """
    Format system status as JSON-API resource object.

    Args:
        status_data: Raw system status data

    Returns:
        JSON-API formatted resource object
    """
    return {
        "type": "system-status",
        "id": "current",
        "attributes": {
            **status_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "links": {"self": "/api/system/status"},
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


def safe_json_value(value: Any) -> Any:
    """Convert a value to a JSON-serializable type."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {k: safe_json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe_json_value(v) for v in value]
    # For any other type (including MagicMock, _SentinelObject, etc.)
    try:
        # Try to convert to string
        return str(value)
    except Exception:  # noqa: BLE001
        return None


def setup_system_routes(app: Flask, core_engine: BatteryHawkCore) -> None:  # noqa: PLR0915
    """
    Set up system-related API routes.

    Args:
        app: Flask application instance
        core_engine: Core engine instance
    """

    @app.route("/api/system/config", methods=["GET"])
    def get_system_config() -> tuple[dict[str, Any], int]:
        """
        Get current system configuration.

        Returns:
            JSON-API formatted response with system configuration
        """
        try:
            # Get system configuration
            system_config = core_engine.config.get_config("system")

            response = {
                "data": format_system_config_resource(system_config),
                "links": {"self": "/api/system/config"},
            }

        except Exception as e:
            logger.exception("Error retrieving system configuration")
            return format_error_response(f"Internal server error: {e!s}", 500)
        else:
            logger.debug("Retrieved system configuration")
            return response, 200

    @app.route("/api/system/config", methods=["PATCH"])
    def update_system_config() -> tuple[dict[str, Any], int]:  # noqa: PLR0911
        """
        Update system configuration.

        Returns:
            JSON-API formatted response with updated configuration
        """
        try:
            # Validate request data
            request_data = request.get_json()
            if not request_data:
                return format_error_response("Request body must contain JSON data", 400)

            validate_system_config_data(request_data)

            resource = request_data["data"]

            # Validate resource ID
            if "id" in resource and resource["id"] != "current":
                return format_error_response("Resource ID must be 'current'", 409)

            attributes = resource.get("attributes", {})

            # Get current system configuration
            current_config = core_engine.config.get_config("system")

            # Validate and apply updates
            updated_config = current_config.copy()

            # Only allow updating certain safe configuration sections
            allowed_sections = [
                "logging",
                "bluetooth",
                "discovery",
                "influxdb",
                "mqtt",
                "api",
            ]

            for section, section_data in attributes.items():
                if section not in allowed_sections:
                    return format_error_response(
                        f"Configuration section '{section}' cannot be modified via API",
                        400,
                        section,
                    )

                if not isinstance(section_data, dict):
                    return format_error_response(
                        f"Configuration section '{section}' must be an object",
                        400,
                        section,
                    )

                # Merge the updates into the current configuration
                if section in updated_config:
                    updated_config[section].update(section_data)
                else:
                    updated_config[section] = section_data

            # Validate specific configuration constraints
            if "logging" in attributes:
                level = attributes["logging"].get("level")
                if level and level not in [
                    "DEBUG",
                    "INFO",
                    "WARNING",
                    "ERROR",
                    "CRITICAL",
                ]:
                    return format_error_response(
                        "Invalid logging level",
                        400,
                        "logging.level",
                    )

            if "bluetooth" in attributes:
                max_conn = attributes["bluetooth"].get("max_concurrent_connections")
                if max_conn is not None and (
                    not isinstance(max_conn, int)
                    or max_conn < MIN_BLUETOOTH_CONNECTIONS
                    or max_conn > MAX_BLUETOOTH_CONNECTIONS
                ):
                    return format_error_response(
                        f"max_concurrent_connections must be between {MIN_BLUETOOTH_CONNECTIONS} and {MAX_BLUETOOTH_CONNECTIONS}",
                        HTTP_BAD_REQUEST,
                        "bluetooth.max_concurrent_connections",
                    )

            if "api" in attributes:
                port = attributes["api"].get("port")
                if port is not None and (
                    not isinstance(port, int)
                    or port < MIN_API_PORT
                    or port > MAX_API_PORT
                ):
                    return format_error_response(
                        f"API port must be between {MIN_API_PORT} and {MAX_API_PORT}",
                        HTTP_BAD_REQUEST,
                        "api.port",
                    )

            # Update the configuration
            core_engine.config.configs["system"] = updated_config
            core_engine.config.save_config("system")

            response = {
                "data": format_system_config_resource(updated_config),
                "links": {"self": "/api/system/config"},
            }

        except SystemValidationError as e:
            return format_error_response(e.message, 400, e.field)
        except Exception as e:
            logger.exception("Error updating system configuration")
            return format_error_response(f"Internal server error: {e!s}", 500)
        else:
            logger.info("Updated system configuration")
            return response, 200

    @app.route("/api/system/status", methods=["GET"])
    def get_system_status() -> tuple[dict[str, Any], int]:
        """
        Get current system status.

        Returns:
            JSON-API formatted response with system status
        """
        try:
            # Get core engine status
            core_status = core_engine.get_status()

            # Get storage health information
            storage_health = None
            storage_metrics = None
            if hasattr(core_engine.data_storage, "get_health_status"):
                try:
                    storage_health = core_engine.data_storage.get_health_status()
                    storage_metrics = core_engine.data_storage.get_metrics()
                    # Convert to dict if they have __dict__ attribute
                    if hasattr(storage_health, "__dict__"):
                        storage_health = storage_health.__dict__
                    if hasattr(storage_metrics, "__dict__"):
                        storage_metrics = storage_metrics.__dict__
                except Exception:  # noqa: BLE001
                    # If health status retrieval fails, use None
                    storage_health = None
                    storage_metrics = None

            # Compile comprehensive status
            status_data = {
                "core": safe_json_value(core_status),
                "storage": {
                    "connected": core_status.get("storage_connected", False),
                    "health": safe_json_value(storage_health),
                    "metrics": safe_json_value(storage_metrics),
                },
                "components": {
                    "device_registry": {
                        "total_devices": len(core_engine.device_registry.devices),
                        "configured_devices": len(
                            core_engine.device_registry.get_configured_devices(),
                        ),
                    },
                    "vehicle_registry": {
                        "total_vehicles": len(core_engine.vehicle_registry.vehicles),
                    },
                    "discovery_service": {
                        "discovered_devices": len(
                            getattr(
                                core_engine.discovery_service,
                                "discovered_devices",
                                {},
                            ),
                        ),
                        "scanning": bool(
                            getattr(core_engine.discovery_service, "scanning", False),
                        ),
                    },
                    "state_manager": safe_json_value(
                        core_status.get("state_manager", {}),
                    ),
                },
            }

            response = {
                "data": format_system_status_resource(status_data),
                "links": {"self": "/api/system/status"},
            }

        except Exception as e:
            logger.exception("Error retrieving system status")
            return format_error_response(f"Internal server error: {e!s}", 500)
        else:
            logger.debug("Retrieved system status")
            return response, 200

    @app.route("/api/system/health", methods=["GET"])
    def get_system_health() -> tuple[dict[str, Any], int]:
        """
        Get system health check.

        Returns:
            JSON-API formatted response with health status
        """
        try:
            # Perform health checks
            storage_healthy = (
                run_async(core_engine.data_storage.health_check())
                if hasattr(core_engine.data_storage, "health_check")
                else True
            )
            core_running = core_engine.running

            # Determine overall health
            overall_healthy = storage_healthy and core_running

            health_data = {
                "healthy": overall_healthy,
                "components": {
                    "core_engine": core_running,
                    "data_storage": storage_healthy,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            response = {
                "data": {
                    "type": "system-health",
                    "id": "current",
                    "attributes": health_data,
                    "links": {"self": "/api/system/health"},
                },
            }

            status_code = 200 if overall_healthy else 503

        except Exception as e:
            logger.exception("Error performing system health check")
            return format_error_response(f"Internal server error: {e!s}", 500)
        else:
            logger.debug(
                "System health check: %s",
                "healthy" if overall_healthy else "unhealthy",
            )
            return response, status_code
