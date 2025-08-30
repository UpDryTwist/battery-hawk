"""
Pytest configuration and shared fixtures for Battery Hawk tests.

This file imports and exposes fixtures from the fixtures module
to make them available to all test files.
"""

from tests.support.fixtures.test_sample_data import (
    bm2_advertisement_data,
    bm2_expected_readings,
    bm2_raw_data,
    bm2_test_config,
    bm6_advertisement_data,
    bm6_expected_readings,
    bm6_raw_data,
    bm6_test_config,
    expected_readings,
    performance_test_scenarios,
    sample_advertisement_data,
    sample_raw_data,
    test_device_configs,
    test_devices,
)

# Re-export all fixtures to make them available to all test files
__all__ = [
    "bm2_advertisement_data",
    "bm2_expected_readings",
    "bm2_raw_data",
    "bm2_test_config",
    "bm6_advertisement_data",
    "bm6_expected_readings",
    "bm6_raw_data",
    "bm6_test_config",
    "expected_readings",
    "performance_test_scenarios",
    "sample_advertisement_data",
    "sample_raw_data",
    "test_device_configs",
    "test_devices",
]
