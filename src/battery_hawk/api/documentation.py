"""
API documentation configuration using Swagger/OpenAPI.

This module configures Flasgger for automatic API documentation generation
with comprehensive endpoint descriptions and examples.
"""

from __future__ import annotations

from flasgger import Swagger
from flask import Flask


def configure_swagger(app: Flask) -> Swagger:
    """
    Configure Swagger/OpenAPI documentation for the Flask app.

    Args:
        app: Flask application instance

    Returns:
        Configured Swagger instance
    """
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec",
                "route": "/api/docs/apispec.json",
                "rule_filter": lambda rule: True,  # Include all endpoints
                "model_filter": lambda tag: True,  # Include all models
            }
        ],
        "static_url_path": "/api/docs/static",
        "swagger_ui": True,
        "specs_route": "/api/docs/",
        "title": "Battery Hawk API Documentation",
        "version": "1.0.0",
        "description": "Comprehensive REST API for Battery Hawk monitoring system",
        "termsOfService": "",
        "contact": {
            "name": "Battery Hawk Support",
            "email": "support@batteryhawk.com",
            "url": "https://github.com/UpDryTwist/battery-hawk",
        },
        "license": {"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    }

    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "Battery Hawk API",
            "description": """
# Battery Hawk REST API

The Battery Hawk API provides comprehensive management of battery monitoring devices, vehicles, and data collection.

## Features

- **Device Management**: Configure and monitor battery monitoring devices
- **Vehicle Management**: Organize devices by vehicle
- **Data Collection**: Access real-time and historical battery readings
- **System Management**: Configure system settings and monitor health

## JSON-API Specification

This API follows the [JSON-API specification](https://jsonapi.org/) for consistent data formatting:

- All resources follow the standard JSON-API structure
- Relationships between resources are properly defined
- Error responses follow JSON-API error format
- Pagination and filtering are supported where applicable

## Authentication

Currently, the API does not require authentication. In production deployments,
consider implementing appropriate authentication and authorization mechanisms.

## Rate Limiting

API endpoints are rate-limited to prevent abuse:
- Default: 100 requests per minute per IP
- Burst: 200 requests per minute per IP
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

## Error Handling

All errors follow the JSON-API error specification with detailed error information:

```json
{
  "errors": [
    {
      "id": "unique-error-id",
      "status": "400",
      "code": "VALIDATION_ERROR",
      "title": "Validation Error",
      "detail": "The provided data is invalid",
      "source": {
        "pointer": "/data/attributes/field_name"
      }
    }
  ]
}
```

## Versioning

The API uses URL versioning. Current version is v1, accessible at `/api/v1/`.
Legacy endpoints without version prefix default to v1.
            """,
            "version": "1.0.0",
            "contact": {
                "name": "Battery Hawk Support",
                "email": "support@batteryhawk.com",
                "url": "https://github.com/UpDryTwist/battery-hawk",
            },
            "license": {"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
        },
        "host": "localhost:5000",
        "basePath": "/api",
        "schemes": ["http", "https"],
        "consumes": ["application/vnd.api+json", "application/json"],
        "produces": ["application/vnd.api+json", "application/json"],
        "securityDefinitions": {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for authentication (future implementation)",
            }
        },
        "definitions": {
            "Error": {
                "type": "object",
                "required": ["status", "title", "detail"],
                "properties": {
                    "id": {"type": "string", "description": "Unique error identifier"},
                    "status": {"type": "string", "description": "HTTP status code"},
                    "code": {
                        "type": "string",
                        "description": "Application-specific error code",
                    },
                    "title": {"type": "string", "description": "Short error summary"},
                    "detail": {
                        "type": "string",
                        "description": "Detailed error description",
                    },
                    "source": {
                        "type": "object",
                        "description": "Error source information",
                        "properties": {
                            "pointer": {
                                "type": "string",
                                "description": "JSON Pointer to the field causing the error",
                            },
                            "parameter": {
                                "type": "string",
                                "description": "Query parameter causing the error",
                            },
                            "header": {
                                "type": "string",
                                "description": "Header causing the error",
                            },
                        },
                    },
                    "meta": {
                        "type": "object",
                        "description": "Additional error metadata",
                    },
                },
            },
            "ErrorResponse": {
                "type": "object",
                "required": ["errors"],
                "properties": {
                    "errors": {
                        "type": "array",
                        "items": {"$ref": "#/definitions/Error"},
                        "description": "Array of error objects",
                    }
                },
            },
            "DeviceAttributes": {
                "type": "object",
                "required": ["mac_address", "device_type", "friendly_name"],
                "properties": {
                    "mac_address": {
                        "type": "string",
                        "pattern": "^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$",
                        "description": "Device MAC address",
                        "example": "AA:BB:CC:DD:EE:FF",
                    },
                    "device_type": {
                        "type": "string",
                        "enum": ["BM2", "BM6", "BM7", "GENERIC"],
                        "description": "Type of battery monitor device",
                    },
                    "friendly_name": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 100,
                        "description": "Human-readable device name",
                    },
                    "vehicle_id": {
                        "type": "string",
                        "description": "ID of associated vehicle",
                    },
                    "polling_interval": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 86400,
                        "default": 3600,
                        "description": "Polling interval in seconds",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["discovered", "configured", "error"],
                        "description": "Device status",
                    },
                },
            },
            "VehicleAttributes": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 100,
                        "description": "Vehicle name",
                    },
                    "device_count": {
                        "type": "integer",
                        "description": "Number of associated devices",
                    },
                    "created_at": {
                        "type": "string",
                        "format": "date-time",
                        "description": "Vehicle creation timestamp",
                    },
                },
            },
            "ReadingAttributes": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Device MAC address",
                    },
                    "timestamp": {
                        "type": "string",
                        "format": "date-time",
                        "description": "Reading timestamp",
                    },
                    "voltage": {
                        "type": "number",
                        "format": "float",
                        "description": "Voltage in volts",
                    },
                    "current": {
                        "type": "number",
                        "format": "float",
                        "description": "Current in amperes",
                    },
                    "temperature": {
                        "type": "number",
                        "format": "float",
                        "description": "Temperature in Celsius",
                    },
                    "state_of_charge": {
                        "type": "number",
                        "format": "float",
                        "description": "State of charge percentage",
                    },
                    "power": {
                        "type": "number",
                        "format": "float",
                        "description": "Power in watts",
                    },
                },
            },
        },
        "responses": {
            "400": {
                "description": "Bad Request",
                "schema": {"$ref": "#/definitions/ErrorResponse"},
            },
            "401": {
                "description": "Unauthorized",
                "schema": {"$ref": "#/definitions/ErrorResponse"},
            },
            "403": {
                "description": "Forbidden",
                "schema": {"$ref": "#/definitions/ErrorResponse"},
            },
            "404": {
                "description": "Not Found",
                "schema": {"$ref": "#/definitions/ErrorResponse"},
            },
            "409": {
                "description": "Conflict",
                "schema": {"$ref": "#/definitions/ErrorResponse"},
            },
            "422": {
                "description": "Unprocessable Entity",
                "schema": {"$ref": "#/definitions/ErrorResponse"},
            },
            "429": {
                "description": "Too Many Requests",
                "schema": {"$ref": "#/definitions/ErrorResponse"},
            },
            "500": {
                "description": "Internal Server Error",
                "schema": {"$ref": "#/definitions/ErrorResponse"},
            },
        },
        "tags": [
            {
                "name": "General",
                "description": "General API endpoints for health and version information",
            },
            {
                "name": "Devices",
                "description": "Device management endpoints for battery monitoring devices",
            },
            {
                "name": "Vehicles",
                "description": "Vehicle management endpoints for organizing devices",
            },
            {
                "name": "Readings",
                "description": "Data endpoints for accessing battery readings and measurements",
            },
            {
                "name": "System",
                "description": "System management endpoints for configuration and monitoring",
            },
        ],
    }

    return Swagger(app, config=swagger_config, template=swagger_template)
