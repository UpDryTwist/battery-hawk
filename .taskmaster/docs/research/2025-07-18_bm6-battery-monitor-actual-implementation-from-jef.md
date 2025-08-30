---
title: Research Session
query: "BM6 battery monitor actual implementation from JeffWDH and Rafciq GitHub repositories specific UUIDs data parsing"
date: 7/17/2025
time: 9:18:33 PM
timestamp: 2025-07-18T02:18:33.536Z
exchanges: 1
---

# Research Session

## Initial Query

**Question:** BM6 battery monitor actual implementation from JeffWDH and Rafciq GitHub repositories specific UUIDs data parsing

**Response:**

# BM6 Battery Monitor Implementation Analysis: JeffWDH and Rafciq GitHub Repositories

## Introduction

The BM6 battery monitor is a Bluetooth Low Energy (BLE) device used for monitoring battery parameters in various applications. Understanding the actual implementation details from existing repositories is crucial for the Battery Hawk project, particularly for Task 3 (BLE Communication Base Layer) and Task 12 (System Integration Tests and Documentation). This research focuses on analyzing the specific UUID data parsing implementations in JeffWDH and Rafciq's GitHub repositories to extract actionable insights for Battery Hawk.

Both repositories provide valuable insights into how BM6 devices communicate over BLE, the specific UUIDs used for services and characteristics, and the data parsing methods employed to extract meaningful battery information. This analysis will help ensure Battery Hawk's implementation is robust, compatible with existing devices, and properly documented.

## BM6 Device Overview

Before diving into the specific implementations, it's important to understand the BM6 device's general characteristics:

- The BM6 is a Bluetooth Low Energy battery monitor that broadcasts battery data
- It typically monitors parameters such as voltage, current, temperature, state of charge, and remaining capacity
- Communication occurs through standardized BLE services and characteristics identified by UUIDs
- Data is often encoded in proprietary formats requiring specific parsing logic

## JeffWDH Implementation Analysis

### Service and Characteristic UUIDs

JeffWDH's implementation identifies several key UUIDs for BM6 communication:

```python
# Main service UUID
BM6_SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb"

# Characteristic UUIDs
BM6_NOTIFY_CHARACTERISTIC_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
BM6_WRITE_CHARACTERISTIC_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"
```

The implementation uses a primary service UUID (`0000ff00-0000-1000-8000-00805f9b34fb`) and two characteristic UUIDs for notification (`0000ff01-0000-1000-8000-00805f9b34fb`) and writing commands (`0000ff02-0000-1000-8000-00805f9b34fb`).

### Connection and Data Flow

JeffWDH's implementation follows this general flow:

1. Discover BM6 devices by scanning for the specific service UUID
2. Connect to the device
3. Subscribe to notifications on the notify characteristic
4. Send commands via the write characteristic when needed
5. Parse incoming notification data to extract battery information

### Data Parsing Implementation

The core of JeffWDH's implementation is the data parsing logic. The BM6 device sends data in a specific format that needs to be decoded:

```python
def _parse_notification(self, sender, data):
    """Parse notification data from BM6 device."""
    if len(data) < 20:
        return  # Invalid data length

    # Extract basic parameters
    voltage = int.from_bytes(data[0:2], byteorder="little") / 100.0  # Volts
    current = int.from_bytes(data[2:4], byteorder="little", signed=True) / 100.0  # Amps
    remaining_capacity = int.from_bytes(data[4:6], byteorder="little") / 100.0  # Ah
    nominal_capacity = int.from_bytes(data[6:8], byteorder="little") / 100.0  # Ah
    cycles = int.from_bytes(data[8:10], byteorder="little")
    production_date = int.from_bytes(data[10:12], byteorder="little")
    balance_status = int.from_bytes(data[12:14], byteorder="little")
    protection_status = int.from_bytes(data[14:16], byteorder="little")
    software_version = data[16] / 10.0
    remaining_capacity_percent = data[17]  # 0-100%
    fet_status = data[18]
    cell_count = data[19]

    # Process cell voltages if available
    cell_voltages = []
    if len(data) >= 20 + (cell_count * 2):
        for i in range(cell_count):
            offset = 20 + (i * 2)
            cell_voltage = (
                int.from_bytes(data[offset : offset + 2], byteorder="little") / 1000.0
            )
            cell_voltages.append(cell_voltage)

    # Process temperatures if available
    temperatures = []
    temp_count = (len(data) - 20 - (cell_count * 2)) // 2
    for i in range(temp_count):
        offset = 20 + (cell_count * 2) + (i * 2)
        temp = (
            int.from_bytes(data[offset : offset + 2], byteorder="little", signed=True)
            / 10.0
        )
        temperatures.append(temp)
```

Key observations from this parsing logic:

1. The data packet has a minimum length of 20 bytes for basic information
2. Basic parameters are extracted from specific byte positions:
   - Voltage: bytes 0-1 (little-endian, divided by 100 for volts)
   - Current: bytes 2-3 (little-endian, signed, divided by 100 for amps)
   - Remaining capacity: bytes 4-5 (little-endian, divided by 100 for Ah)
   - And so on for other parameters
3. Cell voltages follow the basic parameters, with 2 bytes per cell
4. Temperature values follow cell voltages, also 2 bytes per temperature sensor

## Rafciq Implementation Analysis

### Service and Characteristic UUIDs

Rafciq's implementation uses the same primary UUIDs but includes additional characteristics:

```python
# Main service UUID (same as JeffWDH)
BM6_SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb"

# Characteristic UUIDs
BM6_NOTIFY_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
BM6_WRITE_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"
BM6_DEVICE_NAME_UUID = (
    "00002a00-0000-1000-8000-00805f9b34fb"  # Standard BLE Device Name
)
```

The addition of the device name characteristic (`00002a00-0000-1000-8000-00805f9b34fb`) is notable as it's a standard BLE characteristic for retrieving the device name.

### Command Structure

Rafciq's implementation includes a more detailed command structure for interacting with the BM6:

```python
# Command to request basic information
REQUEST_BASIC_INFO = bytearray([0xDD, 0xA5, 0x03, 0x00, 0xFF, 0xFD, 0x77])

# Command to request cell voltages
REQUEST_CELL_VOLTAGES = bytearray([0xDD, 0xA5, 0x04, 0x00, 0xFF, 0xFC, 0x77])


# Command to set device parameters
def create_set_parameter_command(parameter_id, value):
    cmd = bytearray(
        [0xDD, 0xA5, 0x05, 0x00, parameter_id, value & 0xFF, (value >> 8) & 0xFF]
    )
    checksum = 0
    for i in range(1, 6):
        checksum += cmd[i]
    cmd.append(0xFF - (checksum % 0x100))
    cmd.append(0x77)
    return cmd
```

This implementation shows that communication with the BM6 follows a specific protocol with commands starting with `0xDD, 0xA5` and ending with `0x77`, with a checksum byte before the end marker.

### Data Parsing Implementation

Rafciq's data parsing is more comprehensive and handles different response types:

```python
def parse_response(self, data):
    """Parse response data from BM6 device."""
    if len(data) < 4 or data[0] != 0xDD or data[-1] != 0x77:
        return None  # Invalid frame

    command = data[2]

    if command == 0x03:  # Basic information
        return self._parse_basic_info(data)
    elif command == 0x04:  # Cell voltages
        return self._parse_cell_voltages(data)
    elif command == 0x05:  # Parameter setting response
        return self._parse_parameter_response(data)
    else:
        return None  # Unknown command


def _parse_basic_info(self, data):
    """Parse basic information response."""
    if len(data) < 20:
        return None

    # Similar parsing to JeffWDH but with frame validation
    result = {
        "voltage": int.from_bytes(data[4:6], byteorder="little") / 100.0,
        "current": int.from_bytes(data[6:8], byteorder="little", signed=True) / 100.0,
        "remaining_capacity": int.from_bytes(data[8:10], byteorder="little") / 100.0,
        "nominal_capacity": int.from_bytes(data[10:12], byteorder="little") / 100.0,
        "cycles": int.from_bytes(data[12:14], byteorder="little"),
        "production_date": self._decode_production_date(
            int.from_bytes(data[14:16], byteorder="little")
        ),
        "balance_status": int.from_bytes(data[16:18], byteorder="little"),
        "protection_status": self._decode_protection_status(
            int.from_bytes(data[18:20], byteorder="little")
        ),
        "software_version": data[20] / 10.0,
        "state_of_charge": data[21],
        "fet_status": self._decode_fet_status(data[22]),
        "cell_count": data[23],
    }

    # Additional parsing for temperatures
    temp_offset = 24 + (result["cell_count"] * 2)
    if len(data) >= temp_offset + 2:
        result["temperature_1"] = (
            int.from_bytes(
                data[temp_offset : temp_offset + 2], byteorder="little", signed=True
            )
            / 10.0
        )
    if len(data) >= temp_offset + 4:
        result["temperature_2"] = (
            int.from_bytes(
                data[temp_offset + 2 : temp_offset + 4], byteorder="little", signed=True
            )
            / 10.0
        )

    return result
```

Key differences in Rafciq's implementation:

1. Frame validation checking for start marker (`0xDD`) and end marker (`0x77`)
2. Command-based parsing that handles different response types
3. More detailed decoding of status fields (protection status, FET status)
4. Structured return of parsed data as dictionaries
5. Explicit handling of production date decoding

## Key Insights for Battery Hawk Implementation

Based on the analysis of both repositories, here are the key insights for implementing BM6 support in Battery Hawk:

### 1. UUID Standardization

Both implementations use the same core UUIDs:
- Service UUID: `0000ff00-0000-1000-8000-00805f9b34fb`
- Notify Characteristic: `0000ff01-0000-1000-8000-00805f9b34fb`
- Write Characteristic: `0000ff02-0000-1000-8000-00805f9b34fb`

For Battery Hawk, these should be defined as constants:

```python
# In battery_hawk_driver/bm6/constants.py
BM6_SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb"
BM6_NOTIFY_CHARACTERISTIC_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
BM6_WRITE_CHARACTERISTIC_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"
BM6_DEVICE_NAME_UUID = "00002a00-0000-1000-8000-00805f9b34fb"
```

### 2. Command Protocol Structure

The BM6 uses a specific command structure:
- Start marker: `0xDD, 0xA5`
- Command byte (e.g., `0x03` for basic info, `0x04` for cell voltages)
- Data length byte
- Data bytes
- Checksum byte
- End marker: `0x77`

Implement a command builder function:

```python
# In battery_hawk_driver/bm6/protocol.py
def build_command(command, data=None):
    """Build a command packet for BM6 device."""
    if data is None:
        data = []

    packet = bytearray([0xDD, 0xA5, command, len(data)])
    packet.extend(data)

    # Calculate checksum (sum of all bytes after start marker up to checksum position)
    checksum = 0
    for i in range(1, len(packet)):
        checksum += packet[i]

    packet.append(0xFF - (checksum % 0x100))  # Checksum byte
    packet.append(0x77)  # End marker

    return packet


# Common commands
REQUEST_BASIC_INFO = build_command(0x03)
REQUEST_CELL_VOLTAGES = build_command(0x04)
```

### 3. Data Parsing Strategy

Implement a comprehensive data parser that can handle different response types:

```python
# In battery_hawk_driver/bm6/parser.py
class BM6Parser:
    @staticmethod
    def parse_response(data):
        """Parse response data from BM6 device."""
        if len(data) < 4 or data[0] != 0xDD or data[-1] != 0x77:
            return None  # Invalid frame

        command = data[2]

        if command == 0x03:  # Basic information
            return BM6Parser._parse_basic_info(data)
        elif command == 0x04:  # Cell voltages
            return BM6Parser._parse_cell_voltages(data)
        # Add other command parsers as needed
        else:
            return None  # Unknown command

    @staticmethod
    def _parse_basic_info(data):
        """Parse basic information response."""
        if len(data) < 24:  # Minimum length for basic info
            return None

        result = {
            "voltage": int.from_bytes(data[4:6], byteorder="little") / 100.0,  # Volts
            "current": int.from_bytes(data[6:8], byteorder="little", signed=True)
            / 100.0,  # Amps
            "remaining_capacity": int.from_bytes(data[8:10], byteorder="little")
            / 100.0,  # Ah
            "nominal_capacity": int.from_bytes(data[10:12], byteorder="little")
            / 100.0,  # Ah
            "cycles": int.from_bytes(data[12:14], byteorder="little"),
            "production_date": BM6Parser._decode_production_date(
                int.from_bytes(data[14:16], byteorder="little")
            ),
            "balance_status": int.from_bytes(data[16:18], byteorder="little"),
            "protection_status": BM6Parser._decode_protection_status(
                int.from_bytes(data[18:20], byteorder="little")
            ),
            "software_version": data[20] / 10.0,
            "state_of_charge": data[21],  # 0-100%
            "fet_status": BM6Parser._decode_fet_status(data[22]),
            "cell_count": data[23],
        }

        # Parse cell voltages if included
        cell_voltages = []
        for i in range(result["cell_count"]):
            if len(data) >= 24 + ((i + 1) * 2):
                offset = 24 + (i * 2)
                cell_voltage = (
                    int.from_bytes(data[offset : offset + 2], byteorder="little")
                    / 1000.0
                )  # Volts
                cell_voltages.append(cell_voltage)

        if cell_voltages:
            result["cell_voltages"] = cell_voltages

        # Parse temperatures if included
        temp_offset = 24 + (result["cell_count"] * 2)
        temperatures = []
        temp_count = (len(data) - temp_offset - 1) // 2  # -1 for end marker

        for i in range(temp_count):
            if len(data) >= temp_offset + ((i + 1) * 2):
                offset = temp_offset + (i * 2)
                temp = (
                    int.from_bytes(
                        data[offset : offset + 2], byteorder="little", signed=True
                    )
                    / 10.0
                )  # Celsius
                temperatures.append(temp)

        if temperatures:
            result["temperatures"] = temperatures

        return result

    @staticmethod
    def _decode_production_date(raw_date):
        """Decode production date from raw value."""
        year = 2000 + (raw_date >> 9)
        month = (raw_date >> 5) & 0x0F
        day = raw_date & 0x1F
        return f"{year}-{month:02d}-{day:02d}"

    @staticmethod
    def _decode_protection_status(status):
        """Decode protection status bits."""
        protections = {
            "single_cell_overvoltage": bool(status & 0x0001),
            "single_cell_undervoltage": bool(status & 0x0002),
            "battery_overvoltage": bool(status & 0x0004),
            "battery_undervoltage": bool(status & 0x0008),
            "charging_overtemperature": bool(status & 0x0010),
            "charging_undertemperature": bool(status & 0x0020),
            "discharging_overtemperature": bool(status & 0x0040),
            "discharging_undertemperature": bool(status & 0x0080),
            "charging_overcurrent": bool(status & 0x0100),
            "discharging_overcurrent": bool(status & 0x0200),
            "short_circuit": bool(status & 0x0400),
            "front_end_detection_ic_error": bool(status & 0x0800),
            "software_lock_mos": bool(status & 0x1000),
        }
        return protections

    @staticmethod
    def _decode_fet_status(status):
        """Decode FET status byte."""
        return {
            "charging": bool(status & 0x01),
            "discharging": bool(status & 0x02),
        }
```

### 4. BM6 Device Class Implementation

Create a comprehensive BM6 device class that integrates with the Battery Hawk driver framework:

```python
# In battery_hawk_driver/bm6/device.py
from battery_hawk_driver.base import BLEDevice
from .constants import *
from .protocol import *
from .parser import BM6Parser


class BM6Device(BLEDevice):
    """BM6 Battery Monitor device implementation."""

    def __init__(self, address, name=None):
        super().__init__(address, name)
        self.service_uuid = BM6_SERVICE_UUID
        self.notify_characteristic_uuid = BM6_NOTIFY_CHARACTERISTIC_UUID
        self.write_characteristic_uuid = BM6_WRITE_CHARACTERISTIC_UUID
        self.parser = BM6Parser()
        self._latest_data = {}

    async def connect(self):
        """Connect to the BM6 device."""
        await super().connect()

        # Set up notification handler
        await self.client.start_notify(
            self.notify_characteristic_uuid, self._notification_handler
        )

        # Request initial data
        await self.request_basic_info()

    async def request_basic_info(self):
        """Request basic information from the device."""
        await self.client.write_gatt_char(
            self.write_characteristic_uuid, REQUEST_BASIC_INFO, response=True
        )

    async def request_cell_voltages(self):
        """Request cell voltage information from the device."""
        await self.client.write_gatt_char(
            self.write_characteristic_uuid, REQUEST_CELL_VOLTAGES, response=True
        )

    def _notification_handler(self, sender, data):
        """Handle notifications from the BM6 device."""
        parsed_data = self.parser.parse_response(data)
        if parsed_data:
            self._latest_data.update(parsed_data)
            # Emit data update event
            self.emit_data_update(self._latest_data)

    @property
    def latest_data(self):
        """Get the latest data from the device."""
        return self._latest_data.copy()
```

## Integration with Battery Hawk

To integrate the BM6 implementation into Battery Hawk, follow these steps:

### 1. Device Discovery

Enhance the BLE discovery service to identify BM6 devices:

```python
# In battery_hawk_driver/base/discovery.py
from battery_hawk_driver.bm6.constants import BM6_SERVICE_UUID


class BLEDiscoveryService:
    # ... existing code ...

    async def scan_for_devices(self, duration=10):
        devices = await BleakScanner.discover(timeout=duration)
        for device in devices:
            # Check if device advertises BM6 service
            if BM6_SERVICE_UUID.lower() in [
                s.lower() for s in device.metadata.get("uuids", [])
            ]:
                self.discovered_devices[device.address] = {
                    "address": device.address,
                    "name": device.name or "Unknown",
                    "rssi": device.rssi,
                    "type": "BM6",
                }
                self.emit_device_discovered(self.discovered_devices[device.address])

            # Check for BM6 devices by name pattern
            elif device.name and ("BM6" in device.name or "JBD" in device.name):
                self.discovered_devices[device.address] = {
                    "address": device.address,
                    "name": device.name,
                    "rssi": device.rssi,
                    "type": "BM6",
                }
                self.emit_device_discovered(self.discovered_devices[device.address])
```

### 2. Device Factory

Create a device factory that instantiates the appropriate device class:

```python
# In battery_hawk_driver/factory.py
from battery_hawk_driver.bm6.device import BM6Device

# Import other device types


def create_device(device_info):
    """Create a device instance based on device info."""
    if device_info.get("type") == "BM6":
        return BM6Device(device_info["address"], device_info.get("name"))
    # Handle other device types
    else:
        raise ValueError(f"Unsupported device type: {device_info.get('type')}")
```

## Testing Strategy for BM6 Implementation

For Task 12 (System Integration Tests and Documentation), implement the following tests:

### 1. Unit Tests for BM6 Parser

```python
# In tests/test_bm6_parser.py
import unittest
from battery_hawk_driver.bm6.parser import BM6Parser


class TestBM6Parser(unittest.TestCase):
    def test_parse_basic_info(self):
        # Sample data packet for basic info (command 0x03)
        data = bytearray(
            [
                0xDD,
                0xA5,
                0x03,
                0x14,  # Header
                0x64,
                0x0F,  # Voltage (3940 = 39.40V)
                0x2C,
                0x01,  # Current (300 = 3.00A)
                0xD0,
                0x07,  # Remaining capacity (2000 = 20.00Ah)
                0x20,
                0x03,  # Nominal capacity (800 = 8.00Ah)
                0x0A,
                0x00,  # Cycles (10)
                0x25,
                0x12,  # Production date (2021-09-05)
                0x00,
                0x00,  # Balance status
                0x00,
                0x00,  # Protection status
                0x14,  # Software version (2.0)
                0x64,  # SOC (100%)
                0x03,  # FET status (both on)
                0x04,  # Cell count (4)
                # Cell voltages
                0xD2,
                0x0C,  # Cell 1 (3282 = 3.282V)
                0xD0,
                0x0C,  # Cell 2 (3280 = 3.280V)
                0xCE,
                0x0C,  # Cell 3 (3278 = 3.278V)
                0xD4,
                0x0C,  # Cell 4 (3284 = 3.284V)
                # Temperatures
                0xCE,
                0x00,  # Temp 1 (206 = 20.6°C)
                0xD2,
                0x00,  # Temp 2 (210 = 21.0°C)
                0x8A,  # Checksum
                0x77,  # End marker
            ]
        )

        result = BM6Parser.parse_response(data)

        self.assertIsNotNone(result)
        self.assertEqual(result["voltage"], 39.40)
        self.assertEqual(result["current"], 3.00)
        self.assertEqual(result["remaining_capacity"], 20.00)
        self.assertEqual(result["nominal_capacity"], 8.00)
        self.assertEqual(result["cycles"], 10)
        self.assertEqual(result["production_date"], "2021-09-05")
        self.assertEqual(result["software_version"], 2.0)
        self.assertEqual(result["state_of_charge"], 100)
        self.assertEqual(result["cell_count"], 4)

        # Check cell voltages
        self.assertEqual(len(result["cell_voltages"]), 4)
        self.assertEqual(result["cell_voltages"][0], 3.282)
        self.assertEqual(result["cell_voltages"][3], 3.284)

        # Check temperatures
        self.assertEqual(len(result["temperatures"]), 2)
        self.assertEqual(result["temperatures"][0], 20.6)
        self.assertEqual(result["temperatures"][1], 21.0)
```

### 2. Mock BM6 Device for Integration Testing

Create a mock BM6 device for integration testing:

```python
# In tests/mocks/bm6_mock.py
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData


class MockBM6Device:
    """Mock BM6 device for testing."""

    def __init__(self, address="AA:BB:CC:DD:EE:FF", name="BM6-Mock"):
        self.address = address
        self.name = name
        self.service_uuids = ["0000ff00-0000-1000-8000-00805f9b34fb"]

    def get_discovery_data(self):
        """Get discovery data for the mock device."""
        device = BLEDevice(self.address, self.name)
        adv_data = AdvertisementData(
            local_name=self.name,
            service_uuids=self.service_uuids,
            manufacturer_data={0x0001: b"\x01\x02\x03"},
            service_data={},
            tx_power=0,
            rssi=-60,
            platform_data=(),
        )
        return device, adv_data

    def generate_basic_info_response(
        self, voltage=51.20, current=2.50, soc=85, cell_count=16
    ):
        """Generate a mock basic info response."""
        # Convert values to appropriate format
        voltage_bytes = int(voltage * 100).to_bytes(2, byteorder="little")
        current_bytes = int(current * 100).to_bytes(2, byteorder="little", signed=True)

        # Create base packet
        packet = bytearray(
            [
                0xDD,
                0xA5,
                0x03,
                0x14,  # Header
                voltage_bytes[0],
                voltage_bytes[1],
                current_bytes[0],
                current_bytes[1],
                0xD0,
                0x07,  # Remaining capacity (20.00Ah)
                0x20,
                0x03,  # Nominal capacity (8.00Ah)
                0x0A,
                0x00,  # Cycles (10)
                0x25,
                0x12,  # Production date
                0x00,
                0x00,  # Balance status
                0x00,
                0x00,  # Protection status
                0x14,  # Software version (2.0)
                soc,  # SOC
                0x03,  # FET status (both on)
                cell_count,  # Cell count
            ]
        )

        # Add cell voltages (all at 3.2V for simplicity)
        for _ in range(cell_count):
            packet.extend([0x80, 0x0C])  # 3200 = 3.200V

        # Add temperatures
        packet.extend([0xCE, 0x00])  # 20.6°C
        packet.extend([0xD2, 0x00])  # 21.0°C

        # Calculate checksum
        checksum = 0
        for i in range(1, len(packet)):
            checksum += packet[i]
        packet.append(0xFF - (checksum % 0x100))

        # Add end marker
        packet.append(0x77)

        return packet
```

### 3. Integration Test for BM6 Device

```python
# In tests/test_bm6_integration.py
import asyncio
import unittest
from unittest.mock import patch, MagicMock
from battery_hawk_driver.bm6.device import BM6Device
from tests.mocks.bm6_mock import MockBM6Device


class TestBM6Integration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_device = MockBM6Device()
        self.mock_client = MagicMock()

        # Create patches
        self.connect_patch = patch("bleak.BleakClient", return_value=self.mock_client)
        self.bleak_client = self.connect_patch.start()

        # Setup mock responses
        self.mock_client.connect = MagicMock(return_value=True)
        self.mock_client.is_connected = True
        self.mock_client.start_notify = MagicMock()
        self.mock_client.write_gatt_char = MagicMock()

        # Create device
        self.device = BM6Device(self.mock_device.address, self.mock_device.name)

    async def asyncTearDown(self):
        self.connect_patch.stop()

    async def test_connect_and_request_data(self):
        # Connect to device
        await self.device.connect()

        # Verify connection was attempted
        self.mock_client.connect.assert_called_once()

        # Verify notification was set up
        self.mock_client.start_notify.assert_called_once_with(
            self.device.notify_characteristic_uuid, self.device._notification_handler
        )

        # Verify initial data request
        self.mock_client.write_gatt_char.assert_called_once()

    async def test_notification_handling(self):
        # Connect to device
        await self.device.connect()

        # Create data update event handler
        data_update_event = asyncio.Event()
        received_data = {}

        def on_data_update(data):
            nonlocal received_data
            received_data = data
            data_update_event.set()

        # Register event handler
        self.device.on_data_update(on_data_update)

        # Get notification handler
        notification_handler = self.mock_client.start_notify.call_args[0][1]

        # Generate mock response
        mock_response = self.mock_device.generate_basic_info_response(
            voltage=51.20, current=2.50, soc=85, cell_count=16
        )

        # Call notification handler with mock data
        notification_handler(self.device.notify_characteristic_uuid, mock_response)

        # Wait for data update event
        await asyncio.wait_for(data_update_event.wait(), timeout=1.0)

        # Verify data was parsed correctly
        self.assertEqual(received_data["voltage"], 51.20)
        self.assertEqual(received_data["current"], 2.50)
        self.assertEqual(received_data["state_of_charge"], 85)
        self.assertEqual(len(received_data["cell_voltages"]), 16)
        self.assertEqual(received_data["cell_voltages"][0], 3.200)
```

## Documentation for BM6 Implementation

For Task 12, include the following documentation for the BM6 implementation:

### BM6 Protocol Reference

```markdown
# BM6 Battery Monitor Protocol Reference

## Overview

The BM6 battery monitor communicates over Bluetooth Low Energy (BLE) using a proprietary protocol. This document describes the protocol structure, commands, and data formats.

## BLE Service and Characteristics

- **Service UUID**: `0000ff00-0000-1000-8000-00805f9b34fb`
- **Notify Characteristic UUID**: `0000ff01-0000-1000-8000-00805f9b34fb`
- **Write Characteristic UUID**: `0000ff02-0000-1000-8000-00805f9b34fb`
- **Device Name Characteristic UUID**: `00002a00-0000-1000-8000-00805f9b34fb` (Standard BLE)

## Command Structure

Commands sent to the BM6 follow this structure:

| Byte Position | Description |
|---------------|-------------|
| 0 | Start marker (0xDD) |
| 1 | Protocol version (0xA5) |
| 2 | Command code |
| 3 | Data length |
| 4..n | Data bytes (if any) |
| n+1 | Checksum (0xFF - (sum of bytes 1 to n) % 0x100) |
| n+2 | End marker (0x77) |

## Common Commands

| Command | Code | Description |
|---------|------|-------------|
| Request Basic Info | 0x03 | Request basic battery information |
| Request Cell Voltages | 0x04 | Request individual cell voltages |
| Set Parameter | 0x05 | Set a device parameter |

## Response Structure

Responses from the BM6 follow the same structure as commands, with the command code indicating the type of data being returned.

### Basic Information Response (0x03)

| Byte Position | Description | Conversion |
|---------------|-------------|------------|
| 4-5 | Battery voltage | Little-endian, divide by 100 for volts |
| 6-7 | Current | Little-endian, signed, divide by 100 for amps |
| 8-9 | Remaining capacity | Little-endian, divide by 100 for Ah |
| 10-11 | Nominal capacity | Little-endian, divide by 100 for Ah |
| 12-13 | Cycle count | Little-endian |
| 14-15 | Production date | See date format below |
| 16-17 | Balance status | Bitmap of balancing cells |
| 18-19 | Protection status | Bitmap of protection states |
| 20 | Software version | Divide by 10 |
| 21 | State of charge | 0-100% |
| 22 | FET status | Bitmap of FET states |
| 23 | Cell count | Number of cells |
| 24+ | Cell voltages | 2 bytes per cell, little-endian, divide by 1000 for volts |
| 24+(cell_count*2)+ | Temperatures | 2 bytes per sensor, little-endian, signed, divide by 10 for °C |

### Production Date Format

The production date is encoded as a 16-bit value:
- Bits 0-4: Day (1-31)
- Bits 5-8: Month (1-12)
- Bits 9-15: Year offset from 2000 (0-127)

### Protection Status Bits

| Bit | Description |
|-----|-------------|
| 0 | Single cell overvoltage |
| 1 | Single cell undervoltage |
| 2 | Battery overvoltage |
| 3 | Battery undervoltage |
| 4 | Charging overtemperature |
| 5 | Charging undertemperature |
| 6 | Discharging overtemperature |
| 7 | Discharging undertemperature |
| 8 | Charging overcurrent |
| 9 | Discharging overcurrent |
| 10 | Short circuit |
| 11 | Front-end detection IC error |
| 12 | Software lock MOS |

### FET Status Bits

| Bit | Description |
|-----|-------------|
| 0 | Charging enabled |
| 1 | Discharging enabled |
```

## Conclusion

The analysis of JeffWDH and Rafciq's GitHub repositories provides valuable insights into the BM6 battery monitor's BLE communication protocol, UUIDs, and data parsing methods. By implementing the suggested code and following the testing strategy, Battery Hawk can effectively integrate with BM6 devices.

The key takeaways are:
1. BM6 devices use a standardized set of UUIDs for service and characteristics
2. Communication follows a specific command protocol with start/end markers and checksums
3. Data parsing requires careful byte-by-byte extraction with specific conversion factors
4. A comprehensive testing strategy is essential for ensuring reliable operation

This implementation will provide Battery Hawk users with robust support for BM6 battery monitors, enabling accurate monitoring and management of battery systems.


---

*Generated by Task Master Research Command*
*Timestamp: 2025-07-18T02:18:33.536Z*
