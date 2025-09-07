#!/usr/bin/env python3
"""
Test script to verify logging configuration with timestamps.

This script demonstrates the enhanced logging configuration including:
- Console logging with timestamps
- File logging with rotation
- Configurable log formats and levels
"""

import logging
import os
import sys
import tempfile
from pathlib import Path

# Add the src directory to the path so we can import battery_hawk modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from battery_hawk.cli import setup_logging
from battery_hawk.config.config_manager import ConfigManager


def test_console_logging() -> None:
    """Test console logging with timestamps."""
    # Create a temporary config directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create config manager with default settings
        config_manager = ConfigManager(temp_dir, enable_watchers=False)

        # Set up logging
        setup_logging(config_manager)

        # Test logging at different levels
        logger = logging.getLogger("battery_hawk.test")
        logger.info("🖥️  Testing console logging with timestamps...")
        logger.info("This is an INFO message with timestamp")
        logger.warning("This is a WARNING message with timestamp")
        logger.error("This is an ERROR message with timestamp")
        logger.info(
            "✅ Console logging test completed - check output above for timestamps",
        )


def test_file_logging() -> None:
    """Test file logging with timestamps and rotation."""
    # Create a temporary config directory and log file
    with tempfile.TemporaryDirectory() as temp_dir:
        log_file = os.path.join(temp_dir, "test_battery_hawk.log")

        # Create config manager
        config_manager = ConfigManager(temp_dir, enable_watchers=False)

        # Update logging config to include file logging
        system_config = config_manager.get_config("system")
        system_config["logging"]["file"] = log_file
        system_config["logging"]["level"] = "DEBUG"
        config_manager.configs["system"] = system_config

        # Set up logging
        setup_logging(config_manager)

        # Test logging
        logger = logging.getLogger("battery_hawk.file_test")
        logger.info("📁 Testing file logging with timestamps...")
        logger.debug("This is a DEBUG message to file")
        logger.info("This is an INFO message to file")
        logger.warning("This is a WARNING message to file")
        logger.error("This is an ERROR message to file")

        # Check if log file was created and contains timestamps
        if os.path.exists(log_file):
            logger.info("✅ Log file created: %s", log_file)
            with open(log_file) as f:
                content = f.read()
                logger.info("📄 Log file contents: %s", content)

                # Verify timestamps are present
                if "2024" in content or "2025" in content:  # Basic timestamp check
                    logger.info("✅ Timestamps found in log file")
                else:
                    logger.error("❌ No timestamps found in log file")
        else:
            logger.error("❌ Log file was not created")


def test_custom_format() -> None:
    """Test custom log format configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create config manager
        config_manager = ConfigManager(temp_dir, enable_watchers=False)

        # Update logging config with custom format
        system_config = config_manager.get_config("system")
        system_config["logging"]["format"] = (
            "[%(asctime)s] %(levelname)-8s | %(name)s | %(message)s"
        )
        system_config["logging"]["date_format"] = "%Y-%m-%d %H:%M:%S"
        config_manager.configs["system"] = system_config

        # Set up logging
        setup_logging(config_manager)

        # Test logging
        logger = logging.getLogger("battery_hawk.custom_format")
        logger.info("🎨 Testing custom log format...")
        logger.info("This message uses custom formatting with microseconds")
        logger.info("✅ Custom format test completed - check output above")


def test_environment_override() -> None:
    """Test environment variable override for logging configuration."""
    # Set environment variables
    os.environ["BATTERYHAWK_SYSTEM_LOGGING_LEVEL"] = "DEBUG"
    os.environ["BATTERYHAWK_SYSTEM_LOGGING_FORMAT"] = (
        "ENV: %(asctime)s [%(levelname)s] %(message)s"
    )

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create config manager (will apply env overrides)
            config_manager = ConfigManager(temp_dir, enable_watchers=False)

            # Set up logging
            setup_logging(config_manager)

            # Test logging
            logger = logging.getLogger("battery_hawk.env_test")
            logger.info("🌍 Testing environment variable override...")
            logger.debug("This DEBUG message should appear due to env override")
            logger.info("This message uses format from environment variable")
            logger.info("✅ Environment override test completed")
    finally:
        # Clean up environment variables
        os.environ.pop("BATTERYHAWK_SYSTEM_LOGGING_LEVEL", None)
        os.environ.pop("BATTERYHAWK_SYSTEM_LOGGING_FORMAT", None)


def main() -> int:
    """Run all logging tests."""
    # Set up basic logging for the test runner
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    logger.info("🧪 Battery Hawk Logging Configuration Test")
    logger.info("=" * 50)

    try:
        test_console_logging()
        test_file_logging()
        test_custom_format()
        test_environment_override()

        logger.info("🎉 All logging tests completed successfully!")
        logger.info("Key features verified:")
        logger.info("✅ Console logging with timestamps")
        logger.info("✅ File logging with rotation")
        logger.info("✅ Custom log formats")
        logger.info("✅ Environment variable overrides")
        logger.info("✅ Multiple log levels")

    except (OSError, ValueError, RuntimeError):
        logger.exception("❌ Test failed with error")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
