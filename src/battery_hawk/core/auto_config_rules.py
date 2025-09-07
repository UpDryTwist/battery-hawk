"""Auto-configuration rules engine for device configuration strategies."""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from battery_hawk.config.config_manager import ConfigManager


@dataclass
class DeviceConfigurationResult:
    """Result of device configuration rule evaluation."""
    
    should_configure: bool
    device_type: str | None = None
    friendly_name: str | None = None
    polling_interval: int | None = None
    vehicle_id: str | None = None
    confidence: float = 0.0
    rule_name: str | None = None


class ConfigurationRule(ABC):
    """Abstract base class for device configuration rules."""

    def __init__(self, name: str, priority: int = 0) -> None:
        """
        Initialize the configuration rule.

        Args:
            name: Name of the rule
            priority: Priority of the rule (higher = more important)
        """
        self.name = name
        self.priority = priority
        self.logger = logging.getLogger(f"{__name__}.{name}")

    @abstractmethod
    def evaluate(
        self,
        mac_address: str,
        device_info: dict[str, Any],
        detected_type: str | None,
    ) -> DeviceConfigurationResult:
        """
        Evaluate the rule for a device.

        Args:
            mac_address: MAC address of the device
            device_info: Device information from discovery
            detected_type: Auto-detected device type

        Returns:
            Configuration result
        """


class DefaultDeviceTypeRule(ConfigurationRule):
    """Rule for configuring devices based on detected type."""

    def __init__(self, config_manager: ConfigManager) -> None:
        """Initialize with configuration manager."""
        super().__init__("default_device_type", priority=100)
        self.config_manager = config_manager

    def evaluate(
        self,
        mac_address: str,
        device_info: dict[str, Any],
        detected_type: str | None,
    ) -> DeviceConfigurationResult:
        """Evaluate based on detected device type."""
        if not detected_type:
            return DeviceConfigurationResult(should_configure=False)

        discovery_config = self.config_manager.get_config("system").get("discovery", {})
        auto_config = discovery_config.get("auto_configure", {})
        rules = auto_config.get("rules", {})
        
        device_rules = rules.get(detected_type, {})
        
        if not device_rules.get("auto_configure", True):
            return DeviceConfigurationResult(should_configure=False)

        # Generate name
        name_template = device_rules.get(
            "default_name_template",
            f"{detected_type} Device {{mac_suffix}}",
        )
        mac_suffix = mac_address.replace(":", "")[-4:].upper()
        
        try:
            friendly_name = name_template.format(
                mac_address=mac_address,
                mac_suffix=mac_suffix,
                device_type=detected_type,
                original_name=device_info.get("name", "Unknown"),
            )
        except (KeyError, ValueError):
            friendly_name = f"{detected_type} Device {mac_suffix}"

        # Get polling interval
        polling_interval = device_rules.get(
            "polling_interval",
            auto_config.get("default_polling_interval", 3600),
        )

        return DeviceConfigurationResult(
            should_configure=True,
            device_type=detected_type,
            friendly_name=friendly_name,
            polling_interval=polling_interval,
            confidence=0.8,
            rule_name=self.name,
        )


class LocationBasedRule(ConfigurationRule):
    """Rule for configuring devices based on location patterns."""

    def __init__(self, config_manager: ConfigManager) -> None:
        """Initialize with configuration manager."""
        super().__init__("location_based", priority=200)
        self.config_manager = config_manager

    def evaluate(
        self,
        mac_address: str,
        device_info: dict[str, Any],
        detected_type: str | None,
    ) -> DeviceConfigurationResult:
        """Evaluate based on device location patterns."""
        # This is a placeholder for location-based rules
        # Could be extended to use RSSI, known locations, etc.
        
        rssi = device_info.get("rssi")
        if rssi is not None and rssi > -40:
            # Very close device - might be a primary battery
            if detected_type:
                return DeviceConfigurationResult(
                    should_configure=True,
                    device_type=detected_type,
                    friendly_name=f"Primary {detected_type}",
                    polling_interval=1800,  # More frequent polling for primary
                    confidence=0.9,
                    rule_name=self.name,
                )

        return DeviceConfigurationResult(should_configure=False)


class VehicleAssignmentRule(ConfigurationRule):
    """Rule for automatically assigning devices to vehicles."""

    def __init__(self, config_manager: ConfigManager) -> None:
        """Initialize with configuration manager."""
        super().__init__("vehicle_assignment", priority=150)
        self.config_manager = config_manager

    def evaluate(
        self,
        mac_address: str,
        device_info: dict[str, Any],
        detected_type: str | None,
    ) -> DeviceConfigurationResult:
        """Evaluate for automatic vehicle assignment."""
        # This is a placeholder for vehicle assignment logic
        # Could be extended to use naming patterns, location, etc.
        
        device_name = device_info.get("name", "").lower()
        
        # Look for vehicle indicators in device name
        vehicle_patterns = {
            "car": r"car|auto|vehicle",
            "truck": r"truck|lorry",
            "boat": r"boat|marine|yacht",
            "rv": r"rv|motorhome|camper",
        }
        
        for vehicle_type, pattern in vehicle_patterns.items():
            if re.search(pattern, device_name):
                return DeviceConfigurationResult(
                    should_configure=True,
                    device_type=detected_type,
                    vehicle_id=f"auto_{vehicle_type}",
                    confidence=0.6,
                    rule_name=self.name,
                )

        return DeviceConfigurationResult(should_configure=False)


class AutoConfigurationRulesEngine:
    """Engine for evaluating and applying auto-configuration rules."""

    def __init__(self, config_manager: ConfigManager) -> None:
        """
        Initialize the rules engine.

        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.rules: list[ConfigurationRule] = []
        
        # Initialize default rules
        self._initialize_default_rules()

    def _initialize_default_rules(self) -> None:
        """Initialize the default set of configuration rules."""
        self.rules = [
            DefaultDeviceTypeRule(self.config_manager),
            LocationBasedRule(self.config_manager),
            VehicleAssignmentRule(self.config_manager),
        ]
        
        # Sort by priority (highest first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def add_rule(self, rule: ConfigurationRule) -> None:
        """
        Add a custom configuration rule.

        Args:
            rule: Configuration rule to add
        """
        self.rules.append(rule)
        # Re-sort by priority
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def remove_rule(self, rule_name: str) -> bool:
        """
        Remove a configuration rule by name.

        Args:
            rule_name: Name of the rule to remove

        Returns:
            True if rule was removed
        """
        for i, rule in enumerate(self.rules):
            if rule.name == rule_name:
                del self.rules[i]
                return True
        return False

    def evaluate_device(
        self,
        mac_address: str,
        device_info: dict[str, Any],
        detected_type: str | None,
    ) -> DeviceConfigurationResult:
        """
        Evaluate all rules for a device and return the best result.

        Args:
            mac_address: MAC address of the device
            device_info: Device information from discovery
            detected_type: Auto-detected device type

        Returns:
            Best configuration result from all rules
        """
        results = []
        
        for rule in self.rules:
            try:
                result = rule.evaluate(mac_address, device_info, detected_type)
                if result.should_configure:
                    results.append(result)
                    self.logger.debug(
                        "Rule '%s' suggests configuration for %s with confidence %.2f",
                        rule.name,
                        mac_address,
                        result.confidence,
                    )
            except Exception as e:
                self.logger.exception(
                    "Error evaluating rule '%s' for device %s: %s",
                    rule.name,
                    mac_address,
                    e,
                )

        if not results:
            return DeviceConfigurationResult(should_configure=False)

        # Return the result with highest confidence
        best_result = max(results, key=lambda r: r.confidence)
        
        # Merge results if multiple rules apply
        merged_result = self._merge_results(results, best_result)
        
        self.logger.info(
            "Best configuration for %s: rule='%s', confidence=%.2f",
            mac_address,
            merged_result.rule_name,
            merged_result.confidence,
        )
        
        return merged_result

    def _merge_results(
        self,
        results: list[DeviceConfigurationResult],
        primary_result: DeviceConfigurationResult,
    ) -> DeviceConfigurationResult:
        """
        Merge multiple configuration results into one.

        Args:
            results: All configuration results
            primary_result: Primary result with highest confidence

        Returns:
            Merged configuration result
        """
        # Start with primary result
        merged = DeviceConfigurationResult(
            should_configure=primary_result.should_configure,
            device_type=primary_result.device_type,
            friendly_name=primary_result.friendly_name,
            polling_interval=primary_result.polling_interval,
            vehicle_id=primary_result.vehicle_id,
            confidence=primary_result.confidence,
            rule_name=primary_result.rule_name,
        )

        # Override with more specific values from other rules
        for result in results:
            if result == primary_result:
                continue
                
            # Vehicle assignment from specialized rules takes precedence
            if result.vehicle_id and not merged.vehicle_id:
                merged.vehicle_id = result.vehicle_id
                
            # Use more specific polling intervals
            if (result.polling_interval and 
                result.polling_interval != merged.polling_interval and
                result.confidence > 0.7):
                merged.polling_interval = result.polling_interval

        return merged
