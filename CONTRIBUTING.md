# Contributing to Battery Hawk

Thank you for your interest in contributing to Battery Hawk! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- Poetry for dependency management
- Git
- Bluetooth adapter with BLE support (for testing)

### Development Setup

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/battery-hawk.git
   cd battery-hawk
   ```

2. **Install dependencies**:
   ```bash
   poetry install --with dev
   poetry shell
   ```

3. **Install pre-commit hooks**:
   ```bash
   pre-commit install
   ```

4. **Run tests to ensure everything works**:
   ```bash
   pytest
   ```

## 📋 Development Guidelines

### Code Style

We use several tools to maintain code quality:

- **Ruff**: For linting and formatting
- **isort**: For import sorting
- **mypy**: For type checking
- **pytest**: For testing

#### Running Code Quality Checks

```bash
# Linting and formatting
ruff check src/ tests/
ruff format src/ tests/

# Import sorting
isort src/ tests/

# Type checking
mypy src/

# Run all checks
make lint
```

### Coding Standards

1. **Follow PEP 8** style guidelines
2. **Use type hints** for all function parameters and return values
3. **Write docstrings** for all public functions and classes
4. **Add tests** for new functionality
5. **Update documentation** when adding new features

#### Example Code Style

```python
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

def process_device_reading(
    device_id: str,
    reading_data: Dict[str, Any],
    timeout: Optional[float] = None
) -> bool:
    """
    Process a device reading and store it in the database.
    
    Args:
        device_id: MAC address of the device
        reading_data: Dictionary containing reading values
        timeout: Optional timeout for the operation
        
    Returns:
        True if processing was successful, False otherwise
        
    Raises:
        ValidationError: If reading data is invalid
        DatabaseError: If storage operation fails
    """
    logger.info("Processing reading for device %s", device_id)
    
    # Implementation here
    return True
```

### Testing

#### Test Structure

- **Unit tests**: `tests/test_*.py`
- **Integration tests**: `tests/integration/`
- **API tests**: `tests/test_api_*.py`
- **Load tests**: `tests/load/`

#### Writing Tests

```python
import pytest
from unittest.mock import MagicMock

from src.battery_hawk.core.device import DeviceManager

class TestDeviceManager:
    """Test cases for DeviceManager."""
    
    @pytest.fixture
    def mock_bluetooth_adapter(self):
        """Create a mock bluetooth adapter."""
        return MagicMock()
    
    @pytest.fixture
    def device_manager(self, mock_bluetooth_adapter):
        """Create a DeviceManager instance for testing."""
        return DeviceManager(mock_bluetooth_adapter)
    
    def test_device_discovery(self, device_manager):
        """Test device discovery functionality."""
        # Test implementation
        assert device_manager.discover_devices() is not None
```

#### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_api_devices.py

# Run with coverage
pytest --cov=src/battery_hawk --cov-report=html

# Run integration tests
pytest tests/integration/ -m integration
```

### Documentation

#### API Documentation

- API endpoints are automatically documented using Swagger/OpenAPI
- Add docstrings to endpoint functions with parameter descriptions
- Include example requests and responses

#### Code Documentation

- Use Google-style docstrings
- Document all public functions, classes, and modules
- Include type information in docstrings
- Provide usage examples for complex functions

## 🐛 Bug Reports

When reporting bugs, please include:

1. **Clear description** of the issue
2. **Steps to reproduce** the problem
3. **Expected behavior** vs actual behavior
4. **Environment information**:
   - Python version
   - Operating system
   - Bluetooth adapter model
   - Battery monitor device model
5. **Log output** (with DEBUG level if possible)
6. **Configuration** (sanitized, no secrets)

### Bug Report Template

```markdown
## Bug Description
Brief description of the issue

## Steps to Reproduce
1. Step one
2. Step two
3. Step three

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: Ubuntu 22.04
- Python: 3.12.1
- Battery Hawk: v1.0.0
- Device: BM6 v2.1

## Logs
```
[Include relevant log output here]
```

## Configuration
```yaml
[Include sanitized configuration]
```
```

## 💡 Feature Requests

When requesting features, please include:

1. **Clear description** of the feature
2. **Use case** - why is this needed?
3. **Proposed implementation** (if you have ideas)
4. **Alternatives considered**
5. **Additional context**

## 🔄 Pull Request Process

### Before Submitting

1. **Create an issue** first to discuss the change
2. **Fork the repository** and create a feature branch
3. **Write tests** for your changes
4. **Update documentation** if needed
5. **Run the full test suite**
6. **Check code quality** with linting tools

### Pull Request Guidelines

1. **Use a clear title** that describes the change
2. **Reference the issue** number in the description
3. **Describe the changes** made and why
4. **Include testing information**
5. **Update the changelog** if applicable

### Pull Request Template

```markdown
## Description
Brief description of changes

## Related Issue
Fixes #123

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] Changelog updated
```

### Review Process

1. **Automated checks** must pass (CI/CD)
2. **Code review** by maintainers
3. **Testing** on different environments
4. **Documentation review**
5. **Approval** and merge

## 🏗️ Architecture Guidelines

### Project Structure

```
src/battery_hawk/
├── api/                 # REST API implementation
├── core/               # Core business logic
├── drivers/            # Device drivers
├── storage/            # Data storage implementations
├── config/             # Configuration management
└── utils/              # Utility functions

tests/
├── unit/               # Unit tests
├── integration/        # Integration tests
├── api/               # API tests
└── load/              # Load tests
```

### Design Principles

1. **Separation of concerns** - each module has a single responsibility
2. **Dependency injection** - use dependency injection for testability
3. **Interface-based design** - define clear interfaces between components
4. **Error handling** - comprehensive error handling with proper logging
5. **Configuration-driven** - make behavior configurable where appropriate

## 📚 Resources

### Documentation
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [pytest Documentation](https://docs.pytest.org/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Poetry Documentation](https://python-poetry.org/docs/)

### Tools
- [Ruff](https://docs.astral.sh/ruff/) - Linting and formatting
- [mypy](https://mypy.readthedocs.io/) - Type checking
- [pre-commit](https://pre-commit.com/) - Git hooks

## 🤝 Community

- **GitHub Discussions**: For questions and general discussion
- **GitHub Issues**: For bug reports and feature requests
- **Code Reviews**: All contributions are reviewed by maintainers

## 📄 License

By contributing to Battery Hawk, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Battery Hawk! 🔋🦅
