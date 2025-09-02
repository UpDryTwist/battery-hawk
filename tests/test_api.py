"""Tests for Battery Hawk API module."""

from __future__ import annotations

from typing import NoReturn
from unittest.mock import MagicMock

import pytest

from src.battery_hawk.api import BatteryHawkAPI
from src.battery_hawk.config.config_manager import ConfigManager
from src.battery_hawk.core.engine import BatteryHawkCore


class MockConfigManager(ConfigManager):
    """Mock configuration manager for testing."""

    def __init__(self, config_dir: str = "/data") -> None:
        """Initialize mock configuration manager with test data."""
        self.config_dir = config_dir
        self.configs = {
            "system": {
                "version": "1.0",
                "logging": {"level": "INFO"},
                "bluetooth": {"max_concurrent_connections": 3, "test_mode": False},
                "discovery": {"initial_scan": True, "scan_duration": 10},
                "influxdb": {"enabled": False},
                "mqtt": {"enabled": False, "topic_prefix": "batteryhawk"},
                "api": {
                    "enabled": True,
                    "host": "127.0.0.1",
                    "port": 5001,  # Use different port for testing
                    "debug": False,
                },
            },
            "devices": {"version": "1.0", "devices": {}},
            "vehicles": {"version": "1.0", "vehicles": {}},
        }

    def get_config(self, key: str) -> dict:
        """Get a config by key."""
        return self.configs[key]

    def save_config(self, key: str) -> None:
        """Mock save config."""


@pytest.fixture
def mock_config_manager():
    """Create a mock configuration manager."""
    return MockConfigManager()


@pytest.fixture
def mock_core_engine():
    """Create a mock core engine."""
    mock_engine = MagicMock(spec=BatteryHawkCore)
    mock_engine.running = True
    return mock_engine


@pytest.fixture
def api_instance(mock_config_manager, mock_core_engine):
    """Create a BatteryHawkAPI instance for testing."""
    return BatteryHawkAPI(mock_config_manager, mock_core_engine)


class TestBatteryHawkAPI:
    """Test cases for BatteryHawkAPI class."""

    def test_api_initialization(self, api_instance) -> None:
        """Test that API initializes correctly."""
        assert api_instance.app is not None
        assert api_instance.config is not None
        assert api_instance.core_engine is not None
        assert not api_instance.running
        assert api_instance.server_thread is None

    def test_flask_app_configuration(self, api_instance) -> None:
        """Test that Flask app is configured correctly."""
        app = api_instance.app
        assert not app.config["DEBUG"]  # Should be False in test config
        assert not app.config["TESTING"]
        assert not app.config["JSON_SORT_KEYS"]
        assert app.config["JSONIFY_PRETTYPRINT_REGULAR"]

    def test_health_endpoint(self, api_instance) -> None:
        """Test the health check endpoint."""
        with api_instance.app.test_client() as client:
            response = client.get("/api/health")
            assert response.status_code == 200

            data = response.get_json()
            assert data["status"] == "healthy"
            assert data["service"] == "battery-hawk-api"
            assert data["core_running"] is True

    def test_version_endpoint(self, api_instance) -> None:
        """Test the version information endpoint."""
        with api_instance.app.test_client() as client:
            response = client.get("/api/version")
            assert response.status_code == 200

            data = response.get_json()
            assert "api_version" in data
            assert "core_version" in data
            assert data["service"] == "battery-hawk-api"

    def test_404_error_handler(self, api_instance) -> None:
        """Test 404 error handling."""
        with api_instance.app.test_client() as client:
            response = client.get("/api/nonexistent")
            assert response.status_code == 404

            data = response.get_json()
            assert "errors" in data
            assert len(data["errors"]) == 1
            error = data["errors"][0]
            assert error["detail"] == "The requested resource was not found"
            assert error["status"] == "404"
            assert error["code"] == "NOT_FOUND"

    def test_api_error_handling(self, api_instance) -> None:
        """Test custom API error handling."""
        from src.battery_hawk.api.api import APIError

        # Add a test route that raises APIError
        @api_instance.app.route("/api/test-error")
        def test_error() -> NoReturn:
            raise APIError("Test error message", 400)

        with api_instance.app.test_client() as client:
            response = client.get("/api/test-error")
            assert response.status_code == 400

            data = response.get_json()
            assert "errors" in data
            assert len(data["errors"]) == 1
            error = data["errors"][0]
            assert error["detail"] == "Test error message"
            assert error["status"] == "400"

    def test_start_stop_methods(self, api_instance) -> None:
        """Test start and stop methods (without actually starting server)."""
        # Test that methods exist and can be called
        assert hasattr(api_instance, "start")
        assert hasattr(api_instance, "stop")
        assert hasattr(api_instance, "start_async")
        assert hasattr(api_instance, "stop_async")

        # Test initial state
        assert not api_instance.running

        # Test stop when not running
        api_instance.stop()  # Should not raise error
        assert not api_instance.running


if __name__ == "__main__":
    pytest.main([__file__])
