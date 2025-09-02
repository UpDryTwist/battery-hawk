"""
Flask REST API implementation for Battery Hawk.

This module provides the BatteryHawkAPI class which manages the Flask application
and integrates with the core engine for serving REST API endpoints.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING, Any

from flask import Flask, request
from flask_cors import CORS
from flask_marshmallow import Marshmallow

from .devices import setup_device_routes
from .documentation import configure_swagger
from .middleware import configure_all_middleware
from .readings import setup_readings_routes
from .system import setup_system_routes
from .validation import APIError, APIValidationError, format_error_response
from .vehicles import setup_vehicle_routes

if TYPE_CHECKING:
    from battery_hawk.config.config_manager import ConfigManager
    from battery_hawk.core.engine import BatteryHawkCore


class APIError(Exception):
    """Custom exception for API-related errors."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        """
        Initialize APIError.

        Args:
            message: Error message
            status_code: HTTP status code
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class BatteryHawkAPI:
    """
    Flask REST API for Battery Hawk.

    This class manages the Flask application instance and provides integration
    with the core monitoring engine through AsyncIO.
    """

    def __init__(
        self, config_manager: ConfigManager, core_engine: BatteryHawkCore
    ) -> None:
        """
        Initialize BatteryHawkAPI with configuration and core engine.

        Args:
            config_manager: Configuration manager instance
            core_engine: Core monitoring engine instance
        """
        self.config = config_manager
        self.core_engine = core_engine
        self.logger = logging.getLogger("battery_hawk.api")

        # Flask application instance
        self.app = Flask(__name__)

        # Configure CORS
        CORS(self.app)

        # Initialize Marshmallow
        self.ma = Marshmallow(self.app)

        # API state tracking
        self.running = False
        self.server_thread: threading.Thread | None = None

        # Setup Flask application
        self._configure_app()
        self._setup_error_handlers()
        self._configure_middleware()
        self._configure_documentation()
        self.setup_routes()

        self.logger.info("BatteryHawkAPI initialized")

    def _configure_app(self) -> None:
        """Configure Flask application settings."""
        # Get API configuration
        api_config = self.config.get_config("system").get("api", {})

        # Configure Flask settings
        self.app.config.update(
            {
                "DEBUG": api_config.get("debug", False),
                "TESTING": False,
                "JSON_SORT_KEYS": False,
                "JSONIFY_PRETTYPRINT_REGULAR": True,
            }
        )

    def _setup_error_handlers(self) -> None:
        """Setup Flask error handlers for consistent error responses."""

        @self.app.errorhandler(APIError)
        def handle_api_error(error: APIError) -> tuple[dict[str, Any], int]:
            """Handle custom API errors."""
            self.logger.error(
                "API Error: %s (status: %d)", error.message, error.status_code
            )
            return format_error_response(
                error.message,
                error.status_code,
                getattr(error, "error_code", None),
                getattr(error, "source", None),
                getattr(error, "meta", None),
            )

        @self.app.errorhandler(APIValidationError)
        def handle_validation_error(
            error: APIValidationError,
        ) -> tuple[dict[str, Any], int]:
            """Handle validation errors."""
            self.logger.warning(
                "Validation Error: %s (status: %d)", error.message, error.status_code
            )
            return format_error_response(
                error.message,
                error.status_code,
                getattr(error, "error_code", None),
                getattr(error, "source", None),
                getattr(error, "meta", None),
            )

        @self.app.errorhandler(404)
        def handle_not_found(error: Any) -> tuple[dict[str, Any], int]:
            """Handle 404 errors."""
            return format_error_response(
                "The requested resource was not found", 404, "NOT_FOUND"
            )

        @self.app.errorhandler(500)
        def handle_internal_error(error: Any) -> tuple[dict[str, Any], int]:
            """Handle internal server errors."""
            self.logger.exception("Internal server error: %s", error)
            return format_error_response(
                "An internal server error occurred", 500, "INTERNAL_ERROR"
            )

    def _configure_middleware(self) -> None:
        """Configure middleware components."""
        self.logger.info("Configuring API middleware")

        # Configure all middleware (rate limiting, logging, security, etc.)
        self.limiter = configure_all_middleware(self.app)

        self.logger.info("API middleware configured successfully")

    def _configure_documentation(self) -> None:
        """Configure API documentation."""
        self.logger.info("Configuring API documentation")

        # Configure Swagger/OpenAPI documentation
        self.swagger = configure_swagger(self.app)

        self.logger.info("API documentation configured at /api/docs/")

        @self.app.before_request
        def log_request() -> None:
            """Log incoming requests."""
            self.logger.debug(
                "API Request: %s %s from %s",
                request.method,
                request.path,
                request.remote_addr,
            )

    def setup_routes(self) -> None:
        """
        Setup all API routes.

        This method registers all API endpoints. Additional route modules
        will be integrated here as they are implemented.
        """

        @self.app.route("/api/health", methods=["GET"])
        def health_check() -> dict[str, Any]:
            """Health check endpoint."""
            return {
                "status": "healthy",
                "service": "battery-hawk-api",
                "core_running": self.core_engine.running if self.core_engine else False,
            }

        @self.app.route("/api/version", methods=["GET"])
        def version_info() -> dict[str, Any]:
            """Version information endpoint."""
            from battery_hawk.api import __version__ as api_version
            from battery_hawk.core import __version__ as core_version

            return {
                "api_version": api_version,
                "core_version": core_version,
                "service": "battery-hawk-api",
            }

        # Setup device routes
        setup_device_routes(self.app, self.core_engine)

        # Setup vehicle routes
        setup_vehicle_routes(self.app, self.core_engine)

        # Setup readings routes
        setup_readings_routes(self.app, self.core_engine)

        # Setup system routes
        setup_system_routes(self.app, self.core_engine)

        self.logger.info("API routes registered")

    def start(self) -> None:
        """
        Start the Flask API server in a separate thread.

        This method starts the Flask development server in a background thread
        to allow integration with the AsyncIO-based core engine.
        """
        if self.running:
            self.logger.warning("API server is already running")
            return

        # Get API configuration
        api_config = self.config.get_config("system").get("api", {})
        host = api_config.get("host", "0.0.0.0")  # nosec B104 - Configurable bind address
        port = api_config.get("port", 5000)
        debug = api_config.get("debug", False)

        self.logger.info("Starting API server on %s:%d", host, port)

        def run_server() -> None:
            """Run Flask server in thread."""
            try:
                self.app.run(
                    host=host,
                    port=port,
                    debug=debug,
                    use_reloader=False,  # Disable reloader in thread
                    threaded=True,
                )
            except Exception:
                self.logger.exception("API server error")

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.running = True

        self.logger.info("API server started successfully")

    def stop(self) -> None:
        """
        Stop the Flask API server.

        Note: Flask development server doesn't have a clean shutdown method,
        so this sets the running flag to False. In production, a proper
        WSGI server should be used.
        """
        if not self.running:
            self.logger.warning("API server is not running")
            return

        self.logger.info("Stopping API server")
        self.running = False

        # Note: Flask dev server doesn't support clean shutdown
        # In production, use a proper WSGI server like Gunicorn
        if self.server_thread and self.server_thread.is_alive():
            self.logger.info("API server thread will terminate when main process exits")

    async def start_async(self) -> None:
        """
        Start the API server asynchronously.

        This method provides an async interface for starting the API server
        that can be integrated into the main AsyncIO event loop.
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.start)

    async def stop_async(self) -> None:
        """
        Stop the API server asynchronously.

        This method provides an async interface for stopping the API server
        that can be integrated into the main AsyncIO event loop.
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.stop)
