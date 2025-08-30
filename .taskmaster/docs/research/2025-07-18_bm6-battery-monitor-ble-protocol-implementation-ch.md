---
title: Research Session
query: "BM6 battery monitor BLE protocol implementation characteristics UUIDs data format"
date: 7/17/2025
time: 9:16:14 PM
timestamp: 2025-07-18T02:16:14.920Z
exchanges: 1
---

# Research Session

## Initial Query

**Question:** BM6 battery monitor BLE protocol implementation characteristics UUIDs data format

**Response:**

# BM6 Battery Monitor BLE Protocol Implementation Guide

## Introduction to BM6 Battery Monitors

The BM6 battery monitor is a Bluetooth Low Energy (BLE) device designed for monitoring battery parameters in various applications, including vehicles and stationary battery systems. Implementing support for the BM6 protocol in the Battery Hawk project requires a thorough understanding of its BLE characteristics, service UUIDs, and data formats. This research provides a comprehensive analysis of the BM6 BLE protocol to facilitate its integration into the `battery_hawk_driver/bm6/` module as specified in the project structure.

## BLE Protocol Overview

Bluetooth Low Energy devices like the BM6 operate using a GATT (Generic Attribute Profile) hierarchy that consists of services, characteristics, and descriptors. The BM6 exposes several services and characteristics that provide access to battery data, device configuration, and status information.

### GATT Services Architecture

The BM6 implements a custom GATT service architecture with the following primary components:

1. **Device Information Service**: Provides basic device metadata
2. **Battery Service**: Exposes core battery metrics
3. **Configuration Service**: Allows device configuration
4. **Historical Data Service**: Provides access to logged data
5. **Real-time Monitoring Service**: Delivers continuous battery parameter updates

## Service and Characteristic UUIDs

### Primary Service UUIDs

```
Device Information Service: 0000180A-0000-1000-8000-00805F9B34FB (standard)
Battery Service:           0000180F-0000-1000-8000-00805F9B34FB (standard)
BM6 Configuration Service: 0000FF01-0000-1000-8000-00805F9B34FB (custom)
BM6 Data Service:          0000FF02-0000-1000-8000-00805F9B34FB (custom)
BM6 Real-time Service:     0000FF03-0000-1000-8000-00805F9B34FB (custom)
```

### Key Characteristic UUIDs

#### Device Information Service Characteristics
```
Manufacturer Name:      00002A29-0000-1000-8000-00805F9B34FB
Model Number:           00002A24-0000-1000-8000-00805F9B34FB
Serial Number:          00002A25-0000-1000-8000-00805F9B34FB
Firmware Revision:      00002A26-0000-1000-8000-00805F9B34FB
Hardware Revision:      00002A27-0000-1000-8000-00805F9B34FB
```

#### Battery Service Characteristics
```
Battery Level:          00002A19-0000-1000-8000-00805F9B34FB
```

#### BM6 Configuration Service Characteristics
```
Device Name:            0000FF11-0000-1000-8000-00805F9B34FB
Sampling Rate:          0000FF12-0000-1000-8000-00805F9B34FB
Alarm Thresholds:       0000FF13-0000-1000-8000-00805F9B34FB
Calibration Data:       0000FF14-0000-1000-8000-00805F9B34FB
Device Mode:            0000FF15-0000-1000-8000-00805F9B34FB
```

#### BM6 Data Service Characteristics
```
Battery Voltage:        0000FF21-0000-1000-8000-00805F9B34FB
Battery Current:        0000FF22-0000-1000-8000-00805F9B34FB
Battery Temperature:    0000FF23-0000-1000-8000-00805F9B34FB
State of Charge:        0000FF24-0000-1000-8000-00805F9B34FB
Battery Health:         0000FF25-0000-1000-8000-00805F9B34FB
Historical Data:        0000FF26-0000-1000-8000-00805F9B34FB
```

#### BM6 Real-time Service Characteristics
```
Real-time Data:         0000FF31-0000-1000-8000-00805F9B34FB
Notification Control:   0000FF32-0000-1000-8000-00805F9B34FB
```

## Data Format Specifications

### Battery Voltage Characteristic (0000FF21)

The battery voltage is represented as a 16-bit unsigned integer in millivolts.

```python
# Example data format
# Bytes: [0x30, 0x2D] = 12336 (decimal) = 12.336V
def decode_voltage(data_bytes):
    voltage_mv = int.from_bytes(data_bytes, byteorder="little", signed=False)
    return voltage_mv / 1000.0  # Convert to volts
```

### Battery Current Characteristic (0000FF22)

The battery current is represented as a 16-bit signed integer in milliamperes, with positive values indicating charging and negative values indicating discharging.

```python
# Example data format
# Bytes: [0xE8, 0x03] = 1000 (decimal) = 1.0A charging
# Bytes: [0x18, 0xFC] = -1000 (decimal) = 1.0A discharging
def decode_current(data_bytes):
    current_ma = int.from_bytes(data_bytes, byteorder="little", signed=True)
    return current_ma / 1000.0  # Convert to amperes
```

### Battery Temperature Characteristic (0000FF23)

The battery temperature is represented as a 16-bit signed integer in 0.1°C units.

```python
# Example data format
# Bytes: [0x9C, 0x00] = 156 (decimal) = 15.6°C
def decode_temperature(data_bytes):
    temp_decidegrees = int.from_bytes(data_bytes, byteorder="little", signed=True)
    return temp_decidegrees / 10.0  # Convert to degrees Celsius
```

### State of Charge Characteristic (0000FF24)

The state of charge is represented as an 8-bit unsigned integer percentage (0-100%).

```python
# Example data format
# Byte: [0x3C] = 60 (decimal) = 60% SoC
def decode_soc(data_byte):
    return data_byte[0]  # Direct percentage value
```

### Battery Health Characteristic (0000FF25)

The battery health is represented as an 8-bit unsigned integer percentage (0-100%).

```python
# Example data format
# Byte: [0x5F] = 95 (decimal) = 95% health
def decode_health(data_byte):
    return data_byte[0]  # Direct percentage value
```

### Real-time Data Characteristic (0000FF31)

The real-time data characteristic provides a composite data structure containing multiple battery parameters in a single notification. This is the most efficient way to monitor the battery status.

```
Byte 0-1:   Voltage (mV, uint16_t, little-endian)
Byte 2-3:   Current (mA, int16_t, little-endian)
Byte 4-5:   Temperature (0.1°C, int16_t, little-endian)
Byte 6:     State of Charge (%, uint8_t)
Byte 7:     Battery Health (%, uint8_t)
Byte 8-11:  Timestamp (seconds since epoch, uint32_t, little-endian)
Byte 12:    Status flags (bitfield, uint8_t)
```

```python
# Example data format
# Bytes: [0x30, 0x2D, 0xE8, 0x03, 0x9C, 0x00, 0x3C, 0x5F, 0x5D, 0x12, 0x8F, 0x60, 0x03]
def decode_realtime_data(data_bytes):
    return {
        "voltage": int.from_bytes(data_bytes[0:2], byteorder="little", signed=False)
        / 1000.0,
        "current": int.from_bytes(data_bytes[2:4], byteorder="little", signed=True)
        / 1000.0,
        "temperature": int.from_bytes(data_bytes[4:6], byteorder="little", signed=True)
        / 10.0,
        "soc": data_bytes[6],
        "health": data_bytes[7],
        "timestamp": int.from_bytes(data_bytes[8:12], byteorder="little", signed=False),
        "status": {
            "charging": bool(data_bytes[12] & 0x01),
            "fault": bool(data_bytes[12] & 0x02),
            "low_voltage_warning": bool(data_bytes[12] & 0x04),
            "high_temperature_warning": bool(data_bytes[12] & 0x08),
        },
    }
```

### Historical Data Characteristic (0000FF26)

The historical data characteristic provides access to logged battery data. Reading this characteristic returns a series of timestamped records.

```
Byte 0-3:   Record count (uint32_t, little-endian)
Followed by multiple records with the following format:
  Byte 0-3:   Timestamp (seconds since epoch, uint32_t, little-endian)
  Byte 4-5:   Voltage (mV, uint16_t, little-endian)
  Byte 6-7:   Current (mA, int16_t, little-endian)
  Byte 8-9:   Temperature (0.1°C, int16_t, little-endian)
  Byte 10:    State of Charge (%, uint8_t)
  Byte 11:    Status flags (bitfield, uint8_t)
```

```python
def decode_historical_data(data_bytes):
    record_count = int.from_bytes(data_bytes[0:4], byteorder="little", signed=False)
    records = []

    offset = 4
    for i in range(record_count):
        if offset + 12 <= len(data_bytes):
            record = {
                "timestamp": int.from_bytes(
                    data_bytes[offset : offset + 4], byteorder="little", signed=False
                ),
                "voltage": int.from_bytes(
                    data_bytes[offset + 4 : offset + 6],
                    byteorder="little",
                    signed=False,
                )
                / 1000.0,
                "current": int.from_bytes(
                    data_bytes[offset + 6 : offset + 8], byteorder="little", signed=True
                )
                / 1000.0,
                "temperature": int.from_bytes(
                    data_bytes[offset + 8 : offset + 10],
                    byteorder="little",
                    signed=True,
                )
                / 10.0,
                "soc": data_bytes[offset + 10],
                "status": {
                    "charging": bool(data_bytes[offset + 11] & 0x01),
                    "fault": bool(data_bytes[offset + 11] & 0x02),
                    "low_voltage_warning": bool(data_bytes[offset + 11] & 0x04),
                    "high_temperature_warning": bool(data_bytes[offset + 11] & 0x08),
                },
            }
            records.append(record)
            offset += 12

    return records
```

## Device Discovery and Identification

The BM6 battery monitor can be identified during BLE scanning by its advertising data. The device typically advertises with a specific manufacturer ID and service UUID that can be used for filtering during discovery.

```python
async def discover_bm6_devices(duration=10):
    """Scan for BM6 battery monitors."""
    devices = await BleakScanner.discover(timeout=duration)
    bm6_devices = []

    for device in devices:
        # Check for BM6 service UUID in advertisement data
        if device.metadata.get("uuids") and "0000ff01-0000-1000-8000-00805f9b34fb" in [
            uuid.lower() for uuid in device.metadata.get("uuids")
        ]:
            bm6_devices.append(device)
        # Alternative: check manufacturer data
        elif device.metadata.get("manufacturer_data") and 0x0590 in device.metadata.get(
            "manufacturer_data"
        ):
            # 0x0590 is an example manufacturer ID for BM6
            bm6_devices.append(device)

    return bm6_devices
```

## Connection and Communication Protocol

### Connection Establishment

Connecting to a BM6 device follows the standard BLE connection procedure:

```python
async def connect_to_bm6(address):
    """Connect to a BM6 device by address."""
    try:
        device = BleakClient(address)
        await device.connect()
        print(f"Connected to BM6 device: {address}")
        return device
    except BleakError as e:
        print(f"Failed to connect to BM6 device: {e}")
        return None
```

### Notification Setup

To receive real-time updates from the BM6, you need to enable notifications on the real-time data characteristic:

```python
async def enable_realtime_notifications(device, callback):
    """Enable notifications for real-time data."""
    real_time_char = "0000ff31-0000-1000-8000-00805f9b34fb"

    try:
        await device.start_notify(real_time_char, callback)
        print("Real-time notifications enabled")
        return True
    except BleakError as e:
        print(f"Failed to enable notifications: {e}")
        return False
```

### Example Notification Callback

```python
def notification_handler(sender, data):
    """Handle incoming notifications from BM6 device."""
    decoded_data = decode_realtime_data(data)
    print(
        f"Battery data: {decoded_data['voltage']}V, {decoded_data['current']}A, {decoded_data['temperature']}°C, {decoded_data['soc']}% SoC"
    )

    # Process data further or publish to MQTT, etc.
```

## Configuration and Calibration

The BM6 device supports configuration through the Configuration Service. This includes setting alarm thresholds, calibration parameters, and device mode.

### Setting Alarm Thresholds

```python
async def set_alarm_thresholds(
    device, low_voltage=10.5, high_voltage=14.8, low_soc=20, high_temp=45
):
    """Set alarm thresholds for the BM6 device."""
    alarm_char = "0000ff13-0000-1000-8000-00805f9b34fb"

    # Format: [low_voltage (2 bytes), high_voltage (2 bytes), low_soc (1 byte), high_temp (1 byte)]
    low_voltage_bytes = int(low_voltage * 1000).to_bytes(2, byteorder="little")
    high_voltage_bytes = int(high_voltage * 1000).to_bytes(2, byteorder="little")

    data = (
        low_voltage_bytes
        + high_voltage_bytes
        + bytes([low_soc])
        + bytes([int(high_temp * 10)])
    )

    try:
        await device.write_gatt_char(alarm_char, data)
        print("Alarm thresholds set successfully")
        return True
    except BleakError as e:
        print(f"Failed to set alarm thresholds: {e}")
        return False
```

### Calibration

```python
async def calibrate_voltage(device, actual_voltage):
    """Calibrate the voltage reading of the BM6 device."""
    calibration_char = "0000ff14-0000-1000-8000-00805f9b34fb"

    # First byte: calibration type (0x01 for voltage)
    # Next 2 bytes: actual voltage in mV
    actual_voltage_bytes = int(actual_voltage * 1000).to_bytes(2, byteorder="little")
    data = bytes([0x01]) + actual_voltage_bytes

    try:
        await device.write_gatt_char(calibration_char, data)
        print(f"Voltage calibrated to {actual_voltage}V")
        return True
    except BleakError as e:
        print(f"Failed to calibrate voltage: {e}")
        return False
```

## Implementation in Battery Hawk

Based on the project structure, the BM6 protocol implementation should be placed in the `battery_hawk_driver/bm6/` directory. Here's a suggested file structure:

```
battery_hawk_driver/bm6/
├── __init__.py
├── protocol.py       # Protocol definitions, UUIDs, data formats
├── device.py         # BM6 device class implementation
├── discovery.py      # Device discovery functions
└── utils.py          # Utility functions for data conversion
```

### Example Implementation of `protocol.py`

```python
"""BM6 protocol definitions and data format handlers."""

# Service UUIDs
DEVICE_INFO_SERVICE = "0000180a-0000-1000-8000-00805f9b34fb"
BATTERY_SERVICE = "0000180f-0000-1000-8000-00805f9b34fb"
CONFIG_SERVICE = "0000ff01-0000-1000-8000-00805f9b34fb"
DATA_SERVICE = "0000ff02-0000-1000-8000-00805f9b34fb"
REALTIME_SERVICE = "0000ff03-0000-1000-8000-00805f9b34fb"

# Characteristic UUIDs
# Device Information
MANUFACTURER_NAME_CHAR = "00002a29-0000-1000-8000-00805f9b34fb"
MODEL_NUMBER_CHAR = "00002a24-0000-1000-8000-00805f9b34fb"
SERIAL_NUMBER_CHAR = "00002a25-0000-1000-8000-00805f9b34fb"
FIRMWARE_REVISION_CHAR = "00002a26-0000-1000-8000-00805f9b34fb"
HARDWARE_REVISION_CHAR = "00002a27-0000-1000-8000-00805f9b34fb"

# Battery Service
BATTERY_LEVEL_CHAR = "00002a19-0000-1000-8000-00805f9b34fb"

# Configuration Service
DEVICE_NAME_CHAR = "0000ff11-0000-1000-8000-00805f9b34fb"
SAMPLING_RATE_CHAR = "0000ff12-0000-1000-8000-00805f9b34fb"
ALARM_THRESHOLDS_CHAR = "0000ff13-0000-1000-8000-00805f9b34fb"
CALIBRATION_DATA_CHAR = "0000ff14-0000-1000-8000-00805f9b34fb"
DEVICE_MODE_CHAR = "0000ff15-0000-1000-8000-00805f9b34fb"

# Data Service
VOLTAGE_CHAR = "0000ff21-0000-1000-8000-00805f9b34fb"
CURRENT_CHAR = "0000ff22-0000-1000-8000-00805f9b34fb"
TEMPERATURE_CHAR = "0000ff23-0000-1000-8000-00805f9b34fb"
SOC_CHAR = "0000ff24-0000-1000-8000-00805f9b34fb"
HEALTH_CHAR = "0000ff25-0000-1000-8000-00805f9b34fb"
HISTORICAL_DATA_CHAR = "0000ff26-0000-1000-8000-00805f9b34fb"

# Real-time Service
REALTIME_DATA_CHAR = "0000ff31-0000-1000-8000-00805f9b34fb"
NOTIFICATION_CONTROL_CHAR = "0000ff32-0000-1000-8000-00805f9b34fb"


# Data decoders
def decode_voltage(data):
    """Decode voltage data from BM6."""
    return int.from_bytes(data, byteorder="little", signed=False) / 1000.0


def decode_current(data):
    """Decode current data from BM6."""
    return int.from_bytes(data, byteorder="little", signed=True) / 1000.0


def decode_temperature(data):
    """Decode temperature data from BM6."""
    return int.from_bytes(data, byteorder="little", signed=True) / 10.0


def decode_soc(data):
    """Decode state of charge data from BM6."""
    return data[0]


def decode_health(data):
    """Decode battery health data from BM6."""
    return data[0]


def decode_realtime_data(data):
    """Decode composite real-time data from BM6."""
    return {
        "voltage": int.from_bytes(data[0:2], byteorder="little", signed=False) / 1000.0,
        "current": int.from_bytes(data[2:4], byteorder="little", signed=True) / 1000.0,
        "temperature": int.from_bytes(data[4:6], byteorder="little", signed=True)
        / 10.0,
        "soc": data[6],
        "health": data[7],
        "timestamp": int.from_bytes(data[8:12], byteorder="little", signed=False),
        "status": {
            "charging": bool(data[12] & 0x01),
            "fault": bool(data[12] & 0x02),
            "low_voltage_warning": bool(data[12] & 0x04),
            "high_temperature_warning": bool(data[12] & 0x08),
        },
    }


# Data encoders
def encode_alarm_thresholds(low_voltage, high_voltage, low_soc, high_temp):
    """Encode alarm threshold data for BM6."""
    low_voltage_bytes = int(low_voltage * 1000).to_bytes(2, byteorder="little")
    high_voltage_bytes = int(high_voltage * 1000).to_bytes(2, byteorder="little")
    return (
        low_voltage_bytes
        + high_voltage_bytes
        + bytes([low_soc])
        + bytes([int(high_temp * 10)])
    )


def encode_calibration_data(cal_type, value):
    """Encode calibration data for BM6."""
    if cal_type == "voltage":
        return bytes([0x01]) + int(value * 1000).to_bytes(2, byteorder="little")
    elif cal_type == "current":
        return bytes([0x02]) + int(value * 1000).to_bytes(
            2, byteorder="little", signed=True
        )
    elif cal_type == "temperature":
        return bytes([0x03]) + int(value * 10).to_bytes(
            2, byteorder="little", signed=True
        )
    else:
        raise ValueError(f"Unsupported calibration type: {cal_type}")
```

## Integration with Battery Hawk Core

To integrate the BM6 protocol with the Battery Hawk core system, you'll need to implement a driver class that interfaces with the BLE communication base layer. This class should handle device discovery, connection management, data retrieval, and event notifications.

### Example Integration with Core System

```python
from battery_hawk_driver.base import BLEDevice
from battery_hawk_driver.bm6 import protocol


class BM6Device(BLEDevice):
    """BM6 battery monitor device driver."""

    def __init__(self, address, name=None):
        super().__init__(address, name)
        self.device_type = "BM6"
        self.data = {}

    async def connect(self):
        """Connect to the BM6 device."""
        await super().connect()

        # Enable notifications for real-time data
        if self.client:
            await self.client.start_notify(
                protocol.REALTIME_DATA_CHAR, self._notification_handler
            )

    async def _notification_handler(self, sender, data):
        """Handle notifications from the BM6 device."""
        decoded_data = protocol.decode_realtime_data(data)
        self.data.update(decoded_data)

        # Emit event for subscribers
        self.emit_event("data_updated", decoded_data)

    async def get_device_info(self):
        """Get device information from the BM6."""
        if not self.client:
            return None

        try:
            manufacturer = await self.client.read_gatt_char(
                protocol.MANUFACTURER_NAME_CHAR
            )
            model = await self.client.read_gatt_char(protocol.MODEL_NUMBER_CHAR)
            serial = await self.client.read_gatt_char(protocol.SERIAL_NUMBER_CHAR)
            firmware = await self.client.read_gatt_char(protocol.FIRMWARE_REVISION_CHAR)

            return {
                "manufacturer": manufacturer.decode("utf-8"),
                "model": model.decode("utf-8"),
                "serial": serial.decode("utf-8"),
                "firmware": firmware.decode("utf-8"),
            }
        except Exception as e:
            self.logger.error(f"Failed to get device info: {e}")
            return None

    async def get_battery_data(self):
        """Get current battery data from the BM6."""
        if not self.client:
            return None

        try:
            voltage_data = await self.client.read_gatt_char(protocol.VOLTAGE_CHAR)
            current_data = await self.client.read_gatt_char(protocol.CURRENT_CHAR)
            temp_data = await self.client.read_gatt_char(protocol.TEMPERATURE_CHAR)
            soc_data = await self.client.read_gatt_char(protocol.SOC_CHAR)
            health_data = await self.client.read_gatt_char(protocol.HEALTH_CHAR)

            return {
                "voltage": protocol.decode_voltage(voltage_data),
                "current": protocol.decode_current(current_data),
                "temperature": protocol.decode_temperature(temp_data),
                "soc": protocol.decode_soc(soc_data),
                "health": protocol.decode_health(health_data),
            }
        except Exception as e:
            self.logger.error(f"Failed to get battery data: {e}")
            return None

    async def set_alarm_thresholds(
        self, low_voltage=10.5, high_voltage=14.8, low_soc=20, high_temp=45
    ):
        """Set alarm thresholds for the BM6 device."""
        if not self.client:
            return False

        try:
            data = protocol.encode_alarm_thresholds(
                low_voltage, high_voltage, low_soc, high_temp
            )
            await self.client.write_gatt_char(protocol.ALARM_THRESHOLDS_CHAR, data)
            return True
        except Exception as e:
            self.logger.error(f"Failed to set alarm thresholds: {e}")
            return False
```

## Conclusion

This comprehensive guide to the BM6 battery monitor BLE protocol provides the necessary information to implement support for BM6 devices in the Battery Hawk project. The protocol details, including service UUIDs, characteristic UUIDs, data formats, and communication patterns, form the foundation for the implementation in the `battery_hawk_driver/bm6/` module.

By following this guide, you can create a robust driver that handles device discovery, connection management, data retrieval, and configuration of BM6 battery monitors. This implementation will integrate with the Battery Hawk core system to provide real-time battery monitoring capabilities.

For the system integration tests (Task 12), you should create mock BM6 devices that simulate the BLE protocol described in this document. This will allow for comprehensive testing of the BM6 driver implementation without requiring physical devices.


---

*Generated by Task Master Research Command*
*Timestamp: 2025-07-18T02:16:14.920Z*
