"""
Tests for API validation, error handling, and documentation features.

This module tests the comprehensive validation system, rate limiting,
error handling, and API documentation features.
"""

import json
from unittest.mock import MagicMock

import pytest

from src.battery_hawk.api import BatteryHawkAPI
from src.battery_hawk.api.validation import (
    format_error_response,
)


class TestValidationDecorators:
    """Test validation decorators and error handling."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock config manager."""
        mock_config = MagicMock()
        mock_config.get.return_value = {"api": {"port": 5000}}
        return mock_config

    @pytest.fixture
    def mock_core_engine(self):
        """Create a mock core engine."""
        mock_engine = MagicMock()
        mock_engine.running = True
        return mock_engine

    @pytest.fixture
    def api_instance(self, mock_config_manager, mock_core_engine):
        """Create API instance for testing."""
        return BatteryHawkAPI(mock_config_manager, mock_core_engine)

    @pytest.fixture
    def client(self, api_instance):
        """Create test client."""
        api_instance.app.config["TESTING"] = True
        return api_instance.app.test_client()

    def test_json_validation_success(self, client) -> None:
        """Test successful JSON validation."""
        valid_data = {
            "data": {
                "type": "devices",
                "attributes": {
                    "mac_address": "AA:BB:CC:DD:EE:FF",
                    "device_type": "BM6",
                    "friendly_name": "Test Device",
                },
            }
        }

        response = client.post(
            "/api/devices",
            data=json.dumps(valid_data),
            content_type="application/vnd.api+json",
        )

        # Should not fail validation (might fail for other reasons like device not found)
        assert response.status_code != 400

    def test_json_validation_invalid_content_type(self, client) -> None:
        """Test JSON validation with invalid content type."""
        valid_data = {
            "data": {
                "type": "devices",
                "attributes": {
                    "mac_address": "AA:BB:CC:DD:EE:FF",
                    "device_type": "BM6",
                    "friendly_name": "Test Device",
                },
            }
        }

        response = client.post(
            "/api/devices",
            data=json.dumps(valid_data),
            content_type="application/json",  # Wrong content type
        )

        assert response.status_code == 415
        data = response.get_json()
        assert "errors" in data
        assert data["errors"][0]["code"] == "UNSUPPORTED_MEDIA_TYPE"

    def test_json_validation_missing_data(self, client) -> None:
        """Test JSON validation with missing data."""
        invalid_data = {
            "type": "devices"  # Missing 'data' wrapper
        }

        response = client.post(
            "/api/devices",
            data=json.dumps(invalid_data),
            content_type="application/vnd.api+json",
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "errors" in data

    def test_json_validation_invalid_mac_address(self, client) -> None:
        """Test JSON validation with invalid MAC address."""
        invalid_data = {
            "data": {
                "type": "devices",
                "attributes": {
                    "mac_address": "invalid-mac",
                    "device_type": "BM6",
                    "friendly_name": "Test Device",
                },
            }
        }

        response = client.post(
            "/api/devices",
            data=json.dumps(invalid_data),
            content_type="application/vnd.api+json",
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "errors" in data
        # Check that there's a validation error for mac_address
        assert any(
            "mac_address" in error.get("source", {}).get("pointer", "")
            or "Invalid MAC address format" in error.get("detail", "")
            for error in data["errors"]
        )

    def test_query_parameter_validation(self, client) -> None:
        """Test query parameter validation."""
        # Test invalid limit
        response = client.get("/api/devices?limit=2000")  # Exceeds max limit
        assert response.status_code == 400
        data = response.get_json()
        assert "errors" in data

        # Test invalid offset
        response = client.get("/api/devices?offset=-1")  # Negative offset
        assert response.status_code == 400
        data = response.get_json()
        assert "errors" in data

    def test_error_response_format(self) -> None:
        """Test error response formatting."""
        response, status_code = format_error_response(
            "Test error message",
            400,
            "TEST_ERROR",
            {"pointer": "/data/attributes/field"},
            {"additional": "info"},
        )

        assert status_code == 400
        assert "errors" in response
        assert len(response["errors"]) == 1

        error = response["errors"][0]
        assert error["status"] == "400"
        assert error["code"] == "TEST_ERROR"
        assert error["detail"] == "Test error message"
        assert error["source"]["pointer"] == "/data/attributes/field"
        assert error["meta"]["additional"] == "info"


class TestAPIDocumentation:
    """Test API documentation features."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock config manager."""
        mock_config = MagicMock()
        mock_config.get.return_value = {"api": {"port": 5000}}
        return mock_config

    @pytest.fixture
    def mock_core_engine(self):
        """Create a mock core engine."""
        mock_engine = MagicMock()
        mock_engine.running = True
        return mock_engine

    @pytest.fixture
    def api_instance(self, mock_config_manager, mock_core_engine):
        """Create API instance for testing."""
        return BatteryHawkAPI(mock_config_manager, mock_core_engine)

    @pytest.fixture
    def client(self, api_instance):
        """Create test client."""
        api_instance.app.config["TESTING"] = True
        return api_instance.app.test_client()

    def test_swagger_documentation_available(self, client) -> None:
        """Test that Swagger documentation is available."""
        response = client.get("/api/docs/")
        assert response.status_code == 200
        assert (
            b"swagger" in response.data.lower() or b"openapi" in response.data.lower()
        )

    def test_api_spec_available(self, client) -> None:
        """Test that API specification is available."""
        response = client.get("/api/docs/apispec.json")
        assert response.status_code == 200

        spec = response.get_json()
        assert "swagger" in spec or "openapi" in spec
        assert "info" in spec
        assert "paths" in spec


class TestRateLimiting:
    """Test rate limiting functionality."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock config manager."""
        mock_config = MagicMock()
        mock_config.get.return_value = {"api": {"port": 5000}}
        return mock_config

    @pytest.fixture
    def mock_core_engine(self):
        """Create a mock core engine."""
        mock_engine = MagicMock()
        mock_engine.running = True
        return mock_engine

    @pytest.fixture
    def api_instance(self, mock_config_manager, mock_core_engine):
        """Create API instance for testing."""
        return BatteryHawkAPI(mock_config_manager, mock_core_engine)

    @pytest.fixture
    def client(self, api_instance):
        """Create test client."""
        api_instance.app.config["TESTING"] = True
        return api_instance.app.test_client()

    def test_rate_limit_headers(self, client) -> None:
        """Test that rate limit headers are present."""
        response = client.get("/api/devices")

        # Check for rate limit headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers

    def test_health_check_bypass(self, client) -> None:
        """Test that health checks bypass rate limiting."""
        # Health checks should not be rate limited
        for _ in range(10):
            response = client.get("/api/health")
            assert response.status_code == 200


class TestSecurityHeaders:
    """Test security headers and middleware."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock config manager."""
        mock_config = MagicMock()
        mock_config.get.return_value = {"api": {"port": 5000}}
        return mock_config

    @pytest.fixture
    def mock_core_engine(self):
        """Create a mock core engine."""
        mock_engine = MagicMock()
        mock_engine.running = True
        return mock_engine

    @pytest.fixture
    def api_instance(self, mock_config_manager, mock_core_engine):
        """Create API instance for testing."""
        return BatteryHawkAPI(mock_config_manager, mock_core_engine)

    @pytest.fixture
    def client(self, api_instance):
        """Create test client."""
        api_instance.app.config["TESTING"] = True
        return api_instance.app.test_client()

    def test_security_headers_present(self, client) -> None:
        """Test that security headers are present."""
        response = client.get("/api/devices")

        # Check for security headers
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

        assert "X-XSS-Protection" in response.headers
        assert "Content-Security-Policy" in response.headers

    def test_cors_headers_present(self, client) -> None:
        """Test that CORS headers are present."""
        response = client.get("/api/devices")

        # Check for CORS headers
        assert "Access-Control-Allow-Headers" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers
        assert "Access-Control-Expose-Headers" in response.headers

    def test_api_versioning_header(self, client) -> None:
        """Test that API version header is present."""
        response = client.get("/api/devices")

        # Check for API version header
        assert "X-API-Version" in response.headers
        assert response.headers["X-API-Version"] == "v1"


class TestErrorHandling:
    """Test comprehensive error handling."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock config manager."""
        mock_config = MagicMock()
        mock_config.get.return_value = {"api": {"port": 5000}}
        return mock_config

    @pytest.fixture
    def mock_core_engine(self):
        """Create a mock core engine."""
        mock_engine = MagicMock()
        mock_engine.running = True
        return mock_engine

    @pytest.fixture
    def api_instance(self, mock_config_manager, mock_core_engine):
        """Create API instance for testing."""
        return BatteryHawkAPI(mock_config_manager, mock_core_engine)

    @pytest.fixture
    def client(self, api_instance):
        """Create test client."""
        api_instance.app.config["TESTING"] = True
        return api_instance.app.test_client()

    def test_404_error_format(self, client) -> None:
        """Test 404 error response format."""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404

        data = response.get_json()
        assert "errors" in data
        assert len(data["errors"]) == 1

        error = data["errors"][0]
        assert error["status"] == "404"
        assert error["code"] == "NOT_FOUND"

    def test_method_not_allowed_error(self, client) -> None:
        """Test method not allowed error."""
        response = client.delete(
            "/api/health"
        )  # Health endpoint doesn't support DELETE
        assert response.status_code == 405
