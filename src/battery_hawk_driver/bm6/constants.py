"""BM6 protocol constants and UUIDs."""

# Service UUIDs - Updated to match real BM6 protocol
BM6_SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"

# Characteristic UUIDs - Updated to match real BM6 protocol
BM6_NOTIFY_CHARACTERISTIC_UUID = "0000fff4-0000-1000-8000-00805f9b34fb"
BM6_WRITE_CHARACTERISTIC_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"
BM6_DEVICE_NAME_UUID = (
    "00002a00-0000-1000-8000-00805f9b34fb"  # Standard BLE Device Name
)

# AES Encryption key for BM6 protocol
# Key: "legend" + 0xFF + 0xFE + "0100009"
BM6_AES_KEY = bytes(
    [108, 101, 97, 103, 101, 110, 100, 255, 254, 48, 49, 48, 48, 48, 48, 57],
)

# Real BM6 commands
CMD_REQUEST_VOLTAGE_TEMP = "d15507"  # Request voltage and temperature data

# Data parsing constants
VOLTAGE_CONVERSION_FACTOR = 100.0  # Divide by 100 for volts
TEMPERATURE_CONVERSION_FACTOR = 10.0  # Divide by 10 for Celsius
TEMPERATURE_SIGN_BIT = 0x01  # Bit indicating negative temperature

# Response patterns
VOLTAGE_PATTERN = "55aa"  # Start of voltage data
TEMPERATURE_PATTERN = "55bb"  # Start of temperature data
SOC_PATTERN = "55cc"  # Start of state of charge data

# Legacy protocol constants (kept for backward compatibility)
CMD_REQUEST_BASIC_INFO = 0x03
CMD_REQUEST_CELL_VOLTAGES = 0x04
CMD_SET_PARAMETER = 0x05

# Protocol markers
START_MARKER = 0xDD
PROTOCOL_VERSION = 0xA5
END_MARKER = 0x77

# Data conversion factors
CURRENT_CONVERSION_FACTOR = 100.0  # Divide by 100 for amps
CAPACITY_CONVERSION_FACTOR = 100.0  # Divide by 100 for Ah
CELL_VOLTAGE_CONVERSION_FACTOR = 1000.0  # Divide by 1000 for volts
SOFTWARE_VERSION_CONVERSION_FACTOR = 10.0  # Divide by 10 for version

# Minimum data lengths
MIN_BASIC_INFO_LENGTH = 24
MIN_CELL_VOLTAGES_LENGTH = 6
MIN_NOTIFICATION_LENGTH = 20
MIN_RESPONSE_LENGTH = 4
