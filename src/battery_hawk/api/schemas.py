"""
Marshmallow schemas for Battery Hawk API validation and serialization.

This module defines all validation schemas for API requests and responses
following JSON-API specification.
"""

from __future__ import annotations

from typing import Any

from marshmallow import Schema, ValidationError, fields, validate, validates_schema

from .constants import (
    MAX_API_PORT,
    MAX_BLUETOOTH_CONNECTIONS,
    MIN_API_PORT,
    MIN_BLUETOOTH_CONNECTIONS,
)


class DeviceAttributesSchema(Schema):
    """Schema for device attributes validation."""

    mac_address = fields.Str(
        required=True,
        validate=validate.Regexp(
            r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$",
            error="Invalid MAC address format",
        ),
        metadata={"description": "Device MAC address in format AA:BB:CC:DD:EE:FF"},
    )
    device_type = fields.Str(
        required=True,
        validate=validate.OneOf(["BM2", "BM6", "BM7", "GENERIC"]),
        metadata={"description": "Type of battery monitor device"},
    )
    friendly_name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=100),
        metadata={"description": "Human-readable device name"},
    )
    vehicle_id = fields.Str(
        allow_none=True,
        validate=validate.Length(min=1, max=50),
        metadata={"description": "ID of associated vehicle"},
    )
    polling_interval = fields.Int(
        load_default=3600,
        validate=validate.Range(min=60, max=86400),
        metadata={"description": "Polling interval in seconds (60-86400)"},
    )


class DeviceResourceSchema(Schema):
    """Schema for device resource in JSON-API format."""

    id = fields.Str(dump_only=True, metadata={"description": "Device MAC address"})
    type = fields.Str(
        dump_only=True,
        dump_default="devices",
        metadata={"description": "Resource type"},
    )
    attributes = fields.Nested(DeviceAttributesSchema)


class DeviceSchema(Schema):
    """JSON-API schema for device resources."""

    data = fields.Nested(DeviceResourceSchema)


class DeviceConfigurationSchema(Schema):
    """Schema for device configuration requests."""

    data = fields.Nested(lambda: DeviceConfigurationDataSchema(), required=True)


class DeviceConfigurationDataSchema(Schema):
    """Schema for device configuration data."""

    type = fields.Str(required=True, validate=validate.Equal("devices"))
    attributes = fields.Nested(DeviceAttributesSchema, required=True)


class VehicleAttributesSchema(Schema):
    """Schema for vehicle attributes validation."""

    name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=100),
        metadata={"description": "Vehicle name"},
    )
    id = fields.Str(
        allow_none=True,
        validate=validate.Length(min=1, max=50),
        metadata={"description": "Custom vehicle ID (optional)"},
    )


class VehicleResourceSchema(Schema):
    """Schema for vehicle resource in JSON-API format."""

    id = fields.Str(dump_only=True, metadata={"description": "Vehicle ID"})
    type = fields.Str(
        dump_only=True,
        dump_default="vehicles",
        metadata={"description": "Resource type"},
    )
    attributes = fields.Nested(VehicleAttributesSchema)


class VehicleSchema(Schema):
    """JSON-API schema for vehicle resources."""

    data = fields.Nested(VehicleResourceSchema)


class VehicleCreationSchema(Schema):
    """Schema for vehicle creation requests."""

    data = fields.Nested(lambda: VehicleCreationDataSchema(), required=True)


class VehicleCreationDataSchema(Schema):
    """Schema for vehicle creation data."""

    type = fields.Str(required=True, validate=validate.Equal("vehicles"))
    attributes = fields.Nested(VehicleAttributesSchema, required=True)


class ReadingAttributesSchema(Schema):
    """Schema for reading attributes."""

    device_id = fields.Str(
        dump_only=True,
        metadata={"description": "Device MAC address"},
    )
    timestamp = fields.DateTime(
        dump_only=True,
        metadata={"description": "Reading timestamp"},
    )
    voltage = fields.Float(
        allow_none=True,
        metadata={"description": "Voltage in volts"},
    )
    current = fields.Float(
        allow_none=True,
        metadata={"description": "Current in amperes"},
    )
    temperature = fields.Float(
        allow_none=True,
        metadata={"description": "Temperature in Celsius"},
    )
    state_of_charge = fields.Float(
        allow_none=True,
        metadata={"description": "State of charge percentage"},
    )
    power = fields.Float(allow_none=True, metadata={"description": "Power in watts"})
    device_type = fields.Str(allow_none=True, metadata={"description": "Device type"})
    vehicle_id = fields.Str(
        allow_none=True,
        metadata={"description": "Associated vehicle ID"},
    )


class ReadingResourceSchema(Schema):
    """Schema for reading resource in JSON-API format."""

    id = fields.Str(dump_only=True, metadata={"description": "Reading ID"})
    type = fields.Str(
        dump_only=True,
        dump_default="readings",
        metadata={"description": "Resource type"},
    )
    attributes = fields.Nested(ReadingAttributesSchema)


class ReadingSchema(Schema):
    """JSON-API schema for reading resources."""

    data = fields.Nested(ReadingResourceSchema)


class SystemConfigAttributesSchema(Schema):
    """Schema for system configuration attributes."""

    logging = fields.Dict(
        keys=fields.Str(),
        values=fields.Raw(),
        metadata={"description": "Logging configuration"},
    )
    bluetooth = fields.Dict(
        keys=fields.Str(),
        values=fields.Raw(),
        metadata={"description": "Bluetooth configuration"},
    )
    discovery = fields.Dict(
        keys=fields.Str(),
        values=fields.Raw(),
        metadata={"description": "Device discovery configuration"},
    )
    influxdb = fields.Dict(
        keys=fields.Str(),
        values=fields.Raw(),
        metadata={"description": "InfluxDB configuration"},
    )
    mqtt = fields.Dict(
        keys=fields.Str(),
        values=fields.Raw(),
        metadata={"description": "MQTT configuration"},
    )
    api = fields.Dict(
        keys=fields.Str(),
        values=fields.Raw(),
        metadata={"description": "API configuration"},
    )

    @validates_schema
    def validate_logging_level(self, data: dict[str, Any], **_kwargs: Any) -> None:
        """Validate logging level if present."""
        if "logging" in data and "level" in data["logging"]:
            level = data["logging"]["level"]
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if level not in valid_levels:
                raise ValidationError(
                    f"Invalid logging level. Must be one of: {valid_levels}",
                )

    @validates_schema
    def validate_bluetooth_connections(
        self,
        data: dict[str, Any],
        **_kwargs: Any,
    ) -> None:
        """Validate bluetooth max connections if present."""
        if "bluetooth" in data and "max_concurrent_connections" in data["bluetooth"]:
            max_conn = data["bluetooth"]["max_concurrent_connections"]
            if (
                not isinstance(max_conn, int)
                or max_conn < MIN_BLUETOOTH_CONNECTIONS
                or max_conn > MAX_BLUETOOTH_CONNECTIONS
            ):
                raise ValidationError(
                    f"max_concurrent_connections must be between {MIN_BLUETOOTH_CONNECTIONS} and {MAX_BLUETOOTH_CONNECTIONS}",
                )

    @validates_schema
    def validate_api_port(self, data: dict[str, Any], **_kwargs: Any) -> None:
        """Validate API port if present."""
        if "api" in data and "port" in data["api"]:
            port = data["api"]["port"]
            if not isinstance(port, int) or port < MIN_API_PORT or port > MAX_API_PORT:
                raise ValidationError(
                    f"API port must be between {MIN_API_PORT} and {MAX_API_PORT}",
                )


class SystemConfigResourceSchema(Schema):
    """Schema for system config resource in JSON-API format."""

    id = fields.Str(
        dump_only=True,
        dump_default="current",
        metadata={"description": "Configuration ID"},
    )
    type = fields.Str(
        dump_only=True,
        dump_default="system-config",
        metadata={"description": "Resource type"},
    )
    attributes = fields.Nested(SystemConfigAttributesSchema)


class SystemConfigSchema(Schema):
    """JSON-API schema for system configuration."""

    data = fields.Nested(SystemConfigResourceSchema)


class SystemConfigUpdateSchema(Schema):
    """Schema for system configuration update requests."""

    data = fields.Nested(lambda: SystemConfigUpdateDataSchema(), required=True)


class SystemConfigUpdateDataSchema(Schema):
    """Schema for system configuration update data."""

    type = fields.Str(required=True, validate=validate.Equal("system-config"))
    id = fields.Str(required=True, validate=validate.Equal("current"))
    attributes = fields.Nested(SystemConfigAttributesSchema, required=True)


class SystemStatusAttributesSchema(Schema):
    """Schema for system status attributes."""

    core = fields.Dict(dump_only=True, metadata={"description": "Core engine status"})
    storage = fields.Dict(
        dump_only=True,
        metadata={"description": "Storage system status"},
    )
    components = fields.Dict(
        dump_only=True,
        metadata={"description": "Component status"},
    )
    timestamp = fields.DateTime(
        dump_only=True,
        metadata={"description": "Status timestamp"},
    )


class SystemStatusResourceSchema(Schema):
    """Schema for system status resource in JSON-API format."""

    id = fields.Str(
        dump_only=True,
        dump_default="current",
        metadata={"description": "Status ID"},
    )
    type = fields.Str(
        dump_only=True,
        dump_default="system-status",
        metadata={"description": "Resource type"},
    )
    attributes = fields.Nested(SystemStatusAttributesSchema)


class SystemStatusSchema(Schema):
    """JSON-API schema for system status."""

    data = fields.Nested(SystemStatusResourceSchema)


class SystemHealthAttributesSchema(Schema):
    """Schema for system health attributes."""

    healthy = fields.Bool(
        dump_only=True,
        metadata={"description": "Overall system health"},
    )
    components = fields.Dict(
        dump_only=True,
        metadata={"description": "Component health status"},
    )
    timestamp = fields.DateTime(
        dump_only=True,
        metadata={"description": "Health check timestamp"},
    )


class SystemHealthResourceSchema(Schema):
    """Schema for system health resource in JSON-API format."""

    id = fields.Str(
        dump_only=True,
        dump_default="current",
        metadata={"description": "Health check ID"},
    )
    type = fields.Str(
        dump_only=True,
        dump_default="system-health",
        metadata={"description": "Resource type"},
    )
    attributes = fields.Nested(SystemHealthAttributesSchema)


class SystemHealthSchema(Schema):
    """JSON-API schema for system health."""

    data = fields.Nested(SystemHealthResourceSchema)


class ErrorSchema(Schema):
    """Schema for error responses following JSON-API specification."""

    id = fields.Str(
        allow_none=True,
        metadata={"description": "Unique error identifier"},
    )
    status = fields.Str(required=True, metadata={"description": "HTTP status code"})
    code = fields.Str(
        allow_none=True,
        metadata={"description": "Application-specific error code"},
    )
    title = fields.Str(required=True, metadata={"description": "Short error summary"})
    detail = fields.Str(
        required=True,
        metadata={"description": "Detailed error description"},
    )
    source = fields.Dict(
        allow_none=True,
        metadata={"description": "Error source information"},
    )
    meta = fields.Dict(
        allow_none=True,
        metadata={"description": "Additional error metadata"},
    )


class ErrorResponseSchema(Schema):
    """Schema for error response wrapper."""

    errors = fields.List(fields.Nested(ErrorSchema), required=True)


# Query parameter schemas
class ReadingsQuerySchema(Schema):
    """Schema for readings endpoint query parameters."""

    limit = fields.Int(
        load_default=100,
        validate=validate.Range(min=1, max=1000),
        metadata={"description": "Maximum number of readings to return (1-1000)"},
    )
    offset = fields.Int(
        load_default=0,
        validate=validate.Range(min=0),
        metadata={"description": "Number of readings to skip for pagination"},
    )
    sort = fields.Str(
        load_default="-timestamp",
        validate=validate.OneOf(
            [
                "timestamp",
                "-timestamp",
                "voltage",
                "-voltage",
                "current",
                "-current",
                "temperature",
                "-temperature",
            ],
        ),
        metadata={"description": "Sort field and direction"},
    )


class PaginationQuerySchema(Schema):
    """Schema for general pagination query parameters."""

    limit = fields.Int(
        load_default=100,
        validate=validate.Range(min=1, max=1000),
        metadata={"description": "Maximum number of items to return (1-1000)"},
    )
    offset = fields.Int(
        load_default=0,
        validate=validate.Range(min=0),
        metadata={"description": "Number of items to skip for pagination"},
    )
