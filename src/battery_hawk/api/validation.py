"""
Request validation and error handling for Battery Hawk API.

This module provides decorators and utilities for comprehensive request
validation and standardized error responses.
"""

from __future__ import annotations

import logging
import uuid
from functools import wraps
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from flask import request
from marshmallow import Schema, ValidationError

logger = logging.getLogger("battery_hawk.api.validation")


class APIValidationError(Exception):
    """Custom exception for API validation errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: str | None = None,
        source: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize APIValidationError.

        Args:
            message: Error message
            status_code: HTTP status code
            error_code: Application-specific error code
            source: Error source information
            meta: Additional error metadata
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.source = source
        self.meta = meta


class APIError(Exception):
    """General API error exception."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str | None = None,
        source: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize APIError.

        Args:
            message: Error message
            status_code: HTTP status code
            error_code: Application-specific error code
            source: Error source information
            meta: Additional error metadata
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.source = source
        self.meta = meta


def format_validation_errors(
    errors: dict[str, Any] | list[str],
) -> list[dict[str, Any]]:
    """
    Format marshmallow validation errors into JSON-API error format.

    Args:
        errors: Marshmallow validation errors

    Returns:
        List of formatted error objects
    """
    formatted_errors = []

    # Handle case where errors is a list of strings
    if isinstance(errors, list):
        for message in errors:
            error = {
                "id": str(uuid.uuid4()),
                "status": "400",
                "code": "VALIDATION_ERROR",
                "title": "Validation Error",
                "detail": str(message),
            }
            formatted_errors.append(error)
        return formatted_errors

    def process_errors(error_dict: dict[str, Any], path_prefix: str = "") -> None:
        """Recursively process nested error dictionaries."""
        for field_path, messages in error_dict.items():
            full_path = f"{path_prefix}/{field_path}" if path_prefix else field_path

            if isinstance(messages, dict):
                # Nested errors (e.g., data.attributes.field)
                process_errors(messages, full_path)
            elif isinstance(messages, list):
                # List of error messages
                for message in messages:
                    error = {
                        "id": str(uuid.uuid4()),
                        "status": "400",
                        "code": "VALIDATION_ERROR",
                        "title": "Validation Error",
                        "detail": message,
                        "source": {"pointer": f"/data/{full_path}"},
                    }
                    formatted_errors.append(error)
            else:
                # Single error message
                error = {
                    "id": str(uuid.uuid4()),
                    "status": "400",
                    "code": "VALIDATION_ERROR",
                    "title": "Validation Error",
                    "detail": str(messages),
                    "source": {"pointer": f"/data/{full_path}"},
                }
                formatted_errors.append(error)

    process_errors(errors)
    return formatted_errors


def format_error_response(
    message: str,
    status_code: int = 400,
    error_code: str | None = None,
    source: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    error_id: str | None = None,
) -> tuple[dict[str, Any], int]:
    """
    Format a single error into JSON-API error response.

    Args:
        message: Error message
        status_code: HTTP status code
        error_code: Application-specific error code
        source: Error source information
        meta: Additional error metadata
        error_id: Unique error identifier

    Returns:
        Tuple of (error response dict, status code)
    """
    error: dict[str, Any] = {
        "id": error_id or str(uuid.uuid4()),
        "status": str(status_code),
        "title": get_error_title(status_code),
        "detail": message,
    }

    if error_code:
        error["code"] = error_code
    if source:
        error["source"] = source
    if meta:
        error["meta"] = meta

    return {"errors": [error]}, status_code


def get_error_title(status_code: int) -> str:
    """
    Get appropriate error title for HTTP status code.

    Args:
        status_code: HTTP status code

    Returns:
        Error title string
    """
    titles = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        409: "Conflict",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout",
    }
    return titles.get(status_code, "Error")


def validate_json_request(schema: type[Schema]) -> Callable:
    """
    Validate JSON request body using marshmallow schema.

    Args:
        schema: Marshmallow schema class for validation

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                # Get request data
                request_data = request.get_json()
                if request_data is None:
                    return format_error_response(
                        "Request body must contain valid JSON data",
                        400,
                        "INVALID_JSON",
                    )

                # Validate using schema
                schema_instance = schema()
                try:
                    validated_data = schema_instance.load(request_data)
                except ValidationError as e:
                    logger.warning("Validation error: %s", e.messages)
                    return {"errors": format_validation_errors(e.messages)}, 400

                # Add validated data to kwargs
                kwargs["validated_data"] = validated_data
                return func(*args, **kwargs)

            except Exception as e:
                logger.exception("Unexpected error in validation decorator")
                return format_error_response(
                    f"Internal server error: {e!s}",
                    500,
                    "INTERNAL_ERROR",
                )

        return wrapper

    return decorator


def validate_query_params(schema: type[Schema]) -> Callable:
    """
    Validate query parameters using marshmallow schema.

    Args:
        schema: Marshmallow schema class for validation

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                # Get query parameters
                query_params = request.args.to_dict()

                # Validate using schema
                schema_instance = schema()
                try:
                    validated_params = schema_instance.load(query_params)
                except ValidationError as e:
                    logger.warning("Query parameter validation error: %s", e.messages)
                    formatted_errors = format_validation_errors(e.messages)
                    return {"errors": formatted_errors}, 400

                # Add validated params to kwargs
                kwargs["validated_params"] = validated_params
                return func(*args, **kwargs)

            except Exception as e:
                logger.exception("Unexpected error in query validation decorator")
                return format_error_response(
                    f"Internal server error: {e!s}",
                    500,
                    "INTERNAL_ERROR",
                )

        return wrapper

    return decorator


def handle_api_errors(func: Callable) -> Callable:
    """
    Handle API exceptions and format error responses.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function with error handling
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except APIValidationError as e:
            logger.warning("API validation error: %s", e.message)
            return format_error_response(
                e.message,
                e.status_code,
                e.error_code,
                e.source,
                e.meta,
            )
        except APIError as e:
            logger.exception("API error: %s", e.message)
            return format_error_response(
                e.message,
                e.status_code,
                e.error_code,
                e.source,
                e.meta,
            )
        except Exception as e:
            logger.exception("Unexpected error in API endpoint")
            return format_error_response(
                "An unexpected error occurred",
                500,
                "INTERNAL_ERROR",
                meta={"original_error": str(e)},
            )

    return wrapper


def require_content_type(content_type: str = "application/vnd.api+json") -> Callable:
    """
    Require specific content type for requests.

    Args:
        content_type: Required content type

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if request.method in ["POST", "PATCH", "PUT"] and (
                not request.content_type
                or not request.content_type.startswith(content_type)
            ):
                return format_error_response(
                    f"Content-Type must be '{content_type}'",
                    415,  # Unsupported Media Type
                    "UNSUPPORTED_MEDIA_TYPE",
                    source={"header": "Content-Type"},
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def validate_resource_id(resource_type: str) -> Callable:
    """
    Validate that resource ID in URL matches request body.

    Args:
        resource_type: Expected resource type

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if request.method in ["PATCH", "PUT"]:
                request_data = request.get_json()
                if request_data and "data" in request_data:
                    resource = request_data["data"]

                    # Check resource type
                    if resource.get("type") != resource_type:
                        return format_error_response(
                            f"Resource type must be '{resource_type}'",
                            409,
                            "RESOURCE_TYPE_MISMATCH",
                            source={"pointer": "/data/type"},
                        )

                    # Check resource ID matches URL parameter
                    url_id = (
                        kwargs.get("mac_address")
                        or kwargs.get("vehicle_id")
                        or kwargs.get("device_id")
                    )
                    resource_id = resource.get("id")

                    if resource_id and resource_id != url_id:
                        return format_error_response(
                            "Resource ID must match URL parameter",
                            409,
                            "RESOURCE_ID_MISMATCH",
                            source={"pointer": "/data/id"},
                        )

            return func(*args, **kwargs)

        return wrapper

    return decorator
