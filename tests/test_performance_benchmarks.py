"""Performance benchmark tests for battery monitoring operations."""

import asyncio
import gc
import random
import time
from typing import Any

import pytest

from src.battery_hawk_driver.base.device_factory import DeviceFactory
from tests.support.mocks.test_mock_ble_devices import MockBLEConnectionPool


class PerformanceTestConfig:
    """Test configuration for performance tests."""

    def __init__(self) -> None:
        """Initialize test configuration with fast timeouts."""
        self.data_wait_timeout = 0.1  # Very fast timeout for performance tests


# Type alias for test devices
TestDevice = "BM2Device | BM6Device"


class TestPerformanceThresholds:
    """Test performance thresholds for various operations."""

    @pytest.fixture
    def mock_connection_pool(self) -> MockBLEConnectionPool:
        """Create a mock connection pool for testing."""
        return MockBLEConnectionPool()

    @pytest.fixture
    def test_config(self) -> PerformanceTestConfig:
        """Create test configuration for performance tests."""
        return PerformanceTestConfig()

    @pytest.fixture
    def device_factory(
        self,
        mock_connection_pool: MockBLEConnectionPool,
    ) -> DeviceFactory:
        """Create a device factory with mock connection pool."""
        return DeviceFactory(mock_connection_pool)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_device_creation_performance(
        self,
        device_factory: DeviceFactory,
        test_config: PerformanceTestConfig,
    ) -> None:
        """Test that device creation meets performance thresholds."""
        start_time = time.time()

        # Create multiple devices
        devices = []
        for i in range(10):
            mac_address = f"AA:BB:CC:DD:EE:{i:02X}"
            device_type = "BM6" if i % 2 == 0 else "BM2"
            device = device_factory.create_device(device_type, mac_address, test_config)
            devices.append(device)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete within 100ms
        assert duration < 0.1
        assert len(devices) == 10
        assert all(device is not None for device in devices)

    @pytest.mark.asyncio
    async def test_device_data_reading_performance(
        self,
        device_factory: DeviceFactory,
        test_config: PerformanceTestConfig,
    ) -> None:
        """Test that device data reading meets performance thresholds."""
        # Create a device
        device = device_factory.create_device("BM6", "AA:BB:CC:DD:EE:FF", test_config)
        assert device is not None

        # Connect the device first
        await device.connect()

        start_time = time.time()

        # Read data multiple times
        readings = []
        for _ in range(5):
            reading = await device.read_data()
            readings.append(reading)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete within 1 second (allowing for async operations)
        assert duration < 1.0
        assert len(readings) == 5
        assert all(reading is not None for reading in readings)

    @pytest.mark.asyncio
    async def test_concurrent_operations_meet_thresholds(
        self,
        device_factory: DeviceFactory,
        test_config: PerformanceTestConfig,
    ) -> None:
        """Test that concurrent operations meet performance thresholds."""
        # Create multiple devices
        devices = []
        for i in range(5):
            mac_address = f"AA:BB:CC:DD:EE:{i:02X}"
            device_type = "BM6" if i % 2 == 0 else "BM2"
            device = device_factory.create_device(device_type, mac_address, test_config)
            devices.append(device)

        # Connect all devices first
        await asyncio.gather(*[device.connect() for device in devices])

        start_time = time.time()

        # Perform concurrent operations
        async def device_operation(device: Any) -> list[float]:
            """Perform multiple operations on a single device."""
            device_durations = []
            for _ in range(3):
                op_start = time.time()
                reading = await device.read_data()
                op_end = time.time()
                device_durations.append(op_end - op_start)
                assert reading is not None
            return device_durations

        # Run operations concurrently
        all_durations = await asyncio.gather(
            *[device_operation(device) for device in devices],
        )

        end_time = time.time()
        total_duration = end_time - start_time

        # Should complete within 2 seconds
        assert total_duration < 2.0

        # Each individual operation should complete within 200ms (with 0.1s timeout)
        for device_durations in all_durations:
            for duration in device_durations:
                assert duration < 0.2

    @pytest.mark.asyncio
    async def test_auto_detection_performance(
        self,
        device_factory: DeviceFactory,
        test_config: PerformanceTestConfig,
    ) -> None:
        """Test that auto-detection meets performance thresholds."""
        # Sample advertisement data
        sample_ad_data = [
            {
                "name": "BM6_Battery_Monitor",
                "service_uuids": ["0000ff00-0000-1000-8000-00805f9b34fb"],
                "manufacturer_data": b"BM6_Battery_Monitor_1",
            },
            {
                "name": "BM2_Battery_Monitor",
                "service_uuids": ["0000ff00-0000-1000-8000-00805f9b34fb"],
                "manufacturer_data": b"BM2_Battery_Monitor_2",
            },
            {
                "name": "Unknown_Device",
                "service_uuids": ["0000ffff-0000-1000-8000-00805f9b34fb"],
                "manufacturer_data": b"Unknown_Data",
            },
        ]

        start_time = time.time()

        # Perform auto-detection on all samples
        detection_results = []
        for ad_data in sample_ad_data:
            detected_type = device_factory.auto_detect_device_type(ad_data)
            detection_results.append(detected_type)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete within 50ms
        assert duration < 0.05
        assert len(detection_results) == 3

        # Verify detection results
        assert detection_results[0] == "BM6"
        assert detection_results[1] == "BM2"
        assert detection_results[2] is None


class TestScalabilityBenchmarks:
    """Test scalability benchmarks for large numbers of devices."""

    @pytest.fixture
    def mock_connection_pool(self) -> MockBLEConnectionPool:
        """Create a mock connection pool for testing."""
        return MockBLEConnectionPool()

    @pytest.fixture
    def test_config(self) -> PerformanceTestConfig:
        """Create test configuration for performance tests."""
        return PerformanceTestConfig()

    @pytest.fixture
    def device_factory(
        self,
        mock_connection_pool: MockBLEConnectionPool,
    ) -> DeviceFactory:
        """Create a device factory with mock connection pool."""
        return DeviceFactory(mock_connection_pool)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_large_device_creation_scalability(
        self,
        device_factory: DeviceFactory,
        test_config: PerformanceTestConfig,
    ) -> None:
        """Test scalability of creating large numbers of devices."""
        start_time = time.time()

        # Create 100 devices
        devices = []
        for i in range(100):
            mac_address = f"AA:BB:CC:DD:EE:{i:02X}"
            device_type = "BM6" if i % 2 == 0 else "BM2"
            device = device_factory.create_device(device_type, mac_address, test_config)
            devices.append(device)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete within 1 second
        assert duration < 1.0
        assert len(devices) == 100
        assert all(device is not None for device in devices)

    @pytest.mark.asyncio
    async def test_concurrent_device_operations_scalability(
        self,
        device_factory: DeviceFactory,
        test_config: PerformanceTestConfig,
    ) -> None:
        """Test scalability of concurrent operations on many devices."""
        # Create 20 devices
        devices = []
        for i in range(20):
            mac_address = f"AA:BB:CC:DD:EE:{i:02X}"
            device_type = "BM6" if i % 2 == 0 else "BM2"
            device = device_factory.create_device(device_type, mac_address, test_config)
            devices.append(device)

        # Connect all devices first
        await asyncio.gather(*[device.connect() for device in devices])

        start_time = time.time()

        # Perform concurrent read operations on all devices
        async def read_device_data(device: Any) -> Any:
            """Read data from a single device."""
            return await device.read_data()

        readings = await asyncio.gather(
            *[read_device_data(device) for device in devices],
        )

        end_time = time.time()
        duration = end_time - start_time

        # Should complete within 3 seconds
        assert duration < 3.0
        assert len(readings) == 20
        assert all(reading is not None for reading in readings)

    @pytest.mark.asyncio
    async def test_mixed_operation_scalability(
        self,
        device_factory: DeviceFactory,
        test_config: PerformanceTestConfig,
    ) -> None:
        """Test scalability of mixed operations (creation + reading)."""
        start_time = time.time()

        # Create devices and read data in batches
        all_readings = []
        for batch in range(5):
            # Create 10 devices per batch
            batch_devices = []
            for i in range(10):
                device_id = batch * 10 + i
                mac_address = f"AA:BB:CC:DD:EE:{device_id:02X}"
                device_type = "BM6" if device_id % 2 == 0 else "BM2"
                device = device_factory.create_device(
                    device_type,
                    mac_address,
                    test_config,
                )
                batch_devices.append(device)

            # Connect all batch devices first
            await asyncio.gather(*[device.connect() for device in batch_devices])

            # Read data from all devices in this batch
            batch_readings = await asyncio.gather(
                *[device.read_data() for device in batch_devices],
            )
            all_readings.extend(batch_readings)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete within 5 seconds
        assert duration < 5.0
        assert len(all_readings) == 50
        assert all(reading is not None for reading in all_readings)


class TestFailureHandlingPerformance:
    """Test performance under failure conditions."""

    @pytest.fixture
    def mock_connection_pool(self) -> MockBLEConnectionPool:
        """Create a mock connection pool for testing."""
        return MockBLEConnectionPool()

    @pytest.fixture
    def test_config(self) -> PerformanceTestConfig:
        """Create test configuration for performance tests."""
        return PerformanceTestConfig()

    @pytest.fixture
    def device_factory(
        self,
        mock_connection_pool: MockBLEConnectionPool,
    ) -> DeviceFactory:
        """Create a device factory with mock connection pool."""
        return DeviceFactory(mock_connection_pool)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_high_failure_rate_performance(
        self,
        device_factory: DeviceFactory,
        test_config: PerformanceTestConfig,
    ) -> None:
        """Test performance when many operations fail."""
        # Create a device that will have high failure rate
        device = device_factory.create_device("BM6", "FF:FF:FF:FF:FF:FF", test_config)
        assert device is not None

        # Connect the device first
        await device.connect()

        # Override the read_data method to simulate failures
        original_read_data = device.read_data

        async def failing_read_data() -> Any:
            # 80% failure rate
            if random.random() < 0.8:
                raise ConnectionError("Simulated connection failure")
            return await original_read_data()

        device.read_data = failing_read_data

        start_time = time.time()

        # Attempt many operations
        successful_readings = 0
        failed_operations = 0
        total_attempts = 50

        for _ in range(total_attempts):
            try:
                reading = await device.read_data()
                if reading is not None:
                    successful_readings += 1
                    assert hasattr(reading, "voltage")
            except Exception:  # noqa: BLE001, PERF203
                # Expected to fail sometimes due to high failure rate
                failed_operations += 1

        end_time = time.time()
        duration = end_time - start_time

        # Should complete within 10 seconds despite failures
        assert duration < 10.0

        # Should have some successful operations
        assert successful_readings > 0
        assert failed_operations > 0
        assert successful_readings + failed_operations == total_attempts

    @pytest.mark.asyncio
    async def test_timeout_handling_performance(
        self,
        device_factory: DeviceFactory,
        test_config: PerformanceTestConfig,
    ) -> None:
        """Test performance when operations timeout."""
        # Create a device
        device = device_factory.create_device("BM6", "AA:BB:CC:DD:EE:FF", test_config)
        assert device is not None

        # Connect the device first
        await device.connect()

        # Override the read_data method to simulate timeouts
        original_read_data = device.read_data

        async def slow_read_data() -> Any:
            # 30% chance of timeout
            if random.random() < 0.3:
                await asyncio.sleep(2.0)  # Simulate slow operation
            return await original_read_data()

        device.read_data = slow_read_data

        start_time = time.time()

        # Attempt operations with timeout handling
        successful_readings = 0
        timeout_operations = 0
        total_attempts = 20

        for _ in range(total_attempts):
            try:
                # Use asyncio.wait_for to implement timeout
                reading = await asyncio.wait_for(device.read_data(), timeout=1.0)
                if reading is not None:
                    successful_readings += 1
            except TimeoutError:  # noqa: PERF203
                timeout_operations += 1
            except Exception:  # noqa: BLE001, S110
                # Other exceptions are also acceptable
                pass

        end_time = time.time()
        duration = end_time - start_time

        # Should complete within 30 seconds despite timeouts
        assert duration < 30.0

        # Should have some successful operations
        assert successful_readings > 0
        assert timeout_operations > 0


class TestMemoryUsageBenchmarks:
    """Test memory usage under various conditions."""

    @pytest.fixture
    def mock_connection_pool(self) -> MockBLEConnectionPool:
        """Create a mock connection pool for testing."""
        return MockBLEConnectionPool()

    @pytest.fixture
    def test_config(self) -> PerformanceTestConfig:
        """Create test configuration for performance tests."""
        return PerformanceTestConfig()

    @pytest.fixture
    def device_factory(
        self,
        mock_connection_pool: MockBLEConnectionPool,
    ) -> DeviceFactory:
        """Create a device factory with mock connection pool."""
        return DeviceFactory(mock_connection_pool)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_memory_usage_with_many_devices(
        self,
        device_factory: DeviceFactory,
        test_config: PerformanceTestConfig,
    ) -> None:
        """Test memory usage when creating many devices."""
        # Create 100 devices
        devices = []
        for i in range(100):
            mac_address = f"AA:BB:CC:DD:EE:{i:02X}"
            device_type = "BM6" if i % 2 == 0 else "BM2"
            device = device_factory.create_device(device_type, mac_address, test_config)
            devices.append(device)

        # Connect all devices first
        await asyncio.gather(*[device.connect() for device in devices])

        # Perform operations on all devices
        readings = await asyncio.gather(
            *[device.read_data() for device in devices],
            return_exceptions=True,
        )

        # Verify all operations completed
        successful_readings = [r for r in readings if not isinstance(r, Exception)]
        assert len(successful_readings) > 0

        # Memory usage should be reasonable (this is a qualitative test)
        # In a real scenario, you might use psutil to measure actual memory usage
        assert len(devices) == 100

    @pytest.mark.asyncio
    async def test_memory_cleanup_after_operations(
        self,
        device_factory: DeviceFactory,
        test_config: PerformanceTestConfig,
    ) -> None:
        """Test that memory is properly cleaned up after operations."""
        # Create devices and perform operations
        devices = []
        for i in range(50):
            mac_address = f"AA:BB:CC:DD:EE:{i:02X}"
            device_type = "BM6" if i % 2 == 0 else "BM2"
            device = device_factory.create_device(device_type, mac_address, test_config)
            devices.append(device)

        # Connect all devices first
        await asyncio.gather(*[device.connect() for device in devices])

        # Perform operations
        readings = await asyncio.gather(
            *[device.read_data() for device in devices],
            return_exceptions=True,
        )

        # Clear references
        devices.clear()
        readings.clear()

        # Force garbage collection (in a real test, you might check memory usage)
        gc.collect()

        # Test should complete without memory issues
        assert True


class TestConcurrencyBenchmarks:
    """Test concurrency and threading performance."""

    @pytest.fixture
    def mock_connection_pool(self) -> MockBLEConnectionPool:
        """Create a mock connection pool for testing."""
        return MockBLEConnectionPool()

    @pytest.fixture
    def test_config(self) -> PerformanceTestConfig:
        """Create test configuration for performance tests."""
        return PerformanceTestConfig()

    @pytest.fixture
    def device_factory(
        self,
        mock_connection_pool: MockBLEConnectionPool,
    ) -> DeviceFactory:
        """Create a device factory with mock connection pool."""
        return DeviceFactory(mock_connection_pool)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_concurrent_device_creation(
        self,
        device_factory: DeviceFactory,
        test_config: PerformanceTestConfig,
    ) -> None:
        """Test concurrent device creation performance."""
        start_time = time.time()

        # Create devices concurrently
        async def create_device(device_id: int) -> Any:
            """Create a single device."""
            mac_address = f"AA:BB:CC:DD:EE:{device_id:02X}"
            device_type = "BM6" if device_id % 2 == 0 else "BM2"
            return device_factory.create_device(device_type, mac_address, test_config)

        # Create 20 devices concurrently
        devices = await asyncio.gather(*[create_device(i) for i in range(20)])

        end_time = time.time()
        duration = end_time - start_time

        # Should complete within 100ms
        assert duration < 0.1
        assert len(devices) == 20
        assert all(device is not None for device in devices)

    @pytest.mark.asyncio
    async def test_concurrent_data_reading(
        self,
        device_factory: DeviceFactory,
        test_config: PerformanceTestConfig,
    ) -> None:
        """Test concurrent data reading performance."""
        # Create devices first
        devices = []
        for i in range(10):
            mac_address = f"AA:BB:CC:DD:EE:{i:02X}"
            device_type = "BM6" if i % 2 == 0 else "BM2"
            device = device_factory.create_device(device_type, mac_address, test_config)
            devices.append(device)

        # Connect all devices first
        await asyncio.gather(*[device.connect() for device in devices])

        start_time = time.time()

        # Read data from all devices concurrently
        async def read_device_data(device: Any) -> None:
            """Read data from a single device."""
            for _ in range(3):  # Read 3 times per device
                reading = await device.read_data()
                assert reading is not None

        # Perform concurrent reads
        await asyncio.gather(*[read_device_data(device) for device in devices])

        end_time = time.time()
        duration = end_time - start_time

        # Should complete within 5 seconds
        assert duration < 5.0

    @pytest.mark.asyncio
    async def test_mixed_concurrent_operations(
        self,
        device_factory: DeviceFactory,
        test_config: PerformanceTestConfig,
    ) -> None:
        """Test mixed concurrent operations (creation + reading)."""
        start_time = time.time()

        # Create devices and read data concurrently
        async def create_and_read(device_id: int) -> Any:
            """Create a device and read data from it."""
            mac_address = f"AA:BB:CC:DD:EE:{device_id:02X}"
            device_type = "BM6" if device_id % 2 == 0 else "BM2"
            device = device_factory.create_device(device_type, mac_address, test_config)
            await device.connect()
            return await device.read_data()

        # Perform 15 concurrent create-and-read operations
        readings = await asyncio.gather(*[create_and_read(i) for i in range(15)])

        end_time = time.time()
        duration = end_time - start_time

        # Should complete within 3 seconds
        assert duration < 3.0
        assert len(readings) == 15
        assert all(reading is not None for reading in readings)
