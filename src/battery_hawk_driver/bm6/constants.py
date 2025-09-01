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

# Real BM6 commands - must be 16 bytes (32 hex chars) for AES encryption
CMD_REQUEST_VOLTAGE_TEMP = (
    "d1550700000000000000000000000000"  # Request voltage and temperature data
)
CMD_REQUEST_VERSION = (  # Request device version
    "d1550100000000000000000000000000"
)

# Data parsing constants
VOLTAGE_CONVERSION_FACTOR = 100.0  # Divide by 100 for volts
TEMPERATURE_CONVERSION_FACTOR = (
    10.0  # Divide by 10 for Celsius (decidegrees to degrees)
)
TEMPERATURE_SIGN_BIT = 0x01  # Bit indicating negative temperature

# BM6 response format positions (in hex string)
BM6_REALTIME_RESPONSE_PREFIX = "d15507"  # Response starts with this
BM6_VERSION_RESPONSE_PREFIX = "d15501"  # Response starts with this
VOLTAGE_POSITION_START = 14
VOLTAGE_POSITION_END = 18
TEMPERATURE_SIGN_POSITION_START = 6
TEMPERATURE_SIGN_POSITION_END = 8
TEMPERATURE_POSITION_START = 8
TEMPERATURE_POSITION_END = 10
SOC_POSITION_START = 12
SOC_POSITION_END = 14
STATE_POSITION_START = 10
STATE_POSITION_END = 12
RAPID_ACCELERATION_POSITION_START = 18
RAPID_ACCELERATION_POSITION_END = 22
RAPID_DECELERATION_POSITION_START = 22
RAPID_DECELERATION_POSITION_END = 26

# Wait time for data responses (configurable)
DEFAULT_DATA_WAIT_TIMEOUT = 5.0  # seconds to wait for data response

# AES encryption constants
BM6_AES_BLOCK_SIZE = 16  # BM6 protocol uses exactly 16-byte blocks

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
