#!/usr/bin/env python3
"""
Example demonstrating Battery Hawk API integration with core engine.

This example shows how to initialize and start the BatteryHawkAPI
alongside the core monitoring engine.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import tempfile
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from battery_hawk.api.api import BatteryHawkAPI
from battery_hawk.config.config_manager import ConfigManager
from battery_hawk.core.engine import BatteryHawkCore


async def main() -> int:
    """Demonstrate API integration with core engine."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("api_example")

    # Initialize variables for cleanup
    api = None
    core_engine = None

    try:
        # Initialize configuration manager
        # In a real deployment, this would point to /data
        with tempfile.TemporaryDirectory(prefix="battery_hawk_example_") as config_dir:
            logger.info("Initializing configuration manager...")
            config_manager = ConfigManager(config_dir)

            # Initialize core engine
            logger.info("Initializing core engine...")
            core_engine = BatteryHawkCore(config_manager)

            # Initialize API
            logger.info("Initializing API...")
            api = BatteryHawkAPI(config_manager, core_engine)

            # Start API server
            logger.info("Starting API server...")
            api.start()

            # In a real application, you would also start the core engine:
            # await core_engine.start()

            logger.info("API server started successfully!")
            logger.info("Try accessing:")
            logger.info("  - Health check: http://localhost:5000/api/health")
            logger.info("  - Version info: http://localhost:5000/api/version")
            logger.info("Press Ctrl+C to stop...")

            # Setup signal handler for graceful shutdown
            shutdown_event = asyncio.Event()

            def signal_handler(signum: int, _frame: object) -> None:
                logger.info("Received shutdown signal %s", signum)
                shutdown_event.set()

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            # Wait for shutdown signal
            await shutdown_event.wait()

    except Exception:
        logger.exception("Error in API example")
        return 1

    finally:
        # Cleanup
        logger.info("Shutting down...")
        if api is not None:
            api.stop()
        if core_engine is not None:
            await core_engine.stop()
        logger.info("Shutdown complete")

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        sys.exit(0)
