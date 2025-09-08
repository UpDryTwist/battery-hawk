"""Tests for auto-configuration functionality."""

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from battery_hawk.config.config_manager import ConfigManager
from battery_hawk.core.auto_config import AutoConfigurationService
from battery_hawk.core.auto_config_rules import (
    AutoConfigurationRulesEngine,
    DefaultDeviceTypeRule,
)
from battery_hawk_driver.base.device_factory import DeviceFactory


@pytest.fixture
def config_manager() -> MagicMock:
    """Create a mock configuration manager."""
    config = MagicMock(spec=ConfigManager)
    config.get_config.return_value = {
        "discovery": {
            "auto_configure": {
                "enabled": True,
                "confidence_threshold": 0.8,
                "default_polling_interval": 3600,
                "auto_assign_names": True,
                "rules": {
                    "BM6": {
                        "auto_configure": True,
                        "default_name_template": "BM6 Battery Monitor {mac_suffix}",
                        "polling_interval": 1800,
                        "priority": 1,
                    },
                    "BM2": {
                        "auto_configure": True,
                        "default_name_template": "BM2 Battery Monitor {mac_suffix}",
                        "polling_interval": 3600,
                        "priority": 2,
                    },
                },
            },
        },
    }
    return config


@pytest.fixture
def device_factory() -> MagicMock:
    """Create a mock device factory."""
    return MagicMock(spec=DeviceFactory)


@pytest.fixture
def auto_config_service(
    config_manager: MagicMock,
    device_factory: MagicMock,
) -> AutoConfigurationService:
    """Create an auto-configuration service."""
    return AutoConfigurationService(config_manager, device_factory)


@pytest.fixture
def sample_device_info() -> dict[str, Any]:
    """Sample device information from discovery."""
    return {
        "mac_address": "50:54:7B:81:33:39",
        "name": "BM6",
        "rssi": -36,
        "discovered_at": "2025-09-06T18:33:40.434205+00:00",
        "status": "discovered",
        "advertisement_data": {
            "local_name": "BM6",
            "service_uuids": ["0000fff0-0000-1000-8000-00805f9b34fb"],
            "manufacturer_data": {"3218": "0071cf9a5094ca58ad4da17bc6e1"},
        },
    }


class TestAutoConfigurationService:
    """Test cases for AutoConfigurationService."""

    def test_is_enabled_true(
        self,
        auto_config_service: AutoConfigurationService,
    ) -> None:
        """Test that auto-configuration is enabled when configured."""
        assert auto_config_service.is_enabled() is True

    def test_is_enabled_false(
        self,
        config_manager: MagicMock,
        device_factory: MagicMock,
    ) -> None:
        """Test that auto-configuration is disabled when configured."""
        config_manager.get_config.return_value = {
            "discovery": {"auto_configure": {"enabled": False}},
        }
        service = AutoConfigurationService(config_manager, device_factory)
        assert service.is_enabled() is False

    def test_is_enabled_default_true(
        self,
        config_manager: MagicMock,
        device_factory: MagicMock,
    ) -> None:
        """Test that auto-configuration defaults to enabled when not configured."""
        config_manager.get_config.return_value = {"discovery": {}}
        service = AutoConfigurationService(config_manager, device_factory)
        assert service.is_enabled() is True

    def test_is_enabled_missing_config(
        self,
        config_manager: MagicMock,
        device_factory: MagicMock,
    ) -> None:
        """Test that auto-configuration defaults to enabled when config is missing."""
        config_manager.get_config.return_value = {}
        service = AutoConfigurationService(config_manager, device_factory)
        assert service.is_enabled() is True

    def test_get_confidence_threshold(
        self,
        auto_config_service: AutoConfigurationService,
    ) -> None:
        """Test getting confidence threshold."""
        assert auto_config_service.get_confidence_threshold() == 0.8

    def test_should_auto_configure_device_enabled(
        self,
        auto_config_service: AutoConfigurationService,
        sample_device_info: dict[str, Any],
    ) -> None:
        """Test device should be auto-configured when enabled."""
        result = auto_config_service.should_auto_configure_device(
            "50:54:7B:81:33:39",
            sample_device_info,
            "BM6",
        )
        assert result is True

    def test_should_auto_configure_device_disabled(
        self,
        config_manager: MagicMock,
        device_factory: MagicMock,
        sample_device_info: dict[str, Any],
    ) -> None:
        """Test device should not be auto-configured when disabled."""
        config_manager.get_config.return_value = {
            "discovery": {"auto_configure": {"enabled": False}},
        }
        service = AutoConfigurationService(config_manager, device_factory)
        result = service.should_auto_configure_device(
            "50:54:7B:81:33:39",
            sample_device_info,
            "BM6",
        )
        assert result is False

    def test_should_auto_configure_device_no_type(
        self,
        auto_config_service: AutoConfigurationService,
        sample_device_info: dict[str, Any],
    ) -> None:
        """Test device should not be auto-configured without detected type."""
        result = auto_config_service.should_auto_configure_device(
            "50:54:7B:81:33:39",
            sample_device_info,
            None,
        )
        assert result is False

    def test_should_auto_configure_device_already_configured(
        self,
        auto_config_service: AutoConfigurationService,
        sample_device_info: dict[str, Any],
    ) -> None:
        """Test device should not be auto-configured if already configured."""
        sample_device_info["status"] = "configured"
        result = auto_config_service.should_auto_configure_device(
            "50:54:7B:81:33:39",
            sample_device_info,
            "BM6",
        )
        assert result is False

    def test_generate_device_name_with_template(
        self,
        auto_config_service: AutoConfigurationService,
        sample_device_info: dict[str, Any],
    ) -> None:
        """Test device name generation with template."""
        name = auto_config_service.generate_device_name(
            "50:54:7B:81:33:39",
            "BM6",
            sample_device_info,
        )
        assert name == "BM6 Battery Monitor 3339"

    def test_generate_device_name_without_auto_assign(
        self,
        config_manager: MagicMock,
        device_factory: MagicMock,
        sample_device_info: dict[str, Any],
    ) -> None:
        """Test device name generation without auto-assign."""
        config_manager.get_config.return_value = {
            "discovery": {
                "auto_configure": {
                    "enabled": True,
                    "auto_assign_names": False,
                    "rules": {},
                },
            },
        }
        service = AutoConfigurationService(config_manager, device_factory)
        name = service.generate_device_name(
            "50:54:7B:81:33:39",
            "BM6",
            sample_device_info,
        )
        assert name == "BM6"

    def test_get_polling_interval_device_specific(
        self,
        auto_config_service: AutoConfigurationService,
    ) -> None:
        """Test getting device-specific polling interval."""
        interval = auto_config_service.get_polling_interval("BM6")
        assert interval == 1800

    def test_get_polling_interval_default(
        self,
        auto_config_service: AutoConfigurationService,
    ) -> None:
        """Test getting default polling interval for unknown device."""
        interval = auto_config_service.get_polling_interval("UNKNOWN")
        assert interval == 3600

    @pytest.mark.asyncio
    async def test_auto_configure_device_success(
        self,
        auto_config_service: AutoConfigurationService,
        sample_device_info: dict[str, Any],
    ) -> None:
        """Test successful auto-configuration of a device."""
        # Mock device factory
        auto_config_service.device_factory.auto_detect_device_type.return_value = "BM6"

        # Mock device registry
        device_registry = AsyncMock()
        device_registry.configure_device.return_value = True

        result = await auto_config_service.auto_configure_device(
            "50:54:7B:81:33:39",
            sample_device_info,
            device_registry,
        )

        assert result is True
        device_registry.configure_device.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_configure_device_should_not_configure(
        self,
        auto_config_service: AutoConfigurationService,
        sample_device_info: dict[str, Any],
    ) -> None:
        """Test auto-configuration when device should not be configured."""
        # Mock device factory to return None (no detection)
        auto_config_service.device_factory.auto_detect_device_type.return_value = None

        # Mock device registry
        device_registry = AsyncMock()

        result = await auto_config_service.auto_configure_device(
            "50:54:7B:81:33:39",
            sample_device_info,
            device_registry,
        )

        assert result is False
        device_registry.configure_device.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_discovered_devices(
        self,
        auto_config_service: AutoConfigurationService,
        sample_device_info: dict[str, Any],
    ) -> None:
        """Test processing multiple discovered devices."""
        discovered_devices = {
            "50:54:7B:81:33:39": sample_device_info,
            "50:54:7B:81:33:40": {
                **sample_device_info,
                "mac_address": "50:54:7B:81:33:40",
            },
        }

        # Mock device factory
        auto_config_service.device_factory.auto_detect_device_type.return_value = "BM6"

        # Mock device registry
        device_registry = AsyncMock()
        device_registry.configure_device.return_value = True

        results = await auto_config_service.process_discovered_devices(
            discovered_devices,
            device_registry,
        )

        assert len(results) == 2
        assert all(results.values())
        assert device_registry.configure_device.call_count == 2


class TestDefaultDeviceTypeRule:
    """Test cases for DefaultDeviceTypeRule."""

    def test_evaluate_with_detected_type(
        self,
        config_manager: MagicMock,
        sample_device_info: dict[str, Any],
    ) -> None:
        """Test rule evaluation with detected device type."""
        rule = DefaultDeviceTypeRule(config_manager)
        result = rule.evaluate("50:54:7B:81:33:39", sample_device_info, "BM6")

        assert result.should_configure is True
        assert result.device_type == "BM6"
        assert result.friendly_name == "BM6 Battery Monitor 3339"
        assert result.polling_interval == 1800
        assert result.confidence == 0.8

    def test_evaluate_without_detected_type(
        self,
        config_manager: MagicMock,
        sample_device_info: dict[str, Any],
    ) -> None:
        """Test rule evaluation without detected device type."""
        rule = DefaultDeviceTypeRule(config_manager)
        result = rule.evaluate("50:54:7B:81:33:39", sample_device_info, None)

        assert result.should_configure is False

    def test_evaluate_disabled_device_type(
        self,
        config_manager: MagicMock,
        sample_device_info: dict[str, Any],
    ) -> None:
        """Test rule evaluation for disabled device type."""
        config_manager.get_config.return_value = {
            "discovery": {
                "auto_configure": {"rules": {"BM6": {"auto_configure": False}}},
            },
        }
        rule = DefaultDeviceTypeRule(config_manager)
        result = rule.evaluate("50:54:7B:81:33:39", sample_device_info, "BM6")

        assert result.should_configure is False


class TestAutoConfigurationRulesEngine:
    """Test cases for AutoConfigurationRulesEngine."""

    def test_initialization(self, config_manager: MagicMock) -> None:
        """Test rules engine initialization."""
        engine = AutoConfigurationRulesEngine(config_manager)
        assert len(engine.rules) == 3  # Default rules
        assert (
            engine.rules[0].priority >= engine.rules[1].priority
        )  # Sorted by priority

    def test_evaluate_device(
        self,
        config_manager: MagicMock,
        sample_device_info: dict[str, Any],
    ) -> None:
        """Test device evaluation with rules engine."""
        engine = AutoConfigurationRulesEngine(config_manager)
        result = engine.evaluate_device("50:54:7B:81:33:39", sample_device_info, "BM6")

        assert result.should_configure is True
        assert result.device_type == "BM6"
        assert result.confidence >= 0.5

    def test_evaluate_device_no_rules_match(
        self,
        config_manager: MagicMock,
        sample_device_info: dict[str, Any],
    ) -> None:
        """Test device evaluation when no rules match."""
        # Mock config to disable all rules and use weak RSSI to avoid location rule
        config_manager.get_config.return_value = {
            "discovery": {
                "auto_configure": {"rules": {"BM6": {"auto_configure": False}}},
            },
        }
        # Use weak RSSI to avoid location-based rule matching
        sample_device_info["rssi"] = -80
        engine = AutoConfigurationRulesEngine(config_manager)
        result = engine.evaluate_device("50:54:7B:81:33:39", sample_device_info, "BM6")

        assert result.should_configure is False


class TestAutoConfigurationEnvironmentVariables:
    """Test cases for environment variable overrides."""

    def test_environment_variable_disable(self, device_factory: MagicMock) -> None:
        """Test that auto-configuration can be disabled via environment variable."""
        # Set environment variable to disable auto-configuration
        os.environ["BATTERYHAWK_SYSTEM_DISCOVERY_AUTO_CONFIGURE_ENABLED"] = "false"

        try:
            # Create a real ConfigManager with a temporary directory
            import tempfile  # noqa: PLC0415

            with tempfile.TemporaryDirectory() as temp_dir:
                config_manager = ConfigManager(temp_dir, enable_watchers=False)
                service = AutoConfigurationService(config_manager, device_factory)

                # Should be disabled due to environment variable
                assert service.is_enabled() is False
        finally:
            # Clean up environment variable
            os.environ.pop("BATTERYHAWK_SYSTEM_DISCOVERY_AUTO_CONFIGURE_ENABLED", None)

    def test_environment_variable_enable(self, device_factory: MagicMock) -> None:
        """Test that auto-configuration can be explicitly enabled via environment variable."""
        # Set environment variable to enable auto-configuration
        os.environ["BATTERYHAWK_SYSTEM_DISCOVERY_AUTO_CONFIGURE_ENABLED"] = "true"

        try:
            # Create a real ConfigManager with a temporary directory
            import tempfile  # noqa: PLC0415

            with tempfile.TemporaryDirectory() as temp_dir:
                config_manager = ConfigManager(temp_dir, enable_watchers=False)
                service = AutoConfigurationService(config_manager, device_factory)

                # Should be enabled due to environment variable
                assert service.is_enabled() is True
        finally:
            # Clean up environment variable
            os.environ.pop("BATTERYHAWK_SYSTEM_DISCOVERY_AUTO_CONFIGURE_ENABLED", None)

    def test_environment_variable_confidence_threshold(
        self,
        device_factory: MagicMock,
    ) -> None:
        """Test that confidence threshold can be set via environment variable."""
        # Set environment variable for confidence threshold
        os.environ[
            "BATTERYHAWK_SYSTEM_DISCOVERY_AUTO_CONFIGURE_CONFIDENCE_THRESHOLD"
        ] = "0.9"

        try:
            # Create a real ConfigManager with a temporary directory
            import tempfile  # noqa: PLC0415

            with tempfile.TemporaryDirectory() as temp_dir:
                config_manager = ConfigManager(temp_dir, enable_watchers=False)
                service = AutoConfigurationService(config_manager, device_factory)

                # Should use the environment variable value
                assert service.get_confidence_threshold() == 0.9
        finally:
            # Clean up environment variable
            os.environ.pop(
                "BATTERYHAWK_SYSTEM_DISCOVERY_AUTO_CONFIGURE_CONFIDENCE_THRESHOLD",
                None,
            )
