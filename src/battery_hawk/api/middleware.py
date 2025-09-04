"""
Middleware components for Battery Hawk API.

This module provides rate limiting, authentication, and other middleware
functionality for the Flask application.
"""

from __future__ import annotations

import logging
import time
from functools import wraps
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from flask import Flask, g, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from .constants import MIN_API_PATH_COMPONENTS
from .validation import format_error_response

logger = logging.getLogger("battery_hawk.api.middleware")


def configure_rate_limiting(app: Flask) -> Limiter:
    """
    Configure rate limiting for the Flask application.

    Args:
        app: Flask application instance

    Returns:
        Configured Limiter instance
    """

    # Custom key function that considers both IP and user agent
    def get_rate_limit_key() -> str:
        """Generate rate limit key based on IP and user agent."""
        ip = get_remote_address()
        _user_agent = request.headers.get("User-Agent", "unknown")
        # Use just IP for now, but could extend to include user agent
        return ip

    limiter = Limiter(
        app=app,
        key_func=get_rate_limit_key,
        default_limits=["1000 per hour", "100 per minute"],
        storage_uri="memory://",  # Use memory storage for simplicity
        headers_enabled=True,
        retry_after="http-date",
    )

    # Custom rate limit exceeded handler
    @limiter.request_filter
    def rate_limit_filter() -> bool:
        """Filter requests that should not be rate limited."""
        # Don't rate limit health checks
        return request.endpoint in ["health_check", "get_system_health"]

    @app.errorhandler(429)
    def rate_limit_exceeded(error: Any) -> tuple[dict[str, Any], int]:
        """Handle rate limit exceeded errors."""
        logger.warning(
            "Rate limit exceeded for %s %s from %s",
            request.method,
            request.path,
            get_remote_address(),
        )

        return format_error_response(
            "Rate limit exceeded. Please slow down your requests.",
            429,
            "RATE_LIMIT_EXCEEDED",
            meta={
                "retry_after": error.retry_after,
                "limit": error.limit,
                "reset_time": error.reset_time,
            },
        )

    return limiter


def configure_request_logging(app: Flask) -> None:
    """
    Configure request logging middleware.

    Args:
        app: Flask application instance
    """

    @app.before_request
    def log_request_info() -> None:
        """Log incoming request information."""
        g.start_time = time.time()

        # Log request details at DEBUG level for normal operations
        logger.debug(
            "Request: %s %s from %s - User-Agent: %s",
            request.method,
            request.path,
            get_remote_address(),
            request.headers.get("User-Agent", "unknown"),
        )

        # Log request body for POST/PATCH/PUT (but not sensitive data)
        if request.method in ["POST", "PATCH", "PUT"] and request.is_json:
            # Don't log the actual data, just that we received JSON
            logger.debug("Request contains JSON data")

    @app.after_request
    def log_response_info(response: Any) -> Any:
        """Log response information."""
        duration = time.time() - g.get("start_time", time.time())

        # Log at INFO level for errors or slow requests, DEBUG for normal operations
        http_error_threshold = 400
        slow_request_threshold = 1.0
        if (
            response.status_code >= http_error_threshold
            or duration > slow_request_threshold
        ):
            logger.info(
                "Response: %s %s - Status: %d - Duration: %.3fs",
                request.method,
                request.path,
                response.status_code,
                duration,
            )
        else:
            logger.debug(
                "Response: %s %s - Status: %d - Duration: %.3fs",
                request.method,
                request.path,
                response.status_code,
                duration,
            )

        # Add response headers for debugging
        response.headers["X-Response-Time"] = f"{duration:.3f}s"

        return response


def configure_cors_headers(app: Flask) -> None:
    """
    Configure additional CORS headers.

    Args:
        app: Flask application instance
    """

    @app.after_request
    def add_cors_headers(response: Any) -> Any:
        """Add additional CORS headers."""
        # Allow common headers
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, Authorization, X-API-Key, X-Requested-With"
        )

        # Allow common methods
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PATCH, PUT, DELETE, OPTIONS"
        )

        # Expose rate limit headers
        response.headers["Access-Control-Expose-Headers"] = (
            "X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset, X-Response-Time"
        )

        return response


def configure_security_headers(app: Flask) -> None:
    """
    Configure security headers.

    Args:
        app: Flask application instance
    """

    @app.after_request
    def add_security_headers(response: Any) -> Any:
        """Add security headers to responses."""
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy (basic)
        if request.endpoint and "docs" in request.endpoint:
            # More permissive CSP for Swagger UI
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self'"
            )
        else:
            # Strict CSP for API endpoints
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'none'; style-src 'none'"
            )

        return response


def require_api_key(api_key: str | None = None) -> Callable:
    """
    Require API key authentication.

    Args:
        api_key: Expected API key (if None, authentication is disabled)

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if api_key is None:
                # Authentication disabled
                return func(*args, **kwargs)

            # Check for API key in header
            provided_key = request.headers.get("X-API-Key")
            if not provided_key:
                logger.warning(
                    "Missing API key for %s %s from %s",
                    request.method,
                    request.path,
                    get_remote_address(),
                )
                return format_error_response(
                    "API key required",
                    401,
                    "MISSING_API_KEY",
                    source={"header": "X-API-Key"},
                )

            if provided_key != api_key:
                logger.warning(
                    "Invalid API key for %s %s from %s",
                    request.method,
                    request.path,
                    get_remote_address(),
                )
                return format_error_response(
                    "Invalid API key",
                    401,
                    "INVALID_API_KEY",
                    source={"header": "X-API-Key"},
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def configure_api_versioning(app: Flask) -> None:
    """
    Configure API versioning support.

    Args:
        app: Flask application instance
    """

    @app.before_request
    def handle_api_versioning() -> tuple[dict[str, Any], int] | None:
        """Handle API version routing."""
        # Extract version from URL path
        path_parts = request.path.strip("/").split("/")

        if len(path_parts) >= MIN_API_PATH_COMPONENTS and path_parts[0] == "api":
            # Check if second part is a version (v1, v2, etc.)
            if path_parts[1].startswith("v") and path_parts[1][1:].isdigit():
                version = path_parts[1]
                g.api_version = version

                # For now, only support v1
                if version != "v1":
                    return format_error_response(
                        f"API version {version} is not supported. Supported versions: v1",
                        400,
                        "UNSUPPORTED_API_VERSION",
                        meta={"supported_versions": ["v1"]},
                    )
            else:
                # Default to v1 for legacy endpoints
                g.api_version = "v1"
        return None

    @app.after_request
    def add_version_header(response: Any) -> Any:
        """Add version header to response."""
        if hasattr(g, "api_version"):
            response.headers["X-API-Version"] = g.api_version
        return response


def configure_health_check_bypass(app: Flask) -> None:
    """
    Configure bypass for health check endpoints.

    Args:
        app: Flask application instance
    """

    @app.before_request
    def bypass_middleware_for_health() -> None:
        """Bypass certain middleware for health check endpoints."""
        # Mark health check requests to bypass some middleware
        if request.endpoint in ["health_check", "get_system_health"]:
            g.is_health_check = True


def configure_all_middleware(app: Flask, _api_key: str | None = None) -> Limiter:
    """
    Configure all middleware components for the Flask application.

    Args:
        app: Flask application instance
        api_key: Optional API key for authentication

    Returns:
        Configured Limiter instance
    """
    logger.info("Configuring API middleware")

    # Configure middleware in order
    configure_health_check_bypass(app)
    configure_api_versioning(app)
    configure_request_logging(app)
    configure_cors_headers(app)
    configure_security_headers(app)

    # Configure rate limiting last
    limiter = configure_rate_limiting(app)

    logger.info("API middleware configuration complete")
    return limiter
