# Battery Hawk Coding Style Guide

This document outlines the coding standards and best practices for the Battery Hawk project to ensure consistent, maintainable, and lint-error-free code.

## Table of Contents

1. [Type Annotations](#type-annotations)
2. [Docstrings](#docstrings)
3. [Logging](#logging)
4. [Error Handling](#error-handling)
5. [Security](#security)
6. [Code Organization](#code-organization)
7. [Testing](#testing)
8. [Common Patterns](#common-patterns)

## Type Annotations

### Required Annotations
- **ALL function arguments** must have type annotations
- **ALL function return types** must be annotated
- Use `from __future__ import annotations` for forward references and PEP 604 unions

```python
from __future__ import annotations


def process_device(
    device_id: str,
    config: dict[str, Any],
    timeout: float = 30.0,
    *args: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """Process device with proper type annotations."""
    pass
```

### Special Cases
- Use `Any` for complex or dynamic types when specific typing is impractical
- Use `NoReturn` for functions that never return (raise exceptions)
- Prefer `list[T]` over `List[T]` (PEP 585)

## Docstrings

### Format Requirements
- **ALL public functions/methods** must have docstrings
- Use **imperative mood** for first line: "Process device data" not "Processes device data"
- Follow Google/NumPy style for parameters and returns

```python
def connect_device(device_id: str, timeout: float = 30.0) -> bool:
    """Connect to the specified device.

    Args:
        device_id: MAC address of the device to connect to
        timeout: Connection timeout in seconds

    Returns:
        True if connection successful, False otherwise

    Raises:
        DeviceConnectionError: If device cannot be reached
    """
    pass
```

## Logging

### Preferred Format
- Use **lazy formatting** with `%` instead of f-strings or `+` concatenation
- Avoid f-strings in logging statements (performance and security)

```python
# ✅ Correct
logger.info("Device %s connected with voltage %s", device_id, voltage)

# ❌ Avoid
logger.info(f"Device {device_id} connected with voltage {voltage}")
logger.info("Device " + device_id + " connected")
```

### Log Levels
- `DEBUG`: Detailed diagnostic information
- `INFO`: General operational messages
- `WARNING`: Something unexpected but recoverable
- `ERROR`: Serious problem that prevented operation
- `CRITICAL`: Very serious error that may abort program

## Error Handling

### Exception Handling
- **Never use bare `except Exception:`** - always specify exception types
- **Always log exceptions** - avoid `try-except-pass`
- Use specific exception types when possible

```python
# ✅ Correct
try:
    result = risky_operation()
except ConnectionError as e:
    logger.warning("Connection failed: %s", e)
    return None
except ValueError as e:
    logger.error("Invalid data: %s", e)
    raise

# ❌ Avoid
try:
    result = risky_operation()
except Exception:
    pass  # Silent failure
```

## Security

### File Paths
- **Never use `/tmp` directly** - use `tempfile` module for temporary files
- Validate all file paths and user inputs
- Use secure defaults for file permissions

```python
# ✅ Correct
import tempfile

with tempfile.TemporaryDirectory() as temp_dir:
    config_path = Path(temp_dir) / "config.json"

# ❌ Avoid
config_path = "/tmp/config.json"  # Security risk
```

### Network Operations
- **Always specify timeouts** for network requests
- Validate URLs and network inputs
- Use HTTPS when possible

```python
# ✅ Correct
response = requests.get(url, timeout=30)

# ❌ Avoid
response = requests.get(url)  # No timeout
```

## Code Organization

### Imports
- Place imports at module level, not inside functions
- Use `from __future__ import annotations` when needed
- Group imports: standard library, third-party, local

### Magic Numbers
- **Replace magic numbers with named constants**
- Use enums for related constants

```python
# ✅ Correct
HTTP_OK = 200
HTTP_NOT_FOUND = 404

if response.status_code == HTTP_OK:
    process_response()

# ❌ Avoid
if response.status_code == 200:  # Magic number
    process_response()
```

### Function Complexity
- Keep functions under 50 statements
- Extract complex logic into smaller functions
- Use descriptive variable names

## Testing

### Test Function Signatures
- Test functions can omit some type annotations (fixtures are often untyped)
- Focus on testing behavior, not implementation details
- Use descriptive test names

```python
def test_device_connection_success(mock_device, mock_config_manager):
    """Test successful device connection."""
    # Test implementation
```

### Fixtures
- Type annotations on fixtures are optional but recommended
- Use meaningful fixture names
- Keep fixtures focused and reusable

## Common Patterns

### Async Functions
```python
async def async_operation(param: str) -> dict[str, Any]:
    """Perform asynchronous operation."""
    try:
        result = await some_async_call(param)
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error("Async operation failed: %s", e)
        return {"status": "error", "message": str(e)}
```

### Configuration Handling
```python
def load_config(config_path: Path) -> dict[str, Any]:
    """Load configuration from file."""
    try:
        with config_path.open() as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("Config file not found: %s", config_path)
        return get_default_config()
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in config: %s", e)
        raise ConfigurationError(f"Invalid config file: {e}")
```

### Signal Handlers
```python
def setup_signal_handler(shutdown_event: asyncio.Event) -> None:
    """Set up signal handlers for graceful shutdown."""

    def signal_handler(signum: int, frame: Any) -> None:
        logger.info("Received signal %s, shutting down", signum)
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
```

## Ruff Configuration

The project uses ruff with specific rules. Key points:

- Examples directory is excluded from strict linting (demonstration code)
- Tests have relaxed annotation requirements
- Core application code follows all rules strictly

## Pre-commit Hooks

Always run `make check` before committing to ensure:
- All linting rules pass
- Type checking passes
- Security scans pass
- Code formatting is consistent

## Quick Reference

### Before Writing Code
1. Add `from __future__ import annotations` if using modern type syntax
2. Plan function signatures with proper type annotations
3. Write docstring first (helps clarify purpose)

### Common Fixes
- `ANN001`: Add type annotation to function argument
- `ANN201`: Add return type annotation
- `D401`: Change docstring to imperative mood
- `G004`: Replace f-string with lazy logging
- `S108`: Use tempfile instead of /tmp
- `PLR2004`: Replace magic number with constant
- `BLE001`: Specify exception type instead of bare Exception

This guide should be referenced when writing new code and used to fix existing linting errors systematically.
