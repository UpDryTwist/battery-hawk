"""
Sample Data Fixtures for Testing.

This module provides sample data and test fixtures for BM6 and BM2 devices
for integration testing purposes.
"""

from typing import Any

import pytest

# Sample advertisement data for different device types
SAMPLE_ADVERTISEMENT_DATA = {
    "BM6": {
        "normal": {
            "name": "BM6_Battery_Monitor",
            "service_uuids": ["0000ff00-0000-1000-8000-00805f9b34fb"],
            "manufacturer_data": b"BM6_Battery_Monitor_6",
            "rssi": -65,
            "address": "AA:BB:CC:DD:EE:01",
        },
        "alternate_name": {
            "name": "Battery Monitor 6 Device",
            "service_uuids": ["0000ff00-0000-1000-8000-00805f9b34fb"],
            "manufacturer_data": b"Battery Monitor 6",
            "rssi": -60,
            "address": "AA:BB:CC:DD:EE:02",
        },
        "no_name": {
            "name": "",
            "service_uuids": ["0000ff00-0000-1000-8000-00805f9b34fb"],
            "manufacturer_data": b"BM6",
            "rssi": -70,
            "address": "AA:BB:CC:DD:EE:03",
        },
    },
    "BM2": {
        "normal": {
            "name": "BM2_Battery_Monitor",
            "service_uuids": ["0000ff00-0000-1000-8000-00805f9b34fb"],
            "manufacturer_data": b"BM2_Battery_Monitor_2",
            "rssi": -70,
            "address": "AA:BB:CC:DD:EE:04",
        },
        "alternate_name": {
            "name": "Battery Monitor 2 Device",
            "service_uuids": ["0000ff00-0000-1000-8000-00805f9b34fb"],
            "manufacturer_data": b"Battery Monitor 2",
            "rssi": -65,
            "address": "AA:BB:CC:DD:EE:05",
        },
        "no_name": {
            "name": "",
            "service_uuids": ["0000ff00-0000-1000-8000-00805f9b34fb"],
            "manufacturer_data": b"BM2",
            "rssi": -75,
            "address": "AA:BB:CC:DD:EE:06",
        },
    },
    "unknown": {
        "unknown_device": {
            "name": "Unknown_Device",
            "service_uuids": ["0000ffff-0000-1000-8000-00805f9b34fb"],
            "manufacturer_data": b"Unknown_Manufacturer",
            "rssi": -80,
            "address": "AA:BB:CC:DD:EE:FF",
        },
    },
}

# Sample raw data packets for different device types
SAMPLE_RAW_DATA = {
    "BM6": {
        "normal_reading": bytes(
            [
                0xE8,
                0x03,  # Voltage: 1000 (10.00V)
                0x64,
                0x00,  # Current: 100 (1.00A)
                0x90,
                0x01,  # Capacity: 400 (400mAh)
                0x64,  # SOC: 100 (100%)
                0x14,  # Temperature: 20 (20°C)
            ],
        ),
        "low_battery": bytes(
            [
                0x90,
                0x01,  # Voltage: 400 (4.00V)
                0x9C,
                0xFF,  # Current: -100 (-1.00A)
                0x32,
                0x00,  # Capacity: 50 (50mAh)
                0x0A,  # SOC: 10 (10%)
                0x0A,  # Temperature: 10 (10°C)
            ],
        ),
        "high_current": bytes(
            [
                0xF4,
                0x01,  # Voltage: 500 (5.00V)
                0xE8,
                0x03,  # Current: 1000 (10.00A)
                0x64,
                0x00,  # Capacity: 100 (100mAh)
                0x32,  # SOC: 50 (50%)
                0x1E,  # Temperature: 30 (30°C)
            ],
        ),
        "negative_temp": bytes(
            [
                0xC8,
                0x00,  # Voltage: 200 (2.00V)
                0x00,
                0x00,  # Current: 0 (0.00A)
                0x00,
                0x00,  # Capacity: 0 (0mAh)
                0x00,  # SOC: 0 (0%)
                0xF6,  # Temperature: -10 (-10°C)
            ],
        ),
    },
    "BM2": {
        "normal_reading": bytes(
            [
                0xAA,  # Header
                0xE8,
                0x03,  # Voltage: 1000 (10.00V)
                0x64,
                0x00,  # Current: 100 (1.00A)
                0x14,  # Temperature: 20 (20°C)
                0x64,  # SOC: 100 (100%)
                0x90,
                0x01,  # Capacity: 400 (400mAh)
                0x8B,  # Checksum
            ],
        ),
        "low_battery": bytes(
            [
                0xAA,  # Header
                0x90,
                0x01,  # Voltage: 400 (4.00V)
                0x9C,
                0xFF,  # Current: -100 (-1.00A)
                0x0A,  # Temperature: 10 (10°C)
                0x0A,  # SOC: 10 (10%)
                0x32,
                0x00,  # Capacity: 50 (50mAh)
                0x2A,  # Checksum
            ],
        ),
        "high_current": bytes(
            [
                0xAA,  # Header
                0xF4,
                0x01,  # Voltage: 500 (5.00V)
                0xE8,
                0x03,  # Current: 1000 (10.00A)
                0x1E,  # Temperature: 30 (30°C)
                0x32,  # SOC: 50 (50%)
                0x64,
                0x00,  # Capacity: 100 (100mAh)
                0x8C,  # Checksum
            ],
        ),
        "negative_temp": bytes(
            [
                0xAA,  # Header
                0xC8,
                0x00,  # Voltage: 200 (2.00V)
                0x00,
                0x00,  # Current: 0 (0.00A)
                0xF6,  # Temperature: -10 (-10°C)
                0x00,  # SOC: 0 (0%)
                0x00,
                0x00,  # Capacity: 0 (0mAh)
                0xBE,  # Checksum
            ],
        ),
    },
}

# Expected parsed readings for the sample data
EXPECTED_READINGS = {
    "BM6": {
        "normal_reading": {
            "voltage": 10.0,
            "current": 1.0,
            "capacity": 400,
            "state_of_charge": 100,
            "temperature": 20,
            "power": 10.0,
        },
        "low_battery": {
            "voltage": 4.0,
            "current": -1.0,
            "capacity": 50,
            "state_of_charge": 10,
            "temperature": 10,
            "power": -4.0,
        },
        "high_current": {
            "voltage": 5.0,
            "current": 10.0,
            "capacity": 100,
            "state_of_charge": 50,
            "temperature": 30,
            "power": 50.0,
        },
        "negative_temp": {
            "voltage": 2.0,
            "current": 0.0,
            "capacity": 0,
            "state_of_charge": 0,
            "temperature": -10,
            "power": 0.0,
        },
    },
    "BM2": {
        "normal_reading": {
            "voltage": 10.0,
            "current": 1.0,
            "temperature": 20,
            "state_of_charge": 100,
            "capacity": 400,
        },
        "low_battery": {
            "voltage": 4.0,
            "current": -1.0,
            "temperature": 10,
            "state_of_charge": 10,
            "capacity": 50,
        },
        "high_current": {
            "voltage": 5.0,
            "current": 10.0,
            "temperature": 30,
            "state_of_charge": 50,
            "capacity": 100,
        },
        "negative_temp": {
            "voltage": 2.0,
            "current": 0.0,
            "temperature": -10,
            "state_of_charge": 0,
            "capacity": 0,
        },
    },
}

# Test device configurations
TEST_DEVICE_CONFIGS = {
    "BM6": {
        "mac_address": "AA:BB:CC:DD:EE:01",
        "device_type": "BM6",
        "friendly_name": "Test BM6 Device",
        "polling_interval": 30,
        "timeout": 30,
        "retry_attempts": 3,
    },
    "BM2": {
        "mac_address": "AA:BB:CC:DD:EE:04",
        "device_type": "BM2",
        "friendly_name": "Test BM2 Device",
        "polling_interval": 25,
        "timeout": 25,
        "retry_attempts": 3,
    },
}

# Performance test scenarios
PERFORMANCE_TEST_SCENARIOS = {
    "concurrent_readings": {
        "num_devices": 10,
        "readings_per_device": 100,
        "concurrent_connections": 5,
        "expected_duration_range": (5, 30),  # seconds
    },
    "rapid_polling": {
        "num_devices": 5,
        "readings_per_device": 50,
        "polling_interval": 1,  # seconds
        "expected_duration_range": (60, 120),  # seconds
    },
    "high_failure_rate": {
        "num_devices": 3,
        "readings_per_device": 20,
        "failure_rate": 0.3,  # 30% failure rate
        "expected_retries": 2,
    },
}


@pytest.fixture
def sample_advertisement_data() -> dict[str, dict[str, Any]]:
    """Fixture providing sample advertisement data for all device types."""
    return SAMPLE_ADVERTISEMENT_DATA


@pytest.fixture
def sample_raw_data() -> dict[str, dict[str, bytes]]:
    """Fixture providing sample raw data packets for all device types."""
    return SAMPLE_RAW_DATA


@pytest.fixture
def expected_readings() -> dict[str, dict[str, dict[str, Any]]]:
    """Fixture providing expected parsed readings for all sample data."""
    return EXPECTED_READINGS


@pytest.fixture
def test_device_configs() -> dict[str, dict[str, Any]]:
    """Fixture providing test device configurations."""
    return TEST_DEVICE_CONFIGS


@pytest.fixture
def performance_test_scenarios() -> dict[str, dict[str, Any]]:
    """Fixture providing performance test scenarios."""
    return PERFORMANCE_TEST_SCENARIOS


@pytest.fixture
def bm6_advertisement_data() -> dict[str, Any]:
    """Fixture providing BM6 advertisement data."""
    return SAMPLE_ADVERTISEMENT_DATA["BM6"]


@pytest.fixture
def bm2_advertisement_data() -> dict[str, Any]:
    """Fixture providing BM2 advertisement data."""
    return SAMPLE_ADVERTISEMENT_DATA["BM2"]


@pytest.fixture
def bm6_raw_data() -> dict[str, bytes]:
    """Fixture providing BM6 raw data packets."""
    return SAMPLE_RAW_DATA["BM6"]


@pytest.fixture
def bm2_raw_data() -> dict[str, bytes]:
    """Fixture providing BM2 raw data packets."""
    return SAMPLE_RAW_DATA["BM2"]


@pytest.fixture
def bm6_expected_readings() -> dict[str, dict[str, Any]]:
    """Fixture providing expected BM6 readings."""
    return EXPECTED_READINGS["BM6"]


@pytest.fixture
def bm2_expected_readings() -> dict[str, dict[str, Any]]:
    """Fixture providing expected BM2 readings."""
    return EXPECTED_READINGS["BM2"]


@pytest.fixture
def bm6_test_config() -> dict[str, Any]:
    """Fixture providing BM6 test configuration."""
    return TEST_DEVICE_CONFIGS["BM6"]


@pytest.fixture
def bm2_test_config() -> dict[str, Any]:
    """Fixture providing BM2 test configuration."""
    return TEST_DEVICE_CONFIGS["BM2"]


def get_test_devices() -> list[dict[str, Any]]:
    """
    Get a list of test devices for integration testing.

    Returns:
        List of test device configurations
    """
    return [
        {
            "mac_address": "AA:BB:CC:DD:EE:01",
            "device_type": "BM6",
            "name": "BM6_Test_Device_1",
            "advertisement_data": SAMPLE_ADVERTISEMENT_DATA["BM6"]["normal"],
            "raw_data": SAMPLE_RAW_DATA["BM6"]["normal_reading"],
            "expected_reading": EXPECTED_READINGS["BM6"]["normal_reading"],
        },
        {
            "mac_address": "AA:BB:CC:DD:EE:04",
            "device_type": "BM2",
            "name": "BM2_Test_Device_1",
            "advertisement_data": SAMPLE_ADVERTISEMENT_DATA["BM2"]["normal"],
            "raw_data": SAMPLE_RAW_DATA["BM2"]["normal_reading"],
            "expected_reading": EXPECTED_READINGS["BM2"]["normal_reading"],
        },
        {
            "mac_address": "AA:BB:CC:DD:EE:02",
            "device_type": "BM6",
            "name": "BM6_Test_Device_2",
            "advertisement_data": SAMPLE_ADVERTISEMENT_DATA["BM6"]["alternate_name"],
            "raw_data": SAMPLE_RAW_DATA["BM6"]["low_battery"],
            "expected_reading": EXPECTED_READINGS["BM6"]["low_battery"],
        },
        {
            "mac_address": "AA:BB:CC:DD:EE:05",
            "device_type": "BM2",
            "name": "BM2_Test_Device_2",
            "advertisement_data": SAMPLE_ADVERTISEMENT_DATA["BM2"]["alternate_name"],
            "raw_data": SAMPLE_RAW_DATA["BM2"]["low_battery"],
            "expected_reading": EXPECTED_READINGS["BM2"]["low_battery"],
        },
    ]


@pytest.fixture
def test_devices() -> list[dict[str, Any]]:
    """Fixture providing a list of test devices for integration testing."""
    return get_test_devices()
